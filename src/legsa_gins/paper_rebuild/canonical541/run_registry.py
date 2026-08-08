"""Logical-to-unique execution registry with exact-input aliases only."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Iterable, Mapping

from .ablation_registry import build_ablation_queue
from .full_method_registry import FEATURE_FIELDS, build_full_queue


class RunRegistryError(ValueError):
    pass


def _strict_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    normalized = str(value).strip().lower()
    if normalized in {"true", "1"}:
        return True
    if normalized in {"false", "0"}:
        return False
    raise RunRegistryError(f"invalid boolean value in execution registry: {value!r}")


def effective_flag_hash(row: Mapping[str, Any]) -> str:
    payload = {field: _strict_bool(row[field]) for field in FEATURE_FIELDS}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def execution_key(*, row: Mapping[str, Any], method_bound_provider_hash: str,
                  runtime_config_hash: str, executable_hash: str) -> str:
    """Bind aliases to the actual method-bound solver input and executable."""

    payload = {
        "method_effective_flags": {field: _strict_bool(row[field]) for field in FEATURE_FIELDS},
        "method_bound_provider_hash": method_bound_provider_hash,
        "runtime_config_hash": runtime_config_hash,
        "executable_hash": executable_hash,
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def build_logical_queues(cases: Iterable[Mapping[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rows = tuple(cases)
    return build_full_queue(rows), build_ablation_queue(rows)


def resolve_execution_aliases(
    logical_rows: Iterable[Mapping[str, Any]],
    *, method_bound_provider_hashes: Mapping[tuple[str, str], str],
    runtime_config_hashes: Mapping[tuple[str, str], str], executable_hash: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Resolve all logical rows; never infer an alias from a supposedly unused column.

    The runner first creates method-bound runtime inputs where unused source
    fields are restored to C00.  Consequently equal keys below mean byte-equal
    actual inputs, not an assumption about what C++ ignores.
    """

    logical_items = tuple(logical_rows)
    signatures = {tuple(_strict_bool(row[field]) for field in FEATURE_FIELDS) for row in logical_items}
    if len(logical_items) != 7033 or len(signatures) != 11:
        raise RunRegistryError("canonical matrix must contain exactly 11 effective execution profiles")
    resolved: list[dict[str, Any]] = []
    unique: list[dict[str, Any]] = []
    canonical_by_key: dict[str, str] = {}
    unique_by_run_id: dict[str, dict[str, Any]] = {}
    for order, source in enumerate(logical_items, start=1):
        row = dict(source); pair = (str(row["method_id"]), str(row["case_id"]))
        provider_hash = method_bound_provider_hashes[pair]
        config_hash = runtime_config_hashes[pair]
        key = execution_key(row=row, method_bound_provider_hash=provider_hash,
                            runtime_config_hash=config_hash, executable_hash=executable_hash)
        canonical = canonical_by_key.get(key)
        if canonical is None:
            run_id = f"RUN_{len(unique) + 1:05d}"
            canonical_by_key[key] = run_id
            unique.append({
                "run_id": run_id, "execution_key": key, "canonical_logical_id": row["logical_id"],
                "case_id": row["case_id"], "method_id": row["method_id"],
                "method_bound_provider_hash": provider_hash, "runtime_config_hash": config_hash,
                "executable_hash": executable_hash, "formal": True, "run_order": len(unique) + 1,
                "logical_alias_count": 1,
            })
            unique_by_run_id[run_id] = unique[-1]
            row.update(execution_alias=False, alias_of="", run_id=run_id)
        else:
            run_id = canonical
            record = unique_by_run_id[run_id]
            record["logical_alias_count"] += 1
            row.update(execution_alias=True, alias_of=record["canonical_logical_id"], run_id=run_id)
        row.update(logical_order=order, execution_key=key,
                   method_bound_provider_hash=provider_hash,
                   runtime_config_hash=config_hash, executable_hash=executable_hash,
                   terminal_status="PENDING")
        resolved.append(row)
    if len(resolved) != 7033 or any(not row.get("run_id") for row in resolved):
        raise RunRegistryError("7033 logical rows were not fully resolved")
    by_logical = {str(row["logical_id"]): row for row in resolved}
    for case_id in {str(row["case_id"]) for row in resolved}:
        for ablation, full in (("A01", "F04"), ("A02", "F03")):
            left = by_logical[f"ABLATION_{ablation}_{case_id}"]
            right = by_logical[f"FULL_{full}_{case_id}"]
            if left["execution_key"] != right["execution_key"] or left["run_id"] != right["run_id"]:
                raise RunRegistryError(f"required exact full/ablation alias failed: {case_id}:{ablation}/{full}")
    allowed_cross_method_sets = {frozenset(("A01", "F04")), frozenset(("A02", "F03"))}
    methods_by_run: dict[str, set[str]] = {}
    for row in resolved:
        methods_by_run.setdefault(str(row["run_id"]), set()).add(str(row["method_id"]))
    unexpected = sorted(
        sorted(methods) for methods in methods_by_run.values()
        if len(methods) > 1 and frozenset(methods) not in allowed_cross_method_sets
    )
    if unexpected:
        raise RunRegistryError(f"unexpected cross-method execution alias sets: {unexpected}")
    return resolved, unique


def validate_terminal_resolution(rows: Iterable[Mapping[str, Any]]) -> None:
    items = tuple(rows)
    allowed = {"COMPLETED_EVALUABLE", "COMPLETED_ALGORITHM_FAILURE_WITH_PROOF"}
    if len(items) != 7033 or any(row.get("terminal_status") not in allowed for row in items):
        raise RunRegistryError("logical terminal registry contains UNKNOWN/MISSING rows")
