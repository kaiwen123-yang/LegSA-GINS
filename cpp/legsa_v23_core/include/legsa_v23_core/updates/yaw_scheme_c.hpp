#pragma once

#include <string>

namespace legsa_v23_core {

// 中文说明：scheme_C 是规则型 yaw 量测门控，不是 Neural Gate，也不改变评价 yaw 门限。
struct YawSchemeCOptions {
  double soft_deg = 6.0;
  double hard_deg = 15.0;
  double downweight_scale = 2.5;
};

// 中文说明：yaw gate 模式用于 manifest 计数；只描述求解器量测接受策略。
enum class YawSchemeCMode {
  NORMAL,
  DOWNWEIGHT,
  REJECT,
};

// 中文说明：scheme_C 决策结果；effective_std_deg 只用于 R_yaw，不是性能修正。
struct YawSchemeCDecision {
  YawSchemeCMode mode = YawSchemeCMode::REJECT;
  bool accepted = false;
  double effective_std_deg = 0.0;
  std::string label = "YAW-REJECT";
};

// 中文说明：根据 yaw residual(deg) 做 NORMAL/DOWNWEIGHT/REJECT；不放宽 yaw >2 deg 评价口径。
YawSchemeCDecision applyYawSchemeC(double residual_deg, double yaw_std_deg,
                                   const YawSchemeCOptions& options = YawSchemeCOptions{});

}  // namespace legsa_v23_core
