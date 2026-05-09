// LegSA-GINS source-backed port file.
// Source reference: KF-GINS-graduation-design / final_v23 reference.
// Source commit: 5a4471efd4fcfcdc31e258a677af354c652ff16f.
// Port role: mature GNSS/INS backbone implementation, not proposed novelty.
// Boundary: no final_v23 output substitution, no trace solver input.
// 中文说明：该文件为受控移植的组合导航骨架代码，后续创新因子将在该骨架通过 parity 后再接入。

#include "legsa_v23_port_core/common/rotation.hpp"

#include <cmath>

namespace legsa_v23_port_core {
namespace {
constexpr double kPi = 3.14159265358979323846;
}

// 中文说明：按 roll/pitch/yaw 构造方向余弦矩阵，R2 将继续对齐 reference 细节。
Matrix3 Rotation::eulerToMatrix(const Vec3& euler_rad) {
  const double cr = std::cos(euler_rad[0]);
  const double sr = std::sin(euler_rad[0]);
  const double cp = std::cos(euler_rad[1]);
  const double sp = std::sin(euler_rad[1]);
  const double cy = std::cos(euler_rad[2]);
  const double sy = std::sin(euler_rad[2]);
  return Matrix3{{{{cp * cy, sr * sp * cy - cr * sy, cr * sp * cy + sr * sy}},
                  {{cp * sy, sr * sp * sy + cr * cy, cr * sp * sy - sr * cy}},
                  {{-sp, sr * cp, cr * cp}}}};
}

// 中文说明：矩阵转欧拉角只用于 toy 输出，避免把 R1 写成完整姿态 parity。
Vec3 Rotation::matrixToEuler(const Matrix3& matrix) {
  const double pitch = std::asin(-matrix[2][0]);
  const double roll = std::atan2(matrix[2][1], matrix[2][2]);
  const double yaw = std::atan2(matrix[1][0], matrix[0][0]);
  return makeVec3(roll, pitch, wrapRad(yaw));
}

// 中文说明：yaw wrap 保持 [-pi, pi]，不用于放宽 yaw gate。
double Rotation::wrapRad(double angle_rad) {
  while (angle_rad > kPi) {
    angle_rad -= 2.0 * kPi;
  }
  while (angle_rad < -kPi) {
    angle_rad += 2.0 * kPi;
  }
  return angle_rad;
}

}  // namespace legsa_v23_port_core
