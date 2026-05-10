"""Compare raw Doppler velocity against receiver-native clean GNSS velocity.

中文说明：比较只用于来源完整性和观测关系诊断；clean .gnss 速度不能作为 raw
Doppler 因子来源。
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


def _rmse(values: list[float]) -> float | None:
    finite = [value for value in values if math.isfinite(value)]
    return math.sqrt(sum(value * value for value in finite) / len(finite)) if finite else None


def _p95(values: list[float]) -> float | None:
    finite = sorted(abs(value) for value in values if math.isfinite(value))
    if not finite:
        return None
    return finite[max(0, min(len(finite) - 1, math.ceil(0.95 * len(finite)) - 1))]


def _corr(a: list[float], b: list[float]) -> float | None:
    pairs = [(x, y) for x, y in zip(a, b) if math.isfinite(x) and math.isfinite(y)]
    if len(pairs) < 2:
        return None
    xs, ys = zip(*pairs)
    mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
    num = sum((x - mx) * (y - my) for x, y in pairs)
    denx = math.sqrt(sum((x - mx) ** 2 for x in xs))
    deny = math.sqrt(sum((y - my) ** 2 for y in ys))
    return num / (denx * deny) if denx and deny else None


def _factor_rows(path: str | Path) -> list[dict[str, float]]:
    with Path(path).open(newline="", encoding="utf-8") as handle:
        return [
            {"time": _f(row.get("time")), "vn": _f(row.get("vn")), "ve": _f(row.get("ve")), "vd": _f(row.get("vd"))}
            for row in csv.DictReader(handle)
        ]


def _gnss_rows(path: str | Path) -> list[dict[str, float]]:
    rows: list[dict[str, float]] = []
    for line in Path(path).read_text(encoding="utf-8", errors="ignore").splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        cells = line.split()
        if len(cells) >= 10:
            # 中文说明：15-column .gnss 的 vn/ve/vd 是 receiver-native baseline velocity，只用于对比。
            rows.append({"time": _f(cells[0]), "vn": _f(cells[7]), "ve": _f(cells[8]), "vd": _f(cells[9])})
    return rows


def compare_raw_doppler_velocity_to_receiver_velocity(
    raw_factor_csv: str | Path,
    clean_gnss_15col: str | Path,
    *,
    tolerance: float = 0.55,
) -> dict[str, Any]:
    raw = _factor_rows(raw_factor_csv)
    gnss = _gnss_rows(clean_gnss_15col)
    aligned: list[tuple[dict[str, float], dict[str, float]]] = []
    idx = 0
    for row in gnss:
        while idx + 1 < len(raw) and abs(raw[idx + 1]["time"] - row["time"]) <= abs(raw[idx]["time"] - row["time"]):
            idx += 1
        if raw and abs(raw[idx]["time"] - row["time"]) <= tolerance:
            aligned.append((raw[idx], row))
    diffs = {axis: [r[axis] - g[axis] for r, g in aligned] for axis in ["vn", "ve", "vd"]}
    horizontal = [math.hypot(dn, de) for dn, de in zip(diffs["vn"], diffs["ve"])]
    bias = {axis: (sum(values) / len(values) if values else None) for axis, values in diffs.items()}
    possible_copy = bool(aligned) and max((_rmse(diffs[axis]) or 0.0) for axis in ["vn", "ve", "vd"]) < 1.0e-6
    return {
        "aligned_count": len(aligned),
        "vn_diff_rmse": _rmse(diffs["vn"]),
        "ve_diff_rmse": _rmse(diffs["ve"]),
        "vd_diff_rmse": _rmse(diffs["vd"]),
        "horizontal_velocity_diff_rmse": _rmse(horizontal),
        "velocity_diff_p95": _p95(horizontal + diffs["vd"]),
        "bias_n": bias["vn"],
        "bias_e": bias["ve"],
        "bias_d": bias["vd"],
        "corr_n": _corr([r["vn"] for r, _ in aligned], [g["vn"] for _, g in aligned]),
        "corr_e": _corr([r["ve"] for r, _ in aligned], [g["ve"] for _, g in aligned]),
        "corr_d": _corr([r["vd"] for r, _ in aligned], [g["vd"] for _, g in aligned]),
        "raw_doppler_not_nav_pvt": True,
        "raw_doppler_not_gnss_15col": True,
        "possible_pvt_velocity_copy_suspect": possible_copy,
        "paper_performance_claim": False,
    }


def write_report(report: dict[str, Any], path: str | Path) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
