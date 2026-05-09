// LegSA-GINS source-backed port file.
// Source reference: KF-GINS-graduation-design / final_v23 reference.
// Source commit: 5a4471efd4fcfcdc31e258a677af354c652ff16f.
// Port role: mature GNSS/INS backbone implementation, not proposed novelty.
// Boundary: no final_v23 output substitution, no trace solver input.
// 中文说明：该文件为受控移植的组合导航骨架代码，后续创新因子将在该骨架通过 parity 后再接入。

#include "legsa_v23_port_core/types.hpp"

#include <algorithm>
#include <cmath>
#include <stdexcept>

namespace legsa_v23_port_core {

Matrix::Matrix(std::size_t row_count, std::size_t col_count, double value)
    : rows(row_count), cols(col_count), data(row_count * col_count, value) {}

double& Matrix::operator()(std::size_t row, std::size_t col) {
  return data.at(row * cols + col);
}

double Matrix::operator()(std::size_t row, std::size_t col) const {
  return data.at(row * cols + col);
}

// 中文说明：构造三维向量，避免在 port-core 引入 Eigen 依赖。
Vec3 makeVec3(double x, double y, double z) {
  return Vec3{x, y, z};
}

// 中文说明：欧氏范数用于矩阵审计和 synthetic smoke，不是性能指标。
double norm(const Vec3& value) {
  return std::sqrt(dot(value, value));
}

Vec3 add(const Vec3& lhs, const Vec3& rhs) {
  return makeVec3(lhs[0] + rhs[0], lhs[1] + rhs[1], lhs[2] + rhs[2]);
}

Vec3 subtract(const Vec3& lhs, const Vec3& rhs) {
  return makeVec3(lhs[0] - rhs[0], lhs[1] - rhs[1], lhs[2] - rhs[2]);
}

Vec3 scale(const Vec3& value, double factor) {
  return makeVec3(value[0] * factor, value[1] * factor, value[2] * factor);
}

double dot(const Vec3& lhs, const Vec3& rhs) {
  return lhs[0] * rhs[0] + lhs[1] * rhs[1] + lhs[2] * rhs[2];
}

Vec3 cross(const Vec3& lhs, const Vec3& rhs) {
  return makeVec3(lhs[1] * rhs[2] - lhs[2] * rhs[1],
                  lhs[2] * rhs[0] - lhs[0] * rhs[2],
                  lhs[0] * rhs[1] - lhs[1] * rhs[0]);
}

Vec3 cwiseDivide(const Vec3& lhs, const Vec3& rhs) {
  return makeVec3(lhs[0] / rhs[0], lhs[1] / rhs[1], lhs[2] / rhs[2]);
}

Vec3 cwiseProduct(const Vec3& lhs, const Vec3& rhs) {
  return makeVec3(lhs[0] * rhs[0], lhs[1] * rhs[1], lhs[2] * rhs[2]);
}

Matrix3 zeroMatrix3() {
  return Matrix3{{{{0.0, 0.0, 0.0}}, {{0.0, 0.0, 0.0}}, {{0.0, 0.0, 0.0}}}};
}

Matrix3 identityMatrix3() {
  Matrix3 value = zeroMatrix3();
  value[0][0] = 1.0;
  value[1][1] = 1.0;
  value[2][2] = 1.0;
  return value;
}

Matrix3 add(const Matrix3& lhs, const Matrix3& rhs) {
  Matrix3 out = zeroMatrix3();
  for (std::size_t r = 0; r < 3; ++r) {
    for (std::size_t c = 0; c < 3; ++c) {
      out[r][c] = lhs[r][c] + rhs[r][c];
    }
  }
  return out;
}

Matrix3 subtract(const Matrix3& lhs, const Matrix3& rhs) {
  Matrix3 out = zeroMatrix3();
  for (std::size_t r = 0; r < 3; ++r) {
    for (std::size_t c = 0; c < 3; ++c) {
      out[r][c] = lhs[r][c] - rhs[r][c];
    }
  }
  return out;
}

Matrix3 scale(const Matrix3& value, double factor) {
  Matrix3 out = zeroMatrix3();
  for (std::size_t r = 0; r < 3; ++r) {
    for (std::size_t c = 0; c < 3; ++c) {
      out[r][c] = value[r][c] * factor;
    }
  }
  return out;
}

Matrix3 multiply(const Matrix3& lhs, const Matrix3& rhs) {
  Matrix3 out = zeroMatrix3();
  for (std::size_t r = 0; r < 3; ++r) {
    for (std::size_t c = 0; c < 3; ++c) {
      for (std::size_t k = 0; k < 3; ++k) {
        out[r][c] += lhs[r][k] * rhs[k][c];
      }
    }
  }
  return out;
}

Vec3 multiply(const Matrix3& lhs, const Vec3& rhs) {
  return makeVec3(lhs[0][0] * rhs[0] + lhs[0][1] * rhs[1] + lhs[0][2] * rhs[2],
                  lhs[1][0] * rhs[0] + lhs[1][1] * rhs[1] + lhs[1][2] * rhs[2],
                  lhs[2][0] * rhs[0] + lhs[2][1] * rhs[1] + lhs[2][2] * rhs[2]);
}

Matrix3 transpose(const Matrix3& value) {
  Matrix3 out = zeroMatrix3();
  for (std::size_t r = 0; r < 3; ++r) {
    for (std::size_t c = 0; c < 3; ++c) {
      out[r][c] = value[c][r];
    }
  }
  return out;
}

Matrix3 skew(const Vec3& value) {
  return Matrix3{{{{0.0, -value[2], value[1]}},
                  {{value[2], 0.0, -value[0]}},
                  {{-value[1], value[0], 0.0}}}};
}

std::vector<double> makeCovarianceDiagonal(double value) {
  std::vector<double> covariance(RANK * RANK, 0.0);
  for (std::size_t i = 0; i < RANK; ++i) {
    covariance[i * RANK + i] = value;
  }
  return covariance;
}

Matrix identityMatrix(std::size_t size) {
  Matrix out(size, size, 0.0);
  for (std::size_t i = 0; i < size; ++i) {
    out(i, i) = 1.0;
  }
  return out;
}

Matrix transpose(const Matrix& value) {
  Matrix out(value.cols, value.rows, 0.0);
  for (std::size_t r = 0; r < value.rows; ++r) {
    for (std::size_t c = 0; c < value.cols; ++c) {
      out(c, r) = value(r, c);
    }
  }
  return out;
}

Matrix multiply(const Matrix& lhs, const Matrix& rhs) {
  if (lhs.cols != rhs.rows) {
    throw std::runtime_error("matrix multiply dimension mismatch");
  }
  Matrix out(lhs.rows, rhs.cols, 0.0);
  for (std::size_t r = 0; r < lhs.rows; ++r) {
    for (std::size_t c = 0; c < rhs.cols; ++c) {
      for (std::size_t k = 0; k < lhs.cols; ++k) {
        out(r, c) += lhs(r, k) * rhs(k, c);
      }
    }
  }
  return out;
}

std::vector<double> multiply(const Matrix& lhs, const std::vector<double>& rhs) {
  if (lhs.cols != rhs.size()) {
    throw std::runtime_error("matrix-vector multiply dimension mismatch");
  }
  std::vector<double> out(lhs.rows, 0.0);
  for (std::size_t r = 0; r < lhs.rows; ++r) {
    for (std::size_t c = 0; c < lhs.cols; ++c) {
      out[r] += lhs(r, c) * rhs[c];
    }
  }
  return out;
}

Matrix add(const Matrix& lhs, const Matrix& rhs) {
  if (lhs.rows != rhs.rows || lhs.cols != rhs.cols) {
    throw std::runtime_error("matrix add dimension mismatch");
  }
  Matrix out(lhs.rows, lhs.cols, 0.0);
  for (std::size_t i = 0; i < lhs.data.size(); ++i) {
    out.data[i] = lhs.data[i] + rhs.data[i];
  }
  return out;
}

Matrix subtract(const Matrix& lhs, const Matrix& rhs) {
  if (lhs.rows != rhs.rows || lhs.cols != rhs.cols) {
    throw std::runtime_error("matrix subtract dimension mismatch");
  }
  Matrix out(lhs.rows, lhs.cols, 0.0);
  for (std::size_t i = 0; i < lhs.data.size(); ++i) {
    out.data[i] = lhs.data[i] - rhs.data[i];
  }
  return out;
}

Matrix scale(const Matrix& value, double factor) {
  Matrix out(value.rows, value.cols, 0.0);
  for (std::size_t i = 0; i < value.data.size(); ++i) {
    out.data[i] = value.data[i] * factor;
  }
  return out;
}

Matrix inverse(const Matrix& value) {
  if (value.rows != value.cols) {
    throw std::runtime_error("inverse requires square matrix");
  }
  const std::size_t n = value.rows;
  Matrix work(n, 2 * n, 0.0);
  for (std::size_t r = 0; r < n; ++r) {
    for (std::size_t c = 0; c < n; ++c) {
      work(r, c) = value(r, c);
    }
    work(r, n + r) = 1.0;
  }
  for (std::size_t col = 0; col < n; ++col) {
    std::size_t pivot = col;
    double best = std::fabs(work(col, col));
    for (std::size_t r = col + 1; r < n; ++r) {
      const double candidate = std::fabs(work(r, col));
      if (candidate > best) {
        best = candidate;
        pivot = r;
      }
    }
    if (best < 1.0e-15) {
      throw std::runtime_error("singular matrix in inverse");
    }
    if (pivot != col) {
      for (std::size_t c = 0; c < 2 * n; ++c) {
        std::swap(work(col, c), work(pivot, c));
      }
    }
    const double diag = work(col, col);
    for (std::size_t c = 0; c < 2 * n; ++c) {
      work(col, c) /= diag;
    }
    for (std::size_t r = 0; r < n; ++r) {
      if (r == col) {
        continue;
      }
      const double factor = work(r, col);
      for (std::size_t c = 0; c < 2 * n; ++c) {
        work(r, c) -= factor * work(col, c);
      }
    }
  }
  Matrix out(n, n, 0.0);
  for (std::size_t r = 0; r < n; ++r) {
    for (std::size_t c = 0; c < n; ++c) {
      out(r, c) = work(r, n + c);
    }
  }
  return out;
}

void setBlock(Matrix& target, std::size_t row, std::size_t col, const Matrix3& block) {
  for (std::size_t r = 0; r < 3; ++r) {
    for (std::size_t c = 0; c < 3; ++c) {
      target(row + r, col + c) = block[r][c];
    }
  }
}

void setBlockIdentity(Matrix& target, std::size_t row, std::size_t col) {
  setBlock(target, row, col, identityMatrix3());
}

Matrix diagonalMatrix(const Vec3& diagonal) {
  Matrix out(3, 3, 0.0);
  out(0, 0) = diagonal[0];
  out(1, 1) = diagonal[1];
  out(2, 2) = diagonal[2];
  return out;
}

std::vector<double> blockVec3(const std::vector<double>& value, std::size_t offset) {
  return std::vector<double>{value.at(offset), value.at(offset + 1), value.at(offset + 2)};
}

void addToBlock(std::vector<double>& value, std::size_t offset, const Vec3& delta) {
  value.at(offset) += delta[0];
  value.at(offset + 1) += delta[1];
  value.at(offset + 2) += delta[2];
}

void zeroVector(std::vector<double>& value) {
  std::fill(value.begin(), value.end(), 0.0);
}

}  // namespace legsa_v23_port_core
