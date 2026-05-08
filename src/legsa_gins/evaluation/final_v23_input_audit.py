"""Audit final_v23 15-column GNSS input source chain.

中文说明：本模块只审计 final_v23 runtime 15-column `.gnss` 输入及其上游字段来源。
它不使用 trace 作为 solver input，不做 output correction，也不把 final_v23 当作 proposed。
"""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path
from statistics import median
from typing import Any


FINAL_V23_GNSS_COLUMNS = [
    "time",
    "lat",
    "lon",
    "height",
    "std_n",
    "std_e",
    "std_d",
    "vn",
    "ve",
    "vd",
    "std_vn",
    "std_ve",
    "std_vd",
    "yaw",
    "yaw_std",
]


def _as_float(value: Any, default: float | None = None) -> float | None:
    if value is None:
        return default
    text = str(value).strip()
    if text == "":
        return default
    try:
        parsed = float(text)
    except ValueError:
        return default
    if math.isnan(parsed):
        return default
    return parsed


def _read_csv(path: str | Path) -> list[dict[str, str]]:
    with Path(path).open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _row_value(row: dict[str, Any], names: list[str]) -> float | None:
    for name in names:
        value = _as_float(row.get(name))
        if value is not None:
            return value
    return None


def parse_final_v23_gnss_file(path: str | Path) -> list[dict[str, float]]:
    """Parse the final_v23 15-column `.gnss` file.

    The format has no header and may be whitespace- or comma-separated.
    """

    rows: list[dict[str, float]] = []
    previous_time: float | None = None
    for line_number, line in enumerate(Path(path).read_text(encoding="utf-8-sig").splitlines(), start=1):
        text = line.strip()
        if not text or text.startswith("#"):
            continue
        parts = [part for part in text.replace(",", " ").split() if part]
        if len(parts) != len(FINAL_V23_GNSS_COLUMNS):
            raise ValueError(
                f"final_v23 .gnss row {line_number} has {len(parts)} columns; expected 15"
            )
        values = [float(part) for part in parts]
        row = dict(zip(FINAL_V23_GNSS_COLUMNS, values))
        current_time = row["time"]
        if previous_time is not None and current_time < previous_time:
            raise ValueError("final_v23 .gnss time must be monotonic non-decreasing")
        previous_time = current_time
        rows.append(row)
    return rows


def _status_time_candidates(status_rows: list[dict[str, Any]]) -> list[tuple[str, list[float]]]:
    candidates: list[tuple[str, list[float]]] = []
    header_values: list[float] = []
    sys_values: list[float] = []
    for row in status_rows:
        header_secs = _row_value(row, ["header.stamp.secs"])
        header_nsecs = _row_value(row, ["header.stamp.nsecs"]) or 0.0
        sys_secs = _row_value(row, ["sys_stamp.secs"])
        sys_nsecs = _row_value(row, ["sys_stamp.nsecs"]) or 0.0
        if header_secs is not None:
            header_values.append(float(header_secs) + float(header_nsecs) * 1.0e-9)
        if sys_secs is not None:
            sys_values.append(float(sys_secs) + float(sys_nsecs) * 1.0e-9)
    if len(header_values) == len(status_rows) and header_values:
        candidates.append(("header.stamp", header_values))
    if len(sys_values) == len(status_rows) and sys_values:
        candidates.append(("sys_stamp", sys_values))
    for field in ["time", "algo_time_sec", "aligned_time", "tow", "time_unix", "timestamp"]:
        values = [_row_value(row, [field]) for row in status_rows]
        values = [value for value in values if value is not None]
        if len(values) == len(status_rows) and values:
            candidates.append((field, values))
    return candidates


def _align_rows_by_time(
    final_rows: list[dict[str, Any]],
    source_rows: list[dict[str, Any]],
    *,
    max_dt: float = 0.2,
) -> tuple[list[tuple[dict[str, Any], dict[str, Any], float]], dict[str, Any]]:
    if not final_rows or not source_rows:
        return [], {"time_field": None, "time_transform": None, "evidence_status": "evidence_missing"}
    final_times = [float(row["time"]) for row in final_rows]
    best: tuple[int, float, str, str, float, list[tuple[dict[str, Any], dict[str, Any], float]]] | None = None
    for field, raw_source_times in _status_time_candidates(source_rows):
        source_variants: list[tuple[str, float, list[float]]] = [("direct", 0.0, raw_source_times)]
        if len(raw_source_times) >= 3 and len(final_times) >= 3:
            offset = median(raw_source_times[: min(50, len(raw_source_times))]) - median(
                final_times[: min(50, len(final_times))]
            )
            offset_candidates = {offset, round(offset)}
            if abs(offset) > 1000.0:
                rounded = round(offset)
                offset_candidates.update({rounded - 1.0, rounded + 1.0})
            for candidate_offset in sorted(offset_candidates):
                source_variants.append(
                    (
                        "constant_file_time_offset",
                        candidate_offset,
                        [value - candidate_offset for value in raw_source_times],
                    )
                )
        for transform, offset, source_times in source_variants:
            pairs: list[tuple[dict[str, Any], dict[str, Any], float]] = []
            source_index = 0
            total_abs_dt = 0.0
            for final_row in final_rows:
                t = float(final_row["time"])
                while (
                    source_index + 1 < len(source_times)
                    and abs(source_times[source_index + 1] - t) <= abs(source_times[source_index] - t)
                ):
                    source_index += 1
                dt = t - source_times[source_index]
                if abs(dt) <= max_dt:
                    pairs.append((final_row, source_rows[source_index], dt))
                    total_abs_dt += abs(dt)
            score = total_abs_dt / max(len(pairs), 1)
            candidate = (len(pairs), score, field, transform, offset, pairs)
            if best is None or candidate[0] > best[0] or (candidate[0] == best[0] and candidate[1] < best[1]):
                best = candidate
    if best is None or not best[5]:
        return [], {"time_field": None, "time_transform": None, "evidence_status": "evidence_missing"}
    _, score, field, transform, offset, pairs = best
    return pairs, {
        "time_field": field,
        "time_transform": transform,
        "event_pair_delta_raw_units_not_clock_offset": offset if transform == "constant_file_time_offset" else 0.0,
        "aligned_count": len(pairs),
        "mean_abs_dt": score,
        "evidence_status": "aligned_for_source_audit",
    }


def _stats(values: list[float]) -> dict[str, Any]:
    if not values:
        return {"count": 0, "max_abs": None, "mean_abs": None}
    return {
        "count": len(values),
        "max_abs": max(abs(value) for value in values),
        "mean_abs": sum(abs(value) for value in values) / len(values),
    }


def audit_position_source(
    final_gnss_rows: list[dict[str, Any]],
    gnss1_status_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    pairs, alignment = _align_rows_by_time(final_gnss_rows, gnss1_status_rows)
    diffs = {"lat": [], "lon": [], "height": []}
    for final_row, status_row, _dt in pairs:
        lat = _row_value(status_row, ["pos_lat", "lat_deg"])
        lon = _row_value(status_row, ["pos_lon", "lon_deg"])
        height = _row_value(status_row, ["pos_height", "height_m"])
        if None in {lat, lon, height}:
            continue
        diffs["lat"].append(float(final_row["lat"]) - float(lat))
        diffs["lon"].append(float(final_row["lon"]) - float(lon))
        diffs["height"].append(float(final_row["height"]) - float(height))
    matched = bool(
        diffs["lat"]
        and _stats(diffs["lat"])["max_abs"] <= 1.0e-6
        and _stats(diffs["lon"])["max_abs"] <= 1.0e-6
        and _stats(diffs["height"])["max_abs"] <= 1.0e-3
    )
    return {
        "position_source_status": "matched_gnss1_status" if matched else "evidence_missing",
        "alignment": alignment,
        "lat_diff_deg": _stats(diffs["lat"]),
        "lon_diff_deg": _stats(diffs["lon"]),
        "height_diff_m": _stats(diffs["height"]),
        "trace_solver_input": False,
        "output_only_correction": False,
    }


def audit_position_std_source(
    final_gnss_rows: list[dict[str, Any]],
    gnss1_status_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    pairs, alignment = _align_rows_by_time(final_gnss_rows, gnss1_status_rows)
    diffs = {"std_n": [], "std_e": [], "std_d": []}
    for final_row, status_row, _dt in pairs:
        acc_h = _row_value(status_row, ["pos_acc_h", "pos_acc_h_m"])
        acc_v = _row_value(status_row, ["pos_acc_v", "pos_acc_v_m"])
        if acc_h is None or acc_v is None:
            continue
        diffs["std_n"].append(float(final_row["std_n"]) - float(acc_h))
        diffs["std_e"].append(float(final_row["std_e"]) - float(acc_h))
        diffs["std_d"].append(float(final_row["std_d"]) - float(acc_v))
    matched = bool(
        diffs["std_n"]
        and _stats(diffs["std_n"])["max_abs"] <= 1.0e-3
        and _stats(diffs["std_e"])["max_abs"] <= 1.0e-3
        and _stats(diffs["std_d"])["max_abs"] <= 1.0e-3
    )
    return {
        "position_std_source_status": "matched_pos_acc_h_pos_acc_v" if matched else "evidence_missing",
        "alignment": alignment,
        "std_n_diff_m": _stats(diffs["std_n"]),
        "std_e_diff_m": _stats(diffs["std_e"]),
        "std_d_diff_m": _stats(diffs["std_d"]),
        "trace_solver_input": False,
        "output_only_correction": False,
    }


def audit_velocity_source(
    final_gnss_rows: list[dict[str, Any]],
    gnss1_raw_summary_or_pvt_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    """Audit velocity source when decoded UBX-NAV-PVT evidence is available."""

    has_pvt_rows = bool(gnss1_raw_summary_or_pvt_rows)
    has_velocity_fields = any(
        all(_row_value(row, [field]) is not None for field in ["vn", "ve", "vd"])
        and _row_value(row, ["sAcc", "s_acc", "std_vn"]) is not None
        for row in gnss1_raw_summary_or_pvt_rows
    )
    status = "found_decoded_pvt_velocity_rows" if has_pvt_rows and has_velocity_fields else "evidence_missing"
    return {
        "velocity_source_status": status,
        "pvt_rows_available": has_pvt_rows,
        "velocity_fields_available": has_velocity_fields,
        "trace_solver_input": False,
        "output_only_correction": False,
    }


def load_status_rows(path: str | Path) -> list[dict[str, str]]:
    return _read_csv(path)


def make_final_v23_input_source_report(
    *,
    final_gnss_file_status: str,
    position_report: dict[str, Any],
    position_std_report: dict[str, Any],
    velocity_report: dict[str, Any],
    yaw_report: dict[str, Any],
    process_data_source_map: dict[str, Any],
    reconstructed_process_data_compat_report: dict[str, Any] | None = None,
) -> dict[str, Any]:
    position_status = position_report.get("position_source_status", "evidence_missing")
    std_status = position_std_report.get("position_std_source_status", "evidence_missing")
    velocity_status = velocity_report.get("velocity_source_status", "evidence_missing")
    yaw_status = yaw_report.get("yaw_column_source_status", "evidence_missing")
    statuses = [position_status, std_status, velocity_status, yaw_status]
    reconstructed_available = bool(
        reconstructed_process_data_compat_report
        and reconstructed_process_data_compat_report.get("runtime_input_reconstructed") is True
    )
    reconstructed_status = (
        "generated_process_data_compat_15_column_gnss"
        if reconstructed_available
        else "not_requested_or_evidence_missing"
    )
    return {
        "phase": "N4H1",
        "runtime_input_layer": "final_v23_reads_15_column_gnss_file",
        "upstream_generation_layer": "process_data_py_generates_gnss_from_status_raw_and_status_yaw",
        "final_v23_gnss_file_status": final_gnss_file_status,
        "historical_final_v23_gnss_file_status": final_gnss_file_status,
        "reconstructed_process_data_compat_gnss_status": reconstructed_status,
        "reconstructed_process_data_compat_available": reconstructed_available,
        "reconstructed_runtime_input_is_historical_exact_final_v23_file": False,
        "runtime_input_reconstruction_layer": "process_data_compat_generated_from_upstream_fields"
        if reconstructed_available
        else "evidence_missing",
        "final_v23_gnss_columns": FINAL_V23_GNSS_COLUMNS,
        "position_source_status": position_status,
        "position_std_source_status": std_status,
        "velocity_source_status": velocity_status,
        "yaw_source_status": yaw_status,
        "position_report": position_report,
        "position_std_report": position_std_report,
        "velocity_report": velocity_report,
        "yaw_report_summary": {
            "best_matching_candidate_to_final_gnss_yaw": yaw_report.get(
                "best_matching_candidate_to_final_gnss_yaw"
            ),
            "yaw_column_source_status": yaw_status,
        },
        "process_data_source_map_summary": {
            "process_data_path": process_data_source_map.get("process_data_path"),
            "found_position_mapping": process_data_source_map.get("found_position_mapping"),
            "found_velocity_mapping": process_data_source_map.get("found_velocity_mapping"),
            "found_yaw_mapping": process_data_source_map.get("found_yaw_mapping"),
            "found_final_status_output": process_data_source_map.get("found_final_status_output"),
        },
        "process_data_compat_summary": {
            "gnss_row_count": (reconstructed_process_data_compat_report or {}).get("gnss_row_count"),
            "imu_row_count": (reconstructed_process_data_compat_report or {}).get("imu_row_count"),
            "coverage_status": (reconstructed_process_data_compat_report or {}).get("coverage_status"),
            "coverage_warning": (reconstructed_process_data_compat_report or {}).get("coverage_warning"),
            "position_source": (reconstructed_process_data_compat_report or {}).get("position_source"),
            "velocity_source": (reconstructed_process_data_compat_report or {}).get("velocity_source"),
            "velocity_std_policy": (reconstructed_process_data_compat_report or {}).get(
                "velocity_std_policy"
            ),
            "yaw_source": (reconstructed_process_data_compat_report or {}).get("yaw_source"),
            "trace_solver_input": (reconstructed_process_data_compat_report or {}).get(
                "trace_solver_input", False
            ),
        },
        "reconstructed_process_data_compat_coverage_status": (
            reconstructed_process_data_compat_report or {}
        ).get("coverage_status"),
        "coverage_suspicious": bool(
            reconstructed_process_data_compat_report
            and reconstructed_process_data_compat_report.get("coverage_status") != "passed"
        ),
        "process_data_compat_row_parity_claim": bool(
            reconstructed_process_data_compat_report
            and reconstructed_process_data_compat_report.get("coverage_status") == "passed"
        ),
        "trace_solver_input": False,
        "trace_evaluation_only": True,
        "final_v23_is_proposed": False,
        "proposed_solver_output": False,
        "output_only_correction": False,
        "numerical_performance_claim": False,
        "evidence_status": "source_chain_audited"
        if all(status != "evidence_missing" for status in statuses[:3])
        else "partial_evidence_missing",
    }


def write_json(path: str | Path, data: dict[str, Any]) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
