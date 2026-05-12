"""N7B orchestration helpers for Go2 contact/velocity readiness.

中文说明：本模块只串联 readiness 报告写入，不改变 solver，不启用 Go2
velocity/yaw prior。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .go2_contact_state import write_contact_state_outputs
from .go2_motion_state import write_motion_state_outputs
from .go2_n7b_decision import make_n7b_decision, write_n7b_decision
from .go2_velocity_quality import write_velocity_quality_outputs
from .go2_yaw_rate_readiness import write_yaw_rate_readiness_outputs


def run_go2_contact_velocity_readiness(
    *,
    go2_rows: list[dict[str, Any]],
    receiver_velocity_rows: list[dict[str, Any]],
    raw_doppler_rows: list[dict[str, Any]],
    output_dir: str | Path,
    n7a_weak_prior_report: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Write N7B readiness reports without enabling any Go2 velocity/yaw prior."""

    out = Path(output_dir)
    contact_csv, contact_json, contact_rows, contact_report = write_contact_state_outputs(go2_rows, out)
    velocity_csv, velocity_json, velocity_rows, velocity_report = write_velocity_quality_outputs(
        go2_rows,
        out,
        receiver_velocity_rows=receiver_velocity_rows,
        raw_doppler_rows=raw_doppler_rows,
        contact_rows=contact_rows,
    )
    motion_csv, motion_json, motion_rows, motion_report = write_motion_state_outputs(go2_rows, out)
    yaw_csv, yaw_json, yaw_rows, yaw_report = write_yaw_rate_readiness_outputs(go2_rows, out)
    decision = make_n7b_decision(
        contact_report=contact_report,
        velocity_report=velocity_report,
        yaw_rate_report=yaw_report,
        motion_report=motion_report,
        n7a_weak_prior_report=n7a_weak_prior_report,
    )
    decision_path = write_n7b_decision(decision, out / "N7B_GO2_VELOCITY_CONTACT_DECISION_REPORT.json")
    return {
        "contact_csv": contact_csv,
        "contact_json": contact_json,
        "contact_rows": contact_rows,
        "contact_report": contact_report,
        "velocity_csv": velocity_csv,
        "velocity_json": velocity_json,
        "velocity_rows": velocity_rows,
        "velocity_report": velocity_report,
        "motion_csv": motion_csv,
        "motion_json": motion_json,
        "motion_rows": motion_rows,
        "motion_report": motion_report,
        "yaw_csv": yaw_csv,
        "yaw_json": yaw_json,
        "yaw_rows": yaw_rows,
        "yaw_report": yaw_report,
        "decision_path": decision_path,
        "decision": decision,
        "go2_velocity_prior_enabled": False,
        "go2_yaw_prior_enabled": False,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "paper_performance_claim": False,
    }
