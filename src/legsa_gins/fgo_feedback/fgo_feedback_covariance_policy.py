"""Conservative covariance proxy for N8G FGO feedback.

中文说明：N8G 协方差策略只保守放大 feedback R，不用 trace/final_v23 调权。
"""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

from .feedback_state_types import FeedbackObservation, stats


def apply_conservative_covariance_policy(
    observations: list[FeedbackObservation],
    *,
    residual_proxy_p95: float = 1.0,
    inflation_factor: float = 2.0,
    std_floor: dict[str, float] | None = None,
    std_cap: dict[str, float] | None = None,
) -> tuple[list[FeedbackObservation], dict[str, object]]:
    floor = {"p": 1.5, "v": 0.20, "att": 1.0, **(std_floor or {})}
    cap = {"p": 30.0, "v": 5.0, "att": 25.0, **(std_cap or {})}
    poor_window_extra = 1.0 + min(4.0, max(0.0, residual_proxy_p95) / 10.0)
    scale = max(1.0, inflation_factor) * poor_window_extra
    adjusted: list[FeedbackObservation] = []
    for obs in observations:
        adjusted.append(
            replace(
                obs,
                std_pN=min(cap["p"], max(floor["p"], obs.std_pN * scale)),
                std_pE=min(cap["p"], max(floor["p"], obs.std_pE * scale)),
                std_pD=min(cap["p"], max(floor["p"], obs.std_pD * scale)),
                std_vN=min(cap["v"], max(floor["v"], obs.std_vN * scale)),
                std_vE=min(cap["v"], max(floor["v"], obs.std_vE * scale)),
                std_vD=min(cap["v"], max(floor["v"], obs.std_vD * scale)),
                std_roll=min(cap["att"], max(floor["att"], obs.std_roll * scale)),
                std_pitch=min(cap["att"], max(floor["att"], obs.std_pitch * scale)),
                std_yaw=min(cap["att"], max(floor["att"], obs.std_yaw * scale)),
            )
        )
    report: dict[str, object] = {
        "stage": "N8G",
        "feedback_rows": len(adjusted),
        "covariance_source": "conservative_residual_proxy",
        "conservative_inflation_factor": scale,
        "no_R_shrink": True,
        "no_trace_tuning": True,
        "no_finalv23_tuning": True,
        "std_p_stats": stats([max(obs.std_pN, obs.std_pE, obs.std_pD) for obs in adjusted]),
        "std_v_stats": stats([max(obs.std_vN, obs.std_vE, obs.std_vD) for obs in adjusted]),
        "std_att_stats": stats([max(obs.std_roll, obs.std_pitch, obs.std_yaw) for obs in adjusted]),
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "paper_performance_claim": False,
    }
    return adjusted, report


def write_covariance_policy_report(path: str | Path, report: dict[str, object]) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
