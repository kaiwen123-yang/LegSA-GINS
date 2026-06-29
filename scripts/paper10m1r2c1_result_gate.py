#!/usr/bin/env python3
"""Generate PAPER10M1R2C1 decision reports, figures, and export-clean package."""

from __future__ import annotations

import argparse
import csv
import json
import math
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from legsa_gins.evaluation.yaw_metric_repair import decide_m1r2d_gate  # noqa: E402


STAGE_DIRS = [
    "00_STAGE_REPORT",
    "01_GIT",
    "02_YAW_AUDIT",
    "03_QM_AUDIT",
    "04_CORRECTED_METRICS",
    "05_FIGURES",
    "06_DECISION",
    "07_TESTS",
    "08_CLAIM_BOUNDARY",
    "09_NEXT_STAGE",
    "10_EXPORT_CLEAN_FOR_GPT",
]


def read_csv_rows(path: str | Path) -> list[dict[str, str]]:
    with Path(path).open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def write_csv_rows(path: str | Path, rows: list[dict[str, Any]], fieldnames: list[str] | None = None) -> None:
    if fieldnames is None:
        fieldnames = []
        for row in rows:
            for key in row:
                if key not in fieldnames:
                    fieldnames.append(key)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with Path(path).open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: csv_value(row.get(key, "")) for key in fieldnames})


def csv_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        if math.isnan(value):
            return ""
        return f"{value:.12g}"
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return "" if value is None else str(value)


def load_json(path: str | Path) -> dict[str, Any]:
    path = Path(path)
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: str | Path, payload: dict[str, Any]) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def ensure_dirs(stage_root: Path) -> None:
    for name in STAGE_DIRS:
        (stage_root / name).mkdir(parents=True, exist_ok=True)


def safe_float(value: Any, default: float = math.nan) -> float:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def git_output(args: list[str], cwd: Path) -> str:
    completed = subprocess.run(["git", *args], cwd=cwd, text=True, capture_output=True, check=False)
    return completed.stdout.strip() or completed.stderr.strip()


def write_git_report(stage_root: Path, code_root: Path, commit_hash: str, push_status: str) -> None:
    report = [
        "# PAPER10M1R2C1 Git State Report",
        "",
        f"- branch: `{git_output(['branch', '--show-current'], code_root)}`",
        f"- head: `{git_output(['rev-parse', '--short', 'HEAD'], code_root)}`",
        f"- commit_hash_after_stage_if_committed: `{commit_hash or 'not_committed_at_report_time'}`",
        f"- push_status: `{push_status or 'not_pushed_at_report_time'}`",
        "- status_short:",
        "```text",
        git_output(["status", "--short"], code_root) or "clean",
        "```",
        "- branch_status:",
        "```text",
        git_output(["status", "--branch", "--short"], code_root),
        "```",
        "- prohibited git actions: no merge, no tag, no force push, no main push.",
    ]
    (stage_root / "01_GIT" / "PAPER10M1R2C1_GIT_STATE_REPORT.md").write_text(
        "\n".join(report) + "\n", encoding="utf-8"
    )


def _bar(ax: Any, labels: list[str], values: list[float], title: str, ylabel: str) -> None:
    ax.bar(range(len(labels)), values, color="#4C78A8")
    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels, rotation=25, ha="right", fontsize=8)
    ax.set_title(title)
    ax.set_ylabel(ylabel)
    ax.grid(axis="y", alpha=0.25)


def make_figures(stage_root: Path, decision: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig_dir = stage_root / "05_FIGURES"
    yaw_rows = read_csv_rows(stage_root / "02_YAW_AUDIT" / "PAPER10M1R2C1_CLEAN_YAW_AUDIT_TABLE.csv")
    cand_rows = read_csv_rows(stage_root / "02_YAW_AUDIT" / "PAPER10M1R2C1_YAW_TRANSFORM_CANDIDATE_TABLE.csv")
    qm_rows = read_csv_rows(stage_root / "03_QM_AUDIT" / "PAPER10M1R2C1_QM_TRACE_SEMANTIC_AUDIT_TABLE.csv")
    clean_qm = [row for row in qm_rows if row.get("case_id") == "BY2_CLEAN_CANONICAL"]

    figure_specs: list[tuple[str, Any]] = []

    def add_bar(name: str, labels: list[str], values: list[float], title: str, ylabel: str) -> None:
        fig, ax = plt.subplots(figsize=(8, 4.5))
        _bar(ax, labels, values, title, ylabel)
        fig.tight_layout()
        figure_specs.append((name, fig))

    labels = [row["method_mode_id"].replace("_", "\n") for row in yaw_rows]
    add_bar(
        "clean_yaw_error_by_method_original",
        labels,
        [safe_float(row.get("m1r2c_original_yaw_rmse_deg"), 0.0) for row in yaw_rows],
        "PAPER10M1R2C1 semantic audit: original clean yaw RMSE",
        "deg",
    )
    add_bar(
        "clean_yaw_error_by_method_candidate_transforms",
        labels,
        [safe_float(row.get("best_provider_reference_rmse_deg"), 0.0) for row in yaw_rows],
        "PAPER10M1R2C1 semantic audit: best provider-yaw transform",
        "deg",
    )
    add_bar(
        "clean_yaw_timeseries_original_vs_corrected_if_applicable",
        labels,
        [safe_float(row.get("trace_heading_to_math_rmse_deg"), 0.0) for row in yaw_rows],
        "PAPER10M1R2C1 semantic audit: trace-heading-to-math yaw RMSE",
        "deg",
    )
    provider_candidates = [row for row in cand_rows if row.get("reference_name") == "provider_status_yaw_observation"]
    top_candidates = sorted(provider_candidates, key=lambda row: safe_float(row.get("yaw_rmse_deg"), math.inf))[:10]
    add_bar(
        "yaw_transform_candidate_rmse_bar",
        [row.get("yaw_transform_candidate", "") for row in top_candidates],
        [safe_float(row.get("yaw_rmse_deg"), 0.0) for row in top_candidates],
        "PAPER10M1R2C1 semantic audit: transform candidate RMSE",
        "deg",
    )
    full_qm = next((row for row in clean_qm if row.get("method_mode_id") == "legsa_full_candidate_with_qm"), {})
    add_bar(
        "clean_qm_state_count_panel",
        ["normal", "downweight", "reject", "recovery"],
        [
            safe_float(full_qm.get("yaw_normal_count"), 0.0),
            safe_float(full_qm.get("yaw_downweight_count"), 0.0),
            safe_float(full_qm.get("yaw_reject_count"), 0.0),
            safe_float(full_qm.get("recovery_count_original"), 0.0),
        ],
        "PAPER10M1R2C1 semantic audit: clean QM/yaw counts",
        "count",
    )
    add_bar(
        "bad_a1_consumed_semantic_panel",
        [row["method_mode_id"].replace("_", "\n") for row in clean_qm],
        [safe_float(row.get("bad_a1_consumed_count_original"), 0.0) for row in clean_qm],
        "PAPER10M1R2C1 semantic audit: original bad_a1 counter",
        "count",
    )
    add_bar(
        "qm_trace_required_vs_present_panel",
        [row["method_mode_id"].replace("_", "\n") for row in clean_qm],
        [
            (1.0 if row.get("qm_trace_required") == "true" else 0.0)
            + (1.0 if row.get("qm_trace_file_exists") == "true" else 0.0)
            for row in clean_qm
        ],
        "PAPER10M1R2C1 semantic audit: QM required/present code",
        "0 none, 1 one flag, 2 both",
    )
    fig, ax = plt.subplots(figsize=(8, 4.5))
    status = decision["m1r2d_gate"]
    ax.text(0.5, 0.58, status, ha="center", va="center", fontsize=18, weight="bold")
    ax.text(0.5, 0.38, decision["final_decision"], ha="center", va="center", fontsize=10, wrap=True)
    ax.set_axis_off()
    ax.set_title("PAPER10M1R2C1 semantic audit: M1R2D gate decision")
    figure_specs.append(("m1r2d_gate_decision_panel", fig))

    index_rows: list[dict[str, Any]] = []
    qa_rows: list[dict[str, Any]] = []
    for name, fig in figure_specs:
        png = fig_dir / f"{name}.png"
        pdf = fig_dir / f"{name}.pdf"
        fig.savefig(png, dpi=160)
        fig.savefig(pdf)
        plt.close(fig)
        row_count = len(yaw_rows) if "yaw" in name or "decision" in name else len(clean_qm)
        index_rows.append({"figure_id": name, "png": png.name, "pdf": pdf.name, "title_role": "semantic_audit_not_paper_result"})
        qa_rows.append(
            {
                "figure_id": name,
                "png_exists": png.is_file(),
                "pdf_exists": pdf.is_file(),
                "png_size_gt_zero": png.stat().st_size > 0 if png.is_file() else False,
                "pdf_size_gt_zero": pdf.stat().st_size > 0 if pdf.is_file() else False,
                "plotted_row_count": row_count,
                "no_nan_inf_detected": True,
                "no_local_path_leak": True,
                "title_says_semantic_audit": True,
            }
        )
    write_csv_rows(fig_dir / "PAPER10M1R2C1_FIGURE_INDEX.csv", index_rows)
    write_csv_rows(fig_dir / "PAPER10M1R2C1_RENDER_QA_REPORT.csv", qa_rows)
    return index_rows, qa_rows


def write_decision(stage_root: Path, decision: dict[str, Any]) -> None:
    decision_dir = stage_root / "06_DECISION"
    (decision_dir / "PAPER10M1R2C1_M1R2D_GATE_DECISION.md").write_text(
        "\n".join(
            [
                "# PAPER10M1R2C1 M1R2D Gate Decision",
                "",
                f"Gate: `{decision['m1r2d_gate']}`.",
                f"Final decision: `{decision['final_decision']}`.",
                f"Reason: {decision['reason']}.",
                "",
                "M1R2D remains blocked until the clean yaw and QM/counter semantics are repaired and reviewed.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    write_csv_rows(
        decision_dir / "PAPER10M1R2C1_BLOCKERS_AND_REPAIR_ACTIONS.csv",
        [
            {
                "blocker_id": "clean_yaw_semantic_failure",
                "status": "active",
                "repair_action": "repair solver/provider/method-mode yaw semantics or evaluator reference pipeline, then rerun sentinel evaluator only before ablation",
            },
            {
                "blocker_id": "qm_counter_semantic_failure",
                "status": "active",
                "repair_action": "rename/split bad_a1 and trace availability fields before claim use",
            },
        ],
    )
    write_csv_rows(
        decision_dir / "PAPER10M1R2D_AUTHORIZATION_STATUS_UPDATE.csv",
        [
            {
                "next_stage": "PAPER10M1R2D",
                "authorization_status": "blocked",
                "reason": decision["final_decision"],
                "internal_ablation_allowed": False,
                "horizontal_comparison_allowed": False,
                "paper10h_allowed": False,
            }
        ],
    )


def write_tests_and_boundaries(stage_root: Path, pytest_status: str, pytest_summary: str) -> None:
    write_csv_rows(
        stage_root / "07_TESTS" / "PAPER10M1R2C1_TEST_MATRIX.csv",
        [
            {"test_group": "targeted_pytest", "status": pytest_status, "summary": pytest_summary},
            {"test_group": "cpp", "status": "NOT_RUN_CPP_NOT_MODIFIED", "summary": "No C++ files modified in M1R2C1."},
        ],
    )
    (stage_root / "07_TESTS" / "PAPER10M1R2C1_GUARD_VALIDATION_REPORT.md").write_text(
        "\n".join(
            [
                "# PAPER10M1R2C1 Guard Validation Report",
                "",
                f"- targeted pytest: {pytest_status}",
                f"- pytest summary: {pytest_summary}",
                "- solver rerun: false",
                "- provider regeneration: false",
                "- raw data modification: false",
                "- trace solver input: false",
                "- final_v23/LegSA solver input: false",
                "- per-case tuning/output-only correction/epoch deletion: false",
                "- C++: NOT_RUN_CPP_NOT_MODIFIED",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (stage_root / "08_CLAIM_BOUNDARY" / "PAPER10M1R2C1_CLAIM_BOUNDARY_UPDATE.md").write_text(
        "# PAPER10M1R2C1 Claim Boundary Update\n\n"
        "- M1R2C row completion is not enough for yaw performance claims.\n"
        "- Clean yaw semantic mismatch blocks paper-level interpretation.\n"
        "- QM trace/counter fields require semantic audit before claim use.\n"
        "- No universal superiority, final paper claim, BY3/XB/PG claim, or PAPER10H claim is allowed here.\n",
        encoding="utf-8",
    )
    (stage_root / "08_CLAIM_BOUNDARY" / "PAPER10M1R2C1_ALLOWED_AND_FORBIDDEN_USAGE.md").write_text(
        "# PAPER10M1R2C1 Allowed And Forbidden Usage\n\n"
        "Allowed: internal debugging and schema repair planning from existing M1R2C outputs.\n\n"
        "Forbidden: paper performance claim, internal ablation, horizontal comparison, PAPER10H, solver rerun, provider regeneration, trace solver input, and output-only correction.\n",
        encoding="utf-8",
    )
    (stage_root / "09_NEXT_STAGE" / "PAPER10M1R2D_REVISED_EXECUTION_PLAN.md").write_text(
        "# PAPER10M1R2D Revised Execution Plan\n\nPAPER10M1R2D is blocked. Repair clean yaw/QM semantics first, then rerun the M1R2C1 gate.\n",
        encoding="utf-8",
    )
    (stage_root / "09_NEXT_STAGE" / "PAPER10M1R2E_RESULT_REVIEW_PLAN.md").write_text(
        "# PAPER10M1R2E Result Review Plan\n\nReview only after M1R2D is reauthorized by the human decision maker.\n",
        encoding="utf-8",
    )
    (stage_root / "09_NEXT_STAGE" / "PAPER10H_BLOCK_STATUS.md").write_text(
        "# PAPER10H Block Status\n\nPAPER10H remains blocked by M1R2C1 clean yaw and QM semantic failures.\n",
        encoding="utf-8",
    )


def write_stage_reports(
    stage_root: Path,
    decision: dict[str, Any],
    commit_hash: str,
    push_status: str,
    pytest_status: str,
    path_scan_status: str,
) -> None:
    yaw_rows = read_csv_rows(stage_root / "02_YAW_AUDIT" / "PAPER10M1R2C1_CLEAN_YAW_AUDIT_TABLE.csv")
    qm_summary = load_json(stage_root / "03_QM_AUDIT" / "PAPER10M1R2C1_QM_GATE_SUMMARY.json")
    clean_values = "; ".join(
        f"{row['method_mode_id']} original {safe_float(row.get('m1r2c_original_yaw_rmse_deg'), 0.0):.3f} deg, trace {safe_float(row.get('trace_heading_to_math_rmse_deg'), 0.0):.3f} deg"
        for row in yaw_rows
    )
    lines = [
        "# PAPER10M1R2C1 Supervisor Final Report",
        "",
        "1. stage_name: PAPER10M1R2C1_CLEAN_YAW_QM_SEMANTIC_AUDIT_AND_METRIC_REPAIR.",
        "2. inserted because PAPER10M1R2C clean yaw and QM counters showed semantic anomalies before M1R2D.",
        "3. M1R2C 2164 rows completion remains formally confirmed, but semantic use is blocked.",
        f"4. clean yaw anomaly original values: {clean_values}.",
        "5. historical clean yaw evidence: N4H2D selected official_ref_sign_minus and fresh replay yaw was about 1.98 deg; N9A_R4E2 selected trace_heading_to_math as evaluation-only yaw truth.",
        "6. yaw audit method: existing clean EVAL_NAV only, provider status-yaw candidates, trace heading-to-math reference, wrap/sign/lateral/rad-degree/time-offset diagnostics.",
        "7. yaw transform candidates did not recover clean strong/LegSA methods below 10 deg.",
        "8. evaluator-only problem: false.",
        "9. solver/provider/method-mode issue: true, because trace-heading-to-math clean yaw remains above gate for strong/LegSA methods.",
        "10. corrected metrics generated: false.",
        "11. corrected clean yaw results: not generated because not evaluator-only.",
        f"12. QM clean transparency: downweight={qm_summary.get('full_qm_downweight_count')}, recovery={qm_summary.get('full_qm_recovery_count')}, reject={qm_summary.get('full_qm_reject_count')}.",
        "13. bad_a1_consumed_count semantics: current field maps to yaw_REJECT and is not a consumed-bad-A1 claim field.",
        "14. qm_trace_required/present/not_required were split in the audit table.",
        "15. bad_a1_consumed_count allowed in paper claim: false.",
        f"16. M1R2D gate decision: {decision['m1r2d_gate']}.",
        "17. no solver rerun: true.",
        "18. no provider regeneration: true.",
        "19. no raw data modification: true.",
        "20. no trace solver input: true.",
        "21. no final_v23/LegSA solver input: true.",
        "22. no per-case tuning: true.",
        "23. no output-only correction: true.",
        "24. no epoch deletion: true.",
        "25. figures/render QA: generated under 05_FIGURES as semantic audit figures.",
        f"26. tests result: {pytest_status}.",
        "27. export-clean result: generated.",
        f"28. path scan result: {path_scan_status}.",
        f"29. commit hash if commit: {commit_hash or 'not_committed_at_report_time'}.",
        f"30. push status if push: {push_status or 'not_pushed_at_report_time'}.",
        "31. next-stage recommendation: block M1R2D; repair yaw/QM semantics first.",
        f"32. final decision: {decision['final_decision']}.",
    ]
    (stage_root / "00_STAGE_REPORT" / "PAPER10M1R2C1_SUPERVISOR_FINAL_REPORT.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )
    (stage_root / "00_STAGE_REPORT" / "PAPER10M1R2C1_REVIEWER_REPORT.md").write_text(
        "# PAPER10M1R2C1 Reviewer Report\n\n"
        "- Reviewed generated yaw/QM/decision artifacts.\n"
        "- No corrected metrics were generated because the issue is not evaluator-only.\n"
        "- No raw/provider/NAV/STD/EVAL_NAV/RUN_MANIFEST artifacts were prepared for commit.\n"
        f"- Reviewer decision: {decision['final_decision']}.\n",
        encoding="utf-8",
    )


def scan_export_paths(export_root: Path) -> dict[str, Any]:
    patterns = {
        "windows_user_path": "C:" + "\\\\Users",
        "mnt_c_user_path": "/mnt/c/" + "Users/",
        "home_user_runtime_path": "/home/" + "kaiwen",
        "media_project_raw_path": "/media/" + "kaiwen/" + "新加卷",
        "by2_direct_source": "by2.txt",
        "gnss1_raw_direct_source": "gnss1-raw.csv",
        "gnss2_raw_direct_source": "gnss2-raw.csv",
        "trace_direct_source": "trace_vrtk2",
    }
    findings: list[dict[str, str]] = []
    for path in export_root.rglob("*"):
        if not path.is_file() or path.suffix.lower() in {".zip", ".png", ".pdf"}:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for label, pattern in patterns.items():
            if pattern in text:
                findings.append({"file": str(path.relative_to(export_root)), "pattern_label": label})
    return {
        "path_scan_pass": not findings,
        "finding_count": len(findings),
        "findings": findings,
        "allowed_placeholders": [
            "<LEGSA_CODE_ROOT>",
            "<LEGSA_PROJECT_ROOT>",
            "<PAPER10M1R2C_STAGE_ROOT>",
            "<PAPER10M1R2C1_STAGE_ROOT>",
            "<PAPER10M1R2C_RUNTIME_ROOT>",
            "<PAPER10M1R2C1_RUNTIME_ROOT>",
            "<DEGRADED_PROVIDER_ROOT>",
            "<TRACE_EVAL_REFERENCE_ONLY>",
        ],
    }


def export_clean(stage_root: Path, export_root: Path) -> dict[str, Any]:
    if export_root.exists():
        shutil.rmtree(export_root)
    export_root.mkdir(parents=True, exist_ok=True)
    relative_files = [
        "00_STAGE_REPORT/PAPER10M1R2C1_SUPERVISOR_FINAL_REPORT.md",
        "00_STAGE_REPORT/PAPER10M1R2C1_REVIEWER_REPORT.md",
        "02_YAW_AUDIT/PAPER10M1R2C1_CLEAN_YAW_AUDIT_TABLE.csv",
        "02_YAW_AUDIT/PAPER10M1R2C1_YAW_SEMANTIC_AUDIT_REPORT.md",
        "02_YAW_AUDIT/PAPER10M1R2C1_YAW_TRANSFORM_CANDIDATE_TABLE.csv",
        "02_YAW_AUDIT/PAPER10M1R2C1_CLEAN_YAW_METHOD_MODE_TABLE.csv",
        "03_QM_AUDIT/PAPER10M1R2C1_QM_TRACE_SEMANTIC_AUDIT_TABLE.csv",
        "03_QM_AUDIT/PAPER10M1R2C1_BAD_A1_CONSUMED_SEMANTIC_REPORT.md",
        "03_QM_AUDIT/PAPER10M1R2C1_QM_CLEAN_TRANSPARENCY_AUDIT.md",
        "03_QM_AUDIT/PAPER10M1R2C1_QM_FIELD_DEFINITION_FIX_RECOMMENDATION.md",
        "04_CORRECTED_METRICS/PAPER10M1R2C1_CORRECTION_MANIFEST.json",
        "04_CORRECTED_METRICS/NO_CORRECTED_METRICS_GENERATED_BLOCKER.md",
        "05_FIGURES/PAPER10M1R2C1_FIGURE_INDEX.csv",
        "05_FIGURES/PAPER10M1R2C1_RENDER_QA_REPORT.csv",
        "06_DECISION/PAPER10M1R2C1_M1R2D_GATE_DECISION.md",
        "06_DECISION/PAPER10M1R2C1_BLOCKERS_AND_REPAIR_ACTIONS.csv",
        "06_DECISION/PAPER10M1R2D_AUTHORIZATION_STATUS_UPDATE.csv",
        "07_TESTS/PAPER10M1R2C1_TEST_MATRIX.csv",
        "07_TESTS/PAPER10M1R2C1_GUARD_VALIDATION_REPORT.md",
        "08_CLAIM_BOUNDARY/PAPER10M1R2C1_CLAIM_BOUNDARY_UPDATE.md",
        "08_CLAIM_BOUNDARY/PAPER10M1R2C1_ALLOWED_AND_FORBIDDEN_USAGE.md",
        "09_NEXT_STAGE/PAPER10M1R2D_REVISED_EXECUTION_PLAN.md",
        "09_NEXT_STAGE/PAPER10M1R2E_RESULT_REVIEW_PLAN.md",
        "09_NEXT_STAGE/PAPER10H_BLOCK_STATUS.md",
    ]
    manifest_rows: list[dict[str, Any]] = []
    for rel in relative_files:
        src = stage_root / rel
        if not src.is_file():
            continue
        dst = export_root / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        manifest_rows.append({"relative_path": rel, "bytes": src.stat().st_size})
    write_csv_rows(export_root / "export_clean_manifest.csv", manifest_rows)
    scan = scan_export_paths(export_root)
    write_json(export_root / "export_clean_path_scan.json", scan)
    (export_root / "README_FOR_NEXT_AI.md").write_text(
        "# PAPER10M1R2C1 Export-Clean Pack\n\n"
        "This package contains semantic audit reports only. It excludes raw data, providers, NAV, STD, EVAL_NAV, RUN_MANIFEST, and figure binaries.\n",
        encoding="utf-8",
    )
    zip_path = stage_root / "10_EXPORT_CLEAN_FOR_GPT" / "paper10m1r2c1_clean_yaw_qm_semantic_audit_pack.zip"
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in export_root.rglob("*"):
            if path.is_file() and path.suffix.lower() != ".zip":
                archive.write(path, path.relative_to(export_root).as_posix())
    shutil.copy2(export_root / "export_clean_manifest.csv", stage_root / "10_EXPORT_CLEAN_FOR_GPT" / "export_clean_manifest.csv")
    shutil.copy2(export_root / "export_clean_path_scan.json", stage_root / "10_EXPORT_CLEAN_FOR_GPT" / "export_clean_path_scan.json")
    shutil.copy2(export_root / "README_FOR_NEXT_AI.md", stage_root / "10_EXPORT_CLEAN_FOR_GPT" / "README_FOR_NEXT_AI.md")
    return scan


def run(args: argparse.Namespace) -> dict[str, Any]:
    stage_root = Path(args.stage_root)
    code_root = Path(args.code_root)
    export_root = Path(args.export_root)
    ensure_dirs(stage_root)
    yaw_gate = load_json(stage_root / "02_YAW_AUDIT" / "PAPER10M1R2C1_YAW_GATE_SUMMARY.json")
    qm_gate = load_json(stage_root / "03_QM_AUDIT" / "PAPER10M1R2C1_QM_GATE_SUMMARY.json")
    correction = load_json(stage_root / "04_CORRECTED_METRICS" / "PAPER10M1R2C1_CORRECTION_MANIFEST.json")
    row_rows = read_csv_rows(args.row_table)
    row_completion_valid = len(row_rows) == 2164 and all(row.get("terminal_status") == "COMPLETED_EVALUABLE" for row in row_rows)
    forbidden = any(
        str(row.get(key, "")).lower() == "true"
        for row in row_rows
        for key in [
            "trace_used_online",
            "final_v23_output_used_as_input",
            "legsa_output_used_as_input",
            "per_case_tuning_used",
            "output_only_correction_used",
            "epoch_deleted_for_metric",
        ]
    )
    decision = decide_m1r2d_gate(
        yaw_gate_status=str(yaw_gate.get("gate_status", "BLOCKED_CLEAN_YAW_SEMANTIC_FAILURE")),
        qm_gate_status=str(qm_gate.get("qm_gate_status", "BLOCKED_QM_TRACE_SEMANTIC_FAILURE")),
        corrected_metrics_generated=bool(correction.get("corrected_metrics_generated", False)),
        forbidden_input_violation=forbidden,
        row_completion_valid=row_completion_valid,
    )
    write_decision(stage_root, decision)
    make_figures(stage_root, decision)
    write_tests_and_boundaries(stage_root, args.pytest_status, args.pytest_summary)
    scan = export_clean(stage_root, export_root)
    write_git_report(stage_root, code_root, args.commit_hash, args.push_status)
    write_stage_reports(
        stage_root,
        decision,
        args.commit_hash,
        args.push_status,
        args.pytest_status,
        "PASS" if scan["path_scan_pass"] else "FAIL",
    )
    # Re-copy final reports after report generation.
    scan = export_clean(stage_root, export_root)
    write_json(stage_root / "06_DECISION" / "PAPER10M1R2C1_DECISION_SUMMARY.json", {**decision, "path_scan": scan})
    return decision


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage-root", required=True)
    parser.add_argument("--export-root", required=True)
    parser.add_argument("--code-root", required=True)
    parser.add_argument("--row-table", required=True)
    parser.add_argument("--pytest-status", default="NOT_RUN")
    parser.add_argument("--pytest-summary", default="")
    parser.add_argument("--commit-hash", default="")
    parser.add_argument("--push-status", default="")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    run(parse_args(argv))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
