// LegSA-GINS source-backed port file.
// Source reference: KF-GINS-graduation-design / final_v23 reference.
// Source commit: 5a4471efd4fcfcdc31e258a677af354c652ff16f.
// Port role: mature GNSS/INS backbone implementation, not proposed novelty.
// Boundary: no final_v23 output substitution, no trace solver input.
// 中文说明：该文件为受控移植的组合导航骨架代码，后续创新因子将在该骨架通过 parity 后再接入。

#include "legsa_v23_port_core/kf_gins/insmech.hpp"

#include "legsa_v23_port_core/common/earth.hpp"
#include "legsa_v23_port_core/common/rotation.hpp"

namespace legsa_v23_port_core {

// 中文说明：R1 仅保留单步传播骨架；完整 vel/pos/att source parity 标为 TODO_R2_SOURCE_PORT。
NavState INSMech::propagateOneStep(const NavState& previous, const ImuData& imu) {
  NavState current = previous;
  current.time = imu.time;
  const double dt = imu.dt > 0.0 ? imu.dt : 0.01;
  current.vel_ned_mps = add(previous.vel_ned_mps, imu.dvel);
  const Matrix3 dri = Earth::DRi(previous.pos_blh_rad_m);
  const Vec3 delta_pos = scale(current.vel_ned_mps, dt);
  current.pos_blh_rad_m[0] += dri[0][0] * delta_pos[0];
  current.pos_blh_rad_m[1] += dri[1][1] * delta_pos[1];
  current.pos_blh_rad_m[2] += dri[2][2] * delta_pos[2];
  current.euler_rad[0] = Rotation::wrapRad(previous.euler_rad[0] + imu.dtheta[0]);
  current.euler_rad[1] = Rotation::wrapRad(previous.euler_rad[1] + imu.dtheta[1]);
  current.euler_rad[2] = Rotation::wrapRad(previous.euler_rad[2] + imu.dtheta[2]);
  return current;
}

}  // namespace legsa_v23_port_core

