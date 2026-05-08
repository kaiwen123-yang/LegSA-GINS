"""中文说明：runtime yaw update audit 只扫描 toy source。"""

from pathlib import Path

from legsa_gins.source_audit.yaw_update_runtime_audit import audit_yaw_update_runtime


def test_yaw_update_runtime_audit_finds_gnss_yaw(tmp_path: Path):
    src = tmp_path / "src"
    src.mkdir()
    (src / "gi_engine.cpp").write_text(
        "gnssdata.yaw yaw_std scheme_C H_gnssyaw R_gnssyaw wrap euler[2] stateFeedback heading\n",
        encoding="utf-8",
    )
    report = audit_yaw_update_runtime(tmp_path)
    assert report["yaw_measurement_loaded"] is True
    assert report["yaw_measurement_matrix"] is True
    assert report["scheme_C_gate_used"] is True
