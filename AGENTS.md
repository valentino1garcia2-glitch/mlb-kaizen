# MLB KAIZEN operating contract

## Source of truth

Start each work block with `STATUS.md`, `.agent/checkpoint.json`, Git state, and only the files relevant to `next_action`. Preserve user changes. Chats, temporary servers, and local archives are not the only copy.

## Data and modeling

Never invent or silently substitute MLB statistics, odds, lineups, pitchers, injuries, results, API responses, or backtest results. Keep provenance. Historical features must be point-in-time: no game outcome or later information may reach a prior prediction. Do not change models, features, data splits, or experiment results without a narrowly scoped task and temporal validation.

## Workflow

Use focused tests during implementation and the fuller suite at a stable boundary. Then update `STATUS.md` and `.agent/checkpoint.json`, make one recoverable commit, push if a verified remote exists, and leave a clean tree. Follow `.agent/recovery.md` after interruption. Keep permanent instructions short; use `.codex/skills/` only for applicable workflows.
