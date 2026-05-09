#!/usr/bin/env python3
"""Audit N4H4R2 source-backed mathematical port.

中文说明：检查 R2 port-core 数学链路、边界旗标、synthetic smoke 和禁止项；
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
TOY_DIR = Path("/tmp/legsa_n4h4r2_audit_synthetic_math")
HEADER = "LegSA-GINS source-backed port file."
CHINESE_RE = re.compile(r"[\u4e00-\u9fff]")
FORBIDDEN_FLAGS = [
    "final_v23_output_solver_input",
    "trace_solver_input",
    "output_only_correction",
    "raw_doppler",
    "go2_prior",
    "lsim_oim",
    "fgo",
    "performance_claim",
]
REQUIRED_FILES = [
    "include/legsa_v23_port_core/common/earth.hpp",
    "src/common/earth.cpp",
    "include/legsa_v23_port_core/common/rotation.hpp",
    "src/common/rotation.cpp",
    "include/legsa_v23_port_core/types.hpp",
    "include/legsa_v23_port_core/options.hpp",
    "include/legsa_v23_port_core/fileio/imu_file_loader.hpp",
    "src/fileio/imu_file_loader.cpp",
    "include/legsa_v23_port_core/fileio/gnss_file_loader.hpp",
    "src/fileio/gnss_file_loader.cpp",
    "include/legsa_v23_port_core/fileio/file_saver.hpp",
    "src/fileio/file_saver.cpp",
    "include/legsa_v23_port_core/writers/port_writers.hpp",
    "src/writers/port_writers.cpp",
    "include/legsa_v23_port_core/kf_gins/insmech.hpp",
    "src/kf_gins/insmech.cpp",
    "include/legsa_v23_port_core/kf_gins/gi_engine.hpp",
    "src/kf_gins/gi_engine.cpp",
    "include/legsa_v23_port_core/runtime/port_runtime.hpp",
    "src/runtime/port_runtime.cpp",
    "src/demo/port_demo.cpp",
    "PORT_MANIFEST.json",
    "PORT_PROVENANCE.md",
]
REQUIRED_FUNCTIONS = [
    "gravity",
    "meridianPrimeVerticalRadius",
    "DRi",
    "DR",
    "matrix2euler",
    "rotvec2quaternion",
    "insMech",
    "velUpdate",
    "posUpdate",
    "attUpdate",
    "newImuProcess",
    "imuInterpolate",
    "imuCompensate",
    "insPropagation",
    "gnssUpdate",
    "EKFPredict",
    "EKFUpdate",
    "stateFeedback",
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
    print(f"N4H4R2 source-backed math port audit failed: {message}")
    for detail in details or []:
        print(f"- {detail}")
    return 1


def _tracked_files() -> list[str]:
    result = _run(["git", "ls-files"])
    if result.returncode != 0:
        raise RuntimeError(result.stderr)
    return [line for line in result.stdout.splitlines() if line.strip()]


def _check_required_files_and_functions() -> int:
    missing = [rel for rel in REQUIRED_FILES if not (PORT_ROOT / rel).exists()]
    if missing:
        return _fail("missing required files", missing)
    joined = "\n".join(
        path.read_text(encoding="utf-8", errors="ignore")
        for path in PORT_ROOT.rglob("*")
        if path.suffix in {".cpp", ".hpp", ".h"}
    )
    missing_functions = [name for name in REQUIRED_FUNCTIONS if name not in joined]
    if missing_functions:
        return _fail("missing required function names", missing_functions)
    if "TODO_R2_SOURCE_PORT" in joined:
        return _fail("TODO_R2_SOURCE_PORT remains")
    return 0


def _check_headers_and_comments() -> int:
    missing_header: list[str] = []
    missing_chinese: list[str] = []
    for path in PORT_ROOT.rglob("*"):
        if path.suffix not in {".cpp", ".hpp", ".h"} or not path.is_file():
            continue
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
    for term in ["legsa_v23_port_core", "legsa_v23_port_core_demo"]:
        if term not in text:
            return _fail("missing CMake target", [term])
    if "reference/final_v23_repo/src" in text:
        return _fail("reference/final_v23_repo appears in CMake compile path")
    return 0


def _run_synthetic_and_check_manifest() -> int:
    shutil.rmtree(TOY_DIR, ignore_errors=True)
    commands = [
        ["cmake", "-S", "cpp", "-B", "build/cpp"],
        ["cmake", "--build", "build/cpp"],
        ["./build/cpp/legsa_v23_port_core_demo", "--dry-run-synthetic-math", "--output-dir", str(TOY_DIR)],
    ]
    for command in commands:
        result = _run(command)
        if result.returncode != 0:
            return _fail("command failed", [" ".join(command), result.stdout, result.stderr])
    for name in ["LegSA_PORT_NAV.nav", "LegSA_PORT_STD.csv", "EVAL_NAV.csv", "RUN_MANIFEST.json"]:
        if not (TOY_DIR / name).exists():
            return _fail("synthetic output missing", [name])
    manifest = json.loads((TOY_DIR / "RUN_MANIFEST.json").read_text(encoding="utf-8"))
    if manifest.get("phase") != "N4H4R2":
        return _fail("manifest phase mismatch", [str(manifest.get("phase"))])
    if manifest.get("parity_attempted") is not False:
        return _fail("parity_attempted must be false")
    for flag in FORBIDDEN_FLAGS:
        if manifest.get(flag) is not False:
            return _fail("forbidden manifest flag is not false", [flag])
    return 0


def _check_manifest() -> int:
    manifest = json.loads((PORT_ROOT / "PORT_MANIFEST.json").read_text(encoding="utf-8"))
    required_false = ["parity_attempted", "real_clean_replay_attempted", *FORBIDDEN_FLAGS]
    if manifest.get("phase") != "N4H4R2":
        return _fail("PORT_MANIFEST phase mismatch")
    if manifest.get("math_port_completed") is not True:
        return _fail("math_port_completed must be true")
    bad = [flag for flag in required_false if manifest.get(flag) is not False]
    if bad:
        return _fail("PORT_MANIFEST forbidden flags are not false", bad)
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
    for check in [
        _check_required_files_and_functions,
        _check_headers_and_comments,
        _check_cmake,
        _check_manifest,
        _run_synthetic_and_check_manifest,
        _check_no_artifacts_or_paths,
    ]:
        result = check()
        if result:
            return result
    print("N4H4R2 source-backed math port audit passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
