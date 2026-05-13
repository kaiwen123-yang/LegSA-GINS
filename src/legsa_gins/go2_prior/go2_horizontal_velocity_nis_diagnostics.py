"""N7C4 residual and NIS-proxy diagnostics for Go2 horizontal velocity.

中文说明：NIS proxy 只来自 solver 输出的 source-aware residual diagnostics，
用于发现过强 prior 的过度自信风险，不作为 trace/final_v23 调参入口。
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


def _variant_trace_rows(variant_dir: str | Path) -> list[dict[str, Any]]:
    rows = []
    for row in _read_csv(Path(variant_dir) / "SOURCE_AWARE_WEIGHT_TRACE.csv"):
        if str(row.get("source_id") or "") == "go2_horizontal_velocity":
            rows.append(row)
    return rows


def summarize_go2_horizontal_velocity_nis(variant_id: str, variant_dir: str | Path) -> dict[str, Any]:
    rows = _variant_trace_rows(variant_dir)
    residuals = [_f(row.get("residual_norm"), math.nan) for row in rows]
    normalized = [_f(row.get("normalized_innovation"), math.nan) for row in rows]
    scales = [_f(row.get("combined_R_scale"), math.nan) for row in rows]
    nis_proxy = [value * value for value in normalized if math.isfinite(value)]
    p95 = _percentile(nis_proxy, 0.95)
    overconfident = p95 > 9.0 or _percentile(normalized, 0.95) > 3.0
    return {
        "variant_id": variant_id,
        "trace_rows": len(rows),
        "residual_norm_p50": _percentile(residuals, 0.50),
        "residual_norm_p95": _percentile(residuals, 0.95),
        "residual_norm_max": max([value for value in residuals if math.isfinite(value)], default=0.0),
        "normalized_innovation_p50": _percentile(normalized, 0.50),
        "normalized_innovation_p95": _percentile(normalized, 0.95),
        "normalized_innovation_max": max([value for value in normalized if math.isfinite(value)], default=0.0),
        "nis_proxy_p50": _percentile(nis_proxy, 0.50),
        "nis_proxy_p95": p95,
        "nis_proxy_max": max(nis_proxy, default=0.0),
        "high_residual_epoch_count": sum(1 for value in normalized if math.isfinite(value) and value > 3.0),
        "source_aware_R_inflation_count": sum(1 for value in scales if math.isfinite(value) and value > 1.10),
        "source_aware_R_scale_p50": _percentile(scales, 0.50),
        "source_aware_R_scale_p95": _percentile(scales, 0.95),
        "overconfidence_status": "overconfident" if overconfident else ("evidence_missing" if not rows else "not_overconfident"),
        "paper_performance_claim": False,
    }


def build_n7c4_nis_diagnostics(*, output_dir: str | Path, variant_ids: list[str]) -> dict[str, Any]:
    out = Path(output_dir)
    variants = {
        variant_id: summarize_go2_horizontal_velocity_nis(variant_id, out / "variants" / variant_id)
        for variant_id in variant_ids
    }
    report = {
        "stage": "N7C4_go2_horizontal_velocity_strength_calibration",
        "variants": variants,
        "nis_proxy_definition": "normalized_innovation^2 from solver-visible source-aware diagnostics",
        "overconfidence_gate": "nis_proxy_p95<=9 and normalized_innovation_p95<=3",
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "no_trace_tuning": True,
        "no_final_v23_tuning": True,
        "paper_performance_claim": False,
        "go2_velocity_truth_claim": False,
        "fgo": False,
    }
    (out / "GO2_HORIZONTAL_VELOCITY_NIS_DIAGNOSTICS_REPORT.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return report
