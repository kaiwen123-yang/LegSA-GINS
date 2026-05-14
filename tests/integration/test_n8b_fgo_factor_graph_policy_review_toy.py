"""中文说明：toy 集成测试 N8B factor graph policy runner。"""

from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path


def _write_csv(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = ["index", "time", "lat_deg", "lon_deg", "height_m", "roll_deg", "pitch_deg", "yaw_deg", "vn_mps", "ve_mps", "vd_mps"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for index, yaw in enumerate([359.0, 1.0, 2.0, 3.0, 4.0, 5.0]):
            writer.writerow({"index": index, "time": float(index), "lat_deg": 30.0, "lon_deg": 120.0, "height_m": 10.0, "roll_deg": 0.0, "pitch_deg": 0.0, "yaw_deg": yaw, "vn_mps": 1.0, "ve_mps": 0.0, "vd_mps": 0.0})


def test_n8b_fgo_factor_graph_policy_review_toy(tmp_path: Path) -> None:
    n8a = tmp_path / "n8a"
    n8a2 = tmp_path / "n8a2"
    n7c6 = tmp_path / "n7c6"
    n7c5 = tmp_path / "n7c5"
    out = tmp_path / "out"
    figs = tmp_path / "figs"
    n7c6.mkdir()
    n7c5.mkdir()
    _write_csv(n8a / "N8A_EKF_STATE_NODES.csv")
    n8a2.mkdir()
    (n8a2 / "N8A2_FGO_YAW_CONVENTION_FIX_DECISION_REPORT.json").write_text(json.dumps({"status": "yaw_convention_fixed_foundation_ready"}), encoding="utf-8")
    (n8a2 / "N8A2_FGO_YAW_FIX_COMPARISON_REPORT.json").write_text(json.dumps({"n8a2_default_yaw_delta_wrapped_rmse_deg": 1.0}), encoding="utf-8")
    subprocess.run(
        [
            sys.executable,
            "scripts/experiments/run_n8b_fgo_factor_graph_policy_review.py",
            "--n8a2-root",
            str(n8a2),
            "--n8a-root",
            str(n8a),
            "--n7c6-root",
            str(n7c6),
            "--n7c5-root",
            str(n7c5),
            "--output-dir",
            str(out),
            "--figure-output-dir",
            str(figs),
            "--allow-run",
        ],
        check=True,
    )
    ablations = json.loads((out / "N8B_FGO_POLICY_ABLATION_SUMMARIES.json").read_text(encoding="utf-8"))
    decision = json.loads((out / "N8B_FGO_FACTOR_GRAPH_POLICY_DECISION_REPORT.json").read_text(encoding="utf-8"))
    manifest = json.loads((out / "N8B_FIGURE_MANIFEST.json").read_text(encoding="utf-8"))
    assert ablations["variant_count"] == 13
    assert ablations["all_variants_real_solver_rerun"]
    assert decision["no_feedback"]
    assert manifest["required_figures_nonempty"]
