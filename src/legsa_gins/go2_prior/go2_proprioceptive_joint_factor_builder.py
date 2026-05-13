"""N7C6 Go2 proprioceptive joint observation factor builder.

中文说明：joint observation z=[roll,pitch,vN,vE] 是 Go2 本体观测，不是 truth；
runtime 另写 separate CSV 供 C++ sequential-equivalent EKF update 使用。
"""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path
from typing import Any

from legsa_gins.go2_prior.go2_attitude_strength_calibration import (
    ATTITUDE_STD_POLICIES_DEG,
    build_attitude_strength_prior_rows,
    read_csv_rows,
    summarize_attitude_prior_rows,
    write_attitude_prior_csv,
)
from legsa_gins.go2_prior.go2_horizontal_velocity_strength_calibration import write_strength_prior_csv


HV_STD_DEFAULT = 1.0
STD_VD_DISABLED = 999.0

JOINT_FIELDS = [
    "time",
    "roll_rad",
    "pitch_rad",
    "vn",
    "ve",
    "std_roll_rad",
    "std_pitch_rad",
    "std_vn",
    "std_ve",
    "std_vd",
    "update_flag",
    "source_status",
    "policy",
    "mode",
    "gait_type",
    "go2_truth_claim",
]


def _f(value: Any, fallback: float = math.nan) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return fallback
    return out if math.isfinite(out) else fallback


def _nearest(rows: list[dict[str, Any]], time_value: float, start: int, tol: float) -> tuple[dict[str, Any] | None, int]:
    if not rows:
        return None, start
    idx = max(0, min(start, len(rows) - 1))
    while idx + 1 < len(rows) and abs(_f(rows[idx + 1].get("time"), 0.0) - time_value) <= abs(_f(rows[idx].get("time"), 0.0) - time_value):
        idx += 1
    return (rows[idx] if abs(_f(rows[idx].get("time"), 0.0) - time_value) <= tol else None), idx


def _velocity_row(source: dict[str, Any], *, std: float, policy: str) -> dict[str, Any]:
    return {
        "time": _f(source.get("time"), 0.0),
        "vn": _f(source.get("vn"), 0.0),
        "ve": _f(source.get("ve"), 0.0),
        "vd": 0.0,
        "std_vn": std,
        "std_ve": std,
        "std_vd": STD_VD_DISABLED,
        "confidence": source.get("confidence", ""),
        "confidence_level": source.get("confidence_level", ""),
        "update_flag": "true",
        "reason_codes": f"n7c6_{policy}_horizontal_velocity_fixed",
        "source_status": "active",
        "quality_flag": f"n7c6_{policy}",
        "contact_model": source.get("contact_model", ""),
        "contact_label": source.get("contact_label", ""),
        "frame_candidate": source.get("frame_candidate", ""),
        "prior_policy": f"n7c6_{policy}_horizontal",
        "diagnostic_only": "false",
        "go2_velocity_truth_claim": "false",
    }


def build_joint_factor_rows(
    *,
    go2_rows: list[dict[str, Any]],
    horizontal_rows: list[dict[str, Any]],
    std_roll_pitch_deg: float,
    std_vn_ve: float = HV_STD_DEFAULT,
    policy_name: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    hrows = sorted(horizontal_rows, key=lambda row: _f(row.get("time"), 0.0))
    hidx = 0
    joint_rows: list[dict[str, Any]] = []
    attitude_rows = build_attitude_strength_prior_rows(go2_rows, std_deg=std_roll_pitch_deg)
    velocity_rows: list[dict[str, Any]] = []
    std_rp_rad = std_roll_pitch_deg * math.pi / 180.0
    for row in attitude_rows:
        hrow, hidx = _nearest(hrows, _f(row.get("time"), 0.0), hidx, 0.08)
        if hrow is None:
            continue
        velocity = _velocity_row(hrow, std=std_vn_ve, policy=policy_name)
        velocity_rows.append(velocity)
        joint_rows.append(
            {
                "time": row["time"],
                "roll_rad": row["roll_rad"],
                "pitch_rad": row["pitch_rad"],
                "vn": velocity["vn"],
                "ve": velocity["ve"],
                "std_roll_rad": std_rp_rad,
                "std_pitch_rad": std_rp_rad,
                "std_vn": std_vn_ve,
                "std_ve": std_vn_ve,
                "std_vd": STD_VD_DISABLED,
                "update_flag": "true",
                "source_status": "active",
                "policy": policy_name,
                "mode": row.get("mode", ""),
                "gait_type": row.get("gait_type", ""),
                "go2_truth_claim": "false",
            }
        )
    return joint_rows, attitude_rows, velocity_rows


def write_joint_factor_csv(path: str | Path, rows: list[dict[str, Any]]) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=JOINT_FIELDS)
        writer.writeheader()
        writer.writerows([{field: row.get(field, "") for field in JOINT_FIELDS} for row in rows])
    return output


def build_and_write_joint_factor_priors(
    *,
    output_dir: str | Path,
    go2_body_state_csv: str | Path,
    horizontal_prior_csv: str | Path,
    policies: dict[str, dict[str, float]] | None = None,
) -> tuple[dict[str, dict[str, Path]], dict[str, Any]]:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    go2_rows = read_csv_rows(go2_body_state_csv)
    horizontal_rows = read_csv_rows(horizontal_prior_csv)
    policy_table = policies or {
        "joint_rp5deg_hv1p0": {"rp_deg": ATTITUDE_STD_POLICIES_DEG["rp5deg"], "hv_std": 1.0},
        "joint_rp3deg_hv1p0": {"rp_deg": ATTITUDE_STD_POLICIES_DEG["rp3deg"], "hv_std": 1.0},
        "joint_rp1p6deg_hv1p0": {"rp_deg": ATTITUDE_STD_POLICIES_DEG["rp1p6deg"], "hv_std": 1.0},
        "joint_rp1deg_hv1p0": {"rp_deg": ATTITUDE_STD_POLICIES_DEG["rp1deg"], "hv_std": 1.0},
        "joint_rp0p75_hv1p0_diagnostic": {"rp_deg": ATTITUDE_STD_POLICIES_DEG["rp0p75deg"], "hv_std": 1.0},
        "joint_rp1p6deg_hv0p75_diagnostic": {"rp_deg": ATTITUDE_STD_POLICIES_DEG["rp1p6deg"], "hv_std": 0.75},
    }
    paths: dict[str, dict[str, Path]] = {}
    reports: dict[str, Any] = {}
    for policy, values in policy_table.items():
        joint_rows, attitude_rows, velocity_rows = build_joint_factor_rows(
            go2_rows=go2_rows,
            horizontal_rows=horizontal_rows,
            std_roll_pitch_deg=values["rp_deg"],
            std_vn_ve=values["hv_std"],
            policy_name=policy,
        )
        policy_dir = out / "priors" / policy
        paths[policy] = {
            "joint": write_joint_factor_csv(policy_dir / "GO2_PROPRIOCEPTIVE_FACTOR_PRIORS.csv", joint_rows),
            "attitude": write_attitude_prior_csv(policy_dir / "GO2_PROPRIOCEPTIVE_ATTITUDE_PRIORS.csv", attitude_rows),
            "horizontal": write_strength_prior_csv(policy_dir / "GO2_PROPRIOCEPTIVE_HORIZONTAL_VELOCITY_PRIORS.csv", velocity_rows),
        }
        reports[policy] = {
            "policy": policy,
            "joint_row_count": len(joint_rows),
            "attitude": summarize_attitude_prior_rows(attitude_rows, std_deg=values["rp_deg"]),
            "horizontal_std_vn": values["hv_std"],
            "horizontal_std_ve": values["hv_std"],
            "std_vd": STD_VD_DISABLED,
            "sequential_equivalent": True,
        }
    report = {
        "stage": "N7C6_go2_proprioceptive_joint_factor",
        "policy_reports": reports,
        "joint_observation_definition": "z=[roll_go2,pitch_go2,vN_go2,vE_go2]",
        "sequential_equivalent": True,
        "go2_not_truth": True,
        "go2_position_prior_enabled": False,
        "go2_yaw_prior_enabled": False,
        "go2_vertical_velocity_prior_enabled": False,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "paper_performance_claim": False,
        "fgo": False,
    }
    (out / "GO2_PROPRIOCEPTIVE_JOINT_FACTOR_PRIOR_BUILD_REPORT.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return paths, report
