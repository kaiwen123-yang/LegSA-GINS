#include "legsa_v23_core/io/imu_file_loader.hpp"

#include <fstream>
#include <sstream>
#include <stdexcept>
#include <string>

namespace legsa_v23_core {
namespace {

// 中文说明：去掉注释和空行，避免把配置说明误读成 IMU 数据。
std::string trimDataLine(const std::string& line) {
  const auto comment_pos = line.find('#');
  std::string value = comment_pos == std::string::npos ? line : line.substr(0, comment_pos);
  const auto first = value.find_first_not_of(" \t\r\n");
  if (first == std::string::npos) {
    return "";
  }
  const auto last = value.find_last_not_of(" \t\r\n");
  return value.substr(first, last - first + 1);
}

}  // namespace

std::vector<IMUData> IMUFileLoader::load(const std::string& path) {
  // 中文说明：这里读的是 process_data-compatible IMU 增量，不是原始 sportmodestate。
  // FLU->FRD 已在 input generation 阶段完成，N4H4A reader 不能再次做坐标转换。
  std::ifstream input(path);
  if (!input) {
    throw std::runtime_error("failed to open IMU file: " + path);
  }

  std::vector<IMUData> data;
  std::string line;
  double previous_time = 0.0;
  bool has_previous = false;
  int line_number = 0;
  while (std::getline(input, line)) {
    ++line_number;
    const std::string cleaned = trimDataLine(line);
    if (cleaned.empty()) {
      continue;
    }

    std::istringstream parser(cleaned);
    IMUData imu;
    if (!(parser >> imu.time >> imu.dtheta[0] >> imu.dtheta[1] >> imu.dtheta[2] >> imu.dvel[0] >>
          imu.dvel[1] >> imu.dvel[2])) {
      throw std::runtime_error("invalid 7-column IMU row at line " + std::to_string(line_number));
    }

    if (has_previous) {
      imu.dt = imu.time - previous_time;
      if (imu.dt <= 0.0) {
        throw std::runtime_error("IMU time is not strictly monotonic at line " + std::to_string(line_number));
      }
    } else {
      imu.dt = 0.0;
      has_previous = true;
    }
    previous_time = imu.time;
    data.push_back(imu);
  }

  return data;
}

}  // namespace legsa_v23_core
