// LegSA-GINS source-backed port file.
// Source reference: KF-GINS-graduation-design / final_v23 reference.
// Source commit: 5a4471efd4fcfcdc31e258a677af354c652ff16f.
// Port role: mature GNSS/INS backbone implementation, not proposed novelty.
// Boundary: no final_v23 output substitution, no trace solver input.
// 中文说明：该文件为受控移植的组合导航骨架代码，后续创新因子将在该骨架通过 parity 后再接入。

#include "legsa_v23_port_core/kf_gins/insmech.hpp"

#include "legsa_v23_port_core/common/earth.hpp"
#include "legsa_v23_port_core/common/rotation.hpp"

#include <cmath>

namespace legsa_v23_port_core {

// 中文说明：机械编排顺序与 reference 一致，必须是 velUpdate -> posUpdate -> attUpdate。
void INSMech::insMech(const NavState& pvapre, NavState& pvacur, const ImuData& imupre, const ImuData& imucur) {
  pvacur = pvapre;
  pvacur.time = imucur.time;
  velUpdate(pvapre, pvacur, imupre, imucur);
  posUpdate(pvapre, pvacur, imupre, imucur);
  attUpdate(pvapre, pvacur, imupre, imucur);
}

// 中文说明：速度更新使用双子样 sculling/coning 项；imucur 是已经按 IMU error 补偿后的增量。
void INSMech::velUpdate(const NavState& pvapre, NavState& pvacur, const ImuData& imupre, const ImuData& imucur) {
  const double dt = imucur.dt > 0.0 ? imucur.dt : 0.01;
  const Vec3 wie_n = Earth::iewn(pvapre.pos_blh_rad_m);
  const Vec3 wen_n = Earth::enwn(pvapre.pos_blh_rad_m, pvapre.vel_ned_mps);
  const Vec3 d_vfb = add(add(imucur.dvel, scale(cross(imucur.dtheta, imucur.dvel), 0.5)),
                         add(scale(cross(imupre.dtheta, imucur.dvel), 1.0 / 12.0),
                             scale(cross(imupre.dvel, imucur.dtheta), 1.0 / 12.0)));
  const Matrix3 cnn = subtract(identityMatrix3(), Rotation::skewSymmetric(scale(add(wie_n, wen_n), dt * 0.5)));
  Vec3 d_vfn = multiply(multiply(cnn, pvapre.cbn), d_vfb);
  const Vec3 gl = makeVec3(0.0, 0.0, Earth::gravity(pvapre.pos_blh_rad_m));
  Vec3 d_vgn = scale(subtract(gl, cross(add(scale(wie_n, 2.0), wen_n), pvapre.vel_ned_mps)), dt);
  Vec3 midvel = add(pvapre.vel_ned_mps, scale(add(d_vfn, d_vgn), 0.5));

  // 中文说明：中间时刻重新计算重力和运输率，保持 NED D 轴和 height 符号一致。
  Vec3 midpos = add(pvapre.pos_blh_rad_m, multiply(Earth::DRi(pvapre.pos_blh_rad_m), scale(midvel, dt * 0.5)));
  auto rmn = Earth::meridianPrimeVerticalRadius(midpos[0]);
  Vec3 wie_mid = Earth::iewn(midpos);
  Vec3 wen_mid = makeVec3(midvel[1] / (rmn.second + midpos[2]),
                          -midvel[0] / (rmn.first + midpos[2]),
                          -midvel[1] * std::tan(midpos[0]) / (rmn.second + midpos[2]));
  Matrix3 cnn_mid = subtract(identityMatrix3(), Rotation::skewSymmetric(scale(add(wie_mid, wen_mid), dt * 0.5)));
  d_vfn = multiply(multiply(cnn_mid, pvapre.cbn), d_vfb);
  const Vec3 gl_mid = makeVec3(0.0, 0.0, Earth::gravity(midpos));
  d_vgn = scale(subtract(gl_mid, cross(add(scale(wie_mid, 2.0), wen_mid), midvel)), dt);
  pvacur.vel_ned_mps = add(pvapre.vel_ned_mps, add(d_vfn, d_vgn));
}

// 中文说明：位置更新用平均速度和 DRi，height 向上而 NED D 向下，因此 DRi(2,2)=-1。
void INSMech::posUpdate(const NavState& pvapre, NavState& pvacur, const ImuData& imupre, const ImuData& imucur) {
  (void)imupre;
  const double dt = imucur.dt > 0.0 ? imucur.dt : 0.01;
  const Vec3 midvel = scale(add(pvapre.vel_ned_mps, pvacur.vel_ned_mps), 0.5);
  const Vec3 midpos = add(pvapre.pos_blh_rad_m, multiply(Earth::DRi(pvapre.pos_blh_rad_m), scale(midvel, dt * 0.5)));
  const Vec3 delta_blh = multiply(Earth::DRi(midpos), scale(midvel, dt));
  pvacur.pos_blh_rad_m = add(pvapre.pos_blh_rad_m, delta_blh);
}

// 中文说明：姿态更新使用 n 系旋转和 b 系圆锥补偿，IMU 已在 process_data 中转 FRD，不能二次转换。
void INSMech::attUpdate(const NavState& pvapre, NavState& pvacur, const ImuData& imupre, const ImuData& imucur) {
  const double dt = imucur.dt > 0.0 ? imucur.dt : 0.01;
  const Vec3 midvel = scale(add(pvapre.vel_ned_mps, pvacur.vel_ned_mps), 0.5);
  const Vec3 midpos = scale(add(pvapre.pos_blh_rad_m, pvacur.pos_blh_rad_m), 0.5);
  const Vec3 wie_n = Earth::iewn(midpos);
  const Vec3 wen_n = Earth::enwn(midpos, midvel);
  const Quaternion qnn = Rotation::rotvec2quaternion(scale(add(wie_n, wen_n), -dt));
  const Vec3 coning = add(imucur.dtheta, scale(cross(imupre.dtheta, imucur.dtheta), 1.0 / 12.0));
  const Quaternion qbb = Rotation::rotvec2quaternion(coning);
  pvacur.qbn = Rotation::multiply(Rotation::multiply(qnn, pvapre.qbn), qbb);
  pvacur.cbn = Rotation::quaternion2matrix(pvacur.qbn);
  pvacur.euler_rad = Rotation::matrix2euler(pvacur.cbn);
}

NavState INSMech::propagateOneStep(const NavState& previous, const ImuData& imu) {
  NavState current = previous;
  insMech(previous, current, imu, imu);
  return current;
}

}  // namespace legsa_v23_port_core
