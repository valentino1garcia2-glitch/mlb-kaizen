"""SQLite persistence that never rewrites a historical prediction."""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
from datetime import date, datetime
from enum import Enum
from contextlib import contextmanager
import json
from pathlib import Path
import sqlite3
from typing import Any
from uuid import uuid4

from mlb_kaizen.domain.models import Game


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
        """Create the initial schema idempotently."""

        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connection() as connection:
            connection.executescript(
                """
                PRAGMA foreign_keys = ON;
                CREATE TABLE IF NOT EXISTS game_snapshots (
                    snapshot_id TEXT PRIMARY KEY,
                    game_id TEXT NOT NULL,
                    official_date TEXT NOT NULL,
                    retrieved_at TEXT NOT NULL,
                    source TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_game_snapshots_game_time
                    ON game_snapshots(game_id, retrieved_at);

                CREATE TABLE IF NOT EXISTS market_quotes (
                    quote_id TEXT PRIMARY KEY,
                    game_id TEXT NOT NULL,
                    sportsbook TEXT NOT NULL,
                    market TEXT NOT NULL,
                    selection TEXT NOT NULL,
                    line REAL,
                    decimal_odds REAL NOT NULL CHECK(decimal_odds > 1),
                    captured_at TEXT NOT NULL,
                    source TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_market_quotes_game_time
                    ON market_quotes(game_id, captured_at);

                CREATE TABLE IF NOT EXISTS predictions (
                    prediction_id TEXT PRIMARY KEY,
                    game_id TEXT NOT NULL,
                    prediction_timestamp TEXT NOT NULL,
                    data_timestamp TEXT NOT NULL,
                    model_version TEXT NOT NULL,
                    feature_version TEXT NOT NULL,
                    raw_probability REAL,
                    calibrated_probability REAL,
                    uncertainty REAL,
                    data_quality REAL NOT NULL CHECK(data_quality >= 0 AND data_quality <= 1),
                    input_json TEXT NOT NULL,
                    output_json TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_predictions_game_time
                    ON predictions(game_id, prediction_timestamp);

                CREATE TABLE IF NOT EXISTS results (
                    result_id TEXT PRIMARY KEY,
                    game_id TEXT NOT NULL,
                    recorded_at TEXT NOT NULL,
                    source TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                );
                """
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

    def prediction_count(self) -> int:
        """Return the number of immutable prediction records."""

        with self._connection() as connection:
            return int(connection.execute("SELECT COUNT(*) FROM predictions").fetchone()[0])

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
