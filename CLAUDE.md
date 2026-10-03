# CLAUDE.md — MLB KAIZEN

`STATUS.md` is the first state source. `AGENTS.md` contains the operating rules.
Do not reread the whole repository unless the task genuinely requires it.
Use `docs/AI_REPO_MAP.md` to locate code/spec/tests, then read only the relevant set.
Use `git status`/`git diff` for incremental context and targeted tests before full-suite runs.

For cloud/subagents: parallelize independent work only; give each agent an explicit task packet and
file scope; never have independent agents silently edit the same file; the lead agent reviews,
integrates, verifies, and updates the checkpoint.

Do not invent MLB data, odds, injuries, lineups, pitchers, weather, API responses, backtests, or
performance. `MODEL_UNCALIBRATED` is a validation label, not a calculation lock. Prefer explicit
`live`, `snapshot`, `manual`, and `hybrid` modes over a generic `--force` bypass.
