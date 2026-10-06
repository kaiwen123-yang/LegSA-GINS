// LegSA-GINS source-backed port file.
// Source reference: KF-GINS-graduation-design / final_v23 reference.
// Source commit: 5a4471efd4fcfcdc31e258a677af354c652ff16f.
// Port role: mature GNSS/INS backbone implementation, not proposed novelty.
// Boundary: no final_v23 output substitution, no trace solver input.
// 中文说明：该文件为受控移植的组合导航骨架代码，后续创新因子将在该骨架通过 parity 后再接入。

#include "legsa_v23_port_core/fileio/imu_file_loader.hpp"

#include <fstream>
#include <cmath>
#include <sstream>
#include <stdexcept>

namespace legsa_v23_port_core {

ImuFileLoader::ImuFileLoader(const std::string& path, std::size_t expected_columns)
    : rows_(loadSevenColumn(path, expected_columns)) {}

// Seven columns retain the frozen legacy convention. Eight columns explicitly
// carry measured duration and require continuous support; a gap must be handled
// by the caller's declared restart policy, never by stretching an increment.
std::vector<ImuData> ImuFileLoader::loadSevenColumn(const std::string& path, std::size_t expected_columns) {
  std::ifstream input(path);
  if (!input) {
    throw std::runtime_error("failed to open IMU file: " + path);
  }
  std::vector<ImuData> rows;
  std::size_t columns = 0;
  std::string line;
  while (std::getline(input, line)) {
    if (line.empty() || line[0] == '#') {
      continue;
    }
    std::istringstream stream(line);
    std::vector<double> values;
    std::string token;
    while (stream >> token) {
      std::size_t used = 0;
      const double value = std::stod(token, &used);
      if (used != token.size() || !std::isfinite(value)) {
        throw std::runtime_error("IMU_INVALID_NUMERIC_TOKEN");
      }
      values.push_back(value);
    }
    if (values.size() != 7 && values.size() != 8) {
      throw std::runtime_error("IMU_EXPECTED_SEVEN_OR_EIGHT_COLUMNS");
    }
    if (expected_columns && values.size() != expected_columns) {
      throw std::runtime_error("IMU_CONFIG_DURATION_SCHEMA_MISMATCH");
    }
    if (columns && columns != values.size()) {
      throw std::runtime_error("IMU_MIXED_DURATION_SCHEMAS");
    }
    columns = values.size();
    ImuData imu;
    imu.time = values[0];
    for (std::size_t axis = 0; axis < 3; ++axis) {
      imu.dtheta[axis] = values[axis + 1];
      imu.dvel[axis] = values[axis + 4];
    }
    const double elapsed = rows.empty() ? 0.0 : imu.time - rows.back().time;
    if (!rows.empty() && elapsed <= 0.0) {
      throw std::runtime_error("IMU_TIME_NOT_STRICTLY_INCREASING");
    }
    imu.dt = columns == 8 ? values[7] : elapsed;
    if (columns == 8 && (imu.dt <= 0.0 ||
        (!rows.empty() && std::fabs(elapsed - imu.dt) > 1.1e-6))) {
      throw std::runtime_error("IMU_INCREMENT_DURATION_DISCONTINUITY");
    }
    // process_data already performed FLU->FRD; no second frame transform.
    rows.push_back(imu);
  }
  return rows;
}

bool ImuFileLoader::next(ImuData& imu) {
  if (index_ >= rows_.size()) {
    return false;
  }
  imu = rows_[index_++];
  return true;
}

bool ImuFileLoader::isEof() const {
  return index_ >= rows_.size();
}

bool ImuFileLoader::isOpen() const {
  return !rows_.empty();
}

double ImuFileLoader::starttime() const {
  return rows_.empty() ? 0.0 : rows_.front().time;
}

double ImuFileLoader::endtime() const {
  return rows_.empty() ? 0.0 : rows_.back().time;
}

}  // namespace legsa_v23_port_core
