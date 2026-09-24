"""HX-02 relative-pose evaluator child for Hartley contact-aided InEKF outputs.

Run only as a registered evaluator subprocess. The child opens the reference
trace exactly once (read-only, SHA-256 checked on the same bytes) and writes only
a metrics JSON and a per-epoch error series CSV.

Evaluation (H7_EVALUATION_CONTRACT.yaml time/interpolation rules and the
forbidden-operation list at :99-117):
  * target grid t_j = w0 + 0.1 j inside the closed window, interpolation only
    between bracketing samples (no extrapolation);
  * Hartley point = Go2 body-IMU origin, moved to the antenna midpoint with the
    frozen FRD lever [0.03, 0.03 - b_med/2, -0.30] m (clean5_parity transform);
    Hartley body frame is Go2 FLU, world frame is gravity-up;
  * one 4-DOF alignment (yaw about gravity + 3-D translation) solved by least
    squares on the first 10 s of the window, derived from the primary branch and
    applied unchanged to every branch, never re-fitted over the window.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np

from ..horizontal_literature.hartley_h7 import interpolate_so3
from ..horizontal_literature.hartley_h7c import (
    apply_fixed_gauge_to_pose,
    fixed_primary_yaw_translation_gauge,
    relative_pose_metrics,
    rotation_z,
)

SCHEMA = "hx02.relative_pose_evaluation.v1"
GRID_STEP_S = 0.1
ALIGNMENT_SECONDS = 10.0
RPE_HORIZONS_S = (1.0, 5.0, 10.0)
WGS84_A = 6378137.0
WGS84_E2 = 6.6943799901413165e-3
FRD_TO_FLU = np.diag([1.0, -1.0, -1.0])
REQUIRED_TRACE_COLUMNS = ("time", "lat", "lon", "height", "roll", "pitch", "yaw")


class RelativePoseError(RuntimeError):
    """Fail-closed relative-pose evaluation violation."""


def wrap180(values):
    return (np.asarray(values, dtype=float) + 180.0) % 360.0 - 180.0


def target_grid(window: Sequence[float]) -> np.ndarray:
    start, end = map(float, window)
    count = int(math.floor((end - start) / GRID_STEP_S + 1e-9)) + 1
    grid = start + GRID_STEP_S * np.arange(count)
    return grid[grid <= end + 1e-9]


def lever_flu(baseline_median_m: float) -> np.ndarray:
    """Frozen FRD antenna-midpoint lever expressed in the Hartley/Go2 FLU body frame."""
    return FRD_TO_FLU @ np.asarray([0.03, 0.03 - 0.5 * float(baseline_median_m), -0.30])


def geodetic_to_ecef(lat_deg, lon_deg, height_m) -> np.ndarray:
    lat, lon = np.radians(lat_deg), np.radians(lon_deg)
    normal = WGS84_A / np.sqrt(1.0 - WGS84_E2 * np.sin(lat) ** 2)
    return np.column_stack(((normal + height_m) * np.cos(lat) * np.cos(lon),
                            (normal + height_m) * np.cos(lat) * np.sin(lon),
                            (normal * (1.0 - WGS84_E2) + height_m) * np.sin(lat)))


def ecef_to_enu(ecef: np.ndarray, origin_lat_deg: float, origin_lon_deg: float, origin_ecef: np.ndarray) -> np.ndarray:
    lat, lon = math.radians(origin_lat_deg), math.radians(origin_lon_deg)
    rotation = np.array([[-math.sin(lon), math.cos(lon), 0.0],
                         [-math.sin(lat) * math.cos(lon), -math.sin(lat) * math.sin(lon), math.cos(lat)],
                         [math.cos(lat) * math.cos(lon), math.cos(lat) * math.sin(lon), math.sin(lat)]])
    return (np.asarray(ecef) - np.asarray(origin_ecef)) @ rotation.T


def read_reference(trace_payload: bytes, base_time: float) -> dict[str, np.ndarray]:
    reader = csv.DictReader(io.StringIO(trace_payload.decode("utf-8-sig")))
    missing = [name for name in REQUIRED_TRACE_COLUMNS if name not in (reader.fieldnames or [])]
    if missing:
        raise RelativePoseError(f"reference lacks columns {missing}")
    rows = list(reader)
    values = {name: np.asarray([float(row[name]) for row in rows], dtype=float) for name in REQUIRED_TRACE_COLUMNS}
    if values["time"].size < 2 or np.any(np.diff(values["time"]) <= 0.0):
        raise RelativePoseError("reference time stream is invalid")
    if not all(np.isfinite(array).all() for array in values.values()):
        raise RelativePoseError("reference stream contains nonfinite values")
    values["t_rel"] = values["time"] - float(base_time)
    values["yaw_enu_unwrapped_deg"] = np.degrees(np.unwrap(np.radians(values["yaw"])))
    return values


def interpolate_reference(reference: Mapping[str, np.ndarray], grid: np.ndarray) -> dict[str, np.ndarray]:
    """Linear LLH and unwrapped ENU yaw inside support; NaN outside (no extrapolation)."""
    t = reference["t_rel"]
    inside = (grid >= t[0]) & (grid <= t[-1])
    result = {"supported": inside}
    for name in ("lat", "lon", "height", "yaw_enu_unwrapped_deg"):
        column = np.full(grid.shape, math.nan)
        column[inside] = np.interp(grid[inside], t, reference[name])
        result[name] = column
    return result


def read_hartley_nav(payload: bytes) -> dict[str, np.ndarray]:
    reader = csv.DictReader(io.StringIO(payload.decode("utf-8")))
    rows = list(reader)
    if not rows:
        raise RelativePoseError("Hartley NAV is empty")
    time_ns = np.asarray([int(row["timestamp_ns"]) for row in rows], dtype=np.int64)
    rotation = np.asarray([[float(row[f"r{i}{j}"]) for i in range(3) for j in range(3)] for row in rows]).reshape(-1, 3, 3)
    position = np.asarray([[float(row["px"]), float(row["py"]), float(row["pz"])] for row in rows])
    if np.any(np.diff(time_ns) <= 0) or not np.isfinite(rotation).all() or not np.isfinite(position).all():
        raise RelativePoseError("Hartley NAV is non-chronological or nonfinite")
    return {"time_unix_s": time_ns.astype(np.float64) * 1.0e-9, "time_ns": time_ns,
            "rotation": rotation, "position": position}


def _orthonormal(rotation: np.ndarray) -> np.ndarray:
    u, _s, vt = np.linalg.svd(rotation)
    value = u @ vt
    if np.linalg.det(value) < 0.0:
        u[:, -1] *= -1.0
        value = u @ vt
    return value


def interpolate_estimate(nav: Mapping[str, np.ndarray], grid_unix: np.ndarray) -> dict[str, np.ndarray]:
    """Linear position and SO(3) geodesic orientation between bracketing NAV rows."""
    times = nav["time_unix_s"]
    supported = (grid_unix >= times[0]) & (grid_unix <= times[-1])
    position = np.full((grid_unix.size, 3), math.nan)
    rotation = np.full((grid_unix.size, 3, 3), math.nan)
    for index in np.flatnonzero(supported):
        t = grid_unix[index]
        right = int(np.searchsorted(times, t, side="left"))
        if right < times.size and times[right] == t:
            position[index] = nav["position"][right]
            rotation[index] = _orthonormal(nav["rotation"][right])
            continue
        left = right - 1
        fraction = (t - times[left]) / (times[right] - times[left])
        position[index] = (1.0 - fraction) * nav["position"][left] + fraction * nav["position"][right]
        rotation[index] = interpolate_so3(_orthonormal(nav["rotation"][left]), _orthonormal(nav["rotation"][right]),
                                          float(fraction))
    return {"supported": supported, "position": position, "rotation": rotation}


def yaw_of(rotation: np.ndarray) -> float:
    return math.atan2(float(rotation[1, 0]), float(rotation[0, 0]))


def ls_yaw_translation_gauge(est_rotation, est_point, ref_yaw_enu_rad, ref_point):
    """Least-squares 4-DOF gauge on the alignment epochs.

    Per epoch the fixed-primary gauge gives a yaw offset; the least-squares yaw
    on the circle is their circular mean, and the least-squares translation for
    that yaw is the mean of p_ref - Rz(psi) p_est. No roll, pitch or scale.
    """
    offsets = []
    for rotation, point, yaw, reference in zip(est_rotation, est_point, ref_yaw_enu_rad, ref_point):
        yaw_gauge, _translation = fixed_primary_yaw_translation_gauge(rotation, point, rotation_z(float(yaw)), reference)
        offsets.append(math.atan2(float(yaw_gauge[1, 0]), float(yaw_gauge[0, 0])))
    offsets = np.asarray(offsets, dtype=float)
    psi = math.atan2(float(np.mean(np.sin(offsets))), float(np.mean(np.cos(offsets))))
    rz = rotation_z(psi)
    translation = np.mean(np.asarray(ref_point) - (rz @ np.asarray(est_point).T).T, axis=0)
    return psi, rz, translation, offsets


def _ols_slope(x: np.ndarray, y: np.ndarray) -> float | None:
    x, y = np.asarray(x, dtype=float), np.asarray(y, dtype=float)
    if x.size < 2 or float(np.var(x)) <= 0.0:
        return None
    return float(np.polyfit(x, y, 1)[0])


def branch_metrics(grid: np.ndarray, estimate: Mapping[str, np.ndarray], reference_enu: np.ndarray,
                   reference_yaw_enu_deg: np.ndarray, valid: np.ndarray, lever: np.ndarray,
                   psi: float, translation: np.ndarray) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    rz = rotation_z(psi)
    rows = []
    errors_h, errors_u, errors_yaw, path, times = [], [], [], [], []
    cumulative = 0.0
    previous_reference = None
    aligned_poses, reference_poses, pose_times = [], [], []
    for index in np.flatnonzero(valid):
        rotation = estimate["rotation"][index]
        point = estimate["position"][index] + rotation @ lever
        pose = np.eye(4)
        pose[:3, :3], pose[:3, 3] = rotation, point
        aligned = apply_fixed_gauge_to_pose(rz, translation, pose)
        error = aligned[:3, 3] - reference_enu[index]
        yaw_est_enu = math.degrees(yaw_of(aligned[:3, :3]))
        # NED body yaw = 90 - ENU yaw for both; error = estimate - reference (NED)
        yaw_error = float(wrap180((90.0 - yaw_est_enu) - (90.0 - reference_yaw_enu_deg[index])))
        if previous_reference is not None:
            cumulative += float(np.linalg.norm(reference_enu[index][:2] - previous_reference[:2]))
        previous_reference = reference_enu[index]
        errors_h.append(float(np.linalg.norm(error[:2])))
        errors_u.append(float(error[2]))
        errors_yaw.append(yaw_error)
        path.append(cumulative)
        times.append(float(grid[index]))
        aligned_poses.append(np.block([[rotation_z(math.radians(yaw_est_enu)), aligned[:3, 3:4]], [np.zeros((1, 3)), np.ones((1, 1))]]))
        reference_poses.append(np.block([[rotation_z(math.radians(float(reference_yaw_enu_deg[index]))),
                                          np.asarray(reference_enu[index]).reshape(3, 1)],
                                         [np.zeros((1, 3)), np.ones((1, 1))]]))
        pose_times.append(float(grid[index]))
        rows.append({"t_rel_s": repr(float(grid[index])), "err_e_m": repr(float(error[0])),
                     "err_n_m": repr(float(error[1])), "err_u_m": repr(float(error[2])),
                     "horizontal_err_m": repr(errors_h[-1]), "yaw_err_deg": repr(yaw_error),
                     "reference_path_m": repr(cumulative)})
    errors_h, errors_u = np.asarray(errors_h), np.asarray(errors_u)
    errors_yaw = np.asarray(errors_yaw)
    unwrapped_yaw = np.degrees(np.unwrap(np.radians(errors_yaw))) if errors_yaw.size else errors_yaw
    drift_path = _ols_slope(np.asarray(path), errors_h)
    drift_yaw = _ols_slope(np.asarray(times) / 60.0, unwrapped_yaw)
    rpe = {}
    step = int(round(GRID_STEP_S * 1000))
    time_keys = {int(round(t * 1000)): k for k, t in enumerate(pose_times)}
    for horizon in RPE_HORIZONS_S:
        translation_errors, yaw_errors = [], []
        for start_index, t0 in enumerate(pose_times):
            end = time_keys.get(int(round(t0 * 1000)) + int(round(horizon * 1000)))
            if end is None:
                continue
            value = relative_pose_metrics(aligned_poses[start_index], aligned_poses[end],
                                          reference_poses[start_index], reference_poses[end])
            translation_errors.append(value["translation_error_m"])
            yaw_errors.append(value["rotation_geodesic_error_deg"])
        rpe[f"{horizon:g}s"] = {
            "pair_count": len(translation_errors),
            "translation_rmse_m": float(np.sqrt(np.mean(np.square(translation_errors)))) if translation_errors else None,
            "yaw_rmse_deg": float(np.sqrt(np.mean(np.square(yaw_errors)))) if yaw_errors else None,
            "grid_step_ms": step,
        }
    metrics = {
        "scored_epochs": int(errors_h.size),
        "horizontal_rmse_m": float(np.sqrt(np.mean(errors_h ** 2))) if errors_h.size else None,
        "up_rmse_m": float(np.sqrt(np.mean(errors_u ** 2))) if errors_u.size else None,
        "yaw_rmse_deg": float(np.sqrt(np.mean(errors_yaw ** 2))) if errors_yaw.size else None,
        "horizontal_max_m": float(np.max(errors_h)) if errors_h.size else None,
        "reference_path_length_m": float(path[-1]) if path else None,
        "position_drift_m_per_100m": None if drift_path is None else 100.0 * drift_path,
        "heading_drift_deg_per_min": drift_yaw,
        "relative_pose_error_yaw_translation": rpe,
        "drift_definitions": {
            "position": "OLS slope (with intercept) of horizontal error norm versus cumulative reference horizontal path, x100",
            "heading": "OLS slope (with intercept) of time-unwrapped wrap-safe NED yaw error versus time in minutes",
        },
    }
    return metrics, rows


def evaluate_payloads(spec: Mapping[str, Any], trace_payload: bytes, nav_payloads: Mapping[str, bytes]) -> dict[str, Any]:
    base_time = float(spec["base_time"])
    window = tuple(map(float, spec["window"]))
    reference = read_reference(trace_payload, base_time)
    grid = target_grid(window)
    interp = interpolate_reference(reference, grid)
    origin_index = int(np.flatnonzero(interp["supported"])[0])
    origin_ecef = geodetic_to_ecef(interp["lat"][origin_index:origin_index + 1], interp["lon"][origin_index:origin_index + 1],
                                   interp["height"][origin_index:origin_index + 1])[0]
    ref_ecef = geodetic_to_ecef(interp["lat"], interp["lon"], interp["height"])
    ref_enu = ecef_to_enu(ref_ecef, float(interp["lat"][origin_index]), float(interp["lon"][origin_index]), origin_ecef)
    lever = lever_flu(float(spec["baseline_median_m"]))
    primary = str(spec["alignment_branch"])
    branches = {label: read_hartley_nav(payload) for label, payload in nav_payloads.items()}
    grid_unix = grid + base_time
    estimates = {label: interpolate_estimate(nav, grid_unix) for label, nav in branches.items()}
    align_mask = (grid <= window[0] + ALIGNMENT_SECONDS + 1e-9) & interp["supported"] & estimates[primary]["supported"]
    if int(np.count_nonzero(align_mask)) < 2:
        raise RelativePoseError("alignment window lacks bracketed estimate/reference epochs")
    est = estimates[primary]
    points = np.asarray([est["position"][i] + est["rotation"][i] @ lever for i in np.flatnonzero(align_mask)])
    psi, rz, translation, offsets = ls_yaw_translation_gauge(
        est["rotation"][align_mask], points, np.radians(interp["yaw_enu_unwrapped_deg"][align_mask]), ref_enu[align_mask])
    result: dict[str, Any] = {
        "schema": SCHEMA, "sequence_id": spec["sequence_id"], "window_seconds": list(window),
        "base_time": base_time, "grid_step_s": GRID_STEP_S, "grid_epochs": int(grid.size),
        "reference_supported_grid_epochs": int(np.count_nonzero(interp["supported"])),
        "alignment": {
            "branch": primary, "window_seconds": [window[0], window[0] + ALIGNMENT_SECONDS],
            "epochs": int(np.count_nonzero(align_mask)), "yaw_offset_deg": math.degrees(psi),
            "translation_enu_m": translation.tolist(),
            "per_epoch_yaw_offset_circular_std_deg": float(np.degrees(np.sqrt(-2.0 * np.log(max(
                math.hypot(float(np.mean(np.sin(offsets))), float(np.mean(np.cos(offsets)))), 1e-300))))),
            "rule": "one least-squares yaw-about-gravity + 3D translation on the first 10 s; primary-derived; applied unchanged to all branches",
            "not_estimated": ["roll", "pitch", "scale", "time_offset"],
        },
        "lever_flu_m": lever.tolist(), "reference_origin": "first supported grid epoch (local ENU)",
        "branches": {}, "series": {},
    }
    for label, estimate in estimates.items():
        valid = interp["supported"] & estimate["supported"]
        metrics, rows = branch_metrics(grid, estimate, ref_enu, interp["yaw_enu_unwrapped_deg"], valid,
                                       lever, psi, translation)
        nav = branches[label]
        metrics.update(nav_rows=int(nav["time_ns"].size),
                       nav_first_rel_s=float(nav["time_unix_s"][0] - base_time),
                       nav_last_rel_s=float(nav["time_unix_s"][-1] - base_time),
                       unsupported_grid_epochs=int(grid.size - np.count_nonzero(valid)))
        result["branches"][label] = metrics
        result["series"][label] = rows
    return result


def evaluate(spec: Mapping[str, Any]) -> dict[str, Any]:
    outdir = Path(spec["outdir"])
    outdir.mkdir(parents=True, exist_ok=False)
    nav_payloads = {}
    for label, entry in spec["branches"].items():
        payload = Path(entry["nav"]).read_bytes()
        if hashlib.sha256(payload).hexdigest() != entry["nav_sha256"]:
            raise RelativePoseError(f"{label} NAV SHA-256 mismatch")
        nav_payloads[label] = payload
    with open(spec["trace"], "rb") as handle:  # the single reference open of this child
        trace_payload = handle.read()
    observed = hashlib.sha256(trace_payload).hexdigest()
    if observed != spec["trace_sha256"]:
        raise RelativePoseError("reference SHA-256 mismatch")
    result = evaluate_payloads(spec, trace_payload, nav_payloads)
    del trace_payload
    series = result.pop("series")
    result.update(trace_sha256_observed=observed, trace_open_count_in_child=1,
                  nav_sha256={label: entry["nav_sha256"] for label, entry in spec["branches"].items()})
    for label, rows in series.items():
        with (outdir / f"RELATIVE_POSE_ERROR_SERIES_{label}.csv").open("x", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()) if rows else ["t_rel_s"], lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)
    with (outdir / "RELATIVE_POSE_METRICS.json").open("x", encoding="utf-8") as handle:
        handle.write(json.dumps(result, indent=2, sort_keys=True) + "\n")
    return result


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spec", type=Path, required=True)
    args = parser.parse_args(argv)
    evaluate(json.loads(args.spec.read_text(encoding="utf-8")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
