"""All HX-02D C calculations; invoked only by the registered HX-02 launcher.

One invocation per sequence, both branches in memory, exactly one reference
open with a hash check on those same bytes. No estimator execution or changes.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import os
import sys
from pathlib import Path

import numpy as np

from . import hx02_relative_pose_evaluation as frozen
from .hx02d_reference_free import dump, interp, ols, rms, unwrap_deg, wrap


def align(points, yaw_deg, reference, ref_yaw, alignment_mask):
    offsets = np.radians(ref_yaw[alignment_mask] - yaw_deg[alignment_mask])
    psi = math.atan2(float(np.mean(np.sin(offsets))), float(np.mean(np.cos(offsets))))
    Q = frozen.rotation_z(psi)
    trans = np.mean(reference[alignment_mask] - points[alignment_mask] @ Q.T, axis=0)
    return points @ Q.T + trans, yaw_deg + math.degrees(psi), {
        "yaw_offset_deg": math.degrees(psi), "translation_enu_m": trans.tolist(),
        "epochs": int(alignment_mask.sum())}


def score(points, yaw, reference, ref_yaw, times, cumulative):
    err = points - reference
    h = np.linalg.norm(err[:, :2], axis=1)
    ye = wrap(ref_yaw - yaw)  # estimated NED yaw minus reference NED yaw
    return {"horizontal_rmse_m": rms(h), "yaw_rmse_deg": rms(ye),
            "position_drift_m_per_100m": ols(cumulative, h)["slope"] * 100,
            "endpoint_horizontal_error_m": float(h[-1]),
            "endpoint_error_m_per_100m": float(h[-1] / cumulative[-1] * 100),
            "heading_drift_deg_per_min": ols(times / 60, unwrap_deg(ye))["slope"]}, err, ye


def write_series(path, header, rows):
    with path.open("x", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(header)
        writer.writerows(rows)


def evaluate(spec):
    out = Path(spec["outdir"])
    out.mkdir(parents=True, exist_ok=False)
    payload = Path(spec["b_arrays"]).read_bytes()
    assert hashlib.sha256(payload).hexdigest() == spec["b_arrays_sha256"]
    with np.load(io.BytesIO(payload), allow_pickle=False) as loaded:
        arrays = {name: loaded[name] for name in loaded.files}
    # This is the only raw reference open in the entire diagnostic process.
    with Path(spec["trace"]).open("rb") as handle:
        trace_payload = handle.read()
    trace_sha = hashlib.sha256(trace_payload).hexdigest()
    assert trace_sha == spec["trace_sha256"]
    ref = frozen.read_reference(trace_payload, spec["base_time"])
    grid = frozen.target_grid(spec["window"])
    ri = frozen.interpolate_reference(ref, grid)
    assert ri["supported"].all()
    ecef = frozen.geodetic_to_ecef(ri["lat"], ri["lon"], ri["height"])
    reference = frozen.ecef_to_enu(ecef, ri["lat"][0], ri["lon"][0], ecef[0])
    ref_yaw = ri["yaw_enu_unwrapped_deg"]
    reference_path = np.r_[0, np.cumsum(np.linalg.norm(np.diff(reference[:, :2], axis=0), axis=1))]
    assert abs(reference_path[-1] - spec["reference_path_length_m"]) < 1e-8
    elapsed = grid - grid[0]
    alignment_mask = elapsed <= 10 + 1e-9
    time_unix = arrays["time_ns"].astype(float) * 1e-9
    lever = frozen.lever_flu(spec["baseline_median_m"])
    results = {"sequence_id": spec["sequence_id"], "trace_sha256_observed": trace_sha,
               "trace_open_count_in_child": 1, "window": spec["window"],
               "time_zero": "Start of HX-02 evaluation window, not first NAV record.",
               "reference_path_length_m": float(reference_path[-1]),
               "branches": {}, "C4": {}}
    for label, original in spec["original_metrics"].items():
        nav = {"time_unix_s": time_unix, "rotation": arrays[f"{label}_rotation"],
               "position": arrays[f"{label}_position"]}
        est = frozen.interpolate_estimate(nav, grid + spec["base_time"])
        assert est["supported"].all()
        point = est["position"] + np.einsum("nij,j->ni", est["rotation"], lever)
        old_align = original["alignment"]
        psi = math.radians(old_align["yaw_offset_deg"])
        Q = frozen.rotation_z(psi)
        aligned_point = point @ Q.T + old_align["translation_enu_m"]
        aligned_R = Q @ est["rotation"]
        yaw = np.degrees(np.arctan2(aligned_R[:, 1, 0], aligned_R[:, 0, 0]))
        metrics, err, yaw_error = score(aligned_point, yaw, reference, ref_yaw, elapsed, reference_path)
        reproduction = {k: {"new": metrics[k], "old": original[k], "abs_difference": abs(metrics[k] - original[k])}
                        for k in ["horizontal_rmse_m", "yaw_rmse_deg", "position_drift_m_per_100m", "heading_drift_deg_per_min"]}
        assert all(v["abs_difference"] < 1e-7 for v in reproduction.values())
        unwrapped_error = unwrap_deg(yaw_error)
        ref_delta_ned = -(ref_yaw - ref_yaw[0])
        times_requested = [10, 30, 60, 120, 240]
        samples = []
        for seconds in times_requested:
            i = int(round(seconds * 10))
            assert abs(elapsed[i] - seconds) < 1e-8
            samples.append({"elapsed_s": seconds, "t_rel_s": float(grid[i]),
                            "err_n_m": float(err[i, 1]), "err_e_m": float(err[i, 0]), "err_u_m": float(err[i, 2]),
                            "yaw_error_ned_wrapped_deg": float(yaw_error[i]),
                            "yaw_error_ned_unwrapped_deg": float(unwrapped_error[i])})
        series = out / f"{label}_C1_1S.csv"
        write_series(series, ["elapsed_s", "t_rel_s", "err_n_m", "err_e_m", "err_u_m", "yaw_error_ned_wrapped_deg",
                             "yaw_error_ned_unwrapped_deg", "reference_yaw_increment_ned_deg", "reference_path_m"],
                     [[float(elapsed[i]), float(grid[i]), *err[i, [1, 0, 2]], float(yaw_error[i]), float(unwrapped_error[i]),
                       float(ref_delta_ned[i]), float(reference_path[i])] for i in range(0, len(grid), 10)])
        transforms = {}
        for name, mirror, negate_yaw in [("original", False, False), ("east_mirror", True, False),
                                          ("yaw_negated", False, True), ("east_mirror_and_yaw_negated", True, True)]:
            p, yy = aligned_point.copy(), yaw.copy()
            if mirror:
                p[:, 0] *= -1
            if negate_yaw:
                yy *= -1
            transformed, y_new, new_alignment = align(p, yy, reference, ref_yaw, alignment_mask)
            score_new, _, _ = score(transformed, y_new, reference, ref_yaw, elapsed, reference_path)
            transforms[name] = {**score_new, "alignment": new_alignment}
        assert abs(transforms["original"]["horizontal_rmse_m"] - metrics["horizontal_rmse_m"]) < 1e-7
        best_h = min(v["horizontal_rmse_m"] for v in transforms.values())
        best_y = min(v["yaw_rmse_deg"] for v in transforms.values())
        results["branches"][label] = {"C1": {"samples": samples, "series": series.name, "frozen_alignment": old_align,
                    "metrics": metrics, "reproduction_check": reproduction},
                "C2": {"transform_frame": "Apply to already aligned ENU antenna-midpoint trajectory; mirror E only and/or negate ENU yaw, then refit the same initial 10 s yaw+translation.",
                       "transforms": transforms, "max_horizontal_improvement_factor": metrics["horizontal_rmse_m"] / best_h,
                       "max_yaw_improvement_factor": metrics["yaw_rmse_deg"] / best_y},
                "C3": {"unwrapped_error_vs_unwrapped_reference_turn": ols(ref_delta_ned, unwrapped_error),
                       "wrapped_error_sensitivity": ols(ref_delta_ned, yaw_error),
                       "reference_turn_range_deg": [float(ref_delta_ned.min()), float(ref_delta_ned.max())],
                       "definition": "OLS with intercept, NED estimate-minus-reference continuous error versus NED reference yaw increment; all 10 Hz epochs."}}
    # Go2 attitude with the primary message foot velocity, plus a fixed finite-difference sensitivity.
    go2_est = frozen.interpolate_estimate({"time_unix_s": time_unix, "position": arrays["leg_go2_position"],
                                          "rotation": arrays["go2_rotation"]}, grid + spec["base_time"])
    G = go2_est["rotation"]
    gyro_yaw = np.degrees(np.arctan2(G[:, 1, 0], G[:, 0, 0]))
    for label, key in [("foot_speed_body", "leg_go2_position"), ("finite_difference", "leg_go2_fd_position")]:
        p_body = interp(arrays["t_rel"], arrays[key], grid)
        p = p_body + np.einsum("nij,j->ni", G, lever)
        aligned, yaw, fit = align(p, gyro_yaw, reference, ref_yaw, alignment_mask)
        metrics, err, ye = score(aligned, yaw, reference, ref_yaw, elapsed, reference_path)
        results["C4"][label] = {**metrics, "alignment": fit, "evaluation_point": "Same antenna-midpoint lever as HX-02",
            "integration_gap_record": spec["leg_integration_gaps"],
            "claim_limit": "Conditional input diagnostic with onboard Go2 attitude; not an independently proven performance bound."}
        write_series(out / f"LEG_{label}_C4_1S.csv", ["elapsed_s", "err_e_m", "err_n_m", "err_u_m", "horizontal_error_m", "reference_path_m"],
                     [[float(elapsed[i]), *err[i], float(np.linalg.norm(err[i, :2])), float(reference_path[i])]
                      for i in range(0, len(grid), 10)])
    dump(out / "C_TABLES.json", results)
    print(json.dumps({"sequence": spec["sequence_id"], "trace_open_count": 1, "branches": list(results["branches"])}))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--spec", type=Path, required=True)
    spec = json.loads(parser.parse_args().spec.read_text())
    expected = Path(spec["trace"])
    seen = 0

    def guard(event, args):
        nonlocal seen
        if event == "open" and isinstance(args[0], (str, bytes, os.PathLike)):
            path = Path(os.fsdecode(args[0]))
            if path.suffix.lower() in {".bag", ".fpl"}:
                raise RuntimeError("No bag/fpl access in diagnostic")
            if path.name.startswith("trace_vrtk"):
                assert path == expected and seen == 0 and not (args[2] & (os.O_WRONLY | os.O_RDWR))
                seen += 1
        if event in {"subprocess.Popen", "os.system", "os.exec", "os.posix_spawn"}:
            raise RuntimeError("Diagnostic child cannot execute another program")
    sys.addaudithook(guard)
    evaluate(spec)
    assert seen == 1


if __name__ == "__main__":
    main()
