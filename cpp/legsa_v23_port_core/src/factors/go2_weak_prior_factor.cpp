// LegSA-GINS source-backed port file.
// Source reference: KF-GINS-graduation-design / final_v23 reference; LegSA-owned N7A extension.
// Source commit: 5a4471efd4fcfcdc31e258a677af354c652ff16f.
// Port role: Go2 body-state roll/pitch weak-prior extension, not final_v23 output substitution.
// Boundary: no trace solver input, no final_v23 output solver input, no Go2 position truth.
// LegSA-GINS N7A Go2 roll/pitch weak-prior factor.
// 中文说明：weak prior 通过 EKFUpdate 进入滤波器，不做输出修正，也不把 Go2 rpy 当 truth。

#include "legsa_v23_port_core/factors/go2_weak_prior_factor.hpp"

#include <algorithm>
#include <cmath>

namespace legsa_v23_port_core {

bool Go2WeakPriorFactor::isActive(const Go2AttitudeWeakPriorMeasurement& measurement) {
  return measurement.source_status == "active" && measurement.std_roll_rad > 0.0 && measurement.std_pitch_rad > 0.0;
}

std::vector<double> Go2WeakPriorFactor::residual(const NavState& state,
                                                 const Go2AttitudeWeakPriorMeasurement& measurement) {
  // 中文说明：residual = current roll/pitch - Go2 roll/pitch；Go2 只作为弱先验拉回，不是高精度真值。
  return {wrapRad(state.euler_rad[0] - measurement.roll_rad), wrapRad(state.euler_rad[1] - measurement.pitch_rad)};
}

Matrix Go2WeakPriorFactor::designMatrix() {
  Matrix H(2, RANK, 0.0);
  // 中文说明：error-state attitude feedback 与 yaw update 同号，负号保证 toy pull test 朝 Go2 prior 收敛。
  H(0, PHI_ID) = -1.0;
  H(1, PHI_ID + 1) = -1.0;
  return H;
}

Matrix Go2WeakPriorFactor::covariance(const Go2AttitudeWeakPriorMeasurement& measurement,
                                      const Go2AttitudeWeakPriorConfig& config) {
  (void)measurement;
  // 中文说明：std screen 由 runtime config 控制，CSV 只记录 builder 默认值，不能让默认值吞掉 3/10deg 诊断变体。
  const double roll_std = std::max(1.0e-6, config.go2_attitude_prior_std_roll_deg * D2R);
  const double pitch_std = std::max(1.0e-6, config.go2_attitude_prior_std_pitch_deg * D2R);
  Matrix R(2, 2, 0.0);
  R(0, 0) = roll_std * roll_std;
  R(1, 1) = pitch_std * pitch_std;
  return R;
}

double Go2WeakPriorFactor::wrapRad(double value) {
  while (value > kPi) {
    value -= 2.0 * kPi;
  }
  while (value <= -kPi) {
    value += 2.0 * kPi;
  }
  return value;
}

}  // namespace legsa_v23_port_core
