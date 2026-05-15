"""N8J final feedback validation plots.

中文说明：图像只写 runtime-only figure 目录，明确 selected feedback 与 baseline
的 evaluation namespace，不做 paper claim。
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

from .feedback_state_types import angle_delta_deg, norm
from .fgo_feedback_final_runner import N8JFinalRunBundle
from .fgo_feedback_visual_loader import read_csv_rows, safe_float, write_json


REQUIRED_N8J_FIGURES = [
    "final_selected_feedback_window_timeline.png",
    "final_selected_feedback_accept_reject_timeline.png",
    "final_selected_feedback_correction_norms.png",
    "final_selected_feedback_reject_reasons.png",
    "baseline_vs_selected_feedback_horizontal_trajectory.png",
    "baseline_vs_selected_feedback_horizontal_error.png",
    "baseline_vs_selected_feedback_up_error.png",
    "baseline_vs_selected_feedback_yaw_error.png",
    "baseline_vs_selected_feedback_roll_pitch_error.png",
    "selected_feedback_minus_baseline_delta_time.png",
    "selected_vs_default_gate_metric_delta.png",
    "reject_all_sanity_vs_baseline.png",
    "final_feedback_policy_summary_panel.png",
    "n8j_decision_panel.png",
]


def generate_final_validation_figures(
    *,
    bundle: N8JFinalRunBundle,
    selected_policy: dict[str, Any],
    variant_summaries: dict[str, Any],
    evaluation_report: dict[str, Any],
    final_manifest: dict[str, Any],
    sanity_report: dict[str, Any] | None,
    decision_report: dict[str, Any] | None,
    figure_output_dir: str | Path,
) -> dict[str, Any]:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    out = Path(figure_output_dir)
    out.mkdir(parents=True, exist_ok=True)
    selected_id = "n8j_selected_conservative_feedback"
    baseline_rows = read_csv_rows(bundle.output_root / "variants" / "baseline_no_feedback" / "run" / "EVAL_NAV.csv")
    selected_rows = read_csv_rows(bundle.output_root / "variants" / selected_id / "run" / "EVAL_NAV.csv")
    default_rows = read_csv_rows(bundle.output_root / "variants" / "default_gate_feedback_for_reference" / "run" / "EVAL_NAV.csv")
    reject_rows = read_csv_rows(bundle.output_root / "variants" / "reject_all_sanity" / "run" / "EVAL_NAV.csv")
    selected_trace = bundle.trace_rows.get(selected_id, [])
    selected_window = bundle.window_reports.get(selected_id, {})
    selected_gate = bundle.gate_reports.get(selected_id, {})
    generated: list[dict[str, Any]] = []

    feedback_time = [safe_float(value) for value in selected_window.get("feedback_time", [])]
    window_start = [safe_float(value) for value in selected_window.get("window_start", [])]
    window_end = [safe_float(value) for value in selected_window.get("window_end", [])]
    generated.append(_line(plt, out, "final_selected_feedback_window_timeline.png", [
        ("window start", feedback_time, window_start),
        ("window end", feedback_time, window_end),
    ], "Selected feedback window timeline", "feedback time (s)", "window time (s)"))

    trace_time = _times(selected_trace)
    accepted = [safe_float(row.get("accepted")) for row in selected_trace]
    rejected = [1.0 - value for value in accepted]
    generated.append(_line(plt, out, "final_selected_feedback_accept_reject_timeline.png", [
        ("accepted", trace_time, accepted),
        ("rejected", trace_time, rejected),
    ], "Selected feedback accept/reject timeline", "time (s)", "gate state (0/1)"))

    generated.append(_line(plt, out, "final_selected_feedback_correction_norms.png", [
        ("velocity", trace_time, [safe_float(row.get("velocity_norm_mps")) for row in selected_trace]),
        ("attitude", trace_time, [safe_float(row.get("attitude_norm_deg")) for row in selected_trace]),
        ("position residual proxy", trace_time, [safe_float(row.get("position_norm_m")) for row in selected_trace]),
    ], "Selected feedback correction norms", "time (s)", "norm (m/s, deg, m)"))

    reasons = selected_gate.get("reject_reasons", {}) or {"none": 0}
    generated.append(_bar(plt, out, "final_selected_feedback_reject_reasons.png", list(reasons), [
        ("reject count", [safe_float(value) for value in reasons.values()]),
    ], "Selected feedback reject reasons", "reason", "count"))

    base_ne = _local_xy(baseline_rows)
    selected_ne = _local_xy(selected_rows, origin=baseline_rows[0] if baseline_rows else None)
    generated.append(_line(plt, out, "baseline_vs_selected_feedback_horizontal_trajectory.png", [
        ("baseline", _downsample(base_ne["east"]), _downsample(base_ne["north"])),
        ("selected feedback", _downsample(selected_ne["east"]), _downsample(selected_ne["north"])),
    ], "Baseline vs selected feedback horizontal trajectory", "east (m)", "north (m)"))

    delta = _nav_delta(baseline_rows, selected_rows)
    generated.append(_line(plt, out, "baseline_vs_selected_feedback_horizontal_error.png", [
        ("selected feedback", _downsample(delta["time"]), _downsample(delta["horizontal_m"])),
    ], "Selected feedback minus baseline horizontal delta", "time (s)", "horizontal delta (m)"))
    generated.append(_line(plt, out, "baseline_vs_selected_feedback_up_error.png", [
        ("selected feedback", _downsample(delta["time"]), _downsample(delta["up_m"])),
    ], "Selected feedback minus baseline up delta", "time (s)", "up delta (m)"))
    generated.append(_line(plt, out, "baseline_vs_selected_feedback_yaw_error.png", [
        ("selected feedback", _downsample(delta["time"]), _downsample(delta["yaw_deg"])),
    ], "Selected feedback minus baseline yaw delta", "time (s)", "yaw delta (deg)"))
    generated.append(_line(plt, out, "baseline_vs_selected_feedback_roll_pitch_error.png", [
        ("selected feedback", _downsample(delta["time"]), _downsample(delta["roll_pitch_deg"])),
    ], "Selected feedback minus baseline roll/pitch delta", "time (s)", "roll/pitch delta (deg)"))
    generated.append(_line(plt, out, "selected_feedback_minus_baseline_delta_time.png", [
        ("horizontal", _downsample(delta["time"]), _downsample(delta["horizontal_m"])),
        ("yaw", _downsample(delta["time"]), _downsample(delta["yaw_deg"])),
        ("roll/pitch", _downsample(delta["time"]), _downsample(delta["roll_pitch_deg"])),
    ], "Selected feedback delta time series", "time (s)", "evaluation-only delta"))

    default_delta = _nav_delta(baseline_rows, default_rows)
    generated.append(_bar(plt, out, "selected_vs_default_gate_metric_delta.png", ["selected", "default"], [
        ("horizontal p95 m", [_p95(delta["horizontal_m"]), _p95(default_delta["horizontal_m"])]),
        ("yaw p95 deg", [_p95(delta["yaw_deg"]), _p95(default_delta["yaw_deg"])]),
    ], "Selected vs default gate metric delta", "variant", "evaluation-only p95 delta"))

    reject_delta = _nav_delta(baseline_rows, reject_rows)
    generated.append(_line(plt, out, "reject_all_sanity_vs_baseline.png", [
        ("reject-all horizontal", _downsample(reject_delta["time"]), _downsample(reject_delta["horizontal_m"])),
        ("reject-all yaw", _downsample(reject_delta["time"]), _downsample(reject_delta["yaw_deg"])),
    ], "Reject-all sanity vs baseline", "time (s)", "evaluation-only delta"))

    generated.append(_panel(plt, out, "final_feedback_policy_summary_panel.png", [
        f"policy: {selected_policy.get('policy_name')}",
        f"mode: {selected_policy.get('feedback_mode')}",
        f"gate: {selected_policy.get('gate_policy')}",
        f"covariance: {selected_policy.get('covariance_policy')}",
        "position feedback: disabled",
        "EKF update: pseudo-measurement feedback",
        "no output substitution / no future data",
        "BY2 engineering validation only",
    ]))
    decision = decision_report or {"status": "pending_n8j_decision", "recommended_next_stage": ""}
    generated.append(_panel(plt, out, "n8j_decision_panel.png", [
        f"decision: {decision.get('status')}",
        f"next: {decision.get('recommended_next_stage')}",
        f"accepted/rejected: {final_manifest.get('accepted')} / {final_manifest.get('rejected')}",
        f"sanity: {(sanity_report or {}).get('all_checks_passed')}",
        "runtime NAV/STD/EVAL generated, not committed",
        "no trace/final_v23 tuning",
        "no paper performance claim",
    ]))

    by_name = {item["filename"]: item for item in generated}
    required = []
    for name in REQUIRED_N8J_FIGURES:
        path = out / name
        required.append(
            {
                "filename": name,
                "path_role": "n8j_figure_output_dir",
                "present": path.exists(),
                "nonempty": path.exists() and path.stat().st_size > 0,
                "plotted_series_count": by_name.get(name, {}).get("plotted_series_count", 0),
                "metric_namespace": "feedback_vs_baseline_delta" if "baseline" in name or "delta" in name else "feedback_runtime_diagnostics",
            }
        )
    return {
        "stage": "N8J",
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


def _line(plt: Any, out: Path, filename: str, series: list[tuple[str, list[float], list[float]]], title: str, xlabel: str, ylabel: str) -> dict[str, Any]:
    fig, ax = plt.subplots(figsize=(10, 4.8))
    plotted = 0
    for label, xs, ys in series:
        count = min(len(xs), len(ys))
        if count <= 0:
            continue
        ax.plot(xs[:count], ys[:count], label=label, linewidth=1.2)
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
    return {"filename": filename, "plotted_series_count": plotted}


def _bar(plt: Any, out: Path, filename: str, labels: list[str], series: list[tuple[str, list[float]]], title: str, xlabel: str, ylabel: str) -> dict[str, Any]:
    fig, ax = plt.subplots(figsize=(10, 4.8))
    x = list(range(len(labels)))
    width = 0.8 / max(1, len(series))
    for index, (label, values) in enumerate(series):
        offsets = [value - 0.4 + width * index + width / 2.0 for value in x]
        ax.bar(offsets, values, width=width, label=label)
    ax.set_title(title)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=25, ha="right")
    ax.legend(loc="best")
    ax.grid(True, axis="y", alpha=0.3)
    fig.tight_layout()
    path = out / filename
    fig.savefig(path, dpi=140)
    plt.close(fig)
    return {"filename": filename, "plotted_series_count": len(series)}


def _panel(plt: Any, out: Path, filename: str, lines: list[str]) -> dict[str, Any]:
    fig, ax = plt.subplots(figsize=(10, 4.8))
    ax.axis("off")
    ax.text(0.02, 0.94, "\n".join(lines), va="top", ha="left", fontsize=12)
    fig.tight_layout()
    path = out / filename
    fig.savefig(path, dpi=140)
    plt.close(fig)
    return {"filename": filename, "plotted_series_count": 1}


def _times(rows: list[dict[str, Any]]) -> list[float]:
    return [safe_float(row.get("update_time", row.get("observation_time", row.get("time")))) for row in rows]


def _local_xy(rows: list[dict[str, Any]], origin: dict[str, Any] | None = None) -> dict[str, list[float]]:
    if not rows:
        return {"north": [], "east": []}
    origin = origin or rows[0]
    lat0 = math.radians(safe_float(origin.get("lat_deg")))
    north = []
    east = []
    for row in rows:
        north.append(math.radians(safe_float(row.get("lat_deg")) - safe_float(origin.get("lat_deg"))) * 6378137.0)
        east.append(math.radians(safe_float(row.get("lon_deg")) - safe_float(origin.get("lon_deg"))) * 6378137.0 * math.cos(lat0))
    return {"north": north, "east": east}


def _nav_delta(baseline: list[dict[str, Any]], feedback: list[dict[str, Any]]) -> dict[str, list[float]]:
    count = min(len(baseline), len(feedback))
    out = {"time": [], "horizontal_m": [], "up_m": [], "yaw_deg": [], "roll_pitch_deg": []}
    for left, right in zip(baseline[:count], feedback[:count]):
        out["time"].append(safe_float(right.get("time", left.get("time"))))
        out["horizontal_m"].append(norm([safe_float(right.get("lat_deg")) - safe_float(left.get("lat_deg")), safe_float(right.get("lon_deg")) - safe_float(left.get("lon_deg"))]) * 111_000.0)
        out["up_m"].append(safe_float(right.get("height_m")) - safe_float(left.get("height_m")))
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


def _p95(values: list[float]) -> float:
    clean = sorted(value for value in values if math.isfinite(value))
    if not clean:
        return 0.0
    return clean[int(round((len(clean) - 1) * 0.95))]


def write_final_figure_manifest(path: str | Path, manifest: dict[str, Any]) -> None:
    write_json(path, manifest)
