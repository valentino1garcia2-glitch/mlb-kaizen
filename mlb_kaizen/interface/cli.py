"""CLI for data retrieval, practical Analyst Mode and model evaluation."""

from __future__ import annotations

import argparse
from dataclasses import asdict, is_dataclass
from datetime import UTC, date, datetime
from enum import Enum
import json
from pathlib import Path
from typing import Any

from mlb_kaizen.config.settings import Settings
from mlb_kaizen.data.http import CachedHttpClient, DataProviderError
from mlb_kaizen.data.mlb_stats import MLBStatsProvider
from mlb_kaizen.data.odds import SportsGameOddsProvider
from mlb_kaizen.data.weather import NWSWeatherProvider
from mlb_kaizen.domain.models import (
    AnalysisContext,
    AnalysisMode,
    AvailabilityStatus,
    DataProvenance,
    Game,
    TeamRunProfile,
)
from mlb_kaizen.features.run_profile import compute_team_run_profile
from mlb_kaizen.features.e8_daily_snapshot import build_e8_daily_feature_snapshot
from mlb_kaizen.observability.logging import configure_logging
from mlb_kaizen.reporting.html import render_analysis_html, render_leaderboard_html
from mlb_kaizen.reporting.text import render_analysis_report
from mlb_kaizen.services.analysis import AnalysisRequest, AnalysisService, MarketInput
from mlb_kaizen.storage.database import KaizenDatabase
from mlb_kaizen.tracking.human_machine import leaderboard
from mlb_kaizen.validation.schema import validate_analysis_document
from mlb_kaizen.training.dataset import load_jsonl
from mlb_kaizen.training.trainers import PoissonTrainer, RandomForestTrainer
from mlb_kaizen.training.artifacts import ModelArtifactMetadata, load_model_artifact, save_model_artifact
from mlb_kaizen.training.inference_artifact import (
    load_e11_inference_artifact,
    train_e11_inference_artifact,
    save_e11_inference_artifact,
)
from mlb_kaizen.evaluation.walk_forward import walk_forward_evaluate
from mlb_kaizen.evaluation.calibration import PlattCalibrator, temporal_calibration_report
from mlb_kaizen.evaluation.compare import ModelComparison
from mlb_kaizen.services.trained_model import TrainedPoissonAnalysisModel


def _parse_timestamp(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("timestamps must include a UTC offset, for example +00:00")
    return parsed


def _parse_provenance(payload: dict[str, Any]) -> DataProvenance:
    return DataProvenance(
        source=str(payload["source"]),
        retrieved_at=_parse_timestamp(str(payload["retrieved_at"])),
        effective_at=_parse_timestamp(str(payload["effective_at"])) if payload.get("effective_at") else None,
        source_url=str(payload["source_url"]) if payload.get("source_url") else None,
        source_version=str(payload["source_version"]) if payload.get("source_version") else None,
        status=AvailabilityStatus(str(payload["status"])),
    )


def _parse_game(payload: dict[str, Any]) -> Game:
    return Game(
        game_id=str(payload["game_id"]),
        official_date=date.fromisoformat(str(payload["official_date"])),
        home_team_id=str(payload["home_team_id"]),
        home_team_name=str(payload["home_team_name"]),
        away_team_id=str(payload["away_team_id"]),
        away_team_name=str(payload["away_team_name"]),
        provenance=_parse_provenance(payload["provenance"]),
        start_time=_parse_timestamp(str(payload["start_time"])) if payload.get("start_time") else None,
        venue_name=str(payload["venue_name"]) if payload.get("venue_name") else None,
    )


def _parse_profile(payload: dict[str, Any]) -> TeamRunProfile:
    return TeamRunProfile(
        team_id=str(payload["team_id"]),
        team_name=str(payload["team_name"]),
        offensive_index=float(payload["offensive_index"]),
        run_prevention_index=float(payload["run_prevention_index"]),
        sample_size=int(payload["sample_size"]),
        data_quality=float(payload["data_quality"]),
        provenance=_parse_provenance(payload["provenance"]),
    )


def _parse_analysis_request(input_path: Path, mode_override: str | None = None) -> AnalysisRequest:
    payload = json.loads(input_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("analysis input must be a JSON object")
    validate_analysis_document(payload, Path("docs/schemas/analysis-input.schema.json"))
    context_data = payload["context"]
    statuses = {
        str(name): AvailabilityStatus(str(status))
        for name, status in dict(context_data.get("data_statuses", {})).items()
    }
    market_data = dict(payload.get("market", {}))
    mode_value = mode_override or payload.get("mode", AnalysisMode.SNAPSHOT.value)
    return AnalysisRequest(
        game=_parse_game(payload["game"]),
        home_profile=_parse_profile(payload["home_profile"]),
        away_profile=_parse_profile(payload["away_profile"]),
        context=AnalysisContext(
            prediction_timestamp=_parse_timestamp(str(context_data["prediction_timestamp"])),
            information_state=str(context_data["information_state"]),
            data_statuses=statuses,
        ),
        league_runs_per_team=float(payload["league_runs_per_team"]),
        mode=AnalysisMode(str(mode_value)),
        market=MarketInput(
            home_decimal_odds=float(market_data["home_decimal_odds"]) if market_data.get("home_decimal_odds") is not None else None,
            away_decimal_odds=float(market_data["away_decimal_odds"]) if market_data.get("away_decimal_odds") is not None else None,
            total_line=float(market_data["total_line"]) if market_data.get("total_line") is not None else None,
            over_decimal_odds=float(market_data["over_decimal_odds"]) if market_data.get("over_decimal_odds") is not None else None,
            under_decimal_odds=float(market_data["under_decimal_odds"]) if market_data.get("under_decimal_odds") is not None else None,
            home_run_line=float(market_data["home_run_line"]) if market_data.get("home_run_line") is not None else None,
            home_run_line_decimal_odds=(float(market_data["home_run_line_decimal_odds"]) if market_data.get("home_run_line_decimal_odds") is not None else None),
            away_run_line_decimal_odds=(float(market_data["away_run_line_decimal_odds"]) if market_data.get("away_run_line_decimal_odds") is not None else None),
            sportsbook=str(market_data["sportsbook"]) if market_data.get("sportsbook") else None,
        ),
    )


def _json_default(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value):
        return asdict(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Path):
        return str(value)
    raise TypeError(f"cannot serialise {type(value)!r}")


def _write_output(content: str, output: Path | None) -> None:
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(content, encoding="utf-8")
        print(f"Wrote {output}")
    else:
        print(content)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="mlb-kaizen", description="MLB KAIZEN research and analyst engine")
    subcommands = parser.add_subparsers(dest="command", required=True)
    subcommands.add_parser("init-db", help="create the local SQLite schema")
    subcommands.add_parser("health", help="show local system configuration")
    subcommands.add_parser("status", help="show the persistent project checkpoint")
    schedule = subcommands.add_parser("schedule", help="retrieve and snapshot an MLB schedule")
    schedule.add_argument("--date", required=True, type=date.fromisoformat)
    pitchers = subcommands.add_parser("probable-pitchers", help="retrieve probable starting pitchers")
    pitchers.add_argument("--date", required=True, type=date.fromisoformat)
    lineups = subcommands.add_parser("lineups", help="retrieve one game's batting order")
    lineups.add_argument("--game-id", required=True)
    team_stats = subcommands.add_parser("team-stats", help="retrieve raw season aggregates")
    team_stats.add_argument("--team-id", required=True)
    team_stats.add_argument("--team-name", required=True)
    team_stats.add_argument("--season", required=True)
    run_profile = subcommands.add_parser("run-profile", help="compute and persist a team run profile")
    run_profile.add_argument("--team-id", required=True)
    run_profile.add_argument("--team-name", required=True)
    run_profile.add_argument("--season", required=True)
    odds = subcommands.add_parser("odds", help="retrieve and persist sportsbook market snapshots")
    odds.add_argument("--game-id", required=True)
    weather = subcommands.add_parser("weather", help="retrieve and persist a point-in-time forecast")
    weather.add_argument("--game-id", required=True)
    weather.add_argument("--venue-id", required=True)
    weather.add_argument("--at", required=True, type=_parse_timestamp)
    analysis = subcommands.add_parser("analyze", help="run practical Analyst Mode from JSON input")
    analysis.add_argument("--input", required=True, type=Path)
    analysis.add_argument("--persist", action="store_true")
    analysis.add_argument("--mode", choices=[mode.value for mode in AnalysisMode])
    analysis.add_argument(
        "--trained-model",
        type=Path,
        help="trusted local Poisson artifact created by train-model (uses the trained E3-style model)",
    )
    analysis.add_argument(
        "--calibrator",
        type=Path,
        help="trusted local Platt calibration artifact; requires --trained-model",
    )
    analysis.add_argument("--format", choices=("text", "json", "html"), default="text")
    analysis.add_argument("--output", type=Path)
    human = subcommands.add_parser("record-human-pick", help="append a human decision for the latest prediction")
    human.add_argument("--game-id", required=True)
    human.add_argument("--market", required=True, choices=("moneyline", "total", "run_line"))
    human.add_argument("--selection", required=True)
    human.add_argument("--line", type=float)
    human.add_argument("--decimal-odds", type=float)
    human.add_argument("--prediction-id")
    result = subcommands.add_parser("record-result", help="append a game result snapshot")
    result.add_argument("--game-id", required=True)
    result.add_argument("--home-score", required=True, type=int)
    result.add_argument("--away-score", required=True, type=int)
    result.add_argument("--source", default="manual")
    result.add_argument("--recorded-at", type=_parse_timestamp)
    leader = subcommands.add_parser("leaderboard", help="show Human vs Machine results")
    leader.add_argument("--format", choices=("text", "json", "html"), default="text")
    leader.add_argument("--output", type=Path)
    train = subcommands.add_parser("train-model", help="fit a model artifact from a point-in-time JSONL dataset")
    train.add_argument("--dataset", required=True, type=Path)
    train.add_argument("--model", required=True, choices=("poisson", "rf"))
    train.add_argument("--output", required=True, type=Path)
    train_e11 = subcommands.add_parser(
        "train-e11-inference",
        help="persist a matching E3+E7+E8 Poisson model and E11 Platt calibrator",
    )
    train_e11.add_argument("--training-dataset", required=True, type=Path)
    train_e11.add_argument("--calibration-training-dataset", required=True, type=Path)
    train_e11.add_argument("--calibration-dataset", required=True, type=Path)
    train_e11.add_argument("--output", required=True, type=Path)
    predict_e11 = subcommands.add_parser(
        "predict-e11-inference",
        help="load a trusted E3+E7+E8/E11 artifact; never retrains",
    )
    predict_e11.add_argument("--artifact", required=True, type=Path)
    predict_e11.add_argument(
        "--features",
        required=True,
        type=Path,
        help="JSON object with exactly the artifact feature names in stored order",
    )
    daily_e11 = subcommands.add_parser(
        "daily-e11-inference",
        help="capture live inputs, snapshot E3+E7+E8, then infer with trusted E11",
    )
    daily_e11.add_argument("--date", required=True, type=date.fromisoformat)
    daily_e11.add_argument("--game-id", required=True)
    daily_e11.add_argument("--history-start", required=True, type=date.fromisoformat)
    daily_e11.add_argument("--artifact", required=True, type=Path)
    backtest = subcommands.add_parser("backtest", help="run expanding-window out-of-sample evaluation")
    backtest.add_argument("--dataset", required=True, type=Path)
    backtest.add_argument("--model", required=True, choices=("poisson", "rf", "compare"))
    backtest.add_argument("--min-train", type=int, default=30)
    backtest.add_argument("--test-window", type=int, default=10)
    backtest.add_argument("--simulations", type=int, default=5000)
    backtest.add_argument("--calibrate", action="store_true")
    backtest.add_argument("--format", choices=("text", "json"), default="text")
    return parser


def _http_client(settings: Settings) -> CachedHttpClient:
    return CachedHttpClient(
        settings.cache_dir,
        timeout_seconds=settings.http_timeout_seconds,
        retries=settings.http_retries,
        cache_ttl_seconds=settings.cache_ttl_seconds,
    )


def _run_daily_e11_inference(
    *,
    provider: MLBStatsProvider,
    database: KaizenDatabase,
    game_date: date,
    game_id: str,
    history_start: date,
    artifact_path: Path,
    prediction_timestamp: datetime,
) -> dict[str, Any]:
    """Fetch verified live inputs, persist the vector, then infer with E11."""

    games = provider.games_on(game_date)
    target = next((item for item in games if item.game_id == game_id), None)
    if target is None:
        raise ValueError(f"game_id {game_id!r} is not present in the requested schedule")
    snapshot = build_e8_daily_feature_snapshot(
        target,
        provider.completed_games(history_start, game_date),
        prediction_timestamp=prediction_timestamp,
    )
    artifact, metadata = load_e11_inference_artifact(artifact_path)
    prediction = artifact.predict(snapshot.features)
    database.initialise()
    database.store_game_snapshot(target)
    database.store_inference_feature_snapshot(snapshot)
    prediction_id = database.store_prediction(
        game_id=target.game_id,
        prediction_timestamp=snapshot.prediction_timestamp,
        data_timestamp=snapshot.source_timestamp,
        model_version=metadata.model_version,
        feature_version=snapshot.feature_schema_version,
        raw_probability=prediction.raw_home_win_probability,
        calibrated_probability=prediction.calibrated_home_win_probability,
        uncertainty=None,
        data_quality=1.0,
        model_input={
            "feature_schema_version": snapshot.feature_schema_version,
            "formula_version": snapshot.formula_version,
            "source_timestamp": snapshot.source_timestamp,
            "features": snapshot.features,
        },
        model_output={
            "experiment": metadata.experiment_id,
            "raw_home_win_probability": prediction.raw_home_win_probability,
            "calibrated_home_win_probability": prediction.calibrated_home_win_probability,
            "home_expected_runs": prediction.run_prediction.home_expected_runs,
            "away_expected_runs": prediction.run_prediction.away_expected_runs,
            "model_validation_status": "experimental",
        },
    )
    return {
        "status": "EXPERIMENTAL_PREGAME_PREDICTION_SAVED",
        "prediction_id": prediction_id,
        "game_id": target.game_id,
        "prediction_timestamp": snapshot.prediction_timestamp,
        "source_timestamp": snapshot.source_timestamp,
        "experiment": metadata.experiment_id,
        "raw_home_win_probability": prediction.raw_home_win_probability,
        "calibrated_home_win_probability": prediction.calibrated_home_win_probability,
        "home_expected_runs": prediction.run_prediction.home_expected_runs,
        "away_expected_runs": prediction.run_prediction.away_expected_runs,
        "note": "Experimental model output; not evidence of betting profitability.",
    }


def main(argv: list[str] | None = None) -> int:
    configure_logging()
    args = build_parser().parse_args(argv)
    settings = Settings.from_environment()
    database = KaizenDatabase(settings.database_path)

    if args.command == "init-db":
        database.initialise()
        print(f"SQLite initialized: {settings.database_path}")
        return 0
    if args.command == "health":
        database.initialise()
        print(json.dumps({
            "database": str(settings.database_path),
            "cache_dir": str(settings.cache_dir),
            "simulation_count": settings.simulation_count,
            "model_status": "baseline_plus_analyst_mode_experimental",
            "analyst_decisions": database.analyst_decision_count(),
            "predictions": database.prediction_count(),
        }, indent=2))
        return 0
    if args.command == "status":
        status_path = Path("STATUS.md")
        print(status_path.read_text(encoding="utf-8") if status_path.exists() else "STATUS.md NOT FOUND")
        return 0
    if args.command == "schedule":
        try:
            games = MLBStatsProvider(_http_client(settings)).games_on(args.date)
        except DataProviderError as exc:
            print(str(exc)); return 2
        database.initialise()
        for game in games:
            database.store_game_snapshot(game)
            print(f"{game.game_id}: {game.away_team_name} @ {game.home_team_name} ({game.start_time})")
        print(f"Retrieved {len(games)} games; source timestamp: {games[0].provenance.retrieved_at if games else 'n/a'}")
        return 0
    if args.command == "probable-pitchers":
        try:
            pitchers = MLBStatsProvider(_http_client(settings)).probable_pitchers_on(args.date)
        except DataProviderError as exc:
            print(str(exc)); return 2
        database.initialise()
        for pitcher in pitchers:
            database.store_probable_pitcher(pitcher)
            name = pitcher.pitcher_name if pitcher.pitcher_name else pitcher.status.value.upper()
            print(f"{pitcher.game_id} [{pitcher.team_id}]: {name}")
        print(f"Persisted {len(pitchers)} probable-pitcher records.")
        return 0
    if args.command == "lineups":
        try:
            game_lineups = MLBStatsProvider(_http_client(settings)).lineups_for(args.game_id)
        except DataProviderError as exc:
            print(str(exc)); return 2
        database.initialise(); database.store_lineups(game_lineups)
        print(f"{args.game_id}: {game_lineups.status.value.upper()}")
        if game_lineups.status == AvailabilityStatus.CONFIRMED:
            for slot in game_lineups.home_slots:
                print(f"  HOME {slot.batting_order}. {slot.player_name} ({slot.position})")
            for slot in game_lineups.away_slots:
                print(f"  AWAY {slot.batting_order}. {slot.player_name} ({slot.position})")
        return 0
    if args.command == "team-stats":
        try:
            stats = MLBStatsProvider(_http_client(settings)).team_season_stats(args.team_id, args.team_name, args.season)
        except DataProviderError as exc:
            print(str(exc)); return 2
        database.initialise(); database.store_team_season_stats(stats)
        print(f"{stats.team_name} ({stats.season}): {stats.games_played} GP, {stats.runs_scored} R, {stats.runs_allowed} RA")
        return 0
    if args.command == "run-profile":
        provider = MLBStatsProvider(_http_client(settings))
        try:
            stats = provider.team_season_stats(args.team_id, args.team_name, args.season)
            league_average = provider.league_average_runs_per_game(args.season)
            profile = compute_team_run_profile(stats, league_average)
        except DataProviderError as exc:
            print(str(exc)); return 2
        except ValueError as exc:
            print(f"DATA_NOT_VERIFIED: {exc}"); return 2
        database.initialise()
        database.store_team_season_stats(stats)
        database.store_team_run_profile(profile, args.season)
        print(f"{profile.team_name} ({args.season}): offensive_index={profile.offensive_index:.3f}, run_prevention_index={profile.run_prevention_index:.3f}, league_avg={league_average:.3f}")
        return 0
    if args.command == "odds":
        if not settings.sports_game_odds_api_key:
            print("DATA NOT VERIFIED: set MLB_KAIZEN_SGO_API_KEY before live odds retrieval.")
            return 2
        try:
            quotes = SportsGameOddsProvider(
                _http_client(settings),
                settings.sports_game_odds_api_key,
                settings.sports_game_odds_bookmakers,
            ).get_market_quotes(args.game_id)
        except (DataProviderError, ValueError) as exc:
            print(str(exc)); return 2
        database.initialise()
        for quote in quotes:
            database.store_market_quote(
                game_id=quote.game_id,
                sportsbook=quote.sportsbook,
                market=quote.market,
                selection=quote.selection,
                decimal_odds=quote.decimal_odds,
                captured_at=quote.captured_at,
                source=quote.source,
                line=quote.line,
                payload={"american_odds": quote.american_odds, "provider_event_id": quote.provider_event_id},
            )
        print(f"Persisted {len(quotes)} market quotes for {args.game_id}.")
        return 0
    if args.command == "weather":
        provider = MLBStatsProvider(_http_client(settings))
        try:
            venue = provider.venue_location(args.venue_id)
            forecast = NWSWeatherProvider(_http_client(settings)).forecast_for(args.game_id, venue, args.at)
        except DataProviderError as exc:
            print(str(exc)); return 2
        database.initialise(); database.store_weather(forecast)
        print(f"{args.game_id}: {forecast.status.value.upper()}")
        if forecast.temperature_fahrenheit is not None:
            print(f"{forecast.temperature_fahrenheit}F, wind {forecast.wind_speed_text or 'n/a'} {forecast.wind_direction or ''}, {forecast.short_forecast or 'n/a'}")
        return 0
    if args.command == "analyze":
        try:
            request = _parse_analysis_request(args.input, args.mode)
            if args.calibrator and not args.trained_model:
                raise ValueError("--calibrator requires --trained-model")
            run_model = None
            calibrator = None
            if args.trained_model:
                run_model, _ = TrainedPoissonAnalysisModel.from_artifact(args.trained_model)
            if args.calibrator:
                calibrator, _ = load_model_artifact(args.calibrator)
                if not isinstance(calibrator, PlattCalibrator):
                    raise ValueError("--calibrator must contain a PlattCalibrator artifact")
            if args.persist:
                database.initialise(); database.store_game_snapshot(request.game)
            result = AnalysisService(
                settings,
                database=database,
                run_model=run_model,
                calibrator=calibrator,
            ).analyse(request, persist=args.persist)
        except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
            print(f"Input rejected: {exc}"); return 2
        if args.format == "text":
            content = render_analysis_report(result)
        elif args.format == "html":
            content = render_analysis_html(result)
        else:
            content = json.dumps(result, default=_json_default, indent=2, sort_keys=True)
        _write_output(content, args.output)
        return 0
    if args.command == "record-human-pick":
        database.initialise()
        latest = database.latest_prediction_for_game(args.game_id)
        if latest is None:
            print("No prediction exists for this game."); return 2
        valid_selections = {
            "moneyline": {"home", "away"},
            "total": {"over", "under"},
            "run_line": {"home", "away"},
        }
        if args.selection not in valid_selections[args.market]:
            print(f"Invalid selection for {args.market}: {args.selection}")
            return 2
        if args.market in {"total", "run_line"} and args.line is None:
            print(f"--line is required for {args.market}")
            return 2
        human_pick = {"market": args.market, "selection": args.selection, "line": args.line, "decimal_odds": args.decimal_odds}
        machine_pick = latest["output"].get("machine_pick")
        decision_id = database.store_analyst_decision(
            game_id=args.game_id,
            prediction_id=args.prediction_id or latest["prediction_id"],
            input_mode=latest["input"].get("mode", "snapshot") if isinstance(latest.get("input"), dict) else "snapshot",
            data_quality=float(latest["data_quality"]),
            model_validation_status=str(latest["output"].get("model_validation_status", "experimental")),
            human_pick=human_pick,
            machine_pick=machine_pick,
        )
        print(f"Recorded human pick: {decision_id}")
        return 0
    if args.command == "record-result":
        database.initialise()
        recorded_at = args.recorded_at or datetime.now(UTC)
        result_id = database.store_result_snapshot(
            game_id=args.game_id,
            recorded_at=recorded_at,
            source=args.source,
            home_score=args.home_score,
            away_score=args.away_score,
        )
        print(f"Recorded result: {result_id}")
        return 0
    if args.command == "train-model":
        try:
            rows = load_jsonl(args.dataset)
            trainer = PoissonTrainer() if args.model == "poisson" else RandomForestTrainer()
            trainer.fit(rows)
            model = trainer.model
            metadata = ModelArtifactMetadata(
                model_version=getattr(model, "model_version", args.model),
                feature_version=getattr(model, "feature_version", "unknown"),
                training_rows=len(rows),
                training_max_prediction_timestamp=max(row.prediction_timestamp for row in rows).isoformat(),
                library="scikit-learn",
            )
            save_model_artifact(model, args.output, metadata)
            print(json.dumps({"status": "TRAINED", "model": args.model, "rows": len(rows), "artifact": str(args.output)}, indent=2))
            return 0
        except (OSError, ValueError, RuntimeError) as exc:
            print(f"Training failed: {exc}"); return 2
    if args.command == "train-e11-inference":
        try:
            artifact, metadata = train_e11_inference_artifact(
                load_jsonl(args.training_dataset),
                load_jsonl(args.calibration_training_dataset),
                load_jsonl(args.calibration_dataset),
            )
            save_e11_inference_artifact(artifact, args.output, metadata)
            print(json.dumps({
                "status": "TRAINED",
                "experiment": metadata.experiment_id,
                "schema": metadata.artifact_schema_version,
                "features": list(metadata.feature_names),
                "artifact": str(args.output),
            }, indent=2))
            return 0
        except (OSError, ValueError, RuntimeError) as exc:
            print(f"Training failed: {exc}"); return 2
    if args.command == "predict-e11-inference":
        try:
            payload = json.loads(args.features.read_text(encoding="utf-8"))
            if not isinstance(payload, dict):
                raise ValueError("features JSON must be an object")
            artifact, metadata = load_e11_inference_artifact(args.artifact)
            prediction = artifact.predict(payload)
            print(json.dumps({
                "experiment": metadata.experiment_id,
                "model_version": metadata.model_version,
                "raw_home_win_probability": prediction.raw_home_win_probability,
                "calibrated_home_win_probability": prediction.calibrated_home_win_probability,
                "home_expected_runs": prediction.run_prediction.home_expected_runs,
                "away_expected_runs": prediction.run_prediction.away_expected_runs,
            }, indent=2, sort_keys=True))
            return 0
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            print(f"Inference rejected: {exc}"); return 2
    if args.command == "daily-e11-inference":
        try:
            output = _run_daily_e11_inference(
                provider=MLBStatsProvider(_http_client(settings)),
                database=database,
                game_date=args.date,
                game_id=args.game_id,
                history_start=args.history_start,
                artifact_path=args.artifact,
                prediction_timestamp=datetime.now(UTC),
            )
            print(json.dumps(output, default=_json_default, indent=2, sort_keys=True))
            return 0
        except (DataProviderError, OSError, ValueError, RuntimeError) as exc:
            print(f"Daily inference rejected: {exc}"); return 2
    if args.command == "backtest":
        try:
            rows = load_jsonl(args.dataset)
            trainer_factories = {
                "poisson": lambda: PoissonTrainer(),
                "rf": lambda: RandomForestTrainer(),
            }
            names = ("poisson", "rf") if args.model == "compare" else (args.model,)
            summaries = tuple(
                walk_forward_evaluate(
                    rows, trainer_factories[name], name, min_train_size=args.min_train,
                    test_window=args.test_window, simulation_count=args.simulations
                )
                for name in names
            )
            comparison = ModelComparison(summaries)
            output: dict[str, Any] = {
                "models": list(comparison.as_rows()),
                "empirical_validation_status": "NOT_VERIFIED",
                "note": "Synthetic/demo data may verify execution but is not evidence of real predictive performance."
            }
            if args.calibrate:
                calibrations = {}
                for summary in summaries:
                    probabilities = [row.home_win_probability for row in summary.predictions]
                    outcomes = [int(row.home_runs > row.away_runs) for row in summary.predictions]
                    calibrations[summary.model_name] = _json_default(temporal_calibration_report(probabilities, outcomes))
                output["temporal_calibration"] = calibrations
            if args.format == "json":
                print(json.dumps(output, indent=2, sort_keys=True, default=_json_default))
            else:
                print("WALK-FORWARD MODEL COMPARISON")
                print("Empirical validation: NOT VERIFIED")
                for row in comparison.as_rows():
                    print(
                        f"{row['model']}: N={row['sample_size']} | home MAE={row['home_run_mae']:.3f} | "
                        f"away MAE={row['away_run_mae']:.3f} | total RMSE={row['total_run_rmse']:.3f} | "
                        f"Brier={row['brier']:.4f} | LogLoss={row['log_loss']:.4f} | accuracy={row['accuracy']:.2%}"
                    )
                if args.calibrate:
                    for name, cal in output["temporal_calibration"].items():
                        print(f"{name} calibration: n={cal['calibration_size']} | eval={cal['evaluation_size']} | raw Brier={cal['raw_brier']:.4f} | calibrated Brier={cal['calibrated_brier']:.4f}")
            return 0
        except (OSError, ValueError, RuntimeError) as exc:
            print(f"Backtest failed: {exc}"); return 2
    if args.command == "leaderboard":
        database.initialise()
        rows = database.leaderboard_rows()
        summary = leaderboard(rows)
        if args.format == "html":
            content = render_leaderboard_html(rows)
        elif args.format == "json":
            content = json.dumps(summary, indent=2, sort_keys=True, default=_json_default)
        else:
            content = (
                "MLB KAIZEN — HUMAN VS MACHINE\n"
                f"Machine: {summary['machine_correct']}/{summary['machine_settled']} = {summary['machine_accuracy'] if summary['machine_accuracy'] is not None else 'DATA NOT VERIFIED'}\n"
                f"Human:   {summary['human_correct']}/{summary['human_settled']} = {summary['human_accuracy'] if summary['human_accuracy'] is not None else 'DATA NOT VERIFIED'}\n"
                f"Records: {summary['records']}"
            )
        _write_output(content, args.output)
        return 0
    raise AssertionError(f"unknown command: {args.command}")
