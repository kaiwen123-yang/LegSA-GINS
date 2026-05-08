"""中文说明：N4H2G2 artifact hash audit 单元测试。"""

from pathlib import Path

from legsa_gins.evaluation.replay_artifact_hash_audit import compare_artifact_hashes, file_meta, hash_replay_artifacts, sha256_file


def _write_gnss(path: Path, yaw: float) -> None:
    path.write_text(f"0 40 116 10 0.5 0.5 0.8 0 0 0 0.1 0.1 0.1 {yaw} 1.5\n", encoding="utf-8")


def test_hash_diff_input_identical_nav_flags_reused_or_ignored(tmp_path: Path) -> None:
    noisy = tmp_path / "noisy"
    clean = tmp_path / "clean"
    noisy.mkdir()
    clean.mkdir()
    _write_gnss(noisy / "input.gnss", 10.0)
    _write_gnss(clean / "CLEAN_STATUS_YAW.gnss", 40.0)
    nav_text = "0 0 40 116 10 0 0 0 0 0 10\n"
    (noisy / "KF_GINS_Navresult.nav").write_text(nav_text, encoding="utf-8")
    (clean / "KF_GINS_Navresult.nav").write_text(nav_text, encoding="utf-8")
    (noisy / "summary.json").write_text('{"yaw_rmse_deg": 93.0}\n', encoding="utf-8")
    (clean / "CLEAN_REPLAY_SUMMARY.json").write_text('{"yaw_rmse_deg": 2.0}\n', encoding="utf-8")

    clean_hash = hash_replay_artifacts(clean, "clean")
    noisy_hash = hash_replay_artifacts(noisy, "noisy")
    comparison = compare_artifact_hashes(clean_hash, noisy_hash)
    assert comparison["clean_input_differs_from_noisy_input"] is True
    assert comparison["clean_nav_differs_from_noisy_nav"] is False
    assert comparison["possible_yaw_input_ignored_or_output_reused"] is True
    assert comparison["trace_solver_input"] is False


def test_file_meta_and_sha256(tmp_path: Path) -> None:
    path = tmp_path / "a.txt"
    path.write_text("abc", encoding="utf-8")
    assert sha256_file(path) == sha256_file(path)
    meta = file_meta(path)
    assert meta["exists"] is True
    assert meta["size_bytes"] == 3
