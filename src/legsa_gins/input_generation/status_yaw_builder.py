"""Build process_data-compatible status yaw from dual receiver status CSVs.

中文说明：本模块只复现上传 process_data 的 A1_dual_diff yaw 生成逻辑；
trace yaw 只能 diagnostic，不能在这里变成 formal solver input。
"""

from __future__ import annotations

import csv
import math
from pathlib import Path
from typing import Any


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


def _read_csv(path: str | Path, *, max_rows: int | None = None) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    with Path(path).open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for index, row in enumerate(reader):
            if max_rows is not None and index >= max_rows:
                break
            rows.append(row)
    return rows


def parse_bool_like(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "t", "yes", "y", "ok"}


def status_time_header(row: dict[str, Any]) -> float:
    secs = _as_float(row.get("header.stamp.secs"))
    nsecs = _as_float(row.get("header.stamp.nsecs"), 0.0)
    if secs is None:
        fallback = _as_float(row.get("time_unix"), _as_float(row.get("Time"), _as_float(row.get("time"))))
        if fallback is None:
            raise ValueError("status row is missing header.stamp time.")
        return fallback
    return float(secs) + float(nsecs or 0.0) * 1.0e-9


def status_time_sys(row: dict[str, Any]) -> float:
    secs = _as_float(row.get("sys_stamp.secs"))
    nsecs = _as_float(row.get("sys_stamp.nsecs"), 0.0)
    if secs is None:
        raise ValueError("status row is missing sys_stamp time.")
    return float(secs) + float(nsecs or 0.0) * 1.0e-9


def _has_field(rows: list[dict[str, Any]], field: str) -> bool:
    return any(field in row for row in rows)


def apply_status_valid_filter(
    rows: list[dict[str, Any]], label: str
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    has_rel_valid = _has_field(rows, "rel_valid")
    has_ant_valid = _has_field(rows, "ant_valid")
    has_ant_state = _has_field(rows, "ant_state")
    kept: list[dict[str, Any]] = []
    reject_rel_valid = 0
    reject_ant_valid = 0
    reject_ant_state = 0
    for row in rows:
        ok = True
        if has_rel_valid and not parse_bool_like(row.get("rel_valid")):
            reject_rel_valid += 1
            ok = False
        if has_ant_valid and not parse_bool_like(row.get("ant_valid")):
            reject_ant_valid += 1
            ok = False
        ant_state = _as_float(row.get("ant_state"))
        if has_ant_state and ant_state != 2.0:
            reject_ant_state += 1
            ok = False
        if ok:
            kept.append(row)
    return kept, {
        "label": label,
        "input_count": len(rows),
        "kept_count": len(kept),
        "rel_valid_filter_present": has_rel_valid,
        "ant_valid_filter_present": has_ant_valid,
        "ant_state_filter_present": has_ant_state,
        "rejected_rel_valid_count": reject_rel_valid,
        "rejected_ant_valid_count": reject_ant_valid,
        "rejected_ant_state_count": reject_ant_state,
    }


def _field(row: dict[str, Any], names: list[str]) -> float | None:
    for name in names:
        value = _as_float(row.get(name))
        if value is not None:
            return value
    return None


def _rel_fields(row: dict[str, Any]) -> dict[str, float] | None:
    values = {
        "n": _field(row, ["rel_pos_n", "rel_pos_n_m"]),
        "e": _field(row, ["rel_pos_e", "rel_pos_e_m"]),
        "d": _field(row, ["rel_pos_d", "rel_pos_d_m"]),
        "acc_n": _field(row, ["rel_acc_n", "rel_acc_n_m"]),
        "acc_e": _field(row, ["rel_acc_e", "rel_acc_e_m"]),
        "acc_d": _field(row, ["rel_acc_d", "rel_acc_d_m"]),
    }
    if any(value is None for value in values.values()):
        return None
    return {key: float(value) for key, value in values.items() if value is not None}


def _prepared_rows(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    prepared: list[dict[str, Any]] = []
    dropped = 0
    for row in rows:
        rel = _rel_fields(row)
        if rel is None:
            dropped += 1
            continue
        try:
            t = status_time_header(row)
        except ValueError:
            dropped += 1
            continue
        prepared.append({"t": t, "row": row, **rel})
    prepared.sort(key=lambda item: float(item["t"]))
    return prepared, dropped


def wrap_deg(angle: float) -> float:
    return angle % 360.0


def _interp(sorted_rows: list[dict[str, Any]], t: float, fields: list[str]) -> dict[str, float] | None:
    if not sorted_rows:
        return None
    if t < float(sorted_rows[0]["t"]) or t > float(sorted_rows[-1]["t"]):
        return None
    lo = 0
    hi = len(sorted_rows) - 1
    while lo <= hi:
        mid = (lo + hi) // 2
        mt = float(sorted_rows[mid]["t"])
        if mt < t:
            lo = mid + 1
        elif mt > t:
            hi = mid - 1
        else:
            return {field: float(sorted_rows[mid][field]) for field in fields}
    left_index = max(0, hi)
    right_index = min(len(sorted_rows) - 1, lo)
    left = sorted_rows[left_index]
    right = sorted_rows[right_index]
    lt = float(left["t"])
    rt = float(right["t"])
    if rt == lt:
        return {field: float(left[field]) for field in fields}
    alpha = (t - lt) / (rt - lt)
    return {
        field: float(left[field]) + alpha * (float(right[field]) - float(left[field]))
        for field in fields
    }


def build_a1_dual_diff_yaw_rows(
    gnss1_status_path: str | Path,
    gnss2_status_path: str | Path,
    *,
    base_time: float,
    max_rows: int | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    raw1 = _read_csv(gnss1_status_path, max_rows=max_rows)
    raw2 = _read_csv(gnss2_status_path, max_rows=max_rows)
    valid1, stats1 = apply_status_valid_filter(raw1, "gnss1")
    valid2, stats2 = apply_status_valid_filter(raw2, "gnss2")
    rows1, dropped1 = _prepared_rows(valid1)
    rows2, dropped2 = _prepared_rows(valid2)
    fields = ["n", "e", "d", "acc_n", "acc_e", "acc_d"]
    yaw_rows: list[dict[str, Any]] = []
    outside_interp = 0
    for item1 in rows1:
        t1 = float(item1["t"])
        item2 = _interp(rows2, t1, fields)
        if item2 is None:
            outside_interp += 1
            continue
        rel_n = float(item2["n"]) - float(item1["n"])
        rel_e = float(item2["e"]) - float(item1["e"])
        rel_d = float(item2["d"]) - float(item1["d"])
        rel_acc_n = math.hypot(float(item1["acc_n"]), float(item2["acc_n"]))
        rel_acc_e = math.hypot(float(item1["acc_e"]), float(item2["acc_e"]))
        rel_acc_d = math.hypot(float(item1["acc_d"]), float(item2["acc_d"]))
        baseline_len = math.sqrt(rel_n * rel_n + rel_e * rel_e + rel_d * rel_d)
        yaw_rows.append(
            {
                "timestamp": t1,
                "aligned_time": t1 - base_time,
                "rel_n": rel_n,
                "rel_e": rel_e,
                "rel_d": rel_d,
                "rel_acc_n": rel_acc_n,
                "rel_acc_e": rel_acc_e,
                "rel_acc_d": rel_acc_d,
                "rel_acc_h": math.hypot(rel_acc_n, rel_acc_e),
                "baseline_len_m": baseline_len,
                "yaw_baseline_deg": wrap_deg(-math.degrees(math.atan2(rel_e, rel_n))),
                "yaw_formula": "-atan2(rel_e,rel_n)",
                "yaw_source": "A1_dual_diff_status",
            }
        )
    audit = {
        "phase": "N4H1P",
        "yaw_source": "A1_dual_diff_status",
        "yaw_formula": "-atan2(rel_e,rel_n)",
        "yaw_ned_formula": "90_minus_yaw_body",
        "gnss1_filter": stats1,
        "gnss2_filter": stats2,
        "gnss1_missing_rel_or_time_count": dropped1,
        "gnss2_missing_rel_or_time_count": dropped2,
        "interpolation_outside_range_count": outside_interp,
        "yaw_row_count": len(yaw_rows),
        "trace_solver_input": False,
        "trace_yaw_for_solver": False,
        "formal_input_source": "status",
    }
    return yaw_rows, audit


def build_single_status_yaw_rows(
    status_path: str | Path,
    label: str,
    *,
    base_time: float,
    max_rows: int | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    raw = _read_csv(status_path, max_rows=max_rows)
    valid, stats = apply_status_valid_filter(raw, label)
    prepared, dropped = _prepared_rows(valid)
    rows: list[dict[str, Any]] = []
    for item in prepared:
        yaw = wrap_deg(-math.degrees(math.atan2(float(item["e"]), float(item["n"]))))
        rows.append(
            {
                "timestamp": float(item["t"]),
                "aligned_time": float(item["t"]) - base_time,
                "rel_n": float(item["n"]),
                "rel_e": float(item["e"]),
                "rel_d": float(item["d"]),
                "baseline_len_m": math.sqrt(
                    float(item["n"]) ** 2 + float(item["e"]) ** 2 + float(item["d"]) ** 2
                ),
                "rel_acc_h": math.hypot(float(item["acc_n"]), float(item["acc_e"])),
                "yaw_baseline_deg": yaw,
                "yaw_formula": "-atan2(rel_pos_e,rel_pos_n)",
                "yaw_source": f"{label}_single_status_diagnostic",
                "diagnostic_only": True,
            }
        )
    return rows, {
        "label": label,
        "filter": stats,
        "missing_rel_or_time_count": dropped,
        "yaw_row_count": len(rows),
        "diagnostic_only": True,
    }


def compute_yaw_std(rows: list[dict[str, Any]], mode: str) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        baseline = max(float(item.get("baseline_len_m") or 0.0), 1.0e-6)
        rel_acc_h = float(item.get("rel_acc_h") or 0.0)
        geometry_deg = math.degrees(math.atan2(rel_acc_h, baseline))
        if mode == "fixed_1p5":
            yaw_std = 1.5
            evidence_status = "fixed_1p5_observed_in_uploaded_code_family"
        elif mode == "fixed_2p0":
            yaw_std = 2.0
            evidence_status = "fixed_2p0_observed_in_uploaded_code_family"
        elif mode == "mild_additive":
            yaw_std = 1.5 + min(2.0, geometry_deg)
            evidence_status = "simplified_but_formula_documented"
        elif mode == "suspicious_only":
            suspicious = baseline < 0.1 or geometry_deg > 20.0
            yaw_std = 10.0 if suspicious else 1.5
            evidence_status = "simplified_but_formula_documented"
        else:
            raise ValueError(f"Unsupported yaw std mode: {mode}")
        item["yaw_std"] = yaw_std
        item["yaw_std_mode"] = mode
        item["yaw_std_evidence_status"] = evidence_status
        output.append(item)
    return output


def apply_yaw_install_and_ned(
    rows: list[dict[str, Any]], *, sign: float, offset_deg: float
) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        yaw_body = wrap_deg(float(sign) * float(item["yaw_baseline_deg"]) + float(offset_deg))
        item["yaw_body_deg"] = yaw_body
        item["yaw_ned_deg"] = wrap_deg(90.0 - yaw_body)
        item["yaw_ned_formula"] = "90_minus_yaw_body"
        item["yaw_sign"] = float(sign)
        item["yaw_install_offset_deg"] = float(offset_deg)
        output.append(item)
    return output
