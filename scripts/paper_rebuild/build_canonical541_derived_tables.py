#!/usr/bin/env python3
"""Build the Canonical-541 derived tables authorised in AGENTS section 12b.

Example:
  python scripts/paper_rebuild/build_canonical541_derived_tables.py \
      --attempt-root <CANONICAL541_ATTEMPT> \
      --out-dir <CLEAN_ROOT>/stages/CLEAN6_PUBLICATION_FIGURES/01_CANONICAL541/00_DERIVED_TABLES

Reads frozen tables only; fails closed on the identity gate and on any mismatch
with the frozen PAIRWISE_SUMMARY or AGENTS section 7A.2.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from legsa_gins.paper_rebuild.publication import derived_tables as dt  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--attempt-root", required=True, type=Path)
    ap.add_argument("--out-dir", required=True, type=Path)
    ap.add_argument("--handoff-subset", action="store_true",
                    help="resolve C00 error series / NAV files from the c541_handoff subset layout instead of the attempt layout")
    ap.add_argument("--bootstrap-samples", type=int, default=dt.BOOT_N)
    ap.add_argument("--bootstrap-seed", type=int, default=dt.BOOT_SEED)
    args = ap.parse_args()
    resolver = dt.handoff_subset_resolver(args.attempt_root) if args.handoff_subset else dt.attempt_series_resolver(args.attempt_root)
    manifest = dt.build_all(args.attempt_root, args.out_dir, resolver=resolver, n_boot=args.bootstrap_samples, seed=args.bootstrap_seed)
    print(json.dumps({k: manifest[k] for k in ("identity_gate", "frozen_validation", "body_frame_status", "git_head")}, indent=2))
    print(f"wrote {len(manifest['outputs_sha256'])} tables to {args.out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
