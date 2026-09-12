import hashlib
import json
from pathlib import Path

import pytest

from legsa_gins.paper_rebuild.canonical541.full_method_registry import FEATURE_FIELDS
from legsa_gins.paper_rebuild.canonical541 import execution_plan
from legsa_gins.paper_rebuild.canonical541.provider_generator import sha256_file
from legsa_gins.paper_rebuild.canonical541.run_registry import (
    RunRegistryError, build_logical_queues, resolve_execution_aliases,
    validate_execution_registry,
)


def _registries():
    cases = []
    for index in range(541):
        case_id = "C00_clean_normal" if index == 0 else f"D{((index - 1) // 9) + 1:02d}_seed_{(index - 1) % 9:02d}"
        cases.append({
            "case_id": case_id, "case_index": index,
            "case_family": "clean" if index == 0 else "test",
            "degradation_type_id": "CLEAN" if index == 0 else case_id[:3],
            "seed_index": "none", "seed_effective": False,
            "independent_realization": False,
        })
    full, ablation = build_logical_queues(cases); logical = [*full, *ablation]
    providers = {}; configs = {}
    for row in logical:
        signature = "".join("1" if row[field] else "0" for field in FEATURE_FIELDS)
        pair = (row["method_id"], row["case_id"])
        providers[pair] = hashlib.sha256(("provider:" + signature).encode()).hexdigest()
        configs[pair] = hashlib.sha256(("config:" + signature).encode()).hexdigest()
    return resolve_execution_aliases(
        logical, method_bound_provider_hashes=providers,
        runtime_config_hashes=configs, executable_hash="e" * 64,
    )


@pytest.mark.parametrize("tamper", ["owner", "order", "key", "signature", "alias"])
def test_persisted_registry_tamper_is_rejected(tamper):
    logical, unique = _registries()
    logical = [dict(row) for row in logical]; unique = [dict(row) for row in unique]
    if tamper == "owner":
        unique[0]["canonical_logical_id"] = unique[1]["canonical_logical_id"]
    elif tamper == "order":
        unique[0]["run_order"] = 2
    elif tamper == "key":
        unique[0]["execution_key"] = "0" * 64
    elif tamper == "signature":
        unique[0][FEATURE_FIELDS[0]] = not unique[0][FEATURE_FIELDS[0]]
    else:
        alias = next(row for row in logical if row["execution_alias"])
        alias["alias_of"] = unique[1]["canonical_logical_id"]
    with pytest.raises(RunRegistryError):
        validate_execution_registry(logical, unique)


def _authoritative_gate_fixture(tmp_path):
    logical, unique = _registries()
    for row in unique:
        row["method_bound_manifest_hash"] = hashlib.sha256(row["run_id"].encode()).hexdigest()
    stage = tmp_path
    full = [row for row in logical if row["matrix"] == "full_algorithm"]
    ablation = [row for row in logical if row["matrix"] == "internal_ablation"]
    paths = {
        "full_queue": stage / "07_FULL_ALGORITHM_REGISTRY/PREPARED_REGISTRY_FREEZE/FULL_ALGORITHM_QUEUE.csv",
        "ablation_queue": stage / "07_FULL_ALGORITHM_REGISTRY/PREPARED_REGISTRY_FREEZE/INTERNAL_ABLATION_QUEUE.csv",
        "unique_registry": stage / "07_FULL_ALGORITHM_REGISTRY/PREPARED_REGISTRY_FREEZE/CANONICAL541_UNIQUE_RUN_REGISTRY.csv",
        "hash_registry": stage / "07_FULL_ALGORITHM_REGISTRY/PROVIDER_CONFIG_EXECUTABLE_HASH_REGISTRY.csv",
        "source_isolation": stage / "04_EFFECT_RULES/CANONICAL541_EXPECTED_SOURCE_ISOLATION_MATRIX.csv",
        "completeness_audit": stage / "16_AUDITS/CANONICAL541_EXECUTION_INPUT_COMPLETENESS_AUDIT.json",
        "preparation_status": stage / "07_FULL_ALGORITHM_REGISTRY/PREPARATION_STATUS.json",
    }
    execution_plan.write_csv_atomic(paths["full_queue"], full)
    execution_plan.write_csv_atomic(paths["ablation_queue"], ablation)
    execution_plan.write_csv_atomic(paths["unique_registry"], unique)
    current_paths = {
        "full_queue": stage / "07_FULL_ALGORITHM_REGISTRY/FULL_ALGORITHM_QUEUE.csv",
        "ablation_queue": stage / "09_INTERNAL_ABLATION_REGISTRY/INTERNAL_ABLATION_QUEUE.csv",
        "unique_registry": stage / "07_FULL_ALGORITHM_REGISTRY/CANONICAL541_UNIQUE_RUN_REGISTRY.csv",
    }
    execution_plan.write_csv_atomic(current_paths["full_queue"], full)
    execution_plan.write_csv_atomic(current_paths["ablation_queue"], ablation)
    execution_plan.write_csv_atomic(current_paths["unique_registry"], unique)
    execution_plan.write_csv_atomic(paths["hash_registry"], [{
        "case_id": row["case_id"], "run_id": row["run_id"],
        "execution_key": row["execution_key"], "runtime_config_hash": row["runtime_config_hash"],
        "method_bound_provider_hash": row["method_bound_provider_hash"],
        "executable_sha256": row["executable_hash"],
        "method_bound_manifest_sha256": row["method_bound_manifest_hash"],
    } for row in unique])
    execution_plan.write_csv_atomic(paths["source_isolation"], [
        {"row": index} for index in range(671)
    ])
    audit = {
        "passed": True, "method_bound_completed": 5951, "unique_runs_planned": 5951,
        "full_queue_rows": 2164, "ablation_queue_rows": 4869,
        "provider_config_executable_hash_rows": 5951, "source_isolation_rows": 671,
        "solver_runs": 0, "evaluator_runs": 0, "trace_reads": 0,
        "formal_execution_started": False, "preparation_code_commit": "p" * 40,
        "worktree_clean": True,
        "full_queue_sha256": sha256_file(paths["full_queue"]),
        "ablation_queue_sha256": sha256_file(paths["ablation_queue"]),
        "unique_registry_sha256": sha256_file(paths["unique_registry"]),
        "hash_registry_sha256": sha256_file(paths["hash_registry"]),
        "source_isolation_sha256": sha256_file(paths["source_isolation"]),
    }
    status = {
        "phase": "READY_FOR_AUTOMATIC_EXECUTION", "method_bound_completed": 5951,
        "full_queue_rows": 2164, "ablation_queue_rows": 4869, "unique_runs_planned": 5951,
        "solver_runs": 0, "evaluator_runs": 0, "trace_reads": 0,
        "formal_execution_started": False, "execution_authorized": True,
        "solver_allowed_after_readiness_freeze": True, "human_approval_required": False,
    }
    for path, payload in ((paths["completeness_audit"], audit), (paths["preparation_status"], status)):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload) + "\n", encoding="utf-8")
    plan = {
        "passed": True, "preparation_code_commit": "p" * 40,
        "prepared_artifact_sha256": {name: sha256_file(path) for name, path in paths.items()},
        "current_status_registry_sha256": {name: sha256_file(path) for name, path in current_paths.items()},
    }
    return stage, plan, unique, logical, paths


def test_authoritative_gate_accepts_exact_plan_last_package(tmp_path):
    stage, plan, unique, logical, _ = _authoritative_gate_fixture(tmp_path)
    result = execution_plan._validate_authoritative_preparation_gate(
        stage=stage, plan=plan, unique=unique, logical=logical,
    )
    assert {key: result[key] for key in plan["prepared_artifact_sha256"]} == plan["prepared_artifact_sha256"]
    assert all(result[f"current_{key}"] == value for key, value in plan["current_status_registry_sha256"].items())


@pytest.mark.parametrize("tamper", ["status", "audit", "hash_registry", "hash_bijection", "preseal"])
def test_authoritative_gate_rejects_tamper_and_preseal_activity(tmp_path, tamper):
    stage, plan, unique, logical, paths = _authoritative_gate_fixture(tmp_path)
    if tamper in {"status", "audit"}:
        path = paths["preparation_status" if tamper == "status" else "completeness_audit"]
        payload = json.loads(path.read_text(encoding="utf-8")); payload["passed" if tamper == "audit" else "phase"] = False
        path.write_text(json.dumps(payload) + "\n", encoding="utf-8")
    elif tamper == "hash_registry":
        with paths["hash_registry"].open("a", encoding="utf-8") as handle:
            handle.write("tamper\n")
    elif tamper == "hash_bijection":
        rows = execution_plan.read_csv(paths["hash_registry"])
        rows[1]["run_id"] = rows[0]["run_id"]
        execution_plan.write_csv_atomic(paths["hash_registry"], rows)
        audit = json.loads(paths["completeness_audit"].read_text())
        audit["hash_registry_sha256"] = sha256_file(paths["hash_registry"])
        paths["completeness_audit"].write_text(json.dumps(audit) + "\n")
        plan["prepared_artifact_sha256"]["hash_registry"] = sha256_file(paths["hash_registry"])
        plan["prepared_artifact_sha256"]["completeness_audit"] = sha256_file(paths["completeness_audit"])
    else:
        proof = stage / "08_FULL_ALGORITHM_RUNS/RUN_00001/RUN_PROOF.json"
        proof.parent.mkdir(parents=True); proof.write_text("{}\n", encoding="utf-8")
    with pytest.raises(execution_plan.ExecutionPlanError):
        execution_plan._validate_authoritative_preparation_gate(
            stage=stage, plan=plan, unique=unique, logical=logical,
        )
