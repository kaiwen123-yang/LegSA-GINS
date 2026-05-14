"""Unit tests for N8F1 visual loader.

中文说明：检查 N8F visual loader 能从 runtime 报告生成绘图输入。
"""

import csv
import json
from pathlib import Path

from legsa_gins.fgo.fgo_n8f_visual_loader import load_n8f_visual_inputs


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


def test_loader_finds_reports_and_builds_proxy_series(tmp_path: Path) -> None:
    root = tmp_path
    _write_json(root / "FGO_CONTACT_AWARE_WEIGHTING_REPORT.json", {"rows": 2})
    _write_json(root / "FGO_FOOT_KINEMATIC_VELOCITY_FACTOR_REPORT.json", {"residual_rows": 2})
    _write_json(root / "FGO_YAWRATE_BETWEEN_FACTOR_REPORT.json", {"residual_rows": 2, "whitened_residual_p95": 0.5})
    _write_json(root / "FGO_RELATIVE_ODOMETRY_BETWEEN_FACTOR_REPORT.json", {"residual_rows": 2, "whitened_residual_p95": 0.6})
    _write_json(root / "FGO_LEGGED_CANDIDATE_FACTOR_CONTRACTS_REPORT.json", {"all_no_truth_claim": True})
    _write_json(root / "N8F_LEGGED_FACTOR_ACTIVATION_VARIANT_SUMMARIES.json", {"variants": [{"variant": "baseline"}]})
    _write_json(root / "N8F_LEGGED_FACTOR_ACTIVATION_COMPARISON_REPORT.json", {"candidate_solver_injection_passed": True})
    _write_json(root / "N8F_LEGGED_CANDIDATE_FACTOR_ACTIVATION_DECISION_REPORT.json", {"no_feedback": True})
    with (root / "FGO_CONTACT_AWARE_WEIGHTING_TIMESERIES.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["time", "contact_weight_scale"])
        writer.writeheader()
        writer.writerow({"time": 0.0, "contact_weight_scale": 1.0})
    with (root / "FGO_FOOT_KINEMATIC_VELOCITY_FACTOR_TABLE.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["time", "vn_mps", "ve_mps", "std_vn_mps", "std_ve_mps"])
        writer.writeheader()
        writer.writerow({"time": 0.0, "vn_mps": 1.0, "ve_mps": 0.0, "std_vn_mps": 1.0, "std_ve_mps": 1.0})
    manifest, data = load_n8f_visual_inputs(n8f_root=root)
    assert manifest["n8f_reports_found"] is True
    assert data["foot_residual_series"]
    assert data["yawrate_residual_series"]

