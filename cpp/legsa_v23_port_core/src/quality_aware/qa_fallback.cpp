#include "legsa_v23_port_core/quality_aware/qa_fallback.hpp"

#include <algorithm>
#include <cmath>
#include <sstream>
#include <utility>

namespace legsa_v23_port_core::quality_aware {
namespace {

void addReason(std::vector<std::string>& reasons, const std::string& reason) {
  if (std::find(reasons.begin(), reasons.end(), reason) == reasons.end()) {
    reasons.push_back(reason);
  }
}

bool hasAlgorithmQaIdentity(const QAFallbackConfig& config) {
  return config.algorithm_id == kLegsaQaFallbackEkf;
}

bool rawAvailable(const QAObservation& observation, const QAFallbackConfig& config) {
  return observation.raw_doppler_available &&
         static_cast<double>(observation.raw_doppler_count) >= config.raw_doppler_min_count;
}

bool go2Available(const QAObservation& observation) {
  return observation.go2_body_state_available || observation.go2_imu_available;
}

bool hasReason(const QADecision& decision, const std::string& reason) {
  return std::find(decision.reason_bits.begin(), decision.reason_bits.end(), reason) !=
         decision.reason_bits.end();
}

bool a1PhysicalQualityNominal(const QADecision& decision) {
  return decision.a1_available &&
         !hasReason(decision, "A1_MISSING") &&
         !hasReason(decision, "A1_BASELINE_INVALID") &&
         !hasReason(decision, "A1_VALID_RATIO_LOW") &&
         !hasReason(decision, "A1_YAW_STD_HIGH") &&
         !hasReason(decision, "A1_YAW_JUMP");
}

bool s1NominalTransparent(const QADecision& decision) {
  return a1PhysicalQualityNominal(decision) &&
         !hasReason(decision, "RECOVERY_PENDING_AFTER_INVALID");
}

double conservativeS1YawRScale(const QAFallbackConfig& config) {
  return std::max(1.0, std::min(config.s1_yaw_r_scale, 2.0));
}

void copyObservation(QADecision& decision, const QAObservation& observation) {
  decision.time = observation.time;
  decision.dataset_id = observation.dataset_id;
  decision.case_id = observation.case_id;
  decision.algorithm_id = observation.algorithm_id;
  decision.a1_available = observation.a1_available;
  decision.a1_baseline_m = observation.a1_baseline_m;
  decision.a1_baseline_available = observation.a1_baseline_available;
  decision.a1_baseline_expected_m = observation.a1_baseline_expected_m;
  decision.a1_baseline_expected_available = observation.a1_baseline_expected_available;
  decision.a1_valid_ratio_window = observation.a1_valid_ratio_window;
  decision.a1_valid_ratio_available = observation.a1_valid_ratio_available;
  decision.a1_yaw_std_deg = observation.a1_yaw_std_deg;
  decision.a1_yaw_std_available = observation.a1_yaw_std_available;
  decision.a1_yaw_residual_deg = observation.a1_yaw_residual_deg;
  decision.a1_yaw_residual_available = observation.a1_yaw_residual_available;
  decision.a1_yaw_jump_deg = observation.a1_yaw_jump_deg;
  decision.a1_yaw_jump_available = observation.a1_yaw_jump_available;
  decision.gnss_pos_available = observation.gnss_pos_available;
  decision.gnss_status_or_fix = observation.gnss_status_or_fix;
  decision.gnss_pos_std_h_m = observation.gnss_pos_std_h_m;
  decision.gnss_pos_std_h_available = observation.gnss_pos_std_h_available;
  decision.gnss_pos_std_u_m = observation.gnss_pos_std_u_m;
  decision.gnss_pos_std_u_available = observation.gnss_pos_std_u_available;
  decision.raw_doppler_available = observation.raw_doppler_available;
  decision.raw_doppler_count = observation.raw_doppler_count;
  decision.raw_doppler_residual = observation.raw_doppler_residual;
  decision.raw_doppler_residual_available = observation.raw_doppler_residual_available;
  decision.go2_body_state_available = observation.go2_body_state_available;
  decision.go2_imu_available = observation.go2_imu_available;
  decision.selected_feedback_allowed_nominal = observation.selected_feedback_allowed_nominal;
}

void applyMeasurementPolicy(QADecision& decision, const QAFallbackConfig& config) {
  const bool raw_available = decision.raw_doppler_available;
  const bool go2_available = decision.go2_body_state_available || decision.go2_imu_available;
  decision.raw_doppler_action = raw_available ? "ACCEPT" : "UNAVAILABLE";
  decision.go2_aux_action = go2_available ? "ACCEPT" : "UNAVAILABLE";
  switch (decision.qa_state) {
    case QAState::S0_NORMAL_A1_VALID:
      break;
    case QAState::S1_A1_DEGRADED_BUT_USABLE:
      if (s1NominalTransparent(decision)) {
        decision.a1_measurement_action = "ACCEPT";
        decision.yaw_R_scale = 1.0;
        decision.selected_feedback_action = "ACCEPT";
      } else {
        decision.a1_measurement_action = "DOWNWEIGHT";
        decision.yaw_R_scale = conservativeS1YawRScale(config);
        decision.selected_feedback_action = "DISABLED";
      }
      break;
    case QAState::S2_A1_INVALID_GNSS_USABLE:
      decision.a1_measurement_action = "REJECT";
      decision.selected_feedback_action = "DISABLED";
      break;
    case QAState::S3_GNSS_POSITION_DEGRADED:
      decision.gnss_position_action = "DOWNWEIGHT";
      decision.gnss_pos_R_scale = std::max(1.0, config.s3_gnss_pos_r_scale);
      if (!decision.a1_valid) {
        decision.a1_measurement_action = "REJECT";
      }
      decision.selected_feedback_action = "DISABLED";
      break;
    case QAState::S4_DOPPLER_IMU_GO2_BRIDGE:
      decision.gnss_position_action = "REJECT";
      decision.gnss_pos_R_scale = std::max(1.0, config.s4_gnss_pos_r_scale);
      decision.a1_measurement_action = decision.a1_valid ? "ACCEPT" : "REJECT";
      decision.selected_feedback_action = "DISABLED";
      break;
    case QAState::S5_HOLD_OR_DEAD_RECKONING:
      decision.gnss_position_action = "HOLD";
      decision.a1_measurement_action = "REJECT";
      decision.selected_feedback_action = "DISABLED";
      break;
    case QAState::S6_RECOVERY_FAST_A1_REACQUISITION: {
      decision.a1_measurement_action = "RECOVERY_RAMP";
      decision.recovery_ramp_active = true;
      decision.recovery_yaw_correction_cap_deg = std::max(0.0, config.recovery_max_yaw_correction_deg);
      const double required = std::max(1, config.recovery_required_consecutive_a1);
      const double ramp_count = std::max(
          1.0,
          static_cast<double>(decision.consecutive_valid_a1_count - config.recovery_required_consecutive_a1 + 1));
      const double progress = std::min(required, ramp_count) / required;
      decision.yaw_R_scale =
          std::max(config.recovery_final_yaw_r_scale,
                   config.recovery_initial_yaw_r_scale -
                       (config.recovery_initial_yaw_r_scale - config.recovery_final_yaw_r_scale) * progress);
      decision.selected_feedback_action = "DISABLED";
      break;
    }
  }
  decision.measurement_policy_id = "qa_fallback_" + qaStateName(decision.qa_state) +
                                   (decision.active_mode ? "_active" : "_passive");
  decision.state_transition_reason = joinReasons(decision.reason_bits);
}

}  // namespace

QAFallbackSupervisor::QAFallbackSupervisor(QAFallbackConfig config) : config_(std::move(config)) {}

bool QAFallbackSupervisor::loggingEnabled() const {
  return config_.qa_passive_logging_enabled || config_.enable_qa_fallback ||
         config_.qa_active_mode || hasAlgorithmQaIdentity(config_);
}

bool QAFallbackSupervisor::activeMode() const {
  return config_.enable_qa_fallback || config_.qa_active_mode || hasAlgorithmQaIdentity(config_);
}

bool QAFallbackSupervisor::lastDecisionRecoveryRampActive() const {
  return !trace_.empty() && trace_.back().recovery_ramp_active;
}

double QAFallbackSupervisor::recoveryMaxYawCorrectionDeg() const {
  return std::max(0.0, config_.recovery_max_yaw_correction_deg);
}

QADecision QAFallbackSupervisor::evaluate(const QAObservation& observation) {
  QADecision decision;
  copyObservation(decision, observation);
  decision.previous_qa_state = previous_state_;
  decision.has_previous_qa_state = has_previous_state_;
  decision.active_mode = activeMode();
  decision.passive_only = !decision.active_mode;
  addReason(decision.reason_bits, "TRACE_NOT_USED");

  bool a1_baseline_invalid = false;
  const double expected = observation.a1_baseline_expected_available
                              ? observation.a1_baseline_expected_m
                              : config_.expected_a1_baseline_m;
  if (observation.a1_baseline_available) {
    a1_baseline_invalid =
        std::fabs(observation.a1_baseline_m - expected) > config_.a1_baseline_tolerance_m;
  }
  if (!observation.a1_available) {
    addReason(decision.reason_bits, "A1_MISSING");
  }
  if (!observation.a1_relpos_diff_valid || a1_baseline_invalid) {
    addReason(decision.reason_bits, "A1_BASELINE_INVALID");
  }
  if (observation.a1_valid_ratio_available &&
      observation.a1_valid_ratio_window < config_.a1_min_valid_ratio) {
    addReason(decision.reason_bits, "A1_VALID_RATIO_LOW");
  }
  if (observation.a1_yaw_std_available &&
      observation.a1_yaw_std_deg > config_.a1_yaw_std_degraded_deg) {
    addReason(decision.reason_bits, "A1_YAW_STD_HIGH");
  }
  if (observation.a1_yaw_residual_available &&
      std::fabs(observation.a1_yaw_residual_deg) > config_.a1_yaw_residual_degraded_deg) {
    addReason(decision.reason_bits, "A1_RESIDUAL_HIGH");
  }
  if (observation.a1_yaw_jump_available &&
      std::fabs(observation.a1_yaw_jump_deg) > config_.a1_yaw_jump_invalid_deg) {
    addReason(decision.reason_bits, "A1_YAW_JUMP");
  }

  const bool a1_yaw_std_invalid =
      observation.a1_yaw_std_available &&
      observation.a1_yaw_std_deg > config_.a1_yaw_std_invalid_deg;
  const bool a1_yaw_residual_invalid =
      observation.a1_yaw_residual_available &&
      std::fabs(observation.a1_yaw_residual_deg) > config_.a1_yaw_residual_invalid_deg;
  const bool a1_yaw_jump_invalid =
      observation.a1_yaw_jump_available &&
      std::fabs(observation.a1_yaw_jump_deg) > config_.a1_yaw_jump_invalid_deg;
  const bool a1_physical_invalid =
      !observation.a1_available || !observation.a1_relpos_diff_valid || a1_baseline_invalid ||
      a1_yaw_std_invalid || a1_yaw_jump_invalid;
  const bool a1_physical_degraded =
      !a1_physical_invalid &&
      ((observation.a1_valid_ratio_available &&
        observation.a1_valid_ratio_window < config_.a1_min_valid_ratio) ||
       (observation.a1_yaw_std_available &&
        observation.a1_yaw_std_deg > config_.a1_yaw_std_degraded_deg));
  const bool a1_hard_invalid = a1_physical_invalid || (a1_physical_degraded && a1_yaw_residual_invalid);
  const bool a1_degraded = !a1_hard_invalid && a1_physical_degraded;
  decision.a1_valid = !a1_hard_invalid && !a1_degraded;

  if (!observation.gnss_pos_available) {
    addReason(decision.reason_bits, "GNSS_POS_MISSING");
  }
  const bool gnss_std_high =
      (observation.gnss_pos_std_h_available &&
       observation.gnss_pos_std_h_m > config_.gnss_pos_std_h_degraded_m) ||
      (observation.gnss_pos_std_u_available &&
       observation.gnss_pos_std_u_m > config_.gnss_pos_std_u_degraded_m);
  const bool gnss_std_invalid =
      (observation.gnss_pos_std_h_available &&
       observation.gnss_pos_std_h_m > config_.gnss_pos_std_h_invalid_m) ||
      (observation.gnss_pos_std_u_available &&
       observation.gnss_pos_std_u_m > config_.gnss_pos_std_u_invalid_m);
  if (gnss_std_high) {
    addReason(decision.reason_bits, "GNSS_POS_STD_HIGH");
  }
  const bool gnss_innov_high =
      observation.gnss_pos_innovation_available &&
      observation.gnss_pos_innovation_m > config_.gnss_pos_innov_high_m;
  if (gnss_innov_high) {
    addReason(decision.reason_bits, "GNSS_POS_INNOV_HIGH");
  }
  const bool gnss_invalid = !observation.gnss_pos_available || gnss_std_invalid;
  const bool gnss_degraded = !gnss_invalid && (gnss_std_high || gnss_innov_high);
  decision.gnss_pos_valid = !gnss_invalid && !gnss_degraded;

  if (!rawAvailable(observation, config_)) {
    addReason(decision.reason_bits, "DOPPLER_MISSING");
  }
  if (!go2Available(observation)) {
    addReason(decision.reason_bits, "GO2_BODY_STATE_MISSING");
  }

  if (decision.a1_valid) {
    ++consecutive_valid_a1_count_;
    last_trusted_a1_time_ = observation.time;
    has_last_trusted_a1_time_ = true;
  } else {
    consecutive_valid_a1_count_ = 0;
  }
  if (decision.gnss_pos_valid) {
    last_trusted_gnss_time_ = observation.time;
    has_last_trusted_gnss_time_ = true;
  }
  decision.consecutive_valid_a1_count = consecutive_valid_a1_count_;
  decision.recovery_consecutive_valid_a1_count = consecutive_valid_a1_count_;
  if (has_last_trusted_a1_time_) {
    decision.time_since_last_trusted_a1_s = std::max(0.0, observation.time - last_trusted_a1_time_);
    decision.time_since_last_trusted_a1_available = true;
  }
  if (has_last_trusted_gnss_time_) {
    decision.time_since_last_trusted_gnss_s = std::max(0.0, observation.time - last_trusted_gnss_time_);
    decision.time_since_last_trusted_gnss_available = true;
  }

  const bool previous_recovery_source =
      has_previous_state_ &&
      (previous_state_ == QAState::S2_A1_INVALID_GNSS_USABLE ||
       previous_state_ == QAState::S4_DOPPLER_IMU_GO2_BRIDGE ||
       previous_state_ == QAState::S5_HOLD_OR_DEAD_RECKONING);
  if (has_previous_state_ && previous_state_ == QAState::S6_RECOVERY_FAST_A1_REACQUISITION &&
      decision.a1_valid && decision.gnss_pos_valid) {
    recovery_candidate_active_ = false;
  } else if (previous_recovery_source && decision.a1_valid && decision.gnss_pos_valid) {
    recovery_candidate_active_ = true;
  }
  if (!decision.a1_valid || !decision.gnss_pos_valid) {
    recovery_candidate_active_ = previous_recovery_source;
  }
  const bool recovery_ready =
      recovery_candidate_active_ &&
      decision.a1_valid && decision.gnss_pos_valid &&
      consecutive_valid_a1_count_ >= config_.recovery_required_consecutive_a1 &&
      (!observation.a1_yaw_residual_available ||
       std::fabs(observation.a1_yaw_residual_deg) <= config_.recovery_yaw_residual_gate_deg) &&
      (!observation.a1_yaw_jump_available ||
       std::fabs(observation.a1_yaw_jump_deg) <= config_.recovery_yaw_jump_gate_deg);
  if (!observation.filter_output_finite || !observation.covariance_finite) {
    addReason(decision.reason_bits, "HOLD_TIMEOUT_RISK");
    decision.qa_state = QAState::S5_HOLD_OR_DEAD_RECKONING;
  } else if (recovery_ready) {
    addReason(decision.reason_bits, "RECOVERY_CONSECUTIVE_A1_VALID");
    decision.qa_state = QAState::S6_RECOVERY_FAST_A1_REACQUISITION;
  } else if (recovery_candidate_active_ && decision.a1_valid && decision.gnss_pos_valid) {
    addReason(decision.reason_bits, "RECOVERY_PENDING_AFTER_INVALID");
    decision.qa_state = QAState::S1_A1_DEGRADED_BUT_USABLE;
  } else if (decision.a1_valid && decision.gnss_pos_valid) {
    decision.qa_state = QAState::S0_NORMAL_A1_VALID;
  } else if (a1_degraded && decision.gnss_pos_valid) {
    decision.qa_state = QAState::S1_A1_DEGRADED_BUT_USABLE;
  } else if (!decision.a1_valid && decision.gnss_pos_valid) {
    decision.qa_state = QAState::S2_A1_INVALID_GNSS_USABLE;
  } else if (gnss_degraded) {
    decision.qa_state = QAState::S3_GNSS_POSITION_DEGRADED;
  } else if (gnss_invalid && (rawAvailable(observation, config_) || go2Available(observation))) {
    decision.qa_state = QAState::S4_DOPPLER_IMU_GO2_BRIDGE;
  } else {
    addReason(decision.reason_bits, "HOLD_TIMEOUT_RISK");
    decision.qa_state = QAState::S5_HOLD_OR_DEAD_RECKONING;
  }
  if (has_previous_state_ && previous_state_ != QAState::S0_NORMAL_A1_VALID &&
      observation.a1_available && !decision.a1_valid) {
    addReason(decision.reason_bits, "RECOVERY_A1_REJECTED");
  }
  decision.state_transition_flag = has_previous_state_ && previous_state_ != decision.qa_state;
  applyMeasurementPolicy(decision, config_);
  trace_.push_back(decision);
  previous_state_ = decision.qa_state;
  has_previous_state_ = true;
  return decision;
}

void QAFallbackSupervisor::setYawCorrectionOnLastDecision(double requested_yaw_correction_deg,
                                                          double yaw_correction_applied_deg,
                                                          bool clipped) {
  if (!trace_.empty() && trace_.back().recovery_ramp_active) {
    trace_.back().requested_yaw_correction_deg = requested_yaw_correction_deg;
    trace_.back().yaw_correction_applied_deg = yaw_correction_applied_deg;
    trace_.back().recovery_yaw_correction_cap_deg = recoveryMaxYawCorrectionDeg();
    trace_.back().yaw_correction_clipped = clipped;
  }
}

const std::vector<QADecision>& QAFallbackSupervisor::trace() const {
  return trace_;
}

std::string qaStateName(QAState state) {
  switch (state) {
    case QAState::S0_NORMAL_A1_VALID:
      return "S0_NORMAL_A1_VALID";
    case QAState::S1_A1_DEGRADED_BUT_USABLE:
      return "S1_A1_DEGRADED_BUT_USABLE";
    case QAState::S2_A1_INVALID_GNSS_USABLE:
      return "S2_A1_INVALID_GNSS_USABLE";
    case QAState::S3_GNSS_POSITION_DEGRADED:
      return "S3_GNSS_POSITION_DEGRADED";
    case QAState::S4_DOPPLER_IMU_GO2_BRIDGE:
      return "S4_DOPPLER_IMU_GO2_BRIDGE";
    case QAState::S5_HOLD_OR_DEAD_RECKONING:
      return "S5_HOLD_OR_DEAD_RECKONING";
    case QAState::S6_RECOVERY_FAST_A1_REACQUISITION:
      return "S6_RECOVERY_FAST_A1_REACQUISITION";
  }
  return "UNKNOWN";
}

std::string joinReasons(const std::vector<std::string>& reasons) {
  std::ostringstream out;
  for (std::size_t i = 0; i < reasons.size(); ++i) {
    if (i > 0) {
      out << "|";
    }
    out << reasons[i];
  }
  return out.str();
}

}  // namespace legsa_v23_port_core::quality_aware
