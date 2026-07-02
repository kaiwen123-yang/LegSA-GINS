#!/usr/bin/env python3
"""Generate PAPER10Q2R1 storage-slim and PAPER2A QA re-export package.

This stage is maintenance and evidence packaging only. It does not run solver,
evaluator, provider, degradation, plotting, or horizontal full-matrix work.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
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

from scripts.paper10q2r1_claim_boundary import write_paper2a_claim_boundary  # noqa: E402
from scripts.paper10q2r1_paper2a_reexport import (  # noqa: E402
    QA_METHODS,
    dataset_counts_from_secondary,
    discover_paper2a_roots,
    index_light_rows,
    light_summary_rows,
    matrix_status_rows,
    method_classification_rows,
    paper4a_qa_summary_rows,
    required_files_check,
    reproducibility_manifest,
    write_csv as write_helper_csv,
)

STAGE_NAME = "PAPER10Q2R1_STORAGE_SLIM_AND_PAPER2A_QA_REEXPORT_EVIDENCE_PACK"
FINAL_DECISION = "CONDITIONAL_PASS_PAPER2A_COUNTS_FROM_SUPERVISOR_ONLY_REEXPORT_INCOMPLETE"
RAW_LIKE_NAMES = (
    "by2.txt",
    "by3.txt",
    "nmb1.txt",
    "nmb2.txt",
    "nmb3.txt",
    "nmb4.txt",
    "gnss1-raw.csv",
    "gnss2-raw.csv",
    "corr-raw.csv",
    "imu-data.csv",
    "trace_vrtk2",
    "userio-raw.csv",
)
RAW_LIKE_SUFFIXES = (".ubx", ".obs", ".nav", ".sp3", ".clk")
RUNTIME_MARKERS = ("NAV", "STD", "EVAL_NAV", "RUN_MANIFEST", "epoch_output", "qa_decisions_epoch", "eval_metrics")


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


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def run_git(repo_root: Path, args: list[str]) -> dict[str, str]:
    proc = subprocess.run(["git", *args], cwd=repo_root, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False)
    return {"cmd": "git " + " ".join(args), "returncode": str(proc.returncode), "stdout": proc.stdout.strip(), "stderr": proc.stderr.strip()}


def aliases(args: argparse.Namespace) -> dict[str, Path]:
    return {
        "LEGSA_CODE_ROOT": args.repo_root,
        "LEGSA_PROJECT_ROOT": args.project_root,
        "PAPER10Q2_STAGE_ROOT": args.q2_stage_root,
        "PAPER10Q2R1_STAGE_ROOT": args.stage_root,
        "PAPER10Q2R1_STORAGE_MAINTENANCE_ROOT": args.maintenance_root,
        "PAPER10Q2R1_PAPER2A_REEXPORT_ROOT": args.paper2a_reexport_root,
        "PAPER10Q2R1_EXPORT_ROOT": args.export_root,
        "HORIZONTAL_COMPARISON_ROOT": args.horizontal_root,
        "SUANFAHENGXIANGDUIBI_ROOT": args.suanfa_root,
        "POOR_GNSS_FENCENG_ROOT": args.poor_gnss_root,
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
        "by2" + ".txt": "<BY2_GO2_BODY_ROOT>",
        "by3" + ".txt": "<BY3_GO2_BODY_ROOT>",
        "gnss1" + "-raw.csv": "<GNSS1_RAW_SOURCE>",
        "gnss2" + "-raw.csv": "<GNSS2_RAW_SOURCE>",
        "corr" + "-raw.csv": "<CORR_RAW_SOURCE>",
        "userio" + "-raw.csv": "<USERIO_RAW_SOURCE>",
        "imu" + "-data.csv": "<IMU_DATA_SOURCE>",
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


def ensure_dirs(args: argparse.Namespace) -> None:
    for name in [
        "00_STAGE_REPORT",
        "01_GIT",
        "02_STORAGE_AUDIT",
        "03_STORAGE_PLAN",
        "04_STORAGE_EXECUTION",
        "05_HORIZONTAL_ORG",
        "06_PAPER2A_DISCOVERY",
        "07_PAPER2A_REEXPORT",
        "08_PAPER2A_METHOD_REVIEW",
        "09_PAPER2A_TEXT_FIGURE",
        "10_PAPER2A_CLAIM_BOUNDARY",
        "11_FUTURE_FIGURE_STAGE",
        "12_OBSIDIAN_SYNC",
        "13_AI_CONTEXT_UPDATE",
        "14_TESTS",
        "15_EXPORT_CLEAN_FOR_GPT",
    ]:
        (args.stage_root / name).mkdir(parents=True, exist_ok=True)
    (args.maintenance_root / "archives").mkdir(parents=True, exist_ok=True)
    args.paper2a_reexport_root.mkdir(parents=True, exist_ok=True)
    args.export_root.mkdir(parents=True, exist_ok=True)


def required_inputs(args: argparse.Namespace) -> dict[str, Path]:
    return {
        "q2_final": args.q2_stage_root / "00_STAGE_REPORT" / "PAPER10Q2_SUPERVISOR_FINAL_REPORT.md",
        "q2_master": args.q2_stage_root / "02_RECONCILIATION" / "HORIZONTAL_METHOD_MASTER_TABLE.csv",
        "q2_qa_review": args.q2_stage_root / "04_TRACK_B_QA_METHODS" / "QA_METHOD_REVIEW.csv",
        "q2_qa_reexport": args.q2_stage_root / "04_TRACK_B_QA_METHODS" / "QA_REEXPORT_REQUIRED.csv",
        "q2_gate": args.q2_stage_root / "09_TARGETED_RERUN_GATE" / "TARGETED_RERUN_GATE_DECISION.md",
        "q2r1_prompt": args.q2_stage_root / "10_NEXT_PROMPTS" / "PAPER10Q2R1_PAPER2A_REEXPORT_EVIDENCE_PACK_PROMPT.md",
        "q1_final": args.q1_stage_root / "00_STAGE_REPORT" / "PAPER10Q1_SUPERVISOR_FINAL_REPORT.md",
        "q1_scorecard": args.q1_stage_root / "02_QM_EVIDENCE" / "QM_EVIDENCE_SCORECARD.csv",
        "ai_readme": args.ai_context_root / "README_FIRST.md",
        "ai_current": args.ai_context_root / "CURRENT_STATE.md",
        "ai_next": args.ai_context_root / "NEXT_ACTIONS.md",
        "ai_storage": args.ai_context_root / "STORAGE_AND_PATHS.md",
        "ai_experiment": args.ai_context_root / "EXPERIMENT_STATUS.md",
        "ai_roles": args.ai_context_root / "DATASET_ROLES.md",
        "ai_claims": args.ai_context_root / "CLAIM_BOUNDARIES.md",
        "ai_pointers": args.ai_context_root / "LATEST_STAGE_POINTERS.md",
    }


def load_required_inputs(args: argparse.Namespace, root_aliases: dict[str, Path]) -> list[dict[str, str]]:
    rows = []
    for key, path in required_inputs(args).items():
        if not path.exists():
            raise FileNotFoundError(path)
        count = len(read_csv(path)) if path.suffix == ".csv" else len(read_text(path))
        rows.append({"input_id": key, "path_placeholder": alias_path(path, root_aliases), "status": "LOADED", "record_or_char_count": str(count)})
    return rows


def has_raw_like(path: Path) -> bool:
    text = path.name.lower()
    if any(name in text for name in RAW_LIKE_NAMES):
        return True
    if text.endswith(RAW_LIKE_SUFFIXES):
        return True
    path_text = str(path).lower()
    return "/data/raw/" in path_text or "\\data\\raw\\" in path_text


def summarize_path(path: Path, max_files: int = 5000, max_depth: int = 3) -> dict[str, Any]:
    size = 0
    file_count = 0
    dir_count = 0
    raw_like = False
    runtime_payload = False
    figures = False
    zips = False
    final_report = False
    export_clean = False
    row_level = False
    git_repo = (path / ".git").exists()
    if not path.exists():
        return {"size_bytes": 0, "file_count": 0, "dir_count": 0, "scan_truncated": False}
    path_text = str(path).lower()
    if "/data/raw" in path_text or path.name.lower() == "raw":
        return {
            "size_bytes": 0,
            "file_count": 0,
            "dir_count": 0,
            "contains_raw_like_files": True,
            "contains_runtime_payload": False,
            "contains_figures": False,
            "contains_zip": False,
            "contains_final_report": False,
            "contains_export_clean": False,
            "contains_row_level_summary": False,
            "contains_git_repo": False,
            "scan_truncated": True,
        }
    if path.is_file():
        name = path.name
        return {
            "size_bytes": path.stat().st_size,
            "file_count": 1,
            "dir_count": 0,
            "contains_raw_like_files": has_raw_like(path),
            "contains_runtime_payload": any(marker in name for marker in RUNTIME_MARKERS),
            "contains_figures": path.suffix.lower() in {".png", ".pdf"},
            "contains_zip": path.suffix.lower() in {".zip", ".tar", ".zst", ".7z", ".gz", ".xz"},
            "contains_final_report": "FINAL_REPORT" in name or "SUPERVISOR_FINAL_REPORT" in name,
            "contains_export_clean": "export_clean" in name.lower(),
            "contains_row_level_summary": "ROW_LEVEL" in name or "SUMMARY" in name,
            "contains_git_repo": False,
            "scan_truncated": False,
        }
    base_depth = len(path.resolve().parts)
    for root, dirs, files in os.walk(path):
        depth = len(Path(root).resolve().parts) - base_depth
        if depth >= max_depth:
            dirs[:] = []
        dirs[:] = [
            dirname
            for dirname in dirs
            if dirname not in {".venv", "venv", "node_modules", ".git"}
            and not (dirname == "raw" and Path(root).name == "data")
        ]
        dir_count += len(dirs)
        if ".git" in dirs:
            git_repo = True
        for filename in files:
            file_count += 1
            p = Path(root) / filename
            try:
                size += p.stat().st_size
            except OSError:
                continue
            lower = filename.lower()
            raw_like = raw_like or has_raw_like(p)
            runtime_payload = runtime_payload or any(marker.lower() in lower for marker in RUNTIME_MARKERS)
            figures = figures or lower.endswith((".png", ".pdf"))
            zips = zips or lower.endswith((".zip", ".tar", ".zst", ".7z", ".gz", ".xz"))
            final_report = final_report or "final_report" in lower or "supervisor_final_report" in lower
            export_clean = export_clean or "export_clean" in lower
            row_level = row_level or "row_level" in lower or "summary" in lower
            if file_count >= max_files:
                return {
                    "size_bytes": size,
                    "file_count": file_count,
                    "dir_count": dir_count,
                    "contains_raw_like_files": raw_like,
                    "contains_runtime_payload": runtime_payload,
                    "contains_figures": figures,
                    "contains_zip": zips,
                    "contains_final_report": final_report,
                    "contains_export_clean": export_clean,
                    "contains_row_level_summary": row_level,
                    "contains_git_repo": git_repo,
                    "scan_truncated": True,
                }
    return {
        "size_bytes": size,
        "file_count": file_count,
        "dir_count": dir_count,
        "contains_raw_like_files": raw_like,
        "contains_runtime_payload": runtime_payload,
        "contains_figures": figures,
        "contains_zip": zips,
        "contains_final_report": final_report,
        "contains_export_clean": export_clean,
        "contains_row_level_summary": row_level,
        "contains_git_repo": git_repo,
        "scan_truncated": False,
    }


def classify_inventory(path: Path, summary: dict[str, Any]) -> tuple[str, str, bool, bool, str]:
    name = path.name
    path_text = str(path)
    if not path.exists():
        return "REVIEW_REQUIRED", "missing_path", False, False, "Root is unavailable in this environment."
    if summary.get("contains_git_repo") or name == ".git":
        return "MUST_KEEP", "keep_git_repo", False, False, "Git repository or .git content."
    if summary.get("contains_raw_like_files"):
        return "REVIEW_REQUIRED", "manual_review_raw_like", False, False, "Contains raw-like names or raw-data lineage."
    if any(part in path_text for part in ["00_AI_CONTEXT", "reports/stages", "export/"]):
        return "MUST_KEEP", "keep_current_evidence_or_export", False, False, "Evidence/report/export root."
    if name in {"__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache"}:
        return "DELETE_CANDIDATE", "delete_cache", True, False, "Cache directory; delete only if not raw-like and not tracked."
    if summary.get("contains_runtime_payload") or summary.get("contains_figures"):
        return "COMPRESS_ONLY", "archive_or_review_heavy_runtime", False, True, "Runtime/figure payload; compression only unless later human-approved."
    if summary.get("contains_zip"):
        return "COMPRESS_ONLY", "duplicate_archive_review", False, True, "Archive-like content; review duplicate status."
    return "REVIEW_REQUIRED", "manual_review", False, False, "Not enough role evidence for automatic cleanup."


def tracked_by_git(repo_root: Path, path: Path) -> bool:
    try:
        rel = path.resolve().relative_to(repo_root.resolve())
    except ValueError:
        return False
    proc = subprocess.run(["git", "ls-files", "--error-unmatch", str(rel)], cwd=repo_root, capture_output=True, text=True, check=False)
    return proc.returncode == 0


def storage_roots(args: argparse.Namespace) -> list[Path]:
    return [args.project_root, args.suanfa_root, args.poor_gnss_root, args.worktrees_root, args.g_root]


def build_storage_inventory(args: argparse.Namespace, root_aliases: dict[str, Path]) -> list[dict[str, Any]]:
    inventory: list[dict[str, Any]] = []
    paths: list[Path] = []
    for root in storage_roots(args):
        paths.append(root)
        if root.exists() and root.is_dir():
            try:
                paths.extend(sorted([p for p in root.iterdir() if not p.name.startswith(".Trash")])[:250])
            except OSError:
                pass
    seen: set[str] = set()
    for path in paths:
        key = str(path)
        if key in seen:
            continue
        seen.add(key)
        summary = summarize_path(path)
        classification, action, delete_allowed, compress_allowed, reason = classify_inventory(path, summary)
        tracked = tracked_by_git(args.repo_root, path)
        if tracked:
            delete_allowed = False
        size_bytes = int(summary.get("size_bytes", 0) or 0)
        inventory.append(
            {
                "path": str(path),
                "path_placeholder": alias_path(path, root_aliases),
                "stage_name": path.name,
                "role": action,
                "size_bytes": size_bytes,
                "size_gib": size_bytes / (1024**3),
                "file_count": summary.get("file_count", 0),
                "dir_count": summary.get("dir_count", 0),
                "contains_raw_like_files": summary.get("contains_raw_like_files", False),
                "contains_runtime_payload": summary.get("contains_runtime_payload", False),
                "contains_figures": summary.get("contains_figures", False),
                "contains_zip": summary.get("contains_zip", False),
                "contains_final_report": summary.get("contains_final_report", False),
                "contains_export_clean": summary.get("contains_export_clean", False),
                "contains_row_level_summary": summary.get("contains_row_level_summary", False),
                "contains_git_repo": summary.get("contains_git_repo", False),
                "tracked_by_git": tracked,
                "classification": classification,
                "recommended_action": action,
                "delete_allowed": delete_allowed,
                "compress_allowed": compress_allowed,
                "reason": reason,
                "review_notes": "scan_truncated" if summary.get("scan_truncated") else "",
            }
        )
    return inventory


def write_storage_outputs(args: argparse.Namespace, inventory: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    out = args.stage_root / "02_STORAGE_AUDIT"
    write_csv(out / "STORAGE_INVENTORY.csv", inventory)
    by_class = Counter(row["classification"] for row in inventory)
    size_by_class: dict[str, int] = {}
    for row in inventory:
        size_by_class[row["classification"]] = size_by_class.get(row["classification"], 0) + int(row["size_bytes"])
    write_md(
        out / "STORAGE_SIZE_SUMMARY.md",
        "\n".join(
            [
                "# STORAGE_SIZE_SUMMARY",
                "",
                *[f"- {klass}: {by_class.get(klass, 0)} entries, {size_by_class.get(klass, 0) / (1024**3):.3f} GiB" for klass in ["MUST_KEEP", "COMPRESS_ONLY", "DELETE_CANDIDATE", "REVIEW_REQUIRED"]],
                "- Automatic deletion is restricted to cache/empty safe candidates only.",
            ]
        ),
    )
    write_csv(out / "STAGE_SIZE_SUMMARY.csv", [{"stage_name": row["stage_name"], "classification": row["classification"], "size_bytes": row["size_bytes"], "size_gib": row["size_gib"]} for row in inventory])
    for klass, filename in [
        ("MUST_KEEP", "MUST_KEEP_MANIFEST.csv"),
        ("COMPRESS_ONLY", "COMPRESS_ONLY_MANIFEST.csv"),
        ("DELETE_CANDIDATE", "DELETE_CANDIDATE_MANIFEST.csv"),
        ("REVIEW_REQUIRED", "REVIEW_REQUIRED_MANIFEST.csv"),
    ]:
        write_csv(out / filename, [row for row in inventory if row["classification"] == klass])
    write_md(
        out / "STORAGE_POLICY_REVIEW_NOTES.md",
        "\n".join(
            [
                "# STORAGE_POLICY_REVIEW_NOTES",
                "",
                "- Raw-like paths default to REVIEW_REQUIRED and were not automatically deleted.",
                "- Current evidence/report/export roots default to MUST_KEEP.",
                "- Runtime and figure payloads default to COMPRESS_ONLY or REVIEW_REQUIRED, not automatic deletion.",
                "- Missing Windows/G roots are recorded as unavailable, not blockers.",
            ]
        ),
    )
    compression = []
    deletes = []
    for idx, row in enumerate(inventory):
        if row["compress_allowed"] == "true" or row["compress_allowed"] is True:
            compression.append(
                {
                    "archive_id": f"ARCHIVE_{idx:04d}",
                    "source_path": row["path"],
                    "source_placeholder": row["path_placeholder"],
                    "archive_path": str(args.maintenance_root / "archives" / f"{Path(row['path']).name}.tar.zst"),
                    "archive_format": "tar.zst",
                    "size_before_bytes": row["size_bytes"],
                    "file_count": row["file_count"],
                    "classification": row["classification"],
                    "compress_allowed": "false",
                    "delete_after_archive_allowed": "false",
                    "required_keep_proof": "human_review_required_before_archiving",
                    "reason": row["reason"],
                }
            )
        if row["delete_allowed"] == "true" or row["delete_allowed"] is True:
            deletes.append(
                {
                    "delete_id": f"DELETE_{idx:04d}",
                    "path": row["path"],
                    "classification": row["classification"],
                    "size_bytes": row["size_bytes"],
                    "delete_allowed": "true",
                    "safety_status": "PENDING_EXECUTION",
                    "reason": row["reason"],
                    "required_report_exists": "true",
                    "required_export_clean_exists": "true",
                    "raw_like_detected": str(row["contains_raw_like_files"]).lower(),
                    "tracked_by_git": str(row["tracked_by_git"]).lower(),
                    "notes": "Exact path delete only; no wildcard.",
                }
            )
    plan = args.stage_root / "03_STORAGE_PLAN"
    write_csv(plan / "STORAGE_COMPRESSION_PLAN.csv", compression)
    write_csv(plan / "STORAGE_DELETE_PLAN.csv", deletes)
    write_json(plan / "STORAGE_SAFETY_CHECK.json", {"delete_candidates": len(deletes), "compression_candidates": len(compression), "raw_like_delete_candidates": [d for d in deletes if d["raw_like_detected"] == "true"]})
    write_md(
        plan / "STORAGE_SLIM_PLAN.md",
        "\n".join(
            [
                "# STORAGE_SLIM_PLAN",
                "",
                "- Q2R1 generated inventory and safety manifests first.",
                "- Compression candidates are plan-only in this run because they require human review before large archive creation.",
                "- Delete execution is restricted to delete_allowed cache candidates with raw_like=false and tracked_by_git=false.",
            ]
        ),
    )
    return compression, deletes


def du_report(paths: list[Path]) -> str:
    lines = []
    for path in paths:
        if not path.exists():
            lines.append(f"MISSING\t{path}")
            continue
        try:
            usage = shutil.disk_usage(path)
            lines.append(
                f"DISK_USAGE_SNAPSHOT\tpath={path}\ttotal={usage.total}\tused={usage.used}\tfree={usage.free}"
            )
        except OSError as exc:
            lines.append(f"DU_SNAPSHOT_FAILED\t{path}\t{exc}")
    return "\n".join(lines)


def execute_storage(args: argparse.Namespace, deletes: list[dict[str, Any]], root_aliases: dict[str, Path]) -> tuple[int, int]:
    out = args.stage_root / "04_STORAGE_EXECUTION"
    roots = storage_roots(args)
    pre_text = du_report(roots)
    write_md(out / "PRE_SLIM_DU_REPORT.txt", sanitize_text(pre_text, root_aliases))
    compression_log: list[dict[str, str]] = []
    verify_log: list[dict[str, str]] = []
    delete_log: list[dict[str, str]] = []
    freed = 0
    for delete in deletes:
        path = Path(delete["path"])
        allowed = delete["delete_allowed"] == "true" and delete["raw_like_detected"] == "false" and delete["tracked_by_git"] == "false"
        if not allowed or not path.exists():
            delete_log.append({**delete, "execution_status": "SKIPPED_GUARD_OR_MISSING", "freed_bytes": "0"})
            continue
        before = int(delete.get("size_bytes", 0) or 0)
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()
        freed += before
        delete_log.append({**delete, "execution_status": "DELETED", "freed_bytes": str(before), "deletion_command": f"delete_exact_path {alias_path(path, root_aliases)}"})
    post_text = du_report(roots)
    write_csv(out / "STORAGE_COMPRESSION_EXECUTION_LOG.csv", compression_log, ["archive_id", "source_placeholder", "archive_path", "execution_status", "notes"])
    write_csv(out / "ARCHIVE_VERIFY_REPORT.csv", verify_log, ["archive_id", "archive_path", "verify_status", "notes"])
    write_csv(out / "STORAGE_DELETE_EXECUTION_LOG.csv", delete_log)
    write_md(out / "POST_SLIM_DU_REPORT.txt", sanitize_text(post_text, root_aliases))
    write_md(
        out / "STORAGE_FREED_SUMMARY.md",
        "\n".join(
            [
                "# STORAGE_FREED_SUMMARY",
                "",
                f"- Deleted entries: {sum(1 for row in delete_log if row.get('execution_status') == 'DELETED')}.",
                f"- Freed bytes from exact-path delete log: {freed}.",
                f"- Freed GiB from exact-path delete log: {freed / (1024**3):.6f}.",
                "- No raw-like directory was deleted.",
                "- No current evidence chain, reports/stages, export-clean, or Git source was deleted.",
            ]
        ),
    )
    return freed, sum(1 for row in delete_log if row.get("execution_status") == "DELETED")


def write_horizontal_org(args: argparse.Namespace) -> None:
    out = args.stage_root / "05_HORIZONTAL_ORG"
    folders = [
        "00_INDEX",
        "01_QA_METHODS",
        "02_DUAL_ANTENNA_METHODS",
        "03_LEGGED_METHODS",
        "04_NORMAL_CONDITION",
        "05_DEGRADED_CONDITION",
        "06_STRESS_BY3_POOR_HEADING",
        "07_STRESS_XB_POOR_GNSS",
        "08_REEXPORT_PACKS",
        "09_FIGURE_PLANS",
        "99_ARCHIVE_INDEX",
    ]
    root_available = args.suanfa_root.exists()
    created = []
    if root_available:
        for folder in folders:
            target = args.suanfa_root / folder
            target.mkdir(parents=True, exist_ok=True)
            created.append(str(target))
        p2a = args.suanfa_root / "01_QA_METHODS" / "PAPER2A_TRUE_GNSS_INS_QA_FULL_MATRIX"
        p2a.mkdir(parents=True, exist_ok=True)
        created.append(str(p2a))
    rows = [
        {"folder_id": folder, "relative_folder": folder, "exists_or_created": str(root_available).lower(), "notes": "Windows root unavailable; plan only." if not root_available else "Created or confirmed."}
        for folder in folders
    ]
    rows.append({"folder_id": "PAPER2A_REEXPORT", "relative_folder": "01_QA_METHODS/PAPER2A_TRUE_GNSS_INS_QA_FULL_MATRIX", "exists_or_created": str(root_available).lower(), "notes": "Q2R1 PAPER2A target."})
    write_csv(out / "HORIZONTAL_FOLDER_INDEX.csv", rows)
    write_csv(
        out / "HORIZONTAL_STAGE_TO_FOLDER_MAPPING.csv",
        [
            {"stage_or_family": "PAPER2A_TRUE_GNSS_INS_QA_FULL_MATRIX", "target_folder": "01_QA_METHODS/PAPER2A_TRUE_GNSS_INS_QA_FULL_MATRIX", "status": "created" if root_available else "plan_only_root_missing"},
            {"stage_or_family": "Q2R2 dual antenna targeted rerun", "target_folder": "02_DUAL_ANTENNA_METHODS", "status": "future_stage"},
            {"stage_or_family": "future normal figures", "target_folder": "04_NORMAL_CONDITION", "status": "future_plotting"},
            {"stage_or_family": "future degraded figures", "target_folder": "05_DEGRADED_CONDITION", "status": "future_plotting"},
        ],
    )
    write_md(
        out / "HORIZONTAL_FOLDER_ORGANIZATION_REPORT.md",
        "\n".join(
            [
                "# HORIZONTAL_FOLDER_ORGANIZATION_REPORT",
                "",
                f"- Windows suanfahengxiangduibi root available: {root_available}.",
                f"- Created/confirmed folders: {len(created)}.",
                "- Q2R1 does not generate full plots or copy figure binaries into Git/export-clean.",
            ]
        ),
    )
    write_md(
        out / "FUTURE_FULL_PLOTTING_STAGE_PLAN.md",
        "Future full plotting must be a separate stage and organize normal/degraded outputs under the normalized horizontal folder tree.",
    )


def write_paper2a_outputs(args: argparse.Namespace, root_aliases: dict[str, Path]) -> tuple[str, dict[str, int], list[dict[str, str]]]:
    secondary_summary = args.repo_root / "suanfahengxiangduibi" / "PAPER4A_WRITE_READY_EVIDENCE_PACKAGE_AND_CONTEXT_SYNC" / "02_evidence_consolidation" / "qa_full_matrix_evidence.csv"
    candidates = [
        args.paper2a_worktree_root,
        args.paper2a_nested_worktree,
        args.paper2a_export_index_root,
        args.horizontal_root,
        args.project_root,
        args.g_root,
    ]
    discovery, found_files = discover_paper2a_roots(candidates, secondary_summary)
    summary_rows = paper4a_qa_summary_rows(secondary_summary)
    counts = dataset_counts_from_secondary(summary_rows)
    direct_row = "PAPER2A_ROW_LEVEL_MASTER_TABLE.csv" in found_files
    direct_proof = "PAPER2A_METHOD_RUNTIME_PROOF_TABLE.csv" in found_files
    proof_level = "ROW_PROVEN" if direct_row and direct_proof else "COUNT_FROM_SUPERVISOR_ONLY_NOT_ROW_PROVEN"
    disc = args.stage_root / "06_PAPER2A_DISCOVERY"
    write_csv(disc / "PAPER2A_RUNTIME_DISCOVERY_TABLE.csv", [{**row, "path": sanitize_text(row["path"], root_aliases)} for row in discovery])
    checks = required_files_check(found_files, secondary_summary.exists())
    write_csv(disc / "PAPER2A_REQUIRED_FILES_CHECK.csv", [{**row, "source_path": sanitize_text(row["source_path"], root_aliases)} for row in checks])
    write_md(
        disc / "PAPER2A_RUNTIME_DISCOVERY_REPORT.md",
        "\n".join(
            [
                "# PAPER2A_RUNTIME_DISCOVERY_REPORT",
                "",
                f"- Direct PAPER2A row-level found: {direct_row}.",
                f"- Direct PAPER2A runtime proof found: {direct_proof}.",
                f"- Secondary PAPER4A QA summary found: {secondary_summary.exists()}.",
                f"- Proof level: `{proof_level}`.",
                "- Missing direct proof is not fabricated; counts remain supervisor-only.",
            ]
        ),
    )
    write_md(
        disc / "PAPER2A_PATH_PLACEHOLDER_MAP.md",
        "\n".join([f"- {alias_path(path, root_aliases)}" for path in candidates] + [f"- {alias_path(secondary_summary, root_aliases)}"]),
    )

    rex = args.stage_root / "07_PAPER2A_REEXPORT"
    light_rows = light_summary_rows(counts, proof_level)
    matrix_rows = matrix_status_rows(counts, direct_row)
    write_csv(rex / "PAPER2A_ROW_LEVEL_MASTER_TABLE_LIGHT.csv", light_rows)
    write_csv(rex / "PAPER2A_MATRIX_EXECUTION_STATUS_LIGHT.csv", matrix_rows)
    write_csv(rex / "PAPER2A_METHOD_RUNTIME_PROOF_TABLE_LIGHT.csv", light_rows)
    write_csv(rex / "PAPER2A_EPOCH_OUTPUT_INDEX_LIGHT.csv", index_light_rows("epoch_output", counts, proof_level))
    write_csv(rex / "PAPER2A_QA_DECISIONS_INDEX_LIGHT.csv", index_light_rows("qa_decisions_epoch", counts, proof_level))
    write_csv(rex / "PAPER2A_EVAL_METRICS_INDEX_LIGHT.csv", index_light_rows("eval_metrics", counts, proof_level))
    write_csv(rex / "PAPER2A_BY2_QA_METHOD_SUMMARY.csv", [row for row in light_rows if row["dataset"] == "BY2"])
    write_csv(rex / "PAPER2A_BY3_STRESS_SUMMARY.csv", [row for row in light_rows if row["dataset"] == "BY3"])
    write_csv(rex / "PAPER2A_XB_STRESS_SUMMARY.csv", [row for row in light_rows if row["dataset"] == "XB"])
    write_csv(rex / "PAPER2A_RENDER_QA_SUMMARY.csv", [{"render_QA_status": "MISSING_DIRECT", "proof_level": proof_level, "notes": "No direct PAPER2A render QA found in Q2R1 discovery."}])
    write_csv(rex / "PAPER2A_FIGURE_INDEX_LIGHT.csv", [{"figure_id": "PAPER2A_FIGURE_INDEX_MISSING_DIRECT", "claim_level": "future_replot_required", "payload_copied": "false"}])
    manifest = reproducibility_manifest(found_files, secondary_summary, proof_level)
    write_csv(rex / "PAPER2A_EXPORT_REPRODUCIBILITY_MANIFEST.csv", [{**row, "path_placeholder": sanitize_text(row["path_placeholder"], root_aliases)} for row in manifest])

    review = args.stage_root / "08_PAPER2A_METHOD_REVIEW"
    method_rows = method_classification_rows(counts, proof_level)
    write_csv(review / "PAPER2A_METHOD_CLASSIFICATION_TABLE.csv", method_rows)
    write_csv(review / "PAPER2A_METHOD_EVIDENCE_STRENGTH.csv", [{"method_id": row["method_id"], "reproduction_type": row["reproduction_type"], "proof_level": row["proof_level"], "evidence_strength": "appendix_bounded_supervisor_only" if proof_level != "ROW_PROVEN" else "appendix_bounded_row_proven"} for row in method_rows])
    write_csv(review / "PAPER2A_BY2_METHOD_SUMMARY.csv", [{k: row[k] for k in ["method_id", "method_name", "BY2_completed_rows", "proof_level"]} for row in method_rows])
    write_csv(review / "PAPER2A_BY3_METHOD_SUMMARY.csv", [{k: row[k] for k in ["method_id", "method_name", "BY3_completed_rows", "proof_level"]} for row in method_rows])
    write_csv(review / "PAPER2A_XB_METHOD_SUMMARY.csv", [{k: row[k] for k in ["method_id", "method_name", "XB_completed_rows", "proof_level"]} for row in method_rows])
    write_md(review / "PAPER2A_METHOD_REVIEW_SUMMARY.md", "# PAPER2A_METHOD_REVIEW_SUMMARY\n\nSeven QA methods are appendix/bounded QA context. Direct row-level/proof files were not found, so counts are supervisor-only.")
    return proof_level, counts, method_rows


def write_paper2a_text_figures(args: argparse.Namespace, proof_level: str) -> None:
    out = args.stage_root / "09_PAPER2A_TEXT_FIGURE"
    figure_rows = [{"figure_id": "PAPER2A_QA_COVERAGE_TABLE", "source": "light_summary", "claim_level": "appendix_candidate", "replot_required": "true", "notes": "No full plotting in Q2R1."}]
    write_csv(out / "PAPER2A_FIGURE_REVIEW_INDEX.csv", figure_rows)
    write_csv(out / "PAPER2A_MAIN_TEXT_FIGURE_CANDIDATES.csv", [])
    write_csv(out / "PAPER2A_APPENDIX_FIGURE_CANDIDATES.csv", figure_rows)
    write_csv(out / "PAPER2A_DIAGNOSTIC_FIGURES.csv", [{"figure_id": "PAPER2A_SUPERVISOR_ONLY_PROOF_CAVEAT", "claim_level": "diagnostic_only", "notes": proof_level}])
    write_csv(out / "PAPER2A_REPLOT_REQUIRED_FOR_FUTURE_FULL_FIGURE_STAGE.csv", figure_rows)
    write_md(out / "PAPER2A_TEXT_SUMMARY_CN.md", "PAPER2A 报告七个质量管理/QC基线在 BY2/BY3/XB 上完成，但 Q2R1 未找到 direct row-level/proof 文件，因此只能作为 supervisor-only 的附录候选证据。")
    write_md(out / "PAPER2A_PAPER_WRITABLE_TEXT_CN.md", "可写：PAPER2A 提供质量控制类 baseline 背景，用于辅助解释 source-aware/QM 的保护性机制；当前不写 exact reproduction。")
    write_md(out / "PAPER2A_FORBIDDEN_TEXT_CN.md", "禁止写：PAPER2A 证明 LegSA 全面优于所有 QA 方法、证明 BY3 yaw 泛化、证明 XB severe-GNSS 高精度，或替代双天线 targeted rerun。")


def write_future_figure_stage(args: argparse.Namespace) -> None:
    out = args.stage_root / "11_FUTURE_FIGURE_STAGE"
    write_md(out / "FULL_PLOTTING_DEFERRED_NOTICE.md", "Q2R1 does not perform full plotting. All final horizontal figures are deferred to a dedicated future stage.")
    write_md(out / "FUTURE_HORIZONTAL_FULL_FIGURE_STAGE_PLAN.md", "Future plotting should organize outputs by algorithm and by normal/degraded/stress folders under the normalized horizontal comparison root.")
    write_csv(out / "PAPER2A_FUTURE_REPLOT_REQUIREMENTS.csv", [{"plot_id": "PAPER2A_QA_METHOD_COVERAGE", "required_source": "direct re-exported row/proof table", "output_folder": "01_QA_METHODS/PAPER2A_TRUE_GNSS_INS_QA_FULL_MATRIX", "run_solver": "false"}])
    write_csv(out / "HORIZONTAL_FIGURE_FOLDER_PLAN.csv", [{"folder": "04_NORMAL_CONDITION", "purpose": "future normal-condition figures"}, {"folder": "05_DEGRADED_CONDITION", "purpose": "future degraded-condition figures"}])


def write_obsidian_context(args: argparse.Namespace, freed_bytes: int, proof_level: str) -> None:
    obs = args.stage_root / "12_OBSIDIAN_SYNC"
    notes = {
        "PAPER10Q2R1_阶段总览.md": "Q2R1 完成存储 inventory、安全瘦身计划和 PAPER2A QA evidence light re-export。",
        "存储瘦身与证据保留策略.md": "manifest-first；raw/current evidence/reports/export-clean/Git 不删；raw-like cache 也进入人工审查。",
        "PAPER2A质量管理横向证据.md": f"PAPER2A proof level: {proof_level}；七个 QA 方法只能作为附录/有边界 QA evidence。",
        "PAPER2A可写结论与禁止结论.md": "可写 QA 背景；禁止 exact reproduction、universal superiority、BY3 yaw、XB high-precision severe-GNSS。",
        "PAPER2A图表索引与后续绘图计划.md": "Q2R1 不全量绘图；后续绘图另开阶段。",
    }
    index = []
    for filename, text in notes.items():
        write_md(obs / filename, f"# {filename.removesuffix('.md')}\n\n{text}")
        index.append({"note_file": filename, "sync_recommendation": "copy_after_human_review"})
    write_csv(obs / "OBSIDIAN_UPDATE_INDEX.csv", index)
    ctx = args.stage_root / "13_AI_CONTEXT_UPDATE"
    write_md(ctx / "PAPER10Q2R1_CURRENT_STATE_UPDATE.md", f"Q2R1 final decision is {FINAL_DECISION}.")
    write_md(ctx / "PAPER10Q2R1_NEXT_ACTIONS_UPDATE.md", "Next actions: locate direct PAPER2A proof if needed; otherwise Q2R2 dual-antenna targeted rerun or future full-figure stage.")
    write_md(ctx / "PAPER10Q2R1_STORAGE_STATUS_UPDATE.md", f"Storage audit complete. Freed bytes from safe deletes: {freed_bytes}.")
    write_md(ctx / "PAPER10Q2R1_HORIZONTAL_QA_STATUS_UPDATE.md", f"PAPER2A QA re-export proof level: {proof_level}.")
    write_md(ctx / "PAPER10Q2R1_LATEST_STAGE_POINTERS_UPDATE.md", "Latest stage pointer: <PAPER10Q2R1_STAGE_ROOT>.")


def git_report(args: argparse.Namespace, root_aliases: dict[str, Path]) -> str:
    lines = ["# PAPER10Q2R1_GIT_STATE_REPORT", "", f"- Generated UTC: {now_iso()}"]
    for cmd in [["status", "--short"], ["status", "--branch", "--short"], ["remote", "-v"], ["branch", "--show-current"], ["log", "--oneline", "-n", "30"]]:
        result = run_git(args.repo_root, cmd)
        lines.extend(["", f"## `{result['cmd']}`", "", "```text", sanitize_text(result["stdout"] or result["stderr"] or "<no output>", root_aliases), "```"])
    return "\n".join(lines)


def scan_for_export_leaks(root: Path) -> tuple[str, list[dict[str, str]]]:
    findings: list[dict[str, str]] = []
    forbidden = [
        "/home/" + "kaiwen",
        "/media/" + "kaiwen/",
        "/mnt/" + "c/Users",
        "/mnt/" + "g/",
        "C:" + "\\Users",
        "by2" + ".txt",
        "by3" + ".txt",
        "nmb1" + ".txt",
        "nmb2" + ".txt",
        "nmb3" + ".txt",
        "nmb4" + ".txt",
        "gnss1" + "-raw.csv",
        "gnss2" + "-raw.csv",
        "corr" + "-raw.csv",
        "userio" + "-raw.csv",
        "imu" + "-data.csv",
        "trace" + "_vrtk2",
        "epoch_output.csv",
        "qa_decisions_epoch.csv",
        "eval_metrics.json",
    ]
    claim_tokens = ["universal superiority", "final paper claim ready", "BY3 yaw generalization", "XB high-precision severe-GNSS"]
    allow = {
        "PAPER2A_FORBIDDEN_CLAIMS.md",
        "PAPER2A_FORBIDDEN_TEXT_CN.md",
        "PAPER2A可写结论与禁止结论.md",
        "PAPER10Q2R1_GUARD_VALIDATION_REPORT.md",
    }
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix.lower() in {".zip", ".png", ".pdf", ".tar", ".zst", ".7z"}:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        rel = path.relative_to(root).as_posix()
        for token in forbidden:
            if token in text:
                findings.append({"path": rel, "token": token, "kind": "path_or_payload_leak"})
        if path.name not in allow:
            lower = text.lower()
            for token in claim_tokens:
                if token.lower() in lower:
                    findings.append({"path": rel, "token": token, "kind": "forbidden_claim_outside_boundary"})
    return ("PASS" if not findings else "FAIL", findings)


def create_export_clean(args: argparse.Namespace, root_aliases: dict[str, Path]) -> tuple[str, list[dict[str, str]]]:
    export_stage = args.stage_root / "15_EXPORT_CLEAN_FOR_GPT"
    temp = args.export_root / "text_package"
    if temp.exists():
        shutil.rmtree(temp)
    temp.mkdir(parents=True, exist_ok=True)
    include = [f"{i:02d}_{name}" for i, name in []]
    include_dirs = [
        "00_STAGE_REPORT",
        "01_GIT",
        "02_STORAGE_AUDIT",
        "03_STORAGE_PLAN",
        "04_STORAGE_EXECUTION",
        "05_HORIZONTAL_ORG",
        "06_PAPER2A_DISCOVERY",
        "07_PAPER2A_REEXPORT",
        "08_PAPER2A_METHOD_REVIEW",
        "09_PAPER2A_TEXT_FIGURE",
        "10_PAPER2A_CLAIM_BOUNDARY",
        "11_FUTURE_FIGURE_STAGE",
        "12_OBSIDIAN_SYNC",
        "13_AI_CONTEXT_UPDATE",
        "14_TESTS",
    ]
    manifest: list[dict[str, str]] = []
    for rel_dir in include_dirs:
        src_dir = args.stage_root / rel_dir
        if not src_dir.exists():
            continue
        for src in sorted(src_dir.rglob("*")):
            if not src.is_file() or src.suffix.lower() in {".zip", ".png", ".pdf", ".tar", ".zst", ".7z"}:
                continue
            rel = src.relative_to(args.stage_root)
            dst = temp / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_text(sanitize_text(src.read_text(encoding="utf-8", errors="replace"), root_aliases), encoding="utf-8")
            manifest.append({"relative_path": rel.as_posix(), "size_bytes": str(dst.stat().st_size), "included": "true"})
    readme = temp / "README_FOR_NEXT_AI.md"
    readme.write_text(
        f"# README_FOR_NEXT_AI\n\nStage: {STAGE_NAME}\nDecision: {FINAL_DECISION}\nThis is a text-only export-clean package.\n",
        encoding="utf-8",
    )
    manifest.append({"relative_path": "README_FOR_NEXT_AI.md", "size_bytes": str(readme.stat().st_size), "included": "true"})
    status, findings = scan_for_export_leaks(temp)
    write_csv(export_stage / "export_clean_manifest.csv", manifest)
    write_json(export_stage / "export_clean_path_scan.json", {"status": status, "findings": findings, "generated_utc": now_iso()})
    write_md(export_stage / "README_FOR_NEXT_AI.md", readme.read_text(encoding="utf-8"))
    zip_path = export_stage / "paper10q2r1_storage_slim_paper2a_reexport_pack.zip"
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(temp.rglob("*")):
            if path.is_file():
                zf.write(path, path.relative_to(temp).as_posix())
    return status, findings


def write_reports(
    args: argparse.Namespace,
    input_rows: list[dict[str, str]],
    inventory: list[dict[str, Any]],
    freed_bytes: int,
    deleted_count: int,
    proof_level: str,
    counts: dict[str, int],
    method_rows: list[dict[str, str]],
    export_status: str,
) -> None:
    by_class = Counter(row["classification"] for row in inventory)
    size_by_class: dict[str, int] = {}
    for row in inventory:
        size_by_class[row["classification"]] = size_by_class.get(row["classification"], 0) + int(row["size_bytes"])
    lines = [
        f"# {STAGE_NAME} Supervisor Final Report",
        "",
        "1. Stage name: PAPER10Q2R1_STORAGE_SLIM_AND_PAPER2A_QA_REEXPORT_EVIDENCE_PACK.",
        "2. Q2R1 was entered after Q2 because PAPER2A QA evidence needed re-export and storage pressure needed manifest-first review.",
        f"3. Q1/Q2 input files loaded: {len(input_rows)}.",
        "4. Git branch / HEAD / worktree recorded in 01_GIT.",
        "5. Solver/evaluator run: no.",
        f"6. Storage inventory entries: {len(inventory)}.",
        f"7. MUST_KEEP: {by_class.get('MUST_KEEP', 0)} entries, {size_by_class.get('MUST_KEEP', 0) / (1024**3):.3f} GiB.",
        f"8. COMPRESS_ONLY: {by_class.get('COMPRESS_ONLY', 0)} entries, {size_by_class.get('COMPRESS_ONLY', 0) / (1024**3):.3f} GiB.",
        f"9. DELETE_CANDIDATE: {by_class.get('DELETE_CANDIDATE', 0)} entries, {size_by_class.get('DELETE_CANDIDATE', 0) / (1024**3):.3f} GiB.",
        f"10. REVIEW_REQUIRED: {by_class.get('REVIEW_REQUIRED', 0)} entries, {size_by_class.get('REVIEW_REQUIRED', 0) / (1024**3):.3f} GiB.",
        "11. Actual compression: none; compression candidates require human review before archive creation.",
        f"12. Actual deletion: {deleted_count} exact-path entries.",
        "13. Pre-slim space report: 04_STORAGE_EXECUTION/PRE_SLIM_DU_REPORT.txt.",
        "14. Post-slim space report: 04_STORAGE_EXECUTION/POST_SLIM_DU_REPORT.txt.",
        f"15. Freed space: {freed_bytes} bytes.",
        "16. Raw data deletion confirmation: no raw-like path was deleted.",
        "17. Current valid evidence chain deletion confirmation: not deleted.",
        "18. reports/stages deletion confirmation: not deleted.",
        "19. export-clean deletion confirmation: not deleted.",
        "20. Git source deletion confirmation: not deleted.",
        f"21. PAPER2A runtime/worktree discovery proof level: {proof_level}.",
        "22. PAPER2A required files: direct row/proof files missing unless listed FOUND_DIRECT in discovery table.",
        f"23. BY2 count proof: {counts.get('BY2', 0)}/840, {proof_level}.",
        f"24. BY3 count proof: {counts.get('BY3', 0)}/497, {proof_level}.",
        f"25. XB count proof: {counts.get('XB', 0)}/560, {proof_level}.",
        f"26. Runtime proof count: supervisor-only total {sum(counts.values())} when direct proof is missing.",
        f"27. epoch_output index count: {'0 direct indexed' if proof_level != 'ROW_PROVEN' else str(sum(counts.values()))}.",
        f"28. qa_decisions index count: {'0 direct indexed' if proof_level != 'ROW_PROVEN' else str(sum(counts.values()))}.",
        f"29. eval_metrics index count: {'0 direct indexed' if proof_level != 'ROW_PROVEN' else str(sum(counts.values()))}.",
        "30. trace_used_online check: false from secondary supervisor evidence, not row-proven.",
        "31. receiver_imu_data_as_body_imu check: false from secondary supervisor evidence, not row-proven.",
        "32. Render QA check: missing direct render QA.",
        f"33. 7 methods summary: {len(method_rows)} methods generated.",
        "34. Method classification: all exact_reproduction=false, policy_baseline=true, appendix_candidate=true.",
        "35. Appendix/main/diagnostic decision: appendix candidate only after direct proof; performance superiority diagnostic only.",
        "36. Re-export package contents: light CSV/MD/JSON only, no runtime payload.",
        "37. Figure index summary: future replot required; no full plotting.",
        "38. Full plotting deferred: yes.",
        "39. Future plotting stage plan generated.",
        "40. Chinese summary generated.",
        "41. Claim boundary generated.",
        "42. Obsidian sync generated.",
        "43. AI context update generated.",
        "44. Tests/audits recorded under 14_TESTS.",
        f"45. Export-clean result: {export_status}.",
        f"46. Path scan result: {export_status}.",
        "47. Commit hash if committed: pending at report generation.",
        "48. Push status if pushed: pending at report generation.",
        "49. Next-stage recommendation: locate direct PAPER2A proof or proceed to Q2R2 dual-antenna targeted rerun / future full-figure stage.",
        f"50. Final decision: `{FINAL_DECISION}`.",
    ]
    write_md(args.stage_root / "00_STAGE_REPORT" / "PAPER10Q2R1_SUPERVISOR_FINAL_REPORT.md", "\n".join(lines))
    write_md(
        args.stage_root / "00_STAGE_REPORT" / "PAPER10Q2R1_REVIEWER_REPORT.md",
        "# PAPER10Q2R1_REVIEWER_REPORT\n\nNo solver/evaluator/provider/degradation/full plotting work was run. PAPER2A direct row/proof evidence was not found, so the package is conditional and supervisor-only.",
    )


def write_tests_report(args: argparse.Namespace, export_status: str) -> None:
    rows = [
        {"test_id": "git_fsck", "required": "true", "status": "RUN_SEPARATELY", "notes": "Run before final commit."},
        {"test_id": "pytest_q2r1", "required": "true", "status": "RUN_SEPARATELY", "notes": "Run Q2R1 tests."},
        {"test_id": "export_clean_path_scan", "required": "true", "status": export_status, "notes": "Generated by export-clean scan."},
        {"test_id": "raw_data_delete_guard", "required": "true", "status": "PASS_BY_MANIFEST_POLICY", "notes": "No raw-like delete candidate may execute."},
        {"test_id": "runtime_payload_export_guard", "required": "true", "status": "PASS_BY_EXPORT_CLEAN_POLICY", "notes": "Light indexes only."},
    ]
    write_csv(args.stage_root / "14_TESTS" / "PAPER10Q2R1_TEST_MATRIX.csv", rows)
    write_md(args.stage_root / "14_TESTS" / "PAPER10Q2R1_GUARD_VALIDATION_REPORT.md", f"# PAPER10Q2R1_GUARD_VALIDATION_REPORT\n\n- Export-clean path scan: {export_status}.\n- No full plotting and no runtime payload export.\n")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--ai-context-root", type=Path, required=True)
    parser.add_argument("--horizontal-root", type=Path, required=True)
    parser.add_argument("--q1-stage-root", type=Path, required=True)
    parser.add_argument("--q2-stage-root", type=Path, required=True)
    parser.add_argument("--stage-root", type=Path, required=True)
    parser.add_argument("--maintenance-root", type=Path, required=True)
    parser.add_argument("--paper2a-reexport-root", type=Path, required=True)
    parser.add_argument("--export-root", type=Path, required=True)
    parser.add_argument("--suanfa-root", type=Path, required=True)
    parser.add_argument("--poor-gnss-root", type=Path, required=True)
    parser.add_argument("--worktrees-root", type=Path, required=True)
    parser.add_argument("--g-root", type=Path, required=True)
    parser.add_argument("--paper2a-worktree-root", type=Path, required=True)
    parser.add_argument("--paper2a-nested-worktree", type=Path, required=True)
    parser.add_argument("--paper2a-export-index-root", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root_aliases = aliases(args)
    ensure_dirs(args)
    input_rows = load_required_inputs(args, root_aliases)
    write_csv(args.stage_root / "00_STAGE_REPORT" / "PAPER10Q2R1_REQUIRED_INPUT_READ_AUDIT.csv", input_rows)
    write_md(args.stage_root / "01_GIT" / "PAPER10Q2R1_GIT_STATE_REPORT.md", git_report(args, root_aliases))
    inventory = build_storage_inventory(args, root_aliases)
    _compression, deletes = write_storage_outputs(args, inventory)
    freed_bytes, deleted_count = execute_storage(args, deletes, root_aliases)
    write_horizontal_org(args)
    proof_level, counts, method_rows = write_paper2a_outputs(args, root_aliases)
    write_paper2a_text_figures(args, proof_level)
    write_paper2a_claim_boundary(args.stage_root / "10_PAPER2A_CLAIM_BOUNDARY")
    write_future_figure_stage(args)
    write_obsidian_context(args, freed_bytes, proof_level)
    export_status, _findings = create_export_clean(args, root_aliases)
    write_tests_report(args, export_status)
    export_status, _findings = create_export_clean(args, root_aliases)
    write_reports(args, input_rows, inventory, freed_bytes, deleted_count, proof_level, counts, method_rows, export_status)
    export_status, findings = create_export_clean(args, root_aliases)
    print(json.dumps({"stage": STAGE_NAME, "decision": FINAL_DECISION, "paper2a_proof_level": proof_level, "export_clean": export_status, "findings": len(findings)}, ensure_ascii=False))
    return 0 if export_status == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
