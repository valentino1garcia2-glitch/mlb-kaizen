# Contrato de input para `analyze`

El comando acepta JSON con identificadores de equipo, perfiles normalizados y
procedencia verificable. Los valores de `offensive_index` y
`run_prevention_index` son índices relativos a la liga; no son métricas crudas
ni deben inventarse. Si todavía no existe un pipeline que los produzca a partir
de snapshots históricos, el análisis debe esperar.

```json
{
  "game": {
    "game_id": "mlb:PROVIDER_GAME_ID",
    "official_date": "YYYY-MM-DD",
    "home_team_id": "PROVIDER_TEAM_ID",
    "home_team_name": "HOME TEAM",
    "away_team_id": "PROVIDER_TEAM_ID",
    "away_team_name": "AWAY TEAM",
    "provenance": {
      "source": "provider name",
      "retrieved_at": "YYYY-MM-DDTHH:MM:SS+00:00",
      "status": "available"
    }
  },
  "home_profile": {
    "team_id": "PROVIDER_TEAM_ID",
    "team_name": "HOME TEAM",
    "offensive_index": 1.0,
    "run_prevention_index": 1.0,
    "sample_size": 0,
    "data_quality": 0.0,
    "provenance": {
      "source": "verified feature store",
      "retrieved_at": "YYYY-MM-DDTHH:MM:SS+00:00",
      "status": "available"
    }
  },
  "away_profile": { "same schema as home_profile": "" },
  "context": {
    "prediction_timestamp": "YYYY-MM-DDTHH:MM:SS+00:00",
    "information_state": "T-6H",
    "data_statuses": {
      "starting_pitchers": "confirmed",
      "lineups": "projected",
      "odds": "available"
    }
  },
  "market": {
    "home_decimal_odds": 0,
    "away_decimal_odds": 0,
    "total_line": 0,
    "home_run_line": 0
  }
}
```

The numeric values above are placeholders, not data or recommended inputs.
Use `available`, `projected`, `confirmed`, `missing`, `not_available`,
`not_yet_published`, `stale` or `unknown` for statuses. An uncalibrated model
returns `MODEL_UNCALIBRATED`; it cannot issue a betting signal.
