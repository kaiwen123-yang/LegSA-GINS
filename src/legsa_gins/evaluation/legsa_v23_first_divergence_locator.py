"""N4H4D4 first-divergence classification.

中文说明：把 trace parity 的首次发散时间映射到诊断类别；不修改 solver 输出。
"""

from __future__ import annotations

from typing import Any


def classify_first_divergence(divergence_report: dict[str, Any], runtime_loop_report: dict[str, Any] | None = None) -> dict[str, Any]:
    """中文说明：判断发散更像发生在首次更新前、首次更新处，还是长时间漂移。"""

    loop = runtime_loop_report or {}
    update_count_low = bool(loop.get("update_count_low", False))
    if divergence_report.get("divergence_before_first_update"):
        category = "before_first_update"
    elif divergence_report.get("divergence_at_first_update"):
        category = "at_first_update"
    elif update_count_low:
        category = "runtime_update_timing"
    elif divergence_report.get("divergence_only_late_drift"):
        category = "late_drift"
    elif divergence_report.get("divergence_after_state_feedback"):
        category = "after_state_feedback"
    else:
        category = "evidence_missing"
    return {
        "first_divergence_category": category,
        "first_divergence_time": divergence_report.get("first_divergence_time"),
        "first_update_time": divergence_report.get("first_update_time"),
        "divergence_before_first_update": bool(divergence_report.get("divergence_before_first_update")),
        "divergence_at_first_update": bool(divergence_report.get("divergence_at_first_update")),
        "divergence_after_state_feedback": bool(divergence_report.get("divergence_after_state_feedback")),
        "trace_solver_input": False,
        "numerical_performance_claim": False,
    }
