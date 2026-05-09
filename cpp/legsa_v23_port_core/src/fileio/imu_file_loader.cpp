// LegSA-GINS source-backed port file.
// Source reference: KF-GINS-graduation-design / final_v23 reference.
// Source commit: 5a4471efd4fcfcdc31e258a677af354c652ff16f.
// Port role: mature GNSS/INS backbone implementation, not proposed novelty.
// Boundary: no final_v23 output substitution, no trace solver input.
// 中文说明：该文件为受控移植的组合导航骨架代码，后续创新因子将在该骨架通过 parity 后再接入。

#include "legsa_v23_port_core/fileio/imu_file_loader.hpp"

#include <fstream>
#include <sstream>
#include <stdexcept>

namespace legsa_v23_port_core {

ImuFileLoader::ImuFileLoader(const std::string& path) : rows_(loadSevenColumn(path)) {}

// 中文说明：读取 7 列 IMU 增量输入；本函数不会读取 final_v23 输出或 trace。
std::vector<ImuData> ImuFileLoader::loadSevenColumn(const std::string& path) {
  std::ifstream input(path);
  if (!input) {
    throw std::runtime_error("failed to open IMU file: " + path);
  }
  std::vector<ImuData> rows;
  std::string line;
  while (std::getline(input, line)) {
    if (line.empty() || line[0] == '#') {
      continue;
    }
    std::istringstream stream(line);
    ImuData imu;
    stream >> imu.time >> imu.dtheta[0] >> imu.dtheta[1] >> imu.dtheta[2] >> imu.dvel[0] >>
        imu.dvel[1] >> imu.dvel[2];
    if (stream) {
      if (!rows.empty()) {
        imu.dt = imu.time - rows.back().time;
      }
      // 中文说明：process_data 已完成 Go2 FLU->FRD，这里只读取增量，不做坐标二次转换。
      rows.push_back(imu);
    }
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
