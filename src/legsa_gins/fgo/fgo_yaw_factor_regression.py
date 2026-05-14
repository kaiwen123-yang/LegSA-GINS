"""Toy yaw-factor regressions for N8A2.

中文说明：这些回归只验证 yaw residual 环绕，不使用 trace/final_v23。
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

from legsa_gins.fgo.fgo_yaw_residuals import dual_yaw_residual_deg, yaw_smoothness_residual_deg
from legsa_gins.fgo.fgo_yaw_smoothness_factor_fix import yaw_smoothness_residual_series


def build_yaw_factor_regression_report() -> dict[str, Any]:
    test1 = yaw_smoothness_residual_deg(359.0, 1.0)
    test2 = dual_yaw_residual_deg(1.0, 359.0)
    sequence = [358.0, 359.0, 1.0, 2.0, 3.0]
    residuals = yaw_smoothness_residual_series(sequence)
    finite_vector = all(math.isfinite(value) for value in [test1, test2, *residuals])
    pass_test1 = abs(test1 - 2.0) < 1e-9
    pass_test2 = abs(test2 - 2.0) < 1e-9
    pass_test3 = max(abs(value) for value in residuals) < 5.0
    return {
        "stage": "N8A2_fgo_yaw_convention_fix",
        "test_359_to_1_smoothness_residual_deg": test1,
        "test_1_minus_359_dual_residual_deg": test2,
        "continuous_wrap_sequence_residuals_deg": residuals,
        "smoothness_359_1_pass": pass_test1,
        "dual_yaw_1_359_pass": pass_test2,
        "continuous_sequence_no_large_spike": pass_test3,
        "finite_residual_vector": finite_vector,
        "all_tests_passed": pass_test1 and pass_test2 and pass_test3 and finite_vector,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "output_only_yaw_correction": False,
        "paper_performance_claim": False,
    }


def write_yaw_factor_regression_report(path: str | Path, report: dict[str, Any]) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output
