def test_mixed_operation_order_and_rng_restart_are_frozen(apply_case):
    result = apply_case("C15")
    operations = [result.ledger_rows[index]["operation"] for index in (0, 40, 80)]
    assert operations == ["baseline_vector_noise", "baseline_vector_spike", "signed_yaw_spike"]
    assert result.policy_report["operation_selected_counts"] == {"baseline_vector_noise": 40, "baseline_vector_spike": 1, "signed_yaw_spike": 1}
