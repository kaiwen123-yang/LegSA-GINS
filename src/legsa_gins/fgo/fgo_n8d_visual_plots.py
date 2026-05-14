"""Runtime-only N8D factor weight policy figures.

中文说明：图像只写 runtime figure 目录，不进入 git。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any


MANDATORY_N8D_FIGURES = [
    "whitened_residual_balance_by_policy.png",
    "factor_contribution_share_by_policy.png",
    "smoothness_component_weight_policy.png",
    "raw_receiver_weight_balance_delta.png",
    "raw_doppler_contribution_by_weight.png",
    "go2_joint_contribution_by_weight.png",
    "dual_yaw_weight_policy_yaw_delta.png",
    "formal_ablation_horizontal_delta_bar.png",
    "formal_ablation_yaw_delta_bar.png",
    "formal_ablation_roll_pitch_delta_bar.png",
    "policy_cost_residual_proxy_bar.png",
    "n8d_decision_panel.png",
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
        "role_alias": "N8D_FIGURE_OUTPUT_DIR",
    }


def _bar(ax: Any, labels: list[str], values: list[float], title: str, ylabel: str) -> None:
    ax.bar(range(len(labels)), values)
    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels, rotation=35, ha="right", fontsize=8)
    ax.set_title(title)
    ax.set_ylabel(ylabel)
    ax.grid(True, axis="y", alpha=0.3)


def _summary_rows(report: dict[str, Any]) -> list[dict[str, Any]]:
    return list(report.get("variants", []))


def _factor_value(summary: dict[str, Any], factor_type: str, field: str) -> float:
    factor = next((row for row in summary.get("factor_balance", []) if row.get("factor_type") == factor_type), {})
    return float(factor.get(field, 0.0) or 0.0)


def generate_n8d_figures(
    *,
    figure_output_dir: str | Path,
    formal_variant_report: dict[str, Any],
    balance_report: dict[str, Any],
    smoothness_report: dict[str, Any],
    raw_receiver_report: dict[str, Any],
    go2_report: dict[str, Any],
    dual_yaw_report: dict[str, Any],
    decision_preview: dict[str, Any],
) -> dict[str, Any]:
    plt = _plt()
    out = Path(figure_output_dir)
    generated: list[dict[str, Any]] = []
    formal_rows = _summary_rows(formal_variant_report)
    formal_labels = [str(row.get("variant")) for row in formal_rows]

    fig, ax = plt.subplots(figsize=(10.5, 4.8))
    _bar(ax, formal_labels, [_factor_value(row, "SmoothnessFactor", "dimension_normalized_whitened_norm") for row in formal_rows], "Whitened smoothness balance by policy", "dim-normalized")
    generated.append(_save(fig, out / MANDATORY_N8D_FIGURES[0], plt))

    fig, ax = plt.subplots(figsize=(10.5, 4.8))
    smooth = [_factor_value(row, "SmoothnessFactor", "contribution_share") for row in formal_rows]
    raw = [_factor_value(row, "RawDopplerVelocityFactor", "contribution_share") for row in formal_rows]
    ax.bar(range(len(formal_labels)), smooth, label="smoothness")
    ax.bar(range(len(formal_labels)), raw, bottom=smooth, label="raw doppler")
    ax.set_xticks(range(len(formal_labels)))
    ax.set_xticklabels(formal_labels, rotation=35, ha="right", fontsize=8)
    ax.set_title("Factor contribution share by policy")
    ax.set_ylabel("share")
    ax.legend()
    ax.grid(True, axis="y", alpha=0.3)
    generated.append(_save(fig, out / MANDATORY_N8D_FIGURES[1], plt))

    smooth_rows = list(smoothness_report.get("component_rows", []))
    labels = [str(row.get("variant")) for row in smooth_rows]
    fig, ax = plt.subplots(figsize=(9.5, 4.8))
    _bar(ax, labels, [float(row.get("smoothness_share", 0.0) or 0.0) for row in smooth_rows], "Smoothness component weight policy", "share")
    generated.append(_save(fig, out / MANDATORY_N8D_FIGURES[2], plt))

    raw_rows = list(raw_receiver_report.get("variants", []))
    labels = [str(row.get("variant")) for row in raw_rows]
    fig, ax = plt.subplots(figsize=(9.5, 4.8))
    _bar(ax, labels, [float(row.get("horizontal_delta_rmse_m", 0.0) or 0.0) for row in raw_rows], "Raw receiver weight balance delta", "horizontal delta m")
    generated.append(_save(fig, out / MANDATORY_N8D_FIGURES[3], plt))

    fig, ax = plt.subplots(figsize=(9.5, 4.8))
    _bar(ax, labels, [float(row.get("raw_doppler_share", 0.0) or 0.0) for row in raw_rows], "Raw Doppler contribution by weight", "share")
    generated.append(_save(fig, out / MANDATORY_N8D_FIGURES[4], plt))

    go2_rows = list(go2_report.get("variants", []))
    labels = [str(row.get("variant")) for row in go2_rows]
    fig, ax = plt.subplots(figsize=(8.5, 4.8))
    _bar(ax, labels, [float(row.get("go2_contribution_share", 0.0) or 0.0) for row in go2_rows], "Go2 joint contribution by weight", "share")
    generated.append(_save(fig, out / MANDATORY_N8D_FIGURES[5], plt))

    dual_rows = list(dual_yaw_report.get("variants", []))
    labels = [str(row.get("variant")) for row in dual_rows]
    fig, ax = plt.subplots(figsize=(8.5, 4.8))
    _bar(ax, labels, [float(row.get("yaw_delta_wrapped_rmse_deg", 0.0) or 0.0) for row in dual_rows], "Dual yaw weight policy yaw delta", "deg")
    generated.append(_save(fig, out / MANDATORY_N8D_FIGURES[6], plt))

    fig, ax = plt.subplots(figsize=(10.5, 4.8))
    _bar(ax, formal_labels, [float(row.get("horizontal_delta_rmse_m", 0.0) or 0.0) for row in formal_rows], "Formal ablation horizontal delta", "m")
    generated.append(_save(fig, out / MANDATORY_N8D_FIGURES[7], plt))

    fig, ax = plt.subplots(figsize=(10.5, 4.8))
    _bar(ax, formal_labels, [float(row.get("yaw_delta_wrapped_rmse_deg", 0.0) or 0.0) for row in formal_rows], "Formal ablation yaw delta", "deg")
    generated.append(_save(fig, out / MANDATORY_N8D_FIGURES[8], plt))

    fig, ax = plt.subplots(figsize=(10.5, 4.8))
    values = [float(row.get("roll_delta_rmse_deg", 0.0) or 0.0) + float(row.get("pitch_delta_rmse_deg", 0.0) or 0.0) for row in formal_rows]
    _bar(ax, formal_labels, values, "Formal ablation roll pitch delta", "deg sum")
    generated.append(_save(fig, out / MANDATORY_N8D_FIGURES[9], plt))

    fig, ax = plt.subplots(figsize=(10.5, 4.8))
    _bar(ax, formal_labels, [float(row.get("final_cost", 0.0) or 0.0) for row in formal_rows], "Policy cost residual proxy", "cost")
    generated.append(_save(fig, out / MANDATORY_N8D_FIGURES[10], plt))

    fig, ax = plt.subplots(figsize=(9, 4.8))
    ax.axis("off")
    lines = [
        f"status: {decision_preview.get('status')}",
        f"next: {decision_preview.get('recommended_next_stage')}",
        f"best_balance: {decision_preview.get('best_solver_visible_balance_variant')}",
        f"smoothness_dominance: {decision_preview.get('smoothness_dominance_detected')}",
        "no trace/final_v23 tuning; no feedback; no paper claim",
        "no smoothness deletion final shortcut",
    ]
    ax.text(0.02, 0.94, "\n".join(lines), va="top", family="monospace")
    ax.set_title("N8D decision panel")
    generated.append(_save(fig, out / MANDATORY_N8D_FIGURES[11], plt))

    paths = [out / name for name in MANDATORY_N8D_FIGURES]
    return {
        "stage": "N8D_fgo_factor_weight_policy_review",
        "required_figures": MANDATORY_N8D_FIGURES,
        "figure_count_total": len(MANDATORY_N8D_FIGURES),
        "generated_figures": generated,
        "required_figures_generated": all(path.exists() for path in paths),
        "required_figures_nonempty": all(path.exists() and path.stat().st_size > 0 for path in paths),
        "figure_role_alias": "N8D_FIGURE_OUTPUT_DIR",
        "runtime_only": True,
        "paper_performance_claim": False,
    }
