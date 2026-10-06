#!/usr/bin/env python3
"""Generate the input-only Hartley H0--H2 BY2 projection audit."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

import yaml

from legsa_gins.paper_rebuild.horizontal_literature.hartley_h0_h2 import (
    DEFAULT_MINIMUM_DWELL_SAMPLES,
    EXPECTED_BY2_MESSAGE_COUNT,
    EXPECTED_BY2_USABLE_RECORD_COUNT,
    PRODUCTION_COMPLETE_RECORD_POLICY_V1,
    HartleyH0H2Error,
    build_hartley_input_audit,
    hartley_audit_prepublication_blocker,
    resolve_hartley_audit_paths,
    scan_hartley_complete_record_prefix,
    verify_by2_hash_lock,
    write_hartley_input_audit,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PATHS_CONFIG = (
    REPOSITORY_ROOT / "configs/paper_rebuild/DATA_PATHS.CLEAN3R4.local.yaml"
)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--paths-config",
        type=Path,
        default=DEFAULT_PATHS_CONFIG,
        help="Ignored local path aliases; the BY2 source has no direct-path override.",
    )
    parser.add_argument(
        "--expected-complete-record-count",
        type=int,
        default=EXPECTED_BY2_USABLE_RECORD_COUNT,
        help="Frozen usable-prefix count; any other production value fails closed.",
    )
    parser.add_argument(
        "--minimum-dwell-samples",
        type=int,
        default=DEFAULT_MINIMUM_DWELL_SAMPLES,
        help="Declared sample-count policy converted using the measured median cadence.",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    arguments = parse_args(argv)
    try:
        if arguments.expected_complete_record_count != EXPECTED_BY2_USABLE_RECORD_COUNT:
            raise HartleyH0H2Error("unapproved production usable-record count")
        if arguments.minimum_dwell_samples != DEFAULT_MINIMUM_DWELL_SAMPLES:
            raise HartleyH0H2Error("unapproved production contact dwell sample count")
        paths = resolve_hartley_audit_paths(arguments.paths_config)
        identity_before = verify_by2_hash_lock(paths)
        scan = scan_hartley_complete_record_prefix(
            paths.by2_source,
            policy=PRODUCTION_COMPLETE_RECORD_POLICY_V1,
        )
        identity_after = verify_by2_hash_lock(paths)
        if identity_before != identity_after or not scan.raw_before_after_identity_match:
            raise HartleyH0H2Error("raw before/after identity mismatch")
        records = scan.records
        audit = build_hartley_input_audit(
            records,
            expected_complete_record_count=arguments.expected_complete_record_count,
            minimum_dwell_samples=arguments.minimum_dwell_samples,
            scan_result=scan,
        )
        output_root = paths.default_output_root
        blocker = hartley_audit_prepublication_blocker(audit)
        if blocker is not None:
            print(json.dumps({
                **blocker,
                "canonical_output_written": False,
                "real_by2_filter_run": False,
            }, sort_keys=True))
            if blocker["terminal_status"] == "BLOCKED_LSE01_CONTACT_INPUT_NOT_IDENTIFIABLE":
                return 3
            if blocker["terminal_status"] == "BLOCKED_LSE01_FOOT_ORDER_CONTRACT_UNRESOLVED":
                return 4
            return 2
        summary = write_hartley_input_audit(
            output_root,
            audit,
            source_identity={
                **identity_after,
                "complete_record_policy_id": scan.policy.policy_id,
                "physical_record_start_count": EXPECTED_BY2_MESSAGE_COUNT,
                "usable_complete_record_count": scan.complete_record_count,
                "raw_before_after_identity_match": True,
            },
        )
    except (OSError, HartleyH0H2Error, yaml.YAMLError) as exc:
        print(json.dumps({
            "terminal_status": "BLOCKED_LSE01_BY2_REQUIRED_FIELD_MISSING",
            "error": str(exc),
            "real_by2_filter_run": False,
        }, sort_keys=True))
        return 2

    print(json.dumps({
        "terminal_status": "PASS_LSE01_H0_H2_BY2_INPUT_AUDIT_READY",
        "audit_output_root": str(output_root),
        "complete_record_count": summary["complete_record_count"],
        "physical_record_start_count": EXPECTED_BY2_MESSAGE_COUNT,
        "duration_seconds": summary["timing"]["duration_seconds"],
        "median_rate_hz": summary["timing"]["median_rate_hz"],
        "real_by2_filter_run": False,
    }, indent=2, sort_keys=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
