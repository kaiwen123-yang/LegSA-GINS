#!/usr/bin/env python3
"""Run N4H4D LegSA-v23 clean replay parity / gap screen.

中文说明：该脚本只把 clean `.gnss/.imu` 送入 LegSA 自有 v23-core，
dual_final_v23 只作为 evaluation reference；不做 trace solver input。
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from legsa_gins.evaluation.legsa_v23_clean_replay_evaluator import (  # noqa: E402
    compare_to_references,
    evaluate_legsa_clean_replay,
    load_dual_official_reference,
    load_external_clean_summary,
    write_report,
)
from legsa_gins.evaluation.legsa_v23_clean_replay_runner import (  # noqa: E402
    build_clean_replay_config,
    check_runtime_outputs,
    default_clean_root,
    default_dual_root,
    default_output_root,
    run_legsa_v23_core,
)
from legsa_gins.evaluation.legsa_v23_gap_screen import screen_gap  # noqa: E402
from legsa_gins.evaluation.legsa_v23_parity_decision import make_decision  # noqa: E402


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _empty_summary(reason: str) -> dict[str, Any]:
    return {
        "count": 0,
        "aligned_count": 0,
        "evidence_status": reason,
        "horizontal_rmse_m": None,
        "up_rmse_m": None,
        "yaw_rmse_deg": None,
        "roll_rmse_deg": None,
        "pitch_rmse_deg": None,
        "trace_solver_input": False,
        "final_v23_output_substitution": False,
        "output_only_correction": False,
        "bad_epoch_deletion_for_metric": False,
        "numerical_performance_claim": False,
    }


def _write_markdown(path: Path, report: dict[str, Any]) -> None:
    summary = report.get("summary", {})
    decision = report.get("decision", {})
    gap = report.get("gap_screen", {})
    lines = [
        "# N4H4D LegSA-v23 Clean Replay Parity",
        "",
        "This runtime report is engineering baseline parity evidence only. It is not a paper performance claim.",
        "",
        "Runtime inputs are role-based clean status-yaw `.gnss/.imu` files. dual_final_v23 is used only as evaluation reference.",
        "",
        "## Summary",
        "",
    ]
    for field in [
        "horizontal_rmse_m",
        "up_rmse_m",
        "yaw_rmse_deg",
        "roll_rmse_deg",
        "pitch_rmse_deg",
        "count",
    ]:
        lines.append(f"- {field}: {summary.get(field)}")
    lines.extend(
        [
            "",
            f"- parity_classification: {decision.get('parity_classification')}",
            f"- recommended_next_stage: {gap.get('recommended_next_stage')}",
            f"- blocking_issues: {gap.get('blocking_issues')}",
            "",
            "Forbidden boundaries: trace_solver_input=false, final_v23_output_substitution=false, "
            "output_only_correction=false, bad_epoch_deletion_for_metric=false, numerical_performance_claim=false.",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def run(args: argparse.Namespace) -> dict[str, Any]:
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    config_report = build_clean_replay_config(args.clean_root, out)
    runner_report: dict[str, Any] = {
        "phase": "N4H4D",
        "clean_input_status": config_report.get("clean_input_status", config_report.get("config_status")),
        "config_report": config_report,
        "clean_root_role": "N4H2G_CLEAN_ROOT",
        "dual_root_role": "DUAL_FINAL_V23_ARTIFACT_ROOT",
        "output_root_role": "N4H4D_OUTPUT_ROOT",
        "trace_solver_input": False,
        "final_v23_output_substitution": False,
        "output_only_correction": False,
        "bad_epoch_deletion_for_metric": False,
        "numerical_performance_claim": False,
    }

    if config_report.get("config_status") != "config_written":
        summary = _empty_summary("clean_input_missing")
        decision = make_decision(summary)
        gap = screen_gap(summary, {}, runner_report, decision)
        report = {"summary": summary, "decision": decision, "gap_screen": gap, "runner_report": runner_report}
        _write_json(out / "LEGSA_V23_CLEAN_REPLAY_SUMMARY.json", summary)
        _write_json(out / "LEGSA_V23_CLEAN_REPLAY_REPORT.json", report)
        _write_json(out / "LEGSA_V23_CLEAN_REPLAY_GAP_SCREEN.json", gap)
        _write_json(out / "LEGSA_V23_CLEAN_REPLAY_DECISION.json", decision)
        _write_markdown(out / "n4h4d_legsa_v23_clean_replay_parity.md", report)
        return report

    run_report = run_legsa_v23_core(args.exe, str(config_report["config_path"]), out, args.allow_run)
    runtime_outputs = check_runtime_outputs(out)
    manifest = runtime_outputs.get("manifest", {})
    runner_report.update({"run_report": run_report, "runtime_outputs": runtime_outputs})

    external_clean = load_external_clean_summary(args.clean_root)
    dual_reference = load_dual_official_reference(args.dual_root)
    runner_report["dual_reference_status"] = dual_reference.get("dual_reference_status")

    eval_nav = out / "EVAL_NAV.csv"
    if (
        run_report.get("run_status") != "completed"
        or runtime_outputs.get("runtime_output_status") != "outputs_ready"
        or dual_reference.get("dual_reference_status") != "reference_loaded"
        or not eval_nav.exists()
    ):
        reason = "runtime_or_reference_missing"
        summary = _empty_summary(reason)
        evaluation = {"phase": "N4H4D", "summary": summary, "evidence_status": reason}
        comparison = compare_to_references(summary, external_clean, dual_reference.get("official_summary", {}))
    else:
        evaluation = evaluate_legsa_clean_replay(eval_nav, dual_reference["reference_rows"], out)
        summary = evaluation["summary"]
        comparison = compare_to_references(summary, external_clean, dual_reference.get("official_summary", {}))

    decision = make_decision(summary, external_clean)
    gap = screen_gap(summary, manifest, runner_report, decision)
    report = {
        "phase": "N4H4D",
        "summary": summary,
        "runner_report": runner_report,
        "evaluation_report": evaluation,
        "comparison_report": comparison,
        "decision": decision,
        "gap_screen": gap,
        "manifest": manifest,
        "trace_solver_input": False,
        "final_v23_output_substitution": False,
        "output_only_correction": False,
        "bad_epoch_deletion_for_metric": False,
        "numerical_performance_claim": False,
    }
    write_report(out / "LEGSA_V23_CLEAN_REPLAY_REPORT.json", report)
    _write_json(out / "LEGSA_V23_CLEAN_REPLAY_GAP_SCREEN.json", gap)
    _write_json(out / "LEGSA_V23_CLEAN_REPLAY_DECISION.json", decision)
    if not (out / "LEGSA_V23_CLEAN_REPLAY_SUMMARY.json").exists():
        _write_json(out / "LEGSA_V23_CLEAN_REPLAY_SUMMARY.json", summary)
    _write_markdown(out / "n4h4d_legsa_v23_clean_replay_parity.md", report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--clean-root", default=str(default_clean_root()))
    parser.add_argument("--dual-root", default=str(default_dual_root()))
    parser.add_argument("--output-dir", default=str(default_output_root()))
    parser.add_argument("--build-dir", default="build/cpp")
    parser.add_argument("--exe", default="./build/cpp/legsa_v23_core_demo")
    parser.add_argument("--allow-run", action="store_true")
    args = parser.parse_args()
    report = run(args)
    print(json.dumps({
        "summary": report.get("summary"),
        "decision": report.get("decision"),
        "gap_screen": report.get("gap_screen"),
    }, indent=2, sort_keys=True))
    return 1 if report.get("runner_report", {}).get("clean_input_status") == "clean_input_missing" else 0


if __name__ == "__main__":
    raise SystemExit(main())
