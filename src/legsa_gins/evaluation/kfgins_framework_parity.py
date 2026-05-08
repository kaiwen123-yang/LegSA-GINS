"""Compare current LegSA code surface with a KF-GINS-style runtime flow.

中文说明：本模块只生成 framework parity 矩阵；N4 当前 filter core 仍是 toy/foundation，
不能被描述为 complete KF-GINS parity 或 formal solver performance。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any


PARITY_ITEMS = {
    "input .gnss/.imu reader": ["standard_receiver_measurement_reader", "standard_imu_increment_reader", ".gnss", ".imu"],
    "config reader": ["runtime_config", "RuntimeConfig", "loadConfig"],
    "addImuData": ["addImuData"],
    "addGnssData": ["addGnssData"],
    "newImuProcess": ["newImuProcess"],
    "isToUpdate": ["isToUpdate"],
    "imuInterpolate": ["imuInterpolate"],
    "imuCompensate": ["imuCompensate"],
    "insPropagation": ["insPropagation", "propagate"],
    "F/G/Phi/Qd": ["Phi", "Qd", "state_transition", "process_noise"],
    "EKFPredict": ["EKFPredict", "predict_to"],
    "EKFUpdate": ["EKFUpdate", "apply_measurement"],
    "stateFeedback": ["stateFeedback"],
    "NAV/STD/EVAL writer": ["LegSA_NAV.nav", "LegSA_STD.csv", "EVAL_NAV.csv"],
}

TOY_OR_PARTIAL_ITEMS = {
    "input .gnss/.imu reader",
    "addImuData",
    "addGnssData",
    "insPropagation",
    "EKFPredict",
    "EKFUpdate",
    "NAV/STD/EVAL writer",
}


def _iter_text_files(root: Path) -> list[Path]:
    suffixes = {".py", ".cpp", ".hpp", ".h", ".md", ".txt"}
    skip = {".git", "__pycache__", ".pytest_cache", "build"}
    files: list[Path] = []
    implementation_roots = [
        root / "cpp",
        root / "src/legsa_gins/estimator",
        root / "src/legsa_gins/experiments",
        root / "src/legsa_gins/input_generation",
        root / "src/legsa_gins/writers",
    ]
    for base in implementation_roots:
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if any(part in skip for part in path.parts):
                continue
            if path.is_file() and path.suffix.lower() in suffixes:
                files.append(path)
    return sorted(files)


def _search_tokens(root: Path, tokens: list[str]) -> list[str]:
    paths: set[str] = set()
    for path in _iter_text_files(root):
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if any(token in text or token in path.name for token in tokens):
            paths.add(str(path))
    return sorted(paths)


def _kfgins_found(kfgins_flow_report: dict[str, Any], item: str) -> bool:
    matrix = kfgins_flow_report.get("found_missing_matrix", {})
    if item in matrix and isinstance(matrix[item], dict):
        return bool(matrix[item].get("found"))
    aliases = {
        "F/G/Phi/Qd": "F/G/Phi/Qd construction",
        "NAV/STD/EVAL writer": "kf_gins.cpp main",
    }
    alias = aliases.get(item)
    if alias in matrix and isinstance(matrix[alias], dict):
        return bool(matrix[alias].get("found"))
    return True


def compare_legsa_to_kfgins_framework(
    kfgins_flow_report: dict[str, Any],
    legsa_repo_root: str | Path,
) -> dict[str, Any]:
    """Compare current LegSA implementation surface against KF-GINS-style flow items."""

    root = Path(legsa_repo_root)
    parity_matrix: dict[str, dict[str, Any]] = {}
    missing: list[str] = []
    toy_only: list[str] = []
    recommendations: list[str] = []
    for item, tokens in PARITY_ITEMS.items():
        paths = _search_tokens(root, tokens)
        legsa_found = bool(paths)
        kfgins_found = _kfgins_found(kfgins_flow_report, item)
        if not legsa_found:
            status = "missing_in_legsa"
            missing.append(item)
            recommendations.append(item)
        elif item in TOY_OR_PARTIAL_ITEMS:
            status = "toy_or_foundation_only"
            toy_only.append(item)
            recommendations.append(f"promote {item} from toy/foundation to KF-GINS-style implementation")
        else:
            status = "present"
        parity_matrix[item] = {
            "kfgins_found": kfgins_found,
            "legsa_status": status,
            "legsa_paths": paths,
            "notes": "N4 current LegSA filter core is not complete KF-GINS parity.",
        }
    return {
        "parity_matrix": parity_matrix,
        "missing_in_legsa": missing,
        "implemented_as_toy_only": toy_only,
        "recommended_reconstruction_items": recommendations,
        "evidence_status": "legsa_framework_gap_recorded",
        "full_kfgins_parity_claim": False,
        "numerical_performance_claim": False,
    }
