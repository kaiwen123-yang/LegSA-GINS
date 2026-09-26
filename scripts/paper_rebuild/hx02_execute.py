#!/usr/bin/env python3
"""HX-02 five-category external comparison controller.

prepare    input pins before the code-freeze commit (no solver, no evaluator, no reference)
run        the 24 registered native runs, evaluations and per-batch archives (resumable; tmux;
           must run under `strace -qq -e trace=openat,execve -o $HX02_CONTROLLER_STRACE`)
aggregate  90_AGGREGATE tables from archived runs and the sealed v3 tables (read-only)
status     print STATE.json counters
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

for _name in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ[_name] = "1"
REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
if str(REPOSITORY_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT / "src"))

from legsa_gins.paper_rebuild.hext import hx02_execution as execution  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("prepare", "run", "aggregate", "status"))
    parser.add_argument("--paths-config", type=Path, default=Path("configs/paper_rebuild/DATA_PATHS.CLEAN3R4.local.yaml"))
    parser.add_argument("--code-freeze", default=None, help="aggregate: the code-freeze commit to cite")
    args = parser.parse_args()
    os.chdir(REPOSITORY_ROOT)
    roots = execution.load_roots(args.paths_config)
    if args.command == "prepare":
        result = execution.prepare(roots)
        print(json.dumps({"pins": str(roots.pins / "INPUT_PINS.json"),
                          "hartley_records": {k: v["record_count"] for k, v in result["hartley"].items()},
                          "ginav_overlap": {k: v["overlap"] for k, v in result["ginav"].items()}}, indent=2))
        return 0
    if args.command == "run":
        state = execution.run_all(roots)
        print(json.dumps(state["counters"], indent=2))
        return 0
    if args.command == "aggregate":
        from legsa_gins.paper_rebuild.hext import hx02_aggregate
        print(json.dumps(hx02_aggregate.aggregate(roots, code_freeze=args.code_freeze), indent=2, default=str)[:4000])
        return 0
    state = json.loads((roots.control / "STATE.json").read_text(encoding="utf-8"))
    print(json.dumps({"counters": state["counters"], "runs": {k: v.get("status") for k, v in state["runs"].items()}},
                     indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
