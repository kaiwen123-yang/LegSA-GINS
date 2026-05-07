// 中文说明：reader 仅解析 toy CSV；不接触真实 BY2 raw data，不读取 trace，不读取 final_v23 output。
// English note: This parser exists for tests and local dry demos only.

#include "legsa_gins/readers/toy_csv_reader.hpp"

#include <fstream>
#include <sstream>
#include <stdexcept>
#include <string>
#include <unordered_map>

#include "legsa_gins/math/constants.hpp"

namespace legsa_gins::readers {
namespace {

using Row = std::unordered_map<std::string, std::string>;

std::vector<std::string> splitCsvLine(const std::string& line) {
  std::vector<std::string> fields;
  std::stringstream stream(line);
  std::string item;
  while (std::getline(stream, item, ',')) {
    fields.push_back(item);
  }
  return fields;
}

std::vector<Row> readRows(const std::filesystem::path& path) {
  std::ifstream stream(path);
  if (!stream) {
    throw std::runtime_error("Failed to open toy CSV: " + path.string());
  }
  std::string line;
  if (!std::getline(stream, line)) {
    throw std::runtime_error("Toy CSV is empty: " + path.string());
  }
  const auto header = splitCsvLine(line);
  std::vector<Row> rows;
  while (std::getline(stream, line)) {
    if (line.empty()) {
      continue;
    }
    const auto fields = splitCsvLine(line);
    if (fields.size() != header.size()) {
      throw std::runtime_error("Toy CSV row has wrong field count: " + path.string());
    }
    Row row;
    for (std::size_t index = 0; index < header.size(); ++index) {
      row[header[index]] = fields[index];
    }
    rows.push_back(row);
  }
  return rows;
}

std::string required(const Row& row, const std::string& key) {
  const auto iter = row.find(key);
  if (iter == row.end()) {
    throw std::runtime_error("Toy CSV missing required field: " + key);
  }
  return iter->second;
}

double asDouble(const Row& row, const std::string& key) {
  return std::stod(required(row, key));
}

bool asBool(const Row& row, const std::string& key) {
  const auto value = required(row, key);
  return value == "1" || value == "true" || value == "True";
}

void ensureMonotonic(double tow, double& previous_tow, bool& has_previous) {
  if (has_previous && tow < previous_tow) {
    throw std::runtime_error("Toy CSV timestamp must be monotonic non-decreasing.");
  }
  has_previous = true;
  previous_tow = tow;
}

}  // namespace

std::vector<types::LegSAImuSample> readToyImuCsv(const std::filesystem::path& path) {
  const auto rows = readRows(path);
  std::vector<types::LegSAImuSample> samples;
  double previous_tow = 0.0;
  bool has_previous = false;
  for (const auto& row : rows) {
    types::LegSAImuSample sample;
    sample.tow = asDouble(row, "tow");
    sample.dt = asDouble(row, "dt");
    sample.dtheta_rad = {
        asDouble(row, "dtheta_x"),
        asDouble(row, "dtheta_y"),
        asDouble(row, "dtheta_z"),
    };
    sample.dvel_mps = {
        asDouble(row, "dvel_x"),
        asDouble(row, "dvel_y"),
        asDouble(row, "dvel_z"),
    };
    ensureMonotonic(sample.tow, previous_tow, has_previous);
    samples.push_back(sample);
  }
  return samples;
}

std::vector<types::ReceiverNativeMeasurement> readToyReceiverCsv(
    const std::filesystem::path& path) {
  const auto rows = readRows(path);
  std::vector<types::ReceiverNativeMeasurement> measurements;
  double previous_tow = 0.0;
  bool has_previous = false;
  for (const auto& row : rows) {
    types::ReceiverNativeMeasurement meas;
    meas.tow = asDouble(row, "tow");
    meas.blh_rad_m = {
        asDouble(row, "lat_deg") * math::deg_to_rad,
        asDouble(row, "lon_deg") * math::deg_to_rad,
        asDouble(row, "height_m"),
    };
    meas.vel_ned_mps = {
        asDouble(row, "vn_mps"),
        asDouble(row, "ve_mps"),
        asDouble(row, "vd_mps"),
    };
    meas.yaw_heading_rad = asDouble(row, "yaw_deg") * math::deg_to_rad;
    const double pos_std = asDouble(row, "pos_std_m");
    const double vel_std = asDouble(row, "vel_std_mps");
    meas.pos_std_m = {pos_std, pos_std, pos_std};
    meas.vel_std_mps = {vel_std, vel_std, vel_std};
    meas.yaw_std_rad = asDouble(row, "yaw_std_deg") * math::deg_to_rad;
    meas.has_position = asBool(row, "has_position");
    meas.has_velocity = asBool(row, "has_velocity");
    meas.has_heading = asBool(row, "has_heading");
    meas.source = "toy_receiver_native";
    ensureMonotonic(meas.tow, previous_tow, has_previous);
    measurements.push_back(meas);
  }
  return measurements;
}

}  // namespace legsa_gins::readers
