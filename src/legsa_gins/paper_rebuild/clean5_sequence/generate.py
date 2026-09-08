"""C-03 supervisor: two strace sessions, provider freeze, then config rendering.

No solver or evaluator entrypoint is invoked. Checkpoint and generation workers
are separate processes; the checkpoint worker waits between its pre/post hashes.
"""
from __future__ import annotations

import argparse
import copy
import json
import os
import subprocess
import sys
from dataclasses import replace
from hashlib import sha256
from pathlib import Path

from ..manifest import sha256_file
from ..paths import guard_path, load_yaml_mapping
from .generation_audit import (audit_checkpoint_session, audit_records, checkpoint,
                               code_freeze_state, open_records, selected_lock,
                               validate_checkpoint, write_json_exclusive)
from .registry import load_registry

CONTROL_STAGE = "CLEAN5_BY2_CONTROL_PROVIDER_PARITY"
FROZEN_EXECUTABLE_RELATIVE = Path("build/canonical541_cpp/legsa_v23_port_core_demo")
FROZEN_EXECUTABLE_SHA256 = "9c00565c45b654453b2b378f3d5995e5dc21d1271323a9b683acdab75993235f"


def execution_registry(registry, *, code_root, code_freeze_commit, execution_script):
    """Use the authorized snapshot in memory; retain the original local YAML."""
    requested = Path(code_root).resolve(strict=True)
    expected = registry.code_root.parent / ("clean5-freeze-" + code_freeze_commit[:12])
    if requested != expected.resolve() or requested == registry.code_root:
        raise RuntimeError("--code-root differs from the authorized attempt-owned detached worktree")
    if (registry.clean_root == requested or requested in registry.clean_root.parents
            or registry.clean_root in requested.parents):
        raise RuntimeError("Provider/config output root must be disjoint from the immutable execution snapshot")
    module_root = Path(__file__).resolve().parents[4]
    script = Path(execution_script).resolve(strict=True)
    if module_root != requested or script != requested / "scripts/paper_rebuild/clean5_generate_providers.py":
        raise RuntimeError("Imported generation module and executed script must come from --code-root")
    for name, module in tuple(sys.modules.items()):
        location = getattr(module, "__file__", None)
        if (name == "legsa_gins" or name.startswith("legsa_gins.")) and location:
            if requested not in Path(location).resolve().parents:
                raise RuntimeError(f"Imported project module is outside --code-root: {name}")
    state = code_freeze_state(requested, code_freeze_commit)
    binary = guard_path(registry.code_root / FROZEN_EXECUTABLE_RELATIVE,
                        role="frozen Canonical solver executable", allowed_root=registry.code_root,
                        must_exist=True, regular_file=True)
    digest = sha256_file(binary)
    if digest != FROZEN_EXECUTABLE_SHA256:
        raise RuntimeError("Frozen Canonical executable SHA-256 mismatch; rebuilding is forbidden")
    executable = {"path": str(binary), "sha256": digest,
                  "path_source": "original local paths.code_root/build/canonical541_cpp/legsa_v23_port_core_demo",
                  "executed_during_c03": False, "rebuilt_during_c03": False}
    return replace(registry, code_root=requested), state, executable


def require_provider_freeze(registry, dataset_id, state):
    """Read a preceding PASS manifest, never substitute an older code identity."""
    root = stage_root(registry, registry.sequences[dataset_id]) / "02_PROVIDER_FREEZE"
    path = root / "PROVIDER_MANIFEST.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    expected = {"dataset_id": dataset_id, "status": "PASS_PROVIDER_FREEZE", **state}
    if any(manifest.get(key) != value for key, value in expected.items()):
        raise RuntimeError(f"{dataset_id} provider freeze must PASS under this exact execution snapshot first")
    if dataset_id == "BY2":
        gate = json.loads((root / "BY2_PROVIDER_PARITY_GATE.json").read_text(encoding="utf-8"))
        if gate.get("passed") is not True or manifest.get("by2_provider_parity_gate") != gate:
            raise RuntimeError("Fresh BY2 provider parity must PASS before subsequent work")
    return manifest


def require_generation_order(registry, sequence, state):
    order = ("BY2", "BY2H", "BY2O")
    index = order.index(sequence.dataset_id)
    for prior in order[:index]:
        require_provider_freeze(registry, prior, state)
    for later in order[index + 1:]:
        later_root = stage_root(registry, registry.sequences[later])
        if any((later_root / name).exists() for name in
               ("01_PROVIDER_GENERATION_AUDIT", "02_PROVIDER_FREEZE", "03_RUNTIME_CONFIGS")):
            raise RuntimeError(f"{later} attempt already exists; provider order or no-retry boundary violated")


def stage_root(registry, sequence):
    name = CONTROL_STAGE if sequence.dataset_id == "BY2" else sequence.stage_id
    return guard_path(registry.clean_root / "stages" / name, role="C-03 stage", allowed_root=registry.clean_root)


def load_generation_contract(registry, sequence):
    repo = registry.code_root
    rel = Path("configs/paper_rebuild/clean5") / f"CLEAN5_{sequence.dataset_id}_SEQUENCE_CONTRACT.yaml"
    if sequence.dataset_id != "BY2":
        contract = load_yaml_mapping(repo / rel)
        sources = {str(rel): sha256_file(repo / rel)}
    else:
        # The control uses archived BY2 parameters, never the first-epoch estimate.
        template = Path("configs/paper_rebuild/clean5/CLEAN5_BY2H_SEQUENCE_CONTRACT.yaml")
        parity_path = Path("configs/paper_rebuild/final_v23_parity_contract.yaml")
        parity = load_yaml_mapping(repo / parity_path)
        parameters = copy.deepcopy(load_yaml_mapping(repo / template)["frozen_parameters"])
        init = parity["runtime_initialization"]
        contract = {"identity": {"dataset_id": "BY2", "stage_id": CONTROL_STAGE, "data_mode": "real_by2_raw"},
                    "time_contract": {"base_time": float(parity["time_contract"]["base_time_unix_seconds"]),
                                      "utc_day_midnight": 1772755200.0, "auxiliary_rebase_offset_seconds": 28800.0},
                    "window_contract": {"t_start": 66.0, "t_end": 340.0},
                    "initialization_contract": {"initpos": init["initpos_deg_deg_m"],
                                                "initvel": init["initvel_ned_mps"],
                                                "initatt": init["initatt_rpy_deg"]},
                    "frozen_parameters": parameters}
        sources = {str(p): sha256_file(repo / p) for p in
                   (parity_path, template, Path("configs/paper_rebuild/clean1_by2_clean_protocol.yaml"))}
    lock = selected_lock(registry, sequence)
    expected_hashes = {key: row["sha256"] for key, row in lock["rows"].items()}
    if sequence.dataset_id != "BY2":
        if contract["identity"]["raw_files_sha256"] != expected_hashes:
            raise RuntimeError("Contract raw hashes do not match the frozen lock")
        for source in contract["frozen_parameter_sources"]:
            source_path = source["path"]
            if source_path.startswith(("<", "build/")) or "#" in source_path:
                continue
            if sha256_file(repo / source_path) != source["sha256"]:
                raise RuntimeError(f"Frozen parameter source changed: {source_path}")
    contract["identity"]["raw_files_sha256"] = expected_hashes
    contract["identity"]["raw_lock_sha256"] = lock["sha256"]
    if contract["identity"]["dataset_id"] != sequence.dataset_id:
        raise RuntimeError("Contract and selected sequence disagree")
    return contract, sources


def reference_inputs(local_config):
    """Resolve only explicitly frozen provider metadata, never NAV or metrics."""
    local = load_yaml_mapping(local_config)["paths"]
    clean = Path(local["clean_root"]).resolve(strict=True)
    raw = Path(local["raw_root"]).resolve(strict=True)
    if clean == raw or raw in clean.parents or clean in raw.parents:
        raise RuntimeError("Reference metadata roots overlap raw data")
    def reference_path(value, parent):
        from .probes import reject_forbidden_path
        reject_forbidden_path(value)
        return guard_path(value, role="frozen C-03 reference", allowed_root=parent,
                          must_exist=True, regular_file=True)
    gate_path = reference_path(local["base_provider_gate"], clean)
    gate = json.loads(gate_path.read_text(encoding="utf-8"))
    if gate.get("passed") is not True:
        raise RuntimeError("CLEAN2R2A1 provider reference gate is not PASS")
    root = guard_path(gate["active_provider_root"], role="sealed BY2 provider root", allowed_root=clean, must_exist=True)
    configured = guard_path(local["base_provider_root"], role="configured BY2 provider root", allowed_root=clean, must_exist=True)
    if root != configured:
        raise RuntimeError("Frozen provider reference root differs from the local configured root")
    parity_path = reference_path(root / "CLEAN2R2A_BASE_PROVIDER_PARITY.json", root)
    parity = json.loads(parity_path.read_text(encoding="utf-8"))
    common_path = reference_path(parity["clean_input_manifest_path"], root)
    aux_path = reference_path(parity["auxiliary_manifest_path"], root)
    if sha256_file(common_path) != parity["clean_input_manifest_sha256"] or sha256_file(aux_path) != parity["auxiliary_manifest_sha256"]:
        raise RuntimeError("Frozen reference provider manifest SHA mismatch")
    common = json.loads(common_path.read_text(encoding="utf-8"))
    aux = json.loads(aux_path.read_text(encoding="utf-8"))
    paths = {role + "_runtime_input": reference_path(common_path.parent / common["artifacts"][role]["relative_path"], common_path.parent) for role in ("imu", "gnss")}
    for role, old in (("raw_doppler_provider", "raw_doppler_provider"), ("go2_attitude_prior", "go2_attitude_prior"),
                      ("go2_horizontal_velocity_prior", "go2_horizontal_velocity_prior")):
        paths[role] = reference_path(aux["auxiliary_artifacts"][old]["path"], aux_path.parent)
    # Prefer an explicit local pinned root, then the source recorded by the sealed helper command.
    explicit = local.get("clean5_rtklib_source_root") or local.get("rtklib_source_root")
    command = aux["raw_doppler_backend"]["helper_compile_command"]
    recorded = Path(command[command.index("-I") + 1]).parent
    rtklib = Path(explicit) if explicit else (recorded if recorded.is_dir() else None)
    if rtklib is not None:
        rtklib = guard_path(rtklib, role="pinned RTKLIB source", allowed_root=rtklib, must_exist=True)
        if rtklib == raw or raw in rtklib.parents:
            raise RuntimeError("Pinned toolchain must not be inside raw_root")
    return paths, gate_path, rtklib


def checkpoint_worker(registry, sequence, audit_dir):
    checkpoint(registry, sequence, "pre_generation", audit_dir)
    print("PRE_GENERATION_PASS", flush=True)
    if sys.stdin.readline().strip() != "POST_GENERATION":
        raise RuntimeError("Checkpoint worker did not receive the post-generation signal")
    checkpoint(registry, sequence, "post_generation", audit_dir)
    print("POST_GENERATION_PASS", flush=True)


def generation_worker(args, registry, sequence, audit_dir):
    from .probes import forbidden_path_guard

    allowed = {registry.raw_root / rel for rel in selected_lock(registry, sequence)["rows"]
               if not Path(rel).name.startswith("trace_") and not rel.endswith((".bag", ".fpl"))}
    with forbidden_path_guard(registry.raw_root, allowed):
        from .provider_chain import generate_sequence_payloads

        state = code_freeze_state(registry.code_root, args.code_freeze_commit)
        contract, _ = load_generation_contract(registry, sequence)
        lock = selected_lock(registry, sequence)
        pre = json.loads((audit_dir / "pre_generation_CHECKPOINT.json").read_text())
        validate_checkpoint(pre, phase="pre_generation", lock=lock)
        _, _, rtklib = reference_inputs(args.paths_config)
        result = generate_sequence_payloads(registry, sequence, contract,
                                            stage_root(registry, sequence) / "02_PROVIDER_FREEZE",
                                            rtklib_root=rtklib)
        if code_freeze_state(registry.code_root, args.code_freeze_commit) != state:
            raise RuntimeError("Code freeze changed during provider generation")
        write_json_exclusive(audit_dir / "GENERATION_RESULT.json", result)


def supervise(args, registry, sequence):
    state = code_freeze_state(registry.code_root, args.code_freeze_commit)
    contract, sources = load_generation_contract(registry, sequence)
    stage = stage_root(registry, sequence)
    out = stage / "02_PROVIDER_FREEZE"
    audit_dir = stage / "01_PROVIDER_GENERATION_AUDIT"
    if out.exists() or audit_dir.exists() or (stage / "03_RUNTIME_CONFIGS").exists():
        raise FileExistsError("C-03 output already exists; refusing overwrite or automatic retry")
    require_generation_order(registry, sequence, state)
    audit_dir.mkdir(parents=True, exist_ok=False)
    checkpoint_log = audit_dir / "CHECKPOINT_OPENAT.strace"
    generation_log = audit_dir / "GENERATION_OPENAT.strace"
    script = registry.code_root / "scripts/paper_rebuild/clean5_generate_providers.py"
    base = [sys.executable, "-B", str(script), "--sequence", sequence.dataset_id,
            "--paths-config", str(args.paths_config), "--registry", str(args.registry),
            "--code-root", str(registry.code_root), "--code-freeze-commit", args.code_freeze_commit]
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
    traced = lambda log, phase: ["strace", "-f", "-s", "4096", "-yy", "-e", "trace=openat", "-o", str(log), *base, "--_worker", phase]
    generation_return = None
    checkpoint_return = None
    with (audit_dir / "CHECKPOINT_PROCESS.log").open("x", encoding="utf-8") as stderr:
        process = subprocess.Popen(traced(checkpoint_log, "checkpoint"), cwd=registry.code_root, env=env,
                                   stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=stderr, text=True)
        ready = process.stdout.readline().strip()
        if ready != "PRE_GENERATION_PASS":
            process.wait()
            raise RuntimeError("Pre-generation checkpoint failed; generation not started")
        print(f"{sequence.dataset_id}: pre-generation 22/22 PASS", flush=True)
        try:
            with (audit_dir / "GENERATION_PROCESS.log").open("x", encoding="utf-8") as generation_stdout:
                run = subprocess.run(traced(generation_log, "generation"), cwd=registry.code_root, env=env,
                                     stdout=generation_stdout, stderr=subprocess.STDOUT, check=False)
                generation_return = run.returncode
        finally:
            process.stdin.write("POST_GENERATION\n")
            process.stdin.flush()
            remaining, _ = process.communicate()
            checkpoint_return = process.returncode
            print(f"{sequence.dataset_id}: {remaining.strip()}", flush=True)
    checkpoint_audit = audit_checkpoint_session(checkpoint_log, registry, sequence, audit_dir)
    allowed = {registry.raw_root / rel for rel in selected_lock(registry, sequence)["rows"]
               if not Path(rel).name.startswith("trace_") and not rel.endswith((".bag", ".fpl"))}
    generation_audit = audit_records(open_records(generation_log, registry.code_root), registry.raw_root, allowed,
                                     checkpoint_phase=False)
    generation_audit.update(strace_pass=generation_audit["pass"], worker_exit_code=generation_return,
                            strace_sha256=sha256_file(generation_log), session_count=1)
    generation_audit["pass"] = generation_audit["strace_pass"] and generation_return == 0
    checkpoint_audit["strace_pass"] = checkpoint_audit["pass"]
    checkpoint_audit["worker_exit_code"] = checkpoint_return
    checkpoint_audit["pass"] = checkpoint_audit["strace_pass"] and checkpoint_return == 0
    write_json_exclusive(audit_dir / "CHECKPOINT_PHASE_STRACE_AUDIT.json", checkpoint_audit)
    write_json_exclusive(audit_dir / "GENERATION_PHASE_STRACE_AUDIT.json", generation_audit)
    if checkpoint_return or not checkpoint_audit["strace_pass"] or not generation_audit["strace_pass"]:
        raise RuntimeError("C-03 checkpoint/strace gate FAILED; see phase audits")
    if generation_return:
        raise RuntimeError("C-03 generation/physical gate FAILED; see GENERATION_PROCESS.log and YAW_PHYSICAL_GATE.json")
    result = json.loads((audit_dir / "GENERATION_RESULT.json").read_text())
    refs, _, _ = reference_inputs(args.paths_config)
    parity = None
    if sequence.dataset_id == "BY2":
        from .provider_parity import validate_by2_parity

        parity = validate_by2_parity(result, refs, registry.code_root, out / "BY2_PROVIDER_PARITY_GATE.json")
    pre = json.loads((audit_dir / "pre_generation_CHECKPOINT.json").read_text())
    post = json.loads((audit_dir / "post_generation_CHECKPOINT.json").read_text())
    if pre["verified_hashes"] != post["verified_hashes"] or code_freeze_state(registry.code_root, args.code_freeze_commit) != state:
        raise RuntimeError("Raw or code identity changed during generation")
    manifest = {**result, **state, "status": "PASS_PROVIDER_FREEZE", "dataset_id": sequence.dataset_id,
                "stage_id": stage.name, "data_mode": sequence.data_mode, "contract_paths_sha256": sources,
                "code_commit": state["code_freeze_commit"],
                "config_hash": sha256(json.dumps(contract, sort_keys=True, separators=(",", ":"),
                                                   allow_nan=False).encode("utf-8")).hexdigest(),
                "paths_config_sha256": sha256_file(args.paths_config),
                "sequence_registry_sha256": sha256_file(args.registry),
                "frozen_executable": args.frozen_executable,
                "raw_source_hashes": pre["verified_hashes"], "pre_generation": pre, "post_generation": post,
                "base_time": contract["time_contract"]["base_time"],
                "utc_day_midnight": contract["time_contract"]["utc_day_midnight"],
                "auxiliary_rebase_offset_seconds": contract["time_contract"]["auxiliary_rebase_offset_seconds"],
                "window": {k: contract["window_contract"][k] for k in ("t_start", "t_end")},
                "window_used_to_generate_providers": False, "trace_used_during_generation": False,
                "trace_used_online": False, "synthetic_data_used": False, "semisynthetic_data_used": False,
                "per_sequence_tuning": False, "per_case_tuning": False, "epoch_deleted_for_metric": False,
                "output_only_correction": False, "receiver_imu_as_body_imu": False,
                "final_v23_output_solver_input": False, "LegSA_output_solver_input": False,
                "old_runtime_input_count": 0, "solver_process_count": 0, "evaluator_process_count": 0,
                "checkpoint_phase_audit": checkpoint_audit, "generation_phase_audit": generation_audit,
                "audit_paths_sha256": {str(p.relative_to(stage)): sha256_file(p) for p in sorted(audit_dir.glob("*.json"))}}
    if parity is not None:
        manifest["by2_provider_parity_gate"] = parity
    if sequence.dataset_id == "BY2O":
        window_path = stage / "01_SEQUENCE_CONTRACT/OCCLUSION_WINDOW.json"
        window = json.loads(window_path.read_text())
        if window["main_window"] != contract["occlusion_window"]["main_window"]:
            raise RuntimeError("Pre-registered BY2O window changed")
        manifest["occlusion_window"] = {"path": str(window_path), "sha256": sha256_file(window_path),
                                        "main_window": window["main_window"]}
    write_json_exclusive(out / "PROVIDER_MANIFEST.json", manifest)
    print(f"{sequence.dataset_id}: provider freeze PASS", flush=True)
    print(json.dumps({"dataset_id": sequence.dataset_id, "provider_manifest_sha256": sha256_file(out / "PROVIDER_MANIFEST.json"),
                      "code_freeze_commit": state["code_freeze_commit"], "provider_freeze": "PASS",
                      "by2_provider_parity_gate": parity, "runtime_configs_rendered": False},
                     ensure_ascii=False, indent=2), flush=True)
    return 0


def render_only(args, registry):
    """Render both sequences together only after the three provider freezes PASS."""
    from .runtime_config import RuntimeConfigError, render_joint_runtime_configs

    state = code_freeze_state(registry.code_root, args.code_freeze_commit)
    manifests = {dataset: require_provider_freeze(registry, dataset, state)
                 for dataset in ("BY2", "BY2H", "BY2O")}
    if any(item.get("frozen_executable") != args.frozen_executable for item in manifests.values()):
        raise RuntimeError("Provider manifests disagree with the frozen executable identity")
    contracts, outputs = {}, {}
    for dataset in ("BY2H", "BY2O"):
        sequence = registry.sequences[dataset]
        contract, sources = load_generation_contract(registry, sequence)
        if manifests[dataset]["contract_paths_sha256"] != sources:
            raise RuntimeError(f"{dataset} contract changed after its provider freeze")
        contracts[dataset] = contract
        stage = stage_root(registry, sequence)
        outputs[dataset] = stage / "03_RUNTIME_CONFIGS"
        if outputs[dataset].exists() or (stage / "01_PROVIDER_GENERATION_AUDIT/RUNTIME_CONFIG_FAILURE.json").exists():
            raise FileExistsError("C-03 runtime rendering already attempted; refusing overwrite or retry")
    _, reference_gate, _ = reference_inputs(args.paths_config)
    try:
        report = render_joint_runtime_configs(
            contracts=contracts, provider_manifests={key: manifests[key] for key in contracts},
            base_provider_gate=reference_gate, output_dirs=outputs, code_root=registry.code_root)
        if code_freeze_state(registry.code_root, args.code_freeze_commit) != state:
            raise RuntimeError("Code freeze changed during runtime rendering")
    except Exception as exc:
        failure = {"status": "FAIL_RUNTIME_CONFIG_DIFF" if isinstance(exc, RuntimeConfigError) else "FAIL_RUNTIME_CONFIG_RENDER",
                   "error": str(exc), "method_id": getattr(exc, "method_id", None),
                   "differences": getattr(exc, "details", None), **state}
        for dataset in contracts:
            audit = stage_root(registry, registry.sequences[dataset]) / "01_PROVIDER_GENERATION_AUDIT"
            write_json_exclusive(audit / "RUNTIME_CONFIG_FAILURE.json", failure)
        raise
    print(json.dumps({"runtime_config_report": report, "frozen_executable": args.frozen_executable,
                      **state}, ensure_ascii=False, indent=2), flush=True)
    return 0


def main(argv=None, *, execution_script=None):
    repo = Path(__file__).resolve().parents[4]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sequence", choices=("BY2", "BY2H", "BY2O"))
    parser.add_argument("--render-only", action="store_true", help="Render BY2H and BY2O together after all three provider gates PASS")
    parser.add_argument("--code-root", type=Path, required=True)
    parser.add_argument("--code-freeze-commit", required=True)
    parser.add_argument("--paths-config", type=Path, required=True)
    parser.add_argument("--registry", type=Path, default=repo / "configs/paper_rebuild/clean5/CLEAN5_SEQUENCE_REGISTRY.yaml")
    parser.add_argument("--_worker", choices=("checkpoint", "generation"), help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if args.render_only and (args.sequence or args._worker):
        parser.error("--render-only accepts neither --sequence nor --_worker; both sequences are rendered jointly")
    if not args.render_only and not args.sequence:
        parser.error("--sequence is required for provider generation")
    try:
        sys.dont_write_bytecode = True
        registry = load_registry(args.registry, args.paths_config)
        registry, _, args.frozen_executable = execution_registry(
            registry, code_root=args.code_root, code_freeze_commit=args.code_freeze_commit,
            execution_script=execution_script if execution_script is not None else sys.argv[0])
        args.paths_config = args.paths_config.resolve(strict=True)
        args.registry = args.registry.resolve(strict=True)
        if registry.code_root not in args.registry.parents:
            raise RuntimeError("Sequence registry must come from the execution code freeze")
        if args.render_only:
            return render_only(args, registry)
        sequence = registry.sequences[args.sequence]
        audit_dir = stage_root(registry, sequence) / "01_PROVIDER_GENERATION_AUDIT"
        if args._worker == "checkpoint":
            checkpoint_worker(registry, sequence, audit_dir)
        elif args._worker == "generation":
            generation_worker(args, registry, sequence, audit_dir)
        else:
            return supervise(args, registry, sequence)
    except Exception as exc:
        print(f"FAIL {type(exc).__name__}: {exc}", file=sys.stderr, flush=True)
        if args._worker:
            raise
        return 2
    return 0
