"""Transparent, configurable baseline for expected MLB runs."""

from __future__ import annotations

from dataclasses import dataclass

from mlb_kaizen.domain.models import Game, TeamRunProfile


@dataclass(frozen=True, slots=True)
class RunProjection:
    """Expected runs and assumptions emitted by the baseline model."""

    game_id: str
    home_expected_runs: float
    away_expected_runs: float
    home_dispersion: float
    away_dispersion: float
    model_version: str
    feature_version: str

    @property
    def expected_total_runs(self) -> float:
        return self.home_expected_runs + self.away_expected_runs


class BaselineRunModel:
    """League-relative run model suitable as a falsifiable first baseline.

    ``expected_home = league_runs * home_offence * away_prevention * home_advantage``
    ``expected_away = league_runs * away_offence * home_prevention``

    The indices must be produced by a timestamp-aware feature pipeline. The
    current model intentionally does not claim that it has learned these weights;
    all constants are configuration and must be validated via walk-forward tests.
    """

    model_version = "MLB-KAIZEN-BASELINE-0.1.0"
    feature_version = "FS-BASELINE-0.1"

    def __init__(
        self,
        league_runs_per_team: float = 4.40,
        home_advantage_multiplier: float = 1.035,
        dispersion: float = 4.0,
    ) -> None:
        if league_runs_per_team <= 0 or home_advantage_multiplier <= 0 or dispersion <= 0:
            raise ValueError("baseline parameters must be positive")
        self.league_runs_per_team = league_runs_per_team
        self.home_advantage_multiplier = home_advantage_multiplier
        self.dispersion = dispersion

    def project(
        self,
        game: Game,
        home_profile: TeamRunProfile,
        away_profile: TeamRunProfile,
    ) -> RunProjection:
        """Project runs only when supplied team profiles match the selected game."""

        if home_profile.team_id != game.home_team_id:
            raise ValueError("home profile does not match game home team")
        if away_profile.team_id != game.away_team_id:
            raise ValueError("away profile does not match game away team")

        home_runs = (
            self.league_runs_per_team
            * home_profile.offensive_index
            * away_profile.run_prevention_index
            * self.home_advantage_multiplier
        )
        away_runs = (
            self.league_runs_per_team
            * away_profile.offensive_index
            * home_profile.run_prevention_index
        )
        return RunProjection(
            game_id=game.game_id,
            home_expected_runs=home_runs,
            away_expected_runs=away_runs,
            home_dispersion=self.dispersion,
            away_dispersion=self.dispersion,
            model_version=self.model_version,
            feature_version=self.feature_version,
        )
