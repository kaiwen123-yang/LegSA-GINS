"""Evaluation helpers for N8G feedback variants.

中文说明：评价只做 baseline delta 和 evaluation-only namespace，不回写 solver。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .feedback_state_types import angle_delta_deg, norm, stats
from .sliding_window_manager import read_eval_nav_csv


def evaluate_variant_against_baseline(
    baseline_eval_nav: str | Path,
    feedback_eval_nav: str | Path,
    *,
    variant_id: str,
    manifest: dict[str, Any],
) -> dict[str, Any]:
    baseline = read_eval_nav_csv(baseline_eval_nav)
    feedback = read_eval_nav_csv(feedback_eval_nav)
    count = min(len(baseline), len(feedback))
    horizontal: list[float] = []
    yaw: list[float] = []
    roll_pitch: list[float] = []
    for left, right in zip(baseline[:count], feedback[:count]):
        horizontal.append(norm([right.lat_deg - left.lat_deg, right.lon_deg - left.lon_deg]) * 111_000.0)
        yaw.append(abs(angle_delta_deg(right.yaw_deg, left.yaw_deg)))
        roll_pitch.append(norm([angle_delta_deg(right.roll_deg, left.roll_deg), angle_delta_deg(right.pitch_deg, left.pitch_deg)]))
    gross_degradation = stats(horizontal)["p95"] > 30.0 or stats(yaw)["p95"] > 20.0
    return {
        "variant_id": variant_id,
        "row_count_compared": count,
        "feedback_count": int(manifest.get("feedback_observation_count", 0) or 0),
        "accepted": int(manifest.get("feedback_accept_count", 0) or 0),
        "rejected": int(manifest.get("feedback_reject_count", 0) or 0),
        "feedback_vs_baseline_delta": {
            "horizontal_m": stats(horizontal),
            "yaw_deg": stats(yaw),
            "roll_pitch_deg": stats(roll_pitch),
        },
        "feedback_vs_reference_evaluation_only": {"available": False, "solver_input": False},
        "parity_to_final_v23": {"available": False, "evaluation_only": True, "solver_input": False},
        "clean_gross_degradation": gross_degradation,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "paper_performance_claim": False,
    }


def build_evaluation_report(results: list[dict[str, Any]]) -> dict[str, Any]:
    accepted_total = sum(int(item.get("accepted", 0) or 0) for item in results)
    rejected_total = sum(int(item.get("rejected", 0) or 0) for item in results)
    return {
        "stage": "N8G",
        "variant_count": len(results),
        "feedback_count": accepted_total + rejected_total,
        "accepted": accepted_total,
        "rejected": rejected_total,
        "variant_results": results,
        "gross_degradation_status": "absent" if not any(item.get("clean_gross_degradation") for item in results) else "present",
        "metric_namespaces": [
            "feedback_vs_baseline_delta",
            "feedback_vs_reference_evaluation_only",
            "parity_to_final_v23_evaluation_only",
        ],
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "paper_performance_claim": False,
    }


def write_evaluation_report(path: str | Path, report: dict[str, Any]) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
