#pragma once

#include <cstddef>

namespace legsa_v23_core {

// 中文说明：N4H4A 只定义框架常量；坐标系为导航系 NED，位置使用 BLH(rad, rad, m)。
constexpr std::size_t kStateSize = 21;
constexpr std::size_t kNoiseSize = 18;
constexpr std::size_t kVector3Size = 3;
constexpr double kDegToRad = 3.14159265358979323846 / 180.0;
constexpr double kRadToDeg = 180.0 / 3.14159265358979323846;
constexpr double kDefaultCovarianceFloor = 1.0e-18;
constexpr double kWgs84A = 6378137.0;
constexpr double kWgs84F = 1.0 / 298.257223563;
constexpr double kWgs84Wie = 7.2921151467e-5;
constexpr double kWgs84GM = 3.986004418e14;
constexpr double kWgs84E2 = kWgs84F * (2.0 - kWgs84F);

// 中文说明：21 维误差状态索引，顺序对齐 KF-GINS-style p/v/phi/bg/ba/sg/sa。
enum ErrorStateIndex : std::size_t {
  P_ID = 0,
  V_ID = 3,
  PHI_ID = 6,
  BG_ID = 9,
  BA_ID = 12,
  SG_ID = 15,
  SA_ID = 18,
};

// 中文说明：IMU 噪声索引，单位转换在 config loader 内完成，N4H4A 不闭合噪声模型。
enum NoiseIndex : std::size_t {
  ARW_ID = 0,
  VRW_ID = 3,
  BGSTD_ID = 6,
  BASTD_ID = 9,
  SGSTD_ID = 12,
  SASTD_ID = 15,
};

}  // namespace legsa_v23_core
