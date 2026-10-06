#!/usr/bin/env python3
"""Measure the eight admitted archives before the storage-only continuation."""
from __future__ import annotations
import argparse
from concurrent.futures import ThreadPoolExecutor
import csv
from datetime import datetime, timezone
import hashlib
import io
import json
import math
from pathlib import Path
import subprocess
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from legsa_gins.paper_rebuild.clean6_canonical_v2.io_recovery import _metadata_bytes


def write_verified(path, payload):
    if path.exists():
        raise FileExistsError(path)
    _metadata_bytes(path, payload, append=False)
    if path.read_bytes() != payload:
        raise RuntimeError("CAPACITY_RECEIPT_COPY_MISMATCH")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, required=True)
    ap.add_argument("--registry", type=Path, required=True)
    ap.add_argument("--aggregate-control-allowance-bytes", type=int, default=20_000_000_000)
    args = ap.parse_args()
    root = args.root
    if root.name != "CLEAN8_PROTOCOL_V3" or root.parent.name != "stages" or root.is_symlink():
        raise ValueError("CAPACITY_ROOT_SCOPE")
    registry = json.loads(args.registry.read_text())
    if len(registry) != 6468:
        raise ValueError("CAPACITY_FROZEN_QUEUE_COUNT")
    for number in range(1, 9):
        audit = json.loads((root / f"00_CONTROL/V3R_RECONCILIATION/BATCH_{number:03d}/BATCH_AUDIT.json").read_text())
        if audit["row"]["verification"] != "PASS" or audit["row"]["run_count"] != 64:
            raise ValueError("CAPACITY_BATCH_NOT_ADMITTED")
    specs = registry[:512]
    entries = [(s, "native", root / "03_NATIVE" / s["run_id"]) for s in specs]
    entries += [(s, v, root / "04_EVALUATION" / s["run_id"] / v) for s in specs for v in ("v3", "v2")]
    paths = [str(e[2]) for e in entries]
    def measure(apparent):
        argv = ["du", "-s", "-B1"] + (["--apparent-size"] if apparent else []) + ["--"] + paths
        result = subprocess.run(argv, capture_output=True, text=True, check=True)
        values = {line.split("\t", 1)[1]: int(line.split("\t", 1)[0]) for line in result.stdout.splitlines()}
        if set(values) != set(paths):
            raise ValueError("CAPACITY_DU_COVERAGE")
        return values
    with ThreadPoolExecutor(2) as pool:
        allocated, apparent = list(pool.map(measure, (False, True)))
    subset = {"C00_clean_normal"} | {f"D{i:02d}_seed_00" for i in range(1, 61)}
    def keep(s):
        return s["domain"] in ("SEQUENCE", "ADDENDUM") or s["case_id"] in subset
    rows = []
    for spec, version, directory in entries:
        error_allocated = error_apparent = 0
        if version != "native":
            # Physical payloads are unique; original plain/gzip receipt aliases
            # may both refer to this one gzip. No data payload is opened here.
            for name in ("error_series.csv", "error_series.csv.gz"):
                p = directory / "FROZEN_EVALUATOR" / name
                if p.exists():
                    if p.is_symlink():
                        raise ValueError("CAPACITY_SYMLINK")
                    st = p.stat()
                    error_allocated += st.st_blocks * 512
                    error_apparent += st.st_size
        rows.append(dict(run_id=spec["run_id"], kind="native" if version == "native" else "evaluator",
            version=version, relative_path=str(directory.relative_to(root)), allocated_bytes=allocated[str(directory)],
            apparent_bytes=apparent[str(directory)], error_allocated_bytes=error_allocated,
            error_apparent_bytes=error_apparent, retain_error_series=keep(spec)))
    totals = {}
    for kind, count, remaining in (("native", 512, 5956), ("evaluator", 1024, 11912)):
        group = [r for r in rows if r["kind"] == kind]
        totals[kind] = dict(sample_slots=count, remaining_archive_slots=remaining)
        for field in ("allocated_bytes", "apparent_bytes", "error_allocated_bytes", "error_apparent_bytes"):
            total = sum(r[field] for r in group)
            totals[kind]["sample_" + field] = total
            totals[kind]["mean_" + field] = total / count
    free = int(subprocess.check_output(["df", "-B1", "--output=avail", "/mnt/g"], text=True).splitlines()[-1])
    predictions = {}
    for metric in ("allocated_bytes", "apparent_bytes"):
        matrix = math.ceil(sum(x["mean_" + metric] * x["remaining_archive_slots"] for x in totals.values()))
        predictions["matrix_remaining_" + metric] = matrix
        predictions["matrix_aggregate_remaining_" + metric] = matrix + args.aggregate_control_allowance_bytes
        omit_remaining = 2 * sum(not keep(s) for s in registry[512:])
        saved = math.floor(totals["evaluator"]["mean_error_" + metric] * omit_remaining)
        predictions["conditional_matrix_aggregate_remaining_" + metric] = matrix - saved + args.aggregate_control_allowance_bytes
        predictions["existing_sample_reclaimable_" + metric] = sum(r["error_" + metric] for r in rows if r["kind"] == "evaluator" and not r["retain_error_series"])
    value = dict(schema="V3R_CAPACITY_FORECAST_V1", measured_utc=datetime.now(timezone.utc).isoformat(),
        storage_provenance_only=True, native_calls=0, evaluator_calls=0,
        registry_sha256=hashlib.sha256(args.registry.read_bytes()).hexdigest(),
        sample_batches=8, samples=totals, remaining_native_calls=5954,
        remaining_native_archive_slots=5956, remaining_evaluator_archive_slots=11912,
        note="Two already sealed sequence identity natives still require archive slots; neither is rerun.",
        g_available_bytes_at_forecast=free, threshold_fraction=0.6, threshold_bytes=free * 0.6,
        aggregate_control_allowance_bytes=args.aggregate_control_allowance_bytes,
        allowance_basis="Conservative engineering reserve, not a measured scientific result; covers aggregate, ten figure groups, control journals and safety slack.",
        projection_assumption="First eight complete batches represent remaining stored slot size; later sequence length and failure mix can change actual occupancy.",
        conditional_retention_triggered=predictions["matrix_aggregate_remaining_allocated_bytes"] > free * 0.6,
        retained_native_slots=sum(keep(s) for s in registry), retained_evaluator_slots=2*sum(keep(s) for s in registry),
        omitted_evaluator_slots=2*sum(not keep(s) for s in registry), **predictions)
    text = io.StringIO(); writer = csv.DictWriter(text, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)
    csv_bytes = text.getvalue().encode()
    control = root / "00_CONTROL"
    write_verified(control / "CAPACITY_SAMPLE_8_BATCHES.csv", csv_bytes)
    value["sample_csv_sha256"] = hashlib.sha256(csv_bytes).hexdigest()
    write_verified(control / "CAPACITY_FORECAST.json", (json.dumps(value, indent=2) + "\n").encode())
    print(json.dumps(value, indent=2), flush=True)


if __name__ == "__main__":
    main()
