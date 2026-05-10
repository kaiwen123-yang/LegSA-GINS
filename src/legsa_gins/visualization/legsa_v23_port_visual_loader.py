"""Load N4H4E source-backed port visual-validation inputs.

中文说明：本模块只读取 runtime-only 的 port、dual_final_v23 与 evaluation
reference 数据；trace/reference 不进入 solver，final_v23 output 不作为 proposed
solver input。
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from legsa_gins.evaluation.error_series_parity import load_official_error_series
from legsa_gins.evaluation.legsa_v23_port_final_v23_parity_eval import load_nav_rows
from legsa_gins.evaluation.official_case_review_reproduction import (
    parse_kfgins_nav,
    reconstruct_reference_from_error_series,
)
from legsa_gins.evaluation.trajectory_metrics import load_trace_reference
from legsa_gins.visualization.dual_replay_plot_loader import parse_kfgins_std


R3C_REPORT_NAMES = [
    "PORT_VS_FINALV23_NAV_PARITY_REPORT.json",
    "FINALV23_VS_TRACE_ABSOLUTE_REPRO_REPORT.json",
    "PORT_VS_TRACE_ABSOLUTE_REPORT.json",
    "PORT_PARITY_VS_ABSOLUTE_COMPARISON_REPORT.json",
    "PORT_METRIC_NAMESPACE_DECISION_REPORT.json",
]


def _write_json(path: str | Path, data: dict[str, Any]) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _load_json(path: str | Path) -> dict[str, Any]:
    candidate = Path(path)
    if not candidate.exists():
        return {}
    try:
        loaded = json.loads(candidate.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return loaded if isinstance(loaded, dict) else {}


def _newest(paths: list[Path]) -> Path | None:
    existing = [path for path in paths if path.exists() and path.is_file()]
    return max(existing, key=lambda path: path.stat().st_mtime) if existing else None


def _find_file(roots: list[str | Path], names: list[str]) -> Path | None:
    candidates: list[Path] = []
    for root_value in roots:
        root = Path(root_value)
        if not root.exists():
            continue
        for name in names:
            candidates.append(root / "run" / name)
            candidates.extend(root.glob(f"**/{name}"))
    return _newest(candidates)


def _normalize_std_row(row: dict[str, str], index: int) -> dict[str, float]:
    def value(*names: str, default: float = 0.0) -> float:
        for name in names:
            raw = row.get(name)
            if raw is not None and str(raw).strip() != "":
                return float(raw)
        return default

    timestamp = value("time", "timestamp", "tow", default=float(index))
    return {
        "timestamp": timestamp,
        "time": timestamp,
        "std_pos_n_m": value("std_pos_n_m", "std_0"),
        "std_pos_e_m": value("std_pos_e_m", "std_1"),
        "std_pos_d_m": value("std_pos_d_m", "std_2"),
        "std_roll_deg": value("std_roll_deg", "std_6"),
        "std_pitch_deg": value("std_pitch_deg", "std_7"),
        "std_yaw_deg": value("std_yaw_deg", "std_8"),
        "std_attitude_unit_input": "deg" if any(name in row for name in ("std_roll_deg", "std_pitch_deg", "std_yaw_deg")) else "unlabeled_legacy",
    }


def load_port_std(path: str | Path | None, nav_rows: list[dict[str, float]] | None = None) -> list[dict[str, float]]:
    """Load LegSA_PORT_STD.csv and borrow NAV timestamps when STD has row index only."""

    if not path or not Path(path).exists():
        return []
    rows: list[dict[str, float]] = []
    with Path(path).open("r", encoding="utf-8-sig", newline="") as handle:
        for index, raw in enumerate(csv.DictReader(handle)):
            row = _normalize_std_row(raw, index)
            if nav_rows and "time" not in raw and "timestamp" not in raw and index < len(nav_rows):
                row["timestamp"] = float(nav_rows[index]["timestamp"])
                row["time"] = row["timestamp"]
            rows.append(row)
    rows.sort(key=lambda item: item["timestamp"])
    return rows


def _load_trace_rows(trace_path: str | Path) -> list[dict[str, float]]:
    try:
        return load_trace_reference(trace_path)
    except (KeyError, ValueError):
        return load_nav_rows(trace_path)


def _locate_trace_reference(dual_root: str | Path, trace_path: str | Path | None = None) -> tuple[list[dict[str, float]], str]:
    if trace_path:
        candidate = Path(trace_path)
        if candidate.exists():
            return _load_trace_rows(candidate), "provided_trace_path_runtime_only"
    dual = Path(dual_root)
    nav = dual / "KF_GINS_Navresult.nav"
    error_series = dual / "error_series.csv"
    if nav.exists() and error_series.exists():
        rows = reconstruct_reference_from_error_series(
            parse_kfgins_nav(nav),
            load_official_error_series(error_series),
        )
        return rows, "dual_official_nav_plus_error_series_reconstruction"
    return [], "evidence_missing"


def locate_visual_inputs(
    *,
    r3_root: str | Path,
    r3a_root: str | Path,
    r3b_root: str | Path,
    r3c_root: str | Path,
    dual_root: str | Path,
    trace_path: str | Path | None = None,
) -> dict[str, Any]:
    roots = [r3c_root, r3b_root, r3a_root, r3_root]
    port_nav = _find_file(roots, ["EVAL_NAV.csv", "LegSA_PORT_NAV.nav"])
    port_std = _find_file(roots, ["LegSA_PORT_STD.csv"])
    dual = Path(dual_root)
    trace_rows, trace_source = _locate_trace_reference(dual, trace_path)
    r3c_reports = {name: _load_json(Path(r3c_root) / name) for name in R3C_REPORT_NAMES}
    return {
        "port_nav_path": str(port_nav) if port_nav else None,
        "port_std_path": str(port_std) if port_std else None,
        "final_v23_nav_path": str(dual / "KF_GINS_Navresult.nav") if (dual / "KF_GINS_Navresult.nav").exists() else None,
        "final_v23_std_path": str(dual / "KF_GINS_STD.txt") if (dual / "KF_GINS_STD.txt").exists() else None,
        "final_v23_summary_path": str(dual / "summary.json") if (dual / "summary.json").exists() else None,
        "final_v23_error_series_path": str(dual / "error_series.csv") if (dual / "error_series.csv").exists() else None,
        "trace_rows": trace_rows,
        "trace_source": trace_source,
        "r3c_reports": r3c_reports,
    }


def load_visual_inputs(
    *,
    r3_root: str | Path,
    r3a_root: str | Path,
    r3b_root: str | Path,
    r3c_root: str | Path,
    dual_root: str | Path,
    output_dir: str | Path,
    trace_path: str | Path | None = None,
) -> dict[str, Any]:
    located = locate_visual_inputs(
        r3_root=r3_root,
        r3a_root=r3a_root,
        r3b_root=r3b_root,
        r3c_root=r3c_root,
        dual_root=dual_root,
        trace_path=trace_path,
    )
    port_rows = load_nav_rows(located["port_nav_path"]) if located.get("port_nav_path") else []
    final_rows = load_nav_rows(located["final_v23_nav_path"]) if located.get("final_v23_nav_path") else []
    port_std = load_port_std(located.get("port_std_path"), port_rows)
    final_std = parse_kfgins_std(located["final_v23_std_path"]) if located.get("final_v23_std_path") else []
    r3c_reports = located["r3c_reports"]
    r3c_reports_found = {name: bool(report) for name, report in r3c_reports.items()}
    manifest = {
        "phase": "N4H4E",
        "port_nav_found": bool(port_rows),
        "port_std_found": bool(port_std),
        "final_v23_nav_found": bool(final_rows),
        "final_v23_std_found": bool(final_std),
        "trace_found": bool(located["trace_rows"]),
        "trace_source": located["trace_source"],
        "r3c_reports_found": r3c_reports_found,
        "r3c_all_reports_found": all(r3c_reports_found.values()),
        "source_backed_port_core_role": "source_backed_port_core",
        "final_v23_role": "final_v23_reference_baseline",
        "trace_role": "evaluation_reference_only",
        "unit_policy": {
            "port_attitude_std_unit_input": "common_unit_deg_or_unlabeled_legacy",
            "finalv23_attitude_std_unit_input": "deg",
            "plot_attitude_std_unit": "deg",
            "conversion_applied_to_port": "none_in_N4H4E_loader",
            "conversion_applied_to_finalv23": "none",
            "std_unit_audit_followup": "N4H4E1",
        },
        "final_v23_output_solver_input": False,
        "trace_solver_input": False,
        "reference_eval_only": True,
        "visual_validation_only": True,
        "paper_performance_claim": False,
        "proposed_factor_claim": False,
        "output_only_correction": False,
        "bad_epoch_deletion_for_metric": False,
        "no_outperform_final_v23_claim": True,
    }
    _write_json(Path(output_dir) / "VISUAL_INPUT_MANIFEST.json", manifest)
    return {
        **located,
        "port_rows": port_rows,
        "final_v23_rows": final_rows,
        "port_std_rows": port_std,
        "final_v23_std_rows": final_std,
        "trace_rows": located["trace_rows"],
        "manifest": manifest,
    }
