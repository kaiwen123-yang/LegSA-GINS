"""Runtime-only N8C no-feedback FGO visual plots.

中文说明：N8C 图像只写 runtime figure 目录，展示诊断曲线，不做性能宣称。
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

from legsa_gins.fgo.fgo_angle_utils import safe_angle_diff_deg, shortest_angle_residual_deg
from legsa_gins.fgo.fgo_n8c_plot_coverage import MANDATORY_N8C_FIGURES, coverage_entry
from legsa_gins.fgo.fgo_yaw_convention_fix import _f


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
        "role_alias": "N8C_FIGURE_OUTPUT_DIR",
    }


def _time(rows: list[dict[str, Any]]) -> list[float]:
    return [_f(row.get("time", row.get("timestamp")), float(index)) for index, row in enumerate(rows)]


def _col(rows: list[dict[str, Any]], name: str) -> list[float]:
    return [_f(row.get(name)) for row in rows]


def _horizontal_error(ekf_rows: list[dict[str, Any]], fgo_rows: list[dict[str, Any]]) -> list[float]:
    values = []
    for ekf, fgo in zip(ekf_rows, fgo_rows):
        lat0 = math.radians(_f(ekf.get("lat_deg")))
        north = (_f(fgo.get("lat_deg")) - _f(ekf.get("lat_deg"))) * 111_320.0
        east = (_f(fgo.get("lon_deg")) - _f(ekf.get("lon_deg"))) * 111_320.0 * math.cos(lat0)
        values.append(math.sqrt(north * north + east * east))
    return values


def _horizontal_diff_between(left_rows: list[dict[str, Any]], right_rows: list[dict[str, Any]]) -> list[float]:
    return _horizontal_error(left_rows, right_rows)


def _delta(rows_a: list[dict[str, Any]], rows_b: list[dict[str, Any]], column: str) -> list[float]:
    return [_f(b.get(column)) - _f(a.get(column)) for a, b in zip(rows_a, rows_b)]


def _yaw_delta(ekf_rows: list[dict[str, Any]], fgo_rows: list[dict[str, Any]]) -> list[float]:
    return [shortest_angle_residual_deg(_f(fgo.get("yaw_deg")), _f(ekf.get("yaw_deg"))) for ekf, fgo in zip(ekf_rows, fgo_rows)]


def _angle_delta(rows_a: list[dict[str, Any]], rows_b: list[dict[str, Any]], column: str) -> list[float]:
    return [safe_angle_diff_deg(_f(b.get(column)), _f(a.get(column))) for a, b in zip(rows_a, rows_b)]


def _velocity_norm(ekf_rows: list[dict[str, Any]], fgo_rows: list[dict[str, Any]]) -> list[float]:
    values = []
    for ekf, fgo in zip(ekf_rows, fgo_rows):
        total = 0.0
        for column in ["vn_mps", "ve_mps", "vd_mps"]:
            total += (_f(fgo.get(column)) - _f(ekf.get(column))) ** 2
        values.append(math.sqrt(total))
    return values


def _go2_joint_proxy(ekf_rows: list[dict[str, Any]], fgo_rows: list[dict[str, Any]]) -> list[float]:
    values = []
    for ekf, fgo in zip(ekf_rows, fgo_rows):
        total = 0.0
        for column in ["roll_deg", "pitch_deg", "vn_mps", "ve_mps"]:
            if column.endswith("_deg"):
                total += safe_angle_diff_deg(_f(fgo.get(column)), _f(ekf.get(column))) ** 2
            else:
                total += (_f(fgo.get(column)) - _f(ekf.get(column))) ** 2
        values.append(math.sqrt(total))
    return values


def _yaw_smoothness(rows: list[dict[str, Any]]) -> list[float]:
    yaws = _col(rows, "yaw_deg")
    return [abs(safe_angle_diff_deg(right, left)) for left, right in zip(yaws, yaws[1:])]


def _bar(ax, labels: list[str], values: list[float], title: str, ylabel: str) -> None:
    ax.bar(range(len(labels)), values)
    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels, rotation=30, ha="right", fontsize=8)
    ax.set_title(title)
    ax.set_ylabel(ylabel)
    ax.grid(True, axis="y", alpha=0.3)


def generate_n8c_figures(
    *,
    figure_output_dir: str | Path,
    ekf_rows: list[dict[str, Any]],
    rows_by_variant: dict[str, list[dict[str, Any]]],
    ablation_summary: dict[str, Any],
    factor_weight_review: dict[str, Any],
    candidate_review: dict[str, Any],
    decision_preview: dict[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    plt = _plt()
    out = Path(figure_output_dir)
    generated: list[dict[str, Any]] = []
    coverage: list[dict[str, Any]] = []
    weak = rows_by_variant.get("weak_yaw_smoothness", [])
    default = rows_by_variant.get("default_active_stack_n8a2", [])
    go2_off = rows_by_variant.get("go2_joint_off", [])
    raw_off = rows_by_variant.get("raw_doppler_off", [])
    times = _time(ekf_rows)
    count = min(len(times), len(ekf_rows), len(weak), len(default))
    times = times[:count]
    ekf = ekf_rows[:count]
    weak = weak[:count]
    default = default[:count]
    go2_off = go2_off[:count]
    raw_off = raw_off[:count]

    def save_with_cov(fig, name: str, series: list[list[float]], *, x: list[float] | None = None, aggregate: bool = False, candidate_label: bool = False) -> None:
        path = out / name
        generated.append(_save(fig, path, plt))
        coverage.append(coverage_entry(figure_name=name, series=series, x_values=x, figure_path=path, aggregate_only=aggregate, diagnostic_candidate_label=candidate_label))

    fig, ax = plt.subplots(figsize=(7.2, 6.0))
    ax.plot(_col(ekf, "lon_deg"), _col(ekf, "lat_deg"), label="EKF baseline", linewidth=1.0)
    ax.plot(_col(weak, "lon_deg"), _col(weak, "lat_deg"), label="FGO weak yaw", linewidth=1.0)
    ax.set_title("FGO_vs_EKF_delta horizontal trajectory")
    ax.set_xlabel("lon deg")
    ax.set_ylabel("lat deg")
    ax.legend()
    ax.grid(True, alpha=0.3)
    save_with_cov(fig, MANDATORY_N8C_FIGURES[0], [_col(ekf, "lat_deg"), _col(weak, "lat_deg")], x=_col(ekf, "lon_deg"), aggregate=True)

    horizontal = _horizontal_error(ekf, weak)
    fig, ax = plt.subplots(figsize=(9, 4.6))
    ax.plot(times, horizontal, linewidth=1.0)
    ax.set_title("FGO minus EKF horizontal diff over time")
    ax.set_xlabel("time")
    ax.set_ylabel("m")
    ax.grid(True, alpha=0.3)
    save_with_cov(fig, MANDATORY_N8C_FIGURES[1], [horizontal], x=times)

    fig, ax = plt.subplots(figsize=(9, 4.6))
    ax.plot(times, _horizontal_error(ekf, default), label="default", linewidth=1.0)
    ax.plot(times, horizontal, label="weak yaw", linewidth=1.0)
    ax.set_title("EKF vs FGO weak yaw horizontal error")
    ax.set_xlabel("time")
    ax.set_ylabel("m")
    ax.legend()
    ax.grid(True, alpha=0.3)
    save_with_cov(fig, MANDATORY_N8C_FIGURES[2], [_horizontal_error(ekf, default), horizontal], x=times)

    up = _delta(ekf, weak, "height_m")
    fig, ax = plt.subplots(figsize=(9, 4.6))
    ax.plot(times, up, linewidth=1.0)
    ax.set_title("EKF vs FGO weak yaw up error")
    ax.set_xlabel("time")
    ax.set_ylabel("m")
    ax.grid(True, alpha=0.3)
    save_with_cov(fig, MANDATORY_N8C_FIGURES[3], [up], x=times)

    yaw = _yaw_delta(ekf, weak)
    fig, ax = plt.subplots(figsize=(9, 4.6))
    ax.plot(times, yaw, linewidth=1.0)
    ax.axhline(0.0, color="black", linewidth=0.8)
    ax.set_title("EKF vs FGO weak yaw yaw error")
    ax.set_xlabel("time")
    ax.set_ylabel("wrapped deg")
    ax.grid(True, alpha=0.3)
    save_with_cov(fig, MANDATORY_N8C_FIGURES[4], [yaw], x=times)

    roll = _angle_delta(ekf, weak, "roll_deg")
    pitch = _angle_delta(ekf, weak, "pitch_deg")
    fig, ax = plt.subplots(figsize=(9, 4.6))
    ax.plot(times, roll, label="roll", linewidth=1.0)
    ax.plot(times, pitch, label="pitch", linewidth=1.0)
    ax.set_title("EKF vs FGO weak yaw roll/pitch error")
    ax.set_xlabel("time")
    ax.set_ylabel("deg")
    ax.legend()
    ax.grid(True, alpha=0.3)
    save_with_cov(fig, MANDATORY_N8C_FIGURES[5], [roll, pitch], x=times)

    fig, ax = plt.subplots(figsize=(9, 4.6))
    ax.plot(times, _col(default, "yaw_deg"), label="default FGO", linewidth=1.0)
    ax.plot(times, _col(weak, "yaw_deg"), label="weak yaw FGO", linewidth=1.0)
    ax.set_title("Default vs weak yaw FGO yaw time")
    ax.set_xlabel("time")
    ax.set_ylabel("yaw deg")
    ax.legend()
    ax.grid(True, alpha=0.3)
    save_with_cov(fig, MANDATORY_N8C_FIGURES[6], [_col(default, "yaw_deg"), _col(weak, "yaw_deg")], x=times)

    default_yaw = _yaw_delta(ekf, default)
    fig, ax = plt.subplots(figsize=(9, 4.6))
    ax.plot(times, default_yaw, label="default", linewidth=1.0)
    ax.plot(times, yaw, label="weak yaw", linewidth=1.0)
    ax.set_title("Default vs weak yaw delta time")
    ax.set_xlabel("time")
    ax.set_ylabel("wrapped deg")
    ax.legend()
    ax.grid(True, alpha=0.3)
    save_with_cov(fig, MANDATORY_N8C_FIGURES[7], [default_yaw, yaw], x=times)

    smooth = _yaw_smoothness(weak)
    fig, ax = plt.subplots(figsize=(9, 4.6))
    ax.plot(times[1:], smooth, linewidth=1.0)
    ax.set_title("Weak yaw smoothness residual time")
    ax.set_xlabel("time")
    ax.set_ylabel("deg")
    ax.grid(True, alpha=0.3)
    save_with_cov(fig, MANDATORY_N8C_FIGURES[8], [smooth], x=times[1:])

    p95 = factor_weight_review.get("per_factor_residual_p95", {})
    labels = list(p95)
    values = [float(p95[name] or 0.0) for name in labels]
    fig, ax = plt.subplots(figsize=(10, 5.0))
    _bar(ax, labels, values, "Per-factor residual p95", "proxy p95")
    save_with_cov(fig, MANDATORY_N8C_FIGURES[9], [values], aggregate=True)

    receiver_pos = horizontal
    fig, ax = plt.subplots(figsize=(9, 4.6))
    ax.plot(times, receiver_pos, linewidth=1.0)
    ax.set_title("Receiver position residual proxy time")
    ax.set_xlabel("time")
    ax.set_ylabel("m")
    ax.grid(True, alpha=0.3)
    save_with_cov(fig, MANDATORY_N8C_FIGURES[10], [receiver_pos], x=times)

    receiver_vel = _velocity_norm(ekf, weak)
    fig, ax = plt.subplots(figsize=(9, 4.6))
    ax.plot(times, receiver_vel, linewidth=1.0)
    ax.set_title("Receiver velocity residual proxy time")
    ax.set_xlabel("time")
    ax.set_ylabel("mps")
    ax.grid(True, alpha=0.3)
    save_with_cov(fig, MANDATORY_N8C_FIGURES[11], [receiver_vel], x=times)

    fig, ax = plt.subplots(figsize=(9, 4.6))
    ax.plot(times, [abs(value) for value in yaw], linewidth=1.0)
    ax.set_title("Dual yaw residual proxy time")
    ax.set_xlabel("time")
    ax.set_ylabel("abs deg")
    ax.grid(True, alpha=0.3)
    save_with_cov(fig, MANDATORY_N8C_FIGURES[12], [[abs(value) for value in yaw]], x=times)

    fig, ax = plt.subplots(figsize=(9, 4.6))
    ax.plot(times, receiver_vel, linewidth=1.0)
    ax.set_title("Raw Doppler residual proxy time")
    ax.set_xlabel("time")
    ax.set_ylabel("mps")
    ax.grid(True, alpha=0.3)
    save_with_cov(fig, MANDATORY_N8C_FIGURES[13], [receiver_vel], x=times)

    go2_joint = _go2_joint_proxy(ekf, weak)
    fig, ax = plt.subplots(figsize=(9, 4.6))
    ax.plot(times, go2_joint, linewidth=1.0)
    ax.set_title("Go2 joint factor residual proxy time")
    ax.set_xlabel("time")
    ax.set_ylabel("proxy norm")
    ax.grid(True, alpha=0.3)
    save_with_cov(fig, MANDATORY_N8C_FIGURES[14], [go2_joint], x=times)

    fig, ax = plt.subplots(figsize=(9, 4.6))
    ax.plot(times[1:], smooth, linewidth=1.0)
    ax.set_title("Smoothness factor residual proxy time")
    ax.set_xlabel("time")
    ax.set_ylabel("deg")
    ax.grid(True, alpha=0.3)
    save_with_cov(fig, MANDATORY_N8C_FIGURES[15], [smooth], x=times[1:])

    variants = {row.get("variant"): row for row in ablation_summary.get("variants", [])}
    off_labels = ["weak_yaw", "go2_joint_off", "raw_doppler_off", "candidate_stack"]
    off_values = [
        float(variants.get("weak_yaw_smoothness", {}).get("yaw_delta_wrapped_rmse_deg", 0.0) or 0.0),
        float(variants.get("go2_joint_off", {}).get("yaw_delta_wrapped_rmse_deg", 0.0) or 0.0),
        float(variants.get("raw_doppler_off", {}).get("yaw_delta_wrapped_rmse_deg", 0.0) or 0.0),
        float(variants.get("candidate_stack_diagnostic", {}).get("yaw_delta_wrapped_rmse_deg", 0.0) or 0.0),
    ]
    fig, ax = plt.subplots(figsize=(8.5, 4.6))
    _bar(ax, off_labels, off_values, "Factor on/off metric delta", "yaw RMSE deg")
    save_with_cov(fig, MANDATORY_N8C_FIGURES[16], [off_values], aggregate=True)

    go2_delta = _horizontal_diff_between(default, go2_off)
    fig, ax = plt.subplots(figsize=(9, 4.6))
    ax.plot(times[: len(go2_delta)], go2_delta, linewidth=1.0)
    ax.set_title("Go2 joint on/off delta time")
    ax.set_xlabel("time")
    ax.set_ylabel("m")
    ax.grid(True, alpha=0.3)
    save_with_cov(fig, MANDATORY_N8C_FIGURES[17], [go2_delta], x=times[: len(go2_delta)])

    raw_delta = _horizontal_diff_between(default, raw_off)
    fig, ax = plt.subplots(figsize=(9, 4.6))
    ax.plot(times[: len(raw_delta)], raw_delta, linewidth=1.0)
    ax.set_title("Raw Doppler on/off delta time")
    ax.set_xlabel("time")
    ax.set_ylabel("m")
    ax.grid(True, alpha=0.3)
    save_with_cov(fig, MANDATORY_N8C_FIGURES[18], [raw_delta], x=times[: len(raw_delta)])

    cand_rows = list(candidate_review.get("candidate_factor_reviews", []))
    cand_labels = [str(row.get("factor_type", "")) for row in cand_rows]
    cand_values = [float(row.get("yaw_delta_wrapped_rmse_deg", 0.0) or 0.0) for row in cand_rows]
    fig, ax = plt.subplots(figsize=(9, 4.6))
    _bar(ax, cand_labels, cand_values, "Candidate factor diagnostic-only delta", "yaw RMSE deg")
    save_with_cov(fig, MANDATORY_N8C_FIGURES[19], [cand_values], aggregate=True, candidate_label=True)

    fig, ax = plt.subplots(figsize=(9, 4.6))
    ax.axis("off")
    lines = [
        f"status: {decision_preview.get('status')}",
        f"next: {decision_preview.get('recommended_next_stage')}",
        f"weak_yaw_visualized: true",
        "no feedback, no substitution, no trace/final_v23 input",
        "candidate factors diagnostic-only",
    ]
    ax.text(0.02, 0.92, "\n".join(lines), va="top", family="monospace")
    ax.set_title("N8C visual decision panel")
    save_with_cov(fig, MANDATORY_N8C_FIGURES[20], [[1.0]], aggregate=True)

    fig, ax = plt.subplots(figsize=(9, 4.6))
    ax.axis("off")
    weak_summary = variants.get("weak_yaw_smoothness", {})
    summary_lines = [
        f"weak yaw RMSE deg: {weak_summary.get('yaw_delta_wrapped_rmse_deg')}",
        f"weak horizontal RMSE m: {weak_summary.get('horizontal_delta_rmse_m')}",
        f"default yaw RMSE deg: {variants.get('default_active_stack_n8a2', {}).get('yaw_delta_wrapped_rmse_deg')}",
        f"figure_count: {len(MANDATORY_N8C_FIGURES)}",
        "metric namespace: FGO_vs_EKF_delta",
    ]
    ax.text(0.02, 0.92, "\n".join(summary_lines), va="top", family="monospace")
    ax.set_title("N8C metric summary panel")
    save_with_cov(fig, MANDATORY_N8C_FIGURES[21], [[1.0]], aggregate=True)

    paths = [out / name for name in MANDATORY_N8C_FIGURES]
    manifest = {
        "stage": "N8C_no_feedback_fgo_visual_validation",
        "required_figures": MANDATORY_N8C_FIGURES,
        "figure_count_total": len(MANDATORY_N8C_FIGURES),
        "generated_figures": generated,
        "required_figures_generated": all(path.exists() for path in paths),
        "required_figures_nonempty": all(path.exists() and path.stat().st_size > 0 for path in paths),
        "figure_role_alias": "N8C_FIGURE_OUTPUT_DIR",
        "runtime_only": True,
        "paper_performance_claim": False,
    }
    return manifest, coverage
