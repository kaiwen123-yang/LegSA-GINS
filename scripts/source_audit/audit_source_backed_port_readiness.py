#!/usr/bin/env python3
"""Audit source-backed port readiness for N4H4R0.

中文说明：本脚本只检查 final_v23 reference gitlink、核心源文件位置和
受控移植边界；不会编译 reference，也不会把 reference 输出作为 solver 输入。
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REFERENCE = Path("reference/final_v23_repo")
EXPECTED_COMMIT = "5a4471efd4fcfcdc31e258a677af354c652ff16f"
SRC_ROOT = ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))
ARTIFACT_RE = re.compile(
    r"(input\.gnss|\.imu$|KF_GINS_Navresult\.nav|KF_GINS_STD\.txt|summary\.json|"
    r"error_series\.csv|\.png$|\.pdf$|\.svg$)"
)

from legsa_gins.source_audit.source_backed_port_readiness import (  # noqa: E402
    collect_pr21_status,
    collect_reference_status,
    make_readiness_report,
)


def _fail(message: str, details: list[str] | None = None) -> int:
    print(f"Source-backed port readiness audit failed: {message}")
    for detail in details or []:
        print(f"- {detail}")
    return 1


def _git(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )


def _tracked_files() -> list[str]:
    completed = _git(["ls-files"])
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr)
    return [line for line in completed.stdout.splitlines() if line.strip()]


def _check_no_uncontrolled_copy() -> int:
    tracked = _tracked_files()
    direct_children = [rel for rel in tracked if rel.startswith(f"{REFERENCE.as_posix()}/")]
    if direct_children:
        return _fail("submodule internals are tracked directly", direct_children[:10])
    forbidden_dirs = [
        "external/KF-GINS",
        "third_party/KF-GINS",
        "vendor/KF-GINS",
        "KF-GINS",
    ]
    present = [rel for rel in forbidden_dirs if (ROOT / rel).exists()]
    if present:
        return _fail("uncontrolled copied source tree detected", present)
    return 0


def _check_no_artifacts() -> int:
    hits = [
        rel
        for rel in _tracked_files()
        if rel != REFERENCE.as_posix()
        and not rel.startswith(f"{REFERENCE.as_posix()}/")
        and ARTIFACT_RE.search(rel)
    ]
    if hits:
        return _fail("tracked raw/result artifacts detected", hits)
    return 0


def main() -> int:
    reference = collect_reference_status(ROOT)
    pr21 = collect_pr21_status(ROOT)
    report = make_readiness_report(reference, pr21)

    failures: list[str] = []
    if not reference["reference_exists"]:
        failures.append("reference/final_v23_repo missing")
    if not reference["gitlink_is_160000"]:
        failures.append(f"gitlink mode is {reference['gitlink_mode']}, expected 160000")
    if reference["actual_commit"] != EXPECTED_COMMIT:
        failures.append(
            f"reference commit is {reference['actual_commit']}, expected {EXPECTED_COMMIT}"
        )
    missing_core = [
        role for role, status in reference["source_files"].items() if not status["exists"]
    ]
    if missing_core:
        failures.append(f"missing core source roles: {missing_core}")
    if not reference["license_status_checked"]:
        failures.append("license status was not checked")
    if report["final_v23_output_solver_input"]:
        failures.append("final_v23 output marked as solver input")
    if not report["final_v23_is_reference_not_proposed"]:
        failures.append("final_v23 reference/proposed boundary broken")

    if failures:
        print(json.dumps(report, indent=2, sort_keys=True))
        return _fail("readiness conditions failed", failures)

    for check in [_check_no_uncontrolled_copy, _check_no_artifacts]:
        result = check()
        if result:
            return result

    print(json.dumps(report, indent=2, sort_keys=True))
    print("Source-backed port readiness audit passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
