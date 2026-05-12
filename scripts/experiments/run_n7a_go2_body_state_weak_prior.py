#!/usr/bin/env python3
"""Run N7A Go2 body-state weak-prior diagnostics.

中文说明：真实路径只来自命令行参数；Go2 by2.txt、prior CSV、runtime reports
和 figures 都是 runtime-only，不允许提交到 Git。
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from legsa_gins.datasets.by2.go2_body_state_parser import parse_go2_body_state_text
from legsa_gins.go2_state.go2_body_state_parser import read_standardized_csv, write_parse_outputs
from legsa_gins.go2_state.go2_frame_contract import write_frame_contract_report
from legsa_gins.go2_state.go2_quaternion_rpy_check import write_quaternion_rpy_report
from legsa_gins.go2_state.go2_time_alignment import find_clean_replay_times, write_time_alignment_report
from legsa_gins.go2_state.go2_weak_prior_builder import write_weak_prior_build_outputs
from legsa_gins.go2_state.go2_weak_prior_decision import make_go2_weak_prior_decision, write_go2_weak_prior_decision
from legsa_gins.go2_state.go2_weak_prior_evaluator import (
    build_n7a_go2_ablation_matrix,
    read_csv_rows,
    run_n7a_go2_matrix,
    write_n7a_reports,
)
from legsa_gins.raw_gnss.raw_doppler_visual_loader import find_factor_csv


REQUIRED_FIGURES = [
    "go2_roll_pitch_vs_filter_roll_pitch.png",
    "go2_roll_pitch_residual_time.png",
    "go2_attitude_prior_update_timeline.png",
    "go2_prior_sourceaware_R_scale_time.png",
    "no_go2_vs_go2_roll_error.png",
    "no_go2_vs_go2_pitch_error.png",
    "no_go2_vs_go2_yaw_error.png",
    "go2_prior_std_screen_panel.png",
    "go2_prior_decision_panel.png",
]


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--go2-body-state-path", required=True)
    parser.add_argument("--clean-root", required=True)
    parser.add_argument("--n5b-root", required=True)
    parser.add_argument("--n6b-root", required=True)
    parser.add_argument("--dual-root", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--figure-output-dir", default="")
    parser.add_argument("--build-dir", required=True)
    parser.add_argument("--exe", required=True)
    parser.add_argument("--allow-run", action="store_true")
    parser.add_argument("--run-std-screen", default="true")
    return parser.parse_args(argv)


def _truthy(value: str | bool) -> bool:
    if isinstance(value, bool):
        return value
    return value.lower() in {"true", "1", "yes", "on"}


def _write_json(path: str | Path, data: dict[str, Any]) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _first_timestamp(path: str | Path) -> float | None:
    rows = parse_go2_body_state_text(path, max_messages=1)
    if not rows:
        return None
    value = rows[0].get("timestamp")
    return float(value) if isinstance(value, (int, float)) else None


def _metric(summary: dict[str, Any], key: str) -> float:
    value = summary.get(key)
    return float(value) if isinstance(value, (int, float)) and math.isfinite(value) else 0.0


def _load_matplotlib():
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    return plt


def _line_plot(path: Path, title: str, xlabel: str, ylabel: str, series: list[tuple[str, list[float], list[float]]]) -> dict[str, Any]:
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


def _bar_plot(path: Path, title: str, labels: list[str], values: list[float]) -> dict[str, Any]:
    plt = _load_matplotlib()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig = plt.figure(figsize=(8.8, 4.8))
    ax = fig.add_axes([0.16, 0.30, 0.78, 0.60])
    ax.bar(range(len(labels)), values, color="#4c78a8")
    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels, rotation=24, ha="right", fontsize=8)
    ax.set_title(title)
    ax.grid(True, axis="y", linewidth=0.3, alpha=0.45)
    fig.savefig(path, dpi=140)
    plt.close(fig)
    return {"path": str(path), "nonempty": path.exists() and path.stat().st_size > 0}


def _eval_nav(path: Path) -> list[dict[str, Any]]:
    return read_csv_rows(path)


def generate_figures(
    *,
    figure_output_dir: str | Path,
    output_dir: str | Path,
    comparison: dict[str, Any],
    decision: dict[str, Any],
) -> dict[str, Any]:
    figs = Path(figure_output_dir)
    out = Path(output_dir)
    prior_rows = read_csv_rows(out / "GO2_ATTITUDE_WEAK_PRIORS.csv")
    go2_variant = out / "variants" / "baseline_plus_raw_sourceaware_n6b_go2_attitude_weak_prior"
    no_go2_variant = out / "variants" / "baseline_plus_raw_sourceaware_n6b_no_go2"
    eval_go2 = _eval_nav(go2_variant / "EVAL_NAV.csv")
    eval_no = _eval_nav(no_go2_variant / "EVAL_NAV.csv")
    trace_rows = read_csv_rows(go2_variant / "SOURCE_AWARE_WEIGHT_TRACE.csv")
    go2_trace = [row for row in trace_rows if row.get("source_id") == "go2_attitude_roll_pitch"]
    generated: list[dict[str, Any]] = []
    prior_times = [float(row.get("time", 0.0) or 0.0) for row in prior_rows[:5000]]
    generated.append(
        _line_plot(
            figs / REQUIRED_FIGURES[0],
            "Go2 roll/pitch weak prior vs filter attitude",
            "time (s)",
            "rad",
            [
                ("go2_roll", prior_times, [float(row.get("roll_rad", 0.0) or 0.0) for row in prior_rows[:5000]]),
                ("go2_pitch", prior_times, [float(row.get("pitch_rad", 0.0) or 0.0) for row in prior_rows[:5000]]),
                ("filter_roll", [float(row.get("time", 0.0) or 0.0) for row in eval_go2[:5000]], [math.radians(float(row.get("roll_deg", 0.0) or 0.0)) for row in eval_go2[:5000]]),
                ("filter_pitch", [float(row.get("time", 0.0) or 0.0) for row in eval_go2[:5000]], [math.radians(float(row.get("pitch_deg", 0.0) or 0.0)) for row in eval_go2[:5000]]),
            ],
        )
    )
    generated.append(
        _line_plot(
            figs / REQUIRED_FIGURES[1],
            "Go2 attitude prior residual time",
            "time (s)",
            "R scale / residual proxy",
            [("go2_R_scale", [float(row.get("time", 0.0) or 0.0) for row in go2_trace], [float(row.get("combined_R_scale", 1.0) or 1.0) for row in go2_trace])],
        )
    )
    generated.append(
        _line_plot(
            figs / REQUIRED_FIGURES[2],
            "Go2 attitude prior update timeline",
            "time (s)",
            "update index",
            [("update_index", [float(row.get("time", 0.0) or 0.0) for row in go2_trace], [float(row.get("update_index", 0.0) or 0.0) for row in go2_trace])],
        )
    )
    generated.append(
        _line_plot(
            figs / REQUIRED_FIGURES[3],
            "Go2 prior source-aware R scale",
            "time (s)",
            "R scale",
            [("combined_R_scale", [float(row.get("time", 0.0) or 0.0) for row in go2_trace], [float(row.get("combined_R_scale", 1.0) or 1.0) for row in go2_trace])],
        )
    )
    for rel, key, title in [
        (REQUIRED_FIGURES[4], "roll_deg", "No-Go2 vs Go2 roll"),
        (REQUIRED_FIGURES[5], "pitch_deg", "No-Go2 vs Go2 pitch"),
        (REQUIRED_FIGURES[6], "yaw_deg", "No-Go2 vs Go2 yaw"),
    ]:
        generated.append(
            _line_plot(
                figs / rel,
                title,
                "time (s)",
                "deg",
                [
                    ("no_go2", [float(row.get("time", 0.0) or 0.0) for row in eval_no[:5000]], [float(row.get(key, 0.0) or 0.0) for row in eval_no[:5000]]),
                    ("go2", [float(row.get("time", 0.0) or 0.0) for row in eval_go2[:5000]], [float(row.get(key, 0.0) or 0.0) for row in eval_go2[:5000]]),
                ],
            )
        )
    std_summaries = comparison.get("std_screen_summaries", [])
    generated.append(
        _bar_plot(
            figs / REQUIRED_FIGURES[7],
            "Go2 prior std screen (diagnostic)",
            [str(row.get("std_deg")) for row in std_summaries],
            [_metric(row.get("summary", {}), "roll_rmse_deg") + _metric(row.get("summary", {}), "pitch_rmse_deg") for row in std_summaries],
        )
    )
    generated.append(
        _bar_plot(
            figs / REQUIRED_FIGURES[8],
            "N7A decision panel",
            ["activated", "paper_claim", "fgo"],
            [
                1.0 if decision.get("go2_attitude_weak_prior_update_count", 0) else 0.0,
                1.0 if decision.get("paper_performance_claim") else 0.0,
                1.0 if decision.get("fgo") else 0.0,
            ],
        )
    )
    manifest = {
        "stage": "N7A_go2_body_state_weak_prior_foundation",
        "required_figures": REQUIRED_FIGURES,
        "figure_count_total": len(generated),
        "required_figures_generated": len(generated) == len(REQUIRED_FIGURES),
        "required_figures_nonempty": all(row["nonempty"] for row in generated),
        "figures": generated,
        "paper_performance_claim": False,
    }
    _write_json(out / "N7A_FIGURE_MANIFEST.json", manifest)
    return manifest


def write_case_review(path: str | Path, decision: dict[str, Any], parse: dict[str, Any], quat: dict[str, Any], frame: dict[str, Any], time: dict[str, Any]) -> None:
    lines = [
        "# N7A Go2 body-state weak prior",
        "",
        "This report is diagnostic engineering evidence only.",
        "",
        f"- row_count: {parse.get('row_count')}",
        f"- quaternion_order_selected: {quat.get('quaternion_order_selected')}",
        f"- frame_activation_allowed: {frame.get('activation_allowed')}",
        f"- overlap_duration: {time.get('overlap_duration')}",
        f"- status: {decision.get('status')}",
        f"- recommended_next_stage: {decision.get('recommended_next_stage')}",
        "- Go2 body-state is not truth.",
        "- only roll/pitch weak prior is activated by default.",
        "- Go2 position/velocity/yaw priors are disabled in N7A.",
        "- trace_solver_input: false",
        "- final_v23_output_solver_input: false",
        "- paper_performance_claim: false",
        "- no_outperform_final_v23_claim: true",
        "- fgo: false",
    ]
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    if not args.allow_run:
        raise SystemExit("--allow-run is required for N7A runtime execution")
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    clean_times = find_clean_replay_times(args.clean_root)
    clean_start = min(clean_times) if clean_times else 0.0
    first_go2 = _first_timestamp(args.go2_body_state_path)
    base_time = None if first_go2 is None else first_go2 - clean_start
    csv_path, _parse_report_path, parse_report = write_parse_outputs(
        args.go2_body_state_path,
        out,
        base_time=base_time,
    )
    rows = read_standardized_csv(csv_path)
    quat_report = write_quaternion_rpy_report(rows, out / "GO2_QUATERNION_RPY_CHECK_REPORT.json")
    frame_report = write_frame_contract_report(rows, quat_report, out / "GO2_FRAME_CONTRACT_REPORT.json")
    time_report = write_time_alignment_report(rows, clean_times, out / "GO2_TIME_ALIGNMENT_REPORT.json")
    prior_csv, _prior_report_path, build_report = write_weak_prior_build_outputs(
        rows,
        out,
        quaternion_report=quat_report,
        frame_report=frame_report,
        time_report=time_report,
    )
    factor_csv = find_factor_csv(args.n5b_root)
    matrix = build_n7a_go2_ablation_matrix(
        output_dir=out,
        raw_doppler_factor_path=factor_csv,
        go2_prior_path=prior_csv,
    )
    _write_json(out / "N7A_GO2_WEAK_PRIOR_ABLATION_MATRIX.json", matrix)
    _, variant_summaries = run_n7a_go2_matrix(
        matrix,
        clean_root=args.clean_root,
        exe=args.exe,
        output_dir=out,
        dual_reference=args.dual_root,
    )
    comparison, source_aware_stats = write_n7a_reports(out, variant_summaries)
    decision = make_go2_weak_prior_decision(
        build_report=build_report,
        frame_report=frame_report,
        comparison_report=comparison,
        source_aware_stats=source_aware_stats,
    )
    write_go2_weak_prior_decision(decision, out / "N7A_GO2_WEAK_PRIOR_DECISION_REPORT.json")
    figure_manifest: dict[str, Any] = {"required_figures_generated": False, "paper_performance_claim": False}
    if args.figure_output_dir:
        figure_manifest = generate_figures(
            figure_output_dir=args.figure_output_dir,
            output_dir=out,
            comparison=comparison,
            decision=decision,
        )
    write_case_review(out / "n7a_go2_weak_prior_case_review.md", decision, parse_report, quat_report, frame_report, time_report)
    run_report = {
        "stage": "N7A_go2_body_state_weak_prior_foundation",
        "parse_report": parse_report,
        "quaternion_rpy_report": quat_report,
        "frame_report": frame_report,
        "time_alignment_report": time_report,
        "weak_prior_build_report": build_report,
        "matrix": matrix,
        "comparison": comparison,
        "source_aware_stats": source_aware_stats,
        "decision": decision,
        "figure_manifest": figure_manifest,
        "n6b_root_role": "source_aware_policy_reference_runtime_root",
        "paper_performance_claim": False,
        "no_outperform_final_v23_claim": True,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "output_only_correction": False,
        "bad_epoch_deletion_for_metric": False,
        "fgo": False,
    }
    _write_json(out / "N7A_GO2_WEAK_PRIOR_RUN_REPORT.json", run_report)
    print(json.dumps(decision, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
