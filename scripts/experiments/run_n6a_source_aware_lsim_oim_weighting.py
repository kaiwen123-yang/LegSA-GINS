#!/usr/bin/env python3
"""Run N6A source-aware LSIM/OIM weighting diagnostics.

中文说明：真实路径只来自命令行参数；本 runner 只写 runtime-only reports/figures，
不提交 raw data、NAV/STD、SOURCE_AWARE_WEIGHT_TRACE 或生成图像。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from legsa_gins.raw_gnss.raw_doppler_ablation_evaluator import load_clean_time_window
from legsa_gins.raw_gnss.raw_doppler_visual_loader import find_factor_csv
from legsa_gins.source_aware.source_aware_ablation_matrix import (
    build_n6a_source_aware_ablation_matrix,
    write_matrix,
)
from legsa_gins.source_aware.source_aware_decision import make_source_aware_decision, write_decision
from legsa_gins.source_aware.source_aware_definition_probe import probe_source_aware_definitions, write_probe_report
from legsa_gins.source_aware.source_aware_evaluator import (
    run_source_aware_matrix,
    write_reports,
)
from legsa_gins.source_aware.source_aware_spike_response import (
    evaluate_spike_response,
    find_n5d1_spike_report,
    write_spike_response_report,
)


REQUIRED_FIGURES = [
    "01_clean_source_aware/clean_horizontal_error_no_sourceaware_vs_lsim_oim.png",
    "01_clean_source_aware/clean_yaw_error_no_sourceaware_vs_lsim_oim.png",
    "02_weight_traces/source_aware_R_scale_by_source_time.png",
    "02_weight_traces/source_aware_R_scale_hist_by_source.png",
    "02_weight_traces/oim_normalized_innovation_by_source.png",
    "02_weight_traces/lsim_score_by_source_time.png",
    "05_raw_doppler_source/raw_doppler_R_scale_and_residual_time.png",
    "03_spike_response/raw_doppler_spike_response_zoom.png",
    "03_spike_response/raw_doppler_spike_response_table.png",
    "04_stress_source_aware/receiver_velocity_stress_no_sourceaware_vs_sourceaware.png",
    "04_stress_source_aware/yaw_stress_no_sourceaware_vs_sourceaware.png",
    "06_summary/source_aware_summary_delta_panel.png",
]


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--clean-root", required=True)
    parser.add_argument("--n5b-root", required=True)
    parser.add_argument("--n5c-root", required=True)
    parser.add_argument("--n5d-root", required=True)
    parser.add_argument("--n5d1-root", required=True)
    parser.add_argument("--dual-root", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--figure-output-dir", required=True)
    parser.add_argument("--build-dir", required=True)
    parser.add_argument("--exe", required=True)
    parser.add_argument("--allow-run", action="store_true")
    parser.add_argument("--run-stress", default="true")
    parser.add_argument("--evaluate-spike-response", default="true")
    return parser.parse_args(argv)


def _write_json(path: str | Path, data: dict[str, Any]) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _read_csv(path: str | Path) -> list[dict[str, Any]]:
    import csv

    source = Path(path)
    if not source.exists():
        return []
    with source.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _metric(variant: dict[str, Any], key: str) -> float | None:
    value = variant.get("summary", {}).get(key)
    return float(value) if isinstance(value, (int, float)) else None


def _load_matplotlib():
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    return plt


def _simple_line_plot(path: Path, title: str, xlabel: str, ylabel: str, series: list[tuple[str, list[float], list[float]]]) -> dict[str, Any]:
    plt = _load_matplotlib()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig = plt.figure(figsize=(8.8, 4.8))
    ax = fig.add_axes([0.12, 0.16, 0.82, 0.74])
    for label, xs, ys in series:
        ax.plot(xs, ys, linewidth=0.9, label=label)
    ax.set_title(title)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.grid(True, linewidth=0.3, alpha=0.45)
    if series:
        ax.legend(loc="best", fontsize=8)
    fig.savefig(path, dpi=140)
    plt.close(fig)
    return {"path": str(path), "nonempty": path.exists() and path.stat().st_size > 0}


def _simple_bar(path: Path, title: str, labels: list[str], values: list[float]) -> dict[str, Any]:
    plt = _load_matplotlib()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig = plt.figure(figsize=(8.8, 4.8))
    ax = fig.add_axes([0.16, 0.28, 0.78, 0.62])
    ax.bar(range(len(labels)), values, color="#4c78a8")
    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels, rotation=25, ha="right", fontsize=8)
    ax.set_title(title)
    ax.grid(True, axis="y", linewidth=0.3, alpha=0.45)
    fig.savefig(path, dpi=140)
    plt.close(fig)
    return {"path": str(path), "nonempty": path.exists() and path.stat().st_size > 0}


def generate_figures(
    *,
    figure_output_dir: str | Path,
    output_dir: str | Path,
    variant_summaries: list[dict[str, Any]],
    spike_response: dict[str, Any],
    comparison: dict[str, Any],
) -> dict[str, Any]:
    figs = Path(figure_output_dir)
    out = Path(output_dir)
    by_id = {row["variant_id"]: row for row in variant_summaries}
    generated: list[dict[str, Any]] = []
    no_src = by_id.get("baseline_plus_raw_no_sourceaware", {})
    lsim_oim = by_id.get("baseline_plus_raw_lsim_oim", {})
    generated.append(
        _simple_bar(
            figs / REQUIRED_FIGURES[0],
            "Clean horizontal RMSE (diagnostic only)",
            ["no_sourceaware", "lsim_oim"],
            [(_metric(no_src, "horizontal_rmse_m") or 0.0), (_metric(lsim_oim, "horizontal_rmse_m") or 0.0)],
        )
    )
    generated.append(
        _simple_bar(
            figs / REQUIRED_FIGURES[1],
            "Clean yaw RMSE (diagnostic only)",
            ["no_sourceaware", "lsim_oim"],
            [(_metric(no_src, "yaw_rmse_deg") or 0.0), (_metric(lsim_oim, "yaw_rmse_deg") or 0.0)],
        )
    )
    trace_rows = _read_csv(out / "variants" / "baseline_plus_raw_lsim_oim" / "SOURCE_AWARE_WEIGHT_TRACE.csv")
    sources = sorted({row.get("source_id", "") for row in trace_rows if row.get("source_id")})
    for rel, key, title, ylabel in [
        (REQUIRED_FIGURES[2], "combined_R_scale", "R scale by source", "R scale"),
        (REQUIRED_FIGURES[4], "normalized_innovation", "OIM normalized innovation", "normalized innovation"),
        (REQUIRED_FIGURES[5], "lsim_score", "LSIM score by source", "LSIM score"),
    ]:
        series = []
        for source in sources:
            rows = [row for row in trace_rows if row.get("source_id") == source]
            xs = [float(row.get("time", 0.0)) for row in rows]
            ys = [float(row.get(key, 0.0)) for row in rows]
            series.append((source, xs, ys))
        generated.append(_simple_line_plot(figs / rel, title, "time (s)", ylabel, series))
    scale_values = [float(row.get("combined_R_scale", 1.0)) for row in trace_rows]
    generated.append(
        _simple_bar(
            figs / REQUIRED_FIGURES[3],
            "R scale histogram proxy by source",
            sources,
            [max([float(row.get("combined_R_scale", 1.0)) for row in trace_rows if row.get("source_id") == source] or [0.0]) for source in sources],
        )
    )
    raw_rows = [row for row in trace_rows if row.get("source_id") == "raw_doppler_velocity"]
    generated.append(
        _simple_line_plot(
            figs / REQUIRED_FIGURES[6],
            "Raw Doppler R scale and residual",
            "time (s)",
            "value",
            [
                ("combined_R_scale", [float(row.get("time", 0.0)) for row in raw_rows], [float(row.get("combined_R_scale", 1.0)) for row in raw_rows]),
                ("residual_norm", [float(row.get("time", 0.0)) for row in raw_rows], [float(row.get("residual_norm", 0.0)) for row in raw_rows]),
            ],
        )
    )
    spike_times = [float(row["spike_time"]) for row in spike_response.get("responses", []) if row.get("spike_time") is not None]
    generated.append(
        _simple_line_plot(
            figs / REQUIRED_FIGURES[7],
            "Raw Doppler spike response zoom",
            "time (s)",
            "R scale",
            [
                (
                    "raw_doppler_combined_R_scale",
                    [float(row.get("time", 0.0)) for row in raw_rows if not spike_times or min(abs(float(row.get("time", 0.0)) - t) for t in spike_times) < 2.0],
                    [float(row.get("combined_R_scale", 1.0)) for row in raw_rows if not spike_times or min(abs(float(row.get("time", 0.0)) - t) for t in spike_times) < 2.0],
                )
            ],
        )
    )
    generated.append(
        _simple_bar(
            figs / REQUIRED_FIGURES[8],
            "Spike response R scale table proxy",
            [f"{row.get('spike_time', 0.0):.3f}" for row in spike_response.get("responses", [])],
            [float(row.get("raw_doppler_combined_R_scale") or 0.0) for row in spike_response.get("responses", [])],
        )
    )
    comp = comparison.get("comparisons", {})
    labels = [key.replace("_sourceaware_minus_no_sourceaware", "") for key in comp if key.startswith("receiver_velocity")]
    values_h = [(comp[key].get("delta", {}).get("horizontal_rmse_m") or 0.0) for key in comp if key.startswith("receiver_velocity")]
    values_y = [(comp[key].get("delta", {}).get("yaw_rmse_deg") or 0.0) for key in comp if key.startswith("receiver_velocity")]
    generated.append(_simple_bar(figs / REQUIRED_FIGURES[9], "Receiver velocity stress horizontal delta", labels, values_h))
    generated.append(_simple_bar(figs / REQUIRED_FIGURES[10], "Receiver velocity stress yaw delta", labels, values_y))
    generated.append(
        _simple_bar(
            figs / REQUIRED_FIGURES[11],
            "Source-aware summary delta panel",
            ["trace_rows", "max_scale", "spike_hits"],
            [float(len(trace_rows)), max(scale_values or [0.0]), float(spike_response.get("nearest_source_aware_trace_rows_found", 0))],
        )
    )
    manifest = {
        "stage": "N6A_source_aware_LSIM_OIM_weighting",
        "required_figures": REQUIRED_FIGURES,
        "figure_count_total": len(generated),
        "required_figures_generated": len(generated) == len(REQUIRED_FIGURES),
        "required_figures_nonempty": all(row["nonempty"] for row in generated),
        "figures": generated,
        "paper_performance_claim": False,
    }
    _write_json(out / "N6A_FIGURE_MANIFEST.json", manifest)
    return manifest


def write_case_review(path: str | Path, decision: dict[str, Any], spike: dict[str, Any], weight_stats: dict[str, Any]) -> None:
    lines = [
        "# N6A source-aware LSIM/OIM weighting",
        "",
        "This report is diagnostic engineering evidence only.",
        "",
        f"- status: {decision.get('status')}",
        f"- recommended_next_stage: {decision.get('recommended_next_stage')}",
        f"- spike_response_status: {spike.get('oim_response_status')}",
        f"- main_variant_trace_rows: {weight_stats.get('main_variant_stats', {}).get('trace_row_count')}",
        "- source-aware weighting changes R inside EKF update path, not output.",
        "- N5D1 spike epochs are evaluation sentinels only.",
        "- paper_performance_claim: false",
        "- no_outperform_final_v23_claim: true",
        "- final_v23_output_solver_input: false",
        "- trace_solver_input: false",
        "- go2_prior: false",
        "- fgo: false",
    ]
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    if not args.allow_run:
        raise SystemExit("--allow-run is required for N6A runtime execution")
    out = Path(args.output_dir)
    figs = Path(args.figure_output_dir)
    out.mkdir(parents=True, exist_ok=True)
    figs.mkdir(parents=True, exist_ok=True)

    definition_probe = probe_source_aware_definitions(ROOT)
    write_probe_report(definition_probe, out / "SOURCE_AWARE_DEFINITION_PROBE_REPORT.json")

    factor_csv = find_factor_csv(args.n5b_root)
    clean_start, _ = load_clean_time_window(args.clean_root)
    matrix = build_n6a_source_aware_ablation_matrix(factor_csv, out, outage_start_sec=float(clean_start or 0.0))
    write_matrix(matrix, out / "N6A_SOURCE_AWARE_ABLATION_MATRIX.json")
    _, variant_summaries = run_source_aware_matrix(
        matrix,
        clean_root=args.clean_root,
        exe=args.exe,
        output_dir=out,
        dual_reference=args.dual_root,
    )
    weight_stats, comparison = write_reports(out, variant_summaries)
    spike_report_path = find_n5d1_spike_report(args.n5d1_root)
    spike_trace = out / "variants" / "baseline_plus_raw_lsim_oim_spike_response_audit" / "SOURCE_AWARE_WEIGHT_TRACE.csv"
    spike_response = evaluate_spike_response(
        spike_report_path=spike_report_path,
        source_aware_trace_path=spike_trace,
    )
    write_spike_response_report(spike_response, out / "N6A_SPIKE_RESPONSE_REPORT.json")
    decision = make_source_aware_decision(weight_stats, comparison, spike_response)
    write_decision(decision, out / "N6A_SOURCE_AWARE_DECISION_REPORT.json")
    figure_manifest = generate_figures(
        figure_output_dir=figs,
        output_dir=out,
        variant_summaries=variant_summaries,
        spike_response=spike_response,
        comparison=comparison,
    )
    write_case_review(out / "n6a_source_aware_case_review.md", decision, spike_response, weight_stats)
    write_case_review(figs / "07_case_review" / "n6a_source_aware_case_review.md", decision, spike_response, weight_stats)
    report = {
        "stage": "N6A_source_aware_LSIM_OIM_weighting",
        "definition_probe": definition_probe,
        "matrix": matrix,
        "weight_stats": weight_stats,
        "comparison": comparison,
        "spike_response": spike_response,
        "decision": decision,
        "figure_manifest": figure_manifest,
        "paper_performance_claim": False,
        "proposed_factor_claim": False,
        "no_outperform_final_v23_claim": True,
        "final_v23_output_solver_input": False,
        "trace_solver_input": False,
        "output_only_correction": False,
        "bad_epoch_deletion_for_metric": False,
        "go2_prior": False,
        "fgo": False,
    }
    _write_json(out / "N6A_SOURCE_AWARE_RUN_REPORT.json", report)
    print(json.dumps(decision, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
