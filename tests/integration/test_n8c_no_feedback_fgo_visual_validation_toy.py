"""中文说明：toy 集成测试 N8C no-feedback FGO visual validation。"""

from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path


def _write_ekf_csv(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = ["index", "time", "lat_deg", "lon_deg", "height_m", "roll_deg", "pitch_deg", "yaw_deg", "vn_mps", "ve_mps", "vd_mps"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for index, yaw in enumerate([359.0, 1.0, 2.0, 3.0, 4.0, 5.0]):
            writer.writerow({"index": index, "time": index * 80.0, "lat_deg": 30.0 + index * 1e-6, "lon_deg": 120.0 + index * 1e-6, "height_m": 10.0, "roll_deg": 0.1 * index, "pitch_deg": 0.0, "yaw_deg": yaw, "vn_mps": 1.0, "ve_mps": 0.0, "vd_mps": 0.0})


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def test_n8c_no_feedback_fgo_visual_validation_toy(tmp_path: Path) -> None:
    n8a = tmp_path / "N8A_no_feedback_fgo_foundation"
    n8a2 = tmp_path / "N8A2_fgo_yaw_convention_fix"
    n8b = tmp_path / "N8B_fgo_factor_graph_policy_review"
    _write_ekf_csv(n8a / "N8A_EKF_STATE_NODES.csv")
    _write_json(n8a2 / "N8A2_FGO_YAW_CONVENTION_FIX_DECISION_REPORT.json", {"status": "yaw_convention_fixed_foundation_ready"})
    _write_json(n8a2 / "N8A2_FGO_YAW_FIX_COMPARISON_REPORT.json", {"n8a2_default_yaw_delta_wrapped_rmse_deg": 1.0})
    subprocess.run(
        [
            sys.executable,
            "scripts/experiments/run_n8b_fgo_factor_graph_policy_review.py",
            "--n8a2-root",
            str(n8a2),
            "--n8a-root",
            str(n8a),
            "--n7c6-root",
            str(tmp_path / "n7c6"),
            "--n7c5-root",
            str(tmp_path / "n7c5"),
            "--output-dir",
            str(n8b),
            "--figure-output-dir",
            str(tmp_path / "n8b_figs"),
            "--allow-run",
        ],
        check=True,
    )
    out = tmp_path / "n8c"
    subprocess.run(
        [
            sys.executable,
            "scripts/experiments/run_n8c_no_feedback_fgo_visual_validation.py",
            "--n8b-root",
            str(n8b),
            "--n8a2-root",
            str(n8a2),
            "--output-dir",
            str(out),
            "--figure-output-dir",
            str(tmp_path / "n8c_figs"),
            "--allow-run",
            "--rerun-missing-timeseries",
            "true",
        ],
        check=True,
    )
    decision = json.loads((out / "N8C_NO_FEEDBACK_FGO_VISUAL_DECISION_REPORT.json").read_text(encoding="utf-8"))
    figures = json.loads((out / "N8C_FIGURE_MANIFEST.json").read_text(encoding="utf-8"))
    assert decision["no_feedback"]
    assert figures["figure_count_total"] == 22
    assert figures["required_figures_nonempty"]
