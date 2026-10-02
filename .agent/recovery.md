# Recovery protocol

Use this after a lost session, a failed environment, a handoff, or uncertainty about state.

1. Read `.agent/checkpoint.json` for the intended state and next action.
2. Run `git log --oneline -10`, `git status --short --branch`, and `git remote -v`; Git is the evidence for what actually persisted.
3. Run the fastest relevant test or `python scripts/verify.py --quick`.
4. Read `STATUS.md`, reconcile it with Git/test evidence, and update it if stale.
5. Continue only with `next_action` or an explicitly documented safe correction. Record any mismatch in `STATUS.md` and the checkpoint.

If the environment is disposable, first clone or restore the canonical remote. If no remote exists, recover from the newest verified ZIP or secondary copy; never overwrite the only remaining copy without first preserving it elsewhere.
