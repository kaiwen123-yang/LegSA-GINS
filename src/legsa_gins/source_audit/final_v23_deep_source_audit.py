"""Deep read-only audit helpers for final_v23 / KF-GINS parity.

中文说明：本模块只做 runtime input 与外部源码的只读证据定位；它不复制外部源码、
不执行调参、不使用 trace 作为 solver input，也不构成性能结论。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any


FINAL_V23_CASE_FILES = [
    "input.gnss",
    "KF_GINS_Navresult.nav",
    "KF_GINS_STD.txt",
    "summary.json",
    "error_series.csv",
]

PROCESS_DATA_KEYWORDS = [
    "process_data.py",
    "final_status_fixed",
    "final_status_fixed1p5",
    "E001_single_nominal_none",
    "extended_degradation_results",
    "status_yaw",
    "trace_yaw",
    "generate_both_gnss",
    "yaw_source_mode",
    "yaw_std_mode",
    "status_yaw_std_mode",
    "fixed_1p5",
    "v22_dynamic",
    "suspicious_only",
    "YAW_SIGN",
    "YAW_INSTALL_OFFSET_DEG",
    "AUTO_APPLY_BEST_INSTALL",
    "enable_outage",
    "outlier_mode",
    "yaw_noise_std_deg",
    "imu_install_roll_deg",
    "imu_gnss_time_offset",
    "antlever",
    "initatt",
    "imunoise",
]

GNSS_ENGINE_KEYWORDS = [
    "GnssFileLoader",
    "gnssfileloader",
    "GNSS struct",
    "gnssdata.blh",
    "gnssdata.std",
    "gnssdata.vel",
    "gnssdata.vel_std",
    "gnssdata.yaw",
    "gnssdata.yaw_std",
    "gnssUpdate",
    "yaw update",
    "velocity update",
    "H_gnssvel",
    "H_gnssyaw",
    "scheme_C",
    "EKFUpdate",
    "stateFeedback",
]

CORE_FLOW_TERMS = {
    "kf_gins.cpp main": ["kf_gins.cpp", "int main"],
    "loadConfig": ["loadConfig"],
    "addImuData": ["addImuData"],
    "addGnssData": ["addGnssData"],
    "newImuProcess": ["newImuProcess"],
    "isToUpdate": ["isToUpdate"],
    "imuInterpolate": ["imuInterpolate"],
    "imuCompensate": ["imuCompensate"],
    "insPropagation": ["insPropagation"],
    "F/G/Phi/Qd construction": ["Phi", "Qd", "F_", "G_"],
    "EKFPredict": ["EKFPredict"],
    "EKFUpdate": ["EKFUpdate"],
    "gnssUpdate": ["gnssUpdate"],
    "stateFeedback": ["stateFeedback"],
    "INSMech::insMech": ["INSMech::insMech", "insMech"],
    "velUpdate": ["velUpdate"],
    "posUpdate": ["posUpdate"],
    "attUpdate": ["attUpdate"],
}

TEXT_SUFFIXES = {
    ".py",
    ".sh",
    ".bash",
    ".cpp",
    ".cc",
    ".cxx",
    ".c",
    ".h",
    ".hpp",
    ".hh",
    ".yaml",
    ".yml",
    ".json",
    ".txt",
    ".md",
    ".cmake",
    ".cfg",
    ".conf",
    ".ini",
}

SKIP_PARTS = {
    ".git",
    "__pycache__",
    ".pytest_cache",
    "build",
    "cmake-build-debug",
    "cmake-build-release",
    "artifacts",
    "extended_degradation_results",
    "log",
    "logs",
    "output",
    "outputs",
    "result",
    "results",
    "third_party",
    "vendor",
}

MAX_TEXT_FILE_BYTES = 2_000_000


def _iter_text_files(root: Path) -> list[Path]:
    if not root.exists():
        return []
    files: list[Path] = []
    for path in root.rglob("*"):
        if any(part in SKIP_PARTS for part in path.parts):
            continue
        if (
            path.is_file()
            and path.suffix.lower() in TEXT_SUFFIXES
            and path.stat().st_size <= MAX_TEXT_FILE_BYTES
        ):
            files.append(path)
    return sorted(files)


def _safe_line_count(path: Path) -> int | None:
    try:
        with path.open("r", encoding="utf-8", errors="ignore") as handle:
            return sum(1 for _ in handle)
    except OSError:
        return None


def _file_probe(path: Path) -> dict[str, Any]:
    exists = path.exists()
    return {
        "exists": exists,
        "size_bytes": path.stat().st_size if exists and path.is_file() else None,
        "line_count": _safe_line_count(path) if exists and path.is_file() else None,
    }


def _path_summary(path: Path, root: Path | None = None) -> str:
    try:
        return str(path.relative_to(root)) if root else path.name
    except ValueError:
        return path.name


def _search_keywords(
    root: Path,
    keywords: list[str],
    *,
    per_keyword_limit: int = 40,
) -> tuple[list[dict[str, Any]], dict[str, bool]]:
    hits: list[dict[str, Any]] = []
    found = {keyword: False for keyword in keywords}
    counts = {keyword: 0 for keyword in keywords}
    for path in _iter_text_files(root):
        try:
            lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
        except OSError:
            continue
        for line_number, line in enumerate(lines, start=1):
            for keyword in keywords:
                if counts[keyword] >= per_keyword_limit:
                    continue
                if keyword == "process_data.py":
                    if path.name != "process_data.py" and keyword not in line:
                        continue
                elif keyword not in line:
                    continue
                found[keyword] = True
                counts[keyword] += 1
                hits.append(
                    {
                        "path": str(path),
                        "line": line_number,
                        "keyword": keyword,
                        "summary": f"{keyword} evidence observed near {_path_summary(path, root)}:{line_number}",
                    }
                )
    return hits, found


def _candidate_paths(root: Path, suffixes: set[str], name_tokens: list[str]) -> list[str]:
    candidates: list[str] = []
    for path in _iter_text_files(root):
        lower = path.name.lower()
        if path.suffix.lower() not in suffixes:
            continue
        if any(token in lower for token in name_tokens):
            candidates.append(str(path))
    return sorted(set(candidates))


def probe_final_v23_case_root(case_root: str | Path) -> dict[str, Any]:
    """Probe actual final_v23 nominal case artifacts without reading them as solver input."""

    root = Path(case_root)
    files = {name: _file_probe(root / name) for name in FINAL_V23_CASE_FILES}
    all_required = all(files[name]["exists"] for name in FINAL_V23_CASE_FILES)
    any_required = any(files[name]["exists"] for name in FINAL_V23_CASE_FILES)
    if all_required:
        status = "complete_case_root_probe"
    elif any_required:
        status = "partial_case_root_probe"
    else:
        status = "evidence_missing"
    return {
        "case_root_exists": root.exists(),
        "files": files,
        "actual_input_gnss_exists": files["input.gnss"]["exists"],
        "evidence_status": status,
        "trace_solver_input": False,
        "final_v23_is_proposed": False,
        "numerical_performance_claim": False,
    }


def search_process_data_and_run_scripts(source_root: str | Path) -> dict[str, Any]:
    """Search process_data and runtime/config scripts by keyword, read-only."""

    root = Path(source_root)
    process_data_candidates: list[str] = []
    direct_process_data = root / "bin" / "process_data.py"
    if direct_process_data.exists():
        process_data_candidates.append(str(direct_process_data))
    else:
        process_data_candidates = [
            str(path) for path in _iter_text_files(root) if path.name == "process_data.py"
        ]
    hits, found = _search_keywords(root, PROCESS_DATA_KEYWORDS)
    run_scripts = _candidate_paths(
        root,
        {".py", ".sh", ".bash"},
        ["run", "replay", "process", "final", "v23", "batch", "case"],
    )
    config_candidates = _candidate_paths(
        root,
        {".yaml", ".yml", ".json", ".cfg", ".conf", ".ini", ".txt"},
        ["config", "kf", "gins", "dataset", "final", "v23", "nominal"],
    )
    located_files = sorted(
        set(process_data_candidates)
        | set(run_scripts)
        | set(config_candidates)
        | {str(Path(hit["path"])) for hit in hits}
    )
    missing_keywords = [keyword for keyword, present in found.items() if not present]
    return {
        "source_root_exists": root.exists(),
        "located_files": located_files,
        "keyword_hits": hits,
        "keywords_found": found,
        "process_data_path": process_data_candidates[0] if process_data_candidates else None,
        "process_data_candidates": process_data_candidates,
        "run_script_candidates": run_scripts,
        "config_candidates": config_candidates,
        "evidence_missing": missing_keywords,
        "evidence_status": "process_data_evidence_found" if process_data_candidates else "evidence_missing",
        "copied_external_source": False,
        "trace_solver_input": False,
    }


def _paths_for_keywords(hits: list[dict[str, Any]], keywords: set[str]) -> list[str]:
    return sorted({hit["path"] for hit in hits if hit["keyword"] in keywords})


def audit_gnss_loader_and_engine_source(source_root: str | Path) -> dict[str, Any]:
    """Audit whether the external runtime appears to load/use velocity and yaw columns."""

    root = Path(source_root)
    hits, found = _search_keywords(root, GNSS_ENGINE_KEYWORDS)
    velocity_paths = _paths_for_keywords(
        hits, {"gnssdata.vel", "gnssdata.vel_std", "velocity update", "H_gnssvel", "velUpdate"}
    )
    yaw_paths = _paths_for_keywords(
        hits, {"gnssdata.yaw", "gnssdata.yaw_std", "yaw update", "H_gnssyaw", "scheme_C"}
    )
    position_paths = _paths_for_keywords(hits, {"gnssdata.blh", "gnssdata.std", "gnssUpdate"})
    loader_columns = {
        "position_blh": found.get("gnssdata.blh", False),
        "position_std": found.get("gnssdata.std", False),
        "velocity": found.get("gnssdata.vel", False),
        "velocity_std": found.get("gnssdata.vel_std", False),
        "yaw": found.get("gnssdata.yaw", False),
        "yaw_std": found.get("gnssdata.yaw_std", False),
        "fifteen_column_runtime_input": all(
            found.get(keyword, False)
            for keyword in [
                "gnssdata.blh",
                "gnssdata.std",
                "gnssdata.vel",
                "gnssdata.vel_std",
                "gnssdata.yaw",
                "gnssdata.yaw_std",
            ]
        ),
    }
    uses_velocity = bool(velocity_paths and (found.get("H_gnssvel") or found.get("velocity update")))
    uses_yaw = bool(yaw_paths and (found.get("H_gnssyaw") or found.get("yaw update") or found.get("scheme_C")))
    if loader_columns["fifteen_column_runtime_input"] and uses_velocity and uses_yaw:
        status = "gnss_loader_velocity_yaw_update_evidence_found"
    elif loader_columns["fifteen_column_runtime_input"]:
        status = "loader_columns_found_runtime_update_evidence_partial"
    else:
        status = "runtime_source_branch_parity_evidence_missing"
    return {
        "source_root_exists": root.exists(),
        "keyword_hits": hits,
        "keywords_found": found,
        "gnss_loader_columns_supported": loader_columns,
        "uses_velocity_update": uses_velocity,
        "uses_yaw_update": uses_yaw,
        "yaw_update_function_paths": yaw_paths,
        "velocity_update_function_paths": velocity_paths,
        "position_update_function_paths": position_paths,
        "evidence_status": status,
        "copied_external_source": False,
        "trace_solver_input": False,
    }


def audit_kfgins_core_flow(source_root: str | Path) -> dict[str, Any]:
    """Build a found/missing matrix for the KF-GINS-style runtime flow."""

    root = Path(source_root)
    files = _iter_text_files(root)
    term_hits_by_name: dict[str, list[dict[str, Any]]] = {term: [] for term in CORE_FLOW_TERMS}
    term_found_keywords: dict[str, dict[str, bool]] = {
        term: {keyword: False for keyword in keywords} for term, keywords in CORE_FLOW_TERMS.items()
    }
    term_counts: dict[str, dict[str, int]] = {
        term: {keyword: 0 for keyword in keywords} for term, keywords in CORE_FLOW_TERMS.items()
    }
    for path in files:
        try:
            lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
        except OSError:
            continue
        for line_number, line in enumerate(lines, start=1):
            for term, keywords in CORE_FLOW_TERMS.items():
                for keyword in keywords:
                    if term_counts[term][keyword] >= 25:
                        continue
                    if keyword == "kf_gins.cpp":
                        matched = path.name == "kf_gins.cpp" or keyword in line
                    else:
                        matched = keyword in line
                    if not matched:
                        continue
                    term_found_keywords[term][keyword] = True
                    term_counts[term][keyword] += 1
                    term_hits_by_name[term].append(
                        {
                            "path": str(path),
                            "line": line_number,
                            "keyword": keyword,
                            "summary": f"{keyword} evidence observed near {_path_summary(path, root)}:{line_number}",
                        }
                    )
    matrix: dict[str, dict[str, Any]] = {}
    all_hits: list[dict[str, Any]] = []
    for term, keywords in CORE_FLOW_TERMS.items():
        term_hits = term_hits_by_name[term]
        found = term_found_keywords[term]
        all_hits.extend(term_hits)
        paths = sorted({hit["path"] for hit in term_hits})
        if term == "kf_gins.cpp main":
            kf_main_paths = [str(path) for path in files if path.name == "kf_gins.cpp"]
            paths = sorted(set(paths) | set(kf_main_paths))
            term_found = bool(paths)
        elif term == "F/G/Phi/Qd construction":
            term_found = sum(1 for key in keywords if found.get(key)) >= 2
        else:
            term_found = any(found.values())
        matrix[term] = {
            "found": term_found,
            "paths": paths,
            "keywords": keywords,
        }
    missing = [term for term, item in matrix.items() if not item["found"]]
    return {
        "found_missing_matrix": matrix,
        "source_paths": {term: item["paths"] for term, item in matrix.items()},
        "missing": missing,
        "keyword_hits": all_hits,
        "evidence_status": "core_flow_evidence_found" if not missing else "core_flow_evidence_partial",
        "copied_external_source": False,
        "trace_solver_input": False,
    }
