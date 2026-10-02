#!/usr/bin/env python3
"""Create a recoverable milestone ZIP, optional local copy, and optional Git tag."""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import zipfile
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXCLUDED = {".git", "__pycache__", ".pytest_cache", ".mypy_cache", "node_modules", ".venv"}

def git(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=ROOT, text=True, capture_output=True)

def ensure_clean_for_tag() -> None:
    result = git("status", "--porcelain")
    if result.returncode != 0:
        raise RuntimeError("Git tag requested, but this is not a Git repository.")
    if result.stdout.strip():
        raise RuntimeError("Git tag requested, but the working tree is not clean.")

def create_zip(destination: Path) -> Path:
    destination.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    archive_base = destination / f"{ROOT.name}-{stamp}"
    archive = archive_base.with_suffix(".zip")
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
        for candidate in ROOT.rglob("*"):
            relative = candidate.relative_to(ROOT)
            if not candidate.is_file() or any(part in EXCLUDED for part in relative.parts):
                continue
            # The default archive location is inside .agent; never capture an
            # archive while it is being written or previous archive files.
            if relative.parts[:2] == (".agent", "backups") or candidate.resolve() == archive.resolve():
                continue
            bundle.write(candidate, relative.as_posix())
    return archive

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--zip", action="store_true", help="Create a ZIP in .agent/backups.")
    parser.add_argument("--destination", type=Path, help="Directory for ZIP output (implies --zip).")
    parser.add_argument("--copy", type=Path, help="Copy the created ZIP to an already mounted secondary location.")
    parser.add_argument("--tag", help="Create an annotated Git milestone tag; requires a clean working tree.")
    args = parser.parse_args()
    if not (args.zip or args.destination or args.copy or args.tag):
        parser.error("choose --zip, --destination, --copy, or --tag")
    if args.tag:
        try:
            ensure_clean_for_tag()
        except RuntimeError as error:
            print(f"BACKUP FAILED: {error}", file=sys.stderr)
            return 1
        result = git("tag", "-a", args.tag, "-m", f"Milestone {args.tag}")
        if result.returncode:
            print(result.stderr.strip(), file=sys.stderr)
            return result.returncode
        print(f"Created Git tag: {args.tag}. Push it explicitly with: git push origin {args.tag}")
    archive: Path | None = None
    if args.zip or args.destination or args.copy:
        archive = create_zip(args.destination or ROOT / ".agent" / "backups")
        print(f"Created ZIP: {archive}")
    if args.copy:
        if archive is None:
            print("BACKUP FAILED: no archive to copy", file=sys.stderr)
            return 1
        args.copy.mkdir(parents=True, exist_ok=True)
        target = args.copy / archive.name
        shutil.copy2(archive, target)
        print(f"Copied ZIP: {target}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
