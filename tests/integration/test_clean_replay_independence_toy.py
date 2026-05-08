"""中文说明：N4H2G2 toy integration 只验证审计链路，不运行外部 KF-GINS。"""

from pathlib import Path

from legsa_gins.evaluation.clean_replay_fresh_summary_audit import recompute_clean_summary_from_nav
from legsa_gins.evaluation.replay_artifact_hash_audit import compare_artifact_hashes, hash_replay_artifacts
from legsa_gins.evaluation.yaw_input_sensitivity_probe import create_yaw_shifted_gnss


def test_clean_replay_independence_toy(tmp_path: Path) -> None:
    noisy = tmp_path / "noisy"
    clean = tmp_path / "clean"
    noisy.mkdir()
    clean.mkdir()
    (noisy / "input.gnss").write_text("0 40 116 10 0 0 0 0 0 0 0 0 0 10 1.5\n", encoding="utf-8")
    (clean / "CLEAN_STATUS_YAW.gnss").write_text("0 40 116 10 0 0 0 0 0 0 0 0 0 40 1.5\n", encoding="utf-8")
    nav = "0 0 40 116 10 0 0 0 0 0 10\n"
    (noisy / "KF_GINS_Navresult.nav").write_text(nav, encoding="utf-8")
    (clean / "KF_GINS_Navresult.nav").write_text(nav, encoding="utf-8")
    (noisy / "summary.json").write_text('{"yaw_rmse_deg": 93.0}\n', encoding="utf-8")
    (clean / "CLEAN_REPLAY_SUMMARY.json").write_text('{"yaw_rmse_deg": 0.0}\n', encoding="utf-8")

    comparison = compare_artifact_hashes(hash_replay_artifacts(clean, "clean"), hash_replay_artifacts(noisy, "noisy"))
    assert comparison["possible_yaw_input_ignored_or_output_reused"] is True

    reference = [{"timestamp": 0.0, "lat_deg": 40.0, "lon_deg": 116.0, "height_m": 10.0, "roll_deg": 0.0, "pitch_deg": 0.0, "yaw_deg": 10.0}]
    fresh = recompute_clean_summary_from_nav(clean / "KF_GINS_Navresult.nav", reference, tmp_path / "fresh", old_clean_summary_path=clean / "CLEAN_REPLAY_SUMMARY.json")
    assert fresh["old_clean_summary_used_as_input"] is False

    shifted = tmp_path / "shifted.gnss"
    create_yaw_shifted_gnss(clean / "CLEAN_STATUS_YAW.gnss", shifted, yaw_shift_deg=30.0)
    assert "70" in shifted.read_text(encoding="utf-8")
