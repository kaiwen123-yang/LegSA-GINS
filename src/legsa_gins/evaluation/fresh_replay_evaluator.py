"""Fresh N4H2 replay evaluation against reconstructed dual official reference.

中文说明：fresh evaluation 只重算 baseline replay diagnostic metrics；不修改
solver output，不使用 trace 作为 solver input，不删 epoch。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from legsa_gins.evaluation.official_case_review_reproduction import parse_kfgins_nav
from legsa_gins.evaluation.trajectory_metrics import align_by_timestamp, compute_errors, summary_metrics, write_error_series


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _as_nav_rows(value: str | Path | list[dict[str, Any]]) -> list[dict[str, Any]]:
    if isinstance(value, list):
        return value
    return parse_kfgins_nav(value)


def _add_gate_booleans(summary: dict[str, Any]) -> dict[str, Any]:
    horizontal = summary.get("horizontal_rmse_m")
    up = summary.get("up_rmse_m")
    yaw = summary.get("yaw_rmse_deg")
    roll = summary.get("roll_rmse_deg")
    pitch = summary.get("pitch_rmse_deg")
    summary.update(
        {
            "horizontal_gate_pass": isinstance(horizontal, (int, float)) and float(horizontal) <= 2.0,
            "up_gate_pass": isinstance(up, (int, float)) and float(up) <= 3.0,
            "yaw_gate_pass": isinstance(yaw, (int, float)) and float(yaw) <= 2.0,
            "roll_strict_gate_pass": isinstance(roll, (int, float)) and float(roll) <= 1.0,
            "pitch_strict_gate_pass": isinstance(pitch, (int, float)) and float(pitch) <= 1.0,
            "roll_relaxed_gate_pass": isinstance(roll, (int, float)) and float(roll) <= 1.6,
            "pitch_relaxed_gate_pass": isinstance(pitch, (int, float)) and float(pitch) <= 1.6,
            "trace_solver_input": False,
            "output_only_correction": False,
            "solver_output_changed": False,
            "bad_epoch_deletion_for_metric": False,
            "numerical_performance_claim": False,
        }
    )
    return summary


def evaluate_replay_against_official_reference(
    replay_nav: str | Path | list[dict[str, Any]],
    official_reference: list[dict[str, Any]],
    output_dir: str | Path,
) -> dict[str, Any]:
    """Evaluate replay NAV against the selected official reference."""

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    replay_rows = _as_nav_rows(replay_nav)
    aligned = align_by_timestamp(replay_rows, official_reference, max_dt=0.05)
    errors = compute_errors(aligned)
    summary = _add_gate_booleans(summary_metrics(errors))
    summary["aligned_count"] = summary.get("count")
    summary["reference_profile"] = "selected_dual_official_reference_direct_identity"
    report = {
        "phase": "N4H2D",
        "fresh_summary": summary,
        "count": summary.get("count"),
        "replay_nav_count": len(replay_rows),
        "official_reference_count": len(official_reference),
        "error_series_path": "FRESH_REPLAY_ERROR_SERIES.csv",
        "summary_path": "FRESH_REPLAY_SUMMARY.json",
        "yaw_profile": "direct_identity",
        "replay_recomputed_under_dual_reference": True,
        "trace_solver_input": False,
        "output_only_correction": False,
        "solver_output_changed": False,
        "bad_epoch_deletion_for_metric": False,
        "numerical_performance_claim": False,
    }
    write_error_series(errors, out / "FRESH_REPLAY_ERROR_SERIES.csv")
    _write_json(out / "FRESH_REPLAY_SUMMARY.json", summary)
    _write_json(out / "FRESH_REPLAY_EVALUATION_REPORT.json", report)
    return report


def compare_fresh_replay_to_dual_summary(
    fresh_summary: dict[str, Any],
    dual_official_summary: dict[str, Any],
) -> dict[str, Any]:
    """Compare fresh replay summary to the official dual summary envelope."""

    def diff(field: str) -> float | None:
        fresh = fresh_summary.get(field)
        official = dual_official_summary.get(field)
        if isinstance(fresh, (int, float)) and isinstance(official, (int, float)):
            return float(fresh) - float(official)
        return None

    horizontal_diff = diff("horizontal_rmse_m")
    up_diff = diff("up_rmse_m")
    yaw_diff = diff("yaw_rmse_deg")
    roll_diff = diff("roll_rmse_deg")
    pitch_diff = diff("pitch_rmse_deg")
    close = bool(
        isinstance(horizontal_diff, (int, float))
        and abs(horizontal_diff) <= 0.1
        and isinstance(up_diff, (int, float))
        and abs(up_diff) <= 0.1
        and isinstance(yaw_diff, (int, float))
        and abs(yaw_diff) <= 0.3
    )
    yaw = fresh_summary.get("yaw_rmse_deg")
    roll = fresh_summary.get("roll_rmse_deg")
    pitch = fresh_summary.get("pitch_rmse_deg")
    return {
        "phase": "N4H2D",
        "horizontal_diff": horizontal_diff,
        "up_diff": up_diff,
        "yaw_diff": yaw_diff,
        "roll_diff": roll_diff,
        "pitch_diff": pitch_diff,
        "fresh_replay_close_to_dual_final_v23": close,
        "yaw_gate_pass": isinstance(yaw, (int, float)) and float(yaw) <= 2.0,
        "dynamic_relaxed_attitude_gate_pass": bool(
            isinstance(roll, (int, float))
            and float(roll) <= 1.6
            and isinstance(pitch, (int, float))
            and float(pitch) <= 1.6
        ),
        "roll_strict_gate_pass": isinstance(roll, (int, float)) and float(roll) <= 1.0,
        "pitch_strict_gate_pass": isinstance(pitch, (int, float)) and float(pitch) <= 1.0,
        "formal_claim_allowed": False,
        "trace_solver_input": False,
        "output_only_correction": False,
        "solver_output_changed": False,
        "numerical_performance_claim": False,
    }
