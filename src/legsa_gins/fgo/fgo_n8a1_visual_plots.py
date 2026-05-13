"""Runtime-only N8A1 yaw-delta visual plots.

中文说明：本模块只生成运行时图像清单，不提交图片。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from legsa_gins.fgo.fgo_yaw_convention_audit import (
    as_float,
    time_series,
    unwrap_degrees,
    wrap_delta_deg,
    yaw_delta_deg,
    yaw_series,
)


REQUIRED_N8A1_FIGURES = [
    "ekf_vs_fgo_yaw_time.png",
    "fgo_minus_ekf_yaw_delta_wrapped.png",
    "fgo_minus_ekf_yaw_delta_unwrapped.png",
    "yaw_delta_by_time_segment.png",
    "yaw_factor_residual_time.png",
    "smoothness_yaw_residual_time.png",
    "factor_residual_p95_by_type.png",
    "n8a1_ablation_yaw_delta_bar.png",
    "fgo_state_epoch_mapping_timeline.png",
    "n8a1_decision_panel.png",
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
        "role_alias": "N8A1_FIGURE_OUTPUT_DIR",
    }


def generate_n8a1_figures(
    *,
    figure_output_dir: str | Path,
    ekf_rows: list[dict[str, Any]],
    fgo_rows: list[dict[str, Any]],
    yaw_convention: dict[str, Any],
    yaw_diagnostics: dict[str, Any],
    state_epoch_mapping: dict[str, Any],
    factor_policy: dict[str, Any],
    ablation: dict[str, Any],
    decision_preview: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Generate required N8A1 figures into a runtime-only directory."""
    plt = _plt()
    out = Path(figure_output_dir)
    generated: list[dict[str, Any]] = []
    times = time_series(ekf_rows)
    ekf_yaw = yaw_series(ekf_rows)
    fgo_yaw = yaw_series(fgo_rows)
    count = min(len(times), len(ekf_yaw), len(fgo_yaw))
    times = times[:count]
    ekf_yaw = ekf_yaw[:count]
    fgo_yaw = fgo_yaw[:count]
    wrapped_delta = [yaw_delta_deg(fgo, ekf) for ekf, fgo in zip(ekf_yaw, fgo_yaw)]
    ekf_unwrapped = unwrap_degrees(ekf_yaw)
    fgo_unwrapped = unwrap_degrees(fgo_yaw)
    unwrapped_delta = [fgo - ekf for ekf, fgo in zip(ekf_unwrapped, fgo_unwrapped)]
    smoothness_yaw = [abs(wrap_delta_deg(right - left)) for left, right in zip(fgo_yaw, fgo_yaw[1:])]

    fig, ax = plt.subplots(figsize=(9, 4.8))
    ax.plot(times, ekf_yaw, label="EKF yaw", linewidth=1.2)
    ax.plot(times, fgo_yaw, label="FGO yaw", linewidth=1.0, alpha=0.82)
    ax.set_title("EKF vs FGO yaw")
    ax.set_xlabel("time")
    ax.set_ylabel("yaw deg")
    ax.grid(True, alpha=0.3)
    ax.legend()
    generated.append(_save(fig, out / REQUIRED_N8A1_FIGURES[0], plt))

    fig, ax = plt.subplots(figsize=(9, 4.8))
    ax.plot(times, wrapped_delta, linewidth=1.0)
    ax.axhline(0.0, color="black", linewidth=0.8)
    ax.set_title("FGO minus EKF yaw delta, wrapped")
    ax.set_xlabel("time")
    ax.set_ylabel("deg")
    ax.grid(True, alpha=0.3)
    generated.append(_save(fig, out / REQUIRED_N8A1_FIGURES[1], plt))

    fig, ax = plt.subplots(figsize=(9, 4.8))
    ax.plot(times, unwrapped_delta, linewidth=1.0)
    ax.axhline(0.0, color="black", linewidth=0.8)
    ax.set_title("FGO minus EKF yaw delta, unwrapped")
    ax.set_xlabel("time")
    ax.set_ylabel("deg")
    ax.grid(True, alpha=0.3)
    generated.append(_save(fig, out / REQUIRED_N8A1_FIGURES[2], plt))

    segments = yaw_diagnostics.get("segments", [])
    fig, ax = plt.subplots(figsize=(9, 4.8))
    labels = [str(row.get("segment_index")) for row in segments]
    values = [as_float(row.get("yaw_delta_rmse_deg")) for row in segments]
    ax.bar(labels, values)
    ax.set_title("Yaw delta by time segment")
    ax.set_xlabel("segment")
    ax.set_ylabel("RMSE deg")
    ax.grid(True, axis="y", alpha=0.3)
    generated.append(_save(fig, out / REQUIRED_N8A1_FIGURES[3], plt))

    fig, ax = plt.subplots(figsize=(9, 4.8))
    ax.plot(times, [abs(value) for value in wrapped_delta], linewidth=1.0)
    ax.set_title("Yaw factor residual proxy")
    ax.set_xlabel("time")
    ax.set_ylabel("abs deg")
    ax.grid(True, alpha=0.3)
    generated.append(_save(fig, out / REQUIRED_N8A1_FIGURES[4], plt))

    fig, ax = plt.subplots(figsize=(9, 4.8))
    ax.plot(times[1:], smoothness_yaw, linewidth=1.0)
    ax.set_title("Smoothness yaw residual proxy")
    ax.set_xlabel("time")
    ax.set_ylabel("neighbor abs deg")
    ax.grid(True, alpha=0.3)
    generated.append(_save(fig, out / REQUIRED_N8A1_FIGURES[5], plt))

    contributions = factor_policy.get("per_factor_contribution_summary", [])
    fig, ax = plt.subplots(figsize=(10, 5.2))
    labels = [str(row.get("factor_type", "")) for row in contributions]
    values = [as_float(row.get("p95")) for row in contributions]
    ax.bar(range(len(labels)), values)
    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels, rotation=35, ha="right", fontsize=8)
    ax.set_title("Factor residual p95 by type")
    ax.set_ylabel("proxy p95")
    ax.grid(True, axis="y", alpha=0.3)
    generated.append(_save(fig, out / REQUIRED_N8A1_FIGURES[6], plt))

    variants = ablation.get("variants", [])
    fig, ax = plt.subplots(figsize=(10, 5.2))
    labels = [str(row.get("variant", "")) for row in variants]
    values = [as_float(row.get("yaw_delta_rmse_deg")) for row in variants]
    ax.bar(range(len(labels)), values)
    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels, rotation=35, ha="right", fontsize=8)
    ax.set_title("N8A1 ablation yaw delta")
    ax.set_ylabel("RMSE deg")
    ax.grid(True, axis="y", alpha=0.3)
    generated.append(_save(fig, out / REQUIRED_N8A1_FIGURES[7], plt))

    fig, ax = plt.subplots(figsize=(9, 4.8))
    ax.plot(times, list(range(count)), linewidth=1.0)
    ax.set_title("FGO state epoch mapping timeline")
    ax.set_xlabel("time")
    ax.set_ylabel("state index")
    ax.grid(True, alpha=0.3)
    txt = f"epochs={state_epoch_mapping.get('epoch_count')} dim={state_epoch_mapping.get('state_dimension_per_epoch')} monotonic={state_epoch_mapping.get('time_monotonic')}"
    ax.text(0.02, 0.94, txt, transform=ax.transAxes, va="top", family="monospace", fontsize=9)
    generated.append(_save(fig, out / REQUIRED_N8A1_FIGURES[8], plt))

    preview = decision_preview or {}
    fig, ax = plt.subplots(figsize=(9, 4.8))
    ax.axis("off")
    lines = [
        f"status: {preview.get('status', 'pending')}",
        f"next: {preview.get('recommended_next_stage', 'pending')}",
        f"yaw blocker: {yaw_convention.get('blocker_status')}",
        f"state mapping: {state_epoch_mapping.get('blocker_status')}",
        f"candidate leak: {factor_policy.get('candidate_factor_leak_suspect')}",
        f"best ablation: {ablation.get('best_yaw_delta_variant')}",
        "no feedback, no substitution, no paper performance claim",
    ]
    ax.text(0.02, 0.92, "\n".join(lines), va="top", family="monospace")
    ax.set_title("N8A1 decision panel")
    generated.append(_save(fig, out / REQUIRED_N8A1_FIGURES[9], plt))

    paths = [out / name for name in REQUIRED_N8A1_FIGURES]
    return {
        "stage": "N8A1_fgo_yaw_delta_policy_review",
        "required_figures": REQUIRED_N8A1_FIGURES,
        "figure_count_total": len(REQUIRED_N8A1_FIGURES),
        "generated_figures": generated,
        "required_figures_generated": all(path.exists() for path in paths),
        "required_figures_nonempty": all(path.exists() and path.stat().st_size > 0 for path in paths),
        "figure_role_alias": "N8A1_FIGURE_OUTPUT_DIR",
        "runtime_only": True,
        "paper_performance_claim": False,
    }
