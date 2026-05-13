"""N7C4 visual plots for Go2 horizontal velocity strength calibration.

中文说明：图像只写到 runtime figure 目录，用于 clean/stress/residual/NIS
诊断可读性验证，不进入 git。
"""

from __future__ import annotations

import csv
import math
from pathlib import Path
from typing import Any


REQUIRED_N7C4_FIGURES = [
    "strength_policy_std_timeline.png",
    "recalibrated_confidence_timeline.png",
    "variant_clean_horizontal_delta_bar.png",
    "variant_clean_yaw_delta_bar.png",
    "variant_stress_delta_bar.png",
    "variant_residual_norm_p95_bar.png",
    "variant_nis_proxy_bar.png",
    "fixed_2p0_vs_1p0_error_curves.png",
    "adaptive_vs_fixed_error_curves.png",
    "n7c4_decision_panel.png",
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
    values: list[float] = []
    for row in rows:
        north = (math.radians(_f(row.get("lat_deg"), 0.0)) - lat0) * 6378137.0
        east = (math.radians(_f(row.get("lon_deg"), 0.0)) - lon0) * 6378137.0 * cos_lat
        values.append(math.hypot(north, east))
    return values


def _axis(plt, figsize: tuple[float, float] = (9.2, 5.0)):
    fig = plt.figure(figsize=figsize)
    ax = fig.add_axes([0.12, 0.16, 0.82, 0.74])
    return fig, ax


def _decorate(ax, title: str, ylabel: str) -> None:
    ax.set_title(title)
    ax.set_xlabel("time since start (s)")
    ax.set_ylabel(ylabel)
    ax.grid(True, linewidth=0.3, alpha=0.45)
    if ax.get_legend_handles_labels()[0]:
        ax.legend(loc="best", fontsize=8)


def _save(fig, path: Path, plt) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=150)
    plt.close(fig)


def _variant_eval(output_dir: Path, variant_id: str) -> list[dict[str, Any]]:
    return _read_csv(output_dir / "variants" / variant_id / "EVAL_NAV.csv")


def _nonempty(path: Path) -> bool:
    return path.exists() and path.stat().st_size > 0


def _comparison_delta(comparison_report: dict[str, Any], name: str, metric: str) -> float:
    return _f(comparison_report.get("comparisons", {}).get(name, {}).get("delta", {}).get(metric), 0.0)


def generate_n7c4_visual_plots(
    *,
    figure_output_dir: str | Path,
    output_dir: str | Path,
    confidence_rows: list[dict[str, Any]],
    prior_rows_by_policy: dict[str, list[dict[str, Any]]],
    comparison_report: dict[str, Any],
    nis_report: dict[str, Any],
    decision: dict[str, Any],
) -> dict[str, Any]:
    plt = _load_matplotlib()
    root = Path(figure_output_dir)
    out = Path(output_dir)
    generated: list[dict[str, Any]] = []

    rel = REQUIRED_N7C4_FIGURES[0]
    fig, ax = _axis(plt)
    for policy, linestyle in [("fixed_std_2p0", "-"), ("fixed_std_1p0", "--"), ("recalibrated_adaptive", ":")]:
        rows = prior_rows_by_policy.get(policy, [])
        ax.plot(_times(rows), _values(rows, "std_vn"), label=policy, linewidth=0.9, linestyle=linestyle)
    _decorate(ax, "N7C4 strength policy std timeline", "std_vn/std_ve (m/s)")
    _save(fig, root / rel, plt)
    generated.append({"figure_name": rel, "source_rows": sum(len(rows) for rows in prior_rows_by_policy.values())})

    rel = REQUIRED_N7C4_FIGURES[1]
    fig, ax = _axis(plt)
    t = _times(confidence_rows)
    for key in ["confidence", "contact_confidence", "frame_confidence", "cross_source_consistency_confidence"]:
        ax.plot(t, _values(confidence_rows, key), label=key, linewidth=0.9, alpha=0.85)
    _decorate(ax, "N7C4 recalibrated confidence timeline", "confidence")
    _save(fig, root / rel, plt)
    generated.append({"figure_name": rel, "source_rows": len(confidence_rows)})

    clean_labels = ["1.5", "1.0", "0.75", "adapt", "adapt-aggr"]
    clean_names = [
        "fixed_1p5_minus_fixed_2p0_clean",
        "fixed_1p0_minus_fixed_2p0_clean",
        "fixed_0p75_minus_fixed_2p0_clean",
        "recalibrated_adaptive_minus_fixed_2p0_clean",
        "recalibrated_adaptive_aggressive_minus_fixed_2p0_clean",
    ]
    rel = REQUIRED_N7C4_FIGURES[2]
    fig, ax = _axis(plt)
    ax.bar(clean_labels, [_comparison_delta(comparison_report, name, "horizontal_rmse_m") for name in clean_names], color="#1f77b4")
    ax.axhline(0.0, color="#333333", linewidth=0.8)
    ax.set_title("N7C4 clean horizontal delta vs fixed 2.0")
    ax.set_ylabel("horizontal RMSE delta (m)")
    ax.grid(True, axis="y", linewidth=0.3, alpha=0.45)
    _save(fig, root / rel, plt)
    generated.append({"figure_name": rel, "source_rows": len(clean_names)})

    rel = REQUIRED_N7C4_FIGURES[3]
    fig, ax = _axis(plt)
    ax.bar(clean_labels, [_comparison_delta(comparison_report, name, "yaw_rmse_deg") for name in clean_names], color="#9467bd")
    ax.axhline(0.0, color="#333333", linewidth=0.8)
    ax.set_title("N7C4 clean yaw delta vs fixed 2.0")
    ax.set_ylabel("yaw RMSE delta (deg)")
    ax.grid(True, axis="y", linewidth=0.3, alpha=0.45)
    _save(fig, root / rel, plt)
    generated.append({"figure_name": rel, "source_rows": len(clean_names)})

    rel = REQUIRED_N7C4_FIGURES[4]
    fig, ax = _axis(plt)
    stress_labels = ["recv 1.0", "recv adapt", "raw 1.0", "raw adapt"]
    stress_names = [
        "receiver_velocity_stress_fixed_1p0_minus_fixed_2p0",
        "receiver_velocity_stress_adaptive_minus_fixed_2p0",
        "raw_doppler_stress_fixed_1p0_minus_fixed_2p0",
        "raw_doppler_stress_adaptive_minus_fixed_2p0",
    ]
    ax.bar(stress_labels, [_comparison_delta(comparison_report, name, "horizontal_rmse_m") for name in stress_names], color="#ff7f0e")
    ax.axhline(0.0, color="#333333", linewidth=0.8)
    ax.set_title("N7C4 stress diagnostic delta vs fixed 2.0")
    ax.set_ylabel("horizontal RMSE delta (m)")
    ax.grid(True, axis="y", linewidth=0.3, alpha=0.45)
    _save(fig, root / rel, plt)
    generated.append({"figure_name": rel, "source_rows": len(stress_names)})

    nis_variants = ["fixed_2p0", "fixed_1p5", "fixed_1p0", "fixed_0p75_aggressive", "recalibrated_adaptive"]
    rel = REQUIRED_N7C4_FIGURES[5]
    fig, ax = _axis(plt)
    ax.bar(nis_variants, [_f(nis_report.get("variants", {}).get(name, {}).get("residual_norm_p95"), 0.0) for name in nis_variants])
    ax.set_title("N7C4 residual norm p95 by variant")
    ax.set_ylabel("residual norm p95")
    ax.tick_params(axis="x", labelrotation=20)
    ax.grid(True, axis="y", linewidth=0.3, alpha=0.45)
    _save(fig, root / rel, plt)
    generated.append({"figure_name": rel, "source_rows": len(nis_variants)})

    rel = REQUIRED_N7C4_FIGURES[6]
    fig, ax = _axis(plt)
    ax.bar(nis_variants, [_f(nis_report.get("variants", {}).get(name, {}).get("nis_proxy_p95"), 0.0) for name in nis_variants], color="#2ca02c")
    ax.axhline(9.0, color="#d62728", linestyle=":", linewidth=0.8, label="overconfidence gate")
    ax.set_title("N7C4 NIS proxy p95 by variant")
    ax.set_ylabel("normalized innovation squared p95")
    ax.tick_params(axis="x", labelrotation=20)
    ax.grid(True, axis="y", linewidth=0.3, alpha=0.45)
    ax.legend(loc="best", fontsize=8)
    _save(fig, root / rel, plt)
    generated.append({"figure_name": rel, "source_rows": len(nis_variants)})

    fixed = _variant_eval(out, "fixed_2p0")
    one = _variant_eval(out, "fixed_1p0")
    rel = REQUIRED_N7C4_FIGURES[7]
    fig, ax = _axis(plt)
    ax.plot(_times(fixed), _local_horizontal(fixed, fixed), label="fixed_2p0", linewidth=0.9, alpha=0.8)
    ax.plot(_times(one), _local_horizontal(one, fixed), label="fixed_1p0", linewidth=0.9, alpha=0.8, linestyle="--")
    _decorate(ax, "N7C4 fixed 2.0 vs fixed 1.0 clean curves", "local horizontal proxy (m)")
    _save(fig, root / rel, plt)
    generated.append({"figure_name": rel, "source_rows": min(len(fixed), len(one))})

    adaptive = _variant_eval(out, "recalibrated_adaptive")
    rel = REQUIRED_N7C4_FIGURES[8]
    fig, ax = _axis(plt)
    ax.plot(_times(fixed), _local_horizontal(fixed, fixed), label="fixed_2p0", linewidth=0.9, alpha=0.8)
    ax.plot(_times(adaptive), _local_horizontal(adaptive, fixed), label="recalibrated_adaptive", linewidth=0.9, alpha=0.8, linestyle="--")
    _decorate(ax, "N7C4 adaptive vs fixed clean curves", "local horizontal proxy (m)")
    _save(fig, root / rel, plt)
    generated.append({"figure_name": rel, "source_rows": min(len(fixed), len(adaptive))})

    rel = REQUIRED_N7C4_FIGURES[9]
    fig, ax = _axis(plt)
    ax.axis("off")
    lines = [
        "N7C4 strength calibration decision",
        f"status: {decision.get('status')}",
        f"recommended_default_policy: {decision.get('recommended_default_policy')}",
        f"confidence_counts: {decision.get('confidence_counts')}",
        f"fixed_1p0 delta: {decision.get('clean_fixed_1p0_minus_2p0_horizontal_rmse_delta_m')}",
        f"fixed_1p0 NIS: {decision.get('fixed_1p0_nis_status')}",
        "Go2 velocity not truth; vertical/yaw/position disabled; no paper claim.",
    ]
    ax.text(0.02, 0.95, "\n".join(lines), va="top", ha="left", family="monospace", fontsize=9)
    ax.set_title("N7C4 decision panel")
    _save(fig, root / rel, plt)
    generated.append({"figure_name": rel, "source_rows": 1})

    paths = [root / name for name in REQUIRED_N7C4_FIGURES]
    return {
        "stage": "N7C4_go2_horizontal_velocity_strength_calibration",
        "figure_count_total": len(REQUIRED_N7C4_FIGURES),
        "required_figure_count": len(REQUIRED_N7C4_FIGURES),
        "required_figures": list(REQUIRED_N7C4_FIGURES),
        "generated_figures": generated,
        "required_figures_generated": all(path.exists() for path in paths),
        "required_figures_nonempty": all(_nonempty(path) for path in paths),
        "figure_role_alias": "N7C4_FIGURE_OUTPUT_DIR",
        "paper_performance_claim": False,
        "go2_velocity_truth_claim": False,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "no_outperform_final_v23_claim": True,
        "fgo": False,
    }
