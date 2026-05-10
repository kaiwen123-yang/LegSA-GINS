"""Evaluation-only N5D1 spike response checker for N6A.

中文说明：本模块读取 N5D1 spike report 作为事后 sentinel；spike 时间绝不进入
C++/Python source-aware 权重策略，也不作为调参门限。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .source_weight_trace import read_source_weight_trace


def _read_json(path: str | Path) -> dict[str, Any]:
    source = Path(path)
    if not source.exists():
        return {}
    return json.loads(source.read_text(encoding="utf-8"))


def find_n5d1_spike_report(n5d1_root: str | Path) -> Path | None:
    root = Path(n5d1_root)
    for name in ["RAW_DOPPLER_SPIKE_AUDIT_REPORT.json", "N5D1_VISUAL_DATA_COVERAGE_SPIKE_AUDIT_REPORT.json"]:
        path = root / name
        if path.exists():
            return path
    matches = sorted(root.rglob("RAW_DOPPLER_SPIKE_AUDIT_REPORT.json"))
    return matches[0] if matches else None


def _spike_epochs(report: dict[str, Any]) -> list[dict[str, Any]]:
    if "spike_epochs" in report:
        return [row for row in report.get("spike_epochs", []) if isinstance(row, dict)]
    nested = report.get("spike_audit", {})
    return [row for row in nested.get("spike_epochs", []) if isinstance(row, dict)] if isinstance(nested, dict) else []


def evaluate_spike_response(
    *,
    spike_report_path: str | Path | None,
    source_aware_trace_path: str | Path,
    tolerance_sec: float = 0.35,
) -> dict[str, Any]:
    spike_report = _read_json(spike_report_path) if spike_report_path else {}
    trace_rows = read_source_weight_trace(source_aware_trace_path)
    raw_rows = [row for row in trace_rows if row.get("source_id") == "raw_doppler_velocity"]
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
        responses.append(
            {
                "spike_time": spike_time,
                "nearest_trace_found": nearest is not None,
                "nearest_time": float(nearest["time"]) if nearest else None,
                "time_delta_sec": nearest_dt if nearest else None,
                "raw_doppler_combined_R_scale": float(nearest.get("combined_R_scale", 0.0)) if nearest else None,
                "raw_doppler_oim_R_scale": float(nearest.get("oim_R_scale", 0.0)) if nearest else None,
                "raw_doppler_lsim_R_scale": float(nearest.get("lsim_R_scale", 0.0)) if nearest else None,
                "reason_codes": nearest.get("reason_codes", "") if nearest else "",
            }
        )
    increased = [
        row
        for row in responses
        if row["nearest_trace_found"] and (row["raw_doppler_combined_R_scale"] or 0.0) > 1.0
    ]
    return {
        "stage": "N6A_source_aware_LSIM_OIM_weighting",
        "spike_report_found": bool(spike_report),
        "spike_report_path": str(spike_report_path) if spike_report_path else "",
        "source_aware_trace_path": str(source_aware_trace_path),
        "spike_count": len(_spike_epochs(spike_report)),
        "nearest_source_aware_trace_rows_found": len([row for row in responses if row["nearest_trace_found"]]),
        "responses": responses,
        "raw_doppler_R_scale_increased_near_spikes": len(increased) == len(responses) and bool(responses),
        "oim_response_status": "oim_or_combined_scale_increased" if increased else "missing_or_no_scale_increase",
        "evaluation_only_sentinel": True,
        "hardcoded_spike_time_weighting": False,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "paper_performance_claim": False,
    }


def write_spike_response_report(report: dict[str, Any], path: str | Path) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
