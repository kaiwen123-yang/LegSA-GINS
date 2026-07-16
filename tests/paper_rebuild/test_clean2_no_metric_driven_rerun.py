import pytest

from legsa_gins.paper_rebuild.clean2_runner import Clean2RunError, validate_attempt_rows


def test_retry_policy_is_technical_only():
    rows = [
        {"run_id": "R001", "run_order": 1, "attempt_number": 1,
         "technical_retry": False, "metric_driven_rerun": False,
         "retry_reason": "process_crash", "returncode": -11,
         "terminal_status": "RETRYABLE_TECHNICAL_FAILURE"},
        {"run_id": "R001", "run_order": 1, "attempt_number": 2,
         "technical_retry": True, "metric_driven_rerun": False,
         "retry_reason": "process_crash", "returncode": 0,
         "terminal_status": "PASS"},
    ]
    assert validate_attempt_rows(rows)["metric_driven_rerun"] is False


def test_timeout_is_not_an_authorized_retry_reason():
    rows = [
        {"run_id": "R001", "run_order": 1, "attempt_number": 1,
         "technical_retry": False, "metric_driven_rerun": False,
         "retry_reason": "timeout", "returncode": 124,
         "terminal_status": "RETRYABLE_TECHNICAL_FAILURE"},
        {"run_id": "R001", "run_order": 1, "attempt_number": 2,
         "technical_retry": True, "metric_driven_rerun": False,
         "retry_reason": "timeout", "returncode": 0,
         "terminal_status": "PASS"},
    ]
    with pytest.raises(Clean2RunError, match="authorized technical retry"):
        validate_attempt_rows(rows)
