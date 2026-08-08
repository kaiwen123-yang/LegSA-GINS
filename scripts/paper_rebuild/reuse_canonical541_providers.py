#!/usr/bin/env python3
"""Validate and bind the old 541 providers into the repaired attempt."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from legsa_gins.paper_rebuild.canonical541.provider_reuse import (
    decide_provider_reuse, materialize_provider_reuse, persist_provider_reuse_decision,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--origin-stage", required=True)
    parser.add_argument("--origin-freeze", required=True)
    parser.add_argument("--destination-stage", required=True)
    parser.add_argument("--provider-root", required=True)
    parser.add_argument("--new-solver-code-freeze", required=True)
    args = parser.parse_args()
    decision = decide_provider_reuse(
        repo_root=REPO_ROOT, origin_stage=args.origin_stage,
        origin_freeze_path=args.origin_freeze,
        new_solver_code_freeze=args.new_solver_code_freeze,
        provider_root=args.provider_root,
    )
    persist_provider_reuse_decision(decision=decision, destination_stage=args.destination_stage)
    if decision["regeneration_required"]:
        print(json.dumps(decision, indent=2, sort_keys=True))
        return 3
    manifest = materialize_provider_reuse(
        decision=decision, origin_stage=args.origin_stage,
        destination_stage=args.destination_stage,
    )
    print(json.dumps({**decision, "reuse_manifest": str(manifest)}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
