#!/usr/bin/env python3
"""Run N4H4R3 source-backed port clean replay parity.

中文说明：真实 clean 输入只进入 port-core；dual_final_v23 official reference 只用于
fresh evaluation，不是 solver input。
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from legsa_gins.evaluation.legsa_v23_port_clean_replay_evaluator import (
    evaluate_port_clean_replay,
    write_json,
)
from legsa_gins.evaluation.legsa_v23_port_clean_replay_runner import (
    locate_clean_inputs,
    run_port_core,
    write_port_clean_config,
)
from legsa_gins.evaluation.legsa_v23_port_gap_screen import make_port_gap_screen
from legsa_gins.evaluation.legsa_v23_port_parity_decision import make_port_parity_decision


def _run_build(build_dir: Path) -> None:
    for command in [["cmake", "-S", "cpp", "-B", str(build_dir)], ["cmake", "--build", str(build_dir)]]:
        completed = subprocess.run(command, cwd=ROOT, check=False, capture_output=True, text=True)
        if completed.returncode != 0:
            raise RuntimeError("command failed: " + " ".join(command) + "\n" + completed.stdout + completed.stderr)


def _write_markdown(path: Path, summary: dict, gap: dict, decision: dict) -> None:
    path.write_text(
        "\n".join(
            [
                "# N4H4R3 Port Clean Replay Parity",
                "",
                "This report is an engineering backbone parity diagnostic only.",
                "It is not a paper performance claim and it is not a proposed factor result.",
                "",
                f"- parity_classification: {decision.get('parity_classification')}",
                f"- recommended_next_stage: {decision.get('recommended_next_stage')}",
                f"- count: {summary.get('count')}",
                f"- horizontal_rmse_m: {summary.get('horizontal_rmse_m')}",
                f"- up_rmse_m: {summary.get('up_rmse_m')}",
                f"- yaw_rmse_deg: {summary.get('yaw_rmse_deg')}",
                f"- roll_rmse_deg: {summary.get('roll_rmse_deg')}",
                f"- pitch_rmse_deg: {summary.get('pitch_rmse_deg')}",
                f"- gap_categories: {', '.join(gap.get('gap_categories', []))}",
                "",
            ]
        ),
        encoding="utf-8",
    )


def run_pipeline(args: argparse.Namespace) -> dict:
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    if args.allow_run:
        _run_build(Path(args.build_dir))
    clean_inputs = locate_clean_inputs(args.clean_root)
    config_report = write_port_clean_config(clean_inputs, output_dir)
    run_report = {"port_core_run_status": "clean_input_missing", "manifest": {}, "outputs": {}}
    if not clean_inputs["clean_input_missing"]:
        run_report = run_port_core(
            args.exe,
            config_report["config_path"],
            output_dir / "run",
            allow_run=args.allow_run,
            cwd=ROOT,
        )

    summary: dict = {
        "phase": "N4H4R3",
        "count": 0,
        "aligned_count": 0,
        "evidence_status": "run_failed_or_missing_output",
        "engineering_backbone_parity_only": True,
        "paper_performance_claim": False,
        "proposed_factor_claim": False,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "output_only_correction": False,
        "bad_epoch_deletion_for_metric": False,
    }
    report: dict = {
        "phase": "N4H4R3",
        "clean_inputs": clean_inputs,
        "config_report": config_report,
        "run_report": run_report,
        "summary": summary,
        "engineering_backbone_parity_only": True,
        "paper_performance_claim": False,
        "proposed_factor_claim": False,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "output_only_correction": False,
        "bad_epoch_deletion_for_metric": False,
    }

    eval_value = run_report.get("outputs", {}).get("EVAL_NAV.csv")
    eval_path = Path(eval_value) if eval_value else None
    if eval_path and eval_path.exists() and Path(args.dual_root, "KF_GINS_Navresult.nav").exists():
        eval_report = evaluate_port_clean_replay(
            eval_path,
            args.dual_root,
            output_dir / "LEGSA_PORT_CLEAN_REPLAY_ERROR_SERIES.csv",
        )
        summary = eval_report["summary"]
        report.update({"evaluation_report": eval_report, "summary": summary})

    manifest = run_report.get("manifest", {})
    gap_screen = make_port_gap_screen(
        summary,
        manifest,
        clean_inputs,
        run_status=run_report.get("port_core_run_status", "failed"),
    )
    decision = make_port_parity_decision(summary, gap_screen)
    report["gap_screen"] = gap_screen
    report["decision"] = decision

    write_json(output_dir / "LEGSA_PORT_CLEAN_REPLAY_SUMMARY.json", summary)
    write_json(output_dir / "LEGSA_PORT_CLEAN_REPLAY_REPORT.json", report)
    write_json(output_dir / "LEGSA_PORT_CLEAN_REPLAY_GAP_SCREEN.json", gap_screen)
    write_json(output_dir / "LEGSA_PORT_CLEAN_REPLAY_DECISION.json", decision)
    _write_markdown(output_dir / "n4h4r3_port_clean_replay_parity.md", summary, gap_screen, decision)
    return report


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--clean-root", default="/home/kaiwen/legsa_n4h2g_clean_replay")
    parser.add_argument("--dual-root", default="/home/kaiwen/legsa_external_artifacts/dual_final_v23_nominal")
    parser.add_argument("--output-dir", default="/home/kaiwen/legsa_n4h4r3_port_clean_parity")
    parser.add_argument("--build-dir", default="build/cpp")
    parser.add_argument("--exe", default="./build/cpp/legsa_v23_port_core_demo")
    parser.add_argument("--allow-run", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    report = run_pipeline(args)
    print(json.dumps(report["decision"], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
