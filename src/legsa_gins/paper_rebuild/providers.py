"""Fresh BY2 provider materialization from canonical raw/status/Go2 sources."""

from __future__ import annotations

import csv
import json
import math
import re
import shutil
import threading
from pathlib import Path
from typing import Any

from legsa_gins.datasets.by2.go2_body_state_parser import parse_go2_body_state_text
from legsa_gins.go2_prior.go2_velocity_frame_review import transform_go2_velocity_for_frame
from legsa_gins.input_generation import process_data_compat as _shared_process_data_compat
from legsa_gins.input_generation.ubx_nav_pvt import (
    extract_pvt_velocity_rows as _expected_shared_pvt_extractor,
)
from legsa_gins.input_generation.status_yaw_builder import (
    build_a1_dual_diff_yaw_rows,
    status_time_header,
    status_time_sys,
    wrap_deg,
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
from .ubx_nav_pvt import extract_pvt_velocity_rows as _active_clean_pvt_extractor


PHYSICAL_BASELINE_MIN_M = 0.20
PHYSICAL_BASELINE_MAX_M = 0.60
GO2_ROLL_PITCH_STD_DEG = 1.6
GO2_HORIZONTAL_STD_MPS = 1.5
RECEIVER_VELOCITY_PARSER_ADAPTER_ID = (
    "paper_rebuild.ubx_nav_pvt_full_frame_sacc_74_78.v1"
)
_PROCESS_DATA_COMPAT_BIND_LOCK = threading.Lock()


class ProviderGenerationError(RuntimeError):
    """Fresh source provider generation failed a physical or lineage gate."""


def _generate_process_data_compat_with_active_pvt(*args: Any, **kwargs: Any) -> dict[str, Any]:
    """Call the maintained compatibility builder with the clean PVT decoder.

    The shared builder exposes no dependency-injection argument.  The clean
    namespace therefore binds only its extractor global for this synchronous,
    serialized call, verifies the expected legacy dependency before binding,
    and restores it in ``finally`` on every exit path.
    """

    with _PROCESS_DATA_COMPAT_BIND_LOCK:
        current = _shared_process_data_compat.extract_pvt_velocity_rows
        if current is not _expected_shared_pvt_extractor:
            raise ProviderGenerationError(
                "Shared process_data compatibility extractor identity changed; "
                "refusing an unreviewed receiver-velocity parser binding"
            )
        _shared_process_data_compat.extract_pvt_velocity_rows = _active_clean_pvt_extractor
        try:
            return _shared_process_data_compat.generate_process_data_compat_inputs(
                *args, **kwargs
            )
        finally:
            _shared_process_data_compat.extract_pvt_velocity_rows = (
                _expected_shared_pvt_extractor
            )


def _percentile(values: list[float], fraction: float) -> float | None:
    finite = sorted(value for value in values if math.isfinite(value))
    if not finite:
        return None
    index = min(len(finite) - 1, max(0, int(round(fraction * (len(finite) - 1)))))
    return finite[index]


def _source_time(path: Path) -> float:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        row = next(csv.DictReader(handle), None)
    if not row:
        raise ProviderGenerationError("GNSS1 status source is empty")
    try:
        timestamp = status_time_sys(row)
    except ValueError:
        timestamp = status_time_header(row)
    if not math.isfinite(timestamp):
        raise ProviderGenerationError("GNSS1 status source has no finite timestamp")
    return timestamp


def infer_source_day_base_time(gnss1_status: Path) -> float:
    """Derive the UTC-day origin only from source timestamps, never trace."""

    timestamp = _source_time(gnss1_status)
    return math.floor(timestamp / 86400.0) * 86400.0


def _write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def build_physical_dual_yaw_provider(
    gnss1_status: Path,
    gnss2_status: Path,
    *,
    base_time: float,
    max_rows: int | None = None,
    fixed_yaw_std_deg: float = 1.5,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Build every accepted status epoch, then fail closed on whole-set geometry."""

    source_rows, source_audit = build_a1_dual_diff_yaw_rows(
        gnss1_status,
        gnss2_status,
        base_time=base_time,
        max_rows=max_rows,
    )
    lengths = [float(row["baseline_len_m"]) for row in source_rows]
    median = _percentile(lengths, 0.50)
    p05 = _percentile(lengths, 0.05)
    p95 = _percentile(lengths, 0.95)
    four_meter = any(3.5 <= value <= 4.5 for value in lengths)
    physical_pass = (
        median is not None
        and PHYSICAL_BASELINE_MIN_M <= median <= PHYSICAL_BASELINE_MAX_M
        and not four_meter
    )
    rows: list[dict[str, Any]] = []
    for source in source_rows:
        north = float(source["rel_n"])
        east = float(source["rel_e"])
        baseline_heading = wrap_deg(math.degrees(math.atan2(east, north)))
        body_yaw = wrap_deg(baseline_heading + 90.0)
        length = float(source["baseline_len_m"])
        rows.append(
            {
                "time": float(source["aligned_time"]),
                "source_timestamp": float(source["timestamp"]),
                "baseline_n_m": north,
                "baseline_e_m": east,
                "baseline_d_m": float(source["rel_d"]),
                "baseline_length_m": length,
                "baseline_heading_ned_deg": baseline_heading,
                "body_yaw_ned_deg": body_yaw,
                "yaw_std_deg": fixed_yaw_std_deg,
                "physical_in_band": PHYSICAL_BASELINE_MIN_M <= length <= PHYSICAL_BASELINE_MAX_M,
                "source_status": "active" if physical_pass else "blocked_physical_gate",
                "gnss_order": "GNSS2-GNSS1",
                "lateral_to_body_offset_deg": 90.0,
                "wrap_safe_residual": True,
                "trace_sign_or_offset_selection": False,
            }
        )
    audit = {
        "source_audit": source_audit,
        "provider_row_count": len(rows),
        "median_baseline_length_m": median,
        "p05_baseline_length_m": p05,
        "p95_baseline_length_m": p95,
        "physical_gate_min_m": PHYSICAL_BASELINE_MIN_M,
        "physical_gate_max_m": PHYSICAL_BASELINE_MAX_M,
        "four_meter_baseline_reappeared": four_meter,
        "physical_baseline_gate_pass": physical_pass,
        "gnss_order": "GNSS2-GNSS1",
        "lateral_to_body_offset_deg": 90.0,
        "wrap_safe_residual": True,
        "trace_sign_or_offset_selection": False,
        "per_case_offset": False,
        "epoch_deleted_for_metric": False,
    }
    return rows, audit


def _go2_priors(
    body: Path,
    *,
    base_time: float,
    max_messages: int | None,
    frame_name: str = "go2_velocity_as_body_flu_then_rotate_by_go2_attitude",
    roll_pitch_std_deg: float = GO2_ROLL_PITCH_STD_DEG,
    horizontal_std_mps: float = GO2_HORIZONTAL_STD_MPS,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    rows = parse_go2_body_state_text(body, max_messages=max_messages)
    attitude: list[dict[str, Any]] = []
    horizontal: list[dict[str, Any]] = []
    for row in rows:
        timestamp = row.get("timestamp")
        roll = row.get("roll_rad")
        pitch = row.get("pitch_rad")
        if not all(isinstance(value, (int, float)) and math.isfinite(float(value)) for value in (timestamp, roll, pitch)):
            continue
        time_value = float(timestamp) - base_time
        attitude.append(
            {
                "time": time_value,
                "roll_rad": float(roll),
                "pitch_rad": float(pitch),
                "std_roll_rad": math.radians(roll_pitch_std_deg),
                "std_pitch_rad": math.radians(roll_pitch_std_deg),
                "source_status": "active",
                "mode": row.get("mode", ""),
                "gait_type": row.get("gait_type", ""),
                "quality_flag": "clean_raw_go2_weak_auxiliary",
                "go2_roll_pitch_truth_claim": False,
            }
        )
        velocity = transform_go2_velocity_for_frame(row, frame_name)
        if all(math.isfinite(value) for value in velocity):
            horizontal.append(
                {
                    "time": time_value,
                    "vn": velocity[0],
                    "ve": velocity[1],
                    "vd": 0.0,
                    "std_vn": horizontal_std_mps,
                    "std_ve": horizontal_std_mps,
                    "std_vd": 999.0,
                    "confidence": "",
                    "confidence_level": "weak_auxiliary",
                    "update_flag": True,
                    "reason_codes": "clean_source_frame_transform_weak_prior",
                    "source_status": "active",
                    "quality_flag": "clean_raw_go2_weak_auxiliary",
                    "contact_model": "not_used_as_truth",
                    "contact_label": "",
                    "frame_candidate": frame_name,
                    "prior_policy": "clean_v1_horizontal_weak_prior",
                    "diagnostic_only": False,
                    "go2_velocity_truth_claim": False,
                }
            )
    report = {
        "body_message_count": len(rows),
        "attitude_prior_count": len(attitude),
        "horizontal_velocity_prior_count": len(horizontal),
        "frame_transform": frame_name,
        "go2_position_truth_claim": False,
        "go2_velocity_truth_claim": False,
        "go2_yaw_truth_claim": False,
        "trace_solver_input": False,
        "receiver_imu_as_body_imu": False,
    }
    return attitude, horizontal, report


def _runtime_yaw_crosscheck(gnss_path: Path, dual_rows: list[dict[str, Any]]) -> dict[str, Any]:
    provider = sorted(dual_rows, key=lambda row: float(row["time"]))
    matched = 0
    errors: list[float] = []
    for line in gnss_path.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        values = [float(value) for value in line.split()]
        if len(values) < 15 or not provider:
            continue
        time_value = values[0]
        nearest = min(provider, key=lambda row: abs(float(row["time"]) - time_value))
        if abs(float(nearest["time"]) - time_value) > 0.6:
            continue
        error = (values[13] - float(nearest["body_yaw_ned_deg"]) + 180.0) % 360.0 - 180.0
        errors.append(abs(error))
        matched += 1
    maximum = max(errors, default=None)
    return {
        "matched_runtime_rows": matched,
        "max_wrap_safe_difference_deg": maximum,
        "passed": matched > 0 and maximum is not None and maximum <= 1.0e-6,
        "comparison": "15-column solver yaw versus GNSS2-GNSS1 lateral +90 body yaw",
    }


def generate_clean_by2_inputs(
    paths: CleanPaths,
    *,
    max_status_rows: int | None = None,
    max_raw_rows: int | None = None,
    max_imu_messages: int | None = None,
    replace: bool = False,
    yaw_sign: float = 1.0,
    yaw_install_offset_deg: float = 0.0,
    status_fixed_yaw_std_deg: float = 1.5,
    receiver_velocity_match_tolerance_seconds: float = 0.1,
    dual_yaw_match_tolerance_seconds: float = 0.6,
    receiver_velocity_std_mps: float = 0.05,
    imu_install_roll_deg: float = -1.0,
    imu_install_pitch_deg: float = 0.0,
    imu_install_yaw_deg: float = 0.0,
    imu_gnss_time_offset: float = 0.0,
    go2_velocity_frame_transform: str = "go2_velocity_as_body_flu_then_rotate_by_go2_attitude",
    go2_roll_pitch_std_deg: float = GO2_ROLL_PITCH_STD_DEG,
    go2_horizontal_velocity_std_mps: float = GO2_HORIZONTAL_STD_MPS,
    stage_id: str = "PAPER10_CLEAN0",
    expected_code_commit: str | None = None,
) -> dict[str, Any]:
    """Materialize clean inputs/providers from four raw source files only.

    The default/smoke entrypoint owns its Git checks exactly as before.  The
    formal CLEAN1 subprocess instead receives a commit already bracketed by
    its parent outside the file-open trace; that path must not run ``git
    status`` inside the traced child.
    """

    provider_root = guard_path(paths.provider_root, role="provider root", allowed_root=paths.clean_root)
    manifest_path = provider_root / "CLEAN_INPUT_MANIFEST.json"
    parent_bracketed_git_state = expected_code_commit is not None
    if parent_bracketed_git_state:
        if stage_id not in {
            "CLEAN1_BY2_CLEAN_FOUR_METHOD_EXECUTION",
            "CLEAN1R1C_FROZEN_PROTOCOL_DIRECT_REIMPLEMENTATION_AND_BY2_FORMAL_EXECUTION",
        }:
            raise ProviderGenerationError(
                "Expected formal code commit is only valid for the CLEAN1 formal stage"
            )
        if not isinstance(expected_code_commit, str) or not re.fullmatch(
            r"[0-9a-f]{40}", expected_code_commit
        ):
            raise ProviderGenerationError("Expected formal code commit is invalid")
        generator_commit = expected_code_commit
    else:
        try:
            generator_commit, generator_dirty = git_code_state(paths.code_root)
        except ValueError as exc:
            raise ProviderGenerationError(str(exc)) from exc
        if generator_dirty:
            raise ProviderGenerationError(
                "Provider generation requires a clean committed Git worktree"
            )
    if provider_root.exists():
        if not replace:
            raise ProviderGenerationError("Clean provider root already exists; use an explicit replace request")
        if provider_root.is_symlink() or not provider_root.is_dir():
            raise ProviderGenerationError("Clean provider replacement target must be an exact real directory")
        shutil.rmtree(provider_root)
    provider_root.mkdir(parents=True, exist_ok=True)

    source_paths = {
        "gnss1_status": paths.by2_fix_root / "gnss1-status.csv",
        "gnss2_status": paths.by2_fix_root / "gnss2-status.csv",
        "gnss1_raw": paths.by2_fix_root / "gnss1-raw.csv",
        "go2_body": paths.by2_go2_body,
    }
    for role, source in source_paths.items():
        guard_path(source, role=role, allowed_root=paths.raw_root, must_exist=True, regular_file=True)
    relative_sources = {
        role: source.resolve(strict=True).relative_to(paths.raw_root.resolve(strict=True)).as_posix()
        for role, source in source_paths.items()
    }
    lock = read_hash_lock(paths.raw_hash_lock)
    raw_hashes = verify_raw_sources(paths.raw_root, relative_sources.values(), lock)

    base_time = infer_source_day_base_time(source_paths["gnss1_status"])
    dual_rows, yaw_audit = build_physical_dual_yaw_provider(
        source_paths["gnss1_status"],
        source_paths["gnss2_status"],
        base_time=base_time,
        max_rows=max_status_rows,
        fixed_yaw_std_deg=status_fixed_yaw_std_deg,
    )
    if not yaw_audit["physical_baseline_gate_pass"]:
        write_json_atomic(provider_root / "DUAL_YAW_PHYSICAL_GATE_BLOCKED.json", yaw_audit)
        raise ProviderGenerationError("BY2 dual-yaw physical short-baseline gate failed")

    generated = _generate_process_data_compat_with_active_pvt(
        paths.by2_fix_root,
        paths.by2_go2_body,
        provider_root / "runtime_inputs",
        base_time=base_time,
        yaw_source_mode="status",
        yaw_sign=yaw_sign,
        yaw_install_offset_deg=yaw_install_offset_deg,
        yaw_std_mode="fixed_1p5",
        enable_outage=False,
        outlier_mode="none",
        yaw_noise_std_deg=0.0,
        status_fixed_yaw_std_deg=status_fixed_yaw_std_deg,
        receiver_velocity_match_tolerance_seconds=receiver_velocity_match_tolerance_seconds,
        dual_yaw_match_tolerance_seconds=dual_yaw_match_tolerance_seconds,
        receiver_velocity_std_mps=receiver_velocity_std_mps,
        imu_install_roll_deg=imu_install_roll_deg,
        imu_install_pitch_deg=imu_install_pitch_deg,
        imu_install_yaw_deg=imu_install_yaw_deg,
        imu_gnss_time_offset=imu_gnss_time_offset,
        stage_id=stage_id,
        max_status_rows=max_status_rows,
        max_raw_rows=max_raw_rows,
        max_imu_messages=max_imu_messages,
    )
    if generated["report"].get("trace_solver_input") is not False:
        raise ProviderGenerationError("Source input generator unexpectedly reports trace input")

    yaw_runtime_crosscheck = _runtime_yaw_crosscheck(Path(generated["gnss_path"]), dual_rows)
    if not yaw_runtime_crosscheck["passed"]:
        raise ProviderGenerationError("15-column runtime yaw does not match clean physical yaw provider")

    dual_path = provider_root / "providers" / "dual_yaw_provider.csv"
    _write_csv(
        dual_path,
        dual_rows,
        [
            "time",
            "source_timestamp",
            "baseline_n_m",
            "baseline_e_m",
            "baseline_d_m",
            "baseline_length_m",
            "baseline_heading_ned_deg",
            "body_yaw_ned_deg",
            "yaw_std_deg",
            "physical_in_band",
            "source_status",
            "gnss_order",
            "lateral_to_body_offset_deg",
            "wrap_safe_residual",
            "trace_sign_or_offset_selection",
        ],
    )
    attitude_rows, horizontal_rows, go2_report = _go2_priors(
        paths.by2_go2_body,
        base_time=base_time,
        max_messages=max_imu_messages,
        frame_name=go2_velocity_frame_transform,
        roll_pitch_std_deg=go2_roll_pitch_std_deg,
        horizontal_std_mps=go2_horizontal_velocity_std_mps,
    )
    if not attitude_rows or not horizontal_rows:
        raise ProviderGenerationError("Go2 raw source did not produce clean weak-prior rows")
    attitude_path = provider_root / "providers" / "GO2_ATTITUDE_WEAK_PRIORS.csv"
    horizontal_path = provider_root / "providers" / "GO2_HORIZONTAL_VELOCITY_WEAK_PRIORS.csv"
    _write_csv(
        attitude_path,
        attitude_rows,
        [
            "time",
            "roll_rad",
            "pitch_rad",
            "std_roll_rad",
            "std_pitch_rad",
            "source_status",
            "mode",
            "gait_type",
            "quality_flag",
            "go2_roll_pitch_truth_claim",
        ],
    )
    _write_csv(
        horizontal_path,
        horizontal_rows,
        [
            "time",
            "vn",
            "ve",
            "vd",
            "std_vn",
            "std_ve",
            "std_vd",
            "confidence",
            "confidence_level",
            "update_flag",
            "reason_codes",
            "source_status",
            "quality_flag",
            "contact_model",
            "contact_label",
            "frame_candidate",
            "prior_policy",
            "diagnostic_only",
            "go2_velocity_truth_claim",
        ],
    )

    artifacts = {
        "imu_runtime_input": Path(generated["imu_path"]),
        "gnss_runtime_input": Path(generated["gnss_path"]),
        "dual_yaw_provider": dual_path,
        "go2_attitude_prior": attitude_path,
        "go2_horizontal_velocity_prior": horizontal_path,
    }
    provider_relpaths = {
        role: path.resolve(strict=True).relative_to(provider_root.resolve(strict=True)).as_posix()
        for role, path in artifacts.items()
    }
    provider_hashes = {role: sha256_file(path) for role, path in artifacts.items()}
    source_roles = {
        relative_sources["gnss1_status"]: "GNSS1 position/status source observation",
        relative_sources["gnss2_status"]: "GNSS2 status for GNSS2-GNSS1 short baseline",
        relative_sources["gnss1_raw"]: "GNSS1 UBX source for receiver-native velocity",
        relative_sources["go2_body"]: "Go2 body IMU and weak auxiliary priors; not truth",
        "trace": "evaluation-only and not read during clean input generation",
    }
    if (
        stage_id
        == "CLEAN1R1C_FROZEN_PROTOCOL_DIRECT_REIMPLEMENTATION_AND_BY2_FORMAL_EXECUTION"
    ):
        receiver_diagnostics = {
            "imu-data.csv": "Fixposition receiver IMU diagnostic-only; never propagation input",
            "imu-biases.csv": "Fixposition receiver IMU bias diagnostic-only; never propagation input",
            "imu-temp.csv": "Fixposition receiver IMU temperature diagnostic-only; never propagation input",
        }
        for name, role in receiver_diagnostics.items():
            relative = str(
                (paths.by2_fix_root / name)
                .resolve(strict=False)
                .relative_to(paths.raw_root.resolve(strict=True))
            )
            source_roles[relative] = role
        source_roles["trace"] = (
            "Fixposition same-source evaluation reference; offline-only and not read "
            "during clean input generation"
        )
    yaw_contract = {
        key: yaw_audit[key]
        for key in (
            "gnss_order",
            "lateral_to_body_offset_deg",
            "wrap_safe_residual",
            "trace_sign_or_offset_selection",
            "physical_baseline_gate_pass",
            "median_baseline_length_m",
            "p05_baseline_length_m",
            "p95_baseline_length_m",
            "physical_gate_min_m",
            "physical_gate_max_m",
            "four_meter_baseline_reappeared",
        )
    }
    generation_contract = {
        "schema_version": "paper-rebuild-provider-generation-v1",
        "generator_code_commit": generator_commit,
        "raw_source_relpaths": relative_sources,
        "max_status_rows": max_status_rows,
        "max_raw_rows": max_raw_rows,
        "max_imu_messages": max_imu_messages,
        "yaw_source_mode": "status",
        "yaw_order": "GNSS2-GNSS1",
        "lateral_to_body_offset_deg": 90.0,
        "go2_prior_policy": "weak_auxiliary_not_truth",
        "yaw_sign": yaw_sign,
        "yaw_install_offset_deg": yaw_install_offset_deg,
        "status_fixed_yaw_std_deg": status_fixed_yaw_std_deg,
        "receiver_velocity_match_tolerance_seconds": receiver_velocity_match_tolerance_seconds,
        "dual_yaw_match_tolerance_seconds": dual_yaw_match_tolerance_seconds,
        "receiver_velocity_std_mps": receiver_velocity_std_mps,
        "receiver_velocity_parser_adapter_id": RECEIVER_VELOCITY_PARSER_ADAPTER_ID,
        "receiver_velocity_sAcc_full_frame_offsets": [74, 78],
        "imu_install_roll_deg": imu_install_roll_deg,
        "imu_install_pitch_deg": imu_install_pitch_deg,
        "imu_install_yaw_deg": imu_install_yaw_deg,
        "imu_gnss_time_offset": imu_gnss_time_offset,
        "go2_velocity_frame_transform": go2_velocity_frame_transform,
        "go2_roll_pitch_std_deg": go2_roll_pitch_std_deg,
        "go2_horizontal_velocity_std_mps": go2_horizontal_velocity_std_mps,
        "stage_id": stage_id,
    }
    generator_config_hash = sha256_text(
        json.dumps(generation_contract, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    )
    manifest = {
        "schema_version": "paper-rebuild-clean-input-v1",
        "data_mode": "real_by2_raw",
        "base_time_source": "GNSS1 status UTC-day floor",
        "raw_source_hashes": raw_hashes,
        "raw_source_roles": {role: relative for role, relative in relative_sources.items()},
        "provider_hashes": provider_hashes,
        "artifacts": {
            role: {"relative_path": relative, "source_generated": True}
            for role, relative in provider_relpaths.items()
        },
        "source_roles": source_roles,
        "yaw_contract": yaw_contract,
        "yaw_runtime_crosscheck": yaw_runtime_crosscheck,
        "go2_contract": go2_report,
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
        "generator_code_commit": generator_commit,
        "generator_worktree_dirty": False,
        "generator_config_hash": generator_config_hash,
        "local_path_config_hash": sha256_file(paths.config_path),
        "generation_contract": generation_contract,
        "raw_doppler_provider_status": "not_required_for_basic_dual_yaw_smoke",
    }
    if not parent_bracketed_git_state:
        final_commit, final_dirty = git_code_state(paths.code_root)
        if final_commit != generator_commit or final_dirty:
            raise ProviderGenerationError(
                "Git code state changed during clean provider generation"
            )
    write_json_atomic(provider_root / "DUAL_YAW_PHYSICAL_GATE.json", yaw_audit)
    write_json_atomic(provider_root / "DUAL_YAW_RUNTIME_CROSSCHECK.json", yaw_runtime_crosscheck)
    write_json_atomic(provider_root / "GO2_PROVIDER_REPORT.json", go2_report)
    write_json_atomic(provider_root / "SOURCE_ROLE_MANIFEST.json", {"source_roles": source_roles})
    write_json_atomic(manifest_path, manifest)
    hash_rows = [
        {"provider_role": role, "relative_path": provider_relpaths[role], "sha256": digest}
        for role, digest in provider_hashes.items()
    ]
    _write_csv(
        provider_root / "PROVIDER_HASH_MANIFEST.csv",
        hash_rows,
        ["provider_role", "relative_path", "sha256"],
    )
    return manifest
