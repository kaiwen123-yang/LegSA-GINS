#pragma once
#include "legsa_v23_port_core/types.hpp"
#include <string>
#include <vector>

namespace legsa_v23_port_core {
struct AttitudeCloneConfig {
  std::string mode = "off";
  std::string events_path;
  std::string position_source_id;
  std::string position_gnss_input_status;
  std::string covariance_source_id;
  std::string covariance_assumption;
  std::string frame_source_id;
  std::string availability_policy;
  Matrix3 foot_frd_to_engine_body{};  // No hidden identity default.
};
struct FootPairEvent {
  double time = 0.0, available_time = 0.0, source_time = 0.0;
  std::string type, clone_id, endpoint_id, foot_i, foot_j, episode_i, episode_j, reason;
  Vec3 direction_body_frd{};
  Matrix difference_covariance;  // Complete 6x6, END only, [d0,d1] m^2.
};
struct AttitudeCloneCounts {
  std::size_t source_rows=0, event_rows=0, starts=0, ends=0, retires=0;
  std::size_t pair_updates=0, pair_skips=0, null_ends=0, rejected_events=0;
  std::size_t ordinary_joint_updates=0, full_resets=0, late_initial_events=0;
  std::size_t innovation_rejects=0, unconsumed_terminal=0, unconsumed_outside_imu=0;
};
void validateAttitudeCloneConfig(const AttitudeCloneConfig& config, const std::string& runtime_contract);
std::vector<FootPairEvent> readFootPairEvents(const AttitudeCloneConfig& config);
}  // namespace legsa_v23_port_core
