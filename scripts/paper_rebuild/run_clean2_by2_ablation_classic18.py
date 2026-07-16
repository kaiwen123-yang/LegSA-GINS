#!/usr/bin/env python3
"""Build the 110-run registry, materialize configs, execute phases, or seal outputs."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from legsa_gins.paper_rebuild.clean2_evidence import seal_formal_outputs
from legsa_gins.paper_rebuild.clean2_run_registry import build_and_write_run_registry
from legsa_gins.paper_rebuild.clean2_runner import (
    _load_case_provider_index,
    create_executable_source_manifest,
    execute_prepared_phase,
    freeze_clean1_structural_reference,
    materialize_runtime_configs,
    produce_structural_gate,
    validate_executable_source_manifest,
    write_terminal_attempt_audit,
)
from legsa_gins.paper_rebuild.clean2_stage_paths import (
    guard_clean2_stage_path,
    load_clean2_stage_paths,
)
from legsa_gins.paper_rebuild.manifest import sha256_file


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    freeze = commands.add_parser("freeze-executable")
    freeze.add_argument("--local-config", required=True)
    freeze.add_argument("--executable", required=True)
    freeze.add_argument("--code-root", default=str(REPO_ROOT))
    freeze.add_argument("--expected-code-freeze-commit", required=True)
    freeze.add_argument("--output", required=True)
    reference = commands.add_parser("freeze-clean1-reference")
    reference.add_argument("--local-config", required=True)
    reference.add_argument("--clean1-evidence-root", required=True)
    reference.add_argument("--output", required=True)
    registry = commands.add_parser("build-registry")
    registry.add_argument("--local-config", required=True)
    registry.add_argument("--ablation", default=str(REPO_ROOT / "configs/paper_rebuild/clean2_ablation_2pow4.yaml"))
    registry.add_argument("--mapping", default=str(REPO_ROOT / "configs/paper_rebuild/clean2_classic18_active_mapping.yaml"))
    registry.add_argument("--case-provider-index", required=True)
    registry.add_argument("--executable", required=True)
    registry.add_argument("--executable-source-manifest", required=True)
    registry.add_argument("--code-root", default=str(REPO_ROOT))
    registry.add_argument("--expected-code-freeze-commit", required=True)
    registry.add_argument("--output", required=True)
    materialize = commands.add_parser("materialize-configs")
    materialize.add_argument("--local-config", required=True)
    materialize.add_argument("--registry", required=True)
    materialize.add_argument("--base-runtime-config", required=True)
    materialize.add_argument("--case-provider-index", required=True)
    materialize.add_argument("--methods", default=str(REPO_ROOT / "configs/paper_rebuild/methods.yaml"))
    materialize.add_argument("--runtime-root", required=True)
    materialize.add_argument("--code-root", default=str(REPO_ROOT))
    materialize.add_argument("--expected-code-freeze-commit", required=True)
    materialize.add_argument("--executable", required=True)
    materialize.add_argument("--executable-source-manifest", required=True)
    materialize.add_argument("--parity-contract", default=str(REPO_ROOT / "configs/paper_rebuild/final_v23_parity_contract.yaml"))
    materialize.add_argument("--clean1-protocol", default=str(REPO_ROOT / "configs/paper_rebuild/clean1_by2_clean_protocol.yaml"))
    materialize.add_argument("--clean2-formal-schema", default=str(REPO_ROOT / "configs/paper_rebuild/clean2_formal_manifest_schema.yaml"))
    materialize.add_argument("--historical-formal-schema", default=str(REPO_ROOT / "configs/paper_rebuild/formal_manifest_schema.yaml"))
    execute = commands.add_parser("execute-phase")
    execute.add_argument("--local-config", required=True)
    execute.add_argument("--registry", required=True)
    execute.add_argument("--runtime-root", required=True)
    execute.add_argument("--executable", required=True)
    execute.add_argument("--phase", choices=("structural_gate", "factorial_remaining", "controlled_canonical", "sentinel_loo"), required=True)
    execute.add_argument("--attempts", required=True)
    execute.add_argument("--jobs", type=int, default=8)
    execute.add_argument("--timeout-seconds", type=int, default=900)
    execute.add_argument("--structural-gate-report")
    execute.add_argument("--clean1-reference-index")
    execute.add_argument("--parity-contract", default=str(REPO_ROOT / "configs/paper_rebuild/final_v23_parity_contract.yaml"))
    execute.add_argument("--case-provider-index", required=True)
    execute.add_argument("--code-root", default=str(REPO_ROOT))
    execute.add_argument("--expected-code-freeze-commit", required=True)
    execute.add_argument("--executable-source-manifest", required=True)
    gate = commands.add_parser("produce-structural-gate")
    gate.add_argument("--local-config", required=True)
    gate.add_argument("--registry", required=True)
    gate.add_argument("--runtime-root", required=True)
    gate.add_argument("--executable", required=True)
    gate.add_argument("--executable-source-manifest", required=True)
    gate.add_argument("--case-provider-index", required=True)
    gate.add_argument("--code-root", default=str(REPO_ROOT))
    gate.add_argument("--expected-code-freeze-commit", required=True)
    gate.add_argument("--clean1-reference-index", required=True)
    gate.add_argument("--parity-contract", default=str(REPO_ROOT / "configs/paper_rebuild/final_v23_parity_contract.yaml"))
    gate.add_argument("--output", required=True)
    seal = commands.add_parser("seal-outputs")
    seal.add_argument("--local-config", required=True)
    seal.add_argument("--registry", required=True)
    seal.add_argument("--runtime-root", required=True)
    seal.add_argument("--output", required=True)
    attempts_audit = commands.add_parser("audit-attempts")
    attempts_audit.add_argument("--local-config", required=True)
    attempts_audit.add_argument("--registry", required=True)
    attempts_audit.add_argument("--attempts", required=True)
    attempts_audit.add_argument("--output", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    stage = load_clean2_stage_paths(args.local_config)

    def guarded(
        value: str | Path,
        *,
        slot: str,
        role: str,
        exact_name: str | None = None,
        must_exist: bool = False,
    ) -> Path:
        return guard_clean2_stage_path(
            stage,
            value,
            slot=slot,
            role=role,
            exact_name=exact_name,
            must_exist=must_exist,
            regular_file=must_exist and exact_name is not None,
        )

    def tracked_config(value: str | Path, relative: str) -> Path:
        expected = (stage.clean.code_root / relative).resolve(strict=True)
        actual = Path(value).resolve(strict=True)
        if actual != expected:
            raise SystemExit(f"CLEAN2 formal config must use tracked path: {relative}")
        return actual

    if hasattr(args, "code_root") and Path(args.code_root).resolve(strict=True) != stage.clean.code_root:
        raise SystemExit("CLEAN2 code root differs from ignored local config")
    if hasattr(args, "executable"):
        expected_executable = (
            stage.clean.code_root / "build/clean2_cpp/legsa_v23_port_core_demo"
        ).resolve(strict=True)
        if Path(args.executable).resolve(strict=True) != expected_executable:
            raise SystemExit("CLEAN2 formal executable must be build/clean2_cpp/legsa_v23_port_core_demo")
    if args.command == "freeze-executable":
        output = guarded(
            args.output,
            slot="git_freeze",
            role="CLEAN2 executable/source manifest",
            exact_name="CLEAN2_EXECUTABLE_SOURCE_MANIFEST.json",
        )
        result = create_executable_source_manifest(
            output_path=output,
            code_root=args.code_root,
            executable=args.executable,
            expected_code_commit=args.expected_code_freeze_commit,
        )
    elif args.command == "freeze-clean1-reference":
        output = guarded(
            args.output,
            slot="git_freeze",
            role="CLEAN1 structural reference index",
            exact_name="CLEAN1R2R1_STRUCTURAL_REFERENCE.json",
        )
        result = freeze_clean1_structural_reference(
            evidence_root=args.clean1_evidence_root,
            output_path=output,
        )
    elif args.command == "build-registry":
        ablation = tracked_config(
            args.ablation, "configs/paper_rebuild/clean2_ablation_2pow4.yaml"
        )
        mapping = tracked_config(
            args.mapping, "configs/paper_rebuild/clean2_classic18_active_mapping.yaml"
        )
        case_index = guarded(
            args.case_provider_index,
            slot="case_providers",
            role="Classic-18 provider index",
            exact_name="CLASSIC18_PROVIDER_INDEX.json",
            must_exist=True,
        )
        executable_manifest = guarded(
            args.executable_source_manifest,
            slot="git_freeze",
            role="CLEAN2 executable/source manifest",
            exact_name="CLEAN2_EXECUTABLE_SOURCE_MANIFEST.json",
            must_exist=True,
        )
        output = guarded(
            args.output,
            slot="run_registry",
            role="CLEAN2 run registry",
            exact_name="CLEAN2_RUN_REGISTRY.csv",
        )
        validate_executable_source_manifest(
            executable_manifest,
            code_root=args.code_root,
            executable=args.executable,
            expected_code_commit=args.expected_code_freeze_commit,
        )
        index, _ = _load_case_provider_index(
            case_index, expected_code_commit=args.expected_code_freeze_commit
        )
        hashes = {row["case_id"]: row["provider_bundle_hash"] for row in index["cases"]}
        rows = build_and_write_run_registry(
            ablation_config=ablation,
            classic_mapping_config=mapping,
            provider_bundle_hashes=hashes,
            executable_hash=sha256_file(args.executable),
            output_path=output,
        )
        result = {"unique_run_count": len(rows), "duplicate_effective_config_count": 0}
    elif args.command == "materialize-configs":
        methods = tracked_config(args.methods, "configs/paper_rebuild/methods.yaml")
        parity = tracked_config(
            args.parity_contract, "configs/paper_rebuild/final_v23_parity_contract.yaml"
        )
        clean1_protocol = tracked_config(
            args.clean1_protocol, "configs/paper_rebuild/clean1_by2_clean_protocol.yaml"
        )
        clean2_schema = tracked_config(
            args.clean2_formal_schema,
            "configs/paper_rebuild/clean2_formal_manifest_schema.yaml",
        )
        historical_schema = tracked_config(
            args.historical_formal_schema,
            "configs/paper_rebuild/formal_manifest_schema.yaml",
        )
        registry = guarded(args.registry, slot="run_registry", role="CLEAN2 run registry", exact_name="CLEAN2_RUN_REGISTRY.csv", must_exist=True)
        case_index = guarded(args.case_provider_index, slot="case_providers", role="Classic-18 provider index", exact_name="CLASSIC18_PROVIDER_INDEX.json", must_exist=True)
        executable_manifest = guarded(args.executable_source_manifest, slot="git_freeze", role="CLEAN2 executable/source manifest", exact_name="CLEAN2_EXECUTABLE_SOURCE_MANIFEST.json", must_exist=True)
        runtime_root = guarded(args.runtime_root, slot="formal_runs", role="CLEAN2 formal runtime root")
        if runtime_root != stage.slot("formal_runs"):
            raise SystemExit("CLEAN2 formal runtime must use exact stage slot 07")
        rows = materialize_runtime_configs(
            registry_path=registry,
            base_runtime_config=args.base_runtime_config,
            case_provider_index=case_index,
            methods_config=methods,
            runtime_root=runtime_root,
            code_root=args.code_root,
            expected_code_freeze_commit=args.expected_code_freeze_commit,
            executable=args.executable,
            executable_source_manifest=executable_manifest,
            parity_contract=parity,
            clean1_protocol=clean1_protocol,
            clean2_formal_schema=clean2_schema,
            historical_formal_schema=historical_schema,
        )
        result = {"runtime_config_count": len(rows), "trace_read_count": 0}
    elif args.command == "execute-phase":
        parity = tracked_config(
            args.parity_contract, "configs/paper_rebuild/final_v23_parity_contract.yaml"
        )
        registry = guarded(args.registry, slot="run_registry", role="CLEAN2 run registry", exact_name="CLEAN2_RUN_REGISTRY.csv", must_exist=True)
        case_index = guarded(args.case_provider_index, slot="case_providers", role="Classic-18 provider index", exact_name="CLASSIC18_PROVIDER_INDEX.json", must_exist=True)
        executable_manifest = guarded(args.executable_source_manifest, slot="git_freeze", role="CLEAN2 executable/source manifest", exact_name="CLEAN2_EXECUTABLE_SOURCE_MANIFEST.json", must_exist=True)
        runtime_root = guarded(args.runtime_root, slot="formal_runs", role="CLEAN2 formal runtime root", must_exist=True)
        attempts = guarded(args.attempts, slot="run_registry", role="CLEAN2 attempt ledger", exact_name="CLEAN2_RUN_ATTEMPTS.csv")
        structural_gate = None
        clean1_reference = None
        if args.structural_gate_report:
            structural_gate = guarded(args.structural_gate_report, slot="audits", role="CLEAN2 structural gate", exact_name="CLEAN2_C00_STRUCTURAL_GATE.json", must_exist=True)
        if args.clean1_reference_index:
            clean1_reference = guarded(args.clean1_reference_index, slot="git_freeze", role="CLEAN1 structural reference", exact_name="CLEAN1R2R1_STRUCTURAL_REFERENCE.json", must_exist=True)
        rows = execute_prepared_phase(
            registry_path=registry,
            runtime_root=runtime_root,
            executable=args.executable,
            phase=args.phase,
            attempts_path=attempts,
            jobs=args.jobs,
            timeout_seconds=args.timeout_seconds,
            structural_gate_report=structural_gate,
            code_root=args.code_root,
            raw_root=stage.clean.raw_root,
            expected_code_freeze_commit=args.expected_code_freeze_commit,
            executable_source_manifest=executable_manifest,
            case_provider_index=case_index,
            clean1_reference_index=clean1_reference,
            parity_contract=parity,
        )
        result = {"phase": args.phase, "terminal_pass_count": len(rows), "performance_metric_read": False}
    elif args.command == "produce-structural-gate":
        parity = tracked_config(
            args.parity_contract, "configs/paper_rebuild/final_v23_parity_contract.yaml"
        )
        registry = guarded(args.registry, slot="run_registry", role="CLEAN2 run registry", exact_name="CLEAN2_RUN_REGISTRY.csv", must_exist=True)
        runtime_root = guarded(args.runtime_root, slot="formal_runs", role="CLEAN2 formal runtime root", must_exist=True)
        executable_manifest = guarded(args.executable_source_manifest, slot="git_freeze", role="CLEAN2 executable/source manifest", exact_name="CLEAN2_EXECUTABLE_SOURCE_MANIFEST.json", must_exist=True)
        case_index = guarded(args.case_provider_index, slot="case_providers", role="Classic-18 provider index", exact_name="CLASSIC18_PROVIDER_INDEX.json", must_exist=True)
        clean1_reference = guarded(args.clean1_reference_index, slot="git_freeze", role="CLEAN1 structural reference", exact_name="CLEAN1R2R1_STRUCTURAL_REFERENCE.json", must_exist=True)
        output = guarded(args.output, slot="audits", role="CLEAN2 structural gate", exact_name="CLEAN2_C00_STRUCTURAL_GATE.json")
        result = produce_structural_gate(
            output,
            registry_path=registry,
            runtime_root=runtime_root,
            executable=args.executable,
            executable_source_manifest=executable_manifest,
            case_provider_index=case_index,
            code_root=args.code_root,
            expected_code_freeze_commit=args.expected_code_freeze_commit,
            clean1_reference_index=clean1_reference,
            parity_contract=parity,
        )
    elif args.command == "seal-outputs":
        registry = guarded(args.registry, slot="run_registry", role="CLEAN2 run registry", exact_name="CLEAN2_RUN_REGISTRY.csv", must_exist=True)
        runtime_root = guarded(args.runtime_root, slot="formal_runs", role="CLEAN2 formal runtime root", must_exist=True)
        output = guarded(args.output, slot="output_seal", role="CLEAN2 complete output seal", exact_name="CLEAN2_COMPLETE_OUTPUT_SEAL.json")
        result = seal_formal_outputs(registry_path=registry, runtime_root=runtime_root, output_path=output)
    else:
        registry = guarded(args.registry, slot="run_registry", role="CLEAN2 run registry", exact_name="CLEAN2_RUN_REGISTRY.csv", must_exist=True)
        attempts = guarded(args.attempts, slot="run_registry", role="CLEAN2 attempt ledger", exact_name="CLEAN2_RUN_ATTEMPTS.csv", must_exist=True)
        output = guarded(args.output, slot="audits", role="CLEAN2 terminal attempt audit", exact_name="CLEAN2_RUN_ATTEMPTS_AUDIT.json")
        result = write_terminal_attempt_audit(registry_path=registry, attempts_path=attempts, output_path=output)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
