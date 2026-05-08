#pragma once

#include "legsa_v23_core/common/math_types.hpp"

namespace legsa_v23_core {

// 中文说明：process_data-compatible IMU 增量，时间单位为秒，角增量为 rad，速度增量为 m/s。
struct IMUData {
  double time = 0.0;
  double dt = 0.0;
  Vector3 dtheta = zeroVector3();
  Vector3 dvel = zeroVector3();
};

}  // namespace legsa_v23_core
