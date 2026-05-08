#pragma once

#include "legsa_v23_core/state/filter_state.hpp"

#include <fstream>
#include <string>

namespace legsa_v23_core {

// 中文说明：写 LegSA_V23_STD.csv skeleton 协方差对角线；单位跟随 21-state 定义。
class StdWriter {
 public:
  // 中文说明：打开 STD CSV 并写列头；N4H4A 只输出占位协方差。
  explicit StdWriter(const std::string& path);

  // 中文说明：写 time 和 21 维协方差对角线。
  void write(double time, const FilterState& state);

 private:
  std::ofstream output_;
};

}  // namespace legsa_v23_core
