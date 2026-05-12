#!/usr/bin/env python3
"""Audit N7B2 threshold review has no trace/final_v23 tuning.

中文说明：contact thresholds 只能来自 Go2 field distribution，不能从 trace、
final_v23 output 或导航 metric 调参。
"""

from __future__ import annotations

import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _fail(message: str) -> None:
    raise SystemExit(f"audit_go2_contact_threshold_no_trace_tuning failed: {message}")


def _run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)


def main() -> int:
    required = [
        ROOT / "src/legsa_gins/go2_prior/go2_contact_distribution.py",
        ROOT / "src/legsa_gins/go2_prior/go2_contact_threshold_review.py",
        ROOT / "src/legsa_gins/go2_prior/go2_contact_state_v2.py",
        ROOT / "docs/experiments/n7b2_go2_contact_threshold_review.md",
        ROOT / "CLAIM_BOUNDARY.md",
    ]
    text = "\n".join(path.read_text(encoding="utf-8", errors="ignore") for path in required)
    for token in [
        "go2_field_distribution_only",
        "thresholds_are_diagnostic",
        "navigation_metric_tuning",
        "trace_solver_input",
        "final_v23_output_solver_input",
    ]:
        if token not in text:
            _fail(f"required threshold boundary token missing: {token}")
    forbidden = [
        "trace-tuned threshold",
        "trace tuned threshold",
        "final_v23 tuned threshold",
        "navigation_metric_tuning\": True",
    ]
    for token in forbidden:
        if token in text:
            _fail(f"forbidden threshold tuning token present: {token}")
    for token in [
        "/mnt/c/Users" + "/ykw/Desktop",
        "/mnt/c/Users" + "/86187/Desktop",
        "C:\\\\Users",
        "/home/kaiwen" + "/legsa_n4h4",
        "/home/kaiwen" + "/legsa_external_artifacts",
    ]:
        proc = _run(["git", "grep", "-n", token, "--", "."])
        if proc.returncode == 0:
            _fail(f"local path leak under tracked files: {token}")
    print("audit_go2_contact_threshold_no_trace_tuning passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
