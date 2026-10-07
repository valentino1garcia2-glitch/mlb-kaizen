from datetime import UTC, datetime
from pathlib import Path
import tempfile
import unittest

from mlb_kaizen.storage.database import KaizenDatabase
from mlb_kaizen.storage.migrations import MIGRATIONS

from .conftest import (
    available_weather,
    confirmed_lineups,
    game,
    home_profile,
    not_available_weather,
    not_yet_published_lineups,
    probable_pitcher,
    team_season_stats,
)


class DatabaseTests(unittest.TestCase):
    def test_database_appends_game_and_prediction_without_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            database = KaizenDatabase(Path(temporary_directory) / "kaizen.sqlite3")
            database.initialise()
            snapshot_id = database.store_game_snapshot(game())
            prediction_id = database.store_prediction(
                game_id="mlb:1",
                prediction_timestamp=datetime(2026, 9, 16, 12, tzinfo=UTC),
                data_timestamp=datetime(2026, 9, 16, 11, tzinfo=UTC),
                model_version="model-test",
                feature_version="features-test",
                raw_probability=0.52,
                calibrated_probability=None,
                uncertainty=0.02,
                data_quality=0.9,
                model_input={"input": "test"},
                model_output={"output": "test"},
            )
            count = database.prediction_count()
        self.assertTrue(snapshot_id)
        self.assertTrue(prediction_id)
        self.assertEqual(count, 1)

    def test_initialise_is_idempotent_and_records_every_migration_once(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            database = KaizenDatabase(Path(temporary_directory) / "kaizen.sqlite3")
            database.initialise()
            database.initialise()
            database.initialise()
            with database._connection() as connection:
                rows = connection.execute("SELECT version FROM schema_migrations ORDER BY version").fetchall()
        applied_versions = [row[0] for row in rows]
        self.assertEqual(applied_versions, [migration.version for migration in MIGRATIONS])

    def test_probable_pitcher_snapshots_are_appended_not_persisted_only_when_projected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            database = KaizenDatabase(Path(temporary_directory) / "kaizen.sqlite3")
            database.initialise()
            database.store_probable_pitcher(probable_pitcher())
            count = database.probable_pitcher_count()
        self.assertEqual(count, 1)

    def test_lineup_snapshots_persist_both_confirmed_and_not_yet_published(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            database = KaizenDatabase(Path(temporary_directory) / "kaizen.sqlite3")
            database.initialise()
            database.store_lineups(not_yet_published_lineups())
            database.store_lineups(confirmed_lineups())
            count = database.lineup_snapshot_count()
        self.assertEqual(count, 2)

    def test_weather_snapshots_persist_both_available_and_not_available(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            database = KaizenDatabase(Path(temporary_directory) / "kaizen.sqlite3")
            database.initialise()
            database.store_weather(available_weather())
            database.store_weather(not_available_weather())
            count = database.weather_snapshot_count()
        self.assertEqual(count, 2)

    def test_team_season_stat_snapshots_are_appended(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            database = KaizenDatabase(Path(temporary_directory) / "kaizen.sqlite3")
            database.initialise()
            database.store_team_season_stats(team_season_stats())
            count = database.team_season_stat_count()
        self.assertEqual(count, 1)

    def test_manual_market_quotes_are_append_only(self) -> None:
        """Two observations of one market must remain two historical records."""

        with tempfile.TemporaryDirectory() as temporary_directory:
            database = KaizenDatabase(Path(temporary_directory) / "kaizen.sqlite3")
            database.initialise()
            first_quote_id = database.store_market_quote(
                game_id="mlb:1",
                sportsbook="Playdoit",
                market="moneyline",
                selection="away",
                decimal_odds=2.2,
                captured_at=datetime(2026, 10, 7, 1, 25, tzinfo=UTC),
                source="manual",
                payload={"entry_method": "manual", "american_odds": 120},
            )
            second_quote_id = database.store_market_quote(
                game_id="mlb:1",
                sportsbook="Playdoit",
                market="moneyline",
                selection="away",
                decimal_odds=2.1,
                captured_at=datetime(2026, 10, 7, 1, 29, tzinfo=UTC),
                source="manual",
                payload={"entry_method": "manual", "american_odds": 110},
            )
            with database._connection() as connection:
                count = connection.execute(
                    "SELECT COUNT(1) FROM market_quotes WHERE game_id = ?", ("mlb:1",)
                ).fetchone()[0]

        self.assertNotEqual(first_quote_id, second_quote_id)
        self.assertEqual(count, 2)


# Fase 4.5 tracking and derived-feature persistence
class DatabaseAnalystTests(unittest.TestCase):
    def test_profile_and_analyst_decision_are_append_only(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            database = KaizenDatabase(Path(temporary_directory) / "kaizen.sqlite3")
            database.initialise()
            database.store_team_run_profile(home_profile(), "2026")
            database.store_analyst_decision(
                game_id="mlb:1",
                input_mode="manual",
                data_quality=0.9,
                model_validation_status="experimental",
                human_pick={"market": "moneyline", "selection": "home"},
                machine_pick={"market": "moneyline", "selection": "away"},
            )
            self.assertEqual(database.team_run_profile_count(), 1)
            self.assertEqual(database.analyst_decision_count(), 1)
