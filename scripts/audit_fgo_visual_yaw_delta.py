#!/usr/bin/env python3
"""Audit N8A1 visual plot generation on toy data.

中文说明：toy 审计验证 N8A1 所需图像均生成且非空。
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from legsa_gins.fgo.fgo_factor_ablation_review import run_factor_ablation_review
from legsa_gins.fgo.fgo_factor_policy_review import review_factor_policy
from legsa_gins.fgo.fgo_n8a1_visual_plots import REQUIRED_N8A1_FIGURES, generate_n8a1_figures
from legsa_gins.fgo.fgo_state_epoch_mapping_audit import audit_state_epoch_mapping
from legsa_gins.fgo.fgo_yaw_convention_audit import audit_yaw_convention
from legsa_gins.fgo.fgo_yaw_delta_diagnostics import diagnose_yaw_delta


def main() -> int:
    ekf_rows = [{"time": float(i), "lat_deg": 30, "lon_deg": 120, "height_m": 10, "roll_deg": 0, "pitch_deg": 0, "yaw_deg": i % 360, "vn_mps": 1, "ve_mps": 0, "vd_mps": 0} for i in range(12)]
    fgo_rows = [dict(row, yaw_deg=float(row["yaw_deg"]) + (5.0 if i % 2 else 0.0)) for i, row in enumerate(ekf_rows)]
    yaw = audit_yaw_convention(ekf_rows=ekf_rows, fgo_rows=fgo_rows)
    state = audit_state_epoch_mapping(ekf_rows=ekf_rows, fgo_rows=fgo_rows, dataset_report={"state_count": len(ekf_rows)})
    factor = review_factor_policy(ekf_rows=ekf_rows, fgo_rows=fgo_rows, yaw_convention_report=yaw)
    diag = diagnose_yaw_delta(ekf_rows=ekf_rows, fgo_rows=fgo_rows, yaw_convention_report=yaw, factor_policy_report=factor)
    ablation = run_factor_ablation_review(ekf_rows=ekf_rows, fgo_rows=fgo_rows)
    with tempfile.TemporaryDirectory() as tmp:
        manifest = generate_n8a1_figures(
            figure_output_dir=tmp,
            ekf_rows=ekf_rows,
            fgo_rows=fgo_rows,
            yaw_convention=yaw,
            yaw_diagnostics=diag,
            state_epoch_mapping=state,
            factor_policy=factor,
            ablation=ablation,
            decision_preview={"status": "toy", "recommended_next_stage": "toy"},
        )
        if manifest.get("figure_count_total") != len(REQUIRED_N8A1_FIGURES):
            raise SystemExit("unexpected figure count")
        if not manifest.get("required_figures_generated") or not manifest.get("required_figures_nonempty"):
            raise SystemExit("required figures missing or empty")
    print("audit_fgo_visual_yaw_delta passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
