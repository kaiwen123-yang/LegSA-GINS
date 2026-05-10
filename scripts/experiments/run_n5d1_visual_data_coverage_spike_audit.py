#!/usr/bin/env python3
"""Run N5D1 visual data coverage repair and raw Doppler spike audit.

中文说明：真实路径只来自命令行参数；本 runner 只写 runtime-only 报告和图，不提交
raw data、runtime artifacts 或 figures，不修改滤波器数学。
"""

from __future__ import annotations

import argparse
from dataclasses import asdict
import json
import math
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from legsa_gins.raw_gnss.raw_doppler_clean_ablation_plot_fix import (
    generate_repaired_clean_ablation_figures,
    load_clean_ablation_error_rows,
    write_clean_fix_report,
)
from legsa_gins.raw_gnss.raw_doppler_n5d1_decision import make_n5d1_decision, write_n5d1_decision
from legsa_gins.raw_gnss.raw_doppler_plot_data_coverage import (
    FigureCoverage,
    inspect_plot_source_data,
    write_coverage_report,
)
from legsa_gins.raw_gnss.raw_doppler_plot_semantics_audit import (
    generate_semantics_fixed_figures,
    write_semantics_fix_report,
)
from legsa_gins.raw_gnss.raw_doppler_spike_audit import (
    audit_raw_doppler_spikes,
    write_spike_audit_report,
)
from legsa_gins.raw_gnss.raw_doppler_stress_evaluator import evaluate_n5d_stress_pairs
from legsa_gins.raw_gnss.raw_doppler_visual_loader import (
    find_clean_gnss,
    find_factor_csv,
    load_raw_doppler_factor_rows,
    load_receiver_velocity_rows,
    read_json,
    write_json,
)


REQUIRED_N5D1_FIGURES = [
    "01_clean_ablation_repaired/clean_horizontal_error_baseline_vs_raw_repaired.png",
    "01_clean_ablation_repaired/clean_up_error_baseline_vs_raw_repaired.png",
    "01_clean_ablation_repaired/clean_yaw_error_baseline_vs_raw_repaired.png",
    "01_clean_ablation_repaired/clean_roll_pitch_error_baseline_vs_raw_repaired.png",
    "01_clean_ablation_repaired/baseline_minus_raw_horizontal_diff_repaired.png",
    "01_clean_ablation_repaired/baseline_minus_raw_yaw_diff_repaired.png",
    "02_raw_doppler_spike_audit/raw_doppler_velocity_with_spike_markers.png",
    "02_raw_doppler_spike_audit/raw_minus_receiver_velocity_norm_with_spike_markers.png",
    "02_raw_doppler_spike_audit/raw_doppler_residual_with_spike_markers.png",
    "02_raw_doppler_spike_audit/spike_epoch_detail_panel.png",
    "03_semantics_fixed/raw_minus_receiver_velocity_consistency_vs_raw_doppler_3sigma.png",
    "03_semantics_fixed/stress_delta_unique_pairs_bar.png",
    "03_semantics_fixed/stress_pair_label_mapping.png",
    "04_summary/plot_data_coverage_summary.png",
    "04_summary/n5d1_decision_panel.png",
]


def _str_bool(value: str) -> bool:
    return value.lower() in {"1", "true", "yes", "on"}


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--n5b-root", required=True)
    parser.add_argument("--n5c-root", required=True)
    parser.add_argument("--n5d-root", required=True)
    parser.add_argument("--clean-root", required=True)
    parser.add_argument("--dual-root", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--figure-output-dir", required=True)
    parser.add_argument("--build-dir", required=True)
    parser.add_argument("--exe", required=True)
    parser.add_argument("--allow-run", action="store_true")
    parser.add_argument("--rerun-clean-variants-if-needed", default="true")
    return parser.parse_args(argv)


def _load_matplotlib():
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    return plt


def _axis(plt, figsize: tuple[float, float] = (8.8, 4.9)):
    fig = plt.figure(figsize=figsize)
    ax = fig.add_axes([0.12, 0.16, 0.82, 0.74])
    return fig, ax


def _rel_times(rows: list[dict[str, Any]]) -> list[float]:
    if not rows:
        return []
    first = float(rows[0].get("time", rows[0].get("timestamp", 0.0)) or 0.0)
    return [float(row.get("time", row.get("timestamp", first)) or first) - first for row in rows]


def _series(rows: list[dict[str, Any]], key: str) -> list[float]:
    out: list[float] = []
    for row in rows:
        try:
            value = float(row.get(key))
        except (TypeError, ValueError):
            continue
        if math.isfinite(value):
            out.append(value)
    return out


def _receiver_pairs(raw_rows: list[dict[str, Any]], receiver_rows: list[dict[str, float]]) -> list[dict[str, float]]:
    pairs: list[dict[str, float]] = []
    if not raw_rows or not receiver_rows:
        return pairs
    index = 0
    for raw in raw_rows:
        raw_time = float(raw["time"])
        while index + 1 < len(receiver_rows) and abs(receiver_rows[index + 1]["time"] - raw_time) <= abs(receiver_rows[index]["time"] - raw_time):
            index += 1
        receiver = receiver_rows[index]
        dt = raw_time - receiver["time"]
        dn = float(raw["vn"]) - receiver["vn"]
        de = float(raw["ve"]) - receiver["ve"]
        dd = float(raw["vd"]) - receiver["vd"]
        sigma = math.sqrt(float(raw["std_vn"]) ** 2 + float(raw["std_ve"]) ** 2 + float(raw["std_vd"]) ** 2)
        pairs.append(
            {
                "time": raw_time,
                "dt": dt,
                "diff_norm": math.sqrt(dn * dn + de * de + dd * dd),
                "raw_3sigma_norm": 3.0 * sigma,
            }
        )
    return pairs


def _load_variant_reports(n5d_root: str | Path, n5c_root: str | Path) -> list[dict[str, Any]]:
    for path in [
        Path(n5d_root) / "N5D_STRESS_VARIANT_SUMMARIES.json",
        Path(n5c_root) / "N5C_ABLATION_VARIANT_EVALUATIONS.json",
    ]:
        data = read_json(path)
        variants = data.get("variants")
        if isinstance(variants, list):
            return [row for row in variants if isinstance(row, dict)]
    return []


def _variant_manifest(n5d_root: str | Path, n5c_root: str | Path, variant_id: str) -> dict[str, Any]:
    for root in [Path(n5d_root), Path(n5c_root)]:
        manifest = read_json(root / "variants" / variant_id / "RUN_MANIFEST.json")
        if manifest:
            return manifest
    return {}


def _plot_spike_figures(
    *,
    raw_rows: list[dict[str, Any]],
    raw_receiver_pairs: list[dict[str, Any]],
    spike_report: dict[str, Any],
    figure_output_dir: str | Path,
) -> tuple[list[str], list[FigureCoverage]]:
    plt = _load_matplotlib()
    fig_root = Path(figure_output_dir)
    spike_times = {round(float(row["time"]), 6) for row in spike_report.get("spike_epochs", [])}
    generated: list[str] = []
    coverage: list[FigureCoverage] = []

    raw_t = _rel_times(raw_rows)
    raw_start = float(raw_rows[0]["time"]) if raw_rows else 0.0
    marker_x = [float(row["time"]) - raw_start for row in spike_report.get("spike_epochs", [])]

    rel = "02_raw_doppler_spike_audit/raw_doppler_velocity_with_spike_markers.png"
    path = fig_root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = _axis(plt)
    for key in ["vn", "ve", "vd"]:
        ax.plot(raw_t, _series(raw_rows, key), linewidth=0.85, label=key)
    for x in marker_x:
        ax.axvline(x, color="red", linewidth=0.8, alpha=0.60)
    ax.set_title("N5D1 raw Doppler velocity spikes (diagnostic only)")
    ax.set_xlabel("time since start (s)")
    ax.set_ylabel("m/s")
    ax.grid(True, linewidth=0.3, alpha=0.45)
    ax.legend(loc="best", fontsize=8)
    fig.savefig(path, dpi=140)
    plt.close(fig)
    source = {
        "figure_path": str(path),
        "mandatory": True,
        "source_data_roles": ["RAW_DOPPLER_VELOCITY_FACTORS.csv"],
        "min_rows": 1000,
        "min_series": 3,
        "min_x_range": 200.0,
        "series": [{"label": key, "x": raw_t, "y": _series(raw_rows, key)} for key in ["vn", "ve", "vd"]],
    }
    coverage.append(inspect_plot_source_data(rel, source))
    generated.append(rel)

    pair_t = _rel_times(raw_receiver_pairs)
    rel = "02_raw_doppler_spike_audit/raw_minus_receiver_velocity_norm_with_spike_markers.png"
    path = fig_root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = _axis(plt)
    ax.plot(pair_t, _series(raw_receiver_pairs, "diff_norm"), linewidth=0.85, label="raw minus receiver norm")
    for x in marker_x:
        ax.axvline(x, color="red", linewidth=0.8, alpha=0.60)
    ax.set_title("N5D1 raw-vs-receiver velocity consistency spikes")
    ax.set_xlabel("time since start (s)")
    ax.set_ylabel("m/s")
    ax.grid(True, linewidth=0.3, alpha=0.45)
    ax.legend(loc="best", fontsize=8)
    fig.savefig(path, dpi=140)
    plt.close(fig)
    coverage.append(
        inspect_plot_source_data(
            rel,
            {
                "figure_path": str(path),
                "mandatory": True,
                "source_data_roles": ["raw_doppler_velocity", "receiver_native_velocity"],
                "min_rows": 1000,
                "min_series": 1,
                "min_x_range": 200.0,
                "series": [{"label": "diff_norm", "x": pair_t, "y": _series(raw_receiver_pairs, "diff_norm")}],
            },
        )
    )
    generated.append(rel)

    rel = "02_raw_doppler_spike_audit/raw_doppler_residual_with_spike_markers.png"
    path = fig_root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = _axis(plt)
    ax.plot(pair_t, _series(raw_receiver_pairs, "diff_norm"), linewidth=0.85, label="residual proxy: raw minus receiver norm")
    for x in marker_x:
        ax.axvline(x, color="red", linewidth=0.8, alpha=0.60)
    ax.set_title("N5D1 raw Doppler residual proxy with spike markers")
    ax.set_xlabel("time since start (s)")
    ax.set_ylabel("m/s")
    ax.grid(True, linewidth=0.3, alpha=0.45)
    ax.legend(loc="best", fontsize=8)
    fig.savefig(path, dpi=140)
    plt.close(fig)
    coverage.append(
        inspect_plot_source_data(
            rel,
            {
                "figure_path": str(path),
                "mandatory": True,
                "source_data_roles": ["raw_doppler_residual_proxy"],
                "min_rows": 1000,
                "min_series": 1,
                "min_x_range": 200.0,
                "series": [{"label": "residual_proxy", "x": pair_t, "y": _series(raw_receiver_pairs, "diff_norm")}],
            },
        )
    )
    generated.append(rel)

    rel = "02_raw_doppler_spike_audit/spike_epoch_detail_panel.png"
    path = fig_root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = _axis(plt, figsize=(9.2, 4.9))
    ax.axis("off")
    lines = [
        f"spike_count: {spike_report.get('spike_count')}",
        f"max_velocity_jump: {spike_report.get('max_velocity_jump')}",
        f"max_diff_norm: {spike_report.get('max_diff_norm')}",
        f"impact: {spike_report.get('spike_impact_on_EKF')}",
        f"action: {spike_report.get('recommended_action')}",
        "spike epochs:",
    ]
    for spike in spike_report.get("spike_epochs", [])[:6]:
        lines.append(
            f"t={float(spike['time']):.3f}, jump={float(spike['component_jumps']['norm']):.3f}, "
            f"sat={spike.get('sat_count')}, std=({spike.get('std_vn')},{spike.get('std_ve')},{spike.get('std_vd')})"
        )
    ax.text(0.02, 0.92, "\n".join(lines), va="top", ha="left", family="monospace", fontsize=9)
    ax.set_title("N5D1 spike epoch detail")
    fig.savefig(path, dpi=140)
    plt.close(fig)
    coverage.append(
        inspect_plot_source_data(
            rel,
            {
                "figure_path": str(path),
                "mandatory": True,
                "source_data_roles": ["RAW_DOPPLER_SPIKE_AUDIT_REPORT"],
                "min_rows": 1,
                "min_series": 1,
                "series": [{"label": "spike_epoch_rows", "x": list(range(len(spike_report.get("spike_epochs", [])))), "y": [1.0] * len(spike_report.get("spike_epochs", []))}],
            },
        )
    )
    generated.append(rel)
    del spike_times
    return generated, coverage


def _plot_summary_figures(
    *,
    coverage_report: dict[str, Any],
    decision: dict[str, Any],
    figure_output_dir: str | Path,
) -> tuple[list[str], list[FigureCoverage]]:
    plt = _load_matplotlib()
    fig_root = Path(figure_output_dir)
    generated: list[str] = []
    coverage: list[FigureCoverage] = []

    rel = "04_summary/plot_data_coverage_summary.png"
    path = fig_root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    labels = ["mandatory", "empty_suspect", "passed"]
    values = [
        float(coverage_report.get("mandatory_figure_count", 0) or 0),
        float(coverage_report.get("empty_plot_suspect_count", 0) or 0),
        1.0 if coverage_report.get("mandatory_coverage_passed") else 0.0,
    ]
    fig, ax = _axis(plt)
    ax.bar(labels, values)
    ax.set_title("N5D1 plot data coverage summary")
    ax.set_ylabel("count / bool")
    ax.grid(True, axis="y", linewidth=0.3, alpha=0.45)
    fig.savefig(path, dpi=140)
    plt.close(fig)
    coverage.append(
        inspect_plot_source_data(
            rel,
            {
                "figure_path": str(path),
                "mandatory": True,
                "source_data_roles": ["N5D_PLOT_DATA_COVERAGE_REPORT"],
                "min_rows": 3,
                "min_series": 1,
                "series": [{"label": "coverage_summary", "x": list(range(len(values))), "y": values}],
            },
        )
    )
    generated.append(rel)

    rel = "04_summary/n5d1_decision_panel.png"
    path = fig_root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        f"status: {decision.get('status')}",
        f"next: {decision.get('recommended_next_stage')}",
        f"blocking: {','.join(decision.get('blocking_issues', [])) or 'none'}",
        "paper_performance_claim: false",
        "no_outperform_final_v23_claim: true",
    ]
    fig, ax = _axis(plt, figsize=(8.8, 4.2))
    ax.axis("off")
    ax.text(0.02, 0.92, "\n".join(lines), va="top", ha="left", family="monospace", fontsize=9)
    ax.set_title("N5D1 decision")
    fig.savefig(path, dpi=140)
    plt.close(fig)
    coverage.append(
        inspect_plot_source_data(
            rel,
            {
                "figure_path": str(path),
                "mandatory": True,
                "source_data_roles": ["N5D1_VISUAL_DATA_COVERAGE_DECISION_REPORT"],
                "min_rows": 5,
                "min_series": 1,
                "series": [{"label": "decision_lines", "x": list(range(len(lines))), "y": [1.0] * len(lines)}],
            },
        )
    )
    generated.append(rel)
    return generated, coverage


def _write_case_review(path: Path, decision: dict[str, Any], coverage: dict[str, Any], spike: dict[str, Any], semantics: dict[str, Any]) -> None:
    lines = [
        "# N5D1 visual data coverage and spike audit",
        "",
        "This runtime report repairs visual validation evidence only; it is not a solver-math change.",
        "",
        f"- status: {decision.get('status')}",
        f"- recommended_next_stage: {decision.get('recommended_next_stage')}",
        f"- mandatory_coverage_passed: {coverage.get('mandatory_coverage_passed')}",
        f"- empty_plot_suspect_count: {coverage.get('empty_plot_suspect_count')}",
        f"- spike_count: {spike.get('spike_count')}",
        f"- spike_recommended_action: {spike.get('recommended_action')}",
        f"- velocity_3sigma_semantics_fixed: {semantics.get('velocity_3sigma_semantics_fixed')}",
        "- raw Doppler spikes audited, not removed or tuned away.",
        "- raw-vs-receiver velocity consistency is not truth error.",
        "- paper_performance_claim: false",
        "- proposed_factor_claim: false",
        "- no_outperform_final_v23_claim: true",
        "- final_v23_output_solver_input: false",
        "- trace_solver_input: false",
        "- output_only_correction: false",
        "- bad_epoch_deletion_for_metric: false",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _coverage_dicts(coverage: list[FigureCoverage]) -> list[dict[str, Any]]:
    return [asdict(item) for item in coverage]


def run_pipeline(args: argparse.Namespace) -> dict[str, Any]:
    if not args.allow_run:
        raise RuntimeError("N5D1 protocol requires --allow-run")
    del args.build_dir, args.exe
    out = Path(args.output_dir)
    figs = Path(args.figure_output_dir)
    out.mkdir(parents=True, exist_ok=True)
    figs.mkdir(parents=True, exist_ok=True)

    factor_csv = find_factor_csv(args.n5b_root)
    clean_gnss = find_clean_gnss(args.clean_root)
    if clean_gnss is None:
        raise FileNotFoundError("clean GNSS input missing under clean root")
    variant_reports = _load_variant_reports(args.n5d_root, args.n5c_root)
    stress_eval = read_json(Path(args.n5d_root) / "N5D_STRESS_PAIR_EVALUATION_REPORT.json") or evaluate_n5d_stress_pairs(variant_reports)
    update_manifest = _variant_manifest(args.n5d_root, args.n5c_root, "baseline_plus_raw_doppler_r1")
    clean_data = load_clean_ablation_error_rows(n5c_root=args.n5c_root, n5d_root=args.n5d_root, dual_root=args.dual_root)
    if clean_data.get("clean_ablation_data_missing") and _str_bool(args.rerun_clean_variants_if_needed):
        # 中文说明：当前修复优先复用已完成的 N5C/N5D runtime 输出；若缺失则诚实报告，
        # 不伪造曲线，也不在 N5D1 中引入新调参。
        clean_data["rerun_clean_variants_if_needed_requested"] = True
        clean_data["rerun_clean_variants_performed"] = False
    clean_fix = generate_repaired_clean_ablation_figures(clean_data=clean_data, figure_output_dir=figs)
    write_clean_fix_report(out / "N5D1_CLEAN_ABLATION_PLOT_FIX_REPORT.json", {**clean_data, **clean_fix})

    raw_rows = load_raw_doppler_factor_rows(factor_csv)
    receiver_rows = load_receiver_velocity_rows(clean_gnss)
    raw_receiver_pairs = _receiver_pairs(raw_rows, receiver_rows)
    spike_report = audit_raw_doppler_spikes(
        factor_csv=factor_csv,
        receiver_velocity_path=clean_gnss,
        update_manifest=update_manifest,
    )
    write_spike_audit_report(out / "RAW_DOPPLER_SPIKE_AUDIT_REPORT.json", spike_report)
    spike_figures, spike_coverage = _plot_spike_figures(
        raw_rows=raw_rows,
        raw_receiver_pairs=raw_receiver_pairs,
        spike_report=spike_report,
        figure_output_dir=figs,
    )

    semantics_report = generate_semantics_fixed_figures(
        raw_receiver_velocity_pairs=raw_receiver_pairs,
        stress_eval=stress_eval,
        figure_output_dir=figs,
    )
    write_semantics_fix_report(out / "N5D_PLOT_SEMANTICS_FIX_REPORT.json", semantics_report)

    initial_coverage = []
    for rel in read_json(Path(args.n5d_root) / "N5D_FIGURE_MANIFEST.json").get("figure_paths", []):
        if str(rel).startswith("01_clean_ablation/"):
            # 中文说明：N5D1 记录旧 clean 图没有可信 source-row 覆盖，所以不能继续作为通过证据。
            initial_coverage.append(
                inspect_plot_source_data(
                    str(rel),
                    {
                        "figure_path": str(Path(args.figure_output_dir).parent / "N5D_raw_doppler_visual_stress_protocol" / rel),
                        "mandatory": False,
                        "source_data_roles": ["legacy_N5D_manifest_only"],
                        "series": [],
                    },
                )
            )

    all_coverage: list[FigureCoverage] = []
    all_coverage.extend(clean_fix.get("coverage", []))
    all_coverage.extend(spike_coverage)
    all_coverage.extend(semantics_report.get("coverage", []))
    partial_report = write_coverage_report(
        out / "N5D_PLOT_DATA_COVERAGE_REPORT.json",
        all_coverage,
        extra={
            "initial_n5d_clean_manifest_only_figures": _coverage_dicts(initial_coverage),
            "clean_ablation_data_missing": clean_data.get("clean_ablation_data_missing", False),
        },
    )
    decision = make_n5d1_decision(
        coverage_report=partial_report,
        spike_report=spike_report,
        semantics_report=semantics_report,
    )
    summary_figures, summary_coverage = _plot_summary_figures(
        coverage_report=partial_report,
        decision=decision,
        figure_output_dir=figs,
    )
    all_coverage.extend(summary_coverage)
    coverage_report = write_coverage_report(
        out / "N5D_PLOT_DATA_COVERAGE_REPORT.json",
        all_coverage,
        extra={
            "initial_n5d_clean_manifest_only_figures": _coverage_dicts(initial_coverage),
            "clean_ablation_data_missing": clean_data.get("clean_ablation_data_missing", False),
        },
    )
    decision = make_n5d1_decision(
        coverage_report=coverage_report,
        spike_report=spike_report,
        semantics_report=semantics_report,
    )
    write_n5d1_decision(out / "N5D1_VISUAL_DATA_COVERAGE_DECISION_REPORT.json", decision)
    # 中文说明：summary decision panel 依赖最终 coverage，因此再生成一次，保证面板内容一致。
    _, summary_coverage = _plot_summary_figures(coverage_report=coverage_report, decision=decision, figure_output_dir=figs)
    all_coverage = all_coverage[:-2] + summary_coverage
    coverage_report = write_coverage_report(
        out / "N5D_PLOT_DATA_COVERAGE_REPORT.json",
        all_coverage,
        extra={
            "initial_n5d_clean_manifest_only_figures": _coverage_dicts(initial_coverage),
            "clean_ablation_data_missing": clean_data.get("clean_ablation_data_missing", False),
        },
    )

    figure_paths = [
        *clean_fix.get("figure_paths", []),
        *spike_figures,
        *semantics_report.get("figure_paths", []),
        *summary_figures,
    ]
    manifest = {
        "stage": "N5D1_visual_data_coverage_spike_audit",
        "figure_paths": figure_paths,
        "figure_count_total": len(figure_paths),
        "required_figures": REQUIRED_N5D1_FIGURES,
        "required_figures_generated": all((figs / rel).exists() for rel in REQUIRED_N5D1_FIGURES) and coverage_report.get("required_figures_nonempty", False),
        "required_figures_nonempty": coverage_report.get("required_figures_nonempty", False),
        "coverage": _coverage_dicts(all_coverage),
        "paper_performance_claim": False,
        "proposed_factor_claim": False,
        "no_outperform_final_v23_claim": True,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "output_only_correction": False,
        "bad_epoch_deletion_for_metric": False,
    }
    write_json(out / "N5D1_FIGURE_MANIFEST.json", manifest)
    write_json(figs / "05_case_review" / "N5D1_FIGURE_MANIFEST.json", manifest)
    _write_case_review(figs / "05_case_review" / "n5d1_visual_case_review.md", decision, coverage_report, spike_report, semantics_report)
    _write_case_review(out / "n5d1_visual_case_review.md", decision, coverage_report, spike_report, semantics_report)
    report = {
        "stage": "N5D1_visual_data_coverage_spike_audit",
        "factor_csv_found": True,
        "clean_gnss_found": True,
        "n5c_reports_found": Path(args.n5c_root).exists(),
        "n5d_reports_found": Path(args.n5d_root).exists(),
        "dual_reference_found": (Path(args.dual_root) / "KF_GINS_Navresult.nav").exists(),
        "plot_data_coverage": coverage_report,
        "spike_audit": spike_report,
        "semantics_fix": {key: value for key, value in semantics_report.items() if key != "coverage"},
        "decision": decision,
        "paper_performance_claim": False,
        "proposed_factor_claim": False,
        "no_outperform_final_v23_claim": True,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "output_only_correction": False,
        "bad_epoch_deletion_for_metric": False,
    }
    write_json(out / "N5D1_VISUAL_DATA_COVERAGE_SPIKE_AUDIT_REPORT.json", report)
    print(json.dumps(decision, indent=2, sort_keys=True))
    return report


def main(argv: list[str] | None = None) -> int:
    run_pipeline(parse_args(argv or sys.argv[1:]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
