"""Future H-EXT offline evaluation adapter; H-EXT-01 does not call it.

Reference payload access belongs solely to the frozen evaluator child. Request
construction uses SequencePaths metadata and never opens or hashes the trace.
"""
from __future__ import annotations

import gzip
import json
import math
import os
from pathlib import Path
import re
import shutil
import sys
import time
from typing import Any, Mapping

import numpy as np

from ..canonical541 import offline_eval_aggregate as canonical
from ..clean5_parity.evaluation import body_frame_bias, transform_nav, write_transformed_nav
from ..clean5_parity_p04.evaluation import metrics as window_metrics
from ..clean5_sequence.evaluation_process import EVALUATOR_SHA256, write_json
from ..clean5_sequence.io_audit import audited_open_records, write_scope_audit
from ..evidence import STRACE_OPENAT_RE
from ..manifest import sha256_file
from ..subprocess_guard import run_process_group

STD_POLICY = "OMITTED_AS_FROZEN_EXTERNAL_CONTRACT"
SELECTED_COLUMNS = {
    "time": "time", "lat": "lat", "lon": "lon", "height": "height",
    "roll": "roll", "pitch": "pitch", "yaw": "yaw",
}


def _window(sequence) -> tuple[float, float]:
    start, end = map(float, sequence.window)
    if not math.isfinite(start) or not math.isfinite(end) or start >= end:
        raise ValueError("Invalid frozen sequence window")
    if not math.isfinite(float(sequence.base_time)):
        raise ValueError("Invalid frozen sequence base_time")
    return start, end


def evaluator_argv(*, sequence, evaluator: Path, nav: Path, outdir: Path) -> list[str]:
    """Frozen external argv: sequence trace/base_time, ENU truth, omitted STD."""
    _window(sequence)
    return [
        sys.executable, str(evaluator), "--trace", str(sequence.trace),
        "--nav", str(nav), "--outdir", str(outdir),
        "--base_time", str(sequence.base_time), "--yaw_truth_mode", "enu",
    ]


def capture_config(*, sequence, evaluator: Path, outdir: Path) -> dict[str, Any]:
    """Metadata only; the child observer hashes its sole trace read handle."""
    digest = str(sequence.trace_sha256)
    if re.fullmatch(r"[0-9a-f]{64}", digest) is None:
        raise ValueError("Invalid declared trace SHA-256")
    return {
        "evaluator": str(evaluator), "evaluator_sha256": EVALUATOR_SHA256,
        "trace": str(sequence.trace), "trace_sha256": digest,
        "window": list(_window(sequence)), "outdir": str(outdir),
        "STD": STD_POLICY,
    }


def prepare_evaluator_nav(*, sequence, nav: Path, outdir: Path, version: str):
    """Keep v2 input bytes; apply the frozen physical-point transform for v3."""
    if version not in ("v2", "v3"):
        raise ValueError("Evaluation version must be v2 or v3")
    nav = Path(nav)
    original = canonical._read_numeric_table(nav).to_numpy(float)
    if original.ndim != 2 or original.shape[1] != 11 or not np.isfinite(original).all():
        raise ValueError("Expected finite 11-column external NAV")
    start, end = _window(sequence)
    if not len(original) or np.any(np.diff(original[:, 1]) <= 0):
        raise ValueError("External NAV must be nonempty and chronological")
    if np.any((original[:, 1] < start) | (original[:, 1] > end)):
        raise ValueError("External NAV was not clipped to the frozen sequence window")
    if version == "v2":
        return nav, original, {"evaluator_contract": "evaluator_contract_v2", "STD": STD_POLICY}
    target_root = Path(outdir)
    target_root.mkdir(parents=True, exist_ok=False)
    target = target_root / "EVALUATOR_INPUT.nav"
    baseline = float(sequence.baseline_median_m)
    write_transformed_nav(nav, target, transform_nav(original, baseline))
    manifest = {
        "evaluator_contract": "evaluator_contract_v3", "input_sha256": sha256_file(nav),
        "output_sha256": sha256_file(target), "baseline_median_m": baseline,
        "lever_frd_m": [0.03, 0.03 - 0.5 * baseline, -0.30],
        "attitude_columns_zero_based": [8, 9, 10], "fit_used": False,
        "further_correction_used": False, "STD": STD_POLICY,
        "uncertainty_status": "UNAVAILABLE_FULL_COVARIANCE_NOT_TRANSPORTED",
    }
    write_json(target_root / "TRANSFORM_MANIFEST.json", manifest)
    return target, original, manifest


def metrics(errors, nav, identity: Mapping[str, Any], *, window, reference_count=None):
    """Use the existing sequence-window metric implementation, never BY2 limits."""
    start, end = map(float, window)
    times = np.asarray(errors["time"], float)
    if not math.isfinite(start) or not math.isfinite(end) or start >= end:
        raise ValueError("Invalid evaluation window")
    if np.any((times < start) | (times > end)):
        raise ValueError("Evaluator errors outside the declared window; no epoch deletion")
    row = window_metrics(errors, nav, identity, (start, end), reference_count)
    row.update(STD=STD_POLICY, uncertainty_status="UNAVAILABLE_NO_EXTERNAL_STD")
    if str(identity.get("evaluator_contract", "")).endswith("v3"):
        row["uncertainty_status"] = "UNAVAILABLE_FULL_COVARIANCE_NOT_TRANSPORTED"
    return row


def _capture_identity_failures(capture, sequence, trace_records):
    """D12 separates identity/access failures from a reported false consistency gate."""
    failures = []
    if (capture.get("trace_sha256") != sequence.trace_sha256
            or capture.get("trace_handle_hash_count") != 1
            or capture.get("selected_columns") != SELECTED_COLUMNS
            or any(row["pid"] != capture.get("pid") for row in trace_records)):
        failures.append("reference hash/process/column observation mismatch")
    if not isinstance(capture.get("consistency", {}).get("passed"), bool):
        failures.append("consistency observation absent or malformed")
    return failures


def _evaluate_process(*, sequence, evaluator: Path, nav: Path, outdir: Path,
                      allow_consistency_failure: bool = False):
    """Frozen child convention, adapted from clean5_sequence.evaluation_process."""
    evaluator, nav, outdir = map(Path, (evaluator, nav, outdir))
    trace, code_root = Path(sequence.trace), Path(sequence.code_root)
    if evaluator.is_symlink() or sha256_file(evaluator) != EVALUATOR_SHA256:
        raise RuntimeError("Archived evaluator identity mismatch")
    if any(path.is_symlink() or not path.is_file() for path in (trace, nav)):
        raise RuntimeError("Evaluator input missing or symlink")
    outdir.mkdir(parents=True, exist_ok=False)
    config_path = outdir / "CAPTURE_CONFIG.json"
    write_json(config_path, capture_config(sequence=sequence, evaluator=evaluator, outdir=outdir))
    environment = {
        "PYTHONDONTWRITEBYTECODE": "1", "GIT_OPTIONAL_LOCKS": "0",
        "OMP_NUM_THREADS": "1", "MKL_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1",
        "NUMEXPR_NUM_THREADS": "1", "MPLCONFIGDIR": str(outdir / ".matplotlib"),
        "XDG_CACHE_HOME": str(outdir / ".cache"), "MPLBACKEND": "Agg",
        "PYTHONPATH": os.pathsep.join((str(code_root / "scripts/paper_rebuild/clean5_evaluator_observer"), str(code_root / "src"))),
        "CLEAN5_EVALUATOR_CAPTURE_CONFIG": str(config_path),
    }
    argv = evaluator_argv(sequence=sequence, evaluator=evaluator, nav=nav, outdir=outdir)
    log = outdir / "EVALUATOR_OPENAT.strace"
    command = ["env", *(f"{key}={value}" for key, value in environment.items()),
               "strace", "-f", "-yy", "-s", "4096", "-e", "trace=openat,execve", "-o", str(log), *argv]
    started = time.monotonic()
    completed = run_process_group(command, cwd=code_root, timeout_seconds=1800,
        timeout_message="H-EXT evaluator timeout; no retry", launch_failure_message="H-EXT evaluator launch failed")
    runtime = time.monotonic() - started
    (outdir / "evaluator_stdout.log").write_text(completed.stdout, encoding="utf-8")
    (outdir / "evaluator_stderr.log").write_text(completed.stderr, encoding="utf-8")
    records = audited_open_records(log, code_root)
    lines = [line for line in log.read_text().splitlines() if STRACE_OPENAT_RE.search(line)]
    for record, line in zip(records, lines):
        match = re.match(r"(?:\[pid\s+)?(\d+)", line)
        if not match:
            raise RuntimeError("strace open lacks process identity")
        record["pid"] = int(match[1])
    trace_records = [row for row in records if Path(row["path"]) == trace]
    raw_records = [row for row in records if Path(sequence.raw_root) in Path(row["path"]).parents]
    scope = write_scope_audit(records, raw_root=sequence.raw_root, clean_root=sequence.clean_root, allowed_write_roots=[outdir])
    capture_path = outdir / "EVALUATOR_CAPTURE.json"
    capture = json.loads(capture_path.read_text()) if capture_path.is_file() else {}
    failures = []
    if completed.returncode:
        failures.append(f"evaluator_returncode={completed.returncode}")
    if len(trace_records) != 1 or any(row["return_code"] < 0 or "O_RDONLY" not in row["flags"] for row in trace_records):
        failures.append("reference must be opened exactly once, successfully and read-only")
    if any(Path(row["path"]) != trace for row in raw_records):
        failures.append("unexpected raw input opened")
    if any(row["path"].endswith((".bag", ".fpl")) for row in records):
        failures.append("bag/fpl open")
    if not scope["pass"]:
        failures.append("write scope violation")
    failures.extend(_capture_identity_failures(capture, sequence, trace_records))
    technical_failures = list(failures)
    consistency_passed = capture.get("consistency", {}).get("passed") is True
    if not consistency_passed:
        failures.append("reference consistency observation mismatch")
    audit = {
        "passed": not failures, "failures": failures, "trace_open_count": len(trace_records),
        "technical_passed": not technical_failures, "technical_failures": technical_failures,
        "consistency_passed": consistency_passed,
        "trace_open_records": trace_records, "raw_open_count": len(raw_records),
        "write_scope": scope, "strace_sha256": sha256_file(log), "exit_code": completed.returncode,
        "runtime_seconds": runtime, "evaluator_argv": argv, "environment": environment,
        "STD": STD_POLICY, "trace_read_role": "archived_evaluator_child_only",
    }
    write_json(outdir / "EVALUATOR_STRACE_AUDIT.json", audit)
    if technical_failures or (failures and not allow_consistency_failure):
        raise RuntimeError("; ".join(failures) + "; stderr tail: " + completed.stderr[-2000:])
    for name in ("summary.json", "error_series.csv"):
        if not (outdir / name).is_file():
            raise RuntimeError("Evaluator missing " + name)
    with (outdir / "error_series.csv").open("rb") as source, gzip.open(outdir / "error_series.csv.gz", "wb", compresslevel=6) as target:
        shutil.copyfileobj(source, target)
    return {"audit": audit, "capture": capture, "runtime_seconds": runtime,
            "summary": json.loads((outdir / "summary.json").read_text()), "outdir": str(outdir)}


def evaluate(*, sequence, evaluator: Path, nav: Path, expected_nav_sha256: str,
             outdir: Path, version: str, identity: Mapping[str, Any],
             nav_input_root: Path | None = None,
             consistency_failure_policy: str = "HARD_STOP",
             bounded_gate: Mapping[str, Any] | None = None):
    """Evaluate one sealed NAV; an explicit stage-06 root receives the v3 transform."""
    nav, outdir = Path(nav), Path(outdir)
    if nav.is_symlink() or sha256_file(nav) != expected_nav_sha256:
        raise ValueError("Sealed external NAV identity mismatch")
    if consistency_failure_policy not in ("HARD_STOP", "D12_BOUNDED_UNAVAILABLE"):
        raise ValueError("Unknown evaluator consistency-failure policy")
    soft = consistency_failure_policy == "D12_BOUNDED_UNAVAILABLE"
    if soft and (bounded_gate is None or bounded_gate.get("passed") is not True
                 or bounded_gate.get("sealed_evaluator_nav_sha256") != expected_nav_sha256):
        raise ValueError("D12 continuation requires a passed identity-bound native D8 gate")
    allowed = (Path(sequence.output_root).resolve(), Path(sequence.hext_scratch).resolve())
    if not any(root in outdir.resolve().parents for root in allowed):
        raise ValueError("Evaluation output must be below an H-EXT output root")
    transform_root = Path(nav_input_root) if nav_input_root is not None else outdir / "NAV_INPUTS"
    if not any(root in transform_root.resolve().parents for root in allowed):
        raise ValueError("Transformed NAV must be below an H-EXT output root")
    outdir.mkdir(parents=True, exist_ok=False)
    actual, original, transform = prepare_evaluator_nav(
        sequence=sequence, nav=nav, outdir=transform_root, version=version)
    process_options = {"allow_consistency_failure": True} if soft else {}
    result = _evaluate_process(sequence=sequence, evaluator=evaluator, nav=actual,
                               outdir=outdir / "EXACT_EVALUATOR_OUTPUT", **process_options)
    evaluation_identity = {
        **identity, "dataset_id": sequence.sequence_id, "evaluator_contract": "evaluator_contract_" + version,
        "evaluator_sha256": EVALUATOR_SHA256, "source_nav_sha256": expected_nav_sha256,
        "evaluator_nav_sha256": sha256_file(actual), "trace_sha256": sequence.trace_sha256,
        "base_time": sequence.base_time, "evaluation_invoked": True, "STD": STD_POLICY,
    }
    if soft and result["capture"]["consistency"]["passed"] is False:
        row = {**evaluation_identity, "status": "UNAVAILABLE_EVALUATION_FAILED",
               "evaluation_status": "UNAVAILABLE_EVALUATION_FAILED",
               "failure_classification": "UNAVAILABLE_EVALUATION_FAILED",
               "reason": "D12: bounded native output; evaluator consistency gate failed; no retry",
               "metrics_admitted": False}
        bias = {**evaluation_identity, "status": "UNAVAILABLE_EVALUATION_FAILED"}
    else:
        errors = canonical._read_error_series(Path(result["outdir"]))
        row = metrics(errors, original, evaluation_identity, window=sequence.window,
                      reference_count=result["capture"].get("reference_epoch_count"))
        bias = {**evaluation_identity, **body_frame_bias(errors, original), "status": "AVAILABLE"}
    row.update(evaluation_runtime_seconds=result["runtime_seconds"], error_series_source=result["outdir"])
    if sha256_file(nav) != expected_nav_sha256:
        raise RuntimeError("External source NAV changed during evaluation")
    if sha256_file(evaluator) != EVALUATOR_SHA256:
        raise RuntimeError("Archived evaluator identity changed during evaluation")
    payload = {"row": row, "body_frame_bias": bias, "audit": result["audit"], "transform": transform}
    write_json(outdir / "EVALUATION_RESULT.json", payload)
    return payload
