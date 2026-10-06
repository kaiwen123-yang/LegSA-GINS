"""Observe existing evaluator arrays after its unchanged capture callback.

Only the explicitly registered BY2/C00/F04/v3 child exports display samples.
No extra trace handle, interpolation, metric, alignment, or solver input is made.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import sys

sys.dont_write_bytecode = True


def export_matched_trajectory(local, outdir):
    """Copy exact frozen-evaluator matched arrays; never reconstruct reference."""
    import hashlib
    import numpy as np
    import pandas as pd

    required = ("t_nav", "gt_lat", "gt_lon", "gt_alt", "gt_yaw_for_cmp", "nav", "err_df")
    if any(name not in local for name in required):
        raise RuntimeError("V3 display observer lacks frozen evaluator matched locals")
    nav = local["nav"]
    columns = {"time": np.asarray(local["t_nav"]),
        "truth_latitude_deg": np.asarray(local["gt_lat"]),
        "truth_longitude_deg": np.asarray(local["gt_lon"]),
        "truth_height_m": np.asarray(local["gt_alt"]),
        "truth_yaw_deg": np.asarray(local["gt_yaw_for_cmp"]),
        "estimate_latitude_deg": nav["lat"].to_numpy(),
        "estimate_longitude_deg": nav["lon"].to_numpy(),
        "estimate_height_m": nav["alt"].to_numpy(),
        "estimate_yaw_deg": nav["yaw"].to_numpy()}
    if len({len(value) for value in columns.values()}) != 1 or not len(columns["time"]):
        raise RuntimeError("V3 display observer matched-array length mismatch")
    if not np.isfinite(np.column_stack(list(columns.values()))).all():
        raise RuntimeError("V3 display observer nonfinite matched arrays")
    if not np.array_equal(columns["time"], local["err_df"]["time"].to_numpy()):
        raise RuntimeError("V3 display observer error/matched epoch mismatch")
    if np.any(np.diff(columns["time"]) <= 0):
        raise RuntimeError("V3 display observer unordered matched epochs")
    output = Path(outdir) / "MATCHED_TRAJECTORY.csv"
    # pandas serializes new views into a separate file; evaluator arrays are untouched.
    with output.open("x", encoding="utf-8", newline="") as stream:
        pd.DataFrame(columns).to_csv(stream, index=False)
    receipt = {"status": "EXPORTED_EXISTING_MATCHED_ARRAYS", "observation_only": True,
        "role": "MFIG00_DISPLAY_ONLY", "additional_trace_opens": 0,
        "reference_reconstructed_from_errors": False, "new_interpolation": False,
        "evaluator_arrays_mutated": False, "matched_epoch_count": len(columns["time"]),
        "data_mode": "real_clean", "synthetic_data_used": False, "semisynthetic_data_used": False,
        "csv_sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
        "source_locals": list(required)}
    with (Path(outdir) / "MATCHED_TRAJECTORY_MANIFEST.json").open("x", encoding="utf-8") as stream:
        json.dump(receipt, stream, indent=2, allow_nan=False)
        stream.write("\n")


def wrap_profile(config, original):
    def observe(frame, event, returned):
        # Preserve the original callback, including its independent-handle hash,
        # selected-column audit, consistency check, and profile-disabling policy.
        original(frame, event, returned)
        if (event == "return" and frame.f_code.co_filename == config["evaluator"]
                and frame.f_code.co_name == "main" and "err_df" in frame.f_locals):
            export_matched_trajectory(frame.f_locals, config["outdir"])
    return observe


def install_v3(config_path):
    from legsa_gins.paper_rebuild.clean5_sequence.evaluator_capture import install
    config = json.loads(Path(config_path).read_text())
    install(config_path)
    if config.get("v3_export_matched_truth") is True:
        original = sys.getprofile()
        if not callable(original):
            raise RuntimeError("Frozen evaluator observer callback was not installed")
        sys.setprofile(wrap_profile(config, original))


if os.environ.get("CLEAN5_EVALUATOR_CAPTURE_CONFIG"):
    try:
        install_v3(os.environ["CLEAN5_EVALUATOR_CAPTURE_CONFIG"])
    except BaseException:
        import traceback
        traceback.print_exc()
        os._exit(125)
