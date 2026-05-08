"""中文说明：检查 N4H4C engine 已打通更新分支，同时禁用非目标因子。"""

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
ENGINE_CPP = REPO_ROOT / "cpp/legsa_v23_core/src/runtime/legsa_v23_engine.cpp"
OPTIONS_HPP = REPO_ROOT / "cpp/legsa_v23_core/include/legsa_v23_core/config/gins_options.hpp"
MANIFEST_CPP = REPO_ROOT / "cpp/legsa_v23_core/src/writers/run_manifest_writer.cpp"


def test_new_imu_process_update_branches_present():
    text = ENGINE_CPP.read_text(encoding="utf-8")
    for keyword in [
        "runUpdateAndFeedback",
        "update_status == 1",
        "update_status == 2",
        "update_status == 3",
        "gnssUpdate",
        "stateFeedback",
        "中文说明",
    ]:
        assert keyword in text


def test_engine_update_wrappers_are_implemented():
    text = ENGINE_CPP.read_text(encoding="utf-8")
    for keyword in [
        "buildGnssPositionMeasurement",
        "buildGnssVelocityMeasurement",
        "buildGnssYawMeasurement",
        "legsa_v23_core::EKFUpdate",
        "legsa_v23_core::stateFeedback",
        "pending_measurements_",
    ]:
        assert keyword in text


def test_manifest_forbidden_flags_stay_false_by_default():
    text = OPTIONS_HPP.read_text(encoding="utf-8") + "\n" + MANIFEST_CPP.read_text(encoding="utf-8")
    for keyword in [
        "raw_doppler = false",
        "go2_prior = false",
        "lsim_oim = false",
        "fgo = false",
        "trace_solver_input = false",
        "numerical_performance_claim",
        "final_v23_output_substitution",
    ]:
        assert keyword in text
