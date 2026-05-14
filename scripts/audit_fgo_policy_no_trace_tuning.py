#!/usr/bin/env python3
"""Audit N8B policy grid does not use trace/final_v23 tuning.

中文说明：N8B policy 不能用 trace/final_v23 调权。
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from legsa_gins.fgo.fgo_policy_grid import build_n8b_policy_grid


def _fail(message: str) -> None:
    raise SystemExit(f"audit_fgo_policy_no_trace_tuning failed: {message}")


def main() -> int:
    grid = build_n8b_policy_grid()
    if grid.get("trace_solver_input") or grid.get("trace_weight_tuning"):
        _fail("trace is enabled")
    if grid.get("final_v23_output_solver_input") or grid.get("final_v23_weight_tuning"):
        _fail("final_v23 tuning/input is enabled")
    proc = subprocess.run(
        [
            "git",
            "grep",
            "-n",
            "trace.*tuning\\|final_v23.*tuning",
            "--",
            "src/legsa_gins/fgo/fgo_policy_grid.py",
            "src/legsa_gins/fgo/fgo_policy_ablation_runner.py",
            "scripts/experiments/run_n8b_fgo_factor_graph_policy_review.py",
        ],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    suspicious = [
        line
        for line in proc.stdout.splitlines()
        if "False" not in line and "not use" not in line and "not used" not in line and "no trace/final_v23 tuning" not in line
    ]
    if suspicious:
        _fail("suspicious trace/final_v23 tuning text: " + suspicious[0])
    print("audit_fgo_policy_no_trace_tuning passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
