#pragma once

#include "legsa_v23_port_core/kf_gins/gi_engine.hpp"

#include <deque>
#include <memory>
#include <map>
#include <set>
#include <string>
#include <utility>
#include <vector>

namespace legsa_v23_port_core {

// A bounded correction of the live common state. Previously issued NAV rows stay
// immutable; raw events are replayed through GIEngine, never through the writer.
class SupportPoseReplay {
 public:
  SupportPoseReplay(bool enabled, const std::vector<SupportPoseEvent>& events);
  void beforeInterval(const GIEngine& engine, double previous_imu_time, const ImuData& imu);
  void afterInterval(GIEngine& engine, double previous_imu_time, const ImuData& imu,
                     const std::vector<GnssData>& events);
  void writeDiagnostics(const std::string& output_dir) const;
  static constexpr double kHistorySeconds = 0.5;

 private:
  struct Frame {
    std::size_t sequence;
    double previous_time;
    ImuData imu;
    std::vector<GnssData> events;
  };
  struct Checkpoint {
    double time;
    std::size_t next_sequence;
    std::unique_ptr<GIEngine> engine;
  };
  struct Correction {
    double notice_time=0, frontier_time=0, factor_start_time=0, accepted_end_time=0, checkpoint_time=0;
    std::size_t accepted_before=0, accepted_after=0, updates_before=0, updates_after=0;
    std::size_t yaw_before=0, yaw_after=0;
    std::string clone_id, status;
    std::size_t replayed_frames=0, replayed_gnss_events=0;
    double position_change_m=0, velocity_change_mps=0, rotation_matrix_change=0;
    double covariance_change=0;
  };
  void checkpoint(const GIEngine& engine, double time, std::size_t next_sequence);
  void prune(double frontier_time);

  bool enabled_;
  std::size_t next_sequence_=0;
  std::deque<Frame> frames_;
  std::deque<Checkpoint> checkpoints_;
  std::set<std::string> revoked_ids_;
  std::map<std::string,double> end_times_;
  std::set<std::pair<double,std::string>> seen_notices_;
  std::vector<Correction> corrections_;
  std::size_t checkpoints_created_=0, peak_checkpoints_=0, peak_frames_=0;
  std::size_t replay_batches_=0, replayed_frames_=0, replayed_gnss_events_=0;
  std::size_t restored_factors_=0, expired_factors_=0;
  double copy_seconds_=0, max_copy_seconds_=0, replay_seconds_=0;
};

}  // namespace legsa_v23_port_core
