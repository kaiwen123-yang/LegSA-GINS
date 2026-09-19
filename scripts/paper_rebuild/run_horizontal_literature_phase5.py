#!/usr/bin/env python3
"""Run the frozen EXT05 C00 native gate or its post-freeze geometric audit."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Sequence

for _thread_variable in (
    "OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS", "NUMEXPR_NUM_THREADS"
):
    os.environ[_thread_variable] = "1"

from legsa_gins.paper_rebuild.horizontal_literature.phase5_runner import (
    DEFAULT_WORKERS,
    Phase5RunnerError,
    load_paths,
    run_geometric_audit,
    run_native,
    run_trace_evaluation,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PATHS_CONFIG = (
    REPOSITORY_ROOT / "configs/paper_rebuild/DATA_PATHS.CLEAN3R4.local.yaml"
)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--mode", choices=("native", "geometric-audit", "trace-evaluation"), required=True,
        help="Native never opens trace; geometric-audit requires and revalidates the native freeze.",
    )
    parser.add_argument(
        "--paths-config", type=Path, default=DEFAULT_PATHS_CONFIG,
        help="Ignored local path-alias configuration.",
    )
    parser.add_argument("--workers", type=int, default=DEFAULT_WORKERS)
    parser.add_argument(
        "--exact-evaluator", type=Path,
        help="Required only for trace-evaluation; bytes must match the frozen aa049248 identity.",
    )
    parser.add_argument("--resume", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    arguments = parse_args(argv)
    try:
        paths = load_paths(arguments.paths_config)
        if arguments.mode == "native":
            result = run_native(paths, workers=arguments.workers, resume=arguments.resume)
        elif arguments.mode == "geometric-audit":
            result = run_geometric_audit(paths, resume=arguments.resume)
        else:
            if arguments.exact_evaluator is None:
                raise Phase5RunnerError("trace-evaluation requires --exact-evaluator")
            result = run_trace_evaluation(
                paths,
                exact_evaluator=arguments.exact_evaluator,
                resume=arguments.resume,
            )
    except (OSError, Phase5RunnerError, ValueError) as exc:
        print(json.dumps({
            "terminal_status": "BLOCKED_EXT05_RUNNER_CONTRACT",
            "error": str(exc),
        }, sort_keys=True))
        return 2
    print(json.dumps(result, indent=2, sort_keys=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
