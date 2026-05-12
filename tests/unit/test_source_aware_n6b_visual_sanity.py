from legsa_gins.source_aware.source_aware_n6b_plot_coverage import N6B1FigureCoverage
from legsa_gins.source_aware.source_aware_n6b_visual_sanity import build_n6b1_visual_sanity_report


def _coverage(category: str = "stress", failed: bool = False) -> N6B1FigureCoverage:
    return N6B1FigureCoverage(
        figure_name="figure.png",
        figure_path="figure.png",
        mandatory=True,
        source_data_roles=[],
        plotted_series_count=2,
        plotted_row_count_by_series={"a": 10, "b": 10},
        total_plotted_row_count=20,
        x_min=0.0,
        x_max=300.0,
        x_range=300.0,
        y_min=0.0,
        y_max=1.0,
        y_range=1.0,
        has_nonempty_data=not failed,
        has_reasonable_time_axis=not failed,
        empty_plot_suspect=failed,
        reason_codes=["failed"] if failed else [],
        source_ids=[],
        figure_category=category,
    )


def _inputs(p50: float = 1.0):
    rows = [{"timestamp": float(i)} for i in range(5)]
    trace = [{"time": float(i)} for i in range(5)]
    return {
        "clean_errors": {"baseline_plus_raw_no_sourceaware": rows, "n6b_lsim_oim": rows},
        "n6b_trace": trace,
        "reports": {
            "N6B_SOURCE_AWARE_POLICY_DIAGNOSTICS.json": {
                "clean_neutrality_gate": {"pass": True},
                "spike_response_status": "increased_mildly",
            },
            "N6B_SOURCE_AWARE_WEIGHT_STATS.json": {
                "main_variant_stats": {
                    "stats_by_source": {
                        "receiver_position": {"R_scale_p50": p50, "R_scale_p95": p50, "R_scale_max": p50},
                        "receiver_velocity": {"R_scale_p50": p50, "R_scale_p95": p50, "R_scale_max": p50},
                    }
                }
            },
            "N6B_SPIKE_RESPONSE_REPORT.json": {"response_status": "increased_mildly", "responses": []},
        },
    }


def test_n6b1_visual_sanity_passes_nominal():
    # 中文说明：sanity pass 需要图像非空、clean 无明显退化、R scale 未卡 cap。
    report = build_n6b1_visual_sanity_report(
        visual_inputs=_inputs(),
        figure_manifest={"required_figures_generated": True, "required_figures_nonempty": True, "coverage": [_coverage()]},
        coverage_report={"required_figures_generated": True, "required_figures_nonempty": True},
    )
    assert report["visual_sanity_passed"] is True
    assert report["paper_performance_claim"] is False


def test_n6b1_visual_sanity_detects_source_stuck_at_cap():
    # 中文说明：source R scale 长期贴近 cap 时必须被识别为策略风险。
    report = build_n6b1_visual_sanity_report(
        visual_inputs=_inputs(p50=5.0),
        figure_manifest={"required_figures_generated": True, "required_figures_nonempty": True, "coverage": [_coverage()]},
        coverage_report={"required_figures_generated": True, "required_figures_nonempty": True},
    )
    assert report["receiver_position_not_slammed_to_cap"] is False
