#!/usr/bin/env python3
"""T5a table/figure derivation; never launches native/evaluator or reads trace."""
import argparse
import json
from pathlib import Path
import sys

sys.dont_write_bytecode = True

from legsa_gins.paper_rebuild.hext.t5a_reporting import aggregate_t5a, render_t5a


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scratch-root", required=True, type=Path)
    parser.add_argument("--code-freeze", required=True)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--aggregate", action="store_true")
    mode.add_argument("--render", action="store_true")
    args = parser.parse_args()
    result = {}
    if not args.render:
        result["aggregate"] = aggregate_t5a(args.scratch_root, code_freeze=args.code_freeze)
    if not args.aggregate:
        result["render"] = render_t5a(args.scratch_root, code_freeze=args.code_freeze)
    print(json.dumps({mode: {key: value[key] for key in ("status", "code_commit", "native_invocation_count", "evaluator_invocation_count", "trace_open_count")}
                      for mode, value in result.items()}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
