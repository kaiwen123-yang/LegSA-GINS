#pragma once
#include "legsa_v23_port_core/types.hpp"
#include <string>
#include <vector>
namespace legsa_v23_port_core {
struct SupportPoseConfig {
  std::string mode="off", events_path;
  std::string observed_axes="body0_xy";
  double point_sigma_m=.01;
  Matrix3 foot_frd_to_engine_body{};
  Vec3 imu_lever_body_frd{};
  bool horizontalOnly() const {return observed_axes=="body0_xy";}
  std::size_t measurementDimension() const {return horizontalOnly()?4:6;}
  double nisThreshold() const {return horizontalOnly()?18.4668269529:22.457744484825323;}
};
struct SupportPoseEvent {
  double time=0, available_time=0, source_time=0, point_sigma_m=.01;
  std::string type, clone_id, endpoint_id, foot_i, foot_j, episode_i, episode_j, reason;
  std::vector<Vec3> positions_body_frd;
};
struct SupportPoseRevocation {double time=0; std::string clone_id;};
struct SupportPoseCounts {
  std::size_t source_rows=0,event_rows=0,starts=0,ends=0,retires=0,revocations=0;
  std::size_t accepted=0,rejected=0,null_ends=0,sdk_ticks_suppressed=0;
  std::size_t ordinary_joint_updates=0,full_resets=0,unconsumed=0;
};
void validateSupportPoseConfig(const SupportPoseConfig&,const std::string& runtime_contract);
std::vector<SupportPoseEvent> readSupportPoseEvents(const SupportPoseConfig&);
}
