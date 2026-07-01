from scripts.paper10q1_qm_evidence_review import comparison_rows, parse_state_counts


def test_parse_state_counts_fills_missing_states():
    counts = parse_state_counts('{"normal": 2, "downweight": 3}')
    assert counts["normal"] == 2
    assert counts["downweight"] == 3
    assert counts["reject"] == 0
    assert counts["fallback"] == 0


def test_comparison_delta_positive_means_full_better():
    rows = [
        {
            "case_id": "case_a",
            "degradation_type_id": "D27",
            "degradation_type_name": "bad_position_optimistic_std",
            "case_family": "quality_mismatch",
            "seed_index": "seed_00",
            "ablation_method_id": "legsa_full_candidate_with_qm",
            "horizontal_rmse_m": "1.0",
            "up_rmse_m": "0.5",
            "yaw_rmse_deg": "2.0",
        },
        {
            "case_id": "case_a",
            "degradation_type_id": "D27",
            "degradation_type_name": "bad_position_optimistic_std",
            "case_family": "quality_mismatch",
            "seed_index": "seed_00",
            "ablation_method_id": "legsa_no_qm",
            "horizontal_rmse_m": "1.2",
            "up_rmse_m": "0.7",
            "yaw_rmse_deg": "2.5",
        },
    ]
    out = comparison_rows(
        rows,
        "legsa_full_candidate_with_qm",
        "legsa_no_qm",
        "full_vs_no_qm",
        "unit",
    )
    assert abs(out[0]["horizontal_rmse_delta_comparison_minus_full_m"] - 0.2) < 1e-12
    assert out[0]["metric_relation"] == "full_qm_better_all_metrics"
