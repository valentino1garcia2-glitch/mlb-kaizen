# Decisions

Record durable decisions in short append-only entries.

## Template

### YYYY-MM-DD — Decision title

- Context: [why it mattered]
- Decision: [what was chosen]
- Consequences: [tradeoffs and follow-up]
- Evidence: [test, benchmark, issue, or source]

## 2026-10-01 — AI Project Operating System v1 baseline

- Context: Projects need recoverable state without relying on chats or temporary servers.
- Decision: Git remote is canonical; checkpoint/status/handoff documents provide concise operating memory; ZIP/copy backups are optional secondary recovery layers.
- Consequences: Each stable block must be committed and pushed when a remote is available. External integrations remain unconfigured until verified.
- Evidence: Initial template verification.

## 2026-10-01 — Preserve, do not reconstruct, unavailable E2–E5 work

- Context: A prior migration note reports `94/94 PASS, 2 skipped`, E2–E5 reconstructed, and E6 not started. The current environment contains only an older foundation code archive (9 historical tests, no commits), a dataset archive, and no remote.
- Decision: Treat the reported E2–E5 state as historical context, not current evidence. Create a recoverable checkout of the available archive and block E6 planning until the newer code or its canonical remote is restored.
- Consequences: No model, feature, split, experiment, or data logic is reconstructed from a chat summary. The baseline test result will be recorded independently.
- Evidence: `STATUS.md`, `.agent/checkpoint.json`, and the archive hashes recorded there.
