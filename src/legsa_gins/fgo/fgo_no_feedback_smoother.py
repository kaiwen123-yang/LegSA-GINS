"""N8A no-feedback FGO smoother."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from legsa_gins.fgo.fgo_linear_solver import solve_no_feedback_linear_system
from legsa_gins.fgo.fgo_state_types import FGOStateDataset


def run_no_feedback_smoother(dataset: FGOStateDataset) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """中文说明：离线 smoother 输出只用于诊断，不回写 EKF，不替换 NAV。"""
    raw = [state.vector() for state in dataset.states]
    solved = solve_no_feedback_linear_system(raw, smoothness_weight=0.15)
    rows: list[dict[str, Any]] = []
    for state, vector in zip(dataset.states, solved.get("smoothed", [])):
        rows.append(
            {
                "index": state.index,
                "time": state.time,
                "lat_deg": vector[0],
                "lon_deg": vector[1],
                "height_m": vector[2],
                "roll_deg": vector[3],
                "pitch_deg": vector[4],
                "yaw_deg": vector[5],
                "vn_mps": vector[6],
                "ve_mps": vector[7],
                "vd_mps": vector[8],
            }
        )
    report = {
        "stage": "N8A_no_feedback_fgo_foundation",
        "solve_status": "solved" if solved.get("solved") and solved.get("finite_output") else "not_solved",
        "state_count": dataset.state_count,
        "output_state_count": len(rows),
        "residual_proxy_p95": solved.get("residual_proxy_p95", 0.0),
        "finite_output": bool(solved.get("finite_output", True)),
        "fixed_weights": True,
        "limited_iterations": True,
        "fgo_output_feedback_to_ekf": False,
        "fgo_output_replaces_ekf_nav": False,
        "output_only_correction": False,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "paper_performance_claim": False,
    }
    return rows, report


def write_smoother_outputs(csv_path: str | Path, report_path: str | Path, rows: list[dict[str, Any]], report: dict[str, Any]) -> None:
    csv_output = Path(csv_path)
    csv_output.parent.mkdir(parents=True, exist_ok=True)
    fields = list(rows[0]) if rows else ["index", "time"]
    with csv_output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    report_output = Path(report_path)
    report_output.parent.mkdir(parents=True, exist_ok=True)
    report_output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
