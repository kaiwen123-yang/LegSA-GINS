#include "legsa_v23_core/filter/state_feedback.hpp"

#include "legsa_v23_core/common/earth.hpp"
#include "legsa_v23_core/common/rotation.hpp"

#include <cstddef>
#include <string>

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

// 中文说明：D2 diagnostic variant 只临时改变反馈符号/反馈侧，默认 baseline_current 完全保持原路径。
bool diagnosticVariantActive(const GINSOptions& options, const std::string& name) {
  return options.diagnostic_mode && options.diagnostic_model_variant == name;
}

}  // namespace

// 中文说明：位置/速度 residual 使用 predicted-observed，因此反馈时 pos/vel 采用负号修正。
// 中文说明：bias/scale 误差状态定义为估计误差，按 KF-GINS-style 直接加到名义 IMU 误差参数。
// 中文说明：姿态误差采用左乘 qpn*qbn，反馈后立刻把 dx 清零，避免重复修正。
void stateFeedback(FilterState& state) {
  GINSOptions options;
  stateFeedback(state, options);
}

// 中文说明：位置误差反馈：位置 residual 使用 predicted-observed，pos -= DRi(pos)*dx[P_ID]。
// 中文说明：速度误差反馈：速度 residual 使用 predicted-observed，vel -= dx[V_ID]。
// 中文说明：姿态误差反馈：baseline 使用正的 dx[PHI_ID] 构造 qpn，并采用左乘 qpn*qbn。
// 中文说明：IMU零偏误差反馈：gyrbias/accbias 按误差状态定义直接加 dx。
// 中文说明：IMU比例因子误差反馈：gyrscale/accscale 按误差状态定义直接加 dx。
// 中文说明：D2 variant 分支是诊断用探针，不是永久 solver fix 或性能实验；反馈后误差状态清零。
void stateFeedback(FilterState& state, const GINSOptions& options) {
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
    if (diagnosticVariantActive(options, "state_feedback_pos_vel_add")) {
      // 中文说明：D2 诊断：临时改为加号，排查位置/速度反馈符号，不作为正式结果。
      state.current_pva.pos_blh_rad_m[i] += delta_blh[i];
      state.current_pva.vel_ned_mps[i] += delta_velocity[i];
    } else {
      state.current_pva.pos_blh_rad_m[i] -= delta_blh[i];
      state.current_pva.vel_ned_mps[i] -= delta_velocity[i];
    }
  }

  if (!diagnosticVariantActive(options, "state_feedback_no_phi")) {
    // 中文说明：baseline_current 姿态误差采用左乘 qpn*qbn；D2 诊断允许临时改符号或右乘定位问题。
    Vector3 feedback_phi = delta_phi;
    if (diagnosticVariantActive(options, "state_feedback_phi_negative")) {
      for (double& value : feedback_phi) {
        value = -value;
      }
    }
    const Quaternion qbn = Rotation::euler2quaternion(state.current_pva.euler_rpy_rad);
    const Quaternion qpn = Rotation::rotvec2quaternion(feedback_phi);
    const Quaternion feedback_qbn = diagnosticVariantActive(options, "state_feedback_phi_right_multiply")
                                        ? Rotation::normalize(Rotation::multiply(qbn, qpn))
                                        : Rotation::normalize(Rotation::multiply(qpn, qbn));
    state.current_pva.euler_rpy_rad = Rotation::matrix2euler(Rotation::quaternion2matrix(feedback_qbn));
  }

  for (std::size_t i = 0; i < kVector3Size; ++i) {
    state.current_pva.gyro_bias[i] += state.dx[BG_ID + i];
    state.current_pva.acc_bias[i] += state.dx[BA_ID + i];
    state.current_pva.gyro_scale[i] += state.dx[SG_ID + i];
    state.current_pva.acc_scale[i] += state.dx[SA_ID + i];
  }
  state.dx = zeroVector21();
}

}  // namespace legsa_v23_core
