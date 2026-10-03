#!/usr/bin/env python3
"""Impact-aware verification for MLB KAIZEN.

Run without arguments. Unknown Python changes trigger the full suite. Known isolated changes run
only their affected test modules first, while schema/migration/domain/CLI changes trigger the full suite.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

IMPACT_TESTS = {
    "mlb_kaizen/features/run_profile.py": "tests.test_run_profile",
    "mlb_kaizen/data/mlb_stats.py": "tests.test_mlb_stats",
    "mlb_kaizen/data/weather.py": "tests.test_weather",
    "mlb_kaizen/data/odds.py": "tests.test_odds_provider",
    "mlb_kaizen/market/odds.py": "tests.test_odds",
    "mlb_kaizen/models/baseline.py": "tests.test_baseline_and_simulation",
    "mlb_kaizen/simulation/monte_carlo.py": "tests.test_baseline_and_simulation",
    "mlb_kaizen/services/analysis.py": "tests.test_analysis_service tests.test_analyst_mode",
    "mlb_kaizen/reporting/text.py": "tests.test_analyst_mode",
    "mlb_kaizen/reporting/html.py": "tests.test_analyst_mode tests.test_tracking",
    "mlb_kaizen/tracking/human_machine.py": "tests.test_tracking",
    "mlb_kaizen/training/dataset.py": "tests.test_training",
    "mlb_kaizen/training/baseline.py": "tests.test_training",
    "mlb_kaizen/training/trainers.py": "tests.test_training",
    "mlb_kaizen/training/artifacts.py": "tests.test_training",
    "mlb_kaizen/models/ml.py": "tests.test_training tests.test_evaluation",
    "mlb_kaizen/evaluation/metrics.py": "tests.test_evaluation",
    "mlb_kaizen/evaluation/walk_forward.py": "tests.test_evaluation",
    "mlb_kaizen/evaluation/calibration.py": "tests.test_evaluation",
    "mlb_kaizen/evaluation/compare.py": "tests.test_evaluation",
    "mlb_kaizen/validation/quality.py": "tests.test_quality tests.test_analysis_service tests.test_analyst_mode",
    "mlb_kaizen/validation/schema.py": "tests.test_schema",
}
FULL_SUITE_HINTS = (
    "mlb_kaizen/domain/",
    "mlb_kaizen/storage/",
    "mlb_kaizen/interface/",
    "pyproject.toml",
    "docs/schemas/",
    "scripts/",
)


def changed_files() -> list[str]:
    tracked = subprocess.run(
        ["git", "diff", "--name-only", "HEAD"], cwd=ROOT, text=True, capture_output=True, check=True
    )
    untracked = subprocess.run(
        ["git", "ls-files", "--others", "--exclude-standard"],
        cwd=ROOT, text=True, capture_output=True, check=True,
    )
    return sorted({line.strip() for line in (tracked.stdout + "\n" + untracked.stdout).splitlines() if line.strip()})


def run(command: list[str]) -> int:
    print("$", " ".join(command))
    return subprocess.run(command, cwd=ROOT).returncode


def main() -> int:
    compile_code = [sys.executable, "-m", "compileall", "-q", "mlb_kaizen", "tests"]
    if run(compile_code) != 0:
        return 1
    changed = changed_files()
    if not changed:
        return run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-t", ".", "-q"])

    full = any(any(path.startswith(prefix) for prefix in FULL_SUITE_HINTS) for path in changed)
    if not full:
        modules: list[str] = []
        unknown = False
        for path in changed:
            if path.startswith("tests/"):
                continue
            mapped = IMPACT_TESTS.get(path)
            if mapped:
                modules.extend(mapped.split())
            elif path.endswith(".py"):
                unknown = True
                break
        full = unknown or not modules
        if not full:
            modules = sorted(set(modules))
            print("Targeted verification:", ", ".join(modules))
            for module in modules:
                if run([sys.executable, "-m", "unittest", module, "-q"]) != 0:
                    return 1
            return 0
    return run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-t", ".", "-q"])


if __name__ == "__main__":
    raise SystemExit(main())
