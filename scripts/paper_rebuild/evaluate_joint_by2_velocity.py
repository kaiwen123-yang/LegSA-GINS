#!/usr/bin/env python3
"""Separate offline BY2 velocity evaluation; frozen p/yaw evaluation is unchanged.

Reference payloads are opened only by --child under strace. A sourced
POI-to-Go2-IMU lever, expressed in POI axes, is a required physical input.
No lever, clock offset, alignment, or velocity is fitted to reference data.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import io
import json
import math
from pathlib import Path
import subprocess
import sys

import numpy as np
from scipy.spatial.transform import Rotation

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from legsa_gins.paper_rebuild.clean5_sequence.io_audit import audited_open_records


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n")


def ecef_from_ned(latitude_rad, longitude_rad):
    sl, cl = math.sin(latitude_rad), math.cos(latitude_rad)
    so, co = math.sin(longitude_rad), math.cos(longitude_rad)
    return np.array([[-sl*co, -so, -cl*co],
                     [-sl*so, co, -cl*so], [cl, 0., -sl]])


def reference_imu_velocity(rotation_ecef_from_poi, velocity_poi, omega_poi,
                           lever_poi_to_imu_in_poi_m):
    """Rigid-body point transport, then rotate axes: v_I=R(v_P+omega x r_PI)."""
    return np.einsum("...ij,...j->...i", rotation_ecef_from_poi,
                     np.asarray(velocity_poi) +
                     np.cross(omega_poi, lever_poi_to_imu_in_poi_m))


def interpolated_velocity(times, velocities, query):
    """Linear interpolation only across adjacent finite published states."""
    times, velocities, query = map(np.asarray, (times, velocities, query))
    out = np.full((len(query), 3), np.nan)
    right = np.searchsorted(times, query, side="left")
    exact = (right < len(times))
    exact[exact] &= times[right[exact]] == query[exact]
    out[exact] = velocities[right[exact]]
    interior = (~exact) & (right > 0) & (right < len(times))
    j = right[interior]
    fraction = (query[interior] - times[j-1]) / (times[j] - times[j-1])
    out[interior] = velocities[j-1] * (1-fraction[:, None]) + velocities[j] * fraction[:, None]
    return out


def velocity_metrics(times, error, eligible_intervals):
    """Exact integral of the square of piecewise-linear vector errors."""
    dt = np.diff(times)[eligible_intervals]
    a, b = error[:-1][eligible_intervals], error[1:][eligible_intervals]
    if not len(dt):
        return dict(duration_s=0., rmse_ned_mps=None, horizontal_rmse_mps=None,
                    three_d_rmse_mps=None)
    second = np.sum(dt[:, None]*(a*a + a*b + b*b)/3., axis=0) / np.sum(dt)
    return dict(duration_s=float(np.sum(dt)), rmse_ned_mps=np.sqrt(second).tolist(),
                horizontal_rmse_mps=float(np.sqrt(second[:2].sum())),
                three_d_rmse_mps=float(np.sqrt(second.sum())))


def read_reference_odometry(path, expected_hash, base_time, lever):
    """One binary handle supplies both identity hash and CSV parse in child only."""
    with Path(path).open("rb") as stream:
        payload = stream.read()
    digest = hashlib.sha256(payload).hexdigest()
    if digest != expected_hash:
        raise ValueError("Reference odometry identity mismatch")
    times, rotations, velocity, omega = [], [], [], []
    for row in csv.DictReader(io.StringIO(payload.decode("utf-8-sig"))):
        if row["header.frame_id"] != "ECEF" or row["child_frame_id"] != "POI":
            raise ValueError("Expected ECEF pose with POI twist axes")
        epoch_ns = int(row["header.stamp.secs"])*10**9 + int(row["header.stamp.nsecs"])
        times.append((epoch_ns-int(base_time)*10**9)/10**9)
        rotations.append([float(row["pose.pose.orientation."+axis]) for axis in "xyzw"])
        velocity.append([float(row["twist.twist.linear."+axis]) for axis in "xyz"])
        omega.append([float(row["twist.twist.angular."+axis]) for axis in "xyz"])
    times = np.array(times)
    if np.any(np.diff(times) <= 0):
        raise ValueError("Odometry measurement epochs must be strictly increasing")
    rotations = Rotation.from_quat(rotations).as_matrix()
    values = reference_imu_velocity(rotations, velocity, omega, lever)
    return times, values, dict(sha256=digest, rows=len(times), binary_handle_opens=1,
                              measurement_time_field="header.stamp", arrival_time_used=False,
                              velocity_field="twist.twist.linear", angular_rate_field="twist.twist.angular",
                              quaternion_field="pose.pose.orientation.xyzw",
                              reference_pose_parent="ECEF", reference_twist_frame="POI")


def child(config_path):
    config = json.loads(Path(config_path).read_text())
    ref_t, ref_v, receipt = read_reference_odometry(
        config["reference_odometry"], config["reference_sha256"], config["base_time"],
        config["extrinsic"]["lever_poi_to_imu_in_poi_m"])
    start, end = config["window_s"]
    inputs = config["arms"]
    knot_arrays = [np.array([start, end]), ref_t[(ref_t > start) & (ref_t < end)]]
    for arm in inputs.values():
        t = np.asarray(arm["times"])
        knot_arrays.append(t[(t > start) & (t < end)])
    knots = np.unique(np.concatenate(knot_arrays))
    rotation = np.asarray(config["R_ecef_from_report_ned"])
    reference = interpolated_velocity(ref_t, ref_v, knots)
    # Source sample support is the measured 10 Hz grid. Missing reference packets
    # create unavailable intervals; they are not bridged by reference interpolation.
    midpoint = (knots[:-1]+knots[1:])/2.
    j = np.searchsorted(ref_t, midpoint, side="right")
    support = (j > 0) & (j < len(ref_t))
    good_j = np.clip(j, 1, len(ref_t)-1)
    support &= (ref_t[good_j]-ref_t[good_j-1]) <= config["reference_max_gap_s"]
    errors = {}
    own = {}
    common = support.copy()
    for name, arm in inputs.items():
        estimate = interpolated_velocity(arm["times"], np.array(arm["velocity_ecef"], float), knots)
        error = (estimate-reference) @ rotation
        valid = np.isfinite(error).all(axis=1)
        eligible = support & valid[:-1] & valid[1:]
        errors[name] = error
        own[name] = velocity_metrics(knots, error, eligible)
        common &= eligible
    intervals = [[float(knots[k]), float(knots[k+1])] for k in np.flatnonzero(common)]
    output = dict(
        status="COMPLETED_SEPARATE_VELOCITY_READOUT", window_s=config["window_s"],
        reference=receipt, extrinsic=config["extrinsic"],
        own_finite_support=own,
        common_finite_support={name: velocity_metrics(knots, error, common) for name,error in errors.items()},
        common_intervals_s=intervals,
        physical_point="GO2_PROPAGATION_IMU",
        point_transport="v_IMU_ecef=R_ecef_from_POI*(v_POI+omega_POI cross r_POI_to_IMU)",
        angular_rate_scope="reported POI twist angular velocity; no online gyro or reference differentiation",
        report_axes="fixed local NED of first joint run",
        time_scope="measurement-epoch accuracy; not zero-delay arrival-time accuracy",
        reference_claim="Fixposition fused reference with shared GNSS lineage; not independent truth",
        uncertainty_evaluated=False, frozen_position_yaw_evaluation_changed=False,
        interpolation="adjacent finite states only; no extrapolation or NO_INIT bridging",
        integration="exact integral of squared piecewise-linear vector error",
        original_v3_initialization="original continuous 66--340 s run, not restarted at short-window start",
        navigator_calls=0)
    save(Path(config_path).parent / "VELOCITY_COMPARISON.json", output)
    with (Path(config_path).parent / "velocity_error_series.csv").open("w", newline="") as stream:
        writer=csv.writer(stream)
        writer.writerow(["time_s", "arm", "error_n_mps", "error_e_mps", "error_d_mps",
                         "common_interval_to_next"])
        for name,error in errors.items():
            for k,t in enumerate(knots):
                writer.writerow([t,name,*error[k],bool(common[k]) if k < len(common) else False])


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--child", type=Path)
    p.add_argument("--run", action="append", default=[], help="NAME=completed joint run directory")
    p.add_argument("--v3-native", type=Path)
    p.add_argument("--reference-odometry", type=Path)
    p.add_argument("--reference-sha256")
    p.add_argument("--extrinsic", type=Path, help="source-explicit POI-to-Go2-IMU geometry JSON")
    p.add_argument("--output", type=Path)
    p.add_argument("--start", type=float)
    p.add_argument("--end", type=float)
    p.add_argument("--base-time", type=int, default=1772784000)
    p.add_argument("--reference-max-gap", type=float, default=.100001)
    a=p.parse_args()
    if a.child:
        child(a.child)
        return
    if not all((a.run,a.v3_native,a.reference_odometry,a.reference_sha256,a.extrinsic,a.output)):
        p.error("run, V3 NAV, reference path/hash, sourced extrinsic and output are required")
    geometry=json.loads(a.extrinsic.read_text())
    if (geometry.get("status") not in ("SOURCE_EXPLICIT", "USER_APPROXIMATE_INSTALLATION") or
        geometry.get("reference_point") != "FP_POI" or
        geometry.get("target_point") != "GO2_PROPAGATION_IMU" or
        not geometry.get("source_evidence")):
        raise ValueError("An explicit sourced or user-approximate POI-to-Go2-IMU extrinsic is required; no default lever")
    lever=np.asarray(geometry["lever_poi_to_imu_in_poi_m"],float)
    if lever.shape != (3,) or not np.isfinite(lever).all():
        raise ValueError("Extrinsic must contain three finite POI-axis coordinates")
    output=a.output.resolve()
    output.mkdir(parents=True,exist_ok=False)
    arms={}; sources={}; rotation=None
    for spec in a.run:
        name,path=spec.split("=",1); path=Path(path)
        status=json.loads((path/"run_status.json").read_text())
        metadata=json.loads((path/"sensor_metadata.json").read_text())
        if status["status"] != "COMPLETED" or metadata["sequence"] != "BY2":
            raise ValueError("Only completed BY2 navigation outputs may be evaluated")
        r=np.asarray(metadata["R_ecef_from_ned"],float)
        rotation=r if rotation is None else rotation
        rows=[json.loads(line) for line in (path/"navigation.jsonl").read_text().splitlines() if line.strip()]
        times=[row["time_s"] for row in rows]
        v=np.array([row["v"] for row in rows],float) @ r.T
        arms[name]=dict(times=times,velocity_ecef=[[float(x) if np.isfinite(x) else None for x in row] for row in v])
        sources[name]={f:sha(path/f) for f in ("run_status.json","sensor_metadata.json","navigation.jsonl")}
    v3=np.loadtxt(a.v3_native,comments="%",ndmin=2)
    lock=json.loads((ROOT/"docs/paper_rebuild/AR_V3_RESEARCH_20261006/V3_BASELINE_LOCK.json").read_text())
    by2=next(item for item in lock["sequences"] if item["sequence_id"]=="BY2")
    # Original V3 identity is locked independently of the new velocity evaluator.
    expected=by2["native_output"]["nav_sha256_from_ledger"]
    if sha(a.v3_native) != expected:
        raise ValueError("V3 native NAV differs from the frozen BY2 original")
    v3e=np.array([ecef_from_ned(*np.radians(row[2:4]))@row[5:8] for row in v3])
    arms["original_V3"]=dict(times=v3[:,1].tolist(),velocity_ecef=v3e.tolist())
    sources["original_V3"]=dict(native_nav_sha256=expected,run_id=by2["run_id"])
    start=a.start if a.start is not None else min(arms[next(iter(arms))]["times"])
    end=a.end if a.end is not None else max(arms[next(iter(arms))]["times"])
    config=dict(arms=arms,window_s=[start,end],extrinsic=geometry,
                reference_odometry=str(a.reference_odometry.resolve()),reference_sha256=a.reference_sha256,
                reference_max_gap_s=a.reference_max_gap,base_time=a.base_time,
                R_ecef_from_report_ned=rotation.tolist())
    config_path=output/"CHILD_INPUT.json"
    save(config_path,config)
    audit_path=output/"REFERENCE_OPENAT.strace"
    command=["strace","-f","-yy","-s","4096","-e","trace=openat,execve","-o",str(audit_path),
             sys.executable,str(Path(__file__).resolve()),"--child",str(config_path)]
    result=subprocess.run(command,cwd=ROOT,capture_output=True,text=True,check=False)
    (output/"child_stdout.log").write_text(result.stdout)
    (output/"child_stderr.log").write_text(result.stderr)
    records=audited_open_records(audit_path,ROOT)
    opened=[r for r in records if Path(r["path"])==a.reference_odometry.resolve()]
    receipt=dict(exit_code=result.returncode,reference_readonly_opens=len(opened),
                 reference_opened_once_readonly=len(opened)==1 and "O_RDONLY" in opened[0]["flags"],
                 parent_reference_payload_opens=0,reference_file_hash_in_parent=False,navigator_calls=0,
                 evaluator_sha256=sha(__file__),extrinsic_sha256=sha(a.extrinsic),sources=sources,
                 frozen_position_yaw_evaluation_changed=False)
    save(output/"EVALUATION_RECEIPT.json",receipt)
    if result.returncode or not receipt["reference_opened_once_readonly"]:
        raise RuntimeError("Offline velocity child failed; inspect child_stderr.log and receipt")
    print(json.dumps({"status":"COMPLETED_SEPARATE_VELOCITY_READOUT","output":str(output)}))


if __name__=="__main__":
    main()
