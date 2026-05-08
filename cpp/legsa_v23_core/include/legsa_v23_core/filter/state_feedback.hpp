#pragma once

#include "legsa_v23_core/state/filter_state.hpp"

namespace legsa_v23_core {

// 中文说明：将 21 维误差状态反馈到名义 PVA 与 IMU bias/scale，并在反馈后清零 dx。
// 中文说明：这是 EKFUpdate 之后的独立步骤，不读取 final_v23 输出；not output-only correction。
void stateFeedback(FilterState& state);

}  // namespace legsa_v23_core
