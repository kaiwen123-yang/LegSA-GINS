import csv
import json
import subprocess
import sys
from pathlib import Path


def test_n8a_no_feedback_fgo_toy(tmp_path: Path) -> None:
    """中文说明：toy runtime 验证 N8A runner 输出 ready 决策。"""
    n7c6 = tmp_path / "n7c6"
    path = n7c6 / "variants" / "joint_rp1deg_hv1p0" / "EVAL_NAV.csv"
    path.parent.mkdir(parents=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["time", "lat_deg", "lon_deg", "height_m", "roll_deg", "pitch_deg", "yaw_deg", "vn", "ve", "vd"])
        writer.writeheader()
        for index in range(5):
            writer.writerow({"time": index, "lat_deg": 30, "lon_deg": 120, "height_m": 10, "roll_deg": 0, "pitch_deg": 0, "yaw_deg": index, "vn": 1, "ve": 0, "vd": 0})
    out = tmp_path / "out"
    subprocess.run(
        [
            sys.executable,
            "scripts/experiments/run_n8a_no_feedback_fgo_foundation.py",
            "--clean-root",
            str(tmp_path / "clean"),
            "--n5b-root",
            str(tmp_path / "n5b"),
            "--n6b-root",
            str(tmp_path / "n6b"),
            "--n7a-root",
            str(tmp_path / "n7a"),
            "--n7b4-root",
            str(tmp_path / "n7b4"),
            "--n7c-root",
            str(tmp_path / "n7c"),
            "--n7c5-root",
            str(tmp_path / "n7c5"),
            "--n7c6-root",
            str(n7c6),
            "--dual-root",
            str(tmp_path / "dual"),
            "--output-dir",
            str(out),
            "--figure-output-dir",
            str(tmp_path / "figs"),
            "--allow-run",
        ],
        check=True,
    )
    decision = json.loads((out / "N8A_NO_FEEDBACK_FGO_DECISION_REPORT.json").read_text(encoding="utf-8"))
    assert decision["status"] == "n8a_no_feedback_fgo_foundation_ready"
