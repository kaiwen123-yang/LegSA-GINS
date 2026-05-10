"""N5D raw Doppler velocity-stress matrix.

中文说明：本矩阵只定义 receiver-native velocity stress 诊断组合，用于检查
raw Doppler 在 baseline velocity 受损/禁用时的独立约束能力；stress 结果不
代表真实传感器故障模型，不作为论文性能结果，也不是调参结论。
"""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path
from typing import Any


REQUIRED_VARIANT_IDS = [
    "baseline_full",
    "baseline_plus_raw_doppler_r1",
    "position_yaw_only",
    "position_yaw_plus_raw_doppler_r1",
    "receiver_velocity_disabled_no_raw",
    "receiver_velocity_disabled_plus_raw",
    "receiver_velocity_std_scale_5_no_raw",
    "receiver_velocity_std_scale_5_plus_raw",
    "receiver_velocity_outage_30s_no_raw",
    "receiver_velocity_outage_30s_plus_raw",
    "receiver_velocity_noise_0p5_no_raw",
    "receiver_velocity_noise_0p5_plus_raw",
]

OPTIONAL_VARIANT_IDS = [
    "receiver_velocity_disabled_plus_raw_R_scale_2",
    "receiver_velocity_disabled_plus_raw_R_scale_5",
]


def _factor_start_time(factor_csv: str | Path) -> float:
    path = Path(factor_csv)
    if not path.exists():
        return 0.0
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            try:
                value = float(row.get("time", "nan"))
            except (TypeError, ValueError):
                continue
            if math.isfinite(value):
                return value
    return 0.0


def _row(
    *,
    variant_id: str,
    output_root: Path,
    factor_csv: str | Path,
    enable_receiver_velocity_update: bool,
    enable_raw_doppler: bool,
    receiver_velocity_stress_mode: str = "none",
    receiver_velocity_std_scale: float = 1.0,
    receiver_velocity_outage_start_sec: float = 0.0,
    receiver_velocity_outage_duration_sec: float = 0.0,
    receiver_velocity_additive_noise_std_mps: float = 0.0,
    raw_doppler_R_scale: float = 1.0,
    diagnostic_only: bool = True,
    diagnostic_stress_only: bool = False,
    proposed_factor_diagnostic_evidence: bool = False,
) -> dict[str, Any]:
    return {
        "variant_id": variant_id,
        "enable_receiver_velocity_update": enable_receiver_velocity_update,
        "enable_raw_doppler": enable_raw_doppler,
        "receiver_velocity_stress_mode": receiver_velocity_stress_mode,
        "receiver_velocity_std_scale": receiver_velocity_std_scale,
        "receiver_velocity_outage_start_sec": receiver_velocity_outage_start_sec,
        "receiver_velocity_outage_duration_sec": receiver_velocity_outage_duration_sec,
        "receiver_velocity_additive_noise_std_mps": receiver_velocity_additive_noise_std_mps,
        "receiver_velocity_additive_noise_seed": 20260510,
        "raw_doppler_R_scale": raw_doppler_R_scale,
        "diagnostic_only": diagnostic_only,
        "diagnostic_stress_only": diagnostic_stress_only,
        "proposed_factor_diagnostic_evidence": proposed_factor_diagnostic_evidence,
        "proposed_factor_claim": False,
        "paper_performance_claim": False,
        "no_outperform_final_v23_claim": True,
        "output_only_correction": False,
        "bad_epoch_deletion_for_metric": False,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "raw_doppler_factor_path": str(factor_csv) if enable_raw_doppler else "",
        "config_path": str(output_root / "runtime_configs" / f"{variant_id}.yaml"),
        "output_dir": str(output_root / "variants" / variant_id),
    }


def build_n5d_stress_matrix(factor_csv: str | Path, output_dir: str | Path) -> dict[str, Any]:
    """Build the required N5D stress matrix.

    中文说明：路径只写入 runtime-only matrix/config；tracked 代码不硬编码本机路径。
    """

    out = Path(output_dir)
    outage_start = _factor_start_time(factor_csv)
    rows = [
        _row(
            variant_id="baseline_full",
            output_root=out,
            factor_csv=factor_csv,
            enable_receiver_velocity_update=True,
            enable_raw_doppler=False,
            diagnostic_only=False,
        ),
        _row(
            variant_id="baseline_plus_raw_doppler_r1",
            output_root=out,
            factor_csv=factor_csv,
            enable_receiver_velocity_update=True,
            enable_raw_doppler=True,
            diagnostic_only=False,
            proposed_factor_diagnostic_evidence=True,
        ),
        _row(
            variant_id="position_yaw_only",
            output_root=out,
            factor_csv=factor_csv,
            enable_receiver_velocity_update=False,
            enable_raw_doppler=False,
            diagnostic_stress_only=True,
        ),
        _row(
            variant_id="position_yaw_plus_raw_doppler_r1",
            output_root=out,
            factor_csv=factor_csv,
            enable_receiver_velocity_update=False,
            enable_raw_doppler=True,
            diagnostic_stress_only=True,
        ),
        _row(
            variant_id="receiver_velocity_disabled_no_raw",
            output_root=out,
            factor_csv=factor_csv,
            enable_receiver_velocity_update=True,
            enable_raw_doppler=False,
            receiver_velocity_stress_mode="disabled",
            diagnostic_stress_only=True,
        ),
        _row(
            variant_id="receiver_velocity_disabled_plus_raw",
            output_root=out,
            factor_csv=factor_csv,
            enable_receiver_velocity_update=True,
            enable_raw_doppler=True,
            receiver_velocity_stress_mode="disabled",
            diagnostic_stress_only=True,
        ),
        _row(
            variant_id="receiver_velocity_std_scale_5_no_raw",
            output_root=out,
            factor_csv=factor_csv,
            enable_receiver_velocity_update=True,
            enable_raw_doppler=False,
            receiver_velocity_stress_mode="std_scale",
            receiver_velocity_std_scale=5.0,
            diagnostic_stress_only=True,
        ),
        _row(
            variant_id="receiver_velocity_std_scale_5_plus_raw",
            output_root=out,
            factor_csv=factor_csv,
            enable_receiver_velocity_update=True,
            enable_raw_doppler=True,
            receiver_velocity_stress_mode="std_scale",
            receiver_velocity_std_scale=5.0,
            diagnostic_stress_only=True,
        ),
        _row(
            variant_id="receiver_velocity_outage_30s_no_raw",
            output_root=out,
            factor_csv=factor_csv,
            enable_receiver_velocity_update=True,
            enable_raw_doppler=False,
            receiver_velocity_stress_mode="outage",
            receiver_velocity_outage_start_sec=outage_start,
            receiver_velocity_outage_duration_sec=30.0,
            diagnostic_stress_only=True,
        ),
        _row(
            variant_id="receiver_velocity_outage_30s_plus_raw",
            output_root=out,
            factor_csv=factor_csv,
            enable_receiver_velocity_update=True,
            enable_raw_doppler=True,
            receiver_velocity_stress_mode="outage",
            receiver_velocity_outage_start_sec=outage_start,
            receiver_velocity_outage_duration_sec=30.0,
            diagnostic_stress_only=True,
        ),
        _row(
            variant_id="receiver_velocity_noise_0p5_no_raw",
            output_root=out,
            factor_csv=factor_csv,
            enable_receiver_velocity_update=True,
            enable_raw_doppler=False,
            receiver_velocity_stress_mode="additive_noise",
            receiver_velocity_additive_noise_std_mps=0.5,
            diagnostic_stress_only=True,
        ),
        _row(
            variant_id="receiver_velocity_noise_0p5_plus_raw",
            output_root=out,
            factor_csv=factor_csv,
            enable_receiver_velocity_update=True,
            enable_raw_doppler=True,
            receiver_velocity_stress_mode="additive_noise",
            receiver_velocity_additive_noise_std_mps=0.5,
            diagnostic_stress_only=True,
        ),
        _row(
            variant_id="receiver_velocity_disabled_plus_raw_R_scale_2",
            output_root=out,
            factor_csv=factor_csv,
            enable_receiver_velocity_update=True,
            enable_raw_doppler=True,
            receiver_velocity_stress_mode="disabled",
            raw_doppler_R_scale=2.0,
            diagnostic_stress_only=True,
        ),
        _row(
            variant_id="receiver_velocity_disabled_plus_raw_R_scale_5",
            output_root=out,
            factor_csv=factor_csv,
            enable_receiver_velocity_update=True,
            enable_raw_doppler=True,
            receiver_velocity_stress_mode="disabled",
            raw_doppler_R_scale=5.0,
            diagnostic_stress_only=True,
        ),
    ]
    return {
        "stage": "N5D_raw_doppler_visual_validation_and_velocity_stress_protocol",
        "matrix": rows,
        "required_variant_ids": REQUIRED_VARIANT_IDS,
        "optional_variant_ids": OPTIONAL_VARIANT_IDS,
        "required_variants_present": sorted(REQUIRED_VARIANT_IDS) == sorted(row["variant_id"] for row in rows if row["variant_id"] in REQUIRED_VARIANT_IDS),
        "variant_count": len(rows),
        "stress_variants_diagnostic_only": all(
            row["diagnostic_stress_only"] and row["diagnostic_only"]
            for row in rows
            if row["variant_id"] not in {"baseline_full", "baseline_plus_raw_doppler_r1"}
        ),
        "R_scale_screen_tuning_claim": False,
        "std_scale_screen_tuning_claim": False,
        "paper_performance_claim": False,
        "proposed_factor_claim": False,
        "no_outperform_final_v23_claim": True,
    }


def write_matrix(report: dict[str, Any], output_path: str | Path) -> None:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
