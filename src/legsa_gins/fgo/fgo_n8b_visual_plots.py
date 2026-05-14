"""Runtime-only N8B factor-policy visual plots.

中文说明：图像只写 runtime 目录，不能提交到仓库。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from legsa_gins.fgo.fgo_angle_utils import shortest_angle_residual_deg
from legsa_gins.fgo.fgo_yaw_convention_fix import _f


REQUIRED_N8B_FIGURES = [
    "policy_ablation_yaw_delta_bar.png",
    "policy_ablation_horizontal_delta_bar.png",
    "smoothness_policy_yaw_delta_bar.png",
    "per_factor_residual_p95_bar.png",
    "default_vs_weak_smoothness_yaw_time.png",
    "default_vs_weak_smoothness_horizontal_error.png",
    "candidate_factor_delta_bar.png",
    "factor_weight_summary.png",
    "fgo_cost_by_policy.png",
    "n8b_decision_panel.png",
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
        "role_alias": "N8B_FIGURE_OUTPUT_DIR",
    }


def _time(rows: list[dict[str, Any]]) -> list[float]:
    return [_f(row.get("time", row.get("timestamp")), float(index)) for index, row in enumerate(rows)]


def _yaw(rows: list[dict[str, Any]]) -> list[float]:
    return [_f(row.get("yaw_deg")) for row in rows]


def _horizontal_error(ekf_rows: list[dict[str, Any]], fgo_rows: list[dict[str, Any]]) -> list[float]:
    import math

    values = []
    for ekf, fgo in zip(ekf_rows, fgo_rows):
        lat0 = math.radians(_f(ekf.get("lat_deg")))
        north = (_f(fgo.get("lat_deg")) - _f(ekf.get("lat_deg"))) * 111_320.0
        east = (_f(fgo.get("lon_deg")) - _f(ekf.get("lon_deg"))) * 111_320.0 * math.cos(lat0)
        values.append((north * north + east * east) ** 0.5)
    return values


def _bar(ax, labels: list[str], values: list[float], title: str, ylabel: str) -> None:
    ax.bar(range(len(labels)), values)
    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels, rotation=35, ha="right", fontsize=8)
    ax.set_title(title)
    ax.set_ylabel(ylabel)
    ax.grid(True, axis="y", alpha=0.3)


def generate_n8b_figures(
    *,
    figure_output_dir: str | Path,
    ekf_rows: list[dict[str, Any]],
    rows_by_variant: dict[str, list[dict[str, Any]]],
    ablation_summary: dict[str, Any],
    smoothness_review: dict[str, Any],
    factor_weight_review: dict[str, Any],
    candidate_review: dict[str, Any],
    decision_preview: dict[str, Any],
) -> dict[str, Any]:
    plt = _plt()
    out = Path(figure_output_dir)
    generated: list[dict[str, Any]] = []
    variants = list(ablation_summary.get("variants", []))
    labels = [str(row.get("variant", "")) for row in variants]

    fig, ax = plt.subplots(figsize=(10.5, 5.2))
    _bar(ax, labels, [float(row.get("yaw_delta_wrapped_rmse_deg", 0.0) or 0.0) for row in variants], "Policy ablation yaw delta", "wrapped RMSE deg")
    generated.append(_save(fig, out / REQUIRED_N8B_FIGURES[0], plt))

    fig, ax = plt.subplots(figsize=(10.5, 5.2))
    _bar(ax, labels, [float(row.get("horizontal_delta_rmse_m", 0.0) or 0.0) for row in variants], "Policy ablation horizontal delta", "RMSE m")
    generated.append(_save(fig, out / REQUIRED_N8B_FIGURES[1], plt))

    smooth_rows = list(smoothness_review.get("smoothness_policy_metrics", []))
    smooth_labels = [str(row.get("variant", "")) for row in smooth_rows]
    fig, ax = plt.subplots(figsize=(9.5, 5.0))
    _bar(ax, smooth_labels, [float(row.get("yaw_delta_wrapped_rmse", 0.0) or 0.0) for row in smooth_rows], "Smoothness policy yaw delta", "wrapped RMSE deg")
    generated.append(_save(fig, out / REQUIRED_N8B_FIGURES[2], plt))

    p95 = factor_weight_review.get("per_factor_residual_p95", {})
    factor_labels = list(p95)
    fig, ax = plt.subplots(figsize=(10, 5.0))
    _bar(ax, factor_labels, [float(p95[name] or 0.0) for name in factor_labels], "Per-factor residual p95", "proxy p95")
    generated.append(_save(fig, out / REQUIRED_N8B_FIGURES[3], plt))

    times = _time(ekf_rows)
    default_rows = rows_by_variant.get("default_active_stack_n8a2", [])
    weak_rows = rows_by_variant.get("weak_yaw_smoothness", [])
    count = min(len(times), len(default_rows), len(weak_rows), len(ekf_rows))
    fig, ax = plt.subplots(figsize=(9.5, 4.8))
    ax.plot(times[:count], _yaw(ekf_rows)[:count], label="EKF yaw", linewidth=1.0)
    ax.plot(times[:count], _yaw(default_rows)[:count], label="default FGO yaw", linewidth=1.0)
    ax.plot(times[:count], _yaw(weak_rows)[:count], label="weak yaw smoothness", linewidth=1.0)
    ax.set_title("Default vs weak smoothness yaw time")
    ax.set_xlabel("time")
    ax.set_ylabel("yaw deg")
    ax.grid(True, alpha=0.3)
    ax.legend()
    generated.append(_save(fig, out / REQUIRED_N8B_FIGURES[4], plt))

    fig, ax = plt.subplots(figsize=(9.5, 4.8))
    ax.plot(times[:count], _horizontal_error(ekf_rows, default_rows)[:count], label="default", linewidth=1.0)
    ax.plot(times[:count], _horizontal_error(ekf_rows, weak_rows)[:count], label="weak yaw", linewidth=1.0)
    ax.set_title("Default vs weak smoothness horizontal error")
    ax.set_xlabel("time")
    ax.set_ylabel("m")
    ax.grid(True, alpha=0.3)
    ax.legend()
    generated.append(_save(fig, out / REQUIRED_N8B_FIGURES[5], plt))

    cand_rows = list(candidate_review.get("candidate_factor_reviews", []))
    fig, ax = plt.subplots(figsize=(9.5, 4.8))
    _bar(ax, [str(row.get("factor_type", "")) for row in cand_rows], [float(row.get("yaw_delta_wrapped_rmse_deg", 0.0) or 0.0) for row in cand_rows], "Candidate factor delta", "wrapped RMSE deg")
    generated.append(_save(fig, out / REQUIRED_N8B_FIGURES[6], plt))

    factor_rows = list(factor_weight_review.get("per_factor_residual_summary", []))
    fig, ax = plt.subplots(figsize=(10, 5.0))
    _bar(ax, [str(row.get("factor_type", "")) for row in factor_rows], [float(row.get("rmse", 0.0) or 0.0) for row in factor_rows], "Factor weight summary", "proxy RMSE")
    generated.append(_save(fig, out / REQUIRED_N8B_FIGURES[7], plt))

    fig, ax = plt.subplots(figsize=(10.5, 5.2))
    _bar(ax, labels, [float(row.get("final_cost", 0.0) or 0.0) for row in variants], "FGO cost by policy", "final cost")
    generated.append(_save(fig, out / REQUIRED_N8B_FIGURES[8], plt))

    fig, ax = plt.subplots(figsize=(9, 4.8))
    ax.axis("off")
    lines = [
        f"status: {decision_preview.get('status')}",
        f"next: {decision_preview.get('recommended_next_stage')}",
        f"smoothness: {smoothness_review.get('recommended_policy')}",
        f"candidates: {len(cand_rows)} diagnostic reviews",
        "no feedback, no substitution, no trace/final_v23 tuning",
        "no smoothness deletion as final shortcut",
    ]
    ax.text(0.02, 0.92, "\n".join(lines), va="top", family="monospace")
    ax.set_title("N8B decision panel")
    generated.append(_save(fig, out / REQUIRED_N8B_FIGURES[9], plt))

    paths = [out / name for name in REQUIRED_N8B_FIGURES]
    return {
        "stage": "N8B_fgo_factor_graph_policy_review",
        "required_figures": REQUIRED_N8B_FIGURES,
        "figure_count_total": len(REQUIRED_N8B_FIGURES),
        "generated_figures": generated,
        "required_figures_generated": all(path.exists() for path in paths),
        "required_figures_nonempty": all(path.exists() and path.stat().st_size > 0 for path in paths),
        "figure_role_alias": "N8B_FIGURE_OUTPUT_DIR",
        "runtime_only": True,
        "paper_performance_claim": False,
    }


def yaw_delta_series(ekf_rows: list[dict[str, Any]], fgo_rows: list[dict[str, Any]]) -> list[float]:
    return [shortest_angle_residual_deg(_f(fgo.get("yaw_deg")), _f(ekf.get("yaw_deg"))) for ekf, fgo in zip(ekf_rows, fgo_rows)]
