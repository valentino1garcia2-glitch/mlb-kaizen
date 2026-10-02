# MLB KAIZEN architecture

## Scope

MLB KAIZEN is a local, reproducible quantitative-analysis foundation. It must return incomplete or uncalibrated states instead of manufacturing a betting signal. The currently available code is the foundation archive only; its `HANDOFF.md` describes the implemented domain, schedule provider, SQLite persistence, market math, transparent run baseline, simulation, CLI, and tests.

## Components and data flow

`data/` adapters obtain and cache source data; `domain/` holds typed, provenance-aware objects; `validation/` blocks incomplete inputs; `models/` calculates transparent run expectations; `simulation/` derives distributions; `market/` calculates labelled market metrics; `services/`, `reporting/`, and `interface/` expose results. `storage/` persists snapshots locally.

Historical game records are stored locally under `data/mlb_kaizen_data/`. Their source manifest reports 12,030 final games from 2022–2026, produced on 2026-09-19. They are an input artifact, ignored by Git, and must not be replaced or regenerated without a recorded provenance decision.

## Recovery and change map

`STATUS.md` and `.agent/checkpoint.json` are concise recovery memory; Git is the versioned evidence when a remote is configured. The operating-system scripts are in `scripts/`; recurring procedures are available in `.codex/skills/`. Before E6 or any modeling change, recover the missing E2–E5 source and its tests. Then locate the relevant evaluation record and use a time-aware, point-in-time test plan.
