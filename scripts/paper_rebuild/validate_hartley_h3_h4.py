#!/usr/bin/env python3
"""Build and execute the bounded Hartley H3--H4 validation suite."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from legsa_gins.paper_rebuild.horizontal_literature.hartley_h3_h4 import (  # noqa: E402
    validate_h3_h4,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--build-dir", type=Path, required=True)
    parser.add_argument("--official-root", type=Path, required=True)
    parser.add_argument("--scoped-tests", default="NOT_RUN_BY_VALIDATOR")
    parser.add_argument("--full-tests", default="NOT_RUN_BY_VALIDATOR")
    arguments = parser.parse_args()
    status = validate_h3_h4(
        repo_root=REPO_ROOT,
        build_dir=arguments.build_dir,
        official_root=arguments.official_root,
        scoped_tests=arguments.scoped_tests,
        full_tests=arguments.full_tests,
    )
    print(json.dumps(status, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
