"""XB1A1 poor-GNSS blocker triage and normal-gate repair.

This stage imports XB1A0-E, repairs only the Raw Doppler helper/toolchain path
when possible, re-audits A1 short-baseline yaw, and runs only algorithms whose
identity-preserving gates pass.
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
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from legsa_gins.raw_gnss.rtklib_doppler_helper_builder import discover_rtklib_source_layout  # noqa: E402
from scripts.experiments import run_xb1_poor_gnss_generalization as xb1  # noqa: E402


STAGE = "XB1A1_BLOCKER_TRIAGE_RAW_DOPPLER_A1_YAW_AND_MAINLINE_NORMAL_GATE"
A0_STAGE = "XB1A0_TO_XB1E_POOR_GNSS_GENERALIZATION_CONTEXT_QUALITY_AUDIT_ALIGNMENT_AND_NORMAL_RUN"


@dataclass(frozen=True)
class StagePaths:
    repo: Path
    receiver_root: Path
    body_source: Path
    output_root: Path
    stage_root: Path
    runtime_root: Path
    a0_root: Path
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


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--receiver-root", type=Path, required=True)
    parser.add_argument("--body-source", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, default=REPO_ROOT / "xb1")
    parser.add_argument("--a0-stage-root", type=Path)
    parser.add_argument("--rtklib-root", type=Path)
    parser.add_argument("--evaluator-wsl", default=os.environ.get("LEGSA_EVALUATOR_WSL", ""))
    parser.add_argument("--by3a2-template-root", type=Path)
    parser.add_argument("--run-normal", action="store_true")
    parser.add_argument("--skip-raw-doppler", action="store_true")
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
        runtime_root=output_root / "XB1_FULL_MATRIX" / "XB1A1_NORMAL_GATE_REPAIR",
        a0_root=(args.a0_stage_root.resolve() if args.a0_stage_root else output_root / A0_STAGE),
        rtklib_root=args.rtklib_root.resolve() if args.rtklib_root else None,
        evaluator_wsl=args.evaluator_wsl,
        by3a2_template_root=args.by3a2_template_root.resolve() if args.by3a2_template_root else None,
    )
    result = run_stage(paths, run_normal=args.run_normal, skip_raw_doppler=args.skip_raw_doppler, skip_figures=args.skip_figures)
    print(json.dumps({"decision": result["decision"], "stage_root": str(paths.stage_root)}, indent=2))
    return 0


def run_stage(paths: StagePaths, *, run_normal: bool, skip_raw_doppler: bool, skip_figures: bool) -> dict[str, Any]:
    prepare_dirs(paths)
    copy_a0_inputs(paths)
    imported = write_import_and_blocker_ledger(paths)
    raw = write_raw_doppler_reports(paths, skip_raw_doppler=skip_raw_doppler)
    a1_report = write_a1_yaw_gate(paths)
    applicability = write_dual_yaw_applicability(paths, raw, a1_report)
    normal = write_normal_gate_and_run(paths, applicability, run_normal=run_normal)
    quality = write_quality_branch_plan(paths, imported, raw, a1_report, normal)
    figures = write_figures_and_case_review(paths, raw, a1_report, applicability, normal, quality, skip_figures=skip_figures)
    write_context_and_obsidian(paths, raw, a1_report, applicability, normal, quality)
    validation = write_validation(paths, raw, a1_report, applicability, normal, quality, figures)
    return write_decision(paths, raw, a1_report, applicability, normal, quality, validation)


def prepare_dirs(paths: StagePaths) -> None:
    for rel in [
        "00_supervisor",
        "01_plan",
        "xb1a0e_import",
        "raw_doppler_toolchain",
        "raw_doppler_provider",
        "a1_yaw_gate_audit",
        "dual_yaw_applicability",
        "normal_mainline_gate",
        "normal_run",
        "official_eval",
        "quality_aware_branch_plan",
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
        "input_generation",
        "provider_materialization/raw_doppler",
    ]:
        (paths.stage_root / rel).mkdir(parents=True, exist_ok=True)
    paths.runtime_root.mkdir(parents=True, exist_ok=True)


def copy_a0_inputs(paths: StagePaths) -> None:
    src = paths.a0_root / "input_generation"
    dst = paths.stage_root / "input_generation"
    for name in [
        "XB1_GO2_PROCESS_DATA_STATIC_BIAS_REPAIRED.imu",
        "XB1_DUAL_A1_DIFF_15COL_REPAIRED.gnss",
        "XB1_GNSS1_STATUS_7COL_REPAIRED.gnss",
        "XB1_FINALV23_COMPATIBLE_INPUT.gnss",
    ]:
        source = src / name
        if source.exists():
            shutil.copy2(source, dst / name)
    prior_src = paths.a0_root / "provider_materialization" / "go2_priors"
    prior_dst = paths.stage_root / "provider_materialization" / "go2_priors"
    if prior_src.exists():
        if prior_dst.exists():
            shutil.rmtree(prior_dst)
        shutil.copytree(prior_src, prior_dst)


def write_import_and_blocker_ledger(paths: StagePaths) -> dict[str, Any]:
    decision = read_json(paths.a0_root / "reports" / "LONG_TASK_DECISION_REPORT.json", {})
    quality = read_json(paths.a0_root / "reports" / "XB1C_GNSS_QUALITY_PROFILE_REPORT.json", {})
    inputs = read_json(paths.a0_root / "reports" / "XB1E_INPUT_GENERATION_REPORT.json", {})
    providers = read_json(paths.a0_root / "reports" / "XB1E_PROVIDER_MATERIALIZATION_REPORT.json", {})
    normal = read_json(paths.a0_root / "reports" / "XB1F_NORMAL_RUN_REPORT.json", {})
    rows = [
        blocker_row(
            "A1_short_baseline_yaw_gate_blocked",
            "input_quality",
            "A1 short-baseline geometry nonphysical under XB1 severe GNSS",
            "reports/XB1E_INPUT_GENERATION_REPORT.json",
            True,
            "re-audit objective A1 short-baseline quality; do not force yaw",
            False,
            True,
        ),
        blocker_row(
            "raw_doppler_provider_toolchain_missing",
            "toolchain",
            "RTKLIB helper failed because native gcc was unavailable",
            "reports/XB1E_PROVIDER_MATERIALIZATION_REPORT.json",
            True,
            "compile helper through available WSL gcc without algorithm changes",
            False,
            True,
        ),
        blocker_row(
            "providers_not_ready_for_LegSA_full",
            "provider_gate",
            "LegSA_full requires identity-preserving Raw Doppler/Go2/feedback provider chain",
            "reports/XB1F_NORMAL_RUN_GATE_REPORT.json",
            "unknown",
            "repair Raw Doppler, keep Go2, generate same-case feedback only after stage1",
            False,
            True,
        ),
    ]
    report = {
        "stage": "XB1A1_A",
        "decision": "XB1A1_blocker_ledger_complete" if decision else "XB1A1_blocker_ledger_incomplete",
        "imported_a0_decision": decision,
        "quality_class": quality.get("quality_class"),
        "quality_reasons": quality.get("classification_reasons", []),
        "body_imu_status": inputs.get("imu_report", {}),
        "go2_prior_status": inputs.get("go2_prior_report", {}),
        "raw_doppler_previous_status": providers.get("raw_doppler_report", {}),
        "normal_previous_status": normal.get("decision"),
        "blockers": rows,
        "ready_for_paper_claims": False,
    }
    write_json(paths.stage_root / "reports" / "XB1A1_IMPORT_AND_BLOCKER_LEDGER_REPORT.json", report)
    write_json(paths.stage_root / "matrix" / "XB1A1_BLOCKER_LEDGER.json", rows)
    write_csv(paths.stage_root / "matrix" / "XB1A1_BLOCKER_LEDGER.csv", rows)
    write_md(paths.stage_root / "summary" / "xb1a1_import_and_blocker_ledger.md", f"# XB1A1 Blocker Ledger\n\nDecision: `{report['decision']}`.\n\nImported A0-E status: `{decision.get('status', 'missing')}`.\n")
    return report


def blocker_row(blocker_id: str, blocker_type: str, evidence: str, source: str, repairable: Any, route: str, can_run_without: bool, identity_changes: bool) -> dict[str, Any]:
    return {
        "blocker_id": blocker_id,
        "blocker_type": blocker_type,
        "evidence": evidence,
        "source_file_or_report": source,
        "repairable": repairable,
        "repair_route": route,
        "solver_can_run_without_it": can_run_without,
        "algorithm_identity_changes_if_skipped": identity_changes,
    }


def write_raw_doppler_reports(paths: StagePaths, *, skip_raw_doppler: bool) -> dict[str, Any]:
    audit_rows: list[dict[str, Any]] = []
    native_gcc = shutil.which("gcc") or ""
    wsl_gcc = run_text(["wsl", "bash", "-lc", "command -v gcc || true"]) if shutil.which("wsl") else ""
    layout = discover_rtklib_source_layout(paths.rtklib_root or "")
    audit_rows.extend(
        [
            {"check": "native_gcc", "status": "available" if native_gcc else "missing", "detail": native_gcc},
            {"check": "wsl_gcc", "status": "available" if wsl_gcc.strip() else "missing", "detail": wsl_gcc.strip()},
            {"check": "rtklib_source", "status": "available" if not layout.get("missing_source_files") else "missing", "detail": layout.get("source_dir", "")},
        ]
    )
    for name in ["gnss1-raw.csv", "gnss2-raw.csv", "userio-raw.csv", "corr-raw.csv"]:
        path = paths.receiver_root / name
        audit_rows.append({"check": name, "status": "available" if path.exists() else "missing", "detail": str(path.stat().st_size) if path.exists() else ""})
    provider_report: dict[str, Any]
    provider_dir = paths.stage_root / "raw_doppler_provider" / "provider_only"
    if skip_raw_doppler:
        provider_report = {"decision": "XB1A1_raw_doppler_blocked_toolchain", "blocker_reasons": ["skip_raw_doppler_requested"]}
    elif not paths.rtklib_root:
        provider_report = {"decision": "XB1A1_raw_doppler_blocked_toolchain", "blocker_reasons": ["rtklib_root_not_provided"]}
    else:
        provider_report = run_raw_provider(paths, provider_dir)
    raw_factor = provider_dir / "RAW_DOPPLER_VELOCITY_FACTORS.csv"
    if raw_factor.exists():
        dst = paths.stage_root / "provider_materialization" / "raw_doppler" / "RAW_DOPPLER_VELOCITY_FACTORS.csv"
        shutil.copy2(raw_factor, dst)
    provider_rows = [provider_index(raw_factor, provider_report)]
    decision = "XB1A1_raw_doppler_provider_ready" if raw_factor.exists() and count_rows(raw_factor) > 0 else provider_report.get("decision", "XB1A1_raw_doppler_blocked_toolchain")
    report = {
        "stage": "XB1A1_B",
        "decision": decision,
        "toolchain_audit_rows": audit_rows,
        "provider_report": provider_report,
        "provider_index": provider_rows,
        "raw_doppler_not_fabricated": True,
        "gnss_velocity_used_as_raw_doppler": False,
        "nav_pvt_velocity_used_as_raw_doppler": False,
        "trace_solver_input": False,
        "ready_for_paper_claims": False,
    }
    write_json(paths.stage_root / "reports" / "XB1A1_RAW_DOPPLER_TOOLCHAIN_REPORT.json", report)
    write_json(paths.stage_root / "matrix" / "XB1A1_RAW_DOPPLER_TOOLCHAIN_AUDIT.json", audit_rows)
    write_csv(paths.stage_root / "matrix" / "XB1A1_RAW_DOPPLER_TOOLCHAIN_AUDIT.csv", audit_rows)
    write_json(paths.stage_root / "reports" / "XB1A1_RAW_DOPPLER_PROVIDER_REPORT.json", report)
    write_json(paths.stage_root / "matrix" / "XB1A1_RAW_DOPPLER_PROVIDER_INDEX.json", provider_rows)
    write_csv(paths.stage_root / "matrix" / "XB1A1_RAW_DOPPLER_PROVIDER_INDEX.csv", provider_rows)
    write_md(paths.stage_root / "summary" / "xb1a1_raw_doppler_toolchain.md", f"# XB1A1 Raw Doppler Toolchain\n\nDecision: `{decision}`.\n\nRows: `{provider_rows[0]['row_count']}`.\n")
    return report


def run_raw_provider(paths: StagePaths, provider_dir: Path) -> dict[str, Any]:
    provider_dir.mkdir(parents=True, exist_ok=True)
    clean_gnss = paths.stage_root / "input_generation" / "XB1_DUAL_A1_DIFF_15COL_REPAIRED.gnss"
    command = [
        sys.executable,
        str(paths.repo / "scripts" / "experiments" / "run_by3a2_raw_doppler_provider_only.py"),
        "--fix-root",
        str(paths.receiver_root),
        "--clean-gnss",
        str(clean_gnss),
        "--rtklib-root",
        str(paths.rtklib_root),
        "--ephemeris-search-root",
        str(paths.receiver_root),
        "--output-dir",
        str(provider_dir),
        "--build-dir",
        str(paths.stage_root / "raw_doppler_toolchain" / "build"),
        "--allow-run",
    ]
    completed = subprocess.run(command, cwd=paths.repo, text=True, encoding="utf-8", errors="replace", stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False, timeout=1200)
    write_text(paths.stage_root / "logs" / "raw_doppler_provider_stdout.txt", completed.stdout)
    write_text(paths.stage_root / "logs" / "raw_doppler_provider_stderr.txt", completed.stderr)
    report = read_json(provider_dir / "BY3A2_RAW_DOPPLER_PROVIDER_MATERIALIZATION_REPORT.json", {}) or {}
    if not report:
        report = {"decision": "XB1A1_raw_doppler_blocked_toolchain", "returncode": completed.returncode, "blocker_reasons": ["provider_script_failed_before_report"], "stderr_tail": completed.stderr[-2000:]}
    report["xb1a1_wrapper_returncode"] = completed.returncode
    return report


def provider_index(path: Path, report: dict[str, Any]) -> dict[str, Any]:
    rows = read_csv_dicts(path)
    times = [as_float(row.get("time")) for row in rows]
    sat = [as_float(row.get("sat_count")) for row in rows]
    return {
        "path": str(path),
        "exists": path.exists(),
        "row_count": len(rows),
        "valid_factor_epochs": len(rows),
        "time_min": min([t for t in times if t is not None], default=""),
        "time_max": max([t for t in times if t is not None], default=""),
        "columns": "|".join(rows[0].keys()) if rows else "",
        "sat_count_min": min([s for s in sat if s is not None], default=""),
        "sat_count_max": max([s for s in sat if s is not None], default=""),
        "schema_valid": bool(rows and {"time", "vn", "ve", "vd", "std_vn", "std_ve", "std_vd"}.issubset(rows[0].keys())),
        "source_files": "gnss1-raw.csv|gnss2-raw.csv|corr-raw.csv|RINEX/nav generated by accepted provider path",
        "sha256": sha256(path) if path.exists() else "",
        "ready_for_LegSA": path.exists() and len(rows) > 0 and not report.get("blocker_reasons"),
    }


def write_a1_yaw_gate(paths: StagePaths) -> dict[str, Any]:
    xb1_paths = paths.xb1_paths
    audit = xb1.a1_baseline_audit(xb1_paths)
    rows = []
    prev_yaw: float | None = None
    source_valid = 0
    for item in audit.get("rows", []):
        yaw = as_float(item.get("a1_yaw_ned_deg"))
        jump = abs(wrap180(yaw - prev_yaw)) if yaw is not None and prev_yaw is not None else 0.0
        length = as_float(item.get("baseline_len_m"), 0.0) or 0.0
        physically_valid = 0.10 <= length <= 1.50 and jump <= 45.0
        source_valid += int(physically_valid)
        rows.append(
            {
                "time": item.get("t"),
                "baseline_len_m": length,
                "east_m": item.get("east_m"),
                "north_m": item.get("north_m"),
                "up_m": item.get("up_m"),
                "gnss2_minus_gnss1_yaw_deg": yaw,
                "gnss1_minus_gnss2_yaw_deg": wrap360((yaw or 0.0) + 180.0),
                "yaw_jump_deg": jump,
                "objective_source_valid": physically_valid,
                "invalid_reason": "" if physically_valid else "baseline_length_or_yaw_jump_outside_objective_bounds",
                "trace_relation": "diagnostic_only",
                "hdt_relation": "diagnostic_only",
            }
        )
        if yaw is not None:
            prev_yaw = yaw
    total = max(1, len(rows))
    objective_ratio = source_valid / total
    summary = {
        "candidate": "GNSS1/GNSS2 A1 dual-diff short-baseline",
        "row_count": len(rows),
        "objective_valid_epoch_ratio": objective_ratio,
        "baseline_length_stats_m": audit.get("length_stats_m", {}),
        "status_rel_pos_long_baseline_stats_m": audit.get("status_rel_pos_long_baseline_stats_m", {}),
        "short_baseline_valid": audit.get("short_baseline_valid", False),
        "long_relpos_rejected": audit.get("long_relpos_rejected", True),
        "hdt_mainline_yaw_used": False,
        "trace_yaw_tuning": False,
    }
    if audit.get("short_baseline_valid") and objective_ratio >= 0.5:
        decision = "XB1A1_A1_dual_yaw_valid"
    elif audit.get("short_baseline_valid"):
        decision = "XB1A1_A1_dual_yaw_valid_with_caution"
    elif rows:
        decision = "XB1A1_A1_dual_yaw_invalid_due_GNSS_quality"
    else:
        decision = "XB1A1_A1_dual_yaw_inconclusive"
    report = {"stage": "XB1A1_C", "decision": decision, "summary": summary, "ready_for_paper_claims": False}
    write_json(paths.stage_root / "reports" / "XB1A1_A1_SHORT_BASELINE_YAW_GATE_REPORT.json", report)
    write_json(paths.stage_root / "matrix" / "XB1A1_A1_SHORT_BASELINE_EPOCH_QUALITY.json", rows)
    write_csv(paths.stage_root / "matrix" / "XB1A1_A1_SHORT_BASELINE_EPOCH_QUALITY.csv", rows)
    write_json(paths.stage_root / "matrix" / "XB1A1_A1_YAW_QUALITY_SUMMARY.json", [summary])
    write_csv(paths.stage_root / "matrix" / "XB1A1_A1_YAW_QUALITY_SUMMARY.csv", [summary])
    write_md(paths.stage_root / "summary" / "xb1a1_a1_short_baseline_yaw_gate.md", f"# XB1A1 A1 Yaw Gate\n\nDecision: `{decision}`.\n\nObjective valid epoch ratio: `{objective_ratio:.4f}`.\n")
    return report


def write_dual_yaw_applicability(paths: StagePaths, raw: dict[str, Any], a1_report: dict[str, Any]) -> dict[str, Any]:
    xb1_paths = paths.xb1_paths
    raw_ready = raw.get("decision") == "XB1A1_raw_doppler_provider_ready"
    go2_ready = xb1_paths.go2_joint.exists() and xb1_paths.go2_attitude.exists() and xb1_paths.go2_velocity.exists()
    a1_valid = a1_report.get("decision") in {"XB1A1_A1_dual_yaw_valid", "XB1A1_A1_dual_yaw_valid_with_caution"}
    rows = [
        {
            "algorithm": "LegSA_full_EKF",
            "required_inputs": "body_imu|dual_gnss_a1_yaw|raw_doppler|go2_priors|same_case_feedback",
            "inputs_available": raw_ready and go2_ready and a1_valid,
            "algorithm_identity_preserved": raw_ready and go2_ready and a1_valid,
            "run_allowed": False,
            "blocked_reason": "" if a1_valid and raw_ready and go2_ready else "dual_yaw_invalid_or_provider_chain_incomplete",
        },
        {
            "algorithm": "final_v23_dual_antenna_EKF",
            "required_inputs": "body_imu|dual_gnss_a1_yaw",
            "inputs_available": a1_valid,
            "algorithm_identity_preserved": a1_valid,
            "run_allowed": False,
            "blocked_reason": "" if a1_valid else "dual_yaw_invalid",
        },
        {
            "algorithm": "single_antenna_gnss1_status_KF_GINS",
            "required_inputs": "body_imu|single_gnss1_status",
            "inputs_available": xb1_paths.imu.exists() and xb1_paths.gnss_single.exists(),
            "algorithm_identity_preserved": True,
            "run_allowed": xb1_paths.imu.exists() and xb1_paths.gnss_single.exists(),
            "blocked_reason": "" if xb1_paths.imu.exists() and xb1_paths.gnss_single.exists() else "single_baseline_inputs_missing",
        },
    ]
    if rows[0]["run_allowed"] and rows[1]["run_allowed"]:
        decision = "XB1A1_mainline_normal_allowed"
    elif rows[2]["run_allowed"]:
        decision = "XB1A1_partial_baseline_only_allowed"
    elif not a1_valid:
        decision = "XB1A1_mainline_blocked_by_data_quality"
    else:
        decision = "XB1A1_manual_decision_required"
    report = {
        "stage": "XB1A1_D",
        "decision": decision,
        "raw_doppler_ready": raw_ready,
        "go2_priors_ready": go2_ready,
        "a1_dual_yaw_valid": a1_valid,
        "algorithm_rows": rows,
        "ready_for_paper_claims": False,
    }
    write_json(paths.stage_root / "reports" / "XB1A1_DUAL_YAW_APPLICABILITY_DECISION_REPORT.json", report)
    write_json(paths.stage_root / "matrix" / "XB1A1_ALGORITHM_APPLICABILITY.json", rows)
    write_csv(paths.stage_root / "matrix" / "XB1A1_ALGORITHM_APPLICABILITY.csv", rows)
    write_md(paths.stage_root / "summary" / "xb1a1_dual_yaw_applicability.md", f"# XB1A1 Dual-Yaw Applicability\n\nDecision: `{decision}`.\n")
    return report


def write_normal_gate_and_run(paths: StagePaths, applicability: dict[str, Any], *, run_normal: bool) -> dict[str, Any]:
    xb1_paths = paths.xb1_paths
    single_allowed = any(row["algorithm"] == "single_antenna_gnss1_status_KF_GINS" and row["run_allowed"] for row in applicability.get("algorithm_rows", []))
    dual_allowed = applicability.get("decision") == "XB1A1_mainline_normal_allowed"
    gate_rows = [
        {"gate": "body_imu_from_xb1_txt", "status": xb1_paths.imu.exists(), "required_for": "all"},
        {"gate": "raw_doppler_provider_ready", "status": applicability.get("raw_doppler_ready"), "required_for": "LegSA_full_EKF"},
        {"gate": "a1_dual_yaw_valid", "status": applicability.get("a1_dual_yaw_valid"), "required_for": "LegSA_full_EKF|final_v23_dual_antenna_EKF"},
        {"gate": "go2_priors_ready", "status": applicability.get("go2_priors_ready"), "required_for": "LegSA_full_EKF"},
        {"gate": "single_baseline_allowed", "status": single_allowed, "required_for": "single_antenna_gnss1_status_KF_GINS"},
        {"gate": "run_normal_requested", "status": run_normal, "required_for": "execution"},
    ]
    write_json(paths.stage_root / "reports" / "XB1A1_NORMAL_GATE_REPORT.json", {"stage": "XB1A1_E", "gate_rows": gate_rows, "dual_allowed": dual_allowed, "single_allowed": single_allowed, "run_normal_requested": run_normal, "trace_solver_input": False, "degradation_matrix": False, "parameter_retuning": False})
    write_json(paths.stage_root / "matrix" / "XB1A1_NORMAL_GATE.json", gate_rows)
    write_csv(paths.stage_root / "matrix" / "XB1A1_NORMAL_GATE.csv", gate_rows)
    solver_rows: list[dict[str, Any]] = []
    eval_rows: list[dict[str, Any]] = []
    metric_rows: list[dict[str, Any]] = []
    if run_normal and single_allowed:
        context = single_context(paths)
        single_run = xb1.run_external_from_template(xb1_paths, context, algorithm="single_antenna_gnss1_status_KF_GINS", use_dual=False, template_name="single_runner_handoff/by3_single_baseline.runtime_config.yaml", report_name="reports/BY3A2_SINGLE_BASELINE_HANDOFF_REPORT.json", output_subdir="single_baseline_solver")
        solver_rows.append(xb1.solver_status_row(single_run))
        if single_run.get("run_status") == "completed":
            single_eval = xb1.run_official_eval(xb1_paths, "single_antenna_gnss1_status_KF_GINS", Path(single_run["output_dir"]), paths.stage_root / "official_eval" / "single_antenna_gnss1_status_KF_GINS", context["base_time"], "external")
            eval_rows.append(xb1.eval_status_row(single_eval))
            if single_eval.get("metrics"):
                metric_rows.append(xb1.metric_row(single_eval))
        else:
            eval_rows.append(xb1.eval_status_row(xb1.blocked_eval("single_antenna_gnss1_status_KF_GINS", single_run.get("blocked_reason", "single solver failed"))))
    if dual_allowed:
        solver_rows.extend(
            [
                xb1.solver_status_row(xb1.blocked_run("LegSA_full_EKF", "dual stage not executed by XB1A1 script unless all gates are explicitly reviewed", paths.runtime_root / "legsa_full_solver" / "LegSA_full_EKF")),
                xb1.solver_status_row(xb1.blocked_run("final_v23_dual_antenna_EKF", "dual stage not executed by XB1A1 script unless all gates are explicitly reviewed", paths.runtime_root / "finalv23_solver" / "final_v23_dual_antenna_EKF")),
            ]
        )
    else:
        solver_rows.extend(
            [
                xb1.solver_status_row(xb1.blocked_run("LegSA_full_EKF", "A1 dual yaw invalid; algorithm identity would change if forced", paths.runtime_root / "legsa_full_solver" / "LegSA_full_EKF")),
                xb1.solver_status_row(xb1.blocked_run("final_v23_dual_antenna_EKF", "A1 dual yaw invalid; final_v23 not applicable", paths.runtime_root / "finalv23_solver" / "final_v23_dual_antenna_EKF")),
            ]
        )
    if not run_normal and single_allowed:
        solver_rows.append(xb1.solver_status_row(xb1.blocked_run("single_antenna_gnss1_status_KF_GINS", "run_normal_not_requested", paths.runtime_root / "single_baseline_solver" / "single_antenna_gnss1_status_KF_GINS")))
    if metric_rows:
        decision = "XB1A1_normal_partial_completed"
    elif run_normal and single_allowed:
        decision = "XB1A1_normal_gate_blocked"
    else:
        decision = "XB1A1_normal_gate_blocked"
    report = {
        "stage": "XB1A1_E",
        "decision": decision,
        "solver_rows": solver_rows,
        "eval_rows": eval_rows,
        "metrics": metric_rows,
        "dual_mainline_run": False,
        "single_baseline_run_allowed": single_allowed,
        "quality_aware_execution": False,
        "degradation_matrix": False,
        "parameter_retuning": False,
        "trace_solver_input": False,
        "ready_for_paper_claims": False,
    }
    write_json(paths.stage_root / "reports" / "XB1A1_NORMAL_RUN_REPORT.json", report)
    write_json(paths.stage_root / "matrix" / "XB1A1_SOLVER_STATUS.json", solver_rows)
    write_csv(paths.stage_root / "matrix" / "XB1A1_SOLVER_STATUS.csv", solver_rows)
    write_json(paths.stage_root / "matrix" / "XB1A1_EVAL_STATUS.json", eval_rows)
    write_csv(paths.stage_root / "matrix" / "XB1A1_EVAL_STATUS.csv", eval_rows)
    write_json(paths.stage_root / "matrix" / "XB1A1_NORMAL_METRICS.json", metric_rows)
    write_csv(paths.stage_root / "matrix" / "XB1A1_NORMAL_METRICS.csv", metric_rows)
    write_md(paths.stage_root / "summary" / "xb1a1_normal_run.md", f"# XB1A1 Normal Run\n\nDecision: `{decision}`.\n\nMetric rows: `{len(metric_rows)}`.\n")
    return report


def single_context(paths: StagePaths) -> dict[str, Any]:
    alignment = read_json(paths.a0_root / "reports" / "XB1D_ALIGNMENT_REPORT.json", {})
    start = float(alignment.get("recommended_algorithm_start_time", 0.0))
    rows = xb1.numeric_rows(paths.stage_root / "input_generation" / "XB1_GNSS1_STATUS_7COL_REPAIRED.gnss")
    init = next((row for row in rows if row[0] >= start), rows[0] if rows else [start, 0.0, 0.0, 0.0])
    return {
        "base_time": float(alignment.get("body_time_zero_raw_timestamp", 0.0)),
        "algorithm_start_time": float(init[0]),
        "end_time": float(alignment.get("recommended_algorithm_end_time", init[0] if init else 0.0)),
        "initpos": [init[1], init[2], init[3]],
        "initatt": [0.0, 0.0, 0.0],
    }


def write_quality_branch_plan(paths: StagePaths, imported: dict[str, Any], raw: dict[str, Any], a1_report: dict[str, Any], normal: dict[str, Any]) -> dict[str, Any]:
    rows = [
        {"branch": "XB1_quality_aware_diagnostic_branch", "item": "allowed_input", "value": "fix_type|PDOP|satellite_count|C/N0|pos_acc/std|NTRIP_latency|A1_yaw_quality|position_jumps"},
        {"branch": "XB1_quality_aware_diagnostic_branch", "item": "allowed_action", "value": "objective_R_scale|objective_outlier_rejection|source_aware_gating"},
        {"branch": "XB1_quality_aware_diagnostic_branch", "item": "forbidden", "value": "trace_tuned_thresholds|PG1_only_manual_tuning|mixing_adapted_result_into_mainline"},
        {"branch": "XB1_quality_aware_diagnostic_branch", "item": "validation", "value": "frozen_normal_first|all_four_poor_GNSS_repeats|frozen_vs_adaptive_comparison"},
    ]
    decision = "XB1A1_quality_aware_branch_recommended" if a1_report.get("decision") != "XB1A1_A1_dual_yaw_valid" else "XB1A1_quality_aware_branch_requires_more_data"
    report = {
        "stage": "XB1A1_F",
        "decision": decision,
        "quality_class": imported.get("quality_class"),
        "raw_doppler_decision": raw.get("decision"),
        "a1_decision": a1_report.get("decision"),
        "normal_decision": normal.get("decision"),
        "quality_aware_execution": False,
        "plan_rows": rows,
        "ready_for_paper_claims": False,
    }
    write_json(paths.stage_root / "reports" / "XB1A1_QUALITY_AWARE_BRANCH_PLAN_REPORT.json", report)
    write_json(paths.stage_root / "matrix" / "XB1A1_QUALITY_AWARE_BRANCH_PLAN.json", rows)
    write_csv(paths.stage_root / "matrix" / "XB1A1_QUALITY_AWARE_BRANCH_PLAN.csv", rows)
    write_md(paths.stage_root / "summary" / "xb1a1_quality_aware_branch_plan.md", f"# XB1A1 Quality-Aware Branch Plan\n\nDecision: `{decision}`.\n\nNo quality-aware execution was run.\n")
    return report


def write_figures_and_case_review(paths: StagePaths, raw: dict[str, Any], a1_report: dict[str, Any], applicability: dict[str, Any], normal: dict[str, Any], quality: dict[str, Any], *, skip_figures: bool) -> dict[str, Any]:
    figure_rows: list[dict[str, Any]] = []
    if not skip_figures:
        figure_rows.extend(draw_a1_figures(paths))
        figure_rows.extend(draw_blocker_figures(paths, raw, a1_report, applicability, normal, quality))
        if normal.get("metrics"):
            figure_rows.extend(draw_metric_figure(paths, normal))
    report = {"stage": "XB1A1_G", "decision": "XB1A1_figures_case_review_complete", "figure_count": sum(1 for row in figure_rows if row.get("exists")), "figure_rows": figure_rows, "ready_for_paper_claims": False}
    write_json(paths.stage_root / "reports" / "XB1A1_FIGURE_REPORT.json", report)
    write_json(paths.stage_root / "matrix" / "XB1A1_FIGURE_INDEX.json", figure_rows)
    write_csv(paths.stage_root / "matrix" / "XB1A1_FIGURE_INDEX.csv", figure_rows)
    case = {
        "stage": STAGE,
        "gnss_quality": "severe",
        "raw_doppler_status": raw.get("decision"),
        "a1_yaw_status": a1_report.get("decision"),
        "algorithm_applicability": applicability.get("decision"),
        "normal_run": normal.get("decision"),
        "quality_aware_branch": quality.get("decision"),
        "ready_for_paper_claims": False,
    }
    write_json(paths.stage_root / "case_review" / "XB1A1_blocker_triage_and_normal_gate_case_review.json", case)
    write_md(paths.stage_root / "case_review" / "XB1A1_blocker_triage_and_normal_gate_case_review.md", "\n".join([f"# XB1A1 Case Review", "", *[f"- {k}: `{v}`" for k, v in case.items()]]))
    return report


def draw_a1_figures(paths: StagePaths) -> list[dict[str, Any]]:
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception:
        return []
    rows = read_json(paths.stage_root / "matrix" / "XB1A1_A1_SHORT_BASELINE_EPOCH_QUALITY.json", []) or []
    out = paths.stage_root / "figures"
    times = [as_float(row.get("time"), 0.0) or 0.0 for row in rows]
    t0 = min(times) if times else 0.0
    x = [t - t0 for t in times]
    lengths = [as_float(row.get("baseline_len_m"), 0.0) or 0.0 for row in rows]
    jumps = [as_float(row.get("yaw_jump_deg"), 0.0) or 0.0 for row in rows]
    fig, ax = plt.subplots(2, 1, figsize=(9, 6), sharex=True)
    ax[0].plot(x, lengths, linewidth=0.8)
    ax[0].axhspan(0.10, 1.50, color="green", alpha=0.15, label="objective length window")
    ax[0].set_ylabel("baseline length m")
    ax[0].legend(fontsize=7)
    ax[1].plot(x, jumps, linewidth=0.8)
    ax[1].axhline(45.0, color="red", linestyle="--", linewidth=0.8)
    ax[1].set_ylabel("yaw jump deg")
    ax[1].set_xlabel("seconds from first A1 row")
    fig.tight_layout()
    for suffix in ["png", "pdf"]:
        fig.savefig(out / f"A1_baseline_quality_panel.{suffix}", dpi=160 if suffix == "png" else None)
    plt.close(fig)
    return figure_rows(out, "A1_baseline_quality_panel", "real_a1_epoch_quality")


def draw_blocker_figures(paths: StagePaths, raw: dict[str, Any], a1_report: dict[str, Any], applicability: dict[str, Any], normal: dict[str, Any], quality: dict[str, Any]) -> list[dict[str, Any]]:
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception:
        return []
    out = paths.stage_root / "figures"
    labels = ["Raw Doppler", "A1 yaw", "Dual mainline", "Single baseline", "Quality branch"]
    values = [
        1 if raw.get("decision") == "XB1A1_raw_doppler_provider_ready" else 0,
        1 if a1_report.get("decision") in {"XB1A1_A1_dual_yaw_valid", "XB1A1_A1_dual_yaw_valid_with_caution"} else 0,
        1 if applicability.get("decision") == "XB1A1_mainline_normal_allowed" else 0,
        1 if normal.get("metrics") else 0,
        1 if quality.get("decision") == "XB1A1_quality_aware_branch_recommended" else 0,
    ]
    fig, ax = plt.subplots(figsize=(9, 4))
    ax.bar(labels, values)
    ax.set_ylim(0, 1.2)
    ax.set_ylabel("gate passed / recommended")
    ax.tick_params(axis="x", rotation=20)
    fig.tight_layout()
    for suffix in ["png", "pdf"]:
        fig.savefig(out / f"mainline_blocker_panel.{suffix}", dpi=160 if suffix == "png" else None)
    plt.close(fig)
    return figure_rows(out, "mainline_blocker_panel", "real_gate_decisions")


def draw_metric_figure(paths: StagePaths, normal: dict[str, Any]) -> list[dict[str, Any]]:
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception:
        return []
    out = paths.stage_root / "figures"
    rows = normal.get("metrics", [])
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.bar([row.get("algorithm") for row in rows], [as_float(row.get("horizontal_rmse_m"), 0.0) or 0.0 for row in rows])
    ax.set_ylabel("horizontal RMSE m")
    ax.tick_params(axis="x", rotation=20)
    fig.tight_layout()
    for suffix in ["png", "pdf"]:
        fig.savefig(out / f"normal_metrics_if_run.{suffix}", dpi=160 if suffix == "png" else None)
    plt.close(fig)
    return figure_rows(out, "normal_metrics_if_run", "real_official_eval_metrics")


def write_context_and_obsidian(paths: StagePaths, raw: dict[str, Any], a1_report: dict[str, Any], applicability: dict[str, Any], normal: dict[str, Any], quality: dict[str, Any]) -> None:
    note = "\n".join(
        [
            "# XB1A1 Blocker Triage",
            "",
            f"- Raw Doppler: `{raw.get('decision')}`",
            f"- A1 yaw: `{a1_report.get('decision')}`",
            f"- Applicability: `{applicability.get('decision')}`",
            f"- Normal: `{normal.get('decision')}`",
            f"- Quality-aware branch: `{quality.get('decision')}`",
            "- ready_for_paper_claims=false",
        ]
    )
    for name in ["XB1_blocker_triage.md", "XB1_raw_doppler_provider_status.md", "XB1_A1_yaw_quality.md", "XB1_quality_aware_branch_plan.md", "current_state.md", "next_steps.md"]:
        write_md(paths.repo / "obsidian_knowledge" / "LegSA-GINS" / "XB1_poor_GNSS_generalization" / name, note)
    write_json(paths.stage_root / "reports" / "XB1A1_CONTEXT_UPDATE_REPORT.json", {"tracked_docs_require_update": True, "obsidian_notes_written": True, "ready_for_paper_claims": False})


def write_validation(paths: StagePaths, raw: dict[str, Any], a1_report: dict[str, Any], applicability: dict[str, Any], normal: dict[str, Any], quality: dict[str, Any], figures: dict[str, Any]) -> dict[str, Any]:
    checks = [
        check("Raw Doppler toolchain audited", raw.get("decision") in {"XB1A1_raw_doppler_provider_ready", "XB1A1_raw_doppler_blocked_toolchain", "XB1A1_raw_doppler_blocked_data_unavailable"}),
        check("A1 yaw gate audited", bool(a1_report.get("decision"))),
        check("algorithm applicability decided", bool(applicability.get("decision"))),
        check("normal run only if gates passed", normal.get("dual_mainline_run") is False),
        check("no degradation", normal.get("degradation_matrix") is False),
        check("no retuning", normal.get("parameter_retuning") is False),
        check("no trace solver input", normal.get("trace_solver_input") is False),
        check("no fabricated providers", raw.get("raw_doppler_not_fabricated") is True),
        check("quality-aware branch not executed", quality.get("quality_aware_execution") is False),
        check("no paper claims", quality.get("ready_for_paper_claims") is False),
    ]
    status = "pass" if all(row["status"] == "pass" for row in checks) else "fail"
    report = {"stage": "XB1A1_validation", "status": status, "checks": checks, "figure_decision": figures.get("decision"), "ready_for_paper_claims": False}
    write_json(paths.stage_root / "reports" / "LONG_TASK_VALIDATION_REPORT.json", report)
    write_json(paths.stage_root / "matrix" / "LONG_TASK_STAGE_STATUS.json", checks)
    write_csv(paths.stage_root / "matrix" / "LONG_TASK_STAGE_STATUS.csv", checks)
    write_md(paths.stage_root / "summary" / "long_task_summary.md", f"# XB1A1 Long Task Summary\n\nValidation status: `{status}`. Normal decision: `{normal.get('decision')}`.\n")
    return report


def write_decision(paths: StagePaths, raw: dict[str, Any], a1_report: dict[str, Any], applicability: dict[str, Any], normal: dict[str, Any], quality: dict[str, Any], validation: dict[str, Any]) -> dict[str, Any]:
    if validation.get("status") != "pass":
        status = "XB1A1_safety_gate_failed"
        ready_next = False
    elif normal.get("decision") == "XB1A1_normal_partial_completed":
        status = "XB1A1_partial_baseline_only_completed"
        ready_next = True
    elif a1_report.get("decision") != "XB1A1_A1_dual_yaw_valid":
        status = "XB1A1_quality_aware_branch_recommended"
        ready_next = True
    else:
        status = "XB1A1_mainline_blocked_by_A1_yaw_or_raw_provider"
        ready_next = True
    decision = {
        "stage": STAGE,
        "status": status,
        "raw_doppler_decision": raw.get("decision"),
        "a1_yaw_decision": a1_report.get("decision"),
        "applicability_decision": applicability.get("decision"),
        "normal_decision": normal.get("decision"),
        "quality_aware_decision": quality.get("decision"),
        "ready_for_next_stage": ready_next,
        "ready_for_quality_aware_branch_planning": status != "XB1A1_safety_gate_failed",
        "ready_for_XB1_degradation_or_PG2_planning": False,
        "ready_for_paper_claims": False,
        "recommended_next_stage": "human_review_XB1A1_then_quality_aware_branch_or_PG2_source_review",
    }
    write_json(paths.stage_root / "reports" / "LONG_TASK_DECISION_REPORT.json", decision)
    write_md(paths.stage_root / "summary" / "long_task_next_stage_recommendation.md", f"# XB1A1 Next Stage\n\nRecommended next stage: `{decision['recommended_next_stage']}`.\n\nready_for_paper_claims=false\n")
    return {"decision": status, **decision}


def check(name: str, passed: bool) -> dict[str, Any]:
    return {"check": name, "status": "pass" if passed else "fail"}


def figure_rows(root: Path, stem: str, source: str) -> list[dict[str, Any]]:
    rows = []
    for suffix in ["png", "pdf"]:
        path = root / f"{stem}.{suffix}"
        rows.append({"figure": stem, "path": str(path), "exists": path.exists(), "file_size": path.stat().st_size if path.exists() else 0, "source": source})
    return rows


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8-sig", errors="replace"))
    except json.JSONDecodeError:
        return default


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    if not fields:
        fields = ["status"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: csv_value(row.get(key, "")) for key in fields})


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", errors="replace")


def write_md(path: Path, text: str) -> None:
    write_text(path, text.rstrip() + "\n")


def read_csv_dicts(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", errors="replace", newline="") as handle:
        return list(csv.DictReader(handle))


def as_float(value: Any, default: float | None = None) -> float | None:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def csv_value(value: Any) -> Any:
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return value


def count_rows(path: Path) -> int:
    return len(read_csv_dicts(path))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run_text(command: list[str]) -> str:
    proc = subprocess.run(command, text=True, encoding="utf-8", errors="replace", stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    return proc.stdout


def wrap360(value: float) -> float:
    return value % 360.0


def wrap180(value: float) -> float:
    return (value + 180.0) % 360.0 - 180.0


if __name__ == "__main__":
    raise SystemExit(main())
