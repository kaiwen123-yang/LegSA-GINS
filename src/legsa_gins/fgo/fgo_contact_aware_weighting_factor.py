"""N8F contact-aware weighting layer for no-feedback FGO.

该模块只生成权重缩放，不生成状态残差。contact probability 是足式本体
观测的置信度输入，不是接触真值，也不作为 hard contact truth 使用。
"""

from __future__ import annotations

import csv
import json
import math
import statistics
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Sequence


USED_BY_FACTORS = [
    "FootKinematicVelocityFactor",
    "Go2HorizontalVelocityComponent",
    "RelativeOdometryBetweenFactor",
    "Go2ProprioceptiveJointFactorOptionalScaling",
]


@dataclass(frozen=True)
class ContactAwareWeightRow:
    """单 epoch 的 contact-aware R scale。"""

    time: float
    contact_weight_scale: float
    support_confidence: float
    slip_risk: float
    uncertainty: float
    mode: str = ""
    gait_phase: str = ""


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def finite_float(value: object, default: float = 0.0) -> float:
    try:
        out = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default
    if not math.isfinite(out):
        return default
    return out


def read_csv_dicts(path: Path) -> List[Dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", newline="") as handle:
        return list(csv.DictReader(handle))


def write_contact_weight_timeseries(path: Path, rows: Sequence[ContactAwareWeightRow]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "time",
                "contact_weight_scale",
                "support_confidence",
                "slip_risk",
                "uncertainty",
                "mode",
                "gait_phase",
            ],
        )
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "time": f"{row.time:.9f}",
                    "contact_weight_scale": f"{row.contact_weight_scale:.9f}",
                    "support_confidence": f"{row.support_confidence:.9f}",
                    "slip_risk": f"{row.slip_risk:.9f}",
                    "uncertainty": f"{row.uncertainty:.9f}",
                    "mode": row.mode,
                    "gait_phase": row.gait_phase,
                }
            )


def _nearest_by_time(rows: Sequence[Mapping[str, str]], time_value: float) -> Mapping[str, str]:
    if not rows:
        return {}
    best = min(rows, key=lambda row: abs(finite_float(row.get("time"), time_value) - time_value))
    return best


def _percentile(values: Sequence[float], q: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = int(round((len(ordered) - 1) * q))
    return ordered[idx]


def compute_contact_scale(
    support_confidence: float,
    slip_risk: float,
    uncertainty: float,
    *,
    min_scale: float = 0.55,
    max_scale: float = 4.0,
) -> float:
    """Compute an R scale without using trace or final_v23 outputs."""

    support_confidence = clamp(support_confidence, 0.0, 1.0)
    slip_risk = clamp(slip_risk, 0.0, 1.0)
    uncertainty = clamp(uncertainty, 0.0, 1.0)

    # 高支撑、低打滑时略缩小 R；高不确定或高打滑时放大 R。
    scale = 1.0 + 1.35 * slip_risk + 0.85 * uncertainty - 0.45 * support_confidence
    return clamp(scale, min_scale, max_scale)


def build_contact_aware_weights(
    *,
    epoch_times: Sequence[float],
    mode_rows: Sequence[Mapping[str, str]],
    foot_rows: Sequence[Mapping[str, str]] | None = None,
) -> List[ContactAwareWeightRow]:
    """Build contact-aware weighting rows aligned to solver epochs."""

    foot_rows = foot_rows or []
    out: List[ContactAwareWeightRow] = []
    for idx, time_value in enumerate(epoch_times):
        mode_row = _nearest_by_time(mode_rows, time_value) if mode_rows else {}
        foot_row = _nearest_by_time(foot_rows, time_value) if foot_rows else {}
        if not mode_row and idx < len(foot_rows):
            foot_row = foot_rows[idx]

        support = finite_float(mode_row.get("support_probability"), 0.5)
        slip = finite_float(foot_row.get("slip_risk"), 1.0 - support)
        uncertainty = finite_float(mode_row.get("uncertainty"), 1.0 - support)
        scale = compute_contact_scale(support, slip, uncertainty)
        out.append(
            ContactAwareWeightRow(
                time=time_value,
                contact_weight_scale=scale,
                support_confidence=clamp(support, 0.0, 1.0),
                slip_risk=clamp(slip, 0.0, 1.0),
                uncertainty=clamp(uncertainty, 0.0, 1.0),
                mode=str(mode_row.get("mode", "")),
                gait_phase=str(mode_row.get("phase", mode_row.get("gait_type", ""))),
            )
        )
    return out


def summarize_contact_aware_weights(rows: Sequence[ContactAwareWeightRow]) -> Dict[str, object]:
    scales = [row.contact_weight_scale for row in rows if math.isfinite(row.contact_weight_scale)]
    finite_ratio = len(scales) / len(rows) if rows else 0.0
    return {
        "stage": "N8F",
        "factor_name": "ContactAwareWeightingLayer",
        "classification": "weighting_layer_no_direct_state_residual",
        "rows": len(rows),
        "finite_ratio": finite_ratio,
        "scale_p50": statistics.median(scales) if scales else 0.0,
        "scale_p95": _percentile(scales, 0.95),
        "scale_max": max(scales) if scales else 0.0,
        "support_confidence_mean": statistics.fmean(row.support_confidence for row in rows) if rows else 0.0,
        "slip_risk_mean": statistics.fmean(row.slip_risk for row in rows) if rows else 0.0,
        "hard_contact_truth": False,
        "direct_state_residual": False,
        "state_jacobian_nonzero_count": 0,
        "used_by_factor": list(USED_BY_FACTORS),
        "no_trace_tuning": True,
        "no_finalv23_tuning": True,
        "paper_performance_claim": False,
    }


def write_contact_aware_report(path: Path, report: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")

