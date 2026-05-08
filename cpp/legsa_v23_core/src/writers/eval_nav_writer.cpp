#include "legsa_v23_core/writers/eval_nav_writer.hpp"

#include "legsa_v23_core/common/constants.hpp"

#include <iomanip>
#include <stdexcept>

namespace legsa_v23_core {

// 中文说明：EVAL_NAV writer 只提供格式桥接，不把评价 trace 变成 solver 输入。
EvalNavWriter::EvalNavWriter(const std::string& path) : output_(path) {
  if (!output_) {
    throw std::runtime_error("failed to open EVAL_NAV output: " + path);
  }
  output_ << "time,lat_deg,lon_deg,height_m,vn,ve,vd,roll_deg,pitch_deg,yaw_deg\n";
}

// 中文说明：评价输出按 writer 统一转 deg，保持 runtime 内部 BLH(rad,rad,m)。
void EvalNavWriter::write(double time, const NavState& state) {
  output_ << std::fixed << std::setprecision(9) << time << "," << state.pos_blh_rad_m[0] * kRadToDeg
          << "," << state.pos_blh_rad_m[1] * kRadToDeg << "," << state.pos_blh_rad_m[2] << ","
          << state.vel_ned_mps[0] << "," << state.vel_ned_mps[1] << "," << state.vel_ned_mps[2] << ","
          << state.euler_rpy_rad[0] * kRadToDeg << "," << state.euler_rpy_rad[1] * kRadToDeg << ","
          << state.euler_rpy_rad[2] * kRadToDeg << "\n";
}

}  // namespace legsa_v23_core
