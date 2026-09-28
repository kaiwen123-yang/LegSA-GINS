#!/usr/bin/env python3
"""Package authorized Canonical-541 generated evidence through the direct route."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from legsa_gins.paper_rebuild.canonical541.trusted_direct_evidence import package_trusted_direct


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--local-config", required=True)
    parser.add_argument("--stage-root", required=True)
    parser.add_argument("--export-root", required=True)
    parser.add_argument("--attempt-id", required=True)
    parser.add_argument("--timestamp", required=True)
    args = parser.parse_args()
    report = package_trusted_direct(local_config=args.local_config, stage_root=args.stage_root,
                                    export_root=args.export_root, attempt_id=args.attempt_id,
                                    timestamp=args.timestamp)
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
