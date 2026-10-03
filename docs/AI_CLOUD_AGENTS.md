# Cloud agents — MLB KAIZEN

## Roles

- **Lead agent:** owns architecture, integration, Git, tests, and checkpoints.
- **Worker agent:** completes one isolated task packet.
- **Reviewer agent:** audits a change without editing the same implementation unless explicitly assigned.

## When to parallelize

Parallelize work only when tasks are independent and have isolated file scopes. Good examples:
provider audit + test audit + documentation. Avoid parallelizing tightly coupled changes or trivial edits.

## Task packet

Each cloud task should include:

```text
TASK:
OBJECTIVE:
KNOWN CONTEXT:
FILES ALLOWED:
FILES FORBIDDEN:
TESTS TO RUN:
EXPECTED EVIDENCE:
STOP CONDITIONS:
```

## Return contract

Workers return only:

```text
RESULT:
FILES CHANGED:
TESTS:
EVIDENCE:
BLOCKERS:
RECOMMENDATION:
```

## Integration rule

The lead agent reviews each result, resolves conflicts, runs the relevant tests, then updates
`STATUS.md` and `.agent/checkpoint.json` at a meaningful checkpoint.

## Token-efficiency rule

Workers must not reread `HANDOFF.md`, the whole README, or unrelated modules unless the task packet
or a discovered dependency proves it is necessary.
