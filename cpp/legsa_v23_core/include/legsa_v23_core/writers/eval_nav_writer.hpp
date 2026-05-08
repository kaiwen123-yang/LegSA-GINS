#pragma once

#include "legsa_v23_core/state/nav_state.hpp"

#include <fstream>
#include <string>

namespace legsa_v23_core {

// 中文说明：写 EVAL_NAV.csv，供后续评价管线读取；N4H4A 不绑定 trace 或 final_v23 输出。
class EvalNavWriter {
 public:
  // 中文说明：打开 EVAL_NAV.csv 并写列头；列单位为 s/deg/deg/m/mps/deg。
  explicit EvalNavWriter(const std::string& path);

  // 中文说明：写一行评价导航状态，当前只来自 LegSA-v23-core skeleton runtime。
  void write(double time, const NavState& state);

 private:
  std::ofstream output_;
};

}  // namespace legsa_v23_core
