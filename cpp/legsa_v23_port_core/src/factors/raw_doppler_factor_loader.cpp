// LegSA-GINS source-backed port file.
// Source reference: KF-GINS-graduation-design / final_v23 reference; LegSA-owned N5A extension.
// Source commit: 5a4471efd4fcfcdc31e258a677af354c652ff16f.
// Port role: first proposed raw Doppler auxiliary factor path, not final_v23 output substitution.
// 中文说明：只接受 RAW_DOPPLER_VELOCITY_FACTORS.csv 语义字段，不能读取 NAV-PVT 或 .gnss。

#include "legsa_v23_port_core/factors/raw_doppler_factor_loader.hpp"

#include <algorithm>
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

}  // namespace

RawDopplerFactorLoadResult RawDopplerFactorLoader::loadCsv(const std::string& path,
                                                           const RawDopplerFactorConfig& config) {
  RawDopplerFactorLoadResult result;
  result.status.code_present = true;
  result.status.solver_enabled = false;
  result.status.factor_source = config.raw_doppler_factor_source;
  result.status.velocity_not_nav_pvt = true;
  result.status.velocity_not_gnss_15col = true;
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
  std::size_t provider_missing_count = 0;
  std::size_t valid_epoch_count = 0;
  while (std::getline(input, line)) {
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
    measurement.velocity_ned_mps = makeVec3(scalar(row, "vn", 0.0), scalar(row, "ve", 0.0), scalar(row, "vd", 0.0));
    measurement.std_ned_mps =
        makeVec3(scalar(row, "std_vn", 1.0), scalar(row, "std_ve", 1.0), scalar(row, "std_vd", 1.0));
    measurement.sat_count = static_cast<std::size_t>(std::max(0.0, scalar(row, "sat_count", 0.0)));
    measurement.gdop_like = scalar(row, "gdop_like", 0.0);
    measurement.provider_status = stringValue(row, "provider_status", "provider_missing");
    if (measurement.provider_status != "available") {
      ++provider_missing_count;
    } else {
      ++valid_epoch_count;
    }
    result.measurements.push_back(measurement);
  }
  result.status.epoch_count = result.measurements.size();
  result.status.valid_epoch_count = valid_epoch_count;
  if (result.measurements.empty()) {
    result.status.provider_status = "factor_file_no_rows";
    return result;
  }
  if (provider_missing_count > 0) {
    result.status.provider_status = "provider_missing_sat_state_export";
    return result;
  }
  result.status.provider_status = "available";
  result.status.solver_enabled = config.enable_raw_doppler;
  return result;
}

}  // namespace legsa_v23_port_core
