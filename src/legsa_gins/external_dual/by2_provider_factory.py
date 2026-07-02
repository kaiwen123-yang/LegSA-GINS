"""BY2 provider factory facade for PAPER10Q2R2R1 A1."""

from __future__ import annotations

from pathlib import Path

from .go2_body_provider import parse_go2_body
from .raw_dual_receiver_provider import summarize_raw_dual_receiver
from .status_dual_yaw_provider import build_status_dual_yaw_provider
from .trace_reference_adapter import load_trace_yaw


def build_by2_provider(receiver_root: Path, go2_body_path: Path) -> dict[str, object]:
    return {
        "status_epochs": build_status_dual_yaw_provider(receiver_root / "gnss1-status.csv", receiver_root / "gnss2-status.csv"),
        "go2_epochs": parse_go2_body(go2_body_path),
        "trace_epochs": load_trace_yaw(next(receiver_root.glob("trace_vrtk2*.csv"))),
        "raw_summary": summarize_raw_dual_receiver(receiver_root / "gnss1-raw.csv", receiver_root / "gnss2-raw.csv", receiver_root / "corr-raw.csv"),
    }
