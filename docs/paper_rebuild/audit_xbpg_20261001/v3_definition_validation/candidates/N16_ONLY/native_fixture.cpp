// New N16_ONLY pure-synthetic fixtures. No configuration/provider/reference file is read.
// Compile separately against the old observed source and the isolated N16 source.
#include "legsa_v23_port_core/kf_gins/gi_engine.hpp"
#include <array>
#include <cmath>
#include <cstring>
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <limits>
#include <string>
#include <vector>

using namespace legsa_v23_port_core;
using namespace legsa_v23_port_core::source_aware;
using legsa_v23_port_core::mechanism_observer::Json;
namespace fs = std::filesystem;

struct PolicyCase {
  std::string name;
  SourceMetadata metadata;
  std::array<bool, 3> mask{{true, true, false}};
  SourceAwarePolicyConfig config;
  double normalized = 0.5;
  bool three_dimensional_control = false;
};

PolicyCase policyCase(const std::string& name) {
  PolicyCase t;
  t.name = name;
  t.metadata.source = MeasurementSource::kGo2HorizontalVelocity;
  t.metadata.std_xyz = {0.2, 0.3, 999.0};
  t.config.enable_source_aware_weighting = true;
  t.config.source_aware_mode = "lsim_oim";
  t.config.source_aware_enable_rolling_innovation_baseline = false;
  return t;
}

std::vector<PolicyCase> policyCases() {
  const double nan = std::numeric_limits<double>::quiet_NaN();
  const double inf = std::numeric_limits<double>::infinity();
  std::vector<PolicyCase> cases;
  const std::vector<std::pair<std::string, double>> inactive{
      {"ordinary", 0.4}, {"sentinel999", 999.0}, {"nan", nan}, {"inf", inf},
      {"negative_inf", -inf}, {"zero", 0.0}, {"negative", -2.0}};
  for (const auto& item : inactive) {
    auto t = policyCase("inactive_D_" + item.first);
    t.metadata.std_xyz[2] = item.second;
    cases.push_back(t);
  }
  for (int axis = 0; axis < 2; ++axis) {
    for (const auto& item : std::vector<std::pair<std::string, double>>{
             {"nan", nan}, {"inf", inf}, {"zero", 0.0}, {"negative", -1.0}}) {
      auto t = policyCase(std::string("active_") + (axis == 0 ? "N_" : "E_") + item.first);
      t.metadata.std_xyz[axis] = item.second;
      cases.push_back(t);
    }
  }
  auto empty = policyCase("empty_active_domain");
  empty.mask = {{false, false, false}};
  cases.push_back(empty);
  auto one = policyCase("single_E_active");
  one.mask = {{false, true, false}};
  one.metadata.std_xyz = {nan, 0.3, inf};
  cases.push_back(one);
  for (double bound : {10.0, std::nextafter(10.0, inf)}) {
    auto t = policyCase(bound == 10.0 ? "active_std_at_10" : "active_std_above_10");
    t.metadata.std_xyz[0] = bound;
    cases.push_back(t);
  }
  auto quality = policyCase("other_quality_remains_1p5");
  quality.metadata.quality_flag = "non_nominal_fixture";
  cases.push_back(quality);
  auto timing = policyCase("time_quality_remains_1p5");
  timing.metadata.time_diff_sec = 0.1;
  cases.push_back(timing);
  auto covariance = policyCase("covariance_missing_remains_1p5");
  covariance.metadata.covariance_available = false;
  cases.push_back(covariance);
  auto unavailable = policyCase("provider_unavailable_rejected");
  unavailable.metadata.provider_status = "unavailable";
  cases.push_back(unavailable);
  auto invalid = policyCase("invalid_source_rejected");
  invalid.metadata.valid = false;
  cases.push_back(invalid);
  auto oim = quality;
  oim.name = "oim_masks_lsim_change";
  oim.normalized = 7.0;
  cases.push_back(oim);
  auto cap = quality;
  cap.name = "cap_masks_lsim_change";
  cap.normalized = 100.0;
  cases.push_back(cap);
  auto off = policyCase("sa_off");
  off.config.enable_source_aware_weighting = false;
  cases.push_back(off);
  auto source_off = policyCase("source_off");
  source_off.config.sources[sourceIndex(source_off.metadata.source)].enabled = false;
  cases.push_back(source_off);
  auto lsim_off = policyCase("lsim_off");
  lsim_off.config.sources[sourceIndex(lsim_off.metadata.source)].lsim_enabled = false;
  cases.push_back(lsim_off);
  auto mode_off = policyCase("mode_off");
  mode_off.config.source_aware_mode = "off";
  cases.push_back(mode_off);
  const std::vector<std::pair<std::string, Vec3>> controls{
      {"nominal", {0.2, 0.3, 0.4}}, {"high_D", {0.2, 0.3, 999.0}},
      {"nan_N", {nan, 20.0, 999.0}}, {"nan_E", {20.0, nan, 999.0}},
      {"nan_D", {0.2, 0.3, nan}}, {"inf_D", {0.2, 0.3, inf}},
      {"zero_D", {0.2, 0.3, 0.0}}, {"negative_D", {0.2, 0.3, -2.0}}};
  for (bool legacy : {false, true}) {
    for (std::size_t source = 0; source < kMeasurementSourceCount; ++source) {
      for (const auto& item : controls) {
        auto t = policyCase(std::string("control3d_") + (legacy ? "legacy_" : "n6b_") +
                            toString(static_cast<MeasurementSource>(source)) + "_" + item.first);
        t.metadata.source = static_cast<MeasurementSource>(source);
        t.metadata.std_xyz = item.second;
        t.metadata.quality_flag = "non_nominal_fixture";
        t.metadata.sat_count = 7;
        t.mask = {{true, true, true}};
        t.three_dimensional_control = true;
        if (legacy) t.config.source_aware_policy_version = "legacy_fixture";
        cases.push_back(t);
      }
    }
  }
  return cases;
}

void runPolicyCases(const fs::path& output) {
  std::ofstream stream(output / "POLICY_RESULTS.jsonl");
  for (auto t : policyCases()) {
    const Vec3 original_std = t.metadata.std_xyz;
    std::array<bool, 3> actual_mask{{true, true, true}};
#ifdef N16_ACTIVE_AXES
    t.metadata.std_active_axes = t.mask;
    actual_mask = t.metadata.std_active_axes;
#endif
    ObservationInnovation innovation;
    innovation.dof = 2;
    innovation.normalized_innovation = t.normalized;
    innovation.nis = 2.0 * t.normalized * t.normalized;
    innovation.residual = {0.1, 0.2};
    innovation.residual_norm = std::sqrt(0.05);
    innovation.base_R_trace = 0.13;
    innovation.hph_trace = 0.2;
    innovation.innovation_cov_trace = 0.33;
    innovation.used_innovation_covariance = true;
    SourceAwarePolicy policy(t.config);
    const auto result = policy.evaluate(t.metadata, innovation);
    Json scientific;
    scientific.add("lsim_R_scale", result.lsim_R_scale).add("oim_R_scale", result.oim_R_scale)
      .add("combined_R_scale", result.combined_R_scale).add("lsim_score", result.lsim_score)
      .add("oim_score", result.oim_score).add("normalized_innovation", result.normalized_innovation)
      .add("nis", result.nis).add("dof", result.dof).add("source_cap", result.source_cap)
      .add("base_R_trace", result.base_R_trace).add("scaled_R_trace", result.scaled_R_trace)
      .add("accepted", result.accepted).add("rejected", result.rejected).add("reason_codes", result.reason_codes);
    Json row;
    row.add("case", t.name).add("data_mode", "synthetic_fixture_only")
      .add("source", toString(t.metadata.source)).add("requested_mask", t.mask).add("actual_mask", actual_mask)
      .add("std_xyz", t.metadata.std_xyz).add("std_bytes_preserved", std::memcmp(original_std.data(), t.metadata.std_xyz.data(), sizeof(Vec3)) == 0)
      .add("three_dimensional_control", t.three_dimensional_control)
      .add("metadata_summary", result.metadata_summary).raw("scientific", scientific.str());
    stream << row.str() << '\n';
  }
}

struct IntegrationCase {
  std::string name;
  double d = 999.0;
  bool horizontal_2d = true;
  bool vertical_sentinel = true;
  bool sa = true;
  bool source_enabled = true;
  std::string quality = "nominal";
  double velocity_jump = 0.0;
};

std::vector<IntegrationCase> integrationCases() {
  const double nan = std::numeric_limits<double>::quiet_NaN();
  const double inf = std::numeric_limits<double>::infinity();
  return {{"hv2d_sentinel999"}, {"hv2d_ordinary_D", 0.4, true, false},
          {"hv2d_nan_D", nan, true, false}, {"hv2d_inf_D", inf, true, false},
          {"hv2d_quality_1p5", 999.0, true, true, true, true, "non_nominal_fixture"},
          {"hv3d_ordinary_D", 0.4, false, false}, {"hv3d_sentinel_D", 999.0, false, true},
          {"hv2d_sa_off", 999.0, true, true, false},
          {"hv2d_source_off", 999.0, true, true, true, false},
          {"hv2d_cap_masked", 999.0, true, true, true, true, "non_nominal_fixture", 100.0}};
}

PortOptions engineOptions(const IntegrationCase& test) {
  PortOptions o;
  o.data_mode = "synthetic_fixture_only";
  o.synthetic_data_used = true;
  o.clean_final_v23_parity_mode = true;
  o.init_pos_std_m = {2.0, 3.0, 4.0};
  o.init_vel_std_mps = {0.5, 0.4, 0.3};
  o.init_att_std_rad = {0.05, 0.04, 0.03};
  auto& c = o.source_aware_policy_config;
  c.enable_source_aware_weighting = test.sa;
  c.source_aware_mode = "lsim_oim";
  c.source_aware_enable_rolling_innovation_baseline = false;
  c.sources[sourceIndex(MeasurementSource::kGo2HorizontalVelocity)].enabled = test.source_enabled;
  auto& h = o.go2_velocity_prior_diagnostic_config;
  h.enable_go2_velocity_prior_diagnostic = true;
  h.enable_go2_horizontal_velocity_prior = true;
  h.go2_diagnostic_prior_only = false;
  h.go2_velocity_prior_time_tolerance_sec = 0.001;
  h.go2_horizontal_velocity_prior_mode = test.horizontal_2d ? "horizontal_2d" : "fixture_actual_3d_branch";
  h.go2_horizontal_velocity_prior_vertical_disabled = test.vertical_sentinel;
  h.go2_horizontal_velocity_prior_source_aware_enabled = true;
  return o;
}

ImuData imu(double time) {
  ImuData i;
  i.time = time;
  i.dt = 0.01;
  i.dtheta = {1e-5, 2e-5, 3e-5};
  i.dvel = {1e-5, -2e-5, -0.0978};
  return i;
}

void emitState(std::ostream& out, const GIEngine& engine, int step) {
  const auto& s = engine.navState();
  out << step << ',' << engine.timestamp();
  auto emit = [&](const auto& v) { for (const auto x : v) out << ',' << x; };
  emit(s.pos_blh_rad_m); emit(s.vel_ned_mps); emit(s.euler_rad);
  out << ',' << s.qbn.w << ',' << s.qbn.x << ',' << s.qbn.y << ',' << s.qbn.z;
  for (const auto& row : s.cbn) emit(row);
  emit(s.imu_error.gyrbias); emit(s.imu_error.accbias); emit(s.imu_error.gyrscale); emit(s.imu_error.accscale);
  emit(engine.getCovariance());
  out << ',' << engine.propagationCount() << ',' << engine.updateCount() << ',' << engine.positionUpdateCount()
      << ',' << engine.sourceAwareEvaluationCount() << ',' << engine.sourceAwareWeightChangedCount()
      << ',' << engine.go2VelocityDiagnosticPriorUpdateCount() << ',' << engine.go2VelocityDiagnosticPriorRejectCount()
      << ',' << engine.covHealthFailCount() << '\n';
}

void runIntegration(const fs::path& root, const IntegrationCase& test, bool observe) {
  const auto output = root / test.name;
  fs::create_directories(output);
  if (observe) {
    setenv("LEGSA_V3_OBSERVER_DIR", (output / "observer").c_str(), 1);
    setenv("LEGSA_V3_OBSERVER_RUN_ID", test.name.c_str(), 1);
  } else {
    unsetenv("LEGSA_V3_OBSERVER_DIR");
    unsetenv("LEGSA_V3_OBSERVER_RUN_ID");
  }
  GIEngine engine(engineOptions(test));
  NavState state;
  state.pos_blh_rad_m = {0.5, 1.0, 10.0};
  state.vel_ned_mps = {0.1, -0.05, 0.0};
  state.euler_rad = {0.01, -0.02, 0.03};
  engine.initialize(state);
  Go2VelocityDiagnosticPriorMeasurement h;
  h.time = 0.02;
  h.velocity_ned_mps = {0.12 + test.velocity_jump, -0.04 - test.velocity_jump, 0.01};
  h.std_ned_mps = {0.2, 0.3, test.d};
  h.source_status = "active";
  h.quality_flag = test.quality;
  h.diagnostic_only = false;
  h.update_flag = true;
  h.prior_policy = "synthetic_n16_fixture";
  Go2VelocityDiagnosticPriorStatus status;
  status.solver_enabled = true;
  status.provider_status = "available";
  engine.setGo2VelocityDiagnosticPriors({h}, status);
  engine.addImuData(imu(0.0), true);
  std::ofstream output_state(output / "SCIENTIFIC_STATE.csv");
  output_state << std::setprecision(17);
  emitState(output_state, engine, 0);
  for (int step = 1; step <= 3; ++step) {
    if (step == 2) {
      GnssData g;
      g.time = 0.02;
      g.blh_rad_m = state.pos_blh_rad_m;
      g.std_ned_m = {0.2, 0.3, 0.4};
      g.validity_explicit = true;
      g.has_position = true;
      g.has_velocity = false;
      g.has_yaw = false;
      engine.addGnssData(g);
    }
    engine.addImuData(imu(step * 0.01));
    engine.newImuProcess();
    emitState(output_state, engine, step);
  }
  if (engine.go2VelocityDiagnosticPriorUpdateCount() != 1)
    throw std::runtime_error("Integration fixture expected exactly one HV update: " + test.name);
}

int main(int argc, char** argv) {
  if (argc != 3) return 2;
  try {
    const fs::path output(argv[1]);
    if (fs::exists(output)) throw std::runtime_error("Refuse existing fixture output");
    fs::create_directories(output);
    runPolicyCases(output);
    for (const auto& test : integrationCases()) runIntegration(output, test, std::string(argv[2]) == "observer_on");
    std::cout << "synthetic_policy_scenarios=" << policyCases().size()
              << " synthetic_integration_scenarios=" << integrationCases().size()
              << " real_native_calls=0\n";
    return 0;
  } catch (const std::exception& error) {
    std::cerr << error.what() << '\n';
    return 1;
  }
}
