// LegSA-GINS source-backed port file.
// Source reference: KF-GINS-graduation-design / final_v23 reference.
// Source commit: 5a4471efd4fcfcdc31e258a677af354c652ff16f.
// Port role: mature GNSS/INS backbone implementation, not proposed novelty.
// Boundary: no final_v23 output substitution, no trace solver input.
// 中文说明：该文件为受控移植的组合导航骨架代码，后续创新因子将在该骨架通过 parity 后再接入。

#include "legsa_v23_port_core/fileio/gnss_file_loader.hpp"

#include <fstream>
#include <sstream>
#include <stdexcept>

namespace legsa_v23_port_core {

// 中文说明：读取 process_data-compatible 15 列高层 GNSS；R1 不读取 raw GNSS。
std::vector<GnssData> GnssFileLoader::loadFifteenColumn(const std::string& path) {
  std::ifstream input(path);
  if (!input) {
    throw std::runtime_error("failed to open GNSS file: " + path);
  }
  std::vector<GnssData> rows;
  std::string line;
  while (std::getline(input, line)) {
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
      rows.push_back(gnss);
    }
  }
  return rows;
}

}  // namespace legsa_v23_port_core

