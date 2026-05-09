// LegSA-GINS source-backed port file.
// Source reference: KF-GINS-graduation-design / final_v23 reference.
// Source commit: 5a4471efd4fcfcdc31e258a677af354c652ff16f.
// Port role: mature GNSS/INS backbone implementation, not proposed novelty.
// Boundary: no final_v23 output substitution, no trace solver input.
// 中文说明：该文件为受控移植的组合导航骨架代码，后续创新因子将在该骨架通过 parity 后再接入。

#pragma once

#include <array>
#include <cstddef>
#include <string>
#include <vector>

namespace legsa_v23_port_core {

using Vec3 = std::array<double, 3>;
using Matrix3 = std::array<std::array<double, 3>, 3>;

struct Quaternion {
  double w = 1.0;
  double x = 0.0;
  double y = 0.0;
  double z = 0.0;
};

struct Matrix {
  std::size_t rows = 0;
  std::size_t cols = 0;
  std::vector<double> data;

  Matrix() = default;
  Matrix(std::size_t row_count, std::size_t col_count, double value = 0.0);
  double& operator()(std::size_t row, std::size_t col);
  double operator()(std::size_t row, std::size_t col) const;
};

// 中文说明：误差状态维度沿用 KF-GINS 的 21 维合同。
constexpr std::size_t kErrorStateSize = 21;
constexpr std::size_t RANK = 21;
constexpr std::size_t NOISERANK = 18;

// 中文说明：状态索引与 KF-GINS reference 保持一致。
constexpr std::size_t P_ID = 0;
constexpr std::size_t V_ID = 3;
constexpr std::size_t PHI_ID = 6;
constexpr std::size_t BG_ID = 9;
constexpr std::size_t BA_ID = 12;
constexpr std::size_t SG_ID = 15;
constexpr std::size_t SA_ID = 18;

// 中文说明：噪声索引用于构造 Qc/G/Qd。
constexpr std::size_t ARW_ID = 0;
constexpr std::size_t VRW_ID = 3;
constexpr std::size_t BGSTD_ID = 6;
constexpr std::size_t BASTD_ID = 9;
constexpr std::size_t SGSTD_ID = 12;
constexpr std::size_t SASTD_ID = 15;

constexpr double kPi = 3.14159265358979323846;
constexpr double D2R = kPi / 180.0;
constexpr double R2D = 180.0 / kPi;
constexpr double TIME_ALIGN_ERR = 0.001;

struct Attitude {
  Vec3 euler = Vec3{0.0, 0.0, 0.0};
  Matrix3 cbn{};
  Quaternion qbn{};
};

struct PVA {
  Vec3 pos = Vec3{0.0, 0.0, 0.0};
  Vec3 vel = Vec3{0.0, 0.0, 0.0};
  Attitude att;
};

struct ImuError {
  Vec3 gyrbias = Vec3{0.0, 0.0, 0.0};
  Vec3 accbias = Vec3{0.0, 0.0, 0.0};
  Vec3 gyrscale = Vec3{0.0, 0.0, 0.0};
  Vec3 accscale = Vec3{0.0, 0.0, 0.0};
};

struct ImuNoise {
  Vec3 gyr_arw = Vec3{1.0e-4, 1.0e-4, 1.0e-4};
  Vec3 acc_vrw = Vec3{1.0e-3, 1.0e-3, 1.0e-3};
  Vec3 gyrbias_std = Vec3{1.0e-5, 1.0e-5, 1.0e-5};
  Vec3 accbias_std = Vec3{1.0e-4, 1.0e-4, 1.0e-4};
  Vec3 gyrscale_std = Vec3{1.0e-6, 1.0e-6, 1.0e-6};
  Vec3 accscale_std = Vec3{1.0e-6, 1.0e-6, 1.0e-6};
  double corr_time = 3600.0;
};

// 中文说明：轻量线性代数工具只服务 LegSA-owned port target，不编译 reference。
Vec3 makeVec3(double x, double y, double z);
double norm(const Vec3& value);
Vec3 add(const Vec3& lhs, const Vec3& rhs);
Vec3 subtract(const Vec3& lhs, const Vec3& rhs);
Vec3 scale(const Vec3& value, double factor);
double dot(const Vec3& lhs, const Vec3& rhs);
Vec3 cross(const Vec3& lhs, const Vec3& rhs);
Vec3 cwiseDivide(const Vec3& lhs, const Vec3& rhs);
Vec3 cwiseProduct(const Vec3& lhs, const Vec3& rhs);
Matrix3 zeroMatrix3();
Matrix3 identityMatrix3();
Matrix3 add(const Matrix3& lhs, const Matrix3& rhs);
Matrix3 subtract(const Matrix3& lhs, const Matrix3& rhs);
Matrix3 scale(const Matrix3& value, double factor);
Matrix3 multiply(const Matrix3& lhs, const Matrix3& rhs);
Vec3 multiply(const Matrix3& lhs, const Vec3& rhs);
Matrix3 transpose(const Matrix3& value);
Matrix3 skew(const Vec3& value);
std::vector<double> makeCovarianceDiagonal(double value);
Matrix identityMatrix(std::size_t size);
Matrix transpose(const Matrix& value);
Matrix multiply(const Matrix& lhs, const Matrix& rhs);
std::vector<double> multiply(const Matrix& lhs, const std::vector<double>& rhs);
Matrix add(const Matrix& lhs, const Matrix& rhs);
Matrix subtract(const Matrix& lhs, const Matrix& rhs);
Matrix scale(const Matrix& value, double factor);
Matrix inverse(const Matrix& value);
void setBlock(Matrix& target, std::size_t row, std::size_t col, const Matrix3& block);
void setBlockIdentity(Matrix& target, std::size_t row, std::size_t col);
Matrix diagonalMatrix(const Vec3& diagonal);
std::vector<double> blockVec3(const std::vector<double>& value, std::size_t offset);
void addToBlock(std::vector<double>& value, std::size_t offset, const Vec3& delta);
void zeroVector(std::vector<double>& value);

}  // namespace legsa_v23_port_core
