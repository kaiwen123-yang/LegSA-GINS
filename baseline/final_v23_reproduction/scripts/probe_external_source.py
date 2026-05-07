#!/usr/bin/env python3
"""Probe an external final_v23/KF-GINS source tree without modifying it."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
from typing import Any


REQUIRED_SOURCE_FILES = [
    "src/kf_gins.cpp",
    "src/kf-gins/gi_engine.cpp",
]

OBSERVED_OUTPUT_FILES = [
    "KF_GINS_Navresult.nav",
    "KF_GINS_STD.txt",
    "KF_GINS_IMU_ERR.txt",
]


def run_git(source_root: Path, args: list[str]) -> str:
    try:
        completed = subprocess.run(
            ["git", "-C", str(source_root), *args],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError as exc:
        return f"git_error: {exc}"
    text = completed.stdout.strip()
    if completed.returncode != 0:
        err = completed.stderr.strip()
        return err or text or f"git_returncode_{completed.returncode}"
    return text


def find_named_files(source_root: Path, filenames: list[str]) -> dict[str, list[str]]:
    found = {name: [] for name in filenames}
    wanted = set(filenames)
    if not source_root.exists():
        return found
    for path in source_root.rglob("*"):
        if ".git" in path.parts:
            continue
        if path.is_file() and path.name in wanted:
            found[path.name].append(str(path.relative_to(source_root)))
    return {name: sorted(paths) for name, paths in found.items()}


def probe_source(source_root: str | Path) -> dict[str, Any]:
    root = Path(source_root)
    exists = root.exists()
    result: dict[str, Any] = {
        "source_root_exists": exists,
        "source_root_is_dir": root.is_dir(),
        "git": {},
        "required_source_files": {},
        "observed_output_files": {},
        "evidence_status": "evidence_missing",
        "modifies_external_source": False,
    }
    if not exists:
        result["evidence_missing"] = [f"external_source_path_missing: {source_root}"]
        return result

    result["git"] = {
        "remote": run_git(root, ["remote", "-v"]),
        "branch": run_git(root, ["branch", "--show-current"]),
        "commit": run_git(root, ["rev-parse", "HEAD"]),
        "status_short": run_git(root, ["status", "--short"]),
    }
    result["required_source_files"] = {
        rel_path: (root / rel_path).is_file() for rel_path in REQUIRED_SOURCE_FILES
    }
    result["observed_output_files"] = find_named_files(root, OBSERVED_OUTPUT_FILES)

    missing = [
        rel_path
        for rel_path, present in result["required_source_files"].items()
        if not present
    ]
    if missing:
        result["evidence_missing"] = missing
    else:
        result["evidence_status"] = "passed"
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", required=True, help="External KF-GINS source root.")
    parser.add_argument("--output-json", required=True, help="Probe JSON output path.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = probe_source(args.source_root)
    output_path = Path(args.output_json)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Wrote {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
