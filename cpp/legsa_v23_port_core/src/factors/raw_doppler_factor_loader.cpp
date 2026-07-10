// LegSA-GINS source-backed port file.
// Source reference: KF-GINS-graduation-design / final_v23 reference; LegSA-owned N5A extension.
// Source commit: 5a4471efd4fcfcdc31e258a677af354c652ff16f.
// Port role: first proposed raw Doppler auxiliary factor path, not final_v23 output substitution.
// 中文说明：只接受 RAW_DOPPLER_VELOCITY_FACTORS.csv 语义字段，不能读取 NAV-PVT 或 .gnss。

#include "legsa_v23_port_core/factors/raw_doppler_factor_loader.hpp"

#include <algorithm>
#include <cmath>
#include <cctype>
#include <fstream>
#include <sstream>
#include <stdexcept>
#include <unordered_map>

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
  if (it == row.end()) {
    return fallback;
  }
  std::istringstream stream(it->second);
  double value = fallback;
  stream >> value;
  return value;
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
  std::string value = stringValue(row, key, fallback ? "true" : "false");
  std::transform(value.begin(), value.end(), value.begin(), [](unsigned char ch) {
    return static_cast<char>(std::tolower(ch));
  });
  if (value == "true" || value == "1" || value == "yes") {
    return true;
  }
  if (value == "false" || value == "0" || value == "no") {
    return false;
  }
  return fallback;
}

bool hasColumn(const std::vector<std::string>& header, const std::string& name) {
  return std::find(header.begin(), header.end(), name) != header.end();
}

bool isSha256(const std::string& value) {
  return value.size() == 64 &&
         std::all_of(value.begin(), value.end(), [](unsigned char ch) {
           return std::isdigit(ch) || (ch >= 'a' && ch <= 'f');
         });
}

[[noreturn]] void lineageFailure(const std::string& detail) {
  throw std::runtime_error("BLOCKED_CLEAN1_RAW_DOPPLER_BACKEND_LINEAGE_NOT_PROVEN: " + detail);
}

void validateFormalLineageConfig(const RawDopplerFactorConfig& config) {
  if (config.raw_doppler_backend_id.empty() ||
      config.raw_doppler_backend_source_files.empty() ||
      config.raw_doppler_backend_source_hashes.empty() ||
      config.covariance_policy.empty()) {
    lineageFailure("missing backend/source/covariance identity");
  }
  if (!isSha256(config.helper_executable_hash) ||
      !isSha256(config.obs_source_hash) ||
      !isSha256(config.nav_source_hash) ||
      !isSha256(config.conversion_config_hash)) {
    lineageFailure("helper/obs/nav/config hash must be lowercase SHA256");
  }
  if (config.rtklib_position_solution_used_as_solver_input ||
      config.nav_pvt_velocity_used_as_raw_doppler ||
      config.gnss_velocity_used_as_raw_doppler ||
      config.status_fallback_used ||
      config.legacy_provider_used) {
    lineageFailure("forbidden Raw Doppler fallback/input flag is true");
  }
}

}  // namespace

RawDopplerFactorLoadResult RawDopplerFactorLoader::loadCsv(const std::string& path,
                                                           const RawDopplerFactorConfig& config) {
  RawDopplerFactorLoadResult result;
  result.status.code_present = true;
  result.status.solver_enabled = false;
  result.status.factor_source = config.raw_doppler_factor_source;
  result.status.velocity_not_nav_pvt = true;
  result.status.velocity_not_gnss_15col = true;
  result.status.status_fallback_used = config.status_fallback_used;
  result.status.legacy_provider_used = config.legacy_provider_used;
  result.status.backend_id = config.raw_doppler_backend_id;
  result.status.obs_source_hash = config.obs_source_hash;
  result.status.nav_source_hash = config.nav_source_hash;
  result.status.conversion_config_hash = config.conversion_config_hash;
  result.status.covariance_policy = config.covariance_policy;
  if (config.formal_lineage_required) {
    validateFormalLineageConfig(config);
  }
  if (path.empty()) {
    result.status.provider_status = "factor_path_missing";
    return result;
  }
  std::ifstream input(path);
  if (!input) {
    result.status.provider_status = "factor_file_missing";
    return result;
  }
  std::string line;
  if (!std::getline(input, line)) {
    result.status.provider_status = "factor_file_empty";
    return result;
  }
  const std::vector<std::string> header = splitCsvLine(line);
  if (config.formal_lineage_required) {
    const std::vector<std::string> required_columns{
        "time", "source_time", "vn", "ve", "vd", "std_vn", "std_ve", "std_vd",
        "sat_count", "gdop_like", "provider_status", "valid", "raw_doppler_backend_id",
        "obs_source_hash", "nav_source_hash", "conversion_config_hash", "covariance_policy"};
    for (const auto& column : required_columns) {
      if (!hasColumn(header, column)) {
        lineageFailure("formal provider missing column " + column);
      }
    }
    if (!hasColumn(header, "quality") && !hasColumn(header, "quality_flag")) {
      lineageFailure("formal provider missing quality/quality_flag column");
    }
  }
  std::size_t provider_missing_count = 0;
  std::size_t valid_epoch_count = 0;
  std::size_t invalid_epoch_count = 0;
  std::size_t line_number = 1;
  while (std::getline(input, line)) {
    ++line_number;
    if (line.empty()) {
      continue;
    }
    const std::vector<std::string> cells = splitCsvLine(line);
    std::unordered_map<std::string, std::string> row;
    for (std::size_t i = 0; i < header.size() && i < cells.size(); ++i) {
      row[header[i]] = cells[i];
    }
    RawDopplerVelocityMeasurement measurement;
    measurement.time = scalar(row, "time", 0.0);
    measurement.source_time = scalar(row, "source_time", measurement.time);
    measurement.velocity_ned_mps = makeVec3(scalar(row, "vn", 0.0), scalar(row, "ve", 0.0), scalar(row, "vd", 0.0));
    measurement.std_ned_mps =
        makeVec3(scalar(row, "std_vn", 1.0), scalar(row, "std_ve", 1.0), scalar(row, "std_vd", 1.0));
    measurement.sat_count = static_cast<std::size_t>(std::max(0.0, scalar(row, "sat_count", 0.0)));
    measurement.gdop_like = scalar(row, "gdop_like", 0.0);
    measurement.provider_status = stringValue(row, "provider_status", "provider_missing");
    measurement.quality = stringValue(row, "quality", stringValue(row, "quality_flag", "invalid"));
    measurement.valid = config.formal_lineage_required ? boolValue(row, "valid", false)
                                                       : measurement.provider_status == "available";
    measurement.raw_doppler_backend_id = stringValue(row, "raw_doppler_backend_id", "");
    measurement.obs_source_hash = stringValue(row, "obs_source_hash", "");
    measurement.nav_source_hash = stringValue(row, "nav_source_hash", "");
    measurement.conversion_config_hash = stringValue(row, "conversion_config_hash", "");
    measurement.covariance_policy = stringValue(row, "covariance_policy", "");
    measurement.lineage_valid = !config.formal_lineage_required ||
        (measurement.raw_doppler_backend_id == config.raw_doppler_backend_id &&
         measurement.obs_source_hash == config.obs_source_hash &&
         measurement.nav_source_hash == config.nav_source_hash &&
         measurement.conversion_config_hash == config.conversion_config_hash &&
         measurement.covariance_policy == config.covariance_policy);
    if (config.formal_lineage_required &&
        (!measurement.lineage_valid || !std::isfinite(measurement.time) ||
         !std::isfinite(measurement.source_time) || measurement.quality.empty())) {
      lineageFailure("row " + std::to_string(line_number) + " has invalid provenance/time/quality");
    }
    if (!measurement.valid || measurement.provider_status != "available") {
      ++provider_missing_count;
      ++invalid_epoch_count;
    } else {
      ++valid_epoch_count;
    }
    result.measurements.push_back(measurement);
  }
  result.status.epoch_count = result.measurements.size();
  result.status.valid_epoch_count = valid_epoch_count;
  result.status.invalid_epoch_count = invalid_epoch_count;
  if (result.measurements.empty()) {
    result.status.provider_status = "factor_file_no_rows";
    return result;
  }
  if (!config.formal_lineage_required && provider_missing_count > 0) {
    result.status.provider_status = "provider_missing_sat_state_export";
    return result;
  }
  if (config.formal_lineage_required && valid_epoch_count == 0) {
    lineageFailure("formal provider has zero valid epochs");
  }
  result.status.provider_status = "available";
  result.status.solver_enabled = config.enable_raw_doppler;
  result.status.lineage_proven = config.formal_lineage_required;
  return result;
}

}  // namespace legsa_v23_port_core
