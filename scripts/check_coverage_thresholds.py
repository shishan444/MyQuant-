#!/usr/bin/env python3
"""Per-module coverage threshold checker.

pytest-cov's ``--cov-fail-under`` only supports a single global floor. This
script adds per-module granularity by reading ``coverage.json`` (produced by
``--cov-report=json``) and checking each module group against its own floor.

Usage::

    venv/bin/python -m pytest tests/ --ignore=tests/e2e          # writes coverage.json
    venv/bin/python scripts/check_coverage_thresholds.py          # checks floors

Exit code 1 if any module group is below its floor. Floors are set
conservatively at "current coverage" (anti-regression baselines); raise them
as coverage improves (target values are noted inline for batch-2 follow-up).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

# Per-file floors (file-level, not prefix — a prefix min would be dragged
# down by the worst file in a directory). Values = measured coverage as of
# 2026-06-19 (anti-regression baselines, rounded down). Raise to the target
# values (noted inline) as batch-2/4 补测 lands.
THRESHOLDS: dict[str, float] = {
    # --- orchestration (currently sparse; baseline = current) ---
    "core/evolution/diversity.py": 13,            # 13.9% -> target 80 (batch-2)
    "core/validation/engine.py": 26,              # 26.2% -> target 70 (batch-2)
    "core/validation/rule_engine.py": 20,         # 20.4% -> target 70 (batch-2)
    "core/validation/scene/scene_engine.py": 38,  # 38.7%
    "core/trading/runner.py": 47,                 # 47.6% -> target 75 (batch-4)
    "core/data/fetcher.py": 57,                   # 57.4%
    # --- API layer ---
    "api/routes/strategies.py": 30,               # ~32% -> target 60 (batch-4)
    "api/routes/evolution.py": 43,                # 43.8%
}


def main(argv: list[str]) -> int:
    cov_path = Path(argv[1]) if len(argv) > 1 else Path("coverage.json")
    if not cov_path.exists():
        print(f"[coverage-thresholds] {cov_path} not found — skipping (run pytest first)")
        return 0
    data = json.loads(cov_path.read_text())
    files: dict[str, dict] = data.get("files", {})

    violations: list[str] = []
    checked = 0
    for prefix, floor in THRESHOLDS.items():
        matched = [
            (p, s["summary"]["percent_covered"])
            for p, s in files.items()
            if p.startswith(prefix) or p == prefix
        ]
        if not matched:
            continue
        worst_path, worst_pct = min(matched, key=lambda x: x[1])
        checked += 1
        if worst_pct < floor:
            violations.append(
                f"  {worst_path}: {worst_pct:.1f}% < {floor:g}% (floor for {prefix})"
            )
    if violations:
        print("[coverage-thresholds] FAIL — module groups below floor:")
        print("\n".join(violations))
        return 1
    print(f"[coverage-thresholds] OK — {checked} module groups meet floors")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
