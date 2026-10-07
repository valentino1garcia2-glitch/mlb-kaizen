#!/usr/bin/env python3
"""Update .agent/checkpoint.json's verifiable fields from the real repo state.

Only touches what can be measured mechanically: test pass/fail counts (by
running the full suite) and the current git commit hash. Never edits phase
status, blockers, or next_action -- those are judgment calls for the agent
to make explicitly, per AGENTS.md's "no debe inventar estados" rule.

Usage:
    python3 scripts/checkpoint.py
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CHECKPOINT_PATH = REPO_ROOT / ".agent" / "checkpoint.json"
STATUS_PATH = REPO_ROOT / "STATUS.md"


def run_suite() -> tuple[int, int]:
    """Return (passed, total) by parsing unittest's own summary line."""

    result = subprocess.run(
        [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-t", "."],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    output = result.stdout + result.stderr
    match = re.search(r"Ran (\d+) tests?", output)
    total = int(match.group(1)) if match else 0
    passed = total if result.returncode == 0 else 0
    if result.returncode != 0:
        print("WARNING: suite did not pass -- checkpoint will record 0 passed", file=sys.stderr)
        print(output[-2000:], file=sys.stderr)
    return passed, total


def current_commit() -> str | None:
    result = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def main() -> int:
    passed, total = run_suite()
    commit = current_commit()

    if CHECKPOINT_PATH.exists():
        data = json.loads(CHECKPOINT_PATH.read_text(encoding="utf-8"))
    else:
        data = {}

    data["checkpoint_date"] = date.today().isoformat()
    data["tests_passed"] = passed
    data["tests_total"] = total
    data["last_verified_commit"] = commit

    CHECKPOINT_PATH.parent.mkdir(parents=True, exist_ok=True)
    CHECKPOINT_PATH.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")

    if STATUS_PATH.exists():
        status_text = STATUS_PATH.read_text(encoding="utf-8")
        status_text = re.sub(r"(?m)^commit: .*$", f"commit: {commit or '(no commits)'}", status_text)
        status_text = re.sub(r"(?m)^```\n\d+ / \d+ PASS\n```", f"```\n{passed} / {total} PASS\n```", status_text)
        STATUS_PATH.write_text(status_text, encoding="utf-8")

    print(f"tests: {passed}/{total}  commit: {commit or '(no commits)'}")
    print("Phase status, blockers and next_action were NOT changed -- edit them explicitly if they changed.")
    return 0 if passed == total and total > 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
