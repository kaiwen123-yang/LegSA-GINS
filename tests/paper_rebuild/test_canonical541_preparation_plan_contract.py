import hashlib

import pytest

from legsa_gins.paper_rebuild.canonical541.full_method_registry import FEATURE_FIELDS
from legsa_gins.paper_rebuild.canonical541.preparation import (
    ABLATION_QUEUE_TOTAL,
    ALL_LOGICAL_TOTAL,
    FULL_QUEUE_TOTAL,
    METHOD_BOUND_TOTAL,
)
from legsa_gins.paper_rebuild.canonical541.run_registry import (
    RunRegistryError, build_logical_queues,
    resolve_execution_aliases,
    validate_execution_registry,
)


def _cases():
    rows = []
    for index in range(541):
        case_id = "C00_clean_normal" if index == 0 else f"D{((index - 1) // 9) + 1:02d}_seed_{(index - 1) % 9:02d}"
        rows.append({
            "case_id": case_id, "case_index": index,
            "case_family": "clean" if index == 0 else "test",
            "degradation_type_id": "CLEAN" if index == 0 else case_id[:3],
            "degradation_type_name": "test", "seed_index": "none",
            "seed_value": "", "seed_effective": False,
            "independent_realization": False, "anchor_name": "none",
            "anchor_time_s": "", "degradation_parameters_json": "{}",
        })
    return rows


def test_preparation_counts_and_required_exact_aliases():
    cases = _cases()
    full, ablation = build_logical_queues(cases)
    logical = [*full, *ablation]
    method_hashes = {}
    runtime_hashes = {}
    for row in logical:
        signature = "".join("1" if row[field] else "0" for field in FEATURE_FIELDS)
        # Deliberately identical across cases: case_id itself must prevent a
        # degradation that is inactive for one profile from cross-case dedup.
        method_hashes[(row["method_id"], row["case_id"])] = hashlib.sha256(
            signature.encode()
        ).hexdigest()
        runtime_hashes[(row["method_id"], row["case_id"])] = hashlib.sha256(signature.encode()).hexdigest()
    resolved, unique = resolve_execution_aliases(
        logical, method_bound_provider_hashes=method_hashes,
        runtime_config_hashes=runtime_hashes, executable_hash="e" * 64,
    )
    assert METHOD_BOUND_TOTAL == 5951
    assert len(full) == FULL_QUEUE_TOTAL == 2164
    assert len(ablation) == ABLATION_QUEUE_TOTAL == 4869
    assert len(resolved) == ALL_LOGICAL_TOTAL == 7033
    assert len(unique) == 5951
    assert sum(bool(row["execution_alias"]) for row in resolved) == 1082
    assert {row["case_id"] for row in unique} == {row["case_id"] for row in cases}
    assert all(sum(row["case_id"] == case["case_id"] for row in unique) == 11 for case in cases)
    by_id = {row["logical_id"]: row for row in resolved}
    for case in cases:
        case_id = case["case_id"]
        assert by_id[f"ABLATION_A01_{case_id}"]["run_id"] == by_id[f"FULL_F04_{case_id}"]["run_id"]
        assert by_id[f"ABLATION_A02_{case_id}"]["run_id"] == by_id[f"FULL_F03_{case_id}"]["run_id"]

    # A persisted registry may never reuse a run ID across case identities.
    tampered = [dict(row) for row in resolved]
    first = next(row for row in tampered if row["case_id"] == cases[0]["case_id"] and not row["execution_alias"])
    second = next(row for row in tampered if row["case_id"] == cases[1]["case_id"] and not row["execution_alias"])
    second["run_id"] = first["run_id"]
    with pytest.raises(RunRegistryError, match="cross-case"):
        validate_execution_registry(tampered, unique)
