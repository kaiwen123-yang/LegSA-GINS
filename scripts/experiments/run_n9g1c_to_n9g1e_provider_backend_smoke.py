"""Generate N9G1C-E provider/backend/logger gate artifacts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from legsa_gins.fgo.fgo_n9g1c_to_n9g1e_provider_backend_smoke import (
    STAGE,
    write_n9g1c_to_n9g1e_artifacts,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace-root", default=".")
    parser.add_argument("--runtime-root", default=None)
    parser.add_argument("--static-validation-status", default="not_run")
    parser.add_argument("--pytest-status", default="not_run")
    parser.add_argument("--pytest-evidence", default="pytest availability not probed by artifact writer")
    parser.add_argument("--context-sync-status", default="pending")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    workspace = Path(args.workspace_root).resolve()
    runtime_root = (
        Path(args.runtime_root).resolve()
        if args.runtime_root
        else workspace / "by2-huitu" / STAGE
    )
    result = write_n9g1c_to_n9g1e_artifacts(
        workspace,
        runtime_root,
        static_validation_status=args.static_validation_status,
        pytest_status=args.pytest_status,
        pytest_evidence=args.pytest_evidence,
        context_sync_status=args.context_sync_status,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
