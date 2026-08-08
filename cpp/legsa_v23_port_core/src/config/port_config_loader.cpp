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
#include <cmath>
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

bool hasKey(const std::unordered_map<std::string, std::string>& kv, const std::string& key) {
  return kv.find(key) != kv.end();
}

[[noreturn]] void formalContractFailure(const std::string& detail) {
  throw std::runtime_error("FAIL_CLEAN1_METHOD_CONTRACT_MISMATCH: " + detail);
}

bool isClean2r2aAblationId(const std::string& algorithm_id) {
  if (algorithm_id.size() != 6 || algorithm_id[0] != 'A' || algorithm_id[1] != 'B') {
    return false;
  }
  return std::all_of(algorithm_id.begin() + 2, algorithm_id.end(),
                     [](char value) { return value == '0' || value == '1'; });
}

bool isCanonical541AblationId(const std::string& algorithm_id) {
  const std::array<const char*, 7> allowed{{
      "AB0111", "AB1011", "AB1101", "AB1110", "AB1100", "AB1000", "AB0100",
  }};
  return std::any_of(allowed.begin(), allowed.end(), [&algorithm_id](const char* value) {
    return algorithm_id == value;
  });
}

bool isCanonical541MatrixRunId(const std::string& run_id) {
  if (run_id.size() != 9 || run_id.substr(0, 4) != "RUN_") {
    return false;
  }
  return std::all_of(run_id.begin() + 4, run_id.end(), [](unsigned char value) {
    return std::isdigit(value);
  });
}

bool isCanonical541MatrixAlgorithmId(const std::string& algorithm_id) {
  return algorithm_id == "single_antenna_EKF" ||
         algorithm_id == "basic_dual_yaw_EKF" ||
         algorithm_id == "strong_dual_yaw_EKF" ||
         algorithm_id == "LegSA_Paper_V1" ||
         isCanonical541AblationId(algorithm_id);
}

bool isCanonical541CompactReadinessIdentity(
    const PortOptions& options, const std::string& requested_runtime_role) {
  if (options.stage_id != "CLEAN3R4_BY2_CANONICAL_541_REPAIRED_MATRIX" ||
      options.protocol_id != "CANONICAL541_BY2_CONTROLLED_DEGRADATION" ||
      requested_runtime_role != "canonical541_formal_controlled_degradation_solver" ||
      options.case_id != "C00_clean_normal" || options.data_mode != "real_clean" ||
      options.run_label != options.run_id) {
    return false;
  }
  const std::array<std::pair<const char*, const char*>, 18> identities{{
      {"CLEAN3R4_READINESS_01_single_antenna_EKF", "single_antenna_EKF"},
      {"CLEAN3R4_READINESS_02_basic_dual_yaw_EKF", "basic_dual_yaw_EKF"},
      {"CLEAN3R4_READINESS_03_AB0000", "strong_dual_yaw_EKF"},
      {"CLEAN3R4_READINESS_04_AB0001", "AB0001"},
      {"CLEAN3R4_READINESS_05_AB0010", "AB0010"},
      {"CLEAN3R4_READINESS_06_AB0011", "AB0011"},
      {"CLEAN3R4_READINESS_07_AB0100", "AB0100"},
      {"CLEAN3R4_READINESS_08_AB0101", "AB0101"},
      {"CLEAN3R4_READINESS_09_AB0110", "AB0110"},
      {"CLEAN3R4_READINESS_10_AB0111", "AB0111"},
      {"CLEAN3R4_READINESS_11_AB1000", "AB1000"},
      {"CLEAN3R4_READINESS_12_AB1001", "AB1001"},
      {"CLEAN3R4_READINESS_13_AB1010", "AB1010"},
      {"CLEAN3R4_READINESS_14_AB1011", "AB1011"},
      {"CLEAN3R4_READINESS_15_AB1100", "AB1100"},
      {"CLEAN3R4_READINESS_16_AB1101", "AB1101"},
      {"CLEAN3R4_READINESS_17_AB1110", "AB1110"},
      {"CLEAN3R4_READINESS_18_AB1111", "LegSA_Paper_V1"},
  }};
  return std::any_of(identities.begin(), identities.end(), [&options](const auto& identity) {
    return options.run_id == identity.first && options.algorithm_id == identity.second;
  });
}

bool isCanonical541CaseId(const std::string& case_id) {
  if (case_id == "C00_clean_normal") {
    return true;
  }
  if (case_id.size() != 11 || case_id[0] != 'D' || case_id[3] != '_' ||
      case_id.substr(4, 5) != "seed_" ||
      !std::isdigit(static_cast<unsigned char>(case_id[1])) ||
      !std::isdigit(static_cast<unsigned char>(case_id[2])) ||
      !std::isdigit(static_cast<unsigned char>(case_id[9])) ||
      !std::isdigit(static_cast<unsigned char>(case_id[10]))) {
    return false;
  }
  const int degradation = (case_id[1] - '0') * 10 + (case_id[2] - '0');
  const int seed = (case_id[9] - '0') * 10 + (case_id[10] - '0');
  return degradation >= 1 && degradation <= 60 && seed >= 0 && seed <= 8;
}

void validateFormalMethodContract(const std::unordered_map<std::string, std::string>& kv,
                                  PortOptions& options) {
  const bool clean3_s3_ab0000_parity_mode =
      boolOrDefault(kv, "clean3_s3_ab0000_parity_mode", false);
  const std::array<const char*, 6> feature_keys{{
      "enable_dual_yaw",
      "enable_receiver_velocity",
      "enable_raw_doppler",
      "enable_source_aware",
      "enable_go2_roll_pitch_prior",
      "enable_go2_horizontal_velocity_prior",
  }};
  for (const char* key : feature_keys) {
    if (!hasKey(kv, key)) {
      formalContractFailure(std::string("formal config missing explicit feature key ") + key);
    }
  }
  const std::array<const char*, 4> go2_truth_keys{{
      "go2_position_truth_claim",
      "go2_velocity_truth_claim",
      "go2_yaw_truth_claim",
      "go2_contact_truth_claim",
  }};
  for (const char* key : go2_truth_keys) {
    if (!hasKey(kv, key) || boolOrDefault(kv, key, true)) {
      formalContractFailure(std::string("formal config must explicitly disable ") + key);
    }
  }
  const bool clean1_v1_identity =
      options.stage_id == "CLEAN1_BY2_CLEAN_FOUR_METHOD_EXECUTION" &&
      options.protocol_id == "CLEAN1_BY2_CLEAN_NORMAL_V1";
  const bool clean1r1c_v2_identity =
      options.stage_id ==
          "CLEAN1R1C_FROZEN_PROTOCOL_DIRECT_REIMPLEMENTATION_AND_BY2_FORMAL_EXECUTION" &&
      options.protocol_id == "CLEAN1_BY2_CLEAN_NORMAL_V2_KICK_ALIGNED";
  const bool clean1r2r1_final_v23_identity =
      options.stage_id ==
          "CLEAN1R2R1_CLEAN_REAL_FINAL_V23_PARITY_AND_FOUR_METHOD_EXECUTION" &&
      options.protocol_id == "CLEAN_REAL_DATA_FINAL_V23";
  const bool clean2r2a_ablation_identity =
      options.stage_id == "CLEAN2R2A_BY2_CLEAN_MODULE_ABLATION_REBUILD" &&
      options.protocol_id == "CLEAN2R2A_BY2_CLEAN_MODULE_ABLATION";
  const bool canonical541_identity =
      options.stage_id == "CLEAN3R4_BY2_CANONICAL_541_REPAIRED_MATRIX" &&
      options.protocol_id == "CANONICAL541_BY2_CONTROLLED_DEGRADATION";
  const std::string canonical541_runtime_role =
      stringOrDefault(kv, "runtime_role", "");
  const bool canonical541_compact_readiness_identity =
      isCanonical541CompactReadinessIdentity(options, canonical541_runtime_role);
  const bool canonical541_matrix_identity =
      canonical541_identity &&
      canonical541_runtime_role == "canonical541_formal_controlled_degradation_solver" &&
      options.run_label == options.run_id && isCanonical541MatrixRunId(options.run_id) &&
      isCanonical541MatrixAlgorithmId(options.algorithm_id);
  const bool clean3_s3_stage_identity =
      options.stage_id ==
          "CLEAN3_MATH_REPAIR_RP_JACOBIAN_RD_LEVERARM_SA_CLEAN_SILENCE" ||
      options.stage_id ==
          "CLEAN3R2_MATH_REPAIR_COUNTER_CONTRACT_ROUTING_REPAIR_AND_S3_RESUME" ||
      options.stage_id ==
          "CLEAN3R3_MATH_REPAIR_PORT_ROLE_FILL_IF_EMPTY_HARDCODE_SWEEP_AND_S3_RESUME";
  const bool clean3_s3_ab0000_identity =
      clean3_s3_ab0000_parity_mode && clean3_s3_stage_identity &&
      options.protocol_id == "CLEAN3_S3_AB0000_PARITY" &&
      options.algorithm_id == "AB0000" && options.run_id == "CLEAN3_S3_AB0000";
  if (clean3_s3_ab0000_parity_mode && !clean3_s3_ab0000_identity) {
    formalContractFailure("CLEAN3 S3 parity mode identity mismatch");
  }
  if (!clean3_s3_ab0000_parity_mode && clean3_s3_stage_identity) {
    formalContractFailure("CLEAN3 S3 parity mode requires its explicit guard key");
  }
  const bool canonical541_data_mode_matches =
      options.case_id == "C00_clean_normal"
          ? options.data_mode == "real_clean"
          : options.data_mode == "real_base_controlled_degradation";
  const bool data_mode_matches = canonical541_identity
                                     ? canonical541_data_mode_matches
                                     : (clean2r2a_ablation_identity || clean3_s3_ab0000_identity)
                                           ? options.data_mode == "real_clean"
                                           : options.data_mode == "real_by2_raw";
  const bool case_id_matches = canonical541_identity
                                   ? isCanonical541CaseId(options.case_id)
                                   : options.case_id == "CLEAN1_BY2_CLEAN_NORMAL";
  if ((!clean1_v1_identity && !clean1r1c_v2_identity && !clean1r2r1_final_v23_identity &&
       !clean2r2a_ablation_identity && !clean3_s3_ab0000_identity && !canonical541_identity) ||
      !case_id_matches || !data_mode_matches ||
      options.run_id.empty()) {
    formalContractFailure("formal stage/protocol/case/data_mode/run identity mismatch");
  }
  if (canonical541_identity &&
      !canonical541_compact_readiness_identity && !canonical541_matrix_identity) {
    formalContractFailure("canonical541 runtime identity is outside readiness/matrix contract");
  }
  // 保留 CLEAN1 的逐字合同，同时只为 CLEAN2R2A 要求同一 final_v23 parity mode。
  if ((options.clean_final_v23_parity_mode != clean1r2r1_final_v23_identity) &&
      !clean2r2a_ablation_identity && !clean3_s3_ab0000_identity && !canonical541_identity) {
    formalContractFailure("clean final_v23 parity mode/profile identity mismatch");
  }
  if ((clean2r2a_ablation_identity || clean3_s3_ab0000_identity || canonical541_identity) &&
      !options.clean_final_v23_parity_mode) {
    formalContractFailure("clean final_v23 parity mode/profile identity mismatch");
  }
  if (!options.common_initialization || !options.common_initialization_dual_yaw_used ||
      options.trace_used_for_initialization ||
      options.method_specific_initialization ||
      options.common_initialization_source.empty() ||
      options.common_initialization_source == "unspecified") {
    formalContractFailure("common source-backed initialization contract is incomplete");
  }
  if (options.propagation_imu_source.empty() ||
      options.solver_output_reference_point != "propagation_imu_reference_point" ||
      options.antlever_config_source != "runtime_config_antlever" ||
      options.evaluation_reference_point_match_established ||
      options.reference_point_compensation_applied) {
    formalContractFailure("solver/reference-point or propagation-IMU contract is not fail-closed");
  }
  if (options.trace_solver_input || options.receiver_imu_as_body_imu ||
      options.synthetic_data_used || options.semisynthetic_data_used ||
      options.final_v23_output_solver_input || options.LegSA_output_solver_input ||
      options.per_case_tuning || options.output_only_correction ||
      options.bad_epoch_deletion_for_metric || options.old_runtime_input_count != 0 ||
      options.legacy_provider_input_count != 0 || options.legacy_row_input_count != 0 ||
      options.legacy_aggregate_input_count != 0 || options.status_fallback_used ||
      options.legacy_provider_used) {
    formalContractFailure("formal forbidden input/tuning/correction flag is nonzero");
  }
  if (options.enable_go2_proprioceptive_joint_factor || options.go2_vertical_velocity_prior_enabled ||
      options.fgo_feedback_config.enable_fgo_feedback ||
      options.enable_no_feedback_fgo ||
      options.quality_state_manager_config.enable_multi_state_qm ||
      options.qa_fallback_config.enable_qa_fallback || options.qa_fallback_config.qa_active_mode ||
      options.enable_active_nine_factor_fgo || options.enable_contact_fk_factor) {
    formalContractFailure("out-of-scope FGO/QM/QA/contact-FK/Go2 joint feature is enabled");
  }

  const bool dual = options.enable_dual_yaw_update;
  const bool receiver_velocity = options.enable_receiver_velocity_update;
  const bool raw_doppler = options.raw_doppler_config.enable_raw_doppler;
  const bool source_aware = options.source_aware_policy_config.enable_source_aware_weighting;
  const bool go2_roll_pitch = options.go2_attitude_prior_config.enable_go2_attitude_weak_prior;
  const bool go2_horizontal =
      options.go2_velocity_prior_diagnostic_config.enable_go2_horizontal_velocity_prior;
  bool expected_dual = false;
  bool expected_receiver_velocity = false;
  bool expected_raw_doppler = false;
  bool expected_source_aware = false;
  bool expected_go2_roll_pitch = false;
  bool expected_go2_horizontal = false;
  if (options.algorithm_id == "single_antenna_EKF") {
    expected_receiver_velocity = true;
  } else if (options.algorithm_id == "basic_dual_yaw_EKF") {
    expected_dual = true;
    if (std::fabs(options.basic_dual_yaw_fixed_std_deg - 1.5) > 1.0e-12) {
      formalContractFailure("basic_dual_yaw_EKF fixed yaw std must be 1.5 deg");
    }
  } else if (options.algorithm_id == "strong_dual_yaw_EKF") {
    expected_dual = true;
    expected_receiver_velocity = true;
  } else if (options.algorithm_id == "LegSA_Paper_V1") {
    expected_dual = true;
    expected_receiver_velocity = true;
    expected_raw_doppler = true;
    expected_source_aware = true;
    expected_go2_roll_pitch = true;
    expected_go2_horizontal = true;
  } else if (((clean2r2a_ablation_identity || clean3_s3_ab0000_identity) &&
              isClean2r2aAblationId(options.algorithm_id)) ||
             (canonical541_matrix_identity && isCanonical541AblationId(options.algorithm_id)) ||
             (canonical541_compact_readiness_identity &&
              isClean2r2aAblationId(options.algorithm_id))) {
    // 中文说明：AB 四位从左到右严格是 RD、SA、RP、HV；backbone 始终是 strong/final_v23。
    expected_dual = true;
    expected_receiver_velocity = true;
    expected_raw_doppler = options.algorithm_id[2] == '1';
    expected_source_aware = options.algorithm_id[3] == '1';
    expected_go2_roll_pitch = options.algorithm_id[4] == '1';
    expected_go2_horizontal = options.algorithm_id[5] == '1';
  } else {
    formalContractFailure("algorithm_id is outside the frozen stage method set");
  }
  if (dual != expected_dual || receiver_velocity != expected_receiver_velocity ||
      raw_doppler != expected_raw_doppler || source_aware != expected_source_aware ||
      go2_roll_pitch != expected_go2_roll_pitch || go2_horizontal != expected_go2_horizontal) {
    formalContractFailure("effective method flags do not match methods.yaml frozen matrix");
  }
  if (expected_source_aware && options.source_aware_policy_config.source_aware_mode == "off") {
    formalContractFailure("source-aware feature is enabled but policy mode is off");
  }
  if (go2_horizontal &&
      (!options.go2_velocity_prior_diagnostic_config.go2_horizontal_velocity_prior_vertical_disabled ||
       options.go2_velocity_prior_diagnostic_config.go2_horizontal_velocity_prior_mode != "horizontal_2d")) {
    formalContractFailure("Go2 horizontal weak prior must be horizontal_2d with vertical disabled");
  }
  if (options.go2_attitude_prior_config.go2_position_prior_enabled ||
      options.go2_attitude_prior_config.go2_velocity_prior_enabled ||
      options.go2_attitude_prior_config.go2_yaw_prior_enabled) {
    formalContractFailure("Go2 truth/position/yaw prior flag is enabled");
  }

  options.enable_basic_dual_yaw_baseline = options.algorithm_id == "basic_dual_yaw_EKF";
  options.yaw_scheme_C_enabled = options.enable_dual_yaw_update && !options.enable_basic_dual_yaw_baseline;
  options.phase = options.stage_id;
  options.port_role = canonical541_identity
                          ? "canonical541_formal_controlled_degradation_solver"
                      : clean3_s3_ab0000_identity
                          ? "clean3_s3_ab0000_parity_solver"
                      : clean2r2a_ablation_identity
                          ? "clean2r2a_formal_clean_ablation_solver"
                          : "clean1_formal_four_method_solver";
  options.run_label = options.run_id;
  options.raw_doppler_config.formal_lineage_required = expected_raw_doppler;
  if (expected_go2_roll_pitch) {
    options.go2_attitude_prior_config.go2_attitude_prior_diagnostic_only = false;
  }
  if (expected_go2_horizontal) {
    options.go2_velocity_prior_diagnostic_config.enable_go2_velocity_prior_diagnostic = true;
    options.go2_velocity_prior_diagnostic_config.go2_diagnostic_prior_only = false;
    options.go2_diagnostic_prior_only = false;
  }
  options.paper_performance_claim = false;
  options.proposed_factor_claim = false;
  options.performance_claim = false;
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
  options.clean1_formal_mode = boolOrDefault(kv, "clean1_formal_mode", options.clean1_formal_mode);
  options.clean_final_v23_parity_mode =
      boolOrDefault(kv, "clean_final_v23_parity_mode", options.clean_final_v23_parity_mode);
  options.stage_id = stringOrDefault(kv, "stage_id", options.stage_id);
  options.protocol_id = stringOrDefault(kv, "protocol_id", options.protocol_id);
  options.case_id = stringOrDefault(kv, "case_id", options.case_id);
  options.run_id = stringOrDefault(kv, "run_id", options.run_id);
  options.data_mode = stringOrDefault(kv, "data_mode", options.data_mode);
  options.run_label = stringOrDefault(kv, "run_label", "N4H4R2_config_run");
  options.algorithm_id = stringOrDefault(kv, "algorithm_id", options.algorithm_id);
  options.qa_fallback_config.algorithm_id = options.algorithm_id;
  options.imu_path = stringOrDefault(kv, "imupath", stringOrDefault(kv, "imu_path", ""));
  options.gnss_path = stringOrDefault(kv, "gnsspath", stringOrDefault(kv, "gnss_path", ""));
  options.clean_input_provenance_label =
      stringOrDefault(kv, "clean_input_provenance_label", options.clean_input_provenance_label);
  options.propagation_imu_source =
      stringOrDefault(kv, "propagation_imu_source", options.propagation_imu_source);
  options.common_initialization =
      boolOrDefault(kv, "common_initialization", options.common_initialization);
  options.common_initialization_dual_yaw_used =
      boolOrDefault(kv, "common_initialization_dual_yaw_used", options.common_initialization_dual_yaw_used);
  options.trace_used_for_initialization =
      boolOrDefault(kv, "trace_used_for_initialization", options.trace_used_for_initialization);
  options.method_specific_initialization =
      boolOrDefault(kv, "method_specific_initialization", options.method_specific_initialization);
  options.common_initialization_source =
      stringOrDefault(kv, "common_initialization_source", options.common_initialization_source);
  options.solver_output_reference_point =
      stringOrDefault(kv, "solver_output_reference_point", options.solver_output_reference_point);
  options.antlever_config_source =
      stringOrDefault(kv, "antlever_config_source", options.antlever_config_source);
  options.evaluation_reference_point_match_established =
      boolOrDefault(kv,
                    "evaluation_reference_point_match_established",
                    options.evaluation_reference_point_match_established);
  options.reference_point_compensation_applied =
      boolOrDefault(kv, "reference_point_compensation_applied", options.reference_point_compensation_applied);
  options.trace_solver_input = boolOrDefault(
      kv, "trace_used_online", boolOrDefault(kv, "trace_solver_input", options.trace_solver_input));
  options.receiver_imu_as_body_imu =
      boolOrDefault(kv, "receiver_imu_as_body_imu", options.receiver_imu_as_body_imu);
  options.synthetic_data_used =
      boolOrDefault(kv, "synthetic_data_used", options.synthetic_data_used);
  options.semisynthetic_data_used =
      boolOrDefault(kv, "semisynthetic_data_used", options.semisynthetic_data_used);
  options.final_v23_output_solver_input =
      boolOrDefault(kv, "final_v23_output_solver_input", options.final_v23_output_solver_input);
  options.LegSA_output_solver_input =
      boolOrDefault(kv, "LegSA_output_solver_input", options.LegSA_output_solver_input);
  options.per_case_tuning = boolOrDefault(kv, "per_case_tuning", options.per_case_tuning);
  options.output_only_correction =
      boolOrDefault(kv, "output_only_correction", options.output_only_correction);
  options.bad_epoch_deletion_for_metric = boolOrDefault(
      kv, "epoch_deleted_for_metric", boolOrDefault(kv, "bad_epoch_deletion_for_metric", false));
  options.old_runtime_input_count = static_cast<std::size_t>(std::max(
      0.0, scalarOrDefault(kv, "old_runtime_input_count", static_cast<double>(options.old_runtime_input_count))));
  options.legacy_provider_input_count = static_cast<std::size_t>(std::max(
      0.0, scalarOrDefault(kv, "legacy_provider_input_count", static_cast<double>(options.legacy_provider_input_count))));
  options.legacy_row_input_count = static_cast<std::size_t>(std::max(
      0.0, scalarOrDefault(kv, "legacy_row_input_count", static_cast<double>(options.legacy_row_input_count))));
  options.legacy_aggregate_input_count = static_cast<std::size_t>(std::max(
      0.0,
      scalarOrDefault(kv,
                      "legacy_aggregate_input_count",
                      static_cast<double>(options.legacy_aggregate_input_count))));
  options.status_fallback_used = boolOrDefault(kv, "status_fallback_used", options.status_fallback_used);
  options.legacy_provider_used = boolOrDefault(kv, "legacy_provider_used", options.legacy_provider_used);
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
  // 中文说明：formal config 使用 methods.yaml 字段名；若两种键并存，machine-readable 方法键优先。
  options.enable_receiver_velocity_update =
      boolOrDefault(kv, "enable_receiver_velocity", options.enable_receiver_velocity_update);
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
  options.enable_basic_dual_yaw_baseline =
      boolOrDefault(kv, "enable_basic_dual_yaw_baseline", options.enable_basic_dual_yaw_baseline);
  options.enable_dual_yaw_update = boolOrDefault(kv, "enable_dual_yaw_update", options.enable_dual_yaw_update);
  options.enable_dual_yaw_update = boolOrDefault(kv, "enable_dual_yaw", options.enable_dual_yaw_update);
  options.basic_dual_yaw_fixed_std_deg =
      scalarOrDefault(kv, "basic_dual_yaw_fixed_std_deg", options.basic_dual_yaw_fixed_std_deg);
  options.yaw_std_min_deg = scalarOrDefault(kv, "yaw_std_min_deg", options.yaw_std_min_deg);
  options.yaw_std_soft_deg = scalarOrDefault(kv, "yaw_std_soft_deg", options.yaw_std_soft_deg);
  options.yaw_std_hard_deg = scalarOrDefault(kv, "yaw_std_hard_deg", options.yaw_std_hard_deg);
  options.yaw_res_soft_deg = scalarOrDefault(kv, "yaw_res_soft_deg", options.yaw_res_soft_deg);
  options.yaw_res_hard_deg = scalarOrDefault(kv, "yaw_res_hard_deg", options.yaw_res_hard_deg);
  options.yaw_downweight_scale =
      scalarOrDefault(kv, "yaw_downweight_scale", options.yaw_downweight_scale);
  options.disable_source_aware = boolOrDefault(kv, "disable_source_aware", options.disable_source_aware);
  options.disable_go2 = boolOrDefault(kv, "disable_go2", options.disable_go2);
  options.disable_qm = boolOrDefault(kv, "disable_qm", options.disable_qm);
  options.disable_raw_doppler = boolOrDefault(kv, "disable_raw_doppler", options.disable_raw_doppler);
  options.disable_fgo_feedback = boolOrDefault(kv, "disable_fgo_feedback", options.disable_fgo_feedback);
  options.basic_dual_yaw_residual_sign =
      stringOrDefault(kv, "basic_dual_yaw_residual_sign", options.basic_dual_yaw_residual_sign);
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
  options.enable_go2_proprioceptive_joint_factor =
      boolOrDefault(kv,
                    "enable_go2_joint_factor",
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
  options.raw_doppler_config.raw_doppler_backend_id =
      stringOrDefault(kv, "raw_doppler_backend_id", options.raw_doppler_config.raw_doppler_backend_id);
  options.raw_doppler_config.raw_doppler_backend_source_files = stringOrDefault(
      kv, "raw_doppler_backend_source_files", options.raw_doppler_config.raw_doppler_backend_source_files);
  options.raw_doppler_config.raw_doppler_backend_source_hashes = stringOrDefault(
      kv, "raw_doppler_backend_source_hashes", options.raw_doppler_config.raw_doppler_backend_source_hashes);
  options.raw_doppler_config.helper_executable_hash =
      stringOrDefault(kv, "helper_executable_hash", options.raw_doppler_config.helper_executable_hash);
  options.raw_doppler_config.obs_source_hash =
      stringOrDefault(kv, "obs_source_hash", options.raw_doppler_config.obs_source_hash);
  options.raw_doppler_config.nav_source_hash =
      stringOrDefault(kv, "nav_source_hash", options.raw_doppler_config.nav_source_hash);
  options.raw_doppler_config.conversion_config_hash =
      stringOrDefault(kv, "conversion_config_hash", options.raw_doppler_config.conversion_config_hash);
  options.raw_doppler_config.covariance_policy =
      stringOrDefault(kv, "covariance_policy", options.raw_doppler_config.covariance_policy);
  options.raw_doppler_config.rtklib_position_solution_used_as_solver_input =
      boolOrDefault(kv,
                    "rtklib_position_solution_used_as_solver_input",
                    options.raw_doppler_config.rtklib_position_solution_used_as_solver_input);
  options.raw_doppler_config.nav_pvt_velocity_used_as_raw_doppler =
      boolOrDefault(kv,
                    "nav_pvt_velocity_used_as_raw_doppler",
                    options.raw_doppler_config.nav_pvt_velocity_used_as_raw_doppler);
  options.raw_doppler_config.gnss_velocity_used_as_raw_doppler =
      boolOrDefault(kv,
                    "gnss_velocity_used_as_raw_doppler",
                    options.raw_doppler_config.gnss_velocity_used_as_raw_doppler);
  options.raw_doppler_config.status_fallback_used =
      boolOrDefault(kv, "status_fallback_used", options.raw_doppler_config.status_fallback_used);
  options.raw_doppler_config.legacy_provider_used =
      boolOrDefault(kv, "legacy_provider_used", options.raw_doppler_config.legacy_provider_used);
  // 中文说明：N7A Go2 attitude weak prior 默认关闭；只读取 builder 生成的 runtime-only CSV。
  options.go2_attitude_prior_config.enable_go2_attitude_weak_prior =
      boolOrDefault(kv,
                    "enable_go2_attitude_weak_prior",
                    options.go2_attitude_prior_config.enable_go2_attitude_weak_prior);
  options.go2_attitude_prior_config.enable_go2_attitude_weak_prior =
      boolOrDefault(kv,
                    "enable_go2_roll_pitch_prior",
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
  options.source_aware_policy_config.enable_source_aware_weighting =
      boolOrDefault(kv,
                    "enable_source_aware",
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
  auto& qm = options.quality_state_manager_config;
  qm.enable_multi_state_qm = boolOrDefault(kv, "enable_multi_state_qm", qm.enable_multi_state_qm);
  qm.multi_state_qm_mode = stringOrDefault(kv, "multi_state_qm_mode", qm.multi_state_qm_mode);
  qm.multi_state_qm_trace_enabled =
      boolOrDefault(kv, "multi_state_qm_trace_enabled", qm.multi_state_qm_trace_enabled);
  qm.multi_state_qm_trace_only =
      boolOrDefault(kv, "multi_state_qm_trace_only", qm.multi_state_qm_trace_only);
  qm.multi_state_qm_enable_downweight_reject =
      boolOrDefault(kv, "multi_state_qm_enable_downweight_reject", qm.multi_state_qm_enable_downweight_reject);
  qm.multi_state_qm_enable_hold_recovery =
      boolOrDefault(kv, "multi_state_qm_enable_hold_recovery", qm.multi_state_qm_enable_hold_recovery);
  qm.multi_state_qm_enable_fallback =
      boolOrDefault(kv, "multi_state_qm_enable_fallback", qm.multi_state_qm_enable_fallback);
  qm.qm_downweight_threshold = scalarOrDefault(kv, "qm_downweight_threshold", qm.qm_downweight_threshold);
  qm.qm_reject_threshold = scalarOrDefault(kv, "qm_reject_threshold", qm.qm_reject_threshold);
  qm.qm_downweight_R_scale = scalarOrDefault(kv, "qm_downweight_R_scale", qm.qm_downweight_R_scale);
  qm.qm_recovery_initial_R_scale =
      scalarOrDefault(kv, "qm_recovery_initial_R_scale", qm.qm_recovery_initial_R_scale);
  qm.qm_hold_R_scale = scalarOrDefault(kv, "qm_hold_R_scale", qm.qm_hold_R_scale);
  qm.qm_fallback_R_scale = scalarOrDefault(kv, "qm_fallback_R_scale", qm.qm_fallback_R_scale);
  qm.qm_hold_enter_count = static_cast<std::size_t>(
      std::max(1.0, scalarOrDefault(kv, "qm_hold_enter_count", static_cast<double>(qm.qm_hold_enter_count))));
  qm.qm_hold_length = static_cast<std::size_t>(
      std::max(1.0, scalarOrDefault(kv, "qm_hold_length", static_cast<double>(qm.qm_hold_length))));
  qm.qm_recovery_count = static_cast<std::size_t>(
      std::max(1.0, scalarOrDefault(kv, "qm_recovery_count", static_cast<double>(qm.qm_recovery_count))));
  qm.qm_fallback_enter_count = static_cast<std::size_t>(
      std::max(1.0, scalarOrDefault(kv, "qm_fallback_enter_count", static_cast<double>(qm.qm_fallback_enter_count))));
  qm.qm_fallback_exit_count = static_cast<std::size_t>(
      std::max(1.0, scalarOrDefault(kv, "qm_fallback_exit_count", static_cast<double>(qm.qm_fallback_exit_count))));
  qm.qm_fallback_max_duration = static_cast<std::size_t>(
      std::max(1.0, scalarOrDefault(kv, "qm_fallback_max_duration", static_cast<double>(qm.qm_fallback_max_duration))));
  qm.qm_timestamp_gap_hold_sec =
      scalarOrDefault(kv, "qm_timestamp_gap_hold_sec", qm.qm_timestamp_gap_hold_sec);
  qm.qm_invalid_hold_enter_count = static_cast<std::size_t>(
      std::max(1.0, scalarOrDefault(kv,
                                    "qm_invalid_hold_enter_count",
                                    static_cast<double>(qm.qm_invalid_hold_enter_count))));
  qm.qm_source_cap = scalarOrDefault(kv, "qm_source_cap", qm.qm_source_cap);
  qm.qm_global_cap = scalarOrDefault(kv, "qm_global_cap", qm.qm_global_cap);
  qm.qm_go2_readiness_low_health =
      scalarOrDefault(kv, "qm_go2_readiness_low_health", qm.qm_go2_readiness_low_health);
  qm.qm_min_stable_epochs = static_cast<std::size_t>(
      std::max(1.0, scalarOrDefault(kv, "qm_min_stable_epochs", static_cast<double>(qm.qm_min_stable_epochs))));
  qm.qm_go2_motion_state_influence =
      boolOrDefault(kv, "qm_go2_motion_state_influence", qm.qm_go2_motion_state_influence);
  qm.qm_readiness_influence = boolOrDefault(kv, "qm_readiness_influence", qm.qm_readiness_influence);
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
  options.fgo_feedback_config.enable_fgo_feedback =
      boolOrDefault(kv,
                    "enable_selected_fgo_feedback",
                    options.fgo_feedback_config.enable_fgo_feedback);
  options.enable_active_nine_factor_fgo =
      boolOrDefault(kv, "enable_active_nine_factor_fgo", options.enable_active_nine_factor_fgo);
  options.enable_no_feedback_fgo =
      boolOrDefault(kv, "enable_no_feedback_fgo", options.enable_no_feedback_fgo);
  options.enable_contact_fk_factor =
      boolOrDefault(kv,
                    "enable_contact_fk",
                    boolOrDefault(kv, "enable_contact_fk_factor", options.enable_contact_fk_factor));
  const bool clean3_s3_guard_requested =
      boolOrDefault(kv, "clean3_s3_ab0000_parity_mode", false);
  const bool clean3_stage_requested =
      options.stage_id ==
          "CLEAN3_MATH_REPAIR_RP_JACOBIAN_RD_LEVERARM_SA_CLEAN_SILENCE" ||
      options.stage_id ==
          "CLEAN3R2_MATH_REPAIR_COUNTER_CONTRACT_ROUTING_REPAIR_AND_S3_RESUME" ||
      options.stage_id ==
          "CLEAN3R3_MATH_REPAIR_PORT_ROLE_FILL_IF_EMPTY_HARDCODE_SWEEP_AND_S3_RESUME";
  if (clean3_stage_requested && !clean3_s3_guard_requested) {
    formalContractFailure("CLEAN3 S3 stage requires its explicit guard key");
  }
  if (clean3_s3_guard_requested && !options.clean1_formal_mode) {
    formalContractFailure("CLEAN3 S3 parity mode cannot weaken formal validation");
  }
  if (options.clean1_formal_mode) {
    validateFormalMethodContract(kv, options);
  }
  if (!options.clean1_formal_mode && options.enable_basic_dual_yaw_baseline) {
    // 中文说明：PAPER10E0 Basic 基线强制关闭 LegSA-GINS-Full 复杂模块；
    // 即使配置误写启用项，也不得让 source-aware/Go2/QM/Raw Doppler/FGO 进入 solver。
    options.phase = "PAPER10E0";
    options.port_role = "basic_dual_yaw_ekf_baseline";
    if (options.algorithm_id.empty() || options.algorithm_id == quality_aware::kLegsaQaFallbackEkf) {
      // 中文说明：Basic baseline 不能被 algorithm_id 误写重新路由到 QA fallback。
      options.algorithm_id = "Basic_Dual_Yaw_EKF";
    }
    options.ablation_variant =
        options.ablation_variant.empty() ? "B01_BASIC_DUAL_YAW_EKF" : options.ablation_variant;
    options.enable_receiver_velocity_update = false;
    options.receiver_velocity_stress_mode = "disabled";
    options.receiver_velocity_additive_noise_std_mps = 0.0;
    options.diagnostic_stress_only = false;
    options.disable_source_aware = true;
    options.disable_go2 = true;
    options.disable_qm = true;
    options.disable_raw_doppler = true;
    options.disable_fgo_feedback = true;
    options.raw_doppler = false;
    options.raw_doppler_config.enable_raw_doppler = false;
    options.raw_doppler_config.raw_doppler_solver_enabled = false;
    options.go2_prior = false;
    options.enable_go2_proprioceptive_joint_factor = false;
    options.go2_attitude_prior_config.enable_go2_attitude_weak_prior = false;
    options.go2_velocity_prior_diagnostic_config.enable_go2_velocity_prior_diagnostic = false;
    options.go2_velocity_prior_diagnostic_config.enable_go2_horizontal_velocity_prior = false;
    options.go2_readiness_lsim_metadata_config.enable_go2_readiness_lsim_metadata = false;
    options.go2_yaw_rate_prior_diagnostic_config.enable_go2_yaw_rate_prior_diagnostic = false;
    options.go2_diagnostic_prior_only = true;
    options.source_aware_policy_config.enable_source_aware_weighting = false;
    options.source_aware_policy_config.source_aware_mode = "off";
    options.source_aware_policy_config.source_aware_trace_enabled = false;
    options.lsim_oim = false;
    options.quality_state_manager_config.enable_multi_state_qm = false;
    options.quality_state_manager_config.multi_state_qm_mode = "QM00_OFF";
    options.quality_state_manager_config.multi_state_qm_trace_enabled = false;
    options.multi_state_qm = false;
    options.fgo = false;
    options.fgo_feedback_config.enable_fgo_feedback = false;
    options.qa_fallback_config.enable_qa_fallback = false;
    options.qa_fallback_config.qa_active_mode = false;
    options.qa_fallback_config.qa_passive_logging_enabled = false;
    options.qa_fallback_layer_present = false;
    options.qa_fallback_active = false;
    options.qa_passive_logging_enabled = false;
    options.yaw_scheme_C_enabled = false;
    options.paper_performance_claim = false;
    options.proposed_factor_claim = false;
    options.performance_claim = false;
  }
  return options;
}

}  // namespace legsa_v23_port_core
