"""Hash-locked BY2 solution-position and IMU-only providers for EXT05.

The position provider decodes every UBX-NAV-HPPOSECEF message from both
receivers, pairs only the already-audited common iTOW relation, and resolves
both streams in one fixed local NED frame.  The IMU provider deliberately
projects only timestamp, gyroscope, and accelerometer fields from ``by2.txt``;
quaternion, RPY, yaw, Go2 navigation state, trace, and prior-method outputs are
never materialized by this adapter.
"""

from __future__ import annotations

import csv
import hashlib
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence

import numpy as np

from .shared_raw_backend import ecef_to_geodetic, reconstruct_ubx_stream


GPS_EPOCH_UNIX_SECONDS = 315_964_800.0
EXPECTED_GPS_WEEK = 2408
EXPECTED_LEAP_SECONDS = 18
EXPECTED_POSITION_EPOCHS = 1510
EXPECTED_RAWX_EPOCHS = 1509
EXPECTED_POSITION_INTERVAL_MS = 200
EXPECTED_HPPOS_MINUS_RAWX_MS = 2
EXPECTED_IMU_SAMPLES = 63_278
BASELINE_BODY_FRD_M = np.array([0.0, -0.350, 0.0])
LEVER_IMU_TO_RECEIVER1_FRD_M = np.array([0.03, 0.03, -0.30])
IMU_INSTALL_RPY_DEG = np.array([-1.0, 0.0, 0.0])


class Ext05ProviderError(ValueError):
    """A source, timing, frame, or calibration contract failed closed."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _hash_lock_rows(path: Path) -> dict[str, dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    required = {"relative_path", "size_bytes", "sha256"}
    if not rows or not required.issubset(rows[0]):
        raise Ext05ProviderError("BY2 hash lock schema is incomplete")
    return {row["relative_path"]: row for row in rows}


def verify_hash_locked_file(path: Path, *, raw_root: Path, hash_lock: Path) -> dict[str, Any]:
    try:
        relative = path.relative_to(raw_root).as_posix()
    except ValueError as exc:
        raise Ext05ProviderError(f"raw input lies outside raw root: {path}") from exc
    row = _hash_lock_rows(hash_lock).get(relative)
    if row is None:
        raise Ext05ProviderError(f"raw input is absent from BY2 hash lock: {relative}")
    size = path.stat().st_size
    digest = sha256_file(path)
    if size != int(row["size_bytes"]) or digest != row["sha256"]:
        raise Ext05ProviderError(f"raw hash-lock mismatch: {relative}")
    return {"relative_path": relative, "size_bytes": size, "sha256": digest}


def fixed_ecef_to_ned_rotation(origin_ecef_m: Sequence[float]) -> np.ndarray:
    """One immutable ECEF-to-NED DCM at the first GNSS1 solution epoch."""

    origin = np.asarray(origin_ecef_m, dtype=float)
    if origin.shape != (3,) or np.any(~np.isfinite(origin)):
        raise Ext05ProviderError("fixed NED origin is invalid")
    latitude, longitude, _height = ecef_to_geodetic(origin)
    sin_lat, cos_lat = math.sin(latitude), math.cos(latitude)
    sin_lon, cos_lon = math.sin(longitude), math.cos(longitude)
    return np.array([
        [-sin_lat * cos_lon, -sin_lat * sin_lon, cos_lat],
        [-sin_lon, cos_lon, 0.0],
        [-cos_lat * cos_lon, -cos_lat * sin_lon, -sin_lat],
    ])


@dataclass(frozen=True)
class SolutionPositionEpoch:
    index: int
    itow_ms: int
    absolute_time_unix_seconds: float
    p1_ned_m: np.ndarray
    p2_ned_m: np.ndarray
    b21_ned_m: np.ndarray
    R1_ned_m2: np.ndarray
    R2_ned_m2: np.ndarray
    Rrel_declared_ned_m2: np.ndarray
    pacc1_m: float
    pacc2_m: float
    receiver1_valid: bool
    receiver2_valid: bool


@dataclass(frozen=True)
class SolutionPositionProvider:
    epochs: tuple[SolutionPositionEpoch, ...]
    origin_ecef_m: np.ndarray
    origin_geodetic_deg_m: tuple[float, float, float]
    ecef_to_ned: np.ndarray
    source_hashes: dict[str, dict[str, Any]]
    diagnostics: dict[str, Any]


def build_solution_position_provider(
    gnss1_raw: Path,
    gnss2_raw: Path,
    *,
    raw_root: Path,
    by2_hash_lock: Path,
) -> SolutionPositionProvider:
    """Decode all 1510 paired solution epochs without sign/time searching."""

    source_hashes = {
        "gnss1_raw": verify_hash_locked_file(gnss1_raw, raw_root=raw_root, hash_lock=by2_hash_lock),
        "gnss2_raw": verify_hash_locked_file(gnss2_raw, raw_root=raw_root, hash_lock=by2_hash_lock),
    }
    first = reconstruct_ubx_stream(gnss1_raw, decode_nav_hpposecef_semantics=True)
    second = reconstruct_ubx_stream(gnss2_raw, decode_nav_hpposecef_semantics=True)
    hp1 = list(first.nav_hpposecef_epochs)
    hp2 = list(second.nav_hpposecef_epochs)
    rawx1 = list(first.rawx_epochs)
    rawx2 = list(second.rawx_epochs)
    if len(hp1) != EXPECTED_POSITION_EPOCHS or len(hp2) != EXPECTED_POSITION_EPOCHS:
        raise Ext05ProviderError("HPPOSECEF receiver count is not 1510/1510")
    if len(rawx1) != EXPECTED_RAWX_EPOCHS or len(rawx2) != EXPECTED_RAWX_EPOCHS:
        raise Ext05ProviderError("RAWX receiver count is not 1509/1509")
    itow1 = [epoch.itow_ms for epoch in hp1]
    itow2 = [epoch.itow_ms for epoch in hp2]
    if itow1 != itow2 or any(b <= a for a, b in zip(itow1, itow1[1:])):
        raise Ext05ProviderError("receiver HPPOSECEF common-iTOW identity failed")
    intervals = np.diff(np.asarray(itow1, dtype=np.int64))
    if intervals.tolist() != [EXPECTED_POSITION_INTERVAL_MS] * (EXPECTED_POSITION_EPOCHS - 1):
        raise Ext05ProviderError("HPPOSECEF common-iTOW cadence is not fixed 200 ms")
    rawx_keys1 = [int(round(epoch.gps_tow_seconds * 1000.0)) for epoch in rawx1]
    rawx_keys2 = [int(round(epoch.gps_tow_seconds * 1000.0)) for epoch in rawx2]
    if rawx_keys1 != rawx_keys2:
        raise Ext05ProviderError("receiver RAWX timelines differ")
    if itow1[1:] != [value + EXPECTED_HPPOS_MINUS_RAWX_MS for value in rawx_keys1]:
        raise Ext05ProviderError("fixed HPPOSECEF=RAWX+2ms relation failed")
    weeks = {epoch.gps_week for epoch in (*rawx1, *rawx2)}
    leaps = {epoch.leap_seconds for epoch in (*rawx1, *rawx2)}
    if weeks != {EXPECTED_GPS_WEEK} or leaps != {EXPECTED_LEAP_SECONDS}:
        raise Ext05ProviderError("RAWX week/leap evidence is inconsistent")

    origin = hp1[0].position_ecef_m.copy()
    rotation = fixed_ecef_to_ned_rotation(origin)
    latitude, longitude, height = ecef_to_geodetic(origin)
    epochs: list[SolutionPositionEpoch] = []
    lengths: list[float] = []
    pacc1_values: list[float] = []
    pacc2_values: list[float] = []
    for index, (left, right) in enumerate(zip(hp1, hp2)):
        p1 = rotation @ (left.position_ecef_m - origin)
        p2 = rotation @ (right.position_ecef_m - origin)
        baseline = p2 - p1
        pacc1 = float(left.position_accuracy_m)
        pacc2 = float(right.position_accuracy_m)
        valid1 = bool(np.all(np.isfinite(p1)) and math.isfinite(pacc1) and pacc1 > 0.0)
        valid2 = bool(np.all(np.isfinite(p2)) and math.isfinite(pacc2) and pacc2 > 0.0)
        R1 = np.eye(3) * pacc1 * pacc1
        R2 = np.eye(3) * pacc2 * pacc2
        absolute = (
            GPS_EPOCH_UNIX_SECONDS
            + EXPECTED_GPS_WEEK * 604800.0
            + left.itow_ms * 1.0e-3
            - EXPECTED_LEAP_SECONDS
        )
        epochs.append(SolutionPositionEpoch(
            index=index,
            itow_ms=left.itow_ms,
            absolute_time_unix_seconds=absolute,
            p1_ned_m=p1,
            p2_ned_m=p2,
            b21_ned_m=baseline,
            R1_ned_m2=R1,
            R2_ned_m2=R2,
            Rrel_declared_ned_m2=R1 + R2,
            pacc1_m=pacc1,
            pacc2_m=pacc2,
            receiver1_valid=valid1,
            receiver2_valid=valid2,
        ))
        lengths.append(float(np.linalg.norm(baseline)))
        pacc1_values.append(pacc1)
        pacc2_values.append(pacc2)
    values = np.asarray(lengths)
    diagnostics = {
        "schema_version": "horizontal_literature.ext05.solution_provider.v1",
        "receiver_identity": {"z1": "GNSS1_RIGHT", "z2": "GNSS2_LEFT"},
        "pairing": "IDENTICAL_STRICT_COMMON_HPPOSECEF_ITOW_NO_SEARCH",
        "hpposecef_equals_rawx_plus_ms": EXPECTED_HPPOS_MINUS_RAWX_MS,
        "position_epoch_count": len(epochs),
        "rawx_epoch_count_per_receiver": len(rawx1),
        "leading_hpposecef_without_rawx_count": 1,
        "fixed_interval_ms": EXPECTED_POSITION_INTERVAL_MS,
        "gps_week": EXPECTED_GPS_WEEK,
        "leap_seconds": EXPECTED_LEAP_SECONDS,
        "time_first_unix_seconds": epochs[0].absolute_time_unix_seconds,
        "time_last_unix_seconds": epochs[-1].absolute_time_unix_seconds,
        "fixed_ned_origin_ecef_m": origin.tolist(),
        "fixed_ned_origin_geodetic_deg_m": [math.degrees(latitude), math.degrees(longitude), height],
        "fixed_ecef_to_ned": rotation.tolist(),
        "baseline_length_mean_m": float(np.mean(values)),
        "baseline_length_median_m": float(np.median(values)),
        "baseline_length_p05_m": float(np.percentile(values, 5.0)),
        "baseline_length_p95_m": float(np.percentile(values, 95.0)),
        "first_baseline_ned_m": epochs[0].b21_ned_m.tolist(),
        "pacc_official_unit": "0.1_mm_decoded_as_1e-4_m",
        "covariance_contract": "R1=pAcc1^2*I3;R2=pAcc2^2*I3;Rrel=R1+R2",
        "cross_receiver_solution_error_independence_exact": False,
        "correlation_limitation": "GNSS1/GNSS2 solution errors may be correlated; independence is a declared instantiation",
        "pacc1_median_m": float(np.median(pacc1_values)),
        "pacc2_median_m": float(np.median(pacc2_values)),
        "receiver1_valid_count": sum(epoch.receiver1_valid for epoch in epochs),
        "receiver2_valid_count": sum(epoch.receiver2_valid for epoch in epochs),
        "trace_open_count": 0,
        "timing_search_used": False,
        "sign_search_used": False,
        "offset_search_used": False,
    }
    return SolutionPositionProvider(
        epochs=tuple(epochs),
        origin_ecef_m=origin,
        origin_geodetic_deg_m=(math.degrees(latitude), math.degrees(longitude), height),
        ecef_to_ned=rotation,
        source_hashes=source_hashes,
        diagnostics=diagnostics,
    )


@dataclass(frozen=True)
class ImuSample:
    absolute_time_unix_seconds: float
    angular_rate_frd_radps: np.ndarray
    specific_force_frd_mps2: np.ndarray


def _float_text(value: str, label: str) -> float:
    try:
        parsed = float(value.strip().strip("'\""))
    except ValueError as exc:
        raise Ext05ProviderError(f"invalid Go2 {label}") from exc
    if not math.isfinite(parsed):
        raise Ext05ProviderError(f"nonfinite Go2 {label}")
    return parsed


def _imu_only_messages(path: Path) -> Iterable[tuple[float, np.ndarray, np.ndarray]]:
    """Stream only stamp/gyro/acc fields; never parse quaternion/RPY/yaw."""

    sec: int | None = None
    nanosec: int | None = None
    gyro: list[float] = []
    accel: list[float] = []
    top = ""
    array = ""
    array_indent = -1

    def finish() -> tuple[float, np.ndarray, np.ndarray] | None:
        if sec is None and nanosec is None and not gyro and not accel:
            return None
        if sec is None or nanosec is None or len(gyro) != 3 or len(accel) != 3:
            raise Ext05ProviderError("Go2 IMU-only message is incomplete")
        return sec + nanosec * 1.0e-9, np.asarray(gyro), np.asarray(accel)

    with path.open("r", encoding="utf-8", errors="strict") as handle:
        for line in handle:
            stripped = line.strip()
            indent = len(line) - len(line.lstrip(" "))
            if stripped == "---":
                item = finish()
                if item is not None:
                    yield item
                sec = nanosec = None
                gyro = []
                accel = []
                top = array = ""
                array_indent = -1
                continue
            if not stripped or stripped.startswith("#"):
                continue
            if indent == 0 and stripped.endswith(":"):
                top = stripped[:-1]
                array = ""
                array_indent = -1
                continue
            if top == "stamp" and ":" in stripped:
                key, value = stripped.split(":", 1)
                if key == "sec":
                    sec = int(_float_text(value, "stamp.sec"))
                elif key == "nanosec":
                    nanosec = int(_float_text(value, "stamp.nanosec"))
                continue
            if top != "imu_state":
                continue
            if stripped in {"gyroscope:", "accelerometer:"}:
                array = stripped[:-1]
                array_indent = indent
                continue
            # The ROS2 YAML emitter places list markers at the same indentation
            # as their owning key (``  gyroscope:`` then ``  - value``).
            if array and indent >= array_indent and stripped.startswith("-"):
                target = gyro if array == "gyroscope" else accel
                target.append(_float_text(stripped[1:], array))
                continue
            if array and indent <= array_indent:
                array = ""
                array_indent = -1
        item = finish()
        if item is not None:
            yield item


def euler_rpy_deg_to_matrix(roll_deg: float, pitch_deg: float, yaw_deg: float) -> np.ndarray:
    roll, pitch, yaw = map(math.radians, (roll_deg, pitch_deg, yaw_deg))
    cr, sr = math.cos(roll), math.sin(roll)
    cp, sp = math.cos(pitch), math.sin(pitch)
    cy, sy = math.cos(yaw), math.sin(yaw)
    rx = np.array([[1.0, 0.0, 0.0], [0.0, cr, -sr], [0.0, sr, cr]])
    ry = np.array([[cp, 0.0, sp], [0.0, 1.0, 0.0], [-sp, 0.0, cp]])
    rz = np.array([[cy, -sy, 0.0], [sy, cy, 0.0], [0.0, 0.0, 1.0]])
    return rz @ ry @ rx


def build_imu_only_provider(
    go2_body: Path,
    *,
    raw_root: Path,
    by2_hash_lock: Path,
) -> tuple[tuple[ImuSample, ...], dict[str, Any], dict[str, Any]]:
    source_hash = verify_hash_locked_file(go2_body, raw_root=raw_root, hash_lock=by2_hash_lock)
    install = euler_rpy_deg_to_matrix(*IMU_INSTALL_RPY_DEG)
    flu_to_frd = np.diag([1.0, -1.0, -1.0])
    transform = install @ flu_to_frd
    samples: list[ImuSample] = []
    for timestamp, gyro_flu, accel_flu in _imu_only_messages(go2_body):
        samples.append(ImuSample(
            absolute_time_unix_seconds=timestamp,
            angular_rate_frd_radps=transform @ gyro_flu,
            specific_force_frd_mps2=transform @ accel_flu,
        ))
    times = np.asarray([sample.absolute_time_unix_seconds for sample in samples])
    if len(samples) != EXPECTED_IMU_SAMPLES:
        raise Ext05ProviderError(f"Go2 IMU-only count is {len(samples)}, expected 63278")
    if np.any(~np.isfinite(times)) or np.any(np.diff(times) <= 0.0):
        raise Ext05ProviderError("Go2 IMU-only timestamps are not unique chronological")
    gyro = np.asarray([sample.angular_rate_frd_radps for sample in samples])
    accel = np.asarray([sample.specific_force_frd_mps2 for sample in samples])
    if np.any(~np.isfinite(gyro)) or np.any(~np.isfinite(accel)):
        raise Ext05ProviderError("Go2 IMU-only projection contains nonfinite values")
    report = {
        "schema_version": "horizontal_literature.ext05.imu_only_provider.v1",
        "sample_count": len(samples),
        "first_time_unix_seconds": float(times[0]),
        "last_time_unix_seconds": float(times[-1]),
        "median_dt_seconds": float(np.median(np.diff(times))),
        "frame_input": "GO2_BODY_FLU",
        "frame_output": "FRD",
        "flu_to_frd": ["x", "-y", "-z"],
        "active_installation_rpy_deg": IMU_INSTALL_RPY_DEG.tolist(),
        "installation_composition": "RzRyRx_active_after_FLU_to_FRD",
        "quaternion_materialized": False,
        "rpy_materialized": False,
        "yaw_materialized": False,
        "go2_navigation_state_materialized": False,
        "trace_open_count": 0,
    }
    return tuple(samples), report, source_hash


def local_normal_gravity_mps2(latitude_deg: float, height_m: float) -> float:
    latitude = math.radians(latitude_deg)
    sine_sq = math.sin(latitude) ** 2
    surface = 9.7803253359 * (1.0 + 0.00193185265241 * sine_sq) / math.sqrt(
        1.0 - 0.00669437999013 * sine_sq
    )
    return surface - 3.086e-6 * height_m


@dataclass(frozen=True)
class StaticCalibration:
    start_time_unix_seconds: float
    end_time_unix_seconds: float
    sample_count: int
    used_preregistered_initial_interval: bool
    gyro_bias_frd_radps: np.ndarray
    mean_specific_force_frd_mps2: np.ndarray
    gyro_norm_median_radps: float
    acceleration_norm_median_mps2: float
    local_gravity_mps2: float
    max_internal_gap_seconds: float


def _calibration_window(
    samples: Sequence[ImuSample], start_index: int, duration_seconds: float
) -> tuple[int, Sequence[ImuSample]]:
    start = samples[start_index].absolute_time_unix_seconds
    end = start + duration_seconds
    stop = start_index
    while stop < len(samples) and samples[stop].absolute_time_unix_seconds <= end:
        stop += 1
    return stop, samples[start_index:stop]


def calibrate_static_imu(
    samples: Sequence[ImuSample],
    *,
    latitude_deg: float,
    height_m: float,
    duration_seconds: float = 5.0,
) -> StaticCalibration:
    """Apply the pre-registered first-input-only-static-window rule."""

    if not samples:
        raise Ext05ProviderError("IMU calibration source is empty")
    gravity = local_normal_gravity_mps2(latitude_deg, height_m)
    median_dt = float(np.median(np.diff([
        sample.absolute_time_unix_seconds for sample in samples
    ])))
    gap_bound = max(0.1, 5.0 * median_dt)
    selected: tuple[int, Sequence[ImuSample], float, float, float] | None = None
    for start_index in range(len(samples)):
        stop, window = _calibration_window(samples, start_index, duration_seconds)
        if not window or window[-1].absolute_time_unix_seconds - window[0].absolute_time_unix_seconds < duration_seconds - 2.0 * median_dt:
            continue
        times = np.asarray([sample.absolute_time_unix_seconds for sample in window])
        maximum_gap = float(np.max(np.diff(times))) if len(times) > 1 else math.inf
        gyro_median = float(np.median([
            np.linalg.norm(sample.angular_rate_frd_radps) for sample in window
        ]))
        accel_median = float(np.median([
            np.linalg.norm(sample.specific_force_frd_mps2) for sample in window
        ]))
        static = (
            maximum_gap <= gap_bound
            and gyro_median < 0.05
            and abs(accel_median - gravity) <= 0.5
        )
        if static:
            selected = start_index, window, maximum_gap, gyro_median, accel_median
            break
        if start_index == 0:
            # The loop then performs the authorized first-contiguous-window fallback.
            continue
    if selected is None:
        raise Ext05ProviderError("no input-only contiguous static five-second interval")
    start_index, window, maximum_gap, gyro_median, accel_median = selected
    gyro_bias = np.mean([sample.angular_rate_frd_radps for sample in window], axis=0)
    mean_force = np.mean([sample.specific_force_frd_mps2 for sample in window], axis=0)
    return StaticCalibration(
        start_time_unix_seconds=window[0].absolute_time_unix_seconds,
        end_time_unix_seconds=window[0].absolute_time_unix_seconds + duration_seconds,
        sample_count=len(window),
        used_preregistered_initial_interval=start_index == 0,
        gyro_bias_frd_radps=np.asarray(gyro_bias),
        mean_specific_force_frd_mps2=np.asarray(mean_force),
        gyro_norm_median_radps=gyro_median,
        acceleration_norm_median_mps2=accel_median,
        local_gravity_mps2=gravity,
        max_internal_gap_seconds=maximum_gap,
    )


def initial_attitude_from_gravity_and_baseline(
    mean_specific_force_frd_mps2: Sequence[float],
    measured_baseline_ned_m: Sequence[float],
    known_baseline_frd_m: Sequence[float] = BASELINE_BODY_FRD_M,
) -> tuple[np.ndarray, dict[str, float]]:
    """Input-only roll/pitch from gravity and yaw from GNSS2-GNSS1."""

    force = np.asarray(mean_specific_force_frd_mps2, dtype=float)
    baseline_ned = np.asarray(measured_baseline_ned_m, dtype=float)
    baseline_body = np.asarray(known_baseline_frd_m, dtype=float)
    if any(value.shape != (3,) or np.any(~np.isfinite(value)) for value in (force, baseline_ned, baseline_body)):
        raise Ext05ProviderError("initialization vectors must be finite three-vectors")
    force_norm = float(np.linalg.norm(force))
    if force_norm <= 0.0:
        raise Ext05ProviderError("initial mean specific force is zero")
    pitch = math.asin(float(np.clip(force[0] / force_norm, -1.0, 1.0)))
    roll = math.atan2(-force[1], -force[2])
    roll_pitch = euler_rpy_deg_to_matrix(math.degrees(roll), math.degrees(pitch), 0.0)
    rotated_body_baseline = roll_pitch @ baseline_body
    horizontal_measured = math.hypot(baseline_ned[0], baseline_ned[1])
    horizontal_known = math.hypot(rotated_body_baseline[0], rotated_body_baseline[1])
    if horizontal_measured <= 0.1 or horizontal_known <= 0.1:
        raise Ext05ProviderError("initial baseline has inadequate horizontal magnitude")
    measured_heading = math.atan2(baseline_ned[1], baseline_ned[0])
    zero_yaw_heading = math.atan2(rotated_body_baseline[1], rotated_body_baseline[0])
    yaw = measured_heading - zero_yaw_heading
    attitude = euler_rpy_deg_to_matrix(
        math.degrees(roll), math.degrees(pitch), math.degrees(yaw)
    )
    gravity_alignment = attitude @ (force / force_norm)
    if float(np.linalg.norm(gravity_alignment - np.array([0.0, 0.0, -1.0]))) > 0.02:
        raise Ext05ProviderError("initial attitude violates C_nb*f_b + g_n = 0")
    return attitude, {
        "roll_deg": math.degrees(roll),
        "pitch_deg": math.degrees(pitch),
        "yaw_ned_deg": math.degrees(yaw) % 360.0,
        "measured_baseline_heading_ned_deg": math.degrees(measured_heading) % 360.0,
        "gravity_alignment_error": float(np.linalg.norm(
            gravity_alignment - np.array([0.0, 0.0, -1.0])
        )),
    }
