from pathlib import Path

from legsa_gins.reporting.by2_degradation_runner_precheck import (
    ApplicabilityRouter,
    EXPECTED_COUNTS,
    FORBIDDEN_EXECUTION_OUTPUT_NAMES,
    RuntimePathPlanner,
    build_algorithm_routing_matrix,
    build_case_registry,
    build_generator_capability_matrix,
    discover_cleaned_matrix_root,
    evaluate_safety_gate,
    load_matrix_bundle,
    run_dryrun_precheck,
    validate_context_paths,
    validate_matrix_bundle,
)


ROOT = Path(__file__).resolve().parents[2]


def _bundle():
    return load_matrix_bundle(discover_cleaned_matrix_root(ROOT))


def test_matrix_parsing_and_expected_counts():
    bundle = _bundle()
    validation = validate_matrix_bundle(bundle)
    assert validation["status"] == "pass"
    assert validation["actual_counts"] == EXPECTED_COUNTS
    assert validation["case_id_unique"] is True


def test_case_registry_contains_execution_graph_metadata():
    bundle = _bundle()
    registry = build_case_registry(bundle)
    assert len(registry) == 81
    first = registry[0]
    assert first.case_id
    assert first.family
    assert first.expected_perturbation.endswith("generator_interface_only=true")
    assert first.status == "dryrun_registered_not_executable"


def test_randomness_rules_are_metadata_only():
    bundle = _bundle()
    deterministic = [row for row in bundle.seed_plan if row["deterministic_or_random"] == "deterministic"]
    assert deterministic
    assert all(row["seed"] == "none" for row in deterministic)
    assert all(row["random_values_required"] == "false" for row in deterministic)
    random_cases = sorted({row["case_id"] for row in bundle.seed_plan if row["deterministic_or_random"] == "random"})
    assert random_cases
    for case_id in random_cases:
        seeds = sorted(row["seed"] for row in bundle.seed_plan if row["case_id"] == case_id)
        assert seeds == [str(i) for i in range(10)]
    assert all(row["array_created"] == "false" for row in bundle.seed_plan)


def test_routing_statuses_and_special_case_boundaries():
    bundle = _bundle()
    router = ApplicabilityRouter(bundle.applicability)
    assert router.route("A_outage_5s", "source_backed_EKF")["routing_status"] == "applicable"
    assert router.route("A_outage_5s", "reject_all_sanity")["routing_status"] == "diagnostic_only"
    assert router.route("A_outage_5s", "final_v23_dual_antenna_EKF")["routing_status"] == "reference_only"
    assert router.route("missing", "source_backed_EKF")["routing_status"] == "blocked"
    for row in bundle.applicability:
        if row["algorithm_group"] == "single_antenna_gnss1_status_KF_GINS" and row["family_code"] not in {"A", "B", "C", "D", "E", "M"}:
            assert row["applicability"] == "not_applicable"
        if row["algorithm_group"] == "pure_INS_reference_initialized":
            assert row["applicability"] in {"not_applicable", "fixed_reference"}
        if row["algorithm_group"] == "final_v23_dual_antenna_EKF":
            assert row["applicability"] == "reference_only"


def test_no_historical_nominal_none_and_no_trace_finalv23_solver_input():
    bundle = _bundle()
    all_text = "\n".join(" ".join(row.values()) for matrix in [bundle.full, bundle.family, bundle.pilot, bundle.applicability] for row in matrix)
    assert "historical_nominal_none" not in all_text
    safety = evaluate_safety_gate(bundle, RuntimePathPlanner(Path("unused")).planned_paths())
    assert safety["status"] == "pass"
    assert safety["ready_for_N9B_execution"] is False
    assert safety["no_solver_run"] is True


def test_generator_capability_matrix_is_interface_only():
    matrix = build_generator_capability_matrix()
    assert {row.generator_id for row in matrix} >= {
        "gnss_outage",
        "deterministic_downsample",
        "position_noise",
        "position_spike",
        "std_inflation",
        "yaw_dropout_noise_spike_bias_std",
        "receiver_velocity",
        "raw_doppler",
        "source_aware",
        "go2_legged",
        "feedback_fgo_diagnostic",
        "mixed_composition",
    }
    assert all(row.interface_only for row in matrix)
    assert all(not row.random_arrays_created for row in matrix)
    assert all(not row.degraded_inputs_created for row in matrix)


def test_context_paths_can_be_validated(tmp_path):
    existing = tmp_path / "normal"
    existing.mkdir()
    report = validate_context_paths({"normal_package_root": existing})
    assert report["status"] == "pass"
    assert report["checked"]["normal_package_root"]["exists"] is True
    external = Path(
        "\\" + "\\" + "wsl.localhost" + "\\Ubuntu-22.04\\" + "home" + "\\user\\KF-GINS\\bin\\evaluate_nav_trace_kfgins_v2.py"
    )
    external_report = validate_context_paths({"official_evaluator_path": external})
    assert external_report["checked"]["official_evaluator_path"]["path"].startswith("<WSL_ALGO_REPO>")


def test_algorithm_routing_matrix_has_expected_rows():
    bundle = _bundle()
    routing = build_algorithm_routing_matrix(bundle)
    assert len(routing) == 891
    assert {row["routing_status"] for row in routing} <= {
        "applicable",
        "diagnostic_only",
        "fixed_reference",
        "reference_only",
        "not_applicable",
        "blocked",
    }
    assert all(row["dryrun_only"] == "true" for row in routing)


def test_dryrun_writes_no_execution_artifacts(tmp_path):
    bundle = _bundle()
    result = run_dryrun_precheck(matrix_root=bundle.matrix_root, runtime_root=tmp_path / "n9b0b", write_outputs=True)
    assert result["decision_report"]["ready_for_N9B_execution"] is False
    assert result["decision_report"]["status"] == "N9B0B_degradation_runner_implementation_ready_for_N9B1_pilot"
    assert result["decision_report"]["ready_for_N9B1_pilot"] is True
    assert result["safety_gate_report"]["no_solver_run"] is True
    forbidden = set(FORBIDDEN_EXECUTION_OUTPUT_NAMES)
    generated_names = {path.name for path in (tmp_path / "n9b0b").rglob("*") if path.is_file()}
    assert not any(any(name.startswith(prefix) for prefix in forbidden) for name in generated_names)
    assert not any(name.endswith(".npy") or name.endswith(".npz") for name in generated_names)
    assert not any(name.endswith(".png") for name in generated_names)
