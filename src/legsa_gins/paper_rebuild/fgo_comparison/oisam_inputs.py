"""Read only the frozen GNSS/Go2 IMU providers required by OiSAM-FGO.

No evaluator, reference, previous NAV, or other-method output is an input.
The provider's right-endpoint increments already contain dt, installation and
the frozen acceleration scale. None of these operations is repeated here.
"""
from __future__ import annotations

from dataclasses import dataclass
import csv
import hashlib
import json
from pathlib import Path

import numpy as np
import yaml

from ...datasets.by2.go2_body_state_parser import _array, _scalar


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def llh_to_ecef(llh_deg_m):
    lat, lon = np.deg2rad(np.asarray(llh_deg_m, float)[:2])
    height = float(llh_deg_m[2])
    a, e2 = 6378137.0, 6.6943799901413165e-3
    n = a / np.sqrt(1.0 - e2 * np.sin(lat) ** 2)
    return np.array([(n + height) * np.cos(lat) * np.cos(lon),
                     (n + height) * np.cos(lat) * np.sin(lon),
                     (n * (1.0 - e2) + height) * np.sin(lat)])


def ecef_to_ned_rotation(llh_deg_m):
    lat, lon = np.deg2rad(np.asarray(llh_deg_m, float)[:2])
    s, c, sl, cl = np.sin(lat), np.cos(lat), np.sin(lon), np.cos(lon)
    return np.array([[-s * cl, -s * sl, c], [-sl, cl, 0.0],
                     [-c * cl, -c * sl, -s]])


def ecef_to_llh(ecef):
    """WGS84 inverse for the ordinary terrestrial navigation domain."""
    x, y, z = np.asarray(ecef, float)
    a, e2 = 6378137.0, 6.6943799901413165e-3
    rho = np.hypot(x, y)
    latitude = np.arctan2(z, rho * (1.0 - e2))
    for _ in range(10):
        radius = a / np.sqrt(1.0 - e2 * np.sin(latitude) ** 2)
        updated = np.arctan2(z + e2 * radius * np.sin(latitude), rho)
        if abs(updated - latitude) < 1e-14:
            latitude = updated
            break
        latitude = updated
    radius = a / np.sqrt(1.0 - e2 * np.sin(latitude) ** 2)
    height = rho / np.cos(latitude) - radius
    return np.array([np.rad2deg(latitude), np.rad2deg(np.arctan2(y, x)), height])


def select_nodes(gnss: np.ndarray, end_s: float, tolerance_s: float):
    """Nearest original observation at each integer second; never retime it.

    Missing seconds remain explicit expected nodes, with row=None. Selecting a
    timestamp precedes any validity/accuracy checks, so support is not selected
    for a favorable measurement value.
    """
    times = gnss[:, 0]
    nodes = []
    for second in range(int(np.ceil(times[0])), int(np.floor(end_s)) + 1):
        i = int(np.searchsorted(times, second))
        candidates = [j for j in (i - 1, i) if 0 <= j < len(times)]
        j = min(candidates, key=lambda x: (abs(times[x] - second), x))
        if abs(times[j] - second) <= tolerance_s:
            nodes.append((float(times[j]), gnss[j].copy(), second))
        else:
            nodes.append((float(second), None, second))
    return nodes


def exact_imu_intervals(imu, raw_times, max_dt=.1):
    """Match the frozen builder's retained rows to its unrounded raw stamps."""
    raw_times = np.asarray(raw_times, float)
    raw_dt = np.diff(raw_times)
    if not np.isfinite(raw_times).all() or np.any(raw_dt < 0):
        raise ValueError("RAW_IMU_TIME_INVALID")
    retained = np.flatnonzero((raw_dt > 0) & (raw_dt <= max_dt)) + 1
    if len(retained) != len(imu) or np.any(np.abs(imu[:, 0] - raw_times[retained]) > .56e-6):
        raise ValueError("RAW_PROVIDER_IMU_TIME_IDENTITY_MISMATCH")
    return np.column_stack((raw_times[retained - 1], raw_times[retained]))


def read_raw_times(path, base_time):
    """Time-only counterpart of wen_ahrs.read_raw_quaternions.

    Gyro/accelerometer fields are checked for record completeness exactly as in
    the common raw builder. Their values, quaternions, and Go2 odometry never
    become OiSAM measurements here. SHA256 is computed from the same read.
    """
    digest, times = hashlib.sha256(), []
    counts = {"message_count": 0, "incomplete_imu_messages": 0}

    def consume(lines):
        if not any(line.strip() for line in lines):
            return
        counts["message_count"] += 1
        try:
            sec = int(_scalar(lines, ["stamp", "sec"]))
            nsec = int(_scalar(lines, ["stamp", "nanosec"]))
            gyro = np.asarray(_array(lines, ["imu_state", "gyroscope"], 3), float)
            accel = np.asarray(_array(lines, ["imu_state", "accelerometer"], 3), float)
            complete = np.isfinite(gyro).all() and np.isfinite(accel).all() and 0 <= nsec < 1000000000
        except (TypeError, ValueError, OverflowError):
            complete = False
        if complete:
            # Match the source parser's floating-point operation order.
            times.append(sec + nsec * 1e-9 - float(base_time))
        else:
            counts["incomplete_imu_messages"] += 1

    with Path(path).open("rb") as stream:
        message = []
        for payload in stream:
            digest.update(payload)
            line = payload.decode("utf-8-sig").rstrip("\r\n")
            if line.strip() == "---":
                consume(message)
                message = []
            else:
                message.append(line)
        consume(message)
    if len(times) < 2:
        raise ValueError("NO_COMPLETE_RAW_IMU_TIMELINE")
    return np.asarray(times), digest.hexdigest(), counts


def imu_pieces(imu: np.ndarray, begin_s: float, end_s: float, max_dt: float, intervals=None):
    """Return (dt, dtheta, dvel) for exact overlap of original intervals.

    Splitting an endpoint uses its frozen current-sample rate. A retained-row
    gap > max_dt is NOT the duration of its last increment: such an interval is
    unsupported and raises. No interpolation or zero/held-rate gap fill occurs.
    """
    if end_s <= begin_s:
        raise ValueError("NONPOSITIVE_PREINTEGRATION_INTERVAL")
    if intervals is None:
        # Synthetic tests use exact generated stamps. Production always passes
        # source-bound intervals from exact_imu_intervals, never rounded dt.
        intervals = np.column_stack((imu[:-1, 0], imu[1:, 0]))
        measured = imu[1:]
    else:
        intervals = np.asarray(intervals)
        measured = imu
    if begin_s < intervals[0, 0] or end_s > intervals[-1, 1]:
        raise ValueError("IMU_SUPPORT_UNAVAILABLE")
    first = int(np.searchsorted(intervals[:, 1], begin_s, side="right"))
    last = int(np.searchsorted(intervals[:, 1], end_s, side="left"))
    pieces = []
    covered = 0.0
    cursor = begin_s
    for i in range(first, last + 1):
        left, right = intervals[i]
        dt = float(right - left)
        overlap = float(min(right, end_s) - max(left, begin_s))
        if overlap <= 0:
            continue
        if not 0.0 < dt <= max_dt:
            raise ValueError(f"IMU_GAP:{left:.9f}:{right:.9f}")
        if left > cursor + 1e-7:
            raise ValueError(f"IMU_GAP:{cursor:.9f}:{left:.9f}")
        if not np.isfinite(measured[i, 1:]).all():
            raise ValueError("IMU_NONFINITE")
        fraction = overlap / dt
        pieces.append((overlap, measured[i, 1:4] * fraction, measured[i, 4:7] * fraction))
        covered += overlap
        cursor = min(right, end_s)
    if abs(covered - (end_s - begin_s)) > 1e-7:
        raise ValueError("IMU_GAP_INTERVAL_NOT_COVERED")
    return pieces


def position_valid(row):
    return (row is not None and row[15] > 0.5 and
            np.isfinite(row[1:7]).all() and np.all(row[4:7] > 0.0))


def initialization_valid(row):
    return (position_valid(row) and row[17] > 0.5 and
            np.isfinite(row[13:15]).all() and row[14] > 0.0)


@dataclass
class SequenceInput:
    sequence: str
    gnss: np.ndarray
    imu: np.ndarray
    nodes: list
    metadata: dict
    imu_intervals: np.ndarray | None = None


def read_sequence(roots_path, sequence: str, config: dict) -> SequenceInput:
    if sequence not in config["gravity_mps2"]:
        raise ValueError("SEQUENCE_NOT_REGISTERED")
    roots = json.loads(Path(roots_path).read_text())["aliases"]

    def resolve(value):
        for alias, path in roots.items():
            value = value.replace(alias, path)
        if "<" in value or ">" in value:
            raise ValueError("UNRESOLVED_INPUT_ALIAS")
        return Path(value)

    contract_path = resolve(config["execution_contract"])
    contract = yaml.safe_load(contract_path.read_text())
    spec = contract["sequences"][sequence]
    portable = config["provider_template"].format(sequence=sequence)
    provider_path = portable
    for alias, path in roots.items():
        provider_path = provider_path.replace(alias, path)
    root = Path(provider_path)
    bundle_path = root / "CALIBRATED_PROVIDER_BUNDLE.json"
    bundle = json.loads(bundle_path.read_text())
    if (bundle.get("dataset_id") != sequence or bundle.get("model_sha256") != contract["model"]["sha256"]
            or bundle["audit"]["base_time"] != spec["base_time"]):
        raise ValueError("PROVIDER_SEQUENCE_IDENTITY")
    for name in ("synthetic_data_used", "semisynthetic_data_used", "trace_used_online",
                 "receiver_imu_as_body_imu", "final_v23_output_solver_input",
                 "LegSA_output_solver_input", "per_case_tuning", "output_only_correction",
                 "epoch_deleted_for_metric"):
        if bundle.get(name) is not False:
            raise ValueError(f"PROVIDER_FORBIDDEN_FLAG:{name}")
    if bundle.get("old_runtime_input_count") != 0:
        raise ValueError("PROVIDER_OLD_RUNTIME_INPUT")
    providers = bundle["variants"]["V2s"]["providers"]
    arrays, pins = {}, {}
    for role, filename, width in (("imupath", "CALIBRATED_IMU.imu", 7),
                                  ("gnsspath", "CALIBRATED_GNSS.gnss", 18)):
        path = root / filename
        digest = sha256(path)
        if digest != providers[role]["sha256"] or digest != config["frozen_provider_sha256"][sequence][role]:
            raise ValueError(f"PROVIDER_HASH_MISMATCH:{role}")
        array = np.loadtxt(path, ndmin=2)
        if array.shape[1] != width or not np.all(np.diff(array[:, 0]) > 0):
            raise ValueError(f"PROVIDER_SCHEMA_OR_TIME:{role}")
        arrays[role] = array
        pins[role] = {"path": f"{portable}/{filename}", "sha256": digest,
                      "rows": len(array)}
    window = bundle["audit"]["window_seconds"]
    nodes = select_nodes(arrays["gnsspath"], window[1], config["maximum_gnss_node_offset_s"])
    raw_pin = spec["raw_inputs"]["body"]
    raw_path, raw_lock = resolve(raw_pin["path"]), resolve(spec["raw_lock"]["path"])
    if sha256(raw_lock) != spec["raw_lock"]["sha256"]:
        raise ValueError("RAW_HASH_LOCK_IDENTITY")
    relative = raw_path.relative_to(resolve("<RAW_ROOT>")).as_posix()
    with raw_lock.open(encoding="utf-8-sig", newline="") as stream:
        locked = next((r for r in csv.DictReader(stream) if r["relative_path"].replace("\\", "/") == relative), None)
    if locked is None or locked["sha256"] != raw_pin["sha256"]:
        raise ValueError("RAW_BODY_NOT_BOUND_TO_LOCK")
    raw_times, raw_digest, parser_counts = read_raw_times(raw_path, spec["base_time"])
    if raw_digest != raw_pin["sha256"] or raw_digest != bundle["raw_source_hashes"]["body"]["sha256"]:
        raise ValueError("RAW_BODY_HASH_MISMATCH")
    intervals = exact_imu_intervals(arrays["imupath"], raw_times, config["maximum_imu_interval_s"])
    gap_indices = np.flatnonzero(intervals[1:, 0] - intervals[:-1, 1] > 1e-7)
    gaps = [[float(intervals[i, 1]), float(intervals[i + 1, 0])] for i in gap_indices]
    raw = {role: {"path": "<RAW_ROOT>/" + item["raw_relative_path"],
                  "sha256": item["sha256"]}
           for role, item in bundle["raw_source_hashes"].items()}
    metadata = {"sequence": sequence, "base_time": bundle["audit"]["base_time"],
                "evaluation_window_s": window, "input_provider_hashes": pins,
                "raw_source_hashes": raw, "raw_hash_status": "BODY_VERIFIED_FROM_SAME_READ_OTHER_ROLES_INHERITED_FROM_FROZEN_BUNDLE",
                "raw_body_time_reader_counts": parser_counts,
                "raw_lock": spec["raw_lock"], "execution_contract_sha256": sha256(contract_path),
                "raw_current_sample_interval_identity": "PASS_ALL_PROVIDER_ROWS_WITHIN_0.56_MICROSECOND_ROUNDING",
                "imu_interval_count": len(intervals), "imu_dt_source": "unrounded_source_raw_stamps",
                "provider_bundle_sha256": sha256(bundle_path),
                "provider_bundle_path": f"{portable}/CALIBRATED_PROVIDER_BUNDLE.json",
                "provider_code_commit": bundle["code_commit"],
                "provider_model_sha256": bundle["model_sha256"],
                "imu_gaps_s": gaps, "imu_transform_reapplied": False,
                "acceleration_scale_reapplied": False, "receiver_imu_as_body_imu": False}
    return SequenceInput(sequence, arrays["gnsspath"], arrays["imupath"], nodes, metadata, intervals)


def run_sequence(roots_path, sequence, out_dir, config_path):
    """Public runner adapter; import the scientific backend only on execution."""
    from .oisam import run_sequence as execute
    return execute(roots_path, sequence, out_dir, config_path)
