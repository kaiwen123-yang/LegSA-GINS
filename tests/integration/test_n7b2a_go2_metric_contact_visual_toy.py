"""中文说明：N7B2A toy runner 生成 runtime-only metric/contact audit reports。"""

import csv
import json
import subprocess
import sys
from pathlib import Path


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data) + "\n", encoding="utf-8")


def _write_contact_v2(path: Path) -> None:
    fields = [
        "time",
        "contact_label_v2",
        "contact_count_v2",
        *[f"foot_{foot}_contact_v2" for foot in range(4)],
        *[f"foot_{foot}_force" for foot in range(4)],
        *[f"foot_{foot}_speed_norm" for foot in range(4)],
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for index in range(18):
            row = {"time": index * 0.1, "contact_label_v2": "walking_contact", "contact_count_v2": 4}
            for foot in range(4):
                row[f"foot_{foot}_contact_v2"] = 1
                row[f"foot_{foot}_force"] = 32.0
                row[f"foot_{foot}_speed_norm"] = 1.2
            writer.writerow(row)


def test_n7b2a_go2_metric_contact_visual_toy(tmp_path):
    root = Path(__file__).resolve().parents[2]
    n7a = tmp_path / "n7a"
    n7b = tmp_path / "n7b"
    n7b2 = tmp_path / "n7b2"
    _write_json(n7a / "GO2_WEAK_PRIOR_BUILD_REPORT.json", {"std_policy": {"std_roll_deg": 5.0, "std_pitch_deg": 5.0}})
    _write_json(n7a / "GO2_QUATERNION_RPY_CHECK_REPORT.json", {"rpy_consistency_status": "passed", "activation_allowed_for_attitude_prior": True})
    _write_json(n7a / "N7A_GO2_WEAK_PRIOR_COMPARISON_REPORT.json", {"go2_attitude_weak_prior_minus_no_go2": {"delta": {"roll_rmse_deg": 0.043, "pitch_rmse_deg": 0.031}}})
    _write_json(n7b / "GO2_VELOCITY_QUALITY_REPORT.json", {"velocity_diff_rmse_to_receiver": 1.1, "not_truth": True})
    _write_json(n7b / "GO2_CONTACT_STATE_REPORT.json", {"uncertain_ratio": 0.9})
    _write_contact_v2(n7b2 / "GO2_CONTACT_STATE_V2_TIMESERIES.csv")
    _write_json(n7b2 / "GO2_CONTACT_DISTRIBUTION_REPORT.json", {"field_quality_status": "usable"})
    _write_json(n7b2 / "GO2_CONTACT_VELOCITY_SEGMENT_REVIEW.json", {"readiness_status": "acceptable"})
    proc = subprocess.run(
        [
            sys.executable,
            str(root / "scripts/experiments/run_n7b2a_go2_metric_contact_visual_audit.py"),
            "--n7a-root",
            str(n7a),
            "--n7b-root",
            str(n7b),
            "--n7b2-root",
            str(n7b2),
            "--output-dir",
            str(tmp_path / "out"),
            "--figure-output-dir",
            str(tmp_path / "fig"),
            "--allow-run",
        ],
        cwd=root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    decision = json.loads((tmp_path / "out/N7B2A_GO2_METRIC_CONTACT_DECISION_REPORT.json").read_text(encoding="utf-8"))
    assert decision["status"] == "contact_v2_not_ready"
    assert decision["go2_velocity_prior_enabled"] is False
    manifest = json.loads((tmp_path / "out/N7B2A_FIGURE_MANIFEST.json").read_text(encoding="utf-8"))
    assert manifest["required_figures_generated"] is True
    assert manifest["required_figures_nonempty"] is True
