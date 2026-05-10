"""Diagnostics for N6B source-aware policy reports.

中文说明：这里只做报告门限判断，不修改 solver 或 runtime artifact。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


METRIC_KEYS = [
    "horizontal_rmse_m",
    "up_rmse_m",
    "yaw_rmse_deg",
    "roll_rmse_deg",
    "pitch_rmse_deg",
]

CLEAN_NEUTRALITY_GATES = {
    "horizontal_rmse_m": 0.10,
    "up_rmse_m": 0.20,
    "yaw_rmse_deg": 0.30,
    "roll_rmse_deg": 0.15,
    "pitch_rmse_deg": 0.15,
}

R_SCALE_GATES = {
    "receiver_position": {"p50": 2.0, "p95": 5.0},
    "receiver_velocity": {"p50": 3.0, "p95": 8.0},
    "raw_doppler_velocity": {"p50": 5.0, "p95": 15.0},
}


def metric_delta(candidate: dict[str, Any] | None, baseline: dict[str, Any] | None) -> dict[str, float | None]:
    out: dict[str, float | None] = {}
    for key in METRIC_KEYS:
        cand = (candidate or {}).get("summary", {}).get(key)
        base = (baseline or {}).get("summary", {}).get(key)
        out[key] = float(cand) - float(base) if isinstance(cand, (int, float)) and isinstance(base, (int, float)) else None
    return out


def clean_neutrality_gate(delta: dict[str, float | None]) -> dict[str, Any]:
    checks: dict[str, bool] = {}
    for key, limit in CLEAN_NEUTRALITY_GATES.items():
        value = delta.get(key)
        checks[key] = value is not None and value <= limit
    return {
        "gate_name": "N6B_clean_lsim_oim_minus_no_sourceaware",
        "pass": all(checks.values()) if checks else False,
        "checks": checks,
        "limits": CLEAN_NEUTRALITY_GATES,
        "delta": delta,
    }


def r_scale_gate(weight_stats: dict[str, Any]) -> dict[str, Any]:
    source_stats = weight_stats.get("stats_by_source", {})
    checks: dict[str, dict[str, bool]] = {}
    for source_id, limits in R_SCALE_GATES.items():
        row = source_stats.get(source_id, {})
        checks[source_id] = {
            "p50": float(row.get("R_scale_p50", 0.0) or 0.0) <= limits["p50"],
            "p95": float(row.get("R_scale_p95", 0.0) or 0.0) <= limits["p95"],
        }
    return {
        "gate_name": "N6B_R_scale_not_all_cap",
        "pass": all(all(inner.values()) for inner in checks.values()) if checks else False,
        "checks": checks,
        "limits": R_SCALE_GATES,
    }


def build_policy_diagnostics(
    *,
    weight_stats: dict[str, Any],
    comparison_report: dict[str, Any],
    spike_response: dict[str, Any],
) -> dict[str, Any]:
    main_stats = weight_stats.get("main_variant_stats", {})
    clean_delta = (
        comparison_report.get("comparisons", {})
        .get("n6b_lsim_oim_minus_no_sourceaware", {})
        .get("delta", {})
    )
    clean_gate = clean_neutrality_gate(clean_delta)
    scale_gate = r_scale_gate(main_stats)
    return {
        "stage": "N6B_source_aware_policy_refinement",
        "policy_version": "n6b_conservative_innovation_covariance",
        "clean_neutrality_gate": clean_gate,
        "R_scale_gate": scale_gate,
        "spike_response_status": spike_response.get("response_status", "evidence_missing"),
        "source_aware_trace_rows": main_stats.get("trace_row_count", 0),
        "paper_performance_claim": False,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "go2_prior": False,
        "fgo": False,
    }


def write_policy_diagnostics(report: dict[str, Any], path: str | Path) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
