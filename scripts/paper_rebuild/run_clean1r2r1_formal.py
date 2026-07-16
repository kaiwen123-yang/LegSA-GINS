#!/usr/bin/env python3
"""Run CLEAN1R2R1 auxiliary generation, four methods, or offline evaluation."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from legsa_gins.paper_rebuild.clean1r2r1_formal import (
    Clean1R2R1FormalError,
    evaluate_four_methods_offline,
    generate_fresh_auxiliaries,
    run_four_methods,
    seal_auxiliary_file_open_audit,
)
from legsa_gins.paper_rebuild.paths import load_clean_paths


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    auxiliary = commands.add_parser("generate-auxiliaries")
    auxiliary.add_argument("--config", required=True)
    auxiliary.add_argument("--clean-input-manifest", required=True)
    auxiliary.add_argument("--output-root", required=True)
    auxiliary.add_argument("--expected-code-commit", required=True)
    auxiliary.add_argument("--provider-protocol", required=True)
    source = auxiliary.add_mutually_exclusive_group(required=True)
    source.add_argument("--rtklib-source-root")
    source.add_argument("--materialize-pinned-rtklib", action="store_true")
    auxiliary.add_argument("--timeout-seconds", type=int, default=900)

    seal = commands.add_parser("seal-auxiliary-trace")
    seal.add_argument("--auxiliary-manifest", required=True)
    seal.add_argument("--strace", required=True)
    seal.add_argument("--raw-root", required=True)
    seal.add_argument("--code-root", default=str(REPO_ROOT))

    run = commands.add_parser("run-four-methods")
    run.add_argument("--repo-root", default=str(REPO_ROOT))
    run.add_argument("--executable", required=True)
    run.add_argument("--clean-input-manifest", required=True)
    run.add_argument("--auxiliary-manifest", required=True)
    run.add_argument("--parity-report", required=True)
    run.add_argument("--parity-active-config", required=True)
    run.add_argument("--provider-protocol", required=True)
    run.add_argument("--runtime-root", required=True)
    run.add_argument("--code-freeze-commit", required=True)
    run.add_argument("--timeout-seconds", type=int, default=1800)

    evaluate = commands.add_parser("evaluate-offline")
    evaluate.add_argument("--runtime-root", required=True)
    evaluate.add_argument("--exact-evaluator", required=True)
    evaluate.add_argument("--evaluator-sha256", required=True)
    evaluate.add_argument("--trace", required=True)
    evaluate.add_argument("--trace-sha256", required=True)
    evaluate.add_argument("--exact-nav", required=True)
    evaluate.add_argument("--exact-std", required=True)
    evaluate.add_argument("--output-root", required=True)
    evaluate.add_argument("--base-time", type=float, default=1772784000.0)
    evaluate.add_argument("--timeout-seconds", type=int, default=900)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "generate-auxiliaries":
            payload = generate_fresh_auxiliaries(
                load_clean_paths(args.config),
                clean_input_manifest=args.clean_input_manifest,
                output_root=args.output_root,
                expected_code_commit=args.expected_code_commit,
                provider_protocol=args.provider_protocol,
                rtklib_source_root=args.rtklib_source_root,
                materialize_pinned_rtklib=args.materialize_pinned_rtklib,
                timeout_seconds=args.timeout_seconds,
            )
            terminal = "READY_CLEAN1R2R1_FRESH_AUXILIARIES"
        elif args.command == "seal-auxiliary-trace":
            payload = seal_auxiliary_file_open_audit(
                auxiliary_manifest=args.auxiliary_manifest,
                strace_path=args.strace,
                raw_root=args.raw_root,
                code_root=args.code_root,
            )
            terminal = "PASS_CLEAN1R2R1_AUXILIARY_NO_TRACE_AUDIT"
        elif args.command == "run-four-methods":
            payload = run_four_methods(
                repo_root=args.repo_root,
                executable=args.executable,
                clean_input_manifest=args.clean_input_manifest,
                auxiliary_manifest=args.auxiliary_manifest,
                parity_report=args.parity_report,
                parity_active_config=args.parity_active_config,
                provider_protocol=args.provider_protocol,
                runtime_root=args.runtime_root,
                code_freeze_commit=args.code_freeze_commit,
                timeout_seconds=args.timeout_seconds,
            )
            terminal = payload["terminal_status"]
        else:
            payload = evaluate_four_methods_offline(
                runtime_root=args.runtime_root,
                exact_evaluator=args.exact_evaluator,
                evaluator_sha256=args.evaluator_sha256,
                trace=args.trace,
                trace_sha256=args.trace_sha256,
                exact_nav=args.exact_nav,
                exact_std=args.exact_std,
                output_root=args.output_root,
                base_time=args.base_time,
                timeout_seconds=args.timeout_seconds,
            )
            terminal = "PASS_EXACT_ARCHIVED_OFFLINE_EVALUATION"
    except (Clean1R2R1FormalError, OSError, ValueError, subprocess.SubprocessError) as exc:
        print(f"BLOCKED_CLEAN1R2R1_FOUR_METHOD_EXECUTION_FAILED: {exc}")
        return 2
    print(json.dumps({"terminal_status": terminal, "result": payload}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
