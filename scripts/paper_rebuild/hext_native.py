#!/usr/bin/env python3
"""H-EXT-01 native BY2 identity only; no evaluator or trace access."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess

for _thread_variable in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ[_thread_variable] = "1"

from legsa_gins.paper_rebuild.hext.ext05_sequence_runner import run_native_sequence
from legsa_gins.paper_rebuild.hext.sequence_paths import load_sequence_paths


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sequence", choices=("BY2",), default="BY2")
    parser.add_argument("--local-config", type=Path, default=Path("configs/paper_rebuild/DATA_PATHS.CLEAN3R4.local.yaml"))
    parser.add_argument("--registry", type=Path, default=Path("configs/paper_rebuild/clean5/CLEAN5_SEQUENCE_REGISTRY.yaml"))
    parser.add_argument("--output-name", default="H_EXT_01_BY2_IDENTITY")
    parser.add_argument("--workers", type=int, default=2)
    args = parser.parse_args()
    name = Path(args.output_name)
    if name.is_absolute() or len(name.parts) != 1 or name.name in ("", ".", ".."):
        parser.error("output-name must be a single new directory name below hext_scratch")
    paths = load_sequence_paths(args.sequence, local_config=args.local_config, registry_path=args.registry)
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=paths.code_root, text=True).strip()
    summary = run_native_sequence(
        paths, paths.hext_scratch / name,
        phase5_contract_path=paths.code_root / "configs/paper_rebuild/horizontal_literature/PHASE5_EXT05_PAVLASEK_CONTRACT_V1.yaml",
        code_commit=commit, workers=args.workers,
    )
    print(json.dumps({
        "terminal_status": summary["terminal_status"],
        "adapters": summary["adapters"],
        "native_invocation_count": summary["native_invocation_count"],
        "evaluator_invocation_count": summary["evaluator_invocation_count"],
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
