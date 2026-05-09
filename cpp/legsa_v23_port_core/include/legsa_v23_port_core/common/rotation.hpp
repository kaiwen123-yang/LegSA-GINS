// LegSA-GINS source-backed port file.
// Source reference: KF-GINS-graduation-design / final_v23 reference.
// Source commit: 5a4471efd4fcfcdc31e258a677af354c652ff16f.
// Port role: mature GNSS/INS backbone implementation, not proposed novelty.
// Boundary: no final_v23 output substitution, no trace solver input.
// 中文说明：该文件为受控移植的组合导航骨架代码，后续创新因子将在该骨架通过 parity 后再接入。

#pragma once

#include "legsa_v23_port_core/types.hpp"

namespace legsa_v23_port_core {

// 中文说明：Rotation 保留姿态转换接口，R1 使用轻量实现，R2 对齐 source-backed 细节。
class Rotation {
 public:
  static Matrix3 eulerToMatrix(const Vec3& euler_rad);
  static Vec3 matrixToEuler(const Matrix3& matrix);
  static double wrapRad(double angle_rad);
};

}  // namespace legsa_v23_port_core

