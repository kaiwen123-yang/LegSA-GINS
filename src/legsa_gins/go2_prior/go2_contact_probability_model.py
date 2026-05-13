"""N7B4 probabilistic Go2 contact model candidates.

中文说明：contact probability 只来自 Go2 fields 和 cross-source consistency
诊断，不使用 trace/final_v23 output 调阈值；概率不是 contact truth。
"""

from __future__ import annotations

import csv
import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any

from .go2_contact_state import _f


MODEL_IDS = [
    "force_probability",
    "speed_probability",
    "force_speed_fused_probability",
    "gait_mode_windowed_probability",
    "physical_plausibility_probability",
    "ensemble_probability",
]

TIMESERIES_FIELDS = [
    "time",
    "model_id",
    "foot_0_contact_probability",
    "foot_1_contact_probability",
    "foot_2_contact_probability",
    "foot_3_contact_probability",
    "support_probability",
    "swing_probability",
    "uncertainty_probability",
    "confidence_score",
    "hard_contact_count",
    "alternating_contact_hint",
    "all_contact_penalty",
    "all_uncertain_penalty",
    "mode",
    "gait_type",
    "body_velocity_norm",
    "trace_solver_input",
    "final_v23_output_solver_input",
    "diagnostic_only",
]


def _clamp01(value: float) -> float:
    if not math.isfinite(value):
        return 0.0
    return max(0.0, min(1.0, value))


def _smooth(values: list[float], index: int, *, half_window: int = 2) -> float:
    start = max(0, index - half_window)
    end = min(len(values), index + half_window + 1)
    subset = [value for value in values[start:end] if math.isfinite(value)]
    return sum(subset) / len(subset) if subset else 0.0


def _group_features(feature_rows: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    grouped: dict[float, list[dict[str, Any]]] = defaultdict(list)
    for row in feature_rows:
        grouped[_f(row.get("time"), 0.0)].append(row)
    out: list[list[dict[str, Any]]] = []
    for _time, rows in sorted(grouped.items()):
        by_foot = {int(_f(row.get("foot"), 0.0)): row for row in rows}
        if len(by_foot) == 4:
            out.append([by_foot[foot] for foot in range(4)])
    return out


def _standing_like(row: dict[str, Any]) -> bool:
    mode = str(row.get("mode", "")).lower()
    gait = str(row.get("gait_type", "")).lower()
    body_speed = _f(row.get("body_velocity_norm"))
    return "stand" in mode or "idle" in mode or "stand" in gait or (math.isfinite(body_speed) and body_speed < 0.12)


def _walking_like(row: dict[str, Any]) -> bool:
    mode = str(row.get("mode", "")).lower()
    gait = str(row.get("gait_type", "")).lower()
    body_speed = _f(row.get("body_velocity_norm"))
    return "walk" in mode or "trot" in gait or "run" in gait or (math.isfinite(body_speed) and body_speed >= 0.25)


def _probabilities_for_model(group: list[dict[str, Any]], model_id: str) -> list[float]:
    probs: list[float] = []
    standing = _standing_like(group[0])
    walking = _walking_like(group[0])
    for row in group:
        force_p = _clamp01(_f(row.get("normalized_foot_force")))
        speed_p = _clamp01(_f(row.get("normalized_inverse_foot_speed")))
        if model_id == "force_probability":
            prob = force_p
        elif model_id == "speed_probability":
            prob = speed_p
        elif model_id == "force_speed_fused_probability":
            prob = 0.55 * force_p + 0.45 * speed_p
        elif model_id == "gait_mode_windowed_probability":
            mode_boost = 0.12 if standing else (0.04 if walking else 0.0)
            prob = 0.45 * force_p + 0.40 * speed_p + mode_boost
        elif model_id == "physical_plausibility_probability":
            prob = 0.50 * force_p + 0.35 * speed_p
            if walking and speed_p > 0.70 and force_p < 0.25:
                prob -= 0.20
            if standing:
                prob += 0.10
        else:
            prob = 0.50 * force_p + 0.30 * speed_p + (0.10 if standing else 0.04 if walking else 0.0)
        probs.append(_clamp01(prob))
    return probs


def _row_summary(group: list[dict[str, Any]], model_id: str, probs: list[float]) -> dict[str, Any]:
    support = sum(probs) / 4.0
    hard = [prob >= 0.55 for prob in probs]
    count = sum(1 for item in hard if item)
    left = int(hard[0]) + int(hard[2])
    right = int(hard[1]) + int(hard[3])
    standing = _standing_like(group[0])
    walking = _walking_like(group[0])
    uncertainty = 1.0 - abs(support - 0.5) * 2.0
    all_contact_penalty = 1.0 if walking and count == 4 else 0.0
    all_uncertain_penalty = 1.0 if all(0.35 <= prob <= 0.65 for prob in probs) else 0.0
    diagonal_pair = (hard[0] and hard[3] and not hard[1] and not hard[2]) or (hard[1] and hard[2] and not hard[0] and not hard[3])
    lateral_imbalance = left != right
    alternating = 1.0 if walking and 1 <= count <= 3 and (lateral_imbalance or diagonal_pair) else 0.0
    confidence = _clamp01((sum(abs(prob - 0.5) for prob in probs) / 2.0) + 0.15 * alternating - 0.20 * all_contact_penalty)
    return {
        "time": _f(group[0].get("time"), 0.0),
        "model_id": model_id,
        "foot_0_contact_probability": probs[0],
        "foot_1_contact_probability": probs[1],
        "foot_2_contact_probability": probs[2],
        "foot_3_contact_probability": probs[3],
        "support_probability": support,
        "swing_probability": 1.0 - support,
        "uncertainty_probability": _clamp01(uncertainty),
        "confidence_score": confidence,
        "hard_contact_count": count,
        "alternating_contact_hint": alternating,
        "all_contact_penalty": all_contact_penalty,
        "all_uncertain_penalty": all_uncertain_penalty,
        "mode": group[0].get("mode", ""),
        "gait_type": group[0].get("gait_type", ""),
        "body_velocity_norm": group[0].get("body_velocity_norm", ""),
        "standing_like": standing,
        "walking_like": walking,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "diagnostic_only": True,
    }


def _score_model(rows: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(rows)
    if not total:
        return {"plausible_for_diagnostic": False, "selection_score": -999.0}
    support_values = [_f(row.get("support_probability")) for row in rows]
    uncertainty_values = [_f(row.get("uncertainty_probability")) for row in rows]
    confidence_values = [_f(row.get("confidence_score")) for row in rows]
    walking_rows = [row for row in rows if bool(row.get("walking_like"))]
    alternating = sum(_f(row.get("alternating_contact_hint")) for row in walking_rows) / len(walking_rows) if walking_rows else 0.0
    all_contact_penalty = sum(_f(row.get("all_contact_penalty")) for row in rows) / total
    all_uncertain_penalty = sum(_f(row.get("all_uncertain_penalty")) for row in rows) / total
    support_mean = sum(support_values) / total
    uncertainty_mean = sum(uncertainty_values) / total
    confidence_mean = sum(confidence_values) / total
    mode_consistency = 1.0 - min(1.0, abs(support_mean - 0.50) * 0.5 + all_contact_penalty)
    contact_conditioned_velocity_consistency = 1.0 - min(1.0, all_contact_penalty + 0.5 * all_uncertain_penalty)
    selection_score = (
        0.35 * confidence_mean
        + 0.25 * alternating
        + 0.20 * mode_consistency
        + 0.20 * contact_conditioned_velocity_consistency
        - 0.45 * all_contact_penalty
        - 0.30 * all_uncertain_penalty
    )
    plausible = bool(
        0.08 <= support_mean <= 0.92
        and uncertainty_mean <= 0.85
        and all_contact_penalty <= 0.50
        and all_uncertain_penalty <= 0.65
        and (not walking_rows or alternating >= 0.10)
    )
    return {
        "row_count": total,
        "support_probability_mean": support_mean,
        "uncertainty_probability_mean": uncertainty_mean,
        "confidence_score_mean": confidence_mean,
        "alternating_score": alternating,
        "all_contact_penalty": all_contact_penalty,
        "all_uncertain_penalty": all_uncertain_penalty,
        "mode_gait_consistency_score": mode_consistency,
        "contact_conditioned_velocity_consistency_score": contact_conditioned_velocity_consistency,
        "selection_score": selection_score,
        "plausible_for_diagnostic": plausible,
    }


def build_contact_probability_models(feature_rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Build probability model time series and select a diagnostic candidate."""

    groups = _group_features(feature_rows)
    raw_by_model: dict[str, list[dict[str, Any]]] = {model_id: [] for model_id in MODEL_IDS}
    for model_id in MODEL_IDS:
        per_foot_series: dict[int, list[float]] = {foot: [] for foot in range(4)}
        rough_probs_by_group: list[list[float]] = []
        for group in groups:
            probs = _probabilities_for_model(group, model_id)
            rough_probs_by_group.append(probs)
            for foot, prob in enumerate(probs):
                per_foot_series[foot].append(prob)
        for index, group in enumerate(groups):
            probs = rough_probs_by_group[index]
            if model_id in {"gait_mode_windowed_probability", "physical_plausibility_probability", "ensemble_probability"}:
                probs = [_smooth(per_foot_series[foot], index) for foot in range(4)]
            raw_by_model[model_id].append(_row_summary(group, model_id, probs))
    reports = {model_id: _score_model(rows) for model_id, rows in raw_by_model.items()}
    ranked = sorted(MODEL_IDS, key=lambda model_id: reports[model_id].get("selection_score", -999.0), reverse=True)
    plausible = [model_id for model_id in ranked if reports[model_id].get("plausible_for_diagnostic")]
    multi_signal_plausible = [
        model_id
        for model_id in plausible
        if model_id not in {"force_probability", "speed_probability"}
    ]
    selected = multi_signal_plausible[0] if multi_signal_plausible else (plausible[0] if plausible else (ranked[0] if ranked else ""))
    all_rows = [row for model_id in MODEL_IDS for row in raw_by_model[model_id]]
    report = {
        "stage": "N7B4_literature_informed_contact_velocity",
        "candidate_probability_models": MODEL_IDS,
        "candidate_count": len(MODEL_IDS),
        "model_reports": reports,
        "plausible_probability_models": plausible,
        "selected_contact_probability_model": selected,
        "contact_probability_model_ready": bool(plausible),
        "selection_policy": "prefer_multi_signal_probability_after_plausibility_screen; not_all_contact+not_all_uncertain+alternating+mode_gait+contact_conditioned_velocity_consistency",
        "metric_namespace": "diagnostic_contact_probability_not_truth_label",
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "trace_tuning": False,
        "final_v23_tuning": False,
        "go2_velocity_truth_claim": False,
        "diagnostic_only": True,
        "paper_performance_claim": False,
        "fgo": False,
    }
    return all_rows, report


def write_contact_probability_outputs(feature_rows: list[dict[str, Any]], output_dir: str | Path) -> tuple[Path, Path, list[dict[str, Any]], dict[str, Any]]:
    """Write probability time series and report."""

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    rows, report = build_contact_probability_models(feature_rows)
    csv_path = out / "GO2_CONTACT_PROBABILITY_TIMESERIES.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=TIMESERIES_FIELDS)
        writer.writeheader()
        writer.writerows([{field: row.get(field, "") for field in TIMESERIES_FIELDS} for row in rows])
    report_path = out / "GO2_CONTACT_PROBABILITY_MODEL_REPORT.json"
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return csv_path, report_path, rows, report
