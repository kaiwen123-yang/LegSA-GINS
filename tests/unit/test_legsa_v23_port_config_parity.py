"""中文说明：测试 R3A runtime config parity 分类。"""

from pathlib import Path

from legsa_gins.evaluation.legsa_v23_port_config_parity import audit_port_clean_config


def _write_config(path: Path, *, imu: str = "CLEAN_STATUS_YAW.imu", gnss: str = "CLEAN_STATUS_YAW.gnss", provenance: bool = True):
    path.write_text(
        "\n".join(
            [
                f"imupath: {path.parent / imu}",
                f"gnsspath: {path.parent / gnss}",
                "starttime: 10",
                "endtime: 20",
                "antlever: [0, 0, -0.25]",
                "arw: [1,1,1]",
                "vrw: [1,1,1]",
                "gbstd: [1,1,1]",
                "abstd: [1,1,1]",
                "corrtime: 1",
                "clean_input_provenance_label: clean_status_yaw_no_synthetic_noise" if provenance else "",
            ]
        ),
        encoding="utf-8",
    )


def test_detects_wrong_input(tmp_path: Path):
    config = tmp_path / "config.conf"
    _write_config(config, imu="wrong.imu")
    report = audit_port_clean_config(config, {"overlap_start": 10, "overlap_end": 20})
    assert report["config_uses_wrong_input"] is True
    assert report["config_ok"] is False


def test_detects_short_config_window(tmp_path: Path):
    config = tmp_path / "config.conf"
    _write_config(config)
    report = audit_port_clean_config(config, {"overlap_start": 10, "overlap_end": 30})
    assert report["config_start_end_too_short"] is True


def test_detects_missing_clean_provenance(tmp_path: Path):
    config = tmp_path / "config.conf"
    _write_config(config, provenance=False)
    report = audit_port_clean_config(config, {"overlap_start": 10, "overlap_end": 20})
    assert report["clean_provenance_missing"] is True
