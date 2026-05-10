"""Generate N4H4E source-backed port visual validation figures.

中文说明：本模块只画 source-backed port、dual_final_v23 reference 与
evaluation reference/trace；不画 pure INS 或 single antenna comparison。
"""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path
from typing import Any

from legsa_gins.evaluation.legsa_v23_port_clean_replay_evaluator import align_by_time, compute_error_rows
from legsa_gins.evaluation.trajectory_metrics import EARTH_RADIUS_M
from legsa_gins.evaluation.yaw_evaluator_parity import compute_errors_for_transforms


REQUIRED_FIGURE_NAMES = [
    "01_trajectory/trajectory_xy_port_finalv23_reference.png",
    "01_trajectory/trajectory_height_time_port_finalv23_reference.png",
    "01_trajectory/trajectory_xy_port_minus_finalv23_zoom.png",
    "01_trajectory/trajectory_xy_error_to_reference.png",
    "02_position_errors/horizontal_error_port_vs_trace.png",
    "02_position_errors/horizontal_error_finalv23_vs_trace.png",
    "02_position_errors/horizontal_error_port_and_finalv23_vs_trace.png",
    "02_position_errors/up_error_port_vs_trace.png",
    "02_position_errors/up_error_finalv23_vs_trace.png",
    "02_position_errors/port_minus_finalv23_horizontal_diff.png",
    "02_position_errors/port_minus_finalv23_up_diff.png",
    "02_position_errors/position_error_p95_window.png",
    "03_attitude_errors/roll_error_port_vs_trace.png",
    "03_attitude_errors/pitch_error_port_vs_trace.png",
    "03_attitude_errors/yaw_error_port_vs_trace.png",
    "03_attitude_errors/yaw_error_finalv23_vs_trace.png",
    "03_attitude_errors/yaw_error_port_and_finalv23_vs_trace.png",
    "03_attitude_errors/port_minus_finalv23_roll_diff.png",
    "03_attitude_errors/port_minus_finalv23_pitch_diff.png",
    "03_attitude_errors/port_minus_finalv23_yaw_diff.png",
    "03_attitude_errors/yaw_wrap_sanity.png",
    "04_port_finalv23_parity/parity_horizontal_diff_time.png",
    "04_port_finalv23_parity/parity_up_diff_time.png",
    "04_port_finalv23_parity/parity_attitude_diff_time.png",
    "04_port_finalv23_parity/parity_error_histograms.png",
    "05_absolute_reference/absolute_horizontal_error_compare.png",
    "05_absolute_reference/absolute_up_error_compare.png",
    "05_absolute_reference/absolute_yaw_error_compare.png",
    "05_absolute_reference/absolute_roll_pitch_error_compare.png",
    "06_update_timeline/update_timeline_counts.png",
    "06_update_timeline/yaw_scheme_modes_over_time.png",
    "06_update_timeline/yaw_residual_over_time.png",
    "07_std_consistency/port_std_position_time.png",
    "07_std_consistency/port_std_attitude_time.png",
    "07_std_consistency/finalv23_std_position_time.png",
    "07_std_consistency/finalv23_std_attitude_time.png",
    "07_std_consistency/error_vs_3sigma_horizontal.png",
    "07_std_consistency/error_vs_3sigma_yaw.png",
    "08_summary_panels/summary_metrics_port_finalv23_absolute.png",
    "08_summary_panels/summary_parity_metrics.png",
    "08_summary_panels/gate_status_panel.png",
]


def _load_matplotlib():
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    return plt


def _wrap_deg(value: float) -> float:
    wrapped = (value + 180.0) % 360.0 - 180.0
    return -180.0 if wrapped == 180.0 else wrapped


def _time0(rows: list[dict[str, Any]]) -> float:
    return float(rows[0].get("timestamp", rows[0].get("time", 0.0))) if rows else 0.0


def _rel_times(rows: list[dict[str, Any]]) -> list[float]:
    start = _time0(rows)
    return [float(row.get("timestamp", row.get("time", 0.0))) - start for row in rows]


def _sample_xy(x: list[float], y: list[float], limit: int = 6000) -> tuple[list[float], list[float]]:
    if len(x) <= limit:
        return x, y
    step = max(1, len(x) // limit)
    return x[::step], y[::step]


def _values(rows: list[dict[str, Any]], key: str) -> list[float]:
    values: list[float] = []
    for row in rows:
        value = row.get(key)
        if isinstance(value, (int, float)) and math.isfinite(float(value)):
            values.append(float(value))
    return values


def _local_neu(rows: list[dict[str, Any]], origin: dict[str, Any]) -> list[dict[str, float]]:
    lat0 = float(origin.get("lat_deg", origin.get("lat")))
    lon0 = float(origin.get("lon_deg", origin.get("lon")))
    h0 = float(origin.get("height_m", origin.get("height")))
    lat0_rad = math.radians(lat0)
    converted = []
    for row in rows:
        lat = float(row.get("lat_deg", row.get("lat")))
        lon = float(row.get("lon_deg", row.get("lon")))
        height = float(row.get("height_m", row.get("height")))
        converted.append(
            {
                "timestamp": float(row.get("timestamp", row.get("time"))),
                "north_m": math.radians(lat - lat0) * EARTH_RADIUS_M,
                "east_m": math.radians(lon - lon0) * EARTH_RADIUS_M * math.cos(lat0_rad),
                "up_m": height - h0,
            }
        )
    return converted


def _save_line(plt, path: Path, series: list[tuple[str, list[float], list[float]]], title: str, ylabel: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(9, 4.8))
    for label, x, y in series:
        sx, sy = _sample_xy(x, y)
        ax.plot(sx, sy, linewidth=1.0, label=label)
    ax.set_title(title)
    ax.set_xlabel("time since start (s)")
    ax.set_ylabel(ylabel)
    ax.grid(True, linewidth=0.3, alpha=0.45)
    if len(series) > 1:
        ax.legend(loc="best", fontsize=8)
    fig.tight_layout()
    fig.savefig(path, dpi=140)
    plt.close(fig)


def _save_xy(plt, path: Path, series: list[tuple[str, list[float], list[float]]], title: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(6, 6))
    for label, east, north in series:
        sx, sy = _sample_xy(east, north)
        ax.plot(sx, sy, linewidth=1.0, label=label)
    ax.set_aspect("equal", adjustable="datalim")
    ax.set_title(title)
    ax.set_xlabel("east (m)")
    ax.set_ylabel("north (m)")
    ax.grid(True, linewidth=0.3, alpha=0.45)
    if len(series) > 1:
        ax.legend(loc="best", fontsize=8)
    fig.tight_layout()
    fig.savefig(path, dpi=140)
    plt.close(fig)


def _save_hist(plt, path: Path, series: list[tuple[str, list[float]]], title: str, xlabel: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(8, 4.8))
    for label, values in series:
        ax.hist(values, bins=50, alpha=0.48, label=label)
    ax.set_title(title)
    ax.set_xlabel(xlabel)
    ax.set_ylabel("count")
    ax.grid(True, linewidth=0.3, alpha=0.45)
    if len(series) > 1:
        ax.legend(loc="best", fontsize=8)
    fig.tight_layout()
    fig.savefig(path, dpi=140)
    plt.close(fig)


def _save_bar(plt, path: Path, labels: list[str], values: list[float], title: str, ylabel: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(8, 4.8))
    ax.bar(labels, values)
    ax.set_title(title)
    ax.set_ylabel(ylabel)
    ax.tick_params(axis="x", labelrotation=25)
    ax.grid(True, axis="y", linewidth=0.3, alpha=0.45)
    fig.tight_layout()
    fig.savefig(path, dpi=140)
    plt.close(fig)


def _write_note(path: Path, title: str, lines: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("# " + title + "\n\n" + "\n".join(f"- {line}" for line in lines) + "\n", encoding="utf-8")


def _read_csv(path: str | Path | None) -> list[dict[str, str]]:
    if not path or not Path(path).exists():
        return []
    with Path(path).open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _newest_named_csv(root_value: str | Path | None, name: str) -> list[dict[str, str]]:
    if not root_value:
        return []
    root = Path(root_value)
    if not root.exists():
        return []
    candidates = [path for path in [root / name, root / "run" / name, *root.glob(f"**/{name}")] if path.exists()]
    if not candidates:
        return []
    return _read_csv(max(candidates, key=lambda path: path.stat().st_mtime))


def _matched_std_rows(
    std_rows: list[dict[str, Any]],
    target_times: list[float],
    *,
    tolerance: float = 0.05,
) -> list[dict[str, Any] | None]:
    """Match monotonic target times to monotonic STD rows in linear time."""

    if not std_rows:
        return [None for _ in target_times]
    std_times = [float(row.get("timestamp", row.get("time", 0.0))) for row in std_rows]
    matched: list[dict[str, Any] | None] = []
    index = 0
    for target in target_times:
        while index + 1 < len(std_times) and abs(std_times[index + 1] - target) <= abs(std_times[index] - target):
            index += 1
        matched.append(std_rows[index] if abs(std_times[index] - target) <= tolerance else None)
    return matched


def _summary_metrics(errors: list[dict[str, float]]) -> dict[str, float | int | None]:
    def rmse(values: list[float]) -> float | None:
        return math.sqrt(sum(value * value for value in values) / len(values)) if values else None

    horizontal = [abs(row["horizontal_error_m"]) for row in errors]
    up = [row["up_error_m"] for row in errors]
    yaw = [row["yaw_error_deg"] for row in errors]
    roll = [row["roll_error_deg"] for row in errors]
    pitch = [row["pitch_error_deg"] for row in errors]
    return {
        "count": len(errors),
        "horizontal_rmse_m": rmse(horizontal),
        "up_rmse_m": rmse(up),
        "yaw_rmse_deg": rmse(yaw),
        "roll_rmse_deg": rmse(roll),
        "pitch_rmse_deg": rmse(pitch),
        "horizontal_max_m": max(horizontal) if horizontal else None,
        "up_max_m": max(abs(value) for value in up) if up else None,
        "yaw_max_deg": max(abs(value) for value in yaw) if yaw else None,
        "roll_max_deg": max(abs(value) for value in roll) if roll else None,
        "pitch_max_deg": max(abs(value) for value in pitch) if pitch else None,
    }


def build_visual_error_bundle(inputs: dict[str, Any]) -> dict[str, Any]:
    port = inputs["port_rows"]
    final = inputs["final_v23_rows"]
    trace = inputs["trace_rows"]
    port_trace_errors = compute_errors_for_transforms(port, trace)
    final_trace_errors = compute_errors_for_transforms(final, trace)
    parity_errors = compute_error_rows(align_by_time(port, final, tolerance=0.005))
    return {
        "port_vs_trace": port_trace_errors,
        "final_v23_vs_trace": final_trace_errors,
        "port_vs_final_v23": parity_errors,
        "port_vs_trace_summary": _summary_metrics(port_trace_errors),
        "final_v23_vs_trace_summary": _summary_metrics(final_trace_errors),
        "port_vs_final_v23_summary": _summary_metrics(parity_errors),
    }


def generate_visual_plots(
    inputs: dict[str, Any],
    *,
    output_dir: str | Path,
    figure_output_dir: str | Path,
    r3a_root: str | Path | None = None,
    r3b_root: str | Path | None = None,
) -> dict[str, Any]:
    plt = _load_matplotlib()
    fig_root = Path(figure_output_dir)
    fig_root.mkdir(parents=True, exist_ok=True)
    errors = build_visual_error_bundle(inputs)
    port = inputs["port_rows"]
    final = inputs["final_v23_rows"]
    trace = inputs["trace_rows"]
    origin = trace[0] if trace else port[0]
    port_neu = _local_neu(port, origin)
    final_neu = _local_neu(final, origin)
    trace_neu = _local_neu(trace, origin)
    generated: list[str] = []
    evidence_missing: list[str] = []

    def add(rel: str) -> Path:
        generated.append(rel)
        return fig_root / rel

    t_port = _rel_times(port)
    t_final = _rel_times(final)
    t_trace = _rel_times(trace)
    port_e = [row["east_m"] for row in port_neu]
    port_n = [row["north_m"] for row in port_neu]
    final_e = [row["east_m"] for row in final_neu]
    final_n = [row["north_m"] for row in final_neu]
    trace_e = [row["east_m"] for row in trace_neu]
    trace_n = [row["north_m"] for row in trace_neu]

    _save_xy(plt, add("01_trajectory/trajectory_xy_port_finalv23_reference.png"), [("port", port_e, port_n), ("dual_final_v23", final_e, final_n), ("reference", trace_e, trace_n)], "trajectory: port, dual_final_v23, reference")
    _save_line(plt, add("01_trajectory/trajectory_height_time_port_finalv23_reference.png"), [("port", t_port, _values(port, "height_m")), ("dual_final_v23", t_final, _values(final, "height_m")), ("reference", t_trace, _values(trace, "height_m"))], "height over time", "height (m)")
    parity = errors["port_vs_final_v23"]
    _save_xy(plt, add("01_trajectory/trajectory_xy_port_minus_finalv23_zoom.png"), [("port - dual_final_v23", [row["east_error_m"] for row in parity], [row["north_error_m"] for row in parity])], "port minus dual_final_v23 horizontal diff")
    _save_xy(plt, add("01_trajectory/trajectory_xy_error_to_reference.png"), [("port error", [row["east_error_m"] for row in errors["port_vs_trace"]], [row["north_error_m"] for row in errors["port_vs_trace"]]), ("dual_final_v23 error", [row["east_error_m"] for row in errors["final_v23_vs_trace"]], [row["north_error_m"] for row in errors["final_v23_vs_trace"]])], "horizontal error to reference")

    pvst = errors["port_vs_trace"]
    fvst = errors["final_v23_vs_trace"]
    t_pvst = _rel_times(pvst)
    t_fvst = _rel_times(fvst)
    t_parity = _rel_times(parity)
    _save_line(plt, add("02_position_errors/horizontal_error_port_vs_trace.png"), [("port", t_pvst, [row["horizontal_error_m"] for row in pvst])], "port horizontal error vs trace", "horizontal error (m)")
    _save_line(plt, add("02_position_errors/horizontal_error_finalv23_vs_trace.png"), [("dual_final_v23", t_fvst, [row["horizontal_error_m"] for row in fvst])], "dual_final_v23 horizontal error vs trace", "horizontal error (m)")
    _save_line(plt, add("02_position_errors/horizontal_error_port_and_finalv23_vs_trace.png"), [("port", t_pvst, [row["horizontal_error_m"] for row in pvst]), ("dual_final_v23", t_fvst, [row["horizontal_error_m"] for row in fvst])], "horizontal error vs trace", "horizontal error (m)")
    _save_line(plt, add("02_position_errors/up_error_port_vs_trace.png"), [("port", t_pvst, [row["up_error_m"] for row in pvst])], "port up error vs trace", "up error (m)")
    _save_line(plt, add("02_position_errors/up_error_finalv23_vs_trace.png"), [("dual_final_v23", t_fvst, [row["up_error_m"] for row in fvst])], "dual_final_v23 up error vs trace", "up error (m)")
    _save_line(plt, add("02_position_errors/port_minus_finalv23_horizontal_diff.png"), [("port - dual_final_v23", t_parity, [row["horizontal_error_m"] for row in parity])], "port minus dual_final_v23 horizontal diff", "horizontal diff (m)")
    _save_line(plt, add("02_position_errors/port_minus_finalv23_up_diff.png"), [("port - dual_final_v23", t_parity, [row["up_error_m"] for row in parity])], "port minus dual_final_v23 up diff", "up diff (m)")
    _save_line(plt, add("02_position_errors/position_error_p95_window.png"), [("port horizontal", t_pvst, [row["horizontal_error_m"] for row in pvst]), ("dual horizontal", t_fvst, [row["horizontal_error_m"] for row in fvst])], "position error p95 visual window", "horizontal error (m)")

    _save_line(plt, add("03_attitude_errors/roll_error_port_vs_trace.png"), [("port", t_pvst, [row["roll_error_deg"] for row in pvst])], "port roll error vs trace", "roll error (deg)")
    _save_line(plt, add("03_attitude_errors/pitch_error_port_vs_trace.png"), [("port", t_pvst, [row["pitch_error_deg"] for row in pvst])], "port pitch error vs trace", "pitch error (deg)")
    _save_line(plt, add("03_attitude_errors/yaw_error_port_vs_trace.png"), [("port", t_pvst, [row["yaw_error_deg"] for row in pvst])], "port yaw error vs trace", "yaw error (deg)")
    _save_line(plt, add("03_attitude_errors/yaw_error_finalv23_vs_trace.png"), [("dual_final_v23", t_fvst, [row["yaw_error_deg"] for row in fvst])], "dual_final_v23 yaw error vs trace", "yaw error (deg)")
    _save_line(plt, add("03_attitude_errors/yaw_error_port_and_finalv23_vs_trace.png"), [("port", t_pvst, [row["yaw_error_deg"] for row in pvst]), ("dual_final_v23", t_fvst, [row["yaw_error_deg"] for row in fvst])], "yaw error vs trace", "yaw error (deg)")
    _save_line(plt, add("03_attitude_errors/port_minus_finalv23_roll_diff.png"), [("roll", t_parity, [row["roll_error_deg"] for row in parity])], "port minus dual_final_v23 roll diff", "roll diff (deg)")
    _save_line(plt, add("03_attitude_errors/port_minus_finalv23_pitch_diff.png"), [("pitch", t_parity, [row["pitch_error_deg"] for row in parity])], "port minus dual_final_v23 pitch diff", "pitch diff (deg)")
    _save_line(plt, add("03_attitude_errors/port_minus_finalv23_yaw_diff.png"), [("yaw", t_parity, [row["yaw_error_deg"] for row in parity])], "port minus dual_final_v23 yaw diff", "yaw diff (deg)")
    yaw_jumps = [0.0] + [abs(_wrap_deg(pvst[index]["yaw_error_deg"] - pvst[index - 1]["yaw_error_deg"])) for index in range(1, len(pvst))]
    _save_line(plt, add("03_attitude_errors/yaw_wrap_sanity.png"), [("wrapped yaw jump", t_pvst, yaw_jumps)], "yaw wrap sanity", "consecutive wrapped jump (deg)")

    _save_line(plt, add("04_port_finalv23_parity/parity_horizontal_diff_time.png"), [("horizontal", t_parity, [row["horizontal_error_m"] for row in parity])], "parity horizontal diff", "diff (m)")
    _save_line(plt, add("04_port_finalv23_parity/parity_up_diff_time.png"), [("up", t_parity, [row["up_error_m"] for row in parity])], "parity up diff", "diff (m)")
    _save_line(plt, add("04_port_finalv23_parity/parity_attitude_diff_time.png"), [("roll", t_parity, [row["roll_error_deg"] for row in parity]), ("pitch", t_parity, [row["pitch_error_deg"] for row in parity]), ("yaw", t_parity, [row["yaw_error_deg"] for row in parity])], "parity attitude diff", "diff (deg)")
    _save_hist(plt, add("04_port_finalv23_parity/parity_error_histograms.png"), [("horizontal m", [row["horizontal_error_m"] for row in parity]), ("yaw deg", [abs(row["yaw_error_deg"]) for row in parity])], "parity error histograms", "absolute error")

    _save_hist(plt, add("05_absolute_reference/absolute_horizontal_error_compare.png"), [("port", [row["horizontal_error_m"] for row in pvst]), ("dual_final_v23", [row["horizontal_error_m"] for row in fvst])], "absolute horizontal error compare", "horizontal error (m)")
    _save_hist(plt, add("05_absolute_reference/absolute_up_error_compare.png"), [("port", [row["up_error_m"] for row in pvst]), ("dual_final_v23", [row["up_error_m"] for row in fvst])], "absolute up error compare", "up error (m)")
    _save_hist(plt, add("05_absolute_reference/absolute_yaw_error_compare.png"), [("port", [row["yaw_error_deg"] for row in pvst]), ("dual_final_v23", [row["yaw_error_deg"] for row in fvst])], "absolute yaw error compare", "yaw error (deg)")
    _save_hist(plt, add("05_absolute_reference/absolute_roll_pitch_error_compare.png"), [("port roll", [row["roll_error_deg"] for row in pvst]), ("port pitch", [row["pitch_error_deg"] for row in pvst]), ("dual roll", [row["roll_error_deg"] for row in fvst]), ("dual pitch", [row["pitch_error_deg"] for row in fvst])], "absolute roll/pitch error compare", "error (deg)")

    update_rows = _newest_named_csv(r3a_root, "PORT_GNSS_UPDATE_TRACE.csv")
    residual_rows = _newest_named_csv(r3b_root, "PORT_UPDATE_RESIDUAL_GAIN_TRACE.csv")
    if update_rows:
        update_times = [float(row.get("gnss_time", index)) - float(update_rows[0].get("gnss_time", 0.0)) for index, row in enumerate(update_rows)]
        applied = [float(row.get("position_update", 0.0)) + float(row.get("velocity_update", 0.0)) + float(row.get("yaw_update", 0.0)) for row in update_rows]
        _save_line(plt, add("06_update_timeline/update_timeline_counts.png"), [("update components", update_times, applied)], "update timeline counts", "component count")
        mode_map: dict[str, float] = {}
        mode_values: list[float] = []
        for row in update_rows:
            mode = str(row.get("yaw_mode", "UNKNOWN"))
            if mode not in mode_map:
                mode_map[mode] = float(len(mode_map))
            mode_values.append(mode_map[mode])
        _save_line(plt, add("06_update_timeline/yaw_scheme_modes_over_time.png"), [("yaw scheme mode index", update_times, mode_values)], "yaw scheme modes over time", "mode index")
    else:
        evidence_missing.append("PORT_GNSS_UPDATE_TRACE.csv")
        _write_note(fig_root / "06_update_timeline/evidence_missing.md", "Update timeline evidence missing", ["PORT_GNSS_UPDATE_TRACE.csv not found"])
    if residual_rows:
        residual_times = [float(row.get("gnss_time", index)) - float(residual_rows[0].get("gnss_time", 0.0)) for index, row in enumerate(residual_rows)]
        residual_yaw = [float(row.get("yaw_residual_deg") or 0.0) for row in residual_rows]
        _save_line(plt, add("06_update_timeline/yaw_residual_over_time.png"), [("yaw residual", residual_times, residual_yaw)], "yaw residual over time", "yaw residual (deg)")
    else:
        evidence_missing.append("PORT_UPDATE_RESIDUAL_GAIN_TRACE.csv")

    port_std = inputs.get("port_std_rows", [])
    final_std = inputs.get("final_v23_std_rows", [])
    if port_std:
        t_std = _rel_times(port_std)
        _save_line(plt, add("07_std_consistency/port_std_position_time.png"), [("N", t_std, _values(port_std, "std_pos_n_m")), ("E", t_std, _values(port_std, "std_pos_e_m")), ("D", t_std, _values(port_std, "std_pos_d_m"))], "port STD position", "STD (m)")
        _save_line(plt, add("07_std_consistency/port_std_attitude_time.png"), [("roll", t_std, _values(port_std, "std_roll_deg")), ("pitch", t_std, _values(port_std, "std_pitch_deg")), ("yaw", t_std, _values(port_std, "std_yaw_deg"))], "port STD attitude", "STD (deg)")
    else:
        evidence_missing.append("port_std")
    if final_std:
        t_fstd = _rel_times(final_std)
        _save_line(plt, add("07_std_consistency/finalv23_std_position_time.png"), [("N", t_fstd, _values(final_std, "std_pos_n_m")), ("E", t_fstd, _values(final_std, "std_pos_e_m")), ("D", t_fstd, _values(final_std, "std_pos_d_m"))], "dual_final_v23 STD position", "STD (m)")
        _save_line(plt, add("07_std_consistency/finalv23_std_attitude_time.png"), [("roll", t_fstd, _values(final_std, "std_roll_deg")), ("pitch", t_fstd, _values(final_std, "std_pitch_deg")), ("yaw", t_fstd, _values(final_std, "std_yaw_deg"))], "dual_final_v23 STD attitude", "STD (deg)")
    else:
        evidence_missing.append("final_v23_std")
    if port_std:
        sigma_h = []
        sigma_yaw = []
        for row, std in zip(pvst, _matched_std_rows(port_std, [float(item["timestamp"]) for item in pvst])):
            if std:
                sigma_h.append(3.0 * math.hypot(float(std.get("std_pos_n_m", 0.0)), float(std.get("std_pos_e_m", 0.0))))
                sigma_yaw.append(3.0 * float(std.get("std_yaw_deg", 0.0)))
            else:
                sigma_h.append(0.0)
                sigma_yaw.append(0.0)
        _save_line(plt, add("07_std_consistency/error_vs_3sigma_horizontal.png"), [("horizontal error", t_pvst, [row["horizontal_error_m"] for row in pvst]), ("3sigma H", t_pvst, sigma_h)], "error vs 3sigma horizontal", "m")
        _save_line(plt, add("07_std_consistency/error_vs_3sigma_yaw.png"), [("yaw error abs", t_pvst, [abs(row["yaw_error_deg"]) for row in pvst]), ("3sigma yaw", t_pvst, sigma_yaw)], "error vs 3sigma yaw", "deg")

    port_abs = inputs["r3c_reports"].get("PORT_VS_TRACE_ABSOLUTE_REPORT.json", {})
    final_abs = inputs["r3c_reports"].get("FINALV23_VS_TRACE_ABSOLUTE_REPRO_REPORT.json", {})
    parity_report = inputs["r3c_reports"].get("PORT_VS_FINALV23_NAV_PARITY_REPORT.json", {})
    comparison = inputs["r3c_reports"].get("PORT_METRIC_NAMESPACE_DECISION_REPORT.json", {})
    _save_bar(plt, add("08_summary_panels/summary_metrics_port_finalv23_absolute.png"), ["port H", "final H", "port yaw", "final yaw"], [float(port_abs.get("horizontal_rmse_m", 0.0)), float(final_abs.get("horizontal_rmse_m", 0.0)), float(port_abs.get("yaw_rmse_deg", 0.0)), float(final_abs.get("yaw_rmse_deg", 0.0))], "absolute metric summary", "mixed metric value")
    _save_bar(plt, add("08_summary_panels/summary_parity_metrics.png"), ["H m", "Up m", "Yaw deg", "Roll deg", "Pitch deg"], [float(parity_report.get("horizontal_rmse_m", 0.0)), float(parity_report.get("up_rmse_m", 0.0)), float(parity_report.get("yaw_rmse_deg", 0.0)), float(parity_report.get("roll_rmse_deg", 0.0)), float(parity_report.get("pitch_rmse_deg", 0.0))], "port vs dual_final_v23 parity metrics", "RMSE")
    _save_bar(plt, add("08_summary_panels/gate_status_panel.png"), ["parity", "final repro", "abs close", "candidate"], [1.0 if parity_report.get("parity_small") else 0.0, 1.0 if final_abs.get("official_summary_reproduced") else 0.0, 1.0 if inputs["r3c_reports"].get("PORT_PARITY_VS_ABSOLUTE_COMPARISON_REPORT.json", {}).get("port_absolute_close_to_finalv23_absolute") else 0.0, 1.0 if comparison.get("engineering_backbone_candidate") is True else 0.0], "gate status panel", "true=1")

    manifest = {
        "phase": "N4H4E",
        "figure_output_dir": str(fig_root),
        "figure_paths": generated,
        "figure_count_total": len(generated),
        "figure_count_by_folder": {},
        "evidence_missing": evidence_missing,
        "pure_single_comparison_absent": not any(("pure" in path.lower() or "single" in path.lower()) for path in generated),
        "paper_performance_claim": False,
        "proposed_factor_claim": False,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "output_only_correction": False,
        "bad_epoch_deletion_for_metric": False,
        "no_outperform_final_v23_claim": True,
    }
    for rel in generated:
        folder = rel.split("/", 1)[0]
        manifest["figure_count_by_folder"][folder] = manifest["figure_count_by_folder"].get(folder, 0) + 1
    output = Path(output_dir) / "FIGURE_MANIFEST.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    case_dir = fig_root / "09_case_review"
    case_dir.mkdir(parents=True, exist_ok=True)
    (case_dir / "FIGURE_MANIFEST.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {**manifest, "errors": errors}
