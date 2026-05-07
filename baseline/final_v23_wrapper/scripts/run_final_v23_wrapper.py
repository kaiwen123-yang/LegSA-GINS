#!/usr/bin/env python3
"""Stage N1 final_v23-style baseline wrapper skeleton.

中文说明：final_v23 wrapper 只服务 baseline/oracle/backbone reference；final_v23 不是 proposed，wrapper 不允许 output substitution。
"""

from __future__ import annotations

import argparse
from pathlib import Path
import shlex
import subprocess
import sys

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from write_final_v23_manifest import write_manifest


PROPOSED_PATH_MARKERS = (
    "results/proposed",
    "/proposed/",
    "\\proposed\\",
)


def contains_proposed_marker(value: str) -> bool:
    normalized = value.replace("\\", "/")
    return any(marker.replace("\\", "/") in normalized for marker in PROPOSED_PATH_MARKERS)


def validate_not_proposed_output(output_dir: Path) -> None:
    # 中文说明：final_v23 baseline 输出不能写入 proposed 目录，避免 output substitution。
    # Keep final_v23 baseline outputs out of proposed paths.
    output_text = str(output_dir).replace("\\", "/")
    if contains_proposed_marker(output_text):
        raise SystemExit(f"final_v23 baseline output must not be written under proposed output paths: {output_dir}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset-config", required=True, help="Dataset config path for the baseline run.")
    parser.add_argument("--final-v23-root", required=True, help="Path to the final_v23-style baseline root.")
    parser.add_argument("--final-v23-command", required=True, help="Command used to run final_v23-style baseline.")
    parser.add_argument("--output-dir", required=True, help="Baseline output directory.")
    parser.add_argument("--dry-run", action="store_true", help="Print command and write manifest without running final_v23.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    final_v23_root = Path(args.final_v23_root)
    output_dir = Path(args.output_dir)

    if not final_v23_root.exists():
        raise SystemExit(f"final_v23 root does not exist: {final_v23_root}")
    validate_not_proposed_output(output_dir)
    if contains_proposed_marker(args.dataset_config):
        raise SystemExit("dataset config for final_v23 baseline must not be a proposed-output path")

    # 中文说明：dry-run 只写 baseline manifest；非 dry-run 也不能让 proposed solver 读取 final_v23 输出。
    # Dry-run writes baseline provenance only; final_v23 never becomes proposed input.
    output_dir.mkdir(parents=True, exist_ok=True)
    command = shlex.split(args.final_v23_command)
    if not command:
        raise SystemExit("--final-v23-command must not be empty")

    print("final_v23-style baseline command:")
    print(" ".join(shlex.quote(part) for part in command))

    if not args.dry_run:
        subprocess.run(command, cwd=final_v23_root, check=True)
    else:
        print("dry-run enabled; command was not executed")

    manifest_path = write_manifest(
        output_dir=output_dir,
        dataset_name=Path(args.dataset_config).stem,
        final_v23_root=str(final_v23_root),
        dry_run=args.dry_run,
    )
    print(f"Wrote {manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
