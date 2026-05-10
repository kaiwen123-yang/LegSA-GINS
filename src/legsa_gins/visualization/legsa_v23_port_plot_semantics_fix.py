"""Generate N4H4E1 corrected visual figures.

中文说明：本模块修正误差向量云图和 STD/3sigma 图语义；不裁剪 epoch，
不改 NAV/STD runtime 数据，不做 paper performance claim。
"""

from __future__ import annotations

import json
import math
import statistics
from pathlib import Path
from typing import Any

from legsa_gins.visualization.legsa_v23_port_std_unit_audit import normalize_attitude_std_for_plot
from legsa_gins.visualization.legsa_v23_port_visual_plots import (
    _load_matplotlib,
    _matched_std_rows,
    _rel_times,
    _sample_xy,
    _save_line,
    build_visual_error_bundle,
)


CORRECTED_FIGURES = [
    "04_port_finalv23_parity/port_minus_finalv23_horizontal_diff_scatter.png",
    "02_position_errors/horizontal_error_vector_cloud_to_reference.png",
    "04_port_finalv23_parity/port_minus_finalv23_up_diff_full_with_initial_marker.png",
    "04_port_finalv23_parity/port_minus_finalv23_up_diff_first5s_zoom.png",
    "07_std_consistency/error_vs_3sigma_horizontal_corrected.png",
    "07_std_consistency/error_vs_3sigma_roll_corrected.png",
    "07_std_consistency/error_vs_3sigma_pitch_corrected.png",
    "07_std_consistency/error_vs_3sigma_yaw_corrected.png",
    "07_std_consistency/port_std_attitude_time_corrected.png",
    "07_std_consistency/finalv23_std_attitude_time_corrected.png",
]


def _write_json(path: str | Path, data: dict[str, Any]) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _save_xy_scatter(plt, path: Path, series: list[tuple[str, list[float], list[float]]], title: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(6, 6))
    for label, east, north in series:
        sx, sy = _sample_xy(east, north)
        ax.scatter(sx, sy, s=4, alpha=0.55, label=label)
    ax.axhline(0.0, linewidth=0.6, alpha=0.55)
    ax.axvline(0.0, linewidth=0.6, alpha=0.55)
    ax.set_aspect("equal", adjustable="datalim")
    ax.set_title(title)
    ax.set_xlabel("east error (m)")
    ax.set_ylabel("north error (m)")
    ax.grid(True, linewidth=0.3, alpha=0.45)
    if len(series) > 1:
        ax.legend(loc="best", fontsize=8)
    fig.tight_layout()
    fig.savefig(path, dpi=140)
    plt.close(fig)


def _save_line_with_first_marker(plt, path: Path, times: list[float], values: list[float], title: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(9, 4.8))
    ax.plot(*_sample_xy(times, values), linewidth=1.0, label="up diff")
    if times and values:
        ax.scatter([times[0]], [values[0]], s=28, label="first sample")
    ax.set_title(title)
    ax.set_xlabel("time since start (s)")
    ax.set_ylabel("up diff (m)")
    ax.grid(True, linewidth=0.3, alpha=0.45)
    ax.legend(loc="best", fontsize=8)
    fig.tight_layout()
    fig.savefig(path, dpi=140)
    plt.close(fig)


def _values(rows: list[dict[str, Any]], key: str) -> list[float]:
    return [float(row[key]) for row in rows if isinstance(row.get(key), (int, float)) and math.isfinite(float(row[key]))]


def _ratio_within(error_values: list[float], sigma_values: list[float]) -> float | None:
    pairs = [(abs(e), s) for e, s in zip(error_values, sigma_values) if math.isfinite(e) and math.isfinite(s) and s > 0.0]
    if not pairs:
        return None
    return sum(1 for e, s in pairs if e <= s) / len(pairs)


def detect_vector_line_plot_misuse(figure_manifest: dict[str, Any]) -> dict[str, Any]:
    names = figure_manifest.get("figure_paths", [])
    suspect = [name for name in names if name.endswith("trajectory_xy_error_to_reference.png") or name.endswith("trajectory_xy_port_minus_finalv23_zoom.png")]
    return {
        "vector_line_plot_misuse_detected": bool(suspect),
        "suspect_legacy_figures": suspect,
    }


def analyze_up_diff_initial_step(parity_errors: list[dict[str, float]]) -> dict[str, Any]:
    values = [float(row["up_error_m"]) for row in parity_errors]
    if not values:
        return {
            "first_sample_up_diff": None,
            "second_sample_up_diff": None,
            "median_up_diff": None,
            "up_diff_step_suspect": False,
            "likely_initialization_or_alignment_offset": "evidence_missing",
        }
    first = values[0]
    second = values[1] if len(values) > 1 else None
    median = statistics.median(values)
    step = abs((second if second is not None else first) - first)
    return {
        "first_sample_up_diff": first,
        "second_sample_up_diff": second,
        "median_up_diff": median,
        "up_diff_step_suspect": abs(first - median) > 0.03 or step > 0.03,
        "likely_initialization_or_alignment_offset": abs(median) <= 0.1,
    }


def _std_sigma_series(
    std_rows: list[dict[str, Any]],
    errors: list[dict[str, float]],
    key: str,
    *,
    horizontal: bool = False,
) -> list[float]:
    matched = _matched_std_rows(std_rows, [float(row["timestamp"]) for row in errors])
    values = []
    for std in matched:
        if not std:
            values.append(0.0)
        elif horizontal:
            values.append(3.0 * math.hypot(float(std.get("std_pos_n_m", 0.0)), float(std.get("std_pos_e_m", 0.0))))
        else:
            values.append(3.0 * float(std.get(key, 0.0)))
    return values


def generate_plot_semantics_fix(
    *,
    inputs: dict[str, Any],
    std_unit_report: dict[str, Any],
    figure_output_dir: str | Path,
    report_output_dir: str | Path,
    legacy_figure_manifest: dict[str, Any] | None = None,
) -> dict[str, Any]:
    plt = _load_matplotlib()
    figure_root = Path(figure_output_dir)
    figure_root.mkdir(parents=True, exist_ok=True)
    errors = build_visual_error_bundle(inputs)
    parity = errors["port_vs_final_v23"]
    pvst = errors["port_vs_trace"]
    fvst = errors["final_v23_vs_trace"]
    generated: list[str] = []

    def add(rel: str) -> Path:
        generated.append(rel)
        return figure_root / rel

    _save_xy_scatter(
        plt,
        add("04_port_finalv23_parity/port_minus_finalv23_horizontal_diff_scatter.png"),
        [("port - dual_final_v23", [row["east_error_m"] for row in parity], [row["north_error_m"] for row in parity])],
        "port minus dual_final_v23 horizontal diff vector cloud",
    )
    _save_xy_scatter(
        plt,
        add("02_position_errors/horizontal_error_vector_cloud_to_reference.png"),
        [
            ("port error", [row["east_error_m"] for row in pvst], [row["north_error_m"] for row in pvst]),
            ("dual_final_v23 error", [row["east_error_m"] for row in fvst], [row["north_error_m"] for row in fvst]),
        ],
        "horizontal error vector cloud to reference",
    )

    t_parity = _rel_times(parity)
    up_values = [row["up_error_m"] for row in parity]
    _save_line_with_first_marker(
        plt,
        add("04_port_finalv23_parity/port_minus_finalv23_up_diff_full_with_initial_marker.png"),
        t_parity,
        up_values,
        "port minus dual_final_v23 up diff full series with first sample",
    )
    zoom_pairs = [(time, value) for time, value in zip(t_parity, up_values) if time <= 5.0]
    _save_line_with_first_marker(
        plt,
        add("04_port_finalv23_parity/port_minus_finalv23_up_diff_first5s_zoom.png"),
        [item[0] for item in zoom_pairs],
        [item[1] for item in zoom_pairs],
        "port minus dual_final_v23 up diff first 5s zoom",
    )

    port_std = normalize_attitude_std_for_plot(inputs.get("port_std_rows", []), std_unit_report.get("port_attitude_std_unit", "deg"))
    final_std = normalize_attitude_std_for_plot(inputs.get("final_v23_std_rows", []), std_unit_report.get("finalv23_attitude_std_unit", "deg"))
    t_pvst = _rel_times(pvst)
    t_port_std = _rel_times(port_std)
    t_final_std = _rel_times(final_std)
    _save_line(
        plt,
        add("07_std_consistency/port_std_attitude_time_corrected.png"),
        [("roll", t_port_std, _values(port_std, "std_roll_deg")), ("pitch", t_port_std, _values(port_std, "std_pitch_deg")), ("yaw", t_port_std, _values(port_std, "std_yaw_deg"))],
        "port STD attitude corrected to deg",
        "STD (deg)",
    )
    _save_line(
        plt,
        add("07_std_consistency/finalv23_std_attitude_time_corrected.png"),
        [("roll", t_final_std, _values(final_std, "std_roll_deg")), ("pitch", t_final_std, _values(final_std, "std_pitch_deg")), ("yaw", t_final_std, _values(final_std, "std_yaw_deg"))],
        "dual_final_v23 STD attitude in deg",
        "STD (deg)",
    )

    sigma_h = _std_sigma_series(port_std, pvst, "std_pos_n_m", horizontal=True)
    sigma_roll = _std_sigma_series(port_std, pvst, "std_roll_deg")
    sigma_pitch = _std_sigma_series(port_std, pvst, "std_pitch_deg")
    sigma_yaw = _std_sigma_series(port_std, pvst, "std_yaw_deg")
    _save_line(plt, add("07_std_consistency/error_vs_3sigma_horizontal_corrected.png"), [("horizontal error", t_pvst, [row["horizontal_error_m"] for row in pvst]), ("3sigma H", t_pvst, sigma_h)], "error vs 3sigma horizontal corrected", "m")
    _save_line(plt, add("07_std_consistency/error_vs_3sigma_roll_corrected.png"), [("roll error abs", t_pvst, [abs(row["roll_error_deg"]) for row in pvst]), ("3sigma roll", t_pvst, sigma_roll)], "error vs 3sigma roll corrected", "deg")
    _save_line(plt, add("07_std_consistency/error_vs_3sigma_pitch_corrected.png"), [("pitch error abs", t_pvst, [abs(row["pitch_error_deg"]) for row in pvst]), ("3sigma pitch", t_pvst, sigma_pitch)], "error vs 3sigma pitch corrected", "deg")
    _save_line(plt, add("07_std_consistency/error_vs_3sigma_yaw_corrected.png"), [("yaw error abs", t_pvst, [abs(row["yaw_error_deg"]) for row in pvst]), ("3sigma yaw", t_pvst, sigma_yaw)], "error vs 3sigma yaw corrected", "deg")

    up_report = analyze_up_diff_initial_step(parity)
    in_3sigma = {
        "horizontal_in_3sigma_ratio": _ratio_within([row["horizontal_error_m"] for row in pvst], sigma_h),
        "roll_in_3sigma_ratio": _ratio_within([row["roll_error_deg"] for row in pvst], sigma_roll),
        "pitch_in_3sigma_ratio": _ratio_within([row["pitch_error_deg"] for row in pvst], sigma_pitch),
        "yaw_in_3sigma_ratio": _ratio_within([row["yaw_error_deg"] for row in pvst], sigma_yaw),
        "consistency_diagnostic_only": True,
    }
    figure_count_by_folder: dict[str, int] = {}
    for rel in generated:
        folder = rel.split("/", 1)[0]
        figure_count_by_folder[folder] = figure_count_by_folder.get(folder, 0) + 1
    legacy = detect_vector_line_plot_misuse(legacy_figure_manifest or {})
    report = {
        "phase": "N4H4E1",
        "vector_xy_line_removed": True,
        "vector_cloud_scatter_created": True,
        "legacy_vector_line_plot_misuse_detected": legacy["vector_line_plot_misuse_detected"],
        "legacy_suspect_figures": legacy["suspect_legacy_figures"],
        "up_diff_initial_step_checked": True,
        **up_report,
        "corrected_3sigma_figures_created": [name for name in generated if "3sigma" in name or "std_attitude" in name],
        "corrected_3sigma_figure_count": len([name for name in generated if "3sigma" in name or "std_attitude" in name]),
        "std_unit_consistency_applied": std_unit_report.get("attitude_3sigma_unit_consistency_ok"),
        "in_3sigma_ratios": in_3sigma,
        "figure_paths": generated,
        "figure_count_total": len(generated),
        "figure_count_by_folder": figure_count_by_folder,
        "required_corrected_figures_generated": all((figure_root / name).exists() for name in CORRECTED_FIGURES),
        "pure_single_comparison_absent": not any(("pure" in name.lower() or "single" in name.lower()) for name in generated),
        "paper_performance_claim": False,
        "proposed_factor_claim": False,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "output_only_correction": False,
        "bad_epoch_deletion_for_metric": False,
        "no_outperform_final_v23_claim": True,
    }
    _write_json(Path(report_output_dir) / "PLOT_SEMANTICS_FIX_REPORT.json", report)
    _write_json(Path(report_output_dir) / "FIGURE_MANIFEST_E1.json", report)
    case_dir = figure_root / "09_case_review"
    _write_json(case_dir / "FIGURE_MANIFEST_E1.json", report)
    return report
