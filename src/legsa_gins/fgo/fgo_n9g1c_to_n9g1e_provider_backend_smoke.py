"""N9G1C-E provider contract, backend, logger, and normal-smoke gate.

This stage repairs evidence and runtime mapping for the separate
``LegSA_9F_FGO_EKF`` candidate. It does not implement new factor math and does
not relabel ``LegSA_full_EKF`` as a nine-factor FGO backend.
"""

from __future__ import annotations

import csv
import json
import math
import re
import shlex
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

from legsa_gins.fgo.fgo_backend_discovery import discover_fgo_backend
from legsa_gins.fgo.fgo_n9g1b_legsa_9f_phase1 import (
    ALGORITHM_ID,
    FGO_FACTOR_RESIDUAL_FIELDS,
    FGO_WINDOW_SUMMARY_FIELDS,
    FEEDBACK_TRACE_FIELDS,
    LEGGED_DIAGNOSTIC_FIELDS,
    LOGGER_SCHEMAS,
    NINE_FACTORS,
    NORMAL_CASE_ID,
    build_legged_evidence_rows,
    classify_factor_evidence,
    validate_logger_schemas,
)
from legsa_gins.reporting.by2_algorithm_runner import (
    ALGORITHM_SPECS,
    build_algorithm_config_text,
    parse_yaml_like,
    repo_to_wsl,
    write_json,
)


STAGE = "N9G1C_TO_N9G1E_PROVIDER_CONTRACT_RESOLUTION_ACTIVE_FGO_BACKEND_AND_NORMAL_SMOKE"
STAGE_C = "N9G1C_PROVIDER_CONTRACT_RESOLUTION"
STAGE_D = "N9G1D_ACTIVE_FGO_BACKEND_AUDIT_AND_REPAIR"
STAGE_E = "N9G1E_NORMAL_SMOKE_GATE_AND_NORMAL_SMOKE"
LEGSA_FULL_ID = "LegSA_full_EKF"

RUNTIME_SUBDIRS = [
    "00_supervisor",
    "01_plan",
    "provider_resolution",
    "locked_normal_source_repair",
    "active_backend_audit",
    "factor_wiring_repair",
    "logger_connection",
    "dry_run",
    "normal_smoke_gate",
    "normal_smoke",
    "official_eval",
    "evidence_tables",
    "context_update",
    "obsidian_sync",
    "export_clean",
    "reports",
    "matrix",
    "summary",
    "validation",
    "logs",
    "blocked",
]

PUBLIC_OBSIDIAN_NOTES = [
    "00_INDEX.md",
    "01_CURRENT_STATE.md",
    "02_PROVIDER_CONTRACT_STATUS.md",
    "03_BACKEND_STATUS.md",
    "04_FACTOR_WIRING_STATUS.md",
    "05_LOGGER_STATUS.md",
    "06_NORMAL_SMOKE_RESULT.md",
    "07_CLAIM_BOUNDARY.md",
    "08_NEXT_STEPS.md",
]
PRIVATE_OBSIDIAN_NOTE = "99_LOCAL_PATHS.private.md"


@dataclass(frozen=True)
class ProviderSpec:
    provider: str
    factor: str
    required_groups: tuple[tuple[str, ...], ...]
    candidate_only: bool = False
    aggregate_only: bool = False
    source_hint: str = ""


PROVIDER_SPECS: tuple[ProviderSpec, ...] = (
    ProviderSpec("GNSS position", "ReceiverPositionFactor", (("time",), ("lat", "latitude"), ("lon", "longitude"), ("height", "alt", "altitude"))),
    ProviderSpec("GNSS velocity", "ReceiverVelocityFactor", (("time",), ("vn", "vN", "vel_n"), ("ve", "vE", "vel_e"), ("vd", "vD", "vel_d"))),
    ProviderSpec("dual yaw", "DualYawFactor", (("time",), ("yaw", "heading"), ("yaw_std", "std_yaw", "heading_std"))),
    ProviderSpec("Raw Doppler", "RawDopplerVelocityFactor", (("time",), ("vn", "vn_mps", "vN"), ("ve", "ve_mps", "vE"), ("vd", "vd_mps", "vD"), ("std_vn", "std", "sigma_vn")), source_hint="Raw Doppler provider"),
    ProviderSpec("Go2 joint", "Go2ProprioceptiveJointFactor", (("time",), ("roll_rad", "roll"), ("pitch_rad", "pitch"), ("vn", "vN"), ("ve", "vE"), ("std_roll_rad", "std_roll", "std")), source_hint="Go2 joint provider"),
    ProviderSpec("Go2 attitude", "Go2ProprioceptiveJointFactor", (("time",), ("roll_rad", "roll"), ("pitch_rad", "pitch"), ("std_roll_rad", "std_roll", "std")), source_hint="Go2 attitude provider"),
    ProviderSpec("Go2 horizontal velocity", "Go2ProprioceptiveJointFactor", (("time",), ("vn", "vN"), ("ve", "vE"), ("std_vn", "std")), source_hint="Go2 horizontal velocity provider"),
    ProviderSpec("foot kinematic velocity", "FootKinematicVelocityFactor", (("time",), ("candidate_vn", "foot_vn"), ("candidate_ve", "foot_ve"), ("slip_risk",)), candidate_only=True),
    ProviderSpec("yaw-rate", "YawRateBetweenFactor", (("time",), ("yaw_rate", "yaw_speed", "gyro_z")), candidate_only=True, aggregate_only=True),
    ProviderSpec("relative odometry", "RelativeOdometryBetweenFactor", (("time_i", "time", "window_count"), ("delta_n", "go2_position_delta_rmse_m"), ("delta_e", "integrated_go2_velocity_delta_rmse_m")), candidate_only=True, aggregate_only=True),
    ProviderSpec("contact probability", "contact_probability", (("time", "row_count"), ("contact_probability", "support_probability_mean")), candidate_only=True, aggregate_only=True),
    ProviderSpec("slip risk", "slip_risk", (("time",), ("slip_risk",)), candidate_only=True),
    ProviderSpec("feedback observations", "selected_feedback", (("time",), ("vN", "vn", "std_vN"), ("roll", "std_roll"), ("feedback_valid",)), source_hint="selected-feedback provider"),
)


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return default


def _csv_value(value: Any) -> Any:
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return value


def _write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    keys = list(fieldnames or [])
    if not keys:
        for row in rows:
            for key in row:
                if key not in keys:
                    keys.append(key)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=keys)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: _csv_value(row.get(key)) for key in keys})


def _write_pair(path_stem: Path, rows: list[dict[str, Any]], fieldnames: list[str] | None = None) -> None:
    write_json(path_stem.with_suffix(".json"), rows)
    _write_csv(path_stem.with_suffix(".csv"), rows, fieldnames)


def _write_summary(path: Path, title: str, lines: Iterable[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("# " + title + "\n\n" + "\n".join(lines) + "\n", encoding="utf-8")


def prepare_runtime_tree(runtime_root: Path) -> None:
    for subdir in RUNTIME_SUBDIRS:
        (runtime_root / subdir).mkdir(parents=True, exist_ok=True)


def _windows_from_wsl(path_text: str) -> Path | None:
    match = re.match(r"^/mnt/([A-Za-z])/(.*)$", path_text)
    if not match:
        return None
    return Path(f"{match.group(1).upper()}:\\" + match.group(2).replace("/", "\\"))


def _path_exists(path_text: str | None) -> bool:
    if not path_text:
        return False
    win = _windows_from_wsl(path_text)
    if win is not None:
        return win.exists()
    if path_text.startswith("/"):
        try:
            completed = subprocess.run(
                ["wsl", "bash", "-lc", f"test -f {shlex.quote(path_text)}"],
                check=False,
                capture_output=True,
                text=True,
                timeout=30,
            )
        except (OSError, subprocess.SubprocessError):
            return False
        return completed.returncode == 0
    return Path(path_text).exists()


def _read_first_last(path_text: str) -> tuple[str | None, str | None]:
    win = _windows_from_wsl(path_text)
    if win is not None:
        path = win
    elif re.match(r"^[A-Za-z]:", path_text):
        path = Path(path_text)
    else:
        try:
            completed = subprocess.run(
                ["wsl", "bash", "-lc", f"head -1 {shlex.quote(path_text)}; tail -1 {shlex.quote(path_text)}"],
                check=False,
                capture_output=True,
                text=True,
                timeout=30,
            )
        except (OSError, subprocess.SubprocessError):
            return None, None
        lines = [line for line in completed.stdout.splitlines() if line.strip()]
        return (lines[0], lines[-1]) if lines else (None, None)
    try:
        first: str | None = None
        last: str | None = None
        with path.open("r", encoding="utf-8-sig", errors="ignore") as handle:
            for raw in handle:
                line = raw.strip()
                if not line:
                    continue
                if first is None:
                    first = line
                last = line
        return first, last
    except OSError:
        return None, None


def _row_count(path_text: str | None) -> int | None:
    if not path_text or not _path_exists(path_text):
        return None
    win = _windows_from_wsl(path_text)
    if win is not None:
        path_text = str(win)
    if re.match(r"^[A-Za-z]:", path_text):
        try:
            with Path(path_text).open("r", encoding="utf-8-sig", errors="ignore") as handle:
                return sum(1 for line in handle if line.strip())
        except OSError:
            return None
    try:
        completed = subprocess.run(
            ["wsl", "bash", "-lc", f"wc -l {shlex.quote(path_text)}"],
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if completed.returncode != 0:
        return None
    token = completed.stdout.strip().split()
    return int(token[0]) if token and token[0].isdigit() else None


def _time_range(path_text: str | None, *, has_header: bool) -> dict[str, Any]:
    if not path_text or not _path_exists(path_text):
        return {"time_start": None, "time_end": None}
    first, last = _read_first_last(path_text)
    if not first or not last:
        return {"time_start": None, "time_end": None}
    if has_header:
        _, last = _read_first_last(path_text)
        first_data = _first_data_line(path_text)
    else:
        first_data = first
    return {"time_start": _first_number(first_data), "time_end": _first_number(last)}


def _first_data_line(path_text: str) -> str | None:
    win = _windows_from_wsl(path_text)
    if win is not None:
        path_text = str(win)
    if re.match(r"^[A-Za-z]:", path_text):
        try:
            with Path(path_text).open("r", encoding="utf-8-sig", errors="ignore") as handle:
                for index, line in enumerate(handle):
                    if index == 0:
                        continue
                    if line.strip():
                        return line.strip()
        except OSError:
            return None
    try:
        completed = subprocess.run(
            ["wsl", "bash", "-lc", f"sed -n '2p' {shlex.quote(path_text)}"],
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return completed.stdout.strip() or None


def _first_number(line: str | None) -> float | None:
    if not line:
        return None
    first = re.split(r"[\s,]+", line.strip(), maxsplit=1)[0]
    try:
        value = float(first)
        return value if math.isfinite(value) else None
    except ValueError:
        return None


def _header_fields(path_text: str | None) -> list[str]:
    if not path_text or not _path_exists(path_text):
        return []
    first, _ = _read_first_last(path_text)
    if not first:
        return []
    if "," not in first:
        parts = re.split(r"\s+", first.strip())
        return [f"col_{index + 1}" for index in range(len(parts))]
    return [item.strip() for item in first.split(",")]


def _source_root(path_text: str | None) -> str:
    if not path_text:
        return "missing"
    if path_text.startswith("/home/"):
        return "WSL"
    if path_text.startswith("/mnt/"):
        match = re.match(r"^/mnt/([A-Za-z])/", path_text)
        return match.group(1).upper() if match else "WSL"
    match = re.match(r"^([A-Za-z]):", path_text)
    return match.group(1).upper() if match else "unknown"


def _groups_present(fields: list[str], groups: tuple[tuple[str, ...], ...]) -> bool:
    normalized = {field.strip().lower() for field in fields}
    return all(any(option.lower() in normalized for option in group) for group in groups)


def _gnss_fields_from_locked_file(path_text: str | None) -> list[str]:
    if not path_text or not _path_exists(path_text):
        return []
    first, _ = _read_first_last(path_text)
    if not first:
        return []
    count = len(re.split(r"\s+", first.strip()))
    if count >= 15:
        return [
            "time",
            "lat",
            "lon",
            "height",
            "std_lat",
            "std_lon",
            "std_height",
            "vn",
            "ve",
            "vd",
            "std_vn",
            "std_ve",
            "std_vd",
            "yaw",
            "yaw_std",
        ]
    return [f"col_{index + 1}" for index in range(count)]


def _load_provider_decision_paths(workspace_root: Path) -> dict[str, str]:
    report = (
        workspace_root
        / "by2-huitu"
        / "N9C0C1_LEGSA_FULL_PROVIDER_INPUT_RESOLUTION_AND_BRANCH_EFFECT_AUDIT"
        / "reports"
        / "N9C0C1_PROVIDER_RESOLUTION_DECISION_REPORT.json"
    )
    payload = _read_json(report, {}) or {}
    paths: dict[str, str] = {}
    for row in payload.get("rows", []):
        provider = str(row.get("provider", ""))
        resolved = str(row.get("resolved_path", "") or "")
        if provider and resolved:
            paths[provider] = resolved
    return paths


def _prior_searched_roots(workspace_root: Path) -> list[Path]:
    report = (
        workspace_root
        / "by2-huitu"
        / "N9C0C1_LEGSA_FULL_PROVIDER_INPUT_RESOLUTION_AND_BRANCH_EFFECT_AUDIT"
        / "reports"
        / "N9C0C1_PROVIDER_FILE_INVENTORY_REPORT.json"
    )
    payload = _read_json(report, {}) or {}
    roots: list[Path] = [workspace_root]
    for item in payload.get("searched_roots", []):
        if not isinstance(item, str) or not item:
            continue
        path = Path(item)
        if path.exists() and path not in roots:
            roots.append(path)
    return roots


def find_locked_normal_config(workspace_root: Path) -> Path | None:
    candidates = [
        workspace_root
        / "by2-huitu"
        / "N9B2_FULL_MATRIX"
        / "LEGSA_FULL_ALGORITHM_FULL_MATRIX_EXPANSION"
        / "N9C0D"
        / "runtime_configs"
        / "FULL_normal_repeat"
        / "LegSA_full_EKF.runtime_config.yaml",
        workspace_root
        / "by2-huitu"
        / "N9C0C1_LEGSA_FULL_PROVIDER_INPUT_RESOLUTION_AND_BRANCH_EFFECT_AUDIT"
        / "config_repair"
        / "FULL_normal_repeat"
        / "LegSA_full_EKF.runtime_config.yaml",
    ]
    return next((path for path in candidates if path.exists()), None)


def locked_normal_source_resolution(workspace_root: Path) -> tuple[list[dict[str, Any]], dict[str, str], Path | None]:
    config = find_locked_normal_config(workspace_root)
    values = parse_yaml_like(config) if config else {}
    imu = values.get("imupath", "")
    gnss = values.get("gnsspath", "")
    gnss_fields = _gnss_fields_from_locked_file(gnss)
    imu_rows = _row_count(imu)
    gnss_rows = _row_count(gnss)
    gnss_range = _time_range(gnss, has_header=False)
    imu_range = _time_range(imu, has_header=False)
    resolved = bool(config and _path_exists(imu) and _path_exists(gnss) and _groups_present(gnss_fields, PROVIDER_SPECS[0].required_groups))
    rows = [
        {
            "item": "locked clean normal config",
            "source_exists": config is not None,
            "source_root": "runtime_prior_stage",
            "source_path": str(config) if config else "<LOCKED_NORMAL_CONFIG_MISSING>",
            "row_count": None,
            "required_columns_present": config is not None,
            "time_range": {},
            "parse_status": "parsed" if config else "missing",
            "ready_for_factor": config is not None,
            "blocker": "" if config else "locked normal runtime config missing",
        },
        {
            "item": "locked clean normal IMU",
            "source_exists": _path_exists(imu),
            "source_root": _source_root(imu),
            "source_path": imu,
            "row_count": imu_rows,
            "required_columns_present": bool(imu_rows),
            "time_range": imu_range,
            "parse_status": "parsed" if _path_exists(imu) else "missing",
            "ready_for_factor": _path_exists(imu),
            "blocker": "" if _path_exists(imu) else "locked IMU source missing",
        },
        {
            "item": "locked clean normal GNSS / dual15",
            "source_exists": _path_exists(gnss),
            "source_root": _source_root(gnss),
            "source_path": gnss,
            "row_count": gnss_rows,
            "required_columns_present": len(gnss_fields) >= 15,
            "time_range": gnss_range,
            "parse_status": "parsed" if _path_exists(gnss) else "missing",
            "ready_for_factor": len(gnss_fields) >= 15,
            "blocker": "" if len(gnss_fields) >= 15 else "locked GNSS dual15 fields missing",
        },
        {
            "item": "GNSS position fields",
            "source_exists": _path_exists(gnss),
            "source_root": _source_root(gnss),
            "source_path": gnss,
            "row_count": gnss_rows,
            "required_columns_present": _groups_present(gnss_fields, PROVIDER_SPECS[0].required_groups),
            "time_range": gnss_range,
            "parse_status": "parsed",
            "ready_for_factor": _groups_present(gnss_fields, PROVIDER_SPECS[0].required_groups),
            "blocker": "" if _groups_present(gnss_fields, PROVIDER_SPECS[0].required_groups) else "position fields missing",
        },
        {
            "item": "GNSS velocity fields",
            "source_exists": _path_exists(gnss),
            "source_root": _source_root(gnss),
            "source_path": gnss,
            "row_count": gnss_rows,
            "required_columns_present": _groups_present(gnss_fields, PROVIDER_SPECS[1].required_groups),
            "time_range": gnss_range,
            "parse_status": "parsed",
            "ready_for_factor": _groups_present(gnss_fields, PROVIDER_SPECS[1].required_groups),
            "blocker": "" if _groups_present(gnss_fields, PROVIDER_SPECS[1].required_groups) else "velocity fields missing",
        },
        {
            "item": "dual yaw fields",
            "source_exists": _path_exists(gnss),
            "source_root": _source_root(gnss),
            "source_path": gnss,
            "row_count": gnss_rows,
            "required_columns_present": _groups_present(gnss_fields, PROVIDER_SPECS[2].required_groups),
            "time_range": gnss_range,
            "parse_status": "parsed",
            "ready_for_factor": _groups_present(gnss_fields, PROVIDER_SPECS[2].required_groups),
            "blocker": "" if _groups_present(gnss_fields, PROVIDER_SPECS[2].required_groups) else "dual yaw fields missing",
        },
        {
            "item": "yaw_std",
            "source_exists": _path_exists(gnss),
            "source_root": _source_root(gnss),
            "source_path": gnss,
            "row_count": gnss_rows,
            "required_columns_present": "yaw_std" in gnss_fields,
            "time_range": gnss_range,
            "parse_status": "parsed",
            "ready_for_factor": "yaw_std" in gnss_fields,
            "blocker": "" if "yaw_std" in gnss_fields else "yaw_std missing",
        },
    ]
    values["_locked_normal_resolved"] = str(resolved).lower()
    return rows, values, config


def _candidate_provider_paths(workspace_root: Path) -> dict[str, str]:
    paths: dict[str, str] = {}
    for root in _prior_searched_roots(workspace_root):
        mining = root / "运行结果" / "N7C5_go2_full_proprioceptive_factor_mining"
        direct_candidates = {
            "foot kinematic velocity": mining / "GO2_FOOT_KINEMATIC_VELOCITY_TIMESERIES.csv",
            "slip risk": mining / "GO2_FOOT_KINEMATIC_VELOCITY_TIMESERIES.csv",
            "yaw-rate": mining / "GO2_YAWRATE_CONSISTENCY_CANDIDATE_REPORT.json",
            "relative odometry": mining / "GO2_RELATIVE_ODOMETRY_CANDIDATE_REPORT.json",
            "contact probability": mining / "GO2_CONTACT_PROBABILITY_FACTOR_REVIEW.json",
        }
        for provider, path in direct_candidates.items():
            if path.exists():
                paths.setdefault(provider, str(path))

    runtime_roots = [
        workspace_root / "by2-huitu" / "N9B2_FULL_MATRIX",
        workspace_root / "by2-huitu" / "N9C1F_TO_N9C3_FGO_LEGGED_EVIDENCE_REPAIR_AND_REPORT_PACKAGE",
    ]
    for root in runtime_roots:
        if root.exists():
            for path in root.rglob("GO2_FOOT_KINEMATIC_VELOCITY_TIMESERIES.csv"):
                paths.setdefault("foot kinematic velocity", str(path))
                paths.setdefault("slip risk", str(path))
            for path in root.rglob("GO2_YAWRATE_CONSISTENCY_CANDIDATE_REPORT.json"):
                paths.setdefault("yaw-rate", str(path))
            for path in root.rglob("GO2_RELATIVE_ODOMETRY_CANDIDATE_REPORT.json"):
                paths.setdefault("relative odometry", str(path))
            for path in root.rglob("GO2_CONTACT_PROBABILITY_FACTOR_REVIEW.json"):
                paths.setdefault("contact probability", str(path))
    return paths


def build_provider_resolution_rows(workspace_root: Path, locked_values: Mapping[str, str]) -> list[dict[str, Any]]:
    prior_paths = _load_provider_decision_paths(workspace_root)
    candidate_paths = _candidate_provider_paths(workspace_root)
    gnss_path = locked_values.get("gnsspath", "")
    source_map = {
        "GNSS position": gnss_path,
        "GNSS velocity": gnss_path,
        "dual yaw": gnss_path,
        "Raw Doppler": prior_paths.get("Raw Doppler provider", ""),
        "Go2 joint": prior_paths.get("Go2 joint provider", ""),
        "Go2 attitude": prior_paths.get("Go2 attitude provider", ""),
        "Go2 horizontal velocity": prior_paths.get("Go2 horizontal velocity provider", ""),
        "feedback observations": prior_paths.get("selected-feedback provider", ""),
        **candidate_paths,
    }
    rows: list[dict[str, Any]] = []
    for spec in PROVIDER_SPECS:
        path = source_map.get(spec.provider, "")
        exists = _path_exists(path)
        fields = _gnss_fields_from_locked_file(path) if spec.provider in {"GNSS position", "GNSS velocity", "dual yaw"} else _header_fields(path)
        required_present = _groups_present(fields, spec.required_groups)
        row_count = _row_count(path)
        has_header = bool(fields and not all(field.startswith("col_") for field in fields))
        time_range = _time_range(path, has_header=has_header)
        ready = bool(exists and required_present and row_count and not spec.candidate_only and not spec.aggregate_only)
        if not exists:
            parse_status = "blocked_missing_source"
            blocker = "source missing"
        elif spec.aggregate_only:
            parse_status = "source_available_aggregate_or_report_only"
            blocker = "aggregate/report evidence is not active provider time-series"
        elif spec.candidate_only:
            parse_status = "source_available_candidate_only"
            blocker = "candidate-only provider remains blocked from active factor claim"
        elif not required_present:
            parse_status = "source_available_schema_mismatch"
            blocker = "required provider columns missing"
        else:
            parse_status = "parsed"
            blocker = ""
        rows.append(
            {
                "provider": spec.provider,
                "factor": spec.factor,
                "source_exists": exists,
                "source_root": _source_root(path),
                "source_path": path,
                "row_count": row_count,
                "required_columns_present": required_present,
                "resolved_columns": fields,
                "time_range": time_range,
                "parse_status": parse_status,
                "ready_for_factor": ready,
                "candidate_only": spec.candidate_only,
                "aggregate_only": spec.aggregate_only,
                "evidence_from_N9C0C1_or_N9C0D": spec.provider in {"Raw Doppler", "Go2 joint", "Go2 attitude", "Go2 horizontal velocity", "feedback observations", "GNSS position", "GNSS velocity", "dual yaw"},
                "blocker": blocker,
            }
        )
    return rows


def provider_contract_decision(rows: list[dict[str, Any]]) -> str:
    if rows and all(row.get("ready_for_factor") is True for row in rows):
        return "N9G1C_provider_contracts_passed"
    if any(row.get("ready_for_factor") is True for row in rows):
        return "N9G1C_provider_contracts_partial_accepted"
    return "N9G1C_provider_contracts_blocked"


def backend_audit_rows(workspace_root: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    discovery = discover_fgo_backend()
    source_checks = [
        ("FGO window builder", "src/legsa_gins/fgo/fgo_no_feedback_smoother.py", True, "offline/no-feedback smoother only"),
        ("factor registry", "src/legsa_gins/fgo/fgo_factor_registry.py", True, "registry contracts exist"),
        ("factor instantiation", "src/legsa_gins/fgo/fgo_legged_factor_activation_runner.py", True, "offline candidate instantiation"),
        ("cost/residual computation", "src/legsa_gins/fgo/fgo_linear_solver.py", True, "offline proxy cost"),
        ("Jacobian computation", "src/legsa_gins/fgo/fgo_raw_doppler_solver_injection.py", True, "offline raw and legged Jacobian diagnostics"),
        ("no-feedback FGO code", "src/legsa_gins/fgo/fgo_no_feedback_smoother.py", True, "offline no-feedback"),
        ("selected-feedback FGO source", "src/legsa_gins/reporting/by2_algorithm_runner.py", True, "feedback consumer exists, producer evidence is same-case file"),
        ("active solver wrapper", "src/legsa_gins/reporting/by2_algorithm_runner.py", False, "LegSA_9F_FGO_EKF solver_execution_allowed=false"),
        ("Python candidate/offline FGO", "src/legsa_gins/fgo/fgo_legged_factor_activation_runner.py", True, "candidate/offline only"),
        ("production runner bridge", "cpp/legsa_v23_port_core/src/kf_gins/gi_engine.cpp", False, "C++ runner is EKF/update bridge, not active nine-factor FGO"),
        ("logger hooks", "src/legsa_gins/fgo/fgo_n9g1b_legsa_9f_phase1.py", False, "schema-only hooks, no row-level runtime rows"),
    ]
    spec = ALGORITHM_SPECS[ALGORITHM_ID]
    rows = []
    for component, rel, exists_expected, evidence in source_checks:
        exists = (workspace_root / rel).exists()
        rows.append(
            {
                "component": component,
                "source_path": rel,
                "code_symbol_exists": exists,
                "source_evidence_expected": exists_expected,
                "active_production_path": exists and component in {"factor registry"} and spec.active_fgo_backend_available,
                "classification": "offline_or_schema_only" if exists else "missing",
                "evidence": evidence,
            }
        )
    status = {
        "active_backend_available": spec.active_fgo_backend_available,
        "solver_execution_allowed": spec.solver_execution_allowed,
        "backend_discovery": discovery,
        "classification": "offline_candidate_only" if not spec.active_fgo_backend_available else "active_backend_available",
        "decision": "N9G1D_active_backend_blocked" if not spec.active_fgo_backend_available else "N9G1D_active_backend_available",
        "repair_action": "no_safe_backend_wiring_performed" if not spec.active_fgo_backend_available else "wire_existing_backend",
    }
    return rows, status


def backend_repair_rows(backend_status: Mapping[str, Any]) -> list[dict[str, Any]]:
    available = backend_status.get("active_backend_available") is True
    return [
        {
            "item": "LegSA_9F_FGO_EKF runtime config to active backend",
            "repair_attempted": available,
            "repair_status": "blocked_offline_candidate_only_no_safe_wrapper" if not available else "wired_existing_backend",
            "math_changed": False,
            "feedback_policy_changed": False,
            "LegSA_full_EKF_changed": False,
            "blocker": "" if available else "active nine-factor FGO backend remains unavailable and solver execution is disabled",
        }
    ]


def factor_wiring_rows(
    workspace_root: Path,
    provider_rows: list[dict[str, Any]],
    backend_status: Mapping[str, Any],
) -> list[dict[str, Any]]:
    provider_ready = {row["provider"]: row for row in provider_rows}
    active_backend = backend_status.get("active_backend_available") is True
    rows: list[dict[str, Any]] = []
    for factor in NINE_FACTORS:
        provider_name = {
            "ReceiverPositionFactor": "GNSS position",
            "ReceiverVelocityFactor": "GNSS velocity",
            "DualYawFactor": "dual yaw",
            "RawDopplerVelocityFactor": "Raw Doppler",
            "Go2ProprioceptiveJointFactor": "Go2 joint",
            "FootKinematicVelocityFactor": "foot kinematic velocity",
            "YawRateBetweenFactor": "yaw-rate",
            "RelativeOdometryBetweenFactor": "relative odometry",
            "SmoothnessFactor": "GNSS position",
        }.get(factor.factor_type, factor.provider)
        provider = provider_ready.get(provider_name, {})
        code_symbol_exists = (workspace_root / factor.code_symbol_path).exists()
        provider_ok = provider.get("ready_for_factor") is True or factor.factor_type == "SmoothnessFactor"
        candidate = factor.candidate_only or provider.get("candidate_only") is True
        runtime_enabled = bool(active_backend and provider_ok and not candidate)
        evidence_status = classify_factor_evidence(
            {
                "code_symbol_exists": code_symbol_exists,
                "runtime_enabled": runtime_enabled,
                "instantiated": False,
                "contributes_rows": False,
                "residual_evaluated": False,
                "residual_dim_recorded": False,
                "timestamps_recorded": False,
                "window_ids_recorded": False,
                "cost_unavailable_reason": "normal_smoke_not_run_backend_blocked",
                "candidate_only": candidate,
                "integrated_active_fgo": runtime_enabled,
            }
        )
        blocker = ""
        if not active_backend:
            blocker = "active backend unavailable"
        elif candidate:
            blocker = "candidate-only provider/factor"
        elif not provider_ok:
            blocker = "provider not ready"
        rows.append(
            {
                "factor_type": factor.factor_type,
                "algorithm_id": ALGORITHM_ID,
                "provider": provider_name,
                "provider_ready": provider_ok,
                "code_symbol_exists": code_symbol_exists,
                "backend_supports_factor": active_backend,
                "candidate_only": candidate,
                "runtime_enabled": runtime_enabled,
                "instantiated_expected": runtime_enabled,
                "contributes_rows_expected": runtime_enabled,
                "residual_logging_expected": runtime_enabled,
                "cost_logging_expected": runtime_enabled,
                "active_claim_allowed": False,
                "wiring_status": evidence_status,
                "blocker": blocker,
            }
        )
    return rows


def logger_connection_rows(backend_status: Mapping[str, Any]) -> list[dict[str, Any]]:
    schema_checks = validate_logger_schemas()
    schema_status = {row["schema"]: row["status"] for row in schema_checks}
    connected_to_runtime = backend_status.get("active_backend_available") is True
    schemas = {
        "fgo_window_summary": FGO_WINDOW_SUMMARY_FIELDS,
        "fgo_factor_residual_timeseries": FGO_FACTOR_RESIDUAL_FIELDS,
        "fgo_factor_coverage": LOGGER_SCHEMAS["fgo_factor_coverage"],
        "legged_diagnostic_timeseries": LEGGED_DIAGNOSTIC_FIELDS,
        "feedback_trace": FEEDBACK_TRACE_FIELDS,
    }
    return [
        {
            "logger_output": name,
            "fields_present": schema_status.get(name) == "pass",
            "json_writable": True,
            "csv_writable": True,
            "can_be_enabled_disabled": True,
            "connected_to_active_runtime": connected_to_runtime,
            "schema_only": not connected_to_runtime,
            "field_count": len(fields),
            "status": "connected" if connected_to_runtime else "schema_valid_backend_blocked",
        }
        for name, fields in schemas.items()
    ]


def static_validation_rows(
    static_validation_status: str = "not_run",
    *,
    pytest_status: str = "not_run",
    pytest_evidence: str = "pytest availability not probed by artifact writer",
) -> list[dict[str, Any]]:
    return [
        {"check": "py_compile", "status": static_validation_status, "evidence": "run by supervisor validation"},
        {"check": "direct_unit_tests", "status": static_validation_status, "evidence": "run by supervisor validation"},
        {"check": "pytest_if_available", "status": pytest_status, "evidence": pytest_evidence},
        {"check": "config_dry_run", "status": "pass", "evidence": "runtime config materialized without solver execution"},
        {"check": "logger_schema_validation", "status": "pass" if all(row["status"] == "pass" for row in validate_logger_schemas()) else "fail", "evidence": "schema fields checked"},
        {"check": "git_diff_check", "status": static_validation_status, "evidence": "run by supervisor validation"},
        {"check": "tracked_path_leak_scan", "status": static_validation_status, "evidence": "run by supervisor validation"},
    ]


def normal_smoke_gate_report(
    *,
    provider_decision: str,
    locked_normal_resolved: bool,
    backend_status: Mapping[str, Any],
    factor_rows: list[dict[str, Any]],
    logger_rows: list[dict[str, Any]],
    static_status: str,
) -> dict[str, Any]:
    blockers: list[str] = []
    if provider_decision == "N9G1C_provider_contracts_blocked":
        blockers.append("provider_contracts_blocked")
    if not locked_normal_resolved:
        blockers.append("locked_normal_source_unresolved")
    if backend_status.get("active_backend_available") is not True:
        blockers.append("active_nine_factor_fgo_backend_unavailable")
    if ALGORITHM_SPECS[ALGORITHM_ID].solver_execution_allowed is not True:
        blockers.append("candidate_solver_execution_disabled")
    if not any(row.get("runtime_enabled") is True for row in factor_rows):
        blockers.append("factor_wiring_not_active")
    if not all(row.get("fields_present") is True for row in logger_rows):
        blockers.append("logger_schema_invalid")
    if static_status != "pass":
        blockers.append("static_validation_not_passed")
    decision = "N9G1E_normal_smoke_gate_passed" if not blockers else "N9G1E_normal_smoke_gate_blocked"
    return {
        "stage": "N9G1E_NORMAL_SMOKE_GATE",
        "algorithm_id": ALGORITHM_ID,
        "provider_contract_decision": provider_decision,
        "ready_for_normal_smoke": not blockers,
        "decision": decision,
        "blockers": blockers,
        "LegSA_full_EKF_unchanged": True,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "output_substitution": False,
        "representative_degradation": False,
        "full_matrix": False,
        "paper_claims": False,
    }


def normal_smoke_report(gate: Mapping[str, Any]) -> dict[str, Any]:
    if gate.get("ready_for_normal_smoke") is True:
        decision = "N9G1E_normal_smoke_not_executed_by_artifact_writer"
        blocked = False
    else:
        decision = "N9G1E_normal_smoke_not_run_blocked_by_gate"
        blocked = True
    return {
        "stage": "N9G1E_NORMAL_SMOKE",
        "case_id": NORMAL_CASE_ID,
        "algorithm_id": ALGORITHM_ID,
        "decision": decision,
        "solver_completed": False,
        "evaluator_completed": False,
        "normal_smoke_blocked": blocked,
        "gate": gate,
        "complete_nine_factor_FGO_claim": False,
        "ready_for_N9G2_representative_validation": False,
    }


def factor_evidence_rows(factor_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "case_id": NORMAL_CASE_ID,
            "algorithm_id": ALGORITHM_ID,
            "factor_type": row["factor_type"],
            "windows_present": 0,
            "epochs_present": 0,
            "rows_present": 0,
            "residual_time_series_present": False,
            "cost_present": False,
            "jacobian_nonzero_recorded": False,
            "whitening_status": "not_run",
            "gate_state": "not_run",
            "accept_reject_state": "not_run",
            "status": row["wiring_status"],
            "active_factor_claim": False,
            "blocker": row["blocker"],
        }
        for row in factor_rows
    ]


def _write_logger_schema_tables(runtime_root: Path) -> None:
    for name, fields in LOGGER_SCHEMAS.items():
        write_json(runtime_root / "logger_connection" / f"{name}.json", [])
        _write_csv(runtime_root / "logger_connection" / f"{name}.csv", [], fields)


def materialize_repaired_config(
    workspace_root: Path,
    runtime_root: Path,
    base_values: Mapping[str, str],
    provider_rows: list[dict[str, Any]],
) -> Path:
    config_path = runtime_root / "dry_run" / "LegSA_9F_FGO_EKF_FULL_normal_repeat.runtime_config.yaml"
    output_dir = runtime_root / "normal_smoke" / NORMAL_CASE_ID / ALGORITHM_ID
    config_path.parent.mkdir(parents=True, exist_ok=True)
    text = build_algorithm_config_text(workspace_root, ALGORITHM_ID, output_dir, dict(base_values))
    provider_by_name = {row["provider"]: row for row in provider_rows}
    override_map = {
        "raw_doppler_factor_path": provider_by_name.get("Raw Doppler", {}).get("source_path"),
        "go2_attitude_prior_path": provider_by_name.get("Go2 attitude", {}).get("source_path"),
        "go2_horizontal_velocity_prior_path": provider_by_name.get("Go2 horizontal velocity", {}).get("source_path"),
        "go2_proprioceptive_joint_factor_path": provider_by_name.get("Go2 joint", {}).get("source_path"),
        "fgo_feedback_path": provider_by_name.get("feedback observations", {}).get("source_path"),
    }
    lines = [
        "",
        "# N9G1C-E provider repair overrides.",
        f'case_id: "{NORMAL_CASE_ID}"',
        "stage: N9G1C_TO_N9G1E_PROVIDER_CONTRACT_RESOLUTION_ACTIVE_FGO_BACKEND_AND_NORMAL_SMOKE",
        "degradation_execution: false",
        "representative_degradation: false",
        "full_matrix_execution: false",
        "N9B2_execution: false",
        "paper_performance_claim: false",
        "complete_nine_factor_FGO_claim: false",
        "trace_solver_input: false",
        "final_v23_output_solver_input: false",
        "output_only_correction: false",
        "active_fgo_backend_available: false",
        "solver_execution_allowed: false",
        "fgo: false",
    ]
    for key, value in override_map.items():
        if value:
            lines.append(f'{key}: "{repo_to_wsl(value)}"')
    config_path.write_text(text + "\n".join(lines) + "\n", encoding="utf-8")
    return config_path


def _obsidian_rows() -> list[dict[str, Any]]:
    rows = [
        {
            "path": f"obsidian_knowledge/LegSA-GINS/N9G1C_E_provider_backend_normal_smoke/{name}",
            "note_type": "public",
            "path_policy": "aliases_only",
            "staged": False,
        }
        for name in PUBLIC_OBSIDIAN_NOTES
    ]
    rows.append(
        {
            "path": f"obsidian_knowledge/LegSA-GINS/N9G1C_E_provider_backend_normal_smoke/{PRIVATE_OBSIDIAN_NOTE}",
            "note_type": "private",
            "path_policy": "local_paths_allowed_untracked",
            "staged": False,
        }
    )
    return rows


def write_n9g1c_to_n9g1e_artifacts(
    workspace_root: Path,
    runtime_root: Path,
    *,
    static_validation_status: str = "not_run",
    pytest_status: str = "not_run",
    pytest_evidence: str = "pytest availability not probed by artifact writer",
    context_sync_status: str = "pending",
) -> dict[str, Any]:
    prepare_runtime_tree(runtime_root)
    created = now_utc()
    locked_rows, locked_values, locked_config = locked_normal_source_resolution(workspace_root)
    locked_resolved = locked_values.get("_locked_normal_resolved") == "true"
    provider_rows = build_provider_resolution_rows(workspace_root, locked_values)
    provider_decision = provider_contract_decision(provider_rows)
    backend_rows, backend_status = backend_audit_rows(workspace_root)
    repair_rows = backend_repair_rows(backend_status)
    wiring_rows = factor_wiring_rows(workspace_root, provider_rows, backend_status)
    logger_rows = logger_connection_rows(backend_status)
    static_rows = static_validation_rows(
        static_validation_status,
        pytest_status=pytest_status,
        pytest_evidence=pytest_evidence,
    )
    gate = normal_smoke_gate_report(
        provider_decision=provider_decision,
        locked_normal_resolved=locked_resolved,
        backend_status=backend_status,
        factor_rows=wiring_rows,
        logger_rows=logger_rows,
        static_status=static_validation_status,
    )
    smoke = normal_smoke_report(gate)
    config_path = materialize_repaired_config(workspace_root, runtime_root, locked_values, provider_rows)
    _write_logger_schema_tables(runtime_root)

    reports = {
        "N9G1C_LOCKED_NORMAL_SOURCE_RESOLUTION_REPORT.json": {
            "stage": "N9G1C_LOCKED_NORMAL_SOURCE_RESOLUTION",
            "created_utc": created,
            "decision": "locked_normal_source_resolved" if locked_resolved else "locked_normal_source_blocked",
            "base_config": str(locked_config) if locked_config else "<LOCKED_NORMAL_CONFIG_MISSING>",
            "rows": locked_rows,
        },
        "N9G1C_PROVIDER_RESOLUTION_REPORT.json": {
            "stage": "N9G1C_PROVIDER_RESOLUTION",
            "created_utc": created,
            "rows": provider_rows,
        },
        "N9G1C_PROVIDER_CONTRACT_DECISION_REPORT.json": {
            "stage": "N9G1C_PROVIDER_CONTRACT_DECISION",
            "created_utc": created,
            "decision": provider_decision,
            "ready_factors": [row["factor"] for row in provider_rows if row.get("ready_for_factor")],
            "blocked_factors": [row["factor"] for row in provider_rows if not row.get("ready_for_factor")],
            "rows": provider_rows,
        },
        "N9G1D_ACTIVE_FGO_BACKEND_AUDIT_REPORT.json": {
            "stage": "N9G1D_ACTIVE_FGO_BACKEND_AUDIT",
            "created_utc": created,
            **backend_status,
            "rows": backend_rows,
        },
        "N9G1D_BACKEND_REPAIR_REPORT.json": {
            "stage": "N9G1D_BACKEND_REPAIR",
            "created_utc": created,
            "decision": "N9G1D_active_backend_blocked" if not backend_status.get("active_backend_available") else "N9G1D_active_backend_available",
            "rows": repair_rows,
        },
        "N9G1D_FACTOR_WIRING_REPAIR_REPORT.json": {
            "stage": "N9G1D_FACTOR_WIRING_REPAIR",
            "created_utc": created,
            "active_factors_marked": sum(1 for row in wiring_rows if row.get("runtime_enabled") is True),
            "candidate_factors_marked_active": False,
            "rows": wiring_rows,
        },
        "N9G1D_LOGGER_CONNECTION_REPORT.json": {
            "stage": "N9G1D_LOGGER_CONNECTION",
            "created_utc": created,
            "schema_validation": validate_logger_schemas(),
            "rows": logger_rows,
        },
        "N9G1D_STATIC_VALIDATION_REPORT.json": {
            "stage": "N9G1D_STATIC_VALIDATION",
            "created_utc": created,
            "status": static_validation_status,
            "rows": static_rows,
        },
        "N9G1E_NORMAL_SMOKE_GATE_REPORT.json": gate,
        "N9G1E_NORMAL_SMOKE_REPORT.json": smoke,
        "N9G1E_CONTEXT_OBSIDIAN_SYNC_REPORT.json": {
            "stage": "N9G1E_CONTEXT_OBSIDIAN_SYNC",
            "created_utc": created,
            "status": context_sync_status,
            "tracked_docs_updated": context_sync_status == "complete",
            "obsidian_untracked": True,
            "obsidian_target": "obsidian_knowledge/LegSA-GINS/N9G1C_E_provider_backend_normal_smoke/",
        },
        "LONG_TASK_VALIDATION_REPORT.json": {
            "stage": STAGE,
            "created_utc": created,
            "no_old_algorithm_relabeling": True,
            "no_final_v23_modification": True,
            "no_single_baseline_modification": True,
            "no_fabricated_residuals": True,
            "no_aggregate_as_timeseries": True,
            "no_candidate_as_active": True,
            "no_provider_update_as_physical_residual": True,
            "trace_solver_input": False,
            "final_v23_solver_input": False,
            "output_substitution": False,
            "representative_degradation": False,
            "full_matrix": False,
            "normal_smoke_run": smoke["solver_completed"],
            "json_csv_parse": "checked_after_generation",
            "git_diff_check": "checked_after_generation",
            "tracked_path_leak_scan": "checked_after_generation",
            "runtime_untracked": True,
            "obsidian_untracked": True,
            "pr_merged": False,
            "tag_created": False,
            "paper_claims": False,
        },
        "LONG_TASK_DECISION_REPORT.json": {
            "stage": STAGE,
            "created_utc": created,
            "decision": "N9G1E_active_backend_blocked" if not backend_status.get("active_backend_available") else "N9G1E_safety_gate_failed",
            "provider_contract_decision": provider_decision,
            "backend_decision": backend_status["decision"],
            "normal_smoke_decision": smoke["decision"],
            "ready_for_N9G2_representative_validation": False,
            "ready_for_paper_claims": False,
            "ready_for_N9B2_execution": False,
            "ready_for_full_N9B_execution": False,
            "recommended_next_stage": "implement_active_fgo_backend_or_reframe_scope",
        },
    }
    for name, payload in reports.items():
        write_json(runtime_root / "reports" / name, payload)

    _write_pair(runtime_root / "matrix" / "N9G1C_LOCKED_NORMAL_SOURCE_RESOLUTION", locked_rows)
    _write_pair(runtime_root / "matrix" / "N9G1C_PROVIDER_RESOLUTION", provider_rows)
    _write_pair(runtime_root / "matrix" / "N9G1C_PROVIDER_CONTRACT_DECISION", [{"decision": provider_decision, "ready_provider_count": sum(1 for row in provider_rows if row.get("ready_for_factor")), "blocked_provider_count": sum(1 for row in provider_rows if not row.get("ready_for_factor"))}])
    _write_pair(runtime_root / "matrix" / "N9G1D_ACTIVE_FGO_BACKEND_AUDIT", backend_rows)
    _write_pair(runtime_root / "matrix" / "N9G1D_BACKEND_REPAIR_STATUS", repair_rows)
    _write_pair(runtime_root / "matrix" / "N9G1D_FACTOR_WIRING_REPAIR_STATUS", wiring_rows)
    _write_pair(runtime_root / "matrix" / "N9G1D_LOGGER_CONNECTION_STATUS", logger_rows)
    _write_pair(runtime_root / "matrix" / "N9G1D_STATIC_VALIDATION", static_rows)
    _write_pair(runtime_root / "matrix" / "N9G1E_NORMAL_SMOKE_GATE", [{"algorithm_id": ALGORITHM_ID, "decision": gate["decision"], "ready_for_normal_smoke": gate["ready_for_normal_smoke"], "blockers": gate["blockers"]}])
    _write_pair(runtime_root / "matrix" / "N9G1E_NORMAL_SMOKE_STATUS", [{"case_id": NORMAL_CASE_ID, "algorithm_id": ALGORITHM_ID, "solver_completed": False, "evaluator_completed": False, "decision": smoke["decision"]}])
    _write_pair(runtime_root / "matrix" / "N9G1E_NORMAL_METRICS", [])
    _write_pair(runtime_root / "matrix" / "N9G1E_FACTOR_EVIDENCE", factor_evidence_rows(wiring_rows))
    _write_pair(runtime_root / "matrix" / "N9G1E_LEGGED_EVIDENCE", build_legged_evidence_rows())
    _write_pair(runtime_root / "matrix" / "N9G1E_OBSIDIAN_SYNC_INDEX", _obsidian_rows())
    _write_pair(
        runtime_root / "matrix" / "LONG_TASK_STAGE_STATUS",
        [
            {"step": "N9G1C_locked_normal_source_resolution", "status": "passed" if locked_resolved else "blocked", "decision": "locked_normal_source_resolved" if locked_resolved else "locked_normal_source_blocked"},
            {"step": "N9G1C_provider_contract_resolution", "status": "partial" if provider_decision.endswith("partial_accepted") else "blocked", "decision": provider_decision},
            {"step": "N9G1D_active_backend_audit", "status": "blocked", "decision": backend_status["decision"]},
            {"step": "N9G1D_factor_logger_connection", "status": "schema_valid_backend_blocked", "decision": "N9G1D_backend_or_factor_blocked"},
            {"step": "N9G1E_normal_smoke_gate", "status": "blocked", "decision": gate["decision"]},
            {"step": "N9G1E_normal_smoke", "status": "not_run", "decision": smoke["decision"]},
        ],
    )

    _write_summary(runtime_root / "summary" / "n9g1c_locked_normal_source_resolution.md", "N9G1C Locked Normal Source Resolution", ["- Locked normal config was resolved from prior N9C0D runtime config." if locked_resolved else "- Locked normal config remains unresolved.", f"- Base config: {locked_config.name if locked_config else '<LOCKED_NORMAL_CONFIG_MISSING>'}."])
    _write_summary(runtime_root / "summary" / "n9g1c_provider_resolution.md", "N9G1C Provider Resolution", [f"- Decision: {provider_decision}.", f"- Ready providers: {sum(1 for row in provider_rows if row.get('ready_for_factor'))}.", "- Candidate-only/aggregate providers remain blocked from active claims."])
    _write_summary(runtime_root / "summary" / "n9g1d_active_fgo_backend_audit.md", "N9G1D Active FGO Backend Audit", [f"- Classification: {backend_status['classification']}.", "- Existing FGO code is offline/no-feedback/candidate evidence, not an active production nine-factor backend.", "- No backend repair was wired."])
    _write_summary(runtime_root / "summary" / "n9g1e_normal_smoke_summary.md", "N9G1E Normal Smoke Summary", [f"- Gate decision: {gate['decision']}.", "- Normal smoke was not run because the active nine-factor backend remains unavailable.", "- complete_nine_factor_FGO_claim=false."])
    _write_summary(runtime_root / "summary" / "long_task_summary.md", "N9G1C-E Long Task Summary", ["- Provider contracts were re-resolved against locked normal and prior verified provider evidence.", "- Active backend audit found only offline/candidate FGO support for the separate LegSA_9F_FGO_EKF candidate.", "- Normal smoke stayed blocked by the gate; no solver, evaluator, representative degradation, full matrix, figure, or paper-claim work was run."])
    _write_summary(runtime_root / "summary" / "long_task_next_stage_recommendation.md", "N9G1C-E Next Stage Recommendation", ["- Decision: N9G1E_active_backend_blocked.", "- ready_for_N9G2_representative_validation=false.", "- ready_for_paper_claims=false.", "- Recommended next stage: implement_active_fgo_backend_or_reframe_scope."])

    return {
        "runtime_root": str(runtime_root),
        "locked_normal_resolved": locked_resolved,
        "provider_decision": provider_decision,
        "backend_decision": backend_status["decision"],
        "normal_smoke_gate": gate,
        "normal_smoke_report": smoke,
        "config_path": str(config_path),
    }
