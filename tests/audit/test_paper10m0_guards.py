"""中文说明：PAPER10M0 guard tests; 队列必须 locked，禁止输入必须 false。"""

from scripts.paper10m0_guard_validator import validate_guard_state


def test_paper10m0_guard_accepts_locked_queue_and_clean_smoke():
    queue_rows = [
        {"run_allowed_now": "false", "human_approval_required": "true"},
        {"run_allowed_now": "false", "human_approval_required": "true"},
    ]
    smoke_rows = [{"row_id": "s1"}, {"row_id": "s2"}]
    smoke_results = [
        {
            "row_id": "s1",
            "trace_used_online": False,
            "final_v23_output_used_as_input": False,
            "legsa_output_used_as_input": False,
            "benchmark_output_used_as_input": False,
            "per_case_tuning_used": False,
            "output_only_correction_used": False,
            "qa_fallback_as_final_method": False,
        }
    ]
    assert validate_guard_state(queue_rows=queue_rows, smoke_rows=smoke_rows, smoke_results=smoke_results)["status"] == "pass"


def test_paper10m0_guard_rejects_unlocked_m1_queue():
    result = validate_guard_state(
        queue_rows=[{"run_allowed_now": "true", "human_approval_required": "true"}],
        smoke_rows=[],
        smoke_results=[],
    )
    assert result["status"] == "fail"
    assert any("run_allowed_now" in issue for issue in result["issues"])


def test_paper10m0_guard_rejects_forbidden_input():
    result = validate_guard_state(
        queue_rows=[{"run_allowed_now": "false", "human_approval_required": "true"}],
        smoke_rows=[{"row_id": "s1"}],
        smoke_results=[{"row_id": "s1", "trace_used_online": True}],
    )
    assert result["status"] == "fail"
    assert any("trace_used_online" in issue for issue in result["issues"])
