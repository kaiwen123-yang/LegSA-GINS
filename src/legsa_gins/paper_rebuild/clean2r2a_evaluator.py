"""Exact same-source offline evaluation for the sealed CLEAN2R2A outputs."""

from __future__ import annotations

import csv
import json
import math
import shutil
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from .clean2r2a_runner import METHOD_ORDER, run_directory, validate_output_seal
from .evidence import BY2_TRACE_RELATIVE_PATH, parse_strace_openat_paths
from .manifest import read_hash_lock, sha256_file, write_json_atomic
from .paths import is_within, load_clean_paths


class Clean2R2AEvaluationError(RuntimeError):
    """Offline evaluation failed after the output-seal gate."""


# 这些身份来自已经闭合的 CLEAN1R2R1 合同；调用者不能用命令行覆盖。
EXACT_EVALUATOR_SHA256 = "aa0492482b6467cdd701bc8882aca11c4170bbe2e7c6bb5f932679dc204978da"
FROZEN_TRACE_SHA256 = "ee3ee42dea3ada196dfdbcc78fd07524f91b4ce4fb94d9d6482a3e7d4b34aa4c"
FROZEN_BASE_TIME = 1772784000.0

EXACT_SUMMARY_FIELDS = {
    "position": {
        "up_rmse_m", "horizontal_rmse_m", "position_3d_rmse_m",
        "horizontal_mae_m", "horizontal_p95_m", "horizontal_max_m",
        "vertical_p95_m", "vertical_max_m",
    },
    "attitude": {
        "roll_rmse_deg", "pitch_rmse_deg", "yaw_rmse_deg",
        "roll_p95_deg", "pitch_p95_deg", "yaw_p95_deg",
        "roll_max_deg", "pitch_max_deg", "yaw_max_deg",
    },
    "meta": {"num_samples", "time_start", "time_end", "duration_sec", "base_time", "yaw_truth_mode"},
}
EXACT_ERROR_COLUMNS = {
    "time", "err_n_m", "err_e_m", "err_u_m", "horizontal_err_m",
    "position_3d_err_m", "roll_err_deg", "pitch_err_deg", "yaw_err_deg",
}
RESULT_FIELDS = (
    "run_order", "configuration_id", "output_epoch_count", "matched_epoch_count",
    "unmatched_epoch_count", "coverage", "horizontal_rmse_m", "up_rmse_m",
    "position_3d_rmse_m", "roll_rmse_deg", "pitch_rmse_deg", "yaw_rmse_deg",
    "horizontal_mae_m", "horizontal_p95_m", "horizontal_max_m", "up_p95_m",
    "up_max_m", "roll_p95_deg", "pitch_p95_deg", "yaw_p95_deg",
    "roll_max_deg", "pitch_max_deg", "yaw_max_deg", "finite_output",
)
COVERAGE_FIELDS = (
    "run_order", "configuration_id", "output_epoch_count", "matched_epoch_count",
    "unmatched_epoch_count", "coverage",
)
LEDGER_FIELDS = (
    "configuration_id", "read_order", "path_alias", "relative_path", "role",
    "sha256", "open_count", "strace_sha256", "output_seal_manifest_sha256",
    "seal_revalidated_before_open",
)


def validate_exact_evaluator_payload(summary: Mapping[str, Any], columns: Iterable[str]) -> None:
    for section, fields in EXACT_SUMMARY_FIELDS.items():
        value = summary.get(section)
        if not isinstance(value, dict) or not fields.issubset(value):
            raise Clean2R2AEvaluationError(f"exact evaluator summary schema drift: {section}")
        for field in fields:
            if field == "yaw_truth_mode":
                continue
            number = value[field]
            if isinstance(number, bool) or not math.isfinite(float(number)):
                raise Clean2R2AEvaluationError(f"exact evaluator returned non-finite {section}.{field}")
    if summary["meta"]["yaw_truth_mode"] != "enu":
        raise Clean2R2AEvaluationError("exact evaluator yaw mode is not frozen ENU conversion")
    if float(summary["meta"]["base_time"]) != FROZEN_BASE_TIME:
        raise Clean2R2AEvaluationError("exact evaluator base time drifted from CLEAN1R2R1")
    if not EXACT_ERROR_COLUMNS.issubset(set(columns)):
        raise Clean2R2AEvaluationError("exact evaluator error-series schema drift")


def _rmse(values: Iterable[float]) -> float:
    rows = list(values)
    return math.sqrt(sum(value * value for value in rows) / len(rows))


def _numeric_row_count(path: Path) -> int:
    count = 0
    for line in path.read_text(encoding="utf-8", errors="strict").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith(("#", "%")):
            continue
        try:
            [float(value) for value in stripped.replace(",", " ").split()]
        except ValueError:
            continue
        count += 1
    return count


def _crosscheck(error_series: Path, summary: dict[str, Any]) -> dict[str, Any]:
    with error_series.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
    if not rows:
        raise Clean2R2AEvaluationError("exact evaluator returned no matched rows")
    validate_exact_evaluator_payload(summary, reader.fieldnames or ())
    mapping = {
        "horizontal_rmse_m": ("position", "horizontal_rmse_m", "horizontal_err_m"),
        "up_rmse_m": ("position", "up_rmse_m", "err_u_m"),
        "position_3d_rmse_m": ("position", "position_3d_rmse_m", "position_3d_err_m"),
        "roll_rmse_deg": ("attitude", "roll_rmse_deg", "roll_err_deg"),
        "pitch_rmse_deg": ("attitude", "pitch_rmse_deg", "pitch_err_deg"),
        "yaw_rmse_deg": ("attitude", "yaw_rmse_deg", "yaw_err_deg"),
    }
    checks: dict[str, Any] = {}
    for name, (section, field, column) in mapping.items():
        computed = _rmse(float(row[column]) for row in rows)
        reported = float(summary[section][field])
        checks[name] = {
            "computed": computed,
            "reported": reported,
            "absolute_difference": abs(computed - reported),
            "passed": abs(computed - reported) <= 1.0e-10,
        }
    return {
        "row_count": len(rows),
        "checks": checks,
        "passed": all(item["passed"] for item in checks.values()),
    }


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise Clean2R2AEvaluationError(f"JSON payload is not a mapping: {path.name}")
    return payload


def _write_csv(path: Path, fields: Sequence[str], rows: Iterable[Mapping[str, Any]]) -> None:
    with path.open("x", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fields))
        writer.writeheader()
        writer.writerows(rows)


def _read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or ()), list(reader)


def _string_rows(rows: Iterable[Mapping[str, Any]]) -> list[dict[str, str]]:
    return [{str(key): str(value) for key, value in row.items()} for row in rows]


def _resolve_frozen_evaluation_inputs(
    *,
    local_config: str | Path,
    exact_evaluator: str | Path,
    stage_root: str | Path | None = None,
) -> dict[str, Path]:
    """Resolve inputs from the local path contract and verify frozen bytes."""

    evaluator = Path(exact_evaluator).expanduser().resolve(strict=True)
    if not evaluator.is_file() or sha256_file(evaluator) != EXACT_EVALUATOR_SHA256:
        raise Clean2R2AEvaluationError("exact evaluator does not match the hard-coded CLEAN1R2R1 SHA256")

    paths = load_clean_paths(local_config)
    raw_root = paths.raw_root.resolve(strict=True)
    trace_lexical = raw_root / BY2_TRACE_RELATIVE_PATH
    cursor = raw_root
    # 原始 reference 路径的任何子组件都不得通过符号链接换源。
    for component in Path(BY2_TRACE_RELATIVE_PATH).parts:
        cursor = cursor / component
        if cursor.is_symlink():
            raise Clean2R2AEvaluationError("same-source trace path crosses a symlink")
    trace = trace_lexical.resolve(strict=True)
    if not trace.is_file() or not is_within(trace, raw_root):
        raise Clean2R2AEvaluationError("same-source trace is not the exact raw-root file")

    lock = read_hash_lock(paths.raw_hash_lock)
    row = lock.get(BY2_TRACE_RELATIVE_PATH)
    if row is None or row.get("sha256") != FROZEN_TRACE_SHA256:
        raise Clean2R2AEvaluationError("raw hash lock does not bind the frozen BY2 trace")
    if int(row.get("size_bytes", "-1")) != trace.stat().st_size:
        raise Clean2R2AEvaluationError("frozen BY2 trace size differs from raw hash lock")
    if sha256_file(trace) != FROZEN_TRACE_SHA256:
        raise Clean2R2AEvaluationError("frozen BY2 trace bytes differ from CLEAN1R2R1")

    runtime_root = paths.runtime_root.resolve(strict=True)
    if stage_root is not None:
        stage = Path(stage_root).expanduser().resolve(strict=True)
        if stage != runtime_root.parent:
            raise Clean2R2AEvaluationError("stage root is not the local config runtime parent")
    return {
        "evaluator": evaluator,
        "trace": trace,
        "raw_root": raw_root,
        "runtime_root": runtime_root,
        "local_config": Path(local_config).expanduser().resolve(strict=True),
    }


def _output_seal_identity(stage: Path) -> dict[str, Any]:
    rows = validate_output_seal(stage)
    seal_root = stage / "07_OUTPUT_SEAL"
    manifest = seal_root / "OUTPUT_HASH_MANIFEST.csv"
    journal = seal_root / "OUTPUT_SEAL_JOURNAL.json"
    return {
        "rows": rows,
        "manifest_sha256": sha256_file(manifest),
        "journal_sha256": sha256_file(journal),
    }


def _result_row(method_id: str, runtime: Path, summary: Mapping[str, Any]) -> dict[str, Any]:
    output_rows = _numeric_row_count(runtime / "KF_GINS_Navresult.nav")
    matched = int(summary["meta"]["num_samples"])
    if output_rows <= 0 or matched < 0 or matched > output_rows:
        raise Clean2R2AEvaluationError(f"invalid output/matched row counts: {method_id}")
    position = summary["position"]
    attitude = summary["attitude"]
    return {
        "run_order": METHOD_ORDER.index(method_id) + 1,
        "configuration_id": method_id,
        "output_epoch_count": output_rows,
        "matched_epoch_count": matched,
        "unmatched_epoch_count": output_rows - matched,
        "coverage": matched / output_rows,
        "horizontal_rmse_m": position["horizontal_rmse_m"],
        "up_rmse_m": position["up_rmse_m"],
        "position_3d_rmse_m": position["position_3d_rmse_m"],
        "roll_rmse_deg": attitude["roll_rmse_deg"],
        "pitch_rmse_deg": attitude["pitch_rmse_deg"],
        "yaw_rmse_deg": attitude["yaw_rmse_deg"],
        "horizontal_mae_m": position["horizontal_mae_m"],
        "horizontal_p95_m": position["horizontal_p95_m"],
        "horizontal_max_m": position["horizontal_max_m"],
        "up_p95_m": position["vertical_p95_m"],
        "up_max_m": position["vertical_max_m"],
        "roll_p95_deg": attitude["roll_p95_deg"],
        "pitch_p95_deg": attitude["pitch_p95_deg"],
        "yaw_p95_deg": attitude["yaw_p95_deg"],
        "roll_max_deg": attitude["roll_max_deg"],
        "pitch_max_deg": attitude["pitch_max_deg"],
        "yaw_max_deg": attitude["yaw_max_deg"],
        "finite_output": True,
    }


def _audit_evaluator_file_opens(
    *,
    configuration_id: str,
    opened_paths: Iterable[Path],
    trace: Path,
    nav: Path,
    std: Path,
    evaluator: Path,
    raw_root: Path,
    runtime_root: Path,
    strace_sha256: str,
    output_seal_manifest_sha256: str,
    seal_validation_completed_ns: int,
    evaluator_started_ns: int,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Prove exact offline reference/NAV/STD opens and reject adjacent raw reads."""

    opened = [Path(path).resolve(strict=False) for path in opened_paths]
    counts = Counter(opened)
    required = (trace, nav, std, evaluator)
    missing = [path.name for path in required if counts[path] <= 0]
    raw_opens = {path for path in opened if is_within(path, raw_root)}
    runtime_opens = {path for path in opened if is_within(path, runtime_root)}
    if missing:
        raise Clean2R2AEvaluationError(
            f"evaluator strace omitted required file(s) for {configuration_id}: {missing}"
        )
    if raw_opens != {trace}:
        raise Clean2R2AEvaluationError(
            f"evaluator opened an unexpected raw-root file for {configuration_id}"
        )
    if runtime_opens != {nav, std}:
        raise Clean2R2AEvaluationError(
            f"evaluator opened an unexpected runtime file for {configuration_id}"
        )
    if evaluator_started_ns < seal_validation_completed_ns:
        raise Clean2R2AEvaluationError("evaluator start preceded output-seal validation")

    specs = (
        ("<RAW_ROOT>", BY2_TRACE_RELATIVE_PATH, "same_source_offline_reference", trace),
        ("<RUNTIME_ROOT>", nav.relative_to(runtime_root).as_posix(), "sealed_nav", nav),
        ("<RUNTIME_ROOT>", std.relative_to(runtime_root).as_posix(), "sealed_std", std),
        ("<EXACT_EVALUATOR>", evaluator.name, "exact_evaluator", evaluator),
    )
    ledger_rows = [
        {
            "configuration_id": configuration_id,
            "read_order": order,
            "path_alias": alias,
            "relative_path": relative,
            "role": role,
            "sha256": sha256_file(path),
            "open_count": counts[path],
            "strace_sha256": strace_sha256,
            "output_seal_manifest_sha256": output_seal_manifest_sha256,
            "seal_revalidated_before_open": True,
        }
        for order, (alias, relative, role, path) in enumerate(specs, start=1)
    ]
    audit = {
        "schema_version": "paper_rebuild.clean2r2a_evaluator_file_open_audit.v2",
        "configuration_id": configuration_id,
        "seal_validation_completed_ns": seal_validation_completed_ns,
        "evaluator_started_ns": evaluator_started_ns,
        "seal_revalidated_before_open": True,
        "output_seal_manifest_sha256": output_seal_manifest_sha256,
        "strace_sha256": strace_sha256,
        "parsed_openat_count": len(opened),
        "required_open_rows": ledger_rows,
        "raw_root_open_aliases": [f"<RAW_ROOT>/{BY2_TRACE_RELATIVE_PATH}"],
        "unexpected_raw_root_open_count": 0,
        "unexpected_runtime_root_open_count": 0,
        "trace_used_online": False,
        "passed": True,
    }
    return audit, ledger_rows


def _assert_persisted_crosscheck(
    persisted: Mapping[str, Any], recomputed: Mapping[str, Any], method_id: str
) -> None:
    """Fail closed when a summary/error-series aggregate has been tampered."""

    if dict(persisted) != dict(recomputed) or recomputed.get("passed") is not True:
        raise Clean2R2AEvaluationError(f"persisted aggregate crosscheck mismatch: {method_id}")


def _expected_manifest(
    *,
    inputs: Mapping[str, Path],
    seal: Mapping[str, Any],
    destination: Path,
    audit_hashes: Mapping[str, str],
) -> dict[str, Any]:
    per_run_summary_hashes = {
        method_id: sha256_file(destination / run_directory(method_id) / "summary.json")
        for method_id in METHOD_ORDER
    }
    per_run_error_series_hashes = {
        method_id: sha256_file(destination / run_directory(method_id) / "error_series.csv")
        for method_id in METHOD_ORDER
    }
    per_run_strace_hashes = {
        method_id: sha256_file(
            destination / run_directory(method_id) / "EVALUATOR_FILE_OPEN_TRACE.raw"
        )
        for method_id in METHOD_ORDER
    }
    return {
        "schema_version": "paper_rebuild.clean2r2a_offline_evaluation.v2",
        "exact_evaluator_sha256": EXACT_EVALUATOR_SHA256,
        "trace_relative_path": BY2_TRACE_RELATIVE_PATH,
        "trace_sha256": FROZEN_TRACE_SHA256,
        "trace_raw_lock_sha256": FROZEN_TRACE_SHA256,
        "base_time": FROZEN_BASE_TIME,
        "yaw_reference_conversion": "wrap360(90-yaw_trace_enu)",
        "sealed_output_file_count": len(seal["rows"]),
        "output_seal_manifest_sha256": seal["manifest_sha256"],
        "output_seal_journal_sha256": seal["journal_sha256"],
        "evaluated_unique_outputs": len(METHOD_ORDER),
        "method_order": list(METHOD_ORDER),
        "local_config_sha256": sha256_file(inputs["local_config"]),
        "factorial_results_sha256": sha256_file(destination / "CLEAN2R2A_FACTORIAL_RESULTS.csv"),
        "match_coverage_sha256": sha256_file(destination / "CLEAN2R2A_MATCH_COVERAGE.csv"),
        "aggregate_crosscheck_sha256": sha256_file(
            destination / "CLEAN2R2A_AGGREGATE_CROSSCHECK.json"
        ),
        "evaluator_read_ledger_sha256": sha256_file(destination / "EVALUATOR_READ_LEDGER.csv"),
        "per_run_summary_sha256": per_run_summary_hashes,
        "per_run_error_series_sha256": per_run_error_series_hashes,
        "per_run_strace_sha256": per_run_strace_hashes,
        "per_run_file_open_audit_sha256": dict(audit_hashes),
        "trace_opened_after_per_run_seal_validation": True,
        "trace_used_online": False,
        "time_search": False,
        "sign_axis_search": False,
        "alignment": False,
        "output_correction": False,
        "epoch_deletion": False,
        "terminal_status": "PASS_CLEAN2R2A_OFFLINE_EVALUATION",
    }


def revalidate_offline_evaluation(
    *,
    stage_root: str | Path,
    local_config: str | Path,
    exact_evaluator: str | Path,
    write_report: bool = False,
) -> dict[str, Any]:
    """Revalidate the terminal evaluation without executing the evaluator again."""

    stage = Path(stage_root).expanduser().resolve(strict=True)
    # sha256_file(trace) 也会打开 reference，因此必须先验证 output seal。
    seal = _output_seal_identity(stage)
    inputs = _resolve_frozen_evaluation_inputs(
        local_config=local_config, exact_evaluator=exact_evaluator, stage_root=stage
    )
    seal_after_identity = _output_seal_identity(stage)
    if (
        seal_after_identity["manifest_sha256"] != seal["manifest_sha256"]
        or seal_after_identity["journal_sha256"] != seal["journal_sha256"]
    ):
        raise Clean2R2AEvaluationError("output seal changed during frozen input validation")
    destination = stage / "08_OFFLINE_EVALUATION"
    if not destination.is_dir():
        raise Clean2R2AEvaluationError("offline evaluation root is missing")

    summary_rows: list[dict[str, Any]] = []
    recomputed_crosschecks: dict[str, Any] = {}
    expected_ledger_rows: list[dict[str, Any]] = []
    audit_hashes: dict[str, str] = {}
    for method_id in METHOD_ORDER:
        run_id = run_directory(method_id)
        runtime = inputs["runtime_root"] / run_id
        output = destination / run_id
        summary_path = output / "summary.json"
        errors_path = output / "error_series.csv"
        strace_path = output / "EVALUATOR_FILE_OPEN_TRACE.raw"
        audit_path = output / "EVALUATOR_FILE_OPEN_AUDIT.json"
        summary = _read_json(summary_path)
        crosscheck = _crosscheck(errors_path, summary)
        if not crosscheck["passed"]:
            raise Clean2R2AEvaluationError(f"aggregate crosscheck failed: {method_id}")
        recomputed_crosschecks[method_id] = crosscheck
        summary_rows.append(_result_row(method_id, runtime, summary))

        persisted_audit = _read_json(audit_path)
        opened = parse_strace_openat_paths(strace_path, cwd=stage)
        recomputed_audit, ledger_rows = _audit_evaluator_file_opens(
            configuration_id=method_id,
            opened_paths=opened,
            trace=inputs["trace"],
            nav=(runtime / "KF_GINS_Navresult.nav").resolve(strict=True),
            std=(runtime / "KF_GINS_STD.txt").resolve(strict=True),
            evaluator=inputs["evaluator"],
            raw_root=inputs["raw_root"],
            runtime_root=inputs["runtime_root"],
            strace_sha256=sha256_file(strace_path),
            output_seal_manifest_sha256=seal["manifest_sha256"],
            seal_validation_completed_ns=int(persisted_audit["seal_validation_completed_ns"]),
            evaluator_started_ns=int(persisted_audit["evaluator_started_ns"]),
        )
        if persisted_audit != recomputed_audit:
            raise Clean2R2AEvaluationError(f"file-open audit was tampered: {method_id}")
        expected_ledger_rows.extend(ledger_rows)
        audit_hashes[method_id] = sha256_file(audit_path)

    result_fields, persisted_results = _read_csv(destination / "CLEAN2R2A_FACTORIAL_RESULTS.csv")
    if result_fields != list(RESULT_FIELDS) or persisted_results != _string_rows(summary_rows):
        raise Clean2R2AEvaluationError("factorial result table differs from the 18 exact summaries")
    coverage_rows = [{key: row[key] for key in COVERAGE_FIELDS} for row in summary_rows]
    coverage_fields, persisted_coverage = _read_csv(destination / "CLEAN2R2A_MATCH_COVERAGE.csv")
    if coverage_fields != list(COVERAGE_FIELDS) or persisted_coverage != _string_rows(coverage_rows):
        raise Clean2R2AEvaluationError("coverage table differs from the 18 exact summaries")
    ledger_fields, persisted_ledger = _read_csv(destination / "EVALUATOR_READ_LEDGER.csv")
    if ledger_fields != list(LEDGER_FIELDS) or persisted_ledger != _string_rows(expected_ledger_rows):
        raise Clean2R2AEvaluationError("evaluator read ledger differs from parsed strace evidence")

    persisted_crosscheck = _read_json(destination / "CLEAN2R2A_AGGREGATE_CROSSCHECK.json")
    expected_crosscheck = {
        "schema_version": "paper_rebuild.clean2r2a_aggregate_crosscheck.v2",
        "method_crosschecks": recomputed_crosschecks,
        "method_order": list(METHOD_ORDER),
        "method_count": len(METHOD_ORDER),
        "all_outputs_sealed_before_trace_open": True,
        "trace_offline_only": True,
        "passed": True,
    }
    if persisted_crosscheck != expected_crosscheck:
        raise Clean2R2AEvaluationError("aggregate crosscheck payload differs from recomputation")
    for method_id in METHOD_ORDER:
        _assert_persisted_crosscheck(
            persisted_crosscheck["method_crosschecks"][method_id],
            recomputed_crosschecks[method_id],
            method_id,
        )

    persisted_manifest = _read_json(destination / "OFFLINE_EVALUATION_MANIFEST.json")
    expected_manifest = _expected_manifest(
        inputs=inputs,
        seal=seal,
        destination=destination,
        audit_hashes=audit_hashes,
    )
    if persisted_manifest != expected_manifest:
        raise Clean2R2AEvaluationError("offline evaluation manifest differs from terminal evidence")
    seal_after = _output_seal_identity(stage)
    if seal_after["manifest_sha256"] != seal["manifest_sha256"] or seal_after["journal_sha256"] != seal["journal_sha256"]:
        raise Clean2R2AEvaluationError("output seal changed during terminal evaluation revalidation")

    report = {
        "schema_version": "paper_rebuild.clean2r2a_offline_evaluation_revalidation.v1",
        "method_count": len(METHOD_ORDER),
        "summary_error_series_crosschecks": len(METHOD_ORDER),
        "file_open_audits_reparsed": len(METHOD_ORDER),
        "read_ledger_rows": len(expected_ledger_rows),
        "output_seal_revalidated_before_and_after": True,
        "exact_evaluator_sha256": EXACT_EVALUATOR_SHA256,
        "trace_sha256": FROZEN_TRACE_SHA256,
        "base_time": FROZEN_BASE_TIME,
        "passed": True,
        "terminal_status": "PASS_CLEAN2R2A_OFFLINE_EVALUATION_REVALIDATION",
    }
    if write_report:
        write_json_atomic(destination / "CLEAN2R2A_OFFLINE_EVALUATION_REVALIDATION.json", report)
    return report


def evaluate_sealed_outputs(
    *,
    stage_root: str | Path,
    local_config: str | Path,
    exact_evaluator: str | Path,
    timeout_seconds: int = 900,
) -> dict[str, Any]:
    """Open the frozen trace only after validating every byte in the output seal."""

    if isinstance(timeout_seconds, bool) or timeout_seconds <= 0:
        raise Clean2R2AEvaluationError("timeout must be a positive integer")
    stage = Path(stage_root).expanduser().resolve(strict=True)
    # 首次读取 trace 字节（包括哈希校验）之前，先闭合 18-run output seal。
    initial_seal = _output_seal_identity(stage)
    inputs = _resolve_frozen_evaluation_inputs(
        local_config=local_config, exact_evaluator=exact_evaluator, stage_root=stage
    )
    seal_after_identity = _output_seal_identity(stage)
    if (
        seal_after_identity["manifest_sha256"] != initial_seal["manifest_sha256"]
        or seal_after_identity["journal_sha256"] != initial_seal["journal_sha256"]
    ):
        raise Clean2R2AEvaluationError("output seal changed during frozen input validation")
    destination = stage / "08_OFFLINE_EVALUATION"
    if not destination.is_dir() or any(destination.iterdir()):
        raise Clean2R2AEvaluationError("offline evaluation root is missing or not empty")
    strace = shutil.which("strace")
    if not strace:
        raise Clean2R2AEvaluationError("strace is required for offline-reference audit")

    summary_rows: list[dict[str, Any]] = []
    crosschecks: dict[str, Any] = {}
    evaluator_ledger_rows: list[dict[str, Any]] = []
    audit_hashes: dict[str, str] = {}
    for method_id in METHOD_ORDER:
        run_id = run_directory(method_id)
        runtime = inputs["runtime_root"] / run_id
        output = destination / run_id
        output.mkdir(parents=False)
        open_trace = output / "EVALUATOR_FILE_OPEN_TRACE.raw"
        nav = (runtime / "KF_GINS_Navresult.nav").resolve(strict=True)
        std = (runtime / "KF_GINS_STD.txt").resolve(strict=True)

        # 每个方法启动前再次验证全部 18 个输出，形成严格的先封存、后开 trace 顺序。
        per_run_seal = _output_seal_identity(stage)
        seal_validation_completed_ns = time.time_ns()
        if per_run_seal["manifest_sha256"] != initial_seal["manifest_sha256"]:
            raise Clean2R2AEvaluationError("output seal changed before evaluator start")
        command = [
            sys.executable,
            str(inputs["evaluator"]),
            "--trace", str(inputs["trace"]),
            "--nav", str(nav),
            "--std", str(std),
            "--outdir", str(output),
            "--base_time", str(FROZEN_BASE_TIME),
            "--yaw_truth_mode", "enu",
        ]
        wrapped = [
            strace, "-f", "-qq", "-yy", "-s", "4096", "-e", "trace=openat",
            "-o", str(open_trace), *command,
        ]
        evaluator_started_ns = time.time_ns()
        try:
            completed = subprocess.run(
                wrapped,
                cwd=stage,
                check=False,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                start_new_session=True,
            )
        except subprocess.TimeoutExpired as error:
            raise Clean2R2AEvaluationError(f"exact evaluator timed out: {method_id}") from error
        (output / "evaluator.stdout.txt").write_text(completed.stdout, encoding="utf-8")
        (output / "evaluator.stderr.txt").write_text(completed.stderr, encoding="utf-8")
        summary_path = output / "summary.json"
        errors_path = output / "error_series.csv"
        if completed.returncode != 0 or not summary_path.is_file() or not errors_path.is_file():
            raise Clean2R2AEvaluationError(f"exact evaluator failed: {method_id}")

        opened = parse_strace_openat_paths(open_trace, cwd=stage)
        audit, ledger_rows = _audit_evaluator_file_opens(
            configuration_id=method_id,
            opened_paths=opened,
            trace=inputs["trace"],
            nav=nav,
            std=std,
            evaluator=inputs["evaluator"],
            raw_root=inputs["raw_root"],
            runtime_root=inputs["runtime_root"],
            strace_sha256=sha256_file(open_trace),
            output_seal_manifest_sha256=per_run_seal["manifest_sha256"],
            seal_validation_completed_ns=seal_validation_completed_ns,
            evaluator_started_ns=evaluator_started_ns,
        )
        audit_path = output / "EVALUATOR_FILE_OPEN_AUDIT.json"
        write_json_atomic(audit_path, audit)
        audit_hashes[method_id] = sha256_file(audit_path)
        evaluator_ledger_rows.extend(ledger_rows)

        summary = _read_json(summary_path)
        crosscheck = _crosscheck(errors_path, summary)
        if not crosscheck["passed"]:
            raise Clean2R2AEvaluationError(f"aggregate crosscheck failed: {method_id}")
        crosschecks[method_id] = crosscheck
        summary_rows.append(_result_row(method_id, runtime, summary))

    _write_csv(destination / "CLEAN2R2A_FACTORIAL_RESULTS.csv", RESULT_FIELDS, summary_rows)
    coverage_rows = [{key: row[key] for key in COVERAGE_FIELDS} for row in summary_rows]
    _write_csv(destination / "CLEAN2R2A_MATCH_COVERAGE.csv", COVERAGE_FIELDS, coverage_rows)
    _write_csv(destination / "EVALUATOR_READ_LEDGER.csv", LEDGER_FIELDS, evaluator_ledger_rows)
    crosscheck_payload = {
        "schema_version": "paper_rebuild.clean2r2a_aggregate_crosscheck.v2",
        "method_crosschecks": crosschecks,
        "method_order": list(METHOD_ORDER),
        "method_count": len(METHOD_ORDER),
        "all_outputs_sealed_before_trace_open": True,
        "trace_offline_only": True,
        "passed": all(item["passed"] for item in crosschecks.values()),
    }
    write_json_atomic(destination / "CLEAN2R2A_AGGREGATE_CROSSCHECK.json", crosscheck_payload)
    final_seal = _output_seal_identity(stage)
    if final_seal["manifest_sha256"] != initial_seal["manifest_sha256"]:
        raise Clean2R2AEvaluationError("output seal changed during offline evaluation")
    write_json_atomic(
        destination / "OFFLINE_EVALUATION_MANIFEST.json",
        _expected_manifest(
            inputs=inputs,
            seal=final_seal,
            destination=destination,
            audit_hashes=audit_hashes,
        ),
    )
    revalidation = revalidate_offline_evaluation(
        stage_root=stage,
        local_config=local_config,
        exact_evaluator=exact_evaluator,
        write_report=True,
    )
    return {"crosscheck": crosscheck_payload, "revalidation": revalidation}
