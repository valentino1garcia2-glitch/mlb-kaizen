"""SQLite persistence that never rewrites a historical prediction."""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
from datetime import UTC, date, datetime
from enum import Enum
from contextlib import contextmanager
import json
from pathlib import Path
import sqlite3
from typing import Any
from uuid import uuid4

from mlb_kaizen.domain.models import (
    Game, GameLineups, GameWeather, InferenceFeatureSnapshot, ProbablePitcher,
    TeamRunProfile, TeamSeasonStats,
)
from mlb_kaizen.storage.migrations import MIGRATIONS


def _json_default(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value):
        return asdict(value)
    raise TypeError(f"cannot serialise {type(value)!r}")


class KaizenDatabase:
    """Local database that can later be mapped to a server-side relational store."""

    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path

    def initialise(self) -> None:
        """Apply every migration that has not run yet, in order, exactly once.

        Safe to call on an empty file, an already-migrated database, or one
        created before this module existed (migration 1 mirrors that legacy
        schema with CREATE TABLE IF NOT EXISTS, so it is a no-op there and is
        simply recorded as applied).
        """

        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connection() as connection:
            connection.execute(
                """CREATE TABLE IF NOT EXISTS schema_migrations (
                       version INTEGER PRIMARY KEY,
                       description TEXT NOT NULL,
                       applied_at TEXT NOT NULL
                   )"""
            )
            applied = {
                row[0] for row in connection.execute("SELECT version FROM schema_migrations").fetchall()
            }
            for migration in MIGRATIONS:
                if migration.version in applied:
                    continue
                connection.executescript(migration.sql)
                connection.execute(
                    "INSERT INTO schema_migrations (version, description, applied_at) VALUES (?, ?, ?)",
                    (migration.version, migration.description, datetime.now(UTC).isoformat()),
                )

    def store_game_snapshot(self, game: Game) -> str:
        """Append a game snapshot. Revised source data remains auditable."""

        snapshot_id = str(uuid4())
        with self._connection() as connection:
            connection.execute(
                """INSERT INTO game_snapshots
                   (snapshot_id, game_id, official_date, retrieved_at, source, payload_json)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    snapshot_id,
                    game.game_id,
                    game.official_date.isoformat(),
                    game.provenance.retrieved_at.isoformat(),
                    game.provenance.source,
                    json.dumps(game, default=_json_default, sort_keys=True),
                ),
            )
        return snapshot_id

    def store_inference_feature_snapshot(self, snapshot: InferenceFeatureSnapshot) -> str:
        """Append a pregame feature vector; never overwrite an earlier pull."""

        snapshot_id = str(uuid4())
        with self._connection() as connection:
            connection.execute(
                """INSERT INTO inference_feature_snapshots
                   (snapshot_id, game_id, prediction_timestamp, source_timestamp,
                    feature_schema_version, formula_version, payload_json)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    snapshot_id,
                    snapshot.game_id,
                    snapshot.prediction_timestamp.isoformat(),
                    snapshot.source_timestamp.isoformat(),
                    snapshot.feature_schema_version,
                    snapshot.formula_version,
                    json.dumps(dict(snapshot.features), sort_keys=False),
                ),
            )
        return snapshot_id

    def inference_feature_snapshot_count(self) -> int:
        """Return the number of immutable daily E3+E7+E8 vectors."""

        with self._connection() as connection:
            return int(connection.execute("SELECT COUNT(*) FROM inference_feature_snapshots").fetchone()[0])

    def store_prediction(
        self,
        *,
        game_id: str,
        prediction_timestamp: datetime,
        data_timestamp: datetime,
        model_version: str,
        feature_version: str,
        raw_probability: float | None,
        calibrated_probability: float | None,
        uncertainty: float | None,
        data_quality: float,
        model_input: Any,
        model_output: Any,
    ) -> str:
        """Append an immutable prediction observation and return its identifier."""

        if prediction_timestamp.tzinfo is None or data_timestamp.tzinfo is None:
            raise ValueError("prediction and data timestamps must be timezone-aware")
        if not 0 <= data_quality <= 1:
            raise ValueError("data_quality must be between zero and one")
        prediction_id = str(uuid4())
        with self._connection() as connection:
            connection.execute(
                """INSERT INTO predictions
                   (prediction_id, game_id, prediction_timestamp, data_timestamp,
                    model_version, feature_version, raw_probability,
                    calibrated_probability, uncertainty, data_quality, input_json, output_json)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    prediction_id,
                    game_id,
                    prediction_timestamp.isoformat(),
                    data_timestamp.isoformat(),
                    model_version,
                    feature_version,
                    raw_probability,
                    calibrated_probability,
                    uncertainty,
                    data_quality,
                    json.dumps(model_input, default=_json_default, sort_keys=True),
                    json.dumps(model_output, default=_json_default, sort_keys=True),
                ),
            )
        return prediction_id

    def store_market_quote(
        self,
        *,
        game_id: str,
        sportsbook: str,
        market: str,
        selection: str,
        decimal_odds: float,
        captured_at: datetime,
        source: str,
        line: float | None = None,
        payload: Any | None = None,
    ) -> str:
        """Append a market observation; opening/current/closing prices are never overwritten."""

        if decimal_odds <= 1:
            raise ValueError("decimal odds must exceed 1")
        if captured_at.tzinfo is None:
            raise ValueError("captured_at must be timezone-aware")
        quote_id = str(uuid4())
        with self._connection() as connection:
            connection.execute(
                """INSERT INTO market_quotes
                   (quote_id, game_id, sportsbook, market, selection, line, decimal_odds,
                    captured_at, source, payload_json)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    quote_id,
                    game_id,
                    sportsbook,
                    market,
                    selection,
                    line,
                    decimal_odds,
                    captured_at.isoformat(),
                    source,
                    json.dumps(payload if payload is not None else {}, default=_json_default, sort_keys=True),
                ),
            )
        return quote_id

    def market_quotes_for_game(self, game_id: str) -> list[dict[str, Any]]:
        """Return immutable market observations for one game in capture order."""

        if not game_id:
            raise ValueError("game_id is required")
        with self._connection() as connection:
            rows = connection.execute(
                """SELECT quote_id, game_id, sportsbook, market, selection, line,
                          decimal_odds, captured_at, source, payload_json
                     FROM market_quotes
                     WHERE game_id = ?
                     ORDER BY captured_at ASC, quote_id ASC""",
                (game_id,),
            ).fetchall()
        return [
            {
                "quote_id": row["quote_id"],
                "game_id": row["game_id"],
                "sportsbook": row["sportsbook"],
                "market": row["market"],
                "selection": row["selection"],
                "line": row["line"],
                "decimal_odds": row["decimal_odds"],
                "captured_at": row["captured_at"],
                "source": row["source"],
                "payload": json.loads(row["payload_json"]),
            }
            for row in rows
        ]

    def prediction_count(self) -> int:
        """Return the number of immutable prediction records."""

        with self._connection() as connection:
            return int(connection.execute("SELECT COUNT(*) FROM predictions").fetchone()[0])

    def latest_prediction_for_game(self, game_id: str) -> dict[str, Any] | None:
        """Return the latest prediction snapshot for a game without mutating history."""

        with self._connection() as connection:
            row = connection.execute(
                "SELECT * FROM predictions WHERE game_id = ? ORDER BY prediction_timestamp DESC LIMIT 1",
                (game_id,),
            ).fetchone()
        if row is None:
            return None
        return {
            "prediction_id": row["prediction_id"],
            "prediction_timestamp": row["prediction_timestamp"],
            "data_timestamp": row["data_timestamp"],
            "data_quality": row["data_quality"],
            "input": json.loads(row["input_json"]),
            "output": json.loads(row["output_json"]),
        }

    def store_probable_pitcher(self, pitcher: ProbablePitcher) -> str:
        """Append one team's probable-pitcher check; never overwrites a prior one.

        Storing a NOT_YET_PUBLISHED record is deliberate: it proves the check
        happened at that timestamp, which a later "still missing" cannot.
        """

        snapshot_id = str(uuid4())
        with self._connection() as connection:
            connection.execute(
                """INSERT INTO probable_pitcher_snapshots
                   (snapshot_id, game_id, team_id, status, retrieved_at, source, payload_json)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    snapshot_id,
                    pitcher.game_id,
                    pitcher.team_id,
                    pitcher.status.value,
                    pitcher.provenance.retrieved_at.isoformat(),
                    pitcher.provenance.source,
                    json.dumps(pitcher, default=_json_default, sort_keys=True),
                ),
            )
        return snapshot_id

    def probable_pitcher_count(self) -> int:
        """Return the number of stored probable-pitcher checks."""

        with self._connection() as connection:
            return int(connection.execute("SELECT COUNT(*) FROM probable_pitcher_snapshots").fetchone()[0])

    def store_lineups(self, lineups: GameLineups) -> str:
        """Append one lineup check for a game; confirmed or not-yet-published both persist."""

        snapshot_id = str(uuid4())
        with self._connection() as connection:
            connection.execute(
                """INSERT INTO lineup_snapshots
                   (snapshot_id, game_id, status, retrieved_at, source, payload_json)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    snapshot_id,
                    lineups.game_id,
                    lineups.status.value,
                    lineups.provenance.retrieved_at.isoformat(),
                    lineups.provenance.source,
                    json.dumps(lineups, default=_json_default, sort_keys=True),
                ),
            )
        return snapshot_id

    def lineup_snapshot_count(self) -> int:
        """Return the number of stored lineup checks."""

        with self._connection() as connection:
            return int(connection.execute("SELECT COUNT(*) FROM lineup_snapshots").fetchone()[0])

    def store_weather(self, weather: GameWeather) -> str:
        """Append one weather check for a game; NOT_AVAILABLE also persists.

        Forecasts drift as game time approaches, so each fetch is its own
        row, never an update to a previous one.
        """

        snapshot_id = str(uuid4())
        with self._connection() as connection:
            connection.execute(
                """INSERT INTO weather_snapshots
                   (snapshot_id, game_id, status, retrieved_at, source, payload_json)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    snapshot_id,
                    weather.game_id,
                    weather.status.value,
                    weather.provenance.retrieved_at.isoformat(),
                    weather.provenance.source,
                    json.dumps(weather, default=_json_default, sort_keys=True),
                ),
            )
        return snapshot_id

    def weather_snapshot_count(self) -> int:
        """Return the number of stored weather checks."""

        with self._connection() as connection:
            return int(connection.execute("SELECT COUNT(*) FROM weather_snapshots").fetchone()[0])

    def store_team_season_stats(self, stats: TeamSeasonStats) -> str:
        """Append one team's raw season-stat snapshot; never overwrites a prior pull."""

        snapshot_id = str(uuid4())
        with self._connection() as connection:
            connection.execute(
                """INSERT INTO team_season_stat_snapshots
                   (snapshot_id, team_id, season, retrieved_at, source, payload_json)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    snapshot_id,
                    stats.team_id,
                    stats.season,
                    stats.provenance.retrieved_at.isoformat(),
                    stats.provenance.source,
                    json.dumps(stats, default=_json_default, sort_keys=True),
                ),
            )
        return snapshot_id

    def team_season_stat_count(self) -> int:
        """Return the number of stored team season-stat snapshots."""

        with self._connection() as connection:
            return int(connection.execute("SELECT COUNT(*) FROM team_season_stat_snapshots").fetchone()[0])

    def store_team_run_profile(self, profile: TeamRunProfile, season: str) -> str:
        """Append a derived TeamRunProfile snapshot for reproducible future backtests."""

        if not season:
            raise ValueError("season is required")
        snapshot_id = str(uuid4())
        formula_version = "FS-RUN-PROFILE-1"
        with self._connection() as connection:
            connection.execute(
                """INSERT INTO team_run_profile_snapshots
                   (snapshot_id, team_id, season, retrieved_at, source, formula_version, payload_json)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    snapshot_id,
                    profile.team_id,
                    season,
                    profile.provenance.retrieved_at.isoformat(),
                    profile.provenance.source,
                    formula_version,
                    json.dumps(profile, default=_json_default, sort_keys=True),
                ),
            )
        return snapshot_id

    def team_run_profile_count(self) -> int:
        """Return the number of stored derived feature snapshots."""

        with self._connection() as connection:
            return int(connection.execute("SELECT COUNT(*) FROM team_run_profile_snapshots").fetchone()[0])

    def store_analyst_decision(
        self,
        *,
        game_id: str,
        input_mode: str,
        data_quality: float,
        model_validation_status: str,
        human_pick: dict[str, Any] | None,
        machine_pick: dict[str, Any] | None,
        prediction_id: str | None = None,
        created_at: datetime | None = None,
    ) -> str:
        """Append an immutable human-vs-machine decision record."""

        if not game_id or not input_mode:
            raise ValueError("game_id and input_mode are required")
        if not 0 <= data_quality <= 1:
            raise ValueError("data_quality must be between zero and one")
        timestamp = created_at or datetime.now(UTC)
        if timestamp.tzinfo is None or timestamp.utcoffset() is None:
            raise ValueError("created_at must be timezone-aware")
        decision_id = str(uuid4())
        human_market = human_selection = machine_market = machine_selection = None
        human_line = machine_line = None
        if human_pick:
            human_market = str(human_pick.get("market")) if human_pick.get("market") is not None else None
            human_selection = str(human_pick.get("selection")) if human_pick.get("selection") is not None else None
            human_line = float(human_pick["line"]) if human_pick.get("line") is not None else None
        if machine_pick:
            machine_market = str(machine_pick.get("market")) if machine_pick.get("market") is not None else None
            machine_selection = str(machine_pick.get("selection")) if machine_pick.get("selection") is not None else None
            machine_line = float(machine_pick["line"]) if machine_pick.get("line") is not None else None
        payload = {"human_pick": human_pick, "machine_pick": machine_pick}
        with self._connection() as connection:
            connection.execute(
                """INSERT INTO analyst_decisions
                   (decision_id, game_id, prediction_id, created_at, input_mode,
                    human_market, human_selection, human_line, machine_market,
                    machine_selection, machine_line, data_quality, model_validation_status, payload_json)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    decision_id, game_id, prediction_id, timestamp.isoformat(), input_mode,
                    human_market, human_selection, human_line, machine_market, machine_selection,
                    machine_line, data_quality, model_validation_status,
                    json.dumps(payload, default=_json_default, sort_keys=True),
                ),
            )
        return decision_id

    def analyst_decision_count(self) -> int:
        """Return the number of immutable analyst decision records."""

        with self._connection() as connection:
            return int(connection.execute("SELECT COUNT(*) FROM analyst_decisions").fetchone()[0])

    def store_result_snapshot(
        self, *, game_id: str, recorded_at: datetime, source: str, home_score: int, away_score: int
    ) -> str:
        """Append a final-result snapshot used by the human-vs-machine tracker."""

        if recorded_at.tzinfo is None or recorded_at.utcoffset() is None:
            raise ValueError("recorded_at must be timezone-aware")
        if home_score < 0 or away_score < 0:
            raise ValueError("scores cannot be negative")
        result_id = str(uuid4())
        payload = {"home_score": home_score, "away_score": away_score}
        with self._connection() as connection:
            connection.execute(
                "INSERT INTO results (result_id, game_id, recorded_at, source, payload_json) VALUES (?, ?, ?, ?, ?)",
                (result_id, game_id, recorded_at.isoformat(), source, json.dumps(payload, sort_keys=True)),
            )
        return result_id

    def result_count(self) -> int:
        """Return the number of stored result snapshots."""

        with self._connection() as connection:
            return int(connection.execute("SELECT COUNT(*) FROM results").fetchone()[0])

    def leaderboard_rows(self) -> list[dict[str, Any]]:
        """Return latest analyst decision/result pairs as dictionaries."""

        with self._connection() as connection:
            decisions = connection.execute(
                "SELECT * FROM analyst_decisions ORDER BY created_at ASC"
            ).fetchall()
            results = connection.execute(
                "SELECT game_id, payload_json, recorded_at FROM results ORDER BY recorded_at ASC"
            ).fetchall()
        latest_result: dict[str, dict[str, Any]] = {}
        for row in results:
            latest_result[row["game_id"]] = {
                **json.loads(row["payload_json"]),
                "recorded_at": row["recorded_at"],
            }
        output: list[dict[str, Any]] = []
        for row in decisions:
            payload = json.loads(row["payload_json"])
            result = latest_result.get(row["game_id"])
            output.append(
                {
                    "game_id": row["game_id"],
                    "created_at": row["created_at"],
                    "input_mode": row["input_mode"],
                    "model_validation_status": row["model_validation_status"],
                    "data_quality": row["data_quality"],
                    "human_pick": payload.get("human_pick"),
                    "machine_pick": payload.get("machine_pick"),
                    "result": result,
                }
            )
        return output

    @contextmanager
    def _connection(self):
        """Yield, commit and always close a connection, including on Windows."""

        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()
