"""Runtime-only N8C3 Raw Doppler factor fix figures.

中文说明：N8C3 图像只写 runtime 目录，用于审查 residual/Jacobian 激活。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from legsa_gins.fgo.fgo_factor_types import RawDopplerVelocityFactorRow
from legsa_gins.fgo.fgo_raw_doppler_factor_contract import raw_doppler_residual, raw_doppler_whitened_residual
from legsa_gins.fgo.fgo_yaw_convention_fix import STATE_FIELDS, _f


MANDATORY_N8C3_FIGURES = [
    "raw_doppler_factor_rows_before_after.png",
    "residual_vector_dim_with_vs_without_raw.png",
    "raw_doppler_jacobian_nonzero_count.png",
    "raw_doppler_residual_solver_vs_proxy_time.png",
    "raw_doppler_whitened_residual_time.png",
    "raw_doppler_weight_sensitivity_yaw_delta.png",
    "raw_doppler_weight_sensitivity_horizontal_delta.png",
    "receiver_velocity_off_raw_on_vs_off.png",
    "raw_doppler_toggle_integrity_panel.png",
    "n8c3_decision_panel.png",
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
        "role_alias": "N8C3_FIGURE_OUTPUT_DIR",
    }


def _bar(ax: Any, labels: list[str], values: list[float], title: str, ylabel: str) -> None:
    ax.bar(range(len(labels)), values)
    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels, rotation=30, ha="right", fontsize=8)
    ax.set_title(title)
    ax.set_ylabel(ylabel)
    ax.grid(True, axis="y", alpha=0.3)


def _vectors_from_rows(rows: list[dict[str, Any]]) -> list[list[float]]:
    return [[_f(row.get(field)) for field in STATE_FIELDS] for row in rows]


def _raw_residual_time_series(rows: list[dict[str, Any]], factors: list[RawDopplerVelocityFactorRow]) -> tuple[list[float], list[float], list[float]]:
    vectors = _vectors_from_rows(rows)
    times: list[float] = []
    raw_norms: list[float] = []
    whitened_norms: list[float] = []
    for factor in factors:
        if factor.state_index >= len(vectors):
            continue
        residual = raw_doppler_residual(vectors[factor.state_index], factor)
        white = raw_doppler_whitened_residual(vectors[factor.state_index], factor, weight_scale=1.0)
        times.append(factor.time)
        raw_norms.append(sum(value * value for value in residual) ** 0.5)
        whitened_norms.append(sum(value * value for value in white) ** 0.5)
    return times, raw_norms, whitened_norms


def generate_n8c3_figures(
    *,
    figure_output_dir: str | Path,
    raw_factors: list[RawDopplerVelocityFactorRow],
    rows_by_variant: dict[str, list[dict[str, Any]]],
    variant_report: dict[str, Any],
    solver_injection_report: dict[str, Any],
    toggle_report: dict[str, Any],
    decision_preview: dict[str, Any],
) -> dict[str, Any]:
    plt = _plt()
    out = Path(figure_output_dir)
    generated: list[dict[str, Any]] = []
    variants = {row.get("variant"): row for row in variant_report.get("variants", [])}
    with_raw = variants.get("weak_yaw_smoothness_with_raw_fixed", {})
    without_raw = variants.get("raw_doppler_off_verified", {})

    fig, ax = plt.subplots(figsize=(7.5, 4.6))
    _bar(ax, ["with_raw", "raw_off"], [float(with_raw.get("raw_factor_rows", 0) or 0), float(without_raw.get("raw_factor_rows", 0) or 0)], "Raw Doppler factor rows before/after", "rows")
    generated.append(_save(fig, out / MANDATORY_N8C3_FIGURES[0], plt))

    fig, ax = plt.subplots(figsize=(7.5, 4.6))
    _bar(ax, ["with_raw", "raw_off"], [float(with_raw.get("solver_residual_dim", 0) or 0), float(without_raw.get("solver_residual_dim", 0) or 0)], "Residual vector dimension", "dim")
    generated.append(_save(fig, out / MANDATORY_N8C3_FIGURES[1], plt))

    fig, ax = plt.subplots(figsize=(7.5, 4.6))
    _bar(ax, ["with_raw", "raw_off"], [float(with_raw.get("jacobian_nonzero_count", 0) or 0), float(without_raw.get("jacobian_nonzero_count", 0) or 0)], "Raw Doppler Jacobian nonzero count", "nonzero")
    generated.append(_save(fig, out / MANDATORY_N8C3_FIGURES[2], plt))

    with_rows = rows_by_variant.get("weak_yaw_smoothness_with_raw_fixed", [])
    off_rows = rows_by_variant.get("raw_doppler_off_verified", [])
    times, solver_residual, whitened = _raw_residual_time_series(with_rows, raw_factors)
    _, proxy_residual, _ = _raw_residual_time_series(off_rows, raw_factors)
    fig, ax = plt.subplots(figsize=(9, 4.8))
    ax.plot(times, solver_residual, linewidth=1.0, label="solver residual")
    ax.plot(times[: len(proxy_residual)], proxy_residual, linewidth=1.0, linestyle="--", label="raw-off proxy")
    ax.set_title("Raw Doppler residual solver vs proxy time")
    ax.set_xlabel("time")
    ax.set_ylabel("mps norm")
    ax.legend()
    ax.grid(True, alpha=0.3)
    generated.append(_save(fig, out / MANDATORY_N8C3_FIGURES[3], plt))

    fig, ax = plt.subplots(figsize=(9, 4.8))
    ax.plot(times, whitened, linewidth=1.0)
    ax.set_title("Raw Doppler whitened residual time")
    ax.set_xlabel("time")
    ax.set_ylabel("whitened norm")
    ax.grid(True, alpha=0.3)
    generated.append(_save(fig, out / MANDATORY_N8C3_FIGURES[4], plt))

    summary_rows = list(variant_report.get("variants", []))
    labels = [str(row.get("variant")) for row in summary_rows]
    fig, ax = plt.subplots(figsize=(10.5, 4.8))
    _bar(ax, labels, [float(row.get("yaw_delta_wrapped_rmse_deg", 0.0) or 0.0) for row in summary_rows], "Raw Doppler weight sensitivity yaw delta", "deg")
    generated.append(_save(fig, out / MANDATORY_N8C3_FIGURES[5], plt))

    fig, ax = plt.subplots(figsize=(10.5, 4.8))
    _bar(ax, labels, [float(row.get("horizontal_delta_rmse_m", 0.0) or 0.0) for row in summary_rows], "Raw Doppler weight sensitivity horizontal delta", "m")
    generated.append(_save(fig, out / MANDATORY_N8C3_FIGURES[6], plt))

    raw_on = rows_by_variant.get("receiver_velocity_off_raw_on", [])
    raw_off = rows_by_variant.get("receiver_velocity_off_raw_off", [])
    times2 = [_f(row.get("time"), float(index)) for index, row in enumerate(raw_on)]
    deltas = [
        abs(_f(left.get("vn_mps")) - _f(right.get("vn_mps"))) + abs(_f(left.get("ve_mps")) - _f(right.get("ve_mps"))) + abs(_f(left.get("vd_mps")) - _f(right.get("vd_mps")))
        for left, right in zip(raw_on, raw_off)
    ]
    fig, ax = plt.subplots(figsize=(9, 4.8))
    ax.plot(times2[: len(deltas)], deltas, linewidth=1.0)
    ax.set_title("Receiver velocity off raw on vs off")
    ax.set_xlabel("time")
    ax.set_ylabel("velocity abs delta")
    ax.grid(True, alpha=0.3)
    generated.append(_save(fig, out / MANDATORY_N8C3_FIGURES[7], plt))

    fig, ax = plt.subplots(figsize=(9, 4.8))
    ax.axis("off")
    lines = [
        f"toggle_passed: {toggle_report.get('toggle_regression_passed')}",
        f"dim_delta: {solver_injection_report.get('dim_delta')}",
        f"residual_rows: {solver_injection_report.get('residual_row_count')}",
        f"jacobian_nonzero: {solver_injection_report.get('jacobian_nonzero_count')}",
    ]
    ax.text(0.02, 0.94, "\n".join(lines), va="top", family="monospace")
    ax.set_title("Raw Doppler toggle integrity panel")
    generated.append(_save(fig, out / MANDATORY_N8C3_FIGURES[8], plt))

    fig, ax = plt.subplots(figsize=(9, 4.8))
    ax.axis("off")
    decision_lines = [
        f"status: {decision_preview.get('status')}",
        f"next: {decision_preview.get('recommended_next_stage')}",
        f"appears_in_solver_residual_vector: {decision_preview.get('appears_in_solver_residual_vector')}",
        "no feedback, no substitution, no trace/final_v23 input",
        "diagnostic only; no paper performance claim",
    ]
    ax.text(0.02, 0.94, "\n".join(decision_lines), va="top", family="monospace")
    ax.set_title("N8C3 decision panel")
    generated.append(_save(fig, out / MANDATORY_N8C3_FIGURES[9], plt))

    paths = [out / name for name in MANDATORY_N8C3_FIGURES]
    return {
        "stage": "N8C3_raw_doppler_fgo_factor_fix",
        "required_figures": MANDATORY_N8C3_FIGURES,
        "figure_count_total": len(MANDATORY_N8C3_FIGURES),
        "generated_figures": generated,
        "required_figures_generated": all(path.exists() for path in paths),
        "required_figures_nonempty": all(path.exists() and path.stat().st_size > 0 for path in paths),
        "figure_role_alias": "N8C3_FIGURE_OUTPUT_DIR",
        "runtime_only": True,
        "paper_performance_claim": False,
    }
