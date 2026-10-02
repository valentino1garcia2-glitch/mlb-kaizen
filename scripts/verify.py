#!/usr/bin/env python3
"""Verify the AI Project Operating System layout and basic state."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REQUIRED = (
    "AGENTS.md", "STATUS.md", "HANDOFF.md", ".agent/checkpoint.json", ".agent/recovery.md",
    "docs/architecture.md", "docs/decisions.md", "docs/experiments/README.md",
    "docs/tooling-guide.md", ".gitignore", "scripts/verify.py", "scripts/checkpoint.py", "scripts/backup.py",
)
SKILLS = ("project-bootstrap", "project-recovery", "project-checkpoint", "experiment-runner", "research-audit", "project-handoff")

def git(*args: str) -> tuple[int, str]:
    result = subprocess.run(["git", *args], cwd=ROOT, text=True, capture_output=True)
    return result.returncode, (result.stdout or result.stderr).strip()

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--quick", action="store_true", help="Skip optional Git checks.")
    args = parser.parse_args()
    failures: list[str] = []
    for relative in REQUIRED:
        if not (ROOT / relative).is_file():
            failures.append(f"missing required file: {relative}")
    try:
        data = json.loads((ROOT / ".agent/checkpoint.json").read_text(encoding="utf-8"))
        for key in ("schema_version", "git", "verification", "state", "next_action"):
            if key not in data:
                failures.append(f"checkpoint missing key: {key}")
    except (OSError, json.JSONDecodeError) as error:
        failures.append(f"invalid checkpoint JSON: {error}")
    for skill in SKILLS:
        skill_file = ROOT / ".codex" / "skills" / skill / "SKILL.md"
        if not skill_file.is_file():
            failures.append(f"missing skill: {skill}")
        elif not skill_file.read_text(encoding="utf-8").lstrip().startswith("---"):
            failures.append(f"skill front matter missing: {skill}")
    if not args.quick:
        code, output = git("rev-parse", "--is-inside-work-tree")
        print("Git:", output if code == 0 else "not initialized (acceptable during bootstrap)")
    if failures:
        print("VERIFY FAILED")
        print("\n".join(f"- {failure}" for failure in failures))
        return 1
    print(f"VERIFY PASS: {len(REQUIRED)} core files and {len(SKILLS)} skills present.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
