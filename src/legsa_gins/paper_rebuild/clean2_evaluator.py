"""Exact archived CLEAN1R2R1 evaluator adapter for sealed CLEAN2 outputs.

This module deliberately does not import :mod:`paper_rebuild.evaluator`.  CLEAN2
uses the recovered ``evaluate_nav_trace_kfgins_v2.py`` program byte-for-byte,
then independently recomputes the extended descriptive metrics from that
program's exact row-level output.
"""

from __future__ import annotations

import csv
import gzip
import json
import math
import re
import shutil
from pathlib import Path, PurePosixPath
from typing import Any, Mapping, Sequence

from .clean2_evidence import sealed_output_hash, validate_complete_output_seal
from .clean2_run_registry import read_run_registry
from .clean2_runner import ATTEMPT_FIELDS, Clean2RunError, validate_attempt_rows
from .manifest import sha256_file, sha256_text, write_json_atomic
from .paths import load_yaml_mapping
from .subprocess_guard import run_process_group


EXACT_EVALUATOR_SHA256 = (
    "aa0492482b6467cdd701bc8882aca11c4170bbe2e7c6bb5f932679dc204978da"
)
EXACT_EVALUATOR_BASENAME = "evaluate_nav_trace_kfgins_v2.py"
EXPECTED_TRACE_SHA256 = (
    "ee3ee42dea3ada196dfdbcc78fd07524f91b4ce4fb94d9d6482a3e7d4b34aa4c"
)
NAV_BASENAME = "KF_GINS_Navresult.nav"
STD_BASENAME = "KF_GINS_STD.txt"
UPDATE_TRACE_BASENAME = "PORT_GNSS_UPDATE_TRACE.csv"
SOURCE_AWARE_TRACE_BASENAME = "SOURCE_AWARE_WEIGHT_TRACE.csv"

EXACT_ERROR_COLUMNS = {
    "north": "err_n_m",
    "east": "err_e_m",
    "up": "err_u_m",
    "horizontal": "horizontal_err_m",
    "roll": "roll_err_deg",
    "pitch": "pitch_err_deg",
    "yaw": "yaw_err_deg",
}
EXACT_TIME_CANDIDATES = ("time", "time_s", "solver_time", "tow")
METRIC_FIELDS = ("horizontal", "up", "position_3d", "roll", "pitch", "yaw")
STAGE_ID = "CLEAN2_BY2_MODULE_ABLATION_AND_CLASSIC18"
ATTEMPT_AUDIT_SCHEMA = "paper_rebuild.clean2_terminal_attempt_audit.v1"


class Clean2EvaluatorError(RuntimeError):
    """Exact offline evaluation is partial, unsealed, or contract-incompatible."""


class SolverArtifactIndex(dict[str, dict[str, Path | None]]):
    """Resolved artifacts plus the verified structured-index provenance."""

    def __init__(
        self,
        rows: Mapping[str, dict[str, Path | None]],
        *,
        metadata: Mapping[str, Any],
        source_path: Path,
    ) -> None:
        super().__init__(rows)
        self.metadata = dict(metadata)
        self.source_path = source_path


def _is_sha256(value: Any) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def _percentile_type7(values: Sequence[float], probability: float) -> float:
    ordered = sorted(float(value) for value in values)
    if not ordered:
        raise Clean2EvaluatorError("Cannot aggregate an empty metric")
    position = (len(ordered) - 1) * probability
    low, high = math.floor(position), math.ceil(position)
    if low == high:
        return ordered[low]
    fraction = position - low
    return ordered[low] * (1.0 - fraction) + ordered[high] * fraction


def metric_summary(values: Sequence[float]) -> dict[str, float]:
    finite = [float(value) for value in values]
    if not finite or not all(math.isfinite(value) for value in finite):
        raise Clean2EvaluatorError("Metric values are empty or non-finite")
    absolute = [abs(value) for value in finite]
    return {
        "rmse": math.sqrt(math.fsum(value * value for value in finite) / len(finite)),
        "mae": math.fsum(absolute) / len(absolute),
        "p95": _percentile_type7(absolute, 0.95),
        "max": max(absolute),
    }


def _read_exact_error_rows(path: str | Path) -> list[dict[str, str]]:
    source = Path(path).resolve(strict=True)
    opener = gzip.open if source.suffix.casefold() == ".gz" else open
    with opener(source, "rt", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fields = set(reader.fieldnames or ())
        if not set(EXACT_ERROR_COLUMNS.values()).issubset(fields) or len(
            fields.intersection(EXACT_TIME_CANDIDATES)
        ) != 1:
            raise Clean2EvaluatorError("Exact evaluator error-series schema drifted")
        rows = list(reader)
    if not rows:
        raise Clean2EvaluatorError("Exact evaluator returned no row-level errors")
    return rows


def _exact_time_field(row: Mapping[str, Any]) -> str:
    matches = [field for field in EXACT_TIME_CANDIDATES if field in row]
    if len(matches) != 1:
        raise Clean2EvaluatorError("Exact evaluator time column is missing or ambiguous")
    return matches[0]


def _float(row: Mapping[str, Any], field: str) -> float:
    try:
        value = float(row[field])
    except (KeyError, TypeError, ValueError) as exc:
        raise Clean2EvaluatorError(f"Exact evaluator row has invalid field: {field}") from exc
    if not math.isfinite(value):
        raise Clean2EvaluatorError("Exact evaluator row contains NaN or infinity")
    return value


def aggregate_exact_error_rows(
    rows: Sequence[Mapping[str, Any]], *, output_epoch_count: int
) -> dict[str, Any]:
    """Independently recompute every CLEAN2 metric from exact evaluator rows."""

    if not rows or output_epoch_count < len(rows):
        raise Clean2EvaluatorError("Exact evaluator coverage cardinality is impossible")
    time_field = _exact_time_field(rows[0])
    times = [_float(row, time_field) for row in rows]
    if any(right <= left for left, right in zip(times, times[1:])):
        raise Clean2EvaluatorError("Exact evaluator row times are not strictly increasing")
    north = [_float(row, EXACT_ERROR_COLUMNS["north"]) for row in rows]
    east = [_float(row, EXACT_ERROR_COLUMNS["east"]) for row in rows]
    up = [_float(row, EXACT_ERROR_COLUMNS["up"]) for row in rows]
    reported_horizontal = [_float(row, EXACT_ERROR_COLUMNS["horizontal"]) for row in rows]
    derived_horizontal = [math.hypot(n, e) for n, e in zip(north, east)]
    if any(
        not math.isclose(left, right, rel_tol=1.0e-9, abs_tol=1.0e-9)
        for left, right in zip(reported_horizontal, derived_horizontal)
    ):
        raise Clean2EvaluatorError("Exact evaluator horizontal row error is inconsistent")
    roll = [_float(row, EXACT_ERROR_COLUMNS["roll"]) for row in rows]
    pitch = [_float(row, EXACT_ERROR_COLUMNS["pitch"]) for row in rows]
    yaw = [_float(row, EXACT_ERROR_COLUMNS["yaw"]) for row in rows]
    position_3d = [
        math.sqrt(n * n + e * e + u * u) for n, e, u in zip(north, east, up)
    ]
    metric_values = {
        "horizontal": derived_horizontal,
        "up": up,
        "position_3d": position_3d,
        "roll": roll,
        "pitch": pitch,
        "yaw": yaw,
    }
    last = len(rows) - 1
    signed = {
        "north_error_m": north[last],
        "east_error_m": east[last],
        "up_error_m": up[last],
        "roll_error_deg": roll[last],
        "pitch_error_deg": pitch[last],
        "yaw_error_deg": yaw[last],
    }
    matched = len(rows)
    return {
        "metrics": {name: metric_summary(values) for name, values in metric_values.items()},
        "component_metrics": {
            "north": metric_summary(north),
            "east": metric_summary(east),
        },
        "output_epoch_count": output_epoch_count,
        "matched_epoch_count": matched,
        "unmatched_epoch_count": output_epoch_count - matched,
        "coverage": matched / output_epoch_count if output_epoch_count else 0.0,
        "final_error": {
            "last_matched_output_row_index": matched - 1,
            "last_matched_solver_time": times[last],
            "signed_components": signed,
            "absolute_components": {name: abs(value) for name, value in signed.items()},
            "horizontal_position_error_m": derived_horizontal[last],
            "position_3d_error_m": position_3d[last],
        },
        "finite_output": True,
    }


def _nav_row_count(path: Path) -> int:
    count = 0
    previous_time: float | None = None
    with path.open("r", encoding="utf-8", errors="strict") as handle:
        for line in handle:
            stripped = line.strip()
            if not stripped or stripped.startswith(("#", "%")):
                continue
            try:
                values = [float(value) for value in stripped.replace(",", " ").split()]
            except ValueError:
                continue
            if len(values) < 2 or not all(math.isfinite(value) for value in values):
                raise Clean2EvaluatorError("Sealed NAV has malformed or non-finite rows")
            time_value = values[1]
            if previous_time is not None and time_value <= previous_time:
                raise Clean2EvaluatorError("Sealed NAV time is not strictly increasing")
            previous_time = time_value
            count += 1
    if count == 0:
        raise Clean2EvaluatorError("Sealed NAV contains no numeric rows")
    return count


def _validate_execution_protocol(path: str | Path) -> dict[str, Any]:
    payload = load_yaml_mapping(path)
    evaluator = payload.get("evaluator")
    if not isinstance(evaluator, Mapping):
        raise Clean2EvaluatorError("CLEAN2 execution protocol lacks evaluator contract")
    expected = {
        "base_time_unix_seconds": 1772784000.0,
        "window_seconds": [66.0, 340.0],
        "offset_search": False,
        "alignment": False,
        "output_correction": False,
        "epoch_deletion": False,
        "final_error_definition": "last_matched_epoch_absolute_and_component_error",
        "reference_trace_role": "evaluation_only_fixposition_same_source",
        "reference_trace_sha256": EXPECTED_TRACE_SHA256,
    }
    if any(evaluator.get(field) != value for field, value in expected.items()):
        raise Clean2EvaluatorError("CLEAN2 exact evaluator contract drifted")
    return dict(evaluator)


def _assert_exact_summary(
    exact: Mapping[str, Any], aggregate: Mapping[str, Any]
) -> dict[str, Any]:
    mapping = {
        "north_rmse_m": ("position", "north_rmse_m", "component_metrics", "north"),
        "east_rmse_m": ("position", "east_rmse_m", "component_metrics", "east"),
        "up_rmse_m": ("position", "up_rmse_m", "metrics", "up"),
        "horizontal_rmse_m": ("position", "horizontal_rmse_m", "metrics", "horizontal"),
        "roll_rmse_deg": ("attitude", "roll_rmse_deg", "metrics", "roll"),
        "pitch_rmse_deg": ("attitude", "pitch_rmse_deg", "metrics", "pitch"),
        "yaw_rmse_deg": ("attitude", "yaw_rmse_deg", "metrics", "yaw"),
    }
    checks: dict[str, Any] = {}
    for name, (section, exact_field, aggregate_section, metric) in mapping.items():
        try:
            reported = float(exact[section][exact_field])
        except (KeyError, TypeError, ValueError) as exc:
            raise Clean2EvaluatorError("Exact evaluator summary schema drifted") from exc
        computed = float(aggregate[aggregate_section][metric]["rmse"])
        difference = abs(reported - computed)
        passed = math.isfinite(reported) and difference <= 1.0e-10
        checks[name] = {
            "reported": reported,
            "independently_computed": computed,
            "absolute_difference": difference,
            "passed": passed,
        }
        if not passed:
            raise Clean2EvaluatorError("FAIL_CLEAN2_AGGREGATE_CROSSCHECK")
    meta = exact.get("meta")
    if not isinstance(meta, Mapping) or int(meta.get("num_samples", -1)) != int(
        aggregate["matched_epoch_count"]
    ):
        raise Clean2EvaluatorError("Exact evaluator summary sample count drifted")
    return {"checks": checks, "passed": True}


def _gzip_exact_csv(source: Path, destination: Path) -> None:
    # 中文说明：固定 gzip mtime，使相同 exact row 文件的压缩 hash 可复验。
    with source.open("rb") as input_handle, destination.open("xb") as raw_output:
        with gzip.GzipFile(fileobj=raw_output, mode="wb", filename="", mtime=0) as output:
            shutil.copyfileobj(input_handle, output)


def _run_exact_evaluator(
    *,
    evaluator: Path,
    trace: Path,
    nav: Path,
    std: Path,
    outdir: Path,
    base_time: float,
    timeout_seconds: int,
    log_dir: Path,
) -> tuple[Path, Path]:
    command = [
        str(evaluator),
        "--trace",
        str(trace),
        "--nav",
        str(nav),
        "--std",
        str(std),
        "--outdir",
        str(outdir),
        "--base_time",
        str(base_time),
        "--yaw_truth_mode",
        "enu",
    ]
    # The recovered program is a Python script; execute it through the current
    # interpreter without relying on its archived executable bit.
    import sys

    command.insert(0, sys.executable)
    completed = run_process_group(
        command,
        cwd=evaluator.parent,
        timeout_seconds=timeout_seconds,
        timeout_message="CLEAN2 exact evaluator timeout; process group terminated",
        launch_failure_message="CLEAN2 exact evaluator launch failure",
    )
    log_dir.mkdir(parents=True, exist_ok=True)
    (log_dir / "evaluator.stdout.txt").write_text(completed.stdout, encoding="utf-8")
    (log_dir / "evaluator.stderr.txt").write_text(completed.stderr, encoding="utf-8")
    summary = outdir / "summary.json"
    errors = outdir / "error_series.csv"
    if completed.returncode != 0 or not summary.is_file() or not errors.is_file():
        raise Clean2EvaluatorError("Exact archived evaluator failed")
    return summary, errors


ARTIFACT_INDEX_SCHEMA = "paper_rebuild.clean2_solver_artifact_index.v1"
ARTIFACT_INDEX_ROLES = {
    "nav": ("exact_nav", NAV_BASENAME),
    "std": ("exact_std", STD_BASENAME),
    "port_gnss_update_trace": ("gnss_action_trace", UPDATE_TRACE_BASENAME),
    "source_aware_weight_trace": ("source_aware_trace", SOURCE_AWARE_TRACE_BASENAME),
}


def _index_digest(payload: Mapping[str, Any]) -> str:
    unsigned = {key: value for key, value in payload.items() if key != "binding_digest"}
    return sha256_text(json.dumps(unsigned, ensure_ascii=False, sort_keys=True, separators=(",", ":")))


def _resolve_index_artifact(runtime: Path, run_id: str, raw: Mapping[str, Any], *, role: str) -> Path:
    try:
        relative = PurePosixPath(str(raw["relative_path"]))
        expected_hash = str(raw["sha256"])
        expected_size = int(raw["size_bytes"])
    except (KeyError, TypeError, ValueError) as exc:
        raise Clean2EvaluatorError(f"Structured artifact row is malformed: {run_id}/{role}") from exc
    if (
        relative.is_absolute()
        or ".." in relative.parts
        or not relative.parts
        or relative.parts[0] != run_id
    ):
        raise Clean2EvaluatorError("Structured artifact path escaped its formal run")
    candidate = runtime.joinpath(*relative.parts)
    current = runtime
    for part in relative.parts:
        current = current / part
        if current.is_symlink():
            raise Clean2EvaluatorError("Structured artifact path crosses a symlink")
    resolved = candidate.resolve(strict=True)
    if runtime not in resolved.parents or not resolved.is_file():
        raise Clean2EvaluatorError("Structured artifact is outside the formal runtime root")
    expected_name = ARTIFACT_INDEX_ROLES[role][1]
    if resolved.name != expected_name:
        raise Clean2EvaluatorError(f"Structured artifact basename drifted: {role}")
    if not _is_sha256(expected_hash) or sha256_file(resolved) != expected_hash:
        raise Clean2EvaluatorError("Structured artifact hash changed")
    if expected_size <= 0 or resolved.stat().st_size != expected_size:
        raise Clean2EvaluatorError("Structured artifact size changed")
    return resolved


def build_solver_artifact_index(
    *,
    complete_output_seal_path: str | Path,
    runtime_root: str | Path,
    registry_path: str | Path,
    output_path: str | Path,
) -> dict[str, Any]:
    """Derive one role-aware 110-run evaluator index from the revalidated seal."""

    runtime_raw = Path(runtime_root)
    if runtime_raw.is_symlink():
        raise Clean2EvaluatorError("Formal runtime root is a symlink")
    runtime = runtime_raw.resolve(strict=True)
    if not runtime.is_dir():
        raise Clean2EvaluatorError("Formal runtime root is not a directory")
    seal_path = Path(complete_output_seal_path).resolve(strict=True)
    registry = Path(registry_path).resolve(strict=True)
    seal = validate_complete_output_seal(
        seal_path,
        runtime_root=runtime,
        registry_path=registry,
    )
    destination = Path(output_path)
    if destination.exists() or destination.is_symlink():
        raise Clean2EvaluatorError("Fresh solver artifact index output already exists")
    entries: list[dict[str, Any]] = []
    for run in seal["runs"]:
        run_id = str(run["run_id"])
        files = {
            str(row["role"]): row
            for row in run["files"]
            if isinstance(row, Mapping)
        }
        expected_roles = {
            "exact_nav",
            "exact_std",
            "gnss_action_trace",
            *({"source_aware_trace"} if bool(run.get("feature_SA")) else set()),
        }
        if not expected_roles.issubset(files):
            raise Clean2EvaluatorError(f"Seal lacks evaluator artifacts: {run_id}")
        artifacts: dict[str, Any] = {}
        for field, (sealed_role, _) in ARTIFACT_INDEX_ROLES.items():
            if sealed_role not in files:
                artifacts[field] = None
                continue
            row = dict(files[sealed_role])
            _resolve_index_artifact(runtime, run_id, row, role=field)
            artifacts[field] = {
                "relative_path": row["relative_path"],
                "sha256": row["sha256"],
                "size_bytes": row["size_bytes"],
            }
        entries.append(
            {
                "run_id": run_id,
                "run_order": int(run["run_order"]),
                "feature_SA": bool(run.get("feature_SA")),
                "artifacts": artifacts,
            }
        )
    payload: dict[str, Any] = {
        "schema_version": ARTIFACT_INDEX_SCHEMA,
        "stage_id": "CLEAN2_BY2_MODULE_ABLATION_AND_CLASSIC18",
        "runtime_root": str(runtime),
        "runtime_root_alias": "<CLEAN2_STAGE>/07_FORMAL_RUNS",
        "complete_output_seal_sha256": sha256_file(seal_path),
        "registry_sha256": sha256_file(registry),
        "run_count": len(entries),
        "runs": entries,
        "passed": len(entries) == 110,
    }
    payload["binding_digest"] = _index_digest(payload)
    write_json_atomic(destination, payload)
    return payload


def load_solver_artifact_index(
    path: str | Path, *, expected_runtime_root: str | Path | None = None
) -> SolverArtifactIndex:
    source = Path(path).resolve(strict=True)
    payload = json.loads(source.read_text(encoding="utf-8"))
    runs = payload.get("runs") if isinstance(payload, Mapping) else None
    if (
        not isinstance(payload, Mapping)
        or payload.get("schema_version") != ARTIFACT_INDEX_SCHEMA
        or payload.get("stage_id") != "CLEAN2_BY2_MODULE_ABLATION_AND_CLASSIC18"
        or payload.get("run_count") != 110
        or payload.get("passed") is not True
        or payload.get("binding_digest") != _index_digest(payload)
        or not _is_sha256(payload.get("complete_output_seal_sha256"))
        or not _is_sha256(payload.get("registry_sha256"))
        or not isinstance(runs, list)
        or len(runs) != 110
    ):
        raise Clean2EvaluatorError("Structured solver artifact index identity is invalid")
    runtime_raw = Path(str(payload.get("runtime_root") or ""))
    if not runtime_raw.is_absolute() or runtime_raw.is_symlink():
        raise Clean2EvaluatorError("Structured solver artifact runtime root is unsafe")
    runtime = runtime_raw.resolve(strict=True)
    if not runtime.is_dir():
        raise Clean2EvaluatorError("Structured solver artifact runtime root is missing")
    if expected_runtime_root is not None and runtime != Path(expected_runtime_root).resolve(strict=True):
        raise Clean2EvaluatorError("Structured solver artifact runtime root differs from configured slot 07")
    resolved_rows: dict[str, dict[str, Path | None]] = {}
    orders: list[int] = []
    for raw in runs:
        if not isinstance(raw, Mapping) or not isinstance(raw.get("artifacts"), Mapping):
            raise Clean2EvaluatorError("Structured solver artifact run is malformed")
        run_id = str(raw.get("run_id") or "")
        order = int(raw.get("run_order") or 0)
        if not run_id or run_id in resolved_rows:
            raise Clean2EvaluatorError("Structured solver artifact run ids are empty/duplicated")
        orders.append(order)
        artifacts = raw["artifacts"]
        if set(artifacts) != set(ARTIFACT_INDEX_ROLES):
            raise Clean2EvaluatorError("Structured solver artifact roles drifted")
        resolved: dict[str, Path | None] = {}
        for role in ARTIFACT_INDEX_ROLES:
            value = artifacts[role]
            resolved[role] = (
                None
                if value is None
                else _resolve_index_artifact(runtime, run_id, value, role=role)
            )
        if resolved["nav"] is None or resolved["std"] is None or resolved["port_gnss_update_trace"] is None:
            raise Clean2EvaluatorError("Structured solver artifact run lacks NAV/STD/action trace")
        if bool(raw.get("feature_SA")) != (resolved["source_aware_weight_trace"] is not None):
            raise Clean2EvaluatorError("Structured solver artifact SA trace role drifted")
        resolved_rows[run_id] = resolved
    if orders != list(range(1, 111)):
        raise Clean2EvaluatorError("Structured solver artifact run order differs from 1..110")
    metadata = dict(payload)
    metadata["index_sha256"] = sha256_file(source)
    return SolverArtifactIndex(resolved_rows, metadata=metadata, source_path=source)


def validate_sealed_solver_artifact_index(
    *,
    artifact_index: Mapping[str, Mapping[str, Path | None]],
    complete_output_seal_path: str | Path,
    require_action_traces: bool,
    runtime_root: str | Path | None = None,
    registry_path: str | Path | None = None,
) -> dict[str, Any]:
    """Validate all artifacts before any evaluation-only trace can be opened."""

    if not isinstance(artifact_index, SolverArtifactIndex):
        raise Clean2EvaluatorError("Evaluator requires the structured solver artifact index")
    seal_path = Path(complete_output_seal_path).resolve(strict=True)
    seal = validate_complete_output_seal(
        seal_path,
        runtime_root=runtime_root,
        registry_path=registry_path,
    )
    if (
        artifact_index.metadata.get("complete_output_seal_sha256") != sha256_file(seal_path)
        or artifact_index.metadata.get("registry_sha256") != seal.get("registry_sha256")
        or artifact_index.metadata.get("run_count") != 110
    ):
        raise Clean2EvaluatorError("Structured solver artifact index is not bound to this seal")
    seal_ids = {str(row["run_id"]) for row in seal["runs"]}
    if set(artifact_index) != seal_ids or len(artifact_index) != 110:
        raise Clean2EvaluatorError("Solver artifact index and complete 110-run seal differ")
    checked = 0
    action_checked = 0
    sealed_by_id = {str(row["run_id"]): row for row in seal["runs"]}
    for run_id, artifacts in artifact_index.items():
        for field in ("nav", "std"):
            path = artifacts.get(field)
            if path is None:
                raise Clean2EvaluatorError(f"Sealed artifact is missing: {run_id}/{field}")
            expected = sealed_output_hash(seal, run_id=run_id, relative_name=path.name)
            if sha256_file(path) != expected:
                raise Clean2EvaluatorError("Sealed NAV/STD changed before offline evaluation")
            checked += 1
        update = artifacts.get("port_gnss_update_trace")
        if require_action_traces and update is None:
            raise Clean2EvaluatorError(f"Sealed PORT_GNSS_UPDATE_TRACE is missing: {run_id}")
        if update is not None:
            expected = sealed_output_hash(seal, run_id=run_id, relative_name=update.name)
            if sha256_file(update) != expected:
                raise Clean2EvaluatorError("Sealed update-action trace changed")
            action_checked += 1
        source = artifacts.get("source_aware_weight_trace")
        if bool(sealed_by_id[run_id].get("feature_SA")) and source is None:
            raise Clean2EvaluatorError(f"SA-enabled run lacks sealed source-aware trace: {run_id}")
        if source is not None:
            expected = sealed_output_hash(seal, run_id=run_id, relative_name=source.name)
            if sha256_file(source) != expected:
                raise Clean2EvaluatorError("Sealed source-aware trace changed")
            action_checked += 1
    return {
        "seal": seal,
        "nav_std_artifact_count": checked,
        "action_artifact_count": action_checked,
        "all_110_outputs_validated_before_trace": True,
        "solver_artifact_index_sha256": artifact_index.metadata["index_sha256"],
        "passed": checked == 220,
    }


def _read_and_validate_attempt_ledger(
    path: str | Path, *, registry_rows: Sequence[Mapping[str, Any]]
) -> tuple[Path, list[dict[str, str]], dict[str, Any]]:
    source_raw = Path(path)
    if source_raw.is_symlink():
        raise Clean2EvaluatorError("CLEAN2 run-attempt ledger is a symlink")
    source = source_raw.resolve(strict=True)
    with source.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if tuple(reader.fieldnames or ()) != ATTEMPT_FIELDS:
            raise Clean2EvaluatorError("CLEAN2 run-attempt ledger columns/order drifted")
        rows = list(reader)
    if any(set(row) != set(ATTEMPT_FIELDS) or None in row for row in rows):
        raise Clean2EvaluatorError("CLEAN2 run-attempt ledger row is malformed")
    try:
        runtimes = [float(row["runtime_seconds"]) for row in rows]
    except (KeyError, TypeError, ValueError) as exc:
        raise Clean2EvaluatorError("CLEAN2 run-attempt runtime is malformed") from exc
    if any(not math.isfinite(value) or value < 0.0 for value in runtimes):
        raise Clean2EvaluatorError("CLEAN2 run-attempt runtime is non-finite or negative")
    required = {str(row["run_id"]) for row in registry_rows}
    try:
        audit = validate_attempt_rows(
            rows,
            registry_rows=registry_rows,
            required_run_ids=required,
        )
    except (Clean2RunError, KeyError, TypeError, ValueError) as exc:
        raise Clean2EvaluatorError(
            "CLEAN2 run-attempt histories are not 110 terminal authorized chains"
        ) from exc
    if audit.get("run_count") != 110 or audit.get("passed") is not True:
        raise Clean2EvaluatorError("CLEAN2 run-attempt ledger is not a terminal 110-run PASS")
    return source, rows, audit


def _validate_terminal_attempt_audit(
    path: str | Path,
    *,
    registry_path: Path,
    attempts_path: Path,
    computed_audit: Mapping[str, Any],
) -> tuple[Path, dict[str, Any]]:
    source_raw = Path(path)
    if source_raw.is_symlink():
        raise Clean2EvaluatorError("CLEAN2 terminal attempt audit is a symlink")
    source = source_raw.resolve(strict=True)
    payload = json.loads(source.read_text(encoding="utf-8"))
    semantic_fields = {
        "run_count",
        "attempt_count",
        "technical_retry_run_count",
        "all_terminal_pass",
        "metric_driven_rerun",
        "passed",
    }
    expected_fields = {
        "schema_version",
        "stage_id",
        "registry_sha256",
        "attempts_sha256",
        *semantic_fields,
    }
    if not isinstance(payload, Mapping) or set(payload) != expected_fields:
        raise Clean2EvaluatorError("CLEAN2 terminal attempt audit schema/fields drifted")
    if (
        payload.get("schema_version") != ATTEMPT_AUDIT_SCHEMA
        or payload.get("stage_id") != STAGE_ID
        or payload.get("registry_sha256") != sha256_file(registry_path)
        or payload.get("attempts_sha256") != sha256_file(attempts_path)
        or any(payload.get(field) != computed_audit.get(field) for field in semantic_fields)
    ):
        raise Clean2EvaluatorError(
            "CLEAN2 registry/attempt-ledger/attempt-audit three-way binding failed"
        )
    return source, dict(payload)


def validate_pretrace_formal_chain(
    *,
    artifact_index: Mapping[str, Mapping[str, Path | None]],
    complete_output_seal_path: str | Path,
    registry_path: str | Path,
    run_attempts_path: str | Path,
    run_attempts_audit_path: str | Path,
    runtime_root: str | Path,
) -> dict[str, Any]:
    """Close registry, attempts, seal, and current runtime before trace access.

    中文说明：这是 formal ``evaluate``/``all`` 的唯一 trace 前置门。它先用
    当前 registry 逐项复验 110 个 runtime wrapper 和全部 sealed artifacts，再
    复验 attempt 历史以及 terminal audit 的三方 hash/语义绑定。任何一步失败
    都发生在 evaluation-only trace 被打开或计算 hash 之前。
    """

    registry_raw = Path(registry_path)
    runtime_raw = Path(runtime_root)
    if registry_raw.is_symlink() or runtime_raw.is_symlink():
        raise Clean2EvaluatorError("CLEAN2 pre-trace registry/runtime path is a symlink")
    registry = registry_raw.resolve(strict=True)
    runtime = runtime_raw.resolve(strict=True)
    if not runtime.is_dir():
        raise Clean2EvaluatorError("CLEAN2 formal runtime root is not a directory")
    registry_rows = read_run_registry(registry)
    if len(registry_rows) != 110:
        raise Clean2EvaluatorError("CLEAN2 pre-trace registry does not contain 110 runs")

    validation = validate_sealed_solver_artifact_index(
        artifact_index=artifact_index,
        complete_output_seal_path=complete_output_seal_path,
        require_action_traces=True,
        runtime_root=runtime,
        registry_path=registry,
    )
    attempts, attempt_rows, computed_audit = _read_and_validate_attempt_ledger(
        run_attempts_path,
        registry_rows=registry_rows,
    )
    attempt_audit, _ = _validate_terminal_attempt_audit(
        run_attempts_audit_path,
        registry_path=registry,
        attempts_path=attempts,
        computed_audit=computed_audit,
    )

    # 将每个 sealed artifact 绑定到该 run 的 terminal PASS attempt，避免 audit
    # 虽然 PASS、seal 却意外引用先前失败 attempt 的输出。
    by_run: dict[str, list[dict[str, str]]] = {}
    for row in attempt_rows:
        by_run.setdefault(str(row["run_id"]), []).append(row)
    for sealed in validation["seal"]["runs"]:
        run_id = str(sealed["run_id"])
        terminal_attempt = int(by_run[run_id][-1]["attempt_number"])
        expected_prefix = (run_id, "attempts", f"attempt_{terminal_attempt}")
        files = sealed.get("files")
        if not isinstance(files, list) or any(
            tuple(PurePosixPath(str(row.get("relative_path") or "")).parts[:3])
            != expected_prefix
            for row in files
            if isinstance(row, Mapping)
        ):
            raise Clean2EvaluatorError(
                "CLEAN2 output seal is not bound to each run's terminal PASS attempt"
            )

    hashes = {
        "registry_sha256": sha256_file(registry),
        "run_attempts_sha256": sha256_file(attempts),
        "run_attempts_audit_sha256": sha256_file(attempt_audit),
    }
    if (
        artifact_index.metadata.get("registry_sha256") != hashes["registry_sha256"]
        or Path(str(artifact_index.metadata.get("runtime_root") or "")).resolve(strict=True)
        != runtime
    ):
        raise Clean2EvaluatorError(
            "CLEAN2 solver artifact index differs from the current registry/runtime"
        )
    return {
        **validation,
        **hashes,
        "attempt_count": computed_audit["attempt_count"],
        "technical_retry_run_count": computed_audit["technical_retry_run_count"],
        "all_110_attempt_histories_validated_before_trace": True,
        "terminal_attempt_audit_validated_before_trace": True,
        "passed": validation.get("passed") is True,
    }


def _verify_exact_evaluator(path: str | Path, expected_sha256: str) -> Path:
    if expected_sha256 != EXACT_EVALUATOR_SHA256:
        raise Clean2EvaluatorError("CLEAN2 evaluator identity is not the exact CLEAN1R2R1 evaluator")
    evaluator = Path(path).resolve(strict=True)
    if evaluator.name != EXACT_EVALUATOR_BASENAME or sha256_file(evaluator) != expected_sha256:
        raise Clean2EvaluatorError("Exact evaluator SHA-256 mismatch")
    return evaluator


def _verify_offline_trace(path: str | Path, expected_sha256: str) -> Path:
    if expected_sha256 != EXPECTED_TRACE_SHA256:
        raise Clean2EvaluatorError("Evaluation-only trace identity differs from the frozen CLEAN1 anchor")
    reference = Path(path).resolve(strict=True)
    if sha256_file(reference) != expected_sha256:
        raise Clean2EvaluatorError("Evaluation-only trace SHA-256 mismatch")
    return reference


def _evaluate_prevalidated_run(
    *,
    run_id: str,
    artifacts: Mapping[str, Path | None],
    reference: Path,
    trace_sha256: str,
    evaluator: Path,
    evaluator_sha256: str,
    protocol: Mapping[str, Any],
    execution_protocol_path: str | Path,
    complete_output_seal_path: str | Path,
    formal_chain_hashes: Mapping[str, str] | None,
    output_dir: str | Path,
    timeout_seconds: int,
) -> dict[str, Any]:
    """Internal per-run executor; caller must already hold the batch pre-trace gate.

    It accepts only an already verified reference ``Path`` and intentionally has no
    public trace-path/hash verification entrypoint. Formal callers are restricted to
    :func:`evaluate_clean2_outputs`, which closes all 110 runs before invoking this.
    """

    nav = artifacts["nav"]
    std = artifacts["std"]
    assert nav is not None and std is not None
    destination = Path(output_dir).resolve(strict=False)
    if destination.exists():
        raise Clean2EvaluatorError("Fresh CLEAN2 evaluator output directory already exists")
    destination.mkdir(parents=True, exist_ok=False)
    exact_root = destination / "exact_evaluator_raw"
    exact_summary_path, exact_error_path = _run_exact_evaluator(
        evaluator=evaluator,
        trace=reference,
        nav=nav,
        std=std,
        outdir=exact_root,
        base_time=float(protocol["base_time_unix_seconds"]),
        timeout_seconds=timeout_seconds,
        log_dir=destination / "logs",
    )
    exact_summary = json.loads(exact_summary_path.read_text(encoding="utf-8"))
    if not isinstance(exact_summary, Mapping):
        raise Clean2EvaluatorError("Exact evaluator summary is not a mapping")
    exact_rows = _read_exact_error_rows(exact_error_path)
    aggregate = aggregate_exact_error_rows(exact_rows, output_epoch_count=_nav_row_count(nav))
    crosscheck = _assert_exact_summary(exact_summary, aggregate)
    copied_exact_summary = write_json_atomic(
        destination / "exact_evaluator_summary.json", dict(exact_summary)
    )
    error_path = destination / "error_series.csv.gz"
    _gzip_exact_csv(exact_error_path, error_path)
    # Only the freshly generated, successfully converted uncompressed row file is
    # removed.  Failed evaluator attempts and their logs are never deleted.
    exact_error_path.unlink()
    summary = {
        "schema_version": "paper_rebuild.clean2_exact_summary.v2",
        "run_id": run_id,
        "reference_role": "Fixposition-derived same-source offline evaluation reference",
        "independent_ground_truth": False,
        "position_same_source_mounting_caveat": True,
        "trace_used_online": False,
        "all_outputs_sealed_before_trace": True,
        "no_offset_search": True,
        "no_alignment": True,
        "no_output_correction": True,
        "epoch_deleted_for_metric": False,
        "exact_evaluator_sha256": evaluator_sha256,
        "trace_sha256": trace_sha256,
        **aggregate,
    }
    summary_path = write_json_atomic(destination / "summary.json", summary)
    coverage_path = write_json_atomic(
        destination / "coverage.json",
        {
            "run_id": run_id,
            "output_epoch_count": aggregate["output_epoch_count"],
            "matched_epoch_count": aggregate["matched_epoch_count"],
            "unmatched_epoch_count": aggregate["unmatched_epoch_count"],
            "coverage": aggregate["coverage"],
            "exact_archived_evaluator_overlap_policy": True,
        },
    )
    chain_hashes = dict(formal_chain_hashes or {})
    if chain_hashes and (
        set(chain_hashes)
        != {"registry_sha256", "run_attempts_sha256", "run_attempts_audit_sha256"}
        or not all(_is_sha256(value) for value in chain_hashes.values())
    ):
        raise Clean2EvaluatorError("CLEAN2 evaluator formal-chain hashes are invalid")
    manifest_path = write_json_atomic(
        destination / "evaluator_manifest.json",
        {
            "schema_version": "paper_rebuild.clean2_exact_evaluator_manifest.v2",
            "run_id": run_id,
            "nav_sha256": sha256_file(nav),
            "std_sha256": sha256_file(std),
            "trace_sha256": trace_sha256,
            "exact_evaluator_sha256": evaluator_sha256,
            "execution_protocol_sha256": sha256_file(execution_protocol_path),
            "complete_output_seal_sha256": sha256_file(complete_output_seal_path),
            **chain_hashes,
            "exact_summary_sha256": sha256_file(copied_exact_summary),
            "error_series_gzip_sha256": sha256_file(error_path),
            "summary_sha256": sha256_file(summary_path),
            "coverage_sha256": sha256_file(coverage_path),
            "exact_summary_row_crosscheck": crosscheck,
            "aggregate_crosscheck": True,
            "trace_opened_offline_after_complete_110_seal": True,
            "passed": True,
        },
    )
    return {
        "run_id": run_id,
        "summary": summary,
        "error_series": str(error_path),
        "summary_path": str(summary_path),
        "coverage_path": str(coverage_path),
        "exact_summary_path": str(copied_exact_summary),
        "evaluator_manifest_path": str(manifest_path),
        "port_gnss_update_trace": str(artifacts["port_gnss_update_trace"] or ""),
        "source_aware_weight_trace": str(artifacts["source_aware_weight_trace"] or ""),
    }


def evaluate_clean2_outputs(
    *,
    solver_artifact_index_path: str | Path,
    reference_trace_path: str | Path,
    trace_sha256: str,
    exact_evaluator_path: str | Path,
    evaluator_sha256: str,
    execution_protocol_path: str | Path,
    complete_output_seal_path: str | Path,
    registry_path: str | Path,
    run_attempts_path: str | Path,
    run_attempts_audit_path: str | Path,
    output_root: str | Path,
    expected_runtime_root: str | Path,
    timeout_seconds: int = 900,
) -> dict[str, Any]:
    """Run the exact evaluator over all 110 outputs as one post-seal phase."""

    artifact_index = load_solver_artifact_index(
        solver_artifact_index_path, expected_runtime_root=expected_runtime_root
    )
    validation = validate_pretrace_formal_chain(
        artifact_index=artifact_index,
        complete_output_seal_path=complete_output_seal_path,
        registry_path=registry_path,
        run_attempts_path=run_attempts_path,
        run_attempts_audit_path=run_attempts_audit_path,
        runtime_root=expected_runtime_root,
    )
    protocol = _validate_execution_protocol(execution_protocol_path)
    evaluator = _verify_exact_evaluator(exact_evaluator_path, evaluator_sha256)
    destination = Path(output_root).resolve(strict=False)
    if destination.exists() or destination.is_symlink():
        raise Clean2EvaluatorError("Fresh unified offline evaluation root already exists")
    # This is the first operation in the batch that opens the evaluation trace.
    reference = _verify_offline_trace(reference_trace_path, trace_sha256)
    destination.mkdir(parents=True, exist_ok=False)
    order = {
        str(row["run_id"]): int(row["run_order"])
        for row in validation["seal"]["runs"]
    }
    results: list[dict[str, Any]] = []
    for run_id in sorted(artifact_index, key=order.__getitem__):
        results.append(
            _evaluate_prevalidated_run(
                run_id=run_id,
                artifacts=artifact_index[run_id],
                reference=reference,
                trace_sha256=trace_sha256,
                evaluator=evaluator,
                evaluator_sha256=evaluator_sha256,
                protocol=protocol,
                execution_protocol_path=execution_protocol_path,
                complete_output_seal_path=complete_output_seal_path,
                formal_chain_hashes={
                    field: str(validation[field])
                    for field in (
                        "registry_sha256",
                        "run_attempts_sha256",
                        "run_attempts_audit_sha256",
                    )
                },
                output_dir=destination / run_id,
                timeout_seconds=timeout_seconds,
            )
        )
    index_path = write_json_atomic(
        destination / "CLEAN2_OFFLINE_EVALUATION_INDEX.json",
        {
            "schema_version": "paper_rebuild.clean2_offline_evaluation_index.v2",
            "run_count": len(results),
            "all_110_outputs_validated_before_trace": True,
            "all_outputs_sealed_before_trace": True,
            "trace_used_online": False,
            "exact_evaluator_sha256": evaluator_sha256,
            "trace_sha256": trace_sha256,
            "solver_artifact_index_sha256": sha256_file(solver_artifact_index_path),
            "complete_output_seal_sha256": sha256_file(complete_output_seal_path),
            "registry_sha256": validation["registry_sha256"],
            "run_attempts_sha256": validation["run_attempts_sha256"],
            "run_attempts_audit_sha256": validation["run_attempts_audit_sha256"],
            "all_110_attempt_histories_validated_before_trace": True,
            "terminal_attempt_audit_validated_before_trace": True,
            "results": results,
            "passed": len(results) == 110,
        },
    )
    return {"run_count": len(results), "index_path": str(index_path), "results": results}


def load_and_crosscheck_evaluation_index(
    path: str | Path,
    *,
    expected_solver_artifact_index_sha256: str | None = None,
    expected_complete_output_seal_sha256: str | None = None,
    expected_registry_sha256: str | None = None,
    expected_run_attempts_sha256: str | None = None,
    expected_run_attempts_audit_sha256: str | None = None,
    expected_solver_artifacts: Mapping[
        str, Mapping[str, Path | None]
    ] | None = None,
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    """Re-read every offline artifact and independently recompute all 110 rows."""

    source_raw = Path(path)
    if source_raw.is_symlink():
        raise Clean2EvaluatorError("Offline evaluation index is a symlink")
    source = source_raw.resolve(strict=True)
    if source.name != "CLEAN2_OFFLINE_EVALUATION_INDEX.json":
        raise Clean2EvaluatorError("Offline evaluation index basename drifted")
    payload = json.loads(source.read_text(encoding="utf-8"))
    results = payload.get("results")
    if (
        payload.get("schema_version")
        != "paper_rebuild.clean2_offline_evaluation_index.v2"
        or payload.get("run_count") != 110
        or payload.get("passed") is not True
        or payload.get("all_110_outputs_validated_before_trace") is not True
        or payload.get("all_outputs_sealed_before_trace") is not True
        or payload.get("all_110_attempt_histories_validated_before_trace") is not True
        or payload.get("terminal_attempt_audit_validated_before_trace") is not True
        or payload.get("trace_used_online") is not False
        or payload.get("exact_evaluator_sha256") != EXACT_EVALUATOR_SHA256
        or payload.get("trace_sha256") != EXPECTED_TRACE_SHA256
        or not isinstance(results, list)
        or len(results) != 110
        or not _is_sha256(payload.get("solver_artifact_index_sha256"))
        or not _is_sha256(payload.get("complete_output_seal_sha256"))
        or not _is_sha256(payload.get("registry_sha256"))
        or not _is_sha256(payload.get("run_attempts_sha256"))
        or not _is_sha256(payload.get("run_attempts_audit_sha256"))
        or (
            expected_solver_artifact_index_sha256 is not None
            and payload.get("solver_artifact_index_sha256")
            != expected_solver_artifact_index_sha256
        )
        or (
            expected_complete_output_seal_sha256 is not None
            and payload.get("complete_output_seal_sha256")
            != expected_complete_output_seal_sha256
        )
        or (
            expected_registry_sha256 is not None
            and payload.get("registry_sha256") != expected_registry_sha256
        )
        or (
            expected_run_attempts_sha256 is not None
            and payload.get("run_attempts_sha256") != expected_run_attempts_sha256
        )
        or (
            expected_run_attempts_audit_sha256 is not None
            and payload.get("run_attempts_audit_sha256")
            != expected_run_attempts_audit_sha256
        )
    ):
        raise Clean2EvaluatorError("Offline evaluation index is incomplete")
    summaries: dict[str, dict[str, Any]] = {}
    checks: dict[str, Any] = {}
    evaluation_root = source.parent
    if evaluation_root.is_symlink():
        raise Clean2EvaluatorError("Offline evaluation root is a symlink")

    def resolve_result_file(run_id: str, raw: Any, basename: str) -> Path:
        run_identity = PurePosixPath(run_id)
        if (
            run_identity.is_absolute()
            or run_identity.parts != (run_id,)
            or run_id in {"", ".", ".."}
        ):
            raise Clean2EvaluatorError("Offline evaluation run id is unsafe")
        run_root = evaluation_root / run_id
        candidate = run_root / basename
        supplied = Path(str(raw or ""))
        if (
            not supplied.is_absolute()
            or run_root.is_symlink()
            or candidate.is_symlink()
        ):
            raise Clean2EvaluatorError("Offline evaluation result path is unsafe")
        resolved = candidate.resolve(strict=True)
        if (
            supplied.resolve(strict=True) != resolved
            or resolved.parent != run_root
            or not resolved.is_file()
        ):
            raise Clean2EvaluatorError(
                "Offline evaluation index path escaped its run directory"
            )
        return resolved

    ordered_run_ids: list[str] = []
    for result in results:
        if not isinstance(result, Mapping):
            raise Clean2EvaluatorError("Offline evaluation result is malformed")
        run_id = str(result.get("run_id") or "")
        if run_id in summaries:
            raise Clean2EvaluatorError("Offline evaluation run ids are duplicated")
        ordered_run_ids.append(run_id)
        summary_path = resolve_result_file(run_id, result.get("summary_path"), "summary.json")
        errors_path = resolve_result_file(
            run_id, result.get("error_series"), "error_series.csv.gz"
        )
        coverage_path = resolve_result_file(
            run_id, result.get("coverage_path"), "coverage.json"
        )
        exact_summary_path = resolve_result_file(
            run_id,
            result.get("exact_summary_path"),
            "exact_evaluator_summary.json",
        )
        manifest_path = resolve_result_file(
            run_id,
            result.get("evaluator_manifest_path"),
            "evaluator_manifest.json",
        )
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        coverage = json.loads(coverage_path.read_text(encoding="utf-8"))
        exact_summary = json.loads(exact_summary_path.read_text(encoding="utf-8"))
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if not all(
            isinstance(value, Mapping)
            for value in (summary, coverage, exact_summary, manifest)
        ):
            raise Clean2EvaluatorError("Offline evaluation JSON artifact is malformed")
        rows = _read_exact_error_rows(errors_path)
        recomputed = aggregate_exact_error_rows(
            rows, output_epoch_count=int(summary["output_epoch_count"])
        )
        numeric_equal = True
        for metric in METRIC_FIELDS:
            for statistic in ("rmse", "mae", "p95", "max"):
                numeric_equal = numeric_equal and math.isclose(
                    float(summary["metrics"][metric][statistic]),
                    float(recomputed["metrics"][metric][statistic]),
                    rel_tol=1.0e-12,
                    abs_tol=1.0e-12,
                )
        scalar_equal = all(
            summary[field] == recomputed[field]
            for field in ("output_epoch_count", "matched_epoch_count", "unmatched_epoch_count")
        ) and math.isclose(
            float(summary["coverage"]), float(recomputed["coverage"]), rel_tol=0.0, abs_tol=1e-15
        )
        final_equal = summary["final_error"] == recomputed["final_error"]
        summary_identity = (
            summary.get("schema_version") == "paper_rebuild.clean2_exact_summary.v2"
            and summary.get("run_id") == run_id
            and summary.get("trace_used_online") is False
            and summary.get("all_outputs_sealed_before_trace") is True
            and summary.get("no_offset_search") is True
            and summary.get("no_alignment") is True
            and summary.get("no_output_correction") is True
            and summary.get("epoch_deleted_for_metric") is False
            and summary.get("exact_evaluator_sha256") == EXACT_EVALUATOR_SHA256
            and summary.get("trace_sha256") == EXPECTED_TRACE_SHA256
            and result.get("summary") == summary
        )
        coverage_equal = (
            coverage.get("run_id") == run_id
            and coverage.get("output_epoch_count") == recomputed["output_epoch_count"]
            and coverage.get("matched_epoch_count") == recomputed["matched_epoch_count"]
            and coverage.get("unmatched_epoch_count") == recomputed["unmatched_epoch_count"]
            and coverage.get("exact_archived_evaluator_overlap_policy") is True
            and math.isclose(
                float(coverage.get("coverage")),
                float(recomputed["coverage"]),
                rel_tol=0.0,
                abs_tol=1.0e-15,
            )
        )
        exact_crosscheck = _assert_exact_summary(exact_summary, recomputed)
        manifest_identity = (
            manifest.get("schema_version")
            == "paper_rebuild.clean2_exact_evaluator_manifest.v2"
            and manifest.get("run_id") == run_id
            and manifest.get("trace_sha256") == EXPECTED_TRACE_SHA256
            and manifest.get("exact_evaluator_sha256") == EXACT_EVALUATOR_SHA256
            and manifest.get("complete_output_seal_sha256")
            == payload.get("complete_output_seal_sha256")
            and manifest.get("registry_sha256") == payload.get("registry_sha256")
            and manifest.get("run_attempts_sha256")
            == payload.get("run_attempts_sha256")
            and manifest.get("run_attempts_audit_sha256")
            == payload.get("run_attempts_audit_sha256")
            and manifest.get("exact_summary_sha256") == sha256_file(exact_summary_path)
            and manifest.get("error_series_gzip_sha256") == sha256_file(errors_path)
            and manifest.get("summary_sha256") == sha256_file(summary_path)
            and manifest.get("coverage_sha256") == sha256_file(coverage_path)
            and manifest.get("exact_summary_row_crosscheck") == exact_crosscheck
            and manifest.get("aggregate_crosscheck") is True
            and manifest.get("trace_opened_offline_after_complete_110_seal") is True
            and manifest.get("passed") is True
            and _is_sha256(manifest.get("execution_protocol_sha256"))
            and _is_sha256(manifest.get("nav_sha256"))
            and _is_sha256(manifest.get("std_sha256"))
        )
        solver_binding = True
        if expected_solver_artifacts is not None:
            artifacts = expected_solver_artifacts.get(run_id)
            if not isinstance(artifacts, Mapping):
                raise Clean2EvaluatorError(
                    "Offline evaluation run is absent from the solver artifact index"
                )
            nav = artifacts.get("nav")
            std = artifacts.get("std")
            port = artifacts.get("port_gnss_update_trace")
            source_aware = artifacts.get("source_aware_weight_trace")

            def same_artifact_path(raw: Any, expected: Path) -> bool:
                candidate = Path(str(raw or ""))
                return (
                    candidate.is_absolute()
                    and not candidate.is_symlink()
                    and candidate == expected
                    and candidate.resolve(strict=True) == expected
                )

            solver_binding = (
                isinstance(nav, Path)
                and isinstance(std, Path)
                and isinstance(port, Path)
                and manifest.get("nav_sha256") == sha256_file(nav)
                and manifest.get("std_sha256") == sha256_file(std)
                and same_artifact_path(result.get("port_gnss_update_trace"), port)
                and (
                    (
                        source_aware is None
                        and str(result.get("source_aware_weight_trace") or "") == ""
                    )
                    or (
                        isinstance(source_aware, Path)
                        and same_artifact_path(
                            result.get("source_aware_weight_trace"), source_aware
                        )
                    )
                )
            )
        passed = all(
            (
                numeric_equal,
                scalar_equal,
                final_equal,
                summary_identity,
                coverage_equal,
                manifest_identity,
                solver_binding,
            )
        )
        if not passed:
            raise Clean2EvaluatorError("FAIL_CLEAN2_AGGREGATE_CROSSCHECK")
        summaries[run_id] = summary
        checks[run_id] = {
            "row_count": len(rows),
            "metrics_recomputed": numeric_equal,
            "coverage_recomputed": scalar_equal,
            "final_error_recomputed": final_equal,
            "summary_identity_bound": summary_identity,
            "coverage_artifact_recomputed": coverage_equal,
            "exact_summary_recomputed": exact_crosscheck["passed"],
            "manifest_all_artifact_hashes_bound": manifest_identity,
            "solver_artifacts_bound": solver_binding,
            "passed": passed,
        }
    if expected_solver_artifacts is not None and ordered_run_ids != list(
        expected_solver_artifacts
    ):
        raise Clean2EvaluatorError(
            "Offline evaluation order differs from the solver artifact index"
        )
    return summaries, {
        "run_count": len(checks),
        "independent_row_recomputation_count": len(checks),
        "checks": checks,
        "passed": len(checks) == 110 and all(row["passed"] for row in checks.values()),
    }
