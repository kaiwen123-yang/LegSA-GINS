"""N7C2 readability plots for overlapped Go2 horizontal velocity visuals.

中文说明：本模块只根据 N7C/N7C1 runtime source data 重新绘制更易读的图，
不修改 solver、不调参、不删除 epoch，也不把图像解释成 paper performance claim。
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

from legsa_gins.go2_prior.go2_n7c_visual_overlap_audit import (
    _local_horizontal_m,
    _times,
    _values,
)


REQUIRED_N7C2_READABILITY_FIGURES = [
    "clean_horizontal_error_no_go2_vs_go2_alpha_style.png",
    "clean_horizontal_delta_go2_minus_no_go2_zoom.png",
    "clean_yaw_error_no_go2_vs_go2_alpha_style.png",
    "clean_yaw_delta_go2_minus_no_go2_zoom.png",
    "go2_horizontal_velocity_vs_receiver_split_components.png",
    "go2_horizontal_velocity_vs_raw_doppler_split_components.png",
    "go2_prior_std_policy_annotated.png",
    "vertical_disabled_annotated.png",
    "update_residual_zoom.png",
    "n7c2_visual_overlap_summary.png",
]


def _load_matplotlib():
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    return plt


def _finite(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if math.isfinite(number) else default


def _axis(plt, figsize: tuple[float, float] = (9.4, 5.2)):
    fig = plt.figure(figsize=figsize)
    ax = fig.add_axes([0.12, 0.16, 0.82, 0.74])
    return fig, ax


def _save(fig, path: Path, plt) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=150)
    plt.close(fig)


def _paired(lhs: list[float], rhs: list[float]) -> tuple[list[float], list[float]]:
    count = min(len(lhs), len(rhs))
    return lhs[:count], rhs[:count]


def _diff(lhs: list[float], rhs: list[float]) -> list[float]:
    left, right = _paired(lhs, rhs)
    return [right[index] - left[index] for index in range(len(left))]


def _markevery(values: list[Any]) -> int:
    return max(1, len(values) // 120)


def _receiver_time(rows: list[dict[str, Any]]) -> list[float]:
    return _times(rows, "time")


def _prior_time(rows: list[dict[str, Any]]) -> list[float]:
    return _times(rows, "time")


def _trace_time(rows: list[dict[str, Any]]) -> list[float]:
    return _times(rows, "time")


def _line_style(ax, x: list[float], y: list[float], *, label: str, color: str, linestyle: str, marker: str, alpha: float) -> None:
    count = min(len(x), len(y))
    ax.plot(
        x[:count],
        y[:count],
        label=label,
        color=color,
        linestyle=linestyle,
        linewidth=1.0,
        alpha=alpha,
        marker=marker,
        markersize=2.4,
        markevery=_markevery(y[:count]),
    )


def _decorate(ax, title: str, ylabel: str) -> None:
    ax.set_title(title)
    ax.set_xlabel("time since start (s)")
    ax.set_ylabel(ylabel)
    ax.grid(True, linewidth=0.3, alpha=0.45)
    handles, _ = ax.get_legend_handles_labels()
    if handles:
        ax.legend(loc="best", fontsize=8)


def _annotate_overlap(ax, overlap_report: dict[str, Any], figure_name: str) -> None:
    for item in overlap_report.get("overlap_items", []):
        if item.get("figure_name") == figure_name:
            status = item.get("visible_difference_status", "unknown")
            p95 = float(item.get("p95_abs_diff", 0.0) or 0.0)
            ax.text(
                0.02,
                0.94,
                f"{status}; p95 diff={p95:.3g}. Diagnostic only.",
                transform=ax.transAxes,
                va="top",
                ha="left",
                fontsize=8,
                bbox={"facecolor": "white", "edgecolor": "#777777", "alpha": 0.78, "pad": 4},
            )
            return


def _text_panel(plt, path: Path, title: str, lines: list[str]) -> None:
    fig, ax = _axis(plt)
    ax.axis("off")
    ax.set_title(title)
    ax.text(0.02, 0.95, "\n".join(lines), va="top", ha="left", fontsize=9, family="monospace")
    _save(fig, path, plt)


def _nonempty(path: Path) -> bool:
    return path.exists() and path.stat().st_size > 0


def generate_n7c2_readability_figures(
    *,
    source_data: dict[str, Any],
    overlap_report: dict[str, Any],
    figure_output_dir: str | Path,
) -> dict[str, Any]:
    """Generate all mandatory N7C2 readability figures."""

    plt = _load_matplotlib()
    root = Path(figure_output_dir)
    generated: list[dict[str, Any]] = []
    baseline = source_data.get("baseline_eval_nav", [])
    main = source_data.get("main_eval_nav", [])
    prior_rows = source_data.get("prior_rows", [])
    raw_rows = source_data.get("raw_doppler_rows", [])
    trace_rows = source_data.get("go2_trace_rows", [])

    base_t = _receiver_time(baseline)
    main_t = _receiver_time(main)
    paired_t = base_t[: min(len(base_t), len(main_t))]
    base_horizontal = _local_horizontal_m(baseline, baseline)
    main_horizontal = _local_horizontal_m(main, baseline)
    base_yaw = _values(baseline, "yaw_deg")
    main_yaw = _values(main, "yaw_deg")

    rel = REQUIRED_N7C2_READABILITY_FIGURES[0]
    fig, ax = _axis(plt)
    _line_style(ax, base_t, base_horizontal, label="no_go2", color="#1f77b4", linestyle="-", marker="o", alpha=0.72)
    _line_style(ax, main_t, main_horizontal, label="go2_horizontal", color="#d62728", linestyle="--", marker="x", alpha=0.62)
    _decorate(ax, "N7C2 clean horizontal overlay with separated style", "local horizontal proxy (m)")
    _annotate_overlap(ax, overlap_report, "clean_horizontal_error_no_go2_vs_go2_horizontal.png")
    _save(fig, root / rel, plt)
    generated.append({"figure_name": rel, "source_rows": min(len(base_horizontal), len(main_horizontal)), "kind": "overlay"})

    rel = REQUIRED_N7C2_READABILITY_FIGURES[1]
    delta_h = _diff(base_horizontal, main_horizontal)
    fig, ax = _axis(plt)
    ax.plot(paired_t[: len(delta_h)], delta_h, color="#6a3d9a", linewidth=1.0)
    ax.axhline(0.0, color="#333333", linewidth=0.6)
    _decorate(ax, "N7C2 horizontal delta zoom (go2 - no_go2)", "delta local horizontal proxy (m)")
    ax.text(0.02, 0.94, "Delta has its own y-axis; no performance claim.", transform=ax.transAxes, va="top", fontsize=8)
    _save(fig, root / rel, plt)
    generated.append({"figure_name": rel, "source_rows": len(delta_h), "kind": "delta_zoom"})

    rel = REQUIRED_N7C2_READABILITY_FIGURES[2]
    fig, ax = _axis(plt)
    _line_style(ax, base_t, base_yaw, label="no_go2", color="#1f77b4", linestyle="-", marker="o", alpha=0.72)
    _line_style(ax, main_t, main_yaw, label="go2_horizontal", color="#d62728", linestyle="--", marker="x", alpha=0.62)
    _decorate(ax, "N7C2 clean yaw overlay with separated style", "yaw (deg)")
    _annotate_overlap(ax, overlap_report, "clean_yaw_error_no_go2_vs_go2_horizontal.png")
    _save(fig, root / rel, plt)
    generated.append({"figure_name": rel, "source_rows": min(len(base_yaw), len(main_yaw)), "kind": "overlay"})

    rel = REQUIRED_N7C2_READABILITY_FIGURES[3]
    delta_yaw = _diff(base_yaw, main_yaw)
    fig, ax = _axis(plt)
    ax.plot(paired_t[: len(delta_yaw)], delta_yaw, color="#b15928", linewidth=1.0)
    ax.axhline(0.0, color="#333333", linewidth=0.6)
    _decorate(ax, "N7C2 yaw delta zoom (go2 - no_go2)", "delta yaw (deg)")
    ax.text(0.02, 0.94, "Delta view explains visually overlapped curves.", transform=ax.transAxes, va="top", fontsize=8)
    _save(fig, root / rel, plt)
    generated.append({"figure_name": rel, "source_rows": len(delta_yaw), "kind": "delta_zoom"})

    rel = REQUIRED_N7C2_READABILITY_FIGURES[4]
    prior_t = _prior_time(prior_rows)
    receiver_t = _receiver_time(main)
    fig, ax = _axis(plt)
    _line_style(ax, prior_t, _values(prior_rows, "vn"), label="go2_vn", color="#2ca02c", linestyle="-", marker=".", alpha=0.72)
    _line_style(ax, prior_t, _values(prior_rows, "ve"), label="go2_ve", color="#9467bd", linestyle="-", marker=".", alpha=0.72)
    _line_style(ax, receiver_t, _values(main, "vn"), label="receiver_vn", color="#1f77b4", linestyle="--", marker="o", alpha=0.56)
    _line_style(ax, receiver_t, _values(main, "ve"), label="receiver_ve", color="#ff7f0e", linestyle="--", marker="x", alpha=0.56)
    _decorate(ax, "N7C2 Go2 horizontal velocity vs receiver output", "velocity (m/s)")
    _save(fig, root / rel, plt)
    generated.append({"figure_name": rel, "source_rows": min(len(prior_rows), len(main)), "kind": "split_components"})

    rel = REQUIRED_N7C2_READABILITY_FIGURES[5]
    raw_t = _prior_time(raw_rows)
    fig, ax = _axis(plt)
    _line_style(ax, prior_t, _values(prior_rows, "vn"), label="go2_vn", color="#2ca02c", linestyle="-", marker=".", alpha=0.72)
    _line_style(ax, prior_t, _values(prior_rows, "ve"), label="go2_ve", color="#9467bd", linestyle="-", marker=".", alpha=0.72)
    _line_style(ax, raw_t, _values(raw_rows, "vn"), label="raw_doppler_vn", color="#1f77b4", linestyle="--", marker="o", alpha=0.56)
    _line_style(ax, raw_t, _values(raw_rows, "ve"), label="raw_doppler_ve", color="#ff7f0e", linestyle="--", marker="x", alpha=0.56)
    _decorate(ax, "N7C2 Go2 horizontal velocity vs raw Doppler", "velocity (m/s)")
    _save(fig, root / rel, plt)
    generated.append({"figure_name": rel, "source_rows": min(len(prior_rows), len(raw_rows)) if raw_rows else len(prior_rows), "kind": "split_components"})

    rel = REQUIRED_N7C2_READABILITY_FIGURES[6]
    fig, ax = _axis(plt)
    _line_style(ax, prior_t, _values(prior_rows, "std_vn"), label="std_vn", color="#2ca02c", linestyle="-", marker=".", alpha=0.80)
    _line_style(ax, prior_t, _values(prior_rows, "std_ve"), label="std_ve", color="#9467bd", linestyle="--", marker="x", alpha=0.80)
    _decorate(ax, "N7C2 horizontal prior std policy (annotated)", "std (m/s)")
    ax.text(0.02, 0.94, "Conservative weak prior; no R shrink, no trace/final_v23 tuning.", transform=ax.transAxes, va="top", fontsize=8)
    _save(fig, root / rel, plt)
    generated.append({"figure_name": rel, "source_rows": len(prior_rows), "kind": "policy"})

    rel = REQUIRED_N7C2_READABILITY_FIGURES[7]
    fig, ax = _axis(plt)
    std_vd = _values(prior_rows, "std_vd")
    _line_style(ax, prior_t, std_vd, label="std_vd_disabled", color="#d62728", linestyle="-", marker=".", alpha=0.70)
    _decorate(ax, "N7C2 vertical velocity disabled evidence", "std_vd (m/s)")
    disabled_count = sum(1 for value in std_vd if value >= 999.0)
    ax.text(0.02, 0.94, f"std_vd>=999 rows: {disabled_count}; no effective vd update.", transform=ax.transAxes, va="top", fontsize=8)
    _save(fig, root / rel, plt)
    generated.append({"figure_name": rel, "source_rows": len(std_vd), "kind": "vertical_disabled"})

    rel = REQUIRED_N7C2_READABILITY_FIGURES[8]
    trace_t = _trace_time(trace_rows)
    fig, ax = _axis(plt)
    _line_style(ax, trace_t, _values(trace_rows, "residual_norm"), label="residual_norm", color="#1f77b4", linestyle="-", marker="o", alpha=0.75)
    _line_style(ax, trace_t, _values(trace_rows, "normalized_innovation"), label="normalized_innovation", color="#d62728", linestyle="--", marker="x", alpha=0.68)
    _decorate(ax, "N7C2 Go2 horizontal update residual zoom", "residual / normalized innovation")
    _save(fig, root / rel, plt)
    generated.append({"figure_name": rel, "source_rows": len(trace_rows), "kind": "update_residual"})

    rel = REQUIRED_N7C2_READABILITY_FIGURES[9]
    status_counts = overlap_report.get("summary", {}).get("status_counts", {})
    lines = [
        "N7C2 visual overlap audit",
        f"items: {overlap_report.get('summary', {}).get('item_count', 0)}",
        f"clearly separated: {status_counts.get('clearly_separated', 0)}",
        f"mostly overlapped: {status_counts.get('mostly_overlapped', 0)}",
        f"near identical: {status_counts.get('identical_or_near_identical', 0)}",
        "Overlap is explained from source data, not image OCR.",
        "Delta/zoom figures generated for readability.",
        "Diagnostic only; no paper performance claim.",
    ]
    _text_panel(plt, root / rel, "N7C2 visual overlap summary", lines)
    generated.append({"figure_name": rel, "source_rows": int(overlap_report.get("summary", {}).get("item_count", 0) or 0), "kind": "summary"})

    required_paths = [root / rel for rel in REQUIRED_N7C2_READABILITY_FIGURES]
    manifest = {
        "stage": "N7C2_go2_horizontal_velocity_jacobian_visual_audit",
        "figure_count_total": len(REQUIRED_N7C2_READABILITY_FIGURES),
        "required_figure_count": len(REQUIRED_N7C2_READABILITY_FIGURES),
        "required_figures": list(REQUIRED_N7C2_READABILITY_FIGURES),
        "generated_figures": generated,
        "required_figures_generated": all(path.exists() for path in required_paths),
        "required_figures_nonempty": all(_nonempty(path) for path in required_paths),
        "delta_zoom_figures_generated": True,
        "figure_role_alias": "N7C2_FIGURE_OUTPUT_DIR",
        "paper_performance_claim": False,
        "go2_velocity_truth_claim": False,
        "no_outperform_final_v23_claim": True,
        "final_v23_output_solver_input": False,
        "trace_solver_input": False,
        "output_only_correction": False,
        "bad_epoch_deletion_for_metric": False,
        "fgo": False,
    }
    return manifest


def write_n7c2_figure_manifest(path: str | Path, manifest: dict[str, Any]) -> dict[str, Any]:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest
