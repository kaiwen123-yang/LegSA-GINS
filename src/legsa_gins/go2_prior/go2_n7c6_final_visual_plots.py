"""Readable N7C6A replacement figures.

中文说明：所有图都是 runtime-only final review figure；图名和坐标轴显式标注
raw series / delta / residual proxy / NIS proxy，避免把 Go2 观测误写为 truth。
"""

from __future__ import annotations

import csv
import math
from pathlib import Path
from typing import Any

from legsa_gins.go2_prior.go2_n7c6_final_visual_loader import read_json
from legsa_gins.go2_prior.go2_n7c6_plot_label_readability import shorten_variant_label


REQUIRED_N7C6A_FIGURES = [
    "joint_factor_update_timeline_readable.png",
    "joint_factor_nis_by_variant_readable.png",
    "horizontal_velocity_residual_by_joint_variant_readable.png",
    "roll_pitch_std_strength_scan_readable.png",
    "roll_pitch_residual_by_std_readable.png",
    "joint_minus_horizontal_only_delta_readable.png",
    "stress_receiver_velocity_baseline_vs_joint_readable.png",
    "stress_raw_doppler_baseline_vs_joint_readable.png",
    "clean_horizontal_series_baseline_vs_joint_readable.png",
    "clean_yaw_series_baseline_vs_joint_readable.png",
    "clean_roll_pitch_series_baseline_vs_joint_readable.png",
    "n7c6a_final_decision_panel.png",
]


def _plt():
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


def _axis(plt, figsize=(10.8, 5.6)):
    fig = plt.figure(figsize=figsize)
    ax = fig.add_axes([0.12, 0.22, 0.82, 0.68])
    return fig, ax


def _save(fig, path: Path, plt) -> dict[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return {"figure_name": path.name, "nonempty": path.exists() and path.stat().st_size > 0, "size_bytes": path.stat().st_size if path.exists() else 0}


def _read_csv(path: Path, max_rows: int = 5000) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = [dict(row) for row in csv.DictReader(handle)]
    if len(rows) <= max_rows:
        return rows
    stride = max(1, len(rows) // max_rows)
    return rows[::stride]


def _times(rows: list[dict[str, Any]]) -> list[float]:
    if not rows:
        return []
    t0 = _f(rows[0].get("time"), 0.0)
    return [_f(row.get("time"), t0) - t0 for row in rows]


def _eval_nav(n7c6_root: Path, variant: str) -> list[dict[str, Any]]:
    return _read_csv(n7c6_root / "variants" / variant / "EVAL_NAV.csv")


def _summaries_by_id(n7c6_root: Path) -> dict[str, dict[str, Any]]:
    report = read_json(n7c6_root / "N7C6_PROPRIOCEPTIVE_JOINT_FACTOR_VARIANT_SUMMARIES.json")
    rows = report.get("variants", [])
    if not isinstance(rows, list):
        return {}
    return {str(row.get("variant_id", "")): row for row in rows if isinstance(row, dict)}


def _bar(ax, names: list[str], values: list[float], *, ylabel: str, title: str) -> None:
    labels = [shorten_variant_label(name) for name in names]
    ax.bar(labels, values, color="#4c78a8")
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    ax.tick_params(axis="x", labelrotation=18, labelsize=8)
    ax.grid(True, axis="y", linewidth=0.3, alpha=0.4)


def generate_n7c6a_readable_figures(
    *,
    n7c6_root: str | Path,
    figure_output_dir: str | Path,
    decision_report: dict[str, Any],
    semantic_report: dict[str, Any],
    readability_report: dict[str, Any],
) -> dict[str, Any]:
    root = Path(n7c6_root)
    out = Path(figure_output_dir)
    plt = _plt()
    generated: list[dict[str, Any]] = []
    summaries = _summaries_by_id(root)
    comparison = read_json(root / "N7C6_PROPRIOCEPTIVE_JOINT_FACTOR_COMPARISON_REPORT.json")
    nis = read_json(root / "N7C6_PROPRIOCEPTIVE_JOINT_FACTOR_NIS_REPORT.json")
    variants = [
        "joint_rp3deg_hv1p0",
        "joint_rp1p6deg_hv1p0",
        "joint_rp1deg_hv1p0",
        "joint_rp0p75_hv1p0_diagnostic",
        "joint_rp1p6deg_hv0p75_diagnostic",
        "joint_rp1p6deg_hv1p0_sourceaware_off",
    ]

    fig, ax = _axis(plt)
    _bar(
        ax,
        variants,
        [_f(summaries.get(v, {}).get("manifest", {}).get("go2_proprioceptive_joint_factor_update_count")) for v in variants],
        ylabel="updates (count)",
        title="N7C6A raw update count by joint variant",
    )
    ax.text(0.01, 0.96, "metric namespace: raw runtime count", transform=ax.transAxes, fontsize=8, va="top")
    generated.append(_save(fig, out / REQUIRED_N7C6A_FIGURES[0], plt))

    fig, ax = _axis(plt)
    _bar(
        ax,
        variants,
        [
            _f(nis.get("variants", {}).get(v, {}).get("attitude", {}).get("nis_proxy", {}).get("p95"))
            + _f(nis.get("variants", {}).get(v, {}).get("horizontal_velocity", {}).get("nis_proxy", {}).get("p95"))
            for v in variants
        ],
        ylabel="p95 NIS proxy",
        title="N7C6A NIS proxy by joint variant",
    )
    ax.text(0.01, 0.96, "metric namespace: NIS_proxy; diagnostic only", transform=ax.transAxes, fontsize=8, va="top")
    generated.append(_save(fig, out / REQUIRED_N7C6A_FIGURES[1], plt))

    fig, ax = _axis(plt)
    _bar(
        ax,
        variants,
        [_f(nis.get("variants", {}).get(v, {}).get("horizontal_velocity", {}).get("residual_norm", {}).get("p95")) for v in variants],
        ylabel="p95 residual norm (m/s proxy)",
        title="N7C6A horizontal velocity residual proxy by variant",
    )
    ax.text(0.01, 0.96, "metric namespace: residual_proxy; not truth error", transform=ax.transAxes, fontsize=8, va="top")
    generated.append(_save(fig, out / REQUIRED_N7C6A_FIGURES[2], plt))

    rp_variants = ["rollpitch_only_5deg", "rollpitch_only_3deg", "rollpitch_only_1p6deg", "rollpitch_only_1deg"]
    fig, ax = _axis(plt)
    _bar(
        ax,
        rp_variants,
        [
            _f(summaries.get(v, {}).get("summary", {}).get("roll_rmse_deg"))
            + _f(summaries.get(v, {}).get("summary", {}).get("pitch_rmse_deg"))
            for v in rp_variants
        ],
        ylabel="roll+pitch evaluation RMSE (deg)",
        title="N7C6A roll/pitch std strength scan",
    )
    ax.text(0.01, 0.96, "metric namespace: evaluation summary; no paper claim", transform=ax.transAxes, fontsize=8, va="top")
    generated.append(_save(fig, out / REQUIRED_N7C6A_FIGURES[3], plt))

    fig, ax = _axis(plt)
    _bar(
        ax,
        rp_variants,
        [_f(nis.get("variants", {}).get(v, {}).get("attitude", {}).get("residual_norm", {}).get("p95")) for v in rp_variants],
        ylabel="p95 residual norm (rad proxy)",
        title="N7C6A roll/pitch residual proxy by std",
    )
    ax.text(0.01, 0.96, "metric namespace: residual_proxy; Go2 not truth", transform=ax.transAxes, fontsize=8, va="top")
    generated.append(_save(fig, out / REQUIRED_N7C6A_FIGURES[4], plt))

    for rel, comp_key, title in [
        (REQUIRED_N7C6A_FIGURES[5], "joint_rp1deg_minus_horizontal_only", "N7C6A joint minus horizontal-only delta"),
        (REQUIRED_N7C6A_FIGURES[6], "receiver_velocity_stress_joint_minus_baseline", "N7C6A receiver velocity stress delta"),
        (REQUIRED_N7C6A_FIGURES[7], "raw_doppler_stress_joint_minus_baseline", "N7C6A raw Doppler stress delta"),
    ]:
        delta = comparison.get("comparisons", {}).get(comp_key, {}).get("delta", {})
        fig, ax = _axis(plt)
        keys = ["horizontal_rmse_m", "yaw_rmse_deg", "roll_rmse_deg", "pitch_rmse_deg"]
        ax.bar(["horiz m", "yaw deg", "roll deg", "pitch deg"], [_f(delta.get(key)) for key in keys], color="#f58518")
        ax.set_title(title)
        ax.set_ylabel("delta vs comparator")
        ax.grid(True, axis="y", linewidth=0.3, alpha=0.4)
        ax.text(0.01, 0.96, "metric namespace: variant_delta; diagnostic engineering evidence", transform=ax.transAxes, fontsize=8, va="top")
        generated.append(_save(fig, out / rel, plt))

    baseline = _eval_nav(root, "baseline_no_go2_proprioceptive")
    selected = _eval_nav(root, "joint_rp1deg_hv1p0")
    for rel, key, title, ylabel in [
        (REQUIRED_N7C6A_FIGURES[8], "vn", "N7C6A clean horizontal raw series: baseline vs selected joint", "vN (m/s)"),
        (REQUIRED_N7C6A_FIGURES[9], "yaw_deg", "N7C6A clean yaw raw series: baseline vs selected joint", "yaw (deg)"),
    ]:
        fig, ax = _axis(plt, figsize=(11.0, 5.2))
        ax.plot(_times(baseline), [_f(row.get(key)) for row in baseline], label="baseline", linewidth=0.8, alpha=0.75)
        ax.plot(_times(selected), [_f(row.get(key)) for row in selected], label="joint rp1.0/hv1.0", linewidth=0.8, linestyle="--", alpha=0.8)
        ax.set_title(title)
        ax.set_xlabel("time since first epoch (s)")
        ax.set_ylabel(ylabel)
        ax.grid(True, linewidth=0.3, alpha=0.4)
        ax.legend(fontsize=8, loc="best")
        ax.text(0.01, 0.96, "metric namespace: raw_series; not truth error", transform=ax.transAxes, fontsize=8, va="top")
        generated.append(_save(fig, out / rel, plt))

    fig, ax = _axis(plt, figsize=(11.0, 5.2))
    ax.plot(_times(baseline), [_f(row.get("roll_deg")) for row in baseline], label="baseline roll", linewidth=0.75, alpha=0.65)
    ax.plot(_times(selected), [_f(row.get("roll_deg")) for row in selected], label="joint roll", linewidth=0.75, linestyle="--")
    ax.plot(_times(baseline), [_f(row.get("pitch_deg")) for row in baseline], label="baseline pitch", linewidth=0.75, alpha=0.65)
    ax.plot(_times(selected), [_f(row.get("pitch_deg")) for row in selected], label="joint pitch", linewidth=0.75, linestyle="--")
    ax.set_title("N7C6A clean roll/pitch raw series: baseline vs selected joint")
    ax.set_xlabel("time since first epoch (s)")
    ax.set_ylabel("attitude (deg)")
    ax.grid(True, linewidth=0.3, alpha=0.4)
    ax.legend(fontsize=8, ncol=2, loc="best")
    ax.text(0.01, 0.96, "metric namespace: raw_series; attitude_series not error", transform=ax.transAxes, fontsize=8, va="top")
    generated.append(_save(fig, out / REQUIRED_N7C6A_FIGURES[10], plt))

    fig, ax = _axis(plt)
    ax.axis("off")
    lines = [
        "N7C6A final visual/metric sanity review",
        f"N7C6 decision: {decision_report.get('status')}",
        f"metric semantics: {semantic_report.get('metric_semantic_status')}",
        f"plot readability: {readability_report.get('plot_label_readability_status')}",
        "replacement figures: readable labels + explicit namespaces",
        "Go2 proprioceptive observation, not truth",
        "No solver math change, no tuning, no FGO, no paper claim",
    ]
    ax.text(0.02, 0.95, "\n".join(lines), va="top", family="monospace", fontsize=9)
    ax.set_title("N7C6A final decision panel")
    generated.append(_save(fig, out / REQUIRED_N7C6A_FIGURES[11], plt))

    paths = [out / name for name in REQUIRED_N7C6A_FIGURES]
    return {
        "stage": "N7C6A_go2_proprioceptive_joint_final_review",
        "required_figures": REQUIRED_N7C6A_FIGURES,
        "figure_count_total": len(REQUIRED_N7C6A_FIGURES),
        "generated_figures": generated,
        "required_figures_generated": all(path.exists() for path in paths),
        "required_figures_nonempty": all(path.exists() and path.stat().st_size > 0 for path in paths),
        "figure_role_alias": "N7C6A_FIGURE_OUTPUT_DIR",
        "metric_namespace_annotated": True,
        "short_variant_labels": True,
        "paper_performance_claim": False,
        "go2_not_truth": True,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "fgo": False,
    }
