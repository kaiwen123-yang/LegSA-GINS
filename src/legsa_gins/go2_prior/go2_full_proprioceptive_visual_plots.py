"""N7C5A visual plot generation for Go2 full proprioceptive mining review.

中文说明：所有图片只写 runtime figure dir；图像用于人工复核，不构成 paper claim。
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any


REQUIRED_N7C5A_FIGURES = [
    "01_field_inventory/go2_field_availability_summary.png",
    "01_field_inventory/go2_signal_rate_and_time_axis.png",
    "02_contact_probability/contact_probability_by_foot_time.png",
    "02_contact_probability/support_uncertainty_probability_time.png",
    "02_contact_probability/contact_probability_histogram.png",
    "03_foot_kinematic_velocity/foot_kinematic_velocity_vs_go2_velocity_components.png",
    "03_foot_kinematic_velocity/foot_kinematic_velocity_vs_receiver_velocity_components.png",
    "03_foot_kinematic_velocity/foot_kinematic_velocity_vs_raw_doppler_components.png",
    "03_foot_kinematic_velocity/foot_kinematic_velocity_residual_norm_time.png",
    "03_foot_kinematic_velocity/slip_risk_time.png",
    "04_mode_gait_yawrate/mode_gait_phase_timeline.png",
    "04_mode_gait_yawrate/yawrate_vs_go2_yaw_derivative.png",
    "04_mode_gait_yawrate/gyro_z_vs_yawrate.png",
    "05_relative_odometry/go2_relative_odometry_delta_time.png",
    "05_relative_odometry/relative_odometry_vs_integrated_velocity.png",
    "06_factor_ranking/factor_ranking_bar.png",
    "06_factor_ranking/factor_candidate_risk_vs_value_scatter.png",
    "07_summary/n7c5a_decision_panel.png",
]


def _plt():
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


def _axis(plt, figsize=(9.2, 5.0)):
    fig = plt.figure(figsize=figsize)
    ax = fig.add_axes([0.12, 0.16, 0.82, 0.74])
    return fig, ax


def _save(fig, path: Path, plt) -> dict[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=145)
    plt.close(fig)
    return {"figure_name": str(path.name), "relative_path": str(path), "nonempty": path.exists() and path.stat().st_size > 0}


def _sample(rows: list[dict[str, Any]], max_rows: int = 6000) -> list[dict[str, Any]]:
    if len(rows) <= max_rows:
        return rows
    stride = max(1, len(rows) // max_rows)
    return rows[::stride]


def generate_n7c5a_visual_review_plots(
    *,
    figure_output_dir: str | Path,
    inputs: dict[str, Any],
    decision_preview: dict[str, Any] | None = None,
) -> dict[str, Any]:
    plt = _plt()
    root = Path(figure_output_dir)
    generated: list[dict[str, Any]] = []
    inventory = inputs.get("inventory_report", {})
    contact_rows = _sample(inputs.get("contact_rows", []))
    foot_rows = _sample(inputs.get("foot_rows", []))
    phase_rows = _sample(inputs.get("phase_rows", []))
    yaw = inputs.get("yawrate_report", {})
    rel = inputs.get("relative_report", {})
    ranking = inputs.get("ranking_report", {})

    fields = inventory.get("fields", {})
    names = list(fields.keys())
    fig, ax = _axis(plt)
    ax.bar(names, [1.0 if fields.get(name, {}).get("available") else 0.0 for name in names])
    ax.set_title("N7C5A Go2 field availability")
    ax.set_ylabel("available")
    ax.tick_params(axis="x", labelrotation=35)
    ax.grid(True, axis="y", linewidth=0.3, alpha=0.4)
    generated.append(_save(fig, root / REQUIRED_N7C5A_FIGURES[0], plt))

    fig, ax = _axis(plt)
    ax.bar(["row_count/1e4", "rate_hz/100", "span_s/100"], [
        _f(inventory.get("row_count")) / 10000.0,
        _f(inventory.get("update_rate", {}).get("rate_hz_p50")) / 100.0,
        _f(inventory.get("update_rate", {}).get("time_span_sec")) / 100.0,
    ])
    ax.set_title("N7C5A signal rate and time axis")
    ax.grid(True, axis="y", linewidth=0.3, alpha=0.4)
    generated.append(_save(fig, root / REQUIRED_N7C5A_FIGURES[1], plt))

    ct = _times(contact_rows)
    fig, ax = _axis(plt)
    for foot in range(4):
        ax.plot(ct, _values(contact_rows, f"foot_{foot}_contact_probability"), linewidth=0.9, label=f"foot {foot}")
    ax.set_title("N7C5A contact probability by foot")
    ax.set_xlabel("time since start (s)")
    ax.set_ylabel("probability")
    ax.grid(True, linewidth=0.3, alpha=0.4)
    ax.legend(fontsize=8)
    generated.append(_save(fig, root / REQUIRED_N7C5A_FIGURES[2], plt))

    fig, ax = _axis(plt)
    ax.plot(ct, _values(contact_rows, "support_probability"), label="support", linewidth=0.9)
    ax.plot(ct, _values(contact_rows, "uncertainty_probability"), label="uncertainty", linewidth=0.9)
    ax.plot(ct, _values(contact_rows, "swing_probability"), label="swing", linewidth=0.9)
    ax.set_title("N7C5A support / uncertainty probability")
    ax.set_xlabel("time since start (s)")
    ax.set_ylabel("probability")
    ax.grid(True, linewidth=0.3, alpha=0.4)
    ax.legend(fontsize=8)
    generated.append(_save(fig, root / REQUIRED_N7C5A_FIGURES[3], plt))

    fig, ax = _axis(plt)
    values = [_f(row.get(f"foot_{foot}_contact_probability")) for row in contact_rows for foot in range(4)]
    ax.hist(values, bins=24)
    ax.set_title("N7C5A contact probability histogram")
    ax.set_xlabel("probability")
    ax.grid(True, axis="y", linewidth=0.3, alpha=0.4)
    generated.append(_save(fig, root / REQUIRED_N7C5A_FIGURES[4], plt))

    ft = _times(foot_rows)
    for rel_path, pairs, title in [
        (REQUIRED_N7C5A_FIGURES[5], [("candidate_vn", "go2_vn"), ("candidate_ve", "go2_ve")], "Foot kinematic vs Go2 velocity"),
        (REQUIRED_N7C5A_FIGURES[6], [("candidate_vn", "receiver_vn"), ("candidate_ve", "receiver_ve")], "Foot kinematic vs receiver velocity"),
        (REQUIRED_N7C5A_FIGURES[7], [("candidate_vn", "raw_vn"), ("candidate_ve", "raw_ve")], "Foot kinematic vs raw Doppler"),
    ]:
        fig, ax = _axis(plt)
        for lhs, rhs in pairs:
            ax.plot(ft, _values(foot_rows, lhs), linewidth=0.75, label=lhs)
            ax.plot(ft, _values(foot_rows, rhs), linewidth=0.75, linestyle="--", label=rhs)
        ax.set_title(f"N7C5A {title}")
        ax.set_xlabel("time since start (s)")
        ax.set_ylabel("m/s")
        ax.grid(True, linewidth=0.3, alpha=0.4)
        ax.legend(fontsize=8)
        generated.append(_save(fig, root / rel_path, plt))

    fig, ax = _axis(plt)
    ax.plot(ft, _values(foot_rows, "residual_to_receiver"), label="to receiver", linewidth=0.8)
    ax.plot(ft, _values(foot_rows, "residual_to_raw"), label="to raw", linewidth=0.8)
    ax.plot(ft, _values(foot_rows, "residual_to_go2"), label="to Go2 velocity", linewidth=0.8)
    ax.set_title("N7C5A foot kinematic residual norm")
    ax.set_xlabel("time since start (s)")
    ax.set_ylabel("m/s")
    ax.grid(True, linewidth=0.3, alpha=0.4)
    ax.legend(fontsize=8)
    generated.append(_save(fig, root / REQUIRED_N7C5A_FIGURES[8], plt))

    fig, ax = _axis(plt)
    ax.plot(ft, _values(foot_rows, "slip_risk"), linewidth=0.85)
    ax.set_title("N7C5A slip risk time")
    ax.set_xlabel("time since start (s)")
    ax.set_ylabel("risk")
    ax.grid(True, linewidth=0.3, alpha=0.4)
    generated.append(_save(fig, root / REQUIRED_N7C5A_FIGURES[9], plt))

    fig, ax = _axis(plt)
    phase_map = {"standing": 0, "walking": 1, "turning": 2, "transition": 3, "uncertain": 4}
    ax.step(_times(phase_rows), [phase_map.get(str(row.get("phase")), 4) for row in phase_rows], where="post", linewidth=0.8)
    ax.set_yticks(list(phase_map.values()))
    ax.set_yticklabels(list(phase_map.keys()))
    ax.set_title("N7C5A mode/gait phase timeline")
    ax.grid(True, linewidth=0.3, alpha=0.4)
    generated.append(_save(fig, root / REQUIRED_N7C5A_FIGURES[10], plt))

    for rel_path, keys, title in [
        (REQUIRED_N7C5A_FIGURES[11], ["yaw_speed_vs_yaw_derivative_rmse_radps", "yaw_speed_derivative_corr"], "Yawrate vs Go2 yaw derivative"),
        (REQUIRED_N7C5A_FIGURES[12], ["yaw_speed_vs_gyro_z_rmse_radps", "yaw_speed_gyro_z_corr"], "Gyro z vs yawrate"),
    ]:
        fig, ax = _axis(plt)
        ax.bar(keys, [_f(yaw.get(key)) for key in keys])
        ax.set_title(f"N7C5A {title}")
        ax.tick_params(axis="x", labelrotation=15)
        ax.grid(True, axis="y", linewidth=0.3, alpha=0.4)
        generated.append(_save(fig, root / rel_path, plt))

    for rel_path, keys, title in [
        (REQUIRED_N7C5A_FIGURES[13], ["go2_position_delta_rmse_m", "integrated_go2_velocity_delta_rmse_m"], "Go2 relative odometry delta"),
        (REQUIRED_N7C5A_FIGURES[14], ["position_vs_integrated_velocity_error_rmse_m", "ekf_displacement_delta_rmse_m"], "Relative odometry vs integrated velocity"),
    ]:
        fig, ax = _axis(plt)
        ax.bar(keys, [_f(rel.get(key)) for key in keys])
        ax.set_title(f"N7C5A {title}")
        ax.tick_params(axis="x", labelrotation=15)
        ax.grid(True, axis="y", linewidth=0.3, alpha=0.4)
        generated.append(_save(fig, root / rel_path, plt))

    candidates = ranking.get("candidates", [])
    fig, ax = _axis(plt)
    ax.barh([row.get("factor_id", "") for row in candidates], [_f(row.get("score")) for row in candidates])
    ax.set_title("N7C5A factor ranking")
    ax.grid(True, axis="x", linewidth=0.3, alpha=0.4)
    generated.append(_save(fig, root / REQUIRED_N7C5A_FIGURES[15], plt))

    risk_map = {"low": 1.0, "medium": 2.0, "high": 3.0}
    fig, ax = _axis(plt)
    for row in candidates:
        ax.scatter(risk_map.get(str(row.get("risk_level")), 2.5), _f(row.get("novelty_value")), s=50)
        ax.text(risk_map.get(str(row.get("risk_level")), 2.5) + 0.02, _f(row.get("novelty_value")), str(row.get("factor_id", ""))[:24], fontsize=7)
    ax.set_xticks([1, 2, 3])
    ax.set_xticklabels(["low", "medium", "high"])
    ax.set_ylabel("novelty value")
    ax.set_title("N7C5A factor candidate risk vs value")
    ax.grid(True, linewidth=0.3, alpha=0.4)
    generated.append(_save(fig, root / REQUIRED_N7C5A_FIGURES[16], plt))

    preview = decision_preview or {}
    fig, ax = _axis(plt)
    ax.axis("off")
    lines = [
        "N7C5A visual review",
        f"status: {preview.get('status', 'pending')}",
        f"next: {preview.get('recommended_next_stage', 'pending')}",
        f"foot rows: {len(inputs.get('foot_rows', []))}",
        f"contact summary only: {inputs.get('contact_rows_summary_only')}",
        f"N7C5 decision: {inputs.get('n7c5_decision', {}).get('status')}",
        "Go2 fields are observation, not truth.",
    ]
    ax.text(0.02, 0.95, "\n".join(lines), va="top", ha="left", family="monospace", fontsize=9)
    ax.set_title("N7C5A decision panel")
    generated.append(_save(fig, root / REQUIRED_N7C5A_FIGURES[17], plt))

    paths = [root / rel for rel in REQUIRED_N7C5A_FIGURES]
    return {
        "stage": "N7C5A_go2_full_proprioceptive_visual_review",
        "required_figures": REQUIRED_N7C5A_FIGURES,
        "figure_count_total": len(REQUIRED_N7C5A_FIGURES),
        "generated_figures": generated,
        "required_figures_generated": all(path.exists() for path in paths),
        "required_figures_nonempty": all(path.exists() and path.stat().st_size > 0 for path in paths),
        "figure_role_alias": "N7C5A_FIGURE_OUTPUT_DIR",
        "paper_performance_claim": False,
        "go2_not_truth": True,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "fgo": False,
    }
