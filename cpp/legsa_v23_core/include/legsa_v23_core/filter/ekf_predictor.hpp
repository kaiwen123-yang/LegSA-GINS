#pragma once

#include "legsa_v23_core/state/filter_state.hpp"

namespace legsa_v23_core {

// 中文说明：EKF predictor 只执行预测传播，不做 measurement update 或 state feedback。
void EKFPredict(FilterState& state, const Matrix21& Phi, const Matrix21& Qd);

}  // namespace legsa_v23_core
