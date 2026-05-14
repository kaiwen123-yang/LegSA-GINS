"""Runtime-only N8E visual plots.

中文说明：图像只写 runtime 目录，不进入 git。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any


MANDATORY_N8E_FIGURES = [
    "final_ablation_horizontal_bar.png",
    "final_ablation_yaw_bar.png",
    "final_ablation_roll_pitch_bar.png",
    "fgo_policy_delta_summary.png",
    "raw_doppler_frontend_vs_fgo_contribution.png",
    "go2_proprioceptive_joint_contribution.png",
    "source_aware_contribution_summary.png",
    "candidate_factor_status_summary.png",
    "no_feedback_fgo_caveat_panel.png",
    "n8e_decision_panel.png",
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
        "role_alias": "N8E_FIGURE_OUTPUT_DIR",
    }


def _bar(ax: Any, labels: list[str], values: list[float], title: str, ylabel: str) -> None:
    ax.bar(range(len(labels)), values)
    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels, rotation=38, ha="right", fontsize=7)
    ax.set_title(title)
    ax.set_ylabel(ylabel)
    ax.grid(True, axis="y", alpha=0.3)


def _rows(report: dict[str, Any]) -> list[dict[str, Any]]:
    return list(report.get("matrix_rows", []))


def _value(row: dict[str, Any], key: str) -> float:
    value = row.get(key)
    return float(value) if isinstance(value, (int, float)) else 0.0


def _module_status_values(module_summary: dict[str, Any], names: list[str]) -> list[float]:
    modules = {row.get("module"): row for row in module_summary.get("modules", [])}
    values: list[float] = []
    for name in names:
        status = str(modules.get(name, {}).get("status", ""))
        values.append(0.5 if "candidate" in status else 1.0 if status else 0.0)
    return values


def generate_n8e_figures(
    *,
    figure_output_dir: str | Path,
    matrix_report: dict[str, Any],
    module_summary: dict[str, Any],
    caveat_report: dict[str, Any],
    decision_preview: dict[str, Any],
) -> dict[str, Any]:
    plt = _plt()
    out = Path(figure_output_dir)
    rows = _rows(matrix_report)
    labels = [str(row.get("variant")) for row in rows]
    generated: list[dict[str, Any]] = []

    fig, ax = plt.subplots(figsize=(12.5, 5.2))
    _bar(ax, labels, [_value(row, "horizontal_rmse_m") for row in rows], "N8E final ablation horizontal delta", "m")
    generated.append(_save(fig, out / MANDATORY_N8E_FIGURES[0], plt))

    fig, ax = plt.subplots(figsize=(12.5, 5.2))
    _bar(ax, labels, [_value(row, "yaw_rmse_deg") for row in rows], "N8E final ablation yaw delta", "deg")
    generated.append(_save(fig, out / MANDATORY_N8E_FIGURES[1], plt))

    fig, ax = plt.subplots(figsize=(12.5, 5.2))
    _bar(
        ax,
        labels,
        [_value(row, "roll_rmse_deg") + _value(row, "pitch_rmse_deg") for row in rows],
        "N8E final ablation roll/pitch delta",
        "deg sum",
    )
    generated.append(_save(fig, out / MANDATORY_N8E_FIGURES[2], plt))

    fgo_rows = [row for row in rows if row.get("group") == "B_no_feedback_FGO_modules"]
    fig, ax = plt.subplots(figsize=(9.5, 4.8))
    _bar(
        ax,
        [str(row.get("variant")) for row in fgo_rows],
        [_value(row, "horizontal_rmse_m") + _value(row, "yaw_rmse_deg") for row in fgo_rows],
        "No-feedback FGO policy delta summary",
        "H + yaw proxy",
    )
    generated.append(_save(fig, out / MANDATORY_N8E_FIGURES[3], plt))

    fig, ax = plt.subplots(figsize=(7.8, 4.6))
    raw_names = ["Raw Doppler EKF", "Raw Doppler FGO"]
    _bar(ax, raw_names, _module_status_values(module_summary, raw_names), "Raw Doppler frontend vs FGO contribution", "status proxy")
    ax.text(0.02, 0.92, "FGO low marginal value is caveat, not failure", transform=ax.transAxes, fontsize=9)
    generated.append(_save(fig, out / MANDATORY_N8E_FIGURES[4], plt))

    fig, ax = plt.subplots(figsize=(7.8, 4.6))
    go2_names = ["Go2 proprioceptive joint", "Contact probability", "Foot kinematic velocity"]
    _bar(ax, go2_names, _module_status_values(module_summary, go2_names), "Go2 proprioceptive contribution", "status proxy")
    generated.append(_save(fig, out / MANDATORY_N8E_FIGURES[5], plt))

    fig, ax = plt.subplots(figsize=(7.8, 4.6))
    _bar(ax, ["Source-aware LSIM/OIM"], _module_status_values(module_summary, ["Source-aware LSIM/OIM"]), "Source-aware contribution summary", "status proxy")
    ax.text(0.02, 0.88, "Active R scaling layer; stress evidence limited", transform=ax.transAxes, fontsize=9)
    generated.append(_save(fig, out / MANDATORY_N8E_FIGURES[6], plt))

    candidate_rows = [row for row in rows if row.get("group") == "D_candidate_factors"]
    fig, ax = plt.subplots(figsize=(9, 4.8))
    _bar(
        ax,
        [str(row.get("variant")) for row in candidate_rows],
        [1.0 if row.get("diagnostic_only") else 0.0 for row in candidate_rows],
        "Candidate factor status summary",
        "diagnostic flag",
    )
    generated.append(_save(fig, out / MANDATORY_N8E_FIGURES[7], plt))

    fig, ax = plt.subplots(figsize=(9.2, 4.8))
    ax.axis("off")
    caveat_lines = [f"- {row.get('id')}: {row.get('is_failure') is False}" for row in caveat_report.get("caveats", [])[:8]]
    ax.text(0.02, 0.95, "\n".join(caveat_lines), va="top", family="monospace", fontsize=9)
    ax.set_title("N8E no-feedback FGO caveat panel")
    generated.append(_save(fig, out / MANDATORY_N8E_FIGURES[8], plt))

    fig, ax = plt.subplots(figsize=(9.2, 4.8))
    ax.axis("off")
    lines = [
        f"status: {decision_preview.get('status')}",
        f"next: {decision_preview.get('recommended_next_stage')}",
        f"secondary: {decision_preview.get('secondary_recommendation')}",
        f"matrix_complete: {decision_preview.get('matrix_complete')}",
        f"claim_boundary: {decision_preview.get('claim_boundary_decision')}",
        "no feedback/substitution; no trace/final_v23 tuning",
        "no paper performance claim; no outperform final_v23 claim",
    ]
    ax.text(0.02, 0.95, "\n".join(lines), va="top", family="monospace", fontsize=9)
    ax.set_title("N8E decision panel")
    generated.append(_save(fig, out / MANDATORY_N8E_FIGURES[9], plt))

    paths = [out / name for name in MANDATORY_N8E_FIGURES]
    return {
        "stage": "N8E_formal_engineering_ablation_with_caveat",
        "required_figures": MANDATORY_N8E_FIGURES,
        "figure_count_total": len(MANDATORY_N8E_FIGURES),
        "generated_figures": generated,
        "required_figures_generated": all(path.exists() for path in paths),
        "required_figures_nonempty": all(path.exists() and path.stat().st_size > 0 for path in paths),
        "figure_role_alias": "N8E_FIGURE_OUTPUT_DIR",
        "runtime_only": True,
        "paper_performance_claim": False,
    }
