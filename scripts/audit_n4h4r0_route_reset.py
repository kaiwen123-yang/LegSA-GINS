#!/usr/bin/env python3
"""Audit N4H4R0 route reset documentation and boundaries.

中文说明：本审计只检查路线重置、PR #21 失败证据冻结和 claim boundary，
不实现 solver，也不复制 reference 源码。
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOCS = [
    "docs/experiments/n4h4r0_pr21_failure_evidence_freeze.md",
    "docs/experiments/n4h4r0_route_reset_decision.md",
    "docs/experiments/n4h4r0_source_backed_port_policy.md",
    "docs/experiments/n4h4r0_port_readiness_checklist.md",
    "docs/experiments/n4h4r0_next_stage_n4h4r1_plan.md",
    "docs/experiments/n4h4r0_source_port_module_manifest.md",
    "docs/experiments/n4h4r0_kfgins_to_legsa_port_matrix.md",
]
GOVERNANCE = ["README.md", "PLANS.md", "PHASE_LOG.md", "CLAIM_BOUNDARY.md"]
REQUIRED_TERMS = [
    "PR #21 is not merged",
    "diagnostic/self-written attempt",
    "source-backed controlled port",
    "final_v23 is not proposed",
    "no performance claim",
    "no raw Doppler",
    "no FGO",
]
LOCAL_PATH_PATTERNS = [
    "/mnt/c/Users" + "/ykw/Desktop",
    "/mnt/c/Users" + "/86187/Desktop",
    "C:" + "\\Users",
    "/home/kaiwen" + "/legsa_n4h4d",
    "/home/kaiwen" + "/legsa_external_artifacts",
]
ARTIFACT_RE = re.compile(
    r"(input\.gnss|\.imu$|KF_GINS_Navresult\.nav|KF_GINS_STD\.txt|summary\.json|"
    r"error_series\.csv|\.png$|\.pdf$|\.svg$)"
)


def _fail(message: str, details: list[str] | None = None) -> int:
    print(f"N4H4R0 route reset audit failed: {message}")
    for detail in details or []:
        print(f"- {detail}")
    return 1


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def _git_ls_files() -> list[str]:
    completed = subprocess.run(
        ["git", "ls-files"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr)
    return [line for line in completed.stdout.splitlines() if line.strip()]


def _check_files() -> int:
    missing = [rel for rel in DOCS + GOVERNANCE if not (ROOT / rel).exists()]
    if missing:
        return _fail("missing required R0 files", missing)
    return 0


def _check_terms() -> int:
    combined = "\n".join(_read(rel) for rel in DOCS + GOVERNANCE)
    lower = combined.lower()
    missing = [term for term in REQUIRED_TERMS if term.lower() not in lower]
    if missing:
        return _fail("missing required route-reset terms", missing)
    more_terms = [
        "PR #21 is not closed",
        "cpp/legsa_v23_port_core",
        "nine-factor",
        "final_v23 output must not be used as solver input",
        "Trace remains evaluation-only",
    ]
    missing_more = [term for term in more_terms if term.lower() not in lower]
    if missing_more:
        return _fail("missing required policy terms", missing_more)
    return 0


def _check_no_local_paths() -> int:
    hits: list[str] = []
    for rel in _git_ls_files():
        if rel == "reference/final_v23_repo" or rel.startswith("reference/final_v23_repo/"):
            continue
        path = ROOT / rel
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for pattern in LOCAL_PATH_PATTERNS:
            if pattern in text:
                hits.append(f"{rel}: {pattern}")
    if hits:
        return _fail("local path leakage detected", hits)
    return 0


def _check_no_artifacts() -> int:
    hits = [
        rel
        for rel in _git_ls_files()
        if rel != "reference/final_v23_repo"
        and not rel.startswith("reference/final_v23_repo/")
        and ARTIFACT_RE.search(rel)
    ]
    if hits:
        return _fail("tracked raw/generated artifacts detected", hits)
    return 0


def main() -> int:
    for check in [_check_files, _check_terms, _check_no_local_paths, _check_no_artifacts]:
        result = check()
        if result:
            return result
    print("N4H4R0 route reset audit passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

