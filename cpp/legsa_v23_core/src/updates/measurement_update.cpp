#include "legsa_v23_core/updates/measurement_update.hpp"

#include "legsa_v23_core/common/constants.hpp"
#include "legsa_v23_core/common/earth.hpp"
#include "legsa_v23_core/common/rotation.hpp"
#include "legsa_v23_core/updates/yaw_scheme_c.hpp"

#include <algorithm>
#include <cmath>
#include <stdexcept>

namespace legsa_v23_core {
namespace {

// 中文说明：创建 rows 行量测块，H 是 rows x 21，R 是 rows x rows，全部初始化为 0。
MeasurementBlock makeBlock(const std::string& name, std::size_t rows) {
  MeasurementBlock block;
  block.name = name;
  block.rows = rows;
  block.residual.assign(rows, 0.0);
  block.H.assign(rows * kStateSize, 0.0);
  block.R.assign(rows * rows, 0.0);
  return block;
}

// 中文说明：三维矩阵乘三维向量；用于 Cbn*lever 和 DR/DRi 小量转换。
Vector3 mat3Vec(const Matrix3& matrix, const Vector3& vector) {
  Vector3 result = zeroVector3();
  for (std::size_t row = 0; row < kVector3Size; ++row) {
    for (std::size_t col = 0; col < kVector3Size; ++col) {
      result[row] += matrix3At(matrix, row, col) * vector[col];
    }
  }
  return result;
}

// 中文说明：保证标准差有正下限；避免 toy 或配置缺失时 R 矩阵奇异。
double varianceWithFloor(double std_value, double floor_value) {
  const double std_used = std::max(std::abs(std_value), floor_value);
  return std_used * std_used;
}

}  // namespace

double& measurementHAt(MeasurementBlock& block, std::size_t row, std::size_t col) {
  return block.H[row * kStateSize + col];
}

double measurementHAt(const MeasurementBlock& block, std::size_t row, std::size_t col) {
  return block.H[row * kStateSize + col];
}

double& measurementRAt(MeasurementBlock& block, std::size_t row, std::size_t col) {
  return block.R[row * block.rows + col];
}

double measurementRAt(const MeasurementBlock& block, std::size_t row, std::size_t col) {
  return block.R[row * block.rows + col];
}

// 中文说明：位置残差采用 predicted antenna position minus GNSS observed position。
// 中文说明：BLH 小差通过 DR 转为 NED(m)，杆臂在 body/IMU(FRD) 坐标系，不能直接当导航系量。
MeasurementBlock buildGnssPositionMeasurement(const NavState& nav, const GNSSData& gnss,
                                               const GINSOptions& options) {
  MeasurementBlock block = makeBlock("gnss_position", 3);
  const Matrix3 cbn = Rotation::euler2matrix(nav.euler_rpy_rad);
  const Vector3 lever_nav = mat3Vec(cbn, options.antlever);
  const Matrix3 dri = Earth::DRi(nav.pos_blh_rad_m);
  const Vector3 lever_blh = mat3Vec(dri, lever_nav);
  Vector3 antenna_blh = nav.pos_blh_rad_m;
  for (std::size_t i = 0; i < kVector3Size; ++i) {
    antenna_blh[i] += lever_blh[i];
  }

  Vector3 blh_error = zeroVector3();
  for (std::size_t i = 0; i < kVector3Size; ++i) {
    blh_error[i] = antenna_blh[i] - gnss.blh[i];
  }
  const Vector3 residual_ned = mat3Vec(Earth::DR(nav.pos_blh_rad_m), blh_error);
  for (std::size_t i = 0; i < kVector3Size; ++i) {
    block.residual[i] = residual_ned[i];
    measurementHAt(block, i, P_ID + i) = 1.0;
    measurementRAt(block, i, i) = varianceWithFloor(gnss.std[i], 1.0e-3);
  }

  const Matrix3 lever_skew = Rotation::skewSymmetric(lever_nav);
  for (std::size_t row = 0; row < kVector3Size; ++row) {
    for (std::size_t col = 0; col < kVector3Size; ++col) {
      measurementHAt(block, row, PHI_ID + col) = matrix3At(lever_skew, row, col);
    }
  }
  return block;
}

// 中文说明：速度残差采用 nav.vel_ned_mps - gnss.vel；速度观测来自 15 列 .gnss 的 vn/ve/vd。
// 中文说明：N4H4C 不实现 raw Doppler，也不在证据缺失时加入杆臂角速度修正。
MeasurementBlock buildGnssVelocityMeasurement(const NavState& nav, const GNSSData& gnss,
                                               const GINSOptions& options) {
  (void)options;
  MeasurementBlock block = makeBlock("gnss_velocity", 3);
  for (std::size_t i = 0; i < kVector3Size; ++i) {
    block.residual[i] = nav.vel_ned_mps[i] - gnss.vel[i];
    measurementHAt(block, i, V_ID + i) = 1.0;
    measurementRAt(block, i, i) = varianceWithFloor(gnss.vel_std[i], 1.0e-3);
  }
  return block;
}

// 中文说明：yaw 残差默认采用 obs-pred，来源证据缺失时在 manifest/report 标记 default_obs_pred。
// 中文说明：yaw 观测来自双天线 status-yaw，不是 raw heading；scheme_C 是求解器门控，不是评价门限。
std::optional<MeasurementBlock> buildGnssYawMeasurement(const NavState& nav, const GNSSData& gnss,
                                                        const GINSOptions& options) {
  (void)options;
  const double pred_yaw_deg = Rotation::wrapAngleDeg(nav.euler_rpy_rad[2] * kRadToDeg);
  const double residual_deg = Rotation::wrapAngleDeg(gnss.yaw_deg - pred_yaw_deg);
  // 中文说明：调用 applyYawSchemeC 执行规则门控；拒绝时不生成 yaw MeasurementBlock。
  const YawSchemeCDecision decision = applyYawSchemeC(residual_deg, gnss.yaw_std_deg);
  if (!decision.accepted) {
    return std::nullopt;
  }

  MeasurementBlock block = makeBlock("gnss_yaw", 1);
  block.residual[0] = residual_deg * kDegToRad;
  measurementHAt(block, 0, PHI_ID + 2) = 1.0;
  measurementRAt(block, 0, 0) = varianceWithFloor(decision.effective_std_deg * kDegToRad, 1.0e-6);
  return block;
}

}  // namespace legsa_v23_core
