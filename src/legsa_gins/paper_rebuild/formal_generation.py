"""Fresh CLEAN1 provider generation from exact hash-locked BY2 sources."""

from __future__ import annotations

import bisect
import csv
import datetime as dt
import hashlib
import json
import math
import shutil
import struct
import subprocess
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from legsa_gins.input_generation.status_yaw_builder import build_a1_dual_diff_yaw_rows
from legsa_gins.input_generation.ubx_nav_pvt import extract_pvt_velocity_rows
from legsa_gins.raw_gnss.rtklib_doppler_helper_builder import (
    HELPER_C_FILES,
    HELPER_SOURCE,
    REQUIRED_SOURCE_FILES,
)
from legsa_gins.raw_gnss.rtklib_doppler_velocity_provider import run_rtklib_doppler_velocity_provider
from legsa_gins.raw_gnss.rtklib_solution_velocity_parser import (
    ecef_velocity_to_ned,
    parse_helper_velocity_csv,
)
from legsa_gins.raw_gnss.ubx_raw_binary_rebuilder import (
    iter_ubx_frames,
    parse_bytes_cell,
    rebuild_csv_to_ubx,
)

from .evidence import (
    BY2_BODY_RELATIVE_PATH,
    BY2_FIX_PREFIX,
    BY2_RAW_RELATIVE_PATHS,
    validate_provider_source_read_set,
)
from .formal_provider import (
    PINNED_RTKLIB_COMMIT,
    PINNED_RTKLIB_REMOTE,
    RAW_DOPPLER_COVARIANCE_POLICY,
    RAW_DOPPLER_TIME_CONVERSION,
    REQUIRED_FORMAL_PROVIDER_ROLES,
    MAINTAINED_SHARED_SOURCE_FILES,
    FormalProviderError,
    validate_raw_doppler_backend_report,
)
from .manifest import (
    git_code_state,
    read_hash_lock,
    sha256_file,
    sha256_text,
    verify_raw_sources,
    write_json_atomic,
)
from .paths import CleanPaths, guard_path
from .providers import generate_clean_by2_inputs, infer_source_day_base_time


FORMAL_RAW_DOPPLER_FIELDS = (
    "time",
    "source_time",
    "vn",
    "ve",
    "vd",
    "std_vn",
    "std_ve",
    "std_vd",
    "sat_count",
    "rtklib_solution_sat_count",
    "doppler_sat_count",
    "gdop_like",
    "provider_status",
    "valid",
    "quality",
    "quality_flag",
    "raw_doppler_backend_id",
    "obs_source_hash",
    "nav_source_hash",
    "conversion_config_hash",
    "covariance_policy",
)

RAW_DOPPLER_BACKEND_ID = "rtklib_b34_pntpos_estvel_fresh_gnss1_rawx_sfrbx"
CONVBIN_SOURCE_FILES = (
    "app/consapp/convbin/convbin.c",
    "app/consapp/convbin/gcc/makefile",
    "src/rtklib.h",
    "src/rtkcmn.c",
    "src/rinex.c",
    "src/sbas.c",
    "src/preceph.c",
    "src/rcvraw.c",
    "src/convrnx.c",
    "src/rtcm.c",
    "src/rtcm2.c",
    "src/rtcm3.c",
    "src/rtcm3e.c",
    "src/pntpos.c",
    "src/ephemeris.c",
    "src/ionex.c",
    "src/rcv/novatel.c",
    "src/rcv/ss2.c",
    "src/rcv/ublox.c",
    "src/rcv/crescent.c",
    "src/rcv/skytraq.c",
    "src/rcv/javad.c",
    "src/rcv/nvs.c",
    "src/rcv/binex.c",
    "src/rcv/rt17.c",
    "src/rcv/septentrio.c",
)

class FormalGenerationError(FormalProviderError):
    """Fresh provider generation stopped at a hard lineage or backend gate."""


def _run(command: list[str], *, cwd: Path, label: str, timeout: int = 600) -> subprocess.CompletedProcess[str]:
    try:
        result = subprocess.run(
            command,
            cwd=cwd,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise FormalGenerationError(f"{label} failed to launch: {exc}") from exc
    if result.returncode != 0:
        raise FormalGenerationError(f"{label} failed with returncode {result.returncode}: {result.stderr[-2000:]}")
    return result


def _git_value(root: Path, args: list[str]) -> str:
    return _run(["git", *args], cwd=root, label="pinned RTKLIB git audit", timeout=60).stdout.strip()


def resolve_pinned_rtklib_source(
    *,
    explicit_root: str | Path | None,
    materialize_root: str | Path | None,
) -> tuple[Path, str]:
    """Use one explicit root or create one exact pinned clone; never search."""

    if bool(explicit_root) == bool(materialize_root):
        raise FormalGenerationError("Choose exactly one RTKLIB source mode")
    if explicit_root:
        root = Path(explicit_root).resolve(strict=True)
        mode = "explicit_local_pinned_root"
    else:
        root = Path(materialize_root or "").resolve(strict=False)
        if root.exists():
            raise FormalGenerationError("Pinned RTKLIB materialization root already exists")
        root.parent.mkdir(parents=True, exist_ok=True)
        _run(
            ["git", "clone", "--no-checkout", PINNED_RTKLIB_REMOTE, str(root)],
            cwd=root.parent,
            label="pinned RTKLIB clone",
            timeout=900,
        )
        _run(["git", "checkout", "--detach", PINNED_RTKLIB_COMMIT], cwd=root, label="pinned RTKLIB checkout")
        mode = "clean_root_materialized_pinned"
    commit = _git_value(root, ["rev-parse", "HEAD"])
    remote = _git_value(root, ["remote", "get-url", "origin"])
    tracked_dirty = _git_value(root, ["status", "--porcelain", "--untracked-files=no"])
    if commit != PINNED_RTKLIB_COMMIT or remote.rstrip("/") != PINNED_RTKLIB_REMOTE.rstrip("/"):
        raise FormalGenerationError("Explicit RTKLIB root does not match pinned remote/commit")
    if tracked_dirty:
        raise FormalGenerationError("Pinned RTKLIB tracked source is dirty")
    return root, mode


def _build_exact_rtklib_doppler_helper(rtklib_root: Path, output_root: Path) -> dict[str, Any]:
    """Compile only the exact pinned src paths; never discover, patch, or substitute files."""

    source_root = rtklib_root / "src"
    source_paths: dict[str, Path] = {}
    for name in REQUIRED_SOURCE_FILES:
        candidate = source_root / name
        if not candidate.is_file():
            raise FormalGenerationError(f"Pinned RTKLIB exact source is missing: src/{name}")
        source_paths[name] = candidate
    output_root.mkdir(parents=True, exist_ok=False)
    helper_source = output_root / "legsa_clean1_rtklib_doppler_helper.c"
    helper_exe = output_root / "legsa_clean1_rtklib_doppler_helper"
    helper_source.write_text(HELPER_SOURCE.strip() + "\n", encoding="utf-8")
    command = [
        "gcc",
        "-O2",
        "-I",
        str(source_root),
        "-o",
        str(helper_exe),
        str(helper_source),
        *[str(source_paths[name]) for name in HELPER_C_FILES],
        "-lm",
        "-lpthread",
    ]
    _run(command, cwd=output_root, label="exact pinned RTKLIB Doppler helper build")
    if not helper_exe.is_file():
        raise FormalGenerationError("Exact pinned RTKLIB helper executable is missing")
    return {
        "helper_compile_status": "success",
        "helper_executable_path": str(helper_exe),
        "helper_source_path": str(helper_source),
        "helper_source_hash": sha256_file(helper_source),
        "exact_compiled_rtklib_source_files": [f"src/{name}" for name in HELPER_C_FILES],
        "compile_command": command,
        "runtime_patch_applied": [],
        "source_discovery_used": False,
    }


def _source_gps_time_contract(raw_path: Path) -> dict[str, int]:
    """Decode GPS week/leap seconds from hash-locked UBX-NAV-TIMEGPS bytes."""

    with raw_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if "data" not in (reader.fieldnames or ()) or "name" not in (reader.fieldnames or ()):
            raise FormalGenerationError("GNSS1 raw source lacks UBX name/data columns")
        for row in reader:
            if (row.get("name") or "").upper() != "UBX-NAV-TIMEGPS":
                continue
            for frame in iter_ubx_frames(parse_bytes_cell(row.get("data", ""))):
                if frame[2:4] != b"\x01\x20":
                    continue
                payload = frame[6:-2]
                if len(payload) < 16:
                    continue
                _, _, gps_week, leap_seconds, valid, _ = struct.unpack_from("<IihbBI", payload, 0)
                if gps_week > 0 and valid & 0x06 == 0x06 and 0 <= leap_seconds <= 64:
                    return {"gps_week": int(gps_week), "leap_seconds": int(leap_seconds)}
    raise FormalGenerationError("Hash-locked GNSS1 raw has no valid UBX-NAV-TIMEGPS week/leap contract")


def _first_source_position_and_time(status_path: Path, raw_path: Path) -> dict[str, Any]:
    gps_time = _source_gps_time_contract(raw_path)
    with status_path.open("r", encoding="utf-8-sig", newline="") as handle:
        for row_number, row in enumerate(csv.DictReader(handle), start=2):
            if str(row.get("pos_valid") or "").casefold() not in {"true", "1"}:
                continue
            try:
                values = {
                    "lat_deg": float(row["pos_lat"]),
                    "lon_deg": float(row["pos_lon"]),
                    "height_m": float(row["pos_height"]),
                    "utc_year": int(row["utc_year"]),
                    "utc_month": int(row["utc_month"]),
                    "utc_day": int(row["utc_day"]),
                    "utc_hour": int(row["utc_hour"]),
                    "utc_minute": int(row["utc_minute"]),
                    "utc_second": float(row["utc_second"]),
                    "selected_status_row_number": row_number,
                    **gps_time,
                }
            except (KeyError, TypeError, ValueError) as exc:
                raise FormalGenerationError("GNSS1 status source position/time fields are invalid") from exc
            if all(math.isfinite(float(values[field])) for field in ("lat_deg", "lon_deg", "height_m")):
                identity = json.dumps(values, sort_keys=True, separators=(",", ":"))
                values["selected_status_fields_sha256"] = sha256_text(identity)
                return values
    raise FormalGenerationError("GNSS1 status has no valid source-backed approximate position")


def _gps_day_index(year: int, month: int, day: int) -> int:
    # Python Monday=0; GPS week starts Sunday=0.
    return (dt.date(year, month, day).weekday() + 1) % 7


def gpst_tow_to_clean_seconds_of_utc_day(source_tow: float, source: dict[str, Any]) -> float:
    clean_time = (
        source_tow
        - _gps_day_index(source["utc_year"], source["utc_month"], source["utc_day"]) * 86400.0
        - float(source["leap_seconds"])
    )
    if not math.isfinite(clean_time) or not 0.0 <= clean_time < 86400.0:
        raise FormalGenerationError("Source-backed GPST to UTC-day conversion left the UTC day")
    return clean_time


def _gdop_like(sat_count: int) -> float:
    return 99.0 if sat_count <= 4 else math.sqrt(1.0 / max(1, sat_count - 4))


def _write_formal_raw_doppler(
    helper_csv: Path,
    output_path: Path,
    *,
    source_position: dict[str, Any],
    obs_hash: str,
    nav_hash: str,
    conversion_config_hash: str,
    min_sat: int,
    std_floor_mps: float,
    covariance_policy: str,
) -> dict[str, Any]:
    raw_rows = parse_helper_velocity_csv(helper_csv)
    valid_rows: list[dict[str, Any]] = []
    for row in raw_rows:
        solution_sat_count = int(row["sat_count"])
        doppler_sat_count = int(row["doppler_obs_count"])
        if row["provider_status"] != "available" or doppler_sat_count < min_sat:
            continue
        vn, ve, vd = ecef_velocity_to_ned(
            float(row["vecef_x"]),
            float(row["vecef_y"]),
            float(row["vecef_z"]),
            source_position["lat_deg"],
            source_position["lon_deg"],
        )
        sigma = max(
            float(row["std_vx"]),
            float(row["std_vy"]),
            float(row["std_vz"]),
            std_floor_mps,
        )
        source_tow = float(row["source_epoch_time"])
        clean_time = gpst_tow_to_clean_seconds_of_utc_day(source_tow, source_position)
        if not all(math.isfinite(value) for value in (clean_time, vn, ve, vd, sigma)):
            continue
        valid_rows.append(
            {
                "time": f"{clean_time:.9f}",
                "source_time": f"{source_tow:.9f}",
                "vn": f"{vn:.9f}",
                "ve": f"{ve:.9f}",
                "vd": f"{vd:.9f}",
                "std_vn": f"{sigma:.6f}",
                "std_ve": f"{sigma:.6f}",
                "std_vd": f"{sigma:.6f}",
                "sat_count": doppler_sat_count,
                "rtklib_solution_sat_count": solution_sat_count,
                "doppler_sat_count": doppler_sat_count,
                "gdop_like": f"{_gdop_like(doppler_sat_count):.6f}",
                "provider_status": "available",
                "valid": 1,
                "quality": row["quality_flag"],
                "quality_flag": row["quality_flag"],
                "raw_doppler_backend_id": RAW_DOPPLER_BACKEND_ID,
                "obs_source_hash": obs_hash,
                "nav_source_hash": nav_hash,
                "conversion_config_hash": conversion_config_hash,
                "covariance_policy": covariance_policy,
            }
        )
    if not valid_rows:
        raise FormalGenerationError("BLOCKED_CLEAN1_RAW_DOPPLER_BACKEND_LINEAGE_NOT_PROVEN")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(FORMAL_RAW_DOPPLER_FIELDS))
        writer.writeheader()
        writer.writerows(valid_rows)
    sat_counts = sorted(int(row["sat_count"]) for row in valid_rows)
    return {
        "raw_epoch_count": len(raw_rows),
        "valid_epoch_count": len(valid_rows),
        "invalid_epoch_count": len(raw_rows) - len(valid_rows),
        "sat_count_min": sat_counts[0],
        "sat_count_median": sat_counts[len(sat_counts) // 2],
        "sat_count_max": sat_counts[-1],
    }


def _has_nearest_within(sorted_times: list[float], value: float, tolerance: float) -> bool:
    index = bisect.bisect_left(sorted_times, value)
    candidates = []
    if index > 0:
        candidates.append(sorted_times[index - 1])
    if index < len(sorted_times):
        candidates.append(sorted_times[index])
    return bool(candidates) and min(abs(candidate - value) for candidate in candidates) <= tolerance


def _upgrade_gnss_to_formal_18_columns(
    path: Path,
    *,
    gnss1_status: Path,
    gnss2_status: Path,
    gnss1_raw: Path,
    base_time: float,
    receiver_velocity_match_tolerance_seconds: float,
    dual_yaw_match_tolerance_seconds: float,
) -> dict[str, int]:
    """Append explicit validity while retaining numeric placeholders for invalid fields."""

    velocity_times = sorted(
        float(row["time"])
        for row in extract_pvt_velocity_rows(gnss1_raw, base_time=base_time, max_rows=None)
    )
    yaw_rows, _ = build_a1_dual_diff_yaw_rows(
        gnss1_status,
        gnss2_status,
        base_time=base_time,
        max_rows=None,
    )
    yaw_times = sorted(float(row["aligned_time"]) for row in yaw_rows)
    if not velocity_times or not yaw_times:
        raise FormalGenerationError("Formal validity registry lacks receiver-velocity or dual-yaw epochs")
    lines: list[str] = []
    counts = {
        "position_valid_count": 0,
        "receiver_velocity_valid_count": 0,
        "receiver_velocity_dropout_count": 0,
        "dual_yaw_valid_count": 0,
        "dual_yaw_dropout_count": 0,
    }
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            lines.append(line)
            continue
        fields = stripped.split()
        if len(fields) != 15:
            raise FormalGenerationError(f"Expected legacy clean 15-column GNSS row at line {number}")
        try:
            time_value = float(fields[0])
        except ValueError as exc:
            raise FormalGenerationError(f"Invalid formal GNSS timestamp at line {number}") from exc
        velocity_valid = int(
            _has_nearest_within(
                velocity_times, time_value, receiver_velocity_match_tolerance_seconds
            )
        )
        yaw_valid = int(
            _has_nearest_within(yaw_times, time_value, dual_yaw_match_tolerance_seconds)
        )
        counts["position_valid_count"] += 1
        counts["receiver_velocity_valid_count" if velocity_valid else "receiver_velocity_dropout_count"] += 1
        counts["dual_yaw_valid_count" if yaw_valid else "dual_yaw_dropout_count"] += 1
        lines.append(f"{stripped} 1 {velocity_valid} {yaw_valid}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return counts


def _write_source_quality(gnss_path: Path, output_path: Path) -> None:
    rows = []
    for line in gnss_path.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        fields = line.split()
        rows.append(
            {
                "time": fields[0],
                "position_valid": fields[15],
                "receiver_velocity_valid": fields[16],
                "dual_yaw_valid": fields[17],
                "source": "hash_locked_gnss_status_and_raw",
                "trace_used": False,
            }
        )
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def generate_formal_clean1_inputs(
    paths: CleanPaths,
    *,
    rtklib_source_root: str | Path | None = None,
    materialize_pinned_rtklib: bool = False,
    timeout_seconds: int = 900,
    provider_generation: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Generate the fresh provider once; no replace, fallback, or provider discovery."""

    provider_root = guard_path(paths.provider_root, role="CLEAN1 provider root", allowed_root=paths.clean_root)
    if provider_root.exists():
        raise FormalGenerationError("Fresh CLEAN1 provider root already exists")
    commit, dirty = git_code_state(paths.code_root)
    if dirty:
        raise FormalGenerationError("Formal provider generation requires a clean committed worktree")
    lock = read_hash_lock(paths.raw_hash_lock)
    by2_lock = {relative: row for relative, row in lock.items() if row.get("dataset") == "BY2"}
    if set(by2_lock) != set(BY2_RAW_RELATIVE_PATHS):
        raise FormalGenerationError("BLOCKED_CLEAN1_BY2_RAW_HASH_OR_ROLE_FAILED")
    locked_hashes = {relative: str(row.get("sha256") or "") for relative, row in by2_lock.items()}
    provider_source_relpaths = (
        f"{BY2_FIX_PREFIX}/gnss1-status.csv",
        f"{BY2_FIX_PREFIX}/gnss2-status.csv",
        f"{BY2_FIX_PREFIX}/gnss1-raw.csv",
        BY2_BODY_RELATIVE_PATH,
    )
    actual_verified = verify_raw_sources(paths.raw_root, provider_source_relpaths, lock)
    if any(actual_verified.get(relative) != locked_hashes.get(relative) for relative in provider_source_relpaths):
        raise FormalGenerationError("BLOCKED_CLEAN1_BY2_RAW_HASH_OR_ROLE_FAILED")
    verified = locked_hashes

    generation = dict(provider_generation or {})
    required_generation_fields = {
        "max_status_rows", "max_raw_rows", "max_imu_messages", "yaw_source_mode", "yaw_sign",
        "yaw_install_offset_deg", "yaw_std_mode", "status_fixed_yaw_std_deg",
        "receiver_velocity_match_tolerance_seconds", "dual_yaw_match_tolerance_seconds",
        "receiver_velocity_std_mps", "imu_install_roll_deg", "imu_install_pitch_deg",
        "imu_install_yaw_deg", "imu_gnss_time_offset_seconds", "go2_velocity_frame_transform",
        "go2_roll_pitch_std_deg", "go2_horizontal_velocity_std_mps", "outage_enabled",
        "raw_doppler_min_sat", "raw_doppler_std_floor_mps", "raw_doppler_covariance_policy",
        "outlier_mode", "yaw_noise_std_deg",
    }
    if set(generation) != required_generation_fields:
        raise FormalGenerationError("Tracked provider-generation contract is incomplete")
    if generation["yaw_source_mode"] != "status" or generation["yaw_std_mode"] != "fixed_1p5" or generation["outage_enabled"] is not False or generation["outlier_mode"] != "none" or float(generation["yaw_noise_std_deg"]) != 0.0:
        raise FormalGenerationError("Tracked provider-generation contract enables a forbidden mode")
    if (
        int(generation["raw_doppler_min_sat"]) <= 0
        or float(generation["raw_doppler_std_floor_mps"]) <= 0.0
        or generation["raw_doppler_covariance_policy"] != RAW_DOPPLER_COVARIANCE_POLICY
    ):
        raise FormalGenerationError("Tracked Raw Doppler generation policy is invalid")
    # Reuse only maintained, hash-recorded source helpers with every formerly implicit value explicit.
    base_manifest = generate_clean_by2_inputs(
        paths,
        max_status_rows=generation["max_status_rows"],
        max_raw_rows=generation["max_raw_rows"],
        max_imu_messages=generation["max_imu_messages"],
        replace=False,
        yaw_sign=float(generation["yaw_sign"]),
        yaw_install_offset_deg=float(generation["yaw_install_offset_deg"]),
        status_fixed_yaw_std_deg=float(generation["status_fixed_yaw_std_deg"]),
        receiver_velocity_match_tolerance_seconds=float(generation["receiver_velocity_match_tolerance_seconds"]),
        dual_yaw_match_tolerance_seconds=float(generation["dual_yaw_match_tolerance_seconds"]),
        receiver_velocity_std_mps=float(generation["receiver_velocity_std_mps"]),
        imu_install_roll_deg=float(generation["imu_install_roll_deg"]),
        imu_install_pitch_deg=float(generation["imu_install_pitch_deg"]),
        imu_install_yaw_deg=float(generation["imu_install_yaw_deg"]),
        imu_gnss_time_offset=float(generation["imu_gnss_time_offset_seconds"]),
        go2_velocity_frame_transform=str(generation["go2_velocity_frame_transform"]),
        go2_roll_pitch_std_deg=float(generation["go2_roll_pitch_std_deg"]),
        go2_horizontal_velocity_std_mps=float(generation["go2_horizontal_velocity_std_mps"]),
        stage_id="CLEAN1_BY2_CLEAN_FOUR_METHOD_EXECUTION",
    )
    gnss_path = provider_root / base_manifest["artifacts"]["gnss_runtime_input"]["relative_path"]
    gnss1_status = paths.by2_fix_root / "gnss1-status.csv"
    gnss2_status = paths.by2_fix_root / "gnss2-status.csv"
    raw_csv = paths.by2_fix_root / "gnss1-raw.csv"
    base_time = infer_source_day_base_time(gnss1_status)
    validity_report = _upgrade_gnss_to_formal_18_columns(
        gnss_path,
        gnss1_status=gnss1_status,
        gnss2_status=gnss2_status,
        gnss1_raw=raw_csv,
        base_time=base_time,
        receiver_velocity_match_tolerance_seconds=float(
            generation["receiver_velocity_match_tolerance_seconds"]
        ),
        dual_yaw_match_tolerance_seconds=float(
            generation["dual_yaw_match_tolerance_seconds"]
        ),
    )
    source_quality_path = provider_root / "providers" / "SOURCE_QUALITY_METADATA.csv"
    _write_source_quality(gnss_path, source_quality_path)

    materialize_root = provider_root / "tools" / "RTKLIB_PINNED_B34" if materialize_pinned_rtklib else None
    rtklib_root, rtklib_mode = resolve_pinned_rtklib_source(
        explicit_root=rtklib_source_root,
        materialize_root=materialize_root,
    )
    convbin_dir = rtklib_root / "app" / "consapp" / "convbin" / "gcc"
    preexisting_convbin_outputs = [
        path.name for path in convbin_dir.iterdir() if path.name == "convbin" or path.suffix == ".o"
    ]
    if preexisting_convbin_outputs:
        raise FormalGenerationError("Pinned RTKLIB convbin build root is not clean")
    _run(["make"], cwd=convbin_dir, label="pinned RTKLIB convbin build", timeout=timeout_seconds)
    convbin = convbin_dir / "convbin"
    if not convbin.is_file():
        raise FormalGenerationError("Pinned RTKLIB convbin executable was not built")

    raw_backend_root = provider_root / "raw_doppler_backend"
    raw_backend_root.mkdir(parents=True, exist_ok=True)
    rebuilt_ubx = raw_backend_root / "gnss1_rebuilt.ubx"
    rebuild_report = rebuild_csv_to_ubx(raw_csv, rebuilt_ubx)
    if not rebuild_report.get("rebuilt_ubx_available") or int(rebuild_report.get("rawx_frame_count") or 0) <= 0 or int(rebuild_report.get("sfrbx_frame_count") or 0) <= 0:
        raise FormalGenerationError("Hash-locked GNSS1 raw did not rebuild RAWX/SFRBX UBX")

    rinex_root = raw_backend_root / "rinex"
    rinex_root.mkdir()
    obs_path = rinex_root / "gnss1.obs"
    nav_path = rinex_root / "gnss1.nav"
    convbin_command = [
        str(convbin), "-r", "ubx", "-v", "3.04", "-od", "-os", "-oi", "-ot", "-ol",
        "-o", str(obs_path), "-n", str(nav_path), "-g", str(rinex_root / "gnss1.gnav"),
        "-h", str(rinex_root / "gnss1.hnav"), "-q", str(rinex_root / "gnss1.qnav"),
        "-l", str(rinex_root / "gnss1.lnav"), "-b", str(rinex_root / "gnss1.cnav"),
        "-i", str(rinex_root / "gnss1.inav"), str(rebuilt_ubx),
    ]
    _run(convbin_command, cwd=rinex_root, label="fresh pinned convbin conversion", timeout=timeout_seconds)
    if not obs_path.is_file() or not nav_path.is_file() or not obs_path.stat().st_size or not nav_path.stat().st_size:
        raise FormalGenerationError("Fresh convbin did not produce nonempty obs/nav")

    helper_report = _build_exact_rtklib_doppler_helper(rtklib_root, raw_backend_root / "helper")
    if helper_report.get("helper_compile_status") != "success" or helper_report.get("runtime_patch_applied") != []:
        raise FormalGenerationError("Formal RTKLIB helper failed or required a runtime patch")
    helper_exe = Path(helper_report["helper_executable_path"])
    retained_tools = raw_backend_root / "tools"
    retained_tools.mkdir()
    retained_convbin = retained_tools / "convbin_pinned_b34"
    shutil.copy2(convbin, retained_convbin)
    source_position = _first_source_position_and_time(gnss1_status, raw_csv)
    helper_run = run_rtklib_doppler_velocity_provider(
        obs_path=obs_path,
        nav_path=nav_path,
        helper_exe=helper_exe,
        approx_position_source={key: source_position[key] for key in ("lat_deg", "lon_deg", "height_m")},
        output_dir=raw_backend_root / "helper_run",
        min_sat=int(generation["raw_doppler_min_sat"]),
    )
    if helper_run.get("helper_run_status") != "success":
        raise FormalGenerationError("Fresh RTKLIB Doppler helper produced no valid velocity epochs")

    obs_hash = sha256_file(obs_path)
    nav_hash = sha256_file(nav_path)
    helper_hash = sha256_file(helper_exe)
    conversion_contract = {
        "rtklib_remote": PINNED_RTKLIB_REMOTE,
        "rtklib_commit": PINNED_RTKLIB_COMMIT,
        "convbin_options": convbin_command[1:-1],
        "min_sat": int(generation["raw_doppler_min_sat"]),
        "std_floor_mps": float(generation["raw_doppler_std_floor_mps"]),
        "time_conversion_formula": RAW_DOPPLER_TIME_CONVERSION,
        "utc_date": [source_position["utc_year"], source_position["utc_month"], source_position["utc_day"]],
        "gps_week": source_position["gps_week"],
        "leap_seconds": source_position["leap_seconds"],
        "approx_position_geodetic_deg_m": [
            source_position["lat_deg"],
            source_position["lon_deg"],
            source_position["height_m"],
        ],
        "selected_status_row_number": source_position["selected_status_row_number"],
        "selected_status_fields_sha256": source_position["selected_status_fields_sha256"],
        "covariance_policy": generation["raw_doppler_covariance_policy"],
        "first_epoch_fit_used": False,
    }
    conversion_hash = sha256_text(json.dumps(conversion_contract, sort_keys=True, separators=(",", ":")))
    formal_raw_path = provider_root / "providers" / "RAW_DOPPLER_VELOCITY.csv"
    count_report = _write_formal_raw_doppler(
        Path(helper_run["helper_raw_csv_path"]),
        formal_raw_path,
        source_position=source_position,
        obs_hash=obs_hash,
        nav_hash=nav_hash,
        conversion_config_hash=conversion_hash,
        min_sat=int(generation["raw_doppler_min_sat"]),
        std_floor_mps=float(generation["raw_doppler_std_floor_mps"]),
        covariance_policy=str(generation["raw_doppler_covariance_policy"]),
    )
    rawx_epoch_count = int(rebuild_report.get("rawx_frame_count") or 0)
    if rawx_epoch_count < int(count_report["valid_epoch_count"]):
        raise FormalGenerationError("Raw Doppler valid epoch count exceeds hash-locked RAWX epochs")
    count_report["raw_epoch_count"] = rawx_epoch_count
    count_report["invalid_epoch_count"] = rawx_epoch_count - int(count_report["valid_epoch_count"])

    helper_sources = [
        "src/legsa_gins/raw_gnss/ubx_raw_binary_rebuilder.py",
        "src/legsa_gins/raw_gnss/rtklib_doppler_helper_builder.py",
        "src/legsa_gins/raw_gnss/rtklib_doppler_velocity_provider.py",
        "src/legsa_gins/raw_gnss/rtklib_solution_velocity_parser.py",
        "src/legsa_gins/paper_rebuild/formal_generation.py",
    ]
    helper_source_hashes = {relative: sha256_file(paths.code_root / relative) for relative in helper_sources}
    maintained_shared_source_hashes = {
        relative: sha256_file(paths.code_root / relative)
        for relative in MAINTAINED_SHARED_SOURCE_FILES
    }
    rtklib_source_files = list(dict.fromkeys([f"src/{name}" for name in REQUIRED_SOURCE_FILES] + list(CONVBIN_SOURCE_FILES)))
    rtklib_source_hashes: dict[str, str] = {}
    for relative in rtklib_source_files:
        source = rtklib_root / relative
        if not source.is_file():
            raise FormalGenerationError(f"Pinned RTKLIB source file is missing: {relative}")
        rtklib_source_hashes[relative] = sha256_file(source)
    raw_relative = f"{BY2_FIX_PREFIX}/gnss1-raw.csv"
    status_relative = f"{BY2_FIX_PREFIX}/gnss1-status.csv"
    retained_backend_paths = {
        "helper_executable": helper_exe,
        "helper_source": Path(helper_report["helper_source_path"]),
        "convbin_executable": retained_convbin,
        "rebuilt_ubx": rebuilt_ubx,
        "rinex_obs": obs_path,
        "rinex_nav": nav_path,
        "formal_raw_doppler_provider": formal_raw_path,
    }
    retained_backend_artifacts = {
        role: {
            "relative_path": path.relative_to(provider_root).as_posix(),
            "sha256": sha256_file(path),
        }
        for role, path in retained_backend_paths.items()
    }
    retained_backend_bundle_hash = sha256_text(
        json.dumps(retained_backend_artifacts, sort_keys=True, separators=(",", ":"))
    )
    backend_report = {
        "schema_version": "paper-rebuild-raw-doppler-backend-v1",
        "raw_doppler_backend_lineage_proven": True,
        "raw_doppler_backend_id": RAW_DOPPLER_BACKEND_ID,
        "raw_doppler_backend_source_files": [raw_relative, status_relative],
        "raw_doppler_backend_source_hashes": {
            raw_relative: verified[raw_relative],
            status_relative: verified[status_relative],
        },
        "helper_source_files": helper_sources,
        "helper_source_hashes": helper_source_hashes,
        "rtklib_source_files": rtklib_source_files,
        "rtklib_source_hashes": rtklib_source_hashes,
        "helper_compiled_rtklib_source_files": helper_report[
            "exact_compiled_rtklib_source_files"
        ],
        "convbin_compiled_source_files": list(CONVBIN_SOURCE_FILES),
        "helper_executable_hash": helper_hash,
        "obs_source_hash": obs_hash,
        "nav_source_hash": nav_hash,
        "conversion_config_hash": conversion_hash,
        "conversion_contract": conversion_contract,
        **count_report,
        "covariance_policy": generation["raw_doppler_covariance_policy"],
        "rtklib_source_mode": rtklib_mode,
        "rtklib_remote": PINNED_RTKLIB_REMOTE,
        "rtklib_commit": PINNED_RTKLIB_COMMIT,
        "rtklib_tracked_source_dirty": bool(
            _git_value(rtklib_root, ["status", "--porcelain", "--untracked-files=no"])
        ),
        "rtklib_untracked_build_outputs_present": bool(
            _git_value(rtklib_root, ["status", "--porcelain", "--untracked-files=normal"])
        ),
        "external_ephemeris_downloaded": False,
        "time_conversion_formula": RAW_DOPPLER_TIME_CONVERSION,
        "time_conversion_inputs_source_backed": True,
        "approx_position_source_relative_path": status_relative,
        "approx_position_source_hash": verified[status_relative],
        "approx_position_geodetic_deg_m": conversion_contract["approx_position_geodetic_deg_m"],
        "selected_status_row_number": source_position["selected_status_row_number"],
        "selected_status_fields_sha256": source_position["selected_status_fields_sha256"],
        "gps_week": source_position["gps_week"],
        "first_epoch_fit_used": False,
        "rtklib_position_solution_used_as_solver_input": False,
        "nav_pvt_velocity_used_as_raw_doppler": False,
        "gnss_velocity_used_as_raw_doppler": False,
        "status_fallback_used": False,
        "tracked_provider_generation": generation,
        "legacy_provider_used": False,
        "convbin_executable_hash": sha256_file(retained_convbin),
        "rebuilt_ubx_hash": sha256_file(rebuilt_ubx),
        "runtime_patch_applied": [],
        "source_discovery_used": False,
        "sat_count_semantics": "distinct_satellites_with_nonzero_doppler_observation",
        "helper_source_hash": helper_report["helper_source_hash"],
        "compiler_version": _run(["gcc", "--version"], cwd=rtklib_root, label="gcc version").stdout.splitlines()[0],
        "convbin_build_command": ["make"],
        "convbin_clean_build": True,
        "convbin_preexisting_output_count": 0,
        "helper_compile_command": helper_report.get("compile_command", []),
        "retained_backend_artifacts": retained_backend_artifacts,
        "retained_backend_bundle_hash": retained_backend_bundle_hash,
    }
    validate_raw_doppler_backend_report(backend_report, verified_raw_hashes=verified)
    backend_report_path = write_json_atomic(
        provider_root / "RAW_DOPPLER_BACKEND_REPORT.json", backend_report
    )

    artifacts = dict(base_manifest["artifacts"])
    formal_dual_path = provider_root / "providers" / "DUAL_YAW_PROVIDER.csv"
    shutil.copy2(
        provider_root / artifacts["dual_yaw_provider"]["relative_path"],
        formal_dual_path,
    )
    artifacts["dual_yaw_provider"] = {
        "relative_path": formal_dual_path.relative_to(provider_root).as_posix(),
        "source_generated": True,
    }
    artifacts["raw_doppler_provider"] = {"relative_path": formal_raw_path.relative_to(provider_root).as_posix(), "source_generated": True}
    artifacts["source_quality_metadata"] = {"relative_path": source_quality_path.relative_to(provider_root).as_posix(), "source_generated": True}
    artifacts = {role: artifacts[role] for role in REQUIRED_FORMAL_PROVIDER_ROLES}
    for role, entry in artifacts.items():
        entry["solver_input"] = role not in {"dual_yaw_provider", "source_quality_metadata"}
        entry["artifact_role"] = (
            "audit_only_lineage"
            if not entry["solver_input"]
            else "potential_formal_solver_input"
        )
    provider_hashes = {
        role: sha256_file(provider_root / entry["relative_path"])
        for role, entry in artifacts.items()
    }
    actual_reads = [
        {
            "relative_path": f"{BY2_FIX_PREFIX}/gnss1-status.csv",
            "role": "gnss_position_and_raw_doppler_approx_position_date_source",
            "reader_component": "paper_rebuild.providers+paper_rebuild.formal_generation",
            "reason": "source-backed GNSS position and Raw Doppler approximate position/date; not receiver velocity",
            "output_provider_lineage": "gnss_runtime_input+raw_doppler_provider",
        },
        {
            "relative_path": f"{BY2_FIX_PREFIX}/gnss2-status.csv",
            "role": "fixed_physical_dual_yaw_source",
            "reader_component": "paper_rebuild.providers",
            "reason": "GNSS2-GNSS1 lateral short baseline",
            "output_provider_lineage": "gnss_runtime_input+dual_yaw_provider",
        },
        {
            "relative_path": raw_relative,
            "role": "receiver_velocity_nav_pvt_and_rawx_sfrbx_raw_doppler_observation_source",
            "reader_component": "paper_rebuild.providers+paper_rebuild.formal_generation",
            "reason": "receiver velocity from UBX NAV-PVT plus fresh RAWX/SFRBX Doppler observations",
            "output_provider_lineage": "gnss_runtime_input+raw_doppler_provider",
        },
        {
            "relative_path": BY2_BODY_RELATIVE_PATH,
            "role": "propagation_imu_source",
            "reader_component": "paper_rebuild.providers",
            "reason": "Go2 body IMU and bounded weak priors; never truth",
            "output_provider_lineage": "imu_runtime_input+go2_attitude_prior+go2_horizontal_velocity_prior",
        },
    ]
    for entry in actual_reads:
        digest = verified[entry["relative_path"]]
        entry["expected_sha256"] = digest
        entry["actual_sha256"] = digest
    validate_provider_source_read_set(actual_reads, verified)
    actual_relative_set = {entry["relative_path"] for entry in actual_reads}
    raw_source_roles = {
        relative: (
            "actual_provider_source"
            if relative in actual_relative_set
            else "evaluation_only_trace"
            if relative.endswith("/trace_vrtk2_a87c6e_2026-03-06-08-00-54_minimal.csv")
            else "hash_verified_not_provider_or_solver_input"
        )
        for relative in BY2_RAW_RELATIVE_PATHS
    }
    generation_contract = {
        "schema_version": "paper-rebuild-clean1-provider-generation-v1",
        "code_commit": commit,
        "provider_roles": list(REQUIRED_FORMAL_PROVIDER_ROLES),
        "raw_doppler_conversion_config_hash": conversion_hash,
        "formal_gnss_columns": 18,
        "formal_gnss_validity_report": validity_report,
        "status_fallback_used": False,
        "tracked_provider_generation": generation,
        "maintained_shared_source_hashes": maintained_shared_source_hashes,
        "maintained_shared_source_commit": commit,
    }
    generation_hash = sha256_text(json.dumps(generation_contract, sort_keys=True, separators=(",", ":")))
    bundle_hash = hashlib.sha256(json.dumps(provider_hashes, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    manifest = {
        "schema_version": "paper-rebuild-clean1-input-v1",
        "data_mode": "real_by2_raw",
        "raw_source_hashes": verified,
        "raw_source_roles": raw_source_roles,
        "actual_source_read_set": actual_reads,
        "provider_hashes": provider_hashes,
        "provider_bundle_hash": bundle_hash,
        "artifacts": artifacts,
        "raw_doppler_backend": backend_report,
        "raw_doppler_backend_report_sha256": sha256_file(backend_report_path),
        "maintained_shared_source_hashes": maintained_shared_source_hashes,
        "maintained_shared_source_commit": commit,
        "yaw_contract": base_manifest.get("yaw_contract", {}),
        "yaw_runtime_crosscheck": base_manifest.get("yaw_runtime_crosscheck", {}),
        "go2_contract": base_manifest.get("go2_contract", {}),
        "source_roles": base_manifest.get("source_roles", {}),
        "synthetic_data_used": False,
        "semisynthetic_data_used": False,
        "trace_used_online": False,
        "receiver_imu_as_body_imu": False,
        "final_v23_output_solver_input": False,
        "LegSA_output_solver_input": False,
        "per_case_tuning": False,
        "output_only_correction": False,
        "epoch_deleted_for_metric": False,
        "old_runtime_input_count": 0,
        "legacy_provider_input_count": 0,
        "legacy_row_input_count": 0,
        "legacy_aggregate_input_count": 0,
        "status_fallback_used": False,
        "legacy_provider_used": False,
        "generator_code_commit": commit,
        "generator_worktree_dirty": False,
        "generator_config_hash": generation_hash,
        "local_path_config_hash": sha256_file(paths.config_path),
        "generation_contract": generation_contract,
    }
    final_commit, final_dirty = git_code_state(paths.code_root)
    if final_commit != commit or final_dirty:
        raise FormalGenerationError("Code state changed during formal provider generation")
    write_json_atomic(provider_root / "CLEAN_INPUT_MANIFEST.json", manifest)
    with (provider_root / "PROVIDER_HASH_MANIFEST.csv").open(
        "w", encoding="utf-8", newline=""
    ) as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["provider_role", "relative_path", "sha256", "solver_input", "artifact_role"],
        )
        writer.writeheader()
        for role in REQUIRED_FORMAL_PROVIDER_ROLES:
            writer.writerow(
                {
                    "provider_role": role,
                    "relative_path": artifacts[role]["relative_path"],
                    "sha256": provider_hashes[role],
                    "solver_input": artifacts[role]["solver_input"],
                    "artifact_role": artifacts[role]["artifact_role"],
                }
            )
    return manifest
