"""中文说明：N4H4A C++ contract 测试锁定函数名、中文注释和 manifest 禁用项。"""

import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
ENGINE_SOURCE = REPO_ROOT / "cpp/legsa_v23_core/src/runtime/legsa_v23_engine.cpp"
ENGINE_HEADER = REPO_ROOT / "cpp/legsa_v23_core/include/legsa_v23_core/runtime/legsa_v23_engine.hpp"
MANIFEST_WRITER = REPO_ROOT / "cpp/legsa_v23_core/src/writers/run_manifest_writer.cpp"
CMAKE_FILE = REPO_ROOT / "cpp/CMakeLists.txt"

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

FORBIDDEN_FLAGS = [
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


def test_required_engine_function_names_exist():
    text = ENGINE_SOURCE.read_text(encoding="utf-8") + "\n" + ENGINE_HEADER.read_text(encoding="utf-8")
    missing = [name for name in REQUIRED_FUNCTIONS if name not in text]
    assert not missing


def test_required_engine_functions_have_chinese_comments():
    text = ENGINE_SOURCE.read_text(encoding="utf-8")
    missing_comments = []
    for name in REQUIRED_FUNCTIONS:
        definition_name = "LegSAV23Engine::LegSAV23Engine" if name == "LegSAV23Engine" else f"LegSAV23Engine::{name}"
        match = re.search(re.escape(definition_name), text)
        assert match, name
        nearby = text[max(0, match.start() - 220) : match.start()]
        if "中文说明" not in nearby:
            missing_comments.append(name)
    assert not missing_comments


def test_manifest_forbidden_flags_are_written_false():
    text = MANIFEST_WRITER.read_text(encoding="utf-8").replace('\\"', '"')
    for flag in FORBIDDEN_FLAGS:
        assert flag in text
        assert not re.search(rf'["\']?{re.escape(flag)}["\']?\s*[:=]\s*true\b', text, re.IGNORECASE)
    assert '"phase": "N4H4A"' in text
    assert '"solver_role": "legsa_v23_core_skeleton"' in text


def test_cmake_has_independent_v23_core_targets_without_reference_compile_path():
    text = CMAKE_FILE.read_text(encoding="utf-8")
    assert "add_library(legsa_v23_core" in text
    assert "add_executable(legsa_v23_core_demo" in text
    forbidden_compile_patterns = [
        r"target_include_directories\([^)]*final_v23_repo",
        r"target_sources\([^)]*final_v23_repo",
        r"file\(GLOB[^)]*final_v23_repo/.+\.cpp",
    ]
    for pattern in forbidden_compile_patterns:
        assert not re.search(pattern, text, re.DOTALL)
