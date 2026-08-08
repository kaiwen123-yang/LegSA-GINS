"""Logical-to-unique execution registry with exact-input aliases only."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Iterable, Mapping

from .ablation_registry import ABLATION_METHODS, build_ablation_queue
from .full_method_registry import FEATURE_FIELDS, FULL_METHODS, build_full_queue


class RunRegistryError(ValueError):
    pass


FROZEN_METHOD_SIGNATURES = {
    profile.method_id: tuple(bool(profile.flags[field]) for field in FEATURE_FIELDS)
    for profile in (*FULL_METHODS, *ABLATION_METHODS)
}
if len(FROZEN_METHOD_SIGNATURES) != 13 or len(set(FROZEN_METHOD_SIGNATURES.values())) != 11:
    raise RuntimeError("frozen Canonical-541 method map is not 13 methods / 11 signatures")


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
    """Bind one canonical case/profile identity to its exact solver inputs."""

    payload = {
        # Case identity is scientific identity even when a degradation happens
        # not to change the bytes consumed by one disabled-module profile.
        # Only the two frozen same-case full/ablation method aliases may share
        # an execution.
        "case_id": str(row["case_id"]),
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
    case_counts: dict[str, int] = {}
    for row in logical_items:
        case_counts[str(row["case_id"])] = case_counts.get(str(row["case_id"]), 0) + 1
    if (
        len(logical_items) != 7033
        or len(signatures) != 11
        or len(case_counts) != 541
        or set(case_counts.values()) != {13}
    ):
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
                **{field: _strict_bool(row[field]) for field in FEATURE_FIELDS},
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
    cases_by_run: dict[str, set[str]] = {}
    for row in resolved:
        cases_by_run.setdefault(str(row["run_id"]), set()).add(str(row["case_id"]))
    if any(len(case_ids) != 1 for case_ids in cases_by_run.values()):
        raise RunRegistryError("cross-case execution aliases are forbidden")
    aliases = [row for row in resolved if bool(row["execution_alias"])]
    expected_aliases = {
        (case_id, ablation, f"FULL_{full}_{case_id}")
        for case_id in case_counts
        for ablation, full in (("A01", "F04"), ("A02", "F03"))
    }
    actual_aliases = {
        (str(row["case_id"]), str(row["method_id"]), str(row["alias_of"]))
        for row in aliases
    }
    unique_by_case: dict[str, int] = {}
    for row in unique:
        unique_by_case[str(row["case_id"])] = unique_by_case.get(str(row["case_id"]), 0) + 1
    if (
        len(unique) != 5951
        or len(aliases) != 1082
        or actual_aliases != expected_aliases
        or set(unique_by_case) != set(case_counts)
        or set(unique_by_case.values()) != {11}
    ):
        raise RunRegistryError("canonical execution identity/alias closure failed")
    validate_execution_registry(resolved, unique)
    return resolved, unique


def validate_execution_registry(
    logical_rows: Iterable[Mapping[str, Any]], unique_rows: Iterable[Mapping[str, Any]],
) -> None:
    """Validate the frozen 541-case logical/physical execution closure."""

    logical = tuple(logical_rows); unique = tuple(unique_rows)
    case_ids = {str(row["case_id"]) for row in logical}
    unique_case_ids = {str(row["case_id"]) for row in unique}
    if (
        len(logical) != 7033 or len(unique) != 5951
        or len(case_ids) != 541 or unique_case_ids != case_ids
        or any(sum(str(row["case_id"]) == case_id for row in logical) != 13 for case_id in case_ids)
        or any(sum(str(row["case_id"]) == case_id for row in unique) != 11 for case_id in case_ids)
    ):
        raise RunRegistryError("canonical execution registry count/case closure failed")
    by_logical = {str(row["logical_id"]): row for row in logical}
    if len(by_logical) != 7033:
        raise RunRegistryError("canonical logical registry contains duplicates")
    aliases = [row for row in logical if _strict_bool(row["execution_alias"])]
    expected = {
        (case_id, ablation, f"FULL_{full}_{case_id}")
        for case_id in case_ids
        for ablation, full in (("A01", "F04"), ("A02", "F03"))
    }
    actual = {
        (str(row["case_id"]), str(row["method_id"]), str(row["alias_of"]))
        for row in aliases
    }
    if len(aliases) != 1082 or actual != expected:
        raise RunRegistryError("canonical aliases are not the exact same-case F04/A01 and F03/A02 set")
    cases_by_run: dict[str, set[str]] = {}
    for row in logical:
        cases_by_run.setdefault(str(row["run_id"]), set()).add(str(row["case_id"]))
    if any(len(values) != 1 for values in cases_by_run.values()):
        raise RunRegistryError("cross-case execution aliases are forbidden")
    if set(cases_by_run) != {str(row["run_id"]) for row in unique}:
        raise RunRegistryError("logical and unique run-id sets differ")
    by_run = {str(row["run_id"]): row for row in unique}
    execution_keys = {str(row.get("execution_key", "")) for row in unique}
    tracked_signatures = {
        tuple(_strict_bool(row[field]) for field in FEATURE_FIELDS) for row in logical
    }
    if len(by_run) != 5951 or len(execution_keys) != 5951 or len(tracked_signatures) != 11:
        raise RunRegistryError("canonical unique registry IDs/keys/profile signatures are not distinct")
    for case_id in case_ids:
        case_logical = [row for row in logical if str(row["case_id"]) == case_id]
        if (
            {str(row["method_id"]) for row in case_logical} != set(FROZEN_METHOD_SIGNATURES)
            or any(
                tuple(_strict_bool(row[field]) for field in FEATURE_FIELDS)
                != FROZEN_METHOD_SIGNATURES[str(row["method_id"])]
                for row in case_logical
            )
        ):
            raise RunRegistryError("canonical case differs from frozen 13-method map")
        case_signatures = {
            tuple(_strict_bool(row[field]) for field in FEATURE_FIELDS)
            for row in unique if str(row["case_id"]) == case_id
        }
        if case_signatures != tracked_signatures:
            raise RunRegistryError("canonical case does not contain all 11 tracked profiles")
    logical_count_by_run: dict[str, int] = {}
    for item in logical:
        logical_count_by_run[str(item["run_id"])] = logical_count_by_run.get(str(item["run_id"]), 0) + 1
    for order, row in enumerate(unique, start=1):
        expected_run_id = f"RUN_{order:05d}"
        owner = by_logical.get(str(row.get("canonical_logical_id", "")))
        if (
            str(row.get("run_id")) != expected_run_id
            or int(row.get("run_order", -1)) != order
            or owner is None
            or _strict_bool(owner.get("execution_alias", True))
            or str(owner.get("run_id")) != expected_run_id
            or str(owner.get("case_id")) != str(row.get("case_id"))
            or str(owner.get("method_id")) != str(row.get("method_id"))
            or str(owner.get("execution_key")) != str(row.get("execution_key"))
            or int(row.get("logical_alias_count", -1))
               != logical_count_by_run.get(expected_run_id)
        ):
            raise RunRegistryError("canonical owner/order/run identity closure failed")
        expected_key = execution_key(
            row=owner,
            method_bound_provider_hash=str(row.get("method_bound_provider_hash", "")),
            runtime_config_hash=str(row.get("runtime_config_hash", "")),
            executable_hash=str(row.get("executable_hash", "")),
        )
        if expected_key != str(row.get("execution_key")):
            raise RunRegistryError("canonical persisted execution key/signature drift")
    for order, row in enumerate(logical, start=1):
        owner = by_run[str(row["run_id"])]
        if (
            int(row.get("logical_order", -1)) != order
            or str(row.get("execution_key")) != str(owner.get("execution_key"))
            or effective_flag_hash(row) != effective_flag_hash(owner)
        ):
            raise RunRegistryError("logical order/key/signature differs from canonical owner")


def validate_terminal_resolution(rows: Iterable[Mapping[str, Any]]) -> None:
    items = tuple(rows)
    allowed = {"COMPLETED_EVALUABLE", "COMPLETED_ALGORITHM_FAILURE_WITH_PROOF"}
    if len(items) != 7033 or any(row.get("terminal_status") not in allowed for row in items):
        raise RunRegistryError("logical terminal registry contains UNKNOWN/MISSING rows")
