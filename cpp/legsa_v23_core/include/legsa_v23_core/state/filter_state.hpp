#pragma once

#include "legsa_v23_core/common/math_types.hpp"
#include "legsa_v23_core/state/nav_state.hpp"

namespace legsa_v23_core {

// 中文说明：21 维误差状态和协方差容器；N4H4A 只保持状态流转，不声明完整 EKF 数值等价。
struct FilterState {
  Vector21 dx = zeroVector21();
  Matrix21 covariance = diagonalMatrix21(1.0);
  NavState current_pva;
  NavState previous_pva;
};

}  // namespace legsa_v23_core
