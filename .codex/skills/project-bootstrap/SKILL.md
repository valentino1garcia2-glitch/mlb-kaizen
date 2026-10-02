---
name: project-bootstrap
description: Bootstrap a new repository with AI Project Operating System state, recovery records, and lightweight verification.
---

# Project bootstrap

Copy the approved operating-system files into the target repository without overwriting project-specific instructions. Fill placeholders from observable project facts. Initialize Git or configure a remote only when authorized. Run `python scripts/verify.py`; record any unconfigured remote or backup as pending, not active. End with a focused baseline commit and push when a remote is available and the user authorizes it.
