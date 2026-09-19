from pathlib import Path

from legsa_gins.paper_rebuild.canonical541.authorization import (
    RUNTIME_ROLE, STAGE_ID, load_execution_authorization,
)
from legsa_gins.paper_rebuild.canonical541.preflight import run_registry_preflight


def test_repaired_execution_authorization_is_explicit_and_fail_closed():
    repo = Path(__file__).resolve().parents[2]
    contract = load_execution_authorization(repo)
    assert contract["stage_id"] == STAGE_ID
    assert contract["runtime_role"] == RUNTIME_ROLE
    assert contract["old_method_bound_formal_reuse_allowed"] is False
    assert contract["method_bound_rebuild_required"] is True
    assert contract["trace_allowed_online"] is False


def test_read_only_registry_preflight_closes_exact_matrix_and_routes():
    repo = Path(__file__).resolve().parents[2]
    result = run_registry_preflight(repo)
    assert result["passed"] is True
    assert result["case_count"] == 541
    assert result["expected_identity_count"] == 5951
    assert result["logical_row_count"] == 7033
    assert result["effective_config_count"] == 11
    assert result["duplicate_identity_count"] == 0
    assert result["missing_identity_count"] == 0
    assert result["invalid_algorithm_role_route_count"] == 0
    assert result["hard_coded_clean2_only_rejection_count"] == 0
    assert result["clean1_role_overwrite_count"] == 0
    assert result["trace_open_count"] == 0
