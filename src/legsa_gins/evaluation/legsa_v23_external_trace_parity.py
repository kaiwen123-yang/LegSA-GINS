"""External clean trace parity helpers for N4H4D4.

中文说明：本模块只把 external clean NAV 当作离线诊断参考，不把外部轨迹、
trace 或 final_v23 输出送入 LegSA-v23-core solver。
"""

from __future__ import annotations

import csv
import math
from pathlib import Path
from typing import Any, Iterable


NAV_KEYS = ["time", "lat_deg", "lon_deg", "height_m", "vn", "ve", "vd", "roll_deg", "pitch_deg", "yaw_deg"]


def _to_float(value: str | None) -> float | None:
    if value is None:
        return None
    try:
        return float(str(value).strip())
    except ValueError:
        return None


def _normalize_header(name: str) -> str:
    lowered = name.strip().lower()
    aliases = {
        "t": "time",
        "timestamp": "time",
        "lat": "lat_deg",
        "latitude": "lat_deg",
        "lon": "lon_deg",
        "longitude": "lon_deg",
        "height": "height_m",
        "h": "height_m",
        "v_n": "vn",
        "v_e": "ve",
        "v_d": "vd",
        "roll": "roll_deg",
        "pitch": "pitch_deg",
        "yaw": "yaw_deg",
        "heading": "yaw_deg",
    }
    return aliases.get(lowered, lowered)


def _row_from_values(values: list[float]) -> dict[str, float] | None:
    if len(values) >= 11 and abs(values[0]) < 1.0e-9:
        # 中文说明：KF-GINS Navresult 常见首列为 week/占位，第二列才是秒时间。
        return {key: values[index + 1] for index, key in enumerate(NAV_KEYS)}
    if len(values) < 10:
        return None
    return {key: values[index] for index, key in enumerate(NAV_KEYS)}


def parse_nav(path: str | Path) -> list[dict[str, float]]:
    """中文说明：解析 LegSA/EVAL_NAV/KF-GINS 风格 NAV；未知列缺失时返回可用行。"""

    nav_path = Path(path)
    rows: list[dict[str, float]] = []
    if not nav_path.exists():
        return rows
    text = nav_path.read_text(encoding="utf-8", errors="ignore").splitlines()
    first_data = next((line for line in text if line.strip() and not line.lstrip().startswith("#")), "")
    if "," in first_data:
        with nav_path.open("r", encoding="utf-8", errors="ignore", newline="") as handle:
            reader = csv.DictReader(handle)
            if not reader.fieldnames:
                return rows
            normalized = {_normalize_header(name): name for name in reader.fieldnames}
            for raw in reader:
                row: dict[str, float] = {}
                for key in NAV_KEYS:
                    value = _to_float(raw.get(normalized.get(key, "")))
                    if value is not None:
                        row[key] = value
                if "time" in row and "lat_deg" in row and "lon_deg" in row and "height_m" in row:
                    rows.append(row)
        return rows
    for line in text:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        parts = stripped.replace(",", " ").split()
        values = [_to_float(part) for part in parts]
        floats = [value for value in values if value is not None]
        row = _row_from_values(floats)
        if row is not None:
            rows.append(row)
    return rows


def locate_external_clean_nav(clean_root: str | Path, dual_root: str | Path | None = None) -> dict[str, Any]:
    """中文说明：按优先级定位 external clean NAV；找不到时保留 evidence_missing。"""

    roots: list[tuple[str, Path]] = [("external_clean_replay", Path(clean_root))]
    if dual_root:
        roots.append(("dual_final_v23_secondary_reference", Path(dual_root)))
    name_hints = ("eval_nav", "nav", "kf_gins_navresult", "legsa_v23_nav")
    for role, root in roots:
        if not root.exists():
            continue
        candidates = []
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            lowered = path.name.lower()
            if lowered.endswith((".csv", ".nav", ".txt")) and any(hint in lowered for hint in name_hints):
                candidates.append(path)
        for candidate in sorted(candidates):
            rows = parse_nav(candidate)
            if len(rows) >= 2:
                return {
                    "status": "found",
                    "path": str(candidate),
                    "role": role,
                    "row_count": len(rows),
                    "trace_solver_input": False,
                    "final_v23_output_substitution": False,
                }
    return {
        "status": "evidence_missing",
        "path": None,
        "role": "external_clean_nav_missing",
        "row_count": 0,
        "trace_solver_input": False,
        "final_v23_output_substitution": False,
    }


def align_by_time(
    legsa_rows: Iterable[dict[str, float]], external_rows: Iterable[dict[str, float]], tolerance: float = 0.005
) -> list[tuple[dict[str, float], dict[str, float]]]:
    """中文说明：按时间戳近邻对齐；只用于评价/诊断，不改变 LegSA 输出。"""

    external = sorted(external_rows, key=lambda row: row.get("time", 0.0))
    pairs: list[tuple[dict[str, float], dict[str, float]]] = []
    cursor = 0
    for legsa in sorted(legsa_rows, key=lambda row: row.get("time", 0.0)):
        time = legsa.get("time")
        if time is None:
            continue
        while cursor + 1 < len(external) and external[cursor + 1].get("time", 0.0) <= time:
            cursor += 1
        candidates = external[max(0, cursor - 1) : min(len(external), cursor + 2)]
        best = min(candidates, key=lambda row: abs(row.get("time", 0.0) - time), default=None)
        if best is not None and abs(best.get("time", 0.0) - time) <= tolerance:
            pairs.append((legsa, best))
    return pairs


def _wrap_deg(value: float) -> float:
    wrapped = (value + 180.0) % 360.0 - 180.0
    return wrapped


def _meters_per_degree_lat() -> float:
    return 111_319.49079327358


def _horizontal_diff_m(left: dict[str, float], right: dict[str, float]) -> float:
    lat_mean = math.radians(0.5 * (left.get("lat_deg", 0.0) + right.get("lat_deg", 0.0)))
    north = (left.get("lat_deg", 0.0) - right.get("lat_deg", 0.0)) * _meters_per_degree_lat()
    east = (left.get("lon_deg", 0.0) - right.get("lon_deg", 0.0)) * _meters_per_degree_lat() * math.cos(lat_mean)
    return math.hypot(north, east)


def _rms(values: list[float]) -> float | None:
    if not values:
        return None
    return math.sqrt(sum(value * value for value in values) / len(values))


def _picks_by_window(diff_series: list[dict[str, float]], seconds: float) -> dict[str, Any]:
    if not diff_series:
        return {"status": "missing"}
    first_time = diff_series[0]["time"]
    window = [row for row in diff_series if row["time"] - first_time <= seconds + 1.0e-9]
    return _summarize_diff(window)


def _summarize_diff(diff_series: list[dict[str, float]]) -> dict[str, Any]:
    return {
        "count": len(diff_series),
        "horizontal_rmse_m": _rms([row["horizontal_diff_m"] for row in diff_series]),
        "up_rmse_m": _rms([row["up_diff_m"] for row in diff_series]),
        "vel_rmse_mps": _rms([row["vel_diff_mps"] for row in diff_series]),
        "roll_rmse_deg": _rms([row["roll_diff_deg"] for row in diff_series]),
        "pitch_rmse_deg": _rms([row["pitch_diff_deg"] for row in diff_series]),
        "yaw_rmse_deg": _rms([row["yaw_diff_deg"] for row in diff_series]),
    }


def compare_legsa_to_external_nav(
    legsa_nav: str | Path | list[dict[str, float]],
    external_nav: str | Path | list[dict[str, float]],
    tolerance: float = 0.005,
) -> dict[str, Any]:
    """中文说明：输出 LegSA 与 external clean NAV 的逐时刻差异摘要。"""

    legsa_rows = parse_nav(legsa_nav) if not isinstance(legsa_nav, list) else legsa_nav
    external_rows = parse_nav(external_nav) if not isinstance(external_nav, list) else external_nav
    pairs = align_by_time(legsa_rows, external_rows, tolerance=tolerance)
    diff_series: list[dict[str, float]] = []
    for left, right in pairs:
        roll = _wrap_deg(left.get("roll_deg", 0.0) - right.get("roll_deg", 0.0))
        pitch = _wrap_deg(left.get("pitch_deg", 0.0) - right.get("pitch_deg", 0.0))
        yaw = _wrap_deg(left.get("yaw_deg", 0.0) - right.get("yaw_deg", 0.0))
        vel = math.sqrt(
            (left.get("vn", 0.0) - right.get("vn", 0.0)) ** 2
            + (left.get("ve", 0.0) - right.get("ve", 0.0)) ** 2
            + (left.get("vd", 0.0) - right.get("vd", 0.0)) ** 2
        )
        diff_series.append(
            {
                "time": left.get("time", 0.0),
                "horizontal_diff_m": _horizontal_diff_m(left, right),
                "up_diff_m": left.get("height_m", 0.0) - right.get("height_m", 0.0),
                "vel_diff_mps": vel,
                "roll_diff_deg": roll,
                "pitch_diff_deg": pitch,
                "yaw_diff_deg": yaw,
            }
        )
    full = _summarize_diff(diff_series)
    return {
        "aligned_count": len(pairs),
        "legsa_count": len(legsa_rows),
        "external_count": len(external_rows),
        "first_time": diff_series[0]["time"] if diff_series else None,
        "last_time": diff_series[-1]["time"] if diff_series else None,
        "first_row_diff": diff_series[0] if diff_series else {},
        "first_1s_diff": _picks_by_window(diff_series, 1.0),
        "first_5s_diff": _picks_by_window(diff_series, 5.0),
        "first_10s_diff": _picks_by_window(diff_series, 10.0),
        "first_30s_diff": _picks_by_window(diff_series, 30.0),
        "first_60s_diff": _picks_by_window(diff_series, 60.0),
        "full_diff": full,
        "diff_series": diff_series,
        "trace_solver_input": False,
        "shadow_external_nav_solver_input": False,
        "numerical_performance_claim": False,
    }


def locate_first_divergence(diff_series: list[dict[str, float]], first_update_time: float | None = None) -> dict[str, Any]:
    """中文说明：定位首次超过阈值的时刻，判断发散发生在首个 GNSS update 前后。"""

    thresholds = {
        "first_H_gt_1m_time": ("horizontal_diff_m", 1.0),
        "first_H_gt_10m_time": ("horizontal_diff_m", 10.0),
        "first_Up_gt_3m_time": ("up_diff_m", 3.0),
        "first_yaw_gt_5deg_time": ("yaw_diff_deg", 5.0),
        "first_roll_pitch_gt_5deg_time": ("roll_pitch", 5.0),
        "first_velocity_gt_2mps_time": ("vel_diff_mps", 2.0),
    }
    result: dict[str, Any] = {}
    for name, (key, threshold) in thresholds.items():
        value = None
        for row in diff_series:
            metric = max(abs(row["roll_diff_deg"]), abs(row["pitch_diff_deg"])) if key == "roll_pitch" else abs(row[key])
            if metric > threshold:
                value = row["time"]
                break
        result[name] = value
    first_any = min([value for value in result.values() if value is not None], default=None)
    update_time = first_update_time
    result.update(
        {
            "first_divergence_time": first_any,
            "first_update_time": update_time,
            "divergence_before_first_update": bool(first_any is not None and update_time is not None and first_any < update_time),
            "divergence_at_first_update": bool(
                first_any is not None and update_time is not None and abs(first_any - update_time) <= 0.05
            ),
            "divergence_after_many_updates": bool(
                first_any is not None and update_time is not None and first_any > update_time + 5.0
            ),
            "divergence_after_state_feedback": bool(
                first_any is not None and update_time is not None and first_any >= update_time
            ),
            "divergence_only_late_drift": bool(
                first_any is not None and diff_series and first_any - diff_series[0]["time"] > 60.0
            ),
            "trace_solver_input": False,
            "output_only_correction": False,
            "bad_epoch_deletion_for_metric": False,
        }
    )
    return result
