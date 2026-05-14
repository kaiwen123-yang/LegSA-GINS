"""中文说明：测试 N8C visual loader 的 no-feedback manifest。"""

import csv
import json
from pathlib import Path

from legsa_gins.fgo.fgo_n8c_visual_loader import load_n8c_visual_inputs
from legsa_gins.fgo.fgo_policy_grid import build_n8b_policy_grid


def _write_csv(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = ["index", "time", "lat_deg", "lon_deg", "height_m", "roll_deg", "pitch_deg", "yaw_deg", "vn_mps", "ve_mps", "vd_mps"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for index, yaw in enumerate([359.0, 1.0, 2.0, 3.0]):
            writer.writerow({"index": index, "time": index * 100.0, "lat_deg": 30.0, "lon_deg": 120.0, "height_m": 10.0, "roll_deg": 0.0, "pitch_deg": 0.0, "yaw_deg": yaw, "vn_mps": 1.0, "ve_mps": 0.0, "vd_mps": 0.0})


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_n8c_visual_loader_reruns_missing_timeseries(tmp_path: Path) -> None:
    n8a = tmp_path / "N8A_no_feedback_fgo_foundation"
    n8b = tmp_path / "N8B_fgo_factor_graph_policy_review"
    n8a2 = tmp_path / "N8A2_fgo_yaw_convention_fix"
    _write_csv(n8a / "N8A_EKF_STATE_NODES.csv")
    _write_json(n8b / "N8B_FGO_POLICY_GRID.json", build_n8b_policy_grid())
    _write_json(n8b / "N8B_FGO_POLICY_ABLATION_SUMMARIES.json", {"variants": [{"variant": "weak_yaw_smoothness"}, {"variant": "default_active_stack_n8a2"}]})
    _write_json(n8b / "FGO_FACTOR_WEIGHT_REVIEW_REPORT.json", {"per_factor_residual_p95": {"SmoothnessFactor": 1.0}})
    _write_json(n8b / "FGO_CANDIDATE_FACTOR_REVIEW_REPORT.json", {"candidate_factors_remain_diagnostic": True})
    manifest, data = load_n8c_visual_inputs(n8b_root=n8b, n8a2_root=n8a2)
    assert manifest["weak_yaw_variant_found"]
    assert manifest["ekf_baseline_found"]
    assert manifest["timeseries_rerun_performed_runtime_only"]
    assert data["rows_by_variant"]["weak_yaw_smoothness"]
