"""Load N5D raw Doppler visual/stress inputs.

中文说明：本模块只读取 runtime-only N5B/N5C/N5D 报告和 clean 输入；raw
Doppler 来源仍是 RTKLIB Doppler provider，不是 NAV-PVT，也不是 .gnss 速度。
"""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path
from typing import Any

from legsa_gins.evaluation.legsa_v23_port_clean_replay_evaluator import (
    align_by_time,
    compute_error_rows,
    load_port_eval_nav,
)
from legsa_gins.evaluation.official_case_review_reproduction import parse_kfgins_nav


def _f(value: Any, fallback: float = math.nan) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return fallback
    return out if math.isfinite(out) else fallback


def read_json(path: str | Path) -> dict[str, Any]:
    source = Path(path)
    if not source.exists():
        return {}
    try:
        loaded = json.loads(source.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return loaded if isinstance(loaded, dict) else {}


def write_json(path: str | Path, data: dict[str, Any]) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def read_csv_rows(path: str | Path) -> list[dict[str, str]]:
    source = Path(path)
    if not source.exists():
        return []
    with source.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def load_raw_doppler_factor_rows(path: str | Path) -> list[dict[str, float | str]]:
    rows: list[dict[str, float | str]] = []
    for row in read_csv_rows(path):
        rows.append(
            {
                "time": _f(row.get("time")),
                "vn": _f(row.get("vn")),
                "ve": _f(row.get("ve")),
                "vd": _f(row.get("vd")),
                "std_vn": _f(row.get("std_vn")),
                "std_ve": _f(row.get("std_ve")),
                "std_vd": _f(row.get("std_vd")),
                "sat_count": _f(row.get("sat_count"), 0.0),
                "provider_status": row.get("provider_status", ""),
                "quality_flag": row.get("quality_flag", ""),
            }
        )
    return rows


def load_receiver_velocity_rows(clean_gnss_15col: str | Path | None) -> list[dict[str, float]]:
    if not clean_gnss_15col or not Path(clean_gnss_15col).exists():
        return []
    rows: list[dict[str, float]] = []
    for line in Path(clean_gnss_15col).read_text(encoding="utf-8", errors="ignore").splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        cells = line.split()
        if len(cells) >= 10:
            # 中文说明：15-column .gnss vn/ve/vd 只作为 receiver-native velocity 对照，不是 raw Doppler 来源。
            rows.append({"time": _f(cells[0]), "vn": _f(cells[7]), "ve": _f(cells[8]), "vd": _f(cells[9])})
    return rows


def load_std_csv(path: str | Path | None) -> list[dict[str, float]]:
    if not path or not Path(path).exists():
        return []
    out: list[dict[str, float]] = []
    for index, row in enumerate(read_csv_rows(path)):
        item: dict[str, float] = {"row": float(index)}
        for key, value in row.items():
            item[key] = _f(value)
        out.append(item)
    return out


def find_factor_csv(n5b_root: str | Path) -> Path:
    root = Path(n5b_root)
    direct = root / "RAW_DOPPLER_VELOCITY_FACTORS.csv"
    if direct.exists():
        return direct
    matches = sorted(root.rglob("RAW_DOPPLER_VELOCITY_FACTORS.csv"))
    if matches:
        return matches[0]
    raise FileNotFoundError("RAW_DOPPLER_VELOCITY_FACTORS.csv missing under N5B root")


def find_clean_gnss(clean_root: str | Path) -> Path | None:
    root = Path(clean_root)
    for name in ["CLEAN_STATUS_YAW.gnss", "input.gnss", "clean.gnss"]:
        candidate = root / name
        if candidate.exists():
            return candidate
    matches = sorted(root.rglob("*.gnss"))
    return matches[0] if matches else None


def _nearest_pairs(
    raw_rows: list[dict[str, Any]],
    receiver_rows: list[dict[str, float]],
    *,
    tolerance: float = 0.55,
) -> list[dict[str, float]]:
    pairs: list[dict[str, float]] = []
    if not raw_rows or not receiver_rows:
        return pairs
    index = 0
    for receiver in receiver_rows:
        rtime = receiver["time"]
        while (
            index + 1 < len(raw_rows)
            and abs(float(raw_rows[index + 1]["time"]) - rtime) <= abs(float(raw_rows[index]["time"]) - rtime)
        ):
            index += 1
        raw = raw_rows[index]
        dt = float(raw["time"]) - rtime
        if abs(dt) <= tolerance:
            dn = float(raw["vn"]) - receiver["vn"]
            de = float(raw["ve"]) - receiver["ve"]
            dd = float(raw["vd"]) - receiver["vd"]
            sigma = math.sqrt(float(raw["std_vn"]) ** 2 + float(raw["std_ve"]) ** 2 + float(raw["std_vd"]) ** 2)
            pairs.append(
                {
                    "time": rtime,
                    "dt": dt,
                    "raw_vn": float(raw["vn"]),
                    "raw_ve": float(raw["ve"]),
                    "raw_vd": float(raw["vd"]),
                    "receiver_vn": receiver["vn"],
                    "receiver_ve": receiver["ve"],
                    "receiver_vd": receiver["vd"],
                    "diff_n": dn,
                    "diff_e": de,
                    "diff_d": dd,
                    "diff_norm": math.sqrt(dn * dn + de * de + dd * dd),
                    "raw_3sigma_norm": 3.0 * sigma,
                }
            )
    return pairs


def _variant_root_from_report(report: dict[str, Any]) -> Path | None:
    path = report.get("output_dir") or report.get("manifest_path")
    if not path:
        return None
    candidate = Path(path)
    if candidate.name == "RUN_MANIFEST.json":
        return candidate.parent
    return candidate


def build_variant_error_rows(variant_reports: list[dict[str, Any]], dual_root: str | Path | None) -> dict[str, list[dict[str, float]]]:
    if not dual_root or not (Path(dual_root) / "KF_GINS_Navresult.nav").exists():
        return {}
    reference = parse_kfgins_nav(Path(dual_root) / "KF_GINS_Navresult.nav")
    out: dict[str, list[dict[str, float]]] = {}
    for report in variant_reports:
        variant_id = str(report.get("variant_id", ""))
        root = _variant_root_from_report(report)
        if not variant_id or root is None:
            continue
        eval_nav = root / "EVAL_NAV.csv"
        if not eval_nav.exists():
            continue
        estimate = load_port_eval_nav(eval_nav)
        out[variant_id] = compute_error_rows(align_by_time(estimate, reference, tolerance=0.005))
    return out


def load_n5d_visual_inputs(
    *,
    factor_csv: str | Path,
    clean_root: str | Path | None,
    n5c_root: str | Path | None,
    variant_reports: list[dict[str, Any]],
    dual_root: str | Path | None = None,
    factor_diag: dict[str, Any] | None = None,
    velocity_comparison: dict[str, Any] | None = None,
    time_alignment: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Collect all visual inputs into one dictionary."""

    clean_gnss = find_clean_gnss(clean_root) if clean_root else None
    raw_rows = load_raw_doppler_factor_rows(factor_csv)
    receiver_rows = load_receiver_velocity_rows(clean_gnss)
    n5c = Path(n5c_root) if n5c_root else None
    return {
        "stage": "N5D_raw_doppler_visual_validation_and_velocity_stress_protocol",
        "factor_csv": str(factor_csv),
        "clean_gnss": str(clean_gnss) if clean_gnss else "",
        "raw_factor_rows": raw_rows,
        "receiver_velocity_rows": receiver_rows,
        "raw_receiver_velocity_pairs": _nearest_pairs(raw_rows, receiver_rows),
        "variant_reports": variant_reports,
        "variant_reports_by_id": {str(row.get("variant_id")): row for row in variant_reports},
        "variant_error_rows": build_variant_error_rows(variant_reports, dual_root),
        "factor_diagnostics": factor_diag or (read_json(n5c / "RAW_DOPPLER_FACTOR_DIAGNOSTICS_REPORT.json") if n5c else {}),
        "velocity_comparison": velocity_comparison or (read_json(n5c / "RAW_DOPPLER_VELOCITY_COMPARISON_REPORT.json") if n5c else {}),
        "time_alignment": time_alignment or (read_json(n5c / "RAW_DOPPLER_TIME_ALIGNMENT_REPORT.json") if n5c else {}),
        "n5c_ablation_comparison": read_json(n5c / "N5C_ABLATION_COMPARISON_REPORT.json") if n5c else {},
        "source_flags": {
            "raw_doppler_not_nav_pvt": True,
            "raw_doppler_not_gnss_15col": True,
            "rtklib_position_solution_used_as_solver_input": False,
            "final_v23_output_solver_input": False,
            "trace_solver_input": False,
        },
        "paper_performance_claim": False,
        "proposed_factor_claim": False,
        "no_outperform_final_v23_claim": True,
    }
