"""Versioned, additive SQLite migrations.

Each migration is forward-only. Migration 1 is the original schema exactly
as it shipped before this module existed (CREATE TABLE/INDEX IF NOT EXISTS),
so opening a database created before migrations were tracked is safe: the
statements are no-ops against tables that already exist, and version 1 is
simply recorded as applied. Later migrations do not need to stay idempotent
themselves — KaizenDatabase only ever runs a given version once, tracked in
schema_migrations.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Migration:
    version: int
    description: str
    sql: str


MIGRATIONS: tuple[Migration, ...] = (
    Migration(
        version=1,
        description="initial schema: game snapshots, market quotes, predictions, results",
        sql="""
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
        """,
    ),
    Migration(
        version=2,
        description="probable pitcher and lineup snapshots, point-in-time and append-only",
        sql="""
            CREATE TABLE IF NOT EXISTS probable_pitcher_snapshots (
                snapshot_id TEXT PRIMARY KEY,
                game_id TEXT NOT NULL,
                team_id TEXT NOT NULL,
                status TEXT NOT NULL,
                retrieved_at TEXT NOT NULL,
                source TEXT NOT NULL,
                payload_json TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_probable_pitcher_snapshots_game_team_time
                ON probable_pitcher_snapshots(game_id, team_id, retrieved_at);

            CREATE TABLE IF NOT EXISTS lineup_snapshots (
                snapshot_id TEXT PRIMARY KEY,
                game_id TEXT NOT NULL,
                status TEXT NOT NULL,
                retrieved_at TEXT NOT NULL,
                source TEXT NOT NULL,
                payload_json TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_lineup_snapshots_game_time
                ON lineup_snapshots(game_id, retrieved_at);
        """,
    ),
    Migration(
        version=3,
        description="weather forecasts and raw team season-stat snapshots, point-in-time and append-only",
        sql="""
            CREATE TABLE IF NOT EXISTS weather_snapshots (
                snapshot_id TEXT PRIMARY KEY,
                game_id TEXT NOT NULL,
                status TEXT NOT NULL,
                retrieved_at TEXT NOT NULL,
                source TEXT NOT NULL,
                payload_json TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_weather_snapshots_game_time
                ON weather_snapshots(game_id, retrieved_at);

            CREATE TABLE IF NOT EXISTS team_season_stat_snapshots (
                snapshot_id TEXT PRIMARY KEY,
                team_id TEXT NOT NULL,
                season TEXT NOT NULL,
                retrieved_at TEXT NOT NULL,
                source TEXT NOT NULL,
                payload_json TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_team_season_stat_snapshots_team_season_time
                ON team_season_stat_snapshots(team_id, season, retrieved_at);
        """,
    ),
    Migration(
        version=4,
        description="feature profile snapshots and human-vs-machine analyst records",
        sql="""
            CREATE TABLE IF NOT EXISTS team_run_profile_snapshots (
                snapshot_id TEXT PRIMARY KEY,
                team_id TEXT NOT NULL,
                season TEXT NOT NULL,
                retrieved_at TEXT NOT NULL,
                source TEXT NOT NULL,
                formula_version TEXT NOT NULL,
                payload_json TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_team_run_profile_snapshots_team_season_time
                ON team_run_profile_snapshots(team_id, season, retrieved_at);

            CREATE TABLE IF NOT EXISTS analyst_decisions (
                decision_id TEXT PRIMARY KEY,
                game_id TEXT NOT NULL,
                prediction_id TEXT,
                created_at TEXT NOT NULL,
                input_mode TEXT NOT NULL,
                human_market TEXT,
                human_selection TEXT,
                human_line REAL,
                machine_market TEXT,
                machine_selection TEXT,
                machine_line REAL,
                data_quality REAL NOT NULL CHECK(data_quality >= 0 AND data_quality <= 1),
                model_validation_status TEXT NOT NULL,
                payload_json TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_analyst_decisions_game_time
                ON analyst_decisions(game_id, created_at);
            CREATE INDEX IF NOT EXISTS idx_analyst_decisions_prediction
                ON analyst_decisions(prediction_id);
        """,
    ),
)
