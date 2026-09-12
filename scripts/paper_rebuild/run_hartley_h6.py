#!/usr/bin/env python3
"""Thin isolated command line for the frozen Hartley H6 workflow."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import subprocess
import sys
import types
from pathlib import Path


REPOSITORY = Path(__file__).resolve().parents[2]


def _load_h6_isolated():
    package_name = "_legsa_hartley_h6_isolated"
    package_path = REPOSITORY / "src/legsa_gins/paper_rebuild/horizontal_literature"
    package = types.ModuleType(package_name)
    package.__package__ = package_name
    package.__path__ = [str(package_path)]
    sys.modules[package_name] = package
    for basename in ("hartley_h0_h2", "hartley_h5", "hartley_h6"):
        qualified = f"{package_name}.{basename}"
        spec = importlib.util.spec_from_file_location(qualified, package_path / f"{basename}.py")
        if spec is None or spec.loader is None:
            raise ImportError(f"cannot load isolated Hartley module: {basename}")
        module = importlib.util.module_from_spec(spec)
        sys.modules[qualified] = module
        spec.loader.exec_module(module)
        setattr(package, basename, module)
    return sys.modules[f"{package_name}.hartley_h6"]


h6 = _load_h6_isolated()


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--scratch", type=Path, required=True)
    common.add_argument("--executable", type=Path, required=True)
    common.add_argument("--cache", type=Path, required=True)
    common.add_argument("--h5-anchor", type=Path, required=True)
    parity = commands.add_parser("zero-parity", parents=[common])
    parity.add_argument("--h5-external-anchor", type=Path, required=True)
    tolerance = commands.add_parser("freeze-tolerances")
    tolerance.add_argument("--scratch", type=Path, required=True)
    member = commands.add_parser("run-member", parents=[common])
    member.add_argument("--run-id", choices=tuple(h6.YAW_BY_RUN_ID), required=True)
    commands.add_parser("run-ensemble", parents=[common])
    aggregate = commands.add_parser("aggregate-equivalence")
    aggregate.add_argument("--scratch", type=Path, required=True)
    selection = commands.add_parser("freeze-window-selection")
    selection.add_argument("--scratch", type=Path, required=True)
    selection.add_argument("--cache", type=Path, required=True)
    observability = commands.add_parser("analyze-observability")
    observability.add_argument("--scratch", type=Path, required=True)
    observability.add_argument("--cache", type=Path, required=True)
    observability.add_argument("--h5-anchor", type=Path, required=True)
    nis = commands.add_parser("analyze-nis-covariance")
    nis.add_argument("--scratch", type=Path, required=True)
    nis.add_argument("--cache", type=Path, required=True)
    nis.add_argument("--h5-anchor", type=Path, required=True)
    finalize = commands.add_parser("finalize")
    finalize.add_argument("--scratch", type=Path, required=True)
    finalize.add_argument("--h5-anchor", type=Path, required=True)
    finalize_blocked = commands.add_parser("finalize-blocked")
    finalize_blocked.add_argument("--scratch", type=Path, required=True)
    finalize_blocked.add_argument("--h5-anchor", type=Path, required=True)
    publish = commands.add_parser("publish")
    publish.add_argument("--scratch", type=Path, required=True)
    publish.add_argument("--stage-root", type=Path, required=True)
    publish.add_argument("--h5-anchor", type=Path, required=True)
    publish_blocked = commands.add_parser("publish-blocked")
    publish_blocked.add_argument("--scratch", type=Path, required=True)
    publish_blocked.add_argument("--stage-root", type=Path, required=True)
    publish_blocked.add_argument("--h5-anchor", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = arguments()
    script = Path(__file__).resolve()
    if args.command == "zero-parity":
        result = h6.run_zero_parity(
            REPOSITORY, script, args.scratch, args.executable, args.cache,
            args.h5_anchor, args.h5_external_anchor,
        )
    elif args.command == "freeze-tolerances":
        result = h6.freeze_tolerance_registry(args.scratch)
    elif args.command == "run-member":
        result = h6.run_member(
            REPOSITORY, script, args.scratch, args.executable, args.cache,
            args.h5_anchor, args.run_id,
        )
    elif args.command == "run-ensemble":
        processes = []
        for run_id in h6.YAW_BY_RUN_ID:
            command = [
                sys.executable, str(script), "run-member",
                "--scratch", str(args.scratch), "--executable", str(args.executable),
                "--cache", str(args.cache), "--h5-anchor", str(args.h5_anchor),
                "--run-id", run_id,
            ]
            processes.append((run_id, subprocess.Popen(
                command, cwd=REPOSITORY, text=True,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            )))
        results = []
        failures = []
        for run_id, process in processes:
            stdout, stderr = process.communicate()
            if process.returncode:
                failures.append({"run_id": run_id, "return_code": process.returncode, "stderr": stderr[-4000:]})
            else:
                results.append(json.loads(stdout.splitlines()[-1]))
        if failures:
            raise h6.HartleyH6Error(f"parallel nonzero ensemble failed: {failures}")
        result = {"nonzero_yaw_run_count": len(results), "maximum_processes": 6, "members": results}
    elif args.command == "aggregate-equivalence":
        result = h6.aggregate_equivalence(args.scratch)
    elif args.command == "freeze-window-selection":
        result = h6.freeze_window_selection(args.scratch, args.cache)
    elif args.command == "analyze-observability":
        result = h6.analyze_observability(args.scratch, args.cache, args.h5_anchor)
    elif args.command == "analyze-nis-covariance":
        result = h6.analyze_nis_and_covariance(args.scratch, args.cache, args.h5_anchor)
    elif args.command == "finalize":
        result = h6.finalize_h6(args.scratch, args.h5_anchor)
    elif args.command == "finalize-blocked":
        result = h6.finalize_blocked_h6(args.scratch, REPOSITORY, args.h5_anchor)
    elif args.command == "publish":
        result = h6.publish_h6(args.scratch, REPOSITORY, args.stage_root, args.h5_anchor)
    else:
        result = h6.publish_blocked_h6(args.scratch, REPOSITORY, args.stage_root, args.h5_anchor)
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
