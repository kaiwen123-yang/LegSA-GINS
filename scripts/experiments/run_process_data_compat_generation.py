#!/usr/bin/env python3
"""Run N4H1P process_data-compatible input generation.

中文说明：本脚本只在指定 output-dir 生成 baseline/parity 输入重建产物；
不提交 raw data，不运行 proposed solver，不使用 trace 作为 formal input。
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from legsa_gins.input_generation.process_data_compat import (  # noqa: E402
    generate_process_data_compat_inputs,
)


def _bool_arg(value: str) -> bool:
    lowered = value.strip().lower()
    if lowered in {"1", "true", "t", "yes", "y"}:
        return True
    if lowered in {"0", "false", "f", "no", "n"}:
        return False
    raise argparse.ArgumentTypeError(f"Expected true/false, got {value!r}")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fix-root", required=True)
    parser.add_argument("--body-imu", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--base-time", type=float, default=1772784000.0)
    parser.add_argument("--yaw-source-mode", choices=["status", "trace"], default="status")
    parser.add_argument("--yaw-std-mode", default="fixed_1p5")
    parser.add_argument("--yaw-sign", type=float, default=1.0)
    parser.add_argument("--yaw-install-offset-deg", type=float, default=0.0)
    parser.add_argument("--enable-outage", type=_bool_arg, default=False)
    parser.add_argument("--outlier-mode", default="none")
    parser.add_argument("--yaw-noise-std-deg", type=float, default=0.0)
    parser.add_argument("--imu-install-roll-deg", type=float, default=-1.0)
    parser.add_argument("--imu-install-pitch-deg", type=float, default=0.0)
    parser.add_argument("--imu-install-yaw-deg", type=float, default=0.0)
    parser.add_argument("--imu-gnss-time-offset", type=float, default=0.0)
    parser.add_argument("--max-status-rows", type=int, default=None)
    parser.add_argument(
        "--max-raw-rows",
        type=int,
        default=None,
        help="Optional diagnostic raw CSV row limit; omit or pass 0 for unlimited scan.",
    )
    parser.add_argument("--max-imu-messages", type=int, default=None)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    result = generate_process_data_compat_inputs(
        args.fix_root,
        args.body_imu,
        args.output_dir,
        base_time=args.base_time,
        yaw_source_mode=args.yaw_source_mode,
        yaw_sign=args.yaw_sign,
        yaw_install_offset_deg=args.yaw_install_offset_deg,
        yaw_std_mode=args.yaw_std_mode,
        enable_outage=args.enable_outage,
        outlier_mode=args.outlier_mode,
        yaw_noise_std_deg=args.yaw_noise_std_deg,
        imu_install_roll_deg=args.imu_install_roll_deg,
        imu_install_pitch_deg=args.imu_install_pitch_deg,
        imu_install_yaw_deg=args.imu_install_yaw_deg,
        imu_gnss_time_offset=args.imu_gnss_time_offset,
        max_status_rows=args.max_status_rows,
        max_raw_rows=args.max_raw_rows,
        max_imu_messages=args.max_imu_messages,
    )
    if args.yaw_source_mode == "trace":
        result["diagnostic_trace_yaw_only"] = True
        result["formal_allowed"] = False
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
