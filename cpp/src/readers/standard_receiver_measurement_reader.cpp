// 中文说明：N4E 读入标准化 receiver-native GNSS status；不构造 raw Doppler、trace 或 final_v23 输入。
// English note: has_velocity stays false because N4E does not derive velocity from this CSV.

#include "legsa_gins/readers/standard_receiver_measurement_reader.hpp"

#include <fstream>
#include <sstream>
#include <stdexcept>
#include <string>
#include <unordered_map>

#include "legsa_gins/math/constants.hpp"

namespace legsa_gins::readers {
namespace {

using Row = std::unordered_map<std::string, std::string>;

const std::vector<std::string> kRequiredFields = {
    "tow",
    "lat_deg",
    "lon_deg",
    "height_m",
    "pos_acc_h_m",
    "pos_acc_v_m",
    "has_position",
    "heading_deg",
    "heading_valid",
    "source_name",
};

std::vector<std::string> splitCsvLine(const std::string& line) {
  std::vector<std::string> fields;
  std::stringstream stream(line);
  std::string item;
  while (std::getline(stream, item, ',')) {
    fields.push_back(item);
  }
  return fields;
}

void requireHeader(const std::vector<std::string>& header,
                   const std::filesystem::path& path) {
  for (const auto& required : kRequiredFields) {
    bool present = false;
    for (const auto& field : header) {
      if (field == required) {
        present = true;
        break;
      }
    }
    if (!present) {
      throw std::runtime_error("Standard receiver CSV missing required field " + required +
                               ": " + path.string());
    }
  }
}

std::vector<Row> readRows(const std::filesystem::path& path) {
  std::ifstream stream(path);
  if (!stream) {
    throw std::runtime_error("Failed to open standard receiver CSV: " + path.string());
  }
  std::string line;
  if (!std::getline(stream, line)) {
    throw std::runtime_error("Standard receiver CSV is empty: " + path.string());
  }
  const auto header = splitCsvLine(line);
  requireHeader(header, path);

  std::vector<Row> rows;
  while (std::getline(stream, line)) {
    if (line.empty()) {
      continue;
    }
    const auto fields = splitCsvLine(line);
    if (fields.size() != header.size()) {
      throw std::runtime_error("Standard receiver CSV row has wrong field count: " +
                               path.string());
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
  if (iter == row.end() || iter->second.empty()) {
    throw std::runtime_error("Standard receiver CSV missing required value: " + key);
  }
  return iter->second;
}

double asDouble(const Row& row, const std::string& key) {
  return std::stod(required(row, key));
}

bool asBool(const Row& row, const std::string& key) {
  const auto value = required(row, key);
  return value == "1" || value == "true" || value == "True" || value == "TRUE";
}

void ensureMonotonic(double tow, double& previous_tow, bool& has_previous) {
  if (has_previous && tow < previous_tow) {
    throw std::runtime_error(
        "Standard receiver CSV timestamp must be monotonic non-decreasing.");
  }
  previous_tow = tow;
  has_previous = true;
}

}  // namespace

std::vector<types::ReceiverNativeMeasurement> readStandardReceiverStatusCsv(
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
    const double pos_acc_h = asDouble(row, "pos_acc_h_m");
    const double pos_acc_v = asDouble(row, "pos_acc_v_m");
    meas.pos_std_m = {pos_acc_h, pos_acc_h, pos_acc_v};
    meas.has_position = asBool(row, "has_position");
    meas.has_velocity = false;
    meas.has_heading = asBool(row, "heading_valid");
    if (meas.has_heading) {
      meas.yaw_heading_rad = asDouble(row, "heading_deg") * math::deg_to_rad;
    }
    meas.source = required(row, "source_name");
    ensureMonotonic(meas.tow, previous_tow, has_previous);
    measurements.push_back(meas);
  }
  return measurements;
}

}  // namespace legsa_gins::readers
