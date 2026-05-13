#!/usr/bin/env python3
"""Audit N8A1 state/epoch mapping logic on a toy state table.

中文说明：toy 审计验证 state_count 解释为 epoch_count。
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from legsa_gins.fgo.fgo_state_epoch_mapping_audit import audit_state_epoch_mapping


def main() -> int:
    rows = [
        {"time": 0.0, "lat_deg": 30, "lon_deg": 120, "height_m": 10, "roll_deg": 0, "pitch_deg": 0, "yaw_deg": 0, "vn_mps": 1, "ve_mps": 0, "vd_mps": 0},
        {"time": 1.0, "lat_deg": 30, "lon_deg": 120, "height_m": 10, "roll_deg": 0, "pitch_deg": 0, "yaw_deg": 1, "vn_mps": 1, "ve_mps": 0, "vd_mps": 0},
    ]
    report = audit_state_epoch_mapping(ekf_rows=rows, fgo_rows=rows, dataset_report={"state_count": 2})
    if report.get("state_count_interpretation") != "epoch_count":
        raise SystemExit("state_count should be interpreted as epoch_count")
    if report.get("state_dimension_per_epoch") != 9:
        raise SystemExit("unexpected state dimension")
    if report.get("blocker_status") != "clear":
        raise SystemExit("unexpected state/epoch blocker")
    print("audit_fgo_state_epoch_mapping passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
