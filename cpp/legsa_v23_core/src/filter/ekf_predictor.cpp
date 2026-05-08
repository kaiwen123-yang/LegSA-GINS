#include "legsa_v23_core/filter/ekf_predictor.hpp"

#include <cmath>
#include <stdexcept>

namespace legsa_v23_core {
namespace {

// 中文说明：矩阵乘法使用固定 21 维数组，避免外部线性代数依赖。
Matrix21 multiply21(const Matrix21& lhs, const Matrix21& rhs) {
  Matrix21 result{};
  result.fill(0.0);
  for (std::size_t i = 0; i < kStateSize; ++i) {
    for (std::size_t j = 0; j < kStateSize; ++j) {
      double sum = 0.0;
      for (std::size_t k = 0; k < kStateSize; ++k) {
        sum += matrix21At(lhs, i, k) * matrix21At(rhs, k, j);
      }
      matrix21At(result, i, j) = sum;
    }
  }
  return result;
}

// 中文说明：A*B*A^T，用于协方差预测。
Matrix21 multiplyABAT(const Matrix21& a, const Matrix21& b) {
  Matrix21 result{};
  result.fill(0.0);
  for (std::size_t i = 0; i < kStateSize; ++i) {
    for (std::size_t j = 0; j < kStateSize; ++j) {
      double sum = 0.0;
      for (std::size_t k = 0; k < kStateSize; ++k) {
        for (std::size_t l = 0; l < kStateSize; ++l) {
          sum += matrix21At(a, i, k) * matrix21At(b, k, l) * matrix21At(a, j, l);
        }
      }
      matrix21At(result, i, j) = sum;
    }
  }
  return result;
}

}  // namespace

// 中文说明：Cov = Phi*Cov*Phi^T + Qd，dx = Phi*dx；本函数不做 GNSS 量测更新和 state feedback。
void EKFPredict(FilterState& state, const Matrix21& Phi, const Matrix21& Qd) {
  const Matrix21 predicted_covariance = multiplyABAT(Phi, state.covariance);
  Matrix21 covariance{};
  for (std::size_t i = 0; i < kStateSize; ++i) {
    for (std::size_t j = 0; j < kStateSize; ++j) {
      matrix21At(covariance, i, j) = matrix21At(predicted_covariance, i, j) + matrix21At(Qd, i, j);
    }
  }

  const Matrix21 phi_copy = Phi;
  Vector21 predicted_dx{};
  predicted_dx.fill(0.0);
  for (std::size_t i = 0; i < kStateSize; ++i) {
    for (std::size_t j = 0; j < kStateSize; ++j) {
      predicted_dx[i] += matrix21At(phi_copy, i, j) * state.dx[j];
    }
  }
  state.dx = predicted_dx;

  for (std::size_t i = 0; i < kStateSize; ++i) {
    for (std::size_t j = i + 1; j < kStateSize; ++j) {
      const double symmetric = 0.5 * (matrix21At(covariance, i, j) + matrix21At(covariance, j, i));
      matrix21At(covariance, i, j) = symmetric;
      matrix21At(covariance, j, i) = symmetric;
    }
  }
  for (std::size_t i = 0; i < kStateSize; ++i) {
    const double diag = matrix21At(covariance, i, i);
    if (!std::isfinite(diag) || diag < -1.0e-12) {
      throw std::runtime_error("EKFPredict covariance diagonal is invalid");
    }
    if (diag < 0.0) {
      matrix21At(covariance, i, i) = 0.0;
    }
  }
  state.covariance = covariance;
}

}  // namespace legsa_v23_core
