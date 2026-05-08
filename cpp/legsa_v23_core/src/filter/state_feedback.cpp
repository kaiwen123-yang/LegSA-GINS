#include "legsa_v23_core/filter/state_feedback.hpp"

#include "legsa_v23_core/common/earth.hpp"
#include "legsa_v23_core/common/rotation.hpp"

#include <cstddef>

namespace legsa_v23_core {
namespace {

// 中文说明：三维矩阵乘三维向量；位置反馈中 DRi 把 NED(m) 小误差转回 BLH(rad,rad,m)。
Vector3 mat3Vec(const Matrix3& matrix, const Vector3& vector) {
  Vector3 result = zeroVector3();
  for (std::size_t row = 0; row < kVector3Size; ++row) {
    for (std::size_t col = 0; col < kVector3Size; ++col) {
      result[row] += matrix3At(matrix, row, col) * vector[col];
    }
  }
  return result;
}

}  // namespace

// 中文说明：位置/速度 residual 使用 predicted-observed，因此反馈时 pos/vel 采用负号修正。
// 中文说明：bias/scale 误差状态定义为估计误差，按 KF-GINS-style 直接加到名义 IMU 误差参数。
// 中文说明：姿态误差采用左乘 qpn*qbn，反馈后立刻把 dx 清零，避免重复修正。
void stateFeedback(FilterState& state) {
  Vector3 delta_position = zeroVector3();
  Vector3 delta_velocity = zeroVector3();
  Vector3 delta_phi = zeroVector3();
  for (std::size_t i = 0; i < kVector3Size; ++i) {
    delta_position[i] = state.dx[P_ID + i];
    delta_velocity[i] = state.dx[V_ID + i];
    delta_phi[i] = state.dx[PHI_ID + i];
  }

  const Vector3 delta_blh = mat3Vec(Earth::DRi(state.current_pva.pos_blh_rad_m), delta_position);
  for (std::size_t i = 0; i < kVector3Size; ++i) {
    state.current_pva.pos_blh_rad_m[i] -= delta_blh[i];
    state.current_pva.vel_ned_mps[i] -= delta_velocity[i];
  }

  const Quaternion qbn = Rotation::euler2quaternion(state.current_pva.euler_rpy_rad);
  const Quaternion qpn = Rotation::rotvec2quaternion(delta_phi);
  const Quaternion feedback_qbn = Rotation::normalize(Rotation::multiply(qpn, qbn));
  state.current_pva.euler_rpy_rad = Rotation::matrix2euler(Rotation::quaternion2matrix(feedback_qbn));

  for (std::size_t i = 0; i < kVector3Size; ++i) {
    state.current_pva.gyro_bias[i] += state.dx[BG_ID + i];
    state.current_pva.acc_bias[i] += state.dx[BA_ID + i];
    state.current_pva.gyro_scale[i] += state.dx[SG_ID + i];
    state.current_pva.acc_scale[i] += state.dx[SA_ID + i];
  }
  state.dx = zeroVector21();
}

}  // namespace legsa_v23_core
