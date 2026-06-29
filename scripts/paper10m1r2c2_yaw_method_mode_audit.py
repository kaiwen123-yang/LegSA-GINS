#!/usr/bin/env python3
"""Audit PAPER10M1R2C2 method-mode yaw input semantics."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from legsa_gins.evaluation.yaw_method_mode_semantics import (  # noqa: E402
    METHODS,
    common_yaw_convention_pass,
    method_mode_yaw_semantic_row,
)
from scripts.paper10m0_method_mode_loader import load_all, resolve_effective_feature_flags, validate_mode_safety  # noqa: E402
from scripts.paper10m1r2c_full_algorithm_matrix import write_csv  # noqa: E402


def run(args: argparse.Namespace) -> dict[str, object]:
    stage_root = Path(args.stage_root)
    out = stage_root / "03_METHOD_MODE_AUDIT"
    out.mkdir(parents=True, exist_ok=True)
    loaded = load_all(Path(args.code_root))
    provider_status = {
        "raw_doppler": True,
        "go2_roll_pitch": True,
        "go2_horizontal_velocity": True,
        "go2_joint_factor": True,
        "go2_readiness_motion_metadata": False,
        "multi_state_qm": True,
    }
    rows = []
    for method in METHODS:
        mode = loaded["method_modes"][method].data
        effective = resolve_effective_feature_flags(mode, provider_status)
        safety = validate_mode_safety(mode, effective)
        row = method_mode_yaw_semantic_row(
            method,
            mode,
            effective,
            yaw_source_path="<PAPER10M1R2C2_RUNTIME_ROOT>/01_REPAIRED_CLEAN_PROVIDER/BY2_CLEAN_CANONICAL/02_GENERATED_PROVIDERS/dual_yaw_provider.csv",
            yaw_provider_fixed=True,
        )
        row["mode_safety_issues"] = "; ".join(safety)
        row["semantic_status"] = "PASS" if not safety and row["semantic_status"] == "PASS" else "BLOCKED"
        rows.append(row)
    write_csv(out / "PAPER10M1R2C2_METHOD_MODE_YAW_INPUT_AUDIT.csv", rows)
    common = common_yaw_convention_pass(rows)
    report = [
        "# PAPER10M1R2C2 Method-Mode Yaw Semantic Report",
        "",
        f"Common yaw convention across four modes: `{str(common).lower()}`.",
        "",
        "All four modes are configured to consume the same solver-visible provider convention:",
        "`NED solver body heading`, degrees, GNSS2-GNSS1, lateral conversion applied.",
        "",
        "Forbidden input checks are fixed at false for trace, final_v23 output, and LegSA output.",
    ]
    if not common:
        report.append("")
        report.append("Blocker: at least one method mode did not pass common yaw convention audit.")
    (out / "PAPER10M1R2C2_METHOD_MODE_YAW_SEMANTIC_REPORT.md").write_text(
        "\n".join(report) + "\n", encoding="utf-8"
    )
    return {"rows": len(rows), "common_yaw_convention_pass": common}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage-root", required=True)
    parser.add_argument("--code-root", default=str(REPO_ROOT))
    return parser.parse_args()


def main() -> int:
    print(json.dumps(run(parse_args()), ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
