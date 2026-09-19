"""Artificial synthetic unit inputs only; no raw/provider/trace or evaluator access.

The compiled harness exercises measurement math and loader APIs, never a native
trajectory run. All compiled files stay in the separate T5bc candidate build.
"""
import csv
import json
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
BUILD = ROOT / "build/t5bc_v3_candidate_cpp"
INCLUDE = ROOT / "cpp/legsa_v23_port_core/include"

HARNESS = r'''
#include "legsa_v23_port_core/baseline3d.hpp"
#include "legsa_v23_port_core/common/rotation.hpp"
#include "legsa_v23_port_core/config/port_config_loader.hpp"
#include "legsa_v23_port_core/fileio/gnss_file_loader.hpp"
#include "legsa_v23_port_core/fileio/file_saver.hpp"
#include "legsa_v23_port_core/kf_gins/gi_engine.hpp"
#include <cmath>
#include <iostream>
#include <limits>
#include <stdexcept>
#include <string>

using namespace legsa_v23_port_core;

void require(bool passed, const std::string& message) {
  if (!passed) throw std::runtime_error(message);
}
NavState state(double roll, double pitch, double yaw) {
  NavState value;
  value.pos_blh_rad_m = makeVec3(0.5, 1.0, 20.0);
  value.euler_rad = makeVec3(roll, pitch, yaw);
  value.qbn = Rotation::euler2quaternion(value.euler_rad);
  value.cbn = Rotation::quaternion2matrix(value.qbn);
  return value;
}
PortOptions options(bool basic) {
  PortOptions value;
  value.data_mode = "synthetic_unit_test";
  value.synthetic_data_used = true;
  value.enable_basic_dual_yaw_baseline = basic;
  value.enable_receiver_velocity_update = false;
  value.dual_antenna_measurement_model = "baseline3d";
  value.baseline3d_length_m = 1.2;
  value.baseline3d_k_b = 1.0;
  value.baseline3d_path = "synthetic_sidecar.csv";
  value.basic_dual_yaw_fixed_std_deg = 2.933193;
  value.init_att_std_rad = makeVec3(0.02, 0.02, 0.1);
  return value;
}
GnssData observation(const PortOptions& value, const NavState& truth) {
  GnssData data;
  data.time = 1.0;
  data.isvalid = true;
  data.has_position = false;
  data.has_velocity = false;
  data.has_yaw = false;
  data.yaw_rad = data.yaw_std_rad = std::numeric_limits<double>::quiet_NaN();
  data.baseline3d.present = true;
  data.baseline3d.valid = true;
  data.baseline3d.reason = "valid";
  data.baseline3d.ned_m = multiply(truth.cbn, makeVec3(0.0, -value.baseline3d_length_m, 0.0));
  data.baseline3d.pacc1_m = data.baseline3d.pacc2_m =
      value.baseline3d_length_m * value.basic_dual_yaw_fixed_std_deg * D2R / std::sqrt(2.0);
  return data;
}

void jacobian() {
  const auto opt = options(true);
  double max_error = 0.0;
  for (const auto& rpy : {makeVec3(0.0, 0.0, 0.0), makeVec3(0.2, -0.3, 1.1),
                          makeVec3(-0.7, 0.4, -2.8), makeVec3(0.0, 0.0, 3.13)}) {
    const auto truth = state(rpy[0], rpy[1], rpy[2]);
    const auto obs = observation(opt, truth).baseline3d;
    const auto model = buildBaseline3dModel(truth.cbn, obs, opt.baseline3d_length_m, opt.baseline3d_k_b);
    constexpr double eps = 1.0e-6;
    for (std::size_t axis = 0; axis < 3; ++axis) {
      Vec3 error = makeVec3(0.0, 0.0, 0.0);
      error[axis] = eps;
      // Nominal error is Exp(-phi) C_true, opposite to feedback Exp(+phi).
      const auto plus = multiply(Rotation::quaternion2matrix(Rotation::rotvec2quaternion(scale(error, -1.0))), truth.cbn);
      const auto minus = multiply(Rotation::quaternion2matrix(Rotation::rotvec2quaternion(error)), truth.cbn);
      const auto rp = buildBaseline3dModel(plus, obs, opt.baseline3d_length_m, 1.0).residual_m;
      const auto rm = buildBaseline3dModel(minus, obs, opt.baseline3d_length_m, 1.0).residual_m;
      for (std::size_t row = 0; row < 3; ++row) {
        max_error = std::max(max_error, std::fabs((rp[row] - rm[row]) / (2.0 * eps) - model.H(row, PHI_ID + axis)));
      }
    }
    for (std::size_t row = 0; row < 3; ++row) {
      double gauge = 0.0;
      for (std::size_t col = 0; col < 3; ++col) gauge += model.H(row, PHI_ID + col) * model.predicted_m[col];
      require(std::fabs(gauge) < 1.0e-12, "baseline-axis rotation gauge violated");
      for (std::size_t col = 0; col < RANK; ++col) {
        if (col < PHI_ID || col >= PHI_ID + 3) require(model.H(row, col) == 0.0, "non-attitude H column");
      }
    }
  }
  std::cout << "synthetic_jacobian_max_abs_error=" << max_error << '\n';
  require(max_error < 2.0e-9, "B3 numerical Jacobian sign/value failure");
}

void scalarConsistency() {
  const auto b3 = options(true);
  auto scalar = b3;
  scalar.dual_antenna_measurement_model = "scalar";
  double max_difference = 0.0;
  for (double yaw : {-2.8, -0.4, 0.0, 0.8, 2.8}) {
    const auto initial = state(0.0, 0.0, yaw);
    constexpr double delta = 1.0e-4;
    const auto truth = state(0.0, 0.0, yaw + delta);
    auto b3_obs = observation(b3, truth);
    auto scalar_obs = b3_obs;
    scalar_obs.has_yaw = true;
    scalar_obs.yaw_rad = yaw + delta;
    // Basic scalar ignores the provider yaw_std, including this poison value.
    scalar_obs.yaw_std_rad = std::numeric_limits<double>::quiet_NaN();
    GIEngine vector_engine(b3), scalar_engine(scalar);
    vector_engine.initialize(initial);
    scalar_engine.initialize(initial);
    vector_engine.gnssUpdate(b3_obs);
    scalar_engine.gnssUpdate(scalar_obs);
    vector_engine.stateFeedback();
    scalar_engine.stateFeedback();
    const double vector_yaw = vector_engine.navState().euler_rad[2];
    const double scalar_yaw = scalar_engine.navState().euler_rad[2];
    // Both engine outputs are in [0,2pi); the fixture includes negative yaw.
    // Compare rotations, never their different angle representations.
    const auto angle_difference = [](double a, double b) {
      return std::atan2(std::sin(a - b), std::cos(a - b));
    };
    max_difference = std::max(max_difference, std::fabs(angle_difference(vector_yaw, scalar_yaw)));
    const double correction = angle_difference(vector_yaw, yaw);
    require(correction > 0.0 && std::fabs(correction - delta) < delta, "B3 correction wrong direction");
    require(vector_engine.baseline3dCounts().accepted == 1 && scalar_engine.yawNormalCount() == 1,
            "comparison did not apply both updates");
  }
  std::cout << "synthetic_scalar_yaw_max_difference_rad=" << max_difference << '\n';
  require(max_difference < 1.0e-6, "horizontal B3/scalar yaw correction differs >=1e-6 rad");
}

void intakeDuringPositionVelocityOutage() {
  const auto initial = state(0.0, 0.0, 0.0);
  const auto opt = options(true);
  auto data = observation(opt, state(0.0, 0.0, 0.001));
  data.validity_explicit = true;
  data.isvalid = false;  // Match loader output; addGnssData owns scheduling validity.
  GIEngine engine(opt);
  engine.initialize(initial);
  engine.addGnssData(data);
  engine.gnssUpdate();
  require(engine.baseline3dCounts().accepted == 1, "B3 lost during position/RV outage");
  auto scalar_opt = opt;
  scalar_opt.dual_antenna_measurement_model = "scalar";
  GIEngine scalar_engine(scalar_opt);
  scalar_engine.initialize(initial);
  scalar_engine.addGnssData(data);
  scalar_engine.gnssUpdate();
  require(scalar_engine.yawUpdateCount() == 0 && scalar_engine.baseline3dCounts().attempts == 0,
          "scalar mode used the B3-only validity bit");
}

void gating(const std::string& output) {
  auto basic = options(true);
  auto robust = options(false);
  const auto initial = state(0.0, 0.0, 0.0);
  auto b_obs = observation(basic, initial);
  b_obs.baseline3d.ned_m[0] += 10.0;
  auto r_obs = b_obs;
  GIEngine b(basic), r(robust);
  b.initialize(initial); r.initialize(initial);
  b.gnssUpdate(b_obs); r.gnssUpdate(r_obs);
  require(b.baseline3dCounts().accepted == 1 && b.baseline3dCounts().rejected == 0,
          "Basic B3 unexpectedly gated");
  require(r.baseline3dCounts().rejected == 1 && r.baseline3dDiagnostics().front().reason == "NIS_3DOF_REJECT",
          "nonbasic B3 missing NIS gate");
  GnssData missing;
  missing.isvalid = true; missing.has_position = false; missing.has_velocity = false;
  missing.time = 2.0;
  r.gnssUpdate(missing);
  require(r.baseline3dCounts().invalid == 1 && r.baseline3dCounts().missing == 1,
          "missing B3 was treated as a zero observation");
  r.writeBaseline3dDiagnostics(output);
  robust.baseline3d_counts = r.baseline3dCounts();
  FileSaver::writeRunManifest(output, robust);
}

void sourceAware() {
  auto enabled = options(false);
  enabled.source_aware_policy_config.enable_source_aware_weighting = true;
  enabled.source_aware_policy_config.source_aware_mode = "lsim_oim";
  GIEngine on(enabled);
  auto disabled = enabled;
  disabled.source_aware_policy_config.enable_source_aware_weighting = false;
  GIEngine off(disabled);
  const auto initial = state(0.0, 0.0, 0.0);
  on.initialize(initial); off.initialize(initial);
  auto a = observation(enabled, state(0.0, 0.0, 0.0001));
  auto b = a;
  on.gnssUpdate(a); off.gnssUpdate(b);
  require(on.baseline3dCounts().accepted == 1 && off.baseline3dCounts().accepted == 1, "SA synthetic update missing");
  require(on.sourceAwareEvaluationCount() == 1 && off.sourceAwareEvaluationCount() == 0,
          "source-aware enable semantics changed");
}

void zeroCovariance() {
  const auto opt = options(true);
  GIEngine engine(opt);
  const auto initial = state(0.0, 0.0, 0.0);
  engine.initialize(initial);
  auto one_zero = observation(opt, initial);
  one_zero.baseline3d.pacc1_m = 0.0;
  engine.gnssUpdate(one_zero);
  require(engine.baseline3dCounts().accepted == 1, "single zero pAcc was rejected");
  auto both_zero = observation(opt, initial);
  both_zero.baseline3d.pacc1_m = both_zero.baseline3d.pacc2_m = 0.0;
  engine.gnssUpdate(both_zero);
  require(engine.baseline3dCounts().attempts == 2 && engine.baseline3dCounts().rejected == 1,
          "invalid covariance attempt/reject accounting failed");
  require(engine.baseline3dDiagnostics().back().reason == "REJECT_INVALID_COVARIANCE",
          "invalid covariance was not explicitly classified");
}

int main(int argc, char** argv) {
  try {
    if (argc < 2) return 2;
    const std::string mode = argv[1];
    if (mode == "jacobian") jacobian();
    else if (mode == "scalar") scalarConsistency();
    else if (mode == "outage_intake") intakeDuringPositionVelocityOutage();
    else if (mode == "gating" && argc == 3) gating(argv[2]);
    else if (mode == "sa") sourceAware();
    else if (mode == "zero_covariance") zeroCovariance();
    else if (mode == "loader" && argc == 4) {
      const auto rows = GnssFileLoader::loadBaseline3d(argv[2], argv[3]);
      for (const auto& row : rows) std::cout << row.time << ',' << row.baseline3d.present << ','
          << row.baseline3d.valid << ',' << row.has_yaw << ',' << row.baseline3d.reason << '\n';
    } else if (mode == "config" && argc == 4) {
      const auto value = PortConfigLoader::loadYamlLike(argv[2]);
      FileSaver::writeRunManifest(argv[3], value);
    } else if (mode == "scalar_identity" && argc == 3) {
      auto value = options(true);
      value.dual_antenna_measurement_model = "scalar";
      GIEngine engine(value);
      engine.writeBaseline3dDiagnostics(argv[2]);
      FileSaver::writeRunManifest(argv[2], value);
    } else return 3;
    return 0;
  } catch (const std::exception& error) {
    std::cerr << error.what() << '\n';
    return 1;
  }
}
'''


@pytest.fixture(scope="module")
def t5bc_harness() -> Path:
    BUILD.mkdir(parents=True, exist_ok=True)
    subprocess.run(["cmake", "-S", str(ROOT / "cpp"), "-B", str(BUILD),
                    "-DCMAKE_BUILD_TYPE=Release"], check=True)
    subprocess.run(["cmake", "--build", str(BUILD), "--target", "legsa_v23_port_core_demo", "-j2"], check=True)
    source = BUILD / "t5bc_synthetic_harness.cpp"
    source.write_text(HARNESS, encoding="utf-8")
    executable = BUILD / "t5bc_synthetic_harness"
    subprocess.run(["g++", "-std=c++17", "-O2", "-I", str(INCLUDE), str(source),
                    str(BUILD / "liblegsa_v23_port_core.a"), "-o", str(executable)], check=True)
    return executable


def run_harness(executable: Path, *args: object, ok: bool = True) -> subprocess.CompletedProcess:
    result = subprocess.run([str(executable), *(str(arg) for arg in args)], capture_output=True, text=True)
    assert (result.returncode == 0) == ok, result.stdout + result.stderr
    return result


def test_numerical_error_state_jacobian(t5bc_harness: Path) -> None:
    print(run_harness(t5bc_harness, "jacobian").stdout)


def test_horizontal_scalar_consistency_and_basic_fixed_std(t5bc_harness: Path) -> None:
    print(run_harness(t5bc_harness, "scalar").stdout)


def test_basic_no_gate_nonbasic_nis_and_missing_diagnostics(t5bc_harness: Path, tmp_path: Path) -> None:
    run_harness(t5bc_harness, "gating", tmp_path)
    rows = list(csv.DictReader((tmp_path / "BASELINE3D_DIAGNOSTICS.csv").open()))
    assert len(rows) == 2
    assert None not in rows[0] and None not in rows[1]
    assert rows[0]["reason"] == "NIS_3DOF_REJECT"
    assert float(rows[0]["nis_actual_innovation"]) > 11.34
    assert rows[1]["reason"] == "missing_exact_time"
    assert rows[1]["z_n_m"] == rows[1]["nis_actual_innovation"] == ""
    manifest = json.loads((tmp_path / "RUN_MANIFEST.json").read_text())
    assert manifest["baseline3d_attempt_count"] == manifest["baseline3d_reject_count"] == 1
    assert manifest["baseline3d_invalid_count"] == 1
    assert manifest["actual_solver_input_roles"]["dual_antenna_baseline3d"] == "three_dimensional_gnss_baseline_measurement"
    assert manifest["baseline3d_scalar_yaw_observation_used"] is False


def test_source_aware_enabled_and_disabled_semantics(t5bc_harness: Path) -> None:
    run_harness(t5bc_harness, "sa")


def test_single_zero_pacc_and_both_zero_covariance(t5bc_harness: Path) -> None:
    run_harness(t5bc_harness, "zero_covariance")


def test_baseline_intake_remains_active_during_position_velocity_outage(t5bc_harness: Path) -> None:
    run_harness(t5bc_harness, "outage_intake")


def write_gnss(path: Path) -> None:
    path.write_text("".join(f"{time} 30 120 10 1 1 1 0 0 0 1 1 1 NOT_YAW NOT_STD 1 0 NOT_VALID\n"
                            for time in (1, 2, 3, 4)))


def test_loader_exact_time_invalid_empty_and_scalar_tokens_ignored(t5bc_harness: Path, tmp_path: Path) -> None:
    gnss, sidecar = tmp_path / "synthetic.gnss", tmp_path / "synthetic.csv"
    write_gnss(gnss)
    sidecar.write_text("time,b_n,b_e,b_d,pAcc1,pAcc2,valid\n"
                       "1,0,-1,0,0,0.02,1\n2.0000000001,0,-1,0,0.01,0.02,1\n"
                       "3,,,,,,0\n4,0,-1,0,0.01,0.02,1\n")
    result = run_harness(t5bc_harness, "loader", gnss, sidecar)
    assert result.stdout.splitlines() == ["1,1,1,0,valid", "2,0,0,0,missing_exact_time",
                                          "3,1,0,0,provider_invalid", "4,1,1,0,valid"]


@pytest.mark.parametrize("rows,reason", [
    ("1,0,-1,0,0.01,0.02,1\n1,0,-1,0,0.01,0.02,1\n", "DUPLICATE_TIME"),
    ("1,0,-1,0,-0.01,0.02,1\n", "PACC_MUST_BE_NONNEGATIVE"),
    ("1,0,-1,0,,0.02,1\n", "VALID_ROW_HAS_MISSING_VALUES"),
    ("1,0,-1,0,nan,0.02,1\n", "NONFINITE_OR_MALFORMED_NUMBER"),
])
def test_loader_invalid_structure(t5bc_harness: Path, tmp_path: Path, rows: str, reason: str) -> None:
    gnss, sidecar = tmp_path / "synthetic.gnss", tmp_path / "synthetic.csv"
    write_gnss(gnss)
    sidecar.write_text("time,b_n,b_e,b_d,pAcc1,pAcc2,valid\n" + rows)
    assert reason in run_harness(t5bc_harness, "loader", gnss, sidecar, ok=False).stderr


BASE_CONFIG = """data_mode: synthetic_unit_test
synthetic_data_used: true
dual_antenna_measurement_model: baseline3d
baseline3d_path: synthetic.csv
baseline3d_length_m: 1.2
baseline3d_k_b: 1.0
"""


@pytest.mark.parametrize("old,new,reason", [
    ("baseline3d_k_b: 1.0\n", "", "REQUIRED_CONFIG"),
    ("baseline3d_length_m: 1.2", "baseline3d_length_m: 0", "REQUIRED_POSITIVE_CONFIG"),
    ("baseline3d_path: synthetic.csv", "baseline3d_path: ''", "REQUIRED_CONFIG"),
    ("baseline3d_k_b: 1.0", "baseline3d_k_b: 1.0junk", "REQUIRED_POSITIVE_CONFIG"),
    ("", "enable_multi_state_qm: true\n", "SCOPE_REQUIRES_QA_QM_OFF"),
    ("", "enable_qa_fallback: true\n", "SCOPE_REQUIRES_QA_QM_OFF"),
])
def test_b3_required_config_and_scope(t5bc_harness: Path, tmp_path: Path, old: str, new: str, reason: str) -> None:
    config = tmp_path / "synthetic.yaml"
    config.write_text(BASE_CONFIG.replace(old, new) if old else BASE_CONFIG + new)
    assert reason in run_harness(t5bc_harness, "config", config, tmp_path / "out", ok=False).stderr


def test_b3_echo_and_scalar_no_new_echo_or_diagnostics(t5bc_harness: Path, tmp_path: Path) -> None:
    config = tmp_path / "synthetic.yaml"
    config.write_text(BASE_CONFIG)
    run_harness(t5bc_harness, "config", config, tmp_path / "b3")
    manifest = json.loads((tmp_path / "b3/RUN_MANIFEST.json").read_text())
    assert manifest["dual_antenna_measurement_model"] == "baseline3d"
    assert manifest["baseline3d_length_m"] == 1.2
    assert manifest["baseline3d_k_b"] == 1.0
    assert manifest["actual_solver_input_paths"]["dual_antenna_baseline3d"] == "synthetic.csv"
    run_harness(t5bc_harness, "scalar_identity", tmp_path / "scalar")
    scalar = json.loads((tmp_path / "scalar/RUN_MANIFEST.json").read_text())
    assert not any("baseline3d" in key or key == "dual_antenna_measurement_model" for key in scalar)
    assert "dual_antenna_baseline3d" not in scalar["actual_solver_input_paths"]
    assert not (tmp_path / "scalar/BASELINE3D_DIAGNOSTICS.csv").exists()
