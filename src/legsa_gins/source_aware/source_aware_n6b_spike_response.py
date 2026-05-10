"""Evaluation-only N6B spike response audit.

中文说明：N5D1 spike times are sentinels only; they are read after a run and
never enter the C++/Python source-aware policy.
"""

from __future__ import annotations

import json
from pathlib import Path
from statistics import median
from typing import Any

from .source_aware_spike_response import find_n5d1_spike_report
from .source_weight_trace import read_source_weight_trace


def _read_json(path: str | Path | None) -> dict[str, Any]:
    if not path:
        return {}
    source = Path(path)
    if not source.exists():
        return {}
    return json.loads(source.read_text(encoding="utf-8"))


def _spike_epochs(report: dict[str, Any]) -> list[dict[str, Any]]:
    if "spike_epochs" in report:
        return [row for row in report.get("spike_epochs", []) if isinstance(row, dict)]
    nested = report.get("spike_audit", {})
    return [row for row in nested.get("spike_epochs", []) if isinstance(row, dict)] if isinstance(nested, dict) else []


def evaluate_n6b_spike_response(
    *,
    spike_report_path: str | Path | None,
    source_aware_trace_path: str | Path,
    tolerance_sec: float = 0.35,
) -> dict[str, Any]:
    spike_report = _read_json(spike_report_path)
    trace_rows = read_source_weight_trace(source_aware_trace_path)
    raw_rows = [row for row in trace_rows if row.get("source_id") == "raw_doppler_velocity"]
    raw_scales = []
    for row in raw_rows:
        try:
            raw_scales.append(float(row.get("combined_R_scale", 1.0)))
        except (TypeError, ValueError):
            pass
    normal_median = float(median(raw_scales)) if raw_scales else 0.0
    responses: list[dict[str, Any]] = []
    for spike in _spike_epochs(spike_report):
        try:
            spike_time = float(spike.get("time"))
        except (TypeError, ValueError):
            continue
        nearest = None
        nearest_dt = tolerance_sec
        for row in raw_rows:
            try:
                row_time = float(row.get("time", "nan"))
            except ValueError:
                continue
            dt = abs(row_time - spike_time)
            if dt <= nearest_dt:
                nearest = row
                nearest_dt = dt
        combined = float(nearest.get("combined_R_scale", 0.0)) if nearest else None
        normalized = float(nearest.get("normalized_innovation", 0.0)) if nearest else None
        responses.append(
            {
                "spike_time": spike_time,
                "nearest_trace_found": nearest is not None,
                "nearest_time": float(nearest["time"]) if nearest else None,
                "time_delta_sec": nearest_dt if nearest else None,
                "raw_doppler_combined_R_scale": combined,
                "raw_doppler_oim_R_scale": float(nearest.get("oim_R_scale", 0.0)) if nearest else None,
                "raw_doppler_lsim_R_scale": float(nearest.get("lsim_R_scale", 0.0)) if nearest else None,
                "raw_doppler_normal_median_scale": normal_median,
                "spike_scale_to_median_ratio": (combined / normal_median) if combined is not None and normal_median > 0 else None,
                "oim_normalized_at_spike": normalized,
                "reason_codes": nearest.get("reason_codes", "") if nearest else "",
            }
        )
    found_count = len([row for row in responses if row["nearest_trace_found"]])
    ratios = [row["spike_scale_to_median_ratio"] for row in responses if isinstance(row.get("spike_scale_to_median_ratio"), (int, float))]
    if not spike_report or not responses or found_count == 0:
        status = "evidence_missing"
    elif any(ratio >= 2.0 for ratio in ratios):
        status = "increased_strongly"
    elif any(ratio > 1.10 for ratio in ratios):
        status = "increased_mildly"
    else:
        status = "no_response"
    return {
        "stage": "N6B_source_aware_policy_refinement",
        "spike_report_found": bool(spike_report),
        "spike_report_path": str(spike_report_path) if spike_report_path else "",
        "source_aware_trace_path": str(source_aware_trace_path),
        "spike_count": len(_spike_epochs(spike_report)),
        "nearest_rows_found": found_count,
        "nearest_source_aware_trace_rows_found": found_count,
        "raw_doppler_normal_median_scale": normal_median,
        "responses": responses,
        "response_status": status,
        "hardcoded_spike_time_weighting": False,
        "evaluation_only_sentinel": True,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "paper_performance_claim": False,
    }


def write_n6b_spike_response_report(report: dict[str, Any], path: str | Path) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
