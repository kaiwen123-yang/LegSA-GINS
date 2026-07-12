from scripts.paper_rebuild import finalize_clean1r2_blocked as finalizer


def test_measurement_std_and_noise_injection_are_independent_fields() -> None:
    audit = finalizer.build_yaw_audit()
    assert audit["measurement"]["yaw_measurement_std_deg"] == 1.5
    assert audit["measurement"]["role"] == "measurement_covariance_R"
    assert audit["injection"]["enabled_in_archived_E001_same_run"] is True
    assert audit["injection"]["yaw_noise_injection_std_deg"] == 1.5
    assert audit["injection"]["seed"] == 42
    assert audit["fixed_1p5_implies_noise_injection"] is False
    assert audit["archived_actual_data_mode"] == "semisynthetic"


def test_clean_requirement_conflicts_with_archived_same_run() -> None:
    gate = finalizer.load_contract()["evidence_contamination_gate"]
    first = gate["first_divergence"]
    assert first["field"] == "yaw_noise_injection_std_deg"
    assert first["expected_clean_value"] == 0.0
    assert first["archived_actual_value"] == 1.5
    second = gate["second_divergence"]
    assert second["field"] == "trace_used_online"
    assert second["expected_clean_value"] is False
    assert second["archived_actual_value"] is True
    assert second["source_lines"] == "741-798,967-977,1007-1035,1083-1111"
    assert gate["contradiction"]["both_can_be_claimed_by_one_run"] is False
