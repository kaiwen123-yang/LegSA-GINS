#!/usr/bin/env python3
"""Regenerate 541 BY2 providers with fixed A1 yaw lineage for M1R2B2."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from legsa_gins.degradation.m1r2b2_provider_regen import B2Paths, finalize_b2_stage  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", required=True)
    parser.add_argument("--m1r2a-root", required=True)
    parser.add_argument("--old-m1r2b-root", required=True)
    parser.add_argument("--m1r2c2-root", required=True)
    parser.add_argument("--stage-root", required=True)
    parser.add_argument("--runtime-root", required=True)
    parser.add_argument("--provider-root", required=True)
    parser.add_argument("--export-root", required=True)
    parser.add_argument("--by2-fix-root", required=True)
    parser.add_argument("--by2-go2-body-root", required=True)
    parser.add_argument("--raw-doppler-provider", required=True)
    parser.add_argument("--skip-generator", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    env = os.environ.copy()
    env.update(
        {
            "LEGSA_CODE_ROOT": str(REPO_ROOT),
            "LEGSA_PROJECT_ROOT": args.project_root,
            "PAPER10M1R2A_STAGE_ROOT": args.m1r2a_root,
            "PAPER10M1R2B_STAGE_ROOT": args.stage_root,
            "PAPER10M1R2B_RUNTIME_ROOT": args.runtime_root,
            "PAPER10M1R2B_PROVIDER_ROOT": args.provider_root,
            "PAPER10M1R2B_EXPORT_ROOT": args.export_root,
            "BY2_FIX_ROOT": args.by2_fix_root,
            "BY2_GO2_BODY_ROOT": args.by2_go2_body_root,
            "BY2_RAW_DOPPLER_PROVIDER": args.raw_doppler_provider,
        }
    )
    if not args.skip_generator:
        subprocess.run([sys.executable, str(REPO_ROOT / "scripts/paper10m1r2b_generate_by2_degraded_providers.py")], cwd=REPO_ROOT, env=env, check=True)
    paths = B2Paths(
        code_root=REPO_ROOT,
        project_root=Path(args.project_root),
        m1r2a_root=Path(args.m1r2a_root),
        old_m1r2b_root=Path(args.old_m1r2b_root),
        m1r2c2_root=Path(args.m1r2c2_root),
        stage_root=Path(args.stage_root),
        runtime_root=Path(args.runtime_root),
        provider_root=Path(args.provider_root),
        export_root=Path(args.export_root),
    )
    result = finalize_b2_stage(paths)
    print(
        json.dumps(
            {
                "final_decision": result["final_decision"],
                "cases": result["cases"],
                "provider_ready": sum(1 for row in result["ready_rows"] if row["provider_ready"] == "true"),
                "m1r2c_r1_rows": len(result["full_rows"]),
                "m1r2d_r1_rows": len(result["ablation_rows"]),
                "path_scan": result["path_scan"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

