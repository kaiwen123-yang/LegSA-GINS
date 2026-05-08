"""中文说明：检查 N4H4C GNSS position/velocity/yaw 量测模型文本合约。"""

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
MEASUREMENT = REPO_ROOT / "cpp/legsa_v23_core/src/updates/measurement_update.cpp"


def test_position_measurement_has_p_phi_blocks_and_lever_arm():
    text = MEASUREMENT.read_text(encoding="utf-8")
    for keyword in [
        "buildGnssPositionMeasurement",
        "antenna_blh",
        "Earth::DRi",
        "Earth::DR",
        "P_ID",
        "PHI_ID",
        "skewSymmetric",
        "predicted antenna position minus GNSS observed position",
        "中文说明",
    ]:
        assert keyword in text


def test_velocity_measurement_has_v_block_and_no_raw_doppler():
    text = MEASUREMENT.read_text(encoding="utf-8")
    for keyword in [
        "buildGnssVelocityMeasurement",
        "nav.vel_ned_mps[i] - gnss.vel[i]",
        "V_ID",
        "raw Doppler",
        "N4H4C 不实现 raw Doppler",
    ]:
        assert keyword in text


def test_yaw_measurement_uses_obs_pred_and_conservative_phi_z():
    text = MEASUREMENT.read_text(encoding="utf-8")
    for keyword in [
        "buildGnssYawMeasurement",
        "gnss.yaw_deg - pred_yaw_deg",
        "PHI_ID + 2",
        "scheme_C",
        "status-yaw",
        "中文说明",
    ]:
        assert keyword in text
