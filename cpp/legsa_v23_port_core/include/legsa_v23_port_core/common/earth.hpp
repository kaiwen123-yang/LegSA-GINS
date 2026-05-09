// LegSA-GINS source-backed port file.
// Source reference: KF-GINS-graduation-design / final_v23 reference.
// Source commit: 5a4471efd4fcfcdc31e258a677af354c652ff16f.
// Port role: mature GNSS/INS backbone implementation, not proposed novelty.
// Boundary: no final_v23 output substitution, no trace solver input.
// 中文说明：该文件为受控移植的组合导航骨架代码，后续创新因子将在该骨架通过 parity 后再接入。

#pragma once

#include "legsa_v23_port_core/types.hpp"

namespace legsa_v23_port_core {

// 中文说明：Earth 提供 R1 toy 所需的基础地球常数和 BLH/NED 高度符号合同。
class Earth {
 public:
  static constexpr double kWgs84A = 6378137.0;
  static constexpr double kWgs84E2 = 6.6943799901413165e-3;

  static double degToRad(double deg);
  static double radToDeg(double rad);
  static Matrix3 DR(const Vec3& blh_rad_m);
  static Matrix3 DRi(const Vec3& blh_rad_m);
};

}  // namespace legsa_v23_port_core

