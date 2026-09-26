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
#include <map>
#include <sstream>
#include <stdexcept>

namespace legsa_v23_port_core {

GnssFileLoader::GnssFileLoader(const std::string& path) : rows_(loadFifteenColumn(path)) {}

GnssFileLoader::GnssFileLoader(const std::string& path, const std::string& baseline3d_path)
    : rows_(loadBaseline3d(path, baseline3d_path)) {}

std::vector<GnssData> GnssFileLoader::loadBaseline3d(const std::string& path,
                                                 const std::string& baseline3d_path) {
  std::ifstream sidecar(baseline3d_path);
  if (!sidecar) throw std::runtime_error("failed to open baseline3d file: " + baseline3d_path);
  std::string line;
  if (!std::getline(sidecar, line)) throw std::runtime_error("BASELINE3D_MISSING_CSV_HEADER");
  if (!line.empty() && line.back() == '\r') line.pop_back();
  if (line != "time,b_n,b_e,b_d,pAcc1,pAcc2,valid") {
    throw std::runtime_error("BASELINE3D_INVALID_CSV_HEADER");
  }
  auto number = [](const std::string& token) {
    std::size_t used = 0;
    const double value = std::stod(token, &used);
    if (used != token.size() || !std::isfinite(value)) {
      throw std::runtime_error("BASELINE3D_NONFINITE_OR_MALFORMED_NUMBER");
    }
    return value;
  };
  std::map<double, Baseline3dMeasurement> observations;
  while (std::getline(sidecar, line)) {
    if (!line.empty() && line.back() == '\r') line.pop_back();
    if (line.empty()) continue;
    std::vector<std::string> tokens;
    std::size_t begin = 0;
    for (;;) {
      const auto comma = line.find(',', begin);
      tokens.push_back(line.substr(begin, comma == std::string::npos ? comma : comma - begin));
      if (comma == std::string::npos) break;
      begin = comma + 1;
    }
    if (tokens.size() != 7 || (tokens[6] != "0" && tokens[6] != "1")) {
      throw std::runtime_error("BASELINE3D_EXPECTED_SEVEN_COLUMNS_AND_VALID_0_1");
    }
    const double time = number(tokens[0]);
    Baseline3dMeasurement observation;
    observation.present = true;
    observation.valid = tokens[6] == "1";
    observation.reason = observation.valid ? "valid" : "provider_invalid";
    bool complete = true;
    for (std::size_t i = 1; i <= 5; ++i) {
      if (tokens[i].empty()) { complete = false; continue; }
      const double value = number(tokens[i]);
      if (i <= 3) observation.ned_m[i - 1] = value;
      else {
        if (value < 0.0) throw std::runtime_error("BASELINE3D_PACC_MUST_BE_NONNEGATIVE");
        (i == 4 ? observation.pacc1_m : observation.pacc2_m) = value;
      }
    }
    if (observation.valid && !complete) throw std::runtime_error("BASELINE3D_VALID_ROW_HAS_MISSING_VALUES");
    if (!observations.emplace(time, observation).second) {
      throw std::runtime_error("BASELINE3D_DUPLICATE_TIME");
    }
  }
  std::ifstream input(path);
  if (!input) throw std::runtime_error("failed to open GNSS file: " + path);
  std::vector<GnssData> rows;
  while (std::getline(input, line)) {
    if (line.empty() || line[0] == '#') continue;
    std::istringstream stream(line);
    GnssData gnss;
    std::string ignored_yaw, ignored_yaw_std, ignored_yaw_valid, trailing;
    int position_valid = -1, velocity_valid = -1;
    // Scalar heading tokens are deliberately strings: they cannot affect B3.
    if (!(stream >> gnss.time >> gnss.blh_rad_m[0] >> gnss.blh_rad_m[1] >> gnss.blh_rad_m[2] >>
          gnss.std_ned_m[0] >> gnss.std_ned_m[1] >> gnss.std_ned_m[2] >>
          gnss.vel_ned_mps[0] >> gnss.vel_ned_mps[1] >> gnss.vel_ned_mps[2] >>
          gnss.vel_std_mps[0] >> gnss.vel_std_mps[1] >> gnss.vel_std_mps[2] >>
          ignored_yaw >> ignored_yaw_std >> position_valid >> velocity_valid >> ignored_yaw_valid) ||
        (stream >> trailing) || !std::isfinite(gnss.time) ||
        (position_valid != 0 && position_valid != 1) ||
        (velocity_valid != 0 && velocity_valid != 1)) {
      throw std::runtime_error("BASELINE3D_EXPECTED_GNSS18_WITH_POSITION_VELOCITY_VALIDITY");
    }
    if (std::fabs(gnss.blh_rad_m[0]) > kPi / 2.0 || std::fabs(gnss.blh_rad_m[1]) > kPi) {
      gnss.blh_rad_m[0] = Earth::degToRad(gnss.blh_rad_m[0]);
      gnss.blh_rad_m[1] = Earth::degToRad(gnss.blh_rad_m[1]);
    }
    gnss.has_position = position_valid != 0;
    gnss.has_velocity = velocity_valid != 0;
    gnss.has_yaw = false;
    gnss.validity_explicit = true;
    const auto found = observations.find(gnss.time);  // exact double equality, no tolerance/nearest fit
    if (found != observations.end()) gnss.baseline3d = found->second;
    rows.push_back(gnss);
  }
  return rows;
}

// 中文说明：读取 process_data-compatible 15 列高层 GNSS；R1 不读取 raw GNSS。
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
    if (line.empty() || line[0] == '#') {
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
      if (stream >> position_valid) {
        if (!(stream >> velocity_valid >> yaw_valid) ||
            (position_valid != 0 && position_valid != 1) ||
            (velocity_valid != 0 && velocity_valid != 1) ||
            (yaw_valid != 0 && yaw_valid != 1)) {
          throw std::runtime_error(
              "GNSS formal validity extension must be three 0/1 columns at line " +
              std::to_string(line_number));
        }
        std::string trailing;
        if (stream >> trailing) {
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
