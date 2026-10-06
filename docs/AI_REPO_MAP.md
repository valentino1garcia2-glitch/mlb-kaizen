# AI_REPO_MAP.md

Mapa de navegación: pregunta → código → especificación → tests. Actualizar cuando se agregue una
feature nueva. Este archivo evita exploración redundante del repositorio.

## Configuración / agente

```text
Runtime settings            mlb_kaizen/config/settings.py
Agent rules                 AGENTS.md
Claude entrypoint           CLAUDE.md
Project state               STATUS.md
Machine checkpoint          .agent/checkpoint.json
Cloud-agent protocol        docs/AI_CLOUD_AGENTS.md
```

## Dominio

```text
Game, DataProvenance,
ProbablePitcher, Lineups,
GameWeather, TeamSeasonStats,
TeamRunProfile, AnalysisContext,
analysis status enums        mlb_kaizen/domain/models.py
                              tests/test_domain_models.py
```

## Proveedores / datos

```text
MLB schedule/pitchers/lineups/venue/team stats/league average
                             mlb_kaizen/data/mlb_stats.py
                             tests/test_mlb_stats.py
NWS weather                  mlb_kaizen/data/weather.py
                             tests/test_weather.py
Provider contracts           mlb_kaizen/data/providers.py
SportsGameOdds odds adapter   mlb_kaizen/data/odds.py          tests/test_odds_provider.py
                              live provider still NOT VERIFIED; docs/odds-provider.md
Statcast                     NOT IMPLEMENTED / not verified
```

## Features

```text
TeamRunProfile               mlb_kaizen/features/run_profile.py
                             docs/features/run_profile.md
                             tests/test_run_profile.py
Opponent strength (E7)       mlb_kaizen/training/build_dataset.py
                             docs/features/opponent_strength.md
Recent form (E8)             mlb_kaizen/training/build_dataset.py
                             docs/features/recent_form.md
Daily E3+E7+E8 snapshot      mlb_kaizen/features/e8_daily_snapshot.py
                             docs/features/e8_daily_snapshot.md
Rest days (E9, negative)     mlb_kaizen/training/build_dataset.py
                             docs/features/rest_days.md
Site splits (E10, negative)  mlb_kaizen/training/build_dataset.py
                             docs/features/site_splits.md
League average definition    docs/features/league_average.md
```

## Mercado / simulación

```text
Odds conversion/no-vig/EV/Kelly
                             mlb_kaizen/market/odds.py
                             tests/test_odds.py
Baseline transparent runs    mlb_kaizen/models/baseline.py
                             tests/test_baseline_and_simulation.py
Monte Carlo                  mlb_kaizen/simulation/monte_carlo.py
```

## Analyst Mode

```text
Analysis orchestration       mlb_kaizen/services/analysis.py
CLI                          mlb_kaizen/interface/cli.py
Text report                  mlb_kaizen/reporting/text.py
HTML reports                 mlb_kaizen/reporting/html.py
Human vs Machine             mlb_kaizen/tracking/human_machine.py
                             tests/test_analyst_mode.py
                             tests/test_tracking.py
```

## Training / evaluation

```text
Historical dataset contract  mlb_kaizen/training/dataset.py
Poisson trainable baseline   mlb_kaizen/training/baseline.py
Trainer adapters              mlb_kaizen/training/trainers.py
ML challenger                 mlb_kaizen/models/ml.py
Artifacts                     mlb_kaizen/training/artifacts.py
E3+E7+E8/E11 inference        mlb_kaizen/training/inference_artifact.py
                             docs/inference-artifacts.md
Metrics                       mlb_kaizen/evaluation/metrics.py
Walk-forward                  mlb_kaizen/evaluation/walk_forward.py
Calibration                   mlb_kaizen/evaluation/calibration.py
Model comparison              mlb_kaizen/evaluation/compare.py
Protocol                      docs/evaluation/protocol.md
                             tests/test_training.py
                             tests/test_evaluation.py
```

## Persistencia

```text
KaizenDatabase               mlb_kaizen/storage/database.py
Migrations                    mlb_kaizen/storage/migrations.py
                             tests/test_database.py
```

## Validación

```text
QualityGate                   mlb_kaizen/validation/quality.py
Input JSON schema              mlb_kaizen/validation/schema.py
Schema document                docs/schemas/analysis-input.schema.json
                             tests/test_quality.py
                             tests/test_schema.py
```

## Automatización del agente

```text
Impact-aware verification     scripts/verify.py
Checkpoint updater            scripts/checkpoint.py
Snapshot strategy             docs/snapshot-policy.md
```
