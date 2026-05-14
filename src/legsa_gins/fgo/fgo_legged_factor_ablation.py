"""N8F ablation comparison helpers.

中文说明：汇总 N8F variant 求解、注入和退化标志，不生成性能宣称。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Mapping, Sequence


def build_n8f_comparison_report(variant_report: Mapping[str, Any]) -> Dict[str, Any]:
    variants = list(variant_report.get("variants", []))
    solved = [row for row in variants if row.get("solve_status") == "solved" and row.get("finite_output")]
    gross = [row.get("variant") for row in variants if row.get("gross_degradation_flag")]
    injection_failures = [
        row.get("variant")
        for row in variants
        if (
            row.get("foot_kinematic_velocity_enabled")
            or row.get("yawrate_between_enabled")
            or row.get("relative_odometry_between_enabled")
        )
        and int(row.get("candidate_solver_residual_dim", 0) or 0) <= 0
    ]
    return {
        "stage": "N8F",
        "variant_count": len(variants),
        "solved_variant_count": len(solved),
        "solved_variants": [row.get("variant") for row in solved],
        "gross_degradation_variants": gross,
        "candidate_solver_injection_failures": injection_failures,
        "candidate_solver_injection_passed": not injection_failures,
        "contact_weighting_variants": [row.get("variant") for row in variants if row.get("contact_weighting_enabled")],
        "foot_kinematic_variants": [row.get("variant") for row in variants if row.get("foot_kinematic_velocity_enabled")],
        "yawrate_variants": [row.get("variant") for row in variants if row.get("yawrate_between_enabled")],
        "relative_odometry_variants": [row.get("variant") for row in variants if row.get("relative_odometry_between_enabled")],
        "no_feedback": True,
        "output_substitution": False,
        "trace_solver_input": False,
        "finalv23_solver_input": False,
        "paper_performance_claim": False,
    }


def write_ablation_report(path: Path, report: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
