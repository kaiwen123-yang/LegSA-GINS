"""中文说明：测试 N8A2 runner 的 toy 集成流程。"""

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
            writer.writerow({"index": index, "time": float(index), "lat_deg": 30, "lon_deg": 120, "height_m": 10, "roll_deg": 0, "pitch_deg": 0, "yaw_deg": yaw, "vn_mps": 1, "ve_mps": 0, "vd_mps": 0})


def test_n8a2_runner_toy(tmp_path: Path) -> None:
    n8a = tmp_path / "n8a"
    _write_csv(n8a / "N8A_EKF_STATE_NODES.csv", [359.0, 1.0, 2.0, 3.0, 4.0])
    _write_csv(n8a / "N8A_FGO_DIAGNOSTIC_STATES.csv", [180.0, 120.0, 2.0, 3.0, 4.0])
    (n8a / "N8A_NO_FEEDBACK_SMOOTHER_REPORT.json").write_text(json.dumps({"solve_status": "solved", "finite_output": True}) + "\n", encoding="utf-8")
    out = tmp_path / "out"
    subprocess.run(
        [
            sys.executable,
            "scripts/experiments/run_n8a2_fgo_yaw_convention_fix.py",
            "--n8a-root",
            str(n8a),
            "--output-dir",
            str(out),
            "--figure-output-dir",
            str(tmp_path / "figs"),
            "--allow-run",
            "--run-rerun",
            "true",
        ],
        check=True,
    )
    decision = json.loads((out / "N8A2_FGO_YAW_CONVENTION_FIX_DECISION_REPORT.json").read_text(encoding="utf-8"))
    assert decision["status"] != "yaw_wrap_fix_failed"
    assert decision["output_only_yaw_correction"] is False
    assert (out / "N8A2_FGO_RERUN_VARIANT_SUMMARIES.json").exists()
