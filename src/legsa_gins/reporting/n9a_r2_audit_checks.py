"""Shared audits for N9A_R2 real BY2 normal plot materialization.

中文说明：这些审计防止 source/proxy 图被误当作真实算法结果。
"""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Any, Callable

from legsa_gins.reporting.n9a_r2_by2_normal_real_plot_materialization import POINTER_PATH, TARGET_ALGORITHM_SERIES


REPORTS = {
    "input": "N9A_R2_INPUT_SOURCE_ROLE_REPORT.json",
    "discovery": "N9A_R2_ALGORITHM_OUTPUT_DISCOVERY_REPORT.json",
    "plot": "N9A_R2_BY2_NORMAL_REAL_PLOT_AUDIT_REPORT.json",
    "category": "N9A_R2_CATEGORY_COVERAGE_REPORT.json",
    "decision": "N9A_R2_DECISION_REPORT.json",
    "source_proxy": "N9A_R2_SOURCE_PROXY_EXCLUSION_REPORT.json",
    "trajectory": "N9A_R2_REAL_TRAJECTORY_SEMANTICS_REPORT.json",
    "position": "N9A_R2_REAL_POSITION_ERROR_SEMANTICS_REPORT.json",
    "metric_bar": "N9A_R2_METRIC_BAR_SEMANTICS_REPORT.json",
    "velocity": "N9A_R2_VELOCITY_SOURCE_DISTINCTION_REPORT.json",
    "compare": "N9A_R2_COMPARE_REQUIRES_ALGORITHM_OUTPUTS_REPORT.json",
    "consistency": "N9A_R2_CONSISTENCY_REQUIRES_STD_REPORT.json",
}


def main(check_name: str) -> int:
    parser = argparse.ArgumentParser(description=f"Run N9A_R2 audit: {check_name}")
    parser.add_argument("--report-dir", default="")
    args = parser.parse_args()
    run_check(check_name, resolve_report_dir(args.report_dir))
    print(f"audit_n9a_r2_{check_name} passed")
    return 0


def resolve_report_dir(value: str = "") -> Path:
    if value:
        path = Path(value)
    else:
        if not POINTER_PATH.exists():
            raise SystemExit("N9A_R2 audit failed: run runner first or pass --report-dir")
        payload = json.loads(POINTER_PATH.read_text(encoding="utf-8"))
        path = Path(payload.get("report_output_dir", ""))
    if not path.exists():
        raise SystemExit(f"N9A_R2 audit failed: missing report dir {path}")
    return path


def read_report(report_dir: Path, key: str) -> dict[str, Any]:
    path = report_dir / REPORTS[key]
    if not path.exists():
        raise SystemExit(f"N9A_R2 audit failed: missing {path.name}")
    return json.loads(path.read_text(encoding="utf-8"))


def run_check(check_name: str, report_dir: Path) -> None:
    checks: dict[str, Callable[[Path], None]] = {
        "algorithm_output_discovery": check_algorithm_output_discovery,
        "no_source_proxy_as_algorithm_result": check_no_source_proxy_as_algorithm_result,
        "real_trajectory_semantics": check_real_trajectory_semantics,
        "real_position_error_semantics": check_real_position_error_semantics,
        "metric_bar_semantics": check_metric_bar_semantics,
        "velocity_source_distinction": check_velocity_source_distinction,
        "compare_requires_algorithm_outputs": check_compare_requires_algorithm_outputs,
        "consistency_requires_std": check_consistency_requires_std,
        "no_false_complete": check_no_false_complete,
        "no_placeholder_for_applicable_plots": check_no_placeholder_for_applicable_plots,
        "no_algorithm_change": check_no_algorithm_change,
        "no_degradation_matrix_run": check_no_degradation_matrix_run,
        "no_performance_claim": check_no_performance_claim,
    }
    if check_name not in checks:
        raise SystemExit(f"unknown N9A_R2 audit: {check_name}")
    checks[check_name](report_dir)


def check_algorithm_output_discovery(report_dir: Path) -> None:
    report = read_report(report_dir, "discovery")
    series = report.get("algorithm_series", [])
    if report.get("algorithm_series_count") != len(TARGET_ALGORITHM_SERIES) or len(series) != len(TARGET_ALGORITHM_SERIES):
        raise SystemExit("N9A_R2 discovery failed: target series count mismatch")
    for item in series:
        for key in [
            "series_name",
            "available",
            "output_root",
            "nav_path",
            "std_path",
            "eval_path",
            "manifest_path",
            "metrics_path",
            "figure_source_role",
            "row_count_nav",
            "row_count_eval",
            "row_count_std",
            "can_plot_trajectory",
            "can_plot_position_error",
            "can_plot_velocity",
            "can_plot_attitude",
            "can_plot_consistency",
            "can_plot_compare",
            "missing_reason",
        ]:
            if key not in item:
                raise SystemExit(f"N9A_R2 discovery failed: missing {key}")
    if report.get("formal_ablation_variants_counted_as_normal_cases") is not False:
        raise SystemExit("N9A_R2 discovery failed: formal ablation variants counted as cases")


def check_no_source_proxy_as_algorithm_result(report_dir: Path) -> None:
    discovery = read_report(report_dir, "discovery")
    source_proxy = read_report(report_dir, "source_proxy")
    if source_proxy.get("source_data_treated_as_algorithm_estimate") is not False:
        raise SystemExit("N9A_R2 source proxy audit failed: source data treated as algorithm estimate")
    if source_proxy.get("trace_solver_input") is not False or source_proxy.get("by2_txt_truth") is not False:
        raise SystemExit("N9A_R2 source proxy audit failed: forbidden source role")
    for item in discovery.get("algorithm_series", []):
        if item.get("available") and item.get("figure_source_role") != "real_algorithm_runtime_output":
            raise SystemExit("N9A_R2 source proxy audit failed: available series is not real runtime output")
    plot = read_report(report_dir, "plot")
    for item in plot.get("inventory", []):
        if item.get("source_proxy") and item.get("completion_eligible"):
            raise SystemExit("N9A_R2 source proxy audit failed: proxy contributes completion")


def check_real_trajectory_semantics(report_dir: Path) -> None:
    discovery = read_report(report_dir, "discovery")
    trajectory = read_report(report_dir, "trajectory")
    if discovery.get("available_algorithm_series_count", 0) == 0 and trajectory.get("trajectory_category_complete"):
        raise SystemExit("N9A_R2 trajectory audit failed: complete without algorithm NAV")
    plot = read_report(report_dir, "plot")
    for item in plot.get("inventory", []):
        if item.get("category") == "01_trajectory" and item.get("present") and item.get("applicable") and item.get("source_type") != "algorithm_nav":
            raise SystemExit("N9A_R2 trajectory audit failed: non-algorithm trajectory present as applicable")


def check_real_position_error_semantics(report_dir: Path) -> None:
    discovery = read_report(report_dir, "discovery")
    position = read_report(report_dir, "position")
    if discovery.get("available_algorithm_series_count", 0) == 0 and position.get("position_error_category_complete"):
        raise SystemExit("N9A_R2 position audit failed: complete without algorithm EVAL/NAV")
    if position.get("gnss_status_minus_trace_as_algorithm_error") is not False:
        raise SystemExit("N9A_R2 position audit failed: GNSS status used as algorithm error")


def check_metric_bar_semantics(report_dir: Path) -> None:
    report = read_report(report_dir, "metric_bar")
    if report.get("non_bar_metric_bar_count", 0) != 0:
        raise SystemExit("N9A_R2 metric bar audit failed: *_bar figure is not a bar")


def check_velocity_source_distinction(report_dir: Path) -> None:
    report = read_report(report_dir, "velocity")
    if report.get("same_proxy_used_for_all_velocity_sources"):
        raise SystemExit("N9A_R2 velocity audit failed: all velocity sources share one proxy")


def check_compare_requires_algorithm_outputs(report_dir: Path) -> None:
    report = read_report(report_dir, "compare")
    if report.get("compare_complete") and int(report.get("available_algorithm_series_count", 0)) < 2:
        raise SystemExit("N9A_R2 compare audit failed: compare complete with fewer than two real outputs")


def check_consistency_requires_std(report_dir: Path) -> None:
    report = read_report(report_dir, "consistency")
    if report.get("error_proxy_used_as_3sigma") is not False:
        raise SystemExit("N9A_R2 consistency audit failed: error proxy used as 3sigma")
    if report.get("consistency_entries_present_without_std", 0) != 0:
        raise SystemExit("N9A_R2 consistency audit failed: consistency figure present without STD")


def check_no_false_complete(report_dir: Path) -> None:
    discovery = read_report(report_dir, "discovery")
    decision = read_report(report_dir, "decision")
    category = read_report(report_dir, "category")
    plot = read_report(report_dir, "plot")
    if discovery.get("available_algorithm_series_count", 0) == 0 and decision.get("status") != "N9A_R2_algorithm_outputs_missing":
        raise SystemExit("N9A_R2 no-false-complete failed: missing outputs not failed")
    if plot.get("missing_count", 0) > 0 and category.get("category_coverage_complete"):
        raise SystemExit("N9A_R2 no-false-complete failed: category complete despite missing figures")
    if decision.get("ready_for_N9B") not in {False, "true_only_after_user_approval"}:
        raise SystemExit("N9A_R2 no-false-complete failed: invalid ready_for_N9B")
    if decision.get("status") != "N9A_R2_BY2_normal_real_plot_materialization_complete" and decision.get("ready_for_N9B") is not False:
        raise SystemExit("N9A_R2 no-false-complete failed: incomplete stage ready for N9B")


def check_no_placeholder_for_applicable_plots(report_dir: Path) -> None:
    plot = read_report(report_dir, "plot")
    if plot.get("placeholder_count", 0) != 0:
        raise SystemExit("N9A_R2 placeholder audit failed")
    for item in plot.get("inventory", []):
        if item.get("applicable") and item.get("placeholder"):
            raise SystemExit("N9A_R2 placeholder audit failed: applicable placeholder")


def check_no_algorithm_change(report_dir: Path) -> None:
    decision = read_report(report_dir, "decision")
    if decision.get("algorithm_changes") is not False or decision.get("no_algorithm_changes") is not True:
        raise SystemExit("N9A_R2 algorithm-change audit failed: decision flags")
    forbidden = [
        path
        for path in git_changed_paths()
        if path.startswith("cpp/legsa_v23_core/src/runtime/")
        or path.startswith("cpp/legsa_v23_port_core/src/kf_gins/")
        or path.endswith("gi_engine.cpp")
        or path.endswith("gi_engine.h")
    ]
    if forbidden:
        raise SystemExit(f"N9A_R2 algorithm-change audit failed: {forbidden}")


def check_no_degradation_matrix_run(report_dir: Path) -> None:
    decision = read_report(report_dir, "decision")
    if decision.get("degradation_matrix_run") is not False or decision.get("N9B_degradation_matrix_run") is not False:
        raise SystemExit("N9A_R2 degradation matrix audit failed")


def check_no_performance_claim(report_dir: Path) -> None:
    decision = read_report(report_dir, "decision")
    if decision.get("paper_performance_claim") is not False or decision.get("outperform_final_v23_claim") is not False:
        raise SystemExit("N9A_R2 performance claim audit failed: decision flags")
    for line in new_claim_lines():
        lower = line.lower()
        if "n9a_r2_audit_checks.py" in lower:
            continue
        if any(guard in lower for guard in ["no ", "not ", "without ", "false", "禁止", "不", "不能", "不得"]):
            continue
        raise SystemExit(f"N9A_R2 performance claim audit failed: {line}")


def git_changed_paths() -> list[str]:
    root = Path(__file__).resolve().parents[3]
    commands = [
        ["git", "diff", "--name-only", "origin/main...HEAD"],
        ["git", "diff", "--name-only"],
        ["git", "diff", "--cached", "--name-only"],
    ]
    paths: set[str] = set()
    for command in commands:
        try:
            out = subprocess.check_output(command, cwd=root, text=True)
        except subprocess.CalledProcessError:
            continue
        paths.update(line for line in out.splitlines() if line)
    return sorted(paths)


def new_claim_lines() -> list[str]:
    root = Path(__file__).resolve().parents[3]
    tokens = ["outperform final_v23", "paper performance claim", "rtk fixed", "tight coupling", "full raw gnss factor", "full pose fgo"]
    lines: list[str] = []
    try:
        diff = subprocess.check_output(["git", "diff", "--unified=0", "--", "docs", "README.md", "CLAIM_BOUNDARY.md", "PHASE_LOG.md", "scripts", "src"], cwd=root, text=True)
    except subprocess.CalledProcessError:
        diff = ""
    current = ""
    for raw in diff.splitlines():
        if raw.startswith("+++ b/"):
            current = raw[6:]
        elif raw.startswith("+") and not raw.startswith("+++"):
            text = raw[1:]
            if any(token in text.lower() for token in tokens):
                lines.append(f"{current}: {text}")
    try:
        untracked = subprocess.check_output(["git", "ls-files", "--others", "--exclude-standard", "--", "docs", "README.md", "CLAIM_BOUNDARY.md", "PHASE_LOG.md", "scripts", "src"], cwd=root, text=True)
    except subprocess.CalledProcessError:
        untracked = ""
    for rel in untracked.splitlines():
        path = root / rel
        if not path.is_file():
            continue
        for lineno, text in enumerate(path.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
            if any(token in text.lower() for token in tokens):
                lines.append(f"{rel}:{lineno}: {text}")
    return lines
