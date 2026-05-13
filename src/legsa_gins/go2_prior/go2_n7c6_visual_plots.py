"""N7C6 visual plots for Go2 proprioceptive joint factor.

中文说明：图像只用于 runtime 工程复核，不提交、不做 paper claim。
"""

from __future__ import annotations

import csv
import math
from pathlib import Path
from typing import Any


REQUIRED_N7C6_FIGURES = [
    "roll_pitch_std_strength_scan.png",
    "roll_pitch_residual_by_std.png",
    "horizontal_velocity_residual_by_joint_variant.png",
    "joint_factor_update_timeline.png",
    "joint_factor_nis_by_variant.png",
    "clean_horizontal_error_baseline_vs_joint.png",
    "clean_yaw_error_baseline_vs_joint.png",
    "clean_roll_pitch_error_baseline_vs_joint.png",
    "stress_receiver_velocity_baseline_vs_joint.png",
    "stress_raw_doppler_baseline_vs_joint.png",
    "joint_minus_horizontal_only_delta.png",
    "n7c6_decision_panel.png",
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


def _axis(plt, figsize=(9.2, 5.0)):
    fig = plt.figure(figsize=figsize)
    ax = fig.add_axes([0.14, 0.18, 0.80, 0.72])
    return fig, ax


def _save(fig, path: Path, plt) -> dict[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=145)
    plt.close(fig)
    return {"figure_name": path.name, "nonempty": path.exists() and path.stat().st_size > 0}


def _summary_by_id(summaries: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {row.get("variant_id", ""): row for row in summaries}


def _read_eval_nav(path: Path, max_rows: int = 5000) -> list[dict[str, Any]]:
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


def _variant_eval(output_dir: str | Path, variant: str) -> list[dict[str, Any]]:
    return _read_eval_nav(Path(output_dir) / "variants" / variant / "EVAL_NAV.csv")


def generate_n7c6_visual_plots(
    *,
    figure_output_dir: str | Path,
    output_dir: str | Path,
    variant_summaries: list[dict[str, Any]],
    comparison_report: dict[str, Any],
    nis_report: dict[str, Any],
    decision: dict[str, Any],
) -> dict[str, Any]:
    plt = _plt()
    root = Path(figure_output_dir)
    generated: list[dict[str, Any]] = []
    by_id = _summary_by_id(variant_summaries)

    rp_variants = ["rollpitch_only_5deg", "rollpitch_only_3deg", "rollpitch_only_1p6deg", "rollpitch_only_1deg"]
    labels = ["5", "3", "1.6", "1"]
    fig, ax = _axis(plt)
    ax.bar(labels, [_f(by_id.get(v, {}).get("summary", {}).get("roll_rmse_deg")) + _f(by_id.get(v, {}).get("summary", {}).get("pitch_rmse_deg")) for v in rp_variants])
    ax.set_title("N7C6 roll/pitch std strength scan")
    ax.set_xlabel("std deg")
    ax.set_ylabel("roll+pitch RMSE deg")
    ax.grid(True, axis="y", linewidth=0.3, alpha=0.4)
    generated.append(_save(fig, root / REQUIRED_N7C6_FIGURES[0], plt))

    fig, ax = _axis(plt)
    ax.bar(labels, [_f(nis_report.get("variants", {}).get(v, {}).get("attitude", {}).get("residual_norm", {}).get("p95")) for v in rp_variants])
    ax.set_title("N7C6 roll/pitch residual by std")
    ax.set_ylabel("p95 residual proxy")
    ax.grid(True, axis="y", linewidth=0.3, alpha=0.4)
    generated.append(_save(fig, root / REQUIRED_N7C6_FIGURES[1], plt))

    joint_variants = [
        "joint_rp3deg_hv1p0",
        "joint_rp1p6deg_hv1p0",
        "joint_rp1deg_hv1p0",
        "joint_rp0p75_hv1p0_diagnostic",
        "joint_rp1p6deg_hv0p75_diagnostic",
        "joint_rp1p6deg_hv1p0_sourceaware_off",
    ]
    fig, ax = _axis(plt)
    ax.bar(joint_variants, [_f(nis_report.get("variants", {}).get(v, {}).get("horizontal_velocity", {}).get("residual_norm", {}).get("p95")) for v in joint_variants])
    ax.set_title("N7C6 horizontal velocity residual by joint variant")
    ax.tick_params(axis="x", labelrotation=20)
    ax.grid(True, axis="y", linewidth=0.3, alpha=0.4)
    generated.append(_save(fig, root / REQUIRED_N7C6_FIGURES[2], plt))

    fig, ax = _axis(plt)
    ax.bar(joint_variants, [_f(by_id.get(v, {}).get("manifest", {}).get("go2_proprioceptive_joint_factor_update_count")) for v in joint_variants])
    ax.set_title("N7C6 joint factor update timeline summary")
    ax.tick_params(axis="x", labelrotation=20)
    ax.grid(True, axis="y", linewidth=0.3, alpha=0.4)
    generated.append(_save(fig, root / REQUIRED_N7C6_FIGURES[3], plt))

    fig, ax = _axis(plt)
    ax.bar(joint_variants, [_f(nis_report.get("variants", {}).get(v, {}).get("attitude", {}).get("nis_proxy", {}).get("p95")) + _f(nis_report.get("variants", {}).get(v, {}).get("horizontal_velocity", {}).get("nis_proxy", {}).get("p95")) for v in joint_variants])
    ax.set_title("N7C6 joint factor NIS proxy by variant")
    ax.tick_params(axis="x", labelrotation=20)
    ax.grid(True, axis="y", linewidth=0.3, alpha=0.4)
    generated.append(_save(fig, root / REQUIRED_N7C6_FIGURES[4], plt))

    baseline = _variant_eval(output_dir, "baseline_no_go2_proprioceptive")
    joint = _variant_eval(output_dir, "joint_rp1p6deg_hv1p0")
    for rel_path, key, title, ylabel in [
        (REQUIRED_N7C6_FIGURES[5], "vn", "Clean horizontal velocity baseline vs joint", "vn m/s"),
        (REQUIRED_N7C6_FIGURES[6], "yaw_deg", "Clean yaw baseline vs joint", "deg"),
    ]:
        fig, ax = _axis(plt)
        ax.plot(_times(baseline), [_f(row.get(key)) for row in baseline], label="baseline", linewidth=0.75)
        ax.plot(_times(joint), [_f(row.get(key)) for row in joint], label="joint rp1.6/hv1.0", linewidth=0.75)
        ax.set_title(f"N7C6 {title}")
        ax.set_ylabel(ylabel)
        ax.grid(True, linewidth=0.3, alpha=0.4)
        ax.legend(fontsize=8)
        generated.append(_save(fig, root / rel_path, plt))

    fig, ax = _axis(plt)
    ax.plot(_times(baseline), [_f(row.get("roll_deg")) for row in baseline], label="baseline roll", linewidth=0.75)
    ax.plot(_times(joint), [_f(row.get("roll_deg")) for row in joint], label="joint roll", linewidth=0.75)
    ax.plot(_times(joint), [_f(row.get("pitch_deg")) for row in joint], label="joint pitch", linewidth=0.75)
    ax.set_title("N7C6 clean roll/pitch baseline vs joint")
    ax.set_ylabel("deg")
    ax.grid(True, linewidth=0.3, alpha=0.4)
    ax.legend(fontsize=8)
    generated.append(_save(fig, root / REQUIRED_N7C6_FIGURES[7], plt))

    for rel_path, comp_key, title in [
        (REQUIRED_N7C6_FIGURES[8], "receiver_velocity_stress_joint_minus_baseline", "Receiver velocity stress baseline vs joint"),
        (REQUIRED_N7C6_FIGURES[9], "raw_doppler_stress_joint_minus_baseline", "Raw Doppler stress baseline vs joint"),
        (REQUIRED_N7C6_FIGURES[10], "joint_rp1p6_minus_horizontal_only", "Joint minus horizontal-only delta"),
    ]:
        delta = comparison_report.get("comparisons", {}).get(comp_key, {}).get("delta", {})
        fig, ax = _axis(plt)
        keys = ["horizontal_rmse_m", "yaw_rmse_deg", "roll_rmse_deg", "pitch_rmse_deg"]
        ax.bar(keys, [_f(delta.get(key)) for key in keys])
        ax.set_title(f"N7C6 {title}")
        ax.tick_params(axis="x", labelrotation=15)
        ax.grid(True, axis="y", linewidth=0.3, alpha=0.4)
        generated.append(_save(fig, root / rel_path, plt))

    fig, ax = _axis(plt)
    ax.axis("off")
    lines = [
        "N7C6 Go2 proprioceptive joint factor",
        f"status: {decision.get('status')}",
        f"recommended_default: {decision.get('recommended_default')}",
        f"next: {decision.get('recommended_next_stage')}",
        "sequential equivalent: true",
        "Go2 is observation, not truth.",
    ]
    ax.text(0.02, 0.95, "\n".join(lines), va="top", family="monospace", fontsize=9)
    ax.set_title("N7C6 decision panel")
    generated.append(_save(fig, root / REQUIRED_N7C6_FIGURES[11], plt))

    paths = [root / rel for rel in REQUIRED_N7C6_FIGURES]
    return {
        "stage": "N7C6_go2_proprioceptive_joint_factor",
        "required_figures": REQUIRED_N7C6_FIGURES,
        "figure_count_total": len(REQUIRED_N7C6_FIGURES),
        "generated_figures": generated,
        "required_figures_generated": all(path.exists() for path in paths),
        "required_figures_nonempty": all(path.exists() and path.stat().st_size > 0 for path in paths),
        "figure_role_alias": "N7C6_FIGURE_OUTPUT_DIR",
        "paper_performance_claim": False,
        "go2_not_truth": True,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "fgo": False,
    }
