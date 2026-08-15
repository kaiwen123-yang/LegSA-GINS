#!/usr/bin/env python3
"""Run the isolated Phase-4 EXT04 Wu-2025/C00 lifecycle."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

for _name in (
    "OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS",
    "NUMEXPR_NUM_THREADS",
):
    os.environ[_name] = "1"

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
SOURCE_ROOT = REPOSITORY_ROOT / "src"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from legsa_gins.paper_rebuild.horizontal_literature.phase4_runner import (  # noqa: E402
    ALLOWED_MODES,
    CASE_ID,
    DEFAULT_WORKERS,
    METHOD_ID,
    run_phase4,
    terminal_json,
    terminalize_failure,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--paths-config", type=Path,
        default=Path("configs/paper_rebuild/DATA_PATHS.CLEAN3R4.local.yaml"),
    )
    parser.add_argument("--mode", choices=sorted(ALLOWED_MODES), default="full")
    parser.add_argument("--method-id", default=METHOD_ID)
    parser.add_argument("--case-id", default=CASE_ID)
    parser.add_argument("--trace-mode", default="disabled")
    parser.add_argument("--workers", type=int, default=DEFAULT_WORKERS)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--execution-lock", type=Path)
    parser.add_argument("--execution-lock-sha256")
    parser.add_argument("--preexisting-manifest", type=Path)
    parser.add_argument("--preexisting-manifest-sha256")
    parser.add_argument("--artifact-root", type=Path)
    parser.add_argument(
        "--reviewer-verdict", choices=("PENDING", "APPROVED", "REJECTED"),
        default="PENDING",
    )
    parser.add_argument("--reviewer-summary", default="")
    parser.add_argument("--reviewer-summary-sha256")
    parser.add_argument(
        "--focused-tests", choices=("NOT_RUN", "PASS", "FAIL"),
        default="NOT_RUN",
    )
    parser.add_argument(
        "--full-tests", choices=("NOT_RUN", "PASS", "FAIL"),
        default="NOT_RUN",
    )
    parser.add_argument("--focused-test-summary", default="")
    parser.add_argument("--full-test-summary", default="")
    parser.add_argument("--expected-original-report-sha256")
    parser.add_argument("--expected-original-status-sha256")
    parser.add_argument("--expected-r1-report-sha256")
    parser.add_argument("--expected-r1-status-sha256")
    parser.add_argument("--expected-r2-report-sha256")
    parser.add_argument("--expected-r2-status-sha256")
    parser.add_argument("--expected-r3-report-sha256")
    parser.add_argument("--expected-r3-status-sha256")
    parser.add_argument("--expected-r4-report-sha256")
    parser.add_argument("--expected-r4-status-sha256")
    parser.add_argument("--expected-r5-report-sha256")
    parser.add_argument("--expected-r5-status-sha256")
    parser.add_argument("--expected-r6-report-sha256")
    parser.add_argument("--expected-r6-status-sha256")
    args = parser.parse_args()
    try:
        result = run_phase4(
            args.paths_config, mode=args.mode, method_id=args.method_id,
            case_id=args.case_id, trace_mode=args.trace_mode,
            workers=args.workers, resume=args.resume,
            execution_lock=args.execution_lock,
            execution_lock_sha256=args.execution_lock_sha256,
            preexisting_manifest=args.preexisting_manifest,
            preexisting_manifest_sha256=args.preexisting_manifest_sha256,
            artifact_root=args.artifact_root,
            reviewer_verdict=args.reviewer_verdict,
            reviewer_summary=args.reviewer_summary,
            reviewer_summary_sha256=args.reviewer_summary_sha256,
            focused_tests=args.focused_tests, full_tests=args.full_tests,
            focused_test_summary=args.focused_test_summary,
            full_test_summary=args.full_test_summary,
            expected_original_report_sha256=args.expected_original_report_sha256,
            expected_original_status_sha256=args.expected_original_status_sha256,
            expected_r1_report_sha256=args.expected_r1_report_sha256,
            expected_r1_status_sha256=args.expected_r1_status_sha256,
            expected_r2_report_sha256=args.expected_r2_report_sha256,
            expected_r2_status_sha256=args.expected_r2_status_sha256,
            expected_r3_report_sha256=args.expected_r3_report_sha256,
            expected_r3_status_sha256=args.expected_r3_status_sha256,
            expected_r4_report_sha256=args.expected_r4_report_sha256,
            expected_r4_status_sha256=args.expected_r4_status_sha256,
            expected_r5_report_sha256=args.expected_r5_report_sha256,
            expected_r5_status_sha256=args.expected_r5_status_sha256,
            expected_r6_report_sha256=args.expected_r6_report_sha256,
            expected_r6_status_sha256=args.expected_r6_status_sha256,
        )
    except Exception as exc:
        result = terminalize_failure(
            args.paths_config, args.mode, exc,
            execution_lock=args.execution_lock,
            execution_lock_sha256=args.execution_lock_sha256,
            preexisting_manifest=args.preexisting_manifest,
            preexisting_manifest_sha256=args.preexisting_manifest_sha256,
            artifact_root=args.artifact_root,
        )
    print(terminal_json(result))
    status = str(result.get("terminal_status", ""))
    return 0 if status.startswith("PASS_PHASE4_") else 2


if __name__ == "__main__":
    raise SystemExit(main())
