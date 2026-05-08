#include "legsa_v23_core/mechanization/ins_mechanization.hpp"

#include "legsa_v23_core/common/earth.hpp"
#include "legsa_v23_core/common/rotation.hpp"

#include <algorithm>
#include <cmath>

namespace legsa_v23_core {
namespace {

// 中文说明：三维向量叉乘，用于 coning/sculling 和 Coriolis 项。
Vector3 cross(const Vector3& lhs, const Vector3& rhs) {
  return {lhs[1] * rhs[2] - lhs[2] * rhs[1], lhs[2] * rhs[0] - lhs[0] * rhs[2],
          lhs[0] * rhs[1] - lhs[1] * rhs[0]};
}

// 中文说明：三维向量加法，单位由调用侧保持一致。
Vector3 add(const Vector3& lhs, const Vector3& rhs) {
  return {lhs[0] + rhs[0], lhs[1] + rhs[1], lhs[2] + rhs[2]};
}

// 中文说明：三维向量缩放，避免引入外部线性代数依赖。
Vector3 scale(const Vector3& vector, double factor) {
  return {vector[0] * factor, vector[1] * factor, vector[2] * factor};
}

// 中文说明：矩阵向量乘法，矩阵按行优先存储。
Vector3 matVec(const Matrix3& matrix, const Vector3& vector) {
  return {matrix3At(matrix, 0, 0) * vector[0] + matrix3At(matrix, 0, 1) * vector[1] +
              matrix3At(matrix, 0, 2) * vector[2],
          matrix3At(matrix, 1, 0) * vector[0] + matrix3At(matrix, 1, 1) * vector[1] +
              matrix3At(matrix, 1, 2) * vector[2],
          matrix3At(matrix, 2, 0) * vector[0] + matrix3At(matrix, 2, 1) * vector[1] +
              matrix3At(matrix, 2, 2) * vector[2]};
}

}  // namespace

// 中文说明：主机械编排按 KF-GINS-style 顺序执行；vel/pos/att 顺序不可调换，N4H4B 只做预测传播。
void INSMechanization::insMech(const PVAState& pvapre, PVAState& pvacur, const IMUData& imupre,
                               const IMUData& imucur) {
  pvacur = pvapre;
  velUpdate(pvapre, pvacur, imupre, imucur);
  posUpdate(pvapre, pvacur, imucur);
  attUpdate(pvapre, pvacur, imupre, imucur);
}

// 中文说明：速度更新读取 process_data-compatible IMU 增量；Go2 原始 FLU 已在输入生成阶段转 FRD。
void INSMechanization::velUpdate(const PVAState& pvapre, PVAState& pvacur, const IMUData& imupre,
                                 const IMUData& imucur) {
  const double dt = std::max(imucur.dt, 1.0e-6);
  const Matrix3 cbn = Rotation::euler2matrix(pvapre.euler_rpy_rad);
  const Vector3 coning = scale(cross(imupre.dtheta, imucur.dvel), 0.5);
  const Vector3 sculling = scale(add(cross(imupre.dvel, imucur.dtheta), cross(imupre.dtheta, imucur.dvel)), 1.0 / 12.0);
  const Vector3 dvel_body = add(imucur.dvel, add(coning, sculling));
  const Vector3 dvel_nav = matVec(cbn, dvel_body);

  const Vector3 rmn = Earth::meridianPrimeVerticalRadius(pvapre.pos_blh_rad_m[0]);
  const Vector3 omega_ie_n = Earth::iewn(pvapre.pos_blh_rad_m[0]);
  const Vector3 omega_en_n = Earth::enwn(rmn, pvapre.pos_blh_rad_m, pvapre.vel_ned_mps);
  const Vector3 gravity_n = Earth::gravity(pvapre.pos_blh_rad_m);
  const Vector3 coriolis = cross(add(scale(omega_ie_n, 2.0), omega_en_n), pvapre.vel_ned_mps);

  for (std::size_t i = 0; i < kVector3Size; ++i) {
    pvacur.vel_ned_mps[i] = pvapre.vel_ned_mps[i] + dvel_nav[i] + (gravity_n[i] - coriolis[i]) * dt;
  }
}

// 中文说明：位置更新通过 midpoint velocity 积分，DRi 将 NED 位移转为 BLH 增量。
void INSMechanization::posUpdate(const PVAState& pvapre, PVAState& pvacur, const IMUData& imucur) {
  const double dt = std::max(imucur.dt, 1.0e-6);
  Vector3 mid_vel{};
  for (std::size_t i = 0; i < kVector3Size; ++i) {
    mid_vel[i] = 0.5 * (pvapre.vel_ned_mps[i] + pvacur.vel_ned_mps[i]);
  }
  const Matrix3 dri = Earth::DRi(pvapre.pos_blh_rad_m);
  const Vector3 delta_blh = matVec(dri, scale(mid_vel, dt));
  for (std::size_t i = 0; i < kVector3Size; ++i) {
    pvacur.pos_blh_rad_m[i] = pvapre.pos_blh_rad_m[i] + delta_blh[i];
  }
}

// 中文说明：姿态更新包含 b-frame coning correction 和 n-frame 转率修正；本阶段不做量测反馈。
void INSMechanization::attUpdate(const PVAState& pvapre, PVAState& pvacur, const IMUData& imupre,
                                 const IMUData& imucur) {
  const double dt = std::max(imucur.dt, 1.0e-6);
  const Vector3 rmn = Earth::meridianPrimeVerticalRadius(pvapre.pos_blh_rad_m[0]);
  const Vector3 omega_ie_n = Earth::iewn(pvapre.pos_blh_rad_m[0]);
  const Vector3 omega_en_n = Earth::enwn(rmn, pvapre.pos_blh_rad_m, pvapre.vel_ned_mps);
  const Vector3 delta_theta_b = add(imucur.dtheta, scale(cross(imupre.dtheta, imucur.dtheta), 1.0 / 12.0));
  const Vector3 delta_theta_n = scale(add(omega_ie_n, omega_en_n), -dt);

  const Quaternion qbn_pre = Rotation::euler2quaternion(pvapre.euler_rpy_rad);
  const Quaternion qnn = Rotation::rotvec2quaternion(delta_theta_n);
  const Quaternion qbb = Rotation::rotvec2quaternion(delta_theta_b);
  const Quaternion qbn_cur = Rotation::multiply(Rotation::multiply(qnn, qbn_pre), qbb);
  pvacur.euler_rpy_rad = Rotation::matrix2euler(Rotation::quaternion2matrix(qbn_cur));
}

}  // namespace legsa_v23_core
