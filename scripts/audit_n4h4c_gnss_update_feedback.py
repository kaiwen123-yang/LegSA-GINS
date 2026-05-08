#!/usr/bin/env python3
"""Audit N4H4C GNSS update, EKFUpdate, and stateFeedback boundary.

中文说明：本脚本确认 LegSA-v23-core 已打通量测更新闭环，同时保持
raw Doppler/Go2/LSIM-OIM/FGO/final_v23 输出替代和性能声明全部禁用。
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
TOY_OUTPUT_DIR = Path("/tmp/legsa_n4h4c_audit_update_toy")

REQUIRED_FILES = [
    "cpp/legsa_v23_core/include/legsa_v23_core/updates/measurement_update.hpp",
    "cpp/legsa_v23_core/src/updates/measurement_update.cpp",
    "cpp/legsa_v23_core/include/legsa_v23_core/updates/yaw_scheme_c.hpp",
    "cpp/legsa_v23_core/src/updates/yaw_scheme_c.cpp",
    "cpp/legsa_v23_core/include/legsa_v23_core/filter/ekf_update.hpp",
    "cpp/legsa_v23_core/src/filter/ekf_update.cpp",
    "cpp/legsa_v23_core/include/legsa_v23_core/filter/state_feedback.hpp",
    "cpp/legsa_v23_core/src/filter/state_feedback.cpp",
    "cpp/legsa_v23_core/include/legsa_v23_core/runtime/legsa_v23_engine.hpp",
    "cpp/legsa_v23_core/src/runtime/legsa_v23_engine.cpp",
]

KEY_FUNCTIONS = [
    "buildGnssPositionMeasurement",
    "buildGnssVelocityMeasurement",
    "buildGnssYawMeasurement",
    "applyYawSchemeC",
    "EKFUpdate",
    "stateFeedback",
    "gnssUpdate",
    "gnssPositionUpdate",
    "gnssVelocityUpdate",
    "gnssYawUpdate",
    "newImuProcess",
]

MANIFEST_TRUE_FLAGS = [
    "measurement_update_implemented",
    "state_feedback_implemented",
    "position_update_implemented",
    "velocity_update_implemented",
    "yaw_update_implemented",
]

MANIFEST_FALSE_FLAGS = [
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
    print(f"N4H4C audit failed: {message}")
    for item in details or []:
        print(f"- {item}")
    return 1


def _check_required_files() -> int:
    missing = [path for path in REQUIRED_FILES if not (REPO_ROOT / path).is_file()]
    if missing:
        return _fail("missing required N4H4C files", missing)
    return 0


def _check_key_functions_and_comments() -> int:
    text = "\n".join(_read(path) for path in REQUIRED_FILES)
    missing = [name for name in KEY_FUNCTIONS if name not in text]
    if missing:
        return _fail("missing key function names", missing)

    missing_comments = []
    for name in KEY_FUNCTIONS:
        match = re.search(re.escape(name), text)
        if not match:
            continue
        nearby = text[max(0, match.start() - 320) : match.start()]
        if "中文说明" not in nearby:
            missing_comments.append(name)
    if missing_comments:
        return _fail("missing Chinese comments near key functions", missing_comments)
    return 0


def _check_model_text() -> int:
    measurement = _read("cpp/legsa_v23_core/src/updates/measurement_update.cpp")
    required_measurement = [
        "antenna_blh",
        "Earth::DRi",
        "Earth::DR",
        "P_ID",
        "PHI_ID",
        "V_ID",
        "gnss.yaw_deg - pred_yaw_deg",
        "PHI_ID + 2",
        "raw Doppler",
    ]
    missing = [item for item in required_measurement if item not in measurement]
    if missing:
        return _fail("measurement model text missing required evidence", missing)

    ekf = _read("cpp/legsa_v23_core/src/filter/ekf_update.cpp")
    if "Joseph form" not in ekf or "I_minus_KH" not in ekf or "innovation[row] = meas.residual[row] - predicted" not in ekf:
        return _fail("EKFUpdate Joseph-form evidence missing")

    feedback = _read("cpp/legsa_v23_core/src/filter/state_feedback.cpp")
    required_feedback = ["-=", "+=", "Rotation::multiply(qpn, qbn)", "state.dx = zeroVector21()"]
    missing_feedback = [item for item in required_feedback if item not in feedback]
    if missing_feedback:
        return _fail("stateFeedback sign/reset evidence missing", missing_feedback)
    return 0


def _check_engine_update_path() -> int:
    engine = _read("cpp/legsa_v23_core/src/runtime/legsa_v23_engine.cpp")
    required = [
        "runUpdateAndFeedback",
        "update_status == 1",
        "update_status == 2",
        "update_status == 3",
        "buildGnssPositionMeasurement",
        "buildGnssVelocityMeasurement",
        "buildGnssYawMeasurement",
        "legsa_v23_core::EKFUpdate",
        "legsa_v23_core::stateFeedback",
    ]
    missing = [item for item in required if item not in engine]
    if missing:
        return _fail("engine update path missing required evidence", missing)
    return 0


def _check_cmake_reference_boundary() -> int:
    cmake = _read("cpp/CMakeLists.txt")
    if "legsa_v23_core" not in cmake or "legsa_v23_core_demo" not in cmake:
        return _fail("missing v23-core CMake targets")
    forbidden = [
        r"target_include_directories\([^)]*final_v23_repo",
        r"target_sources\([^)]*final_v23_repo",
        r"file\(GLOB[^)]*final_v23_repo",
        r"reference/final_v23_repo/.+\.cpp",
    ]
    hits = [pattern for pattern in forbidden if re.search(pattern, cmake, flags=re.DOTALL)]
    if hits:
        return _fail("reference/final_v23_repo appears in compile/include paths", hits)
    return 0


def _check_no_artifacts() -> int:
    result = _run(["git", "ls-files"])
    if result.returncode != 0:
        return _fail("git ls-files failed", [result.stderr])
    hits = [line for line in result.stdout.splitlines() if RAW_ARTIFACT_PATTERN.search(line)]
    if hits:
        return _fail("tracked raw/generated artifacts detected", hits)
    return 0


def _build_and_run_toy() -> tuple[int, dict[str, object] | None]:
    for command in [["cmake", "-S", "cpp", "-B", "build/cpp"], ["cmake", "--build", "build/cpp"]]:
        completed = _run(command)
        if completed.returncode != 0:
            return _fail("CMake command failed", [completed.stdout, completed.stderr]), None

    if TOY_OUTPUT_DIR.exists():
        shutil.rmtree(TOY_OUTPUT_DIR)
    TOY_OUTPUT_DIR.mkdir(parents=True)
    demo = _run([
        str(REPO_ROOT / "build/cpp/legsa_v23_core_demo"),
        "--dry-run-update-toy",
        "--output-dir",
        str(TOY_OUTPUT_DIR),
    ])
    if demo.returncode != 0:
        return _fail("dry-run-update-toy failed", [demo.stdout, demo.stderr]), None

    missing = [
        name
        for name in ["LegSA_V23_NAV.nav", "LegSA_V23_STD.csv", "EVAL_NAV.csv", "RUN_MANIFEST.json"]
        if not (TOY_OUTPUT_DIR / name).is_file()
    ]
    if missing:
        return _fail("toy update output missing", missing), None
    manifest = json.loads((TOY_OUTPUT_DIR / "RUN_MANIFEST.json").read_text(encoding="utf-8"))
    return 0, manifest


def _check_manifest(manifest: dict[str, object]) -> int:
    missing_true = [key for key in MANIFEST_TRUE_FLAGS if manifest.get(key) is not True]
    if missing_true:
        return _fail("manifest true flags are not true", missing_true)
    bad_false = [key for key in MANIFEST_FALSE_FLAGS if manifest.get(key) is not False]
    if bad_false:
        return _fail("manifest forbidden flags are not false", bad_false)
    if manifest.get("yaw_normal_count") != 1 or manifest.get("yaw_downweight_count") != 1 or manifest.get("yaw_reject_count") != 1:
        return _fail("manifest yaw mode counts are unexpected", [json.dumps(manifest, indent=2)])
    return 0


def main() -> int:
    checks = [
        _check_required_files,
        _check_key_functions_and_comments,
        _check_model_text,
        _check_engine_update_path,
        _check_cmake_reference_boundary,
        _check_no_artifacts,
    ]
    for check in checks:
        result = check()
        if result:
            return result
    result, manifest = _build_and_run_toy()
    if result:
        return result
    assert manifest is not None
    result = _check_manifest(manifest)
    if result:
        return result
    print("N4H4C GNSS update EKF feedback audit passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
