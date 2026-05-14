"""Dataset builder for N8F legged candidate FGO activation.

该 builder 只读取 runtime-only stage 报告，不把 raw data 或本地绝对路径写入
tracked 文件；所有路径在 runner 参数中传入。
"""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Mapping, Sequence

from .fgo_contact_aware_weighting_factor import build_contact_aware_weights, read_csv_dicts
from .fgo_foot_kinematic_velocity_factor import build_foot_kinematic_velocity_factors
from .fgo_n8c_visual_loader import load_n8c_visual_inputs
from .fgo_raw_doppler_dataset_link import link_raw_doppler_to_fgo_epochs
from .fgo_relative_odometry_between_factor import build_relative_odometry_between_factors
from .fgo_yaw_convention_fix import _f, rows_to_dataset
from .fgo_yawrate_between_factor import build_yawrate_between_factors


@dataclass
class LeggedFactorDataset:
    ekf_rows: List[Dict[str, Any]]
    raw_factors: List[Any]
    contact_rows: List[Any]
    foot_factor_rows: List[Any]
    yawrate_factor_rows: List[Any]
    relative_factor_rows: List[Any]
    source_reports: Dict[str, Any]
    manifest: Dict[str, Any]


def read_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def rows_to_vectors(ekf_rows: Sequence[Mapping[str, Any]]) -> List[List[float]]:
    dataset = rows_to_dataset([dict(row) for row in ekf_rows])
    return [state.vector() for state in dataset.states]


def epoch_times_from_rows(ekf_rows: Sequence[Mapping[str, Any]]) -> List[float]:
    return [_f(row.get("time", row.get("timestamp")), float(index)) for index, row in enumerate(ekf_rows)]


def _relative_report_with_scale_hint(n7c5_root: Path) -> Dict[str, Any]:
    report = read_json(n7c5_root / "GO2_RELATIVE_ODOMETRY_CANDIDATE_REPORT.json")
    # N7C5 report often contains aggregate-only evidence. Keep the hint bounded.
    report.setdefault("relative_odometry_scale_hint", 1.0)
    return report


def build_legged_factor_dataset(
    *,
    n8b_root: str | Path,
    n8a2_root: str | Path,
    n7c5_root: str | Path,
    n5b_root: str | Path,
    max_factor_rows: int | None = None,
) -> LeggedFactorDataset:
    n7c5 = Path(n7c5_root)
    visual_manifest, visual_data = load_n8c_visual_inputs(n8b_root=n8b_root, n8a2_root=n8a2_root, rerun_missing_timeseries=True)
    ekf_rows = [dict(row) for row in visual_data.get("ekf_rows", [])]
    epoch_times = epoch_times_from_rows(ekf_rows)
    vectors = rows_to_vectors(ekf_rows)

    raw_factors, raw_report = link_raw_doppler_to_fgo_epochs(fgo_rows=ekf_rows, n5b_root=n5b_root)
    foot_rows = read_csv_dicts(n7c5 / "GO2_FOOT_KINEMATIC_VELOCITY_TIMESERIES.csv")
    mode_rows = read_csv_dicts(n7c5 / "GO2_MODE_GAIT_PHASE_TIMESERIES.csv")

    contact_rows = build_contact_aware_weights(epoch_times=epoch_times, mode_rows=mode_rows, foot_rows=foot_rows)
    foot_factor_rows = build_foot_kinematic_velocity_factors(
        epoch_times=epoch_times,
        foot_rows=foot_rows,
        contact_rows=contact_rows,
        max_rows=max_factor_rows,
    )
    yawrate_factor_rows = build_yawrate_between_factors(
        epoch_times=epoch_times,
        yaw_speed_rows=mode_rows,
        solution_vectors=vectors,
        max_rows=max_factor_rows,
    )
    relative_report = _relative_report_with_scale_hint(n7c5)
    relative_factor_rows = build_relative_odometry_between_factors(
        epoch_times=epoch_times,
        solution_vectors=vectors,
        contact_rows=contact_rows,
        aggregate_report=relative_report,
        max_rows=max_factor_rows,
    )

    reports = {
        "raw_doppler_alignment": raw_report,
        "n7c5_foot_kinematic_velocity": read_json(n7c5 / "GO2_FOOT_KINEMATIC_VELOCITY_CANDIDATE_REPORT.json"),
        "n7c5_contact_probability": read_json(n7c5 / "GO2_CONTACT_PROBABILITY_FACTOR_REVIEW.json"),
        "n7c5_yawrate": read_json(n7c5 / "GO2_YAWRATE_CONSISTENCY_CANDIDATE_REPORT.json"),
        "n7c5_relative_odometry": relative_report,
        "n8c_visual_manifest": visual_manifest,
    }
    manifest = {
        "stage": "N8F",
        "ekf_rows": len(ekf_rows),
        "raw_factor_rows": len(raw_factors),
        "contact_weight_rows": len(contact_rows),
        "foot_kinematic_factor_rows": len(foot_factor_rows),
        "yawrate_between_factor_rows": len(yawrate_factor_rows),
        "relative_odometry_factor_rows": len(relative_factor_rows),
        "n7c5_role_alias": "N7C5_REPORT_OUTPUT_DIR",
        "n8b_role_alias": "N8B_REPORT_OUTPUT_DIR",
        "n8a2_role_alias": "N8A2_REPORT_OUTPUT_DIR",
        "n5b_role_alias": "N5B_REPORT_OUTPUT_DIR",
        "no_feedback": True,
        "output_substitution": False,
        "trace_solver_input": False,
        "finalv23_solver_input": False,
        "paper_performance_claim": False,
    }
    return LeggedFactorDataset(
        ekf_rows=ekf_rows,
        raw_factors=raw_factors,
        contact_rows=contact_rows,
        foot_factor_rows=foot_factor_rows,
        yawrate_factor_rows=yawrate_factor_rows,
        relative_factor_rows=relative_factor_rows,
        source_reports=reports,
        manifest=manifest,
    )


def write_factor_table_csv(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "variant",
        "factor_type",
        "factor_count",
        "residual_rows",
        "jacobian_nonzero",
        "enabled",
        "diagnostic_only",
    ]
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({name: row.get(name, "") for name in fieldnames})

