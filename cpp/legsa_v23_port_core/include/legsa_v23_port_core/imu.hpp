// LegSA-GINS source-backed port file.
// Source reference: KF-GINS-graduation-design / final_v23 reference.
// Source commit: 5a4471efd4fcfcdc31e258a677af354c652ff16f.
// Port role: mature GNSS/INS backbone implementation, not proposed novelty.
// Boundary: no final_v23 output substitution, no trace solver input.
// 中文说明：该文件为受控移植的组合导航骨架代码，后续创新因子将在该骨架通过 parity 后再接入。

#pragma once

#include "legsa_v23_port_core/types.hpp"

namespace legsa_v23_port_core {

// 中文说明：IMU 增量保持 KF-GINS 风格的 time/dtheta/dvel 合同，R1 不提交 raw IMU。
struct ImuData {
  double time = 0.0;
  double dt = 0.0;
  Vec3 dtheta = makeVec3(0.0, 0.0, 0.0);
  Vec3 dvel = makeVec3(0.0, 0.0, 0.0);
};

}  // namespace legsa_v23_port_core

