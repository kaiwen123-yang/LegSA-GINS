#!/usr/bin/env python3
"""H-EXT-03 explicit actions: zero native calls, at most eleven unused evaluator slots."""
import argparse
import json
import os

os.environ["GIT_OPTIONAL_LOCKS"] = "0"
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
for name in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ[name] = "1"

from legsa_gins.paper_rebuild.hext import continuation


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("preflight", "freeze", "evaluate"))
    args = parser.parse_args()
    actions = {"preflight": continuation.preflight, "freeze": continuation.freeze_receipt,
               "evaluate": continuation.run_evaluation_matrix}
    try:
        result = actions[args.action]()
        print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
    except Exception as exc:
        _, scratch, _ = continuation.stage_roots()
        path = scratch / ("HARD_STOP_" + args.action.upper() + ".json")
        if not path.exists():
            continuation.io.write_json(path, {"action": args.action, "status": "HARD_STOP",
                "error_type": type(exc).__name__, "error": str(exc), "automatic_retry_allowed": False})
        raise


if __name__ == "__main__":
    main()
