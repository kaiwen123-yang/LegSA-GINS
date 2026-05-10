#!/usr/bin/env python3
"""Run N5A RTKLIB and ephemeris discovery.

中文说明：本脚本只接受 runtime 参数/环境变量，不在 tracked 文件中硬编码本机绝对路径。
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from legsa_gins.raw_gnss.ephemeris_discovery import discover_ephemeris
from legsa_gins.raw_gnss.raw_doppler_factor_report import write_json_report
from legsa_gins.raw_gnss.rtklib_discovery import discover_rtklib


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rtklib-root", required=True)
    parser.add_argument("--ephemeris-search-root", action="append", default=[])
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    rtklib_report = discover_rtklib(args.rtklib_root)
    eph_roots = args.ephemeris_search_root or [args.rtklib_root]
    eph_report = discover_ephemeris(eph_roots)
    write_json_report(rtklib_report, out / "RTKLIB_DISCOVERY_REPORT.json")
    write_json_report(eph_report, out / "EPHEMERIS_DISCOVERY_REPORT.json")
    print(out / "RTKLIB_DISCOVERY_REPORT.json")
    print(out / "EPHEMERIS_DISCOVERY_REPORT.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
