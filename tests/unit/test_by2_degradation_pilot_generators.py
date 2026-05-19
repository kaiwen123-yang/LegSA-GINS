from pathlib import Path

from legsa_gins.reporting.by2_degradation_pilot_generators import (
    PILOT_CASE_IDS,
    RANDOM_CASE_IDS,
    build_applicability_routing_check,
    build_pilot_generations,
    discover_cleaned_matrix_root,
    generate_a_outage_5s,
    generate_b_gnss_downsample_2hz,
    generate_c_position_noise_medium,
    generate_d_position_spike_medium,
    generate_h_dual_yaw_noise_medium,
    load_matrix_bundle,
    run_pilot_generator_precheck,
    validate_pilot_precheck_result,
)


ROOT = Path(__file__).resolve().parents[2]


def _bundle():
    return load_matrix_bundle(discover_cleaned_matrix_root(ROOT))


def test_all_approved_pilot_cases_have_generators_and_seed_rows():
    bundle = _bundle()
    generations = build_pilot_generations(bundle)
    generated_cases = {generation.case_id for generation in generations}
    assert generated_cases == set(PILOT_CASE_IDS)
    assert len([generation for generation in generations if generation.case_id in RANDOM_CASE_IDS]) == 30
    assert len([generation for generation in generations if generation.case_id not in RANDOM_CASE_IDS]) == 7


def test_outage_and_downsample_are_deterministic_toy_masks():
    outage = generate_a_outage_5s()
    assert outage.seed == "none"
    assert outage.manifest["outage_start_s"] == 206.2
    assert outage.manifest["outage_end_s"] == 211.2
    assert outage.manifest["mask_count"] == 6
    downsample = generate_b_gnss_downsample_2hz()
    assert downsample.manifest["source_rate_hz"] == 10
    assert downsample.manifest["target_rate_hz"] == 2
    assert downsample.manifest["integer_step"] == 5
    assert downsample.manifest["kept_count"] == 4


def test_seeded_random_cases_create_only_tiny_toy_values():
    noise = generate_c_position_noise_medium(0)
    spike = generate_d_position_spike_medium(0)
    yaw = generate_h_dual_yaw_noise_medium(0)
    assert noise.manifest["sigma_h_m"] == 1.5
    assert noise.manifest["sigma_v_m"] == 2.5
    assert len(noise.toy_values) == 5
    assert spike.manifest["probability"] == 0.05
    assert spike.manifest["horizontal_amplitude_m"] == 4.0
    assert spike.manifest["vertical_amplitude_m"] == 2.0
    assert spike.manifest["toy_population_count"] == 20
    assert yaw.manifest["sigma_yaw_deg"] == 3.0
    assert yaw.manifest["single_antenna_routing_expected"] == "not_applicable"
    assert yaw.manifest["pure_INS_routing_expected"] == "not_applicable"
    assert all(row["not_degradation_execution"] is True for row in [noise.manifest, spike.manifest, yaw.manifest])


def test_applicability_routing_preserves_cleaned_matrix_boundaries():
    bundle = _bundle()
    rows = build_applicability_routing_check(bundle)
    assert len(rows) == 110
    lookup = {(row["case_id"], row["algorithm_group"]): row["routing_status"] for row in rows}
    for cid in ["A_outage_5s", "B_gnss_downsample_2Hz", "C_position_noise_medium", "D_position_spike_medium"]:
        assert lookup[(cid, "single_antenna_gnss1_status_KF_GINS")] == "applicable"
    assert lookup[("H_dual_yaw_noise_medium", "single_antenna_gnss1_status_KF_GINS")] == "not_applicable"
    assert lookup[("H_dual_yaw_noise_medium", "pure_INS_reference_initialized")] == "not_applicable"
    assert all(
        status == "reference_only"
        for (case_id, algorithm), status in lookup.items()
        if algorithm == "final_v23_dual_antenna_EKF"
    )


def test_precheck_writes_required_reports_without_execution_artifacts(tmp_path):
    bundle = _bundle()
    runtime_root = tmp_path / "n9b0c"
    result = run_pilot_generator_precheck(matrix_root=bundle.matrix_root, runtime_root=runtime_root, write_outputs=True)
    validation = validate_pilot_precheck_result(result, runtime_root)
    assert validation["status"] == "pass"
    assert result["decision_report"]["ready_for_N9B_execution"] is False
    assert result["decision_report"]["ready_for_N9B1_execution"] is True
    assert result["decision_report"]["status"] == "N9B0C_pilot_generators_ready_for_N9B1_execution"
    assert all(row["ready_for_N9B1_execution"] for row in result["n9b1_pilot_ready_matrix"])
    assert len(result["toy_random_value_manifest"]) == 30
    assert all(row["hash_sha256"] for row in result["toy_random_value_manifest"])
    assert not list(runtime_root.rglob("*.npy"))
    assert not list(runtime_root.rglob("*.npz"))
    assert not list(runtime_root.rglob("*.png"))
