#include "legsa_v23_core/writers/std_writer.hpp"

#include "legsa_v23_core/common/constants.hpp"

#include <algorithm>
#include <cmath>
#include <iomanip>
#include <stdexcept>

namespace legsa_v23_core {

// 中文说明：STD writer 输出预测协方差 sqrt；N4H4B 不把它写成性能或 parity 证据。
StdWriter::StdWriter(const std::string& path) : output_(path) {
  if (!output_) {
    throw std::runtime_error("failed to open STD output: " + path);
  }
  output_ << "time";
  for (std::size_t i = 0; i < kStateSize; ++i) {
    output_ << ",std" << i;
  }
  output_ << "\n";
}

// 中文说明：写协方差对角线平方根；姿态标准差转 deg，bias/scale 保持 KF-GINS-style 内部单位。
void StdWriter::write(double time, const FilterState& state) {
  output_ << std::fixed << std::setprecision(9) << time;
  for (std::size_t i = 0; i < kStateSize; ++i) {
    const double variance = matrix21At(state.covariance, i, i);
    if (!std::isfinite(variance) || variance < -1.0e-15) {
      throw std::runtime_error("STD writer found uninitialized or invalid covariance");
    }
    double std_value = std::sqrt(std::max(0.0, variance));
    if (i >= PHI_ID && i < PHI_ID + kVector3Size) {
      std_value *= kRadToDeg;
    }
    output_ << "," << std_value;
  }
  output_ << "\n";
}

}  // namespace legsa_v23_core
