#!/usr/bin/env python3
"""Run N4H4D3 source-backed guarded formula fix replay.

中文说明：D3 只运行 source-backed 默认公式和 clean replay gap screen；
不启用 diagnostic variants，不调参，不删 epoch，不做 output-only correction。
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

from legsa_gins.evaluation.legsa_v23_clean_replay_runner import default_clean_root, default_dual_root  # noqa: E402
from legsa_gins.evaluation.legsa_v23_guarded_fix_decision import make_guarded_fix_decision  # noqa: E402
from legsa_gins.evaluation.legsa_v23_guarded_fix_replay import run_guarded_fix_clean_replay  # noqa: E402
from legsa_gins.evaluation.legsa_v23_guarded_formula_fix_audit import audit_guarded_fix_source  # noqa: E402
from legsa_gins.evaluation.legsa_v23_runtime_debug_trace import read_json  # noqa: E402


def default_d2_root() -> Path:
    return Path.home() / "legsa_n4h4d2_formula_variants"


def default_output_root() -> Path:
    return Path.home() / "legsa_n4h4d3_guarded_formula_fix"


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _build_cpp(build_dir: str | Path) -> dict[str, Any]:
    """中文说明：runner 内执行 C++ build，确保 replay 使用当前 guarded formula 代码。"""

    commands = [["cmake", "-S", "cpp", "-B", str(build_dir)], ["cmake", "--build", str(build_dir)]]
    reports = []
    for command in commands:
        completed = subprocess.run(command, cwd=REPO_ROOT, check=False, capture_output=True, text=True)
        reports.append(
            {
                "command": command,
                "returncode": completed.returncode,
                "stdout_tail": completed.stdout[-1200:],
                "stderr_tail": completed.stderr[-1200:],
            }
        )
        if completed.returncode != 0:
            return {"build_status": "failed", "steps": reports}
    return {"build_status": "passed", "steps": reports}


def _write_markdown(path: Path, report: dict[str, Any]) -> None:
    summary = report.get("replay_report", {}).get("summary", {})
    decision = report.get("decision", {})
    comparison = report.get("replay_report", {}).get("comparison_report", {})
    lines = [
        "# N4H4D3 Guarded Formula Fix",
        "",
        "D3 applies source-backed formula verification/fixes only. It does not promote diagnostic variants.",
        "",
        "## Source Audit",
        f"- audit_status: {report.get('audit_report', {}).get('audit_status')}",
        f"- source_backed_fix_applied: {report.get('audit_report', {}).get('source_backed_fix_applied')}",
        f"- yaw_H_mapping_not_fixed_in_D3: {report.get('audit_report', {}).get('yaw_H_mapping_not_fixed_in_D3')}",
        "",
        "## Replay Summary",
        f"- horizontal_rmse_m: {summary.get('horizontal_rmse_m')}",
        f"- up_rmse_m: {summary.get('up_rmse_m')}",
        f"- yaw_rmse_deg: {summary.get('yaw_rmse_deg')}",
        f"- roll_rmse_deg: {summary.get('roll_rmse_deg')}",
        f"- pitch_rmse_deg: {summary.get('pitch_rmse_deg')}",
        f"- count: {summary.get('count')}",
        f"- guarded_fix_parity_status: {summary.get('guarded_fix_parity_status')}",
        "",
        "## Comparison",
        f"- delta_vs_N4H4D_baseline_current: {comparison.get('delta_vs_N4H4D_baseline_current')}",
        f"- delta_vs_external_clean_replay: {comparison.get('delta_vs_external_clean_replay')}",
        "",
        "## Decision",
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
    audit_report = audit_guarded_fix_source(REPO_ROOT)
    build_report = _build_cpp(args.build_dir)
    replay_report = run_guarded_fix_clean_replay(
        args.clean_root,
        args.dual_root,
        args.d2_root,
        out,
        args.exe,
        allow_run=args.allow_run and build_report.get("build_status") == "passed",
    )
    d2_report = read_json(Path(args.d2_root) / "N4H4D2_DECISION_REPORT.json")
    decision = make_guarded_fix_decision(audit_report, replay_report, d2_report)
    report = {
        "phase": "N4H4D3",
        "audit_report": audit_report,
        "build_report": build_report,
        "replay_report": replay_report,
        "d2_decision": d2_report,
        "decision": decision,
        "trace_solver_input": False,
        "final_v23_output_substitution": False,
        "output_only_correction": False,
        "bad_epoch_deletion_for_metric": False,
        "numerical_performance_claim": False,
        "not_for_performance_claim": True,
    }
    _write_json(out / "GUARDED_FORMULA_FIX_AUDIT_REPORT.json", audit_report)
    _write_json(out / "N4H4D3_DECISION_REPORT.json", decision)
    _write_json(out / "N4H4D3_GUARDED_FORMULA_FIX_REPORT.json", report)
    _write_markdown(out / "n4h4d3_guarded_formula_fix.md", report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--clean-root", default=str(default_clean_root()))
    parser.add_argument("--dual-root", default=str(default_dual_root()))
    parser.add_argument("--d2-root", default=str(default_d2_root()))
    parser.add_argument("--output-dir", default=str(default_output_root()))
    parser.add_argument("--build-dir", default="build/cpp")
    parser.add_argument("--exe", default="./build/cpp/legsa_v23_core_demo")
    parser.add_argument("--allow-run", action="store_true")
    args = parser.parse_args()
    report = run(args)
    print(
        json.dumps(
            {
                "audit": report["audit_report"],
                "summary": report["replay_report"].get("summary"),
                "comparison": report["replay_report"].get("comparison_report"),
                "decision": report["decision"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
