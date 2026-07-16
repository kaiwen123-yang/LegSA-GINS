#!/usr/bin/env python3
"""Generate all 18 current-A1 CLEAN2 case provider bundles without trace."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from legsa_gins.paper_rebuild.clean2_case_provider import generate_classic18_case_bundles


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mapping", default=str(REPO_ROOT / "configs/paper_rebuild/clean2_classic18_active_mapping.yaml"))
    parser.add_argument("--local-config", required=True)
    parser.add_argument("--clean-input-manifest", required=True)
    parser.add_argument("--auxiliary-bundle-manifest", required=True)
    parser.add_argument("--base-dual-yaw-provider", required=True)
    parser.add_argument("--raw-pre-checkpoint", required=True)
    parser.add_argument("--raw-post-checkpoint", required=True)
    parser.add_argument("--raw-hash-lock", required=True)
    parser.add_argument("--code-root", default=str(REPO_ROOT))
    parser.add_argument("--expected-code-freeze-commit", required=True)
    parser.add_argument("--output-root", required=True)
    args = parser.parse_args(argv)
    result = generate_classic18_case_bundles(
        mapping_config=args.mapping,
        clean_input_manifest_path=args.clean_input_manifest,
        auxiliary_bundle_manifest_path=args.auxiliary_bundle_manifest,
        base_dual_yaw_provider_path=args.base_dual_yaw_provider,
        output_root=args.output_root,
        raw_pre_checkpoint_path=args.raw_pre_checkpoint,
        raw_post_checkpoint_path=args.raw_post_checkpoint,
        raw_hash_lock_path=args.raw_hash_lock,
        local_config_path=args.local_config,
        code_root=args.code_root,
        expected_code_freeze_commit=args.expected_code_freeze_commit,
        dual_yaw_match_tolerance_seconds=0.6,
    )
    print(json.dumps({"case_count": len(result), "trace_read_count": 0, "cases": result}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
