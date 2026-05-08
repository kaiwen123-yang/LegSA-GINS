#pragma once

#include "legsa_v23_core/common/math_types.hpp"

namespace legsa_v23_core {

// 中文说明：final_v23-style 15 列 GNSS 高层状态输入，不是 RAWX/SFRBX/RTCM 原始观测。
// blh 使用 rad/rad/m；速度为 NED m/s；yaw 保留 deg，更新函数可自行转 rad。
struct GNSSData {
  double time = 0.0;
  Vector3 blh = zeroVector3();
  Vector3 std = zeroVector3();
  Vector3 vel = zeroVector3();
  Vector3 vel_std = zeroVector3();
  double yaw_deg = 0.0;
  double yaw_std_deg = 0.0;
  bool has_velocity = false;
  bool has_yaw = false;
  bool isvalid = false;
};

}  // namespace legsa_v23_core
