"""Runtime-only N8A2 yaw convention fix plots.

中文说明：图像只写 runtime 目录，不提交到仓库。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from legsa_gins.fgo.fgo_angle_utils import shortest_angle_residual_deg, unwrap_series_deg
from legsa_gins.fgo.fgo_yaw_convention_fix import _f
from legsa_gins.fgo.fgo_yaw_residuals import dual_yaw_residual_deg, yaw_smoothness_residual_deg
from legsa_gins.fgo.fgo_yaw_smoothness_factor_fix import yaw_smoothness_residual_series


REQUIRED_N8A2_FIGURES = [
    "yaw_residual_wrap_toy_examples.png",
    "ekf_vs_fgo_yaw_after_fix.png",
    "fgo_minus_ekf_yaw_delta_wrapped_after_fix.png",
    "fgo_minus_ekf_yaw_delta_raw_vs_wrapped.png",
    "yaw_smoothness_residual_before_after.png",
    "dual_yaw_factor_residual_after_fix.png",
    "n8a_vs_n8a2_yaw_delta_bar.png",
    "n8a2_variant_yaw_delta_bar.png",
    "fgo_iteration_cost_after_fix.png",
    "n8a2_decision_panel.png",
]


def _plt():
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    return plt


def _save(fig, path: Path, plt) -> dict[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(path, dpi=145)
    plt.close(fig)
    return {
        "figure_name": path.name,
        "nonempty": path.exists() and path.stat().st_size > 0,
        "size_bytes": path.stat().st_size if path.exists() else 0,
        "role_alias": "N8A2_FIGURE_OUTPUT_DIR",
    }


def _yaw(rows: list[dict[str, Any]]) -> list[float]:
    return [_f(row.get("yaw_deg")) for row in rows]


def _time(rows: list[dict[str, Any]]) -> list[float]:
    return [_f(row.get("time", row.get("timestamp")), float(index)) for index, row in enumerate(rows)]


def generate_n8a2_figures(
    *,
    figure_output_dir: str | Path,
    ekf_rows: list[dict[str, Any]],
    original_fgo_rows: list[dict[str, Any]],
    fixed_fgo_rows: list[dict[str, Any]],
    variant_summary: dict[str, Any],
    comparison: dict[str, Any],
    decision_preview: dict[str, Any],
) -> dict[str, Any]:
    plt = _plt()
    out = Path(figure_output_dir)
    generated: list[dict[str, Any]] = []
    times = _time(ekf_rows)
    ekf_yaw = _yaw(ekf_rows)
    original_yaw = _yaw(original_fgo_rows)
    fixed_yaw = _yaw(fixed_fgo_rows)
    count = min(len(times), len(ekf_yaw), len(original_yaw), len(fixed_yaw))
    times = times[:count]
    ekf_yaw = ekf_yaw[:count]
    original_yaw = original_yaw[:count]
    fixed_yaw = fixed_yaw[:count]
    raw_delta = [fgo - ekf for ekf, fgo in zip(ekf_yaw, fixed_yaw)]
    wrapped_delta = [shortest_angle_residual_deg(fgo, ekf) for ekf, fgo in zip(ekf_yaw, fixed_yaw)]
    before_smoothness = yaw_smoothness_residual_series(original_yaw)
    after_smoothness = yaw_smoothness_residual_series(fixed_yaw)

    fig, ax = plt.subplots(figsize=(8.8, 4.8))
    labels = ["dual 1-359", "smooth 359->1", "yawrate 359->1,1dps"]
    values = [dual_yaw_residual_deg(1.0, 359.0), yaw_smoothness_residual_deg(359.0, 1.0), yaw_smoothness_residual_deg(359.0, 1.0, 1.0)]
    ax.bar(labels, values)
    ax.set_title("Yaw residual wrap toy examples")
    ax.set_ylabel("deg")
    ax.grid(True, axis="y", alpha=0.3)
    generated.append(_save(fig, out / REQUIRED_N8A2_FIGURES[0], plt))

    fig, ax = plt.subplots(figsize=(9, 4.8))
    ax.plot(times, ekf_yaw, label="EKF yaw", linewidth=1.0)
    ax.plot(times, fixed_yaw, label="FGO yaw after fix", linewidth=1.0)
    ax.set_title("EKF vs FGO yaw after fix")
    ax.set_xlabel("time")
    ax.set_ylabel("yaw deg")
    ax.grid(True, alpha=0.3)
    ax.legend()
    generated.append(_save(fig, out / REQUIRED_N8A2_FIGURES[1], plt))

    fig, ax = plt.subplots(figsize=(9, 4.8))
    ax.plot(times, wrapped_delta, linewidth=1.0)
    ax.axhline(0.0, color="black", linewidth=0.8)
    ax.set_title("FGO minus EKF yaw delta, wrapped after fix")
    ax.set_xlabel("time")
    ax.set_ylabel("deg")
    ax.grid(True, alpha=0.3)
    generated.append(_save(fig, out / REQUIRED_N8A2_FIGURES[2], plt))

    fig, ax = plt.subplots(figsize=(9, 4.8))
    ax.plot(times, raw_delta, label="raw delta", linewidth=1.0)
    ax.plot(times, wrapped_delta, label="wrapped delta", linewidth=1.0)
    ax.set_title("Raw vs wrapped yaw delta after fix")
    ax.set_xlabel("time")
    ax.set_ylabel("deg")
    ax.grid(True, alpha=0.3)
    ax.legend()
    generated.append(_save(fig, out / REQUIRED_N8A2_FIGURES[3], plt))

    fig, ax = plt.subplots(figsize=(9, 4.8))
    ax.plot(times[1:], before_smoothness[: max(0, count - 1)], label="before", linewidth=1.0)
    ax.plot(times[1:], after_smoothness[: max(0, count - 1)], label="after", linewidth=1.0)
    ax.set_title("Yaw smoothness residual before/after")
    ax.set_xlabel("time")
    ax.set_ylabel("deg")
    ax.grid(True, alpha=0.3)
    ax.legend()
    generated.append(_save(fig, out / REQUIRED_N8A2_FIGURES[4], plt))

    fig, ax = plt.subplots(figsize=(9, 4.8))
    ax.plot(times, [abs(value) for value in wrapped_delta], linewidth=1.0)
    ax.set_title("Dual yaw factor residual after fix")
    ax.set_xlabel("time")
    ax.set_ylabel("abs deg")
    ax.grid(True, alpha=0.3)
    generated.append(_save(fig, out / REQUIRED_N8A2_FIGURES[5], plt))

    fig, ax = plt.subplots(figsize=(8.8, 4.8))
    ax.bar(
        ["N8A reference", "N8A2 fixed default"],
        [
            comparison.get("n8a_reference_yaw_delta_wrapped_rmse_deg", 0.0),
            comparison.get("n8a2_default_yaw_delta_wrapped_rmse_deg", 0.0),
        ],
    )
    ax.set_title("N8A vs N8A2 yaw delta")
    ax.set_ylabel("wrapped RMSE deg")
    ax.grid(True, axis="y", alpha=0.3)
    generated.append(_save(fig, out / REQUIRED_N8A2_FIGURES[6], plt))

    variants = variant_summary.get("variants", [])
    fig, ax = plt.subplots(figsize=(10, 5.2))
    labels = [str(row.get("variant", "")) for row in variants]
    values = [float(row.get("yaw_delta_wrapped_rmse_deg", 0.0) or 0.0) for row in variants]
    ax.bar(range(len(labels)), values)
    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels, rotation=35, ha="right", fontsize=8)
    ax.set_title("N8A2 variant yaw delta")
    ax.set_ylabel("wrapped RMSE deg")
    ax.grid(True, axis="y", alpha=0.3)
    generated.append(_save(fig, out / REQUIRED_N8A2_FIGURES[7], plt))

    fig, ax = plt.subplots(figsize=(9, 4.8))
    costs = [float(row.get("final_cost", 0.0) or 0.0) for row in variants]
    ax.plot(range(len(costs)), costs, marker="o")
    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels, rotation=35, ha="right", fontsize=8)
    ax.set_title("FGO iteration cost after fix")
    ax.set_ylabel("cost")
    ax.grid(True, alpha=0.3)
    generated.append(_save(fig, out / REQUIRED_N8A2_FIGURES[8], plt))

    fig, ax = plt.subplots(figsize=(9, 4.8))
    ax.axis("off")
    lines = [
        f"status: {decision_preview.get('status')}",
        f"next: {decision_preview.get('recommended_next_stage')}",
        f"wrapped rmse: {decision_preview.get('default_fixed_yaw_delta_wrapped_rmse_deg')}",
        f"secondary: {decision_preview.get('secondary_recommendation', '')}",
        "no feedback, no substitution, no output-only yaw correction",
    ]
    ax.text(0.02, 0.92, "\n".join(lines), va="top", family="monospace")
    ax.set_title("N8A2 decision panel")
    generated.append(_save(fig, out / REQUIRED_N8A2_FIGURES[9], plt))

    paths = [out / name for name in REQUIRED_N8A2_FIGURES]
    return {
        "stage": "N8A2_fgo_yaw_convention_fix",
        "required_figures": REQUIRED_N8A2_FIGURES,
        "figure_count_total": len(REQUIRED_N8A2_FIGURES),
        "generated_figures": generated,
        "required_figures_generated": all(path.exists() for path in paths),
        "required_figures_nonempty": all(path.exists() and path.stat().st_size > 0 for path in paths),
        "figure_role_alias": "N8A2_FIGURE_OUTPUT_DIR",
        "runtime_only": True,
        "paper_performance_claim": False,
    }
