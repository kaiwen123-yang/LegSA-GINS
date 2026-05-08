"""Recover dual_final_v23 artifact candidates without copying artifacts.

中文说明：本模块只在 runtime 搜索候选 artifact；tracked docs 只能写 role alias，
不能提交真实 input/nav/std/summary/error_series，也不能提交本地绝对路径。
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
    "summary.json",
    "error_series.csv",
    "case_review.md",
}

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
    "builds",
    "cmake-build-debug",
    "cmake-build-release",
    "node_modules",
    "ThirdParty",
    "third_party",
    "vendor",
}

MAX_SUMMARY_BYTES = 2_000_000
MAX_REVIEW_BYTES = 2_000_000
WINDOWS_USERS_PREFIX = str(Path("/mnt") / "c" / "Users") + "/"


def _flatten(prefix: str, value: Any, out: dict[str, Any]) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            _flatten(f"{prefix}.{key}" if prefix else str(key), item, out)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _flatten(f"{prefix}.{index}" if prefix else str(index), item, out)
    else:
        out[prefix] = value


def _summary_metrics(path: Path | None) -> dict[str, float]:
    if path is None or not path.exists() or path.stat().st_size > MAX_SUMMARY_BYTES:
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    flat: dict[str, Any] = {}
    _flatten("", data, flat)
    metrics: dict[str, float] = {}
    for target in SUMMARY_KEYS:
        for key, value in flat.items():
            if target in key and isinstance(value, (int, float)) and not isinstance(value, bool):
                metrics[target] = float(value)
                break
    return metrics


def _line_count(path: Path | None) -> int | None:
    if path is None or not path.exists() or not path.is_file():
        return None
    try:
        with path.open("r", encoding="utf-8", errors="ignore") as handle:
            return sum(1 for _ in handle)
    except OSError:
        return None


def _review_mentions_dual(path: Path | None) -> bool:
    if path is None or not path.exists() or path.stat().st_size > MAX_REVIEW_BYTES:
        return False
    try:
        with path.open("r", encoding="utf-8", errors="ignore") as handle:
            for line in handle:
                lower = line.lower()
                if "dual_final_v23" in lower or ("dual" in lower and "final_v23" in lower):
                    return True
    except OSError:
        return False
    return False


def _depth(root: Path, current: Path) -> int:
    try:
        return len(current.relative_to(root).parts)
    except ValueError:
        return 999


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
    root_text = str(root).replace(os.sep, "/")
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
                "tmp",
            ]
        )
    if root_text.startswith(WINDOWS_USERS_PREFIX):
        return lower in {"desktop", "documents", "downloads"} or any(
            token in lower for token in ["final", "extended", "degradation", "毕业", "毕设", "artifact", "数据"]
        )
    return True


def _should_keep_nested_dir(root: Path, current: Path, name: str) -> bool:
    root_text = str(root).replace(os.sep, "/")
    if not root_text.startswith(WINDOWS_USERS_PREFIX):
        return True
    depth = _depth(root, current)
    lower = name.lower()
    if depth <= 1:
        tokens = ["final", "v23", "dual", "single", "extended", "degradation", "毕业", "毕设", "数据", "artifact"]
    else:
        tokens = [
            "final",
            "v23",
            "dual",
            "single",
            "e001",
            "nominal",
            "extended",
            "degradation",
            "results",
            "case",
            "review",
            "artifact",
        ]
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
            kept = [name for name in kept if _should_keep_nested_dir(root, current, name)]
        dirnames[:] = kept
        for filename in filenames:
            if filename in ARTIFACT_NAMES:
                candidates.append(current / filename)
    return candidates


def _around(value: float | None, target: float, width: float) -> bool:
    return value is not None and abs(value - target) <= width


def _metric_score(metrics: dict[str, float]) -> tuple[int, list[str]]:
    score = 0
    notes: list[str] = []
    horizontal = metrics.get("horizontal_rmse_m")
    yaw = metrics.get("yaw_rmse_deg")
    if horizontal is not None and 0.25 <= horizontal <= 0.50:
        score += 5
        notes.append("dual_horizontal_window")
    if yaw is not None and 1.0 <= yaw <= 3.0:
        score += 5
        notes.append("dual_yaw_window")
    if _around(horizontal, 38.0, 5.0) or _around(yaw, 41.0, 5.0):
        score -= 5
        notes.append("single_antenna_like_penalty")
    return score, notes


def _path_score(directory: Path) -> tuple[int, list[str]]:
    text = str(directory).replace(os.sep, "/").lower()
    score = 0
    notes: list[str] = []
    if "final_v23" in text:
        score += 3
        notes.append("final_v23_path")
    if "dual" in text:
        score += 3
        notes.append("dual_path")
    if "e001_single_nominal_none" in text:
        score += 2
        notes.append("e001_single_nominal_none_path")
    if "extended_degradation_results" in text:
        score += 2
        notes.append("extended_degradation_results_path")
    if "single_antenna_compare" in text or "tmp_single_antenna_compare" in text:
        score -= 4
        notes.append("single_antenna_compare_penalty")
    if "pure_ins" in text:
        score -= 8
        notes.append("pure_ins_penalty")
    return score, notes


def _group_score(directory: Path, files: dict[str, Path]) -> dict[str, Any]:
    metrics = _summary_metrics(files.get("summary.json"))
    score, notes = _metric_score(metrics)
    path_bonus, path_notes = _path_score(directory)
    score += path_bonus
    notes.extend(path_notes)
    artifact_score = 0
    for name in ["input.gnss", "KF_GINS_Navresult.nav", "KF_GINS_STD.txt", "error_series.csv", "summary.json"]:
        if name in files:
            artifact_score += 2
            notes.append(f"has_{name}")
    score += artifact_score
    review_dual = _review_mentions_dual(files.get("case_review.md"))
    if review_dual:
        score += 2
        notes.append("case_review_mentions_dual_final_v23")
    return {
        "score": score,
        "candidate_rank_evidence": notes,
        "summary_metrics": metrics,
        "case_review_mentions_dual_final_v23": review_dual,
        "contains_input_gnss": "input.gnss" in files,
        "contains_nav": "KF_GINS_Navresult.nav" in files,
        "contains_std": "KF_GINS_STD.txt" in files,
        "contains_summary": "summary.json" in files,
        "contains_error_series": "error_series.csv" in files,
        "contains_case_review": "case_review.md" in files,
        "line_counts": {
            "input_gnss": _line_count(files.get("input.gnss")),
            "nav": _line_count(files.get("KF_GINS_Navresult.nav")),
            "std": _line_count(files.get("KF_GINS_STD.txt")),
        },
    }


def _has_dual_metrics(group: dict[str, Any]) -> bool:
    metrics = group.get("summary_metrics") or {}
    horizontal = metrics.get("horizontal_rmse_m")
    yaw = metrics.get("yaw_rmse_deg")
    return isinstance(horizontal, (int, float)) and isinstance(yaw, (int, float)) and 0.25 <= horizontal <= 0.50 and 1.0 <= yaw <= 3.0


def recover_dual_final_v23_artifacts(search_roots: Any, *, max_depth: int = 9) -> dict[str, Any]:
    """Search roots for dual_final_v23-like artifact groups.

    Runtime reports include full paths. Tracked reports should summarize only
    role aliases, metrics, and evidence status.
    """

    groups: list[dict[str, Any]] = []
    seen_roots: set[str] = set()
    for root_role, root in _as_role_roots(search_roots):
        try:
            resolved_root = str(root.resolve())
        except OSError:
            resolved_root = str(root)
        if resolved_root in seen_roots:
            continue
        seen_roots.add(resolved_root)
        by_dir: dict[Path, dict[str, Path]] = {}
        for path in _walk_candidates(root, max_depth=max_depth):
            by_dir.setdefault(path.parent, {})[path.name] = path
        for index, (directory, files) in enumerate(sorted(by_dir.items(), key=lambda item: str(item[0]))):
            status = _group_score(directory, files)
            group = {
                "group_id": f"{root_role}:{index}",
                "role_alias": f"DUAL_FINAL_V23_CANDIDATE:{len(groups)}",
                "root_role": root_role,
                "directory": str(directory),
                "artifacts": {name: str(path) for name, path in sorted(files.items())},
                **status,
            }
            if _has_dual_metrics(group):
                group["evidence_status"] = "candidate_dual_final_v23_artifact_group"
            elif group.get("contains_summary"):
                group["evidence_status"] = "summary_not_dual_final_v23_metric_window"
            else:
                group["evidence_status"] = "partial_dual_final_v23_artifact_candidate"
            groups.append(group)

    groups.sort(key=lambda item: (-int(item.get("score", 0)), item.get("root_role", ""), item.get("directory", "")))
    best = groups[0] if groups else None
    found = bool(best and _has_dual_metrics(best) and best.get("contains_nav") and best.get("contains_summary"))
    evidence_status = (
        "dual_final_v23_artifact_candidate_found"
        if found
        else "dual_artifact_missing"
        if not groups
        else "dual_final_v23_artifact_not_confirmed"
    )
    return {
        "phase": "N4R2",
        "candidate_groups": groups,
        "candidate_group_count": len(groups),
        "best_dual_candidate_group": best,
        "dual_artifact_found": found,
        "dual_input_recovered": bool(best and best.get("contains_input_gnss")),
        "dual_nav_recovered": bool(best and best.get("contains_nav")),
        "dual_summary_recovered": bool(best and best.get("contains_summary")),
        "dual_error_series_recovered": bool(best and best.get("contains_error_series")),
        "best_dual_summary_metrics": (best or {}).get("summary_metrics", {}),
        "evidence_status": evidence_status,
        "copied_external_source": False,
        "raw_data_committed": False,
        "solver_input_modified": False,
        "solver_output_changed": False,
        "evaluator_only": True,
        "trace_solver_input": False,
        "output_only_correction": False,
        "numerical_performance_claim": False,
    }
