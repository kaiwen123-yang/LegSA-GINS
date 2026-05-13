"""N7C5 visual plots for full Go2 proprioceptive factor mining.

中文说明：图像只写入 runtime figure 目录，不提交到仓库。
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any


REQUIRED_N7C5_FIGURES = [
    "go2_field_inventory_summary.png",
    "contact_probability_by_foot.png",
    "foot_kinematic_velocity_vs_go2_velocity.png",
    "foot_kinematic_velocity_vs_receiver_raw.png",
    "foot_kinematic_velocity_residual_norm.png",
    "mode_gait_phase_timeline.png",
    "yawrate_consistency.png",
    "relative_odometry_delta_consistency.png",
    "factor_ranking_bar.png",
    "n7c5_decision_panel.png",
]


def _load_matplotlib():
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    return plt


def _f(value: Any, fallback: float = 0.0) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return fallback
    return out if math.isfinite(out) else fallback


def _times(rows: list[dict[str, Any]]) -> list[float]:
    if not rows:
        return []
    t0 = _f(rows[0].get("time"), 0.0)
    return [_f(row.get("time"), t0) - t0 for row in rows]


def _values(rows: list[dict[str, Any]], key: str) -> list[float]:
    return [_f(row.get(key), 0.0) for row in rows]


def _axis(plt, figsize: tuple[float, float] = (9.4, 5.1)):
    fig = plt.figure(figsize=figsize)
    ax = fig.add_axes([0.12, 0.16, 0.82, 0.74])
    return fig, ax


def _save(fig, path: Path, plt) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=150)
    plt.close(fig)


def _nonempty(path: Path) -> bool:
    return path.exists() and path.stat().st_size > 0


def generate_n7c5_visual_plots(
    *,
    figure_output_dir: str | Path,
    inventory_report: dict[str, Any],
    contact_rows: list[dict[str, Any]],
    foot_rows: list[dict[str, Any]],
    phase_rows: list[dict[str, Any]],
    yawrate_report: dict[str, Any],
    relative_report: dict[str, Any],
    ranking_report: dict[str, Any],
    decision: dict[str, Any],
) -> dict[str, Any]:
    plt = _load_matplotlib()
    root = Path(figure_output_dir)
    generated: list[dict[str, Any]] = []

    rel = REQUIRED_N7C5_FIGURES[0]
    fig, ax = _axis(plt)
    groups = list(inventory_report.get("fields", {}).keys())
    ratios = [_f(inventory_report.get("fields", {}).get(group, {}).get("finite_ratio"), 0.0) for group in groups]
    ax.bar(groups, ratios)
    ax.set_title("N7C5 Go2 field finite-ratio inventory")
    ax.set_ylabel("finite ratio")
    ax.tick_params(axis="x", labelrotation=35)
    ax.grid(True, axis="y", linewidth=0.3, alpha=0.45)
    _save(fig, root / rel, plt)
    generated.append({"figure_name": rel, "source_rows": len(groups)})

    rel = REQUIRED_N7C5_FIGURES[1]
    fig, ax = _axis(plt)
    t = _times(contact_rows)
    for foot in range(4):
        ax.plot(t, _values(contact_rows, f"foot_{foot}_contact_probability"), label=f"foot {foot}", linewidth=0.8)
    ax.plot(t, _values(contact_rows, "support_probability"), label="support", linewidth=1.1, color="#111111")
    ax.set_title("N7C5 contact probability by foot")
    ax.set_xlabel("time since start (s)")
    ax.set_ylabel("probability")
    ax.grid(True, linewidth=0.3, alpha=0.45)
    ax.legend(loc="best", fontsize=8)
    _save(fig, root / rel, plt)
    generated.append({"figure_name": rel, "source_rows": len(contact_rows)})

    rel = REQUIRED_N7C5_FIGURES[2]
    fig, ax = _axis(plt)
    ft = _times(foot_rows)
    ax.plot(ft, _values(foot_rows, "candidate_vn"), label="foot candidate vn", linewidth=0.8)
    ax.plot(ft, _values(foot_rows, "go2_vn"), label="Go2 velocity vn", linewidth=0.8, linestyle="--")
    ax.set_title("N7C5 foot kinematic velocity vs Go2 velocity")
    ax.set_xlabel("time since start (s)")
    ax.set_ylabel("vn (m/s)")
    ax.grid(True, linewidth=0.3, alpha=0.45)
    ax.legend(loc="best", fontsize=8)
    _save(fig, root / rel, plt)
    generated.append({"figure_name": rel, "source_rows": len(foot_rows)})

    rel = REQUIRED_N7C5_FIGURES[3]
    fig, ax = _axis(plt)
    ax.plot(ft, _values(foot_rows, "candidate_vn"), label="foot candidate vn", linewidth=0.8)
    ax.plot(ft, _values(foot_rows, "receiver_vn"), label="receiver vn", linewidth=0.8, linestyle="--")
    ax.plot(ft, _values(foot_rows, "raw_vn"), label="raw Doppler vn", linewidth=0.8, linestyle=":")
    ax.set_title("N7C5 foot kinematic velocity vs receiver/raw")
    ax.set_xlabel("time since start (s)")
    ax.set_ylabel("vn (m/s)")
    ax.grid(True, linewidth=0.3, alpha=0.45)
    ax.legend(loc="best", fontsize=8)
    _save(fig, root / rel, plt)
    generated.append({"figure_name": rel, "source_rows": len(foot_rows)})

    rel = REQUIRED_N7C5_FIGURES[4]
    fig, ax = _axis(plt)
    ax.plot(ft, _values(foot_rows, "residual_to_receiver"), label="to receiver", linewidth=0.8)
    ax.plot(ft, _values(foot_rows, "residual_to_raw"), label="to raw", linewidth=0.8, linestyle="--")
    ax.plot(ft, _values(foot_rows, "residual_to_go2"), label="to Go2 velocity", linewidth=0.8, linestyle=":")
    ax.set_title("N7C5 foot kinematic residual norm")
    ax.set_xlabel("time since start (s)")
    ax.set_ylabel("horizontal residual (m/s)")
    ax.grid(True, linewidth=0.3, alpha=0.45)
    ax.legend(loc="best", fontsize=8)
    _save(fig, root / rel, plt)
    generated.append({"figure_name": rel, "source_rows": len(foot_rows)})

    rel = REQUIRED_N7C5_FIGURES[5]
    fig, ax = _axis(plt)
    phase_map = {"standing": 0, "walking": 1, "turning": 2, "transition": 3, "uncertain": 4}
    ax.step(_times(phase_rows), [phase_map.get(str(row.get("phase")), 4) for row in phase_rows], where="post", linewidth=0.8)
    ax.set_yticks(list(phase_map.values()))
    ax.set_yticklabels(list(phase_map.keys()))
    ax.set_title("N7C5 mode/gait phase timeline")
    ax.set_xlabel("time since start (s)")
    ax.grid(True, linewidth=0.3, alpha=0.45)
    _save(fig, root / rel, plt)
    generated.append({"figure_name": rel, "source_rows": len(phase_rows)})

    rel = REQUIRED_N7C5_FIGURES[6]
    fig, ax = _axis(plt)
    ax.bar(["yaw-vs-dyaw", "yaw-vs-gyro"], [_f(yawrate_report.get("yaw_speed_vs_yaw_derivative_rmse_radps"), 0.0), _f(yawrate_report.get("yaw_speed_vs_gyro_z_rmse_radps"), 0.0)])
    ax.set_title("N7C5 yaw-rate consistency")
    ax.set_ylabel("RMSE (rad/s)")
    ax.grid(True, axis="y", linewidth=0.3, alpha=0.45)
    _save(fig, root / rel, plt)
    generated.append({"figure_name": rel, "source_rows": 2})

    rel = REQUIRED_N7C5_FIGURES[7]
    fig, ax = _axis(plt)
    ax.bar(["pos delta", "vel integral", "consistency err"], [_f(relative_report.get("go2_position_delta_rmse_m"), 0.0), _f(relative_report.get("integrated_go2_velocity_delta_rmse_m"), 0.0), _f(relative_report.get("position_vs_integrated_velocity_error_rmse_m"), 0.0)])
    ax.set_title("N7C5 relative odometry delta consistency")
    ax.set_ylabel("RMSE / norm (m)")
    ax.grid(True, axis="y", linewidth=0.3, alpha=0.45)
    _save(fig, root / rel, plt)
    generated.append({"figure_name": rel, "source_rows": 3})

    rel = REQUIRED_N7C5_FIGURES[8]
    fig, ax = _axis(plt)
    candidates = ranking_report.get("candidates", [])
    ax.barh([row.get("factor_id", "") for row in candidates], [_f(row.get("score"), 0.0) for row in candidates])
    ax.set_title("N7C5 factor ranking")
    ax.set_xlabel("score")
    ax.grid(True, axis="x", linewidth=0.3, alpha=0.45)
    _save(fig, root / rel, plt)
    generated.append({"figure_name": rel, "source_rows": len(candidates)})

    rel = REQUIRED_N7C5_FIGURES[9]
    fig, ax = _axis(plt)
    ax.axis("off")
    lines = [
        "N7C5 Go2 proprioceptive factor mining",
        f"status: {decision.get('status')}",
        f"next: {decision.get('recommended_next_stage')}",
        f"EKF candidate: {decision.get('recommended_EKF_next_factor')}",
        f"foot candidate: {decision.get('foot_kinematic_activation_candidate')}",
        f"yawrate: {decision.get('yawrate_stability_status')}",
        f"relative odom: {decision.get('relative_odometry_stability')}",
        "Go2 fields are not truth; no trace/final_v23 tuning; no paper claim.",
    ]
    ax.text(0.02, 0.95, "\n".join(lines), va="top", ha="left", family="monospace", fontsize=9)
    ax.set_title("N7C5 decision panel")
    _save(fig, root / rel, plt)
    generated.append({"figure_name": rel, "source_rows": 1})

    paths = [root / name for name in REQUIRED_N7C5_FIGURES]
    return {
        "stage": "N7C5_go2_full_proprioceptive_factor_mining",
        "figure_count_total": len(REQUIRED_N7C5_FIGURES),
        "required_figure_count": len(REQUIRED_N7C5_FIGURES),
        "required_figures": list(REQUIRED_N7C5_FIGURES),
        "generated_figures": generated,
        "required_figures_generated": all(path.exists() for path in paths),
        "required_figures_nonempty": all(_nonempty(path) for path in paths),
        "figure_role_alias": "N7C5_FIGURE_OUTPUT_DIR",
        "paper_performance_claim": False,
        "go2_not_truth": True,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "fgo": False,
    }
