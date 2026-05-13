"""Build diagnostic-only Go2 yaw-rate prior evidence for N7B3.

中文说明：当前 v23 error-state 没有 yaw-rate state，本模块只构造 runtime-only
CSV 和一致性报告；C++ manifest 必须报告 yaw_rate_prior_not_activated_due_to_state_model。
"""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path
from typing import Any

from .go2_contact_state import _f, _time_value
from .go2_velocity_quality import _corr, _rmse


FIELDS = [
    "time",
    "yaw_rate_radps",
    "std_yaw_rate_radps",
    "source_status",
    "quality_flag",
    "diagnostic_only",
    "formal_activation_allowed",
]


def build_go2_yaw_rate_diagnostic_prior(
    *,
    go2_rows: list[dict[str, Any]],
    output_dir: str | Path,
) -> tuple[Path, dict[str, Any]]:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []
    derivative_pairs: list[tuple[float, float]] = []
    sorted_rows = sorted(go2_rows, key=_time_value)
    previous_time: float | None = None
    previous_yaw: float | None = None
    diffs: list[float] = []
    for row in sorted_rows:
        time_value = _time_value(row)
        yaw_speed = _f(row.get("yaw_speed_radps"))
        yaw = _f(row.get("yaw_rad"))
        derivative = math.nan
        if previous_time is not None and previous_yaw is not None and math.isfinite(yaw) and time_value > previous_time:
            delta = yaw - previous_yaw
            while delta > math.pi:
                delta -= 2.0 * math.pi
            while delta <= -math.pi:
                delta += 2.0 * math.pi
            derivative = delta / (time_value - previous_time)
        if math.isfinite(yaw_speed):
            rows.append(
                {
                    "time": time_value,
                    "yaw_rate_radps": yaw_speed,
                    "std_yaw_rate_radps": 0.50,
                    "source_status": "active",
                    "quality_flag": "diagnostic_yaw_speed",
                    "diagnostic_only": True,
                    "formal_activation_allowed": False,
                }
            )
        if math.isfinite(yaw_speed) and math.isfinite(derivative):
            derivative_pairs.append((yaw_speed, derivative))
            diffs.append(yaw_speed - derivative)
        if math.isfinite(yaw):
            previous_time = time_value
            previous_yaw = yaw
    path = out / "GO2_YAW_RATE_WEAK_PRIORS_DIAGNOSTIC.csv"
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    corr = _corr([pair[0] for pair in derivative_pairs], [pair[1] for pair in derivative_pairs])
    report = {
        "stage": "N7B3_go2_contact_velocity_diagnostic_activation",
        "prior_csv_generated": bool(rows),
        "prior_epoch_count": len(rows),
        "yaw_speed_vs_yaw_derivative_correlation": corr,
        "yaw_speed_minus_derivative_rmse": _rmse(diffs),
        "std_policy": {"std_yaw_rate_radps": 0.50, "rule": "conservative_fixed_diagnostic"},
        "diagnostic_only": True,
        "formal_activation_allowed": False,
        "activation_allowed_for_diagnostic": False,
        "activation_status": "yaw_rate_prior_not_activated_due_to_state_model",
        "go2_yaw_prior_enabled": False,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "paper_performance_claim": False,
        "fgo": False,
    }
    (out / "GO2_YAW_RATE_PRIOR_DIAGNOSTIC_BUILD_REPORT.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path, report
