#!/usr/bin/env python3
"""Write the Stage N3C final_v23 reproduction RUN_MANIFEST.json.

中文说明：本模块只处理 final_v23/KF-GINS baseline 输出或只读外部源码探测；不修改外部源码、不复制源码、不做数值修正或性能结论。
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


MANIFEST_FILENAME = "RUN_MANIFEST.json"


def build_manifest(
    *,
    dataset_name: str,
    source_root: str,
    evidence_missing: list[str] | None = None,
) -> dict[str, Any]:
    # 中文说明：N3C manifest 明确 baseline 身份和 forbidden flags，防止后续误用。
    # The N3C manifest preserves baseline identity and forbidden flags.
    manifest: dict[str, Any] = {
        "phase": "N3C",
        "algorithm_role": "baseline",
        "algorithm_name": "final_v23_reproduction_connection",
        "dataset_name": dataset_name,
        "source_root": source_root,
        "final_v23_is_proposed": False,
        "proposed_reads_final_v23_output": False,
        "final_v23_output_substitution": False,
        "trace_solver_input": False,
        "trace_used_for_tuning": False,
        "output_only_correction": False,
        "bad_epoch_deletion_for_metric": False,
        "raw_data_committed": False,
        "numerical_claim_without_oracle_pass": False,
        "evidence_status": "output_standardized_no_oracle_claim",
    }
    if evidence_missing:
        manifest["evidence_missing"] = evidence_missing
    return manifest


def write_manifest(
    *,
    output_dir: str | Path,
    dataset_name: str,
    source_root: str,
    evidence_missing: list[str] | None = None,
) -> Path:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    manifest_path = output_path / MANIFEST_FILENAME
    manifest = build_manifest(
        dataset_name=dataset_name,
        source_root=source_root,
        evidence_missing=evidence_missing,
    )
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True, help="Directory where RUN_MANIFEST.json will be written.")
    parser.add_argument("--dataset-name", required=True, help="Dataset name for provenance.")
    parser.add_argument("--source-root", required=True, help="External final_v23/KF-GINS source root.")
    parser.add_argument(
        "--evidence-missing",
        action="append",
        default=[],
        help="Missing evidence marker to include. May be passed multiple times.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    manifest_path = write_manifest(
        output_dir=args.output_dir,
        dataset_name=args.dataset_name,
        source_root=args.source_root,
        evidence_missing=args.evidence_missing,
    )
    print(f"Wrote {manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
