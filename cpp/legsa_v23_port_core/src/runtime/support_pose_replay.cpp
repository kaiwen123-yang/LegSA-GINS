#include "legsa_v23_port_core/runtime/support_pose_replay.hpp"
#include "legsa_v23_port_core/common/earth.hpp"

#include <algorithm>
#include <chrono>
#include <cmath>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <limits>

namespace legsa_v23_port_core {
namespace {
double normDifference(const Vec3& a,const Vec3& b) {
  double sum=0; for(std::size_t i=0;i<3;++i) sum+=(a[i]-b[i])*(a[i]-b[i]);
  return std::sqrt(sum);
}
std::string csv(const std::string& s) {
  std::string out="\""; for(char c:s) {out+=c;if(c=='"') out+=c;} return out+"\"";
}
}
SupportPoseReplay::SupportPoseReplay(bool enabled,const std::vector<SupportPoseEvent>& events):enabled_(enabled) {
  for(const auto& event:events) if(event.type=="END") end_times_[event.clone_id]=event.time;
}

void SupportPoseReplay::checkpoint(const GIEngine& engine,double time,std::size_t sequence) {
  const auto begin=std::chrono::steady_clock::now();
  auto snapshot=std::make_unique<GIEngine>(engine);
  const double seconds=std::chrono::duration<double>(std::chrono::steady_clock::now()-begin).count();
  copy_seconds_+=seconds; max_copy_seconds_=std::max(max_copy_seconds_,seconds);
  checkpoints_.push_back({time,sequence,std::move(snapshot)});
  ++checkpoints_created_;
  peak_checkpoints_=std::max(peak_checkpoints_,checkpoints_.size());
}

void SupportPoseReplay::prune(double frontier) {
  while(!checkpoints_.empty() && checkpoints_.front().time < frontier-kHistorySeconds)
    checkpoints_.pop_front();
  if(checkpoints_.empty()) {frames_.clear(); return;}
  while(!frames_.empty() && frames_.front().sequence < checkpoints_.front().next_sequence)
    frames_.pop_front();
}

void SupportPoseReplay::beforeInterval(const GIEngine& engine,double previous,const ImuData& imu) {
  if(!enabled_) return;
  prune(previous);
  if(engine.hasSupportPoseStartBetween(previous,imu.time))
    checkpoint(engine,previous,next_sequence_);
}

void SupportPoseReplay::afterInterval(GIEngine& engine,double previous,const ImuData& imu,
                                      const std::vector<GnssData>& events) {
  if(!enabled_) return;
  frames_.push_back({next_sequence_++,previous,imu,events});
  peak_frames_=std::max(peak_frames_,frames_.size());
  // A corrected trajectory may accept a different factor before its already
  // observed REVOKE. Resolve that notice at this same output frontier too.
  for(;;) {
  // Copy notices before assigning the engine; a reference into it would expire.
  const auto notices=engine.pendingSupportRevocations();
  std::vector<std::size_t> recoverable_rows;
  std::size_t selected_sequence=std::numeric_limits<std::size_t>::max();
  for(const auto& notice:notices) {
    if(!seen_notices_.insert({notice.time,notice.clone_id}).second) continue;
    revoked_ids_.insert(notice.clone_id);
    Correction row;
    row.notice_time=notice.time; row.frontier_time=imu.time; row.clone_id=notice.clone_id;
    row.factor_start_time=engine.supportPoseFactorStartTime(notice.clone_id);
    row.accepted_end_time=end_times_.at(notice.clone_id);
    row.accepted_before=engine.supportPoseCounts().accepted;row.accepted_after=row.accepted_before;
    row.updates_before=engine.updateCount();row.updates_after=row.updates_before;
    row.yaw_before=engine.yawUpdateCount();row.yaw_after=row.yaw_before;
    const Checkpoint* selected=nullptr;
    for(const auto& saved:checkpoints_)
      if(saved.time>=imu.time-kHistorySeconds && saved.time<=row.factor_start_time &&
         saved.next_sequence<=frames_.back().sequence)
        selected=&saved;
    if(selected && !frames_.empty() && frames_.front().sequence<=selected->next_sequence) {
      row.checkpoint_time=selected->time;
      row.status="RESTORED_CURRENT_STATE";
      selected_sequence=std::min(selected_sequence,selected->next_sequence);
      recoverable_rows.push_back(corrections_.size());
    } else {
      row.status="EXPIRED_NO_POSTERIOR_RESTORATION";
      ++expired_factors_;
    }
    corrections_.push_back(std::move(row));
  }
  engine.setRevokedSupportFactorIds(revoked_ids_);
  if(recoverable_rows.empty()) break;
  {
    const auto begin=std::chrono::steady_clock::now();
    const NavState before=engine.getNavState();
    const std::vector<double> covariance_before=engine.getCovariance();
    const Checkpoint* selected=nullptr;
    for(const auto& saved:checkpoints_)
      if(saved.next_sequence==selected_sequence) {selected=&saved;break;}
    const double checkpoint_time=selected->time;
    engine=*selected->engine;
    engine.setRevokedSupportFactorIds(revoked_ids_);
    // Later snapshots contain the withdrawn posterior. Rebuild them from the
    // corrected trajectory; the chosen pre-factor checkpoint itself stays valid.
    while(!checkpoints_.empty() && checkpoints_.back().next_sequence>selected_sequence)
      checkpoints_.pop_back();
    std::size_t frame_count=0,event_count=0;
    for(const auto& frame:frames_) {
      if(frame.sequence<selected_sequence) continue;
      if(frame.sequence>selected_sequence &&
         engine.hasSupportPoseStartBetween(frame.previous_time,frame.imu.time))
        checkpoint(engine,frame.previous_time,frame.sequence);
      engine.addImuData(frame.imu);
      engine.newImuProcessWithEvents(frame.events);
      ++frame_count; event_count+=frame.events.size();
    }
    const NavState after=engine.getNavState();
    const auto& covariance_after=engine.getCovariance();
    double rotation_change=0,covariance_change=0;
    for(std::size_t i=0;i<3;++i) for(std::size_t j=0;j<3;++j)
      rotation_change+=(after.cbn[i][j]-before.cbn[i][j])*(after.cbn[i][j]-before.cbn[i][j]);
    for(std::size_t i=0;i<covariance_after.size();++i)
      covariance_change+=(covariance_after[i]-covariance_before[i])*(covariance_after[i]-covariance_before[i]);
    for(const auto index:recoverable_rows) {
      auto& row=corrections_[index];
      row.checkpoint_time=checkpoint_time;row.replayed_frames=frame_count;
      row.accepted_after=engine.supportPoseCounts().accepted;row.updates_after=engine.updateCount();
      row.yaw_after=engine.yawUpdateCount();
      row.replayed_gnss_events=event_count;
      row.position_change_m=normDifference(Earth::blh2ecef(after.pos_blh_rad_m),
                                           Earth::blh2ecef(before.pos_blh_rad_m));
      row.velocity_change_mps=normDifference(after.vel_ned_mps,before.vel_ned_mps);
      row.rotation_matrix_change=std::sqrt(rotation_change);
      row.covariance_change=std::sqrt(covariance_change);
    }
    ++replay_batches_;restored_factors_+=recoverable_rows.size();
    replayed_frames_+=frame_count;replayed_gnss_events_+=event_count;
    replay_seconds_+=std::chrono::duration<double>(std::chrono::steady_clock::now()-begin).count();
  }
  }
  prune(imu.time);
}

void SupportPoseReplay::writeDiagnostics(const std::string& output_dir) const {
  if(!enabled_) return;
  std::filesystem::create_directories(output_dir);
  std::ofstream out(std::filesystem::path(output_dir)/"SUPPORT_POSE_REPLAY_SUMMARY.json");
  out<<std::setprecision(17)
     <<"{\n  \"history_seconds\": "<<kHistorySeconds
     <<",\n  \"checkpoint_policy\": \"deep_copy_GIEngine_before_START_IMU_interval\""
     <<",\n  \"checkpoints_created\": "<<checkpoints_created_
     <<",\n  \"peak_retained_checkpoints\": "<<peak_checkpoints_
     <<",\n  \"peak_cached_IMU_intervals\": "<<peak_frames_
     <<",\n  \"checkpoint_copy_seconds\": "<<copy_seconds_
     <<",\n  \"max_checkpoint_copy_seconds\": "<<max_copy_seconds_
     <<",\n  \"replay_batches\": "<<replay_batches_
     <<",\n  \"replayed_IMU_intervals\": "<<replayed_frames_
     <<",\n  \"replayed_GNSS_carrier_events\": "<<replayed_gnss_events_
     <<",\n  \"restored_factors\": "<<restored_factors_
     <<",\n  \"expired_factors_without_restoration\": "<<expired_factors_
     <<",\n  \"replay_seconds\": "<<replay_seconds_
     <<",\n  \"past_NAV_rows_rewritten\": false"
     <<",\n  \"independent_carrier_inputs_preserved\": true"
     <<",\n  \"SDK_restored_in_revoked_interval\": false"
     <<",\n  \"RETIRE_triggers_replay\": false"
     <<",\n  \"posterior_counter_semantics\": \"counts_on_corrected_engine_trajectory_not_total_execution_work\""
     <<",\n  \"unrepaired_expired_dependency_present\": "<<(expired_factors_?"true":"false")<<"\n}\n";
  std::ofstream trace(std::filesystem::path(output_dir)/"SUPPORT_POSE_REPLAY_EVENTS.csv");
  trace<<std::setprecision(17)
       <<"notice_time,frontier_time,clone_id,factor_start_time,original_accepted_END_time,checkpoint_time,status,support_accepted_before,support_accepted_after,measurement_updates_before,measurement_updates_after,yaw_updates_before,yaw_updates_after,replayed_IMU_intervals,replayed_GNSS_carrier_events,current_position_change_m,current_velocity_change_mps,current_rotation_matrix_change,current_covariance_change\n";
  for(const auto& row:corrections_)
    trace<<row.notice_time<<','<<row.frontier_time<<','<<csv(row.clone_id)<<','
         <<row.factor_start_time<<','<<row.accepted_end_time<<','<<row.checkpoint_time<<','<<row.status<<','
         <<row.accepted_before<<','<<row.accepted_after<<','<<row.updates_before<<','<<row.updates_after<<','
         <<row.yaw_before<<','<<row.yaw_after<<','
         <<row.replayed_frames<<','<<row.replayed_gnss_events<<','<<row.position_change_m<<','
         <<row.velocity_change_mps<<','<<row.rotation_matrix_change<<','<<row.covariance_change<<'\n';
}
}  // namespace legsa_v23_port_core
