"""Point-in-time historical dataset contracts for training and backtesting."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
import json
from pathlib import Path
from typing import Mapping


MODEL_FEATURES = (
    "home_offensive_index",
    "away_offensive_index",
    "home_run_prevention_index",
    "away_run_prevention_index",
    "home_advantage",
)


@dataclass(frozen=True, slots=True)
class HistoricalGameRow:
    """One historical information set plus post-game targets."""

    game_id: str
    official_date: date
    prediction_timestamp: datetime
    feature_timestamp: datetime
    features: Mapping[str, float]
    home_runs: int
    away_runs: int

    def __post_init__(self) -> None:
        if self.prediction_timestamp.tzinfo is None or self.prediction_timestamp.utcoffset() is None:
            raise ValueError("prediction_timestamp must be timezone-aware")
        if self.feature_timestamp.tzinfo is None or self.feature_timestamp.utcoffset() is None:
            raise ValueError("feature_timestamp must be timezone-aware")
        if self.feature_timestamp > self.prediction_timestamp:
            raise ValueError("feature_timestamp cannot be later than prediction_timestamp")
        if self.home_runs < 0 or self.away_runs < 0:
            raise ValueError("run targets cannot be negative")
        missing = [name for name in MODEL_FEATURES if name not in self.features]
        if missing:
            raise ValueError(f"missing model features: {', '.join(missing)}")

    @property
    def home_win(self) -> int:
        return int(self.home_runs > self.away_runs)

    @property
    def total_runs(self) -> int:
        return self.home_runs + self.away_runs


def load_jsonl(path: Path) -> tuple[HistoricalGameRow, ...]:
    """Load explicit historical rows from JSONL and validate point-in-time constraints."""

    rows: list[HistoricalGameRow] = []
    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not raw_line.strip():
            continue
        payload = json.loads(raw_line)
        try:
            row = HistoricalGameRow(
                game_id=str(payload["game_id"]),
                official_date=date.fromisoformat(str(payload["official_date"])),
                prediction_timestamp=_parse_timestamp(payload["prediction_timestamp"]),
                feature_timestamp=_parse_timestamp(payload["feature_timestamp"]),
                features={name: float(payload["features"][name]) for name in MODEL_FEATURES},
                home_runs=int(payload["home_runs"]),
                away_runs=int(payload["away_runs"]),
            )
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise ValueError(f"invalid dataset row at line {line_number}: {exc}") from exc
        rows.append(row)
    if not rows:
        raise ValueError("historical dataset is empty")
    return tuple(sorted(rows, key=lambda row: (row.prediction_timestamp, row.game_id)))


def save_jsonl(path: Path, rows: tuple[HistoricalGameRow, ...] | list[HistoricalGameRow]) -> None:
    """Persist a validated point-in-time dataset without mutating the source rows."""

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            payload = {
                "game_id": row.game_id,
                "official_date": row.official_date.isoformat(),
                "prediction_timestamp": row.prediction_timestamp.isoformat(),
                "feature_timestamp": row.feature_timestamp.isoformat(),
                "features": dict(row.features),
                "home_runs": row.home_runs,
                "away_runs": row.away_runs,
            }
            handle.write(json.dumps(payload, sort_keys=True) + "\n")


def _parse_timestamp(value: object) -> datetime:
    if not isinstance(value, str):
        raise ValueError("timestamp must be a string")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("timestamp must include a UTC offset")
    return parsed.astimezone(UTC)
