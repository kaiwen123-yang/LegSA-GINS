#include "legsa_v23_core/updates/yaw_scheme_c.hpp"

#include <algorithm>
#include <cmath>

namespace legsa_v23_core {

// 中文说明：scheme_C 是 final_v23-style 的稳健 yaw 量测门控骨架；N4H4C 只影响量测方差或拒绝量测。
YawSchemeCDecision applyYawSchemeC(double residual_deg, double yaw_std_deg, const YawSchemeCOptions& options) {
  const double abs_residual = std::abs(residual_deg);
  const double std_floor = std::max(yaw_std_deg, 1.0e-3);

  if (abs_residual <= options.soft_deg) {
    return {YawSchemeCMode::NORMAL, true, std_floor, "YAW-NORMAL"};
  }
  if (abs_residual <= options.hard_deg) {
    return {YawSchemeCMode::DOWNWEIGHT, true, std_floor * options.downweight_scale, "YAW-DOWNWEIGHT"};
  }
  return {YawSchemeCMode::REJECT, false, std_floor, "YAW-REJECT"};
}

}  // namespace legsa_v23_core
