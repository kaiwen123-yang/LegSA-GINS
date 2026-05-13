"""N7B3 comparison for diagnostic Go2 contact model candidates.

中文说明：contact model comparison 只判断 physical plausibility 与 cross-source
velocity consistency，不把 Go2 contact/velocity 当 truth 或正式 solver result。
"""

from __future__ import annotations

import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any

from .go2_contact_state import _f, _time_value
from .go2_velocity_frame_review import transform_go2_velocity_for_frame
from .go2_velocity_quality import _nearest_from_index, _norm, _rmse


def _source_velocity(row: dict[str, Any] | None) -> list[float]:
    if not row:
        return [math.nan, math.nan, math.nan]
    return [_f(row.get(axis)) for axis in ("vn", "ve", "vd")]


def _candidate_by_model(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        out[str(row.get("candidate_model", "unknown"))].append(row)
    return {key: sorted(value, key=lambda row: _f(row.get("time"), 0.0)) for key, value in out.items()}


def _contact_conditioned_velocity_consistency(
    *,
    model_rows: list[dict[str, Any]],
    go2_rows: list[dict[str, Any]],
    receiver_rows: list[dict[str, Any]],
    raw_rows: list[dict[str, Any]],
    frame_name: str,
) -> dict[str, Any]:
    receiver_sorted = sorted(receiver_rows, key=lambda row: _f(row.get("time"), 0.0))
    raw_sorted = sorted(raw_rows, key=lambda row: _f(row.get("time"), 0.0))
    contact_sorted = sorted(model_rows, key=lambda row: _f(row.get("time"), 0.0))
    receiver_index = raw_index = contact_index = 0
    buckets: dict[str, dict[str, list[float]]] = defaultdict(lambda: {"receiver": [], "raw": []})
    for go2 in sorted(go2_rows, key=_time_value):
        time_value = _time_value(go2)
        contact, contact_index = _nearest_from_index(contact_sorted, time_value, contact_index, tolerance=0.10)
        if not contact:
            continue
        label = str(contact.get("contact_label", "unknown"))
        candidate = transform_go2_velocity_for_frame(go2, frame_name)
        if not all(math.isfinite(value) for value in candidate):
            continue
        receiver, receiver_index = _nearest_from_index(receiver_sorted, time_value, receiver_index, tolerance=0.55)
        raw, raw_index = _nearest_from_index(raw_sorted, time_value, raw_index, tolerance=0.55)
        for name, source in [("receiver", _source_velocity(receiver)), ("raw", _source_velocity(raw))]:
            diff = _norm([candidate[axis] - source[axis] for axis in range(3)])
            if math.isfinite(diff):
                buckets[label][name].append(diff)
    return {
        label: {
            "count_receiver": len(values["receiver"]),
            "count_raw": len(values["raw"]),
            "rmse_to_receiver": _rmse(values["receiver"]),
            "rmse_to_raw": _rmse(values["raw"]),
        }
        for label, values in sorted(buckets.items())
    }


def compare_contact_models(
    *,
    candidate_timeseries: list[dict[str, Any]],
    candidate_report: dict[str, Any],
    go2_rows: list[dict[str, Any]],
    receiver_velocity_rows: list[dict[str, Any]],
    raw_doppler_rows: list[dict[str, Any]],
    velocity_frame_report: dict[str, Any],
) -> dict[str, Any]:
    frame_name = str(velocity_frame_report.get("recommended_frame_for_diagnostic_prior") or "")
    by_model = _candidate_by_model(candidate_timeseries)
    reports = candidate_report.get("model_reports", {})
    comparison: dict[str, Any] = {}
    plausible_models: list[str] = []
    for model_id, rows in by_model.items():
        model_report = reports.get(model_id, {})
        consistency = _contact_conditioned_velocity_consistency(
            model_rows=rows,
            go2_rows=go2_rows,
            receiver_rows=receiver_velocity_rows,
            raw_rows=raw_doppler_rows,
            frame_name=frame_name,
        )
        physical = model_report.get("physical_plausibility_status", "unknown")
        plausible = bool(model_report.get("plausible_for_diagnostic", False))
        if plausible:
            plausible_models.append(model_id)
        comparison[model_id] = {
            "physical_plausibility_status": physical,
            "avoids_all_contact": float(model_report.get("all_contact_walking_ratio") or 0.0) <= 0.40,
            "avoids_all_uncertain": float(model_report.get("uncertain_ratio") or 1.0) <= 0.70,
            "alternating_ratio": model_report.get("alternating_ratio"),
            "contact_ratio": model_report.get("contact_ratio"),
            "swing_ratio": model_report.get("swing_ratio"),
            "uncertain_ratio": model_report.get("uncertain_ratio"),
            "contact_conditioned_velocity_consistency": consistency,
            "plausible_for_diagnostic": plausible,
        }
    selected = ""
    if plausible_models:
        selected = sorted(
            plausible_models,
            key=lambda model: (
                -(comparison[model].get("alternating_ratio") or 0.0),
                comparison[model].get("uncertain_ratio") or 1.0,
            ),
        )[0]
    return {
        "stage": "N7B3_go2_contact_velocity_diagnostic_activation",
        "candidate_models": sorted(by_model),
        "plausible_models": plausible_models,
        "selected_diagnostic_contact_model": selected,
        "contact_model_ready": bool(selected),
        "comparison_by_model": comparison,
        "selected_model_report": reports.get(selected, {}) if selected else {},
        "metric_namespace": "cross_source_consistency_not_truth_error",
        "diagnostic_only": True,
        "go2_velocity_truth_claim": False,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "paper_performance_claim": False,
        "fgo": False,
    }


def write_contact_model_comparison(
    *,
    candidate_timeseries: list[dict[str, Any]],
    candidate_report: dict[str, Any],
    go2_rows: list[dict[str, Any]],
    receiver_velocity_rows: list[dict[str, Any]],
    raw_doppler_rows: list[dict[str, Any]],
    velocity_frame_report: dict[str, Any],
    output_dir: str | Path,
) -> tuple[Path, dict[str, Any]]:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    report = compare_contact_models(
        candidate_timeseries=candidate_timeseries,
        candidate_report=candidate_report,
        go2_rows=go2_rows,
        receiver_velocity_rows=receiver_velocity_rows,
        raw_doppler_rows=raw_doppler_rows,
        velocity_frame_report=velocity_frame_report,
    )
    path = out / "GO2_CONTACT_MODEL_COMPARISON_REPORT.json"
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path, report
