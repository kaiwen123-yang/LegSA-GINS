"""Hash replay artifacts for N4H2G2 cache/staleness diagnostics.

中文说明：本模块只读取 runtime artifacts 的 metadata/hash，用于判断是否存在
缓存或 stale summary 风险；不提交 artifacts，不修改 solver output。
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any


def sha256_file(path: str | Path) -> str:
    """Return SHA-256 for a file without loading it all at once."""

    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def file_meta(path: str | Path) -> dict[str, Any]:
    """Return existence, size, mtime, and hash metadata."""

    item = Path(path)
    if not item.exists():
        return {"exists": False, "size_bytes": None, "mtime": None, "sha256": None}
    stat = item.stat()
    return {
        "exists": True,
        "size_bytes": stat.st_size,
        "mtime": stat.st_mtime,
        "sha256": sha256_file(item),
    }


def _first_existing(candidates: list[Path]) -> Path | None:
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def _locate(root: Path) -> dict[str, Path | None]:
    return {
        "input_gnss": _first_existing(
            [
                root / "CLEAN_STATUS_YAW.gnss",
                root / "input.gnss",
                root / "inputs" / "BY2_PROCESS_DATA_COMPAT.gnss",
                root / "_generation" / "BY2_PROCESS_DATA_COMPAT.gnss",
            ]
        ),
        "input_imu": _first_existing(
            [
                root / "CLEAN_STATUS_YAW.imu",
                root / "input.imu",
                root / "inputs" / "BY2_PROCESS_DATA_COMPAT.imu",
                root / "_generation" / "BY2_PROCESS_DATA_COMPAT.imu",
            ]
        ),
        "nav": _first_existing([root / "kfgins_output" / "KF_GINS_Navresult.nav", root / "replay" / "kfgins_output" / "KF_GINS_Navresult.nav", root / "KF_GINS_Navresult.nav"]),
        "std": _first_existing([root / "kfgins_output" / "KF_GINS_STD.txt", root / "replay" / "kfgins_output" / "KF_GINS_STD.txt", root / "KF_GINS_STD.txt"]),
        "imu_err": _first_existing([root / "kfgins_output" / "KF_GINS_IMU_ERR.txt", root / "replay" / "kfgins_output" / "KF_GINS_IMU_ERR.txt", root / "KF_GINS_IMU_ERR.txt"]),
        "summary": _first_existing(
            [
                root / "CLEAN_REPLAY_FRESH_SUMMARY.json",
                root / "CLEAN_REPLAY_SUMMARY.json",
                root / "FRESH_REPLAY_SUMMARY.json",
                root / "summary.json",
                root / "replay" / "evaluation" / "FINAL_V23_TRACE_EVAL_SUMMARY.json",
                root / "N4H2G_DECISION_REPORT.json",
            ]
        ),
        "error_series": _first_existing(
            [
                root / "CLEAN_REPLAY_FRESH_ERROR_SERIES.csv",
                root / "CLEAN_REPLAY_ERROR_SERIES.csv",
                root / "FRESH_REPLAY_ERROR_SERIES.csv",
                root / "error_series.csv",
                root / "replay" / "evaluation" / "FINAL_V23_TRACE_ERROR_SERIES.csv",
            ]
        ),
    }


def hash_replay_artifacts(root: str | Path, role: str) -> dict[str, Any]:
    """Hash known replay/input artifacts under a role root."""

    base = Path(root)
    located = _locate(base)
    file_hashes: dict[str, Any] = {}
    missing: list[str] = []
    for name, path in located.items():
        if path is None:
            file_hashes[name] = {"path_role": None, **file_meta(base / f"__missing_{name}__")}
            if name in {"input_gnss", "nav", "summary"}:
                missing.append(name)
            continue
        file_hashes[name] = {"path_role": name, **file_meta(path)}
    return {
        "phase": "N4H2G2",
        "role": role,
        "root_exists": base.exists(),
        "file_hashes": file_hashes,
        "evidence_status": "hashed" if base.exists() and not missing else "evidence_missing",
        "evidence_missing": missing,
        "trace_solver_input": False,
        "output_only_correction": False,
        "solver_output_changed": False,
        "numerical_performance_claim": False,
    }


def _hash(report: dict[str, Any], key: str) -> str | None:
    return ((report.get("file_hashes") or {}).get(key) or {}).get("sha256")


def _mtime(report: dict[str, Any], key: str) -> float | None:
    return ((report.get("file_hashes") or {}).get(key) or {}).get("mtime")


def compare_artifact_hashes(
    clean_hashes: dict[str, Any],
    noisy_hashes: dict[str, Any],
    *,
    clean_run_start_time: float | None = None,
) -> dict[str, Any]:
    """Compare clean/noisy hash reports and flag possible cache/stale risks."""

    exact_matches: list[str] = []
    for key in ["input_gnss", "input_imu", "nav", "std", "imu_err", "summary", "error_series"]:
        clean = _hash(clean_hashes, key)
        noisy = _hash(noisy_hashes, key)
        if clean and noisy and clean == noisy:
            exact_matches.append(key)

    clean_input_differs = bool(_hash(clean_hashes, "input_gnss") and _hash(noisy_hashes, "input_gnss") and _hash(clean_hashes, "input_gnss") != _hash(noisy_hashes, "input_gnss"))
    clean_nav_differs = bool(_hash(clean_hashes, "nav") and _hash(noisy_hashes, "nav") and _hash(clean_hashes, "nav") != _hash(noisy_hashes, "nav"))
    clean_summary_differs = bool(_hash(clean_hashes, "summary") and _hash(noisy_hashes, "summary") and _hash(clean_hashes, "summary") != _hash(noisy_hashes, "summary"))

    stale_output_files: list[str] = []
    if clean_run_start_time is not None:
        for key in ["nav", "std", "imu_err", "summary", "error_series"]:
            mtime = _mtime(clean_hashes, key)
            if isinstance(mtime, (int, float)) and mtime < clean_run_start_time:
                stale_output_files.append(key)

    possible_yaw_ignored_or_reused = bool(clean_input_differs and not clean_nav_differs and _hash(clean_hashes, "nav") and _hash(noisy_hashes, "nav"))
    possible_stale_summary = bool(
        _hash(clean_hashes, "summary")
        and _hash(noisy_hashes, "summary")
        and _hash(clean_hashes, "summary") == _hash(noisy_hashes, "summary")
        and clean_nav_differs
    )
    stale_output = bool(stale_output_files)
    return {
        "phase": "N4H2G2",
        "clean_role": clean_hashes.get("role"),
        "noisy_role": noisy_hashes.get("role"),
        "clean_input_differs_from_noisy_input": clean_input_differs,
        "clean_nav_differs_from_noisy_nav": clean_nav_differs,
        "clean_summary_differs_from_noisy_summary": clean_summary_differs,
        "exact_hash_matches": exact_matches,
        "possible_reused_artifact": bool(possible_yaw_ignored_or_reused or stale_output),
        "possible_yaw_input_ignored_or_output_reused": possible_yaw_ignored_or_reused,
        "possible_stale_summary": possible_stale_summary,
        "stale_output": stale_output,
        "stale_output_files": stale_output_files,
        "evidence_status": "compared",
        "trace_solver_input": False,
        "output_only_correction": False,
        "solver_output_changed": False,
        "numerical_performance_claim": False,
    }
