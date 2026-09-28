#!/usr/bin/env python3
"""One H-EXT-02 provider-cache preparation or one native run; no evaluator."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess

for _thread_variable in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ[_thread_variable] = "1"

from legsa_gins.paper_rebuild.hext.ext05_sequence_runner import (
    H02_CONFIGURATIONS, H02_START_MODES, prepare_h02_cache, run_h02_native,
)
from legsa_gins.paper_rebuild.hext.sequence_paths import load_sequence_paths


def _relative(value: str) -> Path:
    path = Path(value)
    if path.is_absolute() or not path.parts or any(part in (".", "..") for part in path.parts):
        raise argparse.ArgumentTypeError("path must be nonempty and relative to hext_scratch, without traversal")
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("prepare-cache", "run"), required=True)
    parser.add_argument("--sequence", choices=("BY2", "BY2H", "BY2O"), required=True)
    parser.add_argument("--cache-relative", type=_relative, required=True)
    parser.add_argument("--output-relative", type=_relative)
    parser.add_argument("--configuration", choices=tuple(H02_CONFIGURATIONS))
    parser.add_argument("--start-mode", choices=H02_START_MODES, default="FILE_START")
    parser.add_argument("--identity-only", action="store_true")
    parser.add_argument("--contract", type=Path, default=Path("configs/paper_rebuild/hext/H_EXT_CONTRACT_V1.yaml"))
    parser.add_argument("--local-config", type=Path, default=Path("configs/paper_rebuild/DATA_PATHS.CLEAN3R4.local.yaml"))
    args = parser.parse_args()
    sequence = load_sequence_paths(args.sequence, local_config=args.local_config)
    contract = args.contract if args.contract.is_absolute() else sequence.code_root / args.contract
    cache_root = sequence.hext_scratch / args.cache_relative
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=sequence.code_root, text=True).strip()
    if args.mode == "prepare-cache":
        result = prepare_h02_cache(sequence, cache_root, contract_path=contract, code_commit=commit)
        print(json.dumps({"status": "PROVIDER_CACHE_PREPARED", "sequence_id": sequence.sequence_id,
                          "solver_invocation_count": 0, "trace_open_count": 0,
                          "first_five_seconds_static_audit": result["first_five_seconds_static_audit"]}, indent=2))
        return 0
    if args.configuration is None or args.output_relative is None:
        parser.error("run requires --configuration and --output-relative")
    result = run_h02_native(
        sequence, cache_root=cache_root, output_root=sequence.hext_scratch / args.output_relative,
        configuration_id=args.configuration, start_mode=args.start_mode,
        contract_path=contract, code_commit=commit, identity_only=args.identity_only,
    )
    print(json.dumps({key: result.get(key) for key in (
        "status", "sequence_id", "configuration_id", "start_mode", "identity_only", "adapter",
        "gap_count", "native_invocation_count", "evaluator_invocation_count", "trace_open_count",
        "failure_type", "failure_message",
    )}, indent=2, sort_keys=True))
    return 0 if result["status"] == "COMPLETED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
