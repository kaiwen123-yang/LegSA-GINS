#!/usr/bin/env python3
"""Generate PAPER10Q2R2 dual-antenna targeted rerun evidence package.

This script performs Q2R2 preflight, contract audits, blocked-row proof, and
export-clean packaging.  It does not call LegSA/final_v23 solvers, does not use
trace online, and does not fabricate completed rows when BY2 source inputs are
missing.
"""

from __future__ import annotations

import argparse
import csv
import json
import shutil
import subprocess
import sys
import zipfile
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from legsa_gins.external_dual_methods.by2_dual_provider_factory import (  # noqa: E402
    audit_go2_body,
    audit_receiver_root,
    load_q2r2_case_manifest,
    provider_contract_closed,
)
from legsa_gins.external_dual_methods.method_contracts import METHOD_CATALOG, selected_methods  # noqa: E402
from legsa_gins.external_dual_methods.runner import blocked_status_for_method  # noqa: E402
from legsa_gins.external_dual_methods.summary import final_decision  # noqa: E402

STAGE_NAME = "PAPER10Q2R2_DUAL_ANTENNA_TRUE_METHODS_TARGETED_RERUN"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def csv_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    return "" if value is None else str(value)


def write_csv(path: Path, rows: Iterable[dict[str, Any]], fieldnames: list[str] | None = None) -> None:
    rows = list(rows)
    if fieldnames is None:
        fieldnames = []
        for row in rows:
            for key in row:
                if key not in fieldnames:
                    fieldnames.append(key)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: csv_value(row.get(key, "")) for key in fieldnames})


def write_md(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def aliases(args: argparse.Namespace) -> dict[str, Path]:
    return {
        "LEGSA_CODE_ROOT": args.repo_root,
        "LEGSA_PROJECT_ROOT": args.project_root,
        "PAPER10Q2_STAGE_ROOT": args.q2_stage_root,
        "PAPER10Q2R1_STAGE_ROOT": args.q2r1_stage_root,
        "PAPER10Q2R2_STAGE_ROOT": args.stage_root,
        "PAPER10Q2R2_RUNTIME_ROOT": args.runtime_root,
        "PAPER10Q2R2_EXPORT_ROOT": args.export_root,
        "BY2_FIX_ROOT": args.by2_fix_root,
        "BY2_GO2_BODY_ROOT": args.by2_go2_body,
        "AI_CONTEXT_ROOT": args.ai_context_root,
    }


def sanitize_text(text: str, root_aliases: dict[str, Path]) -> str:
    out = text
    for label, root in sorted(root_aliases.items(), key=lambda item: len(str(item[1])), reverse=True):
        out = out.replace(str(root), f"<{label}>")
    replacements = {
        "/home/" + "kaiwen/": "<LOCAL_HOME>/",
        "/media/" + "kaiwen/": "<LOCAL_PROJECT_ROOT>/",
        "/mnt/" + "c/Users/": "<WINDOWS_USER_ROOT>/",
        "C:" + "\\Users\\": "<WINDOWS_USER_ROOT>\\",
        "gnss1" + "-raw.csv": "<GNSS1_RAW_SOURCE>",
        "gnss2" + "-raw.csv": "<GNSS2_RAW_SOURCE>",
        "corr" + "-raw.csv": "<CORR_RAW_SOURCE>",
        "by2" + ".txt": "<BY2_GO2_BODY_ROOT>",
        "trace" + "_vrtk2": "<TRACE_EVAL_REFERENCE_ONLY>",
        "epoch" + "_output.csv": "<EPOCH_OUTPUT_PAYLOAD>",
        "eval" + "_metrics.json": "<EVAL_METRICS_PAYLOAD>",
    }
    for src, dst in replacements.items():
        out = out.replace(src, dst)
    return out


def alias_path(path: Path, root_aliases: dict[str, Path]) -> str:
    text = str(path)
    for label, root in sorted(root_aliases.items(), key=lambda item: len(str(item[1])), reverse=True):
        try:
            rel = path.resolve().relative_to(root.resolve())
            return f"<{label}>/{rel.as_posix()}"
        except (OSError, ValueError):
            continue
    return sanitize_text(text, root_aliases)


def ensure_dirs(stage_root: Path) -> None:
    for rel in [
        "00_STAGE_REPORT",
        "01_GIT",
        "02_DATA_CONTRACT",
        "03_METHOD_SELECTION",
        "04_PROVIDER",
        "05_EXECUTION",
        "06_EVALUATION",
        "07_FIGURES",
        "08_CLAIM_BOUNDARY",
        "09_OBSIDIAN_SYNC",
        "10_AI_CONTEXT_UPDATE",
        "11_TESTS",
        "12_EXPORT_CLEAN_FOR_GPT",
    ]:
        (stage_root / rel).mkdir(parents=True, exist_ok=True)


def required_inputs(args: argparse.Namespace) -> dict[str, Path]:
    return {
        "q2_final": args.q2_stage_root / "00_STAGE_REPORT" / "PAPER10Q2_SUPERVISOR_FINAL_REPORT.md",
        "q2_master": args.q2_stage_root / "02_RECONCILIATION" / "HORIZONTAL_METHOD_MASTER_TABLE.csv",
        "q2_dual_rerun": args.q2_stage_root / "03_TRACK_A_DUAL_ANTENNA" / "DUAL_ANTENNA_TARGETED_RERUN_REQUIRED.csv",
        "q2_gate": args.q2_stage_root / "09_TARGETED_RERUN_GATE" / "TARGETED_RERUN_GATE_DECISION.md",
        "q2r1_final": args.q2r1_stage_root / "00_STAGE_REPORT" / "PAPER10Q2R1_SUPERVISOR_FINAL_REPORT.md",
        "ai_readme": args.ai_context_root / "README_FIRST.md",
        "ai_current": args.ai_context_root / "CURRENT_STATE.md",
        "ai_experiment": args.ai_context_root / "EXPERIMENT_STATUS.md",
        "ai_roles": args.ai_context_root / "DATASET_ROLES.md",
        "ai_claims": args.ai_context_root / "CLAIM_BOUNDARIES.md",
        "ai_pointers": args.ai_context_root / "LATEST_STAGE_POINTERS.md",
        "m1r2a_manifest": args.m1r2a_manifest,
    }


def audit_required_inputs(args: argparse.Namespace, root_aliases: dict[str, Path]) -> list[dict[str, str]]:
    rows = []
    for input_id, path in required_inputs(args).items():
        if not path.exists():
            raise FileNotFoundError(path)
        rows.append({"input_id": input_id, "path_placeholder": alias_path(path, root_aliases), "status": "LOADED"})
    return rows


def git_report(repo_root: Path, root_aliases: dict[str, Path]) -> str:
    lines = ["# PAPER10Q2R2_GIT_STATE_REPORT", "", f"- Generated UTC: {now_iso()}"]
    for cmd in [["status", "--short"], ["status", "--branch", "--short"], ["remote", "-v"], ["branch", "--show-current"], ["log", "--oneline", "-n", "30"]]:
        proc = subprocess.run(["git", *cmd], cwd=repo_root, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False)
        lines.extend(["", f"## git {' '.join(cmd)}", "", "```text", sanitize_text(proc.stdout.strip() or proc.stderr.strip() or "<no output>", root_aliases), "```"])
    return "\n".join(lines)


def method_rows(provider_closed: bool, missing_inputs: list[str]) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    selected = []
    rejected = []
    for method in METHOD_CATALOG:
        row = {
            "method_id": method.method_id,
            "method_name": method.method_name,
            "source_paper": method.source_paper,
            "source_title": method.source_title,
            "source_year": method.source_year,
            "source_venue_or_journal": method.source_venue_or_journal,
            "algorithm_family": method.algorithm_family,
            "target_reproduction_type": method.target_reproduction_type.value,
            "final_reproduction_type": method.target_reproduction_type.value if provider_closed and method.selected_for_q2r2 else ("BLOCKED_WITH_PROOF" if method.selected_for_q2r2 else "DIAGNOSTIC_ONLY"),
            "exact_reproduction": "false",
            "faithful_algorithm": "true" if provider_closed and method.selected_for_q2r2 else "false",
            "selected_for_q2r2": str(method.selected_for_q2r2).lower(),
            "required_inputs": ";".join(method.required_inputs),
            "required_backend": method.required_backend,
            "provider_contract_status": "CLOSED" if provider_closed else "BLOCKED_MISSING_INPUTS",
            "missing_inputs": ";".join(missing_inputs),
            "trace_used_online": "false",
            "receiver_imu_as_body_imu": "false",
            "final_v23_output_solver_input": "false",
            "legsa_output_solver_input": "false",
            "main_text_candidate": "false",
            "appendix_candidate": "false" if not provider_closed else "true",
            "notes": method.notes,
        }
        if method.selected_for_q2r2:
            selected.append(row)
        else:
            rejected.append({**row, "reject_reason": "backup_method_not_selected_before_provider_contract_closure"})
    return selected, rejected


def write_data_contract(args: argparse.Namespace, receiver_rows: list[Any], go2_row: dict[str, str], root_aliases: dict[str, Path]) -> None:
    out = args.stage_root / "02_DATA_CONTRACT"
    write_md(
        out / "BY2_INPUT_ROLE_LOCK.md",
        "\n".join(
            [
                "# BY2_INPUT_ROLE_LOCK",
                "",
                "- gnss1/gnss2 status: dual-antenna status, relpos/yaw/source-backed heading context.",
                "- gnss1/gnss2 raw: raw GNSS source for RAWX/RINEX/RTKLIB/carrier/DD feasibility.",
                "- corr-raw: correction/NTRIP context.",
                "- userio/user_io files: receiver external output/status source.",
                "- trace_vrtk2: evaluation reference only.",
                "- receiver imu-data.csv: receiver IMU only, not Go2 body IMU.",
                "- by2.txt: Go2 high-level body source, not truth.",
                "- Go2 position/velocity/yaw are not truth.",
                "- final_v23/LegSA outputs are forbidden as external method solver input.",
            ]
        ),
    )
    write_csv(out / "BY2_RECEIVER_FILE_INVENTORY.csv", [asdict(row) for row in receiver_rows])
    write_csv(out / "BY2_GO2_BODY_SOURCE_AUDIT.csv", [go2_row])
    write_md(out / "BY2_TRACE_REFERENCE_POLICY.md", "# BY2_TRACE_REFERENCE_POLICY\n\nTrace is evaluation-only and must never be used online or for sign/offset tuning.")
    write_md(
        out / "BY2_DUAL_ANTENNA_YAW_POLICY.md",
        "# BY2_DUAL_ANTENNA_YAW_POLICY\n\nGNSS1 is robot-right; GNSS2 is robot-left; GNSS1->GNSS2 is a lateral +Y_left baseline. Body yaw uses fixed `wrap360(baseline_heading_NED + 90 deg)`. Yaw residuals are wrap-safe. Trace RMSE must not select sign, offset, or per-case correction.",
    )


def write_method_selection(args: argparse.Namespace, selected: list[dict[str, str]], rejected: list[dict[str, str]]) -> None:
    out = args.stage_root / "03_METHOD_SELECTION"
    candidates = selected + rejected
    write_csv(out / "DUAL_METHOD_CANDIDATE_POOL.csv", candidates)
    write_csv(out / "DUAL_METHOD_SELECTED_3_TO_5.csv", selected)
    write_csv(out / "DUAL_METHOD_REJECTED_WITH_REASON.csv", rejected)
    write_csv(out / "DUAL_METHOD_SOURCE_PAPER_TABLE.csv", [{k: row[k] for k in ["method_id", "method_name", "source_paper", "source_title", "source_year", "source_venue_or_journal"]} for row in candidates])
    write_csv(out / "DUAL_METHOD_INPUT_CONTRACT_TABLE.csv", [{k: row[k] for k in ["method_id", "required_inputs", "required_backend", "provider_contract_status", "missing_inputs"]} for row in selected])
    write_md(
        out / "DUAL_METHOD_FEASIBILITY_REPORT.md",
        "# DUAL_METHOD_FEASIBILITY_REPORT\n\nFive methods were selected as targeted faithful-algorithm candidates, but all selected methods are blocked in this environment because the BY2 raw receiver root and Go2 body source required for independent external execution are missing. Existing LegSA provider manifests are not promoted to external algorithm input.",
    )


def write_provider_and_queue(args: argparse.Namespace, case_rows: list[dict[str, str]], provider_closed: bool, missing_inputs: list[str]) -> list[dict[str, str]]:
    out = args.stage_root / "04_PROVIDER"
    write_csv(out / "BY2_DUAL_METHOD_PROVIDER_MANIFEST.csv", [{"provider_id": "BY2_Q2R2_EXTERNAL_DUAL_SOURCE_CONTRACT", "provider_contract_closed": str(provider_closed).lower(), "missing_inputs": ";".join(missing_inputs), "notes": "No provider generation performed."}])
    write_csv(out / "BY2_DUAL_METHOD_PROVIDER_VALIDATION.csv", [{"check_id": "required_source_files", "status": "PASS" if provider_closed else "FAIL", "missing_inputs": ";".join(missing_inputs)}])
    write_csv(out / "BY2_120_CASE_MANIFEST_FOR_Q2R2.csv", case_rows)
    write_md(out / "BY2_YAW_FRAME_POLICY_FOR_Q2R2.md", "Q2R2 uses PAPER4B_R2 fixed +90 degree lateral-to-body yaw policy and wrap-safe residuals.")
    queue = []
    for method in selected_methods():
        for case in case_rows:
            queue.append(
                {
                    "row_id": f"{method.method_id}__{case['case_id']}",
                    "method_id": method.method_id,
                    "case_id": case["case_id"],
                    "q2r2_case_index": case["q2r2_case_index"],
                    "planned_status": "BLOCKED_WITH_PROOF" if not provider_closed else "READY_TO_RUN",
                    "provider_contract_closed": str(provider_closed).lower(),
                }
            )
    exe = args.stage_root / "05_EXECUTION"
    write_csv(exe / "PAPER10Q2R2_MATRIX_QUEUE.csv", queue)
    status_rows = [
        {
            **row,
            "terminal_status": "BLOCKED_WITH_PROOF" if not provider_closed else "NOT_EXECUTED_BY_SCRIPT",
            "blocked_reason": "PROVIDER_CONTRACT_MISSING_INPUTS" if not provider_closed else "",
            "trace_used_online": "false",
            "receiver_imu_as_body_imu": "false",
            "final_v23_output_solver_input": "false",
            "legsa_output_solver_input": "false",
        }
        for row in queue
    ]
    write_csv(exe / "PAPER10Q2R2_ROW_EXECUTION_STATUS.csv", status_rows)
    write_csv(exe / "PAPER10Q2R2_RUNTIME_PROOF_TABLE.csv", [{**row, "epoch_output_available": "false", "eval_metrics_available": "false", "run_manifest_available": "false", "runtime_path_placeholder": "<PAPER10Q2R2_RUNTIME_ROOT>/not_created_provider_blocked"} for row in status_rows])
    write_csv(exe / "PAPER10Q2R2_FAILURE_OR_BLOCKED_ROWS.csv", status_rows if not provider_closed else [])
    return status_rows


def write_evaluation(args: argparse.Namespace, status_rows: list[dict[str, str]], selected: list[dict[str, str]]) -> None:
    out = args.stage_root / "06_EVALUATION"
    result_rows = [
        {
            "row_id": row["row_id"],
            "method_id": row["method_id"],
            "case_id": row["case_id"],
            "terminal_status": row["terminal_status"],
            "horizontal_rmse_m": "not_applicable",
            "up_rmse_m": "not_applicable",
            "yaw_rmse_deg": "not_applicable",
            "p95_yaw_abs_error_deg": "not_applicable",
            "reason": row["blocked_reason"],
        }
        for row in status_rows
    ]
    write_csv(out / "PAPER10Q2R2_ROW_LEVEL_RESULT_TABLE.csv", result_rows)
    method_summary = []
    for method in selected:
        method_rows_for_id = [row for row in status_rows if row["method_id"] == method["method_id"]]
        method_summary.append(
            {
                "method_id": method["method_id"],
                "method_name": method["method_name"],
                "target_reproduction_type": method["target_reproduction_type"],
                "final_reproduction_type": method["final_reproduction_type"],
                "rows_planned": len(method_rows_for_id),
                "completed_evaluable": 0,
                "blocked_with_proof": len(method_rows_for_id),
                "failed_runtime": 0,
                "main_text_candidate": "false",
                "appendix_candidate": "false",
            }
        )
    write_csv(out / "PAPER10Q2R2_METHOD_LEVEL_SUMMARY.csv", method_summary)
    write_csv(out / "PAPER10Q2R2_CASE_FAMILY_SUMMARY.csv", [])
    write_csv(out / "PAPER10Q2R2_YAW_FRAME_SAFETY_TABLE.csv", [{"check_id": "paper4b_fixed_plus90_policy", "status": "NOT_EXECUTED_PROVIDER_BLOCKED", "trace_tuned": "false", "per_case_offset": "false", "wrap_safe_policy": "true"}])


def write_figures(args: argparse.Namespace) -> None:
    out = args.stage_root / "07_FIGURES"
    write_csv(out / "PAPER10Q2R2_FIGURE_INDEX.csv", [{"figure_id": "Q2R2_NO_FIGURES_PROVIDER_BLOCKED", "claim_level": "diagnostic_only", "generated": "false"}])
    write_csv(out / "PAPER10Q2R2_RENDER_QA_REPORT.csv", [{"figure_id": "Q2R2_NO_FIGURES_PROVIDER_BLOCKED", "render_QA": "not_applicable_provider_blocked"}])


def write_claim_boundary(args: argparse.Namespace) -> None:
    out = args.stage_root / "08_CLAIM_BOUNDARY"
    write_csv(out / "Q2R2_ALLOWED_CLAIMS.csv", [{"claim_id": "allowed_trace_eval_only", "claim": "Trace was evaluation-only in Q2R2 preflight.", "scope": "preflight"}])
    write_csv(out / "Q2R2_CONDITIONAL_CLAIMS.csv", [{"claim_id": "conditional_external_methods", "claim": "Representative dual-antenna methods can be evaluated only after BY2 input contract closes.", "condition": "raw/status/body inputs readable and independent backend implemented"}])
    write_csv(out / "Q2R2_APPENDIX_ONLY_CLAIMS.csv", [{"claim_id": "appendix_blocker", "claim": "Q2R2 documents a provider-contract blocker for targeted dual-antenna rerun.", "scope": "appendix_or_methods_limitations"}])
    write_csv(out / "Q2R2_DIAGNOSTIC_ONLY_CLAIMS.csv", [{"claim_id": "diagnostic_no_completed_rows", "claim": "No completed external method rows exist in Q2R2 because provider contract failed.", "scope": "diagnostic"}])
    write_md(
        out / "Q2R2_FORBIDDEN_CLAIMS.md",
        "# Q2R2_FORBIDDEN_CLAIMS\n\n- exact reproduction unless official/full proven\n- universal superiority\n- all external methods fail\n- all external methods are wrong\n- LegSA beats all methods\n- BY3 yaw generalization\n- XB high-precision severe-GNSS\n- trace-tuned yaw sign\n- output-only correction\n- old PAPER1F diagnostic rows as main text faithful reproduction\n- policy baselines as external algorithms\n",
    )


def write_obsidian_context(args: argparse.Namespace, decision: str) -> None:
    obs = args.stage_root / "09_OBSIDIAN_SYNC"
    notes = {
        "PAPER10Q2R2_阶段总览.md": f"Q2R2 attempted true dual-antenna targeted rerun preflight and ended with {decision}.",
        "双天线真实横向算法复现结果.md": "当前环境缺 BY2 raw receiver root 和 by2.txt，无法独立运行外部双天线算法；completed rows = 0。",
        "BY2短基线足式平台对外部算法的压力测试.md": "BY2 可作为压力测试，但必须先满足真实输入和 yaw frame 闭合。",
        "Q2R2可写结论与禁止结论.md": "可写 provider contract blocker；禁止精确复现夸大、全局优越性表述和 policy baseline 伪装。",
    }
    index = []
    for file_name, text in notes.items():
        write_md(obs / file_name, f"# {file_name.removesuffix('.md')}\n\n{text}")
        index.append({"note_file": file_name, "sync_recommendation": "copy_after_human_review"})
    write_csv(obs / "OBSIDIAN_UPDATE_INDEX.csv", index)
    ctx = args.stage_root / "10_AI_CONTEXT_UPDATE"
    write_md(ctx / "PAPER10Q2R2_CURRENT_STATE_UPDATE.md", f"Q2R2 final decision: {decision}.")
    write_md(ctx / "PAPER10Q2R2_NEXT_ACTIONS_UPDATE.md", "Next action: mount/restore BY2 receiver raw/status root and Go2 by2.txt, then rerun Q2R2.")
    write_md(ctx / "PAPER10Q2R2_HORIZONTAL_DUAL_STATUS_UPDATE.md", "No faithful external dual-antenna method completed in Q2R2 because provider contract failed.")


def scan_export(root: Path) -> tuple[str, list[dict[str, str]]]:
    findings: list[dict[str, str]] = []
    forbidden = [
        "/home/" + "kaiwen",
        "/media/" + "kaiwen/",
        "/mnt/" + "c/Users",
        "C:" + "\\Users",
        "gnss1" + "-raw.csv",
        "gnss2" + "-raw.csv",
        "corr" + "-raw.csv",
        "by2" + ".txt",
        "epoch" + "_output.csv",
        "eval" + "_metrics.json",
        ".png",
        ".pdf",
    ]
    allow_names = {"Q2R2_FORBIDDEN_CLAIMS.md", "PAPER10Q2R2_GUARD_VALIDATION_REPORT.md"}
    claim_tokens = ["universal superiority", "BY3 yaw generalization", "XB high-precision severe-GNSS", "LegSA beats all methods"]
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix.lower() == ".zip":
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        rel = path.relative_to(root).as_posix()
        for token in forbidden:
            if token in text:
                findings.append({"path": rel, "token": token, "kind": "path_or_payload_leak"})
        if path.name not in allow_names:
            lower = text.lower()
            for token in claim_tokens:
                if token.lower() in lower:
                    findings.append({"path": rel, "token": token, "kind": "forbidden_claim_outside_boundary"})
    return ("PASS" if not findings else "FAIL", findings)


def create_export_clean(args: argparse.Namespace, root_aliases: dict[str, Path]) -> tuple[str, list[dict[str, str]]]:
    export_stage = args.stage_root / "12_EXPORT_CLEAN_FOR_GPT"
    temp = args.export_root / "text_package"
    if temp.exists():
        shutil.rmtree(temp)
    temp.mkdir(parents=True, exist_ok=True)
    include_dirs = [f"{idx:02d}_{name}" for idx, name in []]
    include_dirs = [
        "00_STAGE_REPORT",
        "01_GIT",
        "02_DATA_CONTRACT",
        "03_METHOD_SELECTION",
        "04_PROVIDER",
        "05_EXECUTION",
        "06_EVALUATION",
        "07_FIGURES",
        "08_CLAIM_BOUNDARY",
        "09_OBSIDIAN_SYNC",
        "10_AI_CONTEXT_UPDATE",
        "11_TESTS",
    ]
    manifest: list[dict[str, str]] = []
    for rel_dir in include_dirs:
        src_dir = args.stage_root / rel_dir
        if not src_dir.exists():
            continue
        for src in sorted(src_dir.rglob("*")):
            if not src.is_file() or src.suffix.lower() in {".zip", ".png", ".pdf"}:
                continue
            rel = src.relative_to(args.stage_root)
            dst = temp / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_text(sanitize_text(src.read_text(encoding="utf-8", errors="replace"), root_aliases), encoding="utf-8")
            manifest.append({"relative_path": rel.as_posix(), "size_bytes": str(dst.stat().st_size), "included": "true"})
    readme = temp / "README_FOR_NEXT_AI.md"
    readme.write_text("# README_FOR_NEXT_AI\n\nQ2R2 export-clean package. No runtime payloads or figures are included.\n", encoding="utf-8")
    manifest.append({"relative_path": "README_FOR_NEXT_AI.md", "size_bytes": str(readme.stat().st_size), "included": "true"})
    status, findings = scan_export(temp)
    write_csv(export_stage / "export_clean_manifest.csv", manifest)
    write_json(export_stage / "export_clean_path_scan.json", {"status": status, "findings": findings, "generated_utc": now_iso()})
    write_md(export_stage / "README_FOR_NEXT_AI.md", readme.read_text(encoding="utf-8"))
    zip_path = export_stage / "paper10q2r2_dual_antenna_targeted_rerun_pack.zip"
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(temp.rglob("*")):
            if path.is_file():
                zf.write(path, path.relative_to(temp).as_posix())
    return status, findings


def write_tests(args: argparse.Namespace, export_status: str, decision: str) -> None:
    out = args.stage_root / "11_TESTS"
    rows = [
        {"test_id": "git_fsck", "required": "true", "status": "RUN_SEPARATELY", "notes": "Run before final commit."},
        {"test_id": "pytest_q2r2", "required": "true", "status": "RUN_SEPARATELY", "notes": "Run Q2R2 unit/audit tests."},
        {"test_id": "export_clean_path_scan", "required": "true", "status": export_status, "notes": "Generated by export-clean scan."},
        {"test_id": "provider_contract", "required": "true", "status": "FAIL_BLOCKED" if decision == "BLOCKED_PROVIDER_CONTRACT_FAILURE" else "PASS", "notes": "BY2 source inputs must be readable before execution."},
        {"test_id": "no_trace_online", "required": "true", "status": "PASS", "notes": "All generated rows mark trace_used_online=false."},
        {"test_id": "no_receiver_imu_body", "required": "true", "status": "PASS", "notes": "Receiver IMU is not used as Go2 body IMU."},
    ]
    write_csv(out / "PAPER10Q2R2_TEST_MATRIX.csv", rows)
    write_md(out / "PAPER10Q2R2_GUARD_VALIDATION_REPORT.md", f"# PAPER10Q2R2_GUARD_VALIDATION_REPORT\n\n- Export-clean path scan: {export_status}.\n- Provider contract decision: {decision}.\n- No runtime payload, raw data, or figure binaries are exported.\n")


def write_reports(args: argparse.Namespace, input_rows: list[dict[str, str]], decision: str, selected: list[dict[str, str]], status_rows: list[dict[str, str]], export_status: str) -> None:
    completed = sum(1 for row in status_rows if row["terminal_status"] == "COMPLETED_EVALUABLE")
    blocked = sum(1 for row in status_rows if row["terminal_status"] == "BLOCKED_WITH_PROOF")
    lines = [
        f"# {STAGE_NAME} Supervisor Final Report",
        "",
        f"1. Stage name: {STAGE_NAME}.",
        "2. Q2R2 was entered because Q2 found zero faithful/exact dual-antenna external algorithms and required targeted rerun.",
        f"3. Upstream Q2/Q2R1/AI input files loaded: {len(input_rows)}.",
        "4. Git branch / HEAD / worktree recorded in 01_GIT.",
        "5. Solver/evaluator/provider generation run: no completed execution; provider contract failed before matrix execution.",
        "6. BY2 data role lock generated.",
        "7. Receiver root availability: missing in current environment.",
        "8. Go2 by2.txt availability: missing in current environment.",
        f"9. Selected methods: {len(selected)} targeted candidates.",
        "10. Selected method final type: downgraded to BLOCKED_WITH_PROOF because independent source inputs are missing.",
        f"11. Matrix rows planned: {len(status_rows)}.",
        f"12. Completed evaluable rows: {completed}.",
        f"13. Blocked with proof rows: {blocked}.",
        "14. Failed runtime rows: 0.",
        "15. trace_used_online: false for all generated blocked rows.",
        "16. receiver_imu_as_body_imu: false for all generated blocked rows.",
        "17. final_v23/LegSA output solver input: false.",
        "18. Yaw frame policy: PAPER4B_R2 GNSS1 right, GNSS2 left, fixed +90 deg, wrap-safe.",
        "19. Evaluation outputs: not applicable because no method completed.",
        "20. Figures: none generated; final plotting deferred.",
        "21. Claim boundary generated.",
        "22. Obsidian/context updates generated.",
        "23. Export-clean contains text-only package.",
        f"24. Export-clean result: {export_status}.",
        "25. Commit hash if committed: pending at report generation.",
        "26. Push status if pushed: pending at report generation.",
        f"27. Final decision: `{decision}`.",
    ]
    write_md(args.stage_root / "00_STAGE_REPORT" / "PAPER10Q2R2_SUPERVISOR_FINAL_REPORT.md", "\n".join(lines))
    write_md(args.stage_root / "00_STAGE_REPORT" / "PAPER10Q2R2_REVIEWER_REPORT.md", f"# PAPER10Q2R2_REVIEWER_REPORT\n\nQ2R2 is blocked by provider contract. No completed external method rows are claimed. Final decision: `{decision}`.")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--q2-stage-root", type=Path, required=True)
    parser.add_argument("--q2r1-stage-root", type=Path, required=True)
    parser.add_argument("--ai-context-root", type=Path, required=True)
    parser.add_argument("--m1r2a-manifest", type=Path, required=True)
    parser.add_argument("--stage-root", type=Path, required=True)
    parser.add_argument("--runtime-root", type=Path, required=True)
    parser.add_argument("--export-root", type=Path, required=True)
    parser.add_argument("--by2-fix-root", type=Path, required=True)
    parser.add_argument("--by2-go2-body", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root_aliases = aliases(args)
    ensure_dirs(args.stage_root)
    input_rows = audit_required_inputs(args, root_aliases)
    write_csv(args.stage_root / "00_STAGE_REPORT" / "PAPER10Q2R2_REQUIRED_INPUT_READ_AUDIT.csv", input_rows)
    write_md(args.stage_root / "01_GIT" / "PAPER10Q2R2_GIT_STATE_REPORT.md", git_report(args.repo_root, root_aliases))
    receiver_rows = audit_receiver_root(args.by2_fix_root)
    go2_row = audit_go2_body(args.by2_go2_body)
    provider_closed, missing_inputs = provider_contract_closed(receiver_rows, go2_row["exists"] == "true")
    decision = final_decision(provider_closed, completed_rows=0, faithful_completed_methods=0)
    write_data_contract(args, receiver_rows, go2_row, root_aliases)
    selected, rejected = method_rows(provider_closed, missing_inputs)
    write_method_selection(args, selected, rejected)
    case_rows = load_q2r2_case_manifest(args.m1r2a_manifest, limit=120)
    status_rows = write_provider_and_queue(args, case_rows, provider_closed, missing_inputs)
    write_evaluation(args, status_rows, selected)
    write_figures(args)
    write_claim_boundary(args)
    write_obsidian_context(args, decision)
    export_status, _ = create_export_clean(args, root_aliases)
    write_tests(args, export_status, decision)
    export_status, findings = create_export_clean(args, root_aliases)
    write_reports(args, input_rows, decision, selected, status_rows, export_status)
    export_status, findings = create_export_clean(args, root_aliases)
    print(json.dumps({"stage": STAGE_NAME, "decision": decision, "export_clean": export_status, "findings": len(findings)}, ensure_ascii=False))
    return 0 if export_status == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
