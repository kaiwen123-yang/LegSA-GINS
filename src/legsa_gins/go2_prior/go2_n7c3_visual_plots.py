"""N7C3 plots for bounded adaptive Go2 horizontal velocity std.

中文说明：本模块生成运行期图像验证文件，图像不进入版本库。
"""

from __future__ import annotations

import csv
import math
from pathlib import Path
from typing import Any


REQUIRED_N7C3_FIGURES = [
    "confidence_timeline.png",
    "bounded_adaptive_std_timeline.png",
    "update_flag_timeline.png",
    "fixed_vs_bounded_adaptive_clean_horizontal_error.png",
    "fixed_vs_bounded_adaptive_clean_yaw_error.png",
    "adaptive_residual_time.png",
    "confidence_vs_residual_scatter.png",
    "stress_fixed_vs_bounded_adaptive_delta.png",
    "vertical_disabled_bounded_adaptive_check.png",
    "n7c3_decision_panel.png",
]


def _load_matplotlib():
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    return plt


def _f(value: Any, fallback: float = 0.0) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return fallback
    return out if math.isfinite(out) else fallback


def _read_csv(path: str | Path) -> list[dict[str, Any]]:
    source = Path(path)
    if not source.exists():
        return []
    with source.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _times(rows: list[dict[str, Any]]) -> list[float]:
    if not rows:
        return []
    t0 = _f(rows[0].get("time"), 0.0)
    return [_f(row.get("time"), t0) - t0 for row in rows]


def _values(rows: list[dict[str, Any]], key: str) -> list[float]:
    return [_f(row.get(key), 0.0) for row in rows]


def _local_horizontal(rows: list[dict[str, Any]], ref_rows: list[dict[str, Any]] | None = None) -> list[float]:
    if not rows:
        return []
    ref = ref_rows or rows
    lat0 = math.radians(_f(ref[0].get("lat_deg"), 0.0))
    lon0 = math.radians(_f(ref[0].get("lon_deg"), 0.0))
    cos_lat = math.cos(lat0)
    out: list[float] = []
    for row in rows:
        north = (math.radians(_f(row.get("lat_deg"), 0.0)) - lat0) * 6378137.0
        east = (math.radians(_f(row.get("lon_deg"), 0.0)) - lon0) * 6378137.0 * cos_lat
        out.append(math.hypot(north, east))
    return out


def _axis(plt, figsize: tuple[float, float] = (9.2, 5.0)):
    fig = plt.figure(figsize=figsize)
    ax = fig.add_axes([0.12, 0.16, 0.82, 0.74])
    return fig, ax


def _save(fig, path: Path, plt) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=150)
    plt.close(fig)


def _decorate(ax, title: str, ylabel: str) -> None:
    ax.set_title(title)
    ax.set_xlabel("time since start (s)")
    ax.set_ylabel(ylabel)
    ax.grid(True, linewidth=0.3, alpha=0.45)
    if ax.get_legend_handles_labels()[0]:
        ax.legend(loc="best", fontsize=8)


def _variant_eval(output_dir: Path, variant_id: str) -> list[dict[str, Any]]:
    return _read_csv(output_dir / "variants" / variant_id / "EVAL_NAV.csv")


def _trace(output_dir: Path, variant_id: str) -> list[dict[str, Any]]:
    return _read_csv(output_dir / "variants" / variant_id / "SOURCE_AWARE_WEIGHT_TRACE.csv")


def _nonempty(path: Path) -> bool:
    return path.exists() and path.stat().st_size > 0


def generate_n7c3_visual_plots(
    *,
    figure_output_dir: str | Path,
    output_dir: str | Path,
    confidence_rows: list[dict[str, Any]],
    adaptive_prior_rows: list[dict[str, Any]],
    comparison_report: dict[str, Any],
    decision: dict[str, Any],
) -> dict[str, Any]:
    plt = _load_matplotlib()
    root = Path(figure_output_dir)
    out = Path(output_dir)
    generated: list[dict[str, Any]] = []

    rel = REQUIRED_N7C3_FIGURES[0]
    fig, ax = _axis(plt)
    t = _times(confidence_rows)
    for key, color in [
        ("confidence", "#1f77b4"),
        ("contact_confidence", "#2ca02c"),
        ("frame_confidence", "#9467bd"),
        ("cross_source_consistency_confidence", "#ff7f0e"),
    ]:
        ax.plot(t, _values(confidence_rows, key), label=key, linewidth=0.9, alpha=0.85, color=color)
    _decorate(ax, "N7C3 bounded confidence timeline", "confidence")
    _save(fig, root / rel, plt)
    generated.append({"figure_name": rel, "source_rows": len(confidence_rows)})

    rel = REQUIRED_N7C3_FIGURES[1]
    fig, ax = _axis(plt)
    pt = _times(adaptive_prior_rows)
    ax.plot(pt, _values(adaptive_prior_rows, "std_vn"), label="std_vn", linewidth=0.9)
    ax.plot(pt, _values(adaptive_prior_rows, "std_ve"), label="std_ve", linestyle="--", linewidth=0.9)
    ax.axhline(5.0, color="#d62728", linewidth=0.8, linestyle=":", label="5 m/s cap")
    _decorate(ax, "N7C3 bounded adaptive horizontal std", "std (m/s)")
    _save(fig, root / rel, plt)
    generated.append({"figure_name": rel, "source_rows": len(adaptive_prior_rows)})

    rel = REQUIRED_N7C3_FIGURES[2]
    fig, ax = _axis(plt)
    flags = [1.0 if str(row.get("update_flag")).lower() == "true" else 0.0 for row in adaptive_prior_rows]
    ax.step(pt, flags, where="post", label="update_flag", linewidth=0.9)
    _decorate(ax, "N7C3 update flag timeline", "update=1 skip=0")
    _save(fig, root / rel, plt)
    generated.append({"figure_name": rel, "source_rows": len(adaptive_prior_rows)})

    fixed = _variant_eval(out, "fixed_std_2mps_main")
    adaptive = _variant_eval(out, "bounded_adaptive_std_soft_gating")
    fixed_t = _times(fixed)
    adaptive_t = _times(adaptive)
    fixed_h = _local_horizontal(fixed, fixed)
    adaptive_h = _local_horizontal(adaptive, fixed)
    rel = REQUIRED_N7C3_FIGURES[3]
    fig, ax = _axis(plt)
    ax.plot(fixed_t, fixed_h, label="fixed_std_2mps", linewidth=0.9, alpha=0.75)
    ax.plot(adaptive_t, adaptive_h, label="bounded_adaptive", linewidth=0.9, alpha=0.75, linestyle="--")
    _decorate(ax, "N7C3 fixed vs bounded adaptive clean horizontal", "local horizontal proxy (m)")
    _save(fig, root / rel, plt)
    generated.append({"figure_name": rel, "source_rows": min(len(fixed_h), len(adaptive_h))})

    rel = REQUIRED_N7C3_FIGURES[4]
    fig, ax = _axis(plt)
    ax.plot(fixed_t, _values(fixed, "yaw_deg"), label="fixed_std_2mps", linewidth=0.9, alpha=0.75)
    ax.plot(adaptive_t, _values(adaptive, "yaw_deg"), label="bounded_adaptive", linewidth=0.9, alpha=0.75, linestyle="--")
    _decorate(ax, "N7C3 fixed vs bounded adaptive clean yaw", "yaw (deg)")
    _save(fig, root / rel, plt)
    generated.append({"figure_name": rel, "source_rows": min(len(fixed), len(adaptive))})

    trace = _trace(out, "bounded_adaptive_std_soft_gating")
    rel = REQUIRED_N7C3_FIGURES[5]
    fig, ax = _axis(plt)
    tt = _times(trace)
    ax.plot(tt, _values(trace, "residual_norm"), label="residual_norm", linewidth=0.9)
    ax.plot(tt, _values(trace, "normalized_innovation"), label="normalized_innovation", linewidth=0.9, linestyle="--")
    _decorate(ax, "N7C3 bounded adaptive residual time", "residual / normalized innovation")
    _save(fig, root / rel, plt)
    generated.append({"figure_name": rel, "source_rows": len(trace)})

    rel = REQUIRED_N7C3_FIGURES[6]
    fig, ax = _axis(plt)
    confidence_by_time = {_f(row.get("time"), 0.0): _f(row.get("confidence"), 0.0) for row in confidence_rows}
    xs: list[float] = []
    ys: list[float] = []
    for row in trace:
        if not confidence_by_time:
            break
        time_value = _f(row.get("time"), 0.0)
        nearest_time = min(confidence_by_time, key=lambda value: abs(value - time_value))
        xs.append(confidence_by_time[nearest_time])
        ys.append(_f(row.get("residual_norm"), 0.0))
    ax.scatter(xs, ys, s=8, alpha=0.65)
    ax.set_title("N7C3 confidence vs residual")
    ax.set_xlabel("confidence")
    ax.set_ylabel("residual norm")
    ax.grid(True, linewidth=0.3, alpha=0.45)
    _save(fig, root / rel, plt)
    generated.append({"figure_name": rel, "source_rows": len(xs)})

    rel = REQUIRED_N7C3_FIGURES[7]
    fig, ax = _axis(plt)
    labels = ["receiver_stress", "raw_doppler_stress"]
    values = [
        comparison_report.get("comparisons", {}).get("receiver_velocity_stress_bounded_adaptive_minus_fixed", {}).get("delta", {}).get("horizontal_rmse_m"),
        comparison_report.get("comparisons", {}).get("raw_doppler_stress_bounded_adaptive_minus_fixed", {}).get("delta", {}).get("horizontal_rmse_m"),
    ]
    ax.bar(labels, [_f(value, 0.0) for value in values], color=["#1f77b4", "#ff7f0e"])
    ax.axhline(0.0, color="#333333", linewidth=0.8)
    ax.set_title("N7C3 stress fixed vs bounded adaptive delta")
    ax.set_ylabel("horizontal RMSE delta (m)")
    ax.grid(True, axis="y", linewidth=0.3, alpha=0.45)
    _save(fig, root / rel, plt)
    generated.append({"figure_name": rel, "source_rows": 2})

    rel = REQUIRED_N7C3_FIGURES[8]
    fig, ax = _axis(plt)
    ax.plot(pt, _values(adaptive_prior_rows, "std_vd"), label="std_vd", linewidth=0.9)
    ax.axhline(999.0, color="#d62728", linestyle=":", linewidth=0.8, label="disabled threshold")
    _decorate(ax, "N7C3 vertical disabled bounded adaptive check", "std_vd (m/s)")
    _save(fig, root / rel, plt)
    generated.append({"figure_name": rel, "source_rows": len(adaptive_prior_rows)})

    rel = REQUIRED_N7C3_FIGURES[9]
    fig, ax = _axis(plt)
    ax.axis("off")
    lines = [
        "N7C3 bounded adaptive std decision",
        f"status: {decision.get('status')}",
        f"max_std: {decision.get('max_std')}",
        f"update_count: {decision.get('update_count')}",
        f"skip_count: {decision.get('skip_count')}",
        f"clean delta: {decision.get('clean_bounded_adaptive_minus_fixed_horizontal_rmse_delta_m')}",
        f"vertical_disabled: {decision.get('vertical_disabled')}",
        "Go2 velocity not truth; no trace/final_v23 tuning; no paper claim.",
    ]
    ax.text(0.02, 0.95, "\n".join(lines), va="top", ha="left", family="monospace", fontsize=9)
    ax.set_title("N7C3 decision panel")
    _save(fig, root / rel, plt)
    generated.append({"figure_name": rel, "source_rows": 1})

    paths = [root / name for name in REQUIRED_N7C3_FIGURES]
    return {
        "stage": "N7C3_go2_horizontal_velocity_bounded_adaptive_std",
        "figure_count_total": len(REQUIRED_N7C3_FIGURES),
        "required_figure_count": len(REQUIRED_N7C3_FIGURES),
        "required_figures": list(REQUIRED_N7C3_FIGURES),
        "generated_figures": generated,
        "required_figures_generated": all(path.exists() for path in paths),
        "required_figures_nonempty": all(_nonempty(path) for path in paths),
        "figure_role_alias": "N7C3_FIGURE_OUTPUT_DIR",
        "paper_performance_claim": False,
        "go2_velocity_truth_claim": False,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "no_outperform_final_v23_claim": True,
        "fgo": False,
    }
