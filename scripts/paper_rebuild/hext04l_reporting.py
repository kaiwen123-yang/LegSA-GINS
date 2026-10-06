#!/usr/bin/env python3
"""Derive H-EXT-04L manuscript flags and scoreboards from pinned H03 tables."""
import argparse
import hashlib
import json
from legsa_gins.paper_rebuild.hext.readonly_reporting import build
from legsa_gins.paper_rebuild.hext.sequence_paths import load_sequence_paths


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--code-commit", required=True, help="Base commit; source hash is recorded separately")
    args = parser.parse_args()
    seq = load_sequence_paths("BY2")
    contract = seq.code_root / "configs/paper_rebuild/hext/H_EXT_CONTRACT_V1.yaml"
    result = build(seq.output_root, code_commit=args.code_commit,
                   config_hash=hashlib.sha256(contract.read_bytes()).hexdigest())
    print(json.dumps(result, ensure_ascii=False, indent=2))
