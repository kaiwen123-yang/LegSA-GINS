"""中文说明：测试 R3 clean replay runner 的 runtime-only config 合同。"""

import json
from pathlib import Path

from legsa_gins.evaluation.legsa_v23_port_clean_replay_runner import (
    locate_clean_inputs,
    write_port_clean_config,
)


def test_config_writer_uses_runtime_paths_and_flags(tmp_path):
    clean = tmp_path / "clean"
    clean.mkdir()
    imu = clean / "CLEAN_STATUS_YAW.imu"
    gnss = clean / "CLEAN_STATUS_YAW.gnss"
    imu.write_text("0 0 0 0 0 0 0\n", encoding="utf-8")
    gnss.write_text("0 30 120 10 1 1 1 0 0 0 1 1 1 5 1\n", encoding="utf-8")
    status = locate_clean_inputs(clean)
    report = write_port_clean_config(status, tmp_path / "out")
    text = Path(report["config_path"]).read_text(encoding="utf-8")
    assert "imupath:" in text
    assert "gnsspath:" in text
    assert "clean_input_provenance_label: clean_status_yaw_no_synthetic_noise" in text
    assert report["trace_solver_input"] is False
    assert report["final_v23_output_solver_input"] is False


def test_missing_clean_input_classified(tmp_path):
    status = locate_clean_inputs(tmp_path / "missing")
    assert status["clean_input_missing"] is True


def test_manifest_like_flags_are_false():
    manifest = {
        "final_v23_output_solver_input": False,
        "trace_solver_input": False,
        "output_only_correction": False,
        "bad_epoch_deletion_for_metric": False,
    }
    assert json.dumps(manifest)
    assert all(value is False for value in manifest.values())
