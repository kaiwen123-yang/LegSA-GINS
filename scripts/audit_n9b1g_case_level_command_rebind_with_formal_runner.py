#!/usr/bin/env python3
"""Audit N9B1G case-level command rebinding outputs."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from legsa_gins.reporting.by2_n9b1g_case_level_command_rebind_with_formal_runner import (  # noqa: E402
    default_n9b1g_runtime_root,
    validate_n9b1g_result,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime-root", "--output-dir", default=None)
    return parser.parse_args()


def _load_rows(path: Path) -> list[dict]:
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    return data if isinstance(data, list) else data.get("rows", [])


def main() -> int:
    args = parse_args()
    runtime_root = Path(args.runtime_root) if args.runtime_root else default_n9b1g_runtime_root(ROOT)
    command_rows = _load_rows(runtime_root / "matrix" / "N9B1G_N9B1D_CASE_LEVEL_COMMAND_MATRIX.json")
    dryrun_rows = _load_rows(runtime_root / "matrix" / "N9B1G_WSL_DRYRUN_CASE_LEVEL_COMMANDS.json")
    validation = validate_n9b1g_result(ROOT, runtime_root, command_rows, dryrun_rows, runtime_written=True)
    print("audit_n9b1g_case_level_command_rebind_with_formal_runner", validation["status"])
    print("runtime_root:", runtime_root)
    print("case_level_command_rows:", validation["case_level_command_rows"])
    print("selected_feedback_dependency_command_count:", validation["selected_feedback_dependency_command_count"])
    if validation["issues"]:
        print("issues:")
        for issue in validation["issues"]:
            print("-", issue)
    return 0 if validation["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
