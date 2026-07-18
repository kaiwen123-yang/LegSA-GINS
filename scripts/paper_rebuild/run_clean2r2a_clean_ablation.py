#!/usr/bin/env python3
"""Run only the CLEAN2R2A 18-configuration BY2 clean ablation."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from legsa_gins.paper_rebuild.clean2r2a_evidence import initialize_stage_documents
from legsa_gins.paper_rebuild.clean2r2a_run_registry import build_clean_run_registry
from legsa_gins.paper_rebuild.clean2r2a_runner import (
    AB_IDS,
    PROTOCOL_ID,
    STAGE_ID,
    STRUCTURAL_ORDER,
    audit_base_provider_parity,
    run_methods,
    seal_outputs,
    structural_parity_gate,
    validate_canonical_provider_protocol,
)
from legsa_gins.paper_rebuild.clean1r2r1_formal import (
    generate_fresh_auxiliaries,
    seal_auxiliary_file_open_audit,
)
from legsa_gins.paper_rebuild.evidence import verify_by2_raw_22, write_raw_audit
from legsa_gins.paper_rebuild.final_v23_clean_input import (
    EXPECTED_RAW_LOCK_SHA256,
    generate_final_v23_clean_input,
    load_raw_checkpoint,
    raw_checkpoint_from_audit,
    seal_clean_input_file_open_audit,
    seal_clean_input_post_raw_checkpoint,
)
from legsa_gins.paper_rebuild.manifest import write_json_atomic
from legsa_gins.paper_rebuild.paths import load_clean_paths, load_yaml_mapping


DEFAULT_PARITY_CONTRACT = REPO_ROOT / "configs/paper_rebuild/final_v23_parity_contract.yaml"


def _clean2r2a_paths(config: str):
    """Reject path substitution outside the exact CLEAN2R2A stage tree."""

    raw_config = load_yaml_mapping(config)
    raw_paths = raw_config.get("paths")
    if not isinstance(raw_paths, dict):
        raise ValueError("local paths mapping is missing")
    for key in ("provider_root", "runtime_root"):
        candidate = Path(str(raw_paths.get(key, ""))).expanduser()
        if any(path.is_symlink() for path in (candidate, *candidate.parents)):
            raise ValueError(f"{key} contains a symlink component")
    paths = load_clean_paths(config)
    expected_stage = (
        paths.clean_root / "stages" / STAGE_ID
    ).resolve(strict=False)
    expected_provider = (expected_stage / "04_BASE_PROVIDER").resolve(strict=False)
    expected_runtime = (expected_stage / "06_FORMAL_RUNS").resolve(strict=False)
    if paths.provider_root.resolve(strict=False) != expected_provider:
        raise ValueError("provider_root is not the exact CLEAN2R2A 04_BASE_PROVIDER")
    if paths.runtime_root.resolve(strict=False) != expected_runtime:
        raise ValueError("runtime_root is not the exact CLEAN2R2A 06_FORMAL_RUNS")
    return paths


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    commands = result.add_subparsers(dest="command", required=True)
    init = commands.add_parser("initialize-stage")
    init.add_argument("--stage-root", required=True); init.add_argument("--code-freeze-commit", required=True)
    registry = commands.add_parser("write-registry")
    registry.add_argument("--contract", required=True); registry.add_argument("--output", required=True)
    raw = commands.add_parser("raw-audit")
    raw.add_argument("--config", required=True); raw.add_argument("--audit-phase", required=True)
    raw.add_argument("--csv", required=True); raw.add_argument("--json", required=True)
    raw_compare = commands.add_parser("compare-raw")
    raw_compare.add_argument("--pre", required=True); raw_compare.add_argument("--post", required=True)
    raw_compare.add_argument("--output", required=True)
    base = commands.add_parser("generate-base")
    base.add_argument("--config", required=True); base.add_argument("--output-root", required=True)
    base.add_argument("--raw-pre-checkpoint", required=True); base.add_argument("--expected-code-commit", required=True)
    base.add_argument("--contract", default=str(DEFAULT_PARITY_CONTRACT))
    base_trace = commands.add_parser("seal-base-trace")
    base_trace.add_argument("--config", required=True); base_trace.add_argument("--manifest", required=True)
    base_trace.add_argument("--strace", required=True)
    base_post = commands.add_parser("seal-base-post")
    base_post.add_argument("--config", required=True); base_post.add_argument("--manifest", required=True)
    base_post.add_argument("--raw-post-checkpoint", required=True)
    auxiliary = commands.add_parser("generate-auxiliaries")
    auxiliary.add_argument("--config", required=True); auxiliary.add_argument("--clean-input-manifest", required=True)
    auxiliary.add_argument("--output-root", required=True); auxiliary.add_argument("--expected-code-commit", required=True)
    auxiliary.add_argument("--provider-protocol", required=True); auxiliary.add_argument("--timeout-seconds", type=int, default=900)
    source = auxiliary.add_mutually_exclusive_group(required=True)
    source.add_argument("--rtklib-source-root"); source.add_argument("--materialize-pinned-rtklib", action="store_true")
    auxiliary_trace = commands.add_parser("seal-auxiliary-trace")
    auxiliary_trace.add_argument("--auxiliary-manifest", required=True); auxiliary_trace.add_argument("--strace", required=True)
    auxiliary_trace.add_argument("--raw-root", required=True); auxiliary_trace.add_argument("--code-root", default=str(REPO_ROOT))
    parity = commands.add_parser("provider-parity")
    parity.add_argument("--clean-input-manifest", required=True); parity.add_argument("--auxiliary-manifest", required=True)
    parity.add_argument("--output", required=True)
    for name in ("run-structural", "run-remaining"):
        run = commands.add_parser(name)
        run.add_argument("--repo-root", default=str(REPO_ROOT)); run.add_argument("--raw-root", required=True)
        run.add_argument("--executable", required=True); run.add_argument("--clean-input-manifest", required=True)
        run.add_argument("--auxiliary-manifest", required=True); run.add_argument("--provider-protocol", required=True)
        run.add_argument("--provider-parity-report", required=True)
        run.add_argument("--local-config", required=True)
        run.add_argument("--runtime-root", required=True); run.add_argument("--code-freeze-commit", required=True)
        run.add_argument("--timeout-seconds", type=int, default=1800)
    gate = commands.add_parser("structural-gate")
    gate.add_argument("--runtime-root", required=True); gate.add_argument("--clean1-runtime-root", required=True)
    seal = commands.add_parser("seal")
    seal.add_argument("--runtime-root", required=True)
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    if args.command == "initialize-stage":
        payload = initialize_stage_documents(stage_root=args.stage_root, repo_root=REPO_ROOT,
                                             code_freeze_commit=args.code_freeze_commit)
    elif args.command == "write-registry":
        rows = build_clean_run_registry(args.contract)
        output = Path(args.output); output.parent.mkdir(parents=True, exist_ok=True)
        with output.open("x", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)
        payload = {"row_count": len(rows), "unique": len({row["profile_identity_hash"] for row in rows})}
    elif args.command == "raw-audit":
        paths = _clean2r2a_paths(args.config)
        audit = verify_by2_raw_22(
            paths.raw_root,
            paths.raw_hash_lock,
            expected_lock_sha256=EXPECTED_RAW_LOCK_SHA256,
            audit_phase=args.audit_phase,
        )
        write_raw_audit(args.csv, audit)
        payload = raw_checkpoint_from_audit(audit)
        write_json_atomic(args.json, payload)
    elif args.command == "compare-raw":
        before = load_raw_checkpoint(args.pre)
        after = load_raw_checkpoint(args.post)
        before_hashes = before.get("verified_hashes")
        after_hashes = after.get("verified_hashes")
        if not isinstance(before_hashes, dict) or not isinstance(after_hashes, dict):
            raise ValueError("raw checkpoint hash maps are missing")
        unchanged = {
            key for key in before_hashes if before_hashes.get(key) == after_hashes.get(key)
        }
        changed = sorted((set(before_hashes) | set(after_hashes)) - unchanged)
        payload = {
            "schema_version": "paper_rebuild.clean2r2a_raw_mutation_audit.v1",
            "pre_checkpoint": str(Path(args.pre).resolve(strict=True)),
            "post_checkpoint": str(Path(args.post).resolve(strict=True)),
            "pre_verified": len(before_hashes), "post_verified": len(after_hashes),
            "changed_relative_paths": changed, "raw_mutation": len(changed),
            "passed": len(before_hashes) == len(after_hashes) == 22 and not changed,
        }
        if not payload["passed"]:
            raise ValueError("raw mutation audit failed")
        write_json_atomic(args.output, payload)
    elif args.command == "generate-base":
        paths = _clean2r2a_paths(args.config)
        payload = generate_final_v23_clean_input(
            paths,
            output_root=args.output_root,
            contract_path=args.contract,
            raw_pre_checkpoint=load_raw_checkpoint(args.raw_pre_checkpoint),
            expected_code_commit=args.expected_code_commit,
            provider_parent=paths.provider_root,
        )
    elif args.command == "seal-base-trace":
        paths = _clean2r2a_paths(args.config)
        payload = seal_clean_input_file_open_audit(
            args.manifest, strace_path=args.strace, raw_root=paths.raw_root,
            code_root=paths.code_root,
        )
    elif args.command == "seal-base-post":
        paths = _clean2r2a_paths(args.config)
        payload = seal_clean_input_post_raw_checkpoint(
            args.manifest,
            raw_post_checkpoint=load_raw_checkpoint(args.raw_post_checkpoint),
            raw_hash_lock_path=paths.raw_hash_lock,
        )
    elif args.command == "generate-auxiliaries":
        canonical_protocol = validate_canonical_provider_protocol(REPO_ROOT, args.provider_protocol)
        payload = generate_fresh_auxiliaries(
            _clean2r2a_paths(args.config),
            clean_input_manifest=args.clean_input_manifest,
            output_root=args.output_root,
            expected_code_commit=args.expected_code_commit,
            provider_protocol=canonical_protocol,
            rtklib_source_root=args.rtklib_source_root,
            materialize_pinned_rtklib=args.materialize_pinned_rtklib,
            timeout_seconds=args.timeout_seconds,
            evidence_stage_id=STAGE_ID,
            evidence_protocol_id=PROTOCOL_ID,
            expected_output_parent=_clean2r2a_paths(args.config).provider_root,
        )
    elif args.command == "seal-auxiliary-trace":
        payload = seal_auxiliary_file_open_audit(
            auxiliary_manifest=args.auxiliary_manifest,
            strace_path=args.strace,
            raw_root=args.raw_root,
            code_root=args.code_root,
        )
    elif args.command == "provider-parity":
        payload = audit_base_provider_parity(
            clean_input_manifest=args.clean_input_manifest,
            auxiliary_manifest=args.auxiliary_manifest,
            output_path=args.output,
        )
    elif args.command in {"run-structural", "run-remaining"}:
        methods = STRUCTURAL_ORDER if args.command == "run-structural" else tuple(item for item in AB_IDS if item not in {"AB0000", "AB1111"})
        payload = run_methods(methods=methods, repo_root=args.repo_root, raw_root=args.raw_root,
                              executable=args.executable, clean_input_manifest=args.clean_input_manifest,
                              auxiliary_manifest=args.auxiliary_manifest, provider_protocol=args.provider_protocol,
                              provider_parity_report=args.provider_parity_report,
                              local_config=args.local_config,
                              runtime_root=args.runtime_root, code_freeze_commit=args.code_freeze_commit,
                              timeout_seconds=args.timeout_seconds)
    elif args.command == "structural-gate":
        payload = structural_parity_gate(runtime_root=args.runtime_root, clean1_runtime_root=args.clean1_runtime_root)
    else:
        payload = seal_outputs(args.runtime_root)
    print(json.dumps(payload, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
