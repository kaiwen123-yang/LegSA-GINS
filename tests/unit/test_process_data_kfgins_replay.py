"""中文说明：N4H2 replay helper 单元测试只验证报告/配置工具，不运行外部 KF-GINS。"""

import csv
import importlib.util
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/experiments/run_process_data_kfgins_replay.py"
spec = importlib.util.spec_from_file_location("run_process_data_kfgins_replay", SCRIPT)
run_process_data_kfgins_replay = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(run_process_data_kfgins_replay)


def test_load_process_data_trace_reference_maps_absolute_time(tmp_path):
    trace = tmp_path / "trace.csv"
    with trace.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "time",
                "lat",
                "lon",
                "height",
                "processed_lat",
                "processed_lon",
                "processed_height",
                "yaw",
                "pitch",
                "roll",
            ],
        )
        writer.writeheader()
        writer.writerow(
            {
                "time": "1772784055.5",
                "lat": "39.0",
                "lon": "116.0",
                "height": "40.0",
                "processed_lat": "[[39.0]]",
                "processed_lon": "[[116.0]]",
                "processed_height": "[[40.0]]",
                "yaw": "90.0",
                "pitch": "1.0",
                "roll": "0.5",
            }
        )

    rows = run_process_data_kfgins_replay.load_process_data_trace_reference(
        trace, base_time=1772784000.0
    )

    assert rows == [
        {
            "timestamp": 55.5,
            "lat_deg": 39.0,
            "lon_deg": 116.0,
            "height_m": 40.0,
            "roll_deg": 0.5,
            "pitch_deg": 1.0,
            "yaw_deg": 90.0,
        }
    ]


def test_write_replay_config_overrides_only_runtime_io_fields(tmp_path):
    template = tmp_path / "template.yaml"
    template.write_text(
        yaml.safe_dump(
            {
                "imupath": "old.imu",
                "gnsspath": "old.gnss",
                "outputpath": "old_output",
                "imudatalen": 7,
                "imudatarate": 200,
                "starttime": 1.0,
                "endtime": 2.0,
                "initpos": [1.0, 2.0, 3.0],
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    output_config = tmp_path / "out/replay.yaml"

    run_process_data_kfgins_replay.write_replay_config(
        template_config=template,
        gnss=tmp_path / "input.gnss",
        imu=tmp_path / "input.imu",
        output_dir=tmp_path / "kfgins_output",
        config_path=output_config,
        starttime=66.0,
        endtime=340.0,
        imudatarate=500,
    )

    written = yaml.safe_load(output_config.read_text(encoding="utf-8"))
    assert written["gnsspath"].endswith("input.gnss")
    assert written["imupath"].endswith("input.imu")
    assert written["outputpath"].endswith("kfgins_output")
    assert written["starttime"] == 66.0
    assert written["endtime"] == 340.0
    assert written["imudatarate"] == 500
    assert written["initpos"] == [1.0, 2.0, 3.0]
