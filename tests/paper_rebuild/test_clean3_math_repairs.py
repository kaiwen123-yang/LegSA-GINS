import json
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
INCLUDE = ROOT / "cpp/legsa_v23_port_core/include"
SOURCE = ROOT / "cpp/legsa_v23_port_core/src"


@pytest.fixture(scope="module")
def clean3_harness(tmp_path_factory: pytest.TempPathFactory) -> Path:
    work = tmp_path_factory.mktemp("clean3_math_harness")
    source = work / "clean3_math_harness.cpp"
    source.write_text(
        r'''
#include "legsa_v23_port_core/common/earth.hpp"
#include "legsa_v23_port_core/common/rotation.hpp"
#include "legsa_v23_port_core/factors/go2_weak_prior_factor.hpp"
#include "legsa_v23_port_core/fileio/file_saver.hpp"
#include "legsa_v23_port_core/kf_gins/gi_engine.hpp"
#include "cpp/legsa_v23_port_core/src/runtime/port_runtime.cpp"

#include <cmath>
#include <filesystem>
#include <iostream>
#include <limits>
#include <string>
#include <vector>

using namespace legsa_v23_port_core;

namespace {

bool near(double actual, double expected, double tolerance) {
  return std::fabs(actual - expected) < tolerance;
}

NavState stateAt(double roll_deg, double pitch_deg, double yaw_deg) {
  NavState state;
  state.pos_blh_rad_m = makeVec3(30.0 * D2R, 120.0 * D2R, 10.0);
  state.euler_rad = makeVec3(roll_deg * D2R, pitch_deg * D2R, yaw_deg * D2R);
  state.qbn = Rotation::euler2quaternion(state.euler_rad);
  state.cbn = Rotation::quaternion2matrix(state.qbn);
  return state;
}

NavState oneWeakPriorStep(const NavState& input) {
  Go2AttitudeWeakPriorMeasurement measurement;
  measurement.roll_rad = 0.0;
  measurement.pitch_rad = 0.0;
  measurement.std_roll_rad = 0.1;
  measurement.std_pitch_rad = 0.1;
  measurement.source_status = "active";
  const auto dz = Go2WeakPriorFactor::residual(input, measurement);
  const Matrix H = Go2WeakPriorFactor::designMatrix(input);
  const Matrix P = identityMatrix(RANK);
  Matrix R(2, 2, 0.0);
  R(0, 0) = 0.01;
  R(1, 1) = 0.01;
  const Matrix Ht = transpose(H);
  const Matrix K = multiply(multiply(P, Ht), inverse(add(multiply(multiply(H, P), Ht), R)));
  const std::vector<double> dx = multiply(K, dz);
  const Vec3 dphi = makeVec3(dx[PHI_ID], dx[PHI_ID + 1], dx[PHI_ID + 2]);
  NavState output = input;
  output.qbn = Rotation::multiply(Rotation::rotvec2quaternion(dphi), input.qbn);
  output.cbn = Rotation::quaternion2matrix(output.qbn);
  output.euler_rad = Rotation::matrix2euler(output.cbn);
  return output;
}

int checkRollPitchJacobian() {
  const std::vector<double> yaws{0.0, 45.0, 90.0, 135.0, 180.0, -90.0};
  for (double yaw : yaws) {
    const NavState roll_after = oneWeakPriorStep(stateAt(2.0, 0.0, yaw));
    if (!(std::fabs(roll_after.euler_rad[0]) <= 0.8 * 2.0 * D2R) ||
        !(std::fabs(roll_after.euler_rad[1]) <= 0.05 * D2R)) {
      std::cerr << "roll pullback failed at yaw=" << yaw << " roll="
                << roll_after.euler_rad[0] * R2D << " pitch=" << roll_after.euler_rad[1] * R2D;
      return 10;
    }
    const NavState pitch_after = oneWeakPriorStep(stateAt(0.0, 2.0, yaw));
    if (!(std::fabs(pitch_after.euler_rad[1]) <= 0.8 * 2.0 * D2R) ||
        !(std::fabs(pitch_after.euler_rad[0]) <= 0.05 * D2R)) {
      std::cerr << "pitch pullback failed at yaw=" << yaw << " roll="
                << pitch_after.euler_rad[0] * R2D << " pitch=" << pitch_after.euler_rad[1] * R2D;
      return 11;
    }
  }

  const Matrix north = Go2WeakPriorFactor::designMatrix(stateAt(0.0, 0.0, 0.0));
  if (!near(north(0, PHI_ID), -1.0, 1.0e-12) ||
      !near(north(0, PHI_ID + 1), 0.0, 1.0e-12) ||
      !near(north(1, PHI_ID), 0.0, 1.0e-12) ||
      !near(north(1, PHI_ID + 1), -1.0, 1.0e-12)) {
    std::cerr << "north-facing Jacobian regression";
    return 12;
  }
  const Matrix capped = Go2WeakPriorFactor::designMatrix(stateAt(0.0, 75.0, 0.0));
  if (!near(capped(0, PHI_ID), -2.0, 1.0e-12)) {
    std::cerr << "secant cap failed: " << capped(0, PHI_ID);
    return 13;
  }
  return 0;
}

GIEngine rawDopplerEngine(const Vec3& lever, const Vec3& dtheta, const Vec3& observed_velocity) {
  PortOptions options;
  options.antlever_m = lever;
  options.enable_receiver_velocity_update = false;
  options.enable_dual_yaw_update = false;
  options.raw_doppler_config.enable_raw_doppler = true;
  options.raw_doppler_config.raw_doppler_residual_gate_mps = 10.0;
  options.init_pos_std_m = makeVec3(1.0, 1.0, 1.0);
  options.init_vel_std_mps = makeVec3(1.0, 1.0, 1.0);
  options.init_att_std_rad = makeVec3(0.1, 0.1, 0.1);
  GIEngine engine(options);
  NavState initial = stateAt(0.0, 0.0, 0.0);
  initial.vel_ned_mps = observed_velocity;
  if (norm(dtheta) > 0.0) {
    initial.vel_ned_mps = makeVec3(0.0, 0.0, 0.0);
  }
  engine.initialize(initial);

  RawDopplerVelocityMeasurement measurement;
  measurement.time = 0.0;
  measurement.velocity_ned_mps = observed_velocity;
  measurement.std_ned_mps = makeVec3(1.0, 1.0, 1.0);
  measurement.sat_count = 6;
  measurement.provider_status = "available";
  measurement.valid = true;
  measurement.lineage_valid = true;
  RawDopplerFactorStatus status;
  status.solver_enabled = true;
  status.provider_status = "available";
  engine.setRawDopplerVelocityMeasurements({measurement}, status);

  ImuData first;
  first.time = 0.0;
  first.dt = 0.01;
  engine.addImuData(first, true);
  ImuData current;
  current.time = 0.01;
  current.dt = 0.01;
  current.dtheta = dtheta;
  engine.addImuData(current);
  GnssData trigger;
  trigger.time = 0.0;
  trigger.validity_explicit = true;
  trigger.has_position = false;
  trigger.has_velocity = false;
  trigger.has_yaw = true;
  trigger.isvalid = true;
  engine.addGnssData(trigger);
  engine.newImuProcess();
  return engine;
}

int checkRawDopplerLeverArm() {
  const Vec3 lever = makeVec3(0.1, 0.05, -0.02);
  const Vec3 rotation_velocity = makeVec3(-0.1, 0.2, 0.0);
  GIEngine rotation = rawDopplerEngine(lever, makeVec3(0.0, 0.0, 0.02), rotation_velocity);
  if (!(rotation.rawDopplerResidualP95() < 1.0e-9) || rotation.rawDopplerUpdateCount() != 1) {
    std::cerr << "rotation residual=" << rotation.rawDopplerResidualP95();
    return 20;
  }

  const Vec3 translation = makeVec3(0.3, -0.2, 0.1);
  GIEngine with_lever = rawDopplerEngine(lever, makeVec3(0.0, 0.0, 0.0), translation);
  GIEngine zero_lever = rawDopplerEngine(makeVec3(0.0, 0.0, 0.0), makeVec3(0.0, 0.0, 0.0), translation);
  if (with_lever.navState().vel_ned_mps != zero_lever.navState().vel_ned_mps ||
      with_lever.getCovariance() != zero_lever.getCovariance() ||
      with_lever.rawDopplerResidualP95() != zero_lever.rawDopplerResidualP95()) {
    std::cerr << "zero-omega path changed";
    return 21;
  }
  return 0;
}

int checkCovHealth(const std::string& output_dir) {
  PortOptions options;
  options.stage_id = "CLEAN3_TEST_COV_HEALTH_FAILURE";
  options.protocol_id = "CLEAN3_TEST_ONLY";
  options.case_id = "FINITE_OVERFLOW";
  options.run_id = "cov_health_failure";
  options.data_mode = "synthetic";
  options.synthetic_data_used = true;
  options.init_pos_std_m = makeVec3(std::numeric_limits<double>::max(), 1.0, 1.0);
  GIEngine engine(options);
  engine.initialize(stateAt(0.0, 0.0, 0.0));
  ImuData first;
  first.time = 0.0;
  first.dt = 0.01;
  engine.addImuData(first, true);
  ImuData current;
  current.time = 0.25;
  current.dt = 0.25;
  engine.addImuData(current);
  engine.newImuProcess();
  if (engine.covHealthFailCount() != 1 || !near(engine.covHealthFirstFailureTime(), 0.25, 1.0e-12)) {
    std::cerr << "cov health counter/time mismatch";
    return 30;
  }

  ImuData next;
  next.time = 0.5;
  next.dt = 0.25;
  engine.addImuData(next);
  engine.newImuProcess();
  if (engine.covHealthFailCount() != 2 || !near(engine.covHealthFirstFailureTime(), 0.25, 1.0e-12)) {
    std::cerr << "cov health repeated-failure semantics mismatch";
    return 31;
  }

  bool failed_closed = false;
  try {
    failClosedOnCovHealth(engine, options, output_dir, "expected covariance failure");
  } catch (const std::runtime_error& error) {
    failed_closed = std::string(error.what()) == "expected covariance failure";
  }
  if (!failed_closed) {
    std::cerr << "production covariance helper did not fail closed";
    return 32;
  }

  PortOptions normal_options;
  GIEngine normal(normal_options);
  normal.initialize(stateAt(0.0, 0.0, 0.0));
  ImuData normal_first;
  normal_first.time = 0.0;
  normal_first.dt = 0.01;
  normal.addImuData(normal_first, true);
  ImuData normal_current;
  normal_current.time = 0.01;
  normal_current.dt = 0.01;
  normal.addImuData(normal_current);
  normal.newImuProcess();
  copyCovHealthStatus(normal, normal_options);
  if (normal.covHealthFailCount() != 0 || normal.covHealthFirstFailureTime() != -1.0 ||
      normal_options.cov_health_status != "PASS") {
    std::cerr << "normal covariance-health zero case failed";
    return 33;
  }
  return 0;
}

}  // namespace

int main(int argc, char** argv) {
  if (argc < 2) return 2;
  const std::string mode = argv[1];
  if (mode == "rp") return checkRollPitchJacobian();
  if (mode == "rd") return checkRawDopplerLeverArm();
  if (mode == "cov" && argc == 3) return checkCovHealth(argv[2]);
  return 3;
}
''',
        encoding="utf-8",
    )
    executable = work / "clean3_math_harness"
    cpp_sources = sorted(
        item for item in SOURCE.rglob("*.cpp")
        if "demo" not in item.parts and item != SOURCE / "runtime/port_runtime.cpp"
    )
    subprocess.run(
        ["g++", "-std=c++17", "-O0", "-I", str(ROOT), "-I", str(INCLUDE),
         *(str(item) for item in cpp_sources),
         str(source), "-o", str(executable)],
        check=True,
    )
    return executable


def _run(executable: Path, *args: object) -> None:
    result = subprocess.run(
        [str(executable), *(str(arg) for arg in args)],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr


def test_roll_pitch_jacobian_pullback_symmetry_regression_and_cap(clean3_harness: Path) -> None:
    _run(clean3_harness, "rp")


def test_raw_doppler_rotation_compensation_and_zero_omega_identity(clean3_harness: Path) -> None:
    _run(clean3_harness, "rd")


def test_covariance_health_failure_counter_time_and_manifest(clean3_harness: Path, tmp_path: Path) -> None:
    _run(clean3_harness, "cov", tmp_path)
    manifest = json.loads((tmp_path / "RUN_MANIFEST.json").read_text(encoding="utf-8"))
    assert manifest["math_port_completed"] is False
    assert manifest["cov_health_status"] == "FAILED"
    assert manifest["cov_health_fail_count"] == 2
    assert manifest["cov_health_first_failure_time"] == pytest.approx(0.25, abs=1.0e-12)
    assert manifest["cov_health_fail_count"] == manifest["propagation_count"] == 2
    assert manifest["measurement_update_count"] == 0
    assert manifest["position_update_count"] == 0
    assert manifest["velocity_update_count"] == 0
    assert manifest["yaw_update_count"] == 0
    assert manifest["stage_id"] == "CLEAN3_TEST_COV_HEALTH_FAILURE"
    assert manifest["protocol_id"] == "CLEAN3_TEST_ONLY"
    assert manifest["case_id"] == "FINITE_OVERFLOW"
    assert manifest["run_id"] == "cov_health_failure"
    assert manifest["data_mode"] == "synthetic"
    assert manifest["synthetic_data_used"] is True
    assert manifest["trace_used_online"] is False
    assert not any(
        (tmp_path / name).exists()
        for name in (
            "LegSA_PORT_NAV.nav", "LegSA_PORT_STD.csv", "EVAL_NAV.csv",
            "KF_GINS_Navresult.nav", "KF_GINS_STD.txt", "KF_GINS_IMU_ERR.txt",
        )
    )
