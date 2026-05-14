// LegSA-GINS source-backed port file.
// Source reference: KF-GINS-graduation-design / final_v23 reference.
// Source commit: 5a4471efd4fcfcdc31e258a677af354c652ff16f.
// Port role: N8G feedback interface attached to the source-backed EKF backbone, not proposed novelty.
// Boundary: FGO feedback enters EKFUpdate as a pseudo-measurement; no NAV overwrite.
// 中文说明：该接口只读取 runtime-only FGO_FEEDBACK_OBSERVATIONS.csv，不读取 trace/final_v23 输出。

#pragma once

#include "legsa_v23_port_core/types.hpp"

#include <cstddef>
#include <string>
#include <vector>

namespace legsa_v23_port_core::fgo_feedback {

struct FgoFeedbackConfig {
  bool enable_fgo_feedback = false;
  std::string fgo_feedback_path;
  std::string fgo_feedback_mode = "pseudo_measurement";
  bool fgo_feedback_position_enabled = false;
  bool fgo_feedback_velocity_enabled = true;
  bool fgo_feedback_attitude_enabled = true;
  double fgo_feedback_covariance_scale = 1.0;
  double fgo_feedback_max_position_correction_m = 6.0;
  double fgo_feedback_max_velocity_correction_mps = 1.5;
  double fgo_feedback_max_attitude_correction_deg = 8.0;
  double fgo_feedback_min_interval_s = 0.5;
  double fgo_feedback_time_tolerance_sec = 0.02;
  bool fgo_feedback_no_future_data_required = true;
};

struct FgoFeedbackObservation {
  double time = 0.0;
  Vec3 position_ned_m = Vec3{0.0, 0.0, 0.0};
  Vec3 velocity_ned_mps = Vec3{0.0, 0.0, 0.0};
  Vec3 attitude_rad = Vec3{0.0, 0.0, 0.0};
  Vec3 position_std_m = Vec3{1.0, 1.0, 1.0};
  Vec3 velocity_std_mps = Vec3{1.0, 1.0, 1.0};
  Vec3 attitude_std_rad = Vec3{1.0 * D2R, 1.0 * D2R, 1.0 * D2R};
  double source_window_start = 0.0;
  double source_window_end = 0.0;
  bool feedback_valid = false;
  std::size_t window_epoch_count = 0;
  std::string feedback_mode = "pseudo_measurement";
};

struct FgoFeedbackStatus {
  bool code_present = true;
  bool solver_enabled = false;
  std::size_t observation_count = 0;
  std::size_t valid_observation_count = 0;
  std::size_t update_count = 0;
  std::size_t accept_count = 0;
  std::size_t reject_count = 0;
  std::size_t future_data_reject_count = 0;
  bool no_future_data = true;
  bool output_substitution = false;
  bool direct_nav_override = false;
  double correction_position_p50_m = 0.0;
  double correction_position_p95_m = 0.0;
  double correction_position_max_m = 0.0;
  double correction_velocity_p50_mps = 0.0;
  double correction_velocity_p95_mps = 0.0;
  double correction_velocity_max_mps = 0.0;
  double correction_attitude_p50_deg = 0.0;
  double correction_attitude_p95_deg = 0.0;
  double correction_attitude_max_deg = 0.0;
  double residual_p95 = 0.0;
  std::string provider_status = "not_loaded";
};

struct FgoFeedbackTraceRow {
  double update_time = 0.0;
  double observation_time = 0.0;
  int accepted = 0;
  std::string reject_reason;
  double position_norm_m = 0.0;
  double velocity_norm_mps = 0.0;
  double attitude_norm_deg = 0.0;
  double yaw_residual_deg = 0.0;
  double source_window_start = 0.0;
  double source_window_end = 0.0;
};

struct FgoFeedbackLoadResult {
  std::vector<FgoFeedbackObservation> observations;
  FgoFeedbackStatus status;
};

class FgoFeedbackLoader {
 public:
  static FgoFeedbackLoadResult loadCsv(const std::string& path, const FgoFeedbackConfig& config);
};

double wrapRadians(double value);
double wrapDegrees(double value);

}  // namespace legsa_v23_port_core::fgo_feedback
