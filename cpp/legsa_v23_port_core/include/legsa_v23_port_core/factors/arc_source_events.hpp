#pragma once
#include "legsa_v23_port_core/types.hpp"
#include <limits>
#include <string>
#include <vector>

namespace legsa_v23_port_core {
// Metadata only: phase z/G/Q, ambiguities, reference and availability proxies are forbidden.
struct ArcCloneConfig {
  std::string mode = "off";
  std::string events_path, events_sha256, manifest_sha256;
  std::string source_time_scale_id, time_mapping_source_id, availability_policy;
};
struct ArcSourceEvent {
  std::string sequence_id, block_id, endpoint_id, role;
  double source_time=0.0, replay_time=0.0;
  std::string source_time_bits_hex;
  double actual_available_time=std::numeric_limits<double>::quiet_NaN();
  std::string availability_mode="SOURCE_TIME_REPLAY_ASSUMPTION";
  std::size_t epoch_index=0;
  std::string endpoint_model_fingerprint;
};
struct ArcCloneCounts {
  std::size_t source_rows=0, source_blocks=0, event_rows=0, starts=0, ends=0, retires=0;
  std::size_t covered_blocks=0, uncovered_initial=0, uncovered_terminal=0;
  std::size_t ordinary_updates=0, ordinary_joint_updates=0, full_resets=0, imu_segments=0;
  std::size_t phase_updates=0;  // Always zero: this mode has no phase likelihood.
};
struct ArcLifecycleEvent {
  ArcSourceEvent start, end;
  bool has_end=false;
  std::string status="PENDING", clone_owner="NONE";
  bool clone_created=false;
  std::string dispatch_phase="NOT_DISPATCHED";
  std::string start_dispatch_phase="NOT_DISPATCHED", end_dispatch_phase="NOT_DISPATCHED";
  double start_state_time=std::numeric_limits<double>::quiet_NaN();
  double end_state_time=std::numeric_limits<double>::quiet_NaN();
  std::size_t start_update_ordinal=0, end_update_ordinal=0;
  std::size_t start_reset_ordinal=0, end_reset_ordinal=0;
  std::size_t start_dispatch_ordinal=0, end_dispatch_ordinal=0;
  std::size_t start_state_sample_count=0, end_state_sample_count=0;
};
struct ArcConditioningEvent {
  std::size_t ordinal=0, update_ordinal=0, reset_ordinal=0;
  double state_time=0.0;
  std::string kind, source_tag, clone_owner, block_id;
  std::string provider_measurement_identity="UNKNOWN";
};
struct ArcImuSegment {
  std::size_t ordinal=0;
  double start_time=0.0, end_time=0.0, measured_dt=0.0;
  Vec3 dtheta{}, dvel{};  // Actual pre-compensation input to insPropagation.
  bool input_compensated=false;
};
struct ArcJointPrior {
  ArcSourceEvent start, end;
  double start_state_time=0.0, end_state_time=0.0;
  std::string conditioning_information_id;
  std::size_t start_update_ordinal=0, end_update_ordinal=0;
  std::size_t start_reset_ordinal=0, end_reset_ordinal=0;
  std::size_t conditioning_ordinal=0;
  Matrix start_P21, J0, P24, J1, B6, P6;
  std::vector<double> dx24;
  Matrix3 start_C0{}, clone_C0_given_end{}, current_cbn{}, current_C1{};
  Vec3 start_blh{}, current_blh{};
};
void validateArcCloneConfig(const ArcCloneConfig& config, const std::string& runtime_contract);
void validateArcSourceEvents(const std::vector<ArcSourceEvent>& events);
std::vector<ArcSourceEvent> readArcSourceEvents(const ArcCloneConfig& config);
std::string arcSourceTimeBits(double value);
}  // namespace legsa_v23_port_core
