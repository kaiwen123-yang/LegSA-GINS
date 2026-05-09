#!/usr/bin/env python3
"""Audit N4H4R1 source-backed port-core foundation.

中文说明：检查 port-core 目录、provenance header、toy demo 和 manifest 边界；
不运行真实 clean replay，不编译 reference/final_v23_repo。
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PORT_ROOT = ROOT / "cpp/legsa_v23_port_core"
TOY_DIR = Path("/tmp/legsa_n4h4r1_audit_toy")
HEADER = "LegSA-GINS source-backed port file."
CHINESE_RE = re.compile(r"[\u4e00-\u9fff]")
FORBIDDEN_FLAGS = [
    "final_v23_output_solver_input",
    "trace_solver_input",
    "output_only_correction",
    "bad_epoch_deletion_for_metric",
    "raw_doppler",
    "go2_prior",
    "lsim_oim",
    "fgo",
    "performance_claim",
]
REQUIRED_FILES = [
    "PORT_PROVENANCE.md",
    "PORT_MANIFEST.json",
    "README.md",
    "include/legsa_v23_port_core/common/earth.hpp",
    "include/legsa_v23_port_core/common/rotation.hpp",
    "include/legsa_v23_port_core/options.hpp",
    "include/legsa_v23_port_core/imu.hpp",
    "include/legsa_v23_port_core/gnss.hpp",
    "include/legsa_v23_port_core/nav_state.hpp",
    "include/legsa_v23_port_core/fileio/imu_file_loader.hpp",
    "include/legsa_v23_port_core/fileio/gnss_file_loader.hpp",
    "include/legsa_v23_port_core/fileio/file_saver.hpp",
    "include/legsa_v23_port_core/config/port_config_loader.hpp",
    "include/legsa_v23_port_core/kf_gins/insmech.hpp",
    "include/legsa_v23_port_core/kf_gins/gi_engine.hpp",
    "include/legsa_v23_port_core/runtime/port_runtime.hpp",
    "src/demo/port_demo.cpp",
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


def _run(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=ROOT, check=False, capture_output=True, text=True)


def _fail(message: str, details: list[str] | None = None) -> int:
    print(f"N4H4R1 source-backed port-core audit failed: {message}")
    for detail in details or []:
        print(f"- {detail}")
    return 1


def _tracked_files() -> list[str]:
    result = _run(["git", "ls-files"])
    if result.returncode != 0:
        raise RuntimeError(result.stderr)
    return [line for line in result.stdout.splitlines() if line.strip()]


def _check_required_files() -> int:
    if not PORT_ROOT.exists():
        return _fail("cpp/legsa_v23_port_core missing")
    missing = [rel for rel in REQUIRED_FILES if not (PORT_ROOT / rel).exists()]
    if missing:
        return _fail("missing required port-core files", missing)
    return 0


def _check_headers_and_comments() -> int:
    port_files = [
        path
        for path in PORT_ROOT.rglob("*")
        if path.suffix in {".cpp", ".hpp", ".h"} and path.is_file()
    ]
    missing_header: list[str] = []
    missing_chinese: list[str] = []
    for path in port_files:
        text = path.read_text(encoding="utf-8", errors="ignore")
        if HEADER not in text[:500]:
            missing_header.append(str(path.relative_to(ROOT)))
        if not CHINESE_RE.search(text):
            missing_chinese.append(str(path.relative_to(ROOT)))
    if missing_header:
        return _fail("missing provenance header", missing_header)
    if missing_chinese:
        return _fail("missing Chinese comments", missing_chinese)
    return 0


def _check_cmake() -> int:
    text = (ROOT / "cpp/CMakeLists.txt").read_text(encoding="utf-8")
    required = ["legsa_v23_port_core", "legsa_v23_port_core_demo", "legsa_v23_port_core/src/*.cpp"]
    missing = [term for term in required if term not in text]
    if missing:
        return _fail("missing CMake target terms", missing)
    forbidden = ["reference/final_v23_repo/src", "reference/final_v23_repo/*.cpp"]
    hits = [term for term in forbidden if term in text]
    if hits:
        return _fail("reference source appears in CMake compile path", hits)
    return 0


def _run_demo_and_check_manifest() -> int:
    shutil.rmtree(TOY_DIR, ignore_errors=True)
    for command in [
        ["cmake", "-S", "cpp", "-B", "build/cpp"],
        ["cmake", "--build", "build/cpp"],
        ["./build/cpp/legsa_v23_port_core_demo", "--dry-run-toy", "--output-dir", str(TOY_DIR)],
    ]:
        result = _run(command)
        if result.returncode != 0:
            return _fail("command failed", [" ".join(command), result.stdout, result.stderr])
    required_outputs = [
        "LegSA_PORT_NAV.nav",
        "LegSA_PORT_STD.csv",
        "EVAL_NAV.csv",
        "RUN_MANIFEST.json",
    ]
    missing = [name for name in required_outputs if not (TOY_DIR / name).exists()]
    if missing:
        return _fail("toy outputs missing", missing)
    manifest = json.loads((TOY_DIR / "RUN_MANIFEST.json").read_text(encoding="utf-8"))
    bad_flags = [flag for flag in FORBIDDEN_FLAGS if manifest.get(flag) is not False]
    if bad_flags:
        return _fail("forbidden manifest flags are not false", bad_flags)
    if manifest.get("parity_attempted") is not False:
        return _fail("parity_attempted must be false")
    return 0


def _check_no_artifacts_or_paths() -> int:
    hits: list[str] = []
    artifact_hits: list[str] = []
    for rel in _tracked_files():
        if rel == "reference/final_v23_repo" or rel.startswith("reference/final_v23_repo/"):
            continue
        if ARTIFACT_RE.search(rel):
            artifact_hits.append(rel)
        path = ROOT / rel
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for pattern in LOCAL_PATH_PATTERNS:
            if pattern in text:
                hits.append(f"{rel}: {pattern}")
    if artifact_hits:
        return _fail("tracked raw/results artifacts detected", artifact_hits)
    if hits:
        return _fail("local path leakage detected", hits)
    return 0


def main() -> int:
    checks = [
        _check_required_files,
        _check_headers_and_comments,
        _check_cmake,
        _run_demo_and_check_manifest,
        _check_no_artifacts_or_paths,
    ]
    for check in checks:
        result = check()
        if result:
            return result
    print("N4H4R1 source-backed port-core audit passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

