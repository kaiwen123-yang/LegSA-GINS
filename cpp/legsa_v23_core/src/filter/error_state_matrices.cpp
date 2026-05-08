#include "legsa_v23_core/filter/error_state_matrices.hpp"

#include "legsa_v23_core/common/earth.hpp"
#include "legsa_v23_core/common/rotation.hpp"

#include <algorithm>
#include <cmath>
#include <string>
#include <stdexcept>

namespace legsa_v23_core {
namespace {

// 中文说明：向 21x21 矩阵写 3x3 大块，行列索引对应误差状态起点。
void setBlock(Matrix21& matrix, std::size_t row, std::size_t col, const Matrix3& block, double scale = 1.0) {
  for (std::size_t r = 0; r < kVector3Size; ++r) {
    for (std::size_t c = 0; c < kVector3Size; ++c) {
      matrix21At(matrix, row + r, col + c) = matrix3At(block, r, c) * scale;
    }
  }
}

// 中文说明：向 21x18 G 矩阵写 3x3 大块，状态行和噪声列均按枚举起点。
void setNoiseBlock(Matrix21x18& matrix, std::size_t row, std::size_t col, const Matrix3& block,
                   double scale = 1.0) {
  for (std::size_t r = 0; r < kVector3Size; ++r) {
    for (std::size_t c = 0; c < kVector3Size; ++c) {
      matrix21x18At(matrix, row + r, col + c) = matrix3At(block, r, c) * scale;
    }
  }
}

// 中文说明：矩阵缩放加法，用于 Phi = I + F*dt。
Matrix21 phiFromF(const Matrix21& f, double dt) {
  Matrix21 phi = identityMatrix21();
  for (std::size_t i = 0; i < kStateSize * kStateSize; ++i) {
    phi[i] += f[i] * dt;
  }
  return phi;
}

// 中文说明：计算 G*Qc*G^T，保持 21-state 维度。
Matrix21 gQcGt(const Matrix21x18& g, const NoiseMatrix& qc) {
  Matrix21 result{};
  result.fill(0.0);
  for (std::size_t i = 0; i < kStateSize; ++i) {
    for (std::size_t j = 0; j < kStateSize; ++j) {
      double sum = 0.0;
      for (std::size_t k = 0; k < kNoiseSize; ++k) {
        for (std::size_t l = 0; l < kNoiseSize; ++l) {
          sum += matrix21x18At(g, i, k) * noiseAt(qc, k, l) * matrix21x18At(g, j, l);
        }
      }
      matrix21At(result, i, j) = sum;
    }
  }
  return result;
}

// 中文说明：计算 A*B*A^T，用于 Qd 二阶对称化近似。
Matrix21 aBaT(const Matrix21& a, const Matrix21& b) {
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

// 中文说明：检查矩阵有限值，防止传播阶段悄悄写出 NaN。
void checkFinite(const Matrix21& matrix, const char* name) {
  for (double value : matrix) {
    if (!std::isfinite(value)) {
      throw std::runtime_error(std::string(name) + " contains non-finite value");
    }
  }
}

}  // namespace

// 中文说明：构造 N4H4B 预测传播矩阵；这里不做 GNSS measurement update、EKFUpdate 或 stateFeedback。
ErrorStateMatrices buildErrorStateMatrices(const PVAState& pvapre, const IMUData& imucur,
                                           const GINSOptions& options, const NoiseMatrix& Qc) {
  (void)options;
  const double dt = std::max(imucur.dt, 1.0e-6);
  const Matrix3 identity = identityMatrix3();
  const Matrix3 cbn = Rotation::euler2matrix(pvapre.euler_rpy_rad);
  const Matrix3 skew_vel = Rotation::skewSymmetric(pvapre.vel_ned_mps);
  const Matrix3 skew_force = Rotation::skewSymmetric(imucur.dvel);
  const Vector3 rmn = Earth::meridianPrimeVerticalRadius(pvapre.pos_blh_rad_m[0]);
  const Vector3 omega_ie_n = Earth::iewn(pvapre.pos_blh_rad_m[0]);
  const Vector3 omega_en_n = Earth::enwn(rmn, pvapre.pos_blh_rad_m, pvapre.vel_ned_mps);
  const Matrix3 skew_omega = Rotation::skewSymmetric({omega_ie_n[0] + omega_en_n[0],
                                                       omega_ie_n[1] + omega_en_n[1],
                                                       omega_ie_n[2] + omega_en_n[2]});

  ErrorStateMatrices matrices;
  matrices.F.fill(0.0);
  matrices.G.fill(0.0);

  // 中文说明：P/P 和 P/V 大块，位置误差由局部曲率和速度误差驱动。
  setBlock(matrices.F, P_ID, P_ID, identity, -1.0e-8);
  setBlock(matrices.F, P_ID, V_ID, identity);

  // 中文说明：V/P、V/V、V/Phi、V/BA、V/SA 大块，表示重力/转率/姿态和加计误差对速度误差的影响。
  setBlock(matrices.F, V_ID, P_ID, skew_vel, 1.0e-7);
  setBlock(matrices.F, V_ID, V_ID, skew_omega, -2.0);
  setBlock(matrices.F, V_ID, PHI_ID, skew_force, -1.0 / dt);
  setBlock(matrices.F, V_ID, BA_ID, cbn, -1.0);
  setBlock(matrices.F, V_ID, SA_ID, cbn, -1.0);

  // 中文说明：Phi/P、Phi/V、Phi/Phi、Phi/BG、Phi/SG 大块，描述姿态误差由导航转率和陀螺误差驱动。
  setBlock(matrices.F, PHI_ID, P_ID, identity, 1.0e-9);
  setBlock(matrices.F, PHI_ID, V_ID, identity, 1.0e-6);
  setBlock(matrices.F, PHI_ID, PHI_ID, skew_omega, -1.0);
  setBlock(matrices.F, PHI_ID, BG_ID, cbn, -1.0);
  setBlock(matrices.F, PHI_ID, SG_ID, cbn, -1.0);

  // 中文说明：BG/BG、BA/BA、SG/SG、SA/SA 大块，N4H4B 使用弱随机游走/一阶保持近似。
  setBlock(matrices.F, BG_ID, BG_ID, identity, -1.0e-5);
  setBlock(matrices.F, BA_ID, BA_ID, identity, -1.0e-5);
  setBlock(matrices.F, SG_ID, SG_ID, identity, -1.0e-5);
  setBlock(matrices.F, SA_ID, SA_ID, identity, -1.0e-5);

  // 中文说明：G 的 V/VRW 和 Phi/ARW 大块，对应加计和陀螺白噪声。
  setNoiseBlock(matrices.G, V_ID, VRW_ID, cbn);
  setNoiseBlock(matrices.G, PHI_ID, ARW_ID, cbn);

  // 中文说明：G 的 BG/BGSTD、BA/BASTD、SG/SGSTD、SA/SASTD 大块，对应 IMU bias/scale 随机游走。
  setNoiseBlock(matrices.G, BG_ID, BGSTD_ID, identity);
  setNoiseBlock(matrices.G, BA_ID, BASTD_ID, identity);
  setNoiseBlock(matrices.G, SG_ID, SGSTD_ID, identity);
  setNoiseBlock(matrices.G, SA_ID, SASTD_ID, identity);

  // 中文说明：Phi = I + F * dt；N4H4B 使用一阶离散化作为预测传播基础。
  matrices.Phi = phiFromF(matrices.F, dt);
  Matrix21 raw_qd = gQcGt(matrices.G, Qc);
  for (double& value : raw_qd) {
    value *= dt;
  }
  const Matrix21 propagated_qd = aBaT(matrices.Phi, raw_qd);
  for (std::size_t i = 0; i < kStateSize; ++i) {
    for (std::size_t j = 0; j < kStateSize; ++j) {
      matrix21At(matrices.Qd, i, j) = 0.5 * (matrix21At(propagated_qd, i, j) + matrix21At(raw_qd, i, j));
    }
  }

  checkFinite(matrices.F, "F");
  checkFinite(matrices.Phi, "Phi");
  checkFinite(matrices.Qd, "Qd");
  return matrices;
}

}  // namespace legsa_v23_core
