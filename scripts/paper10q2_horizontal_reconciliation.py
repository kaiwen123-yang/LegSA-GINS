#!/usr/bin/env python3
"""Generate PAPER10Q2 horizontal-comparison evidence reconciliation package.

Q2 is read/review/index only. It reconciles existing horizontal-comparison
assets, classifies reproduction fidelity, writes claim boundaries and targeted
rerun gates, and builds an export-clean text package. It never invokes solver,
evaluator, provider, degradation, or matrix runners.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import shutil
import subprocess
import sys
import zipfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.paper10q2_horizontal_claim_boundary import (  # noqa: E402
    classify_reproduction_type,
    flag_row,
    write_claim_boundary_outputs,
)
from scripts.paper10q2_horizontal_figure_indexer import (  # noqa: E402
    degraded_organization_rows,
    figure_package_summary,
    figure_review_rows,
    normal_organization_rows,
    replot_rows,
)
from scripts.paper10q2_next_prompt_builder import prompt_map  # noqa: E402

STAGE_NAME = "PAPER10Q2_HORIZONTAL_COMPARISON_EVIDENCE_RECONCILIATION_AND_TARGETED_RERUN_GATE"
FINAL_DECISION = "CONDITIONAL_PASS_PAPER10Q2_QA_REEXPORT_AND_DUAL_TARGETED_RERUN_REQUIRED"
GATE_DECISION = "TARGETED_RERUN_REQUIRED_DUAL_AND_QA"

MASTER_FIELDS = [
    "method_id",
    "method_name",
    "source_paper",
    "source_title",
    "source_year",
    "source_venue_or_journal",
    "source_link_or_doi",
    "algorithm_family",
    "source_stage",
    "dataset_scope",
    "dataset_rows_planned",
    "dataset_rows_completed",
    "dataset_rows_failed",
    "dataset_rows_blocked",
    "by2_rows_completed",
    "by3_rows_completed",
    "xb_rows_completed",
    "reproduction_type",
    "exact_reproduction",
    "faithful_algorithm",
    "faithful_module",
    "paper_derived_policy",
    "diagnostic_only",
    "blocked_with_proof",
    "frame_closed",
    "yaw_semantic_safe",
    "body_heading_convention_closed",
    "lateral_90_rule_safe",
    "enu_ned_safe",
    "yaw_wrap_safe",
    "trace_used_online",
    "final_v23_output_solver_input",
    "legsa_output_solver_input",
    "receiver_imu_as_body_imu",
    "row_level_available",
    "runtime_proof_available",
    "epoch_output_available",
    "eval_metrics_available",
    "render_QA_available",
    "official_code_attempted",
    "official_code_build_status",
    "provider_requirement_status",
    "missing_inputs",
    "missing_backend",
    "paper_location_recommendation",
    "claim_level",
    "rerun_required",
    "reexport_required",
    "replot_required",
    "notes",
]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def csv_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        if not math.isfinite(value):
            return ""
        return f"{value:.12g}"
    return "" if value is None else str(value)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def read_csv_optional(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    return read_csv(path)


def read_text_optional(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


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


def truthy(value: Any) -> bool:
    return str(value).strip().lower() in {"true", "1", "yes", "pass", "supported"}


def aliases(args: argparse.Namespace) -> dict[str, Path]:
    return {
        "LEGSA_CODE_ROOT": args.repo_root,
        "LEGSA_PROJECT_ROOT": args.project_root,
        "PAPER10Q2_STAGE_ROOT": args.stage_root,
        "PAPER10Q2_RECONCILED_ROOT": args.reconciled_root,
        "PAPER10Q2_EXPORT_ROOT": args.export_root,
        "HORIZONTAL_COMPARISON_ROOT": args.horizontal_root,
        "PAPER10Q1_STAGE_ROOT": args.q1_stage_root,
        "PAPER10M1R2E_STAGE_ROOT": args.m1r2e_stage_root,
        "M1R2C_R1_STAGE_ROOT": args.m1r2c_stage_root,
        "M1R2D_R1_STAGE_ROOT": args.m1r2d_stage_root,
        "AI_CONTEXT_ROOT": args.ai_context_root,
    }


def sanitize_text(text: str, root_aliases: dict[str, Path]) -> str:
    out = text
    for label, root in sorted(root_aliases.items(), key=lambda item: len(str(item[1])), reverse=True):
        out = out.replace(str(root), f"<{label}>")
    replacements = {
        "/home/" + "kaiwen/": "<LOCAL_HOME>/",
        "/mnt/" + "c/Users/": "<WINDOWS_USER_ROOT>/",
        "/mnt/" + "g/": "<G_DRIVE_ROOT>/",
        "C:" + "\\Users\\": "<WINDOWS_USER_ROOT>\\",
        "by2" + ".txt": "<BY2_GO2_BODY_SOURCE>",
        "by3" + ".txt": "<BY3_GO2_BODY_SOURCE>",
        "gnss1" + "-raw.csv": "<GNSS1_RAW_SOURCE>",
        "gnss2" + "-raw.csv": "<GNSS2_RAW_SOURCE>",
        "corr" + "-raw.csv": "<CORR_RAW_SOURCE>",
        "trace" + "_vrtk2": "<TRACE_EVAL_REFERENCE_ONLY>",
    }
    for src, dst in replacements.items():
        out = out.replace(src, dst)
    return out


def alias_path(path: Path | str, root_aliases: dict[str, Path]) -> str:
    text = str(path)
    try:
        resolved = Path(path).resolve()
    except OSError:
        return sanitize_text(text, root_aliases)
    for label, root in sorted(root_aliases.items(), key=lambda item: len(str(item[1])), reverse=True):
        try:
            rel = resolved.relative_to(root.resolve())
            return f"<{label}>/{rel.as_posix()}"
        except (OSError, ValueError):
            continue
    return sanitize_text(text, root_aliases)


def ensure_dirs(stage_root: Path, export_root: Path, reconciled_root: Path) -> None:
    for name in [
        "00_STAGE_REPORT",
        "01_GIT",
        "02_RECONCILIATION",
        "03_TRACK_A_DUAL_ANTENNA",
        "04_TRACK_B_QA_METHODS",
        "05_TRACK_C_LEGGED",
        "06_FIGURE_ORGANIZATION",
        "07_TEXT_SUMMARY",
        "08_CLAIM_BOUNDARY",
        "09_TARGETED_RERUN_GATE",
        "10_NEXT_PROMPTS",
        "11_OBSIDIAN_SYNC",
        "12_AI_CONTEXT_UPDATE",
        "13_TESTS",
        "14_EXPORT_CLEAN_FOR_GPT",
    ]:
        (stage_root / name).mkdir(parents=True, exist_ok=True)
    export_root.mkdir(parents=True, exist_ok=True)
    reconciled_root.mkdir(parents=True, exist_ok=True)


def run_git(repo_root: Path, args: list[str]) -> dict[str, Any]:
    proc = subprocess.run(
        ["git", *args],
        cwd=repo_root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    return {
        "cmd": "git " + " ".join(args),
        "returncode": proc.returncode,
        "stdout": proc.stdout.strip(),
        "stderr": proc.stderr.strip(),
    }


def required_upstream_paths(args: argparse.Namespace) -> dict[str, Path]:
    return {
        "q1_final": args.q1_stage_root / "00_STAGE_REPORT" / "PAPER10Q1_SUPERVISOR_FINAL_REPORT.md",
        "q1_master": args.q1_stage_root / "02_QM_EVIDENCE" / "QM_EVIDENCE_MASTER_TABLE.csv",
        "q1_scorecard": args.q1_stage_root / "02_QM_EVIDENCE" / "QM_EVIDENCE_SCORECARD.csv",
        "q1_forbidden": args.q1_stage_root / "05_CLAIM_BOUNDARY" / "QM_FORBIDDEN_CLAIMS.md",
        "m1r2e_final": args.m1r2e_stage_root / "00_STAGE_REPORT" / "PAPER10M1R2E_SUPERVISOR_FINAL_REPORT.md",
        "m1r2e_master": args.m1r2e_stage_root / "02_RESULT_REVIEW" / "PAPER10M1R2E_RESULT_REVIEW_MASTER_TABLE.csv",
        "m1r2e_module": args.m1r2e_stage_root / "03_MODULE_REVIEW" / "MODULE_CONTRIBUTION_FINAL_REVIEW.csv",
        "m1r2e_claim": args.m1r2e_stage_root / "06_CLAIM_BOUNDARY" / "PAPER10M1R2E_CLAIM_BOUNDARY_FREEZE.md",
        "m1r2c_final": args.m1r2c_stage_root / "00_STAGE_REPORT" / "PAPER10M1R2C_R1_SUPERVISOR_FINAL_REPORT.md",
        "m1r2d_final": args.m1r2d_stage_root / "00_STAGE_REPORT" / "PAPER10M1R2D_R1_SUPERVISOR_FINAL_REPORT.md",
        "ai_readme": args.ai_context_root / "README_FIRST.md",
        "ai_current": args.ai_context_root / "CURRENT_STATE.md",
        "ai_next": args.ai_context_root / "NEXT_ACTIONS.md",
        "ai_experiment": args.ai_context_root / "EXPERIMENT_STATUS.md",
        "ai_roles": args.ai_context_root / "DATASET_ROLES.md",
        "ai_claims": args.ai_context_root / "CLAIM_BOUNDARIES.md",
        "ai_pointers": args.ai_context_root / "LATEST_STAGE_POINTERS.md",
    }


def load_upstream(args: argparse.Namespace, root_aliases: dict[str, Path]) -> tuple[dict[str, Any], list[dict[str, str]]]:
    loaded: dict[str, Any] = {}
    rows: list[dict[str, str]] = []
    for name, path in required_upstream_paths(args).items():
        exists = path.exists()
        if not exists:
            raise FileNotFoundError(f"Required upstream file missing: {path}")
        if path.suffix == ".csv":
            payload: Any = read_csv(path)
            count = len(payload)
        else:
            payload = read_text_optional(path)
            count = len(payload)
        loaded[name] = payload
        rows.append(
            {
                "input_id": name,
                "path_alias": alias_path(path, root_aliases),
                "status": "LOADED",
                "record_or_char_count": str(count),
            }
        )
    return loaded, rows


def asset_paths(args: argparse.Namespace) -> dict[str, Path]:
    return {
        "lit_index": args.horizontal_root / "00_INDEX" / "LITERATURE_COMPARISON_INDEX.csv",
        "da_registry": args.horizontal_root / "DA_dual_antenna_attitude" / "method_registry.csv",
        "lc_registry": args.horizontal_root / "LC_gnss_ins_loose_coupling" / "method_registry.csv",
        "lse_registry": args.horizontal_root / "LSE_legged_state_estimation" / "method_registry.csv",
        "blocked_methods": args.horizontal_root / "diagnostic_failed_or_blocked" / "blocked_methods_table.csv",
        "paper4a_qa": args.repo_root
        / "suanfahengxiangduibi"
        / "PAPER4A_WRITE_READY_EVIDENCE_PACKAGE_AND_CONTEXT_SYNC"
        / "02_evidence_consolidation"
        / "qa_full_matrix_evidence.csv",
        "paper4a_da": args.repo_root
        / "suanfahengxiangduibi"
        / "PAPER4A_WRITE_READY_EVIDENCE_PACKAGE_AND_CONTEXT_SYNC"
        / "02_evidence_consolidation"
        / "dual_antenna_literature_native_metrics_evidence.csv",
        "paper4a_ledger": args.repo_root
        / "suanfahengxiangduibi"
        / "PAPER4A_WRITE_READY_EVIDENCE_PACKAGE_AND_CONTEXT_SYNC"
        / "PAPER4A_MASTER_EVIDENCE_LEDGER.csv",
        "paper4g_status": args.repo_root
        / "suanfahengxiangduibi"
        / "PAPER4G_YAW_BOUNDARY_FREEZE_NATIVE_METRICS_WRITE_PACKAGE"
        / "02_native_metrics_consolidation"
        / "PAPER4G_EXTERNAL_LITERATURE_METHOD_STATUS.csv",
        "paper4g_ledger": args.repo_root
        / "suanfahengxiangduibi"
        / "PAPER4G_YAW_BOUNDARY_FREEZE_NATIVE_METRICS_WRITE_PACKAGE"
        / "02_native_metrics_consolidation"
        / "PAPER4G_NATIVE_DDLOS_METRICS_LEDGER.csv",
        "paper4g_final": args.repo_root
        / "suanfahengxiangduibi"
        / "PAPER4G_YAW_BOUNDARY_FREEZE_NATIVE_METRICS_WRITE_PACKAGE"
        / "PAPER4G_SUPERVISOR_FINAL_REPORT.md",
        "paper10c_go2_rows": args.project_root
        / "reports"
        / "stages"
        / "PAPER10C_GO2_HIGH_LEVEL_PRIOR_EVIDENCE_FREEZE"
        / "05_result_tables"
        / "PAPER10C_ROW_LEVEL_MASTER_TABLE_SANITIZED.csv",
    }


def inventory_rows(args: argparse.Namespace, root_aliases: dict[str, Path]) -> tuple[dict[str, Any], list[dict[str, str]]]:
    roots = {
        "project_literature_comparisons": args.horizontal_root,
        "windows_horizontal_root": args.windows_horizontal_root,
        "g_degraded_horizontal_root": args.g_degraded_horizontal_root,
        "g_legsa_root": args.g_legsa_root,
        "repo_root": args.repo_root,
        "home_legacy_repo": args.home_legacy_repo,
    }
    inventory = [
        {
            "root_id": key,
            "path_alias": alias_path(path, root_aliases),
            "exists": str(path.exists()).lower(),
            "read_mode": "read_only" if path.exists() else "unavailable",
            "notes": "Q2 reads or indexes only; no historical file deletion or runtime mutation.",
        }
        for key, path in roots.items()
    ]
    assets: dict[str, Any] = {}
    for name, path in asset_paths(args).items():
        if path.suffix == ".csv":
            payload = read_csv_optional(path)
            count = len(payload)
        else:
            payload = read_text_optional(path)
            count = len(payload)
        assets[name] = payload
        inventory.append(
            {
                "root_id": f"asset::{name}",
                "path_alias": alias_path(path, root_aliases),
                "exists": str(path.exists()).lower(),
                "read_mode": "read_only_loaded" if path.exists() else "missing",
                "notes": f"records_or_chars={count}",
            }
        )
    return assets, inventory


def base_method_row(method_id: str, method_name: str, reproduction_type: str, **updates: Any) -> dict[str, Any]:
    row: dict[str, Any] = {
        "method_id": method_id,
        "method_name": method_name,
        "source_paper": "",
        "source_title": "",
        "source_year": "",
        "source_venue_or_journal": "",
        "source_link_or_doi": "",
        "algorithm_family": "unspecified",
        "source_stage": "",
        "dataset_scope": "BY2",
        "dataset_rows_planned": "0",
        "dataset_rows_completed": "0",
        "dataset_rows_failed": "0",
        "dataset_rows_blocked": "0",
        "by2_rows_completed": "0",
        "by3_rows_completed": "0",
        "xb_rows_completed": "0",
        "reproduction_type": reproduction_type,
        "frame_closed": "false",
        "yaw_semantic_safe": "false",
        "body_heading_convention_closed": "false",
        "lateral_90_rule_safe": "false",
        "enu_ned_safe": "false",
        "yaw_wrap_safe": "false",
        "trace_used_online": "false",
        "final_v23_output_solver_input": "false",
        "legsa_output_solver_input": "false",
        "receiver_imu_as_body_imu": "false",
        "row_level_available": "false",
        "runtime_proof_available": "false",
        "epoch_output_available": "false",
        "eval_metrics_available": "false",
        "render_QA_available": "false",
        "official_code_attempted": "false",
        "official_code_build_status": "not_attempted_in_Q2",
        "provider_requirement_status": "not_reviewed",
        "missing_inputs": "",
        "missing_backend": "",
        "paper_location_recommendation": "diagnostic_only",
        "claim_level": "diagnostic_only",
        "rerun_required": "false",
        "reexport_required": "false",
        "replot_required": "true",
        "notes": "",
    }
    row.update(flag_row(reproduction_type))
    row.update(updates)
    return row


def qa_method_rows() -> list[dict[str, Any]]:
    names = [
        ("PAPER2A_QA01_NIS_CHI_SQUARE_FDE", "NIS chi-square FDE"),
        ("PAPER2A_QA02_RAIM_RESIDUAL_FDE", "RAIM residual FDE"),
        ("PAPER2A_QA03_HUBER_M_ESTIMATOR_IRLS", "Huber M-estimator IRLS"),
        ("PAPER2A_QA04_IGGIII_ROBUST_EQUIVALENT_WEIGHT", "IGG-III robust equivalent weight"),
        ("PAPER2A_QA05_GNC_GEMAN_MCCLURE_IRLS", "GNC Geman-McClure IRLS"),
        ("PAPER2A_QA06_ROBUST_ADAPTIVE_KF_INNOVATION_COVARIANCE", "Robust adaptive KF innovation covariance"),
        ("PAPER2A_QA07_DOPPLER_CONSISTENCY_QC", "Doppler consistency QC"),
    ]
    rows: list[dict[str, Any]] = []
    for method_id, name in names:
        rows.append(
            base_method_row(
                method_id,
                name,
                classify_reproduction_type(paper_policy=True),
                algorithm_family="GNSS_INS_QA",
                source_stage="PAPER2A_TRUE_GNSS_INS_QA_FULL_MATRIX",
                dataset_scope="BY2/BY3/XB",
                dataset_rows_planned="271",
                dataset_rows_completed="271",
                by2_rows_completed="120",
                by3_rows_completed="71",
                xb_rows_completed="80",
                paper_location_recommendation="appendix_candidate_after_reexport",
                claim_level="bounded_QA_baseline_after_reexport",
                reexport_required="true",
                replot_required="true",
                notes=(
                    "Secondary PAPER4A evidence reports 1897 completed evaluable QA rows total, "
                    "but Q2 did not find direct PAPER2A row-level/proof/render-QA files in the current readable roots."
                ),
            )
        )
    return rows


def registry_rows(assets: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in assets.get("da_registry", []):
        rows.append(
            base_method_row(
                f"REG_{row.get('method_id', '')}",
                row.get("method_name", ""),
                classify_reproduction_type(paper_policy=True),
                source_paper=row.get("method_id", ""),
                source_title=row.get("literature_identity", ""),
                algorithm_family="dual_antenna_heading",
                source_stage="literature_comparisons_registry",
                dataset_scope="indexed_existing_evidence",
                provider_requirement_status="indexed_proxy_only",
                missing_backend="full official/source-complete backend not proven",
                paper_location_recommendation="appendix_or_diagnostic",
                claim_level="fidelity_caveated_reference",
                reexport_required="true",
                rerun_required="true",
                notes=f"Registry fidelity: {row.get('fidelity', '')}; forbidden: {row.get('forbidden_claim', '')}",
            )
        )
    for row in assets.get("lc_registry", []):
        rows.append(
            base_method_row(
                f"REG_{row.get('method_id', '')}",
                row.get("method_name", ""),
                classify_reproduction_type(paper_policy=True),
                source_paper=row.get("method_id", ""),
                source_title=row.get("literature_identity", ""),
                algorithm_family="GNSS_INS_loose_coupling",
                source_stage="literature_comparisons_registry",
                dataset_scope="indexed_existing_evidence",
                paper_location_recommendation="appendix_or_diagnostic",
                claim_level="fidelity_caveated_reference",
                reexport_required="true",
                notes=f"Registry fidelity: {row.get('fidelity', '')}; forbidden: {row.get('forbidden_claim', '')}",
            )
        )
    for row in assets.get("lse_registry", []):
        rows.append(
            base_method_row(
                f"REG_{row.get('method_id', '')}",
                row.get("method_name", ""),
                classify_reproduction_type(diagnostic=True),
                source_paper=row.get("method_id", ""),
                source_title=row.get("literature_identity", ""),
                algorithm_family="legged_state_estimation",
                source_stage="literature_comparisons_registry",
                dataset_scope="indexed_existing_evidence",
                paper_location_recommendation="diagnostic_or_appendix",
                claim_level="legged_proxy_boundary",
                reexport_required="true",
                notes=f"Registry fidelity: {row.get('fidelity', '')}; Go2 position/yaw/truth claims remain forbidden.",
            )
        )
    return rows


def paper4g_native_rows(assets: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in assets.get("paper4g_ledger", []):
        body_yaw_allowed = truthy(row.get("body_yaw_allowed"))
        reproduction_type = classify_reproduction_type(faithful_module=True)
        rows.append(
            base_method_row(
                f"P4G_{row.get('method_id', '')}",
                row.get("method_id", ""),
                reproduction_type,
                source_paper=row.get("paper_source", ""),
                source_title=row.get("implementation_level", ""),
                algorithm_family="dual_antenna_native_DD_LOS",
                source_stage="PAPER4G_native_metrics",
                dataset_scope="BY2_native_metrics",
                dataset_rows_planned=row.get("case_count", ""),
                dataset_rows_completed=row.get("completed_count", ""),
                dataset_rows_blocked=row.get("blocked_count", ""),
                by2_rows_completed=row.get("completed_count", ""),
                frame_closed=str(body_yaw_allowed).lower(),
                yaw_semantic_safe=str(body_yaw_allowed).lower(),
                body_heading_convention_closed=str(body_yaw_allowed).lower(),
                lateral_90_rule_safe=str(body_yaw_allowed).lower(),
                enu_ned_safe="true",
                yaw_wrap_safe="true",
                row_level_available="true",
                runtime_proof_available="true",
                eval_metrics_available="true",
                provider_requirement_status=row.get("provider_level", ""),
                paper_location_recommendation="appendix_candidate",
                claim_level="native_metrics_only_no_body_yaw_claim",
                replot_required="true",
                notes=row.get("claim_boundary", ""),
            )
        )
    return rows


def stage_summary_rows() -> list[dict[str, Any]]:
    return [
        base_method_row(
            "PAPER1F_DUAL_ANTENNA_ADAPTERS",
            "Five representative dual-antenna heading-aided adapters",
            classify_reproduction_type(diagnostic=True),
            algorithm_family="dual_antenna_heading",
            source_stage="PAPER1F_FULL_MATRIX_EXECUTION_LOCKED",
            dataset_scope="BY2_and_stress_datasets",
            dataset_rows_planned="3523",
            dataset_rows_completed="2168",
            dataset_rows_blocked="1355",
            by2_rows_completed="1355",
            epoch_output_available="true",
            paper_location_recommendation="diagnostic_only",
            claim_level="adapter_diagnostic_only",
            reexport_required="true",
            notes=(
                "PAPER4A secondary ledger reports completed epoch-output rows, but direct PAPER1F proof and "
                "method-source mapping are incomplete. Do not call these five faithful external algorithms."
            ),
        ),
        base_method_row(
            "QA11G_10_METHOD_MATRIX",
            "QA11G ten-method QA matrix",
            classify_reproduction_type(diagnostic=True),
            algorithm_family="GNSS_INS_QA",
            source_stage="QA11G",
            dataset_scope="BY2_120_if_proof_reexported",
            missing_inputs="direct row-level/proof/render-QA not found by Q2",
            paper_location_recommendation="appendix_or_diagnostic_after_reexport",
            claim_level="evidence_incomplete_reexport_required",
            reexport_required="true",
            notes="Q2 could not locate direct QA11G full row-level/proof files; keep as re-export required.",
        ),
        base_method_row(
            "QA11_20_METHOD_BLOCKED_FAMILY",
            "QA11/QA11B/QA11C/QA11D twenty-method blocked benchmark family",
            classify_reproduction_type(blocked=True),
            algorithm_family="GNSS_INS_QA",
            source_stage="QA11_QA11B_QA11C_QA11D",
            dataset_scope="blocked",
            missing_inputs="sensors/providers/backends for a real 20-method runnable benchmark",
            missing_backend="multiple external backends unavailable or not closed",
            paper_location_recommendation="blocked_with_proof",
            claim_level="do_not_pursue_20_method_claim",
            notes="Do not continue chasing a 20-method benchmark unless real runnable methods are identified.",
        ),
        base_method_row(
            "PAPER0M2_PAPER0N_DOMAIN_STRESS",
            "Domain-stress horizontal methods",
            classify_reproduction_type(diagnostic=True),
            algorithm_family="domain_stress",
            source_stage="PAPER0M2/PAPER0N",
            dataset_scope="BY2/BY3/XB_stress_indexed",
            paper_location_recommendation="diagnostic_only",
            claim_level="domain_stress_context_only",
            reexport_required="true",
            notes="Q2 treats these as domain-stress evidence pending row-level/proof re-export.",
        ),
        base_method_row(
            "PAPER7R2E_PAPER9B_ARCHIVE_POINTERS",
            "PAPER7R2E/PAPER9B/PAPER9B_R1 archived horizontal evidence",
            classify_reproduction_type(diagnostic=True),
            algorithm_family="horizontal_archive",
            source_stage="PAPER7R2E/PAPER9B/PAPER9B_R1",
            dataset_scope="archive_pointer_only",
            missing_inputs="direct lightweight row/proof package not present in current Q2 roots",
            paper_location_recommendation="diagnostic_only",
            claim_level="evidence_incomplete_reexport_required",
            reexport_required="true",
            notes="Archive references are not upgraded to active evidence without re-export.",
        ),
    ]


def paper4a_ledger_rows(assets: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for ledger in assets.get("paper4a_da", []):
        stage = ledger.get("stage", "")
        rows.append(
            base_method_row(
                f"{stage}_DUAL_ANTENNA_STAGE_SUMMARY",
                stage,
                classify_reproduction_type(faithful_module="module" in ledger.get("evidence", "").lower(), diagnostic="diagnostic" in ledger.get("evidence", "").lower()),
                algorithm_family="dual_antenna_stage_summary",
                source_stage=stage,
                dataset_scope="BY2_120_module_or_native_metrics",
                paper_location_recommendation="appendix_candidate",
                claim_level="stage_summary_no_exact_reproduction",
                reexport_required="true",
                notes=ledger.get("evidence", ""),
            )
        )
    return rows


def go2_internal_rows(assets: dict[str, Any]) -> list[dict[str, Any]]:
    rows = assets.get("paper10c_go2_rows", [])
    if not rows:
        return [
            base_method_row(
                "PAPER10C_GO2_PRIOR_EVIDENCE",
                "Go2 prior internal evidence",
                classify_reproduction_type(diagnostic=True),
                algorithm_family="legged_internal_go2_prior",
                source_stage="PAPER10C_GO2_HIGH_LEVEL_PRIOR_EVIDENCE_FREEZE",
                paper_location_recommendation="appendix_or_diagnostic",
                claim_level="internal_weak_prior_evidence_only",
                reexport_required="true",
                notes="Go2 row-level evidence not found in Q2 assets; keep internal only and never truth.",
            )
        ]
    counter = Counter(row.get("method_id") or row.get("method") or row.get("method_mode_id") or "unknown" for row in rows)
    out: list[dict[str, Any]] = []
    for method_id, count in sorted(counter.items()):
        completed = sum(
            1
            for row in rows
            if (row.get("method_id") or row.get("method") or row.get("method_mode_id") or "unknown") == method_id
            and str(row.get("terminal_status", row.get("status", ""))).upper() in {"COMPLETED_EVALUABLE", "COMPLETED"}
        )
        out.append(
            base_method_row(
                f"PAPER10C_{method_id}",
                method_id,
                classify_reproduction_type(diagnostic=True),
                algorithm_family="legged_internal_go2_prior",
                source_stage="PAPER10C_GO2_HIGH_LEVEL_PRIOR_EVIDENCE_FREEZE",
                dataset_scope="BY2_Go2_internal",
                dataset_rows_planned=str(count),
                dataset_rows_completed=str(completed),
                by2_rows_completed=str(completed),
                frame_closed="true",
                row_level_available="true",
                runtime_proof_available="true",
                eval_metrics_available="true",
                paper_location_recommendation="appendix_or_diagnostic",
                claim_level="internal_weak_prior_not_external_algorithm",
                replot_required="true",
                notes="Internal Go2 prior evidence only; Go2 position, yaw, and velocity are not truth.",
            )
        )
    return out


def build_method_rows(assets: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    rows.extend(qa_method_rows())
    rows.extend(registry_rows(assets))
    rows.extend(paper4g_native_rows(assets))
    rows.extend(paper4a_ledger_rows(assets))
    rows.extend(stage_summary_rows())
    rows.extend(go2_internal_rows(assets))
    normalized = []
    seen: set[str] = set()
    for row in rows:
        if row["method_id"] in seen:
            row["method_id"] = f"{row['method_id']}_{len(seen)}"
        seen.add(row["method_id"])
        normalized.append({field: csv_value(row.get(field, "")) for field in MASTER_FIELDS})
    return normalized


def availability_rows(method_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    fields = [
        "row_level_available",
        "runtime_proof_available",
        "epoch_output_available",
        "eval_metrics_available",
        "render_QA_available",
        "reexport_required",
    ]
    return [
        {
            "method_id": row["method_id"],
            "source_stage": row["source_stage"],
            **{field: row[field] for field in fields},
            "availability_status": "COMPLETE_FOR_Q2" if all(row[field] == "true" for field in fields[:2]) else "EVIDENCE_INCOMPLETE_REEXPORT_REQUIRED"
            if row["reexport_required"] == "true"
            else "PARTIAL_OR_DIAGNOSTIC",
        }
        for row in method_rows
    ]


def reproduction_rows(method_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "method_id": row["method_id"],
            "method_name": row["method_name"],
            "source_stage": row["source_stage"],
            "reproduction_type": row["reproduction_type"],
            "exact_reproduction": row["exact_reproduction"],
            "faithful_algorithm": row["faithful_algorithm"],
            "faithful_module": row["faithful_module"],
            "paper_derived_policy": row["paper_derived_policy"],
            "diagnostic_only": row["diagnostic_only"],
            "blocked_with_proof": row["blocked_with_proof"],
            "notes": row["notes"],
        }
        for row in method_rows
    ]


def dataset_rows(method_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "method_id": row["method_id"],
            "dataset_scope": row["dataset_scope"],
            "dataset_rows_planned": row["dataset_rows_planned"],
            "dataset_rows_completed": row["dataset_rows_completed"],
            "dataset_rows_failed": row["dataset_rows_failed"],
            "dataset_rows_blocked": row["dataset_rows_blocked"],
            "by2_rows_completed": row["by2_rows_completed"],
            "by3_rows_completed": row["by3_rows_completed"],
            "xb_rows_completed": row["xb_rows_completed"],
        }
        for row in method_rows
    ]


def yaw_safety_rows(method_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "method_id": row["method_id"],
            "frame_closed": row["frame_closed"],
            "yaw_semantic_safe": row["yaw_semantic_safe"],
            "body_heading_convention_closed": row["body_heading_convention_closed"],
            "lateral_90_rule_safe": row["lateral_90_rule_safe"],
            "enu_ned_safe": row["enu_ned_safe"],
            "yaw_wrap_safe": row["yaw_wrap_safe"],
            "paper_location_recommendation": row["paper_location_recommendation"],
            "notes": row["notes"],
        }
        for row in method_rows
    ]


def runtime_proof_rows(method_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "method_id": row["method_id"],
            "source_stage": row["source_stage"],
            "row_level_available": row["row_level_available"],
            "runtime_proof_available": row["runtime_proof_available"],
            "epoch_output_available": row["epoch_output_available"],
            "eval_metrics_available": row["eval_metrics_available"],
            "trace_used_online": row["trace_used_online"],
            "final_v23_output_solver_input": row["final_v23_output_solver_input"],
            "legsa_output_solver_input": row["legsa_output_solver_input"],
            "receiver_imu_as_body_imu": row["receiver_imu_as_body_imu"],
            "proof_status": "PROOF_PRESENT" if row["row_level_available"] == "true" and row["runtime_proof_available"] == "true" else "PROOF_INCOMPLETE",
        }
        for row in method_rows
    ]


def render_rows(method_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "method_id": row["method_id"],
            "source_stage": row["source_stage"],
            "render_QA_available": row["render_QA_available"],
            "replot_required": row["replot_required"],
            "render_status": "PASS_INDEXED" if row["render_QA_available"] == "true" else "MISSING_OR_REPLOT_REQUIRED",
            "notes": "Q2 does not regenerate or copy figure binaries.",
        }
        for row in method_rows
    ]


def filter_rows(method_rows: list[dict[str, Any]], predicate: Any) -> list[dict[str, Any]]:
    return [row for row in method_rows if predicate(row)]


def track_rows(method_rows: list[dict[str, Any]], family_keywords: tuple[str, ...]) -> list[dict[str, Any]]:
    out = []
    for row in method_rows:
        haystack = " ".join([row["algorithm_family"], row["method_id"], row["method_name"], row["source_stage"]]).lower()
        if any(keyword in haystack for keyword in family_keywords):
            out.append(row)
    return out


def counts_by_type(method_rows: list[dict[str, Any]]) -> Counter[str]:
    return Counter(row["reproduction_type"] for row in method_rows)


def write_reconciliation(stage_root: Path, method_rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    out = stage_root / "02_RECONCILIATION"
    main_candidates = filter_rows(
        method_rows,
        lambda row: "main_text" in row["paper_location_recommendation"] and row["reproduction_type"] in {"EXACT_REPRODUCTION", "FAITHFUL_ALGORITHM_REPRODUCTION"},
    )
    appendix = filter_rows(method_rows, lambda row: "appendix" in row["paper_location_recommendation"])
    diagnostic = filter_rows(method_rows, lambda row: row["diagnostic_only"] == "true" or row["paper_location_recommendation"] == "diagnostic_only")
    excluded = filter_rows(method_rows, lambda row: row["reproduction_type"] == "EXCLUDED_DEPRECATED")
    reexport = filter_rows(method_rows, lambda row: row["reexport_required"] == "true")
    rerun = filter_rows(method_rows, lambda row: row["rerun_required"] == "true")
    write_csv(out / "HORIZONTAL_METHOD_MASTER_TABLE.csv", method_rows, MASTER_FIELDS)
    write_csv(out / "HORIZONTAL_EVIDENCE_AVAILABILITY_TABLE.csv", availability_rows(method_rows))
    write_csv(out / "HORIZONTAL_REPRODUCTION_TYPE_TABLE.csv", reproduction_rows(method_rows))
    write_csv(out / "HORIZONTAL_DATASET_COVERAGE_TABLE.csv", dataset_rows(method_rows))
    write_csv(out / "HORIZONTAL_YAW_FRAME_SAFETY_TABLE.csv", yaw_safety_rows(method_rows))
    write_csv(out / "HORIZONTAL_RUNTIME_PROOF_TABLE.csv", runtime_proof_rows(method_rows))
    write_csv(out / "HORIZONTAL_RENDER_QA_TABLE.csv", render_rows(method_rows))
    write_csv(out / "HORIZONTAL_MAIN_TEXT_CANDIDATES.csv", main_candidates, MASTER_FIELDS)
    write_csv(out / "HORIZONTAL_APPENDIX_CANDIDATES.csv", appendix, MASTER_FIELDS)
    write_csv(out / "HORIZONTAL_DIAGNOSTIC_ONLY.csv", diagnostic, MASTER_FIELDS)
    write_csv(out / "HORIZONTAL_EXCLUDED_DEPRECATED.csv", excluded, MASTER_FIELDS)
    write_csv(out / "HORIZONTAL_REEXPORT_REQUIRED.csv", reexport, MASTER_FIELDS)
    write_csv(out / "HORIZONTAL_RERUN_REQUIRED.csv", rerun, MASTER_FIELDS)
    write_md(
        out / "HORIZONTAL_REVIEWER_NOTES.md",
        "\n".join(
            [
                "# HORIZONTAL_REVIEWER_NOTES",
                "",
                "- Q2 found no current exact external algorithm reproduction that is safe for unqualified main-text use.",
                "- PAPER2A QA evidence is present through secondary PAPER4A summaries, but direct row-level/proof/render-QA re-export is required before paper use.",
                "- PAPER1F is diagnostic-only until method-source mapping and direct proof are repaired.",
                "- PAPER4G native dual-antenna metrics are appendix-supporting evidence only; body-yaw claims remain disallowed.",
                "- QA11G requires direct re-export if used; QA11 20-method blocked stages must not be written as completed.",
                "- External methods are not rejected for vehicle/marine/generic origins. The gate is real BY2 input construction, independent method execution, and closed evaluator semantics.",
            ]
        ),
    )
    return {
        "main": main_candidates,
        "appendix": appendix,
        "diagnostic": diagnostic,
        "excluded": excluded,
        "reexport": reexport,
        "rerun": rerun,
    }


def write_tracks(stage_root: Path, method_rows: list[dict[str, Any]]) -> None:
    dual = track_rows(method_rows, ("dual", "antenna", "dd_los", "heading", "paper1f", "paper3", "paper4g"))
    qa = track_rows(method_rows, ("qa", "gnss_ins_qa", "nis", "raim", "huber", "igg", "doppler", "qa11"))
    legged = track_rows(method_rows, ("legged", "go2", "lse", "inekf", "contact"))

    dual_dir = stage_root / "03_TRACK_A_DUAL_ANTENNA"
    write_csv(dual_dir / "DUAL_ANTENNA_METHOD_REVIEW.csv", dual, MASTER_FIELDS)
    write_csv(dual_dir / "DUAL_ANTENNA_MAIN_TEXT_CANDIDATES.csv", [], MASTER_FIELDS)
    write_csv(dual_dir / "DUAL_ANTENNA_APPENDIX_CANDIDATES.csv", filter_rows(dual, lambda row: "appendix" in row["paper_location_recommendation"]), MASTER_FIELDS)
    write_csv(dual_dir / "DUAL_ANTENNA_DIAGNOSTIC_ONLY.csv", filter_rows(dual, lambda row: row["diagnostic_only"] == "true"), MASTER_FIELDS)
    write_csv(dual_dir / "DUAL_ANTENNA_TARGETED_RERUN_REQUIRED.csv", filter_rows(dual, lambda row: row["rerun_required"] == "true"), MASTER_FIELDS)
    write_md(
        dual_dir / "DUAL_ANTENNA_REVIEW_SUMMARY.md",
        "\n".join(
            [
                "# DUAL_ANTENNA_REVIEW_SUMMARY",
                "",
                "- Q2 did not identify at least three exact/faithful algorithm dual-antenna methods ready for main text.",
                "- Existing DD/LOS/native metrics support appendix-level method/module diagnostics.",
                "- Vehicle/marine/generic dual-antenna methods remain valid candidates for targeted BY2 rerun if inputs and yaw/body semantics close.",
                "- Final gate: targeted 3-5 method dual-antenna rerun is required for main-text true external-method comparison.",
            ]
        ),
    )

    qa_dir = stage_root / "04_TRACK_B_QA_METHODS"
    write_csv(qa_dir / "QA_METHOD_REVIEW.csv", qa, MASTER_FIELDS)
    write_csv(qa_dir / "QA_MAIN_TEXT_CANDIDATES.csv", [], MASTER_FIELDS)
    write_csv(qa_dir / "QA_APPENDIX_CANDIDATES.csv", filter_rows(qa, lambda row: "appendix" in row["paper_location_recommendation"]), MASTER_FIELDS)
    write_csv(qa_dir / "QA_DIAGNOSTIC_ONLY.csv", filter_rows(qa, lambda row: row["diagnostic_only"] == "true"), MASTER_FIELDS)
    write_csv(qa_dir / "QA_REEXPORT_REQUIRED.csv", filter_rows(qa, lambda row: row["reexport_required"] == "true"), MASTER_FIELDS)
    write_md(
        qa_dir / "QA_REVIEW_SUMMARY.md",
        "\n".join(
            [
                "# QA_REVIEW_SUMMARY",
                "",
                "- PAPER2A reports seven QA methods and 1897 completed evaluable rows through secondary PAPER4A evidence.",
                "- Direct row-level/proof/render-QA files were not available in the current Q2 readable roots.",
                "- QA methods can support appendix/bounded quality-control context after re-export.",
                "- They must not be written as exact official systems or as performance-superiority proof before classification support.",
            ]
        ),
    )

    legged_dir = stage_root / "05_TRACK_C_LEGGED"
    write_csv(legged_dir / "LEGGED_METHOD_REVIEW.csv", legged, MASTER_FIELDS)
    write_csv(legged_dir / "GO2_PRIOR_EVIDENCE_REVIEW.csv", filter_rows(legged, lambda row: "go2" in row["algorithm_family"].lower() or "go2" in row["method_id"].lower()), MASTER_FIELDS)
    write_csv(legged_dir / "LEGGED_EXTERNAL_ALGORITHM_FEASIBILITY.csv", filter_rows(legged, lambda row: "REG_LSE" in row["method_id"]), MASTER_FIELDS)
    write_csv(legged_dir / "LEGGED_APPENDIX_OR_DIAGNOSTIC_EVIDENCE.csv", legged, MASTER_FIELDS)
    write_md(
        legged_dir / "LEGGED_REVIEW_SUMMARY.md",
        "\n".join(
            [
                "# LEGGED_REVIEW_SUMMARY",
                "",
                "- Q2 does not find a complete external legged-state-estimation faithful algorithm ready for main-text comparison.",
                "- LSE entries remain proxy/subset or diagnostic unless raw FK/contact/backend evidence is closed elsewhere.",
                "- Current paper support should use internal Go2 prior ablation plus observability diagnostics.",
                "- Go2 yaw, position, velocity, and contact must not be treated as truth.",
            ]
        ),
    )


def write_figures(stage_root: Path, method_rows: list[dict[str, Any]], args: argparse.Namespace) -> None:
    fig_dir = stage_root / "06_FIGURE_ORGANIZATION"
    windows_ok = args.windows_horizontal_root.exists()
    g_ok = args.g_degraded_horizontal_root.exists()
    main_count = len([row for row in method_rows if "main_text" in row["paper_location_recommendation"]])
    appendix_count = len([row for row in method_rows if "appendix" in row["paper_location_recommendation"]])
    diag_count = len([row for row in method_rows if row["diagnostic_only"] == "true"])
    write_csv(fig_dir / "HORIZONTAL_FIGURE_REVIEW_INDEX.csv", figure_review_rows(method_rows))
    write_csv(fig_dir / "HORIZONTAL_NORMAL_FIGURE_ORGANIZATION_PLAN.csv", normal_organization_rows(method_rows, windows_ok, g_ok))
    write_csv(fig_dir / "HORIZONTAL_DEGRADED_FIGURE_ORGANIZATION_PLAN.csv", degraded_organization_rows(method_rows, windows_ok, g_ok))
    write_csv(fig_dir / "HORIZONTAL_REPLOT_REQUIRED.csv", replot_rows(method_rows))
    write_md(
        fig_dir / "HORIZONTAL_FIGURE_PACKAGE_SUMMARY.md",
        figure_package_summary(
            method_count=len(method_rows),
            main_count=main_count,
            appendix_count=appendix_count,
            diagnostic_count=diag_count,
            windows_root=args.windows_horizontal_root,
            g_root=args.g_degraded_horizontal_root,
        ),
    )


def write_text_summaries(stage_root: Path, method_rows: list[dict[str, Any]]) -> None:
    out = stage_root / "07_TEXT_SUMMARY"
    common = (
        "本阶段只读取已有横向算法证据，并按 exact、faithful algorithm、faithful module、policy baseline、diagnostic、blocked 分级。"
        "外部算法来自车载、船载或通用 GNSS/INS 平台本身不是否定理由；关键是 BY2 输入真实、算法独立运行、输出语义闭合。"
    )
    summaries = {
        "00_HORIZONTAL_COMPARISON_OVERALL_SUMMARY_CN.md": [
            "# 横向算法比较总体总结",
            common,
            "Q2 未发现可直接写成 exact reproduction 的外部算法证据。PAPER2A/QA11G 需要 re-export；双天线主文真复现证据不足，需要定向补跑。",
            "论文中可以写证据清账和后续门控，不能写横向算法全面完成或普遍优越。",
        ],
        "01_DUAL_ANTENNA_METHODS_SUMMARY_CN.md": [
            "# 双天线/航向建模横向算法总结",
            "PAPER3/PAPER4G 提供 DD/LOS/native/module 层证据，但 body yaw 主张仍被 yaw-frame 边界限制。",
            "如果外部双天线算法在 BY2 半遮挡短基线足式平台上表现差，只要输入和语义闭合，可作为合理对比结论。",
            "当前不足以写 3-5 个真实外部算法主文对比，建议下一阶段只定向补跑最可行的 3-5 个。",
        ],
        "02_QA_METHODS_SUMMARY_CN.md": [
            "# 质量管理/GNSS-INS QC 横向算法总结",
            "PAPER2A 的七个 QA 方法通过二级证据显示有 1897 行完成，但 Q2 未找到直接 row-level/proof/render QA 包。",
            "因此 QA 方法适合先 re-export，再作为附录或有边界的质量控制 baseline。",
            "不能写成 exact official reproduction 或性能优越证明。",
        ],
        "03_LEGGED_METHODS_SUMMARY_CN.md": [
            "# 足式相关横向证据总结",
            "当前没有完整外部足式状态估计算法的主文级真复现证据。",
            "Go2 prior 证据应作为内部弱先验/可观性诊断，不应伪装成外部 contact-aided InEKF 或完整 leg odometry。",
            "Go2 位置、航向、速度和接触都不能作为真值。",
        ],
        "04_BY2_NORMAL_HORIZONTAL_COMPARISON_TEXT_CN.md": [
            "# BY2 正常工况横向比较文字草案",
            "可写：本文对已有横向算法证据进行了复现等级和语义闭合审查，正常工况图表需要基于 re-export 或 targeted rerun 后的统一 evaluator 结果。",
            "不可写：当前 Q2 已完成新的正常工况横向 full matrix。",
        ],
        "05_BY2_DEGRADED_HORIZONTAL_COMPARISON_TEXT_CN.md": [
            "# BY2 退化工况横向比较文字草案",
            "BY2 退化矩阵可作为外部算法压力测试条件。外部算法在短基线足式半遮挡数据上效果差不是否定方法，而是反映适用边界。",
            "前提是方法独立运行、输入真实、输出 yaw/body/frame/evaluator 语义闭合。",
        ],
        "06_BY3_POOR_HEADING_STRESS_TEXT_CN.md": [
            "# BY3 poor-heading stress 文字边界",
            "BY3 只能写成 poor-heading stress 或诊断，不可写普通 yaw generalization。",
        ],
        "07_XB_POOR_GNSS_STRESS_TEXT_CN.md": [
            "# XB poor-GNSS stress 文字边界",
            "XB 只能写成 poor-GNSS fallback/risk stress，不可写 high-precision severe-GNSS proof。",
        ],
        "08_PAPER_WRITABLE_HORIZONTAL_TEXT_CN.md": [
            "# 可写入论文的横向比较表述",
            "可写：我们将横向算法证据按复现等级和语义闭合程度分级，区分真实算法复现、模块复现、策略 baseline、诊断和 blocked-with-proof。",
            "可写：外部方法原始平台不同不是排除条件；统一输入构造和输出语义闭合是进入比较的前提。",
        ],
        "09_FORBIDDEN_HORIZONTAL_TEXT_CN.md": [
            "# 禁止的横向比较表述",
            "禁止写：已经 exact reproduced 五个双天线外部算法。",
            "禁止写：已经 exact reproduced 二十个文献算法。",
            "禁止写：PAPER1F 或 PAPER2A 已证明主文性能优越。",
            "禁止写：BY3 证明普通 yaw 泛化，XB 证明 severe-GNSS 高精度。",
        ],
        "10_REVIEWER_RISK_CN.md": [
            "# Reviewer Risk",
            "最大风险是把 method-family adapter 或 policy baseline 写成真实论文算法复现。",
            "第二风险是把 native DD/LOS 指标写成 body yaw 同 evaluator 性能。",
            "第三风险是用旧 aggregate 或二级终报口述替代 row-level/proof evidence。",
        ],
    }
    for filename, lines in summaries.items():
        write_md(out / filename, "\n\n".join(lines))


def write_targeted_gate(stage_root: Path, method_rows: list[dict[str, Any]]) -> None:
    out = stage_root / "09_TARGETED_RERUN_GATE"
    reexport = [row for row in method_rows if row["reexport_required"] == "true"]
    dual_rerun = [row for row in method_rows if row["rerun_required"] == "true" and "dual" in row["algorithm_family"].lower()]
    do_not = [row for row in method_rows if row["reproduction_type"] in {"BLOCKED_WITH_PROOF", "DIAGNOSTIC_ONLY"} and row["rerun_required"] != "true"]
    write_csv(out / "HORIZONTAL_REEXPORT_PLAN.csv", reexport, MASTER_FIELDS)
    write_csv(out / "HORIZONTAL_TARGETED_RERUN_PLAN.csv", dual_rerun, MASTER_FIELDS)
    write_csv(out / "HORIZONTAL_DO_NOT_RERUN_LIST.csv", do_not, MASTER_FIELDS)
    write_md(
        out / "HORIZONTAL_PRIORITY_ORDER.md",
        "\n".join(
            [
                "# HORIZONTAL_PRIORITY_ORDER",
                "",
                "1. Re-export PAPER2A evidence pack before using QA rows in paper tables.",
                "2. Re-export QA11G if the 10-method QA matrix is still needed.",
                "3. Run only a targeted 3-5 method dual-antenna true-method comparison if main-text horizontal comparison is required.",
                "4. Do not pursue the 20-method benchmark unless real runnable methods and backends are identified.",
                "5. Keep BY3/XB as separate stress-only stages.",
            ]
        ),
    )
    write_md(
        out / "TARGETED_RERUN_GATE_DECISION.md",
        "\n".join(
            [
                "# TARGETED_RERUN_GATE_DECISION",
                "",
                f"Final gate decision: `{GATE_DECISION}`.",
                "",
                "- PAPER2A: REEXPORT_PAPER2A_REQUIRED before paper use.",
                "- PAPER1F: DIAGNOSTIC_ONLY_UNLESS_MAPPING_REPAIRED.",
                "- QA11G: REEXPORT_REQUIRED_IF_USED.",
                "- Dual antenna: TARGETED_DUAL_ANTENNA_RERUN_REQUIRED for main-text true-method comparison.",
                "- QA methods: QA_METHODS_REEXPORT_OR_REPLOT, not a new run.",
                "- Legged external algorithms: use internal Go2 prior evidence and observability diagnostics unless a future external method closes.",
            ]
        ),
    )


def write_prompts(stage_root: Path) -> None:
    out = stage_root / "10_NEXT_PROMPTS"
    for filename, text in prompt_map().items():
        write_md(out / filename, text)


def write_obsidian_and_context(stage_root: Path) -> None:
    obs = stage_root / "11_OBSIDIAN_SYNC"
    obs_files = {
        "PAPER10Q2_阶段总览.md": "PAPER10Q2 完成横向算法证据清账、复现等级冻结、主文/附录/诊断分类和 targeted rerun gate。",
        "横向算法证据清账.md": "证据按 exact / faithful algorithm / faithful module / policy baseline / diagnostic / blocked 分类。",
        "真实复现与诊断矩阵区别.md": "真实复现需要独立方法、状态/观测/后端闭合和 evaluator 语义闭合；diagnostic adapter 不等价。",
        "双天线横向算法现状.md": "当前没有足够的主文级 exact/faithful dual-antenna 外部算法；需要定向补跑。",
        "质量管理横向算法现状.md": "PAPER2A/QA11G 先 re-export，再作为附录或有边界 baseline。",
        "足式相关横向证据现状.md": "外部足式算法仍是 proxy/diagnostic；内部 Go2 prior 证据不可写成真值。",
        "哪些横向算法能写入论文.md": "可写 bounded 方法清账、appendix native/module evidence 和 re-export 后 QA coverage。",
        "哪些横向算法必须禁止.md": "禁止 exact false 写 exact、policy baseline 写真实算法、frame unsafe yaw 写 yaw claim。",
        "后续是否需要补跑.md": "需要：dual-antenna targeted 3-5 method rerun；PAPER2A/QA11G 是 re-export，不是重跑。",
    }
    index_rows = []
    for filename, body in obs_files.items():
        write_md(obs / filename, f"# {filename.removesuffix('.md')}\n\n{body}")
        index_rows.append({"note_file": filename, "sync_recommendation": "copy_to_obsidian_after_human_review"})
    write_csv(obs / "OBSIDIAN_UPDATE_INDEX.csv", index_rows)

    ctx = stage_root / "12_AI_CONTEXT_UPDATE"
    write_md(
        ctx / "PAPER10Q2_CURRENT_STATE_UPDATE.md",
        "PAPER10Q2 reconciled horizontal-comparison evidence. Final decision is conditional pass: QA re-export and dual-antenna targeted rerun are required before main-text use.",
    )
    write_md(
        ctx / "PAPER10Q2_NEXT_ACTIONS_UPDATE.md",
        "Next actions: Q2R1 PAPER2A re-export, optional Q2R3 QA11G re-export/replot, and Q2R2 targeted 3-5 dual-antenna true-method rerun if main-text comparison is needed.",
    )
    write_md(
        ctx / "PAPER10Q2_LATEST_STAGE_POINTERS_UPDATE.md",
        f"Latest horizontal comparison review stage: <PAPER10Q2_STAGE_ROOT>. Final decision: {FINAL_DECISION}.",
    )
    write_md(
        ctx / "PAPER10Q2_HORIZONTAL_COMPARISON_STATUS_UPDATE.md",
        "Exact reproduction count is zero in the reconciled Q2 evidence; method-inspired baselines and diagnostic adapters must not be promoted.",
    )


def git_report(args: argparse.Namespace, root_aliases: dict[str, Path]) -> str:
    cmds = [
        ["status", "--short"],
        ["status", "--branch", "--short"],
        ["remote", "-v"],
        ["branch", "--show-current"],
        ["log", "--oneline", "-n", "30"],
    ]
    lines = ["# PAPER10Q2_GIT_STATE_REPORT", "", f"- Generated UTC: {now_iso()}", ""]
    for cmd in cmds:
        result = run_git(args.repo_root, cmd)
        lines.extend(
            [
                f"## `{sanitize_text(result['cmd'], root_aliases)}`",
                "",
                "```text",
                sanitize_text(result["stdout"] or result["stderr"] or "<no output>", root_aliases),
                "```",
                "",
            ]
        )
    return "\n".join(lines)


def write_stage_reports(
    args: argparse.Namespace,
    method_rows: list[dict[str, Any]],
    input_rows: list[dict[str, str]],
    inventory: list[dict[str, str]],
    subsets: dict[str, list[dict[str, Any]]],
    path_scan_status: str,
) -> None:
    counts = counts_by_type(method_rows)
    final_lines = [
        f"# {STAGE_NAME} Supervisor Final Report",
        "",
        "1. Stage name: PAPER10Q2_HORIZONTAL_COMPARISON_EVIDENCE_RECONCILIATION_AND_TARGETED_RERUN_GATE.",
        "2. Q2 was entered after Q1 to reconcile horizontal comparison evidence before any targeted rerun.",
        f"3. Q1 files loaded: {sum(1 for row in input_rows if row['input_id'].startswith('q1_'))}.",
        f"4. M1R2E files loaded: {sum(1 for row in input_rows if row['input_id'].startswith('m1r2e_'))}.",
        f"5. Horizontal roots/assets inventoried: {len(inventory)}.",
        "6. Git branch/worktree recorded in 01_GIT/PAPER10Q2_GIT_STATE_REPORT.md.",
        "7. Solver/evaluator/provider/degradation execution: no.",
        "8. PAPER2A result: secondary QA evidence found; direct row-level/proof/render-QA re-export required.",
        "9. PAPER1F result: diagnostic-only until method-source mapping and direct proof are repaired.",
        "10. PAPER3A/PAPER3B/PAPER7R2E/PAPER9B result: native/module/archive evidence only; direct re-export required for missing archives.",
        "11. QA11F/QA11G result: QA11G direct proof not found; re-export required if used.",
        "12. QA11/QA11B/C/D result: 20-method blocked family must not be claimed complete.",
        "13. PAPER0M2/PAPER0N result: domain-stress diagnostic pending re-export.",
        f"14. exact reproduction count: {counts.get('EXACT_REPRODUCTION', 0)}.",
        f"15. faithful algorithm reproduction count: {counts.get('FAITHFUL_ALGORITHM_REPRODUCTION', 0)}.",
        f"16. faithful module reproduction count: {counts.get('FAITHFUL_MODULE_REPRODUCTION', 0)}.",
        f"17. paper-derived policy baseline count: {counts.get('PAPER_DERIVED_POLICY_BASELINE', 0)}.",
        f"18. diagnostic-only count: {counts.get('DIAGNOSTIC_ONLY', 0)}.",
        f"19. blocked-with-proof count: {counts.get('BLOCKED_WITH_PROOF', 0)}.",
        f"20. main text candidates: {len(subsets['main'])}; no unqualified true-reproduction main candidate.",
        f"21. appendix candidates: {len(subsets['appendix'])}.",
        f"22. diagnostic-only candidates: {len(subsets['diagnostic'])}.",
        f"23. excluded/deprecated evidence: {len(subsets['excluded'])}.",
        "24. Dual antenna track conclusion: targeted rerun required for main-text true external comparison.",
        "25. QA methods track conclusion: PAPER2A/QA11G need re-export/replot before paper use.",
        "26. Legged methods track conclusion: use internal Go2 prior/observability diagnostics; no external full algorithm claim.",
        "27. PAPER2A re-export: required.",
        "28. QA11G re-export/replot: required if used.",
        "29. Dual antenna targeted rerun: required for main-text true methods.",
        "30. 20-method benchmark: do not continue unless real runnable methods are available.",
        "31. BY3/XB stress: separate targeted stress only, not executed in Q2.",
        "32. Figure organization plan generated; no figure binaries copied.",
        "33. Chinese summaries generated.",
        "34. Claim boundary frozen.",
        "35. Next prompt drafts generated.",
        "36. Obsidian sync notes generated.",
        "37. AI context update snippets generated.",
        "38. Tests/audits recorded under 13_TESTS.",
        "39. Export-clean result recorded under 14_EXPORT_CLEAN_FOR_GPT.",
        f"40. Path scan result: {path_scan_status}.",
        "41. Commit hash: recorded after commit by git history; this report is generated before final push.",
        "42. Push status: pending until explicit git push command completes.",
        f"43. Final decision: `{FINAL_DECISION}`.",
    ]
    write_md(args.stage_root / "00_STAGE_REPORT" / "PAPER10Q2_SUPERVISOR_FINAL_REPORT.md", "\n".join(final_lines))
    write_md(
        args.stage_root / "00_STAGE_REPORT" / "PAPER10Q2_REVIEWER_REPORT.md",
        "\n".join(
            [
                "# PAPER10Q2_REVIEWER_REPORT",
                "",
                "- The reviewer stance is conservative: no direct proof means no main-text claim.",
                "- No solver/evaluator/provider/degradation command is emitted by Q2 scripts.",
                "- No exact reproduction row is marked true.",
                "- Policy baselines and adapters are not promoted to true algorithms.",
                "- Export-clean excludes raw data, runtime payloads, generated figures, official code snapshots, old zips, and local absolute paths.",
            ]
        ),
    )


def write_tests_report(stage_root: Path, path_scan_status: str) -> None:
    rows = [
        {"test_id": "git_fsck", "required": "true", "status": "RUN_SEPARATELY", "notes": "Run git fsck --full in the final audit."},
        {"test_id": "pytest_q2", "required": "true", "status": "RUN_SEPARATELY", "notes": "Run Q2 unit/audit tests after script generation."},
        {"test_id": "export_clean_path_scan", "required": "true", "status": path_scan_status, "notes": "Generated by Q2 path scan."},
        {"test_id": "no_solver_evaluator_provider_run", "required": "true", "status": "PASS_BY_SCRIPT_BOUNDARY", "notes": "Q2 scripts write only tables/markdown/zip."},
        {"test_id": "raw_runtime_commit_guard", "required": "true", "status": "RUN_SEPARATELY", "notes": "Run before commit using git diff/status guards."},
    ]
    write_csv(stage_root / "13_TESTS" / "PAPER10Q2_TEST_MATRIX.csv", rows)
    write_md(
        stage_root / "13_TESTS" / "PAPER10Q2_GUARD_VALIDATION_REPORT.md",
        "\n".join(
            [
                "# PAPER10Q2_GUARD_VALIDATION_REPORT",
                "",
                f"- Export-clean path scan: {path_scan_status}.",
                "- Forbidden claim grep is implemented with allowlisted forbidden-claim documents.",
                "- Raw data, runtime payload, figure binary, old zip, official code snapshot, and local path guards must run before commit.",
            ]
        ),
    )


def scan_for_export_leaks(root: Path) -> tuple[str, list[dict[str, str]]]:
    findings: list[dict[str, str]] = []
    forbidden_parts = [
        "/home/" + "kaiwen",
        "/media/" + "kaiwen/",
        "/mnt/" + "c/Users",
        "/mnt/" + "g/",
        "C:" + "\\Users",
        "by2" + ".txt",
        "by3" + ".txt",
        "gnss1" + "-raw.csv",
        "gnss2" + "-raw.csv",
        "corr" + "-raw.csv",
        "trace" + "_vrtk2",
    ]
    forbidden_claims = [
        "universally outperform",
        "final paper claim ready",
        "BY3 yaw generalization",
        "XB high-precision severe-GNSS",
        "exactly reproduced five",
        "exactly reproduced twenty",
    ]
    allow_claim_files = {
        "HORIZONTAL_FORBIDDEN_CLAIMS.md",
        "09_FORBIDDEN_HORIZONTAL_TEXT_CN.md",
        "PAPER10Q2R2_DUAL_ANTENNA_TRUE_METHODS_TARGETED_RERUN_PROMPT.md",
        "PAPER10Q2R4_BY3_XB_STRESS_HORIZONTAL_PROMPT.md",
        "PAPER10Q2_GUARD_VALIDATION_REPORT.md",
    }
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.suffix.lower() in {".zip", ".png", ".pdf"}:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        rel = path.relative_to(root).as_posix()
        for token in forbidden_parts:
            if token in text:
                findings.append({"path": rel, "token": token, "kind": "local_path_or_raw_leak"})
        if path.name not in allow_claim_files:
            lower = text.lower()
            for claim in forbidden_claims:
                if claim.lower() in lower:
                    findings.append({"path": rel, "token": claim, "kind": "forbidden_claim_outside_boundary"})
    return ("PASS" if not findings else "FAIL", findings)


def create_export_clean(args: argparse.Namespace, root_aliases: dict[str, Path]) -> tuple[str, list[dict[str, str]]]:
    export_dir = args.stage_root / "14_EXPORT_CLEAN_FOR_GPT"
    temp_dir = args.export_root / "text_package"
    if temp_dir.exists():
        shutil.rmtree(temp_dir)
    temp_dir.mkdir(parents=True, exist_ok=True)
    include_dirs = [
        "00_STAGE_REPORT",
        "01_GIT",
        "02_RECONCILIATION",
        "03_TRACK_A_DUAL_ANTENNA",
        "04_TRACK_B_QA_METHODS",
        "05_TRACK_C_LEGGED",
        "06_FIGURE_ORGANIZATION",
        "07_TEXT_SUMMARY",
        "08_CLAIM_BOUNDARY",
        "09_TARGETED_RERUN_GATE",
        "10_NEXT_PROMPTS",
        "11_OBSIDIAN_SYNC",
        "12_AI_CONTEXT_UPDATE",
        "13_TESTS",
    ]
    manifest: list[dict[str, str]] = []
    for rel_dir in include_dirs:
        src_dir = args.stage_root / rel_dir
        if not src_dir.exists():
            continue
        for src in sorted(src_dir.rglob("*")):
            if not src.is_file() or src.suffix.lower() in {".png", ".pdf", ".zip"}:
                continue
            rel = src.relative_to(args.stage_root)
            dst = temp_dir / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            text = src.read_text(encoding="utf-8", errors="replace")
            dst.write_text(sanitize_text(text, root_aliases), encoding="utf-8")
            manifest.append(
                {
                    "relative_path": rel.as_posix(),
                    "size_bytes": str(dst.stat().st_size),
                    "content_type": "text",
                    "included": "true",
                }
            )
    write_md(
        temp_dir / "README_FOR_NEXT_AI.md",
        "\n".join(
            [
                "# README_FOR_NEXT_AI",
                "",
                f"Stage: {STAGE_NAME}",
                f"Decision: {FINAL_DECISION}",
                "",
                "This export-clean package contains text-only Q2 evidence reconciliation tables, claim boundaries, gate decisions, and prompt drafts.",
                "It excludes raw data, providers, runtime payloads, figure binaries, official code snapshots, old zips, and local absolute paths.",
            ]
        ),
    )
    manifest.append({"relative_path": "README_FOR_NEXT_AI.md", "size_bytes": str((temp_dir / "README_FOR_NEXT_AI.md").stat().st_size), "content_type": "text", "included": "true"})
    scan_status, findings = scan_for_export_leaks(temp_dir)
    write_csv(export_dir / "export_clean_manifest.csv", manifest)
    write_json(export_dir / "export_clean_path_scan.json", {"status": scan_status, "findings": findings, "generated_utc": now_iso()})
    write_md(export_dir / "README_FOR_NEXT_AI.md", (temp_dir / "README_FOR_NEXT_AI.md").read_text(encoding="utf-8"))
    zip_path = export_dir / "paper10q2_horizontal_reconciliation_pack.zip"
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(temp_dir.rglob("*")):
            if path.is_file():
                zf.write(path, path.relative_to(temp_dir).as_posix())
    return scan_status, findings


def copy_reconciled_lightweight(args: argparse.Namespace, method_rows: list[dict[str, Any]]) -> None:
    write_csv(args.reconciled_root / "HORIZONTAL_METHOD_MASTER_TABLE.csv", method_rows, MASTER_FIELDS)
    write_md(
        args.reconciled_root / "README.md",
        "\n".join(
            [
                "# PAPER10Q2_RECONCILED",
                "",
                "Lightweight copy of the Q2 horizontal evidence reconciliation master table.",
                "No runtime payloads, figure binaries, raw data, providers, or official code snapshots are stored here.",
            ]
        ),
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--ai-context-root", type=Path, required=True)
    parser.add_argument("--horizontal-root", type=Path, required=True)
    parser.add_argument("--q1-stage-root", type=Path, required=True)
    parser.add_argument("--m1r2e-stage-root", type=Path, required=True)
    parser.add_argument("--m1r2c-stage-root", type=Path, required=True)
    parser.add_argument("--m1r2d-stage-root", type=Path, required=True)
    parser.add_argument("--stage-root", type=Path, required=True)
    parser.add_argument("--reconciled-root", type=Path, required=True)
    parser.add_argument("--export-root", type=Path, required=True)
    parser.add_argument("--windows-horizontal-root", type=Path, required=True)
    parser.add_argument("--g-degraded-horizontal-root", type=Path, required=True)
    parser.add_argument("--g-legsa-root", type=Path, required=True)
    parser.add_argument("--home-legacy-repo", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root_aliases = aliases(args)
    ensure_dirs(args.stage_root, args.export_root, args.reconciled_root)

    upstream, input_rows = load_upstream(args, root_aliases)
    assets, inventory = inventory_rows(args, root_aliases)
    method_rows = build_method_rows(assets)

    write_csv(args.stage_root / "00_STAGE_REPORT" / "PAPER10Q2_REQUIRED_INPUT_READ_AUDIT.csv", input_rows)
    write_csv(args.stage_root / "00_STAGE_REPORT" / "PAPER10Q2_HORIZONTAL_ASSET_INVENTORY.csv", inventory)
    write_md(args.stage_root / "01_GIT" / "PAPER10Q2_GIT_STATE_REPORT.md", git_report(args, root_aliases))

    subsets = write_reconciliation(args.stage_root, method_rows)
    write_tracks(args.stage_root, method_rows)
    write_figures(args.stage_root, method_rows, args)
    write_text_summaries(args.stage_root, method_rows)
    write_claim_boundary_outputs(args.stage_root / "08_CLAIM_BOUNDARY")
    write_targeted_gate(args.stage_root, method_rows)
    write_prompts(args.stage_root)
    write_obsidian_and_context(args.stage_root)
    copy_reconciled_lightweight(args, method_rows)

    scan_status, _findings = create_export_clean(args, root_aliases)
    write_tests_report(args.stage_root, scan_status)
    scan_status, _findings = create_export_clean(args, root_aliases)
    write_stage_reports(args, method_rows, input_rows, inventory, subsets, scan_status)
    scan_status, findings = create_export_clean(args, root_aliases)
    if scan_status != "PASS":
        write_json(args.stage_root / "14_EXPORT_CLEAN_FOR_GPT" / "export_clean_path_scan.json", {"status": scan_status, "findings": findings, "generated_utc": now_iso()})
    print(json.dumps({"stage": STAGE_NAME, "decision": FINAL_DECISION, "method_rows": len(method_rows), "export_clean": scan_status}, ensure_ascii=False))
    _ = upstream
    return 0 if scan_status == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
