#!/usr/bin/env python3
"""Authorized read-only H-EXT-04L closeout. Never launches native/evaluator."""
import argparse
import json
from legsa_gins.paper_rebuild.hext.readonly_closeout import run_closeout

if __name__ == "__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--code-commit",required=True)
    args=parser.parse_args()
    result=run_closeout(code_commit=args.code_commit)
    print(json.dumps({k:result[k] for k in ("status","native_invocation_count","evaluator_invocation_count","trace_open_count","products")},indent=2))
