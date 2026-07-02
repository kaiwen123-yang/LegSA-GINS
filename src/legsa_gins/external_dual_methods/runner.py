"""Q2R2 runner guard helpers.

The actual external method matrix is permitted only after the BY2 input
contract closes.  When inputs are missing this module reports blocked rows
instead of fabricating completed evaluator outputs.
"""

from __future__ import annotations

from .method_contracts import MethodContract


def blocked_status_for_method(method: MethodContract, missing_inputs: list[str]) -> dict[str, str]:
    return {
        "method_id": method.method_id,
        "terminal_status": "BLOCKED_WITH_PROOF",
        "blocked_reason": "PROVIDER_CONTRACT_MISSING_INPUTS",
        "missing_inputs": ";".join(missing_inputs),
        "trace_used_online": "false",
        "receiver_imu_as_body_imu": "false",
        "final_v23_output_solver_input": "false",
        "legsa_output_solver_input": "false",
    }
