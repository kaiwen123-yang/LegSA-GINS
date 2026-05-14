// LegSA-GINS source-backed port file.
// Source reference: KF-GINS-graduation-design / final_v23 reference.
// Source commit: 5a4471efd4fcfcdc31e258a677af354c652ff16f.
// Port role: N8G feedback observation loader attached to the source-backed EKF backbone, not proposed novelty.
// Boundary: runtime-only FGO feedback observations, no output substitution.
// 中文说明：loader 只解析 FGO_FEEDBACK_OBSERVATIONS.csv 语义字段，不读取 trace/final_v23 输出。

#include "legsa_v23_port_core/fgo_feedback/fgo_feedback.hpp"

#include <algorithm>
#include <cctype>
#include <cmath>
#include <fstream>
#include <sstream>
#include <stdexcept>
#include <unordered_map>

namespace legsa_v23_port_core::fgo_feedback {
namespace {

std::string trim(std::string value) {
  auto not_space = [](unsigned char ch) { return !std::isspace(ch); };
  value.erase(value.begin(), std::find_if(value.begin(), value.end(), not_space));
  value.erase(std::find_if(value.rbegin(), value.rend(), not_space).base(), value.end());
  return value;
}

std::vector<std::string> splitCsvLine(const std::string& line) {
  std::vector<std::string> cells;
  std::string cell;
  std::istringstream stream(line);
  while (std::getline(stream, cell, ',')) {
    cells.push_back(trim(cell));
  }
  return cells;
}

bool parseBool(const std::string& raw) {
  std::string value = trim(raw);
  std::transform(value.begin(), value.end(), value.begin(), [](unsigned char ch) { return std::tolower(ch); });
  return value == "1" || value == "true" || value == "yes" || value == "on";
}

double parseDouble(const std::unordered_map<std::string, std::string>& row,
                   const std::string& key,
                   double fallback = 0.0) {
  const auto it = row.find(key);
  if (it == row.end() || it->second.empty()) {
    return fallback;
  }
  try {
    return std::stod(it->second);
  } catch (const std::exception&) {
    return fallback;
  }
}

std::size_t parseSize(const std::unordered_map<std::string, std::string>& row,
                      const std::string& key,
                      std::size_t fallback = 0) {
  return static_cast<std::size_t>(std::max(0.0, parseDouble(row, key, static_cast<double>(fallback))));
}

Vec3 positiveStd(Vec3 value, double floor_value) {
  return makeVec3(std::max(std::fabs(value[0]), floor_value),
                  std::max(std::fabs(value[1]), floor_value),
                  std::max(std::fabs(value[2]), floor_value));
}

}  // namespace

double wrapRadians(double value) {
  while (value > kPi) {
    value -= 2.0 * kPi;
  }
  while (value <= -kPi) {
    value += 2.0 * kPi;
  }
  return value;
}

double wrapDegrees(double value) {
  while (value > 180.0) {
    value -= 360.0;
  }
  while (value <= -180.0) {
    value += 360.0;
  }
  return value;
}

FgoFeedbackLoadResult FgoFeedbackLoader::loadCsv(const std::string& path, const FgoFeedbackConfig& config) {
  FgoFeedbackLoadResult result;
  result.status.code_present = true;
  if (!config.enable_fgo_feedback) {
    result.status.provider_status = "disabled";
    return result;
  }
  std::ifstream input(path);
  if (!input) {
    result.status.provider_status = "feedback_csv_missing";
    return result;
  }
  std::string header_line;
  if (!std::getline(input, header_line)) {
    result.status.provider_status = "feedback_csv_empty";
    return result;
  }
  const auto headers = splitCsvLine(header_line);
  std::string line;
  while (std::getline(input, line)) {
    if (trim(line).empty()) {
      continue;
    }
    const auto cells = splitCsvLine(line);
    std::unordered_map<std::string, std::string> row;
    for (std::size_t i = 0; i < headers.size() && i < cells.size(); ++i) {
      row[headers[i]] = cells[i];
    }
    FgoFeedbackObservation obs;
    obs.time = parseDouble(row, "time");
    obs.position_ned_m = makeVec3(parseDouble(row, "pN"), parseDouble(row, "pE"), parseDouble(row, "pD"));
    obs.velocity_ned_mps = makeVec3(parseDouble(row, "vN"), parseDouble(row, "vE"), parseDouble(row, "vD"));
    obs.attitude_rad = makeVec3(parseDouble(row, "roll") * D2R,
                                parseDouble(row, "pitch") * D2R,
                                parseDouble(row, "yaw") * D2R);
    obs.position_std_m = positiveStd(makeVec3(parseDouble(row, "std_pN", 3.0),
                                              parseDouble(row, "std_pE", 3.0),
                                              parseDouble(row, "std_pD", 4.0)),
                                     1.0e-3);
    obs.velocity_std_mps = positiveStd(makeVec3(parseDouble(row, "std_vN", 0.5),
                                                parseDouble(row, "std_vE", 0.5),
                                                parseDouble(row, "std_vD", 0.8)),
                                       1.0e-3);
    obs.attitude_std_rad = positiveStd(makeVec3(parseDouble(row, "std_roll", 2.0) * D2R,
                                                parseDouble(row, "std_pitch", 2.0) * D2R,
                                                parseDouble(row, "std_yaw", 3.0) * D2R),
                                       1.0e-6);
    obs.source_window_start = parseDouble(row, "source_window_start", obs.time);
    obs.source_window_end = parseDouble(row, "source_window_end", obs.time);
    obs.feedback_valid = parseBool(row["feedback_valid"]);
    obs.window_epoch_count = parseSize(row, "window_epoch_count", 0);
    obs.feedback_mode = row.count("feedback_mode") ? row["feedback_mode"] : config.fgo_feedback_mode;
    result.observations.push_back(obs);
  }
  result.status.observation_count = result.observations.size();
  result.status.valid_observation_count = static_cast<std::size_t>(std::count_if(
      result.observations.begin(), result.observations.end(), [](const FgoFeedbackObservation& obs) {
        return obs.feedback_valid;
      }));
  result.status.no_future_data = std::all_of(
      result.observations.begin(), result.observations.end(), [](const FgoFeedbackObservation& obs) {
        return obs.source_window_end <= obs.time + 1.0e-9;
      });
  result.status.solver_enabled =
      config.enable_fgo_feedback && result.status.observation_count > 0 &&
      (!config.fgo_feedback_no_future_data_required || result.status.no_future_data);
  result.status.provider_status = result.status.solver_enabled ? "available" : "no_feedback_observations";
  return result;
}

}  // namespace legsa_v23_port_core::fgo_feedback
