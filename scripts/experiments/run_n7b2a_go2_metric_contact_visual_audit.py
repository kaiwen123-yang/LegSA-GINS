#!/usr/bin/env python3
"""Run N7B2A Go2 metric namespace/contact physical sanity audit.

中文说明：真实路径只来自命令行参数；本 runner 只读取 runtime reports 并输出
审计报告/图，不修改 solver output，不启用 Go2 velocity/yaw prior，不实现 FGO。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from legsa_gins.go2_prior.go2_attitude_prior_std_review import write_go2_attitude_prior_std_policy_review
from legsa_gins.go2_prior.go2_contact_v2_physical_sanity import read_csv_rows, write_contact_v2_physical_sanity_report
from legsa_gins.go2_prior.go2_metric_namespace_guard import write_metric_namespace_guard_report
from legsa_gins.go2_prior.go2_n7b2a_decision import make_n7b2a_decision, write_n7b2a_decision
from legsa_gins.go2_prior.go2_n7b2a_visual_plots import generate_n7b2a_visual_plots


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--n7a-root", required=True)
    parser.add_argument("--n7b-root", required=True)
    parser.add_argument("--n7b2-root", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--figure-output-dir", default="")
    parser.add_argument("--allow-run", action="store_true")
    return parser.parse_args(argv)


def _read_json(path: str | Path) -> dict[str, Any]:
    source = Path(path)
    if not source.exists():
        return {}
    try:
        loaded = json.loads(source.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return loaded if isinstance(loaded, dict) else {}


def _write_json(path: str | Path, data: dict[str, Any]) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _load_n7a_reports(root: Path) -> dict[str, dict[str, Any]]:
    return {
        "weak_prior_build": _read_json(root / "GO2_WEAK_PRIOR_BUILD_REPORT.json"),
        "quaternion_rpy": _read_json(root / "GO2_QUATERNION_RPY_CHECK_REPORT.json"),
        "comparison": _read_json(root / "N7A_GO2_WEAK_PRIOR_COMPARISON_REPORT.json"),
        "decision": _read_json(root / "N7A_GO2_WEAK_PRIOR_DECISION_REPORT.json"),
        "run": _read_json(root / "N7A_GO2_WEAK_PRIOR_RUN_REPORT.json"),
    }


def _load_n7b_reports(root: Path) -> dict[str, dict[str, Any]]:
    return {
        "contact": _read_json(root / "GO2_CONTACT_STATE_REPORT.json"),
        "velocity": _read_json(root / "GO2_VELOCITY_QUALITY_REPORT.json"),
        "motion": _read_json(root / "GO2_MOTION_STATE_REPORT.json"),
        "yaw_rate": _read_json(root / "GO2_YAW_RATE_READINESS_REPORT.json"),
        "decision": _read_json(root / "N7B_GO2_VELOCITY_CONTACT_DECISION_REPORT.json"),
    }


def _load_n7b2_reports(root: Path) -> dict[str, dict[str, Any]]:
    return {
        "distribution": _read_json(root / "GO2_CONTACT_DISTRIBUTION_REPORT.json"),
        "contact_v2": _read_json(root / "GO2_CONTACT_STATE_V2_REPORT.json"),
        "smoothing": _read_json(root / "GO2_CONTACT_SMOOTHING_REPORT.json"),
        "velocity_segments": _read_json(root / "GO2_CONTACT_VELOCITY_SEGMENT_REVIEW.json"),
        "decision": _read_json(root / "N7B2_GO2_CONTACT_THRESHOLD_DECISION_REPORT.json"),
        "figure_manifest": _read_json(root / "N7B2_FIGURE_MANIFEST.json"),
    }


def _write_case_review(path: str | Path, reports: dict[str, dict[str, Any]], decision: dict[str, Any]) -> None:
    contact = reports["contact_physical"]
    metric = reports["metric_namespace"]
    attitude = reports["attitude_std"]
    lines = [
        "# N7B2A Go2 metric namespace and contact sanity audit",
        "",
        "This report is review-only engineering evidence.",
        "",
        f"- current_roll_pitch_std_deg: {attitude.get('current_roll_pitch_std_deg')}",
        f"- is_gate_or_threshold: {attitude.get('is_gate_or_threshold')}",
        f"- is_measurement_std: {attitude.get('is_measurement_std')}",
        f"- metric_namespace_missing: {metric.get('metric_namespace_missing')}",
        f"- all_contact_suspect: {contact.get('all_contact_suspect')}",
        f"- contact_too_permissive: {contact.get('contact_too_permissive')}",
        f"- alternating_contact_ratio: {contact.get('alternating_contact_ratio')}",
        f"- physical_plausibility_status: {contact.get('physical_plausibility_status')}",
        f"- decision_status: {decision.get('status')}",
        f"- recommended_next_stage: {decision.get('recommended_next_stage')}",
        "- N7B2A does not activate Go2 velocity/yaw priors.",
        "- N7B2A does not treat Go2 position or velocity as truth.",
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
        raise SystemExit("--allow-run is required for N7B2A runtime execution")
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    n7a_root = Path(args.n7a_root)
    n7b_root = Path(args.n7b_root)
    n7b2_root = Path(args.n7b2_root)
    n7a_reports = _load_n7a_reports(n7a_root)
    n7b_reports = _load_n7b_reports(n7b_root)
    n7b2_reports = _load_n7b2_reports(n7b2_root)
    contact_v2_rows = read_csv_rows(n7b2_root / "GO2_CONTACT_STATE_V2_TIMESERIES.csv")

    _attitude_path, attitude_report = write_go2_attitude_prior_std_policy_review(n7a_reports, out)
    _metric_path, metric_report = write_metric_namespace_guard_report(
        n7a_reports=n7a_reports,
        n7b_reports=n7b_reports,
        n7b2_reports=n7b2_reports,
        output_dir=out,
    )
    _contact_path, contact_report = write_contact_v2_physical_sanity_report(
        contact_v2_rows,
        distribution_report=n7b2_reports["distribution"],
        velocity_segment_report=n7b2_reports["velocity_segments"],
        output_dir=out,
    )
    decision = make_n7b2a_decision(
        attitude_std_report=attitude_report,
        metric_namespace_report=metric_report,
        contact_physical_report=contact_report,
    )
    write_n7b2a_decision(decision, out / "N7B2A_GO2_METRIC_CONTACT_DECISION_REPORT.json")
    figure_manifest: dict[str, Any] = {"required_figures_generated": False, "paper_performance_claim": False}
    if args.figure_output_dir:
        figure_manifest = generate_n7b2a_visual_plots(
            figure_output_dir=args.figure_output_dir,
            output_dir=out,
            contact_v2_rows=contact_v2_rows,
            attitude_std_report=attitude_report,
            metric_namespace_report=metric_report,
            contact_physical_report=contact_report,
            decision=decision,
        )
    reports = {
        "attitude_std": attitude_report,
        "metric_namespace": metric_report,
        "contact_physical": contact_report,
    }
    _write_case_review(out / "n7b2a_metric_contact_case_review.md", reports, decision)
    run_report = {
        "stage": "N7B2A_go2_metric_contact_visual_audit",
        "input_roles": {
            "n7a_root": "N7A_go2_body_state_runtime_report_root",
            "n7b_root": "N7B_velocity_contact_runtime_report_root",
            "n7b2_root": "N7B2_contact_threshold_runtime_report_root",
        },
        "reports": reports,
        "decision": decision,
        "figure_manifest": figure_manifest,
        "paper_performance_claim": False,
        "go2_position_truth_claim": False,
        "go2_velocity_truth_claim": False,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "go2_velocity_prior_enabled": False,
        "go2_yaw_prior_enabled": False,
        "output_only_correction": False,
        "bad_epoch_deletion_for_metric": False,
        "fgo": False,
    }
    _write_json(out / "N7B2A_GO2_METRIC_CONTACT_RUN_REPORT.json", run_report)
    print(json.dumps({"reports": reports, "decision": decision}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
