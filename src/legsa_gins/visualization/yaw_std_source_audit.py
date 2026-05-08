"""Yaw STD source audit for N4H2F.

中文说明：本模块区分 input.gnss 的观测 yaw_std 与 KF_GINS_STD 的状态协方差
std；yaw_std=1.5 不自动等价于 yaw 值注入 1.5deg 噪声。
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from statistics import median
from typing import Any

from legsa_gins.visualization.dual_replay_plot_loader import parse_15col_gnss, parse_kfgins_std


def _mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def _p95(values: list[float]) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = int(math.ceil(0.95 * len(ordered))) - 1
    return ordered[max(0, min(index, len(ordered) - 1))]


def _stats(values: list[float]) -> dict[str, Any]:
    unique = sorted(set(round(value, 9) for value in values))
    return {
        "count": len(values),
        "min": min(values) if values else None,
        "max": max(values) if values else None,
        "mean": _mean(values),
        "median": median(values) if values else None,
        "p95": _p95(values),
        "unique_values": unique if len(unique) <= 12 else None,
        "unique_count": len(unique),
        "is_fixed_1p5": bool(values and all(abs(value - 1.5) <= 1.0e-9 for value in values)),
    }


def analyze_yaw_std_source(input_gnss_path: str | Path, kfgins_std_path: str | Path | None = None) -> dict[str, Any]:
    """Analyze observation yaw_std and optional state yaw std separately."""

    input_rows = parse_15col_gnss(input_gnss_path)
    obs_values = [float(row["yaw_std"]) for row in input_rows]
    obs_stats = _stats(obs_values)
    state_stats: dict[str, Any] = {}
    if kfgins_std_path and Path(kfgins_std_path).exists():
        std_rows = parse_kfgins_std(kfgins_std_path)
        state_values = [float(row["std_yaw_deg"]) for row in std_rows]
        state_stats = _stats(state_values)
        state_stats.update(
            {
                "initial_std_deg": state_values[0] if state_values else None,
                "final_std_deg": state_values[-1] if state_values else None,
                "is_state_covariance_std": True,
            }
        )
    report = {
        "phase": "N4H2F",
        "observation_yaw_std": obs_stats,
        "source_interpretation": "observation_yaw_std_from_process_data_input",
        "yaw_std_is_measurement_std_not_noise_injection": True,
        "obs_std_yaw_is_gnss_measurement_std": True,
        "state_yaw_std": state_stats,
        "state_yaw_std_available": bool(state_stats),
        "state_yaw_std_is_filter_covariance_std": bool(state_stats),
        "yaw_std_not_used_to_relax_gate": True,
        "yaw_gate_rule": "yaw_rmse_deg <= 2.0",
        "interpretation_notes": [
            "input.gnss column 15 is observation yaw standard deviation",
            "KF_GINS_STD yaw std is filter state covariance standard deviation",
            "These two standard deviations must not be treated as the same signal",
            "yaw_std=1.5 deg is not proof that yaw values were injected with 1.5 deg random noise",
        ],
        "trace_solver_input": False,
        "output_only_correction": False,
        "solver_output_changed": False,
        "bad_epoch_deletion_for_metric": False,
        "numerical_performance_claim": False,
    }
    return report


def write_yaw_std_source_report(path: str | Path, report: dict[str, Any]) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output
