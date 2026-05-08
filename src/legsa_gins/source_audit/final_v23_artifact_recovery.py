"""Recover final_v23 artifact groups without copying artifacts.

中文说明：本模块只在 runtime 搜索候选 artifact 并写 /tmp report；tracked docs
只能写 role alias，不能提交真实 input/nav/std/summary 或本地绝对路径。
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


ARTIFACT_NAMES = {
    "input.gnss",
    "KF_GINS_Navresult.nav",
    "KF_GINS_STD.txt",
    "KF_GINS_IMU_ERR.txt",
    "summary.json",
    "error_series.csv",
    "case_review.md",
    "process_data_yaw_install_calibration.md",
    "process_data_dynamic_yaw_std_v22_check.md",
}

DIR_KEYWORDS = [
    "final_v23",
    "E001_single_nominal_none",
    "nominal_none",
    "extended_degradation_results",
    "tmp_single_antenna_compare",
    "runs/nominal_none",
]

SUMMARY_KEYS = [
    "horizontal_rmse_m",
    "up_rmse_m",
    "yaw_rmse_deg",
    "roll_rmse_deg",
    "pitch_rmse_deg",
]

SKIP_DIRS = {
    ".git",
    ".cache",
    ".cargo",
    ".codex",
    ".local",
    ".npm",
    ".rustup",
    ".vscode-server",
    "__pycache__",
    ".pytest_cache",
    "build",
    "cmake-build-debug",
    "cmake-build-release",
    "node_modules",
    "ThirdParty",
    "third_party",
    "vendor",
}

MAX_SUMMARY_BYTES = 2_000_000


def _depth(root: Path, current: Path) -> int:
    try:
        return len(current.relative_to(root).parts)
    except ValueError:
        return 999


def _line_count(path: Path) -> int | None:
    if not path.exists() or not path.is_file():
        return None
    try:
        with path.open("r", encoding="utf-8", errors="ignore") as handle:
            return sum(1 for _ in handle)
    except OSError:
        return None


def _flatten(prefix: str, value: Any, out: dict[str, Any]) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            _flatten(f"{prefix}.{key}" if prefix else str(key), item, out)
    else:
        out[prefix] = value


def _summary_metrics(path: Path) -> dict[str, Any]:
    if not path.exists() or path.stat().st_size > MAX_SUMMARY_BYTES:
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    flat: dict[str, Any] = {}
    _flatten("", data, flat)
    metrics: dict[str, Any] = {}
    for target in SUMMARY_KEYS:
        for key, value in flat.items():
            if target in key and isinstance(value, (int, float)) and not isinstance(value, bool):
                metrics[target] = float(value)
                break
    return metrics


def _as_role_roots(search_roots: Any) -> list[tuple[str, Path]]:
    if isinstance(search_roots, dict):
        return [(str(role), Path(path)) for role, path in search_roots.items()]
    roots: list[tuple[str, Path]] = []
    for index, item in enumerate(search_roots):
        if isinstance(item, (tuple, list)) and len(item) == 2:
            roots.append((str(item[0]), Path(item[1])))
        else:
            roots.append((f"SEARCH_ROOT_{index}", Path(item)))
    return roots


def _should_keep_top_dir(root: Path, name: str) -> bool:
    lower = name.lower()
    if root == Path.home():
        return any(
            token in lower
            for token in [
                "kf-gins",
                "legsa",
                "final",
                "extended",
                "degradation",
                "artifact",
                "tmp_single",
            ]
        )
    if root.parts[-3:] == ("mnt", "c", "Users") or str(root).replace(os.sep, "/").endswith("/mnt/c/Users"):
        return True
    if str(root).replace(os.sep, "/").startswith("/mnt/c/Users/"):
        return lower in {"desktop", "documents", "downloads"} or any(
            token in lower for token in ["final", "extended", "degradation", "毕业", "artifact"]
        )
    return True


def _should_keep_windows_nested_dir(root: Path, current: Path, name: str) -> bool:
    root_text = str(root).replace(os.sep, "/")
    if not root_text.startswith("/mnt/c/Users/"):
        return True
    depth = _depth(root, current)
    if depth == 0:
        return True
    lower = name.lower()
    if depth == 1:
        tokens = ["final", "v23", "extended", "degradation", "毕业", "毕设", "artifact"]
    elif depth == 2:
        tokens = ["final", "v23", "extended", "degradation", "nominal", "毕设", "数据", "artifact"]
    else:
        tokens = ["final", "v23", "extended", "degradation", "nominal", "runs", "results", "single", "artifact"]
    return any(token in lower for token in tokens)


def _walk_candidates(root: Path, *, max_depth: int) -> list[Path]:
    if not root.exists():
        return []
    candidates: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root):
        current = Path(dirpath)
        depth = _depth(root, current)
        if depth >= max_depth:
            dirnames[:] = []
        kept = [name for name in dirnames if name not in SKIP_DIRS]
        if depth == 0:
            kept = [name for name in kept if _should_keep_top_dir(root, name)]
        else:
            kept = [name for name in kept if _should_keep_windows_nested_dir(root, current, name)]
        dirnames[:] = kept
        rel_text = str(current.relative_to(root)).replace(os.sep, "/") if current != root else ""
        keyword_dir = any(keyword in rel_text for keyword in DIR_KEYWORDS)
        for filename in filenames:
            if filename in ARTIFACT_NAMES or keyword_dir:
                if filename in ARTIFACT_NAMES:
                    candidates.append(current / filename)
    return candidates


def _group_status(files: dict[str, Path]) -> dict[str, Any]:
    summary_path = files.get("summary.json")
    input_path = files.get("input.gnss")
    nav_path = files.get("KF_GINS_Navresult.nav")
    std_path = files.get("KF_GINS_STD.txt")
    contains_input = input_path is not None
    contains_nav = nav_path is not None
    contains_std = std_path is not None
    contains_summary = summary_path is not None
    contains_error = "error_series.csv" in files
    contains_review = "case_review.md" in files
    score = sum(
        [
            3 if contains_input else 0,
            2 if contains_nav else 0,
            2 if contains_std else 0,
            2 if contains_summary else 0,
            1 if contains_error else 0,
            1 if contains_review else 0,
        ]
    )
    if contains_input and (contains_nav or contains_std or contains_summary):
        status = "candidate_final_v23_artifact_group"
    elif contains_input:
        status = "input_only_candidate"
    elif contains_nav or contains_std or contains_summary:
        status = "partial_artifact_group"
    else:
        status = "evidence_missing"
    return {
        "contains_input_gnss": contains_input,
        "contains_nav": contains_nav,
        "contains_std": contains_std,
        "contains_summary": contains_summary,
        "contains_error_series": contains_error,
        "contains_case_review": contains_review,
        "summary_metrics": _summary_metrics(summary_path) if summary_path else {},
        "line_counts": {
            "input_gnss": _line_count(input_path) if input_path else None,
            "nav": _line_count(nav_path) if nav_path else None,
            "std": _line_count(std_path) if std_path else None,
        },
        "score": score,
        "evidence_status": status,
    }


def _candidate_rank_bonus(directory: Path) -> tuple[int, list[str]]:
    text = str(directory).replace(os.sep, "/").lower()
    bonus = 0
    notes: list[str] = []
    if "final_v23" in text:
        bonus += 5
        notes.append("final_v23_path")
    if "e001_single_nominal_none" in text:
        bonus += 5
        notes.append("e001_single_nominal_none_path")
    if "runs/nominal_none" in text or "nominal_none" in text:
        bonus += 4
        notes.append("nominal_none_path")
    if "extended_degradation_results" in text:
        bonus += 2
        notes.append("extended_degradation_results_path")
    if "pure_ins" in text:
        bonus -= 6
        notes.append("pure_ins_reference_penalty")
    if "single" in text:
        bonus += 1
        notes.append("single_case_path")
    return bonus, notes


def recover_final_v23_artifacts(search_roots: Any, *, max_depth: int = 6) -> dict[str, Any]:
    """Search roots for final_v23-like artifact groups.

    Runtime reports include full paths. Tracked docs should summarize only the role and group ids.
    """

    groups: list[dict[str, Any]] = []
    for root_role, root in _as_role_roots(search_roots):
        by_dir: dict[Path, dict[str, Path]] = {}
        for path in _walk_candidates(root, max_depth=max_depth):
            by_dir.setdefault(path.parent, {})[path.name] = path
        for index, (directory, files) in enumerate(sorted(by_dir.items(), key=lambda item: str(item[0]))):
            status = _group_status(files)
            bonus, notes = _candidate_rank_bonus(directory)
            status["score"] = int(status.get("score", 0)) + bonus
            status["candidate_rank_evidence"] = notes
            group = {
                "group_id": f"{root_role}:{index}",
                "root_role": root_role,
                "directory": str(directory),
                "artifacts": {name: str(path) for name, path in sorted(files.items())},
                **status,
            }
            groups.append(group)
    groups.sort(key=lambda item: (-int(item.get("score", 0)), item.get("root_role", ""), item.get("directory", "")))
    best = groups[0] if groups else None
    return {
        "artifact_groups_found": len(groups),
        "groups": groups,
        "best_final_v23_candidate_group": best,
        "actual_input_gnss_recovered": bool(best and best.get("contains_input_gnss")),
        "actual_summary_recovered": bool(best and best.get("contains_summary")),
        "evidence_status": "artifact_candidates_found" if groups else "evidence_missing",
        "raw_data_committed": False,
        "copied_external_source": False,
        "trace_solver_input": False,
        "numerical_performance_claim": False,
    }
