#!/usr/bin/env python3
"""Audit that N5A never treats NAV-PVT/.gnss velocity as raw Doppler.

中文说明：NAV-PVT velocity 和 .gnss 速度只能是 baseline receiver-native velocity。
"""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def require_text(path: str, needles: list[str]) -> None:
    text = (ROOT / path).read_text(encoding="utf-8")
    for needle in needles:
        if needle not in text:
            raise AssertionError(f"{path} missing text: {needle}")


def audit_repository() -> None:
    docs = [
        "docs/experiments/n5a_raw_doppler_factor_activation.md",
        "docs/experiments/n5a_raw_gnss_message_scan.md",
        "docs/experiments/n5a_raw_doppler_measurement_model.md",
        "docs/experiments/n5a_factor_integration_contract.md",
    ]
    for doc in docs:
        require_text(doc, ["NAV-PVT velocity is not raw Doppler", ".gnss vn/ve/vd"])
    require_text(
        "src/legsa_gins/raw_gnss/ubx_raw_message_scanner.py",
        ["UBX-NAV-PVT", "UBX-RXM-RAWX", "pvt_velocity_not_raw_doppler"],
    )
    require_text(
        "cpp/legsa_v23_port_core/src/factors/raw_doppler_factor_loader.cpp",
        ["不能读取 NAV-PVT 或 .gnss", "provider_status"],
    )
    require_text(
        "src/legsa_gins/raw_gnss/raw_doppler_readiness.py",
        ["rawx_missing", "provider_missing"],
    )


def main() -> int:
    audit_repository()
    print("Raw Doppler not NAV-PVT velocity audit passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
