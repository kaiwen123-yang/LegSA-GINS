"""N8G feedback visual plots.

中文说明：图像只写 runtime-only 目录，不提交，不作为 solver 输入。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


REQUIRED_N8G_FIGURES = [
    "feedback_window_timeline.png",
    "feedback_accept_reject_timeline.png",
    "feedback_position_correction_norm.png",
    "feedback_velocity_correction_norm.png",
    "feedback_attitude_correction_norm.png",
    "baseline_vs_feedback_horizontal_trajectory.png",
    "baseline_vs_feedback_horizontal_error.png",
    "baseline_vs_feedback_yaw_error.png",
    "baseline_vs_feedback_roll_pitch_error.png",
    "feedback_residual_by_state_block.png",
    "feedback_gate_reject_reasons.png",
    "n8g_decision_panel.png",
]


def _plot(path: Path, title: str, values: list[float], *, ylabel: str = "value") -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    path.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(8, 4), dpi=120)
    ax.plot(range(len(values)), values or [0.0], linewidth=1.4)
    ax.set_title(title)
    ax.set_xlabel("index")
    ax.set_ylabel(ylabel)
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def generate_n8g_figures(
    *,
    figure_output_dir: str | Path,
    window_report: dict[str, Any],
    gate_report: dict[str, Any],
    evaluation_report: dict[str, Any],
    decision_report: dict[str, Any],
) -> dict[str, Any]:
    out = Path(figure_output_dir)
    feedback_times = [float(v) for v in window_report.get("feedback_time", [])]
    accept_count = int(gate_report.get("accept_count", 0) or 0)
    reject_count = int(gate_report.get("reject_count", 0) or 0)
    correction = gate_report.get("correction_norm_stats", {})
    position_stats = correction.get("position_m", {}) if isinstance(correction, dict) else {}
    velocity_stats = correction.get("velocity_mps", {}) if isinstance(correction, dict) else {}
    attitude_stats = correction.get("attitude_deg", {}) if isinstance(correction, dict) else {}
    variant_results = evaluation_report.get("variant_results", [])
    first_delta = variant_results[0].get("feedback_vs_baseline_delta", {}) if variant_results else {}
    horizontal = first_delta.get("horizontal_m", {}) if isinstance(first_delta, dict) else {}
    yaw = first_delta.get("yaw_deg", {}) if isinstance(first_delta, dict) else {}
    roll_pitch = first_delta.get("roll_pitch_deg", {}) if isinstance(first_delta, dict) else {}
    plot_values = {
        "feedback_window_timeline.png": feedback_times,
        "feedback_accept_reject_timeline.png": [accept_count, reject_count],
        "feedback_position_correction_norm.png": list(position_stats.values()) or [0.0],
        "feedback_velocity_correction_norm.png": list(velocity_stats.values()) or [0.0],
        "feedback_attitude_correction_norm.png": list(attitude_stats.values()) or [0.0],
        "baseline_vs_feedback_horizontal_trajectory.png": [float(horizontal.get("p50", 0.0)), float(horizontal.get("p95", 0.0))],
        "baseline_vs_feedback_horizontal_error.png": [float(horizontal.get("max", 0.0))],
        "baseline_vs_feedback_yaw_error.png": list(yaw.values()) or [0.0],
        "baseline_vs_feedback_roll_pitch_error.png": list(roll_pitch.values()) or [0.0],
        "feedback_residual_by_state_block.png": [
            float(position_stats.get("p95", 0.0)),
            float(velocity_stats.get("p95", 0.0)),
            float(attitude_stats.get("p95", 0.0)),
        ],
        "feedback_gate_reject_reasons.png": list((gate_report.get("reject_reasons") or {"none": 0}).values()),
        "n8g_decision_panel.png": [1.0 if decision_report.get("status") == "fgo_feedback_ekf_foundation_ready" else 0.0],
    }
    for name in REQUIRED_N8G_FIGURES:
        _plot(out / name, name.replace("_", " ").replace(".png", ""), [float(v) for v in plot_values[name]])
    files = [out / name for name in REQUIRED_N8G_FIGURES]
    manifest = {
        "stage": "N8G",
        "figure_count_total": len(files),
        "required_figure_count": len(REQUIRED_N8G_FIGURES),
        "all_required_figures_present": all(path.exists() and path.stat().st_size > 0 for path in files),
        "figures": [{"name": path.name, "role": "runtime_only", "nonempty": path.stat().st_size > 0} for path in files],
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "paper_performance_claim": False,
    }
    (out / "N8G_FIGURE_MANIFEST.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest
