#!/usr/bin/env python3
"""Run N4H4R3B over-close, copy-guard, and independence audits.

中文说明：本 runner 只生成 runtime-only 诊断报告；clean GNSS/IMU 是 solver input，
dual_final_v23 official reference 只用于 evaluation，不做性能 claim。
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from legsa_gins.evaluation.legsa_v23_port_clean_replay_evaluator import evaluate_port_clean_replay, write_json
from legsa_gins.evaluation.legsa_v23_port_clean_replay_runner import locate_clean_inputs, write_port_clean_config
from legsa_gins.evaluation.legsa_v23_port_covariance_config_parity import compare_port_config_to_external_policy
from legsa_gins.evaluation.legsa_v23_port_measurement_copy_guard import analyze_measurement_copy
from legsa_gins.evaluation.legsa_v23_port_overclose_audit import analyze_overclose
from legsa_gins.evaluation.legsa_v23_port_overclose_decision import make_overclose_decision
from legsa_gins.evaluation.legsa_v23_port_reference_independence import analyze_reference_independence
from legsa_gins.evaluation.legsa_v23_port_residual_gain_audit import analyze_residual_gain


def _run(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=ROOT, check=False, capture_output=True, text=True)


def _build(build_dir: str) -> None:
    for command in [["cmake", "-S", "cpp", "-B", build_dir], ["cmake", "--build", build_dir]]:
        completed = _run(command)
        if completed.returncode != 0:
            raise RuntimeError("command failed: " + " ".join(command) + "\n" + completed.stdout + completed.stderr)


def _load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def _find_config(args: argparse.Namespace, clean_inputs: dict, output: Path) -> Path:
    candidates = [
        Path(args.r3a_root) / "config" / "legsa_v23_port_clean_replay.conf",
        Path(args.r3_root) / "config" / "legsa_v23_port_clean_replay.conf",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return Path(write_port_clean_config(clean_inputs, output)["config_path"])


def _write_markdown(path: Path, reports: dict) -> None:
    measurement = reports["measurement_copy"]
    independence = reports["reference_independence"]
    covariance = reports["covariance_config"]
    residual = reports["residual_gain"]
    overclose = reports["overclose"]
    decision = reports["decision"]
    path.write_text(
        "\n".join(
            [
                "# N4H4R3B Over-Close Audit",
                "",
                "This diagnostic screens metric-gate pass results for copy, reference, and covariance/config issues.",
                "It is not a paper performance claim and it does not claim outperforming final_v23.",
                "",
                f"- measurement_copy_suspect: {measurement.get('measurement_copy_suspect')}",
                f"- output_substitution_suspect: {measurement.get('output_substitution_suspect')}",
                f"- reference_independence_ok: {independence.get('reference_independence_ok')}",
                f"- config_matches_external_clean_policy: {covariance.get('config_matches_external_clean_policy')}",
                f"- over_tight_measurement_update_suspect: {residual.get('over_tight_measurement_update_suspect')}",
                f"- metric_gate_passed: {overclose.get('metric_gate_passed')}",
                f"- external_closeness_failed: {overclose.get('external_closeness_failed')}",
                f"- overclose_warning: {overclose.get('overclose_warning')}",
                f"- recommended_next_stage: {decision.get('recommended_next_stage')}",
                f"- parity_status: {decision.get('parity_status')}",
                "",
            ]
        ),
        encoding="utf-8",
    )


def run_pipeline(args: argparse.Namespace) -> dict:
    output = Path(args.output_dir)
    output.mkdir(parents=True, exist_ok=True)
    if args.allow_run:
        _build(args.build_dir)

    clean_inputs = locate_clean_inputs(args.clean_root)
    config_path = _find_config(args, clean_inputs, output)
    run_dir = output / "run"
    run_dir.mkdir(parents=True, exist_ok=True)
    command = [
        args.exe,
        "--config",
        str(config_path),
        "--output-dir",
        str(run_dir),
        "--debug-overclose-audit",
        "--debug-measurement-copy-guard",
        "--debug-covariance-gain",
        "--debug-output-dir",
        str(output),
    ]
    completed = _run(command) if args.allow_run else subprocess.CompletedProcess(command, 0, "", "")
    if completed.returncode != 0:
        raise RuntimeError(completed.stdout + completed.stderr)

    manifest = _load_json(run_dir / "RUN_MANIFEST.json")
    summary: dict = {
        "phase": "N4H4R3B",
        "count": 0,
        "engineering_backbone_parity_only": True,
        "paper_performance_claim": False,
        "proposed_factor_claim": False,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "output_only_correction": False,
        "bad_epoch_deletion_for_metric": False,
    }
    evaluation_report: dict = {}
    eval_nav = run_dir / "EVAL_NAV.csv"
    if eval_nav.exists() and (Path(args.dual_root) / "KF_GINS_Navresult.nav").exists():
        evaluation_report = evaluate_port_clean_replay(
            eval_nav,
            args.dual_root,
            output / "LEGSA_PORT_R3B_ERROR_SERIES.csv",
        )
        summary = evaluation_report["summary"]

    measurement_copy = analyze_measurement_copy(
        run_dir / "LegSA_PORT_NAV.nav",
        run_dir / "EVAL_NAV.csv",
        clean_inputs.get("gnss_path") or "",
        output,
    )
    reference_independence = analyze_reference_independence(
        manifest,
        config_path,
        {"clean_inputs": clean_inputs, "run_manifest": manifest},
        {
            **evaluation_report,
            "evaluation_reference_files": {"dual_official": str(Path(args.dual_root) / "KF_GINS_Navresult.nav")},
            "evaluation_reference_role": "dual_final_v23_reference_eval_only",
            "clean_gnss_evaluation_reference": False,
        },
    )
    covariance_config = compare_port_config_to_external_policy(config_path, {"clean_inputs": clean_inputs}, manifest)
    residual_gain = analyze_residual_gain(output / "PORT_UPDATE_RESIDUAL_GAIN_TRACE.csv")
    overclose = analyze_overclose(summary)
    if measurement_copy.get("measurement_copy_suspect") or measurement_copy.get("output_substitution_suspect"):
        overclose["overclose_to_measurement_suspect"] = True
    if not reference_independence.get("reference_independence_ok", False):
        overclose["overclose_to_reference_suspect"] = True
    decision = make_overclose_decision(overclose, measurement_copy, reference_independence, covariance_config, residual_gain)

    reports = {
        "summary": summary,
        "measurement_copy": measurement_copy,
        "reference_independence": reference_independence,
        "covariance_config": covariance_config,
        "residual_gain": residual_gain,
        "overclose": overclose,
        "decision": decision,
        "manifest": manifest,
    }
    write_json(output / "PORT_MEASUREMENT_COPY_GUARD_REPORT.json", measurement_copy)
    write_json(output / "PORT_REFERENCE_INDEPENDENCE_REPORT.json", reference_independence)
    write_json(output / "PORT_COVARIANCE_CONFIG_PARITY_REPORT.json", covariance_config)
    write_json(output / "PORT_RESIDUAL_GAIN_AUDIT_REPORT.json", residual_gain)
    write_json(output / "PORT_OVERCLOSE_AUDIT_REPORT.json", overclose)
    write_json(output / "PORT_OVERCLOSE_DECISION_REPORT.json", decision)
    write_json(output / "PORT_OVERCLOSE_RUN_REPORT.json", reports)
    _write_markdown(output / "n4h4r3b_overclose_audit.md", reports)
    return reports


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--clean-root", default=str(Path.home() / "legsa_n4h2g_clean_replay"))
    parser.add_argument("--dual-root", default=str(Path.home() / "legsa_external_artifacts" / "dual_final_v23_nominal"))
    parser.add_argument("--r3-root", default=str(Path.home() / "legsa_n4h4r3_port_clean_parity"))
    parser.add_argument("--r3a-root", default=str(Path.home() / "legsa_n4h4r3a_update_timeline"))
    parser.add_argument("--output-dir", default=str(Path.home() / "legsa_n4h4r3b_overclose_audit"))
    parser.add_argument("--build-dir", default="build/cpp")
    parser.add_argument("--exe", default="./build/cpp/legsa_v23_port_core_demo")
    parser.add_argument("--allow-run", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    report = run_pipeline(parse_args(argv or sys.argv[1:]))
    print(json.dumps(report["decision"], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
