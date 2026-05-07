// 中文说明：本 reader 只消费 N4F 标准 IMU increment CSV；frame 必须已经是
// IMU_FRD_COMPATIBLE，避免 C++ runtime 内再次做 FLU->FRD。
// English note: No receiver IMU, trace, raw Doppler, or Go2 prior input is read here.

#include "legsa_gins/readers/standard_imu_increment_reader.hpp"

#include <fstream>
#include <sstream>
#include <stdexcept>
#include <string>
#include <unordered_map>

namespace legsa_gins::readers {
namespace {

using Row = std::unordered_map<std::string, std::string>;

const std::vector<std::string> kRequiredFields = {
    "timestamp",
    "tow",
    "dt",
    "dtheta_x",
    "dtheta_y",
    "dtheta_z",
    "dvel_x",
    "dvel_y",
    "dvel_z",
    "frame",
    "source_role",
};

std::vector<std::string> splitCsvLine(const std::string& line) {
  std::vector<std::string> fields;
  std::stringstream stream(line);
  std::string item;
  while (std::getline(stream, item, ',')) {
    if (!item.empty() && item.back() == '\r') {
      item.pop_back();
    }
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
      throw std::runtime_error("Standard IMU increment CSV missing field " + required +
                               ": " + path.string());
    }
  }
}

std::vector<Row> readRows(const std::filesystem::path& path, std::size_t max_rows) {
  std::ifstream stream(path);
  if (!stream) {
    throw std::runtime_error("Failed to open standard IMU increment CSV: " +
                             path.string());
  }
  std::string line;
  if (!std::getline(stream, line)) {
    throw std::runtime_error("Standard IMU increment CSV is empty: " + path.string());
  }
  const auto header = splitCsvLine(line);
  requireHeader(header, path);

  std::vector<Row> rows;
  while (std::getline(stream, line)) {
    if (line.empty()) {
      continue;
    }
    if (max_rows > 0 && rows.size() >= max_rows) {
      break;
    }
    const auto fields = splitCsvLine(line);
    if (fields.size() != header.size()) {
      throw std::runtime_error("Standard IMU increment row has wrong field count: " +
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
    throw std::runtime_error("Standard IMU increment CSV missing value: " + key);
  }
  return iter->second;
}

double asDouble(const Row& row, const std::string& key) {
  return std::stod(required(row, key));
}

}  // namespace

std::vector<types::LegSAImuSample> readStandardImuIncrementCsv(
    const std::filesystem::path& path,
    std::size_t max_rows) {
  const auto rows = readRows(path, max_rows);
  std::vector<types::LegSAImuSample> samples;
  double previous_tow = 0.0;
  bool has_previous = false;
  for (const auto& row : rows) {
    const auto frame = required(row, "frame");
    if (frame != "IMU_FRD_COMPATIBLE") {
      throw std::runtime_error("N4F IMU increment frame must be IMU_FRD_COMPATIBLE.");
    }
    types::LegSAImuSample sample;
    sample.tow = asDouble(row, "timestamp");
    sample.dt = asDouble(row, "dt");
    if (sample.dt <= 0.0) {
      throw std::runtime_error("N4F IMU increment dt must be positive.");
    }
    if (has_previous && sample.tow < previous_tow) {
      throw std::runtime_error("N4F IMU increment timestamp must be monotonic.");
    }
    previous_tow = sample.tow;
    has_previous = true;
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
    sample.frame = frame;
    samples.push_back(sample);
  }
  return samples;
}

}  // namespace legsa_gins::readers
