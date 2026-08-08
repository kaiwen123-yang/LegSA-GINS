#!/usr/bin/env python3
"""Run the read-only repaired Canonical-541 registry/config preflight."""

from __future__ import annotations

import json
import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from legsa_gins.paper_rebuild.canonical541.preflight import run_registry_preflight


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--code-freeze-commit")
    parser.add_argument("--executable-sha256")
    args = parser.parse_args()
    result = run_registry_preflight(
        REPO_ROOT, code_freeze_commit=args.code_freeze_commit,
        executable_sha256=args.executable_sha256,
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    raise SystemExit(0 if result["passed"] else 2)
