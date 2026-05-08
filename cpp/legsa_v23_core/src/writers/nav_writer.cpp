#include "legsa_v23_core/writers/nav_writer.hpp"

#include "legsa_v23_core/common/constants.hpp"

#include <iomanip>
#include <stdexcept>

namespace legsa_v23_core {

// 中文说明：NAV writer 写 LegSA_V23_NAV.nav 合约字段，不写 final_v23 替代输出。
NavWriter::NavWriter(const std::string& path) : output_(path) {
  if (!output_) {
    throw std::runtime_error("failed to open NAV output: " + path);
  }
  output_ << "# time lat_deg lon_deg height_m vn ve vd roll_deg pitch_deg yaw_deg\n";
}

// 中文说明：NAV 行单位转换集中在 writer；roll/pitch/yaw 为 deg，yaw 遵循 NED heading 输出约定。
void NavWriter::write(double time, const NavState& state) {
  output_ << std::fixed << std::setprecision(9) << time << " "
          << state.pos_blh_rad_m[0] * kRadToDeg << " " << state.pos_blh_rad_m[1] * kRadToDeg << " "
          << state.pos_blh_rad_m[2] << " " << state.vel_ned_mps[0] << " " << state.vel_ned_mps[1] << " "
          << state.vel_ned_mps[2] << " " << state.euler_rpy_rad[0] * kRadToDeg << " "
          << state.euler_rpy_rad[1] * kRadToDeg << " " << state.euler_rpy_rad[2] * kRadToDeg << "\n";
}

}  // namespace legsa_v23_core
