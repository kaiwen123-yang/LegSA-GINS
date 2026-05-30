#pragma once

#include <cstddef>
#include <string>
#include <vector>

namespace legsa_v23_port_core::quality_aware {

static constexpr const char* kLegsaQaFallbackEkf = "LegSA_QA_Fallback_EKF";

enum class QAState {
  S0_NORMAL_A1_VALID,
  S1_A1_DEGRADED_BUT_USABLE,
  S2_A1_INVALID_GNSS_USABLE,
  S3_GNSS_POSITION_DEGRADED,
  S4_DOPPLER_IMU_GO2_BRIDGE,
  S5_HOLD_OR_DEAD_RECKONING,
  S6_RECOVERY_FAST_A1_REACQUISITION,
};

struct QAFallbackConfig {
  std::string algorithm_id;
  bool qa_passive_logging_enabled = false;
  bool enable_qa_fallback = false;
  bool qa_active_mode = false;
  double expected_a1_baseline_m = 0.5;
  double a1_baseline_tolerance_m = 0.35;
  double a1_min_valid_ratio = 0.6;
  double a1_yaw_std_degraded_deg = 3.0;
  double a1_yaw_std_invalid_deg = 10.0;
  double a1_yaw_residual_degraded_deg = 6.0;
  double a1_yaw_residual_invalid_deg = 15.0;
  double a1_yaw_jump_invalid_deg = 20.0;
  double gnss_pos_std_h_degraded_m = 3.0;
  double gnss_pos_std_u_degraded_m = 5.0;
  double gnss_pos_std_h_invalid_m = 15.0;
  double gnss_pos_std_u_invalid_m = 25.0;
  double gnss_pos_innov_high_m = 15.0;
  double raw_doppler_min_count = 5.0;
  int recovery_required_consecutive_a1 = 3;
  double recovery_yaw_residual_gate_deg = 8.0;
  double recovery_yaw_jump_gate_deg = 12.0;
  double recovery_initial_yaw_r_scale = 6.0;
  double recovery_final_yaw_r_scale = 1.0;
  double s1_yaw_r_scale = 4.0;
  double s3_gnss_pos_r_scale = 9.0;
  double s4_gnss_pos_r_scale = 25.0;
  double s5_hold_timeout_s = 5.0;
  bool a1_relpos_diff_valid_default = false;
  double a1_baseline_m_default = 0.0;
  bool a1_baseline_default_available = false;
  double a1_valid_ratio_default = 0.0;
  bool a1_valid_ratio_default_available = false;
  double recovery_max_yaw_correction_deg = 5.0;
  std::string a1_quality_source = "explicit_quality_missing_reject_yaw";
};

struct QAObservation {
  double time = 0.0;
  std::string dataset_id;
  std::string case_id;
  std::string algorithm_id;
  bool a1_available = false;
  bool a1_relpos_diff_valid = false;
  double a1_baseline_m = 0.0;
  bool a1_baseline_available = false;
  double a1_baseline_expected_m = 0.0;
  bool a1_baseline_expected_available = false;
  double a1_valid_ratio_window = 1.0;
  bool a1_valid_ratio_available = false;
  double a1_yaw_std_deg = 0.0;
  bool a1_yaw_std_available = false;
  double a1_yaw_residual_deg = 0.0;
  bool a1_yaw_residual_available = false;
  double a1_yaw_jump_deg = 0.0;
  bool a1_yaw_jump_available = false;
  bool gnss_pos_available = false;
  bool gnss_pos_valid = false;
  std::string gnss_status_or_fix;
  double gnss_pos_std_h_m = 0.0;
  bool gnss_pos_std_h_available = false;
  double gnss_pos_std_u_m = 0.0;
  bool gnss_pos_std_u_available = false;
  double gnss_pos_innovation_m = 0.0;
  bool gnss_pos_innovation_available = false;
  bool raw_doppler_available = false;
  std::size_t raw_doppler_count = 0;
  double raw_doppler_residual = 0.0;
  bool raw_doppler_residual_available = false;
  bool go2_body_state_available = false;
  bool go2_imu_available = false;
  bool selected_feedback_allowed_nominal = false;
  bool filter_output_finite = true;
  bool covariance_finite = true;
};

struct QADecision {
  double time = 0.0;
  std::string dataset_id;
  std::string case_id;
  std::string algorithm_id;
  QAState qa_state = QAState::S0_NORMAL_A1_VALID;
  QAState previous_qa_state = QAState::S0_NORMAL_A1_VALID;
  bool has_previous_qa_state = false;
  bool state_transition_flag = false;
  std::vector<std::string> reason_bits;
  bool a1_available = false;
  bool a1_valid = false;
  double a1_baseline_m = 0.0;
  bool a1_baseline_available = false;
  double a1_baseline_expected_m = 0.0;
  bool a1_baseline_expected_available = false;
  double a1_valid_ratio_window = 0.0;
  bool a1_valid_ratio_available = false;
  double a1_yaw_std_deg = 0.0;
  bool a1_yaw_std_available = false;
  double a1_yaw_residual_deg = 0.0;
  bool a1_yaw_residual_available = false;
  double a1_yaw_jump_deg = 0.0;
  bool a1_yaw_jump_available = false;
  double time_since_last_trusted_a1_s = 0.0;
  bool time_since_last_trusted_a1_available = false;
  int consecutive_valid_a1_count = 0;
  bool gnss_pos_available = false;
  bool gnss_pos_valid = false;
  std::string gnss_status_or_fix;
  double gnss_pos_std_h_m = 0.0;
  bool gnss_pos_std_h_available = false;
  double gnss_pos_std_u_m = 0.0;
  bool gnss_pos_std_u_available = false;
  double time_since_last_trusted_gnss_s = 0.0;
  bool time_since_last_trusted_gnss_available = false;
  bool raw_doppler_available = false;
  std::size_t raw_doppler_count = 0;
  double raw_doppler_residual = 0.0;
  bool raw_doppler_residual_available = false;
  bool go2_body_state_available = false;
  bool go2_imu_available = false;
  bool selected_feedback_allowed_nominal = false;
  bool passive_only = true;
  bool trace_used_for_QA = false;
  bool active_mode = false;
  std::string measurement_policy_id;
  std::string a1_measurement_action = "ACCEPT";
  std::string gnss_position_action = "ACCEPT";
  std::string raw_doppler_action = "UNAVAILABLE";
  std::string go2_aux_action = "UNAVAILABLE";
  std::string selected_feedback_action = "ACCEPT";
  double yaw_R_scale = 1.0;
  double gnss_pos_R_scale = 1.0;
  double doppler_R_scale = 1.0;
  bool recovery_ramp_active = false;
  int recovery_consecutive_valid_a1_count = 0;
  double requested_yaw_correction_deg = 0.0;
  double yaw_correction_applied_deg = 0.0;
  double recovery_yaw_correction_cap_deg = 0.0;
  bool yaw_correction_clipped = false;
  std::string state_transition_reason;
};

class QAFallbackSupervisor {
 public:
  explicit QAFallbackSupervisor(QAFallbackConfig config = {});

  bool loggingEnabled() const;
  bool activeMode() const;
  QADecision evaluate(const QAObservation& observation);
  bool lastDecisionRecoveryRampActive() const;
  double recoveryMaxYawCorrectionDeg() const;
  void setYawCorrectionOnLastDecision(double requested_yaw_correction_deg,
                                      double yaw_correction_applied_deg,
                                      bool clipped);
  const std::vector<QADecision>& trace() const;

 private:
  QAFallbackConfig config_;
  QAState previous_state_ = QAState::S0_NORMAL_A1_VALID;
  bool has_previous_state_ = false;
  double last_trusted_a1_time_ = 0.0;
  bool has_last_trusted_a1_time_ = false;
  double last_trusted_gnss_time_ = 0.0;
  bool has_last_trusted_gnss_time_ = false;
  int consecutive_valid_a1_count_ = 0;
  bool recovery_candidate_active_ = false;
  std::vector<QADecision> trace_;
};

std::string qaStateName(QAState state);
std::string joinReasons(const std::vector<std::string>& reasons);

}  // namespace legsa_v23_port_core::quality_aware
