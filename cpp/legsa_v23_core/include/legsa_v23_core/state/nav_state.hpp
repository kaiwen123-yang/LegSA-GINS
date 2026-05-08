#pragma once

#include "legsa_v23_core/common/math_types.hpp"

namespace legsa_v23_core {

// 中文说明：名义导航状态。位置为 BLH(rad,rad,m)，速度为 NED(m/s)，姿态为 roll/pitch/yaw(rad)。
struct NavState {
  Vector3 pos_blh_rad_m = zeroVector3();
  Vector3 vel_ned_mps = zeroVector3();
  Vector3 euler_rpy_rad = zeroVector3();
  Vector3 gyro_bias = zeroVector3();
  Vector3 acc_bias = zeroVector3();
  Vector3 gyro_scale = zeroVector3();
  Vector3 acc_scale = zeroVector3();
};

using PVAState = NavState;

}  // namespace legsa_v23_core
