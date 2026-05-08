#include "legsa_v23_core/writers/std_writer.hpp"

#include <iomanip>
#include <stdexcept>

namespace legsa_v23_core {

// 中文说明：STD writer 不代表完整 EKF 不确定度闭合，只用于运行链路审计。
StdWriter::StdWriter(const std::string& path) : output_(path) {
  if (!output_) {
    throw std::runtime_error("failed to open STD output: " + path);
  }
  output_ << "time";
  for (std::size_t i = 0; i < kStateSize; ++i) {
    output_ << ",p" << i;
  }
  output_ << "\n";
}

// 中文说明：写协方差对角线占位，后续 N4H4B/C 会补齐真实传播和更新。
void StdWriter::write(double time, const FilterState& state) {
  output_ << std::fixed << std::setprecision(9) << time;
  for (std::size_t i = 0; i < kStateSize; ++i) {
    output_ << "," << matrix21At(state.covariance, i, i);
  }
  output_ << "\n";
}

}  // namespace legsa_v23_core
