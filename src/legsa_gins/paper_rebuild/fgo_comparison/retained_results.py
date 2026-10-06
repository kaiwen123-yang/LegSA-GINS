"""Read retained comparisons without solving, evaluating or reconstructing NAV.

Only the four named, existing small CSV tables are opened. Continuous-error
and genuine retained-trajectory descriptors are returned for the caller to
plot; this reader only checks their presence. Original strings, source rows,
support definitions and unavailable denominators survive alongside convenient
numeric aliases. In particular, match/output coverage is not nominal-epoch
coverage, heading-only rows have no position, and BY2H's two LC01 starts are
both retained with their existing geometric-audit failure boundary.
"""
from __future__ import annotations

import csv
import math
from pathlib import Path


_EXT = "<CODE_ROOT>/docs/paper_rebuild/hext/EXT_REPRODUCTION"
_V3 = "<CODE_ROOT>/docs/paper_rebuild/audit_xbpg_20261001/v3_results"
_ERROR_COLUMNS = (
    "err_n_m", "err_e_m", "err_u_m", "horizontal_err_m",
    "position_3d_err_m", "roll_err_deg", "pitch_err_deg", "yaw_err_deg",
)
_NAV_METRICS = {
    "horizontal_rmse_m": "horizontal_rmse_m",
    "horizontal_p95_m": "horizontal_p95_m",
    "vertical_rmse_m": "up_rmse_m",
    "vertical_p95_m": "up_p95_absolute_m",
    "position_3d_rmse_m": "position_3d_rmse_m",
    "yaw_rmse_deg": "yaw_rmse_deg",
    "yaw_p95_deg": "yaw_p95_absolute_deg",
    "roll_rmse_deg": "roll_rmse_deg",
    "pitch_rmse_deg": "pitch_rmse_deg",
}


def _resolve(value, roots):
    value = str(value)
    for alias, root in sorted(roots.items(), key=lambda item: -len(item[0])):
        value = value.replace(alias, str(root))
    if "<" in value:
        raise ValueError(f"Unresolved retained-result alias: {value}")
    return Path(value)


def _rows(source, roots):
    with _resolve(source, roots).open(newline="", encoding="utf-8-sig") as stream:
        return list(csv.DictReader(stream))


def _number(value):
    if value is None or str(value).strip().lower() in ("", "unknown", "none", "nan"):
        return None
    result = float(value)
    return result if math.isfinite(result) else None


def _count(value):
    value = _number(value)
    if value is not None and value != int(value):
        raise ValueError("Retained epoch count is not an integer")
    return None if value is None else int(value)


def _series(source, roots, columns=None, time_column="time", filters=None,
            physical_point="POI_MIDPOINT"):
    if not source or source == "unknown":
        return None
    path = _resolve(source, roots)
    return {
        "source_path": source, "path": str(path), "exists": path.is_file(),
        "format": "csv.gz" if source.endswith(".gz") else "csv",
        "encoding": "utf-8-sig", "time_column": time_column,
        "time_basis": "sequence_relative_seconds",
        "columns": columns if columns is not None else {k: k for k in _ERROR_COLUMNS},
        "filters": filters or {}, "valid_column": None,
        "validity": "retain existing nonfinite errors; do not fill or interpolate",
        "physical_point": physical_point,
    }


def _nav_row(sequence, method, source, source_row_key, read_copy, original, meta):
    metrics = dict(_NAV_METRICS)
    if method == "LC01":
        metrics["horizontal_rmse_m"] = "h_rmse_m"
    result = {
        "sequence_id": sequence, "method_id": method,
        "source_method_id": original.get("method_id"),
        "support": "RETAINED_OWN_VALID",
        "start_policy": original.get("start_convention", "FORMAL_PROTOCOL_V3"),
        "status": original.get("evaluation_status", original.get("status")),
        "failure_classification": original.get("failure_classification"),
        "source_path": source, "source_row_key": source_row_key,
        "read_copy_path": read_copy, "source_row": dict(original),
        "metric_origin": "REUSED_ORIGINAL_METRIC", "old_result_reused": True,
        "native_point": "IMU", "evaluation_point": "POI_MIDPOINT",
        "physical_point": "POI_MIDPOINT", "attitude_is_estimated": True,
        "expected_epoch_count": None,
        "actual_epoch_count": _count(original.get("output_epoch_count")),
        "output_epoch_count": _count(original.get("output_epoch_count")),
        "finite_epoch_count": None,
        "matched_epoch_count": _count(original.get("matched_epoch_count")),
        "unmatched_epoch_count": _count(original.get("unmatched_epoch_count")),
        "reference_epoch_count": _count(original.get("reference_epoch_count")),
        "coverage_fraction": _number(original.get("coverage_ratio")),
        "coverage_denominator": "retained output_epoch_count; nominal expected count not recorded",
        "base_time": meta["base_time"], "window_start_s": meta["window_start_s"],
        "window_end_s": meta["window_end_s"],
        "first_output_s": _number(original.get("time_start")),
        "last_output_s": _number(original.get("time_end")),
        "comparison_boundary": "retained system/application comparison; different inputs and epoch support",
        "evaluator_contract": original.get("evaluator_contract"),
        "error_series": None, "trajectory": None,
        "recorded_hashes_reverified": False,
    }
    result.update({name: _number(original.get(column)) for name, column in metrics.items()})
    return result


def _v3_row(roots, sequence, cells, natural, meta):
    cells = [r for r in cells if r["sequence_id"] == sequence
             and r["record_kind"] == "FORMAL_V3_F04_SOURCE_CELL" and r["method_id"] == "F04"]
    rows = [r for r in natural if r["sequence_id"] == sequence and r["method_id"] == "F04"]
    if not cells or len(rows) != 1 or len({r["run_id"] for r in cells}) != 1:
        raise ValueError(f"Retained F04 identity absent or ambiguous: {sequence}")
    original = {r["column"]: r["value"] for r in cells}
    if len(original) != len(cells):
        raise ValueError("Duplicate retained F04 source cell")
    r = rows[0]
    if r["run_id"] != original["run_id"]:
        raise ValueError("Retained F04 metric/error run identities differ")
    out = _nav_row(sequence, "V3_F04", cells[0]["source_path"], cells[0]["row_key"],
                   cells[0]["read_copy_path"], original, meta)
    out["run_id"] = original["run_id"]
    out["roll_rmse_deg"] = _number(r.get("v3_roll_rmse_deg"))
    out["pitch_rmse_deg"] = _number(r.get("v3_pitch_rmse_deg"))
    out["native_runtime_seconds"] = _number(r.get("native_runtime_seconds"))
    out["runtime_boundary"] = "retained native total wall time; not online worst-case latency"
    fields = ("run_id", "v3_roll_rmse_deg", "v3_pitch_rmse_deg", "native_runtime_seconds",
              "v3_error_series_path", "v3_matched_trajectory_path", "v3_matched_trajectory_status",
              "v3_matched_trajectory_recorded_source_sha256", "v3_matched_trajectory_manifest_path")
    out["supplement_source_path"] = _V3 + "/run_statistics/NATURAL_C00_ALL_CONFIGS.csv"
    out["supplement_source_row_key"] = f"sequence_id={sequence};method_id=F04;run_id={r['run_id']}"
    out["supplement_source_row"] = {key: r.get(key) for key in fields}
    out["error_series"] = _series(r["v3_error_series_path"], roots)
    trajectory = _series(r.get("v3_matched_trajectory_path"), roots, {
        "latitude_deg": "estimate_latitude_deg", "longitude_deg": "estimate_longitude_deg",
        "height_m": "estimate_height_m", "yaw_deg": "estimate_yaw_deg",
    })
    if trajectory is not None:
        trajectory.update({
            "source_status": r.get("v3_matched_trajectory_status"),
            "recorded_sha256": r.get("v3_matched_trajectory_recorded_source_sha256"),
            "manifest_source_path": r.get("v3_matched_trajectory_manifest_path"),
            "provenance": "existing v3 index mapping plus frozen v3 physical-point contract; never reconstructed from error series",
        })
    out["trajectory"] = trajectory
    out["native_trajectory_boundary"] = "native NAV released; only explicitly registered matched trajectory may be drawn"
    return out


def _lc_rows(roots, sequence, rows, meta):
    output = []
    copy = _V3 + "/source_tables/MAIN_TABLE_V3.csv"
    for r in rows:
        if r["sequence_id"] != sequence or r["method_id"] != "LC01" or r["config"] != "LIT":
            continue
        out = _nav_row(sequence, "LC01", r["_source_path"], r["_source_row_key"], copy, r, meta)
        for key in ("geometric_audit_status", "main_row", "manuscript_row", "notes"):
            out[key] = r.get(key)
        out["gap_events_in_window"] = _count(r.get("gap_events_in_window"))
        out["comparison_boundary"] += "; existing start-policy, geometric-audit and after-results amendment boundaries remain in source_row/notes"
        source = r["error_series_source"].rstrip("/") + "/error_series.csv"
        if not _resolve(source, roots).is_file() and _resolve(source + ".gz", roots).is_file():
            source += ".gz"
        out["error_series"] = _series(source, roots)
        output.append(out)
    expected = 2 if sequence == "BY2H" else 1
    if len(output) != expected:
        raise ValueError(f"Retained LC01 start alternatives absent or ambiguous: {sequence}")
    return output


def _heading_rows(roots, sequence, rows):
    output = []
    for row in rows:
        if row["sequence_id"] != sequence:
            continue
        method, support = row["method_id"], row["support"]
        name = "REUSED_ERROR_SERIES.csv" if method.startswith("RTKLIB_") else "ERROR_SERIES.csv"
        column = {"native_valid": "error_valid_deg", "ratio_fixed": "error_ratio_fixed_deg",
                  "causal_held": "error_hold_deg"}[support]
        out = {
            **row, "source_row": dict(row), "old_result_reused": True,
            "read_copy_path": _EXT + "/COMPARISON_TABLE.csv",
            "metric_origin": "REUSED_ORIGINAL_METRIC",
            "native_point": "DUAL_ANTENNA_BASELINE_BODY_HEADING",
            "evaluation_point": "BODY_YAW_ONLY", "physical_point": "BODY_YAW_ONLY",
            "attitude_is_estimated": "heading_only",
            "horizontal_rmse_m": None, "vertical_rmse_m": None, "position_3d_rmse_m": None,
            "yaw_rmse_deg": _number(row["rmse_deg"]),
            "yaw_p95_deg": _number(row["p95_absolute_deg"]),
            "yaw_max_deg": _number(row["max_absolute_deg"]),
            "expected_epoch_count": None,
            "paired_epoch_denominator": _count(row["paired_epoch_denominator"]),
            "actual_epoch_count": None,
            "finite_epoch_count": _count(row["available_epoch_count"]),
            "matched_epoch_count": _count(row["scored_count"]),
            "coverage_fraction": _number(row["availability_fraction"]),
            "coverage_denominator": "retained paired_epoch_denominator; not nominal FGO seconds",
            "comparison_boundary": row["support_boundary"] + "; heading-only baseline solution, not full navigation",
            "error_series": _series(_EXT + f"/evaluation_results/{sequence}/{name}", roots,
                                     {"yaw_err_deg": column}, "t_rel_s", {"method_id": method},
                                     "BODY_YAW_ONLY"),
            "trajectory": None, "recorded_hashes_reverified": False,
        }
        output.append(out)
    if len(output) != 21 or len({(r["method_id"], r["support"]) for r in output}) != 21:
        raise ValueError(f"Retained heading variants/supports absent or ambiguous: {sequence}")
    return output


def read_retained(roots, sequence):
    """Return original F04, all LC01 starts and all seven heading variants.

    ``roots`` accepts either the aliases mapping or its local-config wrapper.
    Rows use numeric metric aliases compatible with the FGO evaluator, plus
    exact ``source_row`` strings. ``error_series`` and ``trajectory`` expose
    local and portable paths, CSV column mappings, time basis and filters.
    Neither payload is opened here. A missing payload remains ``exists=False``;
    it never removes the metric row or triggers recovery/re-evaluation.
    """
    if sequence not in ("BY2", "BY2H", "BY2O"):
        raise ValueError(f"Sequence outside registered FGO comparison: {sequence}")
    roots = roots.get("aliases", roots)
    heading = _rows(_EXT + "/COMPARISON_TABLE.csv", roots)
    selected = [r for r in heading if r["sequence_id"] == sequence]
    if not selected:
        raise ValueError(f"Missing retained sequence metadata: {sequence}")
    meta = {key: _number(selected[0][key]) for key in ("base_time", "window_start_s", "window_end_s")}
    if any(any(_number(r[key]) != value for key, value in meta.items()) for r in selected):
        raise ValueError("Retained sequence time metadata disagree")
    control = _rows(_EXT + "/CONTROL_REFERENCE_ROWS.csv", roots)
    natural = _rows(_V3 + "/run_statistics/NATURAL_C00_ALL_CONFIGS.csv", roots)
    lc = _rows(_V3 + "/source_tables/MAIN_TABLE_V3.csv", roots)
    return ([_v3_row(roots, sequence, control, natural, meta)]
            + _lc_rows(roots, sequence, lc, meta) + _heading_rows(roots, sequence, heading))
