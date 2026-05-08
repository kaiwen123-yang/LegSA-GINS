#!/usr/bin/env python3
"""Run N4H4D1 first-epoch/config/update-isolation diagnostics.

中文说明：本脚本只运行诊断，不修 solver 数学、不调参、不删 epoch；
diagnostic variants 不允许作为性能结果。
"""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
import sys
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from legsa_gins.evaluation.legsa_v23_clean_replay_runner import (  # noqa: E402
    build_clean_replay_config,
    check_runtime_outputs,
    default_clean_root,
    default_dual_root,
)
from legsa_gins.evaluation.legsa_v23_config_init_parity import (  # noqa: E402
    compare_config_init,
    load_external_clean_config_if_available,
)
from legsa_gins.evaluation.legsa_v23_failure_classifier import classify_failure  # noqa: E402
from legsa_gins.evaluation.legsa_v23_first_epoch_diagnostics import analyze_first_epoch  # noqa: E402
from legsa_gins.evaluation.legsa_v23_runtime_debug_trace import load_debug_bundle  # noqa: E402
from legsa_gins.evaluation.legsa_v23_update_isolation_matrix import run_update_isolation_matrix  # noqa: E402
from legsa_gins.evaluation.legsa_v23_update_residual_diagnostics import analyze_update_residuals  # noqa: E402


def default_output_root() -> Path:
    return Path.home() / "legsa_n4h4d1_diagnostics"


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _run_current_debug(args: argparse.Namespace, out: Path) -> dict[str, Any]:
    current_dir = out / "current"
    debug_dir = current_dir / "debug"
    config_report = build_clean_replay_config(args.clean_root, current_dir, current_dir / "config")
    if config_report.get("config_status") != "config_written":
        return {"run_status": "clean_input_missing", "config_report": config_report, "debug_dir": str(debug_dir)}
    command = [
        str(args.exe),
        "--config",
        str(config_report["config_path"]),
        "--output-dir",
        str(current_dir),
        "--debug-output-dir",
        str(debug_dir),
        "--debug-max-updates",
        "30",
        "--diagnostic-run-label",
        "all_updates_current",
    ]
    if not args.allow_run:
        return {"run_status": "not_run_without_allow_run", "config_report": config_report, "debug_dir": str(debug_dir)}
    completed = subprocess.run(command, cwd=REPO_ROOT, check=False, capture_output=True, text=True)
    outputs = check_runtime_outputs(current_dir)
    return {
        "run_status": "completed" if completed.returncode == 0 else "failed",
        "returncode": completed.returncode,
        "stdout_tail": completed.stdout[-1000:],
        "stderr_tail": completed.stderr[-1000:],
        "config_report": config_report,
        "runtime_outputs": outputs,
        "debug_dir": str(debug_dir),
        "trace_solver_input": False,
        "final_v23_output_substitution": False,
        "output_only_correction": False,
        "bad_epoch_deletion_for_metric": False,
        "numerical_performance_claim": False,
    }


def _write_markdown(path: Path, report: dict[str, Any]) -> None:
    first_epoch = report.get("first_epoch_report", {})
    residual = report.get("residual_report", {})
    decision = report.get("failure_decision", {})
    lines = [
        "# N4H4D1 First-Epoch Diagnostics",
        "",
        "N4H4D failed honestly. N4H4D1 adds diagnostic-only instrumentation and isolation runs.",
        "",
        "No solver math is fixed here. No tuning, no epoch deletion, no output-only correction, and no performance claim.",
        "",
        "## First Epoch",
        f"- first_yaw_residual_deg: {first_epoch.get('first_yaw_residual_deg')}",
        f"- first_position_residual_norm_m: {first_epoch.get('first_position_residual_norm_m')}",
        f"- first_velocity_residual_norm_mps: {first_epoch.get('first_velocity_residual_norm_mps')}",
        f"- first_dx_phi_norm_deg: {first_epoch.get('first_dx_phi_norm_deg')}",
        "",
        "## Residuals",
        f"- yaw_reject_ratio: {residual.get('yaw_reject_ratio')}",
        f"- position_residual_norm_p95_m: {residual.get('position_residual_norm_p95_m')}",
        f"- velocity_residual_norm_p95_mps: {residual.get('velocity_residual_norm_p95_mps')}",
        "",
        "## Decision",
        f"- failure_classification: {decision.get('failure_classification')}",
        f"- recommended_next_stage: {decision.get('recommended_next_stage')}",
        f"- blocking_issues: {decision.get('blocking_issues')}",
        "",
        "All generated debug CSV/JSON files are runtime-only artifacts and must not be committed.",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def run(args: argparse.Namespace) -> dict[str, Any]:
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    current_run = _run_current_debug(args, out)
    debug_bundle = load_debug_bundle(current_run["debug_dir"])
    external_policy = load_external_clean_config_if_available(args.clean_root, args.dual_root, None)
    config_report = compare_config_init(debug_bundle["config_snapshot"], external_policy)
    first_epoch_report = analyze_first_epoch(
        debug_bundle["config_snapshot"],
        debug_bundle["input_snapshot"],
        debug_bundle["first_updates"],
        debug_bundle["first_propagations"],
    )
    residual_report = analyze_update_residuals(debug_bundle["first_updates"])
    if args.run_isolation_matrix:
        isolation_report = run_update_isolation_matrix(
            args.clean_root,
            args.dual_root,
            out / "isolation",
            args.exe,
            allow_run=args.allow_run,
        )
    elif (out / "UPDATE_ISOLATION_MATRIX_REPORT.json").exists():
        isolation_report = json.loads((out / "UPDATE_ISOLATION_MATRIX_REPORT.json").read_text(encoding="utf-8"))
    else:
        isolation_report = {
            "phase": "N4H4D1",
            "recommended_issue_source": "evidence_missing",
            "variant_summaries": {},
            "diagnostic_only": True,
            "not_for_performance_claim": True,
            "trace_solver_input": False,
            "final_v23_output_substitution": False,
            "output_only_correction": False,
            "bad_epoch_deletion_for_metric": False,
            "numerical_performance_claim": False,
        }
    failure_decision = classify_failure(config_report, first_epoch_report, residual_report, isolation_report)
    report = {
        "phase": "N4H4D1",
        "current_run": current_run,
        "config_report": config_report,
        "first_epoch_report": first_epoch_report,
        "residual_report": residual_report,
        "isolation_report": isolation_report,
        "failure_decision": failure_decision,
        "diagnostic_only": True,
        "not_for_performance_claim": True,
        "trace_solver_input": False,
        "final_v23_output_substitution": False,
        "output_only_correction": False,
        "bad_epoch_deletion_for_metric": False,
        "numerical_performance_claim": False,
    }
    _write_json(out / "CONFIG_INIT_PARITY_REPORT.json", config_report)
    _write_json(out / "FIRST_EPOCH_DIAGNOSTIC_REPORT.json", first_epoch_report)
    _write_json(out / "UPDATE_RESIDUAL_DIAGNOSTICS_REPORT.json", residual_report)
    _write_json(out / "UPDATE_ISOLATION_MATRIX_REPORT.json", isolation_report)
    _write_json(out / "N4H4D1_FAILURE_DECISION_REPORT.json", failure_decision)
    _write_json(out / "N4H4D1_DIAGNOSTICS_REPORT.json", report)
    _write_markdown(out / "n4h4d1_first_epoch_diagnostics.md", report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--clean-root", default=str(default_clean_root()))
    parser.add_argument("--dual-root", default=str(default_dual_root()))
    parser.add_argument("--output-dir", default=str(default_output_root()))
    parser.add_argument("--build-dir", default="build/cpp")
    parser.add_argument("--exe", default="./build/cpp/legsa_v23_core_demo")
    parser.add_argument("--allow-run", action="store_true")
    parser.add_argument("--run-isolation-matrix", action="store_true")
    args = parser.parse_args()
    report = run(args)
    print(
        json.dumps(
            {
                "config": report["config_report"],
                "first_epoch": report["first_epoch_report"],
                "residual": report["residual_report"],
                "failure_decision": report["failure_decision"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
