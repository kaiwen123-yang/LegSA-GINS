"""A1 matrix row construction helpers."""

from __future__ import annotations

from .method_contracts import MethodContract


def matrix_queue(methods: list[MethodContract], cases: list[dict[str, str]]) -> list[dict[str, str]]:
    return [
        {
            "row_id": f"{method.method_id}__{case['case_id']}",
            "method_id": method.method_id,
            "case_id": case["case_id"],
            "case_family": case.get("case_family", ""),
            "degradation_type_id": case.get("degradation_type_id", ""),
            "planned_status": "RUN",
            "trace_used_online": "false",
            "receiver_imu_as_body_imu": "false",
            "final_v23_output_solver_input": "false",
            "legsa_output_solver_input": "false",
        }
        for method in methods
        for case in cases
    ]
