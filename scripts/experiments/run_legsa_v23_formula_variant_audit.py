#!/usr/bin/env python3
"""Run N4H4D2 formula parity and diagnostic variant audit.

中文说明：本脚本只做公式审计和 diagnostic variants，不永久修复 solver、
不调参、不删 epoch、不做 output-only correction，也不形成 performance claim。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from legsa_gins.evaluation.legsa_v23_clean_replay_runner import (  # noqa: E402
    default_clean_root,
    default_dual_root,
    locate_clean_inputs,
)
from legsa_gins.evaluation.legsa_v23_formula_parity_audit import build_formula_parity_report  # noqa: E402
from legsa_gins.evaluation.legsa_v23_mechanization_sanity import build_mechanization_sanity_report  # noqa: E402
from legsa_gins.evaluation.legsa_v23_runtime_debug_trace import load_debug_bundle, read_json  # noqa: E402
from legsa_gins.evaluation.legsa_v23_update_feedback_variant_matrix import run_variant_matrix  # noqa: E402
from legsa_gins.evaluation.legsa_v23_variant_decision import classify_d2_decision  # noqa: E402


def default_d1_root() -> Path:
    return Path.home() / "legsa_n4h4d1_diagnostics"


def default_output_root() -> Path:
    return Path.home() / "legsa_n4h4d2_formula_variants"


def default_external_root() -> Path:
    return Path.home() / "KF-GINS"


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _load_d1_reports(d1_root: str | Path) -> dict[str, Any]:
    root = Path(d1_root)
    residual = read_json(root / "UPDATE_RESIDUAL_DIAGNOSTICS_REPORT.json")
    decision = read_json(root / "N4H4D1_FAILURE_DECISION_REPORT.json")
    return {
        "residual": residual,
        "decision": decision,
        "yaw_reject_ratio": residual.get("yaw_reject_ratio", 0.0),
    }


def _write_markdown(path: Path, report: dict[str, Any]) -> None:
    formula = report.get("formula_report", {})
    mech = report.get("mechanization_report", {})
    matrix = report.get("variant_matrix", {})
    decision = report.get("decision", {})
    lines = [
        "# N4H4D2 Formula Variant Audit",
        "",
        "N4H4D2 audits formula parity and runs diagnostic-only update/feedback variants.",
        "",
        "No permanent solver fix is applied here. Variant outputs are not performance results.",
        "",
        "## Formula Candidates",
        f"- formula_mismatch_candidates: {formula.get('formula_mismatch_candidates')}",
        f"- evidence_missing: {formula.get('evidence_missing')}",
        "",
        "## Mechanization Sanity",
        f"- immediate_gravity_or_frame_issue: {mech.get('immediate_gravity_or_frame_issue')}",
        f"- long_free_ins_drift_only: {mech.get('long_free_ins_drift_only')}",
        "",
        "## Variant Matrix",
        f"- best_candidate_variant: {matrix.get('best_candidate_variant')}",
        f"- candidate_fix_detected: {matrix.get('candidate_fix_detected')}",
        f"- multi_issue_or_coupled_issue: {matrix.get('multi_issue_or_coupled_issue')}",
        "",
        "## Decision",
        f"- most_likely_issue: {decision.get('most_likely_issue')}",
        f"- secondary_issues: {decision.get('secondary_issues')}",
        f"- recommended_next_stage: {decision.get('recommended_next_stage')}",
        "",
        "All JSON/CSV outputs under the D2 runtime directory are runtime-only artifacts and must not be committed.",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def run(args: argparse.Namespace) -> dict[str, Any]:
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    formula_report = build_formula_parity_report(args.reference_root, args.external_source_root, REPO_ROOT)
    d1_debug_dir = Path(args.d1_root) / "current" / "debug"
    debug_bundle = load_debug_bundle(d1_debug_dir)
    located = locate_clean_inputs(args.clean_root)
    imu_path = located.get("imu_path")
    mech_report = build_mechanization_sanity_report(
        imu_path,
        debug_bundle.get("input_snapshot", {}),
        d1_debug_dir / "FIRST_PROPAGATIONS.csv",
    )
    if args.run_variant_matrix:
        variant_matrix = run_variant_matrix(
            args.clean_root,
            args.dual_root,
            out / "variants",
            args.exe,
            allow_run=args.allow_run,
        )
    else:
        variant_matrix = {
            "phase": "N4H4D2",
            "variant_summaries": {},
            "candidate_fix_detected": False,
            "best_candidate_variant": "not_run_without_run_variant_matrix",
            "multi_issue_or_coupled_issue": False,
            "diagnostic_only": True,
            "not_for_performance_claim": True,
            "trace_solver_input": False,
            "final_v23_output_substitution": False,
            "output_only_correction": False,
            "bad_epoch_deletion_for_metric": False,
            "numerical_performance_claim": False,
        }
    d1_reports = _load_d1_reports(args.d1_root)
    decision = classify_d2_decision(formula_report, mech_report, variant_matrix, d1_reports)
    report = {
        "phase": "N4H4D2",
        "formula_report": formula_report,
        "mechanization_report": mech_report,
        "variant_matrix": variant_matrix,
        "d1_reports": d1_reports,
        "decision": decision,
        "diagnostic_only": True,
        "not_for_performance_claim": True,
        "trace_solver_input": False,
        "final_v23_output_substitution": False,
        "output_only_correction": False,
        "bad_epoch_deletion_for_metric": False,
        "numerical_performance_claim": False,
    }
    _write_json(out / "FORMULA_PARITY_AUDIT_REPORT.json", formula_report)
    _write_json(out / "MECHANIZATION_SANITY_REPORT.json", mech_report)
    _write_json(out / "UPDATE_FEEDBACK_VARIANT_MATRIX_REPORT.json", variant_matrix)
    _write_json(out / "N4H4D2_DECISION_REPORT.json", decision)
    _write_json(out / "N4H4D2_FORMULA_VARIANT_AUDIT_REPORT.json", report)
    _write_markdown(out / "n4h4d2_formula_variant_audit.md", report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--clean-root", default=str(default_clean_root()))
    parser.add_argument("--dual-root", default=str(default_dual_root()))
    parser.add_argument("--d1-root", default=str(default_d1_root()))
    parser.add_argument("--external-source-root", default=str(default_external_root()))
    parser.add_argument("--reference-root", default="reference/final_v23_repo")
    parser.add_argument("--output-dir", default=str(default_output_root()))
    parser.add_argument("--build-dir", default="build/cpp")
    parser.add_argument("--exe", default="./build/cpp/legsa_v23_core_demo")
    parser.add_argument("--allow-run", action="store_true")
    parser.add_argument("--run-variant-matrix", action="store_true")
    args = parser.parse_args()
    report = run(args)
    print(
        json.dumps(
            {
                "formula_candidates": report["formula_report"].get("formula_mismatch_candidates"),
                "mechanization": report["mechanization_report"],
                "variant_decision": {
                    "best_candidate_variant": report["variant_matrix"].get("best_candidate_variant"),
                    "candidate_fix_detected": report["variant_matrix"].get("candidate_fix_detected"),
                    "multi_issue_or_coupled_issue": report["variant_matrix"].get("multi_issue_or_coupled_issue"),
                },
                "decision": report["decision"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
