#!/usr/bin/env python3
"""Run the trace-closed Phase-1R EXT01/C00 validity audit."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

for _name in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ[_name] = "1"

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
SOURCE_ROOT = REPOSITORY_ROOT / "src"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from legsa_gins.paper_rebuild.horizontal_literature.phase1r_runner import (
    DEFAULT_WORKERS,
    PASS_REPAIRED,
    PASS_VALIDATED,
    UNSUPPORTED,
    run_phase1r,
    terminal_json,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--paths-config", type=Path,
        default=Path("configs/paper_rebuild/DATA_PATHS.CLEAN3R4.local.yaml"),
    )
    parser.add_argument("--method-id", default="EXT01_CLAMBDA")
    parser.add_argument("--case-id", default="C00_VALIDATED")
    parser.add_argument("--trace-mode", default="post-native-descriptive")
    parser.add_argument("--workers", type=int, default=DEFAULT_WORKERS)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    try:
        result = run_phase1r(
            args.paths_config,
            method_id=args.method_id,
            case_id=args.case_id,
            trace_mode=args.trace_mode,
            workers=args.workers,
            resume=args.resume,
        )
    except (OSError, ValueError) as exc:
        result = {
            "terminal_status": "BLOCKED_PHASE1R_CONTRACT_ERROR",
            "error_type": type(exc).__name__, "error": str(exc),
            "trace_used_online": False, "canonical541_accessed": False,
        }
    print(terminal_json(result))
    accepted = {PASS_REPAIRED, PASS_VALIDATED, UNSUPPORTED}
    return 0 if result.get("terminal_status") in accepted else 2


if __name__ == "__main__":
    raise SystemExit(main())
