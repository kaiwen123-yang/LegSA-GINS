"""中文说明：测试 N4H4D clean replay runner 的输入定位和 config 生成。"""

from pathlib import Path

from legsa_gins.evaluation.legsa_v23_clean_replay_runner import build_clean_replay_config, locate_clean_inputs


def test_missing_clean_input_classified(tmp_path: Path):
    report = locate_clean_inputs(tmp_path / "missing")
    assert report["clean_input_status"] == "clean_input_missing"
    assert "clean_gnss" in report["missing"]
    assert "clean_imu" in report["missing"]


def test_config_writer_runtime_only_paths(tmp_path: Path):
    clean = tmp_path / "clean"
    clean.mkdir()
    (clean / "CLEAN_STATUS_YAW.imu").write_text("0.00 0 0 0 0 0 -0.1\n0.01 0 0 0 0 0 -0.1\n", encoding="utf-8")
    (clean / "CLEAN_STATUS_YAW.gnss").write_text(
        "0.01 31 121 10 1 1 1 0 0 0 0.1 0.1 0.1 10 1.5\n",
        encoding="utf-8",
    )
    (clean / "kf-gins-n4h2g-clean-replay.yaml").write_text(
        "starttime: 0\nendtime: 0.01\ninitpos: [31,121,10]\ninitvel: [0,0,0]\ninitatt: [0,0,10]\n",
        encoding="utf-8",
    )
    report = build_clean_replay_config(clean, tmp_path / "out")
    assert report["config_status"] == "config_written"
    config_text = Path(report["config_path"]).read_text(encoding="utf-8")
    assert "trace" not in config_text.lower()
    assert "final_v23_output" not in config_text
    assert "clean_status_yaw_no_synthetic_noise" in config_text
