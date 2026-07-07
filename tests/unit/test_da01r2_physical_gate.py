from legsa_gins.da_repro.full_backend_classic_runner import baseline_physical_summary_from_rows, dd_provider_summary_from_rows


def test_physical_gate_detects_valid_and_four_meter_baselines():
    valid = [{"baseline_length_m": 0.355}, {"baseline_length_m": 0.36}, {"baseline_length_m": 0.35}]
    assert baseline_physical_summary_from_rows(valid)["baseline_physical_gate_pass"] is True
    bad = [{"baseline_length_m": 4.0}, {"baseline_length_m": 4.1}, {"baseline_length_m": 3.9}]
    summary = baseline_physical_summary_from_rows(bad)
    assert summary["baseline_physical_gate_pass"] is False
    assert summary["four_meter_baseline_reappeared"] is True


def test_dd_provider_summary_counts_rank3_epochs():
    rows = [
        {"num_dd": 5, "design_rank": 3, "design_condition_number": 2.0},
        {"num_dd": 4, "design_rank": 3, "design_condition_number": 3.0},
        {"num_dd": 2, "design_rank": 2, "design_condition_number": 9.0},
    ]
    summary = dd_provider_summary_from_rows(rows)
    assert summary["usable_dd_epochs"] == 3
    assert summary["rank3_epoch_count"] == 2
    assert summary["median_num_dd"] == 4.0
