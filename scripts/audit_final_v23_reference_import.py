#!/usr/bin/env python3
"""Audit the controlled final_v23 reference import contract.

中文说明：只检查 N4H3 reference import 的 gitlink、文档和禁提交边界，
不读取外部 raw data，也不把 final_v23 视为 proposed solver。
"""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
REFERENCE_PATH = Path("reference/final_v23_repo")
EXPECTED_URL = "git@github.com:kaiwen123-yang/KF-GINS-graduation-design.git"
REQUIRED_DOCS = [
    "docs/source_audit/final_v23_reference_import.md",
    "docs/source_audit/final_v23_reference_provenance.md",
    "docs/source_audit/final_v23_reference_boundary.md",
    "docs/experiments/final_v23_to_legsa_transplant_plan.md",
    "docs/experiments/kfgins_full_framework_transplant_matrix.md",
    "docs/experiments/clean_noisy_input_provenance_policy.md",
    "docs/experiments/n4h3_reference_import_decision.md",
    "docs/experiments/n4h4_legsa_v23_core_implementation_plan.md",
    "docs/experiments/n4h4_unified_filter_interface_contract.md",
    "docs/experiments/nine_factor_system_roadmap.md",
    "docs/codex_prompts/N4H3_controlled_final_v23_reference_import.md",
    "THIRD_PARTY_NOTICES.md",
]
REQUIRED_STRINGS = [
    "final_v23 is not proposed",
    "final_v23 outputs must not be used as proposed solver input",
    "no raw data committed",
]
LOCAL_PATH_PATTERNS = [
    "/mnt/c/Users" + "/ykw/Desktop",
    "/mnt/c/Users" + "/86187/Desktop",
    "C:" + "\\Users",
    "/home/kaiwen" + "/legsa_n4h2g_clean_replay",
    "/home/kaiwen" + "/legsa_n4h2g2_clean_independence",
    "/home/kaiwen" + "/legsa_external_artifacts",
]
FORBIDDEN_ARTIFACT_NAMES = {
    "error_series.csv",
    "summary.json",
}
FORBIDDEN_ARTIFACT_SUFFIXES = {
    ".gnss",
    ".imu",
    ".nav",
    ".std",
    ".bag",
    ".db3",
    ".ubx",
    ".rtcm",
    ".rinex",
    ".obs",
    ".rnx",
}


def _git(args: list[str]) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True)


def _tracked_files() -> list[str]:
    output = _git(["ls-files"])
    return [line.strip() for line in output.splitlines() if line.strip()]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def _is_reference_child(path: str) -> bool:
    prefix = f"{REFERENCE_PATH.as_posix()}/"
    return path.startswith(prefix)


def _audit_submodule() -> bool:
    gitmodules = ROOT / ".gitmodules"
    if not gitmodules.exists():
        return False
    text = gitmodules.read_text(encoding="utf-8")
    if REFERENCE_PATH.as_posix() not in text:
        raise AssertionError(".gitmodules missing reference/final_v23_repo")
    if EXPECTED_URL not in text:
        raise AssertionError(".gitmodules missing expected final_v23 URL")
    ls_files = _git(["ls-files", "-s", REFERENCE_PATH.as_posix()]).strip()
    if not ls_files:
        return False
    mode = ls_files.split()[0]
    if mode != "160000":
        raise AssertionError(f"reference gitlink mode is {mode}, expected 160000")
    direct_children = [path for path in _tracked_files() if _is_reference_child(path)]
    if direct_children:
        raise AssertionError(f"submodule internal files tracked directly: {direct_children[:5]}")
    return True


def _audit_docs() -> None:
    for rel in REQUIRED_DOCS:
        if not (ROOT / rel).exists():
            raise AssertionError(f"missing required doc: {rel}")
    combined = "\n".join(_read(rel) for rel in REQUIRED_DOCS)
    lowered = combined.lower()
    for required in REQUIRED_STRINGS:
        if required.lower() not in lowered:
            raise AssertionError(f"missing required boundary string: {required}")


def _audit_tracked_text() -> None:
    for rel in _tracked_files():
        if rel == REFERENCE_PATH.as_posix() or _is_reference_child(rel):
            continue
        path = ROOT / rel
        if not path.is_file():
            continue
        data = path.read_bytes()
        text = data.decode("utf-8", errors="ignore")
        for pattern in LOCAL_PATH_PATTERNS:
            if pattern in text:
                raise AssertionError(f"local path leakage in {rel}: {pattern}")


def _audit_artifacts() -> None:
    forbidden: list[str] = []
    for rel in _tracked_files():
        if rel == REFERENCE_PATH.as_posix() or _is_reference_child(rel):
            continue
        path = Path(rel)
        if path.name in FORBIDDEN_ARTIFACT_NAMES or path.suffix.lower() in FORBIDDEN_ARTIFACT_SUFFIXES:
            forbidden.append(rel)
    if forbidden:
        raise AssertionError(f"forbidden tracked artifacts: {forbidden}")


def main() -> int:
    _audit_docs()
    submodule_ok = _audit_submodule()
    if not submodule_ok and not (ROOT / "docs/source_audit/final_v23_reference_import_blocked.md").exists():
        raise AssertionError("submodule import failed but blocked-import doc is missing")
    _audit_tracked_text()
    _audit_artifacts()
    print("passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
