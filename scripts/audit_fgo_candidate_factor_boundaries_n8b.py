#!/usr/bin/env python3
"""Audit N8B candidate factors remain diagnostic-only.

中文说明：候选 factor 在 N8B 必须保持 diagnostic-only。
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from legsa_gins.fgo.fgo_candidate_factor_review import review_candidate_factors
from legsa_gins.fgo.fgo_policy_ablation_runner import run_n8b_policy_ablations
from legsa_gins.fgo.fgo_policy_grid import build_n8b_policy_grid


def _fail(message: str) -> None:
    raise SystemExit(f"audit_fgo_candidate_factor_boundaries_n8b failed: {message}")


def _toy_rows() -> list[dict]:
    return [
        {"index": index, "time": float(index), "lat_deg": 30.0, "lon_deg": 120.0, "height_m": 10.0, "roll_deg": 0.0, "pitch_deg": 0.0, "yaw_deg": yaw, "vn_mps": 1.0, "ve_mps": 0.0, "vd_mps": 0.0}
        for index, yaw in enumerate([359.0, 1.0, 2.0, 3.0, 4.0])
    ]


def main() -> int:
    ablations, _rows = run_n8b_policy_ablations(ekf_rows=_toy_rows(), policy_grid=build_n8b_policy_grid())
    review = review_candidate_factors(ablation_summary=ablations, n7c6_available=True, n7c5_available=True)
    if not review.get("candidate_factors_remain_diagnostic") or not review.get("no_formal_activation"):
        _fail("candidate activation boundary failed")
    for row in review.get("candidate_factor_reviews", []):
        if not row.get("diagnostic_only") or row.get("formal_activation"):
            _fail(f"candidate not diagnostic-only: {row.get('factor_type')}")
    print("audit_fgo_candidate_factor_boundaries_n8b passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
