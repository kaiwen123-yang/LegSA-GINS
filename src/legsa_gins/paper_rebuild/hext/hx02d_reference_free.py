"""HX-02D B diagnostics on retained NAV, cache and pinned Go2 messages only.

No filter implementation is called. All new integration here is the explicitly
requested gyro/leg diagnostic. Raw reference access is rejected by an audit hook.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import itertools
import json
import math
import os
import struct
import sys
from pathlib import Path

import numpy as np
from scipy.spatial.transform import Rotation


def dump(path, value):
    def scalar(item):
        if isinstance(item, np.generic):
            return item.item()
        raise TypeError(f"Unsupported diagnostic JSON type: {type(item).__name__}")
    # Encode before opening the destination so a type failure leaves no partial JSON.
    encoded = json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False, default=scalar)
    with Path(path).open("x", encoding="utf-8") as handle:
        handle.write(encoded + "\n")


def wrap(x):
    return (np.asarray(x) + 180.0) % 360.0 - 180.0


def unwrap_deg(x):
    return np.degrees(np.unwrap(np.radians(x)))


def rms(x):
    a = np.asarray(x)
    return float(np.sqrt(np.mean(a * a))) if a.size else None


def ols(x, y):
    x, y = np.asarray(x), np.asarray(y)
    dx, dy = x - np.mean(x), y - np.mean(y)
    den = float(dx @ dx)
    if len(x) < 2 or den == 0:
        return {"slope": None, "intercept": None, "r2": None, "n": len(x)}
    slope = float(dx @ dy / den)
    intercept = float(np.mean(y) - slope * np.mean(x))
    resid = y - (slope * x + intercept)
    total = float(dy @ dy)
    return {"slope": slope, "intercept": intercept,
            "r2": None if total == 0 else float(1 - resid @ resid / total), "n": len(x)}


def correlation(x, y):
    if len(x) < 2 or np.std(x) == 0 or np.std(y) == 0:
        return None
    return float(np.corrcoef(x, y)[0, 1])


def rpy(R):
    return np.column_stack((np.arctan2(R[:, 2, 1], R[:, 2, 2]),
                            np.arcsin(np.clip(-R[:, 2, 0], -1, 1)),
                            np.arctan2(R[:, 1, 0], R[:, 0, 0])))


def integrate(t, v):
    """Trapezoids only on intervals with two observed endpoints; no gap fill."""
    dt = np.diff(t)
    valid = np.isfinite(v).all(axis=1)
    interval = valid[1:] & valid[:-1]
    increments = np.zeros((len(dt), v.shape[1]))
    increments[interval] = ((v[1:] + v[:-1]) * 0.5 * dt[:, None])[interval]
    return np.vstack((np.zeros(v.shape[1]), np.cumsum(increments, axis=0))), {
        "unobserved_interval_count": int(np.count_nonzero(~interval)),
        "unobserved_duration_s": float(dt[~interval].sum()),
        "policy": "No velocity imputation; zero displacement contribution on unobserved intervals, explicitly incomplete if any."}


def interp(t, a, grid):
    assert grid[0] >= t[0] and grid[-1] <= t[-1]
    a = np.asarray(a)
    return np.column_stack([np.interp(grid, t, a[:, j]) for j in range(a.shape[1])])


def load_raw(path, manifest):
    payload = Path(path).read_bytes()
    assert hashlib.sha256(payload).hexdigest() == manifest["raw_sha256"]
    prefix = payload[:manifest["prefix_interval"][1]]
    assert hashlib.sha256(prefix).hexdigest() == manifest["prefix_sha256"]
    selected = {"rpy": 3, "gyroscope": 3, "foot_force": 4,
                "foot_position_body": 12, "foot_speed_body": 12}
    output = {k: [] for k in selected}
    times, lines, record, active, start = [], [], None, None, None
    for line_no, line in enumerate(prefix.decode("utf-8").splitlines(), 1):
        stripped = line.strip()
        if stripped == "stamp:" and line.startswith("stamp:"):
            assert record is None
            record = {k: [] for k in selected}
            active, start = None, line_no
        elif record is None:
            continue
        elif stripped == "---":
            assert all(len(record[k]) == n for k, n in selected.items())
            times.append(record["sec"] * 1_000_000_000 + record["nanosec"])
            lines.append(start)
            for k in selected:
                output[k].append(record[k])
            record, active = None, None
        elif stripped.startswith("sec:") or stripped.startswith("nanosec:"):
            k, val = stripped.split(":", 1)
            record[k] = int(val)
            active = None
        elif stripped.endswith(":"):
            key = stripped[:-1]
            active = key if key in selected else None
        elif stripped.startswith("- ") and active:
            record[active].append(float(stripped[2:]))
        elif not stripped.startswith("- "):
            active = None
    assert record is None and len(times) == manifest["record_count"]
    return {**{k: np.asarray(v, dtype=float) for k, v in output.items()},
            "time_ns": np.asarray(times, dtype=np.int64), "source_start_line": np.asarray(lines)}


def load_cache(path, manifest):
    payload = Path(path).read_bytes()
    assert hashlib.sha256(payload).hexdigest() == manifest["cache_sha256"]
    header = struct.unpack("<16sIIIIQqq32s32s32s104x", payload[:256])
    assert header[1:5] == (1, 256, 192, manifest["record_count"])
    dtype = np.dtype([("t", "<i8"), ("v", "<f8", (22,)),
                      ("mask", "u1"), ("add", "u1"), ("remove", "u1"), ("reserved", "u1"), ("pad", "V4")])
    assert dtype.itemsize == 192
    return np.frombuffer(payload, dtype=dtype, offset=256)


def read_nav(path, expected):
    payload = Path(path).read_bytes()
    assert hashlib.sha256(payload).hexdigest() == expected
    rows = list(csv.DictReader(io.StringIO(payload.decode())))
    t = np.array([int(r["timestamp_ns"]) for r in rows], dtype=np.int64)
    data = np.array([[float(r[k]) for k in
                    [*(f"r{i}{j}" for i in range(3) for j in range(3)),
                     "vx", "vy", "vz", "px", "py", "pz", "bgx", "bgy", "bgz"]] for r in rows])
    assert np.isfinite(data).all() and (np.diff(t) > 0).all()
    return t, data[:, :9].reshape(-1, 3, 3), data[:, 9:12], data[:, 12:15], data[:, 15:18]


def attitude_stats(est, observed):
    hypotheses = {}
    for swapped, signs in itertools.product([False, True], itertools.product([1, -1], repeat=2)):
        model = observed[:, [1, 0] if swapped else [0, 1]] * signs
        diff = wrap(est[:, :2] - model)
        label = ("swap" if swapped else "identity") + f"_roll{signs[0]:+d}_pitch{signs[1]:+d}"
        hypotheses[label] = {"roll_mean_deg": float(np.mean(diff[:, 0])), "pitch_mean_deg": float(np.mean(diff[:, 1])),
                            "roll_rms_deg": rms(diff[:, 0]), "pitch_rms_deg": rms(diff[:, 1]),
                            "roll_max_abs_deg": float(np.max(np.abs(diff[:, 0]))),
                            "pitch_max_abs_deg": float(np.max(np.abs(diff[:, 1]))), "joint_rms_deg": rms(diff)}
    return {"hypotheses": hypotheses, "closest": min(hypotheses, key=lambda k: hypotheses[k]["joint_rms_deg"])}


def contact_stats(t, masks, forces, select):
    indices = np.flatnonzero(select)
    t, masks, forces = t[select], masks[select], forces[select]
    duration = float(t[-1] - t[0])
    dt = np.r_[np.diff(t), 0.0]
    contacts = (masks[:, None] & (1 << np.arange(4))) != 0
    bins = np.array([-np.inf, 0, 10, 20, 25, 30, 35, 40, 50, 75, 100, 150, np.inf])
    result = {"rows": len(t), "duration_s": duration, "histogram_edges": ["-inf", 0, 10, 20, 25, 30, 35, 40, 50, 75, 100, 150, "inf"], "legs": {},
              "simultaneous_contacts_sample_fraction": {str(k): float(np.mean(contacts.sum(axis=1) == k)) for k in range(5)},
              "simultaneous_contacts_time_fraction": {str(k): float(dt[contacts.sum(axis=1) == k].sum() / duration) for k in range(5)}}
    for j, (leg, on, off) in enumerate([("FL", 33.8, 25.2), ("FR", 34.2, 24.8), ("RL", 32.0, 24.0), ("RR", 30.6, 23.4)]):
        c, f = contacts[:, j], forces[:, j]
        boundaries = np.r_[0, np.flatnonzero(c[1:] != c[:-1]) + 1, len(c)]
        segments = []
        for left, right in zip(boundaries[:-1], boundaries[1:]):
            if c[left]:
                segments.append((float(t[right] - t[left]) if right < len(t) else float(t[-1] - t[left]), left == 0 or right == len(t)))
        complete = [v for v, censored in segments if not censored]
        result["legs"][leg] = {"on_threshold": on, "off_threshold": off,
            "duty_sample_fraction": float(c.mean()), "duty_time_fraction": float(dt[c].sum() / duration),
            "switch_count": int(np.count_nonzero(c[1:] != c[:-1])),
            "switches_per_s": float(np.count_nonzero(c[1:] != c[:-1]) / duration),
            "complete_stance_count": len(complete), "complete_stance_median_s": float(np.median(complete)) if complete else None,
            "censored_stance_count": sum(v[1] for v in segments),
            "force_histogram_counts": np.histogram(f, bins)[0].tolist(),
            "force_quantiles_p05_p25_p50_p75_p95": np.quantile(f, [0.05, .25, .5, .75, .95]).tolist(),
            "force_contact_quantiles": np.quantile(f[c], [.05, .5, .95]).tolist() if c.any() else None,
            "force_noncontact_quantiles": np.quantile(f[~c], [.05, .5, .95]).tolist() if (~c).any() else None,
            "below_off_fraction": float(np.mean(f < off)), "between_off_on_fraction": float(np.mean((f >= off) & (f <= on))),
            "above_on_fraction": float(np.mean(f > on)),
            "interpretation_limit": "Force-selected contact groups are not independent stance/swing labels."}
    return result


def pair_stats(t, left, right):
    diff = (left - left[0]) - (right - right[0])
    return {"rms_difference_deg": rms(diff), "drift_deg_per_min": ols(t / 60, diff)["slope"],
            "ols_r2": ols(t / 60, diff)["r2"], "end_difference_deg": float(diff[-1])}


def diagnose(spec):
    out = Path(spec["outdir"])
    out.mkdir(parents=True, exist_ok=False)
    manifest = json.loads(Path(spec["cache_manifest"]).read_text())
    raw = load_raw(manifest["source_identity"]["source"], manifest)
    cache = load_cache(spec["cache"], manifest)
    assert np.array_equal(raw["time_ns"], cache["t"])
    t = (cache["t"] - cache["t"][0]).astype(float) * 1e-9
    rel = cache["t"].astype(float) * 1e-9 - spec["base_time"]
    native_order = [1, 0, 3, 2]
    C = Rotation.from_euler("x", -1, degrees=True).as_matrix()
    gyro = raw["gyroscope"] @ C.T
    feet = raw["foot_position_body"].reshape(-1, 4, 3)[:, native_order]
    pdot = raw["foot_speed_body"].reshape(-1, 4, 3)[:, native_order]
    force = raw["foot_force"][:, native_order]
    assert np.max(np.abs(gyro - cache["v"][:, :3])) < 1e-14
    assert np.array_equal(feet.reshape(-1, 12), cache["v"][:, 10:22])
    assert np.array_equal(force, cache["v"][:, 6:10])
    G = Rotation.from_euler("xyz", raw["rpy"]).as_matrix()
    contacts = (cache["mask"][:, None] & (1 << np.arange(4))) != 0
    count = contacts.sum(axis=1)
    contact_change = np.count_nonzero(contacts[1:] != contacts[:-1], axis=1)
    # foot_speed_body is a declared diagnostic field, not an online input.
    per_foot = -(np.cross(gyro[:, None, :], feet) + pdot)
    fd_pdot = np.gradient(feet, t, axis=0, edge_order=2)
    per_foot_fd = -(np.cross(gyro[:, None, :], feet) + fd_pdot)
    vb = np.divide((per_foot * contacts[:, :, None]).sum(axis=1), count[:, None],
                   out=np.full((len(t), 3), np.nan), where=count[:, None] > 0)
    vb_fd = np.divide((per_foot_fd * contacts[:, :, None]).sum(axis=1), count[:, None],
                      out=np.full((len(t), 3), np.nan), where=count[:, None] > 0)
    leg_g, gap_g = integrate(t, np.einsum("nij,nj->ni", G, vb))
    leg_g_fd, gap_fd = integrate(t, np.einsum("nij,nj->ni", G, vb_fd))
    dt = np.diff(t)
    # Left rectangular rule matches native IMU sample hold; no bias subtraction.
    gyro_z = np.r_[0, np.cumsum(raw["gyroscope"][:-1, 2] * dt)] * 180 / np.pi
    gyro_body_z = np.r_[0, np.cumsum(gyro[:-1, 2] * dt)] * 180 / np.pi
    go2_yaw = unwrap_deg(np.degrees(raw["rpy"][:, 2]))
    go2_body_rpy = np.degrees(rpy(G @ C.T))
    windows = {"evaluation_window": (rel >= spec["window"][0]) & (rel <= spec["window"][1]),
               "full_native": np.ones(len(t), dtype=bool)}
    arrays = {"time_ns": cache["t"], "t_rel": rel, "go2_rotation": G, "go2_rpy_rad": raw["rpy"],
              "leg_go2_position": leg_g, "leg_go2_fd_position": leg_g_fd, "leg_body_velocity": vb,
              "leg_body_velocity_fd": vb_fd, "contact_mask": cache["mask"], "source_start_line": raw["source_start_line"],
              "raw_gyro_z_integral_deg": gyro_z, "corrected_gyro_z_integral_deg": gyro_body_z, "go2_yaw_unwrapped_deg": go2_yaw}
    result = {"sequence_id": spec["sequence_id"], "sources": spec, "rows": len(t),
              "cache_raw_identity_checks": "PASS exact time/force/foot positions; corrected gyro max abs <1e-14",
              "B3": {name: contact_stats(t, cache["mask"], force, mask) for name, mask in windows.items()},
              "leg_integration_gaps": gap_g, "leg_fd_integration_gaps": gap_fd, "branches": {},
              "gyro_bias_instability_rad_per_s": 4.550529e-5,
              "gyro_bias_instability_deg_per_min": math.degrees(4.550529e-5) * 60,
              "bias_profile_scope": "Arithmetic mean across axes; individual z-axis Allan value unavailable.",
              "p_dot_primary": "Pinned Go2 foot_speed_body, diagnostic-only; nonuniform finite difference of foot_position_body also reported, never selected using reference."}
    for label, entry in spec["branches"].items():
        times, R, velocity, position, bias = read_nav(entry["nav"], entry["nav_sha256"])
        assert np.array_equal(times, cache["t"])
        angles = np.degrees(rpy(R))
        yaw = unwrap_deg(angles[:, 2])
        state_vb = np.einsum("nji,nj->ni", R, velocity)
        leg_h, gap_h = integrate(t, np.einsum("nij,nj->ni", R, vb))
        for key, value in {"rotation": R, "position": position, "velocity": velocity, "gyro_bias": bias,
                           "rpy_deg": angles, "yaw_unwrapped_deg": yaw, "leg_hartley_position": leg_h}.items():
            arrays[f"{label}_{key}"] = value
        branch = {}
        for window, mask in windows.items():
            ids = np.flatnonzero(mask)
            tt = t[mask] - t[mask][0]
            y, gz, gy = yaw[mask], gyro_z[mask], go2_yaw[mask]
            differences = y - y[0] - (gz - gz[0])
            rates = np.diff(differences) / np.diff(tt)
            changes = np.count_nonzero(contacts[ids[1:]] != contacts[ids[:-1]], axis=1)
            signed_bins, absolute_bins, event_bins = [], [], []
            for sec in range(int(tt[-1])):
                selected = (tt[1:] >= sec) & (tt[1:] < sec + 1)
                if selected.any():
                    signed_bins.append(float(np.diff(differences)[selected].sum()))
                    absolute_bins.append(float(np.abs(np.diff(differences)[selected]).sum()))
                    event_bins.append(float(changes[selected].sum()))
            finite = np.isfinite(vb[mask]).all(axis=1)
            a, b = vb[mask][finite], state_vb[mask][finite]
            sa, sb = np.linalg.norm(a, axis=1), np.linalg.norm(b, axis=1)
            direction = (sa > .05) & (sb > .05)
            angle = np.degrees(np.arccos(np.clip(np.sum(a[direction] * b[direction], axis=1) / (sa[direction] * sb[direction]), -1, 1)))
            # Preserve a common 10 Hz path sampling for comparison with HX-02 reference length.
            if window == "evaluation_window":
                grid = spec["window"][0] + np.arange(int(round((spec["window"][1] - spec["window"][0]) * 10)) + 1) / 10
            else:
                grid = np.arange(math.ceil(rel[0] * 10), math.floor(rel[-1] * 10) + 1) / 10
            paths = {name: float(np.linalg.norm(np.diff(interp(rel, p, grid)[:, :2], axis=0), axis=1).sum())
                     for name, p in [("leg_hartley", leg_h), ("leg_go2", leg_g), ("leg_go2_fd", leg_g_fd), ("hartley", position)]}
            branch[window] = {"rows": len(ids), "duration_s": float(tt[-1]),
                "B1_raw_rpy": attitude_stats(angles[mask], np.degrees(raw["rpy"][mask])),
                "B1_installation_adjusted_rpy": attitude_stats(angles[mask], go2_body_rpy[mask]),
                "B2": {"hartley_minus_raw_gyro_z": pair_stats(tt, y, gz),
                       "hartley_minus_go2": pair_stats(tt, y, gy), "go2_minus_raw_gyro_z": pair_stats(tt, gy, gz),
                       "hartley_minus_corrected_gyro_z": pair_stats(tt, y, gyro_body_z[mask]),
                       "contact_switch_correlation": {"epoch_signed_rate_pearson": correlation(changes > 0, rates),
                           "epoch_absolute_rate_pearson": correlation(changes > 0, np.abs(rates)),
                           "one_second_signed_departure_vs_switch_count": correlation(event_bins, signed_bins),
                           "one_second_total_absolute_departure_vs_switch_count": correlation(event_bins, absolute_bins),
                           "switch_intervals": int(np.count_nonzero(changes)),
                           "mean_abs_rate_at_switch_deg_per_s": float(np.mean(np.abs(rates[changes > 0]))) if (changes > 0).any() else None,
                           "mean_abs_rate_without_switch_deg_per_s": float(np.mean(np.abs(rates[changes == 0]))) if (changes == 0).any() else None},
                       "gyro_bias_z_state_rad_per_s_quantiles": np.quantile(bias[mask, 2], [.05, .5, .95]).tolist()},
                "B4": {"observed_velocity_rows": int(finite.sum()), "unobserved_velocity_rows": int((~finite).sum()),
                       "speed_magnitude_difference_rms_mps": rms(sa - sb),
                       "velocity_vector_difference_rms_mps": rms(np.linalg.norm(a - b, axis=1)),
                       "direction_median_deg": float(np.median(angle)) if len(angle) else None,
                       "direction_rows": len(angle), "direction_speed_threshold_mps": .05,
                       "path_lengths_10hz_m": paths,
                       "path_length_ratios_to_recorded_reference": {k: v / spec["reference_path_length_m"] for k, v in paths.items()} if window == "evaluation_window" else None,
                       "recorded_reference_path_length_m": spec["reference_path_length_m"] if window == "evaluation_window" else None,
                       "foot_speed_vs_finite_difference_contact_rms_mps": rms(np.linalg.norm((pdot - fd_pdot)[mask][contacts[mask]], axis=1))}}
        result["branches"][label] = branch
        # Full native-rate arrays retain epoch comparisons without a lossy table export.
        arrays[f"{label}_roll_pitch_difference_deg"] = wrap(angles[:, :2] - np.degrees(raw["rpy"][:, :2]))
    np.savez_compressed(out / "B_ARRAYS.npz", **arrays)
    result["array_sha256"] = hashlib.sha256((out / "B_ARRAYS.npz").read_bytes()).hexdigest()
    dump(out / "B_TABLES.json", result)
    print(json.dumps({"sequence": spec["sequence_id"], "rows": len(t), "branches": list(result["branches"])}))


def guard(event, args):
    if event == "open" and isinstance(args[0], (str, bytes, os.PathLike)):
        p = Path(os.fsdecode(args[0]))
        if p.name.startswith("trace_vrtk") or p.suffix.lower() in {".bag", ".fpl"}:
            raise RuntimeError("HX02D reference-free process attempted forbidden reference/container access")
    if event in {"subprocess.Popen", "os.system", "os.exec", "os.posix_spawn"}:
        raise RuntimeError("HX02D B process cannot execute other programs")


def main():
    sys.addaudithook(guard)
    parser = argparse.ArgumentParser()
    parser.add_argument("--spec", type=Path, required=True)
    args = parser.parse_args()
    diagnose(json.loads(args.spec.read_text()))


if __name__ == "__main__":
    main()
