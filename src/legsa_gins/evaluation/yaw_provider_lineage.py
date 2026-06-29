"""BY2 yaw provider lineage helpers for PAPER10M1R2C2.

The functions in this module encode the source-backed A1 dual-difference yaw
convention. They do not inspect trace or solver outputs and therefore cannot
select a production yaw sign from metric performance.
"""

from __future__ import annotations

import csv
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


def wrap360(angle_deg: float) -> float:
    return float(angle_deg) % 360.0


def circular_diff_deg(a_deg: float, b_deg: float) -> float:
    wrapped = (float(a_deg) - float(b_deg) + 180.0) % 360.0 - 180.0
    return -180.0 if wrapped == 180.0 else wrapped


def as_float(value: Any, default: float = math.nan) -> float:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


@dataclass(frozen=True)
class A1YawLineage:
    """One source-backed A1 yaw conversion result."""

    rel_n_m: float
    rel_e_m: float
    rel_d_m: float
    baseline_length_m: float
    baseline_heading_deg: float
    yaw_baseline_deg: float
    yaw_body_deg: float
    yaw_ned_deg: float
    yaw_std_deg: float
    gnss_order_used: str
    lateral_offset_applied: bool
    lateral_offset_sign: str
    yaw_formula: str
    selection_basis: str
    trace_tuned: bool = False


def by2_a1_dual_diff_yaw_from_status_relpos(
    *,
    gnss1_rel_n_m: float,
    gnss1_rel_e_m: float,
    gnss1_rel_d_m: float,
    gnss2_rel_n_m: float,
    gnss2_rel_e_m: float,
    gnss2_rel_d_m: float,
    yaw_std_deg: float = 1.5,
) -> A1YawLineage:
    """Return solver-visible BY2 body yaw from GNSS2-GNSS1 status relpos.

    Recovered BY2/process_data convention:
    rel = GNSS2 - GNSS1, yaw_baseline = -atan2(rel_e, rel_n),
    yaw_body = yaw_baseline, solver yaw_ned = 90 - yaw_body.

    This is algebraically equivalent to baseline_heading + 90 deg when
    baseline_heading = atan2(rel_e, rel_n) for GNSS2-GNSS1.
    """

    rel_n = float(gnss2_rel_n_m) - float(gnss1_rel_n_m)
    rel_e = float(gnss2_rel_e_m) - float(gnss1_rel_e_m)
    rel_d = float(gnss2_rel_d_m) - float(gnss1_rel_d_m)
    baseline = math.sqrt(rel_n * rel_n + rel_e * rel_e + rel_d * rel_d)
    baseline_heading = wrap360(math.degrees(math.atan2(rel_e, rel_n))) if baseline > 1.0e-12 else 0.0
    yaw_baseline = wrap360(-math.degrees(math.atan2(rel_e, rel_n))) if baseline > 1.0e-12 else 0.0
    yaw_body = yaw_baseline
    yaw_ned = wrap360(90.0 - yaw_body)
    return A1YawLineage(
        rel_n_m=rel_n,
        rel_e_m=rel_e,
        rel_d_m=rel_d,
        baseline_length_m=baseline,
        baseline_heading_deg=baseline_heading,
        yaw_baseline_deg=yaw_baseline,
        yaw_body_deg=yaw_body,
        yaw_ned_deg=yaw_ned,
        yaw_std_deg=float(yaw_std_deg),
        gnss_order_used="gnss2_minus_gnss1",
        lateral_offset_applied=True,
        lateral_offset_sign="baseline_heading_plus_90_equivalent",
        yaw_formula="yaw_ned=wrap360(90-wrap360(-atan2(rel_e,rel_n)))",
        selection_basis="BY2 process_data/source-lineage lateral antenna geometry, not trace RMSE",
        trace_tuned=False,
    )


def m1r2b_legacy_provider_yaw_from_status_relpos(
    *,
    gnss1_rel_n_m: float,
    gnss1_rel_e_m: float,
    gnss2_rel_n_m: float,
    gnss2_rel_e_m: float,
) -> float:
    """Return the pre-M1R2C2 legacy provider yaw convention.

    M1R2B wrote atan2(GNSS1-GNSS2 e/n) directly to yaw_deg, which leaves the
    lateral baseline heading in the solver-visible body-yaw column.
    """

    rel_n = float(gnss1_rel_n_m) - float(gnss2_rel_n_m)
    rel_e = float(gnss1_rel_e_m) - float(gnss2_rel_e_m)
    return wrap360(math.degrees(math.atan2(rel_e, rel_n)))


def repair_legacy_provider_yaw_deg(legacy_yaw_deg: float) -> float:
    """Convert legacy M1R2B baseline-heading yaw to BY2 body yaw.

    This is used only for a copied clean sentinel provider. Future full
    provider regeneration should use by2_a1_dual_diff_yaw_from_status_relpos.
    """

    return wrap360(float(legacy_yaw_deg) - 90.0)


def read_csv_rows(path: str | Path) -> list[dict[str, str]]:
    with Path(path).open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv_rows(path: str | Path, rows: Iterable[dict[str, Any]], fieldnames: list[str] | None = None) -> None:
    rows = list(rows)
    if fieldnames is None:
        fieldnames = []
        for row in rows:
            for key in row:
                if key not in fieldnames:
                    fieldnames.append(key)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with Path(path).open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})


def repair_legacy_dual_yaw_provider_rows(rows: Iterable[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    repaired: list[dict[str, Any]] = []
    diffs: list[float] = []
    for row in rows:
        item = dict(row)
        old_yaw = as_float(item.get("yaw_deg"))
        if math.isfinite(old_yaw):
            new_yaw = repair_legacy_provider_yaw_deg(old_yaw)
            item["legacy_yaw_deg"] = f"{old_yaw:.6f}"
            item["yaw_deg"] = f"{new_yaw:.6f}"
            item["yaw_frame"] = "solver_visible_body_heading_ned_deg"
            item["yaw_provider_lineage"] = "BY2_A1_dual_diff_lateral_conversion"
            item["yaw_transform_from_legacy"] = "legacy_baseline_heading_minus_90_deg"
            item["trace_tuned_yaw_fix"] = "false"
            diffs.append(abs(circular_diff_deg(new_yaw, old_yaw)))
        repaired.append(item)
    summary = {
        "row_count": len(repaired),
        "updated_yaw_row_count": len(diffs),
        "legacy_to_repaired_abs_delta_deg_p50": percentile(diffs, 0.50),
        "legacy_to_repaired_abs_delta_deg_p95": percentile(diffs, 0.95),
        "trace_tuned_yaw_fix": False,
        "output_only_metric_correction": False,
        "provider_runtime_copy_rewritten": True,
    }
    return repaired, summary


def percentile(values: Iterable[float], q: float) -> float:
    vals = sorted(float(value) for value in values if math.isfinite(float(value)))
    if not vals:
        return math.nan
    index = min(len(vals) - 1, max(0, int(round((len(vals) - 1) * float(q)))))
    return vals[index]


def interpolate_angle_deg(
    rows: list[dict[str, float]],
    target_time: float,
    *,
    time_key: str = "time",
    yaw_key: str = "yaw_deg",
    tolerance_sec: float = 2.0,
) -> float | None:
    """Linearly interpolate wrapped yaw rows through an unwrapped sequence."""

    if not rows:
        return None
    times = [float(row[time_key]) for row in rows]
    if target_time < times[0] - tolerance_sec or target_time > times[-1] + tolerance_sec:
        return None
    import bisect

    index = bisect.bisect_left(times, target_time)
    if index == 0:
        return wrap360(float(rows[0][yaw_key])) if abs(times[0] - target_time) <= tolerance_sec else None
    if index >= len(times):
        return wrap360(float(rows[-1][yaw_key])) if abs(times[-1] - target_time) <= tolerance_sec else None
    left = rows[index - 1]
    right = rows[index]
    lt = float(left[time_key])
    rt = float(right[time_key])
    if rt <= lt:
        return wrap360(float(left[yaw_key]))
    if min(abs(target_time - lt), abs(target_time - rt)) > tolerance_sec:
        return None
    ly = float(left[yaw_key])
    dy = circular_diff_deg(float(right[yaw_key]), ly)
    frac = (target_time - lt) / (rt - lt)
    return wrap360(ly + dy * frac)


def repair_provider_rows_from_source_yaw(
    provider_rows: Iterable[dict[str, Any]],
    source_yaw_rows: list[dict[str, float]],
    *,
    provider_to_source_time_offset_sec: float,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Rewrite provider yaw rows by interpolating source-lineage yaw to provider times."""

    repaired: list[dict[str, Any]] = []
    updated = 0
    missing = 0
    deltas: list[float] = []
    for row in provider_rows:
        item = dict(row)
        provider_time = as_float(item.get("time"))
        old_yaw = as_float(item.get("yaw_deg"))
        target_time = provider_time + float(provider_to_source_time_offset_sec)
        new_yaw = interpolate_angle_deg(source_yaw_rows, target_time)
        if new_yaw is None or not math.isfinite(old_yaw):
            missing += 1
            repaired.append(item)
            continue
        item["legacy_yaw_deg"] = f"{old_yaw:.6f}"
        item["yaw_deg"] = f"{new_yaw:.6f}"
        item["yaw_frame"] = "solver_visible_body_heading_ned_deg"
        item["yaw_provider_lineage"] = "BY2_A1_dual_diff_status_interp_to_provider_axis"
        item["yaw_transform_from_legacy"] = "source_lineage_regenerated_not_metric_correction"
        item["provider_to_source_time_offset_sec"] = f"{provider_to_source_time_offset_sec:.6f}"
        item["trace_tuned_yaw_fix"] = "false"
        deltas.append(abs(circular_diff_deg(new_yaw, old_yaw)))
        updated += 1
        repaired.append(item)
    return repaired, {
        "row_count": len(repaired),
        "updated_yaw_row_count": updated,
        "missing_source_yaw_count": missing,
        "legacy_to_repaired_abs_delta_deg_p50": percentile(deltas, 0.50),
        "legacy_to_repaired_abs_delta_deg_p95": percentile(deltas, 0.95),
        "provider_to_source_time_offset_sec": float(provider_to_source_time_offset_sec),
        "trace_tuned_yaw_fix": False,
        "output_only_metric_correction": False,
        "provider_runtime_copy_rewritten": True,
    }


def audit_status_relpos_against_provider(
    *,
    gnss1_status: str | Path,
    gnss2_status: str | Path,
    provider_yaw_csv: str | Path,
    max_rows: int = 20,
) -> list[dict[str, Any]]:
    """Build a compact lineage table for the first provider epochs."""

    g1 = read_csv_rows(gnss1_status)
    g2 = read_csv_rows(gnss2_status)
    provider = read_csv_rows(provider_yaw_csv)
    rows: list[dict[str, Any]] = []
    count = min(max_rows, len(g1), len(g2), len(provider))
    for index in range(count):
        row1 = g1[index]
        row2 = g2[index]
        lineage = by2_a1_dual_diff_yaw_from_status_relpos(
            gnss1_rel_n_m=as_float(row1.get("rel_pos_n")),
            gnss1_rel_e_m=as_float(row1.get("rel_pos_e")),
            gnss1_rel_d_m=as_float(row1.get("rel_pos_d")),
            gnss2_rel_n_m=as_float(row2.get("rel_pos_n")),
            gnss2_rel_e_m=as_float(row2.get("rel_pos_e")),
            gnss2_rel_d_m=as_float(row2.get("rel_pos_d")),
        )
        legacy = m1r2b_legacy_provider_yaw_from_status_relpos(
            gnss1_rel_n_m=as_float(row1.get("rel_pos_n")),
            gnss1_rel_e_m=as_float(row1.get("rel_pos_e")),
            gnss2_rel_n_m=as_float(row2.get("rel_pos_n")),
            gnss2_rel_e_m=as_float(row2.get("rel_pos_e")),
        )
        provider_yaw = as_float(provider[index].get("yaw_deg"))
        rows.append(
            {
                "sample_index": index,
                "provider_time": provider[index].get("time", ""),
                "gnss_order_used": lineage.gnss_order_used,
                "legacy_m1r2b_provider_yaw_deg": f"{provider_yaw:.6f}",
                "legacy_formula_recomputed_yaw_deg": f"{legacy:.6f}",
                "source_lineage_body_yaw_deg": f"{lineage.yaw_ned_deg:.6f}",
                "legacy_minus_source_body_yaw_deg": f"{circular_diff_deg(provider_yaw, lineage.yaw_ned_deg):.6f}",
                "baseline_length_m": f"{lineage.baseline_length_m:.6f}",
                "baseline_heading_deg": f"{lineage.baseline_heading_deg:.6f}",
                "yaw_baseline_deg": f"{lineage.yaw_baseline_deg:.6f}",
                "lateral_offset_applied": lineage.lateral_offset_applied,
                "lateral_offset_sign": lineage.lateral_offset_sign,
                "selection_basis": lineage.selection_basis,
                "trace_solver_input": False,
                "trace_tuned_yaw_fix": False,
                "semantic_status": (
                    "legacy_provider_missing_lateral_body_heading_conversion"
                    if abs(circular_diff_deg(provider_yaw, lineage.yaw_ned_deg)) > 45.0
                    else "provider_matches_source_lineage"
                ),
            }
        )
    return rows
