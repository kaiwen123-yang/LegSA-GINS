// LegSA-GINS source-backed port file.
// Source reference: KF-GINS-graduation-design / final_v23 reference.
// Source commit: 5a4471efd4fcfcdc31e258a677af354c652ff16f.
// Port role: mature GNSS/INS backbone implementation, not proposed novelty.
// Boundary: no final_v23 output substitution, no trace solver input.
// 中文说明：该文件为受控移植的组合导航骨架代码，后续创新因子将在该骨架通过 parity 后再接入。

#pragma once

#include "legsa_v23_port_core/imu.hpp"
#include "legsa_v23_port_core/nav_state.hpp"

namespace legsa_v23_port_core {

// 中文说明：INSMech 是 R1 source-backed skeleton，完整 KF-GINS 数学对齐留到 R2。
class INSMech {
 public:
  static NavState propagateOneStep(const NavState& previous, const ImuData& imu);
};

}  // namespace legsa_v23_port_core

