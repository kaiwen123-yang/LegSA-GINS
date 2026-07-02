#!/usr/bin/env python3
"""Audit Q2R2 method contracts."""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from legsa_gins.external_dual_methods.method_contracts import selected_methods


def main() -> int:
    methods = selected_methods()
    if len(methods) < 3:
        raise SystemExit("Q2R2 needs at least three selected methods")
    for method in methods:
        if not method.required_inputs:
            raise SystemExit(f"missing inputs for {method.method_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
