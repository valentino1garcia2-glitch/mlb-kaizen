# Claude recovery artifact — domain models

## Source

- Received: 2026-10-03 from a user-provided Claude chat export.
- Artifact: one complete Python module containing provider-independent domain records.
- SHA-256 of the received text: `91D44744BC0A2369C9BAF3CBA36F33FCA75A995D1E4EA52F2D8B7D5BD58C89A1`.

## Recovered scope

The artifact exactly extends `mlb_kaizen/domain/models.py` with analysis, calculation, data-quality, and model-validation enums; completed-game, pitcher-line, probable-pitcher, lineup, venue, weather, and raw team-season records.

This is partial E2 recovery only. It contains no providers, persistence, migrations, feature-store logic, training dataset, evaluation experiment, or evidence for E3–E5.

## Verification

- Targeted: `python -m unittest tests.test_recovered_domain_records -v` — 4/4 PASS.
- Full: `python -m unittest discover -s tests -t . -v` — 13/13 PASS.
- `git diff --check` — PASS.
