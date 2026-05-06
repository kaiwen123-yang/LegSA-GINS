#!/usr/bin/env python3
"""Write the Stage N1 final_v23-style baseline RUN_MANIFEST.json."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


MANIFEST_FILENAME = "RUN_MANIFEST.json"


def build_manifest(
    *,
    dataset_name: str,
    final_v23_root: str,
    dry_run: bool,
) -> dict[str, Any]:
    return {
        "phase": "N1",
        "dataset_name": dataset_name,
        "algorithm_role": "baseline",
        "algorithm_name": "final_v23_style_baseline",
        "final_v23_root": final_v23_root,
        "dry_run": dry_run,
        "final_v23_is_proposed": False,
        "proposed_reads_final_v23_output": False,
        "final_v23_output_substitution": False,
        "trace_solver_input": False,
        "trace_used_for_tuning": False,
        "output_only_correction": False,
        "bad_epoch_deletion_for_metric": False,
        "raw_data_committed": False,
        "rtk_fixed_claim": False,
        "carrier_ambiguity_fixed_claim": False,
        "self_raw_heading_claim": False,
        "full_raw_gnss_tight_coupling_claim": False,
        "neural_gate_formal_claim": False,
        "fgo_feedback_claim": False,
        "full_pose_fgo_claim": False,
        "full_leg_odometry_claim": False,
        "evidence_status": "wrapper_only_until_real_final_v23_output_is_connected",
    }


def write_manifest(
    *,
    output_dir: Path,
    dataset_name: str,
    final_v23_root: str,
    dry_run: bool,
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest = build_manifest(
        dataset_name=dataset_name,
        final_v23_root=final_v23_root,
        dry_run=dry_run,
    )
    manifest_path = output_dir / MANIFEST_FILENAME
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True, help="Directory where RUN_MANIFEST.json will be written.")
    parser.add_argument("--dataset-name", required=True, help="Dataset name for manifest provenance.")
    parser.add_argument("--final-v23-root", required=True, help="Path to final_v23-style baseline root.")
    parser.add_argument("--dry-run", action="store_true", help="Allow wrapper-only manifest generation.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    final_v23_root = Path(args.final_v23_root)
    if not args.dry_run and not final_v23_root.exists():
        raise SystemExit(f"final_v23 root does not exist: {final_v23_root}")

    manifest_path = write_manifest(
        output_dir=Path(args.output_dir),
        dataset_name=args.dataset_name,
        final_v23_root=str(final_v23_root),
        dry_run=args.dry_run,
    )
    print(f"Wrote {manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
