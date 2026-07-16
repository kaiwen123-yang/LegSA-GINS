// LegSA-GINS source-backed port file.
// Source reference: KF-GINS-graduation-design / final_v23 reference.
// Source commit: 5a4471efd4fcfcdc31e258a677af354c652ff16f.
// Port role: mature GNSS/INS backbone implementation, not proposed novelty.
// Boundary: no final_v23 output substitution, no trace solver input.
// 中文说明：该文件为受控移植的组合导航骨架代码，后续创新因子将在该骨架通过 parity 后再接入。

#include "legsa_v23_port_core/fileio/gnss_file_loader.hpp"

#include "legsa_v23_port_core/common/earth.hpp"

#include <algorithm>
#include <cmath>
#include <fstream>
#include <sstream>
#include <stdexcept>

namespace legsa_v23_port_core {

GnssFileLoader::GnssFileLoader(const std::string& path) : rows_(loadFifteenColumn(path)) {}

// 中文说明：保留历史函数名；实际严格接受 15 列 legacy 或 18 列 explicit-validity GNSS。
std::vector<GnssData> GnssFileLoader::loadFifteenColumn(const std::string& path) {
  std::ifstream input(path);
  if (!input) {
    throw std::runtime_error("failed to open GNSS file: " + path);
  }
  std::vector<GnssData> rows;
  std::string line;
  std::size_t line_number = 0;
  while (std::getline(input, line)) {
    ++line_number;
    const auto first_non_space = line.find_first_not_of(" \t\r");
    if (first_non_space == std::string::npos || line[first_non_space] == '#') {
      continue;
    }
    std::istringstream stream(line);
    GnssData gnss;
    stream >> gnss.time >> gnss.blh_rad_m[0] >> gnss.blh_rad_m[1] >> gnss.blh_rad_m[2] >>
        gnss.std_ned_m[0] >> gnss.std_ned_m[1] >> gnss.std_ned_m[2] >>
        gnss.vel_ned_mps[0] >> gnss.vel_ned_mps[1] >> gnss.vel_ned_mps[2] >>
        gnss.vel_std_mps[0] >> gnss.vel_std_mps[1] >> gnss.vel_std_mps[2] >>
        gnss.yaw_deg >> gnss.yaw_std_deg;
    if (stream) {
      if (std::fabs(gnss.blh_rad_m[0]) > kPi / 2.0 || std::fabs(gnss.blh_rad_m[1]) > kPi) {
        gnss.blh_rad_m[0] = Earth::degToRad(gnss.blh_rad_m[0]);
        gnss.blh_rad_m[1] = Earth::degToRad(gnss.blh_rad_m[1]);
      }
      gnss.yaw_rad = Earth::degToRad(gnss.yaw_deg);
      gnss.yaw_std_rad = Earth::degToRad(std::max(gnss.yaw_std_deg, 0.001));
      int position_valid = 1;
      int velocity_valid = 1;
      int yaw_valid = 1;
      stream >> std::ws;
      if (!stream.eof()) {
        if (!(stream >> position_valid >> velocity_valid >> yaw_valid) ||
            (position_valid != 0 && position_valid != 1) ||
            (velocity_valid != 0 && velocity_valid != 1) ||
            (yaw_valid != 0 && yaw_valid != 1)) {
          throw std::runtime_error(
              "GNSS formal validity extension must be three 0/1 columns at line " +
              std::to_string(line_number));
        }
        stream >> std::ws;
        if (!stream.eof()) {
          throw std::runtime_error("unexpected GNSS column after formal validity fields at line " +
                                   std::to_string(line_number));
        }
        gnss.validity_explicit = true;
      }
      gnss.has_position = position_valid != 0;
      gnss.has_velocity = velocity_valid != 0;
      gnss.has_yaw = yaw_valid != 0;
      gnss.isvalid = false;
      rows.push_back(gnss);
    } else {
      // 中文说明：坏行不得静默丢弃，否则 formal update count 可能伪绿。
      throw std::runtime_error("GNSS row must contain exactly 15 or 18 columns at line " +
                               std::to_string(line_number));
    }
  }
  return rows;
}

bool GnssFileLoader::next(GnssData& gnss) {
  if (index_ >= rows_.size()) {
    return false;
  }
  gnss = rows_[index_++];
  return true;
}

bool GnssFileLoader::isEof() const {
  return index_ >= rows_.size();
}

bool GnssFileLoader::isOpen() const {
  return !rows_.empty();
}

bool GnssFileLoader::allValidityExplicit() const {
  return !rows_.empty() &&
         std::all_of(rows_.begin(), rows_.end(), [](const GnssData& row) {
           return row.validity_explicit;
         });
}

}  // namespace legsa_v23_port_core
