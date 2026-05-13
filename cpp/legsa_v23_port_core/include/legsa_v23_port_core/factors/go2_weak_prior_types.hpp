// LegSA-GINS source-backed port file.
// Source reference: KF-GINS-graduation-design / final_v23 reference; LegSA-owned N7A extension.
// Source commit: 5a4471efd4fcfcdc31e258a677af354c652ff16f.
// Port role: Go2 body-state roll/pitch weak-prior extension, not final_v23 output substitution.
// Boundary: no trace solver input, no final_v23 output solver input, no Go2 position truth.
// LegSA-GINS N7A Go2 weak-prior extension.
// Boundary: Go2 body-state is internal odometry/IMU state, not global truth.
// 中文说明：Go2 rpy/quaternion 不是高精度真值；N7A 只允许 roll/pitch 弱先验进入 EKF。

#pragma once

#include "legsa_v23_port_core/types.hpp"

#include <cstddef>
#include <string>

namespace legsa_v23_port_core {

struct Go2AttitudeWeakPriorMeasurement {
  double time = 0.0;
  double roll_rad = 0.0;
  double pitch_rad = 0.0;
  double std_roll_rad = 5.0 * 3.14159265358979323846 / 180.0;
  double std_pitch_rad = 5.0 * 3.14159265358979323846 / 180.0;
  std::string source_status = "inactive";
  std::string quality_flag = "suspicious";
  int mode = -1;
  int gait_type = -1;
  double foot_force_sum = 0.0;
  double body_height = 0.0;
};

struct Go2AttitudeWeakPriorConfig {
  bool enable_go2_attitude_weak_prior = false;
  std::string go2_attitude_prior_path;
  double go2_attitude_prior_time_tolerance_sec = 0.02;
  double go2_attitude_prior_std_roll_deg = 5.0;
  double go2_attitude_prior_std_pitch_deg = 5.0;
  bool go2_attitude_prior_sourceaware = true;
  bool go2_attitude_prior_diagnostic_only = true;
  bool go2_position_prior_enabled = false;
  bool go2_velocity_prior_enabled = false;
  bool go2_yaw_prior_enabled = false;
};

struct Go2AttitudeWeakPriorStatus {
  bool code_present = true;
  bool solver_enabled = false;
  std::size_t prior_count = 0;
  std::size_t valid_prior_count = 0;
  std::size_t update_count = 0;
  std::size_t reject_count = 0;
  double residual_roll_p95_rad = 0.0;
  double residual_pitch_p95_rad = 0.0;
  std::string provider_status = "prior_path_missing";
  std::string source_id = "go2_attitude_roll_pitch";
  bool weak_prior = true;
  bool body_state_not_truth = true;
  bool position_prior_enabled = false;
  bool velocity_prior_enabled = false;
  bool yaw_prior_enabled = false;
};

struct Go2VelocityDiagnosticPriorMeasurement {
  double time = 0.0;
  Vec3 velocity_ned_mps = makeVec3(0.0, 0.0, 0.0);
  Vec3 std_ned_mps = makeVec3(2.0, 2.0, 2.0);
  std::string source_status = "inactive";
  std::string quality_flag = "diagnostic_only";
  std::string contact_model;
  std::string contact_label;
  std::string frame_candidate;
  std::string prior_policy;
  bool diagnostic_only = true;
  bool go2_velocity_truth_claim = false;
};

struct Go2VelocityDiagnosticPriorConfig {
  bool enable_go2_velocity_prior_diagnostic = false;
  bool enable_go2_horizontal_velocity_prior = false;
  std::string go2_velocity_prior_diagnostic_path;
  std::string go2_horizontal_velocity_prior_path;
  double go2_velocity_prior_time_tolerance_sec = 0.08;
  double go2_velocity_prior_std_scale = 1.0;
  bool go2_diagnostic_prior_only = true;
  bool go2_horizontal_velocity_prior_vertical_disabled = true;
  bool go2_horizontal_velocity_prior_source_aware_enabled = true;
  std::string go2_horizontal_velocity_prior_mode = "horizontal_2d";
};

struct Go2VelocityDiagnosticPriorStatus {
  bool code_present = true;
  bool solver_enabled = false;
  std::size_t prior_count = 0;
  std::size_t valid_prior_count = 0;
  std::size_t update_count = 0;
  std::size_t reject_count = 0;
  std::size_t horizontal_update_count = 0;
  std::string provider_status = "prior_path_missing";
  std::string source_id = "go2_velocity_diagnostic";
  bool horizontal_only = false;
  bool vertical_disabled = false;
  bool diagnostic_only = true;
  bool controlled_activation = false;
  bool paper_performance_claim = false;
  bool go2_velocity_truth_claim = false;
};

struct Go2YawRateDiagnosticPriorConfig {
  bool enable_go2_yaw_rate_prior_diagnostic = false;
  std::string go2_yaw_rate_prior_diagnostic_path;
  bool go2_diagnostic_prior_only = true;
};

struct Go2YawRateDiagnosticPriorStatus {
  bool code_present = true;
  bool solver_enabled = false;
  std::size_t prior_count = 0;
  std::size_t update_count = 0;
  std::size_t reject_count = 0;
  std::string provider_status = "disabled_by_config";
  std::string activation_status = "yaw_rate_prior_not_activated_due_to_state_model";
  bool diagnostic_only = true;
  bool paper_performance_claim = false;
};

}  // namespace legsa_v23_port_core
