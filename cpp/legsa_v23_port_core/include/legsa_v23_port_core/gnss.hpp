// LegSA-GINS source-backed port file.
// Source reference: KF-GINS-graduation-design / final_v23 reference.
// Source commit: 5a4471efd4fcfcdc31e258a677af354c652ff16f.
// Port role: mature GNSS/INS backbone implementation, not proposed novelty.
// Boundary: no final_v23 output substitution, no trace solver input.
// 中文说明：该文件为受控移植的组合导航骨架代码，后续创新因子将在该骨架通过 parity 后再接入。

#pragma once

#include "legsa_v23_port_core/types.hpp"

namespace legsa_v23_port_core {

// 中文说明：GNSSData 对齐 final_v23 高层 15 列 loose-coupled 输入角色，不表示 raw GNSS。
struct GnssData {
  double time = 0.0;
  Vec3 blh_rad_m = makeVec3(0.0, 0.0, 0.0);
  Vec3 std_ned_m = makeVec3(1.0, 1.0, 1.0);
  Vec3 vel_ned_mps = makeVec3(0.0, 0.0, 0.0);
  Vec3 vel_std_mps = makeVec3(1.0, 1.0, 1.0);
  double yaw_deg = 0.0;
  double yaw_std_deg = 1.0;
  double yaw_rad = 0.0;
  double yaw_std_rad = D2R;
  bool has_position = true;
  bool has_velocity = true;
  bool has_yaw = true;
  // 中文说明：legacy 15 列没有 validity 后缀；formal 18 列必须显式给出 position/velocity/yaw validity。
  bool validity_explicit = false;
  bool isvalid = false;
};

}  // namespace legsa_v23_port_core
