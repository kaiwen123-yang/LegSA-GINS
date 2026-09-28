#!/usr/bin/env python3
"""B2 saved-state algebra: separate bias and contact-update yaw contributions.

Each interval independently uses the saved left endpoint. No state is fed into
the next interval, no covariance/update equation or filter implementation runs.
"""
import argparse
import csv
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
from scipy.spatial.transform import Rotation

from legsa_gins.paper_rebuild.hext.hx02d_reference_free import dump, guard, load_cache, ols, wrap, correlation


def yaw(matrix):
    return np.degrees(np.arctan2(matrix[:, 1, 0], matrix[:, 0, 0]))


def run(root):
    output = root / "B_SAVED_STATE_READOUT"
    output.mkdir(exist_ok=False)
    all_results = {}
    for seq in ["BY2", "BY2O"]:
        base = root / "B_REFERENCE_FREE" / seq
        spec = json.loads((base / "SPEC.json").read_text())
        tables = json.loads((base / "OUTPUT/B_TABLES.json").read_text())
        cache = load_cache(spec["cache"], json.loads(Path(spec["cache_manifest"]).read_text()))
        payload = (base / "OUTPUT/B_ARRAYS.npz").read_bytes()
        assert hashlib.sha256(payload).hexdigest() == tables["array_sha256"]
        import io
        with np.load(io.BytesIO(payload), allow_pickle=False) as z:
            arrays = {k: z[k] for k in z.files}
        tt = (cache["t"] - cache["t"][0]) * 1e-9
        dt = np.diff(tt)
        gyro = cache["v"][:-1, :3]
        select = (arrays["t_rel"] >= spec["window"][0]) & (arrays["t_rel"] <= spec["window"][1])
        selected = np.flatnonzero(select)
        masks = cache["mask"]
        event = masks[1:] != masks[:-1]
        for label in spec["branches"]:
            R = arrays[label + "_rotation"]
            bias = arrays[label + "_gyro_bias"][:-1]
            # Raw gyro and saved-bias increments, each starting at the saved R_k.
            raw_step = R[:-1] @ Rotation.from_rotvec(gyro * dt[:, None]).as_matrix()
            bias_step = R[:-1] @ Rotation.from_rotvec((gyro - bias) * dt[:, None]).as_matrix()
            native_delta = wrap(yaw(R[1:]) - yaw(R[:-1]))
            direct = wrap(yaw(raw_step) - yaw(R[:-1]))
            bias_effect = wrap(yaw(bias_step) - yaw(raw_step))
            update_effect = wrap(yaw(R[1:]) - yaw(bias_step))
            max_identity_error = float(np.max(np.abs(native_delta - direct - bias_effect - update_effect)))
            assert max_identity_error < 1e-8
            scalar_z = np.diff(arrays["raw_gyro_z_integral_deg"])
            components = {"raw_sensor_z_integral": scalar_z,
                          "installation_and_3d_rotation": direct - scalar_z,
                          "saved_gyro_bias_effect": bias_effect,
                          "contact_update_rotation_effect": update_effect,
                          "actual_native_yaw_increment": native_delta}
            cum = {k: np.r_[0., np.cumsum(v)] for k, v in components.items()}
            metrics = {k: {"cumulative_end_minus_start_deg": float(v[selected[-1]] - v[selected[0]]),
                           "ols_rate_deg_per_min": ols(tt[select] / 60, v[select])["slope"]} for k, v in cum.items()}
            correlations = {"update_increment_vs_contact_switch": correlation(event[selected[:-1]], update_effect[selected[:-1]]),
                            "abs_update_increment_vs_contact_switch": correlation(event[selected[:-1]], np.abs(update_effect[selected[:-1]]))}
            # Save complete independent decomposition and switch counts at 1-second bins.
            elapsed = tt[select] - tt[selected[0]]
            with (output / f"{seq}_{label}_B2_DECOMPOSITION_1S.csv").open("x", newline="") as handle:
                writer = csv.writer(handle, lineterminator="\n")
                writer.writerow(["elapsed_s", *cum, "contact_switch_intervals"])
                for second in range(int(elapsed[-1]) + 1):
                    target = tt[selected[0]] + second
                    values = [float(np.interp(target, tt, v) - v[selected[0]]) for v in cum.values()]
                    m = (tt[1:] >= target) & (tt[1:] < target + 1)
                    writer.writerow([second, *values, int(event[m].sum())])
            all_results[f"{seq}_{label}"] = {"components": metrics, "exact_increment_identity_max_abs_deg": max_identity_error,
                "source": {"arrays": str(base / "OUTPUT/B_ARRAYS.npz"), "cache": spec["cache"],
                           "native_step_order": "run_h5.cpp:430-443 previous IMU propagate, then current contact lifecycle; backend.cpp:1197-1211 changes R and gyro bias"},
                "correlations": correlations,
                "scope": "Algebraic per-interval comparison to saved states; not a propagated trajectory or filter execution."}
        dt_window = np.diff(tt)[selected[:-1]]
        # Both-endpoint validity; count only intervals within the scored native support.
        valid = masks > 0
        missing = ~(valid[selected[:-1]] & valid[selected[1:]])
        all_results[seq + "_leg_gap_window"] = {"intervals": int(missing.sum()), "duration_s": float(dt_window[missing].sum())}
    dump(output / "B2_STATE_DECOMPOSITION.json", all_results)


if __name__ == "__main__":
    sys.addaudithook(guard)
    parser = argparse.ArgumentParser()
    parser.add_argument("--execution-root", type=Path, required=True)
    run(parser.parse_args().execution_root)
