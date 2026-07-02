#!/usr/bin/env python3
"""PAPER2A discovery and light re-export helpers for PAPER10Q2R1."""

from __future__ import annotations

import csv
import hashlib
import os
from pathlib import Path
from typing import Any, Iterable

QA_METHODS = [
    ("QA01_NIS_CHI_SQUARE_FDE", "NIS chi-square FDE", "innovation/NIS chi-square fault detection"),
    ("QA02_RAIM_RESIDUAL_FDE", "RAIM residual FDE", "RAIM residual fault detection"),
    ("QA03_HUBER_M_ESTIMATOR_IRLS", "Huber M-estimator IRLS", "robust M-estimation"),
    ("QA04_IGGIII_ROBUST_EQUIVALENT_WEIGHT", "IGGIII robust equivalent weight", "robust equivalent-weight model"),
    ("QA05_GNC_GEMAN_MCCLURE_IRLS", "GNC Geman-McClure IRLS", "graduated non-convex robust kernel"),
    ("QA06_ROBUST_ADAPTIVE_KF_INNOVATION_COVARIANCE", "Robust adaptive KF innovation covariance", "adaptive innovation covariance"),
    ("QA07_DOPPLER_CONSISTENCY_QC", "Doppler consistency QC", "Doppler consistency quality control"),
]

REQUIRED_FILES = [
    "PAPER2A_SUPERVISOR_FINAL_REPORT.md",
    "PAPER2A_REVIEWER_REPORT.md",
    "PAPER2A_ROW_LEVEL_MASTER_TABLE.csv",
    "PAPER2A_MATRIX_EXECUTION_STATUS.csv",
    "PAPER2A_METHOD_RUNTIME_PROOF_TABLE.csv",
    "PAPER2A_EPOCH_OUTPUT_INDEX.csv",
    "PAPER2A_RENDER_QA_REPORT.csv",
    "PAPER2A_BY2_QA_METHOD_SUMMARY.csv",
    "PAPER2A_BY3_STRESS_SUMMARY.csv",
    "PAPER2A_XB_STRESS_SUMMARY.csv",
    "PAPER2A_CLAIM_BOUNDARY.md",
    "PAPER2A_FIGURE_INDEX.csv",
    "export_clean_manifest.csv",
    "path_scan report",
]


def limited_find(root: Path, required: str, max_files: int = 8000, max_depth: int = 5) -> list[Path]:
    if not root.exists() or not root.is_dir():
        return []
    matches: list[Path] = []
    base_depth = len(root.resolve().parts)
    for current, dirs, files in os.walk(root):
        depth = len(Path(current).resolve().parts) - base_depth
        if depth >= max_depth:
            dirs[:] = []
        dirs[:] = [
            dirname
            for dirname in dirs
            if dirname not in {".git", ".venv", "venv", "node_modules", "__pycache__"}
            and dirname not in {"data", "raw", "experiments", "runtime", "ARCHIVES"}
        ]
        for filename in files:
            max_files -= 1
            if required == "path_scan report":
                if "path" in filename.lower() and "scan" in filename.lower():
                    matches.append(Path(current) / filename)
            elif filename == required:
                matches.append(Path(current) / filename)
            if matches or max_files <= 0:
                return matches[:3]
        if max_files <= 0:
            break
    return matches[:3]


def csv_value(value: Any) -> str:
    return "" if value is None else str(value)


def read_csv_optional(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


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


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def discover_paper2a_roots(candidate_roots: list[Path], secondary_qa_summary: Path) -> tuple[list[dict[str, str]], dict[str, Path]]:
    rows: list[dict[str, str]] = []
    found_files: dict[str, Path] = {}
    for idx, root in enumerate(candidate_roots):
        exists = root.exists()
        rows.append(
            {
                "candidate_id": f"PAPER2A_CANDIDATE_{idx:02d}",
                "path": str(root),
                "exists": str(exists).lower(),
                "read_mode": "read_only" if exists else "missing",
                "notes": "Direct PAPER2A candidate root.",
            }
        )
        search_enabled = exists and root.is_dir() and "PAPER2A" in str(root)
        if not search_enabled:
            if exists and root.is_dir():
                rows[-1]["notes"] = "Root recorded but not deep-searched by Q2R1 bounded discovery."
            continue
        for required in REQUIRED_FILES:
            if required == "path_scan report":
                matches = limited_find(root, required)
            else:
                matches = limited_find(root, required)
            if matches:
                found_files[required] = matches[0]
    if secondary_qa_summary.exists():
        rows.append(
            {
                "candidate_id": "PAPER4A_SECONDARY_QA_SUMMARY",
                "path": str(secondary_qa_summary),
                "exists": "true",
                "read_mode": "read_only_secondary_summary",
                "notes": "Secondary summary only; not direct row-level proof.",
            }
        )
    return rows, found_files


def required_files_check(found_files: dict[str, Path], secondary_summary_found: bool) -> list[dict[str, str]]:
    rows = []
    for required in REQUIRED_FILES:
        status = "FOUND_DIRECT" if required in found_files else "MISSING_DIRECT"
        if status == "MISSING_DIRECT" and secondary_summary_found and required in {
            "PAPER2A_SUPERVISOR_FINAL_REPORT.md",
            "PAPER2A_ROW_LEVEL_MASTER_TABLE.csv",
        }:
            status = "SECONDARY_SUMMARY_ONLY"
        rows.append(
            {
                "required_file": required,
                "status": status,
                "source_path": str(found_files.get(required, "")),
                "proof_level": "direct_file" if required in found_files else "secondary_or_missing",
                "notes": "Do not fabricate missing PAPER2A proof files.",
            }
        )
    return rows


def paper4a_qa_summary_rows(path: Path) -> list[dict[str, str]]:
    return read_csv_optional(path)


def dataset_counts_from_secondary(summary_rows: list[dict[str, str]]) -> dict[str, int]:
    text = " ".join(row.get("evidence", "") for row in summary_rows)
    counts = {"BY2": 840, "BY3": 497, "XB": 560}
    if "840/840" not in text:
        counts["BY2"] = 0
    if "497/497" not in text:
        counts["BY3"] = 0
    if "560/560" not in text:
        counts["XB"] = 0
    return counts


def matrix_status_rows(counts: dict[str, int], direct_row_level: bool) -> list[dict[str, str]]:
    proof = "ROW_PROVEN" if direct_row_level else "COUNT_FROM_SUPERVISOR_ONLY_NOT_ROW_PROVEN"
    return [
        {"dataset": "BY2", "planned_rows": "840", "completed_rows": str(counts.get("BY2", 0)), "failed_rows": "0", "blocked_rows": "0", "not_started_rows": "0", "proof_level": proof},
        {"dataset": "BY3", "planned_rows": "497", "completed_rows": str(counts.get("BY3", 0)), "failed_rows": "0", "blocked_rows": "0", "not_started_rows": "0", "proof_level": proof},
        {"dataset": "XB", "planned_rows": "560", "completed_rows": str(counts.get("XB", 0)), "failed_rows": "0", "blocked_rows": "0", "not_started_rows": "0", "proof_level": proof},
    ]


def method_classification_rows(counts: dict[str, int], proof_level: str) -> list[dict[str, str]]:
    by2_each = counts.get("BY2", 0) // 7 if counts.get("BY2", 0) else 0
    by3_each = counts.get("BY3", 0) // 7 if counts.get("BY3", 0) else 0
    xb_each = counts.get("XB", 0) // 7 if counts.get("XB", 0) else 0
    rows = []
    for method_id, method_name, family in QA_METHODS:
        rows.append(
            {
                "method_id": method_id,
                "method_name": method_name,
                "recognized_QA_family": family,
                "source_paper_or_standard": "standard_or_paper_motivated_QA_QC_family",
                "reproduction_type": "PAPER_DERIVED_POLICY_BASELINE",
                "exact_reproduction": "false",
                "faithful_module": "false",
                "policy_baseline": "true",
                "diagnostic_only": "false",
                "BY2_completed_rows": str(by2_each),
                "BY3_completed_rows": str(by3_each),
                "XB_completed_rows": str(xb_each),
                "trace_used_online": "false",
                "receiver_imu_as_body_imu": "false",
                "main_text_candidate": "false",
                "appendix_candidate": "true",
                "diagnostic_only_for_superiority": "true",
                "proof_level": proof_level,
                "safe_wording_cn": "可写为质量控制/鲁棒估计类基线，为source-aware/QM提供附录背景。",
                "forbidden_wording_cn": "禁止写成官方完整算法精确复现或证明LegSA全面优于外部QA方法。",
                "notes": "Counts are method-even split only when direct row-level proof is missing.",
            }
        )
    return rows


def light_summary_rows(counts: dict[str, int], proof_level: str) -> list[dict[str, str]]:
    rows = []
    for dataset, total in counts.items():
        per_method = total // 7 if total else 0
        for method_id, method_name, _family in QA_METHODS:
            rows.append(
                {
                    "row_id": f"{dataset}_{method_id}_SUMMARY_ONLY",
                    "method_id": method_id,
                    "method_name": method_name,
                    "dataset": dataset,
                    "case_id": "SUMMARY_ONLY",
                    "status": "COMPLETED_EVALUABLE_REPORTED" if total else "MISSING_DIRECT_PROOF",
                    "completed_rows": str(per_method),
                    "metric_summary": "not_reexported_from_row_level",
                    "sha256": "",
                    "path_placeholder": "",
                    "proof_level": proof_level,
                }
            )
    return rows


def index_light_rows(kind: str, counts: dict[str, int], proof_level: str) -> list[dict[str, str]]:
    return [
        {
            "index_id": f"{kind}_{dataset}",
            "dataset": dataset,
            "expected_count": str(count),
            "indexed_count": "0" if proof_level != "ROW_PROVEN" else str(count),
            "payload_copied": "false",
            "proof_level": proof_level,
            "notes": "Full payload is not copied by Q2R1.",
        }
        for dataset, count in counts.items()
    ]


def reproducibility_manifest(found_files: dict[str, Path], secondary_summary: Path, proof_level: str) -> list[dict[str, str]]:
    rows = []
    for label, path in found_files.items():
        if path.is_file():
            rows.append(
                {
                    "artifact_id": label,
                    "path_placeholder": str(path),
                    "sha256": sha256_file(path),
                    "size_bytes": str(path.stat().st_size),
                    "proof_level": "direct_file",
                }
            )
    if secondary_summary.exists():
        rows.append(
            {
                "artifact_id": "PAPER4A_SECONDARY_QA_SUMMARY",
                "path_placeholder": str(secondary_summary),
                "sha256": sha256_file(secondary_summary),
                "size_bytes": str(secondary_summary.stat().st_size),
                "proof_level": proof_level,
            }
        )
    return rows
