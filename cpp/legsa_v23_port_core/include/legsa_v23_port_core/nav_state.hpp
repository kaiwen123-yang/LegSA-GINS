// LegSA-GINS source-backed port file.
// Source reference: KF-GINS-graduation-design / final_v23 reference.
// Source commit: 5a4471efd4fcfcdc31e258a677af354c652ff16f.
// Port role: mature GNSS/INS backbone implementation, not proposed novelty.
// Boundary: no final_v23 output substitution, no trace solver input.
// 中文说明：该文件为受控移植的组合导航骨架代码，后续创新因子将在该骨架通过 parity 后再接入。

#pragma once

#include "legsa_v23_port_core/types.hpp"

namespace legsa_v23_port_core {

// 中文说明：导航状态保持 BLH(rad/rad/m)、NED 速度和 RPY(rad)，便于后续 exact port parity。
struct NavState {
  double time = 0.0;
  Vec3 pos_blh_rad_m = makeVec3(0.0, 0.0, 0.0);
  Vec3 vel_ned_mps = makeVec3(0.0, 0.0, 0.0);
  Vec3 euler_rad = makeVec3(0.0, 0.0, 0.0);
  Matrix3 cbn = identityMatrix3();
  Quaternion qbn{};
  ImuError imu_error;
};

}  // namespace legsa_v23_port_core
