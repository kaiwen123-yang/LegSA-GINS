#!/usr/bin/env python3
"""Standardize BY2 local inputs into N4E source-role bounded artifacts.

中文说明：本脚本只在本地 probe 中读取 BY2 输入并写入指定 output-dir；不读 final_v23 output，不使用 trace 作为 solver input，不解析 raw Doppler，不做 numerical evaluation。
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from legsa_gins.datasets.by2.gnss_raw_scanner import (  # noqa: E402
    scan_gnss_raw_csv,
    write_raw_message_summary,
)
from legsa_gins.datasets.by2.gnss_status_adapter import (  # noqa: E402
    parse_gnss_status_csv,
    write_standardized_gnss_status,
)
from legsa_gins.datasets.by2.go2_body_state_parser import (  # noqa: E402
    parse_go2_body_state_text,
    write_go2_body_state_csv,
)
from legsa_gins.datasets.by2.input_manifest import (  # noqa: E402
    create_by2_input_manifest,
    write_manifest,
)
from legsa_gins.datasets.by2.trace_reference_adapter import (  # noqa: E402
    parse_trace_reference,
    write_trace_eval_reference,
)


TRACE_FILENAME = "trace_vrtk2_a87c6e_2026-03-06-08-00-54_minimal.csv"


def standardize_by2_inputs(
    *,
    fix_root: str | Path,
    body_imu: str | Path,
    output_dir: str | Path,
    max_status_rows: int | None = None,
    max_raw_rows: int | None = None,
    max_body_messages: int | None = None,
) -> dict:
    root = Path(fix_root)
    body_path = Path(body_imu)
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    gnss1_status_path = root / "gnss1-status.csv"
    gnss2_status_path = root / "gnss2-status.csv"
    gnss1_raw_path = root / "gnss1-raw.csv"
    gnss2_raw_path = root / "gnss2-raw.csv"
    trace_path = root / TRACE_FILENAME
    receiver_imu_data_path = root / "imu-data.csv"

    outputs = {
        "gnss1_status_standard": out / "BY2_GNSS1_STATUS_STANDARD.csv",
        "gnss2_status_standard": out / "BY2_GNSS2_STATUS_STANDARD.csv",
        "gnss1_raw_message_summary": out / "BY2_GNSS1_RAW_MESSAGE_SUMMARY.json",
        "gnss2_raw_message_summary": out / "BY2_GNSS2_RAW_MESSAGE_SUMMARY.json",
        "trace_reference_eval_only": out / "BY2_TRACE_REFERENCE_EVAL_ONLY.csv",
        "go2_body_state_diagnostic": out / "BY2_GO2_BODY_STATE_DIAGNOSTIC.csv",
        "input_manifest": out / "BY2_INPUT_MANIFEST.json",
    }

    gnss1_rows = parse_gnss_status_csv(
        gnss1_status_path, source_name="gnss1", max_rows=max_status_rows
    )
    gnss2_rows = parse_gnss_status_csv(
        gnss2_status_path, source_name="gnss2", max_rows=max_status_rows
    )
    write_standardized_gnss_status(gnss1_rows, outputs["gnss1_status_standard"])
    write_standardized_gnss_status(gnss2_rows, outputs["gnss2_status_standard"])

    gnss1_summary = scan_gnss_raw_csv(
        gnss1_raw_path, source_name="gnss1", max_rows=max_raw_rows
    )
    gnss2_summary = scan_gnss_raw_csv(
        gnss2_raw_path, source_name="gnss2", max_rows=max_raw_rows
    )
    write_raw_message_summary(gnss1_summary, outputs["gnss1_raw_message_summary"])
    write_raw_message_summary(gnss2_summary, outputs["gnss2_raw_message_summary"])

    trace_rows = parse_trace_reference(trace_path, max_rows=max_status_rows)
    write_trace_eval_reference(trace_rows, outputs["trace_reference_eval_only"])

    body_rows = parse_go2_body_state_text(body_path, max_messages=max_body_messages)
    write_go2_body_state_csv(body_rows, outputs["go2_body_state_diagnostic"])

    manifest = create_by2_input_manifest(
        out,
        gnss1_status_path,
        gnss2_status_path,
        gnss1_raw_path,
        gnss2_raw_path,
        trace_path,
        receiver_imu_data_path,
        body_path,
        outputs,
    )
    write_manifest(manifest, outputs["input_manifest"])
    return manifest


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fix-root", required=True, help="Local BY2 Fixposition root.")
    parser.add_argument("--body-imu", required=True, help="Local BY2 Go2/body-state text file.")
    parser.add_argument("--output-dir", required=True, help="Output directory, normally /tmp.")
    parser.add_argument("--max-status-rows", type=int, default=None)
    parser.add_argument("--max-raw-rows", type=int, default=None)
    parser.add_argument("--max-body-messages", type=int, default=None)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    standardize_by2_inputs(
        fix_root=args.fix_root,
        body_imu=args.body_imu,
        output_dir=args.output_dir,
        max_status_rows=args.max_status_rows,
        max_raw_rows=args.max_raw_rows,
        max_body_messages=args.max_body_messages,
    )
    print(f"Wrote BY2 N4E standardized outputs under {args.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
