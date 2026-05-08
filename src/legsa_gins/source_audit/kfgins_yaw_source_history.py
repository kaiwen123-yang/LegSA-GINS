"""Read-only KF-GINS yaw update source/history audit for N4H2C-runtime.

中文说明：本模块只在 external KF-GINS root 中执行 grep/log/show 级别的只读
审计；不 checkout、不 reset、不写入 source tree。
"""

from __future__ import annotations

from pathlib import Path
import re
import subprocess
from typing import Any


YAW_PATTERNS = [
    "gnssdata.yaw",
    "gnssdata.yaw_std",
    "H_gnssyaw",
    "R_gnssyaw",
    "yaw residual",
    "scheme_C",
    "heading_to_math",
    "90 -",
    "wrap",
    "euler[2]",
    "PHI_ID",
    "stateFeedback",
]


def _run_git(source_root: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=source_root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def _run_rg(source_root: Path, pattern: str) -> list[str]:
    completed = subprocess.run(
        ["rg", "-n", pattern],
        cwd=source_root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if completed.returncode not in {0, 1}:
        return []
    return [line for line in completed.stdout.splitlines() if line.strip()]


def _git_grep(source_root: Path, pattern: str) -> list[str]:
    completed = _run_git(source_root, ["grep", "-n", "-E", pattern])
    if completed.returncode not in {0, 1}:
        return []
    return [line for line in completed.stdout.splitlines() if line.strip()]


def _parse_grep_lines(lines: list[str]) -> list[dict[str, Any]]:
    parsed: list[dict[str, Any]] = []
    for line in lines:
        parts = line.split(":", 2)
        if len(parts) < 2:
            continue
        path = parts[0]
        line_number = parts[1]
        preview = parts[2].strip() if len(parts) > 2 else ""
        matched = [pattern for pattern in YAW_PATTERNS if pattern.lower().replace(" ", "") in preview.lower().replace(" ", "")]
        parsed.append(
            {
                "path": path,
                "line": int(line_number) if line_number.isdigit() else None,
                "matched_patterns": matched,
                "line_preview": preview[:180],
            }
        )
    return parsed


def _infer_residual_formula(matches: list[dict[str, Any]]) -> str:
    previews = "\n".join(str(item.get("line_preview", "")) for item in matches)
    lower = previews.lower()
    if "yaw_res" in lower and "yaw_obs" in lower and "yaw_pred" in lower:
        return "logged_yaw_residual_obs_pred"
    if "gnssdata.yaw" in lower and "euler" in lower and "wrap" in lower:
        return "wrapped_euler_minus_gnssdata_yaw_or_inverse"
    if "gnssdata.yaw" in lower:
        return "gnssdata_yaw_used_formula_needs_line_review"
    return "evidence_missing"


def _infer_transform(matches: list[dict[str, Any]]) -> str:
    previews = "\n".join(str(item.get("line_preview", "")) for item in matches)
    lower = previews.lower()
    if "90" in lower and "yaw" in lower:
        return "possible_90_minus_or_plus90_transform_in_source"
    if "heading_to_math" in lower:
        return "heading_to_math_keyword_present"
    if "gnssdata.yaw" in lower:
        return "direct_gnssdata_yaw_likely"
    return "evidence_missing"


def _infer_scheme_gate(matches: list[dict[str, Any]]) -> str:
    previews = "\n".join(str(item.get("line_preview", "")) for item in matches)
    lower = previews.lower()
    if "scheme_c" in lower and ("downweight" in lower or "rscale" in lower):
        return "scheme_C_downweight_or_gate_present"
    if "scheme_c" in lower:
        return "scheme_C_keyword_present"
    if "yaw-downweight" in lower:
        return "yaw_downweight_logging_present"
    return "evidence_missing"


def audit_current_yaw_update_source(source_root: str | Path) -> dict[str, Any]:
    """Read-only search for the current KF-GINS yaw update implementation."""

    root = Path(source_root)
    if not root.exists():
        return {
            "phase": "N4H2C-runtime",
            "evidence_status": "evidence_missing",
            "current_yaw_measurement_loaded": False,
            "current_yaw_update_enabled": False,
            "current_yaw_residual_formula": "evidence_missing",
            "current_yaw_measurement_transform": "evidence_missing",
            "current_scheme_C_gate": "evidence_missing",
            "source_paths_lines": [],
            "no_source_modification": True,
            "trace_solver_input": False,
            "output_only_correction": False,
            "solver_output_changed": False,
            "numerical_performance_claim": False,
        }

    grep_pattern = r"gnssdata\.yaw|yaw_std|H_gnssyaw|R_gnssyaw|scheme_C|heading_to_math|90\s*-|wrap|euler\[2\]|PHI_ID|stateFeedback|YAW-"
    lines = _git_grep(root, grep_pattern)
    if not lines:
        lines = _run_rg(root, grep_pattern)
    matches = _parse_grep_lines(lines)
    previews = "\n".join(str(item.get("line_preview", "")) for item in matches).lower()
    measurement_loaded = "gnssdata.yaw" in previews or "yaw_std" in previews
    update_enabled = any(token in previews for token in ["h_gnssyaw", "r_gnssyaw", "yaw-normal", "yaw-downweight"])
    return {
        "phase": "N4H2C-runtime",
        "evidence_status": "parsed" if matches else "evidence_missing",
        "current_yaw_measurement_loaded": measurement_loaded,
        "current_yaw_update_enabled": update_enabled,
        "current_yaw_residual_formula": _infer_residual_formula(matches),
        "current_yaw_measurement_transform": _infer_transform(matches),
        "current_scheme_C_gate": _infer_scheme_gate(matches),
        "source_paths_lines": matches[:80],
        "no_source_modification": True,
        "trace_solver_input": False,
        "output_only_correction": False,
        "solver_output_changed": False,
        "numerical_performance_claim": False,
    }


def _parse_commit_lines(text: str) -> list[dict[str, str]]:
    commits: list[dict[str, str]] = []
    for line in text.splitlines():
        match = re.match(r"^([0-9a-fA-F]{7,40})\s+(.*)$", line.strip())
        if not match:
            continue
        commits.append({"commit": match.group(1), "description": match.group(2)})
    return commits


def _extract_branches_from_log(text: str) -> list[str]:
    branches: set[str] = set()
    for item in re.findall(r"\((.*?)\)", text):
        for token in item.split(","):
            cleaned = token.strip()
            if cleaned.startswith("origin/") or cleaned.startswith("tag:"):
                branches.add(cleaned)
    return sorted(branches)


def search_yaw_update_history(source_root: str | Path) -> dict[str, Any]:
    """Run read-only git history searches for yaw update variants."""

    root = Path(source_root)
    if not root.exists():
        return {
            "phase": "N4H2C-runtime",
            "evidence_status": "evidence_missing",
            "candidate_commits": [],
            "candidate_branches": [],
            "evidence_of_yaw_transform_variants": False,
            "possible_source_version_mismatch": False,
            "no_source_modification": True,
            "trace_solver_input": False,
            "output_only_correction": False,
            "solver_output_changed": False,
            "numerical_performance_claim": False,
        }

    path_log = _run_git(
        root,
        [
            "log",
            "--all",
            "--oneline",
            "--decorate",
            "--",
            "src/kf-gins/gi_engine.cpp",
            "src/kf-gins/gi_engine.h",
            "src/fileio/fileloader.cpp",
            "src/fileio/fileloader.h",
            "bin/process_data.py",
        ],
    )
    grep_log = _run_git(
        root,
        [
            "log",
            "--all",
            "-G",
            r"gnssdata.*yaw|yaw_std|scheme_C|heading_to_math|90.*yaw|yaw.*90|YAW_INSTALL|yaw_source",
            "--oneline",
            "--decorate",
        ],
    )
    grep_current = _run_git(
        root,
        [
            "grep",
            "-n",
            "-E",
            r"gnssdata\.yaw|yaw_std|scheme_C|heading_to_math|90.*yaw|yaw.*90",
        ],
    )
    path_commits = _parse_commit_lines(path_log.stdout)
    grep_commits = _parse_commit_lines(grep_log.stdout)
    commit_by_hash: dict[str, dict[str, str]] = {item["commit"]: item for item in path_commits}
    for item in grep_commits:
        commit_by_hash.setdefault(item["commit"], item)
    candidate_commits = list(commit_by_hash.values())
    all_log_text = f"{path_log.stdout}\n{grep_log.stdout}\n{grep_current.stdout}"
    evidence_variants = any(token in all_log_text for token in ["heading_to_math", "90", "YAW_INSTALL", "yaw_source", "scheme_C"])
    possible_mismatch = bool(len(candidate_commits) > 1 and evidence_variants)
    return {
        "phase": "N4H2C-runtime",
        "evidence_status": "parsed",
        "path_log_returncode": path_log.returncode,
        "grep_log_returncode": grep_log.returncode,
        "git_grep_returncode": grep_current.returncode,
        "candidate_commits": candidate_commits[:80],
        "candidate_commit_count": len(candidate_commits),
        "candidate_branches": _extract_branches_from_log(all_log_text),
        "candidate_branch_count": len(_extract_branches_from_log(all_log_text)),
        "evidence_of_yaw_transform_variants": evidence_variants,
        "possible_source_version_mismatch": possible_mismatch,
        "git_grep_hit_count": len(grep_current.stdout.splitlines()) if grep_current.stdout else 0,
        "no_source_modification": True,
        "trace_solver_input": False,
        "output_only_correction": False,
        "solver_output_changed": False,
        "numerical_performance_claim": False,
    }
