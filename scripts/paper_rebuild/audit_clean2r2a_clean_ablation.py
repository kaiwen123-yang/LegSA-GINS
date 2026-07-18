#!/usr/bin/env python3
"""Render, audit, and finalize CLEAN2R2A evidence without running a solver."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path: sys.path.insert(0, str(SRC_ROOT))

from legsa_gins.paper_rebuild.clean2r2a_evidence import audit_terminal_stage, finalize_evidence_zip
from legsa_gins.paper_rebuild.clean2r2a_plots import (
    generate_diagnostic_figures,
    record_visual_figure_review,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    figures = commands.add_parser("figures"); figures.add_argument("--stage-root", required=True)
    audit = commands.add_parser("audit"); audit.add_argument("--stage-root", required=True)
    audit.add_argument("--local-config", required=True); audit.add_argument("--exact-evaluator", required=True)
    review = commands.add_parser("review-figures")
    review.add_argument("--stage-root", required=True); review.add_argument("--review-json", required=True)
    final = commands.add_parser("finalize")
    final.add_argument("--stage-root", required=True); final.add_argument("--export-root", required=True)
    final.add_argument("--timestamp", required=True)
    final.add_argument("--local-config", required=True); final.add_argument("--exact-evaluator", required=True)
    args = parser.parse_args()
    if args.command == "figures": payload = generate_diagnostic_figures(stage_root=args.stage_root)
    elif args.command == "review-figures":
        payload = record_visual_figure_review(
            stage_root=args.stage_root, review_json=args.review_json,
        )
    elif args.command == "audit":
        payload = audit_terminal_stage(
            args.stage_root, local_config=args.local_config, exact_evaluator=args.exact_evaluator,
        )
    else:
        payload = finalize_evidence_zip(
            stage_root=args.stage_root, export_root=args.export_root, timestamp=args.timestamp,
            local_config=args.local_config, exact_evaluator=args.exact_evaluator,
        )
    print(json.dumps(payload, sort_keys=True)); return 0


if __name__ == "__main__": raise SystemExit(main())
