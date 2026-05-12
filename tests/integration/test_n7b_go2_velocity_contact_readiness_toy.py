"""中文说明：N7B toy runner 生成 runtime-only reports/figures。"""

import csv
import json
import subprocess
import sys
from pathlib import Path


def _write_go2(path: Path) -> None:
    fields = [
        "time",
        "aligned_time",
        "yaw_rad",
        "mode",
        "gait_type",
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
        for i in range(16):
            writer.writerow(
                {
                    "time": i,
                    "aligned_time": i,
                    "yaw_rad": i * 0.1,
                    "mode": "walk",
                    "gait_type": 1,
                    "go2_velocity_0": 0.5,
                    "go2_velocity_1": 0.0,
                    "go2_velocity_2": 0.0,
                    "yaw_speed_radps": 0.1,
                    **{f"foot_force_{foot}": 30.0 for foot in range(4)},
                    **{f"foot_speed_body_{axis}": 0.05 for axis in range(12)},
                }
            )


def _write_clean(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(f"{i} 0 0 0 0 0 0 0.5 0 0 0.1 0.1 0.1 1 1" for i in range(16)) + "\n", encoding="utf-8")


def _write_raw(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["time", "vn", "ve", "vd", "std_vn", "std_ve", "std_vd", "sat_count", "provider_status", "quality_flag"])
        writer.writeheader()
        for i in range(16):
            writer.writerow({"time": i, "vn": 0.5, "ve": 0.0, "vd": 0.0, "std_vn": 0.2, "std_ve": 0.2, "std_vd": 0.2, "sat_count": 10, "provider_status": "ok", "quality_flag": "usable"})


def test_n7b_go2_velocity_contact_readiness_toy(tmp_path):
    root = Path(__file__).resolve().parents[2]
    _write_go2(tmp_path / "n7a/GO2_BODY_STATE_STANDARDIZED.csv")
    (tmp_path / "n7a/GO2_WEAK_PRIOR_BUILD_REPORT.json").write_text('{"activation_allowed": true}\n', encoding="utf-8")
    _write_clean(tmp_path / "clean/input.gnss")
    _write_raw(tmp_path / "n5b/RAW_DOPPLER_VELOCITY_FACTORS.csv")
    (tmp_path / "n5c").mkdir()
    (tmp_path / "n6b").mkdir()
    proc = subprocess.run(
        [
            sys.executable,
            str(root / "scripts/experiments/run_n7b_go2_velocity_contact_readiness.py"),
            "--n7a-root",
            str(tmp_path / "n7a"),
            "--n5b-root",
            str(tmp_path / "n5b"),
            "--n5c-root",
            str(tmp_path / "n5c"),
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
    decision = json.loads((tmp_path / "out/N7B_GO2_VELOCITY_CONTACT_DECISION_REPORT.json").read_text(encoding="utf-8"))
    assert decision["go2_velocity_prior_enabled"] is False
    assert decision["go2_yaw_prior_enabled"] is False
    manifest = json.loads((tmp_path / "out/N7B_FIGURE_MANIFEST.json").read_text(encoding="utf-8"))
    assert manifest["required_figures_generated"] is True
    assert manifest["required_figures_nonempty"] is True
