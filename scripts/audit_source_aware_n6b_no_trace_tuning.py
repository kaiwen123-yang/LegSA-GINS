#!/usr/bin/env python3
"""Audit N6B source-aware policy does not tune from trace or outputs.

中文说明：只检查策略源文件，不读取 runtime trace 作为调权依据。
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


POLICY_FILES = [
    ROOT / "src/legsa_gins/source_aware/source_aware_n6b_policy.py",
    ROOT / "cpp/legsa_v23_port_core/src/source_aware/source_aware_policy.cpp",
]


def _fail(message: str) -> None:
    raise SystemExit(f"audit_source_aware_n6b_no_trace_tuning failed: {message}")


def main() -> int:
    combined = "\n".join(path.read_text(encoding="utf-8", errors="ignore") for path in POLICY_FILES)
    forbidden = [
        "SOURCE_AWARE_WEIGHT_TRACE.csv",
        "RUN_MANIFEST.json",
        "KF_GINS_Navresult",
        "evaluate_port_clean_replay",
        "horizontal_rmse",
        "yaw_rmse",
        "output_only_correction",
    ]
    for token in forbidden:
        if token in combined:
            _fail(f"policy references forbidden tuning/evaluation token: {token}")
    if re.search(r"96\.4067945|97\.0067945", combined):
        _fail("policy hardcodes N5D1 spike time")
    if "S=H*P*H^T+R" not in combined and "S = HPH^T + R" not in combined:
        _fail("policy missing innovation covariance statement")
    print("audit_source_aware_n6b_no_trace_tuning passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
