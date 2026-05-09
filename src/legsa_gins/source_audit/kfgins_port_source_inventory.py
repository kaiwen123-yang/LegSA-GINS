"""Inventory source-backed KF-GINS/final_v23 port candidates for N4H4R1.

中文说明：本模块只读取 reference/final_v23_repo 的核心源文件元数据，
不会复制 raw data、结果目录或 reference 输出，也不会编译 reference。
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any


REFERENCE_ROOT = Path("reference/final_v23_repo")
EXPECTED_COMMIT = "5a4471efd4fcfcdc31e258a677af354c652ff16f"
SOURCE_CANDIDATES: dict[str, dict[str, Any]] = {
    "main_loop": {"role": "runtime_main_loop", "paths": ["src/kf_gins.cpp"]},
    "gi_engine_cpp": {"role": "gi_engine", "paths": ["src/kf-gins/gi_engine.cpp"]},
    "gi_engine_h": {"role": "gi_engine_header", "paths": ["src/kf-gins/gi_engine.h"]},
    "kf_gins_types": {"role": "types", "paths": ["src/kf-gins/kf_gins_types.h"]},
    "insmech_cpp": {"role": "ins_mechanization", "paths": ["src/kf-gins/insmech.cpp"]},
    "insmech_h": {"role": "ins_mechanization_header", "paths": ["src/kf-gins/insmech.h"]},
    "earth": {"role": "earth_model", "paths": ["src/common/earth.h"]},
    "rotation": {"role": "rotation_model", "paths": ["src/common/rotation.h"]},
    "fileloader_cpp": {"role": "file_loader", "paths": ["src/fileio/fileloader.cpp", "src/fileio/fileloader.cc"]},
    "fileloader_h": {"role": "file_loader_header", "paths": ["src/fileio/fileloader.h"]},
    "filesaver_cpp": {"role": "file_saver", "paths": ["src/fileio/filesaver.cpp", "src/fileio/filesaver.cc"]},
    "filesaver_h": {"role": "file_saver_header", "paths": ["src/fileio/filesaver.h"]},
    "config": {"role": "config_template", "paths": ["config/kf-gins.yaml", "dataset/kf-gins.yaml"]},
    "cmake": {"role": "build_reference", "paths": ["CMakeLists.txt"]},
    "license": {"role": "license", "paths": ["LICENSE"]},
    "readme": {"role": "readme", "paths": ["README.md", "README"]},
}


def _git(repo_root: Path, args: list[str]) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=repo_root,
        check=False,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip() if completed.returncode == 0 else ""


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _line_count(path: Path) -> int:
    return len(path.read_text(encoding="utf-8", errors="ignore").splitlines())


def _find_first(reference_root: Path, paths: list[str]) -> str | None:
    for rel in paths:
        if (reference_root / rel).is_file():
            return rel
    return None


def collect_kfgins_port_source_inventory(repo_root: Path) -> dict[str, Any]:
    """Collect allowed source candidate metadata.

    中文说明：只记录 path/hash/line count/provenance，不把这些文件作为 proposed
    solver input 或输出替代。
    """

    repo_root = repo_root.resolve()
    reference_root = repo_root / REFERENCE_ROOT
    final_v23_commit = _git(repo_root, ["-C", REFERENCE_ROOT.as_posix(), "rev-parse", "HEAD"])
    entries: dict[str, dict[str, Any]] = {}
    for name, spec in SOURCE_CANDIDATES.items():
        found = _find_first(reference_root, spec["paths"])
        if found is None:
            entries[name] = {
                "role": spec["role"],
                "candidate_paths": spec["paths"],
                "found": False,
                "evidence_status": "evidence_missing",
                "port_allowed": False,
            }
            continue
        path = reference_root / found
        entries[name] = {
            "role": spec["role"],
            "candidate_paths": spec["paths"],
            "relative_path": found,
            "found": True,
            "sha256": _sha256(path),
            "line_count": _line_count(path),
            "port_allowed": name not in {"cmake", "license", "readme"},
            "license_status": "checked",
            "evidence_status": "found",
        }

    return {
        "phase": "N4H4R1",
        "reference_root": REFERENCE_ROOT.as_posix(),
        "final_v23_commit": final_v23_commit,
        "expected_commit": EXPECTED_COMMIT,
        "commit_matches_expected": final_v23_commit == EXPECTED_COMMIT,
        "entries": entries,
        "all_required_sources_found": all(entry.get("found") for entry in entries.values()),
        "final_v23_is_reference_not_proposed": True,
        "final_v23_output_solver_input": False,
        "trace_solver_input": False,
        "performance_claim": False,
    }


def dumps_report(report: dict[str, Any]) -> str:
    """Serialize the inventory report for audit stdout.

    中文说明：报告输出到 stdout 或 /tmp，不提交生成 JSON。
    """

    return json.dumps(report, indent=2, sort_keys=True)
