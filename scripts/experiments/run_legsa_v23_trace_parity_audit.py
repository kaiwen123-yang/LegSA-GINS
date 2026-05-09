#!/usr/bin/env python3
"""Run N4H4D4 external trace parity and shadow measurement audit.

中文说明：D4 只做 external-clean trace/shadow/gain 诊断；external NAV 不进入 solver，
不调参、不删 epoch、不做 output-only correction，也不形成 performance claim。
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from legsa_gins.evaluation.legsa_v23_clean_replay_runner import (  # noqa: E402
    build_clean_replay_config,
    check_runtime_outputs,
    default_clean_root,
    default_dual_root,
    locate_clean_inputs,
)
from legsa_gins.evaluation.legsa_v23_d4_decision import classify_d4  # noqa: E402
from legsa_gins.evaluation.legsa_v23_external_trace_parity import (  # noqa: E402
    compare_legsa_to_external_nav,
    locate_external_clean_nav,
    locate_first_divergence,
    parse_nav,
)
from legsa_gins.evaluation.legsa_v23_gain_feedback_audit import analyze_gain_feedback  # noqa: E402
from legsa_gins.evaluation.legsa_v23_runtime_debug_trace import read_json  # noqa: E402
from legsa_gins.evaluation.legsa_v23_runtime_loop_parity import compare_update_timeline  # noqa: E402
from legsa_gins.evaluation.legsa_v23_shadow_measurement_audit import build_shadow_measurement_residuals  # noqa: E402


def default_output_root() -> Path:
    return Path.home() / "legsa_n4h4d4_trace_parity"


def default_d1_root() -> Path:
    return Path.home() / "legsa_n4h4d1_diagnostics"


def default_d2_root() -> Path:
    return Path.home() / "legsa_n4h4d2_formula_variants"


def default_d3_root() -> Path:
    return Path.home() / "legsa_n4h4d3_guarded_formula_fix"


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _build_cpp(build_dir: str | Path) -> dict[str, Any]:
    commands = [["cmake", "-S", "cpp", "-B", str(build_dir)], ["cmake", "--build", str(build_dir)]]
    steps = []
    for command in commands:
        completed = subprocess.run(command, cwd=REPO_ROOT, check=False, capture_output=True, text=True)
        steps.append(
            {
                "command": command,
                "returncode": completed.returncode,
                "stdout_tail": completed.stdout[-1200:],
                "stderr_tail": completed.stderr[-1200:],
            }
        )
        if completed.returncode != 0:
            return {"build_status": "failed", "steps": steps}
    return {"build_status": "passed", "steps": steps}


def _run_debug_replay(args: argparse.Namespace, out: Path) -> dict[str, Any]:
    run_dir = out / "default_run"
    debug_dir = out / "debug"
    config_report = build_clean_replay_config(args.clean_root, run_dir, out / "config")
    if config_report.get("config_status") != "config_written":
        return {"run_status": "clean_input_missing", "config_report": config_report, "debug_dir": str(debug_dir)}
    if not args.allow_run:
        return {"run_status": "not_run_without_allow_run", "config_report": config_report, "debug_dir": str(debug_dir)}
    command = [
        str(args.exe),
        "--config",
        str(config_report["config_path"]),
        "--output-dir",
        str(run_dir),
        "--debug-output-dir",
        str(debug_dir),
        "--debug-full-update-trace",
        "--debug-full-state-trace",
        "--debug-measurement-matrix-trace",
        "--debug-gain-trace",
        "--debug-max-rows",
        "100000",
        "--diagnostic-run-label",
        "n4h4d4_external_trace_parity",
    ]
    completed = subprocess.run(command, cwd=REPO_ROOT, check=False, capture_output=True, text=True)
    return {
        "run_status": "completed" if completed.returncode == 0 else "failed",
        "returncode": completed.returncode,
        "stdout_tail": completed.stdout[-1000:],
        "stderr_tail": completed.stderr[-1000:],
        "config_report": config_report,
        "runtime_outputs": check_runtime_outputs(run_dir),
        "run_dir": str(run_dir),
        "debug_dir": str(debug_dir),
        "trace_solver_input": False,
        "final_v23_output_substitution": False,
        "output_only_correction": False,
        "bad_epoch_deletion_for_metric": False,
        "numerical_performance_claim": False,
        "shadow_external_nav_solver_input": False,
    }


def _load_context(root: str | Path, filename: str) -> dict[str, Any]:
    return read_json(Path(root) / filename)


def _write_markdown(path: Path, report: dict[str, Any]) -> None:
    trace = report.get("external_trace_report", {})
    shadow = report.get("shadow_measurement_report", {})
    decision = report.get("decision", {})
    lines = [
        "# N4H4D4 Trace Parity Shadow Audit",
        "",
        "N4H4D4 compares LegSA-v23-core runtime output against an external clean NAV reference.",
        "The external reference is diagnostic/evaluation-only and is never used as solver input.",
        "",
        "## External Trace",
        f"- aligned_count: {trace.get('aligned_count')}",
        f"- full_diff: {trace.get('full_diff')}",
        "",
        "## Shadow Measurement",
        f"- external_state_position_residual: {shadow.get('external_state_position_residual')}",
        f"- external_state_velocity_residual: {shadow.get('external_state_velocity_residual')}",
        f"- external_state_yaw_residual: {shadow.get('external_state_yaw_residual')}",
        f"- measurement_model_likely_ok_state_diverges: {shadow.get('measurement_model_likely_ok_state_diverges')}",
        f"- measurement_model_or_convention_issue: {shadow.get('measurement_model_or_convention_issue')}",
        "",
        "## Decision",
        f"- most_likely_issue: {decision.get('most_likely_issue')}",
        f"- recommended_next_stage: {decision.get('recommended_next_stage')}",
        f"- blocking_issues: {decision.get('blocking_issues')}",
        "",
        "No performance claim, no tuning, no output-only correction, no epoch deletion.",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def run(args: argparse.Namespace) -> dict[str, Any]:
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    build_report = _build_cpp(args.build_dir)
    run_report = _run_debug_replay(args, out) if build_report.get("build_status") == "passed" else {"run_status": "build_failed"}
    run_dir = Path(run_report.get("run_dir", out / "default_run"))
    debug_dir = Path(run_report.get("debug_dir", out / "debug"))
    external_nav_info = locate_external_clean_nav(args.clean_root, args.dual_root)
    legsa_nav = run_dir / "EVAL_NAV.csv"
    if external_nav_info.get("status") == "found" and legsa_nav.exists():
        external_trace_report = compare_legsa_to_external_nav(legsa_nav, external_nav_info["path"])
        external_rows = parse_nav(external_nav_info["path"])
    else:
        external_trace_report = {
            "aligned_count": 0,
            "legsa_count": len(parse_nav(legsa_nav)) if legsa_nav.exists() else 0,
            "external_count": 0,
            "external_nav_status": external_nav_info,
            "full_diff": {},
            "diff_series": [],
            "trace_solver_input": False,
            "shadow_external_nav_solver_input": False,
            "numerical_performance_claim": False,
        }
        external_rows = []
    loop_trace_path = debug_dir / "RUNTIME_LOOP_PARITY_TRACE.json"
    all_updates_path = debug_dir / "ALL_UPDATES.csv"
    clean_inputs = locate_clean_inputs(args.clean_root)
    runtime_loop_report = compare_update_timeline(clean_inputs.get("gnss_path"), loop_trace_path, all_updates_path)
    first_update_time = runtime_loop_report.get("first_update_time")
    first_divergence_report = locate_first_divergence(external_trace_report.get("diff_series", []), first_update_time)
    if external_rows and clean_inputs.get("gnss_path"):
        shadow_report = build_shadow_measurement_residuals(external_rows, clean_inputs["gnss_path"], all_updates_path)
    else:
        shadow_report = {
            "aligned_count": 0,
            "measurement_model_likely_ok_state_diverges": False,
            "measurement_model_or_convention_issue": False,
            "evidence_missing": ["external_nav_or_clean_gnss_missing"],
            "shadow_external_nav_solver_input": False,
            "trace_solver_input": False,
            "numerical_performance_claim": False,
        }
    gain_report = analyze_gain_feedback(all_updates_path)
    d1_report = _load_context(args.d1_root, "N4H4D1_FAILURE_DECISION_REPORT.json")
    d2_report = _load_context(args.d2_root, "N4H4D2_DECISION_REPORT.json")
    d3_report = _load_context(args.d3_root, "N4H4D3_DECISION_REPORT.json")
    decision = classify_d4(
        external_trace_report,
        first_divergence_report,
        runtime_loop_report,
        shadow_report,
        gain_report,
        d1_report,
        d2_report,
        d3_report,
    )
    external_trace_for_file = {key: value for key, value in external_trace_report.items() if key != "diff_series"}
    report = {
        "phase": "N4H4D4",
        "build_report": build_report,
        "run_report": run_report,
        "external_nav_info": external_nav_info,
        "external_trace_report": external_trace_for_file,
        "first_divergence_report": first_divergence_report,
        "runtime_loop_report": runtime_loop_report,
        "shadow_measurement_report": shadow_report,
        "gain_feedback_report": gain_report,
        "decision": decision,
        "trace_solver_input": False,
        "final_v23_output_substitution": False,
        "shadow_external_nav_solver_input": False,
        "output_only_correction": False,
        "bad_epoch_deletion_for_metric": False,
        "numerical_performance_claim": False,
        "not_for_performance_claim": True,
    }
    _write_json(out / "EXTERNAL_TRACE_PARITY_REPORT.json", external_trace_for_file)
    _write_json(out / "FIRST_DIVERGENCE_REPORT.json", first_divergence_report)
    _write_json(out / "RUNTIME_LOOP_PARITY_REPORT.json", runtime_loop_report)
    _write_json(out / "SHADOW_MEASUREMENT_AUDIT_REPORT.json", shadow_report)
    _write_json(out / "GAIN_FEEDBACK_AUDIT_REPORT.json", gain_report)
    _write_json(out / "N4H4D4_DECISION_REPORT.json", decision)
    _write_json(out / "N4H4D4_TRACE_PARITY_AUDIT_REPORT.json", report)
    _write_markdown(out / "n4h4d4_trace_parity_shadow_audit.md", report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--clean-root", default=str(default_clean_root()))
    parser.add_argument("--dual-root", default=str(default_dual_root()))
    parser.add_argument("--d1-root", default=str(default_d1_root()))
    parser.add_argument("--d2-root", default=str(default_d2_root()))
    parser.add_argument("--d3-root", default=str(default_d3_root()))
    parser.add_argument("--output-dir", default=str(default_output_root()))
    parser.add_argument("--build-dir", default="build/cpp")
    parser.add_argument("--exe", default="./build/cpp/legsa_v23_core_demo")
    parser.add_argument("--allow-run", action="store_true")
    args = parser.parse_args()
    report = run(args)
    print(
        json.dumps(
            {
                "external_trace": {
                    "aligned_count": report["external_trace_report"].get("aligned_count"),
                    "first_row_diff": report["external_trace_report"].get("first_row_diff"),
                    "full_diff": report["external_trace_report"].get("full_diff"),
                },
                "first_divergence": report["first_divergence_report"],
                "runtime_loop": report["runtime_loop_report"],
                "shadow_measurement": report["shadow_measurement_report"],
                "gain_feedback": report["gain_feedback_report"],
                "decision": report["decision"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
