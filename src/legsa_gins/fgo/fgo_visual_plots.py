"""Runtime-only N8A FGO visual plots."""

from __future__ import annotations

from pathlib import Path
from typing import Any


REQUIRED_N8A_FIGURES = [
    "n8a_backend_and_factor_registry.png",
    "n8a_state_count_and_factor_count.png",
    "n8a_no_feedback_smoother_delta.png",
    "n8a_factor_boundary_panel.png",
    "n8a_decision_panel.png",
]


def _plt():
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    return plt


def _save(fig, path: Path, plt) -> dict[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=145)
    plt.close(fig)
    return {"figure_name": path.name, "nonempty": path.exists() and path.stat().st_size > 0, "size_bytes": path.stat().st_size if path.exists() else 0}


def generate_n8a_figures(
    *,
    figure_output_dir: str | Path,
    backend: dict[str, Any],
    registry: dict[str, Any],
    dataset: dict[str, Any],
    smoother: dict[str, Any],
    evaluation: dict[str, Any],
    decision: dict[str, Any],
) -> dict[str, Any]:
    """中文说明：图像只用于 runtime review，不提交。"""
    plt = _plt()
    out = Path(figure_output_dir)
    generated: list[dict[str, Any]] = []

    fig, ax = plt.subplots(figsize=(8, 4.6))
    ax.axis("off")
    ax.text(0.02, 0.9, f"backend: {backend.get('selected_backend')}\nactive factors: {len(registry.get('active_default_factors', []))}\ndiagnostic candidates: {len(registry.get('diagnostic_candidate_factors', []))}", va="top", family="monospace")
    ax.set_title("N8A backend and factor registry")
    generated.append(_save(fig, out / REQUIRED_N8A_FIGURES[0], plt))

    fig, ax = plt.subplots(figsize=(8, 4.6))
    ax.bar(["states", "active est.", "diagnostic est."], [dataset.get("state_count", 0), dataset.get("active_factor_count_estimate", 0), dataset.get("diagnostic_candidate_factor_count_estimate", 0)])
    ax.set_title("N8A state and factor counts")
    ax.set_ylabel("count")
    ax.grid(True, axis="y", alpha=0.35)
    generated.append(_save(fig, out / REQUIRED_N8A_FIGURES[1], plt))

    fig, ax = plt.subplots(figsize=(8, 4.6))
    ax.bar(
        ["yaw raw RMSE", "yaw wrapped RMSE", "smoother residual p95"],
        [
            evaluation.get("yaw_delta_raw_rmse_deg", evaluation.get("yaw_delta_rmse_deg", 0.0)),
            evaluation.get("yaw_delta_wrapped_rmse_deg", evaluation.get("yaw_delta_rmse_deg", 0.0)),
            smoother.get("residual_proxy_p95", 0.0),
        ],
    )
    ax.set_title("N8A no-feedback diagnostic deltas")
    ax.set_ylabel("diagnostic units")
    ax.grid(True, axis="y", alpha=0.35)
    generated.append(_save(fig, out / REQUIRED_N8A_FIGURES[2], plt))

    fig, ax = plt.subplots(figsize=(8, 4.6))
    ax.axis("off")
    lines = [
        "No feedback to EKF",
        "FGO output does not replace EKF NAV",
        "No trace/final_v23 as factor",
        "Go2 position/yaw/vertical factors disabled",
        "Candidate Go2 foot/yawrate/relative odometry diagnostic only",
    ]
    ax.text(0.02, 0.9, "\n".join(lines), va="top", family="monospace")
    ax.set_title("N8A factor boundary panel")
    generated.append(_save(fig, out / REQUIRED_N8A_FIGURES[3], plt))

    fig, ax = plt.subplots(figsize=(8, 4.6))
    ax.axis("off")
    ax.text(0.02, 0.9, f"status: {decision.get('status')}\nnext: {decision.get('recommended_next_stage')}\nsolve: {smoother.get('solve_status')}", va="top", family="monospace")
    ax.set_title("N8A decision panel")
    generated.append(_save(fig, out / REQUIRED_N8A_FIGURES[4], plt))

    paths = [out / name for name in REQUIRED_N8A_FIGURES]
    return {
        "stage": "N8A_no_feedback_fgo_foundation",
        "required_figures": REQUIRED_N8A_FIGURES,
        "figure_count_total": len(REQUIRED_N8A_FIGURES),
        "generated_figures": generated,
        "required_figures_generated": all(path.exists() for path in paths),
        "required_figures_nonempty": all(path.exists() and path.stat().st_size > 0 for path in paths),
        "figure_role_alias": "N8A_FIGURE_OUTPUT_DIR",
        "paper_performance_claim": False,
    }
