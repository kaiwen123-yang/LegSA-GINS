#!/usr/bin/env python3
"""Generate clean BY2 runtime inputs/providers only from hash-locked raw sources."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from legsa_gins.paper_rebuild.paths import load_clean_paths
from legsa_gins.paper_rebuild.providers import generate_clean_by2_inputs


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, help="Ignored DATA_PATHS.local.yaml")
    parser.add_argument("--max-status-rows", type=int)
    parser.add_argument("--max-raw-rows", type=int)
    parser.add_argument("--max-imu-messages", type=int)
    parser.add_argument("--replace", action="store_true", help="Replace only the exact clean provider files")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    paths = load_clean_paths(args.config)
    manifest = generate_clean_by2_inputs(
        paths,
        max_status_rows=args.max_status_rows,
        max_raw_rows=args.max_raw_rows,
        max_imu_messages=args.max_imu_messages,
        replace=args.replace,
    )
    print(json.dumps({"status": "PASS", "provider_count": len(manifest["provider_hashes"])}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
