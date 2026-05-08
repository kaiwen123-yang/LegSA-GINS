"""Read-only process_data runtime-parameter audit.

中文说明：只解析 process_data.py 默认参数和调用证据；不修改外部源码，不执行
process_data 调参，也不把 trace yaw 作为 solver input。
"""

from __future__ import annotations

import ast
from pathlib import Path
import re
from typing import Any


DEFAULT_KEYS = [
    "BASE_TIME",
    "USE_STATUS_YAW",
    "YAW_SIGN",
    "YAW_INSTALL_OFFSET_DEG",
    "AUTO_APPLY_BEST_INSTALL",
    "YAW_SOURCE_MODE",
    "YAW_NOISE_STD_DEG",
    "OUTAGE_DURATION_SEC",
    "OUTLIER_RATIO_DEFAULT",
    "OUTLIER_MODE_DEFAULT",
    "STATUS_YAW_STD_MODE_DEFAULT",
    "STATUS_FIXED_YAW_STD_DEG_DEFAULT",
    "YAW_STD_MODE_DEFAULT",
    "IMU_INSTALL_ROLL_DEG_DEFAULT",
    "IMU_INSTALL_PITCH_DEG_DEFAULT",
    "IMU_INSTALL_YAW_DEG_DEFAULT",
    "IMU_GNSS_TIME_OFFSET_SEC_DEFAULT",
]

INVOCATION_KEYWORDS = [
    "process_data.py",
    "--yaw_source_mode",
    "--generate_both_gnss",
    "--status_yaw_std_mode",
    "--yaw_std_mode",
    "--enable_outage",
    "--outlier_mode",
    "--yaw_noise_std_deg",
    "--imu_install_roll_deg",
    "--imu_gnss_time_offset",
    "test1_statusyaw",
    "test1_traceyaw",
    "final_status_fixed",
    "final_status_fixed1p5",
]

TEXT_SUFFIXES = {".py", ".sh", ".bash", ".md", ".txt", ".yaml", ".yml", ".json"}
SKIP_DIRS = {
    ".git",
    "__pycache__",
    ".pytest_cache",
    "artifacts",
    "build",
    "cmake-build-debug",
    "cmake-build-release",
    "extended_degradation_results",
    "log",
    "logs",
    "output",
    "outputs",
    "result",
    "results",
    "ThirdParty",
    "third_party",
    "vendor",
}
MAX_TEXT_BYTES = 2_000_000


def _literal(node: ast.AST) -> Any:
    try:
        return ast.literal_eval(node)
    except (ValueError, SyntaxError):
        return None


def extract_process_data_defaults(process_data_path: str | Path) -> dict[str, Any]:
    path = Path(process_data_path)
    defaults = {key: None for key in DEFAULT_KEYS}
    evidence: dict[str, dict[str, Any]] = {}
    if not path.exists():
        return {
            "process_data_exists": False,
            "defaults": defaults,
            "evidence": evidence,
            "evidence_missing": DEFAULT_KEYS,
            "evidence_status": "evidence_missing",
        }
    tree = ast.parse(path.read_text(encoding="utf-8", errors="ignore"))
    lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        value = _literal(node.value)
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id in defaults:
                defaults[target.id] = value
                evidence[target.id] = {
                    "path": str(path),
                    "line": node.lineno,
                    "summary": f"{target.id} default assigned",
                    "source": lines[node.lineno - 1].strip() if 0 <= node.lineno - 1 < len(lines) else "",
                }
    missing = [key for key, value in defaults.items() if value is None]
    return {
        "process_data_exists": True,
        "defaults": defaults,
        "evidence": evidence,
        "evidence_missing": missing,
        "evidence_status": "process_data_defaults_extracted" if not missing else "process_data_defaults_partial",
        "trace_solver_input": False,
        "numerical_performance_claim": False,
    }


def _iter_text_files(root: Path) -> list[Path]:
    if not root.exists():
        return []
    files: list[Path] = []
    for path in root.rglob("*"):
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if path.is_file() and path.suffix.lower() in TEXT_SUFFIXES and path.stat().st_size <= MAX_TEXT_BYTES:
            files.append(path)
    return sorted(files)


def _line_has_any(line: str, keywords: list[str]) -> bool:
    return any(keyword in line for keyword in keywords)


def _score_invocation(line: str) -> int:
    score = 0
    lower = line.lower()
    for token in ["final_v23", "final_status_fixed", "final_status_fixed1p5", "nominal_none", "generate_both_gnss"]:
        if token in lower:
            score += 2
    for token in ["--yaw_source_mode", "--status_yaw_std_mode", "--yaw_std_mode", "--outlier_mode"]:
        if token in line:
            score += 1
    return score


def _safe_flags(line: str) -> bool:
    lower = line.lower()
    noise_zero = ("--yaw_noise_std_deg 0" in lower) or ("--yaw_noise_std_deg=0" in lower)
    outlier_none = ("--outlier_mode none" in lower) or ("--outlier_mode=none" in lower)
    outage_absent = "--enable_outage" not in lower
    outage_false = ("--enable_outage false" in lower) or ("--enable_outage=false" in lower)
    return noise_zero and outlier_none and (outage_absent or outage_false)


def search_run_invocations(source_root: str | Path) -> dict[str, Any]:
    root = Path(source_root)
    candidates: list[dict[str, Any]] = []
    for path in _iter_text_files(root):
        try:
            lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
        except OSError:
            continue
        for line_number, line in enumerate(lines, start=1):
            if not _line_has_any(line, INVOCATION_KEYWORDS):
                continue
            score = _score_invocation(line)
            candidates.append(
                {
                    "path": str(path),
                    "line": line_number,
                    "score": score,
                    "explicit_safe_flags": _safe_flags(line),
                    "keywords": [keyword for keyword in INVOCATION_KEYWORDS if keyword in line],
                    "summary": "process_data runtime invocation evidence",
                }
            )
    candidates.sort(key=lambda item: (-int(item["score"]), item["path"], int(item["line"])))
    nominal = next(
        (item for item in candidates if "nominal_none" in item["path"].lower() or "nominal_none" in str(item).lower()),
        candidates[0] if candidates else None,
    )
    final_v23 = next(
        (item for item in candidates if "final_v23" in item["path"].lower() or "final_status" in str(item).lower()),
        candidates[0] if candidates else None,
    )
    missing = []
    if not candidates:
        missing.append("process_data_invocation")
    if not any(item["explicit_safe_flags"] for item in candidates):
        missing.append("explicit_nominal_safe_flags")
    return {
        "invocation_candidates": candidates,
        "likely_nominal_invocation": nominal,
        "likely_final_v23_invocation": final_v23,
        "explicit_safe_flags_found": any(item["explicit_safe_flags"] for item in candidates),
        "evidence_missing": missing,
        "evidence_status": "process_data_invocations_found" if candidates else "evidence_missing",
        "trace_solver_input": False,
    }


def _as_bool(value: Any) -> bool:
    return bool(value) if isinstance(value, bool) else str(value).strip().lower() in {"1", "true", "yes"}


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def make_process_data_runtime_parameter_report(
    defaults: dict[str, Any],
    invocations: dict[str, Any],
) -> dict[str, Any]:
    default_values = defaults.get("defaults", defaults)
    outlier_mode = default_values.get("OUTLIER_MODE_DEFAULT")
    noise = _as_float(default_values.get("YAW_NOISE_STD_DEG"), 0.0)
    outage = _as_float(default_values.get("OUTAGE_DURATION_SEC"), 0.0)
    outlier_ratio = _as_float(default_values.get("OUTLIER_RATIO_DEFAULT"), 0.0)
    nominal_degraded = bool((outlier_mode not in {None, "", "none"}) or noise > 0.0 or outage > 0.0 or outlier_ratio > 0.0)
    likely_invocation = invocations.get("likely_final_v23_invocation") or invocations.get("likely_nominal_invocation")
    return {
        "defaults": default_values,
        "nominal_defaults_are_noisy_or_degraded": nominal_degraded,
        "explicit_nominal_safe_flags_found": bool(invocations.get("explicit_safe_flags_found")),
        "likely_yaw_source_mode": default_values.get("YAW_SOURCE_MODE"),
        "likely_yaw_std_mode": default_values.get("STATUS_YAW_STD_MODE_DEFAULT") or default_values.get("YAW_STD_MODE_DEFAULT"),
        "likely_yaw_sign": default_values.get("YAW_SIGN"),
        "likely_yaw_install_offset": default_values.get("YAW_INSTALL_OFFSET_DEG"),
        "auto_apply_best_install": _as_bool(default_values.get("AUTO_APPLY_BEST_INSTALL")),
        "likely_nominal_invocation": invocations.get("likely_nominal_invocation"),
        "likely_final_v23_invocation": likely_invocation,
        "evidence_missing": sorted(set(defaults.get("evidence_missing", []) + invocations.get("evidence_missing", []))),
        "evidence_status": "runtime_parameters_audited",
        "trace_solver_input": False,
        "numerical_performance_claim": False,
    }
