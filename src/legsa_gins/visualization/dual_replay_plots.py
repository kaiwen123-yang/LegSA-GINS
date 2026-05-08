"""Generate dual_final_v23-only fresh replay validation plots.

中文说明：本模块只画 dual_final_v23 official reference 与 fresh replay estimate；
不画 pure_ins、不画 single_antenna、不画多方案对比，不修改 solver output。
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Iterable

from legsa_gins.evaluation.trajectory_metrics import align_by_timestamp
from legsa_gins.visualization.dual_replay_plot_loader import local_neu_from_origin


PLOT_DIRS = [
    "01_trajectory",
    "02_position_errors",
    "03_velocity",
    "04_attitude",
    "05_consistency",
    "06_observation_quality",
    "08_summary_panels",
    "09_case_review",
]


def _load_matplotlib():
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        return plt, None
    except Exception as exc:  # pragma: no cover - exercised only on missing dependency hosts
        return None, {
            "plotting_status": "failed",
            "dependency_missing": "matplotlib",
            "error": str(exc),
        }


def _times(rows: list[dict[str, Any]], key: str = "timestamp") -> list[float]:
    if not rows:
        return []
    start = float(rows[0].get(key, rows[0].get("time", 0.0)))
    return [(float(row.get(key, row.get("time", 0.0))) - start) for row in rows]


def _values(rows: list[dict[str, Any]], key: str) -> list[float]:
    return [float(row[key]) for row in rows if key in row and isinstance(row[key], (int, float))]


def _save_line(
    plt,
    path: Path,
    x: list[float],
    series: list[tuple[str, list[float], str]],
    *,
    title: str,
    xlabel: str,
    ylabel: str,
    hline: float | None = None,
    hline_label: str | None = None,
    text: str | None = None,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(9, 4.8))
    for label, values, style in series:
        ax.plot(x[: len(values)], values, style, linewidth=1.1, label=label)
    if hline is not None:
        ax.axhline(hline, color="#444444", linewidth=0.9, linestyle="--", label=hline_label)
        ax.axhline(-hline, color="#444444", linewidth=0.9, linestyle="--")
    if text:
        ax.text(0.01, 0.98, text, transform=ax.transAxes, va="top", ha="left", fontsize=9)
    ax.set_title(title)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.grid(True, linewidth=0.3, alpha=0.45)
    if len(series) > 1 or hline_label:
        ax.legend(loc="best", fontsize=8)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def _save_scatter(
    plt,
    path: Path,
    x: list[float],
    y: list[float],
    *,
    title: str,
    xlabel: str,
    ylabel: str,
    label: str | None = None,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(6, 6))
    ax.scatter(x, y, s=2, alpha=0.55, label=label)
    ax.set_aspect("equal", adjustable="datalim")
    ax.set_title(title)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.grid(True, linewidth=0.3, alpha=0.45)
    if label:
        ax.legend(loc="best", fontsize=8)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def _save_hist(plt, path: Path, values: list[float], *, title: str, xlabel: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(7, 4.8))
    ax.hist(values, bins=50, color="#3b6ea8", alpha=0.82)
    ax.set_title(title)
    ax.set_xlabel(xlabel)
    ax.set_ylabel("count")
    ax.grid(True, linewidth=0.3, alpha=0.45)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def _save_cdf(plt, path: Path, values: list[float], *, title: str, xlabel: str) -> None:
    sorted_values = sorted(values)
    y = [(index + 1) / len(sorted_values) for index in range(len(sorted_values))] if sorted_values else []
    _save_line(plt, path, sorted_values, [("CDF", y, "-")], title=title, xlabel=xlabel, ylabel="fraction")


def _save_box(plt, path: Path, data: list[list[float]], labels: list[str], *, title: str, ylabel: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(7, 4.8))
    ax.boxplot(data, labels=labels, showfliers=False)
    ax.set_title(title)
    ax.set_ylabel(ylabel)
    ax.grid(True, axis="y", linewidth=0.3, alpha=0.45)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def _save_multi_panel(
    plt,
    path: Path,
    panel_data: list[tuple[str, list[float], list[tuple[str, list[float], str]], str]],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig, axes = plt.subplots(len(panel_data), 1, figsize=(9, 2.8 * len(panel_data)), sharex=False)
    if len(panel_data) == 1:
        axes = [axes]
    for ax, (title, x, series, ylabel) in zip(axes, panel_data):
        for label, values, style in series:
            ax.plot(x[: len(values)], values, style, linewidth=1.0, label=label)
        ax.set_title(title)
        ax.set_ylabel(ylabel)
        ax.grid(True, linewidth=0.3, alpha=0.45)
        if len(series) > 1:
            ax.legend(loc="best", fontsize=8)
    axes[-1].set_xlabel("time since start (s)")
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def _aligned_est_ref(
    replay_nav: list[dict[str, Any]],
    reference_rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    aligned = align_by_timestamp(replay_nav, reference_rows, max_dt=0.05)
    est: list[dict[str, Any]] = []
    ref: list[dict[str, Any]] = []
    for item in aligned:
        if isinstance(item["est"], dict) and isinstance(item["ref"], dict):
            est.append(item["est"])
            ref.append(item["ref"])
    return est, ref


def _nearest_std(
    error_rows: list[dict[str, Any]],
    std_rows: list[dict[str, Any]],
) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    if not error_rows or not std_rows:
        return []
    result: list[tuple[dict[str, Any], dict[str, Any]]] = []
    std_index = 0
    for err in error_rows:
        target = float(err["timestamp"])
        while (
            std_index + 1 < len(std_rows)
            and abs(float(std_rows[std_index + 1]["timestamp"]) - target)
            <= abs(float(std_rows[std_index]["timestamp"]) - target)
        ):
            std_index += 1
        std = std_rows[std_index]
        if abs(float(std["timestamp"]) - target) <= 0.05:
            result.append((err, std))
    return result


def _rmse_text(metrics: dict[str, Any]) -> str:
    yaw = metrics.get("yaw_rmse_deg")
    yaw_text = f"yaw RMSE = {float(yaw):.3f} deg\n" if isinstance(yaw, (int, float)) else ""
    return (
        f"H RMSE = {float(metrics.get('horizontal_rmse_m', 0.0)):.3f} m\n"
        f"Up RMSE = {float(metrics.get('up_rmse_m', 0.0)):.3f} m\n"
        f"{yaw_text}"
        "yaw gate <= 2 deg\n"
        "near-boundary\n"
        "roll/pitch relaxed, not strict"
    )


def _safe_metric(value: Any) -> float:
    return float(value) if isinstance(value, (int, float)) and math.isfinite(float(value)) else 0.0


def _plot_trajectory(
    plt,
    root: Path,
    replay_nav: list[dict[str, Any]],
    reference_rows: list[dict[str, Any]],
    input_rows: list[dict[str, Any]],
) -> list[str]:
    out = root / "01_trajectory"
    est_aligned, ref_aligned = _aligned_est_ref(replay_nav, reference_rows)
    origin = ref_aligned[0] if ref_aligned else reference_rows[0]
    est_neu = local_neu_from_origin(est_aligned, origin)
    ref_neu = local_neu_from_origin(ref_aligned, origin)
    obs_neu = local_neu_from_origin(input_rows, origin) if input_rows else []
    paths: list[Path] = []
    _save_scatter(
        plt,
        out / "dual_replay_traj_truth_est.png",
        [row["east_m"] for row in ref_neu],
        [row["north_m"] for row in ref_neu],
        title="dual replay local trajectory: reference",
        xlabel="east (m)",
        ylabel="north (m)",
        label="reference",
    )
    fig_path = out / "dual_replay_traj_truth_est.png"
    fig = plt.figure(figsize=(6, 6))
    ax = fig.add_subplot(111)
    ax.plot([row["east_m"] for row in ref_neu], [row["north_m"] for row in ref_neu], "-", linewidth=1.2, label="reference")
    ax.plot([row["east_m"] for row in est_neu], [row["north_m"] for row in est_neu], "--", linewidth=1.0, label="replay estimate")
    ax.set_aspect("equal", adjustable="datalim")
    ax.set_title("dual replay local trajectory")
    ax.set_xlabel("east (m)")
    ax.set_ylabel("north (m)")
    ax.grid(True, linewidth=0.3, alpha=0.45)
    ax.legend(loc="best", fontsize=8)
    fig.tight_layout()
    fig.savefig(fig_path, dpi=150)
    plt.close(fig)
    paths.append(fig_path)

    fig_path = out / "dual_replay_traj_truth_est_obs.png"
    fig, ax = plt.subplots(figsize=(6, 6))
    ax.plot([row["east_m"] for row in ref_neu], [row["north_m"] for row in ref_neu], "-", linewidth=1.2, label="reference")
    ax.plot([row["east_m"] for row in est_neu], [row["north_m"] for row in est_neu], "--", linewidth=1.0, label="replay estimate")
    if obs_neu:
        ax.scatter([row["east_m"] for row in obs_neu], [row["north_m"] for row in obs_neu], s=1, alpha=0.25, label="GNSS obs")
    ax.set_aspect("equal", adjustable="datalim")
    ax.set_title("dual replay local trajectory with GNSS observations")
    ax.set_xlabel("east (m)")
    ax.set_ylabel("north (m)")
    ax.grid(True, linewidth=0.3, alpha=0.45)
    ax.legend(loc="best", fontsize=8)
    fig.tight_layout()
    fig.savefig(fig_path, dpi=150)
    plt.close(fig)
    paths.append(fig_path)

    times = _times(est_aligned)
    _save_line(
        plt,
        out / "dual_replay_height_time.png",
        times,
        [
            ("reference", _values(ref_aligned, "height_m"), "-"),
            ("replay estimate", _values(est_aligned, "height_m"), "--"),
        ],
        title="dual replay height over time",
        xlabel="time since start (s)",
        ylabel="height (m)",
    )
    paths.append(out / "dual_replay_height_time.png")
    _save_scatter(
        plt,
        out / "dual_replay_height_truth_est.png",
        _values(ref_aligned, "height_m"),
        _values(est_aligned, "height_m"),
        title="dual replay height reference vs estimate",
        xlabel="reference height (m)",
        ylabel="estimate height (m)",
    )
    paths.append(out / "dual_replay_height_truth_est.png")
    return [str(path) for path in paths]


def _plot_position_errors(plt, root: Path, error_rows: list[dict[str, Any]]) -> list[str]:
    out = root / "02_position_errors"
    times = _times(error_rows)
    paths: list[Path] = []
    specs = [
        ("dual_replay_pos_err_n_m.png", "north_error_m", "north error (m)"),
        ("dual_replay_pos_err_e_m.png", "east_error_m", "east error (m)"),
        ("dual_replay_pos_err_u_m.png", "up_error_m", "up error (m)"),
        ("dual_replay_pos_horizontal.png", "horizontal_error_m", "horizontal error (m)"),
    ]
    for filename, key, ylabel in specs:
        _save_line(
            plt,
            out / filename,
            times,
            [(key, _values(error_rows, key), "-")],
            title=f"dual replay {ylabel}",
            xlabel="time since start (s)",
            ylabel=ylabel,
        )
        paths.append(out / filename)
    _save_multi_panel(
        plt,
        out / "dual_replay_pos_neu_combined.png",
        [
            ("north error", times, [("N", _values(error_rows, "north_error_m"), "-")], "m"),
            ("east error", times, [("E", _values(error_rows, "east_error_m"), "-")], "m"),
            ("up error", times, [("U", _values(error_rows, "up_error_m"), "-")], "m"),
        ],
    )
    paths.append(out / "dual_replay_pos_neu_combined.png")
    _save_cdf(plt, out / "dual_replay_pos_cdf.png", _values(error_rows, "horizontal_error_m"), title="dual replay horizontal error CDF", xlabel="horizontal error (m)")
    paths.append(out / "dual_replay_pos_cdf.png")
    _save_hist(plt, out / "dual_replay_pos_hist_horizontal.png", _values(error_rows, "horizontal_error_m"), title="dual replay horizontal error histogram", xlabel="horizontal error (m)")
    paths.append(out / "dual_replay_pos_hist_horizontal.png")
    _save_box(
        plt,
        out / "dual_replay_pos_box_neu.png",
        [_values(error_rows, "north_error_m"), _values(error_rows, "east_error_m"), _values(error_rows, "up_error_m")],
        ["N", "E", "U"],
        title="dual replay NEU error box",
        ylabel="error (m)",
    )
    paths.append(out / "dual_replay_pos_box_neu.png")
    fig_path = out / "dual_replay_pos_hv_summary.png"
    fig, ax = plt.subplots(figsize=(7, 4.8))
    horizontal = _values(error_rows, "horizontal_error_m")
    up = [abs(value) for value in _values(error_rows, "up_error_m")]
    ax.plot(times[: len(horizontal)], horizontal, label="horizontal", linewidth=1.0)
    ax.plot(times[: len(up)], up, label="abs up", linewidth=1.0)
    ax.set_title("dual replay horizontal / vertical error summary")
    ax.set_xlabel("time since start (s)")
    ax.set_ylabel("error magnitude")
    ax.grid(True, linewidth=0.3, alpha=0.45)
    ax.legend(loc="best", fontsize=8)
    fig.tight_layout()
    fig.savefig(fig_path, dpi=150)
    plt.close(fig)
    paths.append(fig_path)
    return [str(path) for path in paths]


def _plot_velocity(plt, root: Path, replay_nav: list[dict[str, Any]], std_rows: list[dict[str, Any]]) -> list[str]:
    out = root / "03_velocity"
    times = _times(replay_nav)
    paths: list[Path] = []
    for filename, key, title in [
        ("dual_replay_vel_n_time.png", "vn", "estimated north velocity"),
        ("dual_replay_vel_e_time.png", "ve", "estimated east velocity"),
        ("dual_replay_vel_d_time.png", "vd", "estimated down velocity"),
    ]:
        _save_line(
            plt,
            out / filename,
            times,
            [(key, _values(replay_nav, key), "-")],
            title=f"dual replay {title} / no velocity truth",
            xlabel="time since start (s)",
            ylabel="m/s",
        )
        paths.append(out / filename)
    _save_multi_panel(
        plt,
        out / "dual_replay_vel_combined.png",
        [
            ("north velocity estimate", times, [("vn", _values(replay_nav, "vn"), "-")], "m/s"),
            ("east velocity estimate", times, [("ve", _values(replay_nav, "ve"), "-")], "m/s"),
            ("down velocity estimate", times, [("vd", _values(replay_nav, "vd"), "-")], "m/s"),
        ],
    )
    paths.append(out / "dual_replay_vel_combined.png")
    if std_rows:
        std_times = _times(std_rows)
        for filename, key, title in [
            ("dual_replay_vel_std_n.png", "std_vel_n_mps", "north velocity STD"),
            ("dual_replay_vel_std_e.png", "std_vel_e_mps", "east velocity STD"),
            ("dual_replay_vel_std_d.png", "std_vel_d_mps", "down velocity STD"),
        ]:
            _save_line(
                plt,
                out / filename,
                std_times,
                [(key, _values(std_rows, key), "-")],
                title=f"dual replay {title}",
                xlabel="time since start (s)",
                ylabel="m/s",
            )
            paths.append(out / filename)
    return [str(path) for path in paths]


def _plot_attitude(plt, root: Path, replay_nav: list[dict[str, Any]], reference_rows: list[dict[str, Any]], error_rows: list[dict[str, Any]], metrics: dict[str, Any]) -> list[str]:
    out = root / "04_attitude"
    est_aligned, ref_aligned = _aligned_est_ref(replay_nav, reference_rows)
    times = _times(est_aligned)
    paths: list[Path] = []
    for filename, key_est, key_ref, title in [
        ("dual_replay_roll_truth_est.png", "roll_deg", "roll_deg", "roll reference / estimate"),
        ("dual_replay_pitch_truth_est.png", "pitch_deg", "pitch_deg", "pitch reference / estimate"),
        ("dual_replay_yaw_truth_est.png", "yaw_deg", "yaw_deg", "yaw reference / estimate"),
    ]:
        _save_line(
            plt,
            out / filename,
            times,
            [
                ("reference", _values(ref_aligned, key_ref), "-"),
                ("replay estimate", _values(est_aligned, key_est), "--"),
            ],
            title=f"dual replay {title}",
            xlabel="time since start (s)",
            ylabel="deg",
            text=_rmse_text(metrics) if "yaw" in filename else None,
        )
        paths.append(out / filename)
    _save_multi_panel(
        plt,
        out / "dual_replay_attitude_truth_est_combined.png",
        [
            ("roll", times, [("reference", _values(ref_aligned, "roll_deg"), "-"), ("estimate", _values(est_aligned, "roll_deg"), "--")], "deg"),
            ("pitch", times, [("reference", _values(ref_aligned, "pitch_deg"), "-"), ("estimate", _values(est_aligned, "pitch_deg"), "--")], "deg"),
            ("yaw", times, [("reference", _values(ref_aligned, "yaw_deg"), "-"), ("estimate", _values(est_aligned, "yaw_deg"), "--")], "deg"),
        ],
    )
    paths.append(out / "dual_replay_attitude_truth_est_combined.png")
    err_times = _times(error_rows)
    for filename, key, title in [
        ("dual_replay_roll_error_deg.png", "roll_error_deg", "roll error"),
        ("dual_replay_pitch_error_deg.png", "pitch_error_deg", "pitch error"),
        ("dual_replay_yaw_error_deg.png", "yaw_error_deg", "yaw error"),
    ]:
        _save_line(
            plt,
            out / filename,
            err_times,
            [(key, _values(error_rows, key), "-")],
            title=f"dual replay {title}",
            xlabel="time since start (s)",
            ylabel="deg",
            hline=2.0 if key == "yaw_error_deg" else None,
            hline_label="yaw gate <= 2 deg" if key == "yaw_error_deg" else None,
            text=_rmse_text(metrics) if key == "yaw_error_deg" else None,
        )
        paths.append(out / filename)
    _save_multi_panel(
        plt,
        out / "dual_replay_attitude_error_combined.png",
        [
            ("roll error", err_times, [("roll", _values(error_rows, "roll_error_deg"), "-")], "deg"),
            ("pitch error", err_times, [("pitch", _values(error_rows, "pitch_error_deg"), "-")], "deg"),
            ("yaw error", err_times, [("yaw", _values(error_rows, "yaw_error_deg"), "-")], "deg"),
        ],
    )
    paths.append(out / "dual_replay_attitude_error_combined.png")
    _save_cdf(plt, out / "dual_replay_yaw_cdf.png", [abs(value) for value in _values(error_rows, "yaw_error_deg")], title="dual replay absolute yaw error CDF", xlabel="abs yaw error (deg)")
    paths.append(out / "dual_replay_yaw_cdf.png")
    _save_box(
        plt,
        out / "dual_replay_attitude_box.png",
        [_values(error_rows, "roll_error_deg"), _values(error_rows, "pitch_error_deg"), _values(error_rows, "yaw_error_deg")],
        ["roll", "pitch", "yaw"],
        title="dual replay attitude error box",
        ylabel="deg",
    )
    paths.append(out / "dual_replay_attitude_box.png")
    return [str(path) for path in paths]


def _plot_consistency(plt, root: Path, error_rows: list[dict[str, Any]], std_rows: list[dict[str, Any]]) -> tuple[list[str], list[str]]:
    out = root / "05_consistency"
    missing: list[str] = []
    if not std_rows:
        return [], ["KF_GINS_STD"]
    pairs = _nearest_std(error_rows, std_rows)
    if not pairs:
        return [], ["error_std_alignment"]
    err = [pair[0] for pair in pairs]
    std = [pair[1] for pair in pairs]
    times = _times(err)
    paths: list[Path] = []

    specs = [
        ("dual_replay_consistency_pos_n.png", "north_error_m", "std_pos_n_m", "north position"),
        ("dual_replay_consistency_pos_e.png", "east_error_m", "std_pos_e_m", "east position"),
        ("dual_replay_consistency_pos_u.png", "up_error_m", "std_pos_d_m", "up/down position"),
        ("dual_replay_consistency_roll.png", "roll_error_deg", "std_roll_deg", "roll"),
        ("dual_replay_consistency_pitch.png", "pitch_error_deg", "std_pitch_deg", "pitch"),
        ("dual_replay_consistency_yaw.png", "yaw_error_deg", "std_yaw_deg", "yaw"),
    ]
    for filename, err_key, std_key, title in specs:
        if err_key not in err[0] or std_key not in std[0]:
            missing.append(filename)
            continue
        sigma3 = [3.0 * float(row[std_key]) for row in std]
        _save_line(
            plt,
            out / filename,
            times,
            [(err_key, _values(err, err_key), "-"), ("+3 sigma", sigma3, "--"), ("-3 sigma", [-value for value in sigma3], "--")],
            title=f"dual replay consistency: {title}",
            xlabel="time since start (s)",
            ylabel="error / 3 sigma",
        )
        paths.append(out / filename)

    h_err = _values(err, "horizontal_error_m")
    h_sigma = [
        3.0 * math.hypot(float(row.get("std_pos_n_m", 0.0)), float(row.get("std_pos_e_m", 0.0)))
        for row in std
    ]
    _save_line(
        plt,
        out / "dual_replay_consistency_horizontal.png",
        times,
        [("horizontal error", h_err, "-"), ("3 sigma horizontal", h_sigma, "--")],
        title="dual replay consistency: horizontal position",
        xlabel="time since start (s)",
        ylabel="m",
    )
    paths.append(out / "dual_replay_consistency_horizontal.png")

    for filename, std_key, title in [
        ("dual_replay_consistency_vel_n.png", "std_vel_n_mps", "north velocity STD"),
        ("dual_replay_consistency_vel_e.png", "std_vel_e_mps", "east velocity STD"),
        ("dual_replay_consistency_vel_d.png", "std_vel_d_mps", "down velocity STD"),
    ]:
        if std_key not in std[0]:
            missing.append(filename)
            continue
        _save_line(
            plt,
            out / filename,
            times,
            [(std_key, _values(std, std_key), "-")],
            title=f"dual replay consistency evidence: {title}",
            xlabel="time since start (s)",
            ylabel="m/s",
        )
        paths.append(out / filename)
    return [str(path) for path in paths], missing


def _plot_observation_quality(plt, root: Path, input_rows: list[dict[str, Any]], origin: dict[str, Any]) -> list[str]:
    out = root / "06_observation_quality"
    if not input_rows:
        return []
    times = _times(input_rows, key="time")
    obs_neu = local_neu_from_origin(input_rows, origin)
    paths: list[Path] = []
    _save_multi_panel(
        plt,
        out / "dual_replay_obs_position_series.png",
        [
            ("GNSS observation north", times, [("N", _values(obs_neu, "north_m"), "-")], "m"),
            ("GNSS observation east", times, [("E", _values(obs_neu, "east_m"), "-")], "m"),
            ("GNSS observation up", times, [("U", _values(obs_neu, "up_m"), "-")], "m"),
        ],
    )
    paths.append(out / "dual_replay_obs_position_series.png")
    _save_multi_panel(
        plt,
        out / "dual_replay_obs_velocity_series.png",
        [
            ("GNSS observation vn", times, [("vn", _values(input_rows, "vn"), "-")], "m/s"),
            ("GNSS observation ve", times, [("ve", _values(input_rows, "ve"), "-")], "m/s"),
            ("GNSS observation vd", times, [("vd", _values(input_rows, "vd"), "-")], "m/s"),
        ],
    )
    paths.append(out / "dual_replay_obs_velocity_series.png")
    _save_scatter(
        plt,
        out / "dual_replay_obs_yaw_scatter.png",
        times,
        _values(input_rows, "yaw"),
        title="dual replay GNSS observation yaw",
        xlabel="time since start (s)",
        ylabel="yaw (deg)",
    )
    paths.append(out / "dual_replay_obs_yaw_scatter.png")
    for filename, key, title in [
        ("dual_replay_obs_std_n.png", "std_n", "position north STD"),
        ("dual_replay_obs_std_e.png", "std_e", "position east STD"),
        ("dual_replay_obs_std_d.png", "std_d", "position down STD"),
        ("dual_replay_obs_std_vn.png", "std_vn", "velocity north STD"),
        ("dual_replay_obs_std_ve.png", "std_ve", "velocity east STD"),
        ("dual_replay_obs_std_vd.png", "std_vd", "velocity down STD"),
        ("dual_replay_obs_std_yaw.png", "yaw_std", "yaw STD"),
    ]:
        _save_line(
            plt,
            out / filename,
            times,
            [(key, _values(input_rows, key), "-")],
            title=f"dual replay observation {title}",
            xlabel="time since start (s)",
            ylabel="STD",
        )
        paths.append(out / filename)
    _save_multi_panel(
        plt,
        out / "dual_replay_obs_pos_std_combined.png",
        [
            ("position STD N", times, [("std_n", _values(input_rows, "std_n"), "-")], "m"),
            ("position STD E", times, [("std_e", _values(input_rows, "std_e"), "-")], "m"),
            ("position STD D", times, [("std_d", _values(input_rows, "std_d"), "-")], "m"),
        ],
    )
    paths.append(out / "dual_replay_obs_pos_std_combined.png")
    _save_multi_panel(
        plt,
        out / "dual_replay_obs_vel_std_combined.png",
        [
            ("velocity STD N", times, [("std_vn", _values(input_rows, "std_vn"), "-")], "m/s"),
            ("velocity STD E", times, [("std_ve", _values(input_rows, "std_ve"), "-")], "m/s"),
            ("velocity STD D", times, [("std_vd", _values(input_rows, "std_vd"), "-")], "m/s"),
        ],
    )
    paths.append(out / "dual_replay_obs_vel_std_combined.png")
    fig_path = out / "dual_replay_obs_quality_markers.png"
    fig, ax = plt.subplots(figsize=(9, 4.8))
    ax.plot(times, _values(input_rows, "yaw_std"), label="yaw std", linewidth=1.0)
    ax.plot(times, _values(input_rows, "std_n"), label="pos n std", linewidth=1.0)
    ax.plot(times, _values(input_rows, "std_vn"), label="vel n std", linewidth=1.0)
    ax.set_title("dual replay observation quality markers")
    ax.set_xlabel("time since start (s)")
    ax.set_ylabel("reported STD")
    ax.grid(True, linewidth=0.3, alpha=0.45)
    ax.legend(loc="best", fontsize=8)
    fig.tight_layout()
    fig.savefig(fig_path, dpi=150)
    plt.close(fig)
    paths.append(fig_path)
    return [str(path) for path in paths]


def _plot_summary_panel(
    plt,
    root: Path,
    replay_nav: list[dict[str, Any]],
    reference_rows: list[dict[str, Any]],
    error_rows: list[dict[str, Any]],
    metrics: dict[str, Any],
) -> str:
    out = root / "08_summary_panels"
    out.mkdir(parents=True, exist_ok=True)
    est_aligned, ref_aligned = _aligned_est_ref(replay_nav, reference_rows)
    origin = ref_aligned[0] if ref_aligned else reference_rows[0]
    est_neu = local_neu_from_origin(est_aligned, origin)
    ref_neu = local_neu_from_origin(ref_aligned, origin)
    err_times = _times(error_rows)
    fig, axes = plt.subplots(2, 2, figsize=(12, 8))
    axes[0][0].plot([row["east_m"] for row in ref_neu], [row["north_m"] for row in ref_neu], label="reference", linewidth=1.1)
    axes[0][0].plot([row["east_m"] for row in est_neu], [row["north_m"] for row in est_neu], label="replay estimate", linewidth=1.0, linestyle="--")
    axes[0][0].set_title("local trajectory")
    axes[0][0].set_aspect("equal", adjustable="datalim")
    axes[0][0].legend(fontsize=8)
    axes[0][1].plot(err_times, _values(error_rows, "horizontal_error_m"), linewidth=1.0)
    axes[0][1].set_title("horizontal error")
    axes[0][1].set_ylabel("m")
    axes[1][0].plot(err_times, _values(error_rows, "yaw_error_deg"), linewidth=1.0)
    axes[1][0].axhline(2.0, linestyle="--", linewidth=0.8, color="#555555")
    axes[1][0].axhline(-2.0, linestyle="--", linewidth=0.8, color="#555555")
    axes[1][0].set_title("yaw error (gate <= 2 deg, near-boundary)")
    axes[1][0].set_ylabel("deg")
    axes[1][1].plot(err_times, _values(error_rows, "roll_error_deg"), label="roll", linewidth=1.0)
    axes[1][1].plot(err_times, _values(error_rows, "pitch_error_deg"), label="pitch", linewidth=1.0)
    axes[1][1].axhline(1.6, linestyle="--", linewidth=0.8, color="#555555")
    axes[1][1].axhline(-1.6, linestyle="--", linewidth=0.8, color="#555555")
    axes[1][1].set_title("roll/pitch error (relaxed, not strict)")
    axes[1][1].legend(fontsize=8)
    for axis in axes.ravel():
        axis.grid(True, linewidth=0.3, alpha=0.45)
    fig.text(
        0.02,
        0.02,
        (
            f"H RMSE: {_safe_metric(metrics.get('horizontal_rmse_m')):.3f} m | "
            f"Up RMSE: {_safe_metric(metrics.get('up_rmse_m')):.3f} m | "
            f"Yaw RMSE: {_safe_metric(metrics.get('yaw_rmse_deg')):.3f} deg | "
            f"Roll/Pitch RMSE: {_safe_metric(metrics.get('roll_rmse_deg')):.3f}/"
            f"{_safe_metric(metrics.get('pitch_rmse_deg')):.3f} deg | "
            "manual visual review required"
        ),
        fontsize=10,
    )
    fig.tight_layout(rect=(0, 0.05, 1, 1))
    path = out / "dual_replay_summary_panel.png"
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return str(path)


def write_visual_case_review(
    output_dir: str | Path,
    *,
    metrics: dict[str, Any],
    gates: dict[str, Any],
    figure_paths: list[str],
    visual_sanity: dict[str, Any],
) -> dict[str, Any]:
    out = Path(output_dir) / "09_case_review"
    out.mkdir(parents=True, exist_ok=True)
    rel_figures = [str(Path(path).relative_to(output_dir)) for path in figure_paths if Path(path).is_file()]
    review = {
        "phase": "N4H2E",
        "fresh_replay_metrics": metrics,
        "target_gates": gates,
        "figure_list": rel_figures,
        "visual_sanity_checks": visual_sanity,
        "manual_review_required": True,
        "manual_visual_review_required": True,
        "no_formal_performance_claim": True,
        "old_summary_invalidated": True,
        "solver_output_changed": False,
        "trace_solver_input": False,
        "output_only_correction": False,
        "bad_epoch_deletion_for_metric": False,
        "numerical_performance_claim": False,
    }
    (out / "visual_case_review.json").write_text(json.dumps(review, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    lines = [
        "# N4H2E visual case review",
        "",
        "This case review is dual_final_v23-only fresh replay visual validation.",
        "",
        "## Metrics",
        "",
        f"- horizontal_rmse_m: {metrics.get('horizontal_rmse_m')}",
        f"- up_rmse_m: {metrics.get('up_rmse_m')}",
        f"- yaw_rmse_deg: {metrics.get('yaw_rmse_deg')}",
        f"- roll_rmse_deg: {metrics.get('roll_rmse_deg')}",
        f"- pitch_rmse_deg: {metrics.get('pitch_rmse_deg')}",
        "",
        "## Gates",
        "",
        f"- horizontal_gate_pass: {gates.get('horizontal_gate_pass')}",
        f"- up_gate_pass: {gates.get('up_gate_pass')}",
        f"- yaw_gate_pass: {gates.get('yaw_gate_pass')}",
        f"- roll_strict_gate_pass: {gates.get('roll_strict_gate_pass')}",
        f"- roll_relaxed_gate_pass: {gates.get('roll_relaxed_gate_pass')}",
        f"- pitch_strict_gate_pass: {gates.get('pitch_strict_gate_pass')}",
        f"- pitch_relaxed_gate_pass: {gates.get('pitch_relaxed_gate_pass')}",
        "",
        "## Visual Sanity",
        "",
        f"- time_monotonic: {visual_sanity.get('time_monotonic')}",
        f"- no_nan_inf: {visual_sanity.get('no_nan_inf')}",
        f"- yaw_wrap_spike_detected: {visual_sanity.get('yaw_wrap_spike_detected')}",
        f"- required_figures_generated: {visual_sanity.get('required_figures_generated')}",
        "",
        "## Boundary",
        "",
        "- manual_visual_review_required=true",
        "- solver_output_changed=false",
        "- trace_solver_input=false",
        "- output_only_correction=false",
        "- numerical_performance_claim=false",
        "- old_summary_invalidated=true",
        "",
        "## Figures",
        "",
    ]
    lines.extend([f"- {figure}" for figure in rel_figures])
    (out / "visual_case_review.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return review


def generate_dual_replay_plots(
    *,
    output_dir: str | Path,
    replay_nav_rows: list[dict[str, Any]],
    reference_rows: list[dict[str, Any]],
    error_rows: list[dict[str, Any]],
    replay_std_rows: list[dict[str, Any]],
    input_rows: list[dict[str, Any]],
    metrics: dict[str, Any],
    case_name: str,
    line_name: str,
) -> dict[str, Any]:
    plt, dependency_error = _load_matplotlib()
    if dependency_error:
        return {
            "phase": "N4H2E",
            **dependency_error,
            "manual_visual_review_required": True,
            "trace_solver_input": False,
            "output_only_correction": False,
            "solver_output_changed": False,
            "numerical_performance_claim": False,
        }
    root = Path(output_dir)
    for folder in PLOT_DIRS:
        (root / folder).mkdir(parents=True, exist_ok=True)
    figure_paths: list[str] = []
    evidence_missing: list[str] = []
    figure_paths.extend(_plot_trajectory(plt, root, replay_nav_rows, reference_rows, input_rows))
    figure_paths.extend(_plot_position_errors(plt, root, error_rows))
    figure_paths.extend(_plot_velocity(plt, root, replay_nav_rows, replay_std_rows))
    figure_paths.extend(_plot_attitude(plt, root, replay_nav_rows, reference_rows, error_rows, metrics))
    consistency_paths, consistency_missing = _plot_consistency(plt, root, error_rows, replay_std_rows)
    figure_paths.extend(consistency_paths)
    evidence_missing.extend(consistency_missing)
    origin = reference_rows[0] if reference_rows else replay_nav_rows[0]
    figure_paths.extend(_plot_observation_quality(plt, root, input_rows, origin))
    figure_paths.append(_plot_summary_panel(plt, root, replay_nav_rows, reference_rows, error_rows, metrics))
    return {
        "phase": "N4H2E",
        "plotting_status": "completed",
        "case_name": case_name,
        "line_name": line_name,
        "figure_paths": figure_paths,
        "figure_count": len([path for path in figure_paths if Path(path).suffix == ".png"]),
        "evidence_missing": evidence_missing,
        "dual_only": True,
        "manual_visual_review_required": True,
        "trace_solver_input": False,
        "output_only_correction": False,
        "solver_output_changed": False,
        "bad_epoch_deletion_for_metric": False,
        "numerical_performance_claim": False,
    }

