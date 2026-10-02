---
name: project-recovery
description: Resume a disrupted project safely from its checkpoint, Git evidence, focused tests, and current status.
---

# Project recovery

Read `.agent/checkpoint.json`, then validate it against `git log`, `git status`, configured remotes, and the fastest relevant test. Read and reconcile `STATUS.md` only after those facts. Preserve uncommitted work. Continue only with a documented next action or a narrowly justified correction, and record any discrepancy in durable project state.
