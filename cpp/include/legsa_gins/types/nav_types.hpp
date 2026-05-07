// 中文说明：类型定义只承载状态和观测字段合同，不隐含滤波器、平滑器或性能结论。
// English note: comments define module responsibility and safety boundaries only.

#pragma once

#include <string>

namespace legsa_gins::types {

struct NavState {
  double tow = 0.0;
  double lat_deg = 0.0;
  double lon_deg = 0.0;
  double height_m = 0.0;
  double vn_mps = 0.0;
  double ve_mps = 0.0;
  double vd_mps = 0.0;
  double roll_deg = 0.0;
  double pitch_deg = 0.0;
  double yaw_deg = 0.0;
  std::string status = "initialized";
  std::string source_role = "proposed";
};

struct StdState {
  double tow = 0.0;
  double std_pos_n_m = 0.0;
  double std_pos_e_m = 0.0;
  double std_pos_d_m = 0.0;
  double std_vel_n_mps = 0.0;
  double std_vel_e_mps = 0.0;
  double std_vel_d_mps = 0.0;
  double std_roll_deg = 0.0;
  double std_pitch_deg = 0.0;
  double std_yaw_deg = 0.0;
  double std_gyrbias_x_dph = 0.0;
  double std_gyrbias_y_dph = 0.0;
  double std_gyrbias_z_dph = 0.0;
  double std_accbias_x_mgal = 0.0;
  double std_accbias_y_mgal = 0.0;
  double std_accbias_z_mgal = 0.0;
  double std_gyrscale_x_ppm = 0.0;
  double std_gyrscale_y_ppm = 0.0;
  double std_gyrscale_z_ppm = 0.0;
  double std_accscale_x_ppm = 0.0;
  double std_accscale_y_ppm = 0.0;
  double std_accscale_z_ppm = 0.0;
};

struct ImuSample {
  double tow = 0.0;
  double dt = 0.0;
  double dtheta[3] = {0.0, 0.0, 0.0};
  double dvel[3] = {0.0, 0.0, 0.0};
  std::string frame = "IMU_FRD_COMPATIBLE";
};

struct GnssNativeMeasurement {
  double tow = 0.0;
  double lat_deg = 0.0;
  double lon_deg = 0.0;
  double height_m = 0.0;
  double vn_mps = 0.0;
  double ve_mps = 0.0;
  double vd_mps = 0.0;
  double yaw_deg = 0.0;
  bool has_position = false;
  bool has_velocity = false;
  bool has_yaw = false;
  std::string source = "receiver_native";
};

}  // namespace legsa_gins::types
