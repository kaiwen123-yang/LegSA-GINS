"""N5C raw Doppler ablation matrix.

中文说明：矩阵只定义诊断实验组合；除 baseline_plus_raw_doppler_r1 外，其余组合
都不能作为 proposed candidate 或调参结论。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


REQUIRED_VARIANTS = [
    ("baseline_full", True, False, 1.0, True, False),
    ("baseline_plus_raw_doppler_r1", True, True, 1.0, False, True),
    ("position_yaw_plus_raw_doppler_r1", False, True, 1.0, True, False),
    ("position_yaw_only", False, False, 1.0, True, False),
    ("baseline_plus_raw_doppler_r0p5", True, True, 0.5, True, False),
    ("baseline_plus_raw_doppler_r2", True, True, 2.0, True, False),
    ("baseline_plus_raw_doppler_r5", True, True, 5.0, True, False),
]


def build_n5c_ablation_matrix(factor_csv: str | Path, output_dir: str | Path, *, run_rscale_screen: bool = True) -> dict[str, Any]:
    out = Path(output_dir)
    rows: list[dict[str, Any]] = []
    for variant_id, enable_receiver_velocity, enable_raw, r_scale, diagnostic_only, proposed in REQUIRED_VARIANTS:
        if not run_rscale_screen and variant_id in {
            "baseline_plus_raw_doppler_r0p5",
            "baseline_plus_raw_doppler_r2",
            "baseline_plus_raw_doppler_r5",
        }:
            continue
        rows.append(
            {
                "variant_id": variant_id,
                "enable_receiver_velocity_update": enable_receiver_velocity,
                "enable_raw_doppler": enable_raw,
                "raw_doppler_R_scale": r_scale,
                "diagnostic_only": diagnostic_only,
                "proposed_candidate": proposed,
                "paper_performance_claim": False,
                "config_path": str(out / "runtime_configs" / f"{variant_id}.yaml"),
                "output_dir": str(out / "variants" / variant_id),
                "raw_doppler_factor_path": str(factor_csv) if enable_raw else "",
            }
        )
    report = {
        "stage": "N5C",
        "matrix": rows,
        "variant_count": len(rows),
        "only_baseline_plus_raw_doppler_r1_proposed": all(
            row["proposed_candidate"] == (row["variant_id"] == "baseline_plus_raw_doppler_r1") for row in rows
        ),
        "paper_performance_claim": False,
        "no_outperform_final_v23_claim": True,
    }
    return report


def write_matrix(report: dict[str, Any], output_path: str | Path) -> None:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
