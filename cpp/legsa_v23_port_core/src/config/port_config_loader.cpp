// LegSA-GINS source-backed port file.
// Source reference: KF-GINS-graduation-design / final_v23 reference.
// Source commit: 5a4471efd4fcfcdc31e258a677af354c652ff16f.
// Port role: mature GNSS/INS backbone implementation, not proposed novelty.
// Boundary: no final_v23 output substitution, no trace solver input.
// 中文说明：该文件为受控移植的组合导航骨架代码，后续创新因子将在该骨架通过 parity 后再接入。

#include "legsa_v23_port_core/config/port_config_loader.hpp"

#include "legsa_v23_port_core/common/earth.hpp"

#include <algorithm>
#include <array>
#include <cctype>
#include <fstream>
#include <sstream>
#include <stdexcept>
#include <unordered_map>
#include <utility>

namespace legsa_v23_port_core {
namespace {

std::string trim(std::string value) {
  auto not_space = [](unsigned char ch) { return !std::isspace(ch); };
  value.erase(value.begin(), std::find_if(value.begin(), value.end(), not_space));
  value.erase(std::find_if(value.rbegin(), value.rend(), not_space).base(), value.end());
  return value;
}

std::string normalizeLine(std::string line) {
  const auto hash = line.find('#');
  if (hash != std::string::npos) {
    line = line.substr(0, hash);
  }
  std::replace(line.begin(), line.end(), '[', ' ');
  std::replace(line.begin(), line.end(), ']', ' ');
  std::replace(line.begin(), line.end(), ',', ' ');
  return trim(line);
}

std::vector<double> parseVector(std::string value) {
  value = normalizeLine(value);
  std::istringstream stream(value);
  std::vector<double> out;
  double x = 0.0;
  while (stream >> x) {
    out.push_back(x);
  }
  return out;
}

Vec3 vecOrDefault(const std::unordered_map<std::string, std::string>& kv, const std::string& key, Vec3 fallback) {
  auto it = kv.find(key);
  if (it == kv.end()) {
    return fallback;
  }
  const std::vector<double> values = parseVector(it->second);
  if (values.size() < 3) {
    return fallback;
  }
  return makeVec3(values[0], values[1], values[2]);
}

Vec3 vecOrDefault(const std::unordered_map<std::string, std::string>& kv,
                  const std::string& key,
                  const std::string& alias,
                  Vec3 fallback) {
  auto it = kv.find(key);
  if (it == kv.end()) {
    it = kv.find(alias);
  }
  if (it == kv.end()) {
    return fallback;
  }
  const std::vector<double> values = parseVector(it->second);
  if (values.size() < 3) {
    return fallback;
  }
  return makeVec3(values[0], values[1], values[2]);
}

double scalarOrDefault(const std::unordered_map<std::string, std::string>& kv, const std::string& key, double fallback) {
  auto it = kv.find(key);
  if (it == kv.end()) {
    return fallback;
  }
  std::istringstream stream(it->second);
  double value = fallback;
  stream >> value;
  return value;
}

bool boolOrDefault(const std::unordered_map<std::string, std::string>& kv, const std::string& key, bool fallback) {
  auto it = kv.find(key);
  if (it == kv.end()) {
    return fallback;
  }
  std::string value = trim(it->second);
  std::transform(value.begin(), value.end(), value.begin(), [](unsigned char ch) { return std::tolower(ch); });
  if (value == "true" || value == "1" || value == "yes" || value == "on") {
    return true;
  }
  if (value == "false" || value == "0" || value == "no" || value == "off") {
    return false;
  }
  return fallback;
}

std::string stringOrDefault(const std::unordered_map<std::string, std::string>& kv,
                            const std::string& key,
                            const std::string& fallback) {
  auto it = kv.find(key);
  if (it == kv.end()) {
    return fallback;
  }
  std::string value = trim(it->second);
  // 中文说明：runtime yaml-like 配置可能给路径加引号；去掉外层引号后再打开文件。
  if (value.size() >= 2 && ((value.front() == '"' && value.back() == '"') ||
                            (value.front() == '\'' && value.back() == '\''))) {
    value = value.substr(1, value.size() - 2);
  }
  return value;
}

std::unordered_map<std::string, std::string> readKeyValues(const std::string& path) {
  std::ifstream input(path);
  if (!input) {
    throw std::runtime_error("failed to open config: " + path);
  }
  std::unordered_map<std::string, std::string> kv;
  std::string line;
  while (std::getline(input, line)) {
    line = normalizeLine(line);
    if (line.empty()) {
      continue;
    }
    auto pos = line.find('=');
    if (pos == std::string::npos) {
      pos = line.find(':');
    }
    if (pos == std::string::npos) {
      continue;
    }
    kv[trim(line.substr(0, pos))] = trim(line.substr(pos + 1));
  }
  return kv;
}

}  // namespace

PortOptions PortConfigLoader::loadKeyValue(const std::string& path) {
  return loadYamlLike(path);
}

// 中文说明：轻量 YAML-like parser 支持 R2 所需字段；不读取 trace，也不读取 final_v23 输出。
PortOptions PortConfigLoader::loadYamlLike(const std::string& path) {
  const auto kv = readKeyValues(path);
  PortOptions options;
  options.run_label = stringOrDefault(kv, "run_label", "N4H4R2_config_run");
  options.algorithm_id = stringOrDefault(kv, "algorithm_id", options.algorithm_id);
  options.qa_fallback_config.algorithm_id = options.algorithm_id;
  options.imu_path = stringOrDefault(kv, "imupath", stringOrDefault(kv, "imu_path", ""));
  options.gnss_path = stringOrDefault(kv, "gnsspath", stringOrDefault(kv, "gnss_path", ""));
  options.clean_input_provenance_label =
      stringOrDefault(kv, "clean_input_provenance_label", options.clean_input_provenance_label);
  options.config_policy_evidence_status =
      stringOrDefault(kv, "config_policy_evidence_status", options.config_policy_evidence_status);

  Vec3 initpos = vecOrDefault(kv, "initpos", options.init_pos_blh_rad_m);
  initpos[0] *= D2R;
  initpos[1] *= D2R;
  options.init_pos_blh_rad_m = initpos;
  options.init_vel_ned_mps = vecOrDefault(kv, "initvel", options.init_vel_ned_mps);
  options.init_att_rad = scale(vecOrDefault(kv, "initatt", options.init_att_rad), D2R);
  options.antlever_m = vecOrDefault(kv, "antlever", options.antlever_m);
  options.init_pos_std_m = vecOrDefault(kv, "initposstd", options.init_pos_std_m);
  options.init_vel_std_mps = vecOrDefault(kv, "initvelstd", options.init_vel_std_mps);
  options.init_att_std_rad = scale(vecOrDefault(kv, "initattstd", scale(options.init_att_std_rad, R2D)), D2R);

  options.init_imu_error.gyrbias = scale(vecOrDefault(kv, "initgyrbias", options.init_imu_error.gyrbias), D2R / 3600.0);
  options.init_imu_error.accbias = scale(vecOrDefault(kv, "initaccbias", options.init_imu_error.accbias), 1.0e-5);
  options.init_imu_error.gyrscale = scale(vecOrDefault(kv, "initgyrscale", options.init_imu_error.gyrscale), 1.0e-6);
  options.init_imu_error.accscale = scale(vecOrDefault(kv, "initaccscale", options.init_imu_error.accscale), 1.0e-6);

  options.imunoise.gyr_arw = scale(vecOrDefault(kv, "arw", scale(options.imunoise.gyr_arw, 60.0 / D2R)), D2R / 60.0);
  options.imunoise.acc_vrw = scale(vecOrDefault(kv, "vrw", scale(options.imunoise.acc_vrw, 60.0)), 1.0 / 60.0);
  options.imunoise.gyrbias_std = scale(vecOrDefault(kv, "gbstd", scale(options.imunoise.gyrbias_std, 3600.0 / D2R)), D2R / 3600.0);
  options.imunoise.accbias_std = scale(vecOrDefault(kv, "abstd", scale(options.imunoise.accbias_std, 1.0e5)), 1.0e-5);
  options.imunoise.gyrscale_std = scale(vecOrDefault(kv, "gsstd", scale(options.imunoise.gyrscale_std, 1.0e6)), 1.0e-6);
  options.imunoise.accscale_std = scale(vecOrDefault(kv, "asstd", scale(options.imunoise.accscale_std, 1.0e6)), 1.0e-6);
  options.imunoise.corr_time = scalarOrDefault(kv, "corrtime", options.imunoise.corr_time / 3600.0) * 3600.0;

  options.init_imu_error_std.gyrbias =
      scale(vecOrDefault(kv, "initgyrbiasstd", "initbgstd", scale(options.imunoise.gyrbias_std, 3600.0 / D2R)),
            D2R / 3600.0);
  options.init_imu_error_std.accbias =
      scale(vecOrDefault(kv, "initaccbiasstd", "initbastd", scale(options.imunoise.accbias_std, 1.0e5)), 1.0e-5);
  options.init_imu_error_std.gyrscale =
      scale(vecOrDefault(kv, "initgyrscalestd", "initsgstd", scale(options.imunoise.gyrscale_std, 1.0e6)),
            1.0e-6);
  options.init_imu_error_std.accscale =
      scale(vecOrDefault(kv, "initaccscalestd", "initsastd", scale(options.imunoise.accscale_std, 1.0e6)),
            1.0e-6);

  options.starttime = scalarOrDefault(kv, "starttime", options.starttime);
  options.endtime = scalarOrDefault(kv, "endtime", options.endtime);
  options.imudatalen = static_cast<int>(scalarOrDefault(kv, "imudatalen", options.imudatalen));
  options.imudatarate = scalarOrDefault(kv, "imudatarate", options.imudatarate);
  // 中文说明：receiver-native velocity 是 baseline 松组合速度观测，N5C 仅为诊断可关闭。
  options.enable_receiver_velocity_update =
      boolOrDefault(kv, "enable_receiver_velocity_update", options.enable_receiver_velocity_update);
  // 中文说明：N5D velocity stress 只诊断 raw Doppler 独立约束能力，不代表真实传感器故障模型。
  options.receiver_velocity_stress_mode =
      stringOrDefault(kv, "receiver_velocity_stress_mode", options.receiver_velocity_stress_mode);
  options.receiver_velocity_std_scale =
      scalarOrDefault(kv, "receiver_velocity_std_scale", options.receiver_velocity_std_scale);
  options.receiver_velocity_outage_start_sec =
      scalarOrDefault(kv, "receiver_velocity_outage_start_sec", options.receiver_velocity_outage_start_sec);
  options.receiver_velocity_outage_duration_sec =
      scalarOrDefault(kv, "receiver_velocity_outage_duration_sec", options.receiver_velocity_outage_duration_sec);
  options.receiver_velocity_additive_noise_std_mps =
      scalarOrDefault(kv, "receiver_velocity_additive_noise_std_mps",
                      options.receiver_velocity_additive_noise_std_mps);
  options.receiver_velocity_additive_noise_seed =
      static_cast<int>(scalarOrDefault(kv, "receiver_velocity_additive_noise_seed",
                                       static_cast<double>(options.receiver_velocity_additive_noise_seed)));
  options.diagnostic_stress_only = boolOrDefault(kv, "diagnostic_stress_only", options.diagnostic_stress_only);
  options.diagnostic_only = boolOrDefault(kv, "diagnostic_only", options.diagnostic_only);
  options.no_outperform_final_v23_claim =
      boolOrDefault(kv, "no_outperform_final_v23_claim", options.no_outperform_final_v23_claim);
  options.ablation_variant = stringOrDefault(kv, "raw_doppler_diagnostic_variant_label", options.ablation_variant);
  options.ablation_variant = stringOrDefault(kv, "ablation_variant", options.ablation_variant);
  options.qa_fallback_config.qa_passive_logging_enabled =
      boolOrDefault(kv, "qa_passive_logging_enabled", options.qa_fallback_config.qa_passive_logging_enabled);
  options.qa_fallback_config.enable_qa_fallback =
      boolOrDefault(kv, "enable_qa_fallback", options.qa_fallback_config.enable_qa_fallback);
  options.qa_fallback_config.qa_active_mode =
      boolOrDefault(kv, "qa_active_mode", options.qa_fallback_config.qa_active_mode);
  if (options.algorithm_id == quality_aware::kLegsaQaFallbackEkf) {
    options.qa_fallback_config.enable_qa_fallback = true;
    options.qa_fallback_config.qa_active_mode = true;
    options.qa_fallback_config.qa_passive_logging_enabled = true;
  }
  options.qa_fallback_config.expected_a1_baseline_m =
      scalarOrDefault(kv, "qa_expected_a1_baseline_m", options.qa_fallback_config.expected_a1_baseline_m);
  options.qa_fallback_config.a1_baseline_tolerance_m =
      scalarOrDefault(kv, "qa_a1_baseline_tolerance_m", options.qa_fallback_config.a1_baseline_tolerance_m);
  options.qa_fallback_config.a1_min_valid_ratio =
      scalarOrDefault(kv, "qa_a1_min_valid_ratio", options.qa_fallback_config.a1_min_valid_ratio);
  options.qa_fallback_config.a1_yaw_std_degraded_deg =
      scalarOrDefault(kv, "qa_a1_yaw_std_degraded_deg", options.qa_fallback_config.a1_yaw_std_degraded_deg);
  options.qa_fallback_config.a1_yaw_std_invalid_deg =
      scalarOrDefault(kv, "qa_a1_yaw_std_invalid_deg", options.qa_fallback_config.a1_yaw_std_invalid_deg);
  options.qa_fallback_config.a1_yaw_residual_degraded_deg =
      scalarOrDefault(kv, "qa_a1_yaw_residual_degraded_deg",
                      options.qa_fallback_config.a1_yaw_residual_degraded_deg);
  options.qa_fallback_config.a1_yaw_residual_invalid_deg =
      scalarOrDefault(kv, "qa_a1_yaw_residual_invalid_deg",
                      options.qa_fallback_config.a1_yaw_residual_invalid_deg);
  options.qa_fallback_config.a1_yaw_jump_invalid_deg =
      scalarOrDefault(kv, "qa_a1_yaw_jump_invalid_deg", options.qa_fallback_config.a1_yaw_jump_invalid_deg);
  options.qa_fallback_config.gnss_pos_std_h_degraded_m =
      scalarOrDefault(kv, "qa_gnss_pos_std_h_degraded_m",
                      options.qa_fallback_config.gnss_pos_std_h_degraded_m);
  options.qa_fallback_config.gnss_pos_std_u_degraded_m =
      scalarOrDefault(kv, "qa_gnss_pos_std_u_degraded_m",
                      options.qa_fallback_config.gnss_pos_std_u_degraded_m);
  options.qa_fallback_config.gnss_pos_std_h_invalid_m =
      scalarOrDefault(kv, "qa_gnss_pos_std_h_invalid_m", options.qa_fallback_config.gnss_pos_std_h_invalid_m);
  options.qa_fallback_config.gnss_pos_std_u_invalid_m =
      scalarOrDefault(kv, "qa_gnss_pos_std_u_invalid_m", options.qa_fallback_config.gnss_pos_std_u_invalid_m);
  options.qa_fallback_config.raw_doppler_min_count =
      scalarOrDefault(kv, "qa_raw_doppler_min_count", options.qa_fallback_config.raw_doppler_min_count);
  options.qa_fallback_config.recovery_required_consecutive_a1 =
      static_cast<int>(scalarOrDefault(kv,
                                       "qa_recovery_required_consecutive_a1",
                                       static_cast<double>(options.qa_fallback_config.recovery_required_consecutive_a1)));
  options.qa_fallback_config.recovery_yaw_residual_gate_deg =
      scalarOrDefault(kv, "qa_recovery_yaw_residual_gate_deg",
                      options.qa_fallback_config.recovery_yaw_residual_gate_deg);
  options.qa_fallback_config.recovery_yaw_jump_gate_deg =
      scalarOrDefault(kv, "qa_recovery_yaw_jump_gate_deg", options.qa_fallback_config.recovery_yaw_jump_gate_deg);
  options.qa_fallback_config.recovery_initial_yaw_r_scale =
      scalarOrDefault(kv, "qa_recovery_initial_yaw_r_scale",
                      options.qa_fallback_config.recovery_initial_yaw_r_scale);
  options.qa_fallback_config.s1_yaw_r_scale =
      scalarOrDefault(kv, "qa_s1_yaw_r_scale", options.qa_fallback_config.s1_yaw_r_scale);
  options.qa_fallback_config.s3_gnss_pos_r_scale =
      scalarOrDefault(kv, "qa_s3_gnss_pos_r_scale", options.qa_fallback_config.s3_gnss_pos_r_scale);
  options.qa_fallback_config.s4_gnss_pos_r_scale =
      scalarOrDefault(kv, "qa_s4_gnss_pos_r_scale", options.qa_fallback_config.s4_gnss_pos_r_scale);
  options.qa_fallback_config.a1_relpos_diff_valid_default =
      boolOrDefault(kv, "qa_a1_relpos_diff_valid_default",
                    options.qa_fallback_config.a1_relpos_diff_valid_default);
  options.qa_fallback_config.a1_baseline_m_default =
      scalarOrDefault(kv, "qa_a1_baseline_m_default", options.qa_fallback_config.a1_baseline_m_default);
  options.qa_fallback_config.a1_baseline_default_available =
      boolOrDefault(kv, "qa_a1_baseline_default_available",
                    options.qa_fallback_config.a1_baseline_default_available);
  options.qa_fallback_config.a1_valid_ratio_default =
      scalarOrDefault(kv, "qa_a1_valid_ratio_default", options.qa_fallback_config.a1_valid_ratio_default);
  options.qa_fallback_config.a1_valid_ratio_default_available =
      boolOrDefault(kv, "qa_a1_valid_ratio_default_available",
                    options.qa_fallback_config.a1_valid_ratio_default_available);
  options.qa_fallback_config.recovery_max_yaw_correction_deg =
      scalarOrDefault(kv, "qa_recovery_max_yaw_correction_deg",
                      options.qa_fallback_config.recovery_max_yaw_correction_deg);
  options.qa_fallback_config.a1_quality_source =
      stringOrDefault(kv, "qa_a1_quality_source", options.qa_fallback_config.a1_quality_source);
  options.qa_fallback_layer_present =
      options.qa_fallback_config.qa_passive_logging_enabled ||
      options.qa_fallback_config.enable_qa_fallback ||
      options.qa_fallback_config.qa_active_mode ||
      options.algorithm_id == quality_aware::kLegsaQaFallbackEkf;
  options.qa_fallback_active =
      options.qa_fallback_config.enable_qa_fallback ||
      options.qa_fallback_config.qa_active_mode ||
      options.algorithm_id == quality_aware::kLegsaQaFallbackEkf;
  options.qa_passive_logging_enabled = options.qa_fallback_config.qa_passive_logging_enabled;
  // 中文说明：N7C6 joint factor 默认关闭；开启时只复用 roll/pitch 2D 与 horizontal velocity 2D update。
  options.enable_go2_proprioceptive_joint_factor =
      boolOrDefault(kv,
                    "enable_go2_proprioceptive_joint_factor",
                    options.enable_go2_proprioceptive_joint_factor);
  options.go2_proprioceptive_joint_factor_path =
      stringOrDefault(kv,
                      "go2_proprioceptive_joint_factor_path",
                      options.go2_proprioceptive_joint_factor_path);
  options.go2_proprioceptive_joint_factor_mode =
      stringOrDefault(kv,
                      "go2_proprioceptive_joint_factor_mode",
                      options.go2_proprioceptive_joint_factor_mode);
  options.go2_proprioceptive_joint_factor_policy =
      stringOrDefault(kv,
                      "go2_proprioceptive_joint_factor_policy",
                      options.go2_proprioceptive_joint_factor_policy);
  options.go2_proprioceptive_source_aware_enabled =
      boolOrDefault(kv,
                    "go2_proprioceptive_source_aware_enabled",
                    options.go2_proprioceptive_source_aware_enabled);
  options.go2_vertical_velocity_prior_enabled =
      boolOrDefault(kv,
                    "go2_vertical_velocity_prior_enabled",
                    options.go2_vertical_velocity_prior_enabled);
  // 中文说明：raw Doppler 默认关闭；只有 runtime config 明确启用且 provider-backed CSV 有效时才进入 EKF。
  options.raw_doppler_config.enable_raw_doppler =
      boolOrDefault(kv, "enable_raw_doppler", options.raw_doppler_config.enable_raw_doppler);
  options.raw_doppler_config.raw_doppler_factor_path =
      stringOrDefault(kv, "raw_doppler_factor_path", options.raw_doppler_config.raw_doppler_factor_path);
  options.raw_doppler_config.raw_doppler_factor_source =
      stringOrDefault(kv, "raw_doppler_factor_source", options.raw_doppler_config.raw_doppler_factor_source);
  options.raw_doppler_config.raw_doppler_time_tolerance_sec =
      scalarOrDefault(kv, "raw_doppler_time_tolerance_sec",
                      options.raw_doppler_config.raw_doppler_time_tolerance_sec);
  options.raw_doppler_config.raw_doppler_min_sat =
      static_cast<std::size_t>(std::max(0.0, scalarOrDefault(kv, "raw_doppler_min_sat",
                                                             static_cast<double>(options.raw_doppler_config.raw_doppler_min_sat))));
  options.raw_doppler_config.raw_doppler_residual_gate_mps =
      scalarOrDefault(kv, "raw_doppler_residual_gate_mps",
                      options.raw_doppler_config.raw_doppler_residual_gate_mps);
  options.raw_doppler_config.raw_doppler_R_scale =
      scalarOrDefault(kv, "raw_doppler_R_scale", options.raw_doppler_config.raw_doppler_R_scale);
  options.raw_doppler_config.raw_doppler_mode =
      stringOrDefault(kv, "raw_doppler_mode", options.raw_doppler_config.raw_doppler_mode);
  // 中文说明：N7A Go2 attitude weak prior 默认关闭；只读取 builder 生成的 runtime-only CSV。
  options.go2_attitude_prior_config.enable_go2_attitude_weak_prior =
      boolOrDefault(kv,
                    "enable_go2_attitude_weak_prior",
                    options.go2_attitude_prior_config.enable_go2_attitude_weak_prior);
  options.go2_attitude_prior_config.go2_attitude_prior_path =
      stringOrDefault(kv,
                      "go2_attitude_prior_path",
                      options.go2_attitude_prior_config.go2_attitude_prior_path);
  options.go2_attitude_prior_config.go2_attitude_prior_time_tolerance_sec =
      scalarOrDefault(kv,
                      "go2_attitude_prior_time_tolerance_sec",
                      options.go2_attitude_prior_config.go2_attitude_prior_time_tolerance_sec);
  options.go2_attitude_prior_config.go2_attitude_prior_std_roll_deg =
      scalarOrDefault(kv,
                      "go2_attitude_prior_std_roll_deg",
                      options.go2_attitude_prior_config.go2_attitude_prior_std_roll_deg);
  options.go2_attitude_prior_config.go2_attitude_prior_std_pitch_deg =
      scalarOrDefault(kv,
                      "go2_attitude_prior_std_pitch_deg",
                      options.go2_attitude_prior_config.go2_attitude_prior_std_pitch_deg);
  options.go2_attitude_prior_config.go2_attitude_prior_sourceaware =
      boolOrDefault(kv,
                    "go2_attitude_prior_sourceaware",
                    options.go2_attitude_prior_config.go2_attitude_prior_sourceaware);
  options.go2_attitude_prior_config.go2_attitude_prior_diagnostic_only =
      boolOrDefault(kv,
                    "go2_attitude_prior_diagnostic_only",
                    options.go2_attitude_prior_config.go2_attitude_prior_diagnostic_only);
  options.go2_attitude_prior_config.go2_position_prior_enabled =
      boolOrDefault(kv,
                    "go2_position_prior_enabled",
                    options.go2_attitude_prior_config.go2_position_prior_enabled);
  options.go2_attitude_prior_config.go2_velocity_prior_enabled =
      boolOrDefault(kv,
                    "go2_velocity_prior_enabled",
                    options.go2_attitude_prior_config.go2_velocity_prior_enabled);
  options.go2_attitude_prior_config.go2_yaw_prior_enabled =
      boolOrDefault(kv,
                    "go2_yaw_prior_enabled",
                    options.go2_attitude_prior_config.go2_yaw_prior_enabled);
  // 中文说明：N7B3 diagnostic velocity prior 默认关闭；只能读取 builder 生成的 runtime-only CSV。
  options.go2_velocity_prior_diagnostic_config.enable_go2_velocity_prior_diagnostic =
      boolOrDefault(kv,
                    "enable_go2_velocity_prior_diagnostic",
                    options.go2_velocity_prior_diagnostic_config.enable_go2_velocity_prior_diagnostic);
  options.go2_velocity_prior_diagnostic_config.enable_go2_horizontal_velocity_prior =
      boolOrDefault(kv,
                    "enable_go2_horizontal_velocity_prior",
                    options.go2_velocity_prior_diagnostic_config.enable_go2_horizontal_velocity_prior);
  if (options.go2_velocity_prior_diagnostic_config.enable_go2_horizontal_velocity_prior) {
    options.go2_velocity_prior_diagnostic_config.enable_go2_velocity_prior_diagnostic = true;
  }
  options.go2_velocity_prior_diagnostic_config.go2_velocity_prior_diagnostic_path =
      stringOrDefault(kv,
                      "go2_velocity_prior_diagnostic_path",
                      options.go2_velocity_prior_diagnostic_config.go2_velocity_prior_diagnostic_path);
  options.go2_velocity_prior_diagnostic_config.go2_horizontal_velocity_prior_path =
      stringOrDefault(kv,
                      "go2_horizontal_velocity_prior_path",
                      options.go2_velocity_prior_diagnostic_config.go2_horizontal_velocity_prior_path);
  if (!options.go2_velocity_prior_diagnostic_config.go2_horizontal_velocity_prior_path.empty()) {
    options.go2_velocity_prior_diagnostic_config.go2_velocity_prior_diagnostic_path =
        options.go2_velocity_prior_diagnostic_config.go2_horizontal_velocity_prior_path;
  }
  options.go2_velocity_prior_diagnostic_config.go2_velocity_prior_time_tolerance_sec =
      scalarOrDefault(kv,
                      "go2_velocity_prior_time_tolerance_sec",
                      options.go2_velocity_prior_diagnostic_config.go2_velocity_prior_time_tolerance_sec);
  options.go2_velocity_prior_diagnostic_config.go2_velocity_prior_std_scale =
      scalarOrDefault(kv,
                      "go2_velocity_prior_std_scale",
                      options.go2_velocity_prior_diagnostic_config.go2_velocity_prior_std_scale);
  options.go2_velocity_prior_diagnostic_config.go2_velocity_prior_std_scale =
      scalarOrDefault(kv,
                      "go2_horizontal_velocity_prior_std_scale",
                      options.go2_velocity_prior_diagnostic_config.go2_velocity_prior_std_scale);
  options.go2_velocity_prior_diagnostic_config.go2_diagnostic_prior_only =
      boolOrDefault(kv,
                    "go2_diagnostic_prior_only",
                    options.go2_velocity_prior_diagnostic_config.go2_diagnostic_prior_only);
  options.go2_velocity_prior_diagnostic_config.go2_horizontal_velocity_prior_vertical_disabled =
      boolOrDefault(kv,
                    "go2_horizontal_velocity_prior_vertical_disabled",
                    options.go2_velocity_prior_diagnostic_config.go2_horizontal_velocity_prior_vertical_disabled);
  options.go2_velocity_prior_diagnostic_config.go2_horizontal_velocity_prior_source_aware_enabled =
      boolOrDefault(kv,
                    "go2_horizontal_velocity_prior_source_aware_enabled",
                    options.go2_velocity_prior_diagnostic_config.go2_horizontal_velocity_prior_source_aware_enabled);
  options.go2_velocity_prior_diagnostic_config.go2_horizontal_velocity_prior_mode =
      stringOrDefault(kv,
                      "go2_horizontal_velocity_prior_mode",
                      options.go2_velocity_prior_diagnostic_config.go2_horizontal_velocity_prior_mode);
  options.go2_velocity_prior_diagnostic_config.go2_horizontal_velocity_adaptive_std_enabled =
      boolOrDefault(kv,
                    "go2_horizontal_velocity_adaptive_std_enabled",
                    options.go2_velocity_prior_diagnostic_config.go2_horizontal_velocity_adaptive_std_enabled);
  options.go2_velocity_prior_diagnostic_config.go2_horizontal_velocity_bounded_std_policy =
      stringOrDefault(kv,
                      "go2_horizontal_velocity_bounded_std_policy",
                      options.go2_velocity_prior_diagnostic_config.go2_horizontal_velocity_bounded_std_policy);
  options.go2_velocity_prior_diagnostic_config.go2_horizontal_velocity_strength_policy =
      stringOrDefault(kv,
                      "go2_horizontal_velocity_strength_policy",
                      options.go2_velocity_prior_diagnostic_config.go2_horizontal_velocity_strength_policy);
  options.go2_readiness_lsim_metadata_config.enable_go2_readiness_lsim_metadata =
      boolOrDefault(kv,
                    "enable_go2_readiness_lsim_metadata",
                    options.go2_readiness_lsim_metadata_config.enable_go2_readiness_lsim_metadata);
  options.go2_readiness_lsim_metadata_config.go2_readiness_lsim_metadata_path =
      stringOrDefault(kv,
                      "go2_readiness_lsim_metadata_path",
                      options.go2_readiness_lsim_metadata_config.go2_readiness_lsim_metadata_path);
  options.go2_readiness_lsim_metadata_config.go2_readiness_lsim_time_tolerance_sec =
      scalarOrDefault(kv,
                      "go2_readiness_lsim_time_tolerance_sec",
                      options.go2_readiness_lsim_metadata_config.go2_readiness_lsim_time_tolerance_sec);
  options.go2_readiness_lsim_metadata_config.go2_readiness_lsim_default_closed =
      boolOrDefault(kv,
                    "go2_readiness_lsim_default_closed",
                    options.go2_readiness_lsim_metadata_config.go2_readiness_lsim_default_closed);
  options.go2_yaw_rate_prior_diagnostic_config.enable_go2_yaw_rate_prior_diagnostic =
      boolOrDefault(kv,
                    "enable_go2_yaw_rate_prior_diagnostic",
                    options.go2_yaw_rate_prior_diagnostic_config.enable_go2_yaw_rate_prior_diagnostic);
  options.go2_yaw_rate_prior_diagnostic_config.go2_yaw_rate_prior_diagnostic_path =
      stringOrDefault(kv,
                      "go2_yaw_rate_prior_diagnostic_path",
                      options.go2_yaw_rate_prior_diagnostic_config.go2_yaw_rate_prior_diagnostic_path);
  options.go2_yaw_rate_prior_diagnostic_config.go2_diagnostic_prior_only =
      boolOrDefault(kv,
                    "go2_diagnostic_prior_only",
                    options.go2_yaw_rate_prior_diagnostic_config.go2_diagnostic_prior_only);
  options.go2_diagnostic_prior_only = boolOrDefault(kv, "go2_diagnostic_prior_only", options.go2_diagnostic_prior_only);
  // 中文说明：N6A source-aware 默认关闭；启用后只在 EKFUpdate 前放大 R，不读取 trace/final_v23 输出。
  options.source_aware_policy_config.enable_source_aware_weighting =
      boolOrDefault(kv,
                    "enable_source_aware_weighting",
                    options.source_aware_policy_config.enable_source_aware_weighting);
  options.source_aware_policy_config.source_aware_policy_version =
      stringOrDefault(kv,
                      "source_aware_policy_version",
                      options.source_aware_policy_config.source_aware_policy_version);
  options.source_aware_policy_config.source_aware_mode =
      stringOrDefault(kv, "source_aware_mode", options.source_aware_policy_config.source_aware_mode);
  options.source_aware_policy_config.source_aware_max_R_scale =
      scalarOrDefault(kv,
                      "source_aware_max_R_scale",
                      options.source_aware_policy_config.source_aware_max_R_scale);
  options.source_aware_policy_config.source_aware_global_cap =
      scalarOrDefault(kv,
                      "source_aware_global_cap",
                      options.source_aware_policy_config.source_aware_max_R_scale);
  options.source_aware_policy_config.source_aware_use_innovation_covariance =
      boolOrDefault(kv,
                    "source_aware_use_innovation_covariance",
                    options.source_aware_policy_config.source_aware_use_innovation_covariance);
  options.source_aware_policy_config.source_aware_deadband_normalized =
      scalarOrDefault(kv,
                      "source_aware_deadband_normalized",
                      options.source_aware_policy_config.source_aware_deadband_normalized);
  options.source_aware_policy_config.source_aware_moderate_normalized =
      scalarOrDefault(kv,
                      "source_aware_moderate_normalized",
                      options.source_aware_policy_config.source_aware_moderate_normalized);
  options.source_aware_policy_config.source_aware_strong_normalized =
      scalarOrDefault(kv,
                      "source_aware_strong_normalized",
                      options.source_aware_policy_config.source_aware_strong_normalized);
  options.source_aware_policy_config.source_aware_receiver_position_cap =
      scalarOrDefault(kv,
                      "source_aware_receiver_position_cap",
                      options.source_aware_policy_config.source_aware_receiver_position_cap);
  options.source_aware_policy_config.source_aware_receiver_velocity_cap =
      scalarOrDefault(kv,
                      "source_aware_receiver_velocity_cap",
                      options.source_aware_policy_config.source_aware_receiver_velocity_cap);
  options.source_aware_policy_config.source_aware_dual_yaw_cap =
      scalarOrDefault(kv,
                      "source_aware_dual_yaw_cap",
                      options.source_aware_policy_config.source_aware_dual_yaw_cap);
  options.source_aware_policy_config.source_aware_raw_doppler_cap =
      scalarOrDefault(kv,
                      "source_aware_raw_doppler_cap",
                      options.source_aware_policy_config.source_aware_raw_doppler_cap);
  options.source_aware_policy_config.source_aware_go2_attitude_cap =
      scalarOrDefault(kv,
                      "source_aware_go2_attitude_cap",
                      options.source_aware_policy_config.source_aware_go2_attitude_cap);
  options.source_aware_policy_config.source_aware_go2_horizontal_velocity_cap =
      scalarOrDefault(kv,
                      "source_aware_go2_horizontal_velocity_cap",
                      options.source_aware_policy_config.source_aware_go2_horizontal_velocity_cap);
  options.source_aware_policy_config.source_aware_go2_readiness_lsim_enabled =
      boolOrDefault(kv,
                    "source_aware_go2_readiness_lsim_enabled",
                    options.source_aware_policy_config.source_aware_go2_readiness_lsim_enabled);
  options.source_aware_policy_config.source_aware_go2_readiness_low_scale =
      scalarOrDefault(kv,
                      "source_aware_go2_readiness_low_scale",
                      options.source_aware_policy_config.source_aware_go2_readiness_low_scale);
  options.source_aware_policy_config.source_aware_go2_impact_or_rough_scale =
      scalarOrDefault(kv,
                      "source_aware_go2_impact_or_rough_scale",
                      options.source_aware_policy_config.source_aware_go2_impact_or_rough_scale);
  options.source_aware_policy_config.source_aware_go2_motion_unknown_scale =
      scalarOrDefault(kv,
                      "source_aware_go2_motion_unknown_scale",
                      options.source_aware_policy_config.source_aware_go2_motion_unknown_scale);
  options.source_aware_policy_config.source_aware_go2_in_place_turn_scale =
      scalarOrDefault(kv,
                      "source_aware_go2_in_place_turn_scale",
                      options.source_aware_policy_config.source_aware_go2_in_place_turn_scale);
  options.source_aware_policy_config.source_aware_reject_extreme =
      boolOrDefault(kv,
                    "source_aware_reject_extreme",
                    options.source_aware_policy_config.source_aware_reject_extreme);
  options.source_aware_policy_config.source_aware_no_R_shrink =
      boolOrDefault(kv,
                    "source_aware_no_R_shrink",
                    options.source_aware_policy_config.source_aware_no_R_shrink);
  options.source_aware_policy_config.source_aware_trace_enabled =
      boolOrDefault(kv,
                    "source_aware_trace_enabled",
                    options.source_aware_policy_config.source_aware_trace_enabled);
  options.source_aware_policy_config.source_aware_enable_rolling_innovation_baseline =
      boolOrDefault(kv,
                    "source_aware_enable_rolling_innovation_baseline",
                    options.source_aware_policy_config.source_aware_enable_rolling_innovation_baseline);
  options.source_aware_policy_config.source_aware_rolling_window_size =
      static_cast<std::size_t>(std::max(1.0, scalarOrDefault(kv,
                                                             "source_aware_rolling_window_size",
                                                             static_cast<double>(options.source_aware_policy_config.source_aware_rolling_window_size))));
  options.source_aware_policy_config.source_aware_rolling_mad_floor =
      scalarOrDefault(kv,
                      "source_aware_rolling_mad_floor",
                      options.source_aware_policy_config.source_aware_rolling_mad_floor);
  options.source_aware_policy_config.source_aware_method_family =
      stringOrDefault(kv,
                      "source_aware_method_family",
                      options.source_aware_policy_config.source_aware_method_family);
  options.source_aware_policy_config.source_aware_method_k0 =
      scalarOrDefault(kv,
                      "source_aware_method_k0",
                      options.source_aware_policy_config.source_aware_method_k0);
  options.source_aware_policy_config.source_aware_method_k1 =
      scalarOrDefault(kv,
                      "source_aware_method_k1",
                      options.source_aware_policy_config.source_aware_method_k1);
  options.source_aware_policy_config.source_aware_method_c =
      scalarOrDefault(kv,
                      "source_aware_method_c",
                      options.source_aware_policy_config.source_aware_method_c);
  options.source_aware_policy_config.source_aware_method_alpha =
      scalarOrDefault(kv,
                      "source_aware_method_alpha",
                      options.source_aware_policy_config.source_aware_method_alpha);
  options.source_aware_policy_config.source_aware_method_phi =
      scalarOrDefault(kv,
                      "source_aware_method_phi",
                      options.source_aware_policy_config.source_aware_method_phi);
  options.source_aware_policy_config.source_aware_method_base_gain =
      scalarOrDefault(kv,
                      "source_aware_method_base_gain",
                      options.source_aware_policy_config.source_aware_method_base_gain);
  const std::array<std::pair<source_aware::MeasurementSource, const char*>, source_aware::kMeasurementSourceCount>
      source_keys{{
          {source_aware::MeasurementSource::kReceiverPosition, "receiver_position"},
          {source_aware::MeasurementSource::kReceiverVelocity, "receiver_velocity"},
          {source_aware::MeasurementSource::kDualAntennaYaw, "dual_antenna_yaw"},
          {source_aware::MeasurementSource::kRawDopplerVelocity, "raw_doppler_velocity"},
          {source_aware::MeasurementSource::kGo2AttitudeRollPitch, "go2_attitude_roll_pitch"},
          {source_aware::MeasurementSource::kGo2HorizontalVelocity, "go2_horizontal_velocity"},
      }};
  for (const auto& item : source_keys) {
    auto& source_config = options.source_aware_policy_config.sources[source_aware::sourceIndex(item.first)];
    const std::string prefix = std::string("source_aware_") + item.second + "_";
    source_config.enabled = boolOrDefault(kv, prefix + "enabled", source_config.enabled);
    source_config.lsim_enabled = boolOrDefault(kv, prefix + "lsim_enabled", source_config.lsim_enabled);
    source_config.oim_enabled = boolOrDefault(kv, prefix + "oim_enabled", source_config.oim_enabled);
  }
  options.lsim_oim = options.source_aware_policy_config.enable_source_aware_weighting &&
                     options.source_aware_policy_config.source_aware_mode != "off";
  // 中文说明：N8G feedback 默认关闭；打开后只读取 runtime-only FGO_FEEDBACK_OBSERVATIONS.csv。
  options.fgo_feedback_config.enable_fgo_feedback =
      boolOrDefault(kv, "enable_fgo_feedback", options.fgo_feedback_config.enable_fgo_feedback);
  options.fgo_feedback_config.fgo_feedback_path =
      stringOrDefault(kv, "fgo_feedback_path", options.fgo_feedback_config.fgo_feedback_path);
  options.fgo_feedback_config.fgo_feedback_mode =
      stringOrDefault(kv, "fgo_feedback_mode", options.fgo_feedback_config.fgo_feedback_mode);
  options.fgo_feedback_config.fgo_feedback_position_enabled =
      boolOrDefault(kv,
                    "fgo_feedback_position_enabled",
                    options.fgo_feedback_config.fgo_feedback_position_enabled);
  options.fgo_feedback_config.fgo_feedback_velocity_enabled =
      boolOrDefault(kv,
                    "fgo_feedback_velocity_enabled",
                    options.fgo_feedback_config.fgo_feedback_velocity_enabled);
  options.fgo_feedback_config.fgo_feedback_attitude_enabled =
      boolOrDefault(kv,
                    "fgo_feedback_attitude_enabled",
                    options.fgo_feedback_config.fgo_feedback_attitude_enabled);
  options.fgo_feedback_config.fgo_feedback_covariance_scale =
      scalarOrDefault(kv,
                      "fgo_feedback_covariance_scale",
                      options.fgo_feedback_config.fgo_feedback_covariance_scale);
  options.fgo_feedback_config.fgo_feedback_max_position_correction_m =
      scalarOrDefault(kv,
                      "fgo_feedback_max_position_correction_m",
                      options.fgo_feedback_config.fgo_feedback_max_position_correction_m);
  options.fgo_feedback_config.fgo_feedback_max_velocity_correction_mps =
      scalarOrDefault(kv,
                      "fgo_feedback_max_velocity_correction_mps",
                      options.fgo_feedback_config.fgo_feedback_max_velocity_correction_mps);
  options.fgo_feedback_config.fgo_feedback_max_attitude_correction_deg =
      scalarOrDefault(kv,
                      "fgo_feedback_max_attitude_correction_deg",
                      options.fgo_feedback_config.fgo_feedback_max_attitude_correction_deg);
  options.fgo_feedback_config.fgo_feedback_min_interval_s =
      scalarOrDefault(kv,
                      "fgo_feedback_min_interval_s",
                      options.fgo_feedback_config.fgo_feedback_min_interval_s);
  options.fgo_feedback_config.fgo_feedback_no_future_data_required =
      boolOrDefault(kv,
                    "fgo_feedback_no_future_data_required",
                    options.fgo_feedback_config.fgo_feedback_no_future_data_required);
  return options;
}

}  // namespace legsa_v23_port_core
