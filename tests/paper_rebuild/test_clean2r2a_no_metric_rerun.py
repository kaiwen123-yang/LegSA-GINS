from pathlib import Path

from legsa_gins.paper_rebuild.clean2r2a_run_registry import (
    build_clean_run_registry,
    validate_execution_protocol,
)
from legsa_gins.paper_rebuild.paths import load_yaml_mapping
from legsa_gins.paper_rebuild.clean2r2a_evidence import _attempts_close
from legsa_gins.paper_rebuild.clean2r2a_runner import METHOD_ORDER
from legsa_gins.paper_rebuild.clean2r2a_runner import classify_failure


ROOT = Path(__file__).resolve().parents[2]
PROTOCOL = ROOT / "configs/paper_rebuild/clean2r2a_execution_protocol.yaml"
STATISTICS = ROOT / "configs/paper_rebuild/clean2r2a_statistical_contract.yaml"


def test_clean2r2a_metric_driven_rerun_and_search_are_forbidden() -> None:
    protocol = validate_execution_protocol(PROTOCOL)
    statistics = load_yaml_mapping(STATISTICS)
    assert protocol["execution"]["metric_driven_rerun"] is False
    assert protocol["execution"]["per_case_tuning"] is False
    assert statistics["reporting"]["no_metric_driven_rerun"] is True
    assert statistics["reporting"]["no_parameter_search"] is True
    assert all(row["metric_driven_rerun"] is False for row in build_clean_run_registry())
    assert all(row["per_case_tuning"] is False for row in build_clean_run_registry())


def test_technical_retry_requires_same_config_and_never_metric_rerun() -> None:
    attempts = [{
        "method_id": method, "attempt": "1", "returncode": "0",
        "technical_retry": "False", "technical_failure": "False",
        "failure_class": "success", "retry_authorized": "False",
        "terminal_success": "True", "metric_driven_rerun": "False",
        "runtime_config_hash": "a" * 64, "executable_hash": "b" * 64,
    } for method in METHOD_ORDER]
    passed, retries = _attempts_close(attempts)
    assert passed is True and retries == 0
    attempts[0:1] = [
        {**attempts[0], "attempt": "1", "returncode": "137",
         "technical_failure": "True", "failure_class": "resource_exhaustion",
         "retry_authorized": "True", "terminal_success": "False"},
        {**attempts[0], "attempt": "2", "technical_retry": "True"},
    ]
    passed, retries = _attempts_close(attempts)
    assert passed is True and retries == 1
    attempts[1]["runtime_config_hash"] = "c" * 64
    assert _attempts_close(attempts)[0] is False


def test_generic_solver_failure_is_not_a_technical_retry() -> None:
    assert classify_failure(1, "", "method contract mismatch") == (
        "nontechnical_solver_contract_or_data_failure"
    )
    assert classify_failure(137, "", "killed") == "resource_exhaustion"
