"""C-04b contract amendment and V2 rendering from immutable C-03 providers."""
from __future__ import annotations
import argparse
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys
import yaml

from ..manifest import sha256_file
from .contract_v2 import amend_contract, validate_amendment
from .generation_audit import selected_lock, validate_checkpoint, write_json_exclusive
from .registry import load_registry
from .runtime_config import (METHODS, CONFIG_FILENAMES, OVERRIDE_CATEGORIES, build_runtime_config,
    load_sealed_profiles, frozen_parameter_hash, scientific_runtime_config_hash,
    audit_backend_provenance_sources, _diff_markdown)
from .solver_runner import (C02_COMMIT, C03_COMMIT, _record_hashes, _hash_check, _git_bytes,
    verify_provider_files, execution_registry)

CONFIG_DIR = "03_RUNTIME_CONFIGS_V2"
RUN_DIR = "04_SOLVER_RUNS_V2"
SEAL_DIR = "05_OUTPUT_SEAL_V2"


def read(path):
    return json.loads(Path(path).read_text())


def stage_path(registry, dataset):
    name = "CLEAN5_BY2_CONTROL_PROVIDER_PARITY" if dataset == "BY2" else registry.sequences[dataset].stage_id
    return registry.clean_root / "stages" / name


def event_inputs(registry):
    joint = read(stage_path(registry, "BY2") / "06_ALIGNMENT_DIAGNOSTICS/B_C_PREPARATION_GATE.json")
    order = ["BY2", "BY2H", "BY2O"]
    if (joint.get("passed") is not True or joint.get("ready_for_contract_amendment") is not True
            or joint.get("sequences_completed") != order or joint.get("sequence_order") != order
            or len(joint.get("sequence_gates", [])) != 3):
        raise RuntimeError("Joint event preparation gate must PASS all three sequences")
    output = {}
    for dataset in ("BY2", "BY2H", "BY2O"):
        stage = stage_path(registry, dataset)
        audit_dir = stage / "06_ALIGNMENT_DIAGNOSTICS/00_AUDIT"
        gate = read(audit_dir / "EVENT_PHASE_GATE.json")
        event_path = stage / "01_SEQUENCE_CONTRACT/EVENT_WINDOW_V2.json"
        event = read(event_path)
        if (gate != joint["sequence_gates"][order.index(dataset)]
                or gate.get("dataset_id") != dataset or event.get("dataset_id") != dataset
                or gate.get("code_freeze_commit") != joint.get("code_freeze_commit")
                or gate.get("event_path") != str(event_path)
                or gate.get("event_sha256") != sha256_file(event_path)):
            raise RuntimeError("Event report/gate provenance or bytes differ: " + dataset)
        if gate.get("passed") is not True or event.get("ready_for_v2_contract") is not True:
            raise RuntimeError("All three event/diagnostic integrity gates must PASS: " + dataset)
        lock = selected_lock(registry, registry.sequences[dataset])
        before = read(audit_dir / "pre_event_CHECKPOINT.json")
        after = read(audit_dir / "post_event_CHECKPOINT.json")
        if before != gate.get("pre_checkpoint") or after != gate.get("post_checkpoint"):
            raise RuntimeError("Event checkpoint differs from sealed gate")
        for phase in ("pre_event", "event", "post_event"):
            if gate.get(phase + "_strace", {}).get("pass") is not True:
                raise RuntimeError("Event strace audit did not PASS")
        for phase, checkpoint in (("pre_event", before), ("post_event", after)):
            validate_checkpoint(checkpoint, phase=phase, lock=lock)
        if before["verified_hashes"] != after["verified_hashes"]:
            raise RuntimeError("Event input checkpoints changed")
        output[dataset] = {"event": event, "gate": gate, "event_path": event_path,
            "event_sha256": sha256_file(event_path), "gate_sha256": sha256_file(audit_dir / "EVENT_PHASE_GATE.json")}
    return output


def amend_both_contracts(registry, commit):
    from .revalidation import _git
    if _git(registry.code_root, "rev-parse", "HEAD") != commit:
        raise RuntimeError("Amendment source freeze differs")
    events = event_inputs(registry)
    pending = []
    for dataset in ("BY2H", "BY2O"):
        relative = f"configs/paper_rebuild/clean5/CLEAN5_{dataset}_SEQUENCE_CONTRACT.yaml"
        path = registry.code_root / relative
        old = _git_bytes(registry.code_root, C02_COMMIT, relative).decode()
        if path.read_text() != old:
            raise RuntimeError("v1 contract was modified before event amendment")
        item = events[dataset]
        if item["gate"].get("code_freeze_commit") != commit:
            raise RuntimeError("Event code freeze differs from amendment source")
        new = amend_contract(old, item["event"], item["event_sha256"], commit)
        pending.append((path, new))
    for path, text in pending:
        path.write_text(text)
    return {"status": "CONTRACTS_V2_AMENDED_NOT_COMMITTED", "contracts": {str(path.relative_to(registry.code_root)): sha256_file(path) for path, _ in pending}}


def frozen_inputs(registry, dataset, executable):
    paths, hashes, record_sha = _record_hashes(registry.code_root)
    stage = stage_path(registry, dataset)
    relative = f"configs/paper_rebuild/clean5/CLEAN5_{dataset}_SEQUENCE_CONTRACT.yaml"
    contract_path = registry.code_root / relative
    old = _git_bytes(registry.code_root, C02_COMMIT, relative).decode()
    new = contract_path.read_text()
    validate_amendment(old, new)
    if contract_path.read_bytes() != _git_bytes(registry.code_root, "HEAD", relative):
        raise RuntimeError("V2 contract differs from committed execution snapshot")
    contract = yaml.safe_load(new)
    manifest_path = stage / "02_PROVIDER_FREEZE/PROVIDER_MANIFEST.json"
    check = _hash_check(manifest_path, paths["<CLEAN_ROOT>/"+manifest_path.relative_to(registry.clean_root).as_posix()], root=stage, role="C-03 unchanged provider manifest")
    manifest = read(manifest_path)
    if manifest["contract_paths_sha256"][relative] != contract["supersedes_v1_sha256"]:
        raise RuntimeError("V2 contract does not supersede the frozen provider's C-02 contract")
    if manifest["frozen_executable"]["sha256"] != executable["sha256"] or manifest["frozen_executable"]["path"] != executable["path"]:
        raise RuntimeError("Frozen executable lineage changed")
    if manifest["status"] != "PASS_PROVIDER_FREEZE":
        raise RuntimeError("C-03 provider gate is not PASS")
    lock = selected_lock(registry, registry.sequences[dataset])
    raw = {key: row["sha256"] for key, row in lock["rows"].items()}
    if raw != manifest["raw_source_hashes"] or raw != contract["identity"]["raw_files_sha256"]:
        raise RuntimeError("Raw lock/provider/contract lineage differs")
    providers = verify_provider_files(stage/"02_PROVIDER_FREEZE", manifest)
    metadata = {"02_PROVIDER_FREEZE/PROVIDER_MANIFEST.json": check}
    for path, digest in manifest["audit_paths_sha256"].items():
        metadata[path] = _hash_check(stage/path, digest, root=stage, role="Unchanged C-03 provider audit")
    expected_identity = {"dataset_id": dataset, "stage_id": registry.sequences[dataset].stage_id,
        "data_mode": registry.sequences[dataset].data_mode}
    if any(manifest.get(key) != value or contract["identity"].get(key) != value for key, value in expected_identity.items()):
        raise RuntimeError("C-03/V2 sequence identity mismatch")
    return {"stage": stage, "contract": contract, "provider_manifest": manifest,
        "provider_checks": providers, "frozen_metadata_checks": metadata,
        "contract_check": {"path": str(contract_path), "sha256": sha256_file(contract_path), "supersedes_v1_sha256": contract["supersedes_v1_sha256"]},
        "c03_record_sha256": record_sha, "lock": lock, "frozen_profile_hashes": hashes}


def render_material(registry, state, executable, paths_config):
    events = event_inputs(registry)
    local = yaml.safe_load(Path(paths_config).read_text())["paths"]
    sealed = load_sealed_profiles(local["base_provider_gate"])
    pending, inputs, reports = {}, {}, {}
    for dataset in ("BY2H", "BY2O"):
        item = frozen_inputs(registry, dataset, executable)
        contract = item["contract"]
        if (contract["event_window_report_sha256"] != events[dataset]["event_sha256"]
                or contract["amendment_code_commit"] != events[dataset]["gate"]["code_freeze_commit"]):
            raise RuntimeError("Committed V2 contract/event provenance differs")
        inputs[dataset] = item
        pending[dataset] = {}
        for method, profile in METHODS.items():
            pending[dataset][method] = build_runtime_config(method_id=method, contract=contract,
                provider_manifest=item["provider_manifest"], sealed_profile=sealed["profiles"][method],
                output_path=item["stage"]/RUN_DIR/f"{dataset}_{method}_{profile}")
    gates = []
    for method, profile in METHODS.items():
        hashes = {"BY2": frozen_parameter_hash(sealed["profiles"][method]["text"]),
            **{ds: frozen_parameter_hash(pending[ds][method][0]) for ds in pending}}
        if len(set(hashes.values())) != 1:
            raise RuntimeError("V2 BY2/BY2H/BY2O frozen parameter gate failed")
        gates.append({"method_id": method, "effective_configuration_id": profile, "frozen_parameter_hashes": hashes, "passed": True})
    joint = {"passed": True, "profile_count": 5, "profiles": gates, "scientific_runtime_config_hash_is_cross_sequence_gate": False}
    source_audit = audit_backend_provenance_sources(registry.code_root)
    docs = {}
    for ds, item in inputs.items():
        report = {"schema_version": "paper_rebuild.clean5.runtime_config_audit.v3", "status": "PASS_PREPARED_NOT_EXECUTED",
            "contract_version": 2, "dataset_id": ds, "stage_id": item["contract"]["identity"]["stage_id"],
            "data_mode": item["contract"]["identity"]["data_mode"], "synthetic_data_used": False, "semisynthetic_data_used": False,
            "method_order": list(METHODS), "profiles": [pending[ds][m][1] for m in METHODS],
            "joint_frozen_parameter_gate": joint, "backend_provenance_source_audit": source_audit,
            "override_categories": {key: sorted(value) for key,value in OVERRIDE_CATEGORIES.items()},
            "frozen_executable": executable, "provider_manifest_sha256": item["frozen_metadata_checks"]["02_PROVIDER_FREEZE/PROVIDER_MANIFEST.json"]["sha256"],
            "contract_sha256": item["contract_check"]["sha256"], "event_report_sha256": events[ds]["event_sha256"],
            "provider_regeneration_count": 0, "solver_execution_count": 0, "evaluator_execution_count": 0,
            "trace_content_read_count": 0, "non_whitelisted_difference_count": 0, **state}
        text = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False)+"\n"
        docs[ds] = {"RUNTIME_CONFIG_AUDIT.json": text, "RUNTIME_CONFIG_DIFF_VS_CLEAN2R2A1.json": text,
            "RUNTIME_CONFIG_DIFF_VS_CLEAN2R2A1.md": _diff_markdown(report),
            **{CONFIG_FILENAMES[m]: pending[ds][m][0] for m in METHODS}}
        reports[ds] = report
    return docs, reports, inputs


def preflight_v2(registry, sequence, executable):
    from .solver_runner import execution_state
    state = execution_state(registry.code_root, subprocess.check_output(["git","rev-parse","HEAD"], cwd=registry.code_root, text=True).strip())
    # The original local path file is used only to locate the immutable BY2
    # profile gate. It is never changed to point at the detached snapshot.
    original_root = Path(executable["path"]).parents[2]
    docs, reports, inputs = render_material(registry, state, executable,
        original_root/"configs/paper_rebuild/DATA_PATHS.CLEAN3R4.local.yaml")
    ds = sequence.dataset_id
    result = inputs[ds]
    if (result["stage"]/RUN_DIR).exists() or (result["stage"]/SEAL_DIR).exists():
        raise RuntimeError("V2 solver attempt already exists; no overwrite or retry")
    configurations = {}
    for name, text in docs[ds].items():
        path = result["stage"]/CONFIG_DIR/name
        if path.read_bytes() != text.encode():
            raise RuntimeError("Rendered V2 configuration/audit bytes differ from reproducible frozen inputs: " + name)
        result["frozen_metadata_checks"][CONFIG_DIR+"/"+name] = {"path": str(path), "sha256": sha256_file(path)}
    for profile in reports[ds]["profiles"]:
        method = profile["method_id"]
        path = result["stage"]/CONFIG_DIR/CONFIG_FILENAMES[method]
        configurations[method] = {"text": path.read_text(), "profile": profile,
            "identity": {"path": str(path), "sha256": sha256_file(path)}}
    result["configurations"] = configurations
    result["runs_subdir"] = RUN_DIR
    result["occlusion"] = None
    if ds == "BY2O":
        path = result["stage"]/"01_SEQUENCE_CONTRACT/OCCLUSION_WINDOW.json"
        result["occlusion"] = _hash_check(path, "4ffabd12c71ef08ec3bb43bb5969fe97883b657c6d68aec2fc827f1fb56e349f", root=result["stage"], role="Unchanged preregistered occlusion")
    return result


def main(argv=None, *, execution_script=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", choices=("amend-contracts-v2", "render-v2"), required=True)
    parser.add_argument("--paths-config", type=Path, required=True)
    parser.add_argument("--code-root", type=Path, required=True)
    parser.add_argument("--code-freeze-commit", required=True)
    parser.add_argument("--executable", type=Path, required=True)
    args = parser.parse_args(argv)
    registry = load_registry(args.code_root/"configs/paper_rebuild/clean5/CLEAN5_SEQUENCE_REGISTRY.yaml", args.paths_config)
    if args.phase == "amend-contracts-v2":
        from .revalidation import _published_source
        _published_source(args, registry)
        result = amend_both_contracts(registry, args.code_freeze_commit)
    else:
        registry, state, executable = execution_registry(registry, code_root=args.code_root,
            code_freeze_commit=args.code_freeze_commit, executable=args.executable,
            execution_script=execution_script or sys.argv[0])
        docs, reports, inputs = render_material(registry, state, executable, args.paths_config)
        if any((item["stage"]/CONFIG_DIR).exists() for item in inputs.values()):
            raise RuntimeError("V2 configuration attempt already exists")
        for ds, material in docs.items():
            directory = inputs[ds]["stage"]/CONFIG_DIR
            directory.mkdir()
            for name, text in material.items():
                with (directory/name).open("x") as handle:
                    handle.write(text)
        result = {"status": "PASS_PREPARED_NOT_EXECUTED", "joint_frozen_parameter_gate": reports["BY2H"]["joint_frozen_parameter_gate"]}
    print(json.dumps(result, ensure_ascii=False), flush=True)
    return 0
