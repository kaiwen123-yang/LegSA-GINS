"""中文说明：N7B2 toy runner 生成 runtime-only reports/figures。"""

import csv
import json
import subprocess
import sys
from pathlib import Path


def _write_go2(path: Path) -> None:
    fields = [
        "time",
        "aligned_time",
        "mode",
        "gait_type",
        "body_height",
        "go2_velocity_0",
        "go2_velocity_1",
        "go2_velocity_2",
        "yaw_speed_radps",
        *[f"foot_force_{i}" for i in range(4)],
        *[f"foot_speed_body_{i}" for i in range(12)],
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for index in range(24):
            moving = index >= 8
            writer.writerow(
                {
                    "time": index * 0.1,
                    "aligned_time": index * 0.1,
                    "mode": "walk" if moving else "stand",
                    "gait_type": 1 if moving else 0,
                    "body_height": 0.32,
                    "go2_velocity_0": 0.45 if moving else 0.03,
                    "go2_velocity_1": 0.02,
                    "go2_velocity_2": 0.0,
                    "yaw_speed_radps": 0.1 if moving else 0.0,
                    **{f"foot_force_{foot}": 34.0 if (not moving or foot % 2 == index % 2) else 5.0 for foot in range(4)},
                    **{f"foot_speed_body_{axis}": 0.04 if not moving else 0.20 for axis in range(12)},
                }
            )


def _write_clean(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(f"{i * 0.1} 0 0 0 0 0 0 {0.45 if i >= 8 else 0.03} 0.02 0 0.1 0.1 0.1 1 1" for i in range(24)) + "\n",
        encoding="utf-8",
    )


def _write_raw(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["time", "vn", "ve", "vd", "std_vn", "std_ve", "std_vd", "sat_count", "provider_status", "quality_flag"])
        writer.writeheader()
        for index in range(24):
            writer.writerow({"time": index * 0.1, "vn": 0.45 if index >= 8 else 0.03, "ve": 0.02, "vd": 0.0, "std_vn": 0.2, "std_ve": 0.2, "std_vd": 0.2, "sat_count": 10, "provider_status": "ok", "quality_flag": "usable"})


def _write_n7b(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    with (path / "GO2_CONTACT_STATE_TIMESERIES.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["row_index", "time", "contact_label", "contact_count"])
        writer.writeheader()
        for index in range(24):
            writer.writerow({"row_index": index, "time": index * 0.1, "contact_label": "swing_or_uncertain", "contact_count": 0})
    (path / "GO2_CONTACT_STATE_REPORT.json").write_text('{"recommended_contact_quality_status": "review"}\n', encoding="utf-8")
    (path / "GO2_VELOCITY_QUALITY_REPORT.json").write_text('{"consistency_status": "acceptable_for_future_review"}\n', encoding="utf-8")
    (path / "N7B_GO2_VELOCITY_CONTACT_DECISION_REPORT.json").write_text('{"status": "contact_not_ready"}\n', encoding="utf-8")


def test_n7b2_go2_contact_threshold_review_toy(tmp_path):
    root = Path(__file__).resolve().parents[2]
    _write_go2(tmp_path / "n7a/GO2_BODY_STATE_STANDARDIZED.csv")
    _write_n7b(tmp_path / "n7b")
    _write_clean(tmp_path / "clean/input.gnss")
    _write_raw(tmp_path / "n5b/RAW_DOPPLER_VELOCITY_FACTORS.csv")
    (tmp_path / "n6b").mkdir()
    proc = subprocess.run(
        [
            sys.executable,
            str(root / "scripts/experiments/run_n7b2_go2_contact_threshold_review.py"),
            "--n7a-root",
            str(tmp_path / "n7a"),
            "--n7b-root",
            str(tmp_path / "n7b"),
            "--n5b-root",
            str(tmp_path / "n5b"),
            "--n6b-root",
            str(tmp_path / "n6b"),
            "--clean-root",
            str(tmp_path / "clean"),
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
    decision = json.loads((tmp_path / "out/N7B2_GO2_CONTACT_THRESHOLD_DECISION_REPORT.json").read_text(encoding="utf-8"))
    assert decision["go2_velocity_prior_enabled"] is False
    assert decision["go2_yaw_prior_enabled"] is False
    manifest = json.loads((tmp_path / "out/N7B2_FIGURE_MANIFEST.json").read_text(encoding="utf-8"))
    assert manifest["required_figures_generated"] is True
    assert manifest["required_figures_nonempty"] is True
