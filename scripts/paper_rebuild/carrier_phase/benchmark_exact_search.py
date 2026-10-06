#!/usr/bin/env python3
"""One bounded exact-search performance run on five prepared selection epochs.

Choose the implementation through PYTHONPATH. No validation epochs, navigation
or reference file is loaded. Each output file is exclusive and includes the
actual imported source identities, so paired versions cannot be silently mixed.
"""
from pathlib import Path
from dataclasses import asdict, is_dataclass
import argparse
import hashlib
import json
import os
import time
import numpy as np
from shadow_replay import load_model
from legsa_gins.paper_rebuild.carrier_phase import solver, partial, native_sphere
from legsa_gins.paper_rebuild.horizontal_literature import ext01_clambda


def serial(value):
    if is_dataclass(value):
        return serial(asdict(value))
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, dict):
        return {str(k): serial(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [serial(x) for x in value]
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trial", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--start", type=float, required=True)
    parser.add_argument("--cap", type=int, required=True)
    parser.add_argument("--variant", required=True)
    parser.add_argument("--timeout", type=float, default=30.)
    parser.add_argument("--nodes", type=int, default=100000)
    parser.add_argument("--sphere-library", type=Path)
    args = parser.parse_args()
    if os.uname().sysname != "Linux":
        raise RuntimeError("run algorithm benchmarks in Ubuntu WSL")
    if args.output.exists():
        raise FileExistsError(args.output)
    if any(os.environ.get(k) != "1" for k in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS")):
        raise RuntimeError("benchmark requires one BLAS and OMP thread")
    plan_path = args.trial / "PLAN.json"
    plan = json.loads(plan_path.read_text())
    rows = [row for row in plan["records"] if args.start <= row["time_s"] < args.start + 2.]
    if len(rows) != 10:
        raise ValueError("registered acquisition window requires ten prepared slots")
    # Only the first five models are read. Future rows identify the window but
    # no future numerical observations enter selection or integer optimization.
    models = [load_model(args.trial, row, "GPS_GAL_BDS_DUAL") for row in rows[:5]]
    before = time.perf_counter()
    search = partial.prepare_partial_search(
        models, length_m=plan["baseline_length_m"],
        policy=partial.PartialPolicy(max_ambiguities=args.cap))
    preparation_s = time.perf_counter() - before
    if not search.selection.ready:
        raise ValueError(search.selection.status)
    before = time.perf_counter()
    options = {} if args.sphere_library is None else {"sphere_library": args.sphere_library}
    result = partial.solve_partial(
        search, plan["lambda_library"], node_limit=args.nodes, timeout_s=args.timeout, **options)
    elapsed_s = time.perf_counter() - before
    source = {}
    for module in (solver, partial, ext01_clambda, native_sphere):
        path = Path(module.__file__)
        source[module.__name__] = {
            "path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
    record = {
        "variant": args.variant, "window_start_s": args.start, "cap": args.cap,
        "limits": {"nodes": args.nodes, "timeout_s": args.timeout},
        "model_plan_sha256": hashlib.sha256(plan_path.read_bytes()).hexdigest(),
        "source": source, "sphere_library": str(args.sphere_library) if args.sphere_library else None,
        "selection": serial(search.selection),
        "all_labels": search.problem.ambiguity_labels,
        "certificate": serial(result.certificate),
        "best": serial(result.best), "second": serial(result.second),
        "whole_solve_elapsed_s": elapsed_s, "preparation_elapsed_s": preparation_s,
        "future_model_reads": 0, "reference_reads": 0, "native_runs": 0,
        "data_mode": "real_by2_raw", "runtime_role": "single_case_performance_diagnostic"}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x") as stream:
        json.dump(record, stream, indent=2, allow_nan=False)
        stream.write("\n")
    print(json.dumps({
        "variant": args.variant, "start": args.start, "cap": args.cap,
        "certified": result.global_optimum_certified, "elapsed_s": elapsed_s,
        "termination_reason": result.certificate.termination_reason}), flush=True)


if __name__ == "__main__":
    main()
