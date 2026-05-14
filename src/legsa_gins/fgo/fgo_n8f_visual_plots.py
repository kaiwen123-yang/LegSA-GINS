"""Runtime-only N8F visual plots.

中文说明：图像只写 runner 指定的 runtime 目录，不进入 git。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping, Sequence


MANDATORY_N8F_FIGURES = [
    "contact_weight_scale_time.png",
    "foot_kinematic_velocity_vs_go2_velocity.png",
    "foot_kinematic_velocity_residual_time.png",
    "yawrate_between_residual_time.png",
    "relative_odometry_residual_time.png",
    "candidate_factor_rows_by_type.png",
    "candidate_solver_residual_rows_by_type.png",
    "candidate_factor_toggle_delta_bar.png",
    "candidate_factor_whitened_residual_p95_bar.png",
    "legged_candidate_stack_horizontal_delta_bar.png",
    "legged_candidate_stack_yaw_delta_bar.png",
    "legged_candidate_stack_roll_pitch_delta_bar.png",
    "candidate_factor_gross_degradation_panel.png",
    "n8f_decision_panel.png",
]


def _plt():
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    return plt


def _save(fig: Any, path: Path, plt: Any) -> dict[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(path, dpi=145)
    plt.close(fig)
    return {
        "figure_name": path.name,
        "nonempty": path.exists() and path.stat().st_size > 0,
        "size_bytes": path.stat().st_size if path.exists() else 0,
        "role_alias": "N8F_FIGURE_OUTPUT_DIR",
    }


def _bar(ax: Any, labels: list[str], values: list[float], title: str, ylabel: str) -> None:
    ax.bar(range(len(labels)), values)
    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels, rotation=36, ha="right", fontsize=7)
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    ax.grid(True, axis="y", alpha=0.3)


def _variant_rows(report: Mapping[str, Any]) -> list[dict[str, Any]]:
    return [dict(row) for row in report.get("variants", [])]


def _v(row: Mapping[str, Any], key: str) -> float:
    value = row.get(key)
    return float(value) if isinstance(value, (int, float)) else 0.0


def generate_n8f_figures(
    *,
    figure_output_dir: str | Path,
    contact_timeseries: Sequence[Any],
    foot_residual_rows: Sequence[Mapping[str, Any]],
    yawrate_residual_rows: Sequence[Mapping[str, Any]],
    relative_residual_rows: Sequence[Mapping[str, Any]],
    variant_report: Mapping[str, Any],
    decision_report: Mapping[str, Any],
) -> dict[str, Any]:
    plt = _plt()
    out = Path(figure_output_dir)
    generated: list[dict[str, Any]] = []
    variants = _variant_rows(variant_report)
    labels = [str(row.get("variant")) for row in variants]

    fig, ax = plt.subplots(figsize=(9.5, 4.4))
    ax.plot([row.time for row in contact_timeseries], [row.contact_weight_scale for row in contact_timeseries], lw=0.9)
    ax.set_title("N8F contact-aware R scale")
    ax.set_xlabel("time")
    ax.set_ylabel("R scale")
    ax.grid(True, alpha=0.3)
    generated.append(_save(fig, out / MANDATORY_N8F_FIGURES[0], plt))

    fig, ax = plt.subplots(figsize=(8.8, 4.4))
    ax.scatter(
        [row.get("state_index", 0) for row in foot_residual_rows if row.get("dimension") == "vn"],
        [row.get("whitened_residual", 0.0) for row in foot_residual_rows if row.get("dimension") == "vn"],
        s=6,
        label="vN residual",
    )
    ax.scatter(
        [row.get("state_index", 0) for row in foot_residual_rows if row.get("dimension") == "ve"],
        [row.get("whitened_residual", 0.0) for row in foot_residual_rows if row.get("dimension") == "ve"],
        s=6,
        label="vE residual",
    )
    ax.legend(loc="best", fontsize=8)
    ax.set_title("Foot kinematic velocity residual components")
    ax.grid(True, alpha=0.3)
    generated.append(_save(fig, out / MANDATORY_N8F_FIGURES[1], plt))

    fig, ax = plt.subplots(figsize=(9.0, 4.4))
    ax.plot([idx for idx, _ in enumerate(foot_residual_rows)], [abs(float(row.get("whitened_residual", 0.0))) for row in foot_residual_rows])
    ax.set_title("Foot kinematic whitened residual time")
    ax.set_ylabel("|r|")
    ax.grid(True, alpha=0.3)
    generated.append(_save(fig, out / MANDATORY_N8F_FIGURES[2], plt))

    fig, ax = plt.subplots(figsize=(9.0, 4.4))
    ax.plot([idx for idx, _ in enumerate(yawrate_residual_rows)], [float(row.get("whitened_residual", 0.0)) for row in yawrate_residual_rows])
    ax.set_title("Yaw-rate between residual time")
    ax.set_ylabel("r")
    ax.grid(True, alpha=0.3)
    generated.append(_save(fig, out / MANDATORY_N8F_FIGURES[3], plt))

    fig, ax = plt.subplots(figsize=(9.0, 4.4))
    ax.plot([idx for idx, _ in enumerate(relative_residual_rows)], [float(row.get("whitened_residual", 0.0)) for row in relative_residual_rows])
    ax.set_title("Relative odometry residual time")
    ax.set_ylabel("r")
    ax.grid(True, alpha=0.3)
    generated.append(_save(fig, out / MANDATORY_N8F_FIGURES[4], plt))

    factor_types = ["FootKinematicVelocityFactor", "YawRateBetweenFactor", "RelativeOdometryBetweenFactor"]
    fig, ax = plt.subplots(figsize=(10.2, 4.8))
    _bar(
        ax,
        factor_types,
        [sum(int(row.get("factor_rows_by_type", {}).get(name, 0) or 0) for row in variants) for name in factor_types],
        "Candidate factor rows by type",
        "rows",
    )
    generated.append(_save(fig, out / MANDATORY_N8F_FIGURES[5], plt))

    fig, ax = plt.subplots(figsize=(10.2, 4.8))
    _bar(
        ax,
        factor_types,
        [sum(int(row.get("solver_residual_rows_by_type", {}).get(name, 0) or 0) for row in variants) for name in factor_types],
        "Candidate solver residual rows by type",
        "rows",
    )
    generated.append(_save(fig, out / MANDATORY_N8F_FIGURES[6], plt))

    fig, ax = plt.subplots(figsize=(12.0, 4.8))
    _bar(ax, labels, [_v(row, "solver_residual_dim_delta_vs_baseline") for row in variants], "Candidate factor toggle delta", "residual dim delta")
    generated.append(_save(fig, out / MANDATORY_N8F_FIGURES[7], plt))

    fig, ax = plt.subplots(figsize=(12.0, 4.8))
    _bar(ax, labels, [_v(row, "candidate_whitened_residual_p95") for row in variants], "Candidate whitened residual p95", "p95")
    generated.append(_save(fig, out / MANDATORY_N8F_FIGURES[8], plt))

    fig, ax = plt.subplots(figsize=(12.0, 4.8))
    _bar(ax, labels, [_v(row, "horizontal_delta_p95_m") for row in variants], "Legged candidate stack horizontal delta", "m")
    generated.append(_save(fig, out / MANDATORY_N8F_FIGURES[9], plt))

    fig, ax = plt.subplots(figsize=(12.0, 4.8))
    _bar(ax, labels, [_v(row, "yaw_delta_p95_deg") for row in variants], "Legged candidate stack yaw delta", "deg")
    generated.append(_save(fig, out / MANDATORY_N8F_FIGURES[10], plt))

    fig, ax = plt.subplots(figsize=(12.0, 4.8))
    _bar(
        ax,
        labels,
        [_v(row, "roll_delta_p95_deg") + _v(row, "pitch_delta_p95_deg") for row in variants],
        "Legged candidate stack roll/pitch delta",
        "deg sum",
    )
    generated.append(_save(fig, out / MANDATORY_N8F_FIGURES[11], plt))

    fig, ax = plt.subplots(figsize=(9.2, 4.8))
    ax.axis("off")
    gross = [row.get("variant") for row in variants if row.get("gross_degradation_flag")]
    lines = ["gross_degradation_variants:", *(f"- {name}" for name in gross[:10]), "none" if not gross else ""]
    ax.text(0.02, 0.95, "\n".join(line for line in lines if line), va="top", family="monospace", fontsize=9)
    ax.set_title("Candidate factor gross degradation panel")
    generated.append(_save(fig, out / MANDATORY_N8F_FIGURES[12], plt))

    fig, ax = plt.subplots(figsize=(9.2, 4.8))
    ax.axis("off")
    lines = [
        f"status: {decision_report.get('status')}",
        f"next: {decision_report.get('recommended_next_stage')}",
        f"foot_active: {decision_report.get('foot_kinematic_factor_active')}",
        f"yawrate_active: {decision_report.get('yawrate_between_factor_active')}",
        f"relative_active: {decision_report.get('relative_odometry_between_factor_active')}",
        "no feedback/substitution; no trace/final_v23 tuning",
        "no Go2 truth claim; no paper performance claim",
    ]
    ax.text(0.02, 0.95, "\n".join(lines), va="top", family="monospace", fontsize=9)
    ax.set_title("N8F decision panel")
    generated.append(_save(fig, out / MANDATORY_N8F_FIGURES[13], plt))

    paths = [out / name for name in MANDATORY_N8F_FIGURES]
    return {
        "stage": "N8F_legged_candidate_factor_activation",
        "required_figures": MANDATORY_N8F_FIGURES,
        "figure_count_total": len(MANDATORY_N8F_FIGURES),
        "generated_figures": generated,
        "required_figures_generated": all(path.exists() for path in paths),
        "required_figures_nonempty": all(path.exists() and path.stat().st_size > 0 for path in paths),
        "figure_role_alias": "N8F_FIGURE_OUTPUT_DIR",
        "runtime_only": True,
        "paper_performance_claim": False,
    }

