#pragma once

#include "legsa_v23_core/config/gins_options.hpp"
#include "legsa_v23_core/state/imu_types.hpp"
#include "legsa_v23_core/state/nav_state.hpp"

namespace legsa_v23_core {

// 中文说明：21-state / 18-noise 预测矩阵容器。N4H4B 只用于 EKF predict，不做量测更新。
struct ErrorStateMatrices {
  Matrix21 F = {};
  Matrix21 Phi = identityMatrix21();
  Matrix21 Qd = {};
  Matrix21x18 G = {};
};

// 中文说明：构造 F/G/Phi/Qd；误差状态为 p/v/phi/bg/ba/sg/sa，噪声为 ARW/VRW/BG/BA/SG/SA。
ErrorStateMatrices buildErrorStateMatrices(const PVAState& pvapre, const IMUData& imucur,
                                           const GINSOptions& options, const NoiseMatrix& Qc);

}  // namespace legsa_v23_core
