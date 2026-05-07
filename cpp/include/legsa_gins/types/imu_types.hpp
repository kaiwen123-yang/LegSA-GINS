// 中文说明：N4 toy filter 使用增量形式 IMU；不能把 receiver imu-data.csv 当作 Go2 body-state IMU。
// English note: The default frame is IMU_FRD_COMPATIBLE; BY2 body-state remains separate.

#pragma once

#include <string>

#include "legsa_gins/math/vec3.hpp"

namespace legsa_gins::types {

struct LegSAImuSample {
  double tow = 0.0;
  double dt = 0.0;
  math::Vec3 dtheta_rad{};
  math::Vec3 dvel_mps{};
  std::string frame = "IMU_FRD_COMPATIBLE";
};

}  // namespace legsa_gins::types
