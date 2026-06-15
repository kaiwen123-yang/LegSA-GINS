// LegSA-GINS source-backed port file.
// Port role: PAPER10B2 source-level multi-state quality manager.
// Boundary: solver-visible metadata and innovation only; no trace/final_v23 output tuning.

#pragma once

#include "legsa_v23_port_core/source_aware/measurement_source.hpp"

#include <array>
#include <cstddef>
#include <string>
#include <vector>

namespace legsa_v23_port_core::source_aware {

enum class QualityState : std::size_t {
  kNormal = 0,
  kDownweight = 1,
  kReject = 2,
  kHold = 3,
  kRecovery = 4,
  kFallback = 5,
  kUnknown = 6,
  kPartial = 7,
  kSensorUnavailable = 8,
};

enum class QualityAction : std::size_t {
  kUseOriginalR = 0,
  kInflateR = 1,
  kRejectObservation = 2,
  kHoldSource = 3,
  kRecoveryHysteresis = 4,
  kFallbackPartialSourceFusion = 5,
  kLogOnly = 6,
};

const char* toString(QualityState state);
const char* toString(QualityAction action);

struct QualityStateManagerConfig {
  bool enable_multi_state_qm = false;
  std::string multi_state_qm_mode = "QM00_OFF";
  bool multi_state_qm_trace_enabled = true;
  bool multi_state_qm_trace_only = false;
  bool multi_state_qm_enable_downweight_reject = true;
  bool multi_state_qm_enable_hold_recovery = true;
  bool multi_state_qm_enable_fallback = true;
  double qm_downweight_threshold = 4.0;
  double qm_reject_threshold = 12.0;
  double qm_downweight_R_scale = 2.0;
  double qm_recovery_initial_R_scale = 4.0;
  double qm_hold_R_scale = 10.0;
  double qm_fallback_R_scale = 15.0;
  std::size_t qm_hold_enter_count = 3;
  std::size_t qm_hold_length = 5;
  std::size_t qm_recovery_count = 3;
  std::size_t qm_fallback_enter_count = 2;
  std::size_t qm_fallback_exit_count = 3;
  std::size_t qm_fallback_max_duration = 10;
  double qm_timestamp_gap_hold_sec = 0.25;
  std::size_t qm_invalid_hold_enter_count = 2;
  double qm_source_cap = 25.0;
  double qm_global_cap = 25.0;
  double qm_go2_readiness_low_health = 0.35;
  std::size_t qm_min_stable_epochs = 3;
  bool qm_go2_motion_state_influence = true;
  bool qm_readiness_influence = true;
};

struct QualityStateDecision {
  MeasurementSource source = MeasurementSource::kReceiverPosition;
  QualityState previous_state = QualityState::kUnknown;
  QualityState state = QualityState::kNormal;
  QualityAction action = QualityAction::kUseOriginalR;
  bool state_changed = false;
  bool action_alters_update = false;
  bool accepted = true;
  bool rejected = false;
  double r_scale_multiplier = 1.0;
  std::size_t anomaly_count = 0;
  std::size_t recovery_count = 0;
  std::size_t invalid_count = 0;
  std::size_t hold_remaining = 0;
  std::size_t fallback_remaining = 0;
  double source_health_score = 1.0;
  std::string residual_category = "stable";
  std::vector<std::string> reason_codes;
  bool trace_used_online = false;
  bool final_v23_output_solver_input = false;
  bool legsa_output_solver_input = false;
  bool no_per_case_tuning = true;
};

struct QualityStateRuntimeStats {
  std::size_t trace_row_count = 0;
  std::size_t state_transition_count = 0;
  std::array<std::size_t, kMeasurementSourceCount> normal_count_by_source{};
  std::array<std::size_t, kMeasurementSourceCount> downweight_count_by_source{};
  std::array<std::size_t, kMeasurementSourceCount> reject_count_by_source{};
  std::array<std::size_t, kMeasurementSourceCount> hold_count_by_source{};
  std::array<std::size_t, kMeasurementSourceCount> recovery_count_by_source{};
  std::array<std::size_t, kMeasurementSourceCount> fallback_count_by_source{};
  std::array<std::size_t, kMeasurementSourceCount> action_count_by_source{};
};

class QualityStateManager {
 public:
  explicit QualityStateManager(QualityStateManagerConfig config = {});

  bool enabled() const;
  bool traceEnabled() const;
  const QualityStateManagerConfig& config() const;
  QualityStateDecision evaluate(const SourceMetadata& metadata,
                                const ObservationInnovation& innovation,
                                const SourceWeightResult& weight_result);

 private:
  struct SourceMemory {
    QualityState state = QualityState::kUnknown;
    std::size_t anomaly_count = 0;
    std::size_t recovery_count = 0;
    std::size_t invalid_count = 0;
    std::size_t hold_remaining = 0;
    std::size_t fallback_remaining = 0;
  };

  void applyModeOverrides();
  QualityStateDecision buildDecision(const SourceMetadata& metadata,
                                     const ObservationInnovation& innovation,
                                     const SourceWeightResult& weight_result,
                                     SourceMemory& memory);

  QualityStateManagerConfig config_;
  std::array<SourceMemory, kMeasurementSourceCount> memories_{};
};

}  // namespace legsa_v23_port_core::source_aware
