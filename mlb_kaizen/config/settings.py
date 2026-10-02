"""Centralised, environment-based configuration."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path


@dataclass(frozen=True, slots=True)
class Settings:
    """Runtime settings. Values are deliberately explicit and versionable."""

    database_path: Path
    cache_dir: Path
    http_timeout_seconds: float = 12.0
    http_retries: int = 3
    cache_ttl_seconds: int = 900
    simulation_count: int = 100_000
    random_seed: int = 20_260_916
    minimum_edge: float = 0.025
    minimum_ev: float = 0.02
    maximum_probability_uncertainty: float = 0.035
    minimum_data_quality: float = 0.80
    market_freshness_minutes: int = 10

    @classmethod
    def from_environment(cls) -> "Settings":
        """Build settings without exposing credentials in source code or logs."""

        project_data = Path(os.getenv("MLB_KAIZEN_DATA_DIR", "data"))
        return cls(
            database_path=Path(os.getenv("MLB_KAIZEN_DB", project_data / "mlb_kaizen.sqlite3")),
            cache_dir=Path(os.getenv("MLB_KAIZEN_CACHE_DIR", project_data / "cache")),
            http_timeout_seconds=float(os.getenv("MLB_KAIZEN_HTTP_TIMEOUT", "12")),
            http_retries=int(os.getenv("MLB_KAIZEN_HTTP_RETRIES", "3")),
            cache_ttl_seconds=int(os.getenv("MLB_KAIZEN_CACHE_TTL", "900")),
            simulation_count=int(os.getenv("MLB_KAIZEN_SIMULATIONS", "100000")),
            random_seed=int(os.getenv("MLB_KAIZEN_RANDOM_SEED", "20260916")),
        )
