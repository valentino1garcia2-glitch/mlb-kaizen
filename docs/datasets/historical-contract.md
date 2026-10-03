# Historical training dataset contract

Canonical interchange for the current training/evaluation machinery: UTF-8 JSONL.

Each line must contain:

```json
{
  "game_id": "...",
  "official_date": "YYYY-MM-DD",
  "prediction_timestamp": "ISO-8601 with UTC offset",
  "feature_timestamp": "ISO-8601 with UTC offset",
  "features": {
    "home_offensive_index": 1.0,
    "away_offensive_index": 1.0,
    "home_run_prevention_index": 1.0,
    "away_run_prevention_index": 1.0,
    "home_advantage": 1.0
  },
  "home_runs": 0,
  "away_runs": 0
}
```

The loader rejects empty datasets, malformed timestamps, missing features, negative targets, and
future feature timestamps.

Real validation requires real historical rows. Demo/synthetic rows are never evidence of model quality.
