"""N7B5 frame sensitivity runner 单元测试：blocked run 仍保留边界。"""

from legsa_gins.go2_prior.go2_frame_sensitivity_runner import VARIANT_IDS, run_n7b5_frame_sensitivity_variants


def test_frame_sensitivity_runner_blocks_without_allow_run(tmp_path):
    report, summaries = run_n7b5_frame_sensitivity_variants(
        clean_root=tmp_path / "clean_missing",
        output_dir=tmp_path / "out",
        exe=tmp_path / "missing_demo",
        raw_doppler_factor_path=None,
        prior_paths={},
        allow_run=False,
    )
    assert report["diagnostic_only"] is True
    assert report["formal_go2_velocity_prior"] is False
    assert report["paper_performance_claim"] is False
    assert report["variant_count"] == len(VARIANT_IDS)
    assert all(row["run_status"] == "blocked" for row in summaries["variants"])
