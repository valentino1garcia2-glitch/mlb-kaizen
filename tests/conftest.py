from datetime import UTC, date, datetime

from mlb_kaizen.domain.models import AvailabilityStatus, DataProvenance, Game, TeamRunProfile


def provenance() -> DataProvenance:
    return DataProvenance(
        source="test source",
        retrieved_at=datetime(2026, 9, 16, 12, tzinfo=UTC),
        status=AvailabilityStatus.AVAILABLE,
    )


def game() -> Game:
    return Game(
        game_id="mlb:1",
        official_date=date(2026, 9, 16),
        home_team_id="10",
        home_team_name="Home",
        away_team_id="20",
        away_team_name="Away",
        provenance=provenance(),
    )


def home_profile() -> TeamRunProfile:
    return TeamRunProfile("10", "Home", 1.10, 0.90, 400, 0.90, provenance())


def away_profile() -> TeamRunProfile:
    return TeamRunProfile("20", "Away", 0.95, 1.05, 400, 0.90, provenance())
