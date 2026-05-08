"""Runtime yaw/config parity audit helpers for N4H2C-runtime.

中文说明：本模块只读取仓库外 runtime config/report 证据并比较 yaw 相关配置；
不修改 solver output，不复制 external source，不把 trace/reference 作为 solver input。
"""

from __future__ import annotations

import json
import math
from pathlib import Path
import re
from typing import Any


CONFIG_SUFFIXES = {".yaml", ".yml", ".json", ".sh", ".log", ".txt"}
CONFIG_NAMES = {
    "RUN_MANIFEST.json",
    "KFGINS_REPLAY_REPORT.json",
    "N4H2_REPLAY_REPORT.json",
    "RUN_ATTEMPT.json",
}
ARTIFACT_EXCLUDE_NAMES = {
    "input.gnss",
    "KF_GINS_Navresult.nav",
    "KF_GINS_STD.txt",
    "KF_GINS_IMU_ERR.txt",
    "summary.json",
    "error_series.csv",
}
MAX_CONFIG_BYTES = 2_000_000

FIELD_ALIASES = {
    "imupath": ["imupath", "imu_path", "imu.path", "run_attempt.config.imupath"],
    "gnsspath": ["gnsspath", "gnss_path", "gnss.path", "run_attempt.config.gnsspath"],
    "outputpath": ["outputpath", "output_path", "output_inventory", "run_attempt.config.outputpath"],
    "starttime": ["starttime", "start_time"],
    "endtime": ["endtime", "end_time"],
    "initpos": ["initpos", "init_pos"],
    "initvel": ["initvel", "init_vel"],
    "initatt": ["initatt", "init_att"],
    "initattstd": ["initattstd", "init_att_std"],
    "imunoise": ["imunoise", "imu_noise"],
    "antlever": ["antlever", "ant_lever", "antenna_lever"],
    "imudatalen": ["imudatalen", "imu_data_len"],
    "imudatarate": ["imudatarate", "imu_data_rate"],
    "yaw_source": ["yaw_source", "yaw_source_mode", "input_generation_report.yaw_source"],
    "yaw_mode": ["yaw_mode", "yaw_source_mode", "input_generation_report.yaw_source_mode"],
    "yaw_std": ["yaw_std", "yaw_std_deg", "input_generation_report.yaw_std_mode"],
    "yaw_gate": ["yaw_gate", "yaw_gate_deg", "scheme_C_yaw_gate", "Rscale"],
    "scheme_C": ["scheme_C", "scheme_c", "scheme_C_gate"],
    "executable": ["executable", "run_attempt.executable"],
    "source_commit": ["source_commit", "commit", "head_commit", "kfgins_commit"],
}
NUMERIC_LIST_FIELDS = {"initpos", "initvel", "initatt", "initattstd", "antlever"}
SCALAR_NUMERIC_FIELDS = {"starttime", "endtime", "imudatalen", "imudatarate"}


def _flatten(prefix: str, value: Any, out: dict[str, Any]) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            next_prefix = f"{prefix}.{key}" if prefix else str(key)
            _flatten(next_prefix, item, out)
    elif isinstance(value, list):
        out[prefix] = value
        for index, item in enumerate(value):
            _flatten(f"{prefix}.{index}" if prefix else str(index), item, out)
    else:
        out[prefix] = value


def _parse_scalar(text: str) -> Any:
    value = text.strip().strip("'\"")
    if not value:
        return ""
    if value.lower() in {"true", "false"}:
        return value.lower() == "true"
    if value.lower() in {"null", "none"}:
        return None
    if value.startswith("[") and value.endswith("]"):
        pieces = [piece.strip() for piece in value[1:-1].split(",") if piece.strip()]
        parsed: list[Any] = []
        for piece in pieces:
            parsed.append(_parse_scalar(piece))
        return parsed
    try:
        if re.fullmatch(r"[-+]?\d+", value):
            return int(value)
        return float(value)
    except ValueError:
        return value


def _parse_yaml_like(text: str) -> dict[str, Any]:
    data: dict[str, Any] = {}
    active_key: str | None = None
    active_list: list[Any] = []
    for raw_line in text.splitlines():
        line = raw_line.split("#", 1)[0].rstrip()
        if not line.strip():
            continue
        key_match = re.match(r"^([A-Za-z0-9_.-]+)\s*:\s*(.*)$", line)
        if key_match and not raw_line.startswith((" ", "\t")):
            if active_key is not None:
                data[active_key] = active_list
                active_key = None
                active_list = []
            key = key_match.group(1)
            value = key_match.group(2).strip()
            if value:
                data[key] = _parse_scalar(value)
            else:
                active_key = key
                active_list = []
            continue
        list_match = re.match(r"^\s*-\s*(.*)$", line)
        if active_key is not None and list_match:
            active_list.append(_parse_scalar(list_match.group(1)))
            continue
        nested_match = re.match(r"^\s+([A-Za-z0-9_.-]+)\s*:\s*(.*)$", line)
        if active_key is not None and nested_match:
            nested_key = f"{active_key}.{nested_match.group(1)}"
            value = nested_match.group(2).strip()
            data[nested_key] = _parse_scalar(value) if value else ""
    if active_key is not None:
        data[active_key] = active_list
    return data


def _read_small_text(path: Path) -> str:
    if not path.exists() or not path.is_file() or path.stat().st_size > MAX_CONFIG_BYTES:
        return ""
    return path.read_text(encoding="utf-8", errors="ignore")


def _extract_log_hints(text: str) -> dict[str, Any]:
    hints: dict[str, Any] = {}
    if "[YAW-NORMAL]" in text or "[YAW-DOWNWEIGHT]" in text:
        hints["yaw_update_log_present"] = True
    if "yaw_std_deg=" in text:
        values = [float(value) for value in re.findall(r"yaw_std_deg=([-+]?\d+(?:\.\d+)?)", text)]
        if values:
            hints["yaw_std_log_mean_deg"] = sum(values) / len(values)
            hints["yaw_std_log_count"] = len(values)
    if "Rscale=" in text:
        values = [float(value) for value in re.findall(r"Rscale=([-+]?\d+(?:\.\d+)?)", text)]
        if values:
            hints["yaw_gate_rscale_values"] = sorted({round(value, 6) for value in values})
    return hints


def _extract_fields(path: Path) -> dict[str, Any]:
    text = _read_small_text(path)
    if not text:
        return {"raw_fields": {}, "extracted_fields": {}, "evidence_status": "evidence_missing"}
    raw_fields: dict[str, Any] = {}
    if path.suffix.lower() == ".json":
        try:
            parsed = json.loads(text)
            _flatten("", parsed, raw_fields)
        except json.JSONDecodeError:
            raw_fields.update(_parse_yaml_like(text))
    else:
        raw_fields.update(_parse_yaml_like(text))
    raw_fields.update(_extract_log_hints(text))

    lowered = {key.lower(): key for key in raw_fields}
    extracted: dict[str, Any] = {}
    for output_field, aliases in FIELD_ALIASES.items():
        for alias in aliases:
            key = lowered.get(alias.lower())
            if key is not None:
                extracted[output_field] = raw_fields[key]
                break
    if "yaw_std" not in extracted and "yaw_std_log_mean_deg" in raw_fields:
        extracted["yaw_std"] = raw_fields["yaw_std_log_mean_deg"]
    if "yaw_gate" not in extracted and "yaw_gate_rscale_values" in raw_fields:
        extracted["yaw_gate"] = raw_fields["yaw_gate_rscale_values"]
    if "scheme_C" not in extracted and "yaw_gate_rscale_values" in raw_fields:
        extracted["scheme_C"] = "yaw_rscale_downweight_present"
    return {
        "raw_fields": raw_fields,
        "extracted_fields": extracted,
        "evidence_status": "parsed" if extracted else "no_target_fields",
    }


def _is_config_candidate(path: Path) -> bool:
    if not path.is_file():
        return False
    if path.name in ARTIFACT_EXCLUDE_NAMES:
        return False
    if path.name in CONFIG_NAMES:
        return True
    if path.name.startswith("run") and path.suffix.lower() in CONFIG_SUFFIXES:
        return True
    if "manifest" in path.name.lower() and path.suffix.lower() == ".json":
        return True
    if "replay" in path.name.lower() and path.suffix.lower() in CONFIG_SUFFIXES:
        return True
    return path.suffix.lower() in {".yaml", ".yml", ".sh", ".log"}


def _candidate_score(path: Path, extracted: dict[str, Any]) -> int:
    fields = extracted.get("extracted_fields") or {}
    score = len(fields)
    name = path.name.lower()
    if path.suffix.lower() in {".yaml", ".yml"}:
        score += 4
    if "replay" in name or "manifest" in name or "run_attempt" in name:
        score += 2
    if {"imupath", "gnsspath", "initatt"}.issubset(fields):
        score += 6
    if fields.get("yaw_std") is not None or fields.get("scheme_C") is not None:
        score += 2
    return score


def _collect_candidates(role: str, root: Path, *, max_depth: int = 6) -> dict[str, Any]:
    if not root.exists():
        return {
            "root_role": role,
            "root": str(root),
            "candidates": [],
            "best_config": None,
            "config_status": "evidence_missing",
        }
    candidates: list[dict[str, Any]] = []
    root_depth = len(root.parts)
    for path in sorted(root.rglob("*")):
        if any(part in {".git", "build", "__pycache__"} for part in path.parts):
            continue
        if len(path.parts) - root_depth > max_depth:
            continue
        if not _is_config_candidate(path):
            continue
        extracted = _extract_fields(path)
        candidate = {
            "role": role,
            "path": str(path),
            "path_role": f"{role}:{len(candidates)}",
            "name": path.name,
            "extracted_fields": extracted.get("extracted_fields", {}),
            "evidence_status": extracted.get("evidence_status"),
            "score": _candidate_score(path, extracted),
        }
        if candidate["score"] > 0:
            candidates.append(candidate)
    candidates.sort(key=lambda item: (-int(item["score"]), str(item["path"])))
    best = candidates[0] if candidates else None
    return {
        "root_role": role,
        "root": str(root),
        "candidate_count": len(candidates),
        "candidates": candidates[:20],
        "best_config": best,
        "config_status": "parsed" if best else "evidence_missing",
    }


def _default_roots() -> dict[str, Path]:
    return {
        "DUAL_FINAL_V23_ARTIFACT_ROOT": Path.home() / "legsa_external_artifacts" / "dual_final_v23_nominal",
        "N4H2_ARTIFACTS_ROOT": Path.home() / "legsa_n4h2_artifacts",
        "EXTERNAL_KFGINS_ROOT": Path.home() / "KF-GINS",
    }


def find_runtime_configs(root_candidates: dict[str, str | Path] | list[str | Path] | None) -> dict[str, Any]:
    """Find likely actual/replay/runtime configs under runtime-only roots."""

    if root_candidates is None:
        roots = _default_roots()
    elif isinstance(root_candidates, dict):
        roots = {str(role): Path(path) for role, path in root_candidates.items()}
    else:
        roots = {f"ROOT_{index}": Path(path) for index, path in enumerate(root_candidates)}

    role_reports = {
        role: _collect_candidates(role, root, max_depth=4 if role == "EXTERNAL_KFGINS_ROOT" else 6)
        for role, root in roots.items()
    }
    actual_report = role_reports.get("DUAL_FINAL_V23_ARTIFACT_ROOT")
    replay_report = role_reports.get("N4H2_ARTIFACTS_ROOT")
    external_report = role_reports.get("EXTERNAL_KFGINS_ROOT")
    return {
        "phase": "N4H2C-runtime",
        "role_reports": role_reports,
        "best_actual_config": (actual_report or {}).get("best_config"),
        "best_replay_config": (replay_report or {}).get("best_config"),
        "best_external_config": (external_report or {}).get("best_config"),
        "actual_config_status": (actual_report or {}).get("config_status", "evidence_missing"),
        "replay_config_status": (replay_report or {}).get("config_status", "evidence_missing"),
        "external_config_status": (external_report or {}).get("config_status", "evidence_missing"),
        "trace_solver_input": False,
        "output_only_correction": False,
        "solver_output_changed": False,
        "numerical_performance_claim": False,
    }


def _to_float(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _as_float_list(value: Any) -> list[float] | None:
    if not isinstance(value, list):
        return None
    values: list[float] = []
    for item in value:
        parsed = _to_float(item)
        if parsed is None:
            return None
        values.append(parsed)
    return values


def _field(config: dict[str, Any] | None, name: str) -> Any:
    if not config:
        return None
    fields = config.get("extracted_fields") if "extracted_fields" in config else config
    if not isinstance(fields, dict):
        return None
    return fields.get(name)


def _diff_scalar(actual: Any, replay: Any) -> float | None:
    a = _to_float(actual)
    b = _to_float(replay)
    if a is None or b is None:
        return None
    return b - a


def _diff_list(actual: Any, replay: Any) -> list[float] | None:
    a = _as_float_list(actual)
    b = _as_float_list(replay)
    if a is None or b is None or len(a) != len(b):
        return None
    return [b_item - a_item for a_item, b_item in zip(a, b)]


def _norm(values: list[float] | None) -> float | None:
    if values is None:
        return None
    return math.sqrt(sum(value * value for value in values))


def compare_actual_and_replay_config(
    actual_config: dict[str, Any] | None,
    replay_config: dict[str, Any] | None,
) -> dict[str, Any]:
    """Compare actual dual runtime config evidence with N4H2 replay config."""

    actual_missing = not actual_config
    replay_missing = not replay_config
    scalar_diffs = {
        field: _diff_scalar(_field(actual_config, field), _field(replay_config, field))
        for field in ["starttime", "endtime", "imudatalen", "imudatarate"]
    }
    vector_diffs = {
        field: _diff_list(_field(actual_config, field), _field(replay_config, field))
        for field in ["initpos", "initvel", "initatt", "initattstd", "antlever"]
    }
    exact_diffs: dict[str, dict[str, Any]] = {}
    for field in ["imupath", "gnsspath", "outputpath", "yaw_source", "yaw_mode", "yaw_std", "yaw_gate", "scheme_C", "executable", "source_commit"]:
        actual_value = _field(actual_config, field)
        replay_value = _field(replay_config, field)
        if actual_value != replay_value:
            exact_diffs[field] = {"actual": actual_value, "replay": replay_value}

    initatt_diff = vector_diffs.get("initatt")
    antlever_diff = vector_diffs.get("antlever")
    yaw_relevant: dict[str, Any] = {
        "initatt_diff": initatt_diff,
        "initatt_diff_norm": _norm(initatt_diff),
        "initatt_yaw_diff_deg": initatt_diff[2] if initatt_diff and len(initatt_diff) >= 3 else None,
        "initattstd_diff": vector_diffs.get("initattstd"),
        "antlever_diff": antlever_diff,
        "antlever_diff_norm": _norm(antlever_diff),
        "yaw_std_diff": exact_diffs.get("yaw_std"),
        "yaw_gate_diff": exact_diffs.get("yaw_gate"),
        "scheme_C_diff": exact_diffs.get("scheme_C"),
        "source_commit_diff": exact_diffs.get("source_commit"),
    }
    evidence_missing: list[str] = []
    if actual_missing:
        evidence_missing.append("actual_runtime_config")
    if replay_missing:
        evidence_missing.append("replay_runtime_config")
    if actual_missing:
        actual_status = "evidence_missing"
    else:
        actual_status = str(actual_config.get("evidence_status", "parsed"))
    if replay_missing:
        replay_status = "evidence_missing"
    else:
        replay_status = str(replay_config.get("evidence_status", "parsed"))
    significant_yaw_config_diff = bool(
        (yaw_relevant["initatt_yaw_diff_deg"] is not None and abs(float(yaw_relevant["initatt_yaw_diff_deg"])) > 0.5)
        or yaw_relevant["yaw_std_diff"]
        or yaw_relevant["yaw_gate_diff"]
        or yaw_relevant["scheme_C_diff"]
    )
    return {
        "phase": "N4H2C-runtime",
        "actual_config_status": actual_status,
        "replay_config_status": replay_status,
        "config_diff_summary": {
            "scalar_diffs": scalar_diffs,
            "vector_diffs": vector_diffs,
            "exact_diffs": exact_diffs,
        },
        "initatt_diff": initatt_diff,
        "antlever_diff": antlever_diff,
        "yaw_relevant_config_diff": yaw_relevant,
        "significant_yaw_config_diff": significant_yaw_config_diff,
        "evidence_missing": evidence_missing,
        "recommended_action": "manual_actual_config_recovery_or_source_history_audit"
        if actual_missing
        else "config_parity_review",
        "trace_solver_input": False,
        "output_only_correction": False,
        "solver_output_changed": False,
        "numerical_performance_claim": False,
    }
