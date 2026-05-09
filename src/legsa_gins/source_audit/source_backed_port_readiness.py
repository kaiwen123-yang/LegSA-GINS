"""Source-backed port readiness helpers for N4H4R0.

中文说明：本模块只做 reference/submodule/readiness 只读审计，不复制
final_v23 源码，不编译 reference 源码，也不把 reference 输出作为 solver
输入。
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any


REFERENCE_PATH = Path("reference/final_v23_repo")
EXPECTED_COMMIT = "5a4471efd4fcfcdc31e258a677af354c652ff16f"
CORE_SOURCE_FILES: dict[str, list[str]] = {
    "gi_engine.cpp": ["src/kf-gins/gi_engine.cpp"],
    "gi_engine.h": ["src/kf-gins/gi_engine.h"],
    "kf_gins_types.h": ["src/kf-gins/kf_gins_types.h"],
    "earth.h": ["src/common/earth.h"],
    "rotation.h": ["src/common/rotation.h"],
    "insmech.cpp": ["src/kf-gins/insmech.cpp"],
    "insmech.h": ["src/kf-gins/insmech.h"],
    "fileloader.cpp_or_cc": ["src/fileio/fileloader.cpp", "src/fileio/fileloader.cc"],
    "fileloader.h": ["src/fileio/fileloader.h"],
    "kf_gins.cpp": ["src/kf_gins.cpp"],
    "config": ["config/kf-gins.yaml", "dataset/kf-gins.yaml"],
}
LICENSE_CANDIDATES = {
    "LICENSE": ["LICENSE"],
    "COPYING": ["COPYING"],
    "README": ["README", "README.md", "README_CN.md"],
}


def _run_git(repo_root: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=repo_root,
        check=False,
        capture_output=True,
        text=True,
    )


def _run_gh(repo_root: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["gh", *args],
        cwd=repo_root,
        check=False,
        capture_output=True,
        text=True,
    )


def _git_output(repo_root: Path, args: list[str]) -> str:
    completed = _run_git(repo_root, args)
    if completed.returncode != 0:
        return ""
    return completed.stdout.strip()


def _first_existing(base: Path, candidates: list[str]) -> str | None:
    for rel in candidates:
        if (base / rel).exists():
            return rel
    return None


def collect_reference_status(repo_root: Path) -> dict[str, Any]:
    """Collect final_v23 reference submodule status.

    中文说明：这里只读取 gitlink、子模块文件和 license 线索；不会进入
    reference 编译，也不会复制源码到 LegSA 主仓。
    """

    repo_root = repo_root.resolve()
    reference_root = repo_root / REFERENCE_PATH
    gitmodules = repo_root / ".gitmodules"
    ls_files = _git_output(repo_root, ["ls-files", "-s", REFERENCE_PATH.as_posix()])
    ls_parts = ls_files.split()
    gitlink_mode = ls_parts[0] if len(ls_parts) >= 1 else None
    gitlink_commit = ls_parts[1] if len(ls_parts) >= 2 else None

    submodule_url = None
    if gitmodules.exists():
        completed = _run_git(
            repo_root,
            ["config", "--file", ".gitmodules", "--get", "submodule.reference/final_v23_repo.url"],
        )
        if completed.returncode == 0:
            submodule_url = completed.stdout.strip()

    actual_commit = _git_output(repo_root, ["-C", REFERENCE_PATH.as_posix(), "rev-parse", "HEAD"])
    submodule_status = _git_output(repo_root, ["submodule", "status", REFERENCE_PATH.as_posix()])
    submodule_dirty = _git_output(repo_root, ["-C", REFERENCE_PATH.as_posix(), "status", "--short"])

    source_files: dict[str, dict[str, Any]] = {}
    for role, candidates in CORE_SOURCE_FILES.items():
        found = _first_existing(reference_root, candidates)
        source_files[role] = {
            "candidates": candidates,
            "found": found,
            "exists": found is not None,
        }

    license_files: dict[str, dict[str, Any]] = {}
    for role, candidates in LICENSE_CANDIDATES.items():
        found = _first_existing(reference_root, candidates)
        license_files[role] = {
            "candidates": candidates,
            "found": found,
            "status": "found" if found else "evidence_missing",
        }

    tracked = _git_output(repo_root, ["ls-files"]).splitlines()
    direct_reference_children = [
        rel for rel in tracked if rel.startswith(f"{REFERENCE_PATH.as_posix()}/")
    ]

    return {
        "reference_exists": reference_root.exists(),
        "gitmodules_exists": gitmodules.exists(),
        "submodule_url": submodule_url,
        "gitlink_mode": gitlink_mode,
        "gitlink_commit": gitlink_commit,
        "actual_commit": actual_commit or None,
        "expected_commit": EXPECTED_COMMIT,
        "commit_matches_expected": actual_commit == EXPECTED_COMMIT,
        "submodule_status": submodule_status,
        "submodule_clean": submodule_dirty == "",
        "submodule_dirty_entries": submodule_dirty.splitlines() if submodule_dirty else [],
        "source_files": source_files,
        "core_files_found": all(item["exists"] for item in source_files.values()),
        "license_files": license_files,
        "license_status_checked": True,
        "gitlink_is_160000": gitlink_mode == "160000",
        "direct_reference_children_tracked": direct_reference_children,
        "uncontrolled_copied_source_tree": bool(direct_reference_children),
    }


def collect_pr21_status(repo_root: Path) -> dict[str, Any]:
    """Collect PR #21 and evidence branch status without modifying it.

    中文说明：PR #21 只作为失败证据读取；本函数不会 merge、close 或删除远程
    分支。
    """

    branch_ref = "refs/remotes/origin/stage/N4H4D-clean-replay-parity"
    branch_commit = _git_output(repo_root, ["rev-parse", "--verify", branch_ref])
    status: dict[str, Any] = {
        "evidence_branch": "origin/stage/N4H4D-clean-replay-parity",
        "evidence_branch_present": bool(branch_commit),
        "evidence_branch_commit": branch_commit or None,
        "pr_checked_with_gh": False,
        "pr_open": None,
        "pr_merged": None,
        "pr_url": None,
    }

    if shutil.which("gh"):
        completed = _run_gh(
            repo_root,
            [
                "pr",
                "view",
                "21",
                "--json",
                "number,state,mergedAt,url,headRefName,headRefOid",
            ],
        )
        if completed.returncode == 0:
            data = json.loads(completed.stdout)
            status.update(
                {
                    "pr_checked_with_gh": True,
                    "pr_open": data.get("state") == "OPEN",
                    "pr_merged": data.get("mergedAt") is not None,
                    "pr_url": data.get("url"),
                    "pr_head_ref": data.get("headRefName"),
                    "pr_head_oid": data.get("headRefOid"),
                }
            )
        else:
            status["gh_error"] = completed.stderr.strip() or completed.stdout.strip()

    return status


def make_readiness_report(
    reference_status: dict[str, Any],
    pr21_status: dict[str, Any],
) -> dict[str, Any]:
    """Build the N4H4R0 readiness report.

    中文说明：报告中的布尔值锁定 claim boundary；即使后续进入受控移植，
    final_v23 仍是 reference/backbone，不是 proposed novelty。
    """

    blockers: list[str] = []
    if not reference_status.get("reference_exists"):
        blockers.append("reference_submodule_missing")
    if not reference_status.get("gitlink_is_160000"):
        blockers.append("reference_gitlink_not_160000")
    if not reference_status.get("core_files_found"):
        blockers.append("core_source_files_missing")
    if reference_status.get("uncontrolled_copied_source_tree"):
        blockers.append("uncontrolled_reference_children_tracked")
    if not pr21_status.get("evidence_branch_present"):
        blockers.append("pr21_evidence_branch_missing")
    if pr21_status.get("pr_checked_with_gh") and not pr21_status.get("pr_open"):
        blockers.append("pr21_not_open")
    if pr21_status.get("pr_checked_with_gh") and pr21_status.get("pr_merged"):
        blockers.append("pr21_already_merged")

    return {
        "stage": "N4H4R0",
        "reference_status": reference_status,
        "pr21_status": pr21_status,
        "ready_for_N4H4R1": not blockers,
        "blockers": blockers,
        "final_v23_is_reference_not_proposed": True,
        "final_v23_output_solver_input": False,
        "trace_solver_input": False,
        "output_only_correction": False,
        "raw_data_committed": False,
        "performance_claim": False,
        "uncontrolled_copy_allowed": False,
    }

