#!/usr/bin/env python3
"""Run N4H4D5 one-step propagation, gain, and feedback diagnostics.

中文说明：D5 只做 external-state shadow / update-block / covariance-gain / feedback
isolation 诊断。external clean NAV 只作为离线诊断参考，不进入 solver；所有
diagnostic variant 都不是性能结果。
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
from legsa_gins.evaluation.legsa_v23_covariance_gain_isolation import analyze_covariance_gain_trace  # noqa: E402
from legsa_gins.evaluation.legsa_v23_d5_decision import classify_d5  # noqa: E402
from legsa_gins.evaluation.legsa_v23_external_state_shadow_update import run_external_state_shadow_update  # noqa: E402
from legsa_gins.evaluation.legsa_v23_external_trace_parity import locate_external_clean_nav  # noqa: E402
from legsa_gins.evaluation.legsa_v23_feedback_isolation import run_feedback_isolation_matrix  # noqa: E402
from legsa_gins.evaluation.legsa_v23_one_step_propagation_parity import run_one_step_propagation_parity  # noqa: E402
from legsa_gins.evaluation.legsa_v23_update_block_contribution import analyze_update_block_trace  # noqa: E402


def default_output_root() -> Path:
    return Path.home() / "legsa_n4h4d5_gain_feedback_isolation"


def default_d4_root() -> Path:
    return Path.home() / "legsa_n4h4d4_trace_parity"


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _build_cpp(build_dir: str | Path) -> dict[str, Any]:
    """中文说明：构建 LegSA-v23-core，不编译 reference/final_v23_repo。"""

    steps = []
    for command in [["cmake", "-S", "cpp", "-B", str(build_dir)], ["cmake", "--build", str(build_dir)]]:
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


def _run_d5_debug_replay(args: argparse.Namespace, out: Path) -> dict[str, Any]:
    """中文说明：运行默认 solver 并打开 D5 debug trace；不启用 solver variant。"""

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
        "--debug-update-blocks",
        "--debug-feedback-delta",
        "--debug-covariance-gain",
        "--debug-max-rows",
        "100000",
        "--diagnostic-run-label",
        "n4h4d5_gain_feedback_isolation",
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
        "diagnostic_only": True,
        "trace_solver_input": False,
        "final_v23_output_substitution": False,
        "shadow_external_nav_solver_input": False,
        "output_only_correction": False,
        "bad_epoch_deletion_for_metric": False,
        "numerical_performance_claim": False,
    }


def _write_markdown(path: Path, report: dict[str, Any]) -> None:
    one = report.get("one_step_report", {})
    block = report.get("update_block_report", {})
    cov = report.get("covariance_gain_report", {})
    matrix = report.get("feedback_isolation_matrix_report", {})
    shadow = report.get("external_state_shadow_update_report", {})
    decision = report.get("decision", {})
    lines = [
        "# N4H4D5 Gain Feedback Isolation",
        "",
        "N4H4D5 isolates one-step propagation, measurement block contributions, covariance/gain scaling, and stateFeedback behavior.",
        "External clean state is diagnostic-only and never enters the solver.",
        "",
        "## One-Step Propagation",
        f"- median_horizontal_step_error_m: {one.get('median_horizontal_step_error_m')}",
        f"- median_velocity_step_error_mps: {one.get('median_velocity_step_error_mps')}",
        f"- median_attitude_step_error_deg: {one.get('median_attitude_step_error_deg')}",
        f"- one_step_mechanization_ok: {one.get('one_step_mechanization_ok')}",
        f"- one_step_mechanization_suspect: {one.get('one_step_mechanization_suspect')}",
        "",
        "## Update Blocks",
        f"- worst_block_by_dx_phi: {block.get('worst_block_by_dx_phi')}",
        f"- first_block_causing_dx_phi_gt_5deg: {block.get('first_block_causing_dx_phi_gt_5deg')}",
        "",
        "## Covariance Gain",
        f"- gain_spike_drives_feedback: {cov.get('gain_spike_drives_feedback')}",
        f"- covariance_model_needs_unit_parity_audit: {cov.get('covariance_model_needs_unit_parity_audit')}",
        "",
        "## Feedback Matrix",
        f"- best_diagnostic_variant: {matrix.get('best_diagnostic_variant')}",
        f"- diagnostic_only: {matrix.get('diagnostic_only')}",
        "",
        "## Shadow Update",
        f"- large_dx_caused_by_state_divergence: {shadow.get('large_dx_caused_by_state_divergence')}",
        f"- gain_or_measurement_scaling_issue: {shadow.get('gain_or_measurement_scaling_issue')}",
        "",
        "## Decision",
        f"- most_likely_issue: {decision.get('most_likely_issue')}",
        f"- recommended_next_stage: {decision.get('recommended_next_stage')}",
        f"- blocking_issues: {decision.get('blocking_issues')}",
        "",
        "No performance claim, no output-only correction, no tuning, no epoch deletion.",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def run(args: argparse.Namespace) -> dict[str, Any]:
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    build_report = _build_cpp(args.build_dir)
    run_report = _run_d5_debug_replay(args, out) if build_report.get("build_status") == "passed" else {"run_status": "build_failed"}
    debug_dir = Path(run_report.get("debug_dir", out / "debug"))

    clean_inputs = locate_clean_inputs(args.clean_root)
    external_nav_info = locate_external_clean_nav(args.clean_root, args.dual_root)
    external_nav_path = external_nav_info.get("path")
    if external_nav_info.get("status") == "found" and external_nav_path:
        one_step_report = run_one_step_propagation_parity(external_nav_path, clean_inputs.get("imu_path"))
    else:
        one_step_report = {
            "status": "evidence_missing",
            "one_step_mechanization_ok": False,
            "one_step_mechanization_suspect": False,
            "shadow_external_nav_solver_input": False,
            "trace_solver_input": False,
            "numerical_performance_claim": False,
        }

    update_block_report = analyze_update_block_trace(debug_dir / "UPDATE_BLOCK_TRACE.csv", debug_dir / "FEEDBACK_DELTA_TRACE.csv")
    covariance_gain_report = analyze_covariance_gain_trace(debug_dir / "COVARIANCE_TRACE.csv", debug_dir / "UPDATE_BLOCK_TRACE.csv")
    if args.run_feedback_matrix:
        feedback_matrix_report = run_feedback_isolation_matrix(
            args.clean_root,
            args.dual_root,
            out / "feedback_matrix",
            args.exe,
            allow_run=args.allow_run,
            timeout_s=args.variant_timeout_s,
            parallel_workers=args.variant_workers,
        )
    else:
        feedback_matrix_report = {
            "phase": "N4H4D5",
            "variant_summaries": {},
            "best_diagnostic_variant": "not_run",
            "diagnostic_only": True,
            "not_for_performance_claim": True,
            "trace_solver_input": False,
            "final_v23_output_substitution": False,
            "output_only_correction": False,
            "bad_epoch_deletion_for_metric": False,
            "numerical_performance_claim": False,
        }

    if external_nav_info.get("status") == "found" and clean_inputs.get("gnss_path"):
        shadow_update_report = run_external_state_shadow_update(
            external_nav_path,
            clean_inputs["gnss_path"],
            debug_dir / "COVARIANCE_TRACE.csv",
            debug_dir / "ALL_UPDATES.csv",
        )
    else:
        shadow_update_report = {
            "status": "evidence_missing",
            "large_dx_caused_by_state_divergence": False,
            "gain_or_measurement_scaling_issue": False,
            "shadow_external_nav_solver_input": False,
            "trace_solver_input": False,
            "numerical_performance_claim": False,
        }

    d4_report = _read_json(Path(args.d4_root) / "N4H4D4_DECISION_REPORT.json")
    decision = classify_d5(
        one_step_report,
        update_block_report,
        covariance_gain_report,
        feedback_matrix_report,
        shadow_update_report,
        d4_report,
    )
    report = {
        "phase": "N4H4D5",
        "build_report": build_report,
        "run_report": run_report,
        "external_nav_info": external_nav_info,
        "one_step_report": one_step_report,
        "update_block_report": update_block_report,
        "covariance_gain_report": covariance_gain_report,
        "feedback_isolation_matrix_report": feedback_matrix_report,
        "external_state_shadow_update_report": shadow_update_report,
        "decision": decision,
        "diagnostic_only": True,
        "not_for_performance_claim": True,
        "trace_solver_input": False,
        "final_v23_output_substitution": False,
        "shadow_external_nav_solver_input": False,
        "output_only_correction": False,
        "bad_epoch_deletion_for_metric": False,
        "numerical_performance_claim": False,
    }
    _write_json(out / "ONE_STEP_PROPAGATION_PARITY_REPORT.json", one_step_report)
    _write_json(out / "UPDATE_BLOCK_CONTRIBUTION_REPORT.json", update_block_report)
    _write_json(out / "COVARIANCE_GAIN_ISOLATION_REPORT.json", covariance_gain_report)
    _write_json(out / "FEEDBACK_ISOLATION_MATRIX_REPORT.json", feedback_matrix_report)
    _write_json(out / "EXTERNAL_STATE_SHADOW_UPDATE_REPORT.json", shadow_update_report)
    _write_json(out / "N4H4D5_DECISION_REPORT.json", decision)
    _write_json(out / "N4H4D5_GAIN_FEEDBACK_ISOLATION_REPORT.json", report)
    _write_markdown(out / "n4h4d5_gain_feedback_isolation.md", report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--clean-root", default=str(default_clean_root()))
    parser.add_argument("--dual-root", default=str(default_dual_root()))
    parser.add_argument("--d4-root", default=str(default_d4_root()))
    parser.add_argument("--output-dir", default=str(default_output_root()))
    parser.add_argument("--build-dir", default="build/cpp")
    parser.add_argument("--exe", default="./build/cpp/legsa_v23_core_demo")
    parser.add_argument("--allow-run", action="store_true")
    parser.add_argument("--run-feedback-matrix", action="store_true")
    parser.add_argument("--variant-timeout-s", type=float, default=120.0)
    parser.add_argument("--variant-workers", type=int, default=4)
    args = parser.parse_args()
    report = run(args)
    print(
        json.dumps(
            {
                "one_step": report["one_step_report"],
                "update_block": {
                    "worst_block_by_dx_phi": report["update_block_report"].get("worst_block_by_dx_phi"),
                    "first_block_causing_dx_phi_gt_5deg": report["update_block_report"].get(
                        "first_block_causing_dx_phi_gt_5deg"
                    ),
                },
                "covariance_gain": {
                    "gain_spike_drives_feedback": report["covariance_gain_report"].get("gain_spike_drives_feedback"),
                    "covariance_model_needs_unit_parity_audit": report["covariance_gain_report"].get(
                        "covariance_model_needs_unit_parity_audit"
                    ),
                },
                "feedback_matrix": {
                    "best_diagnostic_variant": report["feedback_isolation_matrix_report"].get("best_diagnostic_variant"),
                    "diagnostic_only": report["feedback_isolation_matrix_report"].get("diagnostic_only"),
                },
                "shadow_update": report["external_state_shadow_update_report"],
                "decision": report["decision"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
