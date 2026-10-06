"""HX-02 Hartley contact-aided InEKF runs on three sequences (provider + native launch).

Provider: the frozen H5 streaming parser and cache format (hartley_h5, unchanged).
FILE_START sequences use hartley_h5.build_immutable_cache on the sequence's
complete-record Go2 prefix. The CONTRACT_START sequence (BY2H) uses the same
parser, record encoding and cache header, but records before the contract start
are not emitted and the frozen contact hysteresis starts at the first kept record
(its first-record initialization rule, unchanged). Contact thresholds, dwell and
FK measurement std are the BY2 instantiation (registry :44, :48-50), not re-fitted.

Native: the C++ hartley_h5_runner built from the unchanged hartley_inekf sources,
invoked as ``runner CACHE CONFIG OUTPUT_DIR`` with the H5 config key set.
Hartley-S = H5_PRIMARY_GO2_ALLAN_EQ61_FK10MM; Hartley-LIT =
H5_PAPER_TABLE1_PROCESS_REGRESSION_WITH_GO2_FK_PROXY; backend
HARTLEY_IJRR2020_REPORTED_BACKEND. The runner has no maximum-dt rule: any IMU gap
inside the processed records is one zero-order-hold propagation step.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any, Iterator, Mapping

import numpy as np

from ..horizontal_literature import hartley_h5 as h5
from . import hx02_sequence

CONFIG_RUN_IDS = {"S": h5.H5_PRIMARY_RUN_ID, "LIT": "H5_PAPER_TABLE1_PROCESS_REGRESSION_WITH_GO2_FK_PROXY"}
PROCESS_POLICY = {"S": "GO2_CONTINUOUS_IMU_PAPER_NATIVE_CONTACT_EQ61", "LIT": "PAPER_TABLE1_FIVE_PROCESS_EQ61"}
SIGMA_FK_M = 0.010
DIVERGENCE_BOUNDS = {"position_displacement_m": 1.0e4, "speed_mps": 50.0, "height_displacement_m": 1.0e3}
SCOPED_SOURCES = (
    "src/legsa_gins/paper_rebuild/horizontal_literature/hartley_h5.py",
    "src/legsa_gins/paper_rebuild/horizontal_literature/hartley_inekf/tools/run_h5.cpp",
    "src/legsa_gins/paper_rebuild/horizontal_literature/hartley_inekf/src/backend.cpp",
    "src/legsa_gins/paper_rebuild/horizontal_literature/hartley_inekf/include/hartley_inekf/backend.hpp",
    "src/legsa_gins/paper_rebuild/horizontal_literature/hartley_inekf/CMakeLists.txt",
    "src/legsa_gins/paper_rebuild/hext/hx02_hartley.py",
)


class HartleyRunError(RuntimeError):
    pass


def identity(sequence: hx02_sequence.HX02Sequence, inventory: Mapping[str, Any]) -> h5.H5SourceIdentity:
    return h5.verify_source_identity(
        Path(sequence.go2_body), expected_raw_size=int(inventory["size_bytes"]),
        expected_raw_sha256=str(inventory["raw"]["sha256"]),
        prefix_end_exclusive=int(inventory["prefix_end_exclusive"]),
        expected_prefix_sha256=str(inventory["prefix_sha256"]))


def _stream_from(source: Path, prefix_end: int, start_ns: int) -> Iterator[h5.H5Record]:
    """hartley_h5.stream_h5_prefix with records before ``start_ns`` withheld from the detector."""
    detector = h5.ContactHysteresis()
    previous_ns = None
    record_lines: list[str] = []
    offset = 0
    parsed = 0
    with source.open("rb") as handle:
        while offset < prefix_end:
            binary = handle.readline()
            if not binary:
                raise HartleyRunError("source ended inside locked prefix")
            offset += len(binary)
            if offset > prefix_end:
                raise HartleyRunError("prefix boundary splits a physical line")
            line = binary.decode("utf-8", errors="strict")
            if line.strip() == "stamp:" and not line[:1].isspace():
                if record_lines:
                    raise HartleyRunError("record start encountered before delimiter")
                record_lines = [line]
                continue
            if not record_lines:
                continue
            record_lines.append(line)
            if line.strip() != "---":
                continue
            parsed += 1
            timestamp_ns, gyro, accel, force_native, feet_native, _counts = h5._parse_allowed_record(record_lines, parsed)
            record_lines = []
            if previous_ns is not None and timestamp_ns <= previous_ns:
                raise HartleyRunError("timestamps are not strictly increasing")
            previous_ns = timestamp_ns
            if timestamp_ns < start_ns:
                continue
            force = tuple(force_native[index] for index in h5.NATIVE_TO_CANONICAL)
            grouped = tuple(tuple(feet_native[index:index + 3]) for index in range(0, 12, 3))
            feet = tuple(grouped[index] for index in h5.NATIVE_TO_CANONICAL)
            mask, add, remove = detector.update(timestamp_ns, force_native)

            def canonical(native_mask: int) -> int:
                return sum((1 << c) for c, n in enumerate(h5.NATIVE_TO_CANONICAL) if native_mask & (1 << n))
            yield h5.H5Record(timestamp_ns, h5._rotation_x_minus_one_degree(gyro), h5._rotation_x_minus_one_degree(accel),
                              force, feet, canonical(mask), canonical(add), canonical(remove))
    if record_lines:
        raise HartleyRunError("locked prefix ended with an undelimited record")


def build_cache(sequence: hx02_sequence.HX02Sequence, inventory: Mapping[str, Any], provider_dir: Path) -> dict[str, Any]:
    provider_dir.mkdir(parents=True, exist_ok=False)
    source = identity(sequence, inventory)
    cache = provider_dir / "H5_INPUT_CACHE.bin"
    ledger = provider_dir / "H5_INPUT_CONTACT_EVENT_LEDGER.jsonl"
    if sequence.native_start_rel_s is None:
        manifest = h5.build_immutable_cache(source, cache, ledger, expected_records=int(inventory["record_separator_count"]))
        manifest["start_convention"] = "FILE_START"
        manifest["prefix_interval"] = [0, source.prefix_end_exclusive]
    else:
        start_ns = int(round((sequence.base_time + float(sequence.native_start_rel_s)) * 1e9))
        records = list(_stream_from(source.source, source.prefix_end_exclusive, start_ns))
        if not records:
            raise HartleyRunError("no Go2 record at or after the contract start")
        events = [json.dumps({"row_index": i, "timestamp_ns": r.timestamp_ns, "contact_mask": r.contact_mask,
                              "add_mask": r.add_mask, "remove_mask": r.remove_mask}, sort_keys=True,
                             separators=(",", ":")) + "\n"
                  for i, r in enumerate(records) if r.add_mask or r.remove_mask]
        event_hash = h5.exclusive_write_bytes(ledger, [e.encode("utf-8") for e in events])
        header = h5.CACHE_HEADER_STRUCT.pack(
            h5.CACHE_MAGIC, h5.CACHE_VERSION, h5.CACHE_HEADER_SIZE, h5.CACHE_RECORD_SIZE, len(records),
            source.prefix_end_exclusive, records[0].timestamp_ns, records[-1].timestamp_ns,
            bytes.fromhex(source.raw_sha256), bytes.fromhex(source.prefix_sha256), bytes.fromhex(event_hash))
        cache_hash = h5.exclusive_write_bytes(cache, [header, *(h5.encode_cache_record(r) for r in records)])
        manifest = {
            "schema_version": "hartley.h5.cache_manifest.v1", "cache_sha256": cache_hash,
            "event_ledger_sha256": event_hash, "record_count": len(records),
            "first_timestamp_ns": records[0].timestamp_ns, "last_timestamp_ns": records[-1].timestamp_ns,
            "cache_size_bytes": h5.CACHE_HEADER_SIZE + len(records) * h5.CACHE_RECORD_SIZE,
            "frozen_transition_event_count_excluding_initial_add": sum(
                r.add_mask.bit_count() + r.remove_mask.bit_count() for r in records[1:]),
            "initial_add_event_count": records[0].add_mask.bit_count(),
            "raw_sha256": source.raw_sha256, "prefix_sha256": source.prefix_sha256,
            "start_convention": "CONTRACT_START", "contract_start_unix_ns": start_ns,
            "records_withheld_before_start": int(inventory["record_separator_count"]) - len(records),
            "no_imputation": True, "no_interpolation": True,
        }
    times = np.frombuffer(cache.read_bytes()[h5.CACHE_HEADER_SIZE:], dtype=np.dtype([("t", "<i8"), ("rest", "V184")]))["t"]
    dt = np.diff(times) * 1e-9
    manifest.update(sequence_id=sequence.sequence_id, source_identity={k: str(v) for k, v in asdict(source).items()},
                    dt_seconds={"min": float(dt.min()), "median": float(np.median(dt)), "max": float(dt.max()),
                                "count_gt_0p1": int(np.count_nonzero(dt > 0.1))},
                    gaps_gt_0p1_s=[{"left_rel_s": float(times[i] * 1e-9 - sequence.base_time), "dt_s": float(dt[i])}
                                   for i in np.flatnonzero(dt > 0.1)])
    (provider_dir / "H5_INPUT_CACHE_MANIFEST.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    return manifest


def build_runner(code_root: Path, build_dir: Path) -> dict[str, Any]:
    """Configure/build hartley_h5_runner from the unchanged sources (Release)."""
    source = Path(code_root) / "src/legsa_gins/paper_rebuild/horizontal_literature/hartley_inekf"
    build_dir.mkdir(parents=True, exist_ok=False)
    commands = [["cmake", "-S", str(source), "-B", str(build_dir), "-DCMAKE_BUILD_TYPE=Release"],
                ["cmake", "--build", str(build_dir), "--target", "hartley_h5_runner", "-j", "8"]]
    logs = []
    for command in commands:
        completed = subprocess.run(command, capture_output=True, text=True, check=False)
        logs.append({"argv": command, "returncode": completed.returncode,
                     "stdout_tail": completed.stdout[-4000:], "stderr_tail": completed.stderr[-4000:]})
        if completed.returncode:
            raise HartleyRunError(f"hartley runner build failed: {completed.stderr[-2000:]}")
    runner = build_dir / "hartley_h5_runner"
    return {"runner": str(runner), "runner_sha256": hx02_sequence.sha256_file(runner), "build_logs": logs}


def scoped_manifest(code_root: Path) -> dict[str, Any]:
    files = {rel: {"size": (Path(code_root) / rel).stat().st_size, "sha256": hx02_sequence.sha256_file(Path(code_root) / rel)}
             for rel in SCOPED_SOURCES}
    return {"files": files, "manifest_sha256": hashlib.sha256(
        json.dumps(files, sort_keys=True, separators=(",", ":")).encode()).hexdigest()}


def write_config(run_dir: Path, *, config: str, record_count: int, cache_sha256: str, code_commit: str,
                 scoped: Mapping[str, Any], runner_sha256: str) -> tuple[Path, str]:
    run_id = CONFIG_RUN_IDS[config]
    base = (f"run_id={run_id}\nbackend_id={h5.H5_BACKEND_ID}\nprocess_policy={PROCESS_POLICY[config]}\n"
            f"sigma_fk_m={SIGMA_FK_M:.3f}\nexpected_records={record_count}\ncache_sha256={cache_sha256}\n"
            f"code_commit={code_commit}\ntask_start_head={code_commit}\ntask_start_dirty_or_precommit=false\n"
            f"scoped_source_manifest_sha256={scoped['manifest_sha256']}\nnative_executable_sha256={runner_sha256}\n"
            f"later_final_commit_mapping={code_commit}\n")
    text = base + f"config_hash={hashlib.sha256(base.encode()).hexdigest()}\n"
    run_dir.mkdir(parents=True, exist_ok=False)
    path = run_dir / "NATIVE_CONFIG.cfg"
    h5.exclusive_write_bytes(path, [text.encode()])
    return path, hashlib.sha256(base.encode()).hexdigest()


def run_native(runner: Path, cache: Path, config: Path, run_dir: Path, timeout_seconds: float = 3600.0) -> dict[str, Any]:
    environment = dict(os.environ)
    for key in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
        environment[key] = "1"
    before = hx02_sequence.sha256_file(runner)
    started = time.monotonic()
    completed = subprocess.run([str(runner), str(cache), str(config), str(run_dir)], capture_output=True,
                               text=True, env=environment, check=False, timeout=timeout_seconds)
    runtime = time.monotonic() - started
    if hx02_sequence.sha256_file(runner) != before:
        raise HartleyRunError("native executable changed across launch interval")
    return {"returncode": completed.returncode, "runtime_seconds": runtime,
            "stdout_tail": completed.stdout[-4000:], "stderr": completed.stderr}


def divergence_gate(nav_csv: Path) -> dict[str, Any]:
    """Registered divergence bounds on the local Hartley state (gauge frame, first row origin)."""
    data = np.genfromtxt(nav_csv, delimiter=",", names=True, dtype=None, encoding="utf-8")
    if data.size == 0:
        return {"passed": False, "classification": "NO_OUTPUT", "row_count": 0}
    position = np.column_stack([data["px"], data["py"], data["pz"]]).astype(float)
    velocity = np.column_stack([data["vx"], data["vy"], data["vz"]]).astype(float)
    finite = np.isfinite(position).all(axis=1) & np.isfinite(velocity).all(axis=1)
    displacement = np.linalg.norm(position - position[0], axis=1)
    speed = np.linalg.norm(velocity, axis=1)
    height = np.abs(position[:, 2] - position[0, 2])
    violation = ~finite | (displacement > DIVERGENCE_BOUNDS["position_displacement_m"]) | (
        speed > DIVERGENCE_BOUNDS["speed_mps"]) | (height > DIVERGENCE_BOUNDS["height_displacement_m"])
    first = int(np.flatnonzero(violation)[0]) if violation.any() else None
    return {"passed": first is None, "classification": "NONE" if first is None else "ALGORITHM_FAILURE_DIVERGED",
            "row_count": int(data.size), "bounds": DIVERGENCE_BOUNDS,
            "maxima": {"position_displacement_m": float(np.nanmax(displacement)), "speed_mps": float(np.nanmax(speed)),
                       "height_displacement_m": float(np.nanmax(height))},
            "first_violation_row": first,
            "first_violation_time_unix_s": None if first is None else float(data["timestamp_ns"][first]) * 1e-9}
