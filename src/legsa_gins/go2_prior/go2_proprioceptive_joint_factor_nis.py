"""N7C6 joint factor residual/NIS diagnostics.

中文说明：NIS 只读取 solver runtime residual/source-aware trace 做诊断，不反向调参。
"""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path
from typing import Any


def _f(value: Any, fallback: float = math.nan) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return fallback
    return out if math.isfinite(out) else fallback


def _read_csv(path: str | Path) -> list[dict[str, Any]]:
    source = Path(path)
    if not source.exists():
        return []
    with source.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _percentile(values: list[float], p: float) -> float:
    finite = sorted(value for value in values if math.isfinite(value))
    if not finite:
        return 0.0
    return finite[min(len(finite) - 1, int(p * (len(finite) - 1)))]


def _stats(values: list[float]) -> dict[str, float]:
    finite = [value for value in values if math.isfinite(value)]
    return {
        "count": len(finite),
        "p50": _percentile(finite, 0.50),
        "p95": _percentile(finite, 0.95),
        "max": max(finite, default=0.0),
    }


def _source_stats(rows: list[dict[str, Any]], source: str) -> dict[str, Any]:
    selected = [row for row in rows if row.get("source_id") == source]
    residual = [_f(row.get("residual_norm"), math.nan) for row in selected]
    nis = [_f(row.get("normalized_innovation"), math.nan) for row in selected]
    scale = [_f(row.get("combined_R_scale"), math.nan) for row in selected]
    return {
        "source_id": source,
        "residual_norm": _stats(residual),
        "nis_proxy": _stats(nis),
        "source_aware_R_scale": _stats(scale),
        "overconfidence_flag": _percentile(nis, 0.95) > 9.0 if selected else False,
        "stuck_at_cap_flag": bool(scale) and _percentile(scale, 0.95) >= max(scale, default=0.0) and max(scale, default=0.0) >= 20.0,
        "update_count": len(selected),
    }


def build_n7c6_joint_factor_nis_report(output_dir: str | Path, variant_ids: list[str]) -> dict[str, Any]:
    root = Path(output_dir)
    variants: dict[str, Any] = {}
    for variant_id in variant_ids:
        variant_root = root / "variants" / variant_id
        rows = _read_csv(variant_root / "SOURCE_AWARE_WEIGHT_TRACE.csv")
        attitude = _source_stats(rows, "go2_attitude_roll_pitch")
        horizontal = _source_stats(rows, "go2_horizontal_velocity")
        variants[variant_id] = {
            "variant_id": variant_id,
            "attitude": attitude,
            "horizontal_velocity": horizontal,
            "joint_update_count_proxy": min(attitude["update_count"], horizontal["update_count"]),
            "overconfidence_flag": attitude["overconfidence_flag"] or horizontal["overconfidence_flag"],
            "stuck_at_cap_flag": attitude["stuck_at_cap_flag"] or horizontal["stuck_at_cap_flag"],
        }
    return {
        "stage": "N7C6_go2_proprioceptive_joint_factor",
        "variants": variants,
        "any_overconfidence": any(row.get("overconfidence_flag") for row in variants.values()),
        "any_stuck_at_cap": any(row.get("stuck_at_cap_flag") for row in variants.values()),
        "go2_not_truth": True,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "paper_performance_claim": False,
        "fgo": False,
    }


def write_n7c6_joint_factor_nis_report(path: str | Path, report: dict[str, Any]) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output
