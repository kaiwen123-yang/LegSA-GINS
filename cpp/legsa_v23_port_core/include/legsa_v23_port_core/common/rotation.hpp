// LegSA-GINS source-backed port file.
// Source reference: KF-GINS-graduation-design / final_v23 reference.
// Source commit: 5a4471efd4fcfcdc31e258a677af354c652ff16f.
// Port role: mature GNSS/INS backbone implementation, not proposed novelty.
// Boundary: no final_v23 output substitution, no trace solver input.
// 中文说明：该文件为受控移植的组合导航骨架代码，后续创新因子将在该骨架通过 parity 后再接入。

#pragma once

#include "legsa_v23_port_core/types.hpp"

#include <array>

namespace legsa_v23_port_core {

// 中文说明：Rotation 按 KF-GINS 的 ZYX/RPY、body 到 NED 姿态约定实现。
class Rotation {
 public:
  static Quaternion normalize(const Quaternion& quaternion);
  static Quaternion multiply(const Quaternion& lhs, const Quaternion& rhs);
  static Quaternion inverse(const Quaternion& quaternion);
  static Quaternion matrix2quaternion(const Matrix3& matrix);
  static Matrix3 quaternion2matrix(const Quaternion& quaternion);
  static Vec3 matrix2euler(const Matrix3& matrix);
  static Vec3 quaternion2euler(const Quaternion& quaternion);
  static Quaternion rotvec2quaternion(const Vec3& rotvec);
  static Vec3 quaternion2vector(const Quaternion& quaternion);
  static Matrix3 euler2matrix(const Vec3& euler_rad);
  static Quaternion euler2quaternion(const Vec3& euler_rad);
  static Matrix3 skewSymmetric(const Vec3& vector);
  static std::array<std::array<double, 4>, 4> quaternionleft(const Quaternion& quaternion);
  static std::array<std::array<double, 4>, 4> quaternionright(const Quaternion& quaternion);
  static Matrix3 eulerToMatrix(const Vec3& euler_rad);
  static Vec3 matrixToEuler(const Matrix3& matrix);
  static double wrapRad(double angle_rad);
  static double wrap2Pi(double angle_rad);
};

}  // namespace legsa_v23_port_core
