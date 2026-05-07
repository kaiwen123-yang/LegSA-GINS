#!/usr/bin/env python3
"""Audit N2 manifest utilities and forbidden-claim enforcement."""

from pathlib import Path
import sys


def _add_src_to_path() -> None:
    root = Path(__file__).resolve().parents[1]
    src = root / "src"
    if str(src) not in sys.path:
        sys.path.insert(0, str(src))


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    required_files = [
        root / "src/legsa_gins/manifests/run_manifest.py",
        root / "src/legsa_gins/manifests/source_manifest.py",
    ]
    missing_files = [str(path.relative_to(root)) for path in required_files if not path.exists()]
    if missing_files:
        print("Manifest contract audit failed. Missing files:")
        for path in missing_files:
            print(f"- {path}")
        return 1

    _add_src_to_path()
    from legsa_gins.manifests.run_manifest import (  # pylint: disable=import-outside-toplevel
        default_run_manifest,
        validate_run_manifest,
    )

    manifest = default_run_manifest(
        phase="N2",
        algorithm_role="infrastructure",
        algorithm_name="frame_writer_evaluator_infrastructure",
        dataset_name="dummy_dataset",
        output_dir="/tmp/legsa_gins_n2",
    )
    try:
        validate_run_manifest(manifest)
    except ValueError as exc:
        print(f"Manifest contract audit failed. Default manifest rejected: {exc}")
        return 1

    manifest["rtk_fixed_claim"] = True
    try:
        validate_run_manifest(manifest)
    except ValueError:
        print("Manifest contract audit passed.")
        return 0

    print("Manifest contract audit failed. rtk_fixed_claim=True was accepted.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
