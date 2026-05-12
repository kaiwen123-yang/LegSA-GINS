"""N7B2 diagnostic contact-threshold review.

中文说明：threshold candidates 只由 Go2 field distributions 产生；禁止 trace
或 final_v23 output 调阈值，也不根据导航指标调参。
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any


def _num(value: Any, fallback: float) -> float:
    return float(value) if isinstance(value, (int, float)) and math.isfinite(float(value)) else fallback


def _foot_thresholds(distribution_report: dict[str, Any], key: str, fallback: float) -> dict[str, float]:
    stats_by_foot = distribution_report.get("foot_force_stats_by_foot", {})
    out: dict[str, float] = {}
    for foot in range(4):
        stats = stats_by_foot.get(f"foot_{foot}", {})
        out[f"foot_{foot}"] = max(0.0, _num(stats.get(key), fallback))
    return out


def _speed_thresholds(distribution_report: dict[str, Any], key: str, fallback: float) -> dict[str, float]:
    stats_by_foot = distribution_report.get("foot_speed_norm_stats_by_foot", {})
    out: dict[str, float] = {}
    for foot in range(4):
        stats = stats_by_foot.get(f"foot_{foot}", {})
        out[f"foot_{foot}"] = max(0.0, _num(stats.get(key), fallback))
    return out


def review_contact_thresholds(distribution_report: dict[str, Any]) -> dict[str, Any]:
    p25_force = _foot_thresholds(distribution_report, "p25", 8.0)
    p35_force = _foot_thresholds(distribution_report, "p35", 12.0)
    p50_force = _foot_thresholds(distribution_report, "p50", 15.0)
    speed_p50 = _speed_thresholds(distribution_report, "p50", 0.50)
    speed_p35 = _speed_thresholds(distribution_report, "p35", 0.35)
    candidates = {
        "force_percentile_based": {
            "force_threshold_by_foot": p25_force,
            "speed_support_threshold_by_foot": speed_p50,
            "description": "contact if force exceeds per-foot p25; speed is supporting evidence only",
        },
        "force_mixture_heuristic": {
            "force_threshold_by_foot": {
                foot: 0.5 * (p25_force[foot] + p50_force[foot]) for foot in p25_force
            },
            "speed_support_threshold_by_foot": speed_p50,
            "description": "midpoint between lower and median force distribution",
        },
        "speed_assisted_contact": {
            "force_threshold_by_foot": p35_force,
            "low_force_threshold_by_foot": {foot: max(0.0, p25_force[foot] * 0.60) for foot in p25_force},
            "speed_support_threshold_by_foot": speed_p35,
            "description": "force threshold with low-speed support for weak-contact rows",
        },
        "mode_gait_assisted_contact": {
            "force_threshold_by_foot": p25_force,
            "low_force_threshold_by_foot": {foot: max(0.0, p25_force[foot] * 0.60) for foot in p25_force},
            "speed_support_threshold_by_foot": speed_p50,
            "description": "recommended N7B2 diagnostic candidate using mode/gait labels and Go2 field distributions",
        },
    }
    return {
        "stage": "N7B2_go2_contact_threshold_review",
        "candidate_thresholds": candidates,
        "recommended_candidate": "mode_gait_assisted_contact",
        "field_quality_status": distribution_report.get("field_quality_status", "unknown"),
        "threshold_source": "go2_field_distribution_only",
        "thresholds_are_diagnostic": True,
        "navigation_metric_tuning": False,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "go2_velocity_truth_claim": False,
        "go2_velocity_prior_enabled": False,
        "go2_yaw_prior_enabled": False,
        "paper_performance_claim": False,
        "fgo": False,
    }


def write_contact_threshold_review(distribution_report: dict[str, Any], output_dir: str | Path) -> tuple[Path, dict[str, Any]]:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    report = review_contact_thresholds(distribution_report)
    path = out / "GO2_CONTACT_THRESHOLD_REVIEW_REPORT.json"
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path, report
