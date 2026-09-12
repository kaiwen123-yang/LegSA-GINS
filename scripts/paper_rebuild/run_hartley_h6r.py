#!/usr/bin/env python3
"""Isolated command line for the Hartley H6R evidence recovery."""

from __future__ import annotations

import argparse
import importlib.util
import json
import subprocess
import sys
import types
from pathlib import Path


REPOSITORY = Path(__file__).resolve().parents[2]


def _load():
    package_name = "_legsa_hartley_h6r_isolated"
    package_path = REPOSITORY / "src/legsa_gins/paper_rebuild/horizontal_literature"
    package = types.ModuleType(package_name)
    package.__package__ = package_name
    package.__path__ = [str(package_path)]
    sys.modules[package_name] = package
    for basename in ("hartley_h0_h2", "hartley_h5", "hartley_h6", "hartley_h6r"):
        name = f"{package_name}.{basename}"
        spec = importlib.util.spec_from_file_location(name, package_path / f"{basename}.py")
        if spec is None or spec.loader is None:
            raise ImportError(f"cannot load isolated Hartley module: {basename}")
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
        setattr(package, basename, module)
    return sys.modules[f"{package_name}.hartley_h6r"]


h6r = _load()


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    prepare = commands.add_parser("prepare")
    prepare.add_argument("--scratch", type=Path, required=True)
    prepare.add_argument("--h5-anchor", type=Path, required=True)
    prepare.add_argument("--original-h6", type=Path, required=True)
    prepare.add_argument("--original-stage", type=Path, required=True)
    prepare.add_argument("--storage-health-json", type=Path, required=True)
    member = commands.add_parser("run-member")
    for option in (member,):
        option.add_argument("--scratch", type=Path, required=True)
        option.add_argument("--executable", type=Path, required=True)
        option.add_argument("--cache", type=Path, required=True)
        option.add_argument("--h5-anchor", type=Path, required=True)
        option.add_argument("--original-h6", type=Path, required=True)
    member.add_argument("--run-id", choices=tuple(h6r.YAW_BY_RUN_ID), required=True)
    ensemble = commands.add_parser("run-ensemble")
    ensemble.add_argument("--scratch", type=Path, required=True)
    ensemble.add_argument("--executable", type=Path, required=True)
    ensemble.add_argument("--cache", type=Path, required=True)
    ensemble.add_argument("--h5-anchor", type=Path, required=True)
    ensemble.add_argument("--original-h6", type=Path, required=True)
    aggregate = commands.add_parser("aggregate-contact")
    aggregate.add_argument("--scratch", type=Path, required=True)
    reuse = commands.add_parser("reuse-windows")
    reuse.add_argument("--scratch", type=Path, required=True)
    reuse.add_argument("--original-h6", type=Path, required=True)
    observe = commands.add_parser("analyze-observability")
    observe.add_argument("--scratch", type=Path, required=True)
    observe.add_argument("--cache", type=Path, required=True)
    observe.add_argument("--h5-anchor", type=Path, required=True)
    nis = commands.add_parser("analyze-nis-covariance")
    nis.add_argument("--scratch", type=Path, required=True)
    nis.add_argument("--cache", type=Path, required=True)
    nis.add_argument("--h5-anchor", type=Path, required=True)
    combine = commands.add_parser("combine-equivalence")
    combine.add_argument("--scratch", type=Path, required=True)
    combine.add_argument("--original-h6", type=Path, required=True)
    finalize = commands.add_parser("finalize")
    finalize.add_argument("--scratch", type=Path, required=True)
    finalize.add_argument("--original-h6", type=Path, required=True)
    publish = commands.add_parser("publish")
    publish.add_argument("--scratch", type=Path, required=True)
    publish.add_argument("--stage-root", type=Path, required=True)
    return parser.parse_args()


def _run_one(args: argparse.Namespace, run_id: str) -> dict:
    execution = h6r.execute_member(
        REPOSITORY, Path(__file__).resolve(), args.scratch, args.executable, args.cache, run_id,
    )
    return h6r.compact_and_verify_member(
        args.scratch, args.cache, args.h5_anchor, args.original_h6, execution,
    )


def _main_impl() -> int:
    args = arguments()
    if args.command == "prepare":
        result = h6r.initialize_recovery(
            args.scratch, args.h5_anchor, args.original_h6, args.original_stage,
            json.loads(args.storage_health_json.read_text()),
        )
    elif args.command == "run-member":
        result = _run_one(args, args.run_id)
    elif args.command == "run-ensemble":
        # Zero is a hard parity gate and always completes before nonzero launches.
        zero = _run_one(args, "H6R_YAW_000")
        processes = []
        for run_id, yaw, _directory in h6r.YAW_MEMBERS:
            if yaw == 0.0:
                continue
            command = [
                sys.executable, str(Path(__file__).resolve()), "run-member",
                "--scratch", str(args.scratch), "--executable", str(args.executable),
                "--cache", str(args.cache), "--h5-anchor", str(args.h5_anchor),
                "--original-h6", str(args.original_h6), "--run-id", run_id,
            ]
            processes.append((run_id, subprocess.Popen(
                command, cwd=REPOSITORY, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            )))
        failures, members = [], [zero]
        for run_id, process in processes:
            stdout, stderr = process.communicate()
            if process.returncode:
                failures.append({"run_id": run_id, "stderr": stderr[-3000:]})
            else:
                members.append(json.loads(stdout.splitlines()[-1]))
        if failures:
            raise h6r.HartleyH6RError(f"H6R nonzero replay failure: {failures}")
        result = {"member_count": len(members), "zero_completed_before_nonzero": True,
                  "maximum_independent_nonzero_processes": 6, "members": members}
    elif args.command == "aggregate-contact":
        result = h6r.aggregate_contact_recovery(args.scratch)
    elif args.command == "reuse-windows":
        result = h6r.reuse_frozen_windows(args.original_h6, args.scratch)
    elif args.command == "analyze-observability":
        result = h6r.analyze_observability_r1(args.scratch, args.cache, args.h5_anchor)
    elif args.command == "analyze-nis-covariance":
        result = h6r.analyze_nis_covariance_r1(args.scratch, args.cache, args.h5_anchor)
    elif args.command == "combine-equivalence":
        result = h6r.combine_gauge_equivalence(args.scratch, args.original_h6)
    elif args.command == "finalize":
        result = h6r.finalize(args.scratch, args.original_h6)
    else:
        result = h6r.publish_exclusive(args.scratch, args.stage_root)
    print(json.dumps(result, sort_keys=True))
    return 0


def main() -> int:
    try:
        return _main_impl()
    except Exception as error:
        scratch = None
        if "--scratch" in sys.argv:
            index = sys.argv.index("--scratch")
            if index + 1 < len(sys.argv):
                scratch = Path(sys.argv[index + 1])
        detail = str(error)
        terminal = next((value for value in h6r.BLOCKERS.values() if value in detail), None)
        if scratch is not None and terminal is not None and scratch.exists():
            payload = h6r.finalize_blocked(scratch, terminal, detail)
            print(json.dumps(payload, sort_keys=True))
        elif scratch is not None:
            h6r.write_internal_failure_ledger(scratch, sys.argv[1] if len(sys.argv) > 1 else "UNKNOWN", detail)
        raise


if __name__ == "__main__":
    raise SystemExit(main())
