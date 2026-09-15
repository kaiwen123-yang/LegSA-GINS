#!/usr/bin/env python3
"""Run the isolated Phase-3 EXT03 Yang-2024/C00 lifecycle."""

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

from legsa_gins.paper_rebuild.horizontal_literature.phase3_runner import (  # noqa: E402
    ALLOWED_MODES, CASE_ID, DEFAULT_WORKERS, METHOD_ID, run_phase3,
    terminal_json, terminalize_failure,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--paths-config", type=Path, default=Path("configs/paper_rebuild/DATA_PATHS.CLEAN3R4.local.yaml"))
    parser.add_argument("--mode", choices=sorted(ALLOWED_MODES), default="full")
    parser.add_argument("--method-id", default=METHOD_ID)
    parser.add_argument("--case-id", default=CASE_ID)
    parser.add_argument("--trace-mode", default="disabled")
    parser.add_argument("--workers", type=int, default=DEFAULT_WORKERS)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--post-recovery-id")
    args = parser.parse_args()
    try:
        result = run_phase3(
            args.paths_config, mode=args.mode, method_id=args.method_id,
            case_id=args.case_id, trace_mode=args.trace_mode, workers=args.workers,
            resume=args.resume, post_recovery_id=args.post_recovery_id,
        )
    except Exception as exc:
        result = terminalize_failure(args.paths_config, args.mode, exc)
    print(terminal_json(result))
    status = str(result.get("terminal_status", ""))
    return 0 if status.startswith("PASS_PHASE3_") or status.startswith("UNSUPPORTED_EXT03_") else 2


if __name__ == "__main__":
    raise SystemExit(main())
