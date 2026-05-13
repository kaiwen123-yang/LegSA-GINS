"""Dataset builder for N8A no-feedback FGO."""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path
from typing import Any

from legsa_gins.fgo.fgo_state_types import FGOState, FGOStateDataset


def _f(value: Any, fallback: float = 0.0) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return fallback
    return out if math.isfinite(out) else fallback


def _read_csv(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def find_n8a_state_source(n7c6_root: str | Path) -> Path | None:
    """中文说明：优先使用 N7C6 selected variant 的 EKF runtime state。"""
    root = Path(n7c6_root)
    candidates = [
        root / "variants" / "joint_rp1deg_hv1p0" / "EVAL_NAV.csv",
        root / "variants" / "joint_rp1p6deg_hv1p0" / "EVAL_NAV.csv",
        root / "variants" / "horizontal_only_fixed_1p0" / "EVAL_NAV.csv",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    matches = sorted(root.rglob("EVAL_NAV.csv"))
    return matches[0] if matches else None


def build_n8a_dataset(*, n7c6_root: str | Path, max_states: int = 800) -> tuple[FGOStateDataset, dict[str, Any]]:
    source = find_n8a_state_source(n7c6_root)
    rows = _read_csv(source) if source else []
    if rows and len(rows) > max_states:
        stride = max(1, len(rows) // max_states)
        rows = rows[::stride]
    states = [
        FGOState(
            index=index,
            time=_f(row.get("time") or row.get("timestamp"), float(index)),
            lat_deg=_f(row.get("lat_deg")),
            lon_deg=_f(row.get("lon_deg")),
            height_m=_f(row.get("height_m")),
            roll_deg=_f(row.get("roll_deg")),
            pitch_deg=_f(row.get("pitch_deg")),
            yaw_deg=_f(row.get("yaw_deg")),
            vn_mps=_f(row.get("vn") or row.get("vn_mps")),
            ve_mps=_f(row.get("ve") or row.get("ve_mps")),
            vd_mps=_f(row.get("vd") or row.get("vd_mps")),
        )
        for index, row in enumerate(rows)
    ]
    dataset = FGOStateDataset(states=states)
    active_factor_count = max(0, len(states) * 5 + max(0, len(states) - 1))
    diagnostic_factor_count = max(0, len(states) * 4)
    report = {
        "stage": "N8A_no_feedback_fgo_foundation",
        "state_source_role": "N7C6_SELECTED_EKF_RUNTIME_STATE",
        "state_source_found": source is not None,
        "state_source_path_role": "N7C6_REPORT_OUTPUT_DIR/variants/selected/EVAL_NAV.csv" if source else "",
        "state_count": len(states),
        "active_factor_count_estimate": active_factor_count,
        "diagnostic_candidate_factor_count_estimate": diagnostic_factor_count,
        "epoch_deletion": False,
        "trace_based_selection": False,
        "final_v23_solver_input": False,
        "paper_performance_claim": False,
        "no_feedback": True,
    }
    return dataset, report


def write_dataset_report(path: str | Path, report: dict[str, Any]) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output


def write_state_csv(path: str | Path, dataset: FGOStateDataset) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    rows = dataset.to_rows()
    fields = list(rows[0]) if rows else ["index", "time"]
    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    return output
