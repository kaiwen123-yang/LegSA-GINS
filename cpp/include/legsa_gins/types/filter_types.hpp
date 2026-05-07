// 中文说明：N4 定义 21 维误差状态合同；当前使用 diagonal covariance foundation，不声明 full EKF matrix。
// English note: Receiver-native P/V/heading measurements are the only N4 updates.

#pragma once

#include <array>
#include <string>

#include "legsa_gins/math/quaternion.hpp"
#include "legsa_gins/math/vec3.hpp"

namespace legsa_gins::types {

constexpr int kErrorStateSize = 21;

enum ErrorStateIndex {
  P_ID = 0,
  V_ID = 3,
  PHI_ID = 6,
  BG_ID = 9,
  BA_ID = 12,
  SG_ID = 15,
  SA_ID = 18,
};

struct PvaState {
  double tow = 0.0;
  math::Vec3 blh_rad_m{};
  math::Vec3 vel_ned_mps{};
  math::Quaternion qbn = math::identity();
  math::Vec3 euler_rad{};
};

struct ImuErrorState {
  math::Vec3 gyro_bias_radps{};
  math::Vec3 accel_bias_mps2{};
  math::Vec3 gyro_scale{};
  math::Vec3 accel_scale{};
};

struct LegSAFilterState {
  PvaState pva{};
  ImuErrorState imu_error{};
  std::string status = "legsa_filter_core_toy_only";
};

struct DiagCovariance21 {
  std::array<double, kErrorStateSize> diag{};
};

struct ErrorState21 {
  std::array<double, kErrorStateSize> dx{};
};

struct ReceiverNativeMeasurement {
  double tow = 0.0;
  bool has_position = false;
  bool has_velocity = false;
  bool has_heading = false;
  math::Vec3 blh_rad_m{};
  math::Vec3 pos_std_m{1.0, 1.0, 1.0};
  math::Vec3 vel_ned_mps{};
  math::Vec3 vel_std_mps{0.1, 0.1, 0.1};
  double yaw_heading_rad = 0.0;
  double yaw_std_rad = 1.0;
  std::string source = "receiver_native";
};

}  // namespace legsa_gins::types
