from pathlib import Path

from legsa_gins.fgo.fgo_n9g1b_legsa_9f_phase1 import (
    ALGORITHM_ID,
    FGO_FACTOR_RESIDUAL_FIELDS,
    LEGGED_DIAGNOSTIC_FIELDS,
    build_factor_wiring_rows,
    classify_factor_evidence,
    logger_schemas,
    normal_smoke_gate,
    write_phase1_artifacts,
)
from legsa_gins.reporting.by2_algorithm_runner import (
    ALGORITHM_SPECS,
    FORMAL_ALGORITHMS,
    build_algorithm_config_text,
)


ROOT = Path(__file__).resolve().parents[2]


def test_legsa_9f_candidate_identity_is_separate_and_blocked_for_solver():
    assert ALGORITHM_ID in FORMAL_ALGORITHMS
    assert ALGORITHM_ID != "LegSA_full_EKF"
    spec = ALGORITHM_SPECS[ALGORITHM_ID]
    assert spec.role == "new_algorithm_candidate"
    assert spec.active_fgo_backend_available is False
    assert spec.solver_execution_allowed is False
    assert spec.complete_nine_factor_fgo_claim is False

    full = ALGORITHM_SPECS["LegSA_full_EKF"]
    assert full.role == "formal_algorithm"
    assert full.solver_execution_allowed is True


def test_legsa_9f_config_records_candidate_boundary(tmp_path):
    text = build_algorithm_config_text(
        ROOT,
        ALGORITHM_ID,
        tmp_path / "out",
        {
            "imupath": "/clean/CLEAN_STATUS_YAW.imu",
            "gnsspath": "/clean/CLEAN_STATUS_YAW.gnss",
        },
    )
    assert "algorithm_id: LegSA_9F_FGO_EKF" in text
    assert "algorithm_role: new_algorithm_candidate" in text
    assert "active_fgo_backend_available: false" in text
    assert "solver_execution_allowed: false" in text
    assert "complete_nine_factor_FGO_claim: false" in text
    assert "trace_solver_input: false" in text
    assert "final_v23_output_solver_input: false" in text
    assert "output_only_correction: false" in text
    assert "fgo: false" in text


def test_logger_schema_contains_required_factor_and_legged_fields():
    schemas = logger_schemas()
    for field in FGO_FACTOR_RESIDUAL_FIELDS:
        assert field in schemas["fgo_factor_residual_timeseries"]
    for field in LEGGED_DIAGNOSTIC_FIELDS:
        assert field in schemas["legged_diagnostic_timeseries"]
    assert "cost_contribution" in schemas["fgo_factor_residual_timeseries"]
    assert "jacobian_nonzero" in schemas["fgo_factor_residual_timeseries"]


def test_factor_status_rules_block_provider_counts_and_candidate_only():
    assert classify_factor_evidence({"provider_update_count_only": True}) == "blocked_provider_update_count_only"
    assert classify_factor_evidence({"candidate_only": True, "integrated_active_fgo": False}) == "candidate_only"
    active = {
        "code_symbol_exists": True,
        "runtime_enabled": True,
        "instantiated": True,
        "contributes_rows": True,
        "residual_evaluated": True,
        "residual_dim_recorded": True,
        "timestamps_recorded": True,
        "window_ids_recorded": True,
        "cost_contribution_recorded": True,
    }
    assert classify_factor_evidence(active) == "active"


def test_phase1_factor_wiring_does_not_mark_candidate_active():
    rows = build_factor_wiring_rows(ROOT)
    assert len(rows) == 9
    assert all(row["algorithm_id"] == ALGORITHM_ID for row in rows)
    assert all(row["active_or_candidate"] != "active" for row in rows)
    assert all(row["contributes_rows"] is False for row in rows)
    legged = [row for row in rows if row["factor_type"] in {"FootKinematicVelocityFactor", "YawRateBetweenFactor", "RelativeOdometryBetweenFactor"}]
    assert legged
    assert all(row["active_or_candidate"] == "candidate_only" for row in legged)


def test_normal_smoke_gate_blocks_without_active_fgo_backend():
    gate = normal_smoke_gate(
        provider_decision="partial_provider_contracts_passed",
        static_validation_status="pass",
        logger_schema_valid=True,
        safety_violation=False,
    )
    assert gate["ready_for_normal_smoke"] is False
    assert gate["decision"] == "normal_smoke_not_run_blocked_by_gate"
    assert "active_nine_factor_fgo_backend_unavailable" in gate["blockers"]
    assert gate["representative_degradation"] is False
    assert gate["full_matrix"] is False


def test_phase1_artifact_writer_emits_parseable_schema_only_outputs(tmp_path):
    result = write_phase1_artifacts(ROOT, tmp_path, static_validation_status="pass")
    assert result["normal_smoke_gate"]["ready_for_normal_smoke"] is False
    assert (tmp_path / "reports" / "N9G1B_NORMAL_SMOKE_REPORT.json").exists()
    assert (tmp_path / "matrix" / "N9G1B_FACTOR_EVIDENCE.csv").exists()
    assert (tmp_path / "logger_schema" / "fgo_factor_residual_timeseries.csv").exists()
    assert not list((tmp_path / "normal_smoke").glob("EVAL_NAV.csv"))
