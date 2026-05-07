// 中文说明：旋转转换是 N4 toy filter 基础工具，不声明 final_v23 姿态机制等价。
// English note: ZYX convention is roll(X), pitch(Y), yaw(Z).

#include "legsa_gins/math/rotation.hpp"

#include <algorithm>
#include <cmath>

#include "legsa_gins/math/angle.hpp"

namespace legsa_gins::math {

Quaternion eulerRadToQuaternion(double roll_rad, double pitch_rad, double yaw_rad) {
  const double cr = std::cos(0.5 * roll_rad);
  const double sr = std::sin(0.5 * roll_rad);
  const double cp = std::cos(0.5 * pitch_rad);
  const double sp = std::sin(0.5 * pitch_rad);
  const double cy = std::cos(0.5 * yaw_rad);
  const double sy = std::sin(0.5 * yaw_rad);

  return normalize({
      cr * cp * cy + sr * sp * sy,
      sr * cp * cy - cr * sp * sy,
      cr * sp * cy + sr * cp * sy,
      cr * cp * sy - sr * sp * cy,
  });
}

Vec3 quaternionToEulerRad(const Quaternion& q) {
  const Quaternion qn = normalize(q);
  const double sinr_cosp = 2.0 * (qn.w * qn.x + qn.y * qn.z);
  const double cosr_cosp = 1.0 - 2.0 * (qn.x * qn.x + qn.y * qn.y);
  const double roll = std::atan2(sinr_cosp, cosr_cosp);

  const double sinp = 2.0 * (qn.w * qn.y - qn.z * qn.x);
  const double pitch = std::abs(sinp) >= 1.0
                           ? std::copysign(0.5 * pi, sinp)
                           : std::asin(sinp);

  const double siny_cosp = 2.0 * (qn.w * qn.z + qn.x * qn.y);
  const double cosy_cosp = 1.0 - 2.0 * (qn.y * qn.y + qn.z * qn.z);
  const double yaw = wrapRad2Pi(std::atan2(siny_cosp, cosy_cosp));
  return {roll, pitch, yaw};
}

}  // namespace legsa_gins::math
