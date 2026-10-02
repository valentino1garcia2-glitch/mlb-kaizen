#!/usr/bin/env python3
"""Refresh machine-readable project state without creating a commit or push."""
from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHECKPOINT = ROOT / ".agent" / "checkpoint.json"

def git(*args: str) -> str | None:
    result = subprocess.run(["git", *args], cwd=ROOT, text=True, capture_output=True)
    return result.stdout.strip() if result.returncode == 0 else None

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--next-action", help="Replace the next action.")
    parser.add_argument("--focused", help="Record focused verification result.")
    parser.add_argument("--full", help="Record full-suite verification result.")
    args = parser.parse_args()
    data = json.loads(CHECKPOINT.read_text(encoding="utf-8"))
    status = git("status", "--porcelain")
    remote = git("remote", "get-url", "origin")
    data["updated_at"] = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    data["git"].update({
        "commit": git("rev-parse", "HEAD"),
        "branch": git("branch", "--show-current"),
        "working_tree": "clean" if status == "" else ("dirty" if status is not None else "not a git repository"),
        "remote": remote,
    })
    if args.next_action:
        data["next_action"] = args.next_action
    if args.focused:
        data["verification"]["focused"] = args.focused
    if args.full:
        data["verification"]["full"] = args.full
    CHECKPOINT.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print(f"Checkpoint updated: {CHECKPOINT}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
