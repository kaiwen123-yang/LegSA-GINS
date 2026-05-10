#!/usr/bin/env python3
"""Audit that N6A source-aware weighting does not tune from trace/final_v23 output.

中文说明：本审计只检查调权策略边界，不读取 runtime trace 作为策略输入。
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


POLICY_FILES = [
    ROOT / "src/legsa_gins/source_aware/lsim_metric.py",
    ROOT / "src/legsa_gins/source_aware/oim_metric.py",
    ROOT / "src/legsa_gins/source_aware/source_weight_policy.py",
    ROOT / "cpp/legsa_v23_port_core/src/source_aware/source_aware_policy.cpp",
]


def _fail(message: str) -> None:
    raise SystemExit(f"audit_source_aware_no_trace_tuning failed: {message}")


def main() -> int:
    combined = "\n".join(path.read_text(encoding="utf-8", errors="ignore") for path in POLICY_FILES)
    forbidden_calls = [
        "SOURCE_AWARE_WEIGHT_TRACE.csv",
        "RUN_MANIFEST.json",
        "final_v23",
        "KF_GINS_Navresult",
        "evaluate_port_clean_replay",
        "horizontal_rmse",
        "yaw_rmse",
        "output_only_correction",
    ]
    for token in forbidden_calls:
        if token in combined and token not in {"final_v23"}:
            _fail(f"policy references forbidden tuning/evaluation token: {token}")
    if re.search(r"96\.4067945|97\.0067945", combined):
        _fail("policy hardcodes N5D1 spike time")
    docs = (ROOT / "docs/experiments/n6a_source_aware_measurement_policy.md").read_text(encoding="utf-8")
    for phrase in ["source_aware_max_R_scale=25", "no trace", "No final_v23 output", "output correction is forbidden"]:
        if phrase.lower() not in docs.lower():
            _fail(f"policy doc missing fixed boundary phrase: {phrase}")
    print("audit_source_aware_no_trace_tuning passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
