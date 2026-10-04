"""Sensor-only external-AHRS adapter for Wen2021 TC Eq. (3)/(25).

The paper's commercial AHRS is replaced by the recorded Go2 quaternion plus
one initial A1 body heading. This is an explicit engineering adaptation, not a
continuous dual-antenna factor. For raw FLU quaternion Rq and the already used
body installation Ri, C_NED<-corrected_body = Rz(alpha) D Rq D Ri.T, where
D=diag(1,-1,-1) and alpha is fixed once. The input calibrated IMU already has
D, Ri, the frozen BY2 acceleration scale, and initial gyro bias applied.

The seven-column IMU stores *current-sample measured-dt* increments. Its rounded
timestamps cannot recover a dropped interval: the original raw stamp sequence
is used to reconstruct each retained increment's exact integration interval.
No raw force/gyro is applied a second time. Missing support omits an INS link;
it is never padded with zero acceleration or a reference-derived trajectory.
"""
from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import numpy as np
import yaml
from scipy.spatial.transform import Rotation, Slerp

from ...datasets.by2.go2_body_state_parser import _array, _scalar
from ..clean5_imu_parity.input_audit import gravity_model
from .wen_tc import WenInputError


def _sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _resolve(value, aliases):
    value = str(value)
    for key, replacement in sorted(aliases.items(), key=lambda item: -len(item[0])):
        value = value.replace(key, str(replacement))
    if "<" in value or ">" in value:
        raise WenInputError("unresolved path alias")
    path = Path(value)
    if not path.is_absolute() or any(part.is_symlink() for part in (path, *path.parents)):
        raise WenInputError("absolute non-symlink sensor path required")
    return path


def read_raw_quaternions(path, base_time):
    """Read only stamp and IMU fields, never Go2 odometry/contact/leg states.

    Retain timestamps whenever the original increment builder had a complete
    gyro/accelerometer record, independently of quaternion validity. The final
    message is admitted iff these IMU fields are complete, matching the source
    parser; a missing final YAML separator does not itself remove a valid IMU.
    Return the raw SHA during the same read. No source file is modified.
    """
    digest = hashlib.sha256()
    raw_times, quaternion_times, quaternions = [], [], []
    counts = {"message_count": 0, "incomplete_imu_messages": 0,
              "invalid_quaternion_messages": 0, "normalized_quaternion_messages": 0}

    def consume(lines):
        if not any(line.strip() for line in lines):
            return
        counts["message_count"] += 1
        try:
            sec = int(_scalar(lines, ["stamp", "sec"]))
            nsec = int(_scalar(lines, ["stamp", "nanosec"]))
            gyro = np.asarray(_array(lines, ["imu_state", "gyroscope"], 3), float)
            accel = np.asarray(_array(lines, ["imu_state", "accelerometer"], 3), float)
            complete = bool(np.isfinite(gyro).all() and np.isfinite(accel).all() and 0 <= nsec < 1000000000)
        except (TypeError, ValueError, OverflowError):
            complete = False
        if not complete:
            counts["incomplete_imu_messages"] += 1
            return
        # Operation order deliberately matches parse_sportmodestate_text.
        time = sec + nsec * 1e-9 - float(base_time)
        raw_times.append(time)
        quat = np.asarray(_array(lines, ["imu_state", "quaternion"], 4), float)
        norm = np.linalg.norm(quat)
        if not np.isfinite(quat).all() or not .9 <= norm <= 1.1:
            counts["invalid_quaternion_messages"] += 1
            return
        counts["normalized_quaternion_messages"] += int(abs(norm - 1) > 1e-8)
        quaternion_times.append(time)
        quaternions.append(quat / norm)

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
    raw_times = np.asarray(raw_times, float)
    quaternion_times = np.asarray(quaternion_times, float)
    quaternions = np.asarray(quaternions, float).reshape(-1, 4)
    if len(raw_times) < 2 or len(quaternion_times) < 2:
        raise WenInputError("no complete raw Go2 IMU/quaternion timeline")
    if np.any(np.diff(raw_times) < 0):
        raise WenInputError("decreasing raw Go2 timestamps require explicit diagnosis")
    # Equal timestamps do not define another integration interval. Keep the
    # last quaternion deterministically, before any reference is available.
    keep = np.r_[np.diff(quaternion_times) > 0, True]
    counts["duplicate_quaternion_timestamps"] = int(np.sum(~keep))
    return {"raw_time_rel_s": raw_times, "quaternion_time_rel_s": quaternion_times[keep],
            "quaternion_wxyz": quaternions[keep], "sha256": digest.hexdigest(), **counts}


def corrected_body_to_ned(quaternions_wxyz, alpha_rad, install_rpy_deg=(-1., 0., 0.)):
    """Apply the source-declared FLU/world-z-up and body-installation changes."""
    q = np.asarray(quaternions_wxyz, float)
    if q.ndim != 2 or q.shape[1] != 4 or not np.isfinite(q).all() or np.any(np.linalg.norm(q, axis=1) < 1e-12):
        raise WenInputError("finite wxyz quaternions required")
    rq = Rotation.from_quat(q[:, [1, 2, 3, 0]]).as_matrix()
    install = Rotation.from_euler("xyz", install_rpy_deg, degrees=True).as_matrix()
    d = np.diag([1., -1., -1.])
    heading = Rotation.from_rotvec([0., 0., float(alpha_rad)]).as_matrix()
    return heading @ d @ rq @ d @ install.T


def _rotation_at(source_times, matrices, query_times, maximum_gap_s):
    source_times, query_times = np.asarray(source_times, float), np.asarray(query_times, float)
    matrices = np.asarray(matrices, float)
    if len(source_times) < 2 or np.any(np.diff(source_times) <= 0):
        raise WenInputError("strictly increasing quaternion interpolation support required")
    valid = (query_times >= source_times[0]) & (query_times <= source_times[-1])
    right = np.searchsorted(source_times, query_times, side="left").clip(1, len(source_times) - 1)
    exact = np.minimum(abs(query_times - source_times[right]), abs(query_times - source_times[right - 1])) <= 1e-10
    valid &= exact | (source_times[right] - source_times[right - 1] <= maximum_gap_s)
    result = np.broadcast_to(np.eye(3), (len(query_times), 3, 3)).copy()
    if valid.any():
        result[valid] = Slerp(source_times, Rotation.from_matrix(matrices))(query_times[valid]).as_matrix()
    return result, valid


def _linear_at(source_times, values, query_times, maximum_gap_s):
    if len(source_times) < 2:
        return np.zeros((len(query_times), 3)), np.zeros(len(query_times), dtype=bool)
    right = np.searchsorted(source_times, query_times, side="left").clip(1, len(source_times) - 1)
    exact = np.minimum(abs(query_times - source_times[right]), abs(query_times - source_times[right - 1])) <= 1e-10
    valid = ((query_times >= source_times[0]) & (query_times <= source_times[-1])
             & (exact | (source_times[right] - source_times[right - 1] <= maximum_gap_s)))
    result = np.column_stack([np.interp(query_times, source_times, values[:, axis]) for axis in range(3)])
    result[~valid] = 0.
    return result, valid


def integrate_ahrs(*, times, imu, raw_times, quaternion_times, rotation_ecef_from_body,
                   gravity_ecef_mps2, seed_time_s, lever_body_m, maximum_gap_s=.1,
                   ins_discretization="HIGH_RATE_INTEGRAL_LEGACY"):
    """Pure array integration for real preparation and separate synthetic tests.

    For IMU-specific force f, body bias b and antenna lever l, the antenna
    velocity equation is dv_A = integral(R(f-b)+g)dt + [R(omega cross l)]_i^j.
    All rotations/omega are input data, not variables or attitude priors.
    Fractional boundary intervals preserve the original right-endpoint force
    convention. Uncovered intervals are explicitly invalid, with no filling.
    """
    times, imu, raw_times = map(lambda v: np.asarray(v, float), (times, imu, raw_times))
    quaternion_times = np.asarray(quaternion_times, float)
    rotations = np.asarray(rotation_ecef_from_body, float)
    if (times.ndim != 1 or len(times) < 2 or not np.isfinite(times).all() or np.any(np.diff(times) <= 0)
            or imu.ndim != 2 or imu.shape[1] != 7 or not np.isfinite(imu).all()
            or len(imu) < 2 or not np.isfinite(raw_times).all() or np.any(np.diff(raw_times) < 0)):
        raise WenInputError("invalid graph/IMU timeline")
    source_dt = np.diff(raw_times)
    source_index = np.flatnonzero((source_dt > 0) & (source_dt <= .1)) + 1
    if len(source_index) != len(imu) or np.any(abs(imu[:, 0] - raw_times[source_index]) > .56e-6):
        raise WenInputError("calibrated IMU is not the source current-sample interval sequence")
    end, start = raw_times[source_index], raw_times[source_index - 1]
    dt = end - start
    sample_rotation, sample_valid = _rotation_at(quaternion_times, rotations, end, maximum_gap_s)
    node_rotation, node_valid = _rotation_at(quaternion_times, rotations, times, maximum_gap_s)
    node_valid &= times >= seed_time_s
    gravity = np.asarray(gravity_ecef_mps2, float)
    lever = np.asarray(lever_body_m, float)
    if gravity.shape != (3,) or lever.shape != (3,) or not np.isfinite(gravity).all() or not np.isfinite(lever).all():
        raise WenInputError("finite gravity and fixed lever vectors required")
    angular_rate_body = imu[:, 1:4] / dt[:, None]
    lever_velocity = np.einsum("nij,nj->ni", sample_rotation, np.cross(angular_rate_body, lever))
    lever_at_node, lever_valid = _linear_at(end[sample_valid], lever_velocity[sample_valid], times, maximum_gap_s)
    node_valid &= lever_valid
    delta_velocity = np.zeros((len(times) - 1, 3))
    bias_integral = np.zeros((len(times) - 1, 3, 3))
    coverage = np.zeros(len(times) - 1)
    for i, (lo, hi) in enumerate(zip(times[:-1], times[1:])):
        left = np.searchsorted(end, lo, side="right")
        right = np.searchsorted(start, hi, side="left")
        ix = np.arange(left, right)
        overlap = np.maximum(0., np.minimum(hi, end[ix]) - np.maximum(lo, start[ix]))
        overlap *= sample_valid[ix]
        coverage[i] = overlap.sum()
        rotated_dvel = np.einsum("nij,nj->ni", sample_rotation[ix], imu[ix, 4:7])
        delta_velocity[i] = np.sum(rotated_dvel * (overlap / dt[ix])[:, None], axis=0) + gravity * coverage[i]
        bias_integral[i] = np.sum(sample_rotation[ix] * overlap[:, None, None], axis=0)
    force_node, force_valid = _linear_at(end, imu[:,4:7]/dt[:,None], times, maximum_gap_s)
    linear_body = force_node + np.einsum("nji,j->ni",node_rotation,gravity)
    node_valid &= force_valid
    if ins_discretization == "RIGHT_ENDPOINT_ACCELERATION_EQ25":
        # The paper's A_k is body-frame linear acceleration, rather than specific
        # force. This sensor adapter removes normal gravity once using the AHRS.
        delta_velocity = np.einsum("nij,nj->ni",node_rotation[1:],linear_body[1:])*np.diff(times)[:,None]
        bias_integral = node_rotation[1:]*np.diff(times)[:,None,None]
    elif ins_discretization != "HIGH_RATE_INTEGRAL_LEGACY":
        raise WenInputError("unknown INS acceleration discretization")
    valid = node_valid[:-1] & node_valid[1:] & (abs(coverage - np.diff(times)) <= 1e-6)
    return {"time_rel_s": times.copy(), "rotation_ecef_from_body": node_rotation,
            "node_valid": node_valid, "delta_velocity_ecef_mps": delta_velocity,
            "linear_acceleration_body_mps2": linear_body,
            "specific_force_body_mps2": force_node,
            "ins_discretization": ins_discretization,
            "bias_integral_ecef_s": bias_integral,
            "lever_velocity_delta_ecef_mps": np.diff(lever_at_node, axis=0),
            "interval_valid": valid, "interval_imu_coverage_s": coverage,
            "source_imu_retained_interval_count": len(imu),
            "source_imu_skipped_interval_count": int(len(source_dt) - len(source_index)),
            "missing_ahrs_sample_count": int(np.sum(~sample_valid))}


def prepare_ahrs(roots_path, sequence, times, config=None):
    """Prepare source-pinned Wen AHRS inputs; caller owns saving and execution.

    Only the raw Go2 text, frozen calibrated GNSS18/IMU7 providers, and their
    metadata/hash lock are opened. GNSS18 supplies exactly one heading gauge,
    and one initial LLH defining the fixed local gravity/ECEF basis. It does
    not supply an ongoing position/velocity/attitude factor or initial NAV.
    No trace/reference path is resolved or opened by this module.
    """
    aliases = json.loads(Path(roots_path).read_text(encoding="utf-8"))["aliases"]
    code_root = _resolve("<CODE_ROOT>", aliases)
    if config is None:
        config = json.loads((code_root / "configs/paper_rebuild/fgo_comparison/WEN_TC_2021.json").read_text())
    preparation = config["preparation"]
    contract_path = _resolve(preparation["execution_contract"], aliases)
    contract = yaml.safe_load(contract_path.read_text(encoding="utf-8"))
    if sequence not in config["frozen_provider_sha256"] or sequence not in contract["sequences"]:
        raise WenInputError("sequence is outside the registered three-sequence queue")
    spec = contract["sequences"][sequence]
    bundle_alias = preparation["provider_bundle_template"].replace("{sequence}", sequence)
    bundle_path = _resolve(bundle_alias, aliases)
    bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
    if (bundle["dataset_id"] != sequence or bundle["model_sha256"] != contract["model"]["sha256"]
            or bundle["trace_used_online"] is not False or bundle["old_runtime_input_count"] != 0):
        raise WenInputError("calibrated provider identity/role mismatch")
    provider_pins = bundle["variants"]["V2s"]["providers"]
    provider_paths, provider_receipts = {}, {}
    for role, name in (("imupath", "CALIBRATED_IMU.imu"), ("gnsspath", "CALIBRATED_GNSS.gnss")):
        path = bundle_path.parent / name
        digest = _sha256(path)
        if digest != provider_pins[role]["sha256"] or digest != config["frozen_provider_sha256"][sequence][role]:
            raise WenInputError("frozen calibrated provider hash mismatch: " + role)
        provider_paths[role] = path
        provider_receipts[role] = {"path": bundle_alias.rsplit("/", 1)[0] + "/" + name, "sha256": digest}
    raw_pin = spec["raw_inputs"]["body"]
    raw_path = _resolve(raw_pin["path"], aliases)
    raw_lock = _resolve(spec["raw_lock"]["path"], aliases)
    if _sha256(raw_lock) != spec["raw_lock"]["sha256"]:
        raise WenInputError("raw hash lock identity mismatch")
    relative = raw_path.relative_to(_resolve("<RAW_ROOT>", aliases)).as_posix()
    with raw_lock.open(encoding="utf-8-sig", newline="") as stream:
        row = next((r for r in csv.DictReader(stream) if r["relative_path"].replace("\\", "/") == relative), None)
    if row is None or row["sha256"] != raw_pin["sha256"]:
        raise WenInputError("Go2 source is not bound to the registered raw lock")
    raw = read_raw_quaternions(raw_path, spec["base_time"])
    if raw["sha256"] != raw_pin["sha256"] or bundle["raw_source_hashes"]["body"]["sha256"] != raw["sha256"]:
        raise WenInputError("raw Go2 source hash mismatch")
    imu = np.loadtxt(provider_paths["imupath"], ndmin=2)
    gnss = np.loadtxt(provider_paths["gnsspath"], ndmin=2)
    if gnss.shape[1] != 18 or not np.isfinite(gnss).all():
        raise WenInputError("frozen GNSS18 schema mismatch")
    qt = raw["quaternion_time_rel_s"]
    unaligned = corrected_body_to_ned(raw["quaternion_wxyz"], 0., preparation["imu_install_rpy_deg"])
    seed_rotation, support = _rotation_at(qt, unaligned, gnss[:, 0], preparation["maximum_ahrs_gap_s"])
    support &= ((gnss[:, 15] == 1) & (gnss[:, 17] == 1)
                & (gnss[:, 0] >= imu[0, 0]) & (gnss[:, 0] <= min(imu[-1, 0], float(times[-1]))))
    if not support.any():
        raise WenInputError("no legal initial A1 heading/position with Go2 AHRS and IMU support")
    seed_index = np.flatnonzero(support)[0]
    initial = gnss[seed_index]
    local_yaw = np.arctan2(seed_rotation[seed_index, 1, 0], seed_rotation[seed_index, 0, 0])
    alpha = (np.deg2rad(initial[13]) - local_yaw + np.pi) % (2 * np.pi) - np.pi
    lat, lon = np.deg2rad(initial[1:3])
    sl, cl, so, co = np.sin(lat), np.cos(lat), np.sin(lon), np.cos(lon)
    ecef_from_ned = np.array([[-sl * co, -so, -cl * co], [-sl * so, co, -cl * so], [cl, 0., -sl]])
    rotations = ecef_from_ned @ corrected_body_to_ned(raw["quaternion_wxyz"], alpha, preparation["imu_install_rpy_deg"])
    gravity = gravity_model(initial[1:4])["g_local_mps2"]
    result = integrate_ahrs(times=times, imu=imu, raw_times=raw["raw_time_rel_s"],
        quaternion_times=qt, rotation_ecef_from_body=rotations,
        gravity_ecef_mps2=ecef_from_ned @ np.array([0., 0., gravity]),
        seed_time_s=initial[0], lever_body_m=preparation["imu_to_gnss1_lever_body_m"],
        maximum_gap_s=preparation["maximum_ahrs_gap_s"],
        ins_discretization=config.get("ins_discretization","HIGH_RATE_INTEGRAL_LEGACY"))
    local_rotations,_ = _rotation_at(qt, corrected_body_to_ned(raw["quaternion_wxyz"],alpha,preparation["imu_install_rpy_deg"]),
                                    np.asarray(times,float),preparation["maximum_ahrs_gap_s"])
    result["rotation_ned_from_body"] = local_rotations
    result["initialization"] = {"time_rel_s": float(initial[0]), "gnss_llh_deg_deg_m": initial[1:4].tolist(),
        "a1_body_yaw_ned_deg": float(initial[13]), "ahrs_heading_gauge_rad": float(alpha),
        "heading_alignment_count": 1, "gravity_mps2": float(gravity)}
    result["provenance"] = {"raw_body": {"path": raw_pin["path"], "sha256": raw["sha256"]},
        "raw_lock": spec["raw_lock"], "providers": provider_receipts,
        "execution_contract_sha256": _sha256(contract_path), "bundle_sha256": _sha256(bundle_path),
        "preparation": preparation, "parser_counts": {k: v for k, v in raw.items() if k.endswith("count") or k.endswith("messages")},
        "base_time_unix_s": float(spec["base_time"]), "data_mode": "real_raw_sensor_adaptation",
        "synthetic_data_used": False, "semisynthetic_data_used": False,
        "trace_used_online": False, "receiver_imu_as_body_imu": False,
        "final_v23_output_solver_input": False, "LegSA_output_solver_input": False,
        "per_case_tuning": False, "output_only_correction": False, "epoch_deleted_for_metric": False,
        "old_runtime_input_count": 0, "continuous_a1_heading_used": False,
        "go2_odometry_used": False, "second_imu_scale_or_install_applied": False,
        "gravity_source": "existing WGS84 gravity_model at sensor-only initial LLH",
        "coordinate_frame": "ECEF; fixed seed NED basis for AHRS/gravity; corrected FRD body bias",
        "coriolis_or_transport_added": False, "attitude_estimated": False,
        "linear_acceleration_contract": "Go2 calibrated specific force plus AHRS-rotated fixed normal gravity in body; not author XSens Ti10 output",
        "acceleration_interpolation": "linear interpolation of current-sample f=dvel/unrounded_dt at node times; maximum gap gate retained",
        "author_AHRS_statistical_equivalence_proven": False,
        "graph_R_GL": "current right-node ECEF position" if config.get("ins_discretization")=="RIGHT_ENDPOINT_ACCELERATION_EQ25" else "fixed seed basis"}
    return result
