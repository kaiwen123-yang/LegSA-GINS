#pragma once

#include "legsa_v23_core/common/constants.hpp"

#include <array>
#include <cstddef>

namespace legsa_v23_core {

using Vector3 = std::array<double, kVector3Size>;
using Vector21 = std::array<double, kStateSize>;
using Matrix21 = std::array<double, kStateSize * kStateSize>;

// 中文说明：返回三维零向量；单位由调用场景决定，常见为 BLH(rad,rad,m) 或 NED(m/s)。
inline Vector3 zeroVector3() { return {0.0, 0.0, 0.0}; }

// 中文说明：返回 21 维零误差状态；N4H4A 仅作为 EKF 框架占位。
inline Vector21 zeroVector21() {
  Vector21 values{};
  values.fill(0.0);
  return values;
}

// 中文说明：返回 21x21 对角矩阵；协方差单位由状态分量决定，N4H4A 不做完整数值传播。
inline Matrix21 diagonalMatrix21(double diagonal_value) {
  Matrix21 values{};
  values.fill(0.0);
  for (std::size_t i = 0; i < kStateSize; ++i) {
    values[i * kStateSize + i] = diagonal_value;
  }
  return values;
}

// 中文说明：访问 21x21 矩阵元素；行列均为误差状态索引。
inline double& matrix21At(Matrix21& matrix, std::size_t row, std::size_t col) {
  return matrix[row * kStateSize + col];
}

// 中文说明：只读访问 21x21 矩阵元素；用于审计和 writer，不做外部依赖。
inline double matrix21At(const Matrix21& matrix, std::size_t row, std::size_t col) {
  return matrix[row * kStateSize + col];
}

}  // namespace legsa_v23_core
