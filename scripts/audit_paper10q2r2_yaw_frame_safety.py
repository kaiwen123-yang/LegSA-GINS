#!/usr/bin/env python3
"""Audit Q2R2 yaw frame safety helpers."""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from legsa_gins.external_dual_methods.yaw_frame_adapter import baseline_heading_to_body_yaw_ned_deg


def main() -> int:
    assert baseline_heading_to_body_yaw_ned_deg(0.0) == 90.0
    assert baseline_heading_to_body_yaw_ned_deg(300.0) == 30.0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
