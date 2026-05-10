from legsa_gins.raw_gnss.raw_doppler_visual_sanity import build_visual_sanity_report


def _inputs(source_issue=False):
    return {
        "raw_factor_rows": [{"time": 1.0, "vn": 1.0, "ve": 0.0, "vd": 0.0}],
        "velocity_comparison": {
            "possible_pvt_velocity_copy_suspect": source_issue,
            "raw_doppler_not_gnss_15col": not source_issue,
        },
        "time_alignment": {"update_alignment_ok": True},
        "variant_reports": [
            {"variant_id": "baseline_plus_raw_doppler_r1", "raw_doppler_update_count": 3, "raw_doppler_reject_count": 0, "enable_raw_doppler": True},
            {"variant_id": "receiver_velocity_disabled_plus_raw", "raw_doppler_update_count": 3, "raw_doppler_reject_count": 0, "enable_raw_doppler": True},
        ],
    }


def test_detects_source_issue_missing_figures_and_time_alignment():
    # 中文说明：sanity gate 优先拦截 source/time/figure 问题。
    report = build_visual_sanity_report(
        inputs=_inputs(source_issue=True),
        figure_manifest={"figure_count_total": 10, "pure_single_absent": True},
        stress_eval={"stress_variants_completed": True, "clean_delta_baseline_plus_raw_minus_baseline": {}},
    )
    assert report["raw_velocity_not_pvt_copy"] is False
    assert report["figures_generated_minimum_ok"] is False
    assert report["visual_stress_candidate_passed"] is False
    bad_time = _inputs()
    bad_time["time_alignment"] = {"update_alignment_ok": False}
    report = build_visual_sanity_report(
        inputs=bad_time,
        figure_manifest={"figure_count_total": 30, "pure_single_absent": True},
        stress_eval={"stress_variants_completed": True, "clean_delta_baseline_plus_raw_minus_baseline": {}},
    )
    assert report["time_alignment_ok"] is False


def test_detects_clean_divergence():
    report = build_visual_sanity_report(
        inputs=_inputs(),
        figure_manifest={"figure_count_total": 30, "pure_single_absent": True},
        stress_eval={
            "stress_variants_completed": True,
            "clean_delta_baseline_plus_raw_minus_baseline": {"yaw_rmse_deg": 2.5},
        },
    )
    assert report["clean_variant_no_gross_divergence"] is False
