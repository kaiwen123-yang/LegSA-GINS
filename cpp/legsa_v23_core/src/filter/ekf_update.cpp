#include "legsa_v23_core/filter/ekf_update.hpp"

#include "legsa_v23_core/common/constants.hpp"

#include <algorithm>
#include <cmath>
#include <stdexcept>
#include <vector>

namespace legsa_v23_core {
namespace {

// 中文说明：动态小矩阵按行优先存储；N4H4C 只用于 1x/3x GNSS 量测更新。
using DynamicMatrix = std::vector<double>;

double& dynAt(DynamicMatrix& matrix, std::size_t cols, std::size_t row, std::size_t col) {
  return matrix[row * cols + col];
}

double dynAt(const DynamicMatrix& matrix, std::size_t cols, std::size_t row, std::size_t col) {
  return matrix[row * cols + col];
}

// 中文说明：高斯-约旦求逆只服务 1~3 维量测 S 矩阵，失败时明确报错而不是静默伪造更新。
DynamicMatrix inverseSmallMatrix(const DynamicMatrix& matrix, std::size_t n) {
  DynamicMatrix augmented(n * 2 * n, 0.0);
  const std::size_t cols = 2 * n;
  for (std::size_t row = 0; row < n; ++row) {
    for (std::size_t col = 0; col < n; ++col) {
      dynAt(augmented, cols, row, col) = dynAt(matrix, n, row, col);
    }
    dynAt(augmented, cols, row, n + row) = 1.0;
  }

  for (std::size_t pivot = 0; pivot < n; ++pivot) {
    std::size_t best = pivot;
    double best_abs = std::abs(dynAt(augmented, cols, pivot, pivot));
    for (std::size_t row = pivot + 1; row < n; ++row) {
      const double candidate = std::abs(dynAt(augmented, cols, row, pivot));
      if (candidate > best_abs) {
        best = row;
        best_abs = candidate;
      }
    }
    if (best_abs < 1.0e-18) {
      throw std::runtime_error("EKFUpdate innovation covariance is singular");
    }
    if (best != pivot) {
      for (std::size_t col = 0; col < cols; ++col) {
        std::swap(dynAt(augmented, cols, pivot, col), dynAt(augmented, cols, best, col));
      }
    }
    const double pivot_value = dynAt(augmented, cols, pivot, pivot);
    for (std::size_t col = 0; col < cols; ++col) {
      dynAt(augmented, cols, pivot, col) /= pivot_value;
    }
    for (std::size_t row = 0; row < n; ++row) {
      if (row == pivot) {
        continue;
      }
      const double factor = dynAt(augmented, cols, row, pivot);
      for (std::size_t col = 0; col < cols; ++col) {
        dynAt(augmented, cols, row, col) -= factor * dynAt(augmented, cols, pivot, col);
      }
    }
  }

  DynamicMatrix inverse(n * n, 0.0);
  for (std::size_t row = 0; row < n; ++row) {
    for (std::size_t col = 0; col < n; ++col) {
      dynAt(inverse, n, row, col) = dynAt(augmented, cols, row, n + col);
    }
  }
  return inverse;
}

void checkStateFinite(const FilterState& state) {
  for (std::size_t i = 0; i < kStateSize; ++i) {
    if (!std::isfinite(state.dx[i])) {
      throw std::runtime_error("EKFUpdate dx is not finite");
    }
    for (std::size_t j = 0; j < kStateSize; ++j) {
      if (!std::isfinite(matrix21At(state.covariance, i, j))) {
        throw std::runtime_error("EKFUpdate covariance is not finite");
      }
    }
    if (matrix21At(state.covariance, i, i) < -kDefaultCovarianceFloor) {
      throw std::runtime_error("EKFUpdate covariance diagonal is negative");
    }
  }
}

}  // namespace

// 中文说明：Joseph form 量测更新：S=HPH^T+R，K=PH^T inv(S)，Cov=(I-KH)P(I-KH)^T+KRK^T。
// 中文说明：dx 是 21 维误差状态，Cov 是误差协方差；这里不直接改 BLH/NED/姿态名义状态。
void EKFUpdate(FilterState& state, const MeasurementBlock& meas) {
  const std::size_t m = meas.rows;
  if (m == 0 || meas.residual.size() != m || meas.H.size() != m * kStateSize || meas.R.size() != m * m) {
    throw std::runtime_error("EKFUpdate received invalid measurement block");
  }

  DynamicMatrix HP(m * kStateSize, 0.0);
  for (std::size_t row = 0; row < m; ++row) {
    for (std::size_t col = 0; col < kStateSize; ++col) {
      double value = 0.0;
      for (std::size_t k = 0; k < kStateSize; ++k) {
        value += measurementHAt(meas, row, k) * matrix21At(state.covariance, k, col);
      }
      dynAt(HP, kStateSize, row, col) = value;
    }
  }

  DynamicMatrix S(m * m, 0.0);
  for (std::size_t row = 0; row < m; ++row) {
    for (std::size_t col = 0; col < m; ++col) {
      double value = measurementRAt(meas, row, col);
      for (std::size_t k = 0; k < kStateSize; ++k) {
        value += dynAt(HP, kStateSize, row, k) * measurementHAt(meas, col, k);
      }
      dynAt(S, m, row, col) = value;
    }
  }
  const DynamicMatrix S_inv = inverseSmallMatrix(S, m);

  DynamicMatrix PHt(kStateSize * m, 0.0);
  // 中文说明：force symmetry，避免 Joseph form 数值舍入导致 P 与 P^T 轻微不一致。
  for (std::size_t row = 0; row < kStateSize; ++row) {
    for (std::size_t col = 0; col < m; ++col) {
      double value = 0.0;
      for (std::size_t k = 0; k < kStateSize; ++k) {
        value += matrix21At(state.covariance, row, k) * measurementHAt(meas, col, k);
      }
      dynAt(PHt, m, row, col) = value;
    }
  }

  DynamicMatrix K(kStateSize * m, 0.0);
  for (std::size_t row = 0; row < kStateSize; ++row) {
    for (std::size_t col = 0; col < m; ++col) {
      for (std::size_t k = 0; k < m; ++k) {
        dynAt(K, m, row, col) += dynAt(PHt, m, row, k) * dynAt(S_inv, m, k, col);
      }
    }
  }

  std::vector<double> innovation(m, 0.0);
  for (std::size_t row = 0; row < m; ++row) {
    double predicted = 0.0;
    for (std::size_t col = 0; col < kStateSize; ++col) {
      predicted += measurementHAt(meas, row, col) * state.dx[col];
    }
    innovation[row] = meas.residual[row] - predicted;
  }

  for (std::size_t row = 0; row < kStateSize; ++row) {
    for (std::size_t col = 0; col < m; ++col) {
      state.dx[row] += dynAt(K, m, row, col) * innovation[col];
    }
  }

  Matrix21 I_minus_KH = identityMatrix21();
  for (std::size_t row = 0; row < kStateSize; ++row) {
    for (std::size_t col = 0; col < kStateSize; ++col) {
      double kh = 0.0;
      for (std::size_t k = 0; k < m; ++k) {
        kh += dynAt(K, m, row, k) * measurementHAt(meas, k, col);
      }
      matrix21At(I_minus_KH, row, col) -= kh;
    }
  }

  Matrix21 temp{};
  temp.fill(0.0);
  for (std::size_t row = 0; row < kStateSize; ++row) {
    for (std::size_t col = 0; col < kStateSize; ++col) {
      for (std::size_t k = 0; k < kStateSize; ++k) {
        matrix21At(temp, row, col) += matrix21At(I_minus_KH, row, k) * matrix21At(state.covariance, k, col);
      }
    }
  }

  Matrix21 joseph_cov{};
  joseph_cov.fill(0.0);
  for (std::size_t row = 0; row < kStateSize; ++row) {
    for (std::size_t col = 0; col < kStateSize; ++col) {
      for (std::size_t k = 0; k < kStateSize; ++k) {
        matrix21At(joseph_cov, row, col) += matrix21At(temp, row, k) * matrix21At(I_minus_KH, col, k);
      }
      for (std::size_t a = 0; a < m; ++a) {
        for (std::size_t b = 0; b < m; ++b) {
          matrix21At(joseph_cov, row, col) += dynAt(K, m, row, a) * measurementRAt(meas, a, b) *
                                               dynAt(K, m, col, b);
        }
      }
    }
  }

  for (std::size_t row = 0; row < kStateSize; ++row) {
    for (std::size_t col = row; col < kStateSize; ++col) {
      const double value = 0.5 * (matrix21At(joseph_cov, row, col) + matrix21At(joseph_cov, col, row));
      matrix21At(state.covariance, row, col) = value;
      matrix21At(state.covariance, col, row) = value;
    }
  }
  checkStateFinite(state);
}

}  // namespace legsa_v23_core
