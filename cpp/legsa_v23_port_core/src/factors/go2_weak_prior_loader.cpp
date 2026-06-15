// LegSA-GINS source-backed port file.
// Source reference: KF-GINS-graduation-design / final_v23 reference; LegSA-owned N7A extension.
// Source commit: 5a4471efd4fcfcdc31e258a677af354c652ff16f.
// Port role: Go2 body-state roll/pitch weak-prior extension, not final_v23 output substitution.
// Boundary: no trace solver input, no final_v23 output solver input, no Go2 position truth.
// LegSA-GINS N7A Go2 weak-prior CSV loader.
// 中文说明：只接受 builder 生成的 runtime-only CSV；Go2 position/velocity/yaw 不在 N7A 激活。

#include "legsa_v23_port_core/factors/go2_weak_prior_loader.hpp"
#include "legsa_v23_port_core/types.hpp"

#include <algorithm>
#include <cctype>
#include <fstream>
#include <sstream>
#include <unordered_map>
#include <vector>

namespace legsa_v23_port_core {
namespace {

std::string trim(std::string value) {
  auto not_space = [](unsigned char ch) { return !std::isspace(ch); };
  value.erase(value.begin(), std::find_if(value.begin(), value.end(), not_space));
  value.erase(std::find_if(value.rbegin(), value.rend(), not_space).base(), value.end());
  return value;
}

std::vector<std::string> splitCsvLine(const std::string& line) {
  std::vector<std::string> out;
  std::string cell;
  bool quoted = false;
  for (char ch : line) {
    if (ch == '"') {
      quoted = !quoted;
      continue;
    }
    if (ch == ',' && !quoted) {
      out.push_back(trim(cell));
      cell.clear();
    } else {
      cell.push_back(ch);
    }
  }
  out.push_back(trim(cell));
  return out;
}

double scalar(const std::unordered_map<std::string, std::string>& row, const std::string& key, double fallback) {
  auto it = row.find(key);
  if (it == row.end() || it->second.empty()) {
    return fallback;
  }
  std::istringstream stream(it->second);
  double value = fallback;
  stream >> value;
  return value;
}

int integer(const std::unordered_map<std::string, std::string>& row, const std::string& key, int fallback) {
  return static_cast<int>(scalar(row, key, static_cast<double>(fallback)));
}

std::string stringValue(const std::unordered_map<std::string, std::string>& row,
                        const std::string& key,
                        const std::string& fallback) {
  auto it = row.find(key);
  return it == row.end() ? fallback : it->second;
}

bool boolValue(const std::unordered_map<std::string, std::string>& row,
               const std::string& key,
               bool fallback) {
  auto it = row.find(key);
  if (it == row.end() || it->second.empty()) {
    return fallback;
  }
  std::string value = it->second;
  std::transform(value.begin(), value.end(), value.begin(), [](unsigned char ch) {
    return static_cast<char>(std::tolower(ch));
  });
  return value == "true" || value == "1" || value == "yes" || value == "on";
}

double percentile(std::vector<double> values, double p) {
  if (values.empty()) {
    return 0.0;
  }
  std::sort(values.begin(), values.end());
  const auto index = static_cast<std::size_t>(p * static_cast<double>(values.size() - 1));
  return values[std::min(index, values.size() - 1)];
}

void countConfidenceLevel(Go2VelocityDiagnosticPriorStatus& status, std::string level) {
  std::transform(level.begin(), level.end(), level.begin(), [](unsigned char ch) {
    return static_cast<char>(std::tolower(ch));
  });
  if (level == "high") {
    ++status.confidence_high_count;
  } else if (level == "medium") {
    ++status.confidence_medium_count;
  } else if (level == "low") {
    ++status.confidence_low_count;
  } else if (level == "invalid") {
    ++status.confidence_invalid_count;
  }
}

}  // namespace

Go2AttitudeWeakPriorLoadResult Go2WeakPriorLoader::loadCsv(const std::string& path,
                                                           const Go2AttitudeWeakPriorConfig& config) {
  Go2AttitudeWeakPriorLoadResult result;
  result.status.code_present = true;
  result.status.solver_enabled = false;
  result.status.source_id = "go2_attitude_roll_pitch";
  result.status.weak_prior = true;
  result.status.body_state_not_truth = true;
  result.status.position_prior_enabled = false;
  result.status.velocity_prior_enabled = false;
  result.status.yaw_prior_enabled = false;
  if (!config.enable_go2_attitude_weak_prior) {
    result.status.provider_status = "disabled_by_config";
    return result;
  }
  if (path.empty()) {
    result.status.provider_status = "prior_path_missing";
    return result;
  }
  std::ifstream input(path);
  if (!input) {
    result.status.provider_status = "prior_file_missing";
    return result;
  }
  std::string line;
  if (!std::getline(input, line)) {
    result.status.provider_status = "prior_file_empty";
    return result;
  }
  const std::vector<std::string> header = splitCsvLine(line);
  while (std::getline(input, line)) {
    if (line.empty()) {
      continue;
    }
    const std::vector<std::string> cells = splitCsvLine(line);
    std::unordered_map<std::string, std::string> row;
    for (std::size_t i = 0; i < header.size() && i < cells.size(); ++i) {
      row[header[i]] = cells[i];
    }
    Go2AttitudeWeakPriorMeasurement measurement;
    measurement.time = scalar(row, "time", 0.0);
    measurement.roll_rad = scalar(row, "roll_rad", 0.0);
    measurement.pitch_rad = scalar(row, "pitch_rad", 0.0);
    measurement.std_roll_rad = scalar(row, "std_roll_rad", config.go2_attitude_prior_std_roll_deg * D2R);
    measurement.std_pitch_rad = scalar(row, "std_pitch_rad", config.go2_attitude_prior_std_pitch_deg * D2R);
    measurement.source_status = stringValue(row, "source_status", "inactive");
    measurement.quality_flag = stringValue(row, "quality_flag", "suspicious");
    measurement.mode = integer(row, "mode", -1);
    measurement.gait_type = integer(row, "gait_type", -1);
    measurement.foot_force_sum = scalar(row, "foot_force_sum", 0.0);
    measurement.body_height = scalar(row, "body_height", 0.0);
    if (measurement.source_status == "active") {
      ++result.status.valid_prior_count;
    }
    result.measurements.push_back(measurement);
  }
  result.status.prior_count = result.measurements.size();
  if (result.measurements.empty()) {
    result.status.provider_status = "prior_file_no_rows";
    return result;
  }
  if (result.status.valid_prior_count == 0) {
    result.status.provider_status = "no_active_prior_rows";
    return result;
  }
  result.status.provider_status = "available";
  result.status.solver_enabled = true;
  return result;
}

Go2VelocityDiagnosticPriorLoadResult Go2WeakPriorLoader::loadVelocityDiagnosticCsv(
    const std::string& path,
    const Go2VelocityDiagnosticPriorConfig& config) {
  Go2VelocityDiagnosticPriorLoadResult result;
  result.status.code_present = true;
  result.status.solver_enabled = false;
  result.status.source_id = config.enable_go2_horizontal_velocity_prior ? "go2_horizontal_velocity" : "go2_velocity_diagnostic";
  result.status.diagnostic_only = !config.enable_go2_horizontal_velocity_prior;
  result.status.controlled_activation = config.enable_go2_horizontal_velocity_prior;
  result.status.paper_performance_claim = false;
  result.status.go2_velocity_truth_claim = false;
  if (!config.enable_go2_velocity_prior_diagnostic && !config.enable_go2_horizontal_velocity_prior) {
    result.status.provider_status = "disabled_by_config";
    return result;
  }
  if (path.empty()) {
    result.status.provider_status = "prior_path_missing";
    return result;
  }
  std::ifstream input(path);
  if (!input) {
    result.status.provider_status = "prior_file_missing";
    return result;
  }
  std::string line;
  if (!std::getline(input, line)) {
    result.status.provider_status = "prior_file_empty";
    return result;
  }
  const std::vector<std::string> header = splitCsvLine(line);
  std::vector<double> std_vn_values;
  std::vector<double> std_ve_values;
  while (std::getline(input, line)) {
    if (line.empty()) {
      continue;
    }
    const std::vector<std::string> cells = splitCsvLine(line);
    std::unordered_map<std::string, std::string> row;
    for (std::size_t i = 0; i < header.size() && i < cells.size(); ++i) {
      row[header[i]] = cells[i];
    }
    Go2VelocityDiagnosticPriorMeasurement measurement;
    measurement.time = scalar(row, "time", 0.0);
    measurement.velocity_ned_mps = makeVec3(scalar(row, "vn", 0.0),
                                            scalar(row, "ve", 0.0),
                                            scalar(row, "vd", 0.0));
    measurement.std_ned_mps = makeVec3(scalar(row, "std_vn", 2.0),
                                       scalar(row, "std_ve", 2.0),
                                       scalar(row, "std_vd", 2.0));
    measurement.source_status = stringValue(row, "source_status", "inactive");
    measurement.quality_flag = stringValue(row, "quality_flag", "diagnostic_only");
    measurement.contact_model = stringValue(row, "contact_model", "");
    measurement.contact_label = stringValue(row, "contact_label", "");
    measurement.frame_candidate = stringValue(row, "frame_candidate", "");
    measurement.prior_policy = stringValue(row, "prior_policy", "");
    measurement.update_flag = boolValue(row, "update_flag", true);
    measurement.diagnostic_only = stringValue(row, "diagnostic_only", "true") != "false";
    measurement.go2_velocity_truth_claim = stringValue(row, "go2_velocity_truth_claim", "false") == "true";
    countConfidenceLevel(result.status, stringValue(row, "confidence_level", ""));
    if (measurement.std_ned_mps[2] >= 999.0 ||
        measurement.prior_policy.find("horizontal") != std::string::npos) {
      result.status.horizontal_only = true;
      result.status.vertical_disabled = true;
    }
    const bool row_allowed =
        measurement.source_status == "active" &&
        measurement.update_flag &&
        !measurement.go2_velocity_truth_claim &&
        (measurement.diagnostic_only || config.enable_go2_horizontal_velocity_prior);
    if (!measurement.update_flag) {
      ++result.status.skip_count;
    }
    if (row_allowed) {
      ++result.status.valid_prior_count;
      std_vn_values.push_back(measurement.std_ned_mps[0]);
      std_ve_values.push_back(measurement.std_ned_mps[1]);
    }
    result.measurements.push_back(measurement);
  }
  result.status.prior_count = result.measurements.size();
  if (result.measurements.empty()) {
    result.status.provider_status = "prior_file_no_rows";
    return result;
  }
  if (result.status.valid_prior_count == 0) {
    result.status.provider_status = "no_active_diagnostic_prior_rows";
    return result;
  }
  result.status.provider_status = "available";
  result.status.solver_enabled = true;
  result.status.std_vn_p50 = percentile(std_vn_values, 0.50);
  result.status.std_vn_p95 = percentile(std_vn_values, 0.95);
  result.status.std_vn_max = std_vn_values.empty() ? 0.0 : *std::max_element(std_vn_values.begin(), std_vn_values.end());
  result.status.std_ve_p50 = percentile(std_ve_values, 0.50);
  result.status.std_ve_p95 = percentile(std_ve_values, 0.95);
  result.status.std_ve_max = std_ve_values.empty() ? 0.0 : *std::max_element(std_ve_values.begin(), std_ve_values.end());
  result.status.max_std_le_5 = result.status.std_vn_max <= 5.0 && result.status.std_ve_max <= 5.0;
  return result;
}

Go2ReadinessLsimMetadataLoadResult Go2WeakPriorLoader::loadReadinessLsimMetadataCsv(
    const std::string& path,
    const Go2ReadinessLsimMetadataConfig& config) {
  Go2ReadinessLsimMetadataLoadResult result;
  result.status.code_present = true;
  result.status.solver_enabled = false;
  result.status.source_id = "go2_readiness_motion_state";
  result.status.readiness_metadata_first_class_lsim = false;
  result.status.trace_solver_input = false;
  result.status.final_v23_output_solver_input = false;
  result.status.go2_position_truth_claim = false;
  result.status.go2_yaw_truth_claim = false;
  if (!config.enable_go2_readiness_lsim_metadata) {
    result.status.provider_status = "disabled_by_config";
    return result;
  }
  if (path.empty()) {
    result.status.provider_status = "metadata_path_missing";
    return result;
  }
  std::ifstream input(path);
  if (!input) {
    result.status.provider_status = "metadata_file_missing";
    return result;
  }
  std::string line;
  if (!std::getline(input, line)) {
    result.status.provider_status = "metadata_file_empty";
    return result;
  }
  const std::vector<std::string> header = splitCsvLine(line);
  while (std::getline(input, line)) {
    if (line.empty()) {
      continue;
    }
    const std::vector<std::string> cells = splitCsvLine(line);
    std::unordered_map<std::string, std::string> row;
    for (std::size_t i = 0; i < header.size() && i < cells.size(); ++i) {
      row[header[i]] = cells[i];
    }
    Go2ReadinessLsimMetadataMeasurement measurement;
    measurement.time = scalar(row, "time", 0.0);
    measurement.source_status = stringValue(row, "source_status", "inactive");
    measurement.motion_state = stringValue(row, "motion_state", "UNKNOWN");
    measurement.contact_label = stringValue(row, "contact_label", "");
    measurement.quality_flag = stringValue(row, "quality_flag", "nominal");
    measurement.readiness_score = scalar(row, "readiness_score", 1.0);
    measurement.readiness_flag = boolValue(row, "readiness_flag", true);
    measurement.stance_stable = boolValue(row, "stance_stable", false);
    measurement.in_place_turn = boolValue(row, "in_place_turn", false);
    measurement.impact_or_rough = boolValue(row, "impact_or_rough", false);
    measurement.readiness_low = boolValue(row, "readiness_low", false);
    measurement.source_valid = boolValue(row, "source_valid", measurement.source_status == "active");
    if (measurement.source_status == "active" && measurement.source_valid) {
      ++result.status.valid_metadata_count;
    }
    result.measurements.push_back(measurement);
  }
  result.status.metadata_count = result.measurements.size();
  if (result.measurements.empty()) {
    result.status.provider_status = "metadata_file_no_rows";
    return result;
  }
  if (result.status.valid_metadata_count == 0) {
    result.status.provider_status = "no_active_metadata_rows";
    return result;
  }
  result.status.provider_status = "available";
  result.status.solver_enabled = true;
  result.status.readiness_metadata_first_class_lsim = true;
  return result;
}

}  // namespace legsa_v23_port_core
