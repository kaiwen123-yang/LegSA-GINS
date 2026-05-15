"""Shared audits for N9A_R1 source-aligned BY2 normal plotting.

中文说明：这些审计读取 N9A_R1 运行报告和 git 差异，防止源数据角色、case model 和边界声明回退。
"""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Any, Callable

from legsa_gins.reporting.n9a_r1_by2_source_aligned_normal import CASE_NAME, POINTER_PATH, R1_CATEGORY_SCHEMA


REPORTS = {
    "source_lineage": "N9A_R1_SOURCE_LINEAGE_REPORT.json",
    "input_files": "N9A_R1_INPUT_FILE_AUDIT_REPORT.json",
    "case_model": "N9A_R1_CASE_MODEL_REPORT.json",
    "plot": "N9A_R1_BY2_NORMAL_PLOT_AUDIT_REPORT.json",
    "category": "N9A_R1_CATEGORY_COVERAGE_REPORT.json",
    "truth": "N9A_R1_TRUTH_REFERENCE_USAGE_REPORT.json",
    "body": "N9A_R1_BODY_IMU_SOURCE_REPORT.json",
    "receiver": "N9A_R1_RECEIVER_IMU_DIAGNOSTIC_REPORT.json",
    "decision": "N9A_R1_DECISION_REPORT.json",
}


def main(check_name: str) -> int:
    parser = argparse.ArgumentParser(description=f"Run N9A_R1 audit: {check_name}")
    parser.add_argument("--report-dir", default="")
    args = parser.parse_args()
    run_check(check_name, resolve_report_dir(args.report_dir))
    print(f"audit_n9a_r1_{check_name} passed")
    return 0


def resolve_report_dir(value: str = "") -> Path:
    if value:
        path = Path(value)
    else:
        if not POINTER_PATH.exists():
            raise SystemExit("N9A_R1 audit failed: run runner first or pass --report-dir")
        payload = json.loads(POINTER_PATH.read_text(encoding="utf-8"))
        path = Path(payload.get("report_output_dir", ""))
    if not path.exists():
        raise SystemExit(f"N9A_R1 audit failed: missing report dir {path}")
    return path


def read_report(report_dir: Path, key: str) -> dict[str, Any]:
    path = report_dir / REPORTS[key]
    if not path.exists():
        raise SystemExit(f"N9A_R1 audit failed: missing {path.name}")
    return json.loads(path.read_text(encoding="utf-8"))


def run_check(check_name: str, report_dir: Path) -> None:
    checks: dict[str, Callable[[Path], None]] = {
        "source_lineage": check_source_lineage,
        "input_files_exist": check_input_files_exist,
        "case_model": check_case_model,
        "trace_evaluation_only": check_trace_evaluation_only,
        "body_imu_source": check_body_imu_source,
        "receiver_imu_diagnostic_only": check_receiver_imu_diagnostic_only,
        "no_ablation_variants_as_cases": check_no_ablation_variants_as_cases,
        "normal_plot_coverage": check_normal_plot_coverage,
        "no_placeholder_for_applicable_plots": check_no_placeholder,
        "no_algorithm_change": check_no_algorithm_change,
        "no_degradation_matrix_run": check_no_degradation_matrix_run,
        "no_performance_claim": check_no_performance_claim,
    }
    if check_name not in checks:
        raise SystemExit(f"unknown N9A_R1 audit: {check_name}")
    checks[check_name](report_dir)


def check_source_lineage(report_dir: Path) -> None:
    report = read_report(report_dir, "source_lineage")
    lineage = report.get("source_lineage", {})
    for key in ["dual_antenna_gnss_raw", "dual_antenna_gnss_status", "truth_reference_evaluation_only", "fused_body_imu_highlevel", "receiver_imu_diagnostic_only"]:
        if key not in lineage:
            raise SystemExit(f"N9A_R1 source lineage failed: missing {key}")
    if report.get("initial_n9a_status") != "N9A_initial_audit_scope_mismatch" or report.get("initial_n9a_ready_for_N9B") is not False:
        raise SystemExit("N9A_R1 source lineage failed: initial N9A not marked mismatch")


def check_input_files_exist(report_dir: Path) -> None:
    report = read_report(report_dir, "input_files")
    if report.get("all_required_source_files_exist") is not True:
        raise SystemExit("N9A_R1 input file audit failed: missing required source")
    for key in ["gnss1_raw", "gnss2_raw", "gnss1_status", "gnss2_status", "trace_truth", "go2_body_imu_highlevel"]:
        item = report.get("files", {}).get(key, {})
        if item.get("exists") is not True or int(item.get("row_count", 0)) <= 0:
            raise SystemExit(f"N9A_R1 input file audit failed: {key}")
    if report.get("raw_status_time_audit_passed") is not True:
        raise SystemExit("N9A_R1 input file audit failed: raw/status time audit")


def check_case_model(report_dir: Path) -> None:
    report = read_report(report_dir, "case_model")
    if report.get("main_case") != CASE_NAME or report.get("case_count") != 1:
        raise SystemExit("N9A_R1 case model failed: missing BY2_normal_clean")
    if report.get("algorithm_series_are_comparison_series_not_cases") is not True:
        raise SystemExit("N9A_R1 case model failed: algorithms treated as cases")


def check_trace_evaluation_only(report_dir: Path) -> None:
    report = read_report(report_dir, "truth")
    if report.get("trace_truth_exists") is not True or report.get("trace_solver_input") is not False or report.get("trace_usage") != "truth_reference_evaluation_only":
        raise SystemExit("N9A_R1 trace audit failed")


def check_body_imu_source(report_dir: Path) -> None:
    report = read_report(report_dir, "body")
    if report.get("go2_body_imu_highlevel_exists") is not True or report.get("by2_txt_is_fused_body_imu_highlevel") is not True:
        raise SystemExit("N9A_R1 body IMU source audit failed")
    if report.get("go2_position_truth") is not False or report.get("go2_yaw_truth") is not False or report.get("go2_contact_truth") is not False:
        raise SystemExit("N9A_R1 body IMU source audit failed: Go2 truth claim")


def check_receiver_imu_diagnostic_only(report_dir: Path) -> None:
    report = read_report(report_dir, "receiver")
    if report.get("receiver_imu_diagnostic_only") is not True or report.get("receiver_imu_used_as_fused_body_imu") is not False:
        raise SystemExit("N9A_R1 receiver IMU diagnostic audit failed")


def check_no_ablation_variants_as_cases(report_dir: Path) -> None:
    report = read_report(report_dir, "case_model")
    if report.get("ablation_variants_counted_as_normal_cases") is not False:
        raise SystemExit("N9A_R1 ablation-as-cases audit failed")
    if report.get("n8k_ablation_archive_variant_count", 0) < 30:
        raise SystemExit("N9A_R1 ablation archive audit failed: archive not detected")


def check_normal_plot_coverage(report_dir: Path) -> None:
    report = read_report(report_dir, "category")
    if report.get("case_name") != CASE_NAME or report.get("category_count") != len(R1_CATEGORY_SCHEMA):
        raise SystemExit("N9A_R1 plot coverage failed: schema")
    if report.get("category_coverage_complete") is not True or report.get("missing_count", 0) != 0:
        raise SystemExit("N9A_R1 plot coverage failed: missing")


def check_no_placeholder(report_dir: Path) -> None:
    report = read_report(report_dir, "plot")
    if report.get("placeholder_count", 0) != 0:
        raise SystemExit("N9A_R1 placeholder audit failed")
    for item in report.get("inventory", []):
        if item.get("applicable") is True and item.get("placeholder"):
            raise SystemExit("N9A_R1 placeholder audit failed: applicable placeholder")


def check_no_algorithm_change(report_dir: Path) -> None:
    decision = read_report(report_dir, "decision")
    if decision.get("algorithm_changes") is not False or decision.get("no_algorithm_changes") is not True:
        raise SystemExit("N9A_R1 no algorithm change audit failed")
    changed = _git_changed_paths()
    forbidden = [path for path in changed if path.endswith("gi_engine.cpp") or path.endswith("gi_engine.h") or path.startswith("cpp/legsa_v23_core/src/runtime/") or path.startswith("cpp/legsa_v23_port_core/src/kf_gins/")]
    if forbidden:
        raise SystemExit(f"N9A_R1 no algorithm change audit failed: {forbidden}")


def check_no_degradation_matrix_run(report_dir: Path) -> None:
    decision = read_report(report_dir, "decision")
    if decision.get("degradation_matrix_run") is not False or decision.get("N9B_degradation_matrix_run") is not False:
        raise SystemExit("N9A_R1 no degradation matrix audit failed")


def check_no_performance_claim(report_dir: Path) -> None:
    decision = read_report(report_dir, "decision")
    for key in ["paper_performance_claim", "outperform_final_v23_claim", "rtk_fixed_claim", "raw_dual_antenna_heading_claim", "tight_coupling_claim", "full_raw_gnss_factor_claim", "full_pose_fgo_claim"]:
        if decision.get(key) is not False:
            raise SystemExit(f"N9A_R1 performance claim audit failed: {key}")
    for line in _new_or_untracked_claim_lines():
        lower = line.lower()
        if "n9a_r1_audit_checks.py" in lower:
            continue
        if "no " in lower or "not " in lower or "禁止" in line or "不" in line:
            continue
        raise SystemExit(f"N9A_R1 performance claim audit failed: {line}")


def _git_changed_paths() -> list[str]:
    root = Path(__file__).resolve().parents[3]
    out = subprocess.check_output(["git", "diff", "--name-only", "N8K-v0.1-BY2-formal-ablation-plot-audit...HEAD"], cwd=root, text=True)
    unstaged = subprocess.check_output(["git", "diff", "--name-only"], cwd=root, text=True)
    staged = subprocess.check_output(["git", "diff", "--cached", "--name-only"], cwd=root, text=True)
    return sorted({line for text in [out, unstaged, staged] for line in text.splitlines() if line})


def _new_or_untracked_claim_lines() -> list[str]:
    root = Path(__file__).resolve().parents[3]
    tokens = ["outperform final_v23", "rtk fixed", "raw dual-antenna heading", "tight coupling", "full raw gnss factor", "full pose fgo"]
    lines: list[str] = []
    diff = subprocess.check_output(["git", "diff", "--unified=0", "--", "docs", "README.md", "CLAIM_BOUNDARY.md", "PHASE_LOG.md", "scripts", "src"], cwd=root, text=True)
    current = ""
    for raw in diff.splitlines():
        if raw.startswith("+++ b/"):
            current = raw[6:]
        elif raw.startswith("+") and not raw.startswith("+++"):
            text = raw[1:]
            if any(token in text.lower() for token in tokens):
                lines.append(f"{current}: {text}")
    untracked = subprocess.check_output(["git", "ls-files", "--others", "--exclude-standard", "--", "docs", "README.md", "CLAIM_BOUNDARY.md", "PHASE_LOG.md", "scripts", "src"], cwd=root, text=True)
    for rel in untracked.splitlines():
        path = root / rel
        if path.is_file():
            for lineno, text in enumerate(path.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
                if any(token in text.lower() for token in tokens):
                    lines.append(f"{rel}:{lineno}: {text}")
    return lines
