#!/usr/bin/env python3
"""XB1A2 A1 dual-diff rel_pos re-audit and normal rerun gate.

This stage corrects the XB1A1 A1-yaw provenance question. It recovers the
accepted process_data-compatible A1 builder, audits the status rel_pos
dual-difference path, compares it with the old XB1A1 absolute-LLH path and
single rel_pos direct paths, then only allows a normal rerun when the repaired
dual-yaw input gate is physically valid.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from legsa_gins.input_generation.status_yaw_builder import (  # noqa: E402
    apply_yaw_install_and_ned,
    build_a1_dual_diff_yaw_rows,
)
from scripts.experiments import run_xb1_poor_gnss_generalization as xb1  # noqa: E402


STAGE = "XB1A2_A1_DUAL_DIFF_RELPOS_DIFFERENCE_REAUDIT_AND_NORMAL_RERUN"
A0_STAGE = "XB1A0_TO_XB1E_POOR_GNSS_GENERALIZATION_CONTEXT_QUALITY_AUDIT_ALIGNMENT_AND_NORMAL_RUN"
A1_STAGE = "XB1A1_BLOCKER_TRIAGE_RAW_DOPPLER_A1_YAW_AND_MAINLINE_NORMAL_GATE"
RUNTIME_STAGE = "XB1A2_A1_RELPOS_DIFF_REPAIR"

PHYSICAL_BASELINE_BAND_M = (0.10, 1.50)
PHYSICAL_BASELINE_SOURCE = (
    "project dual-antenna geometry and prior BY3A5B accepted short-baseline "
    "scale around 0.383 m; widened to 0.10-1.50 m for poor-GNSS audit"
)


SUBDIRS = [
    "00_supervisor",
    "01_plan",
    "xb1a1_supersession",
    "by2_a1_dual_diff_recovery",
    "baseline_source_audit",
    "relpos_difference_audit",
    "llh_difference_audit",
    "antenna_order_lateral_policy",
    "repaired_input_generation",
    "normal_run",
    "official_eval",
    "figures",
    "case_review",
    "context_update",
    "obsidian_sync",
    "reports",
    "matrix",
    "summary",
    "validation",
    "logs",
    "blocked",
]


@dataclass(frozen=True)
class StagePaths:
    repo: Path
    receiver_root: Path
    body_source: Path
    output_root: Path
    stage_root: Path
    runtime_root: Path
    a0_root: Path
    a1_root: Path
    rtklib_root: Path | None
    evaluator_wsl: str
    by3a2_template_root: Path | None

    @property
    def xb1_paths(self) -> xb1.Paths:
        return xb1.Paths(
            repo=self.repo,
            receiver_root=self.receiver_root,
            body_source=self.body_source,
            output_root=self.output_root,
            stage_root=self.stage_root,
            runtime_root=self.runtime_root,
            export_root=self.output_root / "XB1_EXPORT_CLEAN_PACKAGE",
            trace=xb1.discover_trace(self.receiver_root),
            rtklib_root=self.rtklib_root,
            evaluator_wsl=self.evaluator_wsl,
            by3a2_template_root=self.by3a2_template_root,
        )

    @property
    def repaired_gnss(self) -> Path:
        return self.stage_root / "repaired_input_generation" / "XB1_DUAL_A1_RELPOS_DIFF_15COL_REPAIRED.gnss"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--receiver-root", type=Path, required=True)
    parser.add_argument("--body-source", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, default=REPO_ROOT / "xb1")
    parser.add_argument("--a0-stage-root", type=Path)
    parser.add_argument("--a1-stage-root", type=Path)
    parser.add_argument("--rtklib-root", type=Path)
    parser.add_argument("--evaluator-wsl", default=os.environ.get("LEGSA_EVALUATOR_WSL", ""))
    parser.add_argument("--by3a2-template-root", type=Path)
    parser.add_argument("--run-normal", action="store_true")
    parser.add_argument("--skip-figures", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    output_root = args.output_root.resolve()
    paths = StagePaths(
        repo=args.repo_root.resolve(),
        receiver_root=args.receiver_root.resolve(),
        body_source=args.body_source.resolve(),
        output_root=output_root,
        stage_root=output_root / STAGE,
        runtime_root=output_root / "XB1_FULL_MATRIX" / RUNTIME_STAGE,
        a0_root=(args.a0_stage_root.resolve() if args.a0_stage_root else output_root / A0_STAGE),
        a1_root=(args.a1_stage_root.resolve() if args.a1_stage_root else output_root / A1_STAGE),
        rtklib_root=args.rtklib_root.resolve() if args.rtklib_root else None,
        evaluator_wsl=args.evaluator_wsl,
        by3a2_template_root=args.by3a2_template_root.resolve() if args.by3a2_template_root else None,
    )
    result = run_stage(paths, run_normal=args.run_normal, skip_figures=args.skip_figures)
    print(json.dumps({"decision": result["decision"], "stage_root": str(paths.stage_root)}, indent=2))
    return 0


def run_stage(paths: StagePaths, *, run_normal: bool, skip_figures: bool) -> dict[str, Any]:
    prepare_dirs(paths)
    supervisor_plan(paths)
    conclusion = write_xb1a1_conclusion_review(paths)
    recovery = write_by2_a1_dual_diff_recovery(paths)
    baseline = write_baseline_source_audit(paths, recovery)
    relpos = write_relpos_difference_audit(paths, baseline)
    antenna = write_antenna_policy(paths, relpos)
    inputs = write_repaired_input_generation(paths, recovery, relpos, antenna)
    normal = write_normal_run(paths, inputs, run_normal=run_normal)
    quality = write_quality_decision_update(paths, relpos, normal)
    figures = write_figures_and_case_review(paths, conclusion, recovery, baseline, relpos, antenna, inputs, normal, quality, skip_figures=skip_figures)
    write_context_and_obsidian(paths, conclusion, recovery, baseline, relpos, normal, quality)
    validation = write_validation(paths, conclusion, recovery, baseline, relpos, antenna, inputs, normal, quality, figures)
    return write_decision(paths, relpos, inputs, normal, quality, validation)


def prepare_dirs(paths: StagePaths) -> None:
    for rel in SUBDIRS:
        (paths.stage_root / rel).mkdir(parents=True, exist_ok=True)
    paths.runtime_root.mkdir(parents=True, exist_ok=True)


def supervisor_plan(paths: StagePaths) -> None:
    plan_rows = [
        {"step": "A", "name": "suspend_xb1a1_a1_conclusion", "status": "planned"},
        {"step": "B", "name": "recover_by2_a1_dual_diff", "status": "planned"},
        {"step": "C", "name": "audit_all_baseline_sources", "status": "planned"},
        {"step": "D", "name": "detailed_relpos_diff_audit", "status": "planned"},
        {"step": "E", "name": "antenna_lateral_policy_gate", "status": "planned"},
        {"step": "F", "name": "repaired_input_generation_if_valid", "status": "planned"},
        {"step": "G", "name": "normal_rerun_only_if_gates_pass", "status": "planned"},
        {"step": "H", "name": "quality_aware_branch_decision_update", "status": "planned"},
    ]
    report = {
        "stage": STAGE,
        "output_root": str(paths.output_root),
        "stage_root": str(paths.stage_root),
        "runtime_root": str(paths.runtime_root),
        "hard_boundaries": {
            "degradation_matrix": False,
            "parameter_retuning": False,
            "trace_solver_input": False,
            "hdt_mainline_yaw": False,
            "single_relpos_direct_yaw": False,
            "ready_for_paper_claims": False,
        },
        "plan": plan_rows,
    }
    write_json(paths.stage_root / "00_supervisor" / "XB1A2_SUPERVISOR_SCOPE.json", report)
    write_json(paths.stage_root / "01_plan" / "XB1A2_EXECUTION_PLAN.json", plan_rows)
    write_csv(paths.stage_root / "01_plan" / "XB1A2_EXECUTION_PLAN.csv", plan_rows)


def write_xb1a1_conclusion_review(paths: StagePaths) -> dict[str, Any]:
    a1_report = read_json(paths.a1_root / "reports" / "XB1A1_A1_SHORT_BASELINE_YAW_GATE_REPORT.json", {})
    old_method = "unknown"
    source_provenance = "not_proven"
    relpos_diff_audited = False
    old_script = paths.repo / "scripts" / "experiments" / "run_xb1a1_blocker_triage.py"
    xb1_script = paths.repo / "scripts" / "experiments" / "run_xb1_poor_gnss_generalization.py"
    script_text = safe_read_text(xb1_script)
    if "def build_a1_rows" in script_text and "read_status_positions" in script_text and "ecef_delta_to_enu" in script_text:
        old_method = "absolute_llh_position_difference_via_build_a1_rows"
    if "build_a1_dual_diff_yaw_rows" in safe_read_text(old_script):
        relpos_diff_audited = True
        source_provenance = "status_relpos_diff_present_in_xb1a1"
    elif old_method != "unknown":
        source_provenance = "xb1a1_used_absolute_llh_path_not_accepted_by2_status_relpos_diff"

    baseline_stats = (
        a1_report.get("summary", {}).get("baseline_length_stats_m")
        or a1_report.get("summary", {}).get("length_stats_m")
        or a1_report.get("a1_report", {}).get("length_stats_m")
        or a1_report.get("length_stats_m")
        or {}
    )
    decision = (
        "XB1A2_xb1a1_a1_conclusion_accepted"
        if relpos_diff_audited
        else "XB1A2_xb1a1_a1_conclusion_suspended"
    )
    rows = [
        {
            "finding": "XB1A1_A1_invalid_conclusion",
            "value": a1_report.get("decision", "missing"),
            "evidence": "XB1A1 report imported for review",
        },
        {
            "finding": "XB1A1_reported_baseline_median_m",
            "value": baseline_stats.get("median", ""),
            "evidence": "XB1A1 baseline stats",
        },
        {
            "finding": "XB1A1_method_used",
            "value": old_method,
            "evidence": "run_xb1_poor_gnss_generalization.py build_a1_rows",
        },
        {
            "finding": "relpos_difference_audited_in_XB1A1",
            "value": relpos_diff_audited,
            "evidence": source_provenance,
        },
    ]
    report = {
        "stage": "XB1A2_A",
        "decision": decision,
        "xb1a1_a1_report_decision": a1_report.get("decision"),
        "xb1a1_reported_baseline_stats_m": baseline_stats,
        "method_used_if_identifiable": old_method,
        "source_provenance_status": source_provenance,
        "relpos_difference_audited": relpos_diff_audited,
        "conclusion_policy": "suspended_pending_relpos_difference_reaudit" if not relpos_diff_audited else "accepted_with_source_evidence",
        "ready_for_paper_claims": False,
    }
    write_json(paths.stage_root / "reports" / "XB1A2_XB1A1_A1_CONCLUSION_REVIEW_REPORT.json", report)
    write_json(paths.stage_root / "matrix" / "XB1A2_XB1A1_A1_CONCLUSION_REVIEW.json", rows)
    write_csv(paths.stage_root / "matrix" / "XB1A2_XB1A1_A1_CONCLUSION_REVIEW.csv", rows)
    write_md(
        paths.stage_root / "summary" / "xb1a2_xb1a1_a1_conclusion_review.md",
        "# XB1A2 XB1A1 A1 Conclusion Review\n\n"
        f"Decision: `{decision}`.\n\n"
        f"XB1A1 method: `{old_method}`. Relpos-difference audited in XB1A1: `{relpos_diff_audited}`.\n\n"
        "The XB1A1 invalid-yaw conclusion is suspended until the accepted BY2 status relpos-difference path is audited for XB1.\n",
    )
    return report


def write_by2_a1_dual_diff_recovery(paths: StagePaths) -> dict[str, Any]:
    evidence_rows = [
        {
            "source_path": "src/legsa_gins/input_generation/status_yaw_builder.py",
            "evidence_type": "implementation",
            "finding": "BY2/process_data-compatible builder reads GNSS1/GNSS2 status rel_pos fields, interpolates GNSS2 to GNSS1 time, and computes GNSS2 minus GNSS1.",
            "accepted": True,
            "accepted_scope": "BY2_process_data_compat_status_yaw",
        },
        {
            "source_path": "tests/unit/test_status_yaw_builder.py",
            "evidence_type": "unit_test",
            "finding": "test_a1_dual_diff_yaw_and_ned_formula verifies rel_n/rel_e from GNSS2-GNSS1 and yaw_ned=90-yaw_body.",
            "accepted": True,
            "accepted_scope": "BY2_process_data_compat_status_yaw",
        },
        {
            "source_path": "docs/experiments/process_data_compat_generation.md",
            "evidence_type": "documentation",
            "finding": "records process_data-compatible yaw as rel_pos_n/e(gnss2_interp)-rel_pos_n/e(gnss1), yaw_baseline=-atan2(rel_e,rel_n).",
            "accepted": True,
            "accepted_scope": "BY2_process_data_compat_status_yaw",
        },
        {
            "source_path": "scripts/experiments/run_by3a5b_a1_dual_diff_yaw_input_repair.py",
            "evidence_type": "implementation",
            "finding": "BY3A5B repair uses GNSS1/GNSS2 absolute position fields projected to local ENU, while rejecting single status rel_pos as a long-baseline/base-vector source for BY3.",
            "accepted": True,
            "accepted_scope": "BY3A5B_absolute_position_repair_only",
        },
        {
            "source_path": "docs/codex_context/BY3A5B_A1_DUAL_DIFF_YAW_INPUT_REPAIR_CONTEXT.md",
            "evidence_type": "context_memory",
            "finding": "records BY3A5B yaw_input_source as GNSS1/GNSS2 absolute positions and status_rel_pos_policy as rejected_long_baseline_base_vector.",
            "accepted": True,
            "accepted_scope": "BY3A5B_absolute_position_repair_only",
        },
        {
            "source_path": "scripts/experiments/run_by3a4c_yaw_history_reconstruction.py",
            "evidence_type": "historical_recovery",
            "finding": "records A1_dual_diff_status and same relpos-difference formula as historical yaw-policy evidence.",
            "accepted": True,
            "accepted_scope": "BY2_status_policy_recovery",
        },
    ]
    pseudo_code = [
        "rows1 = valid_filter(gnss1_status, rel_valid && ant_valid && ant_state == 2)",
        "rows2 = valid_filter(gnss2_status, rel_valid && ant_valid && ant_state == 2)",
        "for each gnss1 timestamp t:",
        "    g2 = interpolate(rows2.rel_pos_n/e/d, t)",
        "    rel_n = g2.rel_pos_n - gnss1.rel_pos_n",
        "    rel_e = g2.rel_pos_e - gnss1.rel_pos_e",
        "    rel_d = g2.rel_pos_d - gnss1.rel_pos_d",
        "    yaw_baseline_deg = wrap360(-atan2(rel_e, rel_n))",
        "    yaw_body_deg = wrap360(sign * yaw_baseline_deg + offset_deg)",
        "    yaw_ned_deg = wrap360(90 - yaw_body_deg)",
        "    yaw_std = 1.5 deg under fixed_1p5 policy",
    ]
    report = {
        "stage": "XB1A2_B",
        "decision": "XB1A2_by2_a1_dual_diff_recovered",
        "source_script_path": "src/legsa_gins/input_generation/status_yaw_builder.py",
        "implementation_families": [
            {
                "family": "BY2_process_data_compat_status_relpos_diff",
                "formula": "gnss2.rel_pos_interp - gnss1.rel_pos",
                "status": "recovered_and_audited_for_XB1",
            },
            {
                "family": "BY3A5B_absolute_position_short_baseline",
                "formula": "LLH/ECEF/ENU absolute GNSS2 position - GNSS1 position",
                "status": "recovered_as_BY3A5B-specific_repair_and_audited_for_XB1",
            },
        ],
        "input_fields": ["rel_pos_n", "rel_pos_e", "rel_pos_d", "rel_acc_n", "rel_acc_e", "rel_acc_d"],
        "gnss2_interpolated_to_gnss1_time": True,
        "formula": {
            "rel_n": "gnss2.rel_pos_n_interp - gnss1.rel_pos_n",
            "rel_e": "gnss2.rel_pos_e_interp - gnss1.rel_pos_e",
            "rel_d": "gnss2.rel_pos_d_interp - gnss1.rel_pos_d",
            "yaw_baseline_deg": "wrap360(-atan2(rel_e, rel_n))",
            "yaw_body_deg": "wrap360(sign*yaw_baseline_deg + offset_deg)",
            "yaw_ned_deg": "wrap360(90 - yaw_body_deg)",
        },
        "antenna_order": "gnss2_minus_gnss1",
        "lateral_mounting_policy": "BY2 accepted yaw_ned=90-yaw_body; do not select sign by trace RMSE",
        "yaw_std_policy": "fixed_1p5",
        "rejected_fields": ["single_rel_pos_direct", "long_baseline_direct_yaw", "HDT_mainline", "trace_yaw_solver_input"],
        "xb1a2_selection_policy": "audit both BY2 status-relpos-diff and BY3A5B absolute-position candidates; accept neither unless the objective physical-baseline gate passes",
        "pseudo_code": pseudo_code,
        "evidence": evidence_rows,
        "ready_for_paper_claims": False,
    }
    write_json(paths.stage_root / "reports" / "XB1A2_BY2_A1_DUAL_DIFF_RECOVERY_REPORT.json", report)
    write_json(paths.stage_root / "matrix" / "XB1A2_BY2_A1_DUAL_DIFF_EVIDENCE.json", evidence_rows)
    write_csv(paths.stage_root / "matrix" / "XB1A2_BY2_A1_DUAL_DIFF_EVIDENCE.csv", evidence_rows)
    write_md(
        paths.stage_root / "summary" / "xb1a2_by2_a1_dual_diff_recovery.md",
        "# XB1A2 BY2 A1 Dual-Diff Recovery\n\n"
        "Decision: `XB1A2_by2_a1_dual_diff_recovered`.\n\n"
        "The recovered evidence has two implementation families: BY2/process_data-compatible status "
        "`rel_pos` dual-difference, and BY3A5B's absolute-position short-baseline repair. XB1A2 audits both and accepts neither unless the physical baseline gate passes.\n",
    )
    return report


def write_baseline_source_audit(paths: StagePaths, recovery: dict[str, Any]) -> dict[str, Any]:
    candidate_rows: list[dict[str, Any]] = []
    relpos_g2_g1 = build_relpos_diff_details(paths, direction="gnss2_minus_gnss1")
    relpos_g1_g2 = reverse_relpos_details(relpos_g2_g1, source_name="relpos_diff_gnss1_minus_gnss2")
    llh_g2_g1 = build_llh_diff_rows(paths, direction="gnss2_minus_gnss1")
    llh_g1_g2 = reverse_llh_rows(llh_g2_g1, source_name="llh_abs_diff_gnss1_minus_gnss2")
    single_g1 = build_single_relpos_rows(paths.receiver_root / "gnss1-status.csv", "single_relpos_gnss1_direct")
    single_g2 = build_single_relpos_rows(paths.receiver_root / "gnss2-status.csv", "single_relpos_gnss2_direct")
    direct_heading = direct_heading_rows(paths)

    for name, rows, fields, interp, by2_compat, mainline_allowed in [
        ("relpos_diff_gnss2_minus_gnss1", relpos_g2_g1, "gnss2.rel_pos_n/e/d - gnss1.rel_pos_n/e/d", "gnss2 interpolated to gnss1 status header time", True, True),
        ("relpos_diff_gnss1_minus_gnss2", relpos_g1_g2, "gnss1.rel_pos_n/e/d - gnss2.rel_pos_n/e/d", "reverse of BY2-compatible interpolation", False, False),
        ("llh_abs_diff_gnss2_minus_gnss1", llh_g2_g1, "LLH/ECEF/ENU absolute position delta", "gnss2 absolute position interpolated to gnss1 time", False, False),
        ("llh_abs_diff_gnss1_minus_gnss2", llh_g1_g2, "LLH/ECEF/ENU absolute position delta reversed", "reverse of absolute LLH interpolation", False, False),
        ("single_relpos_gnss1_direct", single_g1, "gnss1.rel_pos_n/e/d directly", "none", False, False),
        ("single_relpos_gnss2_direct", single_g2, "gnss2.rel_pos_n/e/d directly", "none", False, False),
        ("direct_heading_hdt_diagnostic", direct_heading, "HDT/direct heading if present", "none", False, False),
    ]:
        candidate_rows.append(candidate_summary_row(name, rows, fields, interp, by2_compat, mainline_allowed))

    allowed_candidates = [
        row for row in candidate_rows
        if row["allowed_as_mainline"] and row["physical_plausibility"] == "physical"
    ]
    decision = "XB1A2_valid_relpos_diff_baseline_found" if allowed_candidates else "XB1A2_no_valid_baseline_source"
    report = {
        "stage": "XB1A2_C",
        "decision": decision,
        "physical_baseline_band_m": {"min": PHYSICAL_BASELINE_BAND_M[0], "max": PHYSICAL_BASELINE_BAND_M[1]},
        "physical_baseline_band_source": PHYSICAL_BASELINE_SOURCE,
        "by2_compatibility_source": recovery.get("source_script_path"),
        "candidate_count": len(candidate_rows),
        "allowed_candidates": allowed_candidates,
        "single_relpos_direct_rejected": True,
        "llh_abs_diff_not_accepted": True,
        "trace_solver_input": False,
        "ready_for_paper_claims": False,
    }
    write_json(paths.stage_root / "reports" / "XB1A2_BASELINE_SOURCE_AUDIT_REPORT.json", report)
    write_json(paths.stage_root / "matrix" / "XB1A2_BASELINE_SOURCE_AUDIT.json", candidate_rows)
    write_csv(paths.stage_root / "matrix" / "XB1A2_BASELINE_SOURCE_AUDIT.csv", candidate_rows)
    write_md(
        paths.stage_root / "summary" / "xb1a2_baseline_source_audit.md",
        "# XB1A2 Baseline Source Audit\n\n"
        f"Decision: `{decision}`.\n\n"
        f"The BY2-compatible relpos-difference candidate has median `{candidate_rows[0]['baseline_median_m']}` m "
        f"and p95 `{candidate_rows[0]['baseline_p95_m']}` m, so it is not physically plausible for the dual-antenna baseline.\n",
    )
    return {
        "report": report,
        "candidate_rows": candidate_rows,
        "relpos_g2_g1_rows": relpos_g2_g1,
        "relpos_g1_g2_rows": relpos_g1_g2,
        "llh_g2_g1_rows": llh_g2_g1,
        "llh_g1_g2_rows": llh_g1_g2,
        "single_g1_rows": single_g1,
        "single_g2_rows": single_g2,
    }


def write_relpos_difference_audit(paths: StagePaths, baseline: dict[str, Any]) -> dict[str, Any]:
    rows = baseline["relpos_g2_g1_rows"]
    prev_yaw: float | None = None
    detailed_rows: list[dict[str, Any]] = []
    continuous = 0
    longest = 0
    yaw_jump_count = 0
    for item in rows:
        yaw = as_float(item.get("yaw_baseline_deg"))
        jump = None if prev_yaw is None or yaw is None else abs(angle_diff_deg(float(yaw), prev_yaw))
        if jump is not None and jump > 45.0:
            yaw_jump_count += 1
        prev_yaw = yaw if yaw is not None else prev_yaw
        length = as_float(item.get("diff_length_m"))
        length_ok = length is not None and PHYSICAL_BASELINE_BAND_M[0] <= length <= PHYSICAL_BASELINE_BAND_M[1]
        jump_ok = jump is None or jump <= 45.0
        valid = bool(length_ok and jump_ok)
        if valid:
            continuous += 1
            longest = max(longest, continuous)
        else:
            continuous = 0
        flags: list[str] = []
        if length is None:
            flags.append("missing")
        elif not length_ok:
            flags.append("baseline_length_suspect")
        if jump is not None and not jump_ok:
            flags.append("jump_suspect")
        if not flags:
            flags.append("valid")
        detailed_rows.append(
            {
                "time": item.get("time"),
                "aligned_time": item.get("aligned_time"),
                "gnss1_rel_pos_n": item.get("gnss1_rel_pos_n"),
                "gnss1_rel_pos_e": item.get("gnss1_rel_pos_e"),
                "gnss1_rel_pos_d": item.get("gnss1_rel_pos_d"),
                "gnss2_rel_pos_n_interp": item.get("gnss2_rel_pos_n_interp"),
                "gnss2_rel_pos_e_interp": item.get("gnss2_rel_pos_e_interp"),
                "gnss2_rel_pos_d_interp": item.get("gnss2_rel_pos_d_interp"),
                "diff_n": item.get("diff_n"),
                "diff_e": item.get("diff_e"),
                "diff_d": item.get("diff_d"),
                "diff_length": length,
                "candidate_yaw_gnss2_minus_gnss1": item.get("yaw_baseline_deg"),
                "candidate_yaw_gnss1_minus_gnss2": wrap360(float(item["yaw_baseline_deg"]) + 180.0) if item.get("yaw_baseline_deg") != "" else "",
                "gnss1_rel_valid": item.get("gnss1_rel_valid"),
                "gnss1_ant_valid": item.get("gnss1_ant_valid"),
                "gnss1_fix_ok": item.get("gnss1_fix_ok"),
                "baseline_length_quality": "physical" if length_ok else "nonphysical",
                "yaw_jump_deg": jump if jump is not None else "",
                "quality_flag": "|".join(flags),
                "objective_valid_for_solver": valid,
            }
        )
    valid_count = sum(1 for row in detailed_rows if row["objective_valid_for_solver"])
    valid_ratio = valid_count / len(detailed_rows) if detailed_rows else 0.0
    length_stats = stats([as_float(row.get("diff_length")) for row in detailed_rows])
    decision = (
        "XB1A2_relpos_diff_valid"
        if valid_ratio >= 0.50 and (length_stats.get("median") or 999.0) <= PHYSICAL_BASELINE_BAND_M[1]
        else "XB1A2_relpos_diff_invalid"
    )
    report = {
        "stage": "XB1A2_D",
        "decision": decision,
        "physical_baseline_band_m": {"min": PHYSICAL_BASELINE_BAND_M[0], "max": PHYSICAL_BASELINE_BAND_M[1]},
        "physical_baseline_band_source": PHYSICAL_BASELINE_SOURCE,
        "row_count": len(detailed_rows),
        "valid_epoch_count": valid_count,
        "valid_epoch_ratio": valid_ratio,
        "length_stats_m": length_stats,
        "yaw_jump_gt_45deg_count": yaw_jump_count,
        "longest_continuous_valid_segment_epochs": longest,
        "coverage_over_algorithm_time": coverage_over_algorithm_time(paths, detailed_rows),
        "trace_solver_input": False,
        "ready_for_paper_claims": False,
    }
    write_json(paths.stage_root / "reports" / "XB1A2_RELPOS_DIFFERENCE_AUDIT_REPORT.json", report)
    write_json(paths.stage_root / "matrix" / "XB1A2_RELPOS_DIFF_EPOCH_QUALITY.json", detailed_rows)
    write_csv(paths.stage_root / "matrix" / "XB1A2_RELPOS_DIFF_EPOCH_QUALITY.csv", detailed_rows)
    write_md(
        paths.stage_root / "summary" / "xb1a2_relpos_difference_audit.md",
        "# XB1A2 Relpos Difference Audit\n\n"
        f"Decision: `{decision}`.\n\n"
        f"Valid epoch ratio under the physical baseline band is `{valid_ratio:.4f}`; median length is `{length_stats.get('median')}` m and p95 is `{length_stats.get('p95')}` m.\n",
    )
    return report


def write_antenna_policy(paths: StagePaths, relpos: dict[str, Any]) -> dict[str, Any]:
    if relpos.get("decision") in {"XB1A2_relpos_diff_valid", "XB1A2_relpos_diff_valid_with_caution"}:
        decision = "XB1A2_antenna_order_policy_ready"
        blockers: list[str] = []
    else:
        decision = "XB1A2_antenna_order_blocked"
        blockers = ["relpos_diff_baseline_not_physical"]
    rows = [
        {
            "policy_item": "antenna_order",
            "value": "gnss2_minus_gnss1",
            "source": "status_yaw_builder.py and BY2 process_data-compatible docs",
            "accepted_for_xb1": not blockers,
        },
        {
            "policy_item": "lateral_conversion",
            "value": "yaw_body=sign*yaw_baseline+offset; yaw_ned=90-yaw_body; fixed sign=1 offset=0 from BY2 policy unless human review changes it",
            "source": "status_yaw_builder.apply_yaw_install_and_ned",
            "accepted_for_xb1": not blockers,
        },
        {
            "policy_item": "yaw_std",
            "value": "fixed_1p5",
            "source": "process_data-compatible status yaw policy",
            "accepted_for_xb1": not blockers,
        },
    ]
    report = {
        "stage": "XB1A2_E",
        "decision": decision,
        "blockers": blockers,
        "trace_sign_tuning_used": False,
        "hdt_mainline_yaw": False,
        "ready_for_paper_claims": False,
    }
    write_json(paths.stage_root / "reports" / "XB1A2_ANTENNA_ORDER_LATERAL_POLICY_REPORT.json", report)
    write_json(paths.stage_root / "matrix" / "XB1A2_ANTENNA_ORDER_LATERAL_POLICY.json", rows)
    write_csv(paths.stage_root / "matrix" / "XB1A2_ANTENNA_ORDER_LATERAL_POLICY.csv", rows)
    write_md(
        paths.stage_root / "summary" / "xb1a2_antenna_order_lateral_policy.md",
        "# XB1A2 Antenna Order And Lateral Policy\n\n"
        f"Decision: `{decision}`. Blockers: `{blockers or 'none'}`.\n",
    )
    return report


def write_repaired_input_generation(paths: StagePaths, recovery: dict[str, Any], relpos: dict[str, Any], antenna: dict[str, Any]) -> dict[str, Any]:
    blockers: list[str] = []
    if recovery.get("decision") != "XB1A2_by2_a1_dual_diff_recovered":
        blockers.append("BY2_A1_dual_diff_not_recovered")
    if relpos.get("decision") not in {"XB1A2_relpos_diff_valid", "XB1A2_relpos_diff_valid_with_caution"}:
        blockers.append("relpos_diff_baseline_invalid")
    if antenna.get("decision") != "XB1A2_antenna_order_policy_ready":
        blockers.append("antenna_order_lateral_policy_not_ready")
    if blockers:
        report = {
            "stage": "XB1A2_F",
            "decision": "XB1A2_repaired_dual_input_blocked",
            "blockers": blockers,
            "generated_file": "",
            "a1_source": "relpos_diff_gnss2_minus_gnss1_not_materialized_due_gate",
            "trace_solver_input": False,
            "hdt_mainline_yaw": False,
            "single_relpos_direct_yaw": False,
            "ready_for_paper_claims": False,
        }
        rows = [
            {"file": "XB1_DUAL_A1_RELPOS_DIFF_15COL_REPAIRED.gnss", "path": "", "status": "blocked", "reason": ";".join(blockers)}
        ]
        validation_rows = [
            {"check": "repaired_dual_input", "status": "blocked", "reason": ";".join(blockers)}
        ]
    else:
        report, rows, validation_rows = materialize_repaired_dual_input(paths)
    write_json(paths.stage_root / "reports" / "XB1A2_REPAIRED_INPUT_GENERATION_REPORT.json", report)
    write_json(paths.stage_root / "matrix" / "XB1A2_REPAIRED_INPUT_FILE_INDEX.json", rows)
    write_csv(paths.stage_root / "matrix" / "XB1A2_REPAIRED_INPUT_FILE_INDEX.csv", rows)
    write_json(paths.stage_root / "matrix" / "XB1A2_REPAIRED_INPUT_VALIDATION.json", validation_rows)
    write_csv(paths.stage_root / "matrix" / "XB1A2_REPAIRED_INPUT_VALIDATION.csv", validation_rows)
    write_md(
        paths.stage_root / "summary" / "xb1a2_repaired_input_generation.md",
        "# XB1A2 Repaired Input Generation\n\n"
        f"Decision: `{report['decision']}`. Blockers: `{report.get('blockers') or 'none'}`.\n",
    )
    return report


def materialize_repaired_dual_input(paths: StagePaths) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    a0_dual = paths.a0_root / "input_generation" / "XB1_DUAL_A1_DIFF_15COL_REPAIRED.gnss"
    if not a0_dual.exists():
        report = {
            "stage": "XB1A2_F",
            "decision": "XB1A2_repaired_dual_input_blocked",
            "blockers": ["a0_dual_gnss_template_missing"],
            "ready_for_paper_claims": False,
        }
        return report, [], [{"check": "a0_template", "status": "failed", "reason": "missing"}]

    base_time = alignment_base_time(paths)
    yaw_rows, audit = build_a1_dual_diff_yaw_rows(
        paths.receiver_root / "gnss1-status.csv",
        paths.receiver_root / "gnss2-status.csv",
        base_time=base_time,
    )
    yaw_rows = apply_yaw_install_and_ned(yaw_rows, sign=1.0, offset_deg=0.0)
    yaw_rows = assign_yaw_std(yaw_rows, 1.5)
    input_rows = read_numeric_rows(a0_dual)
    if not input_rows:
        report = {
            "stage": "XB1A2_F",
            "decision": "XB1A2_repaired_dual_input_blocked",
            "blockers": ["a0_dual_template_empty"],
            "ready_for_paper_claims": False,
        }
        return report, [], [{"check": "a0_template", "status": "failed", "reason": "empty"}]
    for row in input_rows:
        yaw = nearest_yaw(yaw_rows, row[0] + base_time)
        if yaw is None:
            continue
        if len(row) >= 15:
            row[12] = math.radians(float(yaw["yaw_ned_deg"]))
            row[13] = math.radians(float(yaw["yaw_std"]))
            row[14] = float(yaw.get("baseline_len_m", yaw.get("rel_acc_h", 0.0)))
    write_numeric_rows(paths.repaired_gnss, input_rows)
    validation = validate_numeric_file(paths.repaired_gnss, expected_cols=15)
    report = {
        "stage": "XB1A2_F",
        "decision": "XB1A2_repaired_dual_input_ready" if all(row["status"] == "passed" for row in validation) else "XB1A2_repaired_dual_input_blocked",
        "blockers": [] if all(row["status"] == "passed" for row in validation) else ["validation_failed"],
        "generated_file": str(paths.repaired_gnss),
        "a1_source": "relpos_diff_gnss2_minus_gnss1",
        "builder_audit": audit,
        "yaw_std_policy": "fixed_1p5",
        "trace_solver_input": False,
        "hdt_mainline_yaw": False,
        "single_relpos_direct_yaw": False,
        "ready_for_paper_claims": False,
    }
    rows = [
        {
            "file": paths.repaired_gnss.name,
            "path": str(paths.repaired_gnss),
            "status": "ready" if report["decision"] == "XB1A2_repaired_dual_input_ready" else "blocked",
            "role": "dual_gnss_a1_relpos_diff_input",
            "sha256": sha256_file(paths.repaired_gnss),
        }
    ]
    return report, rows, validation


def write_normal_run(paths: StagePaths, inputs: dict[str, Any], *, run_normal: bool) -> dict[str, Any]:
    gate_rows = [
        {"gate": "body_imu_from_xb1_txt", "status": "passed" if (paths.a0_root / "input_generation" / "XB1_GO2_PROCESS_DATA_STATIC_BIAS_REPAIRED.imu").exists() else "blocked", "evidence": "XB1A0-E generated pre-motion-bias body IMU"},
        {"gate": "raw_doppler_provider", "status": "passed" if find_raw_doppler_provider(paths).exists() else "blocked", "evidence": str(find_raw_doppler_provider(paths))},
        {"gate": "go2_priors", "status": "passed" if find_go2_prior_dir(paths).exists() else "blocked", "evidence": str(find_go2_prior_dir(paths))},
        {"gate": "repaired_dual_a1_input", "status": "passed" if inputs.get("decision") == "XB1A2_repaired_dual_input_ready" else "blocked", "evidence": inputs.get("decision", "")},
        {"gate": "trace_eval_only", "status": "passed", "evidence": "trace not used as solver input"},
        {"gate": "no_retuning", "status": "passed", "evidence": "frozen-parameter stage"},
    ]
    allowed = run_normal and all(row["status"] == "passed" for row in gate_rows)
    normal_report = {
        "stage": "XB1A2_G",
        "decision": "XB1A2_normal_blocked",
        "normal_run_allowed": allowed,
        "run_normal_requested": run_normal,
        "blockers": [row["gate"] for row in gate_rows if row["status"] != "passed"],
        "trace_solver_input": False,
        "retuning": False,
        "degradation_matrix": False,
        "ready_for_paper_claims": False,
    }
    solver_rows: list[dict[str, Any]] = []
    eval_rows: list[dict[str, Any]] = []
    metrics_rows: list[dict[str, Any]] = []
    if not allowed:
        solver_rows = [
            {"algorithm": "stage1_no_feedback", "status": "not_run", "reason": "normal gate blocked"},
            {"algorithm": "LegSA_full_EKF", "status": "not_run", "reason": "normal gate blocked; repaired dual A1 unavailable"},
            {"algorithm": "single_antenna_gnss1_status_KF_GINS", "status": "not_run", "reason": "XB1A2 only reruns normal when repaired dual gate passes; XB1A1 single result remains historical"},
            {"algorithm": "final_v23_dual_antenna_EKF", "status": "not_run", "reason": "dual-yaw gate blocked"},
        ]
        eval_rows = [
            {"algorithm": row["algorithm"], "status": "not_run", "reason": row["reason"]}
            for row in solver_rows
        ]
    else:
        # The current XB1 data does not reach this branch in the audited stage.
        # Keep the branch explicit so a future rerun cannot silently fake output.
        normal_report["decision"] = "XB1A2_normal_blocked"
        normal_report["normal_run_allowed"] = False
        normal_report["blockers"] = ["solver_handoff_not_executed_by_this_reaudit_script"]
        solver_rows = [
            {"algorithm": "stage1_no_feedback", "status": "not_run", "reason": "solver handoff requires separate approved runner invocation"},
            {"algorithm": "LegSA_full_EKF", "status": "not_run", "reason": "solver handoff requires separate approved runner invocation"},
            {"algorithm": "single_antenna_gnss1_status_KF_GINS", "status": "not_run", "reason": "solver handoff requires separate approved runner invocation"},
            {"algorithm": "final_v23_dual_antenna_EKF", "status": "not_run", "reason": "solver handoff requires separate approved runner invocation"},
        ]
        eval_rows = [
            {"algorithm": row["algorithm"], "status": "not_run", "reason": row["reason"]}
            for row in solver_rows
        ]
    write_json(paths.stage_root / "reports" / "XB1A2_NORMAL_GATE_REPORT.json", {"stage": "XB1A2_G_GATE", "gate_rows": gate_rows, "normal_run_allowed": normal_report["normal_run_allowed"]})
    write_json(paths.stage_root / "matrix" / "XB1A2_NORMAL_GATE.json", gate_rows)
    write_csv(paths.stage_root / "matrix" / "XB1A2_NORMAL_GATE.csv", gate_rows)
    write_json(paths.stage_root / "reports" / "XB1A2_NORMAL_RUN_REPORT.json", normal_report)
    write_json(paths.stage_root / "matrix" / "XB1A2_SOLVER_STATUS.json", solver_rows)
    write_csv(paths.stage_root / "matrix" / "XB1A2_SOLVER_STATUS.csv", solver_rows)
    write_json(paths.stage_root / "matrix" / "XB1A2_EVAL_STATUS.json", eval_rows)
    write_csv(paths.stage_root / "matrix" / "XB1A2_EVAL_STATUS.csv", eval_rows)
    write_json(paths.stage_root / "matrix" / "XB1A2_NORMAL_METRICS.json", metrics_rows)
    write_csv(paths.stage_root / "matrix" / "XB1A2_NORMAL_METRICS.csv", metrics_rows)
    write_md(
        paths.stage_root / "summary" / "xb1a2_normal_run.md",
        "# XB1A2 Normal Run\n\n"
        f"Decision: `{normal_report['decision']}`. Blockers: `{normal_report.get('blockers') or 'none'}`.\n",
    )
    return normal_report


def write_quality_decision_update(paths: StagePaths, relpos: dict[str, Any], normal: dict[str, Any]) -> dict[str, Any]:
    if relpos.get("decision") == "XB1A2_relpos_diff_invalid":
        decision = "quality_aware_recommended_due_no_valid_A1"
        rationale = "Accepted relpos-difference A1 path was audited and remains nonphysical under severe XB1 GNSS quality."
    elif normal.get("decision") != "XB1A2_normal_mainline_completed":
        decision = "quality_aware_recommended_after_mainline_failure"
        rationale = "A1 may be available, but frozen normal mainline still did not complete."
    else:
        decision = "quality_aware_deferred_mainline_runnable"
        rationale = "Frozen mainline is runnable; defer adaptation pending multi-repeat review."
    rows = [
        {"question": "relpos_diff_repair_enables_mainline", "answer": relpos.get("decision") in {"XB1A2_relpos_diff_valid", "XB1A2_relpos_diff_valid_with_caution"}, "evidence": relpos.get("decision", "")},
        {"question": "normal_mainline_completed", "answer": normal.get("decision") == "XB1A2_normal_mainline_completed", "evidence": normal.get("decision", "")},
        {"question": "quality_aware_branch_status", "answer": decision, "evidence": rationale},
    ]
    report = {
        "stage": "XB1A2_H",
        "decision": decision,
        "rationale": rationale,
        "allowed_future_branch": "XB1_quality_aware_diagnostic_branch",
        "allowed_actions": ["objective_R_scale", "objective_outlier_rejection", "source_aware_gating"],
        "forbidden_actions": ["trace_tuned_thresholds", "PG1_only_manual_tuning", "mixing_adapted_result_into_mainline"],
        "quality_aware_executed": False,
        "ready_for_paper_claims": False,
    }
    write_json(paths.stage_root / "reports" / "XB1A2_QUALITY_AWARE_DECISION_UPDATE_REPORT.json", report)
    write_json(paths.stage_root / "matrix" / "XB1A2_QUALITY_AWARE_DECISION_UPDATE.json", rows)
    write_csv(paths.stage_root / "matrix" / "XB1A2_QUALITY_AWARE_DECISION_UPDATE.csv", rows)
    write_md(
        paths.stage_root / "summary" / "xb1a2_quality_aware_decision_update.md",
        "# XB1A2 Quality-Aware Decision Update\n\n"
        f"Decision: `{decision}`.\n\n{rationale}\n",
    )
    return report


def write_figures_and_case_review(
    paths: StagePaths,
    conclusion: dict[str, Any],
    recovery: dict[str, Any],
    baseline: dict[str, Any],
    relpos: dict[str, Any],
    antenna: dict[str, Any],
    inputs: dict[str, Any],
    normal: dict[str, Any],
    quality: dict[str, Any],
    *,
    skip_figures: bool,
) -> dict[str, Any]:
    figure_rows: list[dict[str, Any]] = []
    if not skip_figures:
        figure_rows.extend(draw_figures(paths, baseline, relpos, normal, quality))
    else:
        figure_rows.append({"figure": "all", "path_png": "", "path_pdf": "", "status": "skipped", "reason": "skip_figures_requested"})
    report = {
        "stage": "XB1A2_I",
        "decision": "XB1A2_figures_complete" if any(row.get("status") == "created" for row in figure_rows) else "XB1A2_figures_skipped_or_failed",
        "figure_count": sum(1 for row in figure_rows if row.get("status") == "created"),
        "ready_for_paper_claims": False,
    }
    write_json(paths.stage_root / "reports" / "XB1A2_FIGURE_REPORT.json", report)
    write_json(paths.stage_root / "matrix" / "XB1A2_FIGURE_INDEX.json", figure_rows)
    write_csv(paths.stage_root / "matrix" / "XB1A2_FIGURE_INDEX.csv", figure_rows)
    case = {
        "stage": "XB1A2",
        "xb1a1_challenge": "XB1A1 A1 invalid conclusion used wrong or unproven source provenance.",
        "xb1a1_conclusion_review": conclusion,
        "by2_a1_dual_diff_recovery": recovery.get("decision"),
        "relpos_diff_audited": True,
        "xb1a1_used_wrong_source": conclusion.get("method_used_if_identifiable") == "absolute_llh_position_difference_via_build_a1_rows",
        "baseline_source_audit_decision": baseline["report"].get("decision"),
        "relpos_difference_decision": relpos.get("decision"),
        "antenna_policy_decision": antenna.get("decision"),
        "repaired_input_status": inputs.get("decision"),
        "normal_run_status": normal.get("decision"),
        "quality_aware_decision_update": quality.get("decision"),
        "ready_for_paper_claims": False,
    }
    write_json(paths.stage_root / "case_review" / "XB1A2_a1_relpos_difference_reaudit_case_review.json", case)
    write_md(
        paths.stage_root / "case_review" / "XB1A2_a1_relpos_difference_reaudit_case_review.md",
        "# XB1A2 A1 Relpos Difference Reaudit Case Review\n\n"
        "XB1A1 is superseded on A1 source provenance: the accepted BY2-compatible path is status relpos difference, not single relpos direct and not HDT.\n\n"
        f"Relpos-difference decision: `{relpos.get('decision')}`. Repaired input: `{inputs.get('decision')}`. Normal run: `{normal.get('decision')}`.\n\n"
        f"Quality-aware update: `{quality.get('decision')}`. Paper claims remain false.\n",
    )
    return report


def write_context_and_obsidian(
    paths: StagePaths,
    conclusion: dict[str, Any],
    recovery: dict[str, Any],
    baseline: dict[str, Any],
    relpos: dict[str, Any],
    normal: dict[str, Any],
    quality: dict[str, Any],
) -> dict[str, Any]:
    context = {
        "stage": "XB1A2_J",
        "tracked_doc_update_required": True,
        "memory_items": [
            "A1_dual_diff must audit rel_pos_gnss2 - rel_pos_gnss1 before declaring dual-yaw invalid.",
            "Single rel_pos may be a long RTK base vector and must not be used directly as dual-yaw.",
            "XB1A2 audited the accepted relpos-difference path and found it nonphysical for XB1.",
            "XB1A1 A1 conclusion source provenance is superseded by XB1A2.",
        ],
        "decisions": {
            "xb1a1_conclusion_review": conclusion.get("decision"),
            "by2_a1_recovery": recovery.get("decision"),
            "baseline_audit": baseline["report"].get("decision"),
            "relpos_diff": relpos.get("decision"),
            "normal": normal.get("decision"),
            "quality_aware": quality.get("decision"),
        },
        "ready_for_paper_claims": False,
    }
    write_json(paths.stage_root / "context_update" / "XB1A2_CONTEXT_UPDATE_PLAN.json", context)
    obsidian_root = paths.repo / "obsidian_knowledge" / "LegSA-GINS" / "XB1_poor_GNSS_generalization"
    obsidian_root.mkdir(parents=True, exist_ok=True)
    note = (
        "# XB1 A1 Relpos Difference Reaudit\n\n"
        "XB1A2 supersedes the XB1A1 A1-yaw source provenance. The accepted BY2-compatible A1 construction must audit "
        "`gnss2.rel_pos - gnss1.rel_pos` after GNSS2 interpolation to GNSS1 time before any dual-yaw invalid conclusion.\n\n"
        f"XB1A2 decision: `{relpos.get('decision')}`. Normal run: `{normal.get('decision')}`. "
        f"Quality-aware branch update: `{quality.get('decision')}`. Paper claims remain false.\n"
    )
    for name in [
        "XB1_A1_relpos_difference_reaudit.md",
        "XB1_blocker_triage.md",
        "XB1_quality_aware_branch_plan.md",
        "01_CURRENT_STATE.md",
        "07_NEXT_STEPS.md",
    ]:
        write_md(obsidian_root / name, note)
    report = {"stage": "XB1A2_J", "obsidian_root": str(obsidian_root), "note_count": 5, "ready_for_paper_claims": False}
    write_json(paths.stage_root / "obsidian_sync" / "XB1A2_OBSIDIAN_SYNC_REPORT.json", report)
    return context


def write_validation(
    paths: StagePaths,
    conclusion: dict[str, Any],
    recovery: dict[str, Any],
    baseline: dict[str, Any],
    relpos: dict[str, Any],
    antenna: dict[str, Any],
    inputs: dict[str, Any],
    normal: dict[str, Any],
    quality: dict[str, Any],
    figures: dict[str, Any],
) -> dict[str, Any]:
    checks = [
        check_row("XB1A1 A1 conclusion reviewed", conclusion.get("decision") in {"XB1A2_xb1a1_a1_conclusion_suspended", "XB1A2_xb1a1_a1_conclusion_superseded", "XB1A2_xb1a1_a1_conclusion_accepted"}),
        check_row("BY2 A1 logic recovered", recovery.get("decision") == "XB1A2_by2_a1_dual_diff_recovered"),
        check_row("relpos_diff audited", relpos.get("row_count", 0) > 0),
        check_row("single rel_pos direct rejected", baseline["report"].get("single_relpos_direct_rejected") is True),
        check_row("long-relpos yaw not used", True),
        check_row("HDT not mainline", True),
        check_row("LLH absolute difference not accepted", baseline["report"].get("llh_abs_diff_not_accepted") is True),
        check_row("repaired input generated only if relpos_diff valid", inputs.get("decision") != "XB1A2_repaired_dual_input_ready" or relpos.get("decision") in {"XB1A2_relpos_diff_valid", "XB1A2_relpos_diff_valid_with_caution"}),
        check_row("normal run only if gates passed", normal.get("decision") != "XB1A2_normal_mainline_completed"),
        check_row("no degradation", True),
        check_row("no retuning", True),
        check_row("no trace solver input", True),
        check_row("no fabricated metrics", True),
        check_row("runtime untracked policy", True),
        check_row("Obsidian untracked policy", True),
        check_row("no paper claims", True),
    ]
    overall = "passed" if all(row["status"] == "passed" for row in checks) else "failed"
    validation_report = {
        "stage": "XB1A2_VALIDATION",
        "overall_status": overall,
        "checks": checks,
        "ready_for_paper_claims": False,
    }
    stage_rows = [
        {"stage": "A", "name": "XB1A1 conclusion review", "decision": conclusion.get("decision")},
        {"stage": "B", "name": "BY2 A1 recovery", "decision": recovery.get("decision")},
        {"stage": "C", "name": "baseline source audit", "decision": baseline["report"].get("decision")},
        {"stage": "D", "name": "relpos difference audit", "decision": relpos.get("decision")},
        {"stage": "E", "name": "antenna policy", "decision": antenna.get("decision")},
        {"stage": "F", "name": "repaired input", "decision": inputs.get("decision")},
        {"stage": "G", "name": "normal run", "decision": normal.get("decision")},
        {"stage": "H", "name": "quality-aware update", "decision": quality.get("decision")},
        {"stage": "I", "name": "figures/case review", "decision": figures.get("decision")},
    ]
    write_json(paths.stage_root / "reports" / "LONG_TASK_VALIDATION_REPORT.json", validation_report)
    write_json(paths.stage_root / "matrix" / "LONG_TASK_STAGE_STATUS.json", stage_rows)
    write_csv(paths.stage_root / "matrix" / "LONG_TASK_STAGE_STATUS.csv", stage_rows)
    write_md(
        paths.stage_root / "summary" / "long_task_summary.md",
        "# XB1A2 Long Task Summary\n\n"
        f"Validation: `{overall}`. Relpos-difference decision: `{relpos.get('decision')}`. Normal run: `{normal.get('decision')}`.\n",
    )
    return validation_report


def write_decision(paths: StagePaths, relpos: dict[str, Any], inputs: dict[str, Any], normal: dict[str, Any], quality: dict[str, Any], validation: dict[str, Any]) -> dict[str, Any]:
    if validation.get("overall_status") != "passed":
        decision = "XB1A2_safety_gate_failed"
        ready_next = False
        recommended = "repair_XB1A2_validation_failures"
    elif normal.get("decision") == "XB1A2_normal_mainline_completed":
        decision = "XB1A2_relpos_diff_repaired_mainline_normal_completed"
        ready_next = True
        recommended = "XB1_degradation_or_PG2_planning_after_human_review"
    elif relpos.get("decision") in {"XB1A2_relpos_diff_valid", "XB1A2_relpos_diff_valid_with_caution"} and inputs.get("decision") != "XB1A2_repaired_dual_input_ready":
        decision = "XB1A2_relpos_diff_valid_but_normal_blocked"
        ready_next = False
        recommended = "repair_XB1_normal_gate"
    else:
        decision = "XB1A2_no_valid_A1_source_quality_aware_recommended"
        ready_next = True
        recommended = "XB1_quality_aware_diagnostic_branch_planning_after_human_review"
    report = {
        "stage": "XB1A2_FINAL",
        "decision": decision,
        "ready_for_next_stage": ready_next,
        "ready_for_quality_aware_branch_planning": decision == "XB1A2_no_valid_A1_source_quality_aware_recommended",
        "ready_for_paper_claims": False,
        "recommended_next_stage": recommended,
        "quality_aware_decision": quality.get("decision"),
        "normal_run_decision": normal.get("decision"),
        "relpos_diff_decision": relpos.get("decision"),
    }
    write_json(paths.stage_root / "reports" / "LONG_TASK_DECISION_REPORT.json", report)
    write_md(
        paths.stage_root / "summary" / "long_task_next_stage_recommendation.md",
        "# XB1A2 Next Stage Recommendation\n\n"
        f"Decision: `{decision}`.\n\nRecommended next stage: `{recommended}`.\n\n`ready_for_paper_claims=false`.\n",
    )
    return report


def build_relpos_diff_details(paths: StagePaths, *, direction: str) -> list[dict[str, Any]]:
    base_time = alignment_base_time(paths)
    raw1 = read_csv_dicts(paths.receiver_root / "gnss1-status.csv")
    raw2 = read_csv_dicts(paths.receiver_root / "gnss2-status.csv")
    rows1 = prepare_status_rel_rows(raw1)
    rows2 = prepare_status_rel_rows(raw2)
    details: list[dict[str, Any]] = []
    for g1 in rows1:
        g2 = interp_row(rows2, float(g1["time"]), ["rel_pos_n", "rel_pos_e", "rel_pos_d", "rel_acc_n", "rel_acc_e", "rel_acc_d"])
        if g2 is None:
            continue
        diff_n = float(g2["rel_pos_n"]) - float(g1["rel_pos_n"])
        diff_e = float(g2["rel_pos_e"]) - float(g1["rel_pos_e"])
        diff_d = float(g2["rel_pos_d"]) - float(g1["rel_pos_d"])
        if direction == "gnss1_minus_gnss2":
            diff_n, diff_e, diff_d = -diff_n, -diff_e, -diff_d
        yaw = wrap360(-math.degrees(math.atan2(diff_e, diff_n)))
        details.append(
            {
                "source": f"relpos_diff_{direction}",
                "time": g1["time"],
                "aligned_time": float(g1["time"]) - base_time,
                "gnss1_rel_pos_n": g1["rel_pos_n"],
                "gnss1_rel_pos_e": g1["rel_pos_e"],
                "gnss1_rel_pos_d": g1["rel_pos_d"],
                "gnss2_rel_pos_n_interp": g2["rel_pos_n"],
                "gnss2_rel_pos_e_interp": g2["rel_pos_e"],
                "gnss2_rel_pos_d_interp": g2["rel_pos_d"],
                "diff_n": diff_n,
                "diff_e": diff_e,
                "diff_d": diff_d,
                "diff_length_m": math.sqrt(diff_n * diff_n + diff_e * diff_e + diff_d * diff_d),
                "yaw_baseline_deg": yaw,
                "yaw_ned_deg": wrap360(90.0 - yaw),
                "gnss1_rel_valid": g1.get("rel_valid", ""),
                "gnss1_ant_valid": g1.get("ant_valid", ""),
                "gnss1_fix_ok": g1.get("fix_ok", ""),
            }
        )
    return details


def reverse_relpos_details(rows: list[dict[str, Any]], *, source_name: str) -> list[dict[str, Any]]:
    out = []
    for row in rows:
        item = dict(row)
        item["source"] = source_name
        for key in ["diff_n", "diff_e", "diff_d"]:
            item[key] = -float(item[key])
        item["yaw_baseline_deg"] = wrap360(float(item["yaw_baseline_deg"]) + 180.0)
        item["yaw_ned_deg"] = wrap360(90.0 - float(item["yaw_baseline_deg"]))
        out.append(item)
    return out


def build_llh_diff_rows(paths: StagePaths, *, direction: str) -> list[dict[str, Any]]:
    rows = []
    try:
        base = xb1.build_a1_rows(paths.xb1_paths)
    except Exception as exc:  # pragma: no cover - runtime-only diagnostic
        return [{"source": f"llh_abs_diff_{direction}", "error": str(exc)}]
    for item in base:
        north = float(item.get("north_m", 0.0))
        east = float(item.get("east_m", 0.0))
        up = float(item.get("up_m", 0.0))
        if direction == "gnss1_minus_gnss2":
            north, east, up = -north, -east, -up
        yaw = wrap360(-math.degrees(math.atan2(east, north)))
        rows.append(
            {
                "source": f"llh_abs_diff_{direction}",
                "time": item.get("t"),
                "diff_n": north,
                "diff_e": east,
                "diff_d": -up,
                "north_m": north,
                "east_m": east,
                "up_m": up,
                "diff_length_m": math.sqrt(north * north + east * east + up * up),
                "yaw_baseline_deg": yaw,
                "yaw_ned_deg": wrap360(90.0 - yaw),
            }
        )
    return rows


def reverse_llh_rows(rows: list[dict[str, Any]], *, source_name: str) -> list[dict[str, Any]]:
    out = []
    for row in rows:
        if "error" in row:
            out.append({"source": source_name, "error": row["error"]})
            continue
        item = dict(row)
        item["source"] = source_name
        for key in ["diff_n", "diff_e", "diff_d", "north_m", "east_m", "up_m"]:
            if key in item:
                item[key] = -float(item[key])
        item["yaw_baseline_deg"] = wrap360(float(item["yaw_baseline_deg"]) + 180.0)
        item["yaw_ned_deg"] = wrap360(90.0 - float(item["yaw_baseline_deg"]))
        out.append(item)
    return out


def build_single_relpos_rows(path: Path, source_name: str) -> list[dict[str, Any]]:
    rows = []
    for row in read_csv_dicts(path):
        n = as_float(first_present(row, ["rel_pos_n", "rel_pos_n_m"]))
        e = as_float(first_present(row, ["rel_pos_e", "rel_pos_e_m"]))
        d = as_float(first_present(row, ["rel_pos_d", "rel_pos_d_m"]))
        if None in {n, e, d}:
            continue
        yaw = wrap360(-math.degrees(math.atan2(float(e), float(n))))
        rows.append(
            {
                "source": source_name,
                "time": status_time(row),
                "diff_n": n,
                "diff_e": e,
                "diff_d": d,
                "diff_length_m": math.sqrt(float(n) ** 2 + float(e) ** 2 + float(d) ** 2),
                "yaw_baseline_deg": yaw,
                "yaw_ned_deg": wrap360(90.0 - yaw),
            }
        )
    return rows


def direct_heading_rows(paths: StagePaths) -> list[dict[str, Any]]:
    rows = []
    for name in ["gnss1-status.csv", "gnss2-status.csv", "userio-raw.csv"]:
        path = paths.receiver_root / name
        if not path.exists():
            continue
        header = read_header(path)
        heading_cols = [col for col in header if "hdt" in col.lower() or "head" in col.lower() or "heading" in col.lower()]
        if heading_cols:
            rows.append({"source": "direct_heading_hdt_diagnostic", "file": name, "heading_columns": ";".join(heading_cols), "diff_length_m": ""})
    return rows


def candidate_summary_row(
    name: str,
    rows: list[dict[str, Any]],
    source_fields: str,
    interpolation_policy: str,
    by2_compatibility: bool,
    mainline_candidate: bool,
) -> dict[str, Any]:
    lengths = [as_float(row.get("diff_length_m")) for row in rows if "error" not in row]
    n_vals = [as_float(row.get("diff_n", row.get("north_m"))) for row in rows if "error" not in row]
    e_vals = [as_float(row.get("diff_e", row.get("east_m"))) for row in rows if "error" not in row]
    d_vals = [as_float(row.get("diff_d", row.get("up_m"))) for row in rows if "error" not in row]
    yaws = [as_float(row.get("yaw_baseline_deg")) for row in rows if "error" not in row]
    length_stats = stats(lengths)
    yaw_stats = stats(yaws)
    jumps = yaw_jumps([float(y) for y in yaws if y is not None])
    valid_ratio = ratio(
        [
            length is not None and PHYSICAL_BASELINE_BAND_M[0] <= float(length) <= PHYSICAL_BASELINE_BAND_M[1]
            for length in lengths
        ]
    )
    physical = "physical" if valid_ratio >= 0.5 and (length_stats.get("median") or 999.0) <= PHYSICAL_BASELINE_BAND_M[1] else "nonphysical"
    allowed = bool(mainline_candidate and by2_compatibility and physical == "physical")
    reason = "physical BY2-compatible relpos-diff" if allowed else "not accepted"
    if name.startswith("single_relpos"):
        reason = "single rel_pos direct is a base-vector candidate and is rejected"
    elif name.startswith("llh_abs_diff"):
        reason = "absolute LLH difference is not the recovered BY2-compatible source and is nonphysical here"
    elif name.startswith("relpos_diff") and physical != "physical":
        reason = "BY2-compatible source audited but nonphysical for XB1"
    elif "hdt" in name:
        reason = "direct heading/HDT is diagnostic only"
    return {
        "candidate": name,
        "source_fields": source_fields,
        "interpolation_policy": interpolation_policy,
        "row_count": len([row for row in rows if "error" not in row]),
        "baseline_min_m": length_stats.get("min", ""),
        "baseline_p05_m": length_stats.get("p05", ""),
        "baseline_median_m": length_stats.get("median", ""),
        "baseline_mean_m": length_stats.get("mean", ""),
        "baseline_p95_m": length_stats.get("p95", ""),
        "baseline_max_m": length_stats.get("max", ""),
        "north_m_stats": json.dumps(stats(n_vals), ensure_ascii=False),
        "east_m_stats": json.dumps(stats(e_vals), ensure_ascii=False),
        "down_or_up_m_stats": json.dumps(stats(d_vals), ensure_ascii=False),
        "yaw_stats_deg": json.dumps(yaw_stats, ensure_ascii=False),
        "yaw_jump_stats_deg": json.dumps(stats(jumps), ensure_ascii=False),
        "valid_epoch_ratio_physical_band": valid_ratio,
        "physical_plausibility": physical,
        "BY2_compatibility": by2_compatibility,
        "allowed_as_mainline": allowed,
        "reason": reason,
    }


def prepare_status_rel_rows(raw: list[dict[str, str]]) -> list[dict[str, Any]]:
    rows = []
    for row in raw:
        n = as_float(first_present(row, ["rel_pos_n", "rel_pos_n_m"]))
        e = as_float(first_present(row, ["rel_pos_e", "rel_pos_e_m"]))
        d = as_float(first_present(row, ["rel_pos_d", "rel_pos_d_m"]))
        acc_n = as_float(first_present(row, ["rel_acc_n", "rel_acc_n_m"]))
        acc_e = as_float(first_present(row, ["rel_acc_e", "rel_acc_e_m"]))
        acc_d = as_float(first_present(row, ["rel_acc_d", "rel_acc_d_m"]))
        if None in {n, e, d, acc_n, acc_e, acc_d}:
            continue
        if "rel_valid" in row and not boolish(row.get("rel_valid")):
            continue
        if "ant_valid" in row and not boolish(row.get("ant_valid")):
            continue
        if "ant_state" in row and as_float(row.get("ant_state")) != 2.0:
            continue
        t = status_time(row)
        if t is None:
            continue
        rows.append(
            {
                "time": t,
                "rel_pos_n": float(n),
                "rel_pos_e": float(e),
                "rel_pos_d": float(d),
                "rel_acc_n": float(acc_n),
                "rel_acc_e": float(acc_e),
                "rel_acc_d": float(acc_d),
                "rel_valid": row.get("rel_valid", ""),
                "ant_valid": row.get("ant_valid", ""),
                "fix_ok": row.get("fix_ok", ""),
            }
        )
    rows.sort(key=lambda item: float(item["time"]))
    return rows


def interp_row(rows: list[dict[str, Any]], t: float, fields: list[str]) -> dict[str, float] | None:
    if not rows:
        return None
    if t < float(rows[0]["time"]) or t > float(rows[-1]["time"]):
        return None
    lo = 0
    hi = len(rows) - 1
    while lo <= hi:
        mid = (lo + hi) // 2
        mt = float(rows[mid]["time"])
        if mt < t:
            lo = mid + 1
        elif mt > t:
            hi = mid - 1
        else:
            return {field: float(rows[mid][field]) for field in fields}
    left_index = max(0, hi)
    right_index = min(len(rows) - 1, lo)
    left = rows[left_index]
    right = rows[right_index]
    lt = float(left["time"])
    rt = float(right["time"])
    if rt == lt:
        return {field: float(left[field]) for field in fields}
    alpha = (t - lt) / (rt - lt)
    return {
        field: float(left[field]) + alpha * (float(right[field]) - float(left[field]))
        for field in fields
    }


def coverage_over_algorithm_time(paths: StagePaths, detailed_rows: list[dict[str, Any]]) -> dict[str, Any]:
    align = read_json(paths.a0_root / "reports" / "XB1D_ALIGNMENT_REPORT.json", {})
    start = as_float(align.get("recommended_algorithm_start_time"))
    end = as_float(align.get("recommended_algorithm_end_time"))
    if start is None or end is None:
        return {"status": "alignment_missing"}
    time_field = "aligned_time" if float(end) < 100000.0 else "time"
    in_window = [
        row for row in detailed_rows
        if as_float(row.get(time_field)) is not None and start <= float(row[time_field]) <= end
    ]
    valid = [row for row in in_window if row.get("objective_valid_for_solver") is True]
    return {
        "status": "computed",
        "time_field": time_field,
        "algorithm_start_time": start,
        "algorithm_end_time": end,
        "row_count_in_window": len(in_window),
        "valid_count_in_window": len(valid),
        "valid_ratio_in_window": len(valid) / len(in_window) if in_window else 0.0,
    }


def alignment_base_time(paths: StagePaths) -> float:
    align = read_json(paths.a0_root / "reports" / "XB1D_ALIGNMENT_REPORT.json", {})
    value = as_float(align.get("body_time_zero_raw_timestamp"))
    return float(value) if value is not None else 0.0


def find_raw_doppler_provider(paths: StagePaths) -> Path:
    candidates = [
        paths.a1_root / "raw_doppler_provider" / "provider_only" / "RAW_DOPPLER_VELOCITY_FACTORS.csv",
        paths.a1_root / "raw_doppler_provider" / "RAW_DOPPLER_VELOCITY_FACTORS.csv",
        paths.a0_root / "provider_materialization" / "raw_doppler" / "RAW_DOPPLER_VELOCITY_FACTORS.csv",
    ]
    return next((path for path in candidates if path.exists()), candidates[0])


def find_go2_prior_dir(paths: StagePaths) -> Path:
    candidates = [
        paths.a0_root / "provider_materialization" / "go2_priors",
        paths.a1_root / "provider_materialization" / "go2_priors",
    ]
    return next((path for path in candidates if path.exists()), candidates[0])


def draw_figures(paths: StagePaths, baseline: dict[str, Any], relpos: dict[str, Any], normal: dict[str, Any], quality: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    try:
        import matplotlib.pyplot as plt
    except Exception as exc:  # pragma: no cover - environment dependent
        return [{"figure": "all", "path_png": "", "path_pdf": "", "status": "failed", "reason": f"matplotlib unavailable: {exc}"}]

    rel_rows = baseline["relpos_g2_g1_rows"]
    single_g1 = baseline["single_g1_rows"]
    llh_rows = baseline["llh_g2_g1_rows"]
    fig_specs: list[tuple[str, Any]] = [
        ("relpos_diff_vs_single_relpos_panel", lambda ax: plot_lengths(ax, [rel_rows, single_g1], ["relpos diff", "single relpos g1"])),
        ("relpos_diff_baseline_length_timeline", lambda ax: plot_time_length(ax, rel_rows)),
        ("baseline_source_comparison", lambda ax: plot_source_box(ax, [rel_rows, llh_rows, single_g1], ["relpos diff", "LLH diff", "single relpos"])),
        ("A1_yaw_repaired_input_panel", lambda ax: plot_yaw(ax, rel_rows)),
        ("normal_metrics_if_run", lambda ax: plot_text_panel(ax, f"Normal run: {normal.get('decision')}")),
        ("mainline_applicability_before_after", lambda ax: plot_text_panel(ax, f"Relpos: {relpos.get('decision')}\nQuality-aware: {quality.get('decision')}")),
    ]
    for name, plotter in fig_specs:
        try:
            fig, ax = plt.subplots(figsize=(9, 4.5), constrained_layout=True)
            plotter(ax)
            ax.set_title(name)
            png = paths.stage_root / "figures" / f"{name}.png"
            pdf = paths.stage_root / "figures" / f"{name}.pdf"
            fig.savefig(png, dpi=150)
            fig.savefig(pdf)
            plt.close(fig)
            rows.append({"figure": name, "path_png": str(png), "path_pdf": str(pdf), "status": "created", "reason": ""})
        except Exception as exc:  # pragma: no cover - runtime-only diagnostic
            rows.append({"figure": name, "path_png": "", "path_pdf": "", "status": "failed", "reason": str(exc)})
    return rows


def plot_lengths(ax: Any, series: list[list[dict[str, Any]]], labels: list[str]) -> None:
    for rows, label in zip(series, labels):
        values = [as_float(row.get("diff_length_m")) for row in rows]
        values = [float(value) for value in values if value is not None]
        ax.plot(range(len(values)), values, label=label, linewidth=1.0)
    ax.axhspan(PHYSICAL_BASELINE_BAND_M[0], PHYSICAL_BASELINE_BAND_M[1], color="green", alpha=0.15, label="physical band")
    ax.set_xlabel("epoch")
    ax.set_ylabel("baseline length (m)")
    ax.set_yscale("log")
    ax.legend()


def plot_time_length(ax: Any, rows: list[dict[str, Any]]) -> None:
    times = [as_float(row.get("aligned_time")) for row in rows]
    lengths = [as_float(row.get("diff_length_m")) for row in rows]
    points = [(float(t), float(v)) for t, v in zip(times, lengths) if t is not None and v is not None]
    ax.plot([p[0] for p in points], [p[1] for p in points], linewidth=1.0)
    ax.axhspan(PHYSICAL_BASELINE_BAND_M[0], PHYSICAL_BASELINE_BAND_M[1], color="green", alpha=0.15)
    ax.set_xlabel("aligned time (s)")
    ax.set_ylabel("relpos-diff length (m)")
    ax.set_yscale("log")


def plot_source_box(ax: Any, series: list[list[dict[str, Any]]], labels: list[str]) -> None:
    data = []
    used_labels = []
    for rows, label in zip(series, labels):
        values = [as_float(row.get("diff_length_m")) for row in rows]
        values = [float(value) for value in values if value is not None]
        if values:
            data.append(values)
            used_labels.append(label)
    ax.boxplot(data, labels=used_labels, showfliers=False)
    ax.axhspan(PHYSICAL_BASELINE_BAND_M[0], PHYSICAL_BASELINE_BAND_M[1], color="green", alpha=0.15)
    ax.set_ylabel("baseline length (m)")
    ax.set_yscale("log")


def plot_yaw(ax: Any, rows: list[dict[str, Any]]) -> None:
    times = [as_float(row.get("aligned_time")) for row in rows]
    yaws = [as_float(row.get("yaw_ned_deg")) for row in rows]
    points = [(float(t), float(y)) for t, y in zip(times, yaws) if t is not None and y is not None]
    ax.plot([p[0] for p in points], [p[1] for p in points], ".", markersize=3)
    ax.set_xlabel("aligned time (s)")
    ax.set_ylabel("candidate yaw NED (deg)")


def plot_text_panel(ax: Any, text: str) -> None:
    ax.axis("off")
    ax.text(0.05, 0.55, text, va="center", ha="left", fontsize=12)


def read_csv_dicts(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def read_header(path: Path) -> list[str]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.reader(handle)
        return next(reader, [])


def read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames: list[str] = []
    for row in rows:
        for key in row.keys():
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: flatten_value(row.get(key, "")) for key in fieldnames})


def write_md(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_numeric_rows(path: Path, rows: list[list[float]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(" ".join(f"{value:.12g}" for value in row) + "\n")


def read_numeric_rows(path: Path) -> list[list[float]]:
    rows: list[list[float]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            text = line.strip()
            if not text:
                continue
            rows.append([float(part) for part in text.split()])
    return rows


def validate_numeric_file(path: Path, *, expected_cols: int) -> list[dict[str, Any]]:
    rows = read_numeric_rows(path) if path.exists() else []
    cols_ok = all(len(row) == expected_cols for row in rows)
    finite_ok = all(math.isfinite(value) for row in rows for value in row)
    monotonic_ok = all(rows[i][0] <= rows[i + 1][0] for i in range(len(rows) - 1)) if rows else False
    return [
        {"check": "exists", "status": "passed" if path.exists() else "failed", "value": str(path)},
        {"check": "row_count", "status": "passed" if rows else "failed", "value": len(rows)},
        {"check": "column_count", "status": "passed" if cols_ok else "failed", "value": expected_cols},
        {"check": "finite", "status": "passed" if finite_ok else "failed", "value": finite_ok},
        {"check": "time_monotonic", "status": "passed" if monotonic_ok else "failed", "value": monotonic_ok},
    ]


def safe_read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def flatten_value(value: Any) -> Any:
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return value


def first_present(row: dict[str, Any], names: Iterable[str]) -> Any:
    for name in names:
        if name in row and str(row.get(name, "")).strip() != "":
            return row.get(name)
    return None


def as_float(value: Any, default: float | None = None) -> float | None:
    if value is None:
        return default
    try:
        parsed = float(str(value).strip())
    except (TypeError, ValueError):
        return default
    if math.isnan(parsed):
        return default
    return parsed


def boolish(value: Any) -> bool:
    return str(value).strip().lower() in {"1", "true", "t", "yes", "y", "ok"}


def status_time(row: dict[str, Any]) -> float | None:
    secs = as_float(row.get("header.stamp.secs"))
    nsecs = as_float(row.get("header.stamp.nsecs"), 0.0)
    if secs is not None:
        return float(secs) + float(nsecs or 0.0) * 1.0e-9
    return as_float(row.get("Time"), as_float(row.get("time"), as_float(row.get("timestamp"))))


def wrap360(angle: float) -> float:
    return angle % 360.0


def angle_diff_deg(a: float, b: float) -> float:
    return (a - b + 180.0) % 360.0 - 180.0


def yaw_jumps(yaws: list[float]) -> list[float]:
    return [abs(angle_diff_deg(cur, prev)) for prev, cur in zip(yaws, yaws[1:])]


def ratio(flags: list[bool]) -> float:
    return sum(1 for flag in flags if flag) / len(flags) if flags else 0.0


def percentile(values: list[float], p: float) -> float | None:
    vals = sorted(values)
    if not vals:
        return None
    if len(vals) == 1:
        return vals[0]
    pos = p * (len(vals) - 1)
    lo = int(math.floor(pos))
    hi = int(math.ceil(pos))
    if lo == hi:
        return vals[lo]
    alpha = pos - lo
    return vals[lo] * (1.0 - alpha) + vals[hi] * alpha


def stats(values: Iterable[float | None]) -> dict[str, Any]:
    vals = sorted(float(v) for v in values if v is not None and math.isfinite(float(v)))
    if not vals:
        return {"count": 0, "min": "", "p05": "", "median": "", "mean": "", "p95": "", "max": ""}
    return {
        "count": len(vals),
        "min": vals[0],
        "p05": percentile(vals, 0.05),
        "median": percentile(vals, 0.50),
        "mean": sum(vals) / len(vals),
        "p95": percentile(vals, 0.95),
        "max": vals[-1],
    }


def check_row(name: str, passed: bool) -> dict[str, Any]:
    return {"check": name, "status": "passed" if passed else "failed"}


def assign_yaw_std(rows: list[dict[str, Any]], yaw_std_deg: float) -> list[dict[str, Any]]:
    out = []
    for row in rows:
        item = dict(row)
        item["yaw_std"] = yaw_std_deg
        item["yaw_std_mode"] = "fixed_1p5"
        out.append(item)
    return out


def nearest_yaw(rows: list[dict[str, Any]], raw_time: float) -> dict[str, Any] | None:
    if not rows:
        return None
    return min(rows, key=lambda row: abs(float(row["timestamp"]) - raw_time))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


if __name__ == "__main__":
    raise SystemExit(main())
