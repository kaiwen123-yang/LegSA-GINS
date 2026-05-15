"""Shared checks for N9A BY2 full plot audit scripts.

中文说明：这些检查只读取 N9A 运行报告和 git 差异，用于防止路径泄露、伪图和越界声明。
"""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Any, Callable

from legsa_gins.reporting.n9a_by2_full_plot_audit import CATEGORY_SCHEMA, DEFAULT_N8K_TAG, POINTER_PATH


REPORTS = {
    "input_discovery": "N9A_INPUT_DISCOVERY_REPORT.json",
    "case_discovery": "N9A_BY2_CASE_DISCOVERY_REPORT.json",
    "category_coverage": "N9A_CATEGORY_COVERAGE_REPORT.json",
    "case_coverage": "N9A_CASE_COVERAGE_REPORT.json",
    "placeholder": "N9A_PLACEHOLDER_AUDIT_REPORT.json",
    "duplicate": "N9A_DUPLICATE_AUDIT_REPORT.json",
    "semantic_filename": "N9A_SEMANTIC_FILENAME_AUDIT_REPORT.json",
    "not_applicable": "N9A_NOT_APPLICABLE_REASON_REPORT.json",
    "derived_data": "N9A_DERIVED_DATA_LABEL_REPORT.json",
    "feedback_applicability": "N9A_FEEDBACK_APPLICABILITY_AUDIT_REPORT.json",
    "degradation_meta": "N9A_DEGRADATION_META_REPORT.json",
    "audit_sanity": "N9A_AUDIT_SANITY_REPORT.json",
    "summary_panels": "N9A_SUMMARY_PANEL_REPORT.json",
    "ppt_assets": "N9A_PPT_ASSET_REPORT.json",
    "decision": "N9A_DECISION_REPORT.json",
    "inventory": "N9A_BY2_FULL_FIGURE_INVENTORY.json",
}

BANNED_CLAIM_TOKENS = [
    "outperform final_v23",
    "rtk fixed",
    "raw dual-antenna heading",
    "tight coupling",
    "full raw gnss factor",
    "full pose fgo",
]


def main(check_name: str) -> int:
    parser = argparse.ArgumentParser(description=f"Run N9A audit check: {check_name}")
    parser.add_argument("--report-dir", default="")
    args = parser.parse_args()
    report_dir = resolve_report_dir(args.report_dir)
    run_check(check_name, report_dir)
    print(f"audit_n9a_{check_name} passed")
    return 0


def resolve_report_dir(value: str = "") -> Path:
    if value:
        path = Path(value)
    else:
        pointer = POINTER_PATH
        if not pointer.exists():
            raise SystemExit("N9A audit failed: missing .legsa_runtime/n9a_latest.json; run the N9A runner first or pass --report-dir")
        payload = json.loads(pointer.read_text(encoding="utf-8"))
        path = Path(payload.get("report_output_dir", ""))
    if not path.exists():
        raise SystemExit(f"N9A audit failed: report dir does not exist: {path}")
    return path


def run_check(check_name: str, report_dir: Path) -> None:
    checks: dict[str, Callable[[Path], None]] = {
        "input_discovery": check_input_discovery,
        "case_discovery": check_case_discovery,
        "category_coverage": check_category_coverage,
        "case_coverage": check_case_coverage,
        "no_placeholder_for_applicable_plots": check_no_placeholder,
        "duplicate_plots": check_duplicate,
        "semantic_filename_alignment": check_semantic,
        "not_applicable_reasons": check_not_applicable,
        "feedback_applicability": check_feedback_applicability,
        "no_empty_axes": check_no_empty_axes,
        "derived_data_labels": check_derived_data,
        "degradation_meta": check_degradation_meta,
        "audit_sanity": check_audit_sanity,
        "summary_panels": check_summary_panels,
        "ppt_assets": check_ppt_assets,
        "no_algorithm_change": check_no_algorithm_change,
        "no_degradation_matrix_run": check_no_degradation_matrix_run,
        "no_performance_claim": check_no_performance_claim,
    }
    if check_name not in checks:
        raise SystemExit(f"unknown N9A audit check: {check_name}")
    checks[check_name](report_dir)


def read_report(report_dir: Path, key: str) -> dict[str, Any]:
    path = report_dir / REPORTS[key]
    if not path.exists():
        raise SystemExit(f"N9A audit failed: missing {path.name}")
    return json.loads(path.read_text(encoding="utf-8"))


def check_input_discovery(report_dir: Path) -> None:
    report = read_report(report_dir, "input_discovery")
    if report.get("enough_to_generate_full_plot_audit") is not True:
        raise SystemExit(f"N9A input discovery failed: {report.get('cannot_proceed_reasons')}")
    if not report.get("found_result_roots"):
        raise SystemExit("N9A input discovery failed: no previous result roots")
    if int(report.get("found_existing_figure_count", 0)) <= 0:
        raise SystemExit("N9A input discovery failed: no existing figures discovered")


def check_case_discovery(report_dir: Path) -> None:
    report = read_report(report_dir, "case_discovery")
    if int(report.get("case_count", 0)) <= 0:
        raise SystemExit("N9A case discovery failed: no cases")
    if report.get("missing_required_cases"):
        raise SystemExit(f"N9A case discovery failed: missing {report['missing_required_cases']}")
    if "A0_source_backed_ekf_baseline" not in report.get("discovered_cases", []):
        raise SystemExit("N9A case discovery failed: A0 baseline missing")


def check_category_coverage(report_dir: Path) -> None:
    report = read_report(report_dir, "category_coverage")
    rows = {row["category"]: row for row in report.get("categories", [])}
    for category in CATEGORY_SCHEMA:
        if category not in rows:
            raise SystemExit(f"N9A category coverage failed: missing {category}")
        if rows[category].get("missing_count", 0) != 0:
            raise SystemExit(f"N9A category coverage failed: missing files in {category}")


def check_case_coverage(report_dir: Path) -> None:
    report = read_report(report_dir, "case_coverage")
    if report.get("case_missing_count", 0) != 0:
        raise SystemExit("N9A case coverage failed: missing cases")
    for row in report.get("cases", []):
        if row.get("missing_count", 0) != 0:
            raise SystemExit(f"N9A case coverage failed: missing files for {row.get('case_name')}")


def check_no_placeholder(report_dir: Path) -> None:
    report = read_report(report_dir, "placeholder")
    if report.get("placeholder_count", 0) != 0 or report.get("applicable_placeholder_count", 0) != 0:
        raise SystemExit("N9A placeholder audit failed")


def check_duplicate(report_dir: Path) -> None:
    report = read_report(report_dir, "duplicate")
    if report.get("blocking_duplicate_count", 0) != 0:
        raise SystemExit("N9A duplicate audit failed: blocking duplicate groups remain")
    if report.get("same_variant_cross_category_duplicate_count", 0) != 0:
        raise SystemExit("N9A duplicate audit failed: same-variant cross-category duplicate remains")


def check_semantic(report_dir: Path) -> None:
    report = read_report(report_dir, "semantic_filename")
    if report.get("semantic_mismatch_count", 0) != 0:
        raise SystemExit("N9A semantic filename audit failed")
    if report.get("compare_figures_are_true_compare") is not True:
        raise SystemExit("N9A semantic filename audit failed: compare semantics")


def check_not_applicable(report_dir: Path) -> None:
    report = read_report(report_dir, "not_applicable")
    if report.get("not_applicable_without_reason_count", 0) != 0:
        raise SystemExit("N9A not-applicable audit failed")


def check_feedback_applicability(report_dir: Path) -> None:
    report = read_report(report_dir, "feedback_applicability")
    if report.get("feedback_applicability_conflict_count", 0) != 0:
        raise SystemExit("N9A feedback applicability audit failed")
    if report.get("A0_feedback_applicable") is not False:
        raise SystemExit("N9A feedback applicability audit failed: A0 is feedback-applicable")


def check_no_empty_axes(report_dir: Path) -> None:
    report = read_report(report_dir, "placeholder")
    if report.get("empty_axis_count", 0) != 0:
        raise SystemExit("N9A empty-axis audit failed")


def check_derived_data(report_dir: Path) -> None:
    report = read_report(report_dir, "derived_data")
    if report.get("derived_surrogate_unlabeled_count", 0) != 0:
        raise SystemExit("N9A derived-data label audit failed")
    if report.get("paper_performance_claim") is not False:
        raise SystemExit("N9A derived-data label audit failed: claim boundary")


def check_degradation_meta(report_dir: Path) -> None:
    report = read_report(report_dir, "degradation_meta")
    if report.get("N9B_degradation_matrix_run") is not False:
        raise SystemExit("N9A degradation-meta audit failed: N9B was run")
    if report.get("degradation_meta_missing_case_count", 0) != 0:
        raise SystemExit("N9A degradation-meta audit failed: degradation metadata missing")


def check_audit_sanity(report_dir: Path) -> None:
    report = read_report(report_dir, "audit_sanity")
    if report.get("audit_sanity_missing_case_count", 0) != 0:
        raise SystemExit("N9A audit-sanity failed: case-level panel missing")
    for key in ["no_future_data_check", "no_output_substitution_check", "path_leak_check"]:
        if report.get(key) is not True:
            raise SystemExit(f"N9A audit-sanity failed: {key}")


def check_summary_panels(report_dir: Path) -> None:
    report = read_report(report_dir, "summary_panels")
    if report.get("summary_panel_count", 0) < 7:
        raise SystemExit("N9A summary-panel audit failed")
    for item in report.get("summary_panels_generated", []):
        if item.get("present") is not True or item.get("nonempty") is not True:
            raise SystemExit(f"N9A summary-panel audit failed: {item.get('filename')}")


def check_ppt_assets(report_dir: Path) -> None:
    report = read_report(report_dir, "ppt_assets")
    if report.get("ppt_asset_count", 0) <= 0:
        raise SystemExit("N9A PPT asset audit failed: no assets")
    manifest = Path(report.get("ppt_asset_manifest", ""))
    if not manifest.exists():
        raise SystemExit("N9A PPT asset audit failed: manifest missing")
    if report.get("pptx_generated") is not False:
        raise SystemExit("N9A PPT asset audit failed: PPTX generated unexpectedly")


def check_no_algorithm_change(report_dir: Path) -> None:
    decision = read_report(report_dir, "decision")
    if decision.get("algorithm_changes") is not False or decision.get("no_algorithm_changes") is not True:
        raise SystemExit("N9A no-algorithm-change audit failed: report flag")
    changed = _git_changed_paths()
    forbidden = [
        path
        for path in changed
        if path.endswith("gi_engine.cpp")
        or path.endswith("gi_engine.h")
        or path.startswith("cpp/legsa_v23_core/src/runtime/")
        or path.startswith("cpp/legsa_v23_port_core/src/kf_gins/")
    ]
    if forbidden:
        raise SystemExit(f"N9A no-algorithm-change audit failed: {forbidden}")


def check_no_degradation_matrix_run(report_dir: Path) -> None:
    decision = read_report(report_dir, "decision")
    degradation = read_report(report_dir, "degradation_meta")
    if decision.get("degradation_matrix_run") is not False or decision.get("N9B_degradation_matrix_run") is not False:
        raise SystemExit("N9A degradation-matrix audit failed: decision flag")
    if degradation.get("N9B_degradation_matrix_run") is not False:
        raise SystemExit("N9A degradation-matrix audit failed: degradation report flag")


def check_no_performance_claim(report_dir: Path) -> None:
    decision = read_report(report_dir, "decision")
    if decision.get("paper_performance_claim") is not False or decision.get("outperform_final_v23_claim") is not False:
        raise SystemExit("N9A performance-claim audit failed: report flag")
    for line in _new_or_untracked_claim_lines():
        lower = line.lower()
        if "n9a_audit_checks.py" in lower:
            continue
        if "no " in lower or "not " in lower or "forbid" in lower or "claim boundary" in lower or "禁止" in line or "不" in line:
            continue
        raise SystemExit(f"N9A performance-claim audit failed: {line}")


def _git_changed_paths() -> list[str]:
    root = Path(__file__).resolve().parents[3]
    try:
        out = subprocess.check_output(["git", "diff", "--name-only", f"{DEFAULT_N8K_TAG}...HEAD"], cwd=root, text=True)
    except subprocess.CalledProcessError:
        out = subprocess.check_output(["git", "diff", "--name-only"], cwd=root, text=True)
    unstaged = subprocess.check_output(["git", "diff", "--name-only"], cwd=root, text=True)
    staged = subprocess.check_output(["git", "diff", "--cached", "--name-only"], cwd=root, text=True)
    return sorted({*(line for line in out.splitlines() if line), *(line for line in unstaged.splitlines() if line), *(line for line in staged.splitlines() if line)})


def _new_or_untracked_claim_lines() -> list[str]:
    root = Path(__file__).resolve().parents[3]
    lines: list[str] = []
    for args in (["git", "diff", "--unified=0"], ["git", "diff", "--cached", "--unified=0"]):
        diff = subprocess.check_output([*args, "--", "docs", "README.md", "CLAIM_BOUNDARY.md", "PHASE_LOG.md", "scripts", "src"], cwd=root, text=True)
        current_file = ""
        for raw in diff.splitlines():
            if raw.startswith("+++ b/"):
                current_file = raw[6:]
            elif raw.startswith("+") and not raw.startswith("+++"):
                text = raw[1:]
                if _contains_banned_claim_token(text):
                    lines.append(f"{current_file}: {text}")
    try:
        untracked = subprocess.check_output(["git", "ls-files", "--others", "--exclude-standard", "--", "docs", "README.md", "CLAIM_BOUNDARY.md", "PHASE_LOG.md", "scripts", "src"], cwd=root, text=True)
    except subprocess.CalledProcessError:
        untracked = ""
    for rel in untracked.splitlines():
        path = root / rel
        if path.is_file():
            for lineno, text in enumerate(path.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
                if _contains_banned_claim_token(text):
                    lines.append(f"{rel}:{lineno}: {text}")
    return lines


def _contains_banned_claim_token(text: str) -> bool:
    lower = text.lower()
    return any(token in lower for token in BANNED_CLAIM_TOKENS)
