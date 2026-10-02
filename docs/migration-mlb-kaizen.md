# MLB Kaizen migration route

## Preserved state

- Verification baseline: **94/94 PASS, 2 skipped**.
- Reconstruction: **E2-E5 reconstructed**.
- Next model phase: **E6 not started**.

This migration is operational only. It must not alter model logic, training data, features, data splits, results, or experiment code.

## Safe sequence

1. In the existing MLB Kaizen repository, create a safety commit/tag only after confirming the recorded baseline and preserving any user changes.
2. Copy this template's operational files into the repository. Merge with existing `AGENTS.md`, `STATUS.md`, or docs rather than overwriting project-specific instructions.
3. Set `STATUS.md` and `.agent/checkpoint.json` to the preserved state above; set the next action to inspect and plan E6, not implement it.
4. Run the repository's existing verification suite and record the exact command/result. Expect the known baseline unless the project state shows otherwise.
5. Commit this operational migration separately, push the remote, and optionally create a milestone tag/ZIP.
6. Only in a later, explicitly scoped work block, begin E6 from the documented checkpoint.

## Do not assume

This workspace did not contain an identifiable MLB Kaizen repository, so no live files were changed and no claim is made about its Git remote or integration status.
