from scripts.paper10m1r2e_result_review import all_completed, classify_module, method_counts


def test_classify_source_aware_as_bounded_positive():
    row = {
        "removed_module": "source_aware_weighting",
        "median_delta_horizontal_rmse_m": "0.0024339446607617443",
        "module_help_count": "514",
        "module_hurt_count": "27",
        "same_order_count": "0",
        "metric_tradeoff_count": "412",
    }
    result = classify_module(row)
    assert result["interpretation_label"] == "moderate_positive_evidence"
    assert result["claim_strength"] == "moderate_bounded_stability"


def test_method_count_and_completion_helpers():
    rows = [
        {"method_mode_id": "a", "terminal_status": "COMPLETED_EVALUABLE"},
        {"method_mode_id": "a", "terminal_status": "COMPLETED_EVALUABLE"},
        {"method_mode_id": "b", "terminal_status": "COMPLETED_EVALUABLE"},
    ]
    assert method_counts(rows, "method_mode_id")["a"] == 2
    assert all_completed(rows)
