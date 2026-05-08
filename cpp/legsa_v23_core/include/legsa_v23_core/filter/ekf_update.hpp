#pragma once

#include "legsa_v23_core/state/filter_state.hpp"
#include "legsa_v23_core/updates/measurement_update.hpp"

namespace legsa_v23_core {

// 中文说明：执行松组合 EKF 量测更新；只更新误差状态 dx 和协方差 Cov。
// 中文说明：名义导航状态修正由 stateFeedback 单独完成，避免 output-only correction。
void EKFUpdate(FilterState& state, const MeasurementBlock& meas);

}  // namespace legsa_v23_core
