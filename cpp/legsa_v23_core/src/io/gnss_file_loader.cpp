#include "legsa_v23_core/io/gnss_file_loader.hpp"

#include "legsa_v23_core/common/constants.hpp"

#include <fstream>
#include <sstream>
#include <stdexcept>
#include <string>

namespace legsa_v23_core {
namespace {

// 中文说明：GNSS 文本允许注释和空行，核心数据必须保持 15 列。
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

std::vector<GNSSData> GNSSFileLoader::load(const std::string& path) {
  // 中文说明：final_v23-style GNSS 是高层状态输入，不是 RAWX/SFRBX/RTCM raw solver。
  // 这一层只负责 15 列 runtime 输入解码，不产生 raw Doppler、RTK 或 FGO 因子声明。
  std::ifstream input(path);
  if (!input) {
    throw std::runtime_error("failed to open GNSS file: " + path);
  }

  std::vector<GNSSData> data;
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

    double lat_deg = 0.0;
    double lon_deg = 0.0;
    GNSSData gnss;
    std::istringstream parser(cleaned);
    if (!(parser >> gnss.time >> lat_deg >> lon_deg >> gnss.blh[2] >> gnss.std[0] >> gnss.std[1] >>
          gnss.std[2] >> gnss.vel[0] >> gnss.vel[1] >> gnss.vel[2] >> gnss.vel_std[0] >>
          gnss.vel_std[1] >> gnss.vel_std[2] >> gnss.yaw_deg >> gnss.yaw_std_deg)) {
      throw std::runtime_error("invalid 15-column GNSS row at line " + std::to_string(line_number));
    }

    if (has_previous && gnss.time <= previous_time) {
      throw std::runtime_error("GNSS time is not strictly monotonic at line " + std::to_string(line_number));
    }
    has_previous = true;
    previous_time = gnss.time;

    gnss.blh[0] = lat_deg * kDegToRad;
    gnss.blh[1] = lon_deg * kDegToRad;
    gnss.has_velocity = true;
    gnss.has_yaw = true;
    gnss.isvalid = true;
    data.push_back(gnss);
  }

  return data;
}

}  // namespace legsa_v23_core
