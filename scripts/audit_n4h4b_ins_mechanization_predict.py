#!/usr/bin/env python3
"""Audit N4H4B INS mechanization and EKF predict boundaries.

中文说明：本脚本只确认预测传播基础和边界；它不验证 final_v23 parity，
也不允许把 N4H4B 写成量测更新或性能结论。
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
TOY_OUTPUT_DIR = Path("/tmp/legsa_n4h4b_audit_propagation_toy")

REQUIRED_FILES = [
    "cpp/legsa_v23_core/include/legsa_v23_core/common/earth.hpp",
    "cpp/legsa_v23_core/src/common/earth.cpp",
    "cpp/legsa_v23_core/include/legsa_v23_core/common/rotation.hpp",
    "cpp/legsa_v23_core/src/common/rotation.cpp",
    "cpp/legsa_v23_core/include/legsa_v23_core/mechanization/ins_mechanization.hpp",
    "cpp/legsa_v23_core/src/mechanization/ins_mechanization.cpp",
    "cpp/legsa_v23_core/include/legsa_v23_core/filter/error_state_matrices.hpp",
    "cpp/legsa_v23_core/src/filter/error_state_matrices.cpp",
    "cpp/legsa_v23_core/include/legsa_v23_core/filter/ekf_predictor.hpp",
    "cpp/legsa_v23_core/src/filter/ekf_predictor.cpp",
    "cpp/legsa_v23_core/include/legsa_v23_core/runtime/legsa_v23_engine.hpp",
    "cpp/legsa_v23_core/src/runtime/legsa_v23_engine.cpp",
]

KEY_FUNCTIONS = [
    "gravity",
    "meridianPrimeVerticalRadius",
    "DRi",
    "DR",
    "qne",
    "blh",
    "iewn",
    "enwn",
    "skewSymmetric",
    "rotvec2quaternion",
    "quaternion2matrix",
    "matrix2euler",
    "euler2matrix",
    "wrapAngleRad",
    "insMech",
    "velUpdate",
    "posUpdate",
    "attUpdate",
    "buildErrorStateMatrices",
    "EKFPredict",
    "imuCompensate",
    "insPropagation",
    "buildFGPhiQd",
    "checkCov",
]

FORBIDDEN_FLAGS = [
    "measurement_update_implemented",
    "state_feedback_implemented",
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
    print(f"N4H4B audit failed: {message}")
    for item in details or []:
        print(f"- {item}")
    return 1


def _check_required_files() -> int:
    missing = [path for path in REQUIRED_FILES if not (REPO_ROOT / path).is_file()]
    if missing:
        return _fail("missing required propagation files", missing)
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
        nearby = text[max(0, match.start() - 260) : match.start()]
        if "中文说明" not in nearby:
            missing_comments.append(name)
    if missing_comments:
        return _fail("missing Chinese comments near key functions", missing_comments)
    return 0


def _check_mechanization_order_and_matrices() -> int:
    mech = _read("cpp/legsa_v23_core/src/mechanization/ins_mechanization.cpp")
    order = [mech.find("velUpdate(pvapre"), mech.find("posUpdate(pvapre"), mech.find("attUpdate(pvapre")]
    if any(index < 0 for index in order) or order != sorted(order):
        return _fail("INS mechanization order is not velUpdate -> posUpdate -> attUpdate")

    matrices = _read("cpp/legsa_v23_core/src/filter/error_state_matrices.cpp")
    required_blocks = [
        "P/P",
        "P/V",
        "V/P",
        "V/V",
        "V/Phi",
        "V/BA",
        "V/SA",
        "Phi/P",
        "Phi/V",
        "Phi/Phi",
        "Phi/BG",
        "Phi/SG",
        "BG/BG",
        "BA/BA",
        "SG/SG",
        "SA/SA",
        "V/VRW",
        "Phi/ARW",
        "BG/BGSTD",
        "BA/BASTD",
        "SG/SGSTD",
        "SA/SASTD",
        "Phi = I + F * dt",
        "G*Qc*G^T",
    ]
    missing = [item for item in required_blocks if item not in matrices]
    if missing:
        return _fail("missing required F/G/Phi/Qd block comments or formulas", missing)
    return 0


def _check_engine_boundary() -> int:
    engine = _read("cpp/legsa_v23_core/src/runtime/legsa_v23_engine.cpp")
    required = [
        "INSMechanization::insMech",
        "buildErrorStateMatrices",
        "legsa_v23_core::EKFPredict",
        "TODO(N4H4C): GNSS position update not implemented in N4H4B",
        "TODO(N4H4C): GNSS velocity update not implemented in N4H4B",
        "TODO(N4H4C): GNSS yaw update not implemented in N4H4B",
        "TODO(N4H4C): EKF measurement update not implemented in N4H4B",
        "TODO(N4H4C): state feedback not implemented in N4H4B",
    ]
    missing = [item for item in required if item not in engine]
    if missing:
        return _fail("engine propagation path or N4H4C TODO boundary missing", missing)
    # 中文说明：N4H4C 之后 engine 源码中允许存在 active GNSS update 调用；
    # N4H4B 边界由 propagation toy manifest 的 measurement/state-feedback=false 来约束。
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
        "--dry-run-propagation-toy",
        "--output-dir",
        str(TOY_OUTPUT_DIR),
    ])
    if demo.returncode != 0:
        return _fail("dry-run-propagation-toy failed", [demo.stdout, demo.stderr]), None

    missing = [
        name
        for name in ["LegSA_V23_NAV.nav", "LegSA_V23_STD.csv", "EVAL_NAV.csv", "RUN_MANIFEST.json"]
        if not (TOY_OUTPUT_DIR / name).is_file()
    ]
    if missing:
        return _fail("toy propagation output missing", missing), None
    manifest = json.loads((TOY_OUTPUT_DIR / "RUN_MANIFEST.json").read_text(encoding="utf-8"))
    return 0, manifest


def _check_manifest(manifest: dict[str, object]) -> int:
    if manifest.get("phase") != "N4H4B":
        return _fail("manifest phase mismatch", [str(manifest.get("phase"))])
    if manifest.get("solver_role") != "legsa_v23_core_propagation_foundation":
        return _fail("manifest solver role mismatch", [str(manifest.get("solver_role"))])
    if manifest.get("mechanization_predict_implemented") is not True:
        return _fail("manifest does not mark propagation implementation true")
    enabled = [flag for flag in FORBIDDEN_FLAGS if manifest.get(flag) is not False]
    if enabled:
        return _fail("manifest forbidden flags are not false", enabled)
    return 0


def main() -> int:
    for check in [
        _check_required_files,
        _check_key_functions_and_comments,
        _check_mechanization_order_and_matrices,
        _check_engine_boundary,
        _check_cmake_reference_boundary,
        _check_no_artifacts,
    ]:
        result = check()
        if result != 0:
            return result

    result, manifest = _build_and_run_toy()
    if result != 0 or manifest is None:
        return result
    result = _check_manifest(manifest)
    if result != 0:
        return result

    print("N4H4B INS mechanization and EKF predict audit passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
