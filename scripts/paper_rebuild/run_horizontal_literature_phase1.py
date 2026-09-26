#!/usr/bin/env python3
"""CLI for the real, trace-closed horizontal-literature Phase 1 run."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
SOURCE_ROOT = REPOSITORY_ROOT / "src"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from legsa_gins.paper_rebuild.horizontal_literature.phase1_runner import (
    PASS_STATUS,
    Phase1RunnerError,
    run_phase1,
    terminal_json,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--paths-config",
        type=Path,
        default=Path("configs/paper_rebuild/DATA_PATHS.CLEAN3R4.local.yaml"),
    )
    parser.add_argument("--method-id", default="EXT01_CLAMBDA")
    parser.add_argument("--case-id", default="C00")
    parser.add_argument("--trace-mode", default="disabled")
    args = parser.parse_args()
    try:
        result = run_phase1(args.paths_config, args.trace_mode, args.method_id, args.case_id)
    except (OSError, ValueError) as exc:
        result = {
            "status": "BLOCKED_PHASE1_CONTRACT_ERROR",
            "error": str(exc),
            "evaluation": "NOT_EVALUATED",
            "paired_epoch_count": None,
            "success_row_count": None,
            "failure_row_count": None,
        }
    print(terminal_json(result))
    return 0 if result["status"] == PASS_STATUS else 2


if __name__ == "__main__":
    raise SystemExit(main())
