#!/usr/bin/env python3
"""Bind existing build/test/preflight/AB0000/clean-18 evidence into one gate."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from legsa_gins.paper_rebuild.canonical541.readiness import (
    derive_compact_readiness_gate, write_compact_readiness_gate,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("build-artifact", "test-artifact", "preflight-artifact",
                 "ab0000-output-root", "ab0000-anchor-root",
                 "clean18-output-root", "clean18-seal-root", "attempt-root"):
        parser.add_argument(f"--{name}", required=True)
    parser.add_argument("--code-freeze-commit", required=True)
    parser.add_argument("--executable-sha256", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    payload = derive_compact_readiness_gate(
        build_artifact=args.build_artifact, test_artifact=args.test_artifact,
        preflight_artifact=args.preflight_artifact,
        ab0000_output_root=args.ab0000_output_root,
        ab0000_anchor_root=args.ab0000_anchor_root,
        clean18_output_root=args.clean18_output_root,
        clean18_seal_root=args.clean18_seal_root,
        attempt_root=args.attempt_root, code_freeze_commit=args.code_freeze_commit,
        executable_sha256=args.executable_sha256,
    )
    write_compact_readiness_gate(args.output, payload)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
