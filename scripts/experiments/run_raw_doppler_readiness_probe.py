#!/usr/bin/env python3
"""Run the full N5A raw Doppler readiness probe.

中文说明：probe 会扫描 RAWX/SFRBX/RTCM，尝试 RTKLIB convbin/rnx2rtkp，并在 provider
缺失时输出 blocker；不会把 NAV-PVT velocity 或 .gnss vn/ve/vd 当作 raw Doppler。
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from legsa_gins.raw_gnss.ephemeris_discovery import discover_ephemeris
from legsa_gins.raw_gnss.raw_doppler_factor_report import write_json_report
from legsa_gins.raw_gnss.raw_doppler_readiness import decide_readiness
from legsa_gins.raw_gnss.rtklib_discovery import discover_rtklib
from legsa_gins.raw_gnss.rtklib_doppler_provider import attempt_rtklib_provider
from legsa_gins.raw_gnss.ubx_raw_binary_rebuilder import rebuild_fix_root
from legsa_gins.raw_gnss.ubx_raw_message_scanner import scan_fix_root
from legsa_gins.raw_gnss.ubx_rawx_parser import parse_fix_root, report_measurements, write_epochs_jsonl
from legsa_gins.raw_gnss.ubx_sfrbx_scanner import scan_fix_root as scan_sfrbx_fix_root


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fix-root", required=True)
    parser.add_argument("--rtklib-root", required=True)
    parser.add_argument("--ephemeris-search-root", action="append", default=[])
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--allow-run", action="store_true")
    args = parser.parse_args()
    if not args.allow_run:
        raise SystemExit("--allow-run is required for runtime filesystem probing")
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)

    rtklib_report = discover_rtklib(args.rtklib_root)
    eph_roots = args.ephemeris_search_root or [args.rtklib_root]
    ephemeris_report = discover_ephemeris(eph_roots)
    scan_report = scan_fix_root(args.fix_root)
    rebuild_report = rebuild_fix_root(args.fix_root, out)
    rebuilt_ubx = [
        item.get("output_ubx", "")
        for item in rebuild_report.get("files", {}).values()
        if item.get("rebuilt_ubx_available")
    ]
    measurements = parse_fix_root(args.fix_root, rebuilt_ubx)
    rawx_report = report_measurements(measurements)
    sfrbx_report = scan_sfrbx_fix_root(args.fix_root)
    provider_report = attempt_rtklib_provider(
        rtklib_report=rtklib_report,
        ephemeris_report=ephemeris_report,
        rebuild_report=rebuild_report,
        output_dir=out,
    )
    decision = decide_readiness(scan_report, ephemeris_report, rtklib_report, provider_report)

    write_json_report(scan_report, out / "RAW_GNSS_MESSAGE_SCAN_REPORT.json")
    write_json_report(rebuild_report, out / "UBX_REBUILD_REPORT.json")
    write_json_report(rawx_report, out / "RAWX_DOPPLER_EPOCH_REPORT.json")
    write_epochs_jsonl(measurements, out / "RAW_DOPPLER_EPOCHS.jsonl")
    write_json_report(sfrbx_report, out / "SFRBX_READINESS_REPORT.json")
    write_json_report(rtklib_report, out / "RTKLIB_DISCOVERY_REPORT.json")
    write_json_report(ephemeris_report, out / "EPHEMERIS_DISCOVERY_REPORT.json")
    write_json_report(provider_report, out / "RTKLIB_RAW_DOPPLER_PROVIDER_REPORT.json")
    write_json_report(decision.to_dict(), out / "RAW_DOPPLER_READINESS_DECISION.json")
    print(out / "RAW_DOPPLER_READINESS_DECISION.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
