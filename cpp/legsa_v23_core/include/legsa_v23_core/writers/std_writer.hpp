#pragma once

#include "legsa_v23_core/state/filter_state.hpp"

#include <fstream>
#include <string>

namespace legsa_v23_core {

// 中文说明：写 LegSA_V23_STD.csv 预测协方差标准差；位置 m、速度 m/s、姿态 deg。
class StdWriter {
 public:
  // 中文说明：打开 STD CSV 并写列头；N4H4B 输出真实预测协方差对角线 sqrt。
  explicit StdWriter(const std::string& path);

  // 中文说明：写 time 和 21 维协方差标准差，不伪造未初始化 covariance。
  void write(double time, const FilterState& state);

 private:
  std::ofstream output_;
};

}  // namespace legsa_v23_core
