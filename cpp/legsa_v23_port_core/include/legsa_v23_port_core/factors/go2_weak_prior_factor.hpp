// LegSA-GINS source-backed port file.
// Source reference: KF-GINS-graduation-design / final_v23 reference; LegSA-owned N7A extension.
// Source commit: 5a4471efd4fcfcdc31e258a677af354c652ff16f.
// Port role: Go2 body-state roll/pitch weak-prior extension, not final_v23 output substitution.
// Boundary: no trace solver input, no final_v23 output solver input, no Go2 position truth.
// LegSA-GINS N7A Go2 roll/pitch weak-prior factor.
// 中文说明：factor 只构造 roll/pitch 残差和保守 R，不使用 Go2 position、trace 或 final_v23 输出。

#pragma once

#include "legsa_v23_port_core/factors/go2_weak_prior_types.hpp"
#include "legsa_v23_port_core/nav_state.hpp"
#include "legsa_v23_port_core/types.hpp"

#include <vector>

namespace legsa_v23_port_core {

class Go2WeakPriorFactor {
 public:
  static bool isActive(const Go2AttitudeWeakPriorMeasurement& measurement);
  static std::vector<double> residual(const NavState& state,
                                      const Go2AttitudeWeakPriorMeasurement& measurement);
  static Matrix designMatrix(const NavState& state);
  static Matrix covariance(const Go2AttitudeWeakPriorMeasurement& measurement,
                           const Go2AttitudeWeakPriorConfig& config);
  static double wrapRad(double value);
};

}  // namespace legsa_v23_port_core
