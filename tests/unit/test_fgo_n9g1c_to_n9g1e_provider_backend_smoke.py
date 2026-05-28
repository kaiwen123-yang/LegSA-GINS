from pathlib import Path

from legsa_gins.fgo.fgo_n9g1c_to_n9g1e_provider_backend_smoke import (
    ALGORITHM_ID,
    backend_audit_rows,
    factor_wiring_rows,
    normal_smoke_gate_report,
    provider_contract_decision,
    write_n9g1c_to_n9g1e_artifacts,
)


ROOT = Path(__file__).resolve().parents[2]


def test_provider_contract_decision_allows_partial_without_claiming_full_pass():
    rows = [
        {"provider": "GNSS position", "ready_for_factor": True},
        {"provider": "foot kinematic velocity", "ready_for_factor": False},
    ]
    assert provider_contract_decision(rows) == "N9G1C_provider_contracts_partial_accepted"


def test_backend_audit_keeps_candidate_solver_blocked():
    rows, status = backend_audit_rows(ROOT)
    assert rows
    assert status["active_backend_available"] is False
    assert status["solver_execution_allowed"] is False
    assert status["classification"] == "offline_candidate_only"
    assert status["decision"] == "N9G1D_active_backend_blocked"


def test_factor_wiring_does_not_enable_without_active_backend():
    provider_rows = [
        {"provider": "GNSS position", "ready_for_factor": True},
        {"provider": "GNSS velocity", "ready_for_factor": True},
        {"provider": "dual yaw", "ready_for_factor": True},
        {"provider": "Raw Doppler", "ready_for_factor": True},
        {"provider": "Go2 joint", "ready_for_factor": True},
    ]
    _, backend_status = backend_audit_rows(ROOT)
    rows = factor_wiring_rows(ROOT, provider_rows, backend_status)
    assert len(rows) == 9
    assert all(row["algorithm_id"] == ALGORITHM_ID for row in rows)
    assert not any(row["runtime_enabled"] for row in rows)
    assert not any(row["active_claim_allowed"] for row in rows)


def test_normal_smoke_gate_blocks_active_backend_absence_even_with_static_pass():
    _, backend_status = backend_audit_rows(ROOT)
    gate = normal_smoke_gate_report(
        provider_decision="N9G1C_provider_contracts_partial_accepted",
        locked_normal_resolved=True,
        backend_status=backend_status,
        factor_rows=[{"runtime_enabled": False}],
        logger_rows=[{"fields_present": True}],
        static_status="pass",
    )
    assert gate["ready_for_normal_smoke"] is False
    assert gate["decision"] == "N9G1E_normal_smoke_gate_blocked"
    assert "active_nine_factor_fgo_backend_unavailable" in gate["blockers"]
    assert "candidate_solver_execution_disabled" in gate["blockers"]
    assert gate["representative_degradation"] is False
    assert gate["full_matrix"] is False


def test_artifact_writer_emits_parseable_blocked_outputs(tmp_path):
    result = write_n9g1c_to_n9g1e_artifacts(ROOT, tmp_path, static_validation_status="pass")
    assert result["backend_decision"] == "N9G1D_active_backend_blocked"
    assert result["normal_smoke_gate"]["ready_for_normal_smoke"] is False
    assert (tmp_path / "reports" / "N9G1C_PROVIDER_RESOLUTION_REPORT.json").exists()
    assert (tmp_path / "reports" / "N9G1E_NORMAL_SMOKE_REPORT.json").exists()
    assert (tmp_path / "matrix" / "N9G1E_FACTOR_EVIDENCE.csv").exists()
    assert (tmp_path / "dry_run" / "LegSA_9F_FGO_EKF_FULL_normal_repeat.runtime_config.yaml").exists()
    assert not list((tmp_path / "normal_smoke").rglob("EVAL_NAV.csv"))
