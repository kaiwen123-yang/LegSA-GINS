#!/usr/bin/env python3
"""Audit N4H4A LegSA-v23-core framework foundation boundaries.

中文说明：本 audit 只确认 C++ 框架、函数骨架、中文注释和 forbidden flags；
它不能被解释为完整 EKF 数学闭合或 final_v23 parity 证据。
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
TOY_OUTPUT_DIR = Path("/tmp/legsa_n4h4a_audit_toy")

REQUIRED_DIRS = [
    "cpp/legsa_v23_core",
    "cpp/legsa_v23_core/include/legsa_v23_core/common",
    "cpp/legsa_v23_core/include/legsa_v23_core/config",
    "cpp/legsa_v23_core/include/legsa_v23_core/io",
    "cpp/legsa_v23_core/include/legsa_v23_core/state",
    "cpp/legsa_v23_core/include/legsa_v23_core/mechanization",
    "cpp/legsa_v23_core/include/legsa_v23_core/filter",
    "cpp/legsa_v23_core/include/legsa_v23_core/updates",
    "cpp/legsa_v23_core/include/legsa_v23_core/runtime",
    "cpp/legsa_v23_core/include/legsa_v23_core/writers",
    "cpp/legsa_v23_core/src/common",
    "cpp/legsa_v23_core/src/config",
    "cpp/legsa_v23_core/src/io",
    "cpp/legsa_v23_core/src/state",
    "cpp/legsa_v23_core/src/mechanization",
    "cpp/legsa_v23_core/src/filter",
    "cpp/legsa_v23_core/src/updates",
    "cpp/legsa_v23_core/src/runtime",
    "cpp/legsa_v23_core/src/writers",
    "cpp/legsa_v23_core/tests",
]

REQUIRED_FILES = [
    "cpp/legsa_v23_core/include/legsa_v23_core/common/constants.hpp",
    "cpp/legsa_v23_core/include/legsa_v23_core/common/time_status.hpp",
    "cpp/legsa_v23_core/include/legsa_v23_core/common/math_types.hpp",
    "cpp/legsa_v23_core/include/legsa_v23_core/state/imu_types.hpp",
    "cpp/legsa_v23_core/include/legsa_v23_core/state/gnss_types.hpp",
    "cpp/legsa_v23_core/include/legsa_v23_core/state/nav_state.hpp",
    "cpp/legsa_v23_core/include/legsa_v23_core/state/filter_state.hpp",
    "cpp/legsa_v23_core/include/legsa_v23_core/config/gins_options.hpp",
    "cpp/legsa_v23_core/include/legsa_v23_core/config/config_loader.hpp",
    "cpp/legsa_v23_core/src/config/config_loader.cpp",
    "cpp/legsa_v23_core/include/legsa_v23_core/io/imu_file_loader.hpp",
    "cpp/legsa_v23_core/src/io/imu_file_loader.cpp",
    "cpp/legsa_v23_core/include/legsa_v23_core/io/gnss_file_loader.hpp",
    "cpp/legsa_v23_core/src/io/gnss_file_loader.cpp",
    "cpp/legsa_v23_core/include/legsa_v23_core/runtime/legsa_v23_engine.hpp",
    "cpp/legsa_v23_core/src/runtime/legsa_v23_engine.cpp",
    "cpp/legsa_v23_core/include/legsa_v23_core/runtime/legsa_v23_runtime.hpp",
    "cpp/legsa_v23_core/src/runtime/legsa_v23_runtime.cpp",
    "cpp/legsa_v23_core/include/legsa_v23_core/writers/nav_writer.hpp",
    "cpp/legsa_v23_core/src/writers/nav_writer.cpp",
    "cpp/legsa_v23_core/include/legsa_v23_core/writers/std_writer.hpp",
    "cpp/legsa_v23_core/src/writers/std_writer.cpp",
    "cpp/legsa_v23_core/include/legsa_v23_core/writers/eval_nav_writer.hpp",
    "cpp/legsa_v23_core/src/writers/eval_nav_writer.cpp",
    "cpp/legsa_v23_core/include/legsa_v23_core/writers/run_manifest_writer.hpp",
    "cpp/legsa_v23_core/src/writers/run_manifest_writer.cpp",
    "cpp/legsa_v23_core/src/legsa_v23_core_demo.cpp",
]

REQUIRED_FUNCTIONS = [
    "LegSAV23Engine",
    "initialize",
    "addImuData",
    "addGnssData",
    "newImuProcess",
    "timestamp",
    "getNavState",
    "getFilterState",
    "isToUpdate",
    "imuInterpolate",
    "imuCompensate",
    "insPropagation",
    "buildFGPhiQd",
    "EKFPredict",
    "gnssUpdate",
    "gnssPositionUpdate",
    "gnssVelocityUpdate",
    "gnssYawUpdate",
    "EKFUpdate",
    "stateFeedback",
    "checkCov",
]

FORBIDDEN_MANIFEST_FLAGS = [
    "final_v23_reference_used_as_solver_input",
    "proposed_reads_final_v23_output",
    "trace_solver_input",
    "raw_doppler",
    "go2_prior",
    "lsim_oim",
    "fgo",
    "fgo_feedback",
    "output_only_correction",
    "bad_epoch_deletion_for_metric",
    "numerical_performance_claim",
    "final_v23_output_substitution",
]

RAW_ARTIFACT_PATTERN = re.compile(
    r"(input\.gnss|\.imu$|KF_GINS_Navresult\.nav|KF_GINS_STD\.txt|summary\.json|"
    r"error_series\.csv|\.png$|\.pdf$|\.svg$)"
)


def _read(path: str) -> str:
    return (REPO_ROOT / path).read_text(encoding="utf-8")


def _run(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=REPO_ROOT, check=False, capture_output=True, text=True)


def _fail(message: str, details: list[str] | None = None) -> int:
    print(f"N4H4A audit failed: {message}")
    for item in details or []:
        print(f"- {item}")
    return 1


def _check_required_paths() -> int:
    missing_dirs = [path for path in REQUIRED_DIRS if not (REPO_ROOT / path).is_dir()]
    if missing_dirs:
        return _fail("missing required directories", missing_dirs)
    missing_files = [path for path in REQUIRED_FILES if not (REPO_ROOT / path).is_file()]
    if missing_files:
        return _fail("missing required files", missing_files)
    return 0


def _check_functions_and_comments() -> int:
    text = _read("cpp/legsa_v23_core/src/runtime/legsa_v23_engine.cpp")
    missing = [name for name in REQUIRED_FUNCTIONS if name not in text]
    if missing:
        return _fail("missing required engine function names", missing)

    missing_comments: list[str] = []
    for name in REQUIRED_FUNCTIONS:
        definition_name = "LegSAV23Engine::LegSAV23Engine" if name == "LegSAV23Engine" else f"LegSAV23Engine::{name}"
        match = re.search(re.escape(definition_name), text)
        if not match:
            continue
        nearby = text[max(0, match.start() - 220) : match.start()]
        if "中文说明" not in nearby:
            missing_comments.append(name)
    if missing_comments:
        return _fail("missing Chinese comments near key functions", missing_comments)
    return 0


def _check_cmake_boundary() -> int:
    cmake = _read("cpp/CMakeLists.txt")
    required = ["add_library(legsa_v23_core", "add_executable(legsa_v23_core_demo"]
    missing = [item for item in required if item not in cmake]
    if missing:
        return _fail("missing CMake targets", missing)
    forbidden_patterns = [
        r"target_include_directories\([^)]*final_v23_repo",
        r"target_sources\([^)]*final_v23_repo",
        r"file\(GLOB[^)]*final_v23_repo",
        r"reference/final_v23_repo/.+\.cpp",
    ]
    hits = [pattern for pattern in forbidden_patterns if re.search(pattern, cmake, flags=re.DOTALL)]
    if hits:
        return _fail("reference/final_v23_repo appears in compile/include paths", hits)
    return 0


def _check_no_raw_artifacts() -> int:
    result = _run(["git", "ls-files"])
    if result.returncode != 0:
        return _fail("git ls-files failed", [result.stderr])
    hits = [line for line in result.stdout.splitlines() if RAW_ARTIFACT_PATTERN.search(line)]
    if hits:
        return _fail("tracked raw/generated artifacts detected", hits)
    return 0


def _check_no_forbidden_claims() -> int:
    text_chunks: list[str] = []
    scoped_paths = [
        REPO_ROOT / "README.md",
        REPO_ROOT / "PLANS.md",
        REPO_ROOT / "PHASE_LOG.md",
        REPO_ROOT / "CLAIM_BOUNDARY.md",
        REPO_ROOT / "docs/experiments/n4h4a_legsa_v23_core_foundation.md",
        REPO_ROOT / "docs/experiments/n4h4a_cpp_module_map.md",
        REPO_ROOT / "docs/experiments/n4h4a_function_contract.md",
        REPO_ROOT / "docs/codex_prompts/N4H4A_legsa_v23_core_foundation.md",
    ]
    scoped_paths.extend(path for path in (REPO_ROOT / "cpp/legsa_v23_core").rglob("*") if path.is_file())
    for path in scoped_paths:
        if path.suffix in {".md", ".cpp", ".hpp", ".txt", ".yaml", ".json"}:
            text_chunks.append(path.read_text(encoding="utf-8", errors="ignore"))
    text = "\n".join(text_chunks).replace('\\"', '"')
    forbidden_true = [
        flag
        for flag in FORBIDDEN_MANIFEST_FLAGS
        if re.search(rf'["\']?{re.escape(flag)}["\']?\s*[:=]\s*true\b', text, flags=re.IGNORECASE)
    ]
    if forbidden_true:
        return _fail("forbidden flags enabled in tracked text", forbidden_true)
    unsupported_claims = [
        "N4H4A reproduces final_v23",
        "N4H4A final_v23 parity passed",
        "N4H4A performance improvement",
        "LegSA-v23-core outperforms final_v23",
    ]
    hits = [item for item in unsupported_claims if item in text]
    if hits:
        return _fail("unsupported performance/parity claim text detected", hits)
    return 0


def _build_and_run_toy() -> tuple[int, dict[str, object] | None]:
    configure = _run(["cmake", "-S", "cpp", "-B", "build/cpp"])
    if configure.returncode != 0:
        return _fail("cmake configure failed", [configure.stdout, configure.stderr]), None
    build = _run(["cmake", "--build", "build/cpp"])
    if build.returncode != 0:
        return _fail("cmake build failed", [build.stdout, build.stderr]), None

    if TOY_OUTPUT_DIR.exists():
        shutil.rmtree(TOY_OUTPUT_DIR)
    TOY_OUTPUT_DIR.mkdir(parents=True)
    demo = _run([
        str(REPO_ROOT / "build/cpp/legsa_v23_core_demo"),
        "--dry-run-toy",
        "--output-dir",
        str(TOY_OUTPUT_DIR),
    ])
    if demo.returncode != 0:
        return _fail("toy demo failed", [demo.stdout, demo.stderr]), None

    required_outputs = [
        "LegSA_V23_NAV.nav",
        "LegSA_V23_STD.csv",
        "EVAL_NAV.csv",
        "RUN_MANIFEST.json",
    ]
    missing = [name for name in required_outputs if not (TOY_OUTPUT_DIR / name).is_file()]
    if missing:
        return _fail("toy demo missing outputs", missing), None
    manifest = json.loads((TOY_OUTPUT_DIR / "RUN_MANIFEST.json").read_text(encoding="utf-8"))
    return 0, manifest


def _check_manifest(manifest: dict[str, object]) -> int:
    if manifest.get("phase") != "N4H4A":
        return _fail("manifest phase mismatch", [str(manifest.get("phase"))])
    if manifest.get("solver_role") != "legsa_v23_core_skeleton":
        return _fail("manifest solver_role mismatch", [str(manifest.get("solver_role"))])
    enabled = [flag for flag in FORBIDDEN_MANIFEST_FLAGS if manifest.get(flag) is not False]
    if enabled:
        return _fail("manifest forbidden flags are not false", enabled)
    return 0


def main() -> int:
    for check in [
        _check_required_paths,
        _check_functions_and_comments,
        _check_cmake_boundary,
        _check_no_raw_artifacts,
        _check_no_forbidden_claims,
    ]:
        result = check()
        if result != 0:
            return result

    result, manifest = _build_and_run_toy()
    if result != 0 or manifest is None:
        return result
    manifest_result = _check_manifest(manifest)
    if manifest_result != 0:
        return manifest_result

    print("N4H4A LegSA-v23-core foundation audit passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
