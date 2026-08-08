"""Exact CLEAN1R2R1 offline evaluator over sealed unique outputs."""

from __future__ import annotations

import csv
import gzip
import json
import math
import os
import shutil
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Iterable, Mapping

import numpy as np

from .provider_generator import sha256_file
from .runner import EXPECTED_OUTPUT_ROWS, validate_output_seal
from ..clean2r2a_evaluator import (
    EXACT_EVALUATOR_SHA256, FROZEN_BASE_TIME, FROZEN_TRACE_SHA256,
    _audit_evaluator_file_opens, _crosscheck,
)
from ..evidence import parse_strace_openat_paths


class CanonicalEvaluationError(RuntimeError):
    pass


def _seal_gate(seal_root: Path) -> dict[str, Any]:
    manifest = seal_root / "OUTPUT_HASH_MANIFEST.csv"; journal = seal_root / "OUTPUT_SEAL_JOURNAL.json"
    if not manifest.is_file() or not journal.is_file():
        raise CanonicalEvaluationError("output seal is incomplete before trace open")
    payload = json.loads(journal.read_text(encoding="utf-8"))
    if payload.get("sealed_before_offline_trace") is not True or payload.get("trace_open_count_before_seal") != 0:
        raise CanonicalEvaluationError("trace embargo did not close before evaluation")
    with manifest.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle); rows = list(reader)
    required = {"run_id", "run_root", "relative_path", "size_bytes", "sha256", "terminal_status"}
    if not required.issubset(reader.fieldnames or ()) or not rows:
        raise CanonicalEvaluationError("output seal lacks mandatory run_root/size/hash closure")
    run_files: dict[str, dict[str, dict[str, Any]]] = {}
    for row in rows:
        root = Path(row["run_root"]).resolve(strict=True)
        relative = Path(row["relative_path"])
        if relative.is_absolute() or ".." in relative.parts:
            raise CanonicalEvaluationError("unsafe sealed output path")
        path = root / relative
        if (not path.is_file() or path.stat().st_size != int(row["size_bytes"]) or
                sha256_file(path) != row["sha256"]):
            raise CanonicalEvaluationError("sealed output hash mismatch")
        if row["relative_path"] in {"KF_GINS_Navresult.nav", "KF_GINS_STD.txt"}:
            run_files.setdefault(str(row["run_id"]), {})[str(row["relative_path"])] = {
                "size_bytes": int(row["size_bytes"]), "sha256": str(row["sha256"]),
            }
    return {"manifest_sha256": sha256_file(manifest), "journal_sha256": sha256_file(journal),
            "row_count": len(rows), "run_files": run_files}


def _series_metrics(error_series: Path, expected_rows: int) -> dict[str, Any]:
    """Derive the complete result row from matched error-series bytes."""

    with error_series.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle); rows = list(reader)
    required = {
        "time", "err_n_m", "err_e_m", "err_u_m", "horizontal_err_m", "position_3d_err_m",
        "roll_err_deg", "pitch_err_deg", "yaw_err_deg",
    }
    if not rows or not required.issubset(reader.fieldnames or ()):
        raise CanonicalEvaluationError("error-series schema/row closure failed")
    columns = {
        "horizontal": "horizontal_err_m", "up": "err_u_m", "position_3d": "position_3d_err_m",
        "roll": "roll_err_deg", "pitch": "pitch_err_deg", "yaw": "yaw_err_deg",
    }
    output: dict[str, Any] = {}
    for prefix, column in columns.items():
        signed = [float(row[column]) for row in rows]
        if any(not math.isfinite(value) for value in signed):
            raise CanonicalEvaluationError(f"non-finite matched error column: {column}")
        absolute = np.abs(np.asarray(signed, dtype=float)); count = len(absolute)
        unit = "deg" if prefix in {"roll", "pitch", "yaw"} else "m"
        output.update({
            f"{prefix}_rmse_{unit}": float(np.sqrt(np.mean(np.square(signed)))),
            f"{prefix}_mae_{unit}": float(np.mean(absolute)),
            f"{prefix}_median_{unit}": float(np.quantile(absolute, .5, method="linear")),
            f"{prefix}_p95_{unit}": float(np.quantile(absolute, .95, method="linear")),
            f"{prefix}_max_{unit}": float(np.max(absolute)),
            f"{prefix}_final_{unit}": float(absolute[-1]),
        })
    matched = len(rows); unmatched = max(0, int(expected_rows) - matched)
    output.update({
        "matched_epoch_count": matched, "unmatched_epoch_count": unmatched,
        "expected_output_epoch_count": int(expected_rows),
        "coverage": matched / int(expected_rows) if expected_rows else 0.0,
        "time_start_s": float(rows[0]["time"]), "time_end_s": float(rows[-1]["time"]),
        "evaluable": True, "finite": True,
    })
    return output


def _deterministic_gzip(source: Path, destination: Path) -> None:
    with source.open("rb") as input_handle, destination.open("xb") as output_handle:
        with gzip.GzipFile(filename="", mode="wb", fileobj=output_handle, compresslevel=9, mtime=0) as compressor:
            shutil.copyfileobj(input_handle, compressor)


def _summary_overlap_crosscheck(metrics: Mapping[str, Any], summary: Mapping[str, Any]) -> None:
    mapping = {
        "horizontal_rmse_m": ("position", "horizontal_rmse_m"),
        "horizontal_mae_m": ("position", "horizontal_mae_m"),
        "horizontal_p95_m": ("position", "horizontal_p95_m"),
        "horizontal_max_m": ("position", "horizontal_max_m"),
        "up_rmse_m": ("position", "up_rmse_m"),
        "up_p95_m": ("position", "vertical_p95_m"),
        "up_max_m": ("position", "vertical_max_m"),
        "position_3d_rmse_m": ("position", "position_3d_rmse_m"),
        **{f"{axis}_{stat}_deg": ("attitude", f"{axis}_{stat}_deg")
           for axis in ("roll", "pitch", "yaw") for stat in ("rmse", "p95", "max")},
    }
    for metric, (section, field) in mapping.items():
        if not math.isclose(float(metrics[metric]), float(summary[section][field]), rel_tol=0, abs_tol=1e-10):
            raise CanonicalEvaluationError(f"error-series/summary overlap mismatch: {metric}")


def _lightweight_seal_identity(seal_root: Path, expected: Mapping[str, Any]) -> dict[str, Any]:
    """Re-bind immutable seal sidecars immediately before each offline trace open."""

    current = {
        "manifest_sha256": sha256_file(seal_root / "OUTPUT_HASH_MANIFEST.csv"),
        "journal_sha256": sha256_file(seal_root / "OUTPUT_SEAL_JOURNAL.json"),
    }
    if any(current[key] != expected[key] for key in current):
        raise CanonicalEvaluationError("output seal identity changed before trace open")
    return current


def _revalidate_run_inputs(runtime: Path, run_id: str, seal: Mapping[str, Any]) -> None:
    expected = seal.get("run_files", {}).get(run_id)
    if not isinstance(expected, Mapping) or set(expected) != {"KF_GINS_Navresult.nav", "KF_GINS_STD.txt"}:
        raise CanonicalEvaluationError(f"sealed NAV/STD identity missing: {run_id}")
    for name, identity in expected.items():
        path = runtime / name
        if (not path.is_file() or path.stat().st_size != int(identity["size_bytes"])
                or sha256_file(path) != identity["sha256"]):
            raise CanonicalEvaluationError(f"sealed runtime input changed before trace open: {run_id}:{name}")


def _load_completed_evaluation(output: Path, *, run_id: str,
                               seal: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any] | None]:
    result_path = output / "CANONICAL541_EVALUATION_RESULT.json"
    manifest_path = output / "evaluator_manifest.json"
    complete_path = output / "EVALUATION_COMPLETE.json"
    if not result_path.is_file() or not manifest_path.is_file() or not complete_path.is_file():
        raise CanonicalEvaluationError(f"partial evaluation output exists: {run_id}")
    complete = json.loads(complete_path.read_text(encoding="utf-8"))
    if (complete.get("run_id") != run_id or complete.get("result_sha256") != sha256_file(result_path)
            or complete.get("evaluator_manifest_sha256") != sha256_file(manifest_path)
            or complete.get("passed") is not True):
        raise CanonicalEvaluationError(f"completed evaluation sidecar drift: {run_id}")
    result = json.loads(result_path.read_text(encoding="utf-8"))
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if (result.get("run_id") != run_id or manifest.get("run_id") != run_id
            or manifest.get("output_seal_manifest_sha256") != seal["manifest_sha256"]
            or manifest.get("seal_revalidated_before_open") is not True
            or manifest.get("exact_evaluator_sha256") != EXACT_EVALUATOR_SHA256
            or manifest.get("trace_sha256") != FROZEN_TRACE_SHA256):
        raise CanonicalEvaluationError(f"completed evaluation identity drift: {run_id}")
    artifacts = manifest.get("artifact_hashes")
    if not isinstance(artifacts, Mapping) or not artifacts:
        raise CanonicalEvaluationError(f"completed evaluation artifact closure missing: {run_id}")
    for relative, digest in artifacts.items():
        path = output / str(relative)
        if not path.is_file() or sha256_file(path) != digest:
            raise CanonicalEvaluationError(f"completed evaluation artifact drift: {run_id}:{relative}")
    metrics = result.get("metrics")
    if not isinstance(metrics, dict):
        raise CanonicalEvaluationError(f"evaluation result metrics missing: {run_id}")
    crosscheck = result.get("crosscheck")
    return metrics, crosscheck if isinstance(crosscheck, dict) else None


def evaluate_unique_outputs(
    *, unique_runs: Iterable[Mapping[str, Any]], seal_root: str | Path,
    trace_path: str | Path, exact_evaluator: str | Path, evaluation_root: str | Path,
    raw_root: str | Path,
    timeout_seconds: int = 900, jobs: int = 8,
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    if not 1 <= jobs <= 16:
        raise CanonicalEvaluationError("evaluation jobs must be 1..16")
    seal_path = Path(seal_root).resolve(strict=True)
    validate_output_seal(seal_path, raw_root=raw_root)
    seal = _seal_gate(seal_path)
    trace = Path(trace_path).resolve(strict=True); evaluator = Path(exact_evaluator).resolve(strict=True)
    raw = Path(raw_root).resolve(strict=True)
    if sha256_file(trace) != FROZEN_TRACE_SHA256 or sha256_file(evaluator) != EXACT_EVALUATOR_SHA256:
        raise CanonicalEvaluationError("trace/evaluator identity differs from CLEAN1R2R1")
    destination = Path(evaluation_root)
    if destination.exists():
        if not destination.is_dir():
            raise CanonicalEvaluationError("evaluation root is not a directory")
    else:
        destination.mkdir(parents=True, exist_ok=False)
    strace = shutil.which("strace")
    if not strace: raise CanonicalEvaluationError("strace is required for offline trace proof")
    rows = tuple(dict(row) for row in unique_runs)
    if len({str(row["run_id"]) for row in rows}) != len(rows):
        raise CanonicalEvaluationError("duplicate unique run_id in evaluator queue")
    attempts_root = destination / ".attempts"; attempts_root.mkdir(exist_ok=True)

    def evaluate_one(row: Mapping[str, Any]) -> tuple[str, dict[str, Any], dict[str, Any] | None]:
        run_id = str(row["run_id"]); runtime = Path(row["output_root"]).resolve(strict=True)
        output = destination / run_id
        if output.is_dir():
            metrics, crosscheck = _load_completed_evaluation(output, run_id=run_id, seal=seal)
            return run_id, metrics, crosscheck
        attempt = attempts_root / run_id
        if attempt.exists():
            raise CanonicalEvaluationError(f"partial evaluator attempt preserved: {run_id}")
        attempt.mkdir(parents=False, exist_ok=False)
        proof = json.loads((runtime / "CANONICAL541_EXECUTION_PROOF.json").read_text(encoding="utf-8"))
        if proof["terminal_status"] == "COMPLETED_ALGORITHM_FAILURE_WITH_PROOF":
            partial_rows = int(proof.get("structure", {}).get("nav", {}).get("rows", 0))
            metrics = {"evaluable": False, "failure_type": proof["failure_type"], "finite": proof["finite"],
                       "matched_epoch_count": 0, "unmatched_epoch_count": EXPECTED_OUTPUT_ROWS,
                       "expected_output_epoch_count": EXPECTED_OUTPUT_ROWS,
                       "partial_output_epoch_count": partial_rows, "coverage": 0.0}
            (attempt / "summary.json").write_text(json.dumps(metrics, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            (attempt / "coverage.json").write_text(json.dumps({
                "matched_epoch_count": 0, "unmatched_epoch_count": EXPECTED_OUTPUT_ROWS,
                "expected_output_epoch_count": EXPECTED_OUTPUT_ROWS,
                "partial_output_epoch_count": partial_rows,
                "coverage": 0.0, "evaluable": False,
            }, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            failure_artifacts = {
                name: sha256_file(attempt / name) for name in ("summary.json", "coverage.json")
            }
            manifest = {
                "run_id": run_id, "output_seal_manifest_sha256": seal["manifest_sha256"],
                "seal_revalidated_before_open": True, "trace_opened_after_seal": False,
                "trace_used_online": False, "algorithm_failure_preserved": True,
                "exact_evaluator_sha256": EXACT_EVALUATOR_SHA256,
                "trace_sha256": FROZEN_TRACE_SHA256, "artifact_hashes": failure_artifacts,
            }
            (attempt / "evaluator_manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            (attempt / "CANONICAL541_EVALUATION_RESULT.json").write_text(json.dumps({
                "run_id": run_id, "metrics": metrics, "crosscheck": None,
            }, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            (attempt / "EVALUATION_COMPLETE.json").write_text(json.dumps({
                "run_id": run_id,
                "result_sha256": sha256_file(attempt / "CANONICAL541_EVALUATION_RESULT.json"),
                "evaluator_manifest_sha256": sha256_file(attempt / "evaluator_manifest.json"),
                "passed": True,
            }, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            os.replace(attempt, output)
            return run_id, metrics, None
        # 全量 seal 只在批次前后验证；每次 trace open 前重新绑定两个 immutable sidecar。
        _lightweight_seal_identity(seal_path, seal)
        _revalidate_run_inputs(runtime, run_id, seal)
        seal_validation_completed_ns = time.time_ns()
        trace_log = attempt / "EVALUATOR_FILE_OPEN_TRACE.raw"
        command = [sys.executable, str(evaluator), "--trace", str(trace),
                   "--nav", str(runtime / "KF_GINS_Navresult.nav"),
                   "--std", str(runtime / "KF_GINS_STD.txt"), "--outdir", str(attempt),
                   "--base_time", str(FROZEN_BASE_TIME), "--yaw_truth_mode", "enu"]
        evaluator_started_ns = time.time_ns()
        completed = subprocess.run([strace, "-f", "-qq", "-yy", "-s", "4096", "-e", "trace=openat", "-o", str(trace_log), *command],
                                   cwd=destination, capture_output=True, text=True,
                                   timeout=timeout_seconds, start_new_session=True, check=False)
        (attempt / "evaluator.stdout.txt").write_text(completed.stdout, encoding="utf-8")
        (attempt / "evaluator.stderr.txt").write_text(completed.stderr, encoding="utf-8")
        summary_path = attempt / "summary.json"; errors = attempt / "error_series.csv"
        if completed.returncode or not summary_path.is_file() or not errors.is_file():
            raise CanonicalEvaluationError(f"exact evaluator failed: {run_id}")
        summary = json.loads(summary_path.read_text(encoding="utf-8")); crosscheck = _crosscheck(errors, summary)
        if not crosscheck["passed"]: raise CanonicalEvaluationError(f"aggregate crosscheck failed: {run_id}")
        flat = _series_metrics(errors, int(proof["structure"]["nav"]["rows"]))
        _summary_overlap_crosscheck(flat, summary)
        opened = parse_strace_openat_paths(trace_log, cwd=destination)
        audit, ledger_rows = _audit_evaluator_file_opens(
            configuration_id=run_id, opened_paths=opened, trace=trace,
            nav=(runtime/"KF_GINS_Navresult.nav").resolve(strict=True),
            std=(runtime/"KF_GINS_STD.txt").resolve(strict=True), evaluator=evaluator,
            raw_root=raw, runtime_root=runtime, strace_sha256=sha256_file(trace_log),
            output_seal_manifest_sha256=seal["manifest_sha256"],
            seal_validation_completed_ns=seal_validation_completed_ns,
            evaluator_started_ns=evaluator_started_ns,
        )
        audit["seal_revalidated_before_open"] = True
        (attempt / "EVALUATOR_READ_LEDGER.json").write_text(json.dumps(audit, indent=2, sort_keys=True)+"\n",encoding="utf-8")
        with (attempt/"EVALUATOR_READ_LEDGER.csv").open("x",encoding="utf-8",newline="") as handle:
            writer=csv.DictWriter(handle,fieldnames=list(ledger_rows[0]),lineterminator="\n");writer.writeheader();writer.writerows(ledger_rows)
        _deterministic_gzip(errors, attempt / "error_series.csv.gz")
        errors.unlink()
        flat.update(
            evaluation_hash=sha256_file(summary_path), error_series_hash=sha256_file(attempt / "error_series.csv.gz"),
            exact_evaluator_sha256=EXACT_EVALUATOR_SHA256, trace_sha256=FROZEN_TRACE_SHA256,
        )
        (attempt / "coverage.json").write_text(json.dumps({
            key: flat[key] for key in (
                "matched_epoch_count", "unmatched_epoch_count", "expected_output_epoch_count",
                "coverage", "time_start_s", "time_end_s", "evaluable", "finite",
            )
        }, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        artifact_names = (
            "summary.json", "coverage.json", "error_series.csv.gz",
            "EVALUATOR_READ_LEDGER.json", "EVALUATOR_READ_LEDGER.csv",
            "EVALUATOR_FILE_OPEN_TRACE.raw", "evaluator.stdout.txt", "evaluator.stderr.txt",
        )
        (attempt / "evaluator_manifest.json").write_text(json.dumps({
            "run_id": run_id, "output_seal_manifest_sha256": seal["manifest_sha256"],
            "seal_revalidated_before_open": True,
            "trace_opened_after_seal": True, "trace_used_online": False,
            "evaluator_read_ledger_sha256": sha256_file(attempt / "EVALUATOR_READ_LEDGER.json"),
            "exact_evaluator_sha256": EXACT_EVALUATOR_SHA256, "trace_sha256": FROZEN_TRACE_SHA256,
            "artifact_hashes": {name: sha256_file(attempt / name) for name in artifact_names},
            "time_search": False, "sign_axis_search": False, "alignment": False,
            "output_correction": False, "epoch_deletion": False,
        }, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        (attempt / "CANONICAL541_EVALUATION_RESULT.json").write_text(json.dumps({
            "run_id": run_id, "metrics": flat, "crosscheck": crosscheck,
        }, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        (attempt / "EVALUATION_COMPLETE.json").write_text(json.dumps({
            "run_id": run_id,
            "result_sha256": sha256_file(attempt / "CANONICAL541_EVALUATION_RESULT.json"),
            "evaluator_manifest_sha256": sha256_file(attempt / "evaluator_manifest.json"),
            "passed": True,
        }, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        os.replace(attempt, output)
        return run_id, flat, crosscheck

    results: dict[str, dict[str, Any]] = {}; crosschecks: dict[str, Any] = {}
    failures: list[BaseException] = []
    with ThreadPoolExecutor(max_workers=jobs) as pool:
        futures = {pool.submit(evaluate_one, row): str(row["run_id"]) for row in rows}
        for future in as_completed(futures):
            try:
                run_id, metrics, crosscheck = future.result(); results[run_id] = metrics
                if crosscheck is not None: crosschecks[run_id] = crosscheck
            except BaseException as exc:
                failures.append(exc)
    if failures:
        raise failures[0]
    validate_output_seal(seal_path, raw_root=raw_root)
    _lightweight_seal_identity(seal_path, seal)
    aggregate = {"unique_output_count": len(results), "evaluable_count": sum(bool(row["evaluable"]) for row in results.values()),
                 "crosschecks": crosschecks, "all_outputs_sealed_before_trace": True,
                 "trace_offline_only": True, "seal_revalidated_after_all_evaluations": True,
                 "evaluation_jobs": jobs,
                 "crosscheck_count": len(crosschecks),
                 "passed": (
                     len(results) == len(rows)
                     and len(crosschecks) == sum(bool(row["evaluable"]) for row in results.values())
                     and all(row["passed"] for row in crosschecks.values())
                 )}
    (destination / "AGGREGATE_CROSSCHECK.json").write_text(json.dumps(aggregate, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return results, aggregate


def resolve_logical_results(logical_rows: Iterable[Mapping[str, Any]],
                            evaluations: Mapping[str, Mapping[str, Any]]) -> list[dict[str, Any]]:
    output = []
    for source in logical_rows:
        row = dict(source); evaluation = evaluations[str(row["run_id"])]
        row.update(evaluation)
        row["terminal_status"] = "COMPLETED_EVALUABLE" if evaluation["evaluable"] else "COMPLETED_ALGORITHM_FAILURE_WITH_PROOF"
        output.append(row)
    if len(output) != 7033:
        raise CanonicalEvaluationError("logical result count is not 7033")
    return output
