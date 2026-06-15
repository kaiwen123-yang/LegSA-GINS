// LegSA-GINS source-backed port file.
// Port role: PAPER10B2 source-level multi-state quality manager.
// Boundary: no trace/final_v23/LegSA output as solver input.

#include "legsa_v23_port_core/source_aware/quality_state_manager.hpp"

#include <algorithm>
#include <cmath>
#include <utility>

namespace legsa_v23_port_core::source_aware {
namespace {

bool isGo2Source(MeasurementSource source) {
  return source == MeasurementSource::kGo2AttitudeRollPitch ||
         source == MeasurementSource::kGo2HorizontalVelocity;
}

bool isPrimaryReceiverSource(MeasurementSource source) {
  return source == MeasurementSource::kReceiverPosition ||
         source == MeasurementSource::kReceiverVelocity;
}

bool providerUnavailable(const SourceMetadata& metadata) {
  return metadata.provider_status == "unavailable" ||
         metadata.provider_status == "missing" ||
         metadata.provider_status == "invalid" ||
         metadata.quality_flag == "invalid";
}

double clampScale(double value, double cap) {
  return std::max(1.0, std::min(std::max(1.0, cap), value));
}

void addReason(std::vector<std::string>& reasons, const std::string& reason) {
  if (std::find(reasons.begin(), reasons.end(), reason) == reasons.end()) {
    reasons.push_back(reason);
  }
}

}  // namespace

const char* toString(QualityState state) {
  switch (state) {
    case QualityState::kNormal:
      return "NORMAL";
    case QualityState::kDownweight:
      return "DOWNWEIGHT";
    case QualityState::kReject:
      return "REJECT";
    case QualityState::kHold:
      return "HOLD";
    case QualityState::kRecovery:
      return "RECOVERY";
    case QualityState::kFallback:
      return "FALLBACK";
    case QualityState::kUnknown:
      return "UNKNOWN";
    case QualityState::kPartial:
      return "PARTIAL";
    case QualityState::kSensorUnavailable:
      return "SENSOR_UNAVAILABLE";
  }
  return "UNKNOWN";
}

const char* toString(QualityAction action) {
  switch (action) {
    case QualityAction::kUseOriginalR:
      return "use_original_R";
    case QualityAction::kInflateR:
      return "inflate_R";
    case QualityAction::kRejectObservation:
      return "reject_current_observation";
    case QualityAction::kHoldSource:
      return "hold_source_finite_window";
    case QualityAction::kRecoveryHysteresis:
      return "recovery_hysteresis";
    case QualityAction::kFallbackPartialSourceFusion:
      return "fallback_partial_source_fusion";
    case QualityAction::kLogOnly:
      return "log_state_only";
  }
  return "log_state_only";
}

QualityStateManager::QualityStateManager(QualityStateManagerConfig config)
    : config_(std::move(config)) {
  applyModeOverrides();
}

bool QualityStateManager::enabled() const {
  return config_.enable_multi_state_qm && config_.multi_state_qm_mode != "QM00_OFF";
}

bool QualityStateManager::traceEnabled() const {
  return enabled() && config_.multi_state_qm_trace_enabled;
}

const QualityStateManagerConfig& QualityStateManager::config() const {
  return config_;
}

void QualityStateManager::applyModeOverrides() {
  if (config_.multi_state_qm_mode == "QM00_OFF") {
    config_.enable_multi_state_qm = false;
    config_.multi_state_qm_trace_only = false;
    config_.multi_state_qm_enable_downweight_reject = false;
    config_.multi_state_qm_enable_hold_recovery = false;
    config_.multi_state_qm_enable_fallback = false;
  } else if (config_.multi_state_qm_mode == "QM01_STATE_TRACE_ONLY") {
    config_.multi_state_qm_trace_only = true;
    config_.multi_state_qm_enable_downweight_reject = true;
    config_.multi_state_qm_enable_hold_recovery = true;
    config_.multi_state_qm_enable_fallback = true;
  } else if (config_.multi_state_qm_mode == "QM02_DOWNWEIGHT_REJECT") {
    config_.multi_state_qm_trace_only = false;
    config_.multi_state_qm_enable_downweight_reject = true;
    config_.multi_state_qm_enable_hold_recovery = false;
    config_.multi_state_qm_enable_fallback = false;
  } else if (config_.multi_state_qm_mode == "QM03_HOLD_RECOVERY") {
    config_.multi_state_qm_trace_only = false;
    config_.multi_state_qm_enable_downweight_reject = true;
    config_.multi_state_qm_enable_hold_recovery = true;
    config_.multi_state_qm_enable_fallback = false;
  } else if (config_.multi_state_qm_mode == "QM04_FULL" ||
             config_.multi_state_qm_mode == "QM05_CONSERVATIVE_FULL") {
    config_.multi_state_qm_trace_only = false;
    config_.multi_state_qm_enable_downweight_reject = true;
    config_.multi_state_qm_enable_hold_recovery = true;
    config_.multi_state_qm_enable_fallback = true;
  }
}

QualityStateDecision QualityStateManager::evaluate(const SourceMetadata& metadata,
                                                   const ObservationInnovation& innovation,
                                                   const SourceWeightResult& weight_result) {
  if (!enabled()) {
    QualityStateDecision decision;
    decision.source = metadata.source;
    decision.state = QualityState::kNormal;
    decision.previous_state = QualityState::kUnknown;
    decision.action = QualityAction::kUseOriginalR;
    decision.accepted = !weight_result.rejected;
    decision.rejected = weight_result.rejected;
    return decision;
  }
  SourceMemory& memory = memories_[sourceIndex(metadata.source)];
  return buildDecision(metadata, innovation, weight_result, memory);
}

QualityStateDecision QualityStateManager::buildDecision(const SourceMetadata& metadata,
                                                        const ObservationInnovation& innovation,
                                                        const SourceWeightResult& weight_result,
                                                        SourceMemory& memory) {
  QualityStateDecision decision;
  decision.source = metadata.source;
  decision.previous_state = memory.state;
  decision.accepted = weight_result.accepted;
  decision.rejected = weight_result.rejected;
  decision.reason_codes = weight_result.reason_codes;
  decision.source_health_score = 1.0;

  const double normalized = std::max(std::fabs(innovation.normalized_innovation),
                                     std::fabs(weight_result.normalized_innovation));
  const bool unavailable = !metadata.valid || providerUnavailable(metadata) ||
                           (isGo2Source(metadata.source) && config_.qm_readiness_influence &&
                            metadata.go2_readiness_metadata_available && !metadata.go2_readiness_flag);
  const bool timestamp_gap = std::fabs(metadata.time_diff_sec) > config_.qm_timestamp_gap_hold_sec;
  const bool readiness_low = isGo2Source(metadata.source) && config_.qm_readiness_influence &&
                             metadata.go2_readiness_metadata_available &&
                             (metadata.go2_readiness_low ||
                              metadata.go2_readiness_score < config_.qm_go2_readiness_low_health);
  const bool rough_motion = isGo2Source(metadata.source) && config_.qm_go2_motion_state_influence &&
                            metadata.go2_readiness_metadata_available &&
                            (metadata.go2_impact_or_rough ||
                             metadata.go2_motion_state == "impact_or_rough");
  const bool in_place_turn = isGo2Source(metadata.source) && config_.qm_go2_motion_state_influence &&
                             metadata.go2_readiness_metadata_available && metadata.go2_in_place_turn;
  const bool explicit_unavailable = unavailable || timestamp_gap || weight_result.rejected;
  const bool go2_degraded = readiness_low || rough_motion || in_place_turn;
  const bool extreme_innovation = normalized >= config_.qm_reject_threshold;
  const bool innovation_can_reject = !isPrimaryReceiverSource(metadata.source);
  const bool strong_anomaly = explicit_unavailable ||
                              (innovation_can_reject && extreme_innovation) ||
                              (isGo2Source(metadata.source) && go2_degraded);
  const bool moderate_anomaly = strong_anomaly ||
                                normalized >= config_.qm_downweight_threshold ||
                                weight_result.combined_R_scale > 1.25 ||
                                go2_degraded;
  const bool stable = !strong_anomaly &&
                      normalized < config_.qm_downweight_threshold &&
                      weight_result.combined_R_scale <= 1.25 &&
                      !go2_degraded;

  if (unavailable) {
    addReason(decision.reason_codes, "provider_status_or_validity_unavailable");
    decision.source_health_score = std::min(decision.source_health_score, 0.0);
  }
  if (timestamp_gap) {
    addReason(decision.reason_codes, "timestamp_gap_hold_candidate");
    decision.source_health_score = std::min(decision.source_health_score, 0.25);
  }
  if (readiness_low) {
    addReason(decision.reason_codes, "go2_readiness_low");
    decision.source_health_score = std::min(decision.source_health_score, metadata.go2_readiness_score);
  }
  if (rough_motion) {
    addReason(decision.reason_codes, "go2_impact_or_rough");
    decision.source_health_score = std::min(decision.source_health_score, 0.35);
  }
  if (in_place_turn) {
    addReason(decision.reason_codes, "go2_in_place_turn");
    decision.source_health_score = std::min(decision.source_health_score, 0.65);
  }
  if (normalized >= config_.qm_reject_threshold) {
    addReason(decision.reason_codes, "normalized_innovation_reject");
    decision.source_health_score = std::min(decision.source_health_score, 0.25);
  } else if (normalized >= config_.qm_downweight_threshold) {
    addReason(decision.reason_codes, "normalized_innovation_downweight");
    decision.source_health_score = std::min(decision.source_health_score, 0.6);
  }

  if (strong_anomaly) {
    ++memory.anomaly_count;
    memory.recovery_count = 0;
  } else if (moderate_anomaly) {
    memory.recovery_count = 0;
  } else if (stable) {
    ++memory.recovery_count;
    if (memory.anomaly_count > 0) {
      --memory.anomaly_count;
    }
  }
  if (unavailable) {
    ++memory.invalid_count;
  } else if (stable && memory.invalid_count > 0) {
    --memory.invalid_count;
  }

  if (memory.hold_remaining > 0 && config_.multi_state_qm_enable_hold_recovery) {
    if (stable && memory.recovery_count >= std::max<std::size_t>(1, config_.qm_recovery_count)) {
      memory.state = QualityState::kRecovery;
      decision.state = QualityState::kRecovery;
      decision.action = QualityAction::kRecoveryHysteresis;
      decision.r_scale_multiplier = clampScale(config_.qm_recovery_initial_R_scale, config_.qm_global_cap);
      decision.accepted = true;
      decision.rejected = false;
      --memory.hold_remaining;
    } else {
      memory.state = QualityState::kHold;
      decision.state = QualityState::kHold;
      decision.action = QualityAction::kHoldSource;
      decision.accepted = false;
      decision.rejected = true;
      decision.r_scale_multiplier = clampScale(config_.qm_hold_R_scale, config_.qm_global_cap);
      --memory.hold_remaining;
    }
  } else if (memory.fallback_remaining > 0 && config_.multi_state_qm_enable_fallback) {
    if (stable && memory.recovery_count >= std::max<std::size_t>(1, config_.qm_fallback_exit_count)) {
      memory.fallback_remaining = 0;
      memory.state = QualityState::kRecovery;
      decision.state = QualityState::kRecovery;
      decision.action = QualityAction::kRecoveryHysteresis;
      decision.accepted = true;
      decision.rejected = false;
      decision.r_scale_multiplier = clampScale(config_.qm_recovery_initial_R_scale, config_.qm_global_cap);
    } else {
      memory.state = QualityState::kFallback;
      decision.state = QualityState::kFallback;
      decision.action = QualityAction::kFallbackPartialSourceFusion;
      decision.accepted = false;
      decision.rejected = true;
      decision.r_scale_multiplier = clampScale(config_.qm_fallback_R_scale, config_.qm_global_cap);
      --memory.fallback_remaining;
    }
  } else if (config_.multi_state_qm_enable_fallback &&
             (memory.invalid_count >= std::max<std::size_t>(1, config_.qm_fallback_enter_count) ||
              (unavailable && memory.anomaly_count >= std::max<std::size_t>(1, config_.qm_fallback_enter_count)))) {
    memory.fallback_remaining = std::max<std::size_t>(1, config_.qm_fallback_max_duration);
    memory.state = QualityState::kFallback;
    decision.state = QualityState::kFallback;
    decision.action = QualityAction::kFallbackPartialSourceFusion;
    decision.accepted = false;
    decision.rejected = true;
    decision.r_scale_multiplier = clampScale(config_.qm_fallback_R_scale, config_.qm_global_cap);
  } else if (config_.multi_state_qm_enable_hold_recovery &&
             strong_anomaly &&
             memory.anomaly_count >= std::max<std::size_t>(1, config_.qm_hold_enter_count)) {
    memory.hold_remaining = std::max<std::size_t>(1, config_.qm_hold_length);
    memory.state = QualityState::kHold;
    decision.state = QualityState::kHold;
    decision.action = QualityAction::kHoldSource;
    decision.accepted = false;
    decision.rejected = true;
    decision.r_scale_multiplier = clampScale(config_.qm_hold_R_scale, config_.qm_global_cap);
  } else if (config_.multi_state_qm_enable_downweight_reject && strong_anomaly) {
    memory.state = QualityState::kReject;
    decision.state = QualityState::kReject;
    decision.action = QualityAction::kRejectObservation;
    decision.accepted = false;
    decision.rejected = true;
    decision.r_scale_multiplier = clampScale(config_.qm_fallback_R_scale, config_.qm_global_cap);
  } else if (config_.multi_state_qm_enable_downweight_reject && moderate_anomaly) {
    memory.state = QualityState::kDownweight;
    decision.state = QualityState::kDownweight;
    decision.action = QualityAction::kInflateR;
    decision.accepted = true;
    decision.rejected = false;
    decision.r_scale_multiplier = clampScale(config_.qm_downweight_R_scale, config_.qm_global_cap);
  } else if (memory.recovery_count > 0 && memory.recovery_count < config_.qm_min_stable_epochs &&
             decision.previous_state != QualityState::kUnknown &&
             decision.previous_state != QualityState::kNormal) {
    memory.state = QualityState::kRecovery;
    decision.state = QualityState::kRecovery;
    decision.action = QualityAction::kRecoveryHysteresis;
    decision.accepted = true;
    decision.rejected = false;
    decision.r_scale_multiplier = clampScale(config_.qm_recovery_initial_R_scale, config_.qm_global_cap);
  } else {
    memory.state = QualityState::kNormal;
    decision.state = QualityState::kNormal;
    decision.action = QualityAction::kUseOriginalR;
    decision.accepted = true;
    decision.rejected = false;
    decision.r_scale_multiplier = 1.0;
  }

  if (config_.multi_state_qm_trace_only) {
    decision.action = QualityAction::kLogOnly;
    decision.action_alters_update = false;
    decision.accepted = weight_result.accepted;
    decision.rejected = weight_result.rejected;
    decision.r_scale_multiplier = 1.0;
  } else {
    decision.action_alters_update = decision.action != QualityAction::kUseOriginalR;
  }

  if (decision.state == QualityState::kNormal) {
    decision.residual_category = "stable";
  } else if (decision.state == QualityState::kDownweight || decision.state == QualityState::kRecovery) {
    decision.residual_category = "moderate";
  } else {
    decision.residual_category = "strong_or_unavailable";
  }

  decision.state_changed = decision.previous_state != decision.state;
  decision.anomaly_count = memory.anomaly_count;
  decision.recovery_count = memory.recovery_count;
  decision.invalid_count = memory.invalid_count;
  decision.hold_remaining = memory.hold_remaining;
  decision.fallback_remaining = memory.fallback_remaining;
  decision.trace_used_online = false;
  decision.final_v23_output_solver_input = false;
  decision.legsa_output_solver_input = false;
  decision.no_per_case_tuning = true;
  return decision;
}

}  // namespace legsa_v23_port_core::source_aware
