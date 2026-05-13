"""中文说明：测试 N8A1 runner 的 toy 集成流程。"""

import csv
import json
import subprocess
import sys
from pathlib import Path


def _write_csv(path: Path, yaws: list[float]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = ["index", "time", "lat_deg", "lon_deg", "height_m", "roll_deg", "pitch_deg", "yaw_deg", "vn_mps", "ve_mps", "vd_mps"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for index, yaw in enumerate(yaws):
            writer.writerow({"index": index, "time": index, "lat_deg": 30, "lon_deg": 120, "height_m": 10, "roll_deg": 0, "pitch_deg": 0, "yaw_deg": yaw, "vn_mps": 1, "ve_mps": 0, "vd_mps": 0})


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def test_n8a1_runner_toy(tmp_path: Path) -> None:
    n8a = tmp_path / "n8a"
    _write_csv(n8a / "N8A_EKF_STATE_NODES.csv", [359, 1, 2, 3, 4, 5])
    _write_csv(n8a / "N8A_FGO_DIAGNOSTIC_STATES.csv", [180, 120, 2, 3, 4, 5])
    _write_json(n8a / "N8A_DATASET_REPORT.json", {"state_count": 6, "epoch_deletion": False})
    _write_json(n8a / "N8A_EVALUATION_REPORT.json", {"yaw_delta_rmse_deg": 85.0})
    _write_json(n8a / "N8A_NO_FEEDBACK_SMOOTHER_REPORT.json", {"solve_status": "solved", "smoothness_weight": 0.15})
    out = tmp_path / "out"
    subprocess.run(
        [
            sys.executable,
            "scripts/experiments/run_n8a1_fgo_yaw_delta_policy_review.py",
            "--n8a-root",
            str(n8a),
            "--output-dir",
            str(out),
            "--figure-output-dir",
            str(tmp_path / "figs"),
            "--allow-run",
            "--run-ablation",
            "true",
        ],
        check=True,
    )
    decision = json.loads((out / "N8A1_FGO_YAW_DELTA_POLICY_DECISION_REPORT.json").read_text(encoding="utf-8"))
    assert decision["status"] == "fgo_yaw_convention_blocker"
    assert (out / "FGO_YAW_DELTA_DIAGNOSTICS_REPORT.json").exists()
