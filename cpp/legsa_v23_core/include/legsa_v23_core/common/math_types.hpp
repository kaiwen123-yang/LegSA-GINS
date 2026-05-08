#pragma once

#include "legsa_v23_core/common/constants.hpp"

#include <array>
#include <cstddef>

namespace legsa_v23_core {

using Vector3 = std::array<double, kVector3Size>;
using Vector21 = std::array<double, kStateSize>;
using Matrix3 = std::array<double, kVector3Size * kVector3Size>;
using Matrix21 = std::array<double, kStateSize * kStateSize>;
using Matrix21x18 = std::array<double, kStateSize * kNoiseSize>;
using NoiseMatrix = std::array<double, kNoiseSize * kNoiseSize>;
using Quaternion = std::array<double, 4>;

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

// 中文说明：返回三维单位矩阵；用于 body/nav/ECEF 姿态旋转和 DR/DRi 近似。
inline Matrix3 identityMatrix3() {
  Matrix3 values{};
  values.fill(0.0);
  values[0] = 1.0;
  values[4] = 1.0;
  values[8] = 1.0;
  return values;
}

// 中文说明：返回 21x21 单位矩阵；用于误差状态 Phi 初始化。
inline Matrix21 identityMatrix21() {
  Matrix21 values{};
  values.fill(0.0);
  for (std::size_t i = 0; i < kStateSize; ++i) {
    values[i * kStateSize + i] = 1.0;
  }
  return values;
}

// 中文说明：返回 18x18 对角噪声谱密度矩阵；N4H4B 只用于预测传播。
inline NoiseMatrix diagonalNoiseMatrix(double diagonal_value) {
  NoiseMatrix values{};
  values.fill(0.0);
  for (std::size_t i = 0; i < kNoiseSize; ++i) {
    values[i * kNoiseSize + i] = diagonal_value;
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

// 中文说明：访问三维矩阵元素；用于旋转矩阵和 DR/DRi。
inline double& matrix3At(Matrix3& matrix, std::size_t row, std::size_t col) {
  return matrix[row * kVector3Size + col];
}

// 中文说明：只读访问三维矩阵元素。
inline double matrix3At(const Matrix3& matrix, std::size_t row, std::size_t col) {
  return matrix[row * kVector3Size + col];
}

// 中文说明：访问 21x18 噪声驱动矩阵元素；行是误差状态，列是噪声状态。
inline double& matrix21x18At(Matrix21x18& matrix, std::size_t row, std::size_t col) {
  return matrix[row * kNoiseSize + col];
}

// 中文说明：只读访问 21x18 噪声驱动矩阵元素。
inline double matrix21x18At(const Matrix21x18& matrix, std::size_t row, std::size_t col) {
  return matrix[row * kNoiseSize + col];
}

// 中文说明：访问 18x18 连续噪声矩阵元素。
inline double& noiseAt(NoiseMatrix& matrix, std::size_t row, std::size_t col) {
  return matrix[row * kNoiseSize + col];
}

// 中文说明：只读访问 18x18 连续噪声矩阵元素。
inline double noiseAt(const NoiseMatrix& matrix, std::size_t row, std::size_t col) {
  return matrix[row * kNoiseSize + col];
}

}  // namespace legsa_v23_core
