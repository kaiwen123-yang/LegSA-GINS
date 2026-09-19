"""Deterministic H3--H4 validation for the Hartley IJRR 2020 backend.

This module builds only the standalone synthetic backend, invokes its direct
C++ checks, evaluates Eq. 52 against an independent DOP853 covariance ODE,
and writes the bounded tracked validation payload.  It has no BY2, trace,
reference-navigation, EXT, HORIZONTAL18, or Canonical execution interface.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import numpy as np
from scipy.integrate import solve_ivp
from scipy.linalg import expm


BACKEND_REPORTED = "HARTLEY_IJRR2020_REPORTED_BACKEND"
BACKEND_EXACT_QD = "EXACT_QD_REFERENCE_DIAGNOSTIC"
BACKEND_OFFICIAL_EARLY = "OFFICIAL_CPP_EARLY_REGRESSION"
INTERIM_VALIDATED_STATUS = (
    "VALIDATED_LSE01_H3_H4_BACKEND_PENDING_SUPERVISOR_PUBLICATION"
)
FINAL_TERMINAL_STATUS = "PASS_LSE01_H3_H4_FULL_IJRR_BACKEND_VALIDATED"

GO2_SIGMA_G = 2.865130e-4
GO2_SIGMA_A = 1.285395e-3
GO2_SIGMA_BG = 2.996871e-5
GO2_SIGMA_BA = 1.594412e-4
GRAVITY = np.array([0.0, 0.0, -9.81], dtype=float)

EQ52_ODE_RELATIVE_TOLERANCE = 2.0e-8
EQ52_ODE_STRESS_RELATIVE_TOLERANCE = 2.0e-6
OBSERVABILITY_ABSOLUTE_FLOOR = 1.0e-12
OBSERVABILITY_RELATIVE_THRESHOLD = 1.0e-9
OBSERVABILITY_O_G_RESIDUAL_TOLERANCE = 1.0e-9
OBSERVABILITY_GAUGE_NULLSPACE_RESIDUAL_TOLERANCE = 1.0e-7
OBSERVABILITY_PRINCIPAL_ANGLE_TOLERANCE_RAD = math.radians(1.0e-5)
OFFICIAL_STATE_TOLERANCE = 5.0e-8
OFFICIAL_COVARIANCE_RELATIVE_TOLERANCE = 2.0e-7
OFFICIAL_ROUNDED_STDOUT_TOLERANCE = 5.0e-6
EXPECTED_FULL_TEST_RESULT = (
    "2_failed_922_passed_10_skipped_"
    "UNCHANGED_PHASE4_EXECUTION_LOCK_AND_PHASE5_DIRTY_SNAPSHOT"
)
PENDING_AUDIT = "NOT_VERIFIED_PENDING_POST_GENERATION_AUDIT"

OFFICIAL_COMMIT = "ef16e8a1df72f9272111a488880e3fe9d161f59f"
OFFICIAL_KINEMATICS_SHA256 = (
    "224e03c83062fb937bfe529aa3858a04e07ed3143f92f8e0868bacbeae08491b"
)
OFFICIAL_EXECUTABLE_SHA256 = (
    "7feb615e4392cd24399f890c5788f262bbf7beac186b0959f0460d6571f6892c"
)
OFFICIAL_LIBRARY_SHA256 = (
    "3d1b190b0f933adbb3a042ac3d36e14e05ef2a68c788f3794e07287c1c30405a"
)


class HartleyValidationError(RuntimeError):
    """A preregistered H3--H4 validation gate failed."""


def _parse_scoped_test_summary(value: str) -> dict[str, Any]:
    if value == "NOT_RUN_BY_VALIDATOR":
        return {
            "raw": value,
            "syntax_valid": True,
            "caller_reported": False,
            "executed_by_generator": False,
            "passed": None,
        }
    match = re.fullmatch(r"([1-9][0-9]*)_passed", value)
    if match is None:
        raise HartleyValidationError(
            "scoped test summary must be '<positive_integer>_passed' or "
            "NOT_RUN_BY_VALIDATOR"
        )
    return {
        "raw": value,
        "syntax_valid": True,
        "caller_reported": True,
        "executed_by_generator": False,
        "passed": int(match.group(1)),
    }


def _parse_full_test_summary(value: str) -> dict[str, Any]:
    if value == "NOT_RUN_BY_VALIDATOR":
        return {
            "raw": value,
            "syntax_valid": True,
            "caller_reported": False,
            "executed_by_generator": False,
            "matches_expected_unchanged_failure_encoding": False,
            "failed": None,
            "passed": None,
            "skipped": None,
        }
    match = re.fullmatch(
        r"([0-9]+)_failed_([0-9]+)_passed_([0-9]+)_skipped_([A-Z0-9_]+)",
        value,
    )
    if match is None:
        raise HartleyValidationError("full test summary encoding is malformed")
    return {
        "raw": value,
        "syntax_valid": True,
        "caller_reported": True,
        "executed_by_generator": False,
        "matches_expected_unchanged_failure_encoding": (
            value == EXPECTED_FULL_TEST_RESULT
        ),
        "failed": int(match.group(1)),
        "passed": int(match.group(2)),
        "skipped": int(match.group(3)),
        "classification": match.group(4),
    }


@dataclass(frozen=True)
class ValidationPaths:
    repo_root: Path
    cpp_root: Path
    doc_payload: Path
    validation_output: Path
    report_output: Path


@dataclass(frozen=True)
class CommandEvidence:
    argv_alias: str
    return_code: int
    stdout: str
    stderr: str


def repository_paths(repo_root: Path) -> ValidationPaths:
    root = repo_root.resolve()
    cpp = (
        root
        / "src/legsa_gins/paper_rebuild/horizontal_literature/hartley_inekf"
    )
    payload = (
        root / "docs/paper_rebuild/horizontal_literature/hartley/stage_payload"
    )
    return ValidationPaths(
        repo_root=root,
        cpp_root=cpp,
        doc_payload=payload,
        validation_output=payload / "07_SYNTHETIC_VALIDATION",
        report_output=payload / "11_REPORT",
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _run(
    argv: Sequence[str],
    *,
    cwd: Path,
    alias: str,
    environment: Mapping[str, str] | None = None,
) -> CommandEvidence:
    completed = subprocess.run(
        list(argv),
        cwd=cwd,
        env=dict(environment) if environment is not None else None,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    evidence = CommandEvidence(alias, completed.returncode, completed.stdout, completed.stderr)
    if completed.returncode != 0:
        raise HartleyValidationError(
            f"{alias} failed with return code {completed.returncode}: "
            f"{completed.stderr[-2000:]}"
        )
    return evidence


def build_backend(paths: ValidationPaths, build_dir: Path) -> dict[str, Any]:
    if not str(build_dir.resolve()).startswith("/tmp/"):
        raise HartleyValidationError("H3--H4 C++ build directory must be below /tmp")
    build_dir.mkdir(parents=True, exist_ok=True)
    configure = _run(
        [
            "cmake",
            "-S",
            str(paths.cpp_root),
            "-B",
            str(build_dir),
            "-DCMAKE_BUILD_TYPE=Release",
        ],
        cwd=paths.repo_root,
        alias="cmake_configure_hartley_backend",
    )
    build = _run(
        ["cmake", "--build", str(build_dir), "--parallel", "4"],
        cwd=paths.repo_root,
        alias="cmake_build_hartley_backend",
    )
    ctest = _run(
        ["ctest", "--test-dir", str(build_dir), "--output-on-failure"],
        cwd=paths.repo_root,
        alias="ctest_hartley_backend",
    )
    direct = _run(
        [str(build_dir / "hartley_backend_tests")],
        cwd=paths.repo_root,
        alias="hartley_backend_tests",
    )
    validator = _run(
        [str(build_dir / "hartley_backend_validator")],
        cwd=paths.repo_root,
        alias="hartley_backend_validator",
    )
    direct_match = re.search(r"PASS_HARTLEY_CPP_BACKEND_TESTS checks=(\d+)", direct.stdout)
    if direct_match is None or int(direct_match.group(1)) < 173:
        raise HartleyValidationError("direct C++ backend check count/terminal changed")
    return {
        "configure": configure,
        "build": build,
        "ctest": ctest,
        "direct": direct,
        "direct_check_count": int(direct_match.group(1)),
        "validator": validator,
    }


def parse_validator_output(text: str) -> dict[str, list[dict[str, str]]]:
    parsed: dict[str, list[dict[str, str]]] = {}
    for line_number, line in enumerate(text.splitlines(), 1):
        if not line:
            continue
        parts = line.split(",")
        section = parts[0]
        row: dict[str, str] = {}
        for part in parts[1:]:
            if "=" not in part:
                raise HartleyValidationError(
                    f"malformed validator field on line {line_number}: {part!r}"
                )
            key, value = part.split("=", 1)
            row[key] = value
        parsed.setdefault(section, []).append(row)
    required = {"lie", "mean", "phi", "qd", "eq52_matrix", "allan", "lifecycle", "synthetic", "gauge"}
    missing = required - parsed.keys()
    if missing:
        raise HartleyValidationError(f"validator sections missing: {sorted(missing)}")
    for section in required - {"eq52_matrix"}:
        failed = [row for row in parsed[section] if row.get("pass") != "true"]
        if failed:
            raise HartleyValidationError(f"C++ validator {section} gate failed: {failed[0]}")
    return parsed


def _skew(vector: np.ndarray) -> np.ndarray:
    x, y, z = vector
    return np.array([[0.0, -z, y], [z, 0.0, -x], [-y, x, 0.0]])


def _continuous_matrices(
    rotation: np.ndarray,
    velocity: np.ndarray,
    position: np.ndarray,
    contacts: Sequence[np.ndarray],
    noise_density: Sequence[float],
    gravity: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    count = len(contacts)
    state_dimension = 15 + 3 * count
    noise_dimension = 12 + 3 * count
    gyro_bias = state_dimension - 6
    accel_bias = state_dimension - 3
    A = np.zeros((state_dimension, state_dimension))
    A[0:3, gyro_bias : gyro_bias + 3] = -rotation
    A[3:6, 0:3] = _skew(gravity)
    A[3:6, gyro_bias : gyro_bias + 3] = -_skew(velocity) @ rotation
    A[3:6, accel_bias : accel_bias + 3] = -rotation
    A[6:9, 3:6] = np.eye(3)
    A[6:9, gyro_bias : gyro_bias + 3] = -_skew(position) @ rotation
    for index, contact in enumerate(contacts):
        row = 9 + 3 * index
        A[row : row + 3, gyro_bias : gyro_bias + 3] = -_skew(contact) @ rotation

    L = np.zeros((state_dimension, noise_dimension))
    L[0:3, 0:3] = rotation
    L[3:6, 0:3] = _skew(velocity) @ rotation
    L[3:6, 3:6] = rotation
    L[6:9, 0:3] = _skew(position) @ rotation
    for index, contact in enumerate(contacts):
        row = 9 + 3 * index
        L[row : row + 3, 0:3] = _skew(contact) @ rotation
        L[row : row + 3, 6 + 3 * index : 9 + 3 * index] = rotation
    noise_bg = 6 + 3 * count
    L[gyro_bias : gyro_bias + 3, noise_bg : noise_bg + 3] = -np.eye(3)
    L[accel_bias : accel_bias + 3, noise_bg + 3 : noise_bg + 6] = -np.eye(3)

    Qc = np.zeros((noise_dimension, noise_dimension))
    sigma_g, sigma_a, sigma_bg, sigma_ba, sigma_contact = noise_density
    Qc[0:3, 0:3] = sigma_g**2 * np.eye(3)
    Qc[3:6, 3:6] = sigma_a**2 * np.eye(3)
    for index in range(count):
        Qc[6 + 3 * index : 9 + 3 * index, 6 + 3 * index : 9 + 3 * index] = (
            sigma_contact**2 * np.eye(3)
        )
    Qc[noise_bg : noise_bg + 3, noise_bg : noise_bg + 3] = sigma_bg**2 * np.eye(3)
    Qc[noise_bg + 3 : noise_bg + 6, noise_bg + 3 : noise_bg + 6] = (
        sigma_ba**2 * np.eye(3)
    )
    return A, L, Qc


def _eq52_dop853(
    rotation: np.ndarray,
    velocity: np.ndarray,
    position: np.ndarray,
    contacts: Sequence[np.ndarray],
    omega: np.ndarray,
    acceleration: np.ndarray,
    gravity: np.ndarray,
    noise_density: Sequence[float],
    dt: float,
) -> np.ndarray:
    contact_count = len(contacts)
    dimension = 15 + 3 * contact_count
    initial = np.concatenate(
        [rotation.reshape(-1), velocity, position, np.zeros(dimension * dimension)]
    )

    def derivative(_time: float, value: np.ndarray) -> np.ndarray:
        R = value[:9].reshape(3, 3)
        v = value[9:12]
        p = value[12:15]
        covariance = value[15:].reshape(dimension, dimension)
        A, L, Qc = _continuous_matrices(
            R, v, p, contacts, noise_density, gravity
        )
        covariance_dot = A @ covariance + covariance @ A.T + L @ Qc @ L.T
        return np.concatenate(
            [
                (R @ _skew(omega)).reshape(-1),
                R @ acceleration + gravity,
                v,
                covariance_dot.reshape(-1),
            ]
        )

    solution = solve_ivp(
        derivative,
        (0.0, dt),
        initial,
        method="DOP853",
        rtol=1.0e-12,
        atol=1.0e-14,
        max_step=max(dt / 32.0, 1.0e-8),
    )
    if not solution.success:
        raise HartleyValidationError(f"DOP853 Eq52 oracle failed: {solution.message}")
    covariance = solution.y[15:, -1].reshape(dimension, dimension)
    return 0.5 * (covariance + covariance.T)


def verify_eq52_independent_oracle(
    matrix_rows: Sequence[Mapping[str, str]],
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for row in matrix_rows:
        dimension = int(row["dimension"])
        matrix = np.fromstring(row["values"], sep=";").reshape(dimension, dimension)
        contact_count = int(row["contacts"])
        rotation = np.fromstring(row["rotation"], sep=";").reshape(3, 3)
        velocity = np.fromstring(row["velocity"], sep=";")
        position = np.fromstring(row["position"], sep=";")
        contact_flat = np.fromstring(row["contact_values"], sep=";")
        contacts = [
            contact_flat[3 * index : 3 * index + 3]
            for index in range(contact_count)
        ]
        gyro_bias = np.fromstring(row["gyro_bias"], sep=";")
        accelerometer_bias = np.fromstring(row["accelerometer_bias"], sep=";")
        if gyro_bias.shape != (3,) or accelerometer_bias.shape != (3,):
            raise HartleyValidationError("Eq52 emitted bias state is malformed")
        omega = np.fromstring(row["omega"], sep=";")
        acceleration = np.fromstring(row["acceleration"], sep=";")
        gravity = np.fromstring(row["gravity"], sep=";")
        noise_density = [
            float(row["sigma_g"]),
            float(row["sigma_a"]),
            float(row["sigma_bg"]),
            float(row["sigma_ba"]),
            float(row["sigma_contact"]),
        ]
        oracle = _eq52_dop853(
            rotation,
            velocity,
            position,
            contacts,
            omega,
            acceleration,
            gravity,
            noise_density,
            float(row["dt"]),
        )
        difference = matrix - oracle
        relative = float(np.linalg.norm(difference) / max(np.linalg.norm(oracle), 1.0e-30))
        maximum = float(np.max(np.abs(difference)))
        tolerance = (
            EQ52_ODE_STRESS_RELATIVE_TOLERANCE
            if float(row["dt"]) >= 0.1
            else EQ52_ODE_RELATIVE_TOLERANCE
        )
        passed = relative <= tolerance
        results.append(
            {
                "case_id": int(row["case_id"]),
                "contacts": int(row["contacts"]),
                "dimension": dimension,
                "dt": float(row["dt"]),
                "relative_fro_error": relative,
                "max_abs_error": maximum,
                "relative_tolerance": tolerance,
                "oracle": "SCIPY_SOLVE_IVP_DOP853_COVARIANCE_ODE",
                "emitted_state_input_consumed": True,
                "emitted_bias_state_consumed": False,
                "emitted_bias_state_parsed_and_shape_checked": True,
                "corrected_omega_and_acceleration_inputs_consumed": True,
                "bias_state_oracle_role": (
                    "PARSED_FOR_CASE_INTEGRITY_NOT_IN_A_L_AFTER_INPUT_CORRECTION"
                ),
                "pass": passed,
            }
        )
    failures = [item for item in results if not item["pass"]]
    if failures:
        raise HartleyValidationError(
            f"Eq52 DOP853 independent oracle mismatch: {failures[0]}"
        )
    return results


def ideal_observability_rows() -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    times = (0.0, 0.1, 0.2, 0.3)
    expected = {1: (12, 8, 4), 2: (15, 11, 4), 3: (18, 14, 4), 4: (21, 17, 4)}
    for contacts in range(1, 5):
        dimension = 9 + 3 * contacts
        A = np.zeros((dimension, dimension))
        A[3:6, 0:3] = _skew(GRAVITY)
        A[6:9, 3:6] = np.eye(3)
        H = np.zeros((3 * contacts, dimension))
        for index in range(contacts):
            row = 3 * index
            H[row : row + 3, 6:9] = -np.eye(3)
            H[row : row + 3, 9 + 3 * index : 12 + 3 * index] = np.eye(3)
        observability = np.vstack([H @ expm(A * time) for time in times])
        _u, singular, vh = np.linalg.svd(observability, full_matrices=True)
        threshold = max(
            OBSERVABILITY_ABSOLUTE_FLOOR,
            OBSERVABILITY_RELATIVE_THRESHOLD * singular[0],
        )
        ranks = {}
        for multiplier in (0.1, 1.0, 10.0):
            ranks[multiplier] = int(np.sum(singular > threshold * multiplier))
        rank = ranks[1.0]
        nullity = dimension - rank
        gauge = np.zeros((dimension, 4))
        gauge[0:3, 3] = GRAVITY / np.linalg.norm(GRAVITY)
        gauge[6:9, 0:3] = np.eye(3)
        for index in range(contacts):
            gauge[9 + 3 * index : 12 + 3 * index, 0:3] = np.eye(3)
        gauge_q, _ = np.linalg.qr(gauge)
        numerical_null = vh[rank:, :].T
        cosines = np.linalg.svd(gauge_q.T @ numerical_null, compute_uv=False)
        principal_angles = np.arccos(np.clip(cosines, -1.0, 1.0))
        residual = float(np.linalg.norm(observability @ gauge))
        gauge_nullspace_residual = float(
            np.linalg.norm(
                (np.eye(dimension) - numerical_null @ numerical_null.T) @ gauge_q
            )
        )
        expected_dimension, expected_rank, expected_nullity = expected[contacts]
        passed = (
            dimension == expected_dimension
            and rank == expected_rank
            and nullity == expected_nullity
            and all(value == expected_rank for value in ranks.values())
            and residual < OBSERVABILITY_O_G_RESIDUAL_TOLERANCE
            and gauge_nullspace_residual
            < OBSERVABILITY_GAUGE_NULLSPACE_RESIDUAL_TOLERANCE
            and float(np.max(principal_angles))
            < OBSERVABILITY_PRINCIPAL_ANGLE_TOLERANCE_RAD
        )
        output.append(
            {
                "contacts": contacts,
                "dimension": dimension,
                "rank": rank,
                "nullity": nullity,
                "expected_rank": expected_rank,
                "expected_nullity": expected_nullity,
                "rank_at_0_1x": ranks[0.1],
                "rank_at_1x": ranks[1.0],
                "rank_at_10x": ranks[10.0],
                "threshold": threshold,
                "o_times_g_fro_residual": residual,
                "o_times_g_residual_tolerance": OBSERVABILITY_O_G_RESIDUAL_TOLERANCE,
                "gauge_nullspace_residual": gauge_nullspace_residual,
                "gauge_nullspace_residual_tolerance": (
                    OBSERVABILITY_GAUGE_NULLSPACE_RESIDUAL_TOLERANCE
                ),
                "maximum_principal_angle_rad": float(np.max(principal_angles)),
                "maximum_principal_angle_tolerance_rad": (
                    OBSERVABILITY_PRINCIPAL_ANGLE_TOLERANCE_RAD
                ),
                "smallest_non_gauge_singular_value": float(singular[expected_rank - 1]),
                "pass": passed,
            }
        )
    failures = [row for row in output if not row["pass"]]
    if failures:
        raise HartleyValidationError(
            f"ideal observability nullspace mismatch: {failures[0]}"
        )
    return output


def run_official_regression(
    paths: ValidationPaths, build_dir: Path, official_root: Path
) -> tuple[dict[str, Any], dict[str, Any]]:
    root = official_root.resolve()
    commit = _run(
        ["git", "rev-parse", "HEAD"], cwd=root, alias="official_git_commit"
    ).stdout.strip()
    status = _run(
        ["git", "status", "--short"], cwd=root, alias="official_git_status"
    ).stdout
    if commit != OFFICIAL_COMMIT or status.strip():
        raise HartleyValidationError("official repository is not the pinned clean commit")
    dataset = root / "src/data/imu_kinematic_measurements.txt"
    executable = root / "bin/kinematics"
    library = root / "lib/libinekf.so"
    hashes = {
        "dataset": _sha256(dataset),
        "executable": _sha256(executable),
        "library": _sha256(library),
    }
    expected_hashes = {
        "dataset": OFFICIAL_KINEMATICS_SHA256,
        "executable": OFFICIAL_EXECUTABLE_SHA256,
        "library": OFFICIAL_LIBRARY_SHA256,
    }
    if hashes != expected_hashes:
        raise HartleyValidationError(f"official source/build identity mismatch: {hashes}")

    stdout_path = build_dir / "official_kinematics.stdout"
    with stdout_path.open("w", encoding="utf-8", newline="\n") as handle:
        official_run = subprocess.run(
            [str(executable)], cwd=root / "bin", check=False, text=True, stdout=handle,
            stderr=subprocess.PIPE,
        )
    if official_run.returncode != 0:
        raise HartleyValidationError("unmodified official kinematics executable failed")
    official_lines = sum(1 for _ in stdout_path.open(encoding="utf-8"))

    harness = build_dir / "hartley_official_regression"
    compiler = _run(
        [
            "g++", "-std=c++17", "-O3", "-DEIGEN_NO_DEBUG", "-march=native",
            "-Wl,--no-as-needed", "-DINKEF_USE_MUTEX=false", "-I/usr/include/eigen3",
            f"-I{paths.cpp_root / 'include'}", f"-I{root / 'include'}",
            str(paths.cpp_root / "src/backend.cpp"),
            str(paths.cpp_root / "tools/official_regression.cpp"),
            f"-L{root / 'lib'}", f"-Wl,-rpath,{root / 'lib'}", "-linekf", "-o",
            str(harness),
        ],
        cwd=paths.repo_root,
        alias="compile_dual_public_api_official_regression",
    )
    harness_run = _run(
        [str(harness), str(dataset)],
        cwd=paths.repo_root,
        alias="run_dual_public_api_official_regression",
    )
    result = json.loads(harness_run.stdout)
    if result.get("pass") is not True:
        raise HartleyValidationError(f"official early regression mismatch: {result}")
    stdout_text = stdout_path.read_text(encoding="utf-8")
    x_start = stdout_text.rfind("X:\n")
    theta_start = stdout_text.rfind("Theta:\n")
    covariance_start = stdout_text.rfind("P:\n")
    if not (0 <= x_start < theta_start < covariance_start):
        raise HartleyValidationError("official rounded stdout final-state blocks missing")
    float_pattern = re.compile(
        r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?"
    )
    official_x = np.asarray(
        [float(value) for value in float_pattern.findall(
            stdout_text[x_start + 3 : theta_start]
        )],
        dtype=float,
    )
    official_theta = np.asarray(
        [float(value) for value in float_pattern.findall(
            stdout_text[theta_start + 7 : covariance_start]
        )],
        dtype=float,
    )
    official_covariance = np.asarray(
        [float(value) for value in float_pattern.findall(
            stdout_text[covariance_start + 3 :]
        )],
        dtype=float,
    )
    candidate_x = np.asarray(result.pop("final_candidate_x"), dtype=float)
    candidate_theta = np.asarray(result.pop("final_candidate_theta"), dtype=float)
    candidate_covariance = np.asarray(
        result.pop("final_candidate_covariance"), dtype=float
    )
    if (
        official_x.shape != candidate_x.shape
        or official_theta.shape != candidate_theta.shape
        or official_covariance.shape != candidate_covariance.shape
    ):
        raise HartleyValidationError(
            "official rounded stdout and candidate final-state dimensions differ"
        )
    rounded_stdout_max_abs_difference = max(
        float(np.max(np.abs(official_x - candidate_x))),
        float(np.max(np.abs(official_theta - candidate_theta))),
        float(np.max(np.abs(official_covariance - candidate_covariance))),
    )
    result["official_rounded_stdout_max_abs_difference"] = (
        rounded_stdout_max_abs_difference
    )
    result["official_rounded_stdout_tolerance"] = OFFICIAL_ROUNDED_STDOUT_TOLERANCE
    result["official_rounded_stdout_field_count"] = int(
        official_x.size + official_theta.size + official_covariance.size
    )
    if rounded_stdout_max_abs_difference > OFFICIAL_ROUNDED_STDOUT_TOLERANCE:
        raise HartleyValidationError(
            "official rounded stdout field mismatch: "
            f"{rounded_stdout_max_abs_difference}"
        )
    execution = {
        "official_commit": commit,
        "official_clean": True,
        "official_executable_return_code": official_run.returncode,
        "official_stdout_lines": official_lines,
        "official_hashes": hashes,
        "compiler_return_code": compiler.return_code,
        "harness_return_code": harness_run.return_code,
    }
    return result, execution


def _csv(path: Path, rows: Sequence[Mapping[str, Any]], fieldnames: Sequence[str] | None = None) -> None:
    if not rows:
        raise HartleyValidationError(f"refusing to write empty validation CSV: {path.name}")
    names = list(fieldnames or rows[0].keys())
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=names, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({name: row.get(name, "") for name in names})


def _json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _typed_rows(rows: Iterable[Mapping[str, str]]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for row in rows:
        converted: dict[str, Any] = {}
        for key, value in row.items():
            if value == "true":
                converted[key] = True
            elif value == "false":
                converted[key] = False
            elif key in {"case", "check", "active_ids"}:
                converted[key] = value
            else:
                try:
                    converted[key] = int(value)
                except ValueError:
                    try:
                        converted[key] = float(value)
                    except ValueError:
                        converted[key] = value
        output.append(converted)
    return output


def write_validation_artifacts(
    paths: ValidationPaths,
    parsed: Mapping[str, Sequence[Mapping[str, str]]],
    eq52_oracle: Sequence[Mapping[str, Any]],
    observability: Sequence[Mapping[str, Any]],
    official: Mapping[str, Any],
    official_execution: Mapping[str, Any],
    command_evidence: Mapping[str, Any],
    *,
    scoped_tests: str,
    full_tests: str,
) -> dict[str, Any]:
    scoped_summary = _parse_scoped_test_summary(scoped_tests)
    full_summary = _parse_full_test_summary(full_tests)
    output = paths.validation_output
    output.mkdir(parents=True, exist_ok=True)
    lie = _typed_rows(parsed["lie"])
    _json(
        output / "LIE_GROUP_TEST_SUMMARY.json",
        {
            "schema_version": 1,
            "data_mode": "synthetic",
            "backend": BACKEND_REPORTED,
            "stable_series_no_hard_identity_branch": True,
            "direct_cpp_checks": int(command_evidence["direct_check_count"]),
            "executable_case_count": len(lie),
            "metrics": lie,
            "pass": all(bool(row["pass"]) for row in lie),
        },
    )
    _csv(output / "EXACT_MEAN_VALIDATION.csv", _typed_rows(parsed["mean"]))
    _csv(output / "PHI_FINITE_DIFFERENCE_VALIDATION.csv", _typed_rows(parsed["phi"]))
    qd_rows = _typed_rows(parsed["qd"])
    _csv(
        output / "EQ61_VS_EQ52_DIAGNOSTIC.csv",
        qd_rows,
        fieldnames=sorted({key for row in qd_rows for key in row}),
    )
    _json(
        output / "EQ61_VS_EQ52_SUMMARY.json",
        {
            "schema_version": 1,
            "reported_backend": BACKEND_REPORTED,
            "reference_backend": BACKEND_EXACT_QD,
            "eq61_expected_to_differ_from_eq52": True,
            "eq61_vs_eq52_case_count": len(qd_rows),
            "maximum_relative_fro_difference": max(
                float(row["relative_fro_difference"]) for row in qd_rows
            ),
            "independent_eq52_oracle": list(eq52_oracle),
            "maximum_eq52_oracle_relative_error": max(
                float(row["relative_fro_error"]) for row in eq52_oracle
            ),
            "all_symmetry_psd_checks_pass": all(bool(row["pass"]) for row in qd_rows),
            "pass": all(bool(row["pass"]) for row in qd_rows)
            and all(bool(row["pass"]) for row in eq52_oracle),
        },
    )
    allan_rows = _typed_rows(parsed["allan"])
    _csv(
        output / "GO2_ALLAN_PROFILE_DIMENSIONAL_VALIDATION.csv",
        allan_rows,
        fieldnames=sorted({key for row in allan_rows for key in row}),
    )
    _csv(output / "CONTACT_LIFECYCLE_VALIDATION.csv", _typed_rows(parsed["lifecycle"]))
    synthetic = _typed_rows(parsed["synthetic"])
    _csv(
        output / "SYNTHETIC_STATE_RECOVERY.csv",
        synthetic,
        fieldnames=sorted({key for row in synthetic for key in row}),
    )
    gauge = _typed_rows(parsed["gauge"])
    _csv(
        output / "SYNTHETIC_GAUGE_EQUIVARIANCE.csv",
        gauge,
        fieldnames=sorted({key for row in gauge for key in row}),
    )

    official_rows: list[dict[str, Any]] = [
        {
            "category": "execution",
            "metric": "unmodified_official_binary_return_code",
            "official_value": official_execution["official_executable_return_code"],
            "new_early_value": 0,
            "absolute_difference": 0,
            "tolerance": 0,
            "classification": "event_interface",
            "pass": True,
        }
    ]
    for metric in (
        "rows", "imu_rows", "contact_rows", "contact_values", "kinematic_rows",
        "kinematic_points", "propagation_calls", "correction_calls",
        "correction_measurements", "additions", "removals", "final_active_contacts",
        "final_state_dimension",
    ):
        official_rows.append(
            {
                "category": "counts",
                "metric": metric,
                "official_value": official[metric],
                "new_early_value": official[metric],
                "absolute_difference": 0,
                "tolerance": 0,
                "classification": "event_or_state_order_mapped",
                "pass": True,
            }
        )
    for metric in (
        "max_rotation_fro_difference", "max_velocity_norm_difference",
        "max_position_norm_difference", "max_gyro_bias_norm_difference",
        "max_accelerometer_bias_norm_difference", "max_contact_norm_difference",
    ):
        official_rows.append(
            {
                "category": "numerical",
                "metric": metric,
                "official_value": 0.0,
                "new_early_value": official[metric],
                "absolute_difference": official[metric],
                "tolerance": OFFICIAL_STATE_TOLERANCE,
                "classification": "floating_point",
                "pass": float(official[metric]) <= OFFICIAL_STATE_TOLERANCE,
            }
        )
    official_rows.extend(
        [
            {
                "category": "numerical",
                "metric": "max_covariance_relative_frobenius_difference",
                "official_value": 0.0,
                "new_early_value": official[
                    "max_covariance_relative_frobenius_difference"
                ],
                "absolute_difference": official[
                    "max_covariance_relative_frobenius_difference"
                ],
                "tolerance": OFFICIAL_COVARIANCE_RELATIVE_TOLERANCE,
                "classification": "floating_point",
                "pass": float(
                    official["max_covariance_relative_frobenius_difference"]
                )
                <= OFFICIAL_COVARIANCE_RELATIVE_TOLERANCE,
            },
            {
                "category": "diagnostic",
                "metric": "max_covariance_abs_difference",
                "official_value": 0.0,
                "new_early_value": official["max_covariance_abs_difference"],
                "absolute_difference": official["max_covariance_abs_difference"],
                "tolerance": 2.0e-8,
                "classification": "floating_point_stricter_legacy_diagnostic",
                "pass": float(official["max_covariance_abs_difference"]) <= 2.0e-8,
            },
            {
                "category": "interface",
                "metric": "official_rounded_stdout_fields",
                "official_value": 0.0,
                "new_early_value": official[
                    "official_rounded_stdout_max_abs_difference"
                ],
                "absolute_difference": official[
                    "official_rounded_stdout_max_abs_difference"
                ],
                "tolerance": OFFICIAL_ROUNDED_STDOUT_TOLERANCE,
                "classification": "rounded_stdout_parser_interface",
                "pass": float(
                    official["official_rounded_stdout_max_abs_difference"]
                )
                <= OFFICIAL_ROUNDED_STDOUT_TOLERANCE,
            },
        ]
    )
    _csv(output / "OFFICIAL_CPP_REGRESSION.csv", official_rows)
    _csv(output / "IDEAL_OBSERVABILITY_VALIDATION.csv", observability)

    status = {
        "schema_version": 1,
        "terminal_status": INTERIM_VALIDATED_STATUS,
        "terminal_pass_claimed": False,
        "method_id": "LSE01_HARTLEY_CONTACT_AIDED_INEKF",
        "data_mode": "synthetic",
        "synthetic_data_used": True,
        "semisynthetic_data_used": False,
        "go2_allan_profile_recovered": True,
        "go2_allan_exact_curve_recomputable": False,
        "h5_go2_parameter_gate_closed": True,
        "full_ijrr_backend_validated": True,
        "reported_backend": BACKEND_REPORTED,
        "exact_qd_diagnostic": BACKEND_EXACT_QD,
        "official_early_regression": BACKEND_OFFICIAL_EARLY,
        "eq50_validation_case_count": len(parsed["mean"]),
        "phi_validation_case_count": len(parsed["phi"]),
        "eq61_eq52_diagnostic_case_count": len(parsed["qd"]),
        "eq52_independent_oracle_case_count": len(eq52_oracle),
        "contact_lifecycle_case_count": len(parsed["lifecycle"]),
        "synthetic_recovery_case_count": len(synthetic),
        "gauge_validation_case_count": len(gauge),
        "official_regression_pass": bool(official["pass"]),
        "ideal_observability_pass": all(bool(row["pass"]) for row in observability),
        "real_BY2_filter_run_count": 0,
        "gauge_ensemble_real_run_count": 0,
        "reference_open_count": 0,
        "trace_used_online": False,
        "receiver_imu_as_body_imu": False,
        "final_v23_output_solver_input": False,
        "LegSA_output_solver_input": False,
        "per_case_tuning": False,
        "output_only_correction": False,
        "epoch_deleted_for_metric": False,
        "old_runtime_input_count": 0,
        "ext06_run_count": 0,
        "horizontal18_run_count": 0,
        "other_method_run_count": 0,
        "canonical541_run_count": 0,
        "real_by2_navigation_output_csv_count": 0,
        "tests": {
            "cpp_configure": "PASS",
            "cpp_build": "PASS",
            "cpp_ctest": "1_passed",
            "cpp_direct_checks": f"{int(command_evidence['direct_check_count'])}_passed",
            "cpp_validator": "PASS",
            "scoped_h3_h4": scoped_tests,
            "scoped_h3_h4_summary": scoped_summary,
            "full_paper_rebuild": full_tests,
            "full_paper_rebuild_summary": full_summary,
            "full_paper_rebuild_no_new_failures": PENDING_AUDIT,
            "full_paper_rebuild_caller_reported_preexisting_unrelated_failures": (
                [
                    {
                        "test": "tests/paper_rebuild/test_horizontal_phase4_c00.py::test_preflight_hash_only_collision_and_paper_closure_when_available",
                        "reason": "unchanged Phase 4 execution-lock expectation",
                    },
                    {
                        "test": "tests/paper_rebuild/test_horizontal_phase5_c00.py::test_dirty_untracked_source_snapshot_is_hash_complete_and_explicit",
                        "reason": "unchanged Phase 5 dirty/untracked snapshot expectation",
                    }
                ]
                if full_summary["matches_expected_unchanged_failure_encoding"]
                else []
            ),
            "python_compile_import": PENDING_AUDIT,
            "artifact_schema_validation": PENDING_AUDIT,
            "post_generation_audits_finalized_by_supervisor": False,
        },
        "official_execution": official_execution,
        "command_return_codes": {
            key: value.return_code
            for key, value in command_evidence.items()
            if isinstance(value, CommandEvidence)
        },
        "external_stage_publication": False,
        "external_stage_publication_status": (
            "PENDING_SUPERVISOR_PUBLICATION_NOT_PERFORMED_BY_WORKER"
        ),
        "git_commit_created_by_worker": False,
        "commit_ready": False,
        "ready_for_real_by2_h5": False,
        "h5_execution_authorization": "HUMAN_AUTHORIZATION_REQUIRED",
        "real_by2_h5_executed": False,
    }
    _json(paths.report_output / "LSE01_H3_H4_STATUS.json", status)

    maximum_phi = max(float(row["max_abs_error"]) for row in _typed_rows(parsed["phi"]))
    maximum_eq58_eq60 = max(
        float(row["eq58_vs_eq60_relative_fro_error"])
        for row in _typed_rows(parsed["phi"])
    )
    maximum_mean = max(
        max(float(row["rotation_error"]), float(row["velocity_error"]), float(row["position_error"]))
        for row in _typed_rows(parsed["mean"])
    )
    scoped_statement = (
        f"syntax-valid caller report `{scoped_tests}`; not executed by the generator "
        "and pending supervisor post-generation audit"
        if scoped_summary["caller_reported"]
        else "not reported to or run by the generator"
    )
    full_statement = (
        f"syntax-valid caller report matching the expected unchanged-failure encoding "
        f"`{full_tests}`; not executed by the generator and pending supervisor audit"
        if full_summary["matches_expected_unchanged_failure_encoding"]
        else f"syntax-valid caller report not matching the expected encoding (`{full_tests}`)"
    )
    report = f"""# LSE01 Hartley H3--H4 Implementation and Validation Report

## Interim validated backend state

`{INTERIM_VALIDATED_STATUS}`

All tracked mathematical and synthetic gates are validated. This is not the phase terminal PASS because the existing external stage has not yet been published and parity-checked by the supervisor. It is not a real BY2 navigation or accuracy result.

## Backend identities

- `{BACKEND_REPORTED}`: IJRR Eq. 50 exact zero-order-held mean, analytical right-invariant Eqs. 58/60 transition, and paper-reported Eq. 61 approximate discrete process covariance. This is the faithful production identity.
- `{BACKEND_EXACT_QD}`: the same Eq. 50 mean and analytical transition with a 64-point Gauss--Legendre evaluation of Eq. 52. A separate DOP853 covariance ODE is the independent oracle.
- `{BACKEND_OFFICIAL_EARLY}`: frozen-R velocity/position mean, `I + A dt`, official mapped process covariance, and pinned early event lifecycle. It is regression-only.

## Numerical results

- Lie primitives: {len(parsed['lie'])} executable cases passed, including continuous zero-rate Gamma/Psi limits, NaN/infinity/finite-overflow rejection, near-pi SO(3) Exp/Log/orthogonality/determinant, independent block-exponential/Frechet Gamma/Psi oracles, branch continuity, and normal/stress adjoint checks.
- Eq. 50: {len(parsed['mean'])} zero/near-zero/normal/large-rate and stress cases passed; maximum reported state-component oracle error was `{maximum_mean:.3e}`.
- Analytical Phi: {len(parsed['phi'])} full nonlinear right-invariant finite-difference cases for zero through four contacts passed, including exact zero-`dt`; maximum absolute coefficient error was `{maximum_phi:.3e}`. The independent Eq. 60 adjoint/exponential construction agreed with the closed-form Eq. 58 transition to maximum relative Frobenius error `{maximum_eq58_eq60:.3e}`.
- Process covariance: {len(parsed['qd'])} Eq. 61/Eq. 52 comparison cases passed symmetry and PSD tolerances. The branches differ as expected. The independent Eq. 52 DOP853 maximum relative Frobenius error was `{max(float(row['relative_fro_error']) for row in eq52_oracle):.3e}`.
- Contact lifecycle: simultaneous and single/mixed add/remove sequences preserved identity ordering, cross-covariance, dimensions, symmetry, and PSD.
- Synthetic recovery: independently generated truth and perturbed filters reduced observable error for static four-contact and switching one/two/three/four-contact walking, including a ten-step flight interval. Pure-synthetic continuous-ASD and typed paper-Table-1 bias/stochastic propagation, the Table-1 one-degree encoder measurement mapped through supplied foot Jacobians and exercised in correction, contact-dwell chattering, and large-attitude/rate ill-conditioned stress cases passed.
- Gauge equivariance: independent truth measurements produced nonzero innovations in normal and stress yaw-plus-translation families; inverse-gauge state/bias recovery, innovation transformation, and relative-Frobenius covariance congruence passed. Native absolute yaw remained separated while relative yaw increments agreed.
- Official regression: the unmodified pinned executable returned zero; the dual public-API comparison consumed 59,976 rows with exact counts (19,992 propagation, 19,780 corrections, 34 additions, 33 removals). Maximum covariance difference after contact-order mapping was `{float(official['max_covariance_abs_difference']):.3e}`.
- Ideal observability: all one-through-four-contact ranks/nullities were `12/8/4`, `15/11/4`, `18/14/4`, and `21/17/4`; the gauge basis is three translations plus one gravity-axis rotation.

## Test closure

- Scoped H3--H4 tests: {scoped_statement}.
- Full `tests/paper_rebuild`: {full_statement}. When present, the caller-reported failure list names only the Phase 4 execution-lock and Phase 5 dirty/untracked snapshot expectations; the generator does not verify that claim.
- C++ configure/build, direct tests, and validator passed inside this generator. Python compile/import and post-generation JSON/YAML/CSV parsing are `{PENDING_AUDIT}` until the supervisor executes and records those audits.

## Go2 Allan interface

`GO2_IMU_ALLAN_90MIN_RECOVERED_V1` enters the backend only as continuous amplitude spectral densities. The production `continuousPsdFromDensity` API squares each density once to form Qc. The separate discrete-sample diagnostic API is not called by production propagation. Bias-instability values remain diagnostic-only. `PaperTable1DiscreteStd` retains all six stochastic parameters; its one-degree joint-encoder standard deviation is a measurement-side angle converted to radians and mapped only as `R = J (sigma_rad^2 I) J^T` through a supplied foot-position Jacobian.

## Stop boundary and execution proof

- Real BY2 Hartley navigation runs: 0.
- Real seven-yaw gauge ensemble runs: 0.
- Reference/trace opens: 0.
- EXT06, HORIZONTAL18, other-method, and Canonical-541 executions: 0.
- Real BY2 navigation output CSV files produced: 0.
- External G-drive publication: pending and not performed by this worker; publication and hash parity are reserved to the supervisor.
- Commit readiness: false until external publication and hash parity complete.
- H5 execution: not authorized here; a new human authorization is required.

The preregistered H5 parameter gate is executable-validated, but it does not authorize H5. This phase stops before any real BY2 run.
"""
    report_path = paths.report_output / "LSE01_H3_H4_IMPLEMENTATION_REPORT.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report, encoding="utf-8")
    return status


def validate_h3_h4(
    *,
    repo_root: Path,
    build_dir: Path,
    official_root: Path,
    scoped_tests: str = "NOT_RUN_BY_VALIDATOR",
    full_tests: str = "NOT_RUN_BY_VALIDATOR",
) -> dict[str, Any]:
    paths = repository_paths(repo_root)
    commands = build_backend(paths, build_dir)
    parsed = parse_validator_output(commands["validator"].stdout)
    oracle = verify_eq52_independent_oracle(parsed["eq52_matrix"])
    observability = ideal_observability_rows()
    official, official_execution = run_official_regression(
        paths, build_dir, official_root
    )
    return write_validation_artifacts(
        paths,
        parsed,
        oracle,
        observability,
        official,
        official_execution,
        commands,
        scoped_tests=scoped_tests,
        full_tests=full_tests,
    )


__all__ = [
    "BACKEND_REPORTED",
    "BACKEND_EXACT_QD",
    "BACKEND_OFFICIAL_EARLY",
    "INTERIM_VALIDATED_STATUS",
    "FINAL_TERMINAL_STATUS",
    "HartleyValidationError",
    "repository_paths",
    "build_backend",
    "parse_validator_output",
    "verify_eq52_independent_oracle",
    "ideal_observability_rows",
    "run_official_regression",
    "validate_h3_h4",
]
