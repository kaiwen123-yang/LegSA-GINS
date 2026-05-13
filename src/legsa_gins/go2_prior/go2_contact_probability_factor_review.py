"""N7C5 contact probability factor review.

中文说明：contact 在 N7C5 中作为概率/权重候选审查，不作为硬阈值 truth。
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any


def _f(value: Any, fallback: float = math.nan) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return fallback
    return out if math.isfinite(out) else fallback


def _mean(values: list[float]) -> float:
    finite = [value for value in values if math.isfinite(value)]
    return sum(finite) / len(finite) if finite else 0.0


def _p95(values: list[float]) -> float:
    finite = sorted(value for value in values if math.isfinite(value))
    return finite[int(0.95 * (len(finite) - 1))] if finite else 0.0


def build_go2_contact_probability_factor_review(rows: list[dict[str, Any]]) -> dict[str, Any]:
    foot_stats: dict[str, Any] = {}
    for foot in range(4):
        key = f"foot_{foot}_contact_probability"
        values = [_f(row.get(key), math.nan) for row in rows]
        foot_stats[key] = {"mean": _mean(values), "p95": _p95(values), "finite_ratio": sum(math.isfinite(v) for v in values) / len(rows) if rows else 0.0}
    support = [_f(row.get("support_probability"), math.nan) for row in rows]
    swing = [_f(row.get("swing_probability"), math.nan) for row in rows]
    uncertainty = [_f(row.get("uncertainty_probability"), math.nan) for row in rows]
    alternating = [_f(row.get("alternating_contact_hint"), 0.0) for row in rows]
    hard_counts = [_f(row.get("hard_contact_count"), math.nan) for row in rows]
    support_mean = _mean(support)
    uncertainty_mean = _mean(uncertainty)
    alternating_mean = _mean(alternating)
    hard_contact_mean = _mean(hard_counts)
    slip_risk_score = min(1.0, 0.55 * uncertainty_mean + 0.25 * max(0.0, 0.55 - support_mean) + 0.20 * (1.0 - alternating_mean))
    usable_as_weight = bool(rows) and support_mean > 0.20
    usable_as_factor = usable_as_weight and uncertainty_mean < 0.35 and alternating_mean > 0.35
    return {
        "stage": "N7C5_go2_full_proprioceptive_factor_mining",
        "row_count": len(rows),
        "foot_probability_stats": foot_stats,
        "support_probability_mean": support_mean,
        "swing_probability_mean": _mean(swing),
        "uncertainty_probability_mean": uncertainty_mean,
        "hard_contact_count_mean": hard_contact_mean,
        "alternating_pattern_mean": alternating_mean,
        "slip_risk_score": slip_risk_score,
        "mode_gait_consistency_status": "reviewed",
        "usable_as_weight": usable_as_weight,
        "usable_as_factor": usable_as_factor,
        "recommendation": "weighting_only_unless_stronger_contact_evidence" if not usable_as_factor else "factor_candidate_with_soft_probability",
        "contact_truth_claim": False,
        "no_hard_threshold_default": True,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "no_trace_tuning": True,
        "no_final_v23_tuning": True,
        "paper_performance_claim": False,
        "fgo": False,
    }


def write_go2_contact_probability_factor_review(path: str | Path, report: dict[str, Any]) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output
