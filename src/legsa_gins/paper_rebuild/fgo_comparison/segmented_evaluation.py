"""Sealed, offline GNSS1 position comparison for the separate gap diagnostic.

All methods share the physical point and fixed local N/E/Up anchor. Their actual sensor
inputs and batch/current-node information remain different. Native positions
are never interpolated, and every missing or prior-only epoch keeps the original
denominator. This evaluator imports no solver and never launches one.
"""
from __future__ import annotations

import argparse
from io import BytesIO
import json
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from .evaluation import evaluator_module, reference_at, ned_to_ecef, statistics, resolve
from ..clean5_parity.evaluation import body_to_ned
from ..horizontal_literature.shared_raw_backend import ecef_to_geodetic
from .raw_inputs import aliases, sha256, dump
from .runner import json_safe, write_csv
from .segmented_diagnostic import verify_sources


def imu_to_gnss1(position, attitude, lever):
    """Use each OiSAM output's OWN estimated attitude at the IMU position."""
    position, attitude, lever = np.asarray(position), np.asarray(attitude), np.asarray(lever)
    if position.shape != attitude.shape or position.ndim != 2 or position.shape[1] != 3 or lever.shape != (3,):
        raise ValueError("GNSS1_POINT_TRANSFORM_SCHEMA")
    if not np.isfinite(position).all() or not np.isfinite(attitude).all() or not np.isfinite(lever).all():
        raise ValueError("GNSS1_POINT_TRANSFORM_NONFINITE")
    if not len(position):
        return position.copy()
    llh = np.asarray([ecef_to_geodetic(item) for item in position])
    cne = ned_to_ecef(np.rad2deg(llh[:, 0]), np.rad2deg(llh[:, 1]))
    return position + np.einsum("nij,njk,k->ni", cne, body_to_ned(attitude), lever)


def score_gnss1(module, reference, states, spec, method, run, role, lever):
    if role not in ("PRIMARY_DYNAMIC_ONLY", "SECONDARY_ALL_VALID_POSITION"):
        raise ValueError("UNREGISTERED_SUPPORT_ROLE")
    start, end = spec["window_seconds"]
    expected = int(end-start)+1
    selected = states.loc[(states.time_rel_s >= start) & (states.time_rel_s <= end)].copy()
    times = selected.time_rel_s.to_numpy(float)
    if not np.isfinite(times).all() or np.any(np.diff(times) <= 0) or len(set(np.rint(times).astype(int))) != len(times):
        raise ValueError("OUTPUT_DUPLICATE_OR_REORDERED_EPOCH")
    if len(times) > expected:
        raise ValueError("OUTPUT_EXCEEDS_ORIGINAL_DENOMINATOR")
    xyz = selected[["x_ecef_m", "y_ecef_m", "z_ecef_m"]].to_numpy(float)
    finite = (selected.valid.to_numpy(float) > 0) & np.isfinite(xyz).all(axis=1)
    prior = np.zeros(len(times), bool)
    if method == "OISAM":
        if "prior_only" not in selected or "dynamic_valid" not in selected:
            raise ValueError("SEGMENTED_PRIOR_ROLE_LEDGER_MISSING")
        prior = selected.prior_only.to_numpy(int) > 0
        attitude = selected[["roll_deg", "pitch_deg", "yaw_deg"]].to_numpy(float)
        finite &= np.isfinite(attitude).all(axis=1)
        if finite.any():
            xyz[finite] = imu_to_gnss1(xyz[finite], attitude[finite], lever)
        if role == "PRIMARY_DYNAMIC_ONLY":
            finite &= (selected.dynamic_valid.to_numpy(int) > 0) & ~prior
    support = finite & (times >= reference.time.min()) & (times <= reference.time.max())
    llh, rpy, truth = reference_at(module, reference, times, spec["baseline_median_m"], "GNSS1_ANTENNA")
    anchor_llh, _, _ = reference_at(module, reference, np.array([start]), spec["baseline_median_m"], "GNSS1_ANTENNA")
    # Fixed common coordinate frame independent of each method's valid support.
    rotation = ned_to_ecef(anchor_llh[:, 0], anchor_llh[:, 1])[0]
    ned = (xyz-truth) @ rotation
    error = pd.DataFrame({"time": times, "expected_second": np.rint(times).astype(int),
        "err_n_m": ned[:, 0], "err_e_m": ned[:, 1], "err_u_m": -ned[:, 2],
        "horizontal_err_m": np.linalg.norm(ned[:, :2], axis=1),
        "position_3d_err_m": np.linalg.norm(ned, axis=1), "valid": support.astype(int),
        "prior_only": prior.astype(int), "native_status": selected.status.to_numpy()})
    error.loc[~support, ["err_n_m", "err_e_m", "err_u_m", "horizontal_err_m", "position_3d_err_m"]] = np.nan
    # Save interpolation support; no estimate interpolation and no extrapolation accepted.
    tt = reference.time.to_numpy(float)
    right = np.searchsorted(tt, times, side="left").clip(0, len(tt)-1)
    left = np.where(tt[right] == times, right, np.maximum(0, right-1))
    error["reference_left_s"], error["reference_right_s"] = tt[left], tt[right]
    error["reference_bracket_span_s"] = tt[right]-tt[left]
    if method == "OISAM":
        error["block_id"] = selected.block_id.to_numpy()
        error["yaw_err_deg"] = module.wrap_deg(attitude[:, 2]-rpy[:, 2])
        error.loc[~support, "yaw_err_deg"] = np.nan
    row = {"sequence_id": spec["dataset_id"], "method_id": method, "support_role": role,
        "support": "OWN_VALID", "physical_point": "GNSS1_ANTENNA", "status": run["terminal_status"],
        "expected_epoch_count": expected, "actual_epoch_count": len(times),
        "finite_epoch_count": int(finite.sum()), "matched_epoch_count": int(support.sum()),
        "missing_or_invalid_count": expected-int(support.sum()), "coverage_fraction": int(support.sum())/expected,
        "prior_only_native_count": int(prior.sum()),
        "prior_only_primary_excluded_count": int(prior.sum()) if role == "PRIMARY_DYNAMIC_ONLY" else 0,
        "first_output_s": float(times[support][0]) if support.any() else None,
        "last_output_s": float(times[support][-1]) if support.any() else None,
        "window_start_s": start, "window_end_s": end,
        "reference_bracket_max_s_on_support": float(error.loc[support, "reference_bracket_span_s"].max()) if support.any() else None,
        "original_native_identity_reused": method != "OISAM", "attitude_is_estimated": method == "OISAM",
        "input_layer": "RTK_BODY_IMU_REPEATED_BLOCK_A1" if method == "OISAM" else "RAW_CODE_AHRS_IMU" if method == "WEN_TC" else "RAW_CODE_DOPPLER",
        "solver_and_adapter_elapsed_s": run.get("solver_and_adapter_elapsed_s"),
        "comparison_boundary": "same physical point/support; different sensors and batch/current-node information; engineering recovery diagnostic",
        **statistics(error)}
    trajectory = pd.DataFrame({"time": times, "valid": support.astype(int), "prior_only": prior.astype(int),
        "x_ecef_m": xyz[:, 0], "y_ecef_m": xyz[:, 1], "z_ecef_m": xyz[:, 2],
        "truth_x_ecef_m": truth[:, 0], "truth_y_ecef_m": truth[:, 1], "truth_z_ecef_m": truth[:, 2]})
    trajectory.loc[~support, ["x_ecef_m", "y_ecef_m", "z_ecef_m"]] = np.nan
    return row, error, trajectory


def common_rows(rows, errors):
    lookup = {}
    for method, error in errors.items():
        times = error.time.to_numpy(float)
        keys = np.rint(times).astype(int)
        valid = (error.valid.to_numpy(int) > 0) & (np.abs(times-keys) <= .005)
        if len(set(keys[valid])) != sum(valid):
            raise ValueError("DUPLICATE_COMMON_SUPPORT_KEY")
        lookup[method] = {int(keys[i]): int(i) for i in np.flatnonzero(valid)}
    if set(lookup) != {"OISAM", "WEN_TC", "GNC"}:
        raise ValueError("INCOMPLETE_COMPARISON_COHORT")
    keys = sorted(set.intersection(*(set(item) for item in lookup.values())))
    result = []
    for row in rows:
        selected = errors[row["method_id"]].iloc[[lookup[row["method_id"]][key] for key in keys]]
        result.append({**row, **statistics(selected), "support": "COMMON_THREE_TIME_KEYS",
            "own_matched_epoch_count": row["matched_epoch_count"], "matched_epoch_count": len(keys),
            "finite_epoch_count": len(keys), "missing_or_invalid_count": row["expected_epoch_count"]-len(keys),
            "coverage_fraction": len(keys)/row["expected_epoch_count"],
            "first_output_s": float(selected.time.iloc[0]) if len(keys) else None,
            "last_output_s": float(selected.time.iloc[-1]) if len(keys) else None,
            "reference_bracket_max_s_on_support": float(selected.reference_bracket_span_s.max()) if len(keys) else None,
            "common_time_tolerance_s": .005})
    return result, keys


def reference_metadata(module, reference, specification):
    """Save independent coordinate-check inputs, without another raw GT open."""
    anchor, _, _ = reference_at(module, reference,
        np.array([specification["window_seconds"][0]]), specification["baseline_median_m"], "GNSS1_ANTENNA")
    return {"anchor_llh_deg_m": anchor[0].tolist(),
            "reference_time_min_s": float(reference.time.min()),
            "reference_time_max_s": float(reference.time.max()),
            "reference_clean_epoch_count": len(reference)}


def evaluate(roots_path, protocol_path, sequence):
    roots = aliases(roots_path)
    code, stage = Path(roots["<CODE_ROOT>"]), Path(roots["<FGO_DIAGNOSTIC_ROOT>"])
    protocol = json.loads(Path(protocol_path).read_text())
    verify_sources(code, protocol)
    seal = json.loads((stage/"ALL_NATIVE_SEALED.json").read_text())
    if not seal["all_three_new_native_terminal"] or seal["new_native_reference_opens"] != 0 or seal["protocol_sha256"] != sha256(protocol_path):
        raise ValueError("DIAGNOSTIC_NATIVE_SEAL_REQUIRED_BEFORE_REFERENCE")
    native = {}
    for method in ("OISAM", "WEN_TC", "GNC"):
        binding = seal["comparison_identities"][sequence][method]
        path = resolve(binding["path"], roots)
        if sha256(path/"RUN.json") != binding["run_json_sha256"]:
            raise ValueError("COMPARISON_RUN_IDENTITY_CHANGED")
        run = json.loads((path/"RUN.json").read_text())
        for name, digest in run["output_hashes"].items():
            if sha256(path/name) != digest:
                raise ValueError("COMPARISON_NATIVE_SEAL_CHANGED")
        native[method] = (run, pd.read_csv(path/"STATES.csv"), binding)
    specification = code/protocol["execution_contract_path"]
    if sha256(specification) != protocol["execution_contract_sha256"]:
        raise ValueError("EXECUTION_CONTRACT_CHANGED")
    spec = yaml.safe_load(specification.read_text())["sequences"][sequence]
    module = evaluator_module(roots)
    source = resolve(spec["trace"]["path"], roots)
    with source.open("rb") as stream:
        payload = stream.read()
    import hashlib
    if hashlib.sha256(payload).hexdigest() != spec["trace"]["sha256"]:
        raise ValueError("REFERENCE_IDENTITY_MISMATCH")
    reference = module.load_trace(BytesIO(payload), spec["base_time"])
    del payload
    if not len(reference) or np.any(np.diff(reference.time) <= 0):
        raise ValueError("REFERENCE_DUPLICATE_OR_REORDERED_TIME")
    destination = stage/"evaluation"/sequence
    destination.mkdir(parents=True, exist_ok=False)
    rows, common_keys = [], {}
    for role in ("PRIMARY_DYNAMIC_ONLY", "SECONDARY_ALL_VALID_POSITION"):
        own, errors = [], {}
        for method, (run, states, binding) in native.items():
            row, error, trajectory = score_gnss1(module, reference, states, spec, method, run, role, protocol["lever_imu_to_gnss1_frd_m"])
            row["native_run_sha256"] = binding["run_json_sha256"]
            own.append(row)
            errors[method] = error
            stem = method+"_"+role
            error.to_csv(destination/(stem+"_ERRORS.csv"), index=False, lineterminator="\n")
            trajectory.to_csv(destination/(stem+"_TRAJECTORY.csv"), index=False, lineterminator="\n")
        common, keys = common_rows(own, errors)
        rows.extend(own+common)
        common_keys[role] = keys
    verify_sources(code, protocol)
    write_csv(destination/"METRICS.csv", rows)
    dump(destination/"EVALUATION.json", json_safe({"sequence": sequence, "rows": rows,
        **reference_metadata(module, reference, spec),
        "common_nominal_keys": common_keys, "reference_read_count": 1,
        "reference_sha256": spec["trace"]["sha256"], "native_seal_sha256": sha256(stage/"ALL_NATIVE_SEALED.json"),
        "protocol_sha256": sha256(protocol_path), "native_bindings": {m: v[2] for m, v in native.items()},
        "reference_interpolation": "frozen linear LLH/RP and unwrap yaw, brackets saved; no extrapolation admitted",
        "output_interpolation": False, "physical_point": "GNSS1_ANTENNA",
        "coordinate_frame": "local N/E/Up anchored at registered formal-window start, same for every method",
        "prior_only_primary_excluded": True, "source_before_after_match": True}))
    return rows


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--roots", required=True)
    parser.add_argument("--protocol", required=True)
    parser.add_argument("--sequence", required=True, choices=["BY2", "BY2H", "BY2O"])
    arguments = parser.parse_args()
    print(json.dumps(json_safe(evaluate(arguments.roots, arguments.protocol, arguments.sequence))), flush=True)
