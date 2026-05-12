#!/usr/bin/env python3
"""Audit N7B2A Go2 metric namespace guard.

中文说明：本审计只检查指标命名空间和声明边界，不修改报告、不触发任何滤波器先验。
"""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _fail(message: str) -> None:
    raise SystemExit(f"audit_go2_metric_namespace_guard failed: {message}")


def main() -> int:
    required = [
        ROOT / "src/legsa_gins/go2_prior/go2_metric_namespace_guard.py",
        ROOT / "docs/experiments/n7b2a_metric_namespace_guard.md",
        ROOT / "CLAIM_BOUNDARY.md",
    ]
    text = "\n".join(path.read_text(encoding="utf-8", errors="ignore") for path in required)
    for token in [
        "parity_to_final_v23",
        "absolute_to_trace",
        "cross_source_consistency",
        "readiness_diagnostic",
        "not absolute accuracy",
        "Go2 velocity comparison",
        "paper_performance_claim",
    ]:
        if token not in text:
            _fail(f"required namespace token missing: {token}")
    print("audit_go2_metric_namespace_guard passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
