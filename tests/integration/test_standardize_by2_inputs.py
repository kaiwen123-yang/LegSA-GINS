"""中文说明：standardize_by2_inputs 集成测试只使用 tmp toy 数据，不读取真实 BY2，不输出性能指标。
"""

import json
from pathlib import Path
import subprocess
import sys


REPO_ROOT = Path(__file__).resolve().parents[2]
TRACE_NAME = "trace_vrtk2_a87c6e_2026-03-06-08-00-54_minimal.csv"


def _write_toy_dataset(root, body_path):
    root.mkdir()
    status = (
        "Time,time_gps_wno,time_gps_tow,msg_valid,pos_lat,pos_lon,pos_height,pos_acc_h,pos_acc_v,pos_valid,fix_ok,fix_type,rel_pos_n,rel_pos_e,rel_pos_d,rel_acc_n,rel_acc_e,rel_acc_d,rel_valid,ant_valid\n"
        "1700000000,2400,100.0,1,30.0,120.0,10.0,0.5,0.8,1,1,3,1.0,1.0,0.0,0.1,0.1,0.2,1,1\n"
    )
    raw = (
        "Time,name,info,protocol,seq\n"
        "1700000000,UBX-NAV-PVT,nav pvt sample,UBX,1\n"
        "1700000001,UBX-NAV-HPPOSECEF,hp posecef sample,UBX,2\n"
    )
    trace = "time,lat,lon,height,yaw,pitch,roll\n1700000000,30.0,120.0,10.0,90.0,1.0,2.0\n"
    for name in ["gnss1-status.csv", "gnss2-status.csv"]:
        (root / name).write_text(status, encoding="utf-8")
    for name in ["gnss1-raw.csv", "gnss2-raw.csv"]:
        (root / name).write_text(raw, encoding="utf-8")
    (root / TRACE_NAME).write_text(trace, encoding="utf-8")
    (root / "imu-data.csv").write_text("Time,acc_x\n1700000000,0.0\n", encoding="utf-8")
    body_path.write_text(
        """
stamp:
  sec: 1700000000
  nanosec: 0
imu_state:
  quaternion: [1, 0, 0, 0]
  gyroscope: [0.1, 0.2, 0.3]
  accelerometer: [1, 2, 3]
  rpy: [0.01, 0.02, 0.03]
yaw_speed: 0.4
foot_force: [10, 20, 30, 40]
foot_position_body: [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]
foot_speed_body: [0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0, 1.1]
---
""".lstrip(),
        encoding="utf-8",
    )


def test_standardize_by2_inputs_outputs_and_manifest(tmp_path):
    fix_root = tmp_path / "fix"
    body_path = tmp_path / "by2.txt"
    output_dir = tmp_path / "out"
    _write_toy_dataset(fix_root, body_path)

    subprocess.run(
        [
            sys.executable,
            "scripts/datasets/standardize_by2_inputs.py",
            "--fix-root",
            str(fix_root),
            "--body-imu",
            str(body_path),
            "--output-dir",
            str(output_dir),
        ],
        cwd=REPO_ROOT,
        check=True,
    )

    expected = [
        "BY2_GNSS1_STATUS_STANDARD.csv",
        "BY2_GNSS2_STATUS_STANDARD.csv",
        "BY2_GNSS1_RAW_MESSAGE_SUMMARY.json",
        "BY2_GNSS2_RAW_MESSAGE_SUMMARY.json",
        "BY2_TRACE_REFERENCE_EVAL_ONLY.csv",
        "BY2_GO2_BODY_STATE_DIAGNOSTIC.csv",
        "BY2_INPUT_MANIFEST.json",
    ]
    for name in expected:
        assert (output_dir / name).exists()

    manifest = json.loads((output_dir / "BY2_INPUT_MANIFEST.json").read_text(encoding="utf-8"))
    assert manifest["source_roles"]["trace"] == "evaluation_reference_only"
    assert manifest["solver_input_policy"]["trace_solver_input"] is False
    assert manifest["solver_input_policy"]["receiver_imu_as_body_imu"] is False
    assert manifest["solver_input_policy"]["raw_doppler_extracted"] is False
    assert manifest["frame_policy"]["body_state_requires_frame_adapter"] is True
