"""Build N7B4 probability-weighted diagnostic Go2 velocity priors.

中文说明：输出 CSV 只允许 runtime-only diagnostic activation；Go2 velocity
不是 truth，contact probability 不是 truth label，不使用 trace/final_v23 调参。
"""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path
from typing import Any

from .go2_contact_state import _f, _time_value
from .go2_velocity_frame_internal_external_score import _candidate_velocity
from .go2_velocity_quality import _nearest_from_index


PRIOR_FIELDS = [
    "time",
    "vn",
    "ve",
    "vd",
    "std_vn",
    "std_ve",
    "std_vd",
    "source_status",
    "quality_flag",
    "contact_model",
    "contact_label",
    "frame_candidate",
    "prior_policy",
    "diagnostic_only",
    "go2_velocity_truth_claim",
]


def _base_std(frame_score_report: dict[str, Any]) -> float:
    best = str(frame_score_report.get("best_candidate") or "")
    metrics = frame_score_report.get("candidates", {}).get(best, {})
    external = metrics.get("external", {})
    values = [_f(external.get("rmse_to_receiver")), _f(external.get("rmse_to_raw"))]
    finite = [value for value in values if math.isfinite(value)]
    return max([2.0, *finite]) if finite else 2.0


def _selected_probability_rows(probability_timeseries: list[dict[str, Any]], model_id: str) -> list[dict[str, Any]]:
    return sorted(
        [row for row in probability_timeseries if row.get("model_id") == model_id],
        key=lambda row: _f(row.get("time"), 0.0),
    )


def _confidence_bucket(support_probability: float, confidence_score: float) -> str:
    if support_probability >= 0.62 and confidence_score >= 0.45:
        return "high"
    if support_probability >= 0.40 and confidence_score >= 0.25:
        return "medium"
    return "low"


def _std_for_bucket(base_std: float, bucket: str) -> float:
    if bucket == "high":
        return base_std
    if bucket == "medium":
        return base_std * 2.0
    return base_std * 5.0


def _contact_label(bucket: str, support_probability: float) -> str:
    if bucket == "high":
        return "probabilistic_high_support"
    if bucket == "medium":
        return "probabilistic_medium_support"
    if support_probability <= 0.25:
        return "probabilistic_low_support"
    return "probabilistic_low_confidence"


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=PRIOR_FIELDS)
        writer.writeheader()
        writer.writerows([{field: row.get(field, "") for field in PRIOR_FIELDS} for row in rows])


def _build_rows(
    *,
    go2_rows: list[dict[str, Any]],
    probability_rows: list[dict[str, Any]],
    frame_name: str,
    contact_model: str,
    base_std: float,
    policy: str,
    include_buckets: set[str],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    prob_index = 0
    for row in sorted(go2_rows, key=_time_value):
        time_value = _time_value(row)
        prob, prob_index = _nearest_from_index(probability_rows, time_value, prob_index, tolerance=0.10)
        if not prob:
            continue
        support = _f(prob.get("support_probability"))
        confidence = _f(prob.get("confidence_score"))
        bucket = _confidence_bucket(support, confidence)
        if bucket not in include_buckets:
            continue
        velocity = _candidate_velocity(row, frame_name)
        if not all(math.isfinite(value) for value in velocity):
            continue
        std = _std_for_bucket(base_std, bucket)
        rows.append(
            {
                "time": time_value,
                "vn": velocity[0],
                "ve": velocity[1],
                "vd": velocity[2],
                "std_vn": std,
                "std_ve": std,
                "std_vd": std,
                "source_status": "active",
                "quality_flag": f"diagnostic_probability_{bucket}_confidence",
                "contact_model": contact_model,
                "contact_label": _contact_label(bucket, support),
                "frame_candidate": frame_name,
                "prior_policy": policy,
                "diagnostic_only": True,
                "go2_velocity_truth_claim": False,
            }
        )
    return rows


def build_probability_weighted_diagnostic_priors(
    *,
    go2_rows: list[dict[str, Any]],
    frame_score_report: dict[str, Any],
    probability_model_report: dict[str, Any],
    probability_timeseries: list[dict[str, Any]],
    output_dir: str | Path,
) -> tuple[dict[str, Path], dict[str, Any]]:
    """Write N7B4 probability-weighted runtime prior CSVs."""

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    frame_status = str(frame_score_report.get("frame_status") or "")
    selected_frame = str(frame_score_report.get("selected_frame_for_diagnostic") or "")
    top2_frame = str(frame_score_report.get("top2_frame_for_diagnostic") or "")
    selected_model = str(probability_model_report.get("selected_contact_probability_model") or "")
    model_ready = bool(probability_model_report.get("contact_probability_model_ready", False))
    allowed = model_ready and bool(selected_frame) and frame_status in {"resolved_for_diagnostic", "ambiguous_but_testable"}
    base_std = _base_std(frame_score_report)
    prob_rows = _selected_probability_rows(probability_timeseries, selected_model)
    weighted: list[dict[str, Any]] = []
    high_only: list[dict[str, Any]] = []
    low_weight_all: list[dict[str, Any]] = []
    top2: list[dict[str, Any]] = []
    if allowed:
        weighted = _build_rows(
            go2_rows=go2_rows,
            probability_rows=prob_rows,
            frame_name=selected_frame,
            contact_model=selected_model,
            base_std=base_std,
            policy="probability_weighted_go2_velocity_diagnostic",
            include_buckets={"high", "medium", "low"},
        )
        high_only = _build_rows(
            go2_rows=go2_rows,
            probability_rows=prob_rows,
            frame_name=selected_frame,
            contact_model=selected_model,
            base_std=base_std,
            policy="high_confidence_only_go2_velocity_diagnostic",
            include_buckets={"high"},
        )
        low_weight_all = _build_rows(
            go2_rows=go2_rows,
            probability_rows=prob_rows,
            frame_name=selected_frame,
            contact_model=selected_model,
            base_std=base_std,
            policy="low_weight_all_epochs_go2_velocity_diagnostic",
            include_buckets={"high", "medium", "low"},
        )
        if top2_frame:
            top2 = _build_rows(
                go2_rows=go2_rows,
                probability_rows=prob_rows,
                frame_name=top2_frame,
                contact_model=selected_model,
                base_std=base_std,
                policy="top2_frame_probability_weighted_diagnostic",
                include_buckets={"high", "medium", "low"},
            )
    paths = {
        "probability_weighted": out / "GO2_VELOCITY_PROBABILITY_WEIGHTED_PRIORS_DIAGNOSTIC.csv",
        "high_confidence_only": out / "GO2_VELOCITY_HIGH_CONFIDENCE_PRIORS_DIAGNOSTIC.csv",
        "low_weight_all_epochs": out / "GO2_VELOCITY_LOW_WEIGHT_ALL_EPOCHS_PRIORS_DIAGNOSTIC.csv",
        "top2_frame_probability_weighted": out / "GO2_VELOCITY_TOP2_FRAME_PROBABILITY_WEIGHTED_PRIORS_DIAGNOSTIC.csv",
    }
    for key, rows in [
        ("probability_weighted", weighted),
        ("high_confidence_only", high_only),
        ("low_weight_all_epochs", low_weight_all),
        ("top2_frame_probability_weighted", top2),
    ]:
        _write_csv(paths[key], rows)
    buckets = {"high": 0, "medium": 0, "low": 0}
    for row in weighted:
        quality = str(row.get("quality_flag", ""))
        if "_high_" in quality:
            buckets["high"] += 1
        elif "_medium_" in quality:
            buckets["medium"] += 1
        else:
            buckets["low"] += 1
    report = {
        "stage": "N7B4_literature_informed_contact_velocity",
        "csv_generated": bool(weighted),
        "epoch_count": len(weighted),
        "high_confidence_count": buckets["high"],
        "medium_confidence_count": buckets["medium"],
        "low_confidence_count": buckets["low"],
        "high_confidence_only_epoch_count": len(high_only),
        "low_weight_all_epoch_count": len(low_weight_all),
        "top2_frame_epoch_count": len(top2),
        "std_policy": {
            "base_std_mps": base_std,
            "high_confidence": "base_std",
            "medium_confidence": "base_std*2",
            "low_confidence": "base_std*5",
            "base_rule": "max(2.0, receiver/raw cross-source RMSE)",
        },
        "selected_frame": selected_frame,
        "top2_frame": top2_frame,
        "frame_status": frame_status,
        "selected_contact_probability_model": selected_model,
        "activation_allowed_for_diagnostic": allowed,
        "formal_activation_allowed": False,
        "activation_blockers": [] if allowed else ["contact_probability_or_velocity_frame_not_ready"],
        "prior_csv_paths": {key: path.name for key, path in paths.items()},
        "diagnostic_only": True,
        "go2_velocity_truth_claim": False,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "paper_performance_claim": False,
        "fgo": False,
    }
    (out / "GO2_PROBABILITY_WEIGHTED_PRIOR_BUILD_REPORT.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return paths, report
