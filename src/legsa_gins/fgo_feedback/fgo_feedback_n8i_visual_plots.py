"""N8I feedback ablation visual plots.

中文说明：图像只写 runtime-only figure 目录，用于 gate/cov/window/mode 消融复核，
不形成论文性能宣称。
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

from .feedback_state_types import angle_delta_deg, norm
from .fgo_feedback_policy_ablation_runner import N8IPolicyRunBundle
from .fgo_feedback_visual_loader import read_csv_rows, safe_float, safe_int, write_json


REQUIRED_N8I_FIGURES = [
    "feedback_policy_accept_reject_bar.png",
    "feedback_gate_threshold_sweep.png",
    "feedback_covariance_inflation_sweep.png",
    "feedback_window_policy_comparison.png",
    "feedback_mode_metric_delta_bar.png",
    "feedback_attitude_spike_timeline.png",
    "conservative_gate_reject_timeline.png",
    "baseline_vs_selected_feedback_horizontal_error.png",
    "baseline_vs_selected_feedback_yaw_error.png",
    "baseline_vs_selected_feedback_roll_pitch_error.png",
    "selected_feedback_correction_norms.png",
    "n8i_decision_panel.png",
]


def generate_n8i_figures(
    *,
    bundle: N8IPolicyRunBundle,
    gate_review: dict[str, Any],
    covariance_review: dict[str, Any],
    window_review: dict[str, Any],
    mode_summaries: dict[str, Any],
    attitude_spike_review: dict[str, Any],
    decision_report: dict[str, Any],
    figure_output_dir: str | Path,
) -> dict[str, Any]:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    out = Path(figure_output_dir)
    out.mkdir(parents=True, exist_ok=True)
    generated: list[dict[str, Any]] = []

    gate_entries = gate_review.get("gate_sweep", [])
    labels = [_short(item.get("policy_id", "")) for item in gate_entries]
    generated.append(_bar(plt, out, "feedback_policy_accept_reject_bar.png", labels, [
        ("accept", [safe_float(item.get("pre_runtime_accept_count")) for item in gate_entries]),
        ("reject", [safe_float(item.get("pre_runtime_reject_count")) for item in gate_entries]),
    ], "Gate accept/reject by policy", "policy", "count"))

    generated.append(_line(plt, out, "feedback_gate_threshold_sweep.png", [
        ("att threshold deg", list(range(len(gate_entries))), [safe_float(item.get("thresholds", {}).get("max_attitude_correction_deg")) for item in gate_entries]),
        ("reject count", list(range(len(gate_entries))), [safe_float(item.get("pre_runtime_reject_count")) for item in gate_entries]),
    ], "Gate threshold sweep", "policy index", "threshold / count"))

    cov_entries = covariance_review.get("covariance_sweep", [])
    cov_labels = [_short(item.get("policy_id", "")) for item in cov_entries]
    generated.append(_bar(plt, out, "feedback_covariance_inflation_sweep.png", cov_labels, [
        ("attitude spikes", [safe_float(item.get("attitude_spike_count_over_4deg")) for item in cov_entries]),
        ("att std p95", [safe_float(item.get("std_att_stats", {}).get("p95")) for item in cov_entries]),
    ], "Covariance inflation sweep", "policy", "spikes / std (deg)"))

    window_entries = window_review.get("window_policy_sweep", [])
    window_labels = [_short(item.get("policy_id", "")) for item in window_entries]
    generated.append(_bar(plt, out, "feedback_window_policy_comparison.png", window_labels, [
        ("window count", [safe_float(item.get("window_count")) for item in window_entries]),
        ("runtime cost proxy", [safe_float(item.get("runtime_cost_proxy")) for item in window_entries]),
    ], "Window policy comparison", "window policy", "count / cost"))

    mode_entries = mode_summaries.get("variants", [])
    mode_labels = [_short(item.get("policy_id", "")) for item in mode_entries]
    generated.append(_bar(plt, out, "feedback_mode_metric_delta_bar.png", mode_labels, [
        ("horizontal p95 m", [safe_float(item.get("baseline_delta", {}).get("horizontal_m", {}).get("p95")) for item in mode_entries]),
        ("yaw p95 deg", [safe_float(item.get("baseline_delta", {}).get("yaw_deg", {}).get("p95")) for item in mode_entries]),
    ], "Mode metric delta vs baseline", "mode", "evaluation-only delta"))

    default_rows = bundle.trace_rows.get("primary_horizontal_velocity_attitude_default", [])
    generated.append(_line(plt, out, "feedback_attitude_spike_timeline.png", [
        ("attitude correction", _times(default_rows), [safe_float(row.get("attitude_norm_deg")) for row in default_rows]),
        ("4 deg threshold", _times(default_rows), [4.0 for _ in default_rows]),
    ], "Attitude correction spike timeline", "time (s)", "attitude correction (deg)"))

    conservative_gate = gate_review.get("gate_sweep", [])
    generated.append(_bar(plt, out, "conservative_gate_reject_timeline.png", labels, [
        ("reject count", [safe_float(item.get("pre_runtime_reject_count")) for item in conservative_gate]),
    ], "Conservative gate reject summary", "policy", "reject count"))

    selected_policy = decision_report.get("selected_feedback_policy", "primary_hv_att_conservative_gate")
    baseline_rows = read_csv_rows(bundle.output_root / "variants" / "baseline_no_feedback" / "run" / "EVAL_NAV.csv")
    selected_rows = read_csv_rows(bundle.output_root / "variants" / selected_policy / "run" / "EVAL_NAV.csv")
    delta = _nav_delta(baseline_rows, selected_rows)
    generated.append(_line(plt, out, "baseline_vs_selected_feedback_horizontal_error.png", [
        ("selected feedback", _downsample(delta["time"]), _downsample(delta["horizontal_m"])),
    ], "Selected feedback minus baseline horizontal delta", "time (s)", "horizontal delta (m)"))
    generated.append(_line(plt, out, "baseline_vs_selected_feedback_yaw_error.png", [
        ("selected feedback", _downsample(delta["time"]), _downsample(delta["yaw_deg"])),
    ], "Selected feedback minus baseline yaw delta", "time (s)", "yaw delta (deg)"))
    generated.append(_line(plt, out, "baseline_vs_selected_feedback_roll_pitch_error.png", [
        ("selected feedback", _downsample(delta["time"]), _downsample(delta["roll_pitch_deg"])),
    ], "Selected feedback minus baseline roll/pitch delta", "time (s)", "roll/pitch delta (deg)"))

    selected_trace = bundle.trace_rows.get(selected_policy, [])
    generated.append(_line(plt, out, "selected_feedback_correction_norms.png", [
        ("velocity", _times(selected_trace), [safe_float(row.get("velocity_norm_mps")) for row in selected_trace]),
        ("attitude", _times(selected_trace), [safe_float(row.get("attitude_norm_deg")) for row in selected_trace]),
    ], "Selected feedback correction norms", "time (s)", "norm (m/s or deg)"))

    generated.append(_panel(plt, out, "n8i_decision_panel.png", [
        f"decision: {decision_report.get('status')}",
        f"next: {decision_report.get('recommended_next_stage')}",
        f"gate: {decision_report.get('selected_gate_policy')}",
        f"covariance: {decision_report.get('selected_covariance_policy')}",
        f"window: {decision_report.get('selected_window_policy')}",
        "no output substitution / no direct NAV override",
        "no trace/final_v23 tuning / no paper claim",
    ]))

    by_name = {item["filename"]: item for item in generated}
    required = []
    for name in REQUIRED_N8I_FIGURES:
        path = out / name
        required.append(
            {
                "filename": name,
                "path_role": "n8i_figure_output_dir",
                "present": path.exists(),
                "nonempty": path.exists() and path.stat().st_size > 0,
                "plotted_series_count": by_name.get(name, {}).get("plotted_series_count", 0),
            }
        )
    return {
        "stage": "N8I",
        "figure_count_total": len(required),
        "required_figures": required,
        "all_required_figures_present": all(item["present"] for item in required),
        "all_required_figures_nonempty": all(item["nonempty"] for item in required),
        "no_output_substitution": True,
        "no_direct_nav_override": True,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "paper_performance_claim": False,
    }


def _bar(plt: Any, out: Path, filename: str, labels: list[str], series: list[tuple[str, list[float]]], title: str, xlabel: str, ylabel: str) -> dict[str, Any]:
    fig, ax = plt.subplots(figsize=(10, 4.8))
    x = list(range(len(labels)))
    width = 0.8 / max(1, len(series))
    for idx, (name, values) in enumerate(series):
        offsets = [value - 0.4 + width * idx + width / 2.0 for value in x]
        ax.bar(offsets, values, width=width, label=name)
    ax.set_title(title)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=30, ha="right", fontsize=8)
    ax.legend(loc="best")
    ax.grid(True, axis="y", alpha=0.3)
    fig.tight_layout()
    path = out / filename
    fig.savefig(path, dpi=140)
    plt.close(fig)
    return {"filename": filename, "plotted_series_count": len(series), "nonempty": path.stat().st_size > 0}


def _line(plt: Any, out: Path, filename: str, series: list[tuple[str, list[float], list[float]]], title: str, xlabel: str, ylabel: str) -> dict[str, Any]:
    fig, ax = plt.subplots(figsize=(10, 4.8))
    plotted = 0
    for name, xs, ys in series:
        count = min(len(xs), len(ys))
        if count <= 0:
            continue
        ax.plot(xs[:count], ys[:count], label=name, linewidth=1.3)
        plotted += 1
    ax.set_title(title)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    if plotted:
        ax.legend(loc="best")
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    path = out / filename
    fig.savefig(path, dpi=140)
    plt.close(fig)
    return {"filename": filename, "plotted_series_count": plotted, "nonempty": path.stat().st_size > 0}


def _panel(plt: Any, out: Path, filename: str, lines: list[str]) -> dict[str, Any]:
    fig, ax = plt.subplots(figsize=(10, 4.8))
    ax.axis("off")
    ax.text(0.02, 0.94, "\n".join(lines), va="top", ha="left", fontsize=12)
    fig.tight_layout()
    path = out / filename
    fig.savefig(path, dpi=140)
    plt.close(fig)
    return {"filename": filename, "plotted_series_count": 1, "nonempty": path.stat().st_size > 0}


def _times(rows: list[dict[str, Any]]) -> list[float]:
    return [safe_float(row.get("update_time", row.get("observation_time", row.get("time")))) for row in rows]


def _nav_delta(baseline: list[dict[str, Any]], feedback: list[dict[str, Any]]) -> dict[str, list[float]]:
    count = min(len(baseline), len(feedback))
    out = {"time": [], "horizontal_m": [], "yaw_deg": [], "roll_pitch_deg": []}
    for left, right in zip(baseline[:count], feedback[:count]):
        out["time"].append(safe_float(right.get("time", left.get("time"))))
        out["horizontal_m"].append(norm([safe_float(right.get("lat_deg")) - safe_float(left.get("lat_deg")), safe_float(right.get("lon_deg")) - safe_float(left.get("lon_deg"))]) * 111_000.0)
        out["yaw_deg"].append(abs(angle_delta_deg(safe_float(right.get("yaw_deg")), safe_float(left.get("yaw_deg")))))
        out["roll_pitch_deg"].append(
            norm(
                [
                    angle_delta_deg(safe_float(right.get("roll_deg")), safe_float(left.get("roll_deg"))),
                    angle_delta_deg(safe_float(right.get("pitch_deg")), safe_float(left.get("pitch_deg"))),
                ]
            )
        )
    return out


def _downsample(values: list[float], limit: int = 1200) -> list[float]:
    if len(values) <= limit:
        return values
    step = max(1, math.ceil(len(values) / limit))
    return values[::step]


def _short(label: str) -> str:
    return str(label).replace("primary_", "p_").replace("horizontal_velocity_attitude", "hv_att").replace("conservative", "cons")


def write_n8i_figure_manifest(path: str | Path, manifest: dict[str, Any]) -> None:
    write_json(path, manifest)
