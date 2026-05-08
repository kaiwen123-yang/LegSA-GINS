#pragma once

#include "legsa_v23_core/config/gins_options.hpp"
#include "legsa_v23_core/state/gnss_types.hpp"
#include "legsa_v23_core/state/nav_state.hpp"

#include <cstddef>
#include <optional>
#include <string>
#include <vector>

namespace legsa_v23_core {

// 中文说明：MeasurementBlock 存储松组合量测 dz/H/R；dz 的单位由量测类型决定。
// 位置残差为 NED(m)，速度残差为 NED(m/s)，yaw 残差为 rad；H 对应 21 维误差状态。
struct MeasurementBlock {
  std::string name;
  std::size_t rows = 0;
  std::vector<double> residual;
  std::vector<double> H;
  std::vector<double> R;
};

// 中文说明：访问 H(row,col)，row 是量测行，col 是 21-state 误差状态索引。
double& measurementHAt(MeasurementBlock& block, std::size_t row, std::size_t col);

// 中文说明：只读访问 H(row,col)，用于 EKFUpdate 审计和数值计算。
double measurementHAt(const MeasurementBlock& block, std::size_t row, std::size_t col);

// 中文说明：访问 R(row,col)，row/col 是量测维度索引。
double& measurementRAt(MeasurementBlock& block, std::size_t row, std::size_t col);

// 中文说明：只读访问 R(row,col)，单位为量测方差。
double measurementRAt(const MeasurementBlock& block, std::size_t row, std::size_t col);

// 中文说明：构建 GNSS 位置量测；输入 GNSS 是 15 列高层 BLH/std，不是 RAWX/SFRBX/RTCM。
MeasurementBlock buildGnssPositionMeasurement(const NavState& nav, const GNSSData& gnss,
                                               const GINSOptions& options);

// 中文说明：构建 GNSS 速度量测；本阶段使用 vn/ve/vd 高层速度，不实现 raw Doppler。
MeasurementBlock buildGnssVelocityMeasurement(const NavState& nav, const GNSSData& gnss,
                                               const GINSOptions& options);

// 中文说明：构建 GNSS yaw 量测；若 scheme_C 拒绝则返回空量测，不伪造 yaw update。
std::optional<MeasurementBlock> buildGnssYawMeasurement(const NavState& nav, const GNSSData& gnss,
                                                        const GINSOptions& options);

}  // namespace legsa_v23_core
