"""Read-only observations inside the unchanged archived evaluator process.

No reference path is opened here. Hashing uses the evaluator's existing handle,
before pandas consumes it; observations never replace a function or array.
"""
from __future__ import annotations

import hashlib
import ast
import json
import os
from pathlib import Path
import sys

import numpy as np


def consistency_check(nav, errors, reference):
    # Execute the unchanged pure function from its tracked source. Importing the
    # plotting module would initialize Matplotlib font-cache threads, despite no
    # plot being requested. No expression or constant in the function is edited.
    source_path = Path(__file__).resolve().parents[1] / "publication/canonical541_figures.py"
    source = source_path.read_bytes()
    nodes = [node for node in ast.parse(source).body if isinstance(node, ast.FunctionDef) and node.name == "_local_enu"]
    if len(nodes) != 1:
        raise RuntimeError("Publication pure projection function is not unique")
    namespace = {"np": np}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(source_path), "exec"), namespace)
    _local_enu = namespace["_local_enu"]
    t = errors["time"].to_numpy(float)
    nt = nav["time"].to_numpy(float)
    tr = reference[(reference.time >= t[0] - 1) & (reference.time <= t[-1] + 1)]
    if tr.empty or not len(t):
        raise RuntimeError("No independent reference support for consistency gate")
    tt = tr.time.to_numpy(float)
    estimate = [np.interp(t, nt, nav[key].to_numpy(float)) for key in ("lat", "lon", "alt")]
    ref = [np.interp(t, tt, tr[key].to_numpy(float)) for key in ("lat", "lon", "alt")]
    est_yaw = np.rad2deg(np.interp(t, nt, np.unwrap(np.deg2rad(nav.yaw.to_numpy(float)))))
    ref_yaw = np.rad2deg(np.interp(t, tt, np.unwrap(np.deg2rad((90 - tr.yaw.to_numpy(float)) % 360))))
    origin = tuple(value[0] for value in ref)
    ee, en, eu = _local_enu(*estimate, *origin)
    re, rn, ru = _local_enu(*ref, *origin)
    de = ee - errors.err_e_m.to_numpy(float) - re
    dn = en - errors.err_n_m.to_numpy(float) - rn
    du = eu - errors.err_u_m.to_numpy(float) - ru
    dy = (est_yaw - errors.yaw_err_deg.to_numpy(float) - ref_yaw + 180) % 360 - 180
    if not np.isfinite(np.column_stack((de, dn, du, dy))).all():
        raise RuntimeError("Nonfinite consistency residual")
    h, u, yaw = float(np.max(np.hypot(de, dn))), float(np.max(np.abs(du))), float(np.max(np.abs(dy)))
    return {"horizontal_max_m": h, "up_max_m": u, "yaw_max_deg": yaw,
            "matched_epoch_count": len(t), "position_threshold_m": 0.01,
            "yaw_threshold_deg": 0.01, "passed": h <= 0.01 and u <= 0.01 and yaw <= 0.01,
            "source": "publication/canonical541_figures.py:mfig00_reference_comparison",
            "projection_source_sha256": hashlib.sha256(source).hexdigest(),
            "projection_source_lines": [nodes[0].lineno, nodes[0].end_lineno],
            "plotting_module_imported": "matplotlib" in sys.modules,
            "independent_reference": "unchanged evaluator load_trace return; no reconstructed reference",
            "time_offset_applied": 0.0}


def install(config_path):
    config = json.loads(Path(config_path).read_text())
    evaluator, trace = config["evaluator"], config["trace"]
    state = {"pid": os.getpid(), "trace_handle_hash_count": 0,
             "evaluator_sha256": config["evaluator_sha256"]}
    reference = None

    def observe(frame, event, returned):
        nonlocal reference
        if event != "return":
            return
        name = frame.f_code.co_name
        if name == "get_handle" and frame.f_globals.get("__name__") == "pandas.io.common":
            handle = getattr(returned, "handle", None)
            if str(getattr(handle, "name", "")) == trace:
                if state["trace_handle_hash_count"]:
                    raise RuntimeError("Evaluator opened reference more than once")
                position = handle.tell()
                if position != 0:
                    raise RuntimeError("Reference hash observation did not precede parsing")
                binary = getattr(handle, "buffer", handle)
                digest = hashlib.sha256()
                size = 0
                while chunk := binary.read(1024 * 1024):
                    if not isinstance(chunk, bytes):
                        raise RuntimeError("Reference handle is not byte-addressable")
                    digest.update(chunk)
                    size += len(chunk)
                handle.seek(position)
                state.update(trace_handle_hash_count=1, trace_sha256=digest.hexdigest(), trace_size_bytes=size)
                if state["trace_sha256"] != config["trace_sha256"]:
                    raise RuntimeError("Reference SHA256 mismatch before evaluator parsing")
        if frame.f_code.co_filename != evaluator:
            return
        if name == "load_trace":
            if state["trace_handle_hash_count"] != 1:
                raise RuntimeError("Evaluator trace handle was not independently hash-verified")
            local = frame.f_locals
            state["selected_columns"] = {key: local[var] for key, var in
                (("time", "time_col"), ("lat", "lat_col"), ("lon", "lon_col"),
                 ("height", "alt_col"), ("yaw", "yaw_col"), ("pitch", "pitch_col"), ("roll", "roll_col"))}
            state["trace_header"] = list(local["df"].columns)
            start, end = config["window"]
            times = local["gt_time"].to_numpy(float)
            state["reference_epoch_count"] = int(np.sum((times >= start) & (times <= end)))
            reference = returned
            print("CLEAN5_SELECTED_TRACE_COLUMNS " + json.dumps(state["selected_columns"], sort_keys=True), flush=True)
        elif name == "main" and reference is not None and "err_df" in frame.f_locals:
            import pandas as pd
            errors = pd.read_csv(Path(config["outdir"]) / "error_series.csv")
            state["consistency"] = consistency_check(frame.f_locals["nav"], errors, reference)
            state["hash_role"] = "existing evaluator handle; hash then rewind before parsing; zero extra trace opens"
            state["observation_only"] = True
            state["window"] = config["window"]
            path = Path(config["outdir"]) / "EVALUATOR_CAPTURE.json"
            with path.open("x", encoding="utf-8") as handle:
                json.dump(state, handle, indent=2, ensure_ascii=False, allow_nan=False)
                handle.write("\n")
            sys.setprofile(None)

    sys.setprofile(observe)
