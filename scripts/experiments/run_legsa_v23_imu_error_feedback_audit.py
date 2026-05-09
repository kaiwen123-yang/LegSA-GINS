#!/usr/bin/env python3
"""Run N4H4D6 IMU error feedback and compensation diagnostics."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from legsa_gins.evaluation.legsa_v23_bias_scale_variant_matrix import run_bias_scale_variant_matrix  # noqa: E402
from legsa_gins.evaluation.legsa_v23_clean_replay_runner import (  # noqa: E402
    build_clean_replay_config,
    check_runtime_outputs,
    default_clean_root,
    default_dual_root,
)
from legsa_gins.evaluation.legsa_v23_covariance_unit_parity import audit_covariance_unit_parity  # noqa: E402
from legsa_gins.evaluation.legsa_v23_d6_decision import classify_d6  # noqa: E402
from legsa_gins.evaluation.legsa_v23_imu_compensation_timing import analyze_imu_compensation_timing  # noqa: E402
from legsa_gins.evaluation.legsa_v23_imu_error_feedback_audit import analyze_imu_error_feedback  # noqa: E402


def default_output_root() -> Path:
    return Path.home() / "legsa_n4h4d6_imu_error_feedback"


def default_d5_root() -> Path:
    return Path.home() / "legsa_n4h4d5_gain_feedback_isolation"


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _build_cpp(build_dir: str | Path) -> dict[str, Any]:
    """中文说明：构建 LegSA-v23-core；不编译 reference/final_v23_repo。"""

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


def _run_d6_debug_replay(args: argparse.Namespace, out: Path) -> dict[str, Any]:
    """中文说明：运行默认 solver 并打开 D6 debug trace；不启用正式性能 variant。"""

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
        "--debug-imu-error-feedback",
        "--debug-imu-compensation",
        "--debug-cross-covariance",
        "--debug-max-rows",
        "100000",
        "--diagnostic-run-label",
        "n4h4d6_imu_error_feedback",
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
        "output_only_correction": False,
        "bad_epoch_deletion_for_metric": False,
        "numerical_performance_claim": False,
    }


def _write_markdown(path: Path, report: dict[str, Any]) -> None:
    imu = report.get("imu_error_feedback_report", {})
    comp = report.get("imu_compensation_timing_report", {})
    cov = report.get("covariance_unit_parity_report", {})
    matrix = report.get("bias_scale_variant_matrix_report", {})
    decision = report.get("decision", {})
    lines = [
        "# N4H4D6 IMU Error Feedback Audit",
        "",
        "N4H4D6 audits IMU error-state feedback, compensation timing, covariance-unit parity, and bias/scale diagnostic variants.",
        "All outputs are diagnostic-only; no trace, external clean NAV, or final_v23 output enters the solver.",
        "",
        "## IMU Error Feedback",
        f"- bias_scale_feedback_primary_suspect: {imu.get('bias_scale_feedback_primary_suspect')}",
        f"- bias_feedback_overcorrection: {imu.get('bias_feedback_overcorrection')}",
        f"- scale_feedback_overcorrection: {imu.get('scale_feedback_overcorrection')}",
        "",
        "## Compensation Timing",
        f"- repeated_compensation_detected: {comp.get('repeated_compensation_detected')}",
        f"- compensation_not_persistent_issue: {comp.get('compensation_not_persistent_issue')}",
        f"- res3_interpolation_compensation_issue: {comp.get('res3_interpolation_compensation_issue')}",
        f"- compensation_timing_ok: {comp.get('compensation_timing_ok')}",
        "",
        "## Covariance Units",
        f"- init_bias_scale_std_units_ok: {cov.get('init_bias_scale_std_units_ok')}",
        f"- process_noise_units_ok: {cov.get('process_noise_units_ok')}",
        f"- corr_time_units_ok: {cov.get('corr_time_units_ok')}",
        f"- Qc_bias_model_ok: {cov.get('Qc_bias_model_ok')}",
        f"- covariance_unit_mismatch_suspect: {cov.get('covariance_unit_mismatch_suspect')}",
        "",
        "## Bias/Scale Matrix",
        f"- best_diagnostic_variant: {matrix.get('best_diagnostic_variant')}",
        f"- bias_scale_feedback_primary_suspect: {matrix.get('bias_scale_feedback_primary_suspect')}",
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
    run_report = _run_d6_debug_replay(args, out) if build_report.get("build_status") == "passed" else {"run_status": "build_failed"}
    debug_dir = Path(run_report.get("debug_dir", out / "debug"))

    imu_error_feedback_report = analyze_imu_error_feedback(debug_dir / "IMU_ERROR_FEEDBACK_TRACE.csv")
    imu_compensation_timing_report = analyze_imu_compensation_timing(debug_dir / "IMU_COMPENSATION_TRACE.csv")
    covariance_unit_parity_report = audit_covariance_unit_parity(
        debug_dir / "IMU_ERROR_UNIT_SNAPSHOT.json",
        debug_dir / "CONFIG_INIT_SNAPSHOT.json",
    )
    if args.run_bias_scale_variant_matrix:
        bias_scale_variant_matrix_report = run_bias_scale_variant_matrix(
            args.clean_root,
            args.dual_root,
            out / "bias_scale_variant_matrix",
            args.exe,
            allow_run=args.allow_run,
            timeout_s=args.variant_timeout_s,
            parallel_workers=args.variant_workers,
        )
    else:
        bias_scale_variant_matrix_report = {
            "phase": "N4H4D6",
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

    d5_report = _read_json(Path(args.d5_root) / "N4H4D5_DECISION_REPORT.json")
    decision = classify_d6(
        imu_error_feedback_report,
        imu_compensation_timing_report,
        covariance_unit_parity_report,
        bias_scale_variant_matrix_report,
        d5_report,
    )
    combined = {
        "phase": "N4H4D6",
        "build_report": build_report,
        "run_report": run_report,
        "imu_error_feedback_report": imu_error_feedback_report,
        "imu_compensation_timing_report": imu_compensation_timing_report,
        "covariance_unit_parity_report": covariance_unit_parity_report,
        "bias_scale_variant_matrix_report": bias_scale_variant_matrix_report,
        "decision": decision,
        "diagnostic_only": True,
        "not_for_performance_claim": True,
        "trace_solver_input": False,
        "final_v23_output_substitution": False,
        "output_only_correction": False,
        "bad_epoch_deletion_for_metric": False,
        "numerical_performance_claim": False,
    }
    _write_json(out / "IMU_ERROR_FEEDBACK_AUDIT_REPORT.json", imu_error_feedback_report)
    _write_json(out / "IMU_COMPENSATION_TIMING_REPORT.json", imu_compensation_timing_report)
    _write_json(out / "COVARIANCE_UNIT_PARITY_REPORT.json", covariance_unit_parity_report)
    _write_json(out / "BIAS_SCALE_VARIANT_MATRIX_REPORT.json", bias_scale_variant_matrix_report)
    _write_json(out / "N4H4D6_DECISION_REPORT.json", decision)
    _write_json(out / "N4H4D6_IMU_ERROR_FEEDBACK_AUDIT_REPORT.json", combined)
    _write_markdown(out / "n4h4d6_imu_error_feedback_audit.md", combined)
    return combined


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--clean-root", type=Path, default=default_clean_root())
    parser.add_argument("--dual-root", type=Path, default=default_dual_root())
    parser.add_argument("--d5-root", type=Path, default=default_d5_root())
    parser.add_argument("--output-dir", type=Path, default=default_output_root())
    parser.add_argument("--build-dir", type=Path, default=Path("build/cpp"))
    parser.add_argument("--exe", type=Path, default=Path("./build/cpp/legsa_v23_core_demo"))
    parser.add_argument("--allow-run", action="store_true")
    parser.add_argument("--run-bias-scale-variant-matrix", action="store_true")
    parser.add_argument("--variant-timeout-s", type=float, default=120.0)
    parser.add_argument("--variant-workers", type=int, default=4)
    return parser.parse_args()


def main() -> int:
    report = run(parse_args())
    print(json.dumps(report["decision"], indent=2, sort_keys=True))
    return 0 if report.get("build_report", {}).get("build_status") == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())

