#!/usr/bin/env python3
"""Dry-run-safe external final_v23/KF-GINS build wrapper.

中文说明：本模块只处理 final_v23/KF-GINS baseline 输出或只读外部源码探测；不修改外部源码、不复制源码、不做数值修正或性能结论。
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
from typing import Any


def is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def build_external(
    *,
    source_root: str | Path,
    build_dir: str | Path,
    dry_run: bool,
    allow_build: bool,
) -> dict[str, Any]:
    # 中文说明：默认 dry-run；真实 build 必须显式 allow，且 build_dir 不能在 source-root 内。
    # Default dry-run; real builds require explicit allow and an out-of-source build dir.
    source = Path(source_root).resolve()
    build = Path(build_dir).resolve()
    result: dict[str, Any] = {
        "phase": "N3C",
        "algorithm_role": "baseline",
        "source_root_exists": source.exists(),
        "build_dir": str(build),
        "dry_run": dry_run,
        "allow_build": allow_build,
        "modifies_source_root": False,
        "evidence_status": "dry_run_not_built",
    }
    if is_relative_to(build, source):
        result["evidence_status"] = "build_dir_inside_source_root_forbidden"
        return result
    if dry_run or not allow_build:
        return result
    if not source.exists():
        result["evidence_status"] = "external_source_path_missing"
        return result

    build.mkdir(parents=True, exist_ok=True)
    configure = subprocess.run(
        ["cmake", "-S", str(source), "-B", str(build)],
        check=False,
        capture_output=True,
        text=True,
    )
    result["configure_returncode"] = configure.returncode
    result["configure_stdout_tail"] = configure.stdout[-4000:]
    result["configure_stderr_tail"] = configure.stderr[-4000:]
    if configure.returncode != 0:
        result["evidence_status"] = "build_failed"
        return result

    build_run = subprocess.run(
        ["cmake", "--build", str(build), "-j"],
        check=False,
        capture_output=True,
        text=True,
    )
    result["build_returncode"] = build_run.returncode
    result["build_stdout_tail"] = build_run.stdout[-4000:]
    result["build_stderr_tail"] = build_run.stderr[-4000:]
    result["evidence_status"] = "built" if build_run.returncode == 0 else "build_failed"
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", required=True, help="External KF-GINS source root.")
    parser.add_argument("--build-dir", required=True, help="Build directory outside source-root.")
    parser.add_argument(
        "--dry-run",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Default true. Pass --no-dry-run with --allow-build to build.",
    )
    parser.add_argument("--allow-build", action="store_true", help="Allow a real cmake build.")
    parser.add_argument("--output-json", help="Optional build attempt JSON path.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = build_external(
        source_root=args.source_root,
        build_dir=args.build_dir,
        dry_run=args.dry_run,
        allow_build=args.allow_build,
    )
    text = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output_json:
        output_path = Path(args.output_json)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(text, encoding="utf-8")
        print(f"Wrote {output_path}")
    else:
        print(text, end="")
    return 0 if result["evidence_status"] not in {"build_failed", "build_dir_inside_source_root_forbidden"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
