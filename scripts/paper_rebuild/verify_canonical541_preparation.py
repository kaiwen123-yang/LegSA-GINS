#!/usr/bin/env python3
"""Read-only queue/hash/authorization audit for completed preparation."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from build_canonical541_manifest import load_local
from legsa_gins.paper_rebuild.canonical541.authorization import validate_attempt_root
from legsa_gins.paper_rebuild.canonical541.preparation import verify_preparation_only


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--local-config", required=True)
    args = parser.parse_args(argv)
    paths = load_local(Path(args.local_config).resolve(strict=True))
    result = verify_preparation_only(repo_root=REPO_ROOT, stage_root=validate_attempt_root(paths["runtime_root"]))
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
