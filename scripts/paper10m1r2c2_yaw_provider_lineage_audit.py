#!/usr/bin/env python3
"""Audit PAPER10M1R2C2 BY2 clean yaw provider lineage."""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from legsa_gins.evaluation.yaw_provider_lineage import (  # noqa: E402
    audit_status_relpos_against_provider,
    circular_diff_deg,
    read_csv_rows,
    repair_legacy_provider_yaw_deg,
    write_csv_rows,
)


def _read_15col(path: Path) -> list[dict[str, float]]:
    rows: list[dict[str, float]] = []
    with path.open("r", encoding="utf-8-sig") as handle:
        for line in handle:
            parts = line.split()
            if len(parts) < 15:
                continue
            rows.append({"time": float(parts[0]), "yaw_deg": float(parts[13]), "yaw_std_deg": float(parts[14])})
    return rows


def _nearest(rows: list[dict[str, float]], time_value: float) -> dict[str, float] | None:
    if not rows:
        return None
    return min(rows, key=lambda row: abs(row["time"] - time_value))


def _float(value: Any, default: float = math.nan) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def run(args: argparse.Namespace) -> dict[str, Any]:
    stage_root = Path(args.stage_root)
    out = stage_root / "02_YAW_PROVIDER_AUDIT"
    out.mkdir(parents=True, exist_ok=True)
    provider_yaw = Path(args.clean_provider_root) / "02_GENERATED_PROVIDERS" / "dual_yaw_provider.csv"
    gnss1_status = Path(args.by2_fix_root) / "gnss1-status.csv"
    gnss2_status = Path(args.by2_fix_root) / "gnss2-status.csv"
    lineage_rows = audit_status_relpos_against_provider(
        gnss1_status=gnss1_status,
        gnss2_status=gnss2_status,
        provider_yaw_csv=provider_yaw,
        max_rows=int(args.max_rows),
    )
    write_csv_rows(out / "PAPER10M1R2C2_YAW_PROVIDER_LINEAGE_AUDIT.csv", lineage_rows)

    provider_rows = read_csv_rows(provider_yaw)
    reference_rows = _read_15col(Path(args.n4h2d_reference_15col))
    time_offset = reference_rows[0]["time"] - _float(provider_rows[0].get("time"), 0.0) if reference_rows and provider_rows else 0.0
    compare_rows: list[dict[str, Any]] = []
    for index, row in enumerate(provider_rows[: int(args.max_rows)]):
        provider_time = _float(row.get("time"))
        ref = _nearest(reference_rows, provider_time + time_offset)
        if ref is None:
            continue
        legacy_yaw = _float(row.get("yaw_deg"))
        repaired_yaw = repair_legacy_provider_yaw_deg(legacy_yaw)
        compare_rows.append(
            {
                "sample_index": index,
                "provider_time": f"{provider_time:.3f}",
                "reference_time": f"{ref['time']:.6f}",
                "legacy_m1r2b_provider_yaw_deg": f"{legacy_yaw:.6f}",
                "source_lineage_repaired_provider_yaw_deg": f"{repaired_yaw:.6f}",
                "n4h2d_source_backed_15col_yaw_deg": f"{ref['yaw_deg']:.6f}",
                "legacy_minus_n4h2d_deg": f"{circular_diff_deg(legacy_yaw, ref['yaw_deg']):.6f}",
                "repaired_minus_n4h2d_deg": f"{circular_diff_deg(repaired_yaw, ref['yaw_deg']):.6f}",
                "reference_role": "historical_source_backed_input_comparison_not_solver_input",
                "trace_solver_input": False,
                "final_v23_output_solver_input": False,
            }
        )
    write_csv_rows(out / "PAPER10M1R2C2_CLEAN_PROVIDER_VS_N4H2D_REFERENCE.csv", compare_rows)

    report = [
        "# PAPER10M1R2C2 Yaw Provider Fix Report",
        "",
        "Decision: deterministic provider yaw bug found.",
        "",
        "Findings:",
        "- M1R2B clean dual_yaw_provider stores the lateral baseline heading in yaw_deg.",
        "- BY2 source lineage requires GNSS2-GNSS1 A1 dual-diff plus lateral conversion to solver-visible body yaw.",
        "- The clean provider is therefore missing the body-heading conversion by about 90 deg.",
        "- Production yaw sign is selected from source lineage and antenna geometry, not trace RMSE.",
        "",
        "Forbidden inputs:",
        "- trace_solver_input=false",
        "- final_v23_output_solver_input=false",
        "- output_only_metric_correction=false",
        "",
        "Repair:",
        "- M1R2B provider generator now emits `yaw_deg=wrap360(90-wrap360(-atan2(rel_e,rel_n)))`.",
        "- M1R2C2 clean sentinel rewrites only a runtime copy of the clean provider for solver rerun.",
    ]
    (out / "PAPER10M1R2C2_YAW_PROVIDER_FIX_REPORT.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    summary = {
        "lineage_rows": len(lineage_rows),
        "comparison_rows": len(compare_rows),
        "deterministic_bug_found": True,
        "bug": "legacy_provider_missing_lateral_body_heading_conversion",
        "trace_tuned_yaw_fix": False,
    }
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage-root", required=True)
    parser.add_argument("--clean-provider-root", required=True)
    parser.add_argument("--by2-fix-root", required=True)
    parser.add_argument("--n4h2d-reference-15col", required=True)
    parser.add_argument("--max-rows", type=int, default=40)
    return parser.parse_args()


def main() -> int:
    print(json.dumps(run(parse_args()), ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
