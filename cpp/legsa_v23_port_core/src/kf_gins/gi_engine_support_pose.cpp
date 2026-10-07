#include "legsa_v23_port_core/kf_gins/gi_engine.hpp"
#include "legsa_v23_port_core/common/earth.hpp"
#include "legsa_v23_port_core/common/rotation.hpp"
#include <algorithm>
#include <cmath>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <limits>
#include <stdexcept>
namespace legsa_v23_port_core {
pose_clone::Gaussian GIEngine::supportPoseJointState() const {
  const std::size_t base=supportPoseCurrentSize(),n=base+(support_pose_active_?6:0);
  if(n==21) return {Cov_,dx_};
  Matrix p(n,n);std::vector<double> mean(n);
  for(std::size_t i=0;i<21;++i) {
    mean[i]=dx_[i];
    for(std::size_t j=0;j<21;++j) p(i,j)=Cov_(i,j);
    if(sdk_discrepancy_initialized_) for(std::size_t j=0;j<2;++j)
      p(i,21+j)=p(21+j,i)=sdk_discrepancy_cross_(i,j);
    if(support_pose_active_) for(std::size_t j=0;j<6;++j)
      p(i,base+j)=p(base+j,i)=support_pose_cross_(i,j);
  }
  if(sdk_discrepancy_initialized_) for(std::size_t i=0;i<2;++i) {
    mean[21+i]=sdk_discrepancy_error_[i];
    for(std::size_t j=0;j<2;++j) p(21+i,21+j)=sdk_discrepancy_cov_(i,j);
    if(support_pose_active_) for(std::size_t j=0;j<6;++j)
      p(21+i,base+j)=p(base+j,21+i)=sdk_discrepancy_clone_cross_(i,j);
  }
  if(support_pose_active_) for(std::size_t i=0;i<6;++i) {
    mean[base+i]=support_pose_error_[i];
    for(std::size_t j=0;j<6;++j) p(base+i,base+j)=support_pose_cov_(i,j);
  }
  return {p,mean};
}
void GIEngine::setSupportPoseJointState(const pose_clone::Gaussian& state) {
  const std::size_t base=supportPoseCurrentSize();
  for(std::size_t i=0;i<21;++i) {
    dx_[i]=state.mean[i];
    for(std::size_t j=0;j<21;++j) Cov_(i,j)=state.covariance(i,j);
    if(sdk_discrepancy_initialized_) for(std::size_t j=0;j<2;++j)
      sdk_discrepancy_cross_(i,j)=state.covariance(i,21+j);
    if(support_pose_active_) for(std::size_t j=0;j<6;++j) support_pose_cross_(i,j)=state.covariance(i,base+j);
  }
  if(sdk_discrepancy_initialized_) for(std::size_t i=0;i<2;++i) {
    sdk_discrepancy_error_[i]=state.mean[21+i];
    for(std::size_t j=0;j<2;++j) sdk_discrepancy_cov_(i,j)=state.covariance(21+i,21+j);
    if(support_pose_active_) for(std::size_t j=0;j<6;++j)
      sdk_discrepancy_clone_cross_(i,j)=state.covariance(21+i,base+j);
  }
  if(support_pose_active_) for(std::size_t i=0;i<6;++i) {
    support_pose_error_[i]=state.mean[base+i];
    for(std::size_t j=0;j<6;++j) support_pose_cov_(i,j)=state.covariance(base+i,base+j);
  }
}
void GIEngine::setSupportPoseEvents(const std::vector<SupportPoseEvent>& events) {
  if(initialized_ || !supportPoseEnabled()) throw std::runtime_error("SUPPORT_POSE_SOURCE_INIT_ORDER");
  support_pose_events_=events;
}
bool GIEngine::hasSupportPoseStartBetween(double after,double through) const {
  for(std::size_t i=next_support_pose_event_;i<support_pose_events_.size();++i) {
    const auto& e=support_pose_events_[i];if(e.time>through) break;
    if(e.time>=after && e.type=="START") return true;
  }
  return false;
}
double GIEngine::supportPoseFactorStartTime(const std::string& id) const {
  for(const auto& e:support_pose_events_) if(e.type=="START" && e.clone_id==id) return e.time;
  return std::numeric_limits<double>::quiet_NaN();
}
void GIEngine::recordSupportPose(const SupportPoseEvent& e,const std::string& reason,bool attempted,bool accepted,double statistic) {
  support_pose_diagnostics_.push_back({e.time,timestamp_,statistic,e.type,e.clone_id,reason,attempted,accepted});
}
void GIEngine::retireSupportPose() {
  // The current marginal already contains every accepted joint update.
  support_pose_active_=false;support_pose_cross_=Matrix(21,6);support_pose_cov_=Matrix(6,6);
  support_pose_error_.assign(6,0.0);sdk_discrepancy_clone_cross_=Matrix(2,6);
}
void GIEngine::appendSupportPoseEvents(std::vector<JointTimedEvent>& combined) {
  if(!supportPoseEnabled()) return;
  if(!support_pose_stream_started_) {
    while(next_support_pose_event_<support_pose_events_.size() && support_pose_events_[next_support_pose_event_].time<=imupre_.time) {
      recordSupportPose(support_pose_events_[next_support_pose_event_++],"UNCONSUMED_INITIAL_POSE_SUPPORT");
      ++support_pose_counts_.unconsumed;
    }
    support_pose_stream_started_=true;
  }
  while(next_support_pose_event_<support_pose_events_.size() && support_pose_events_[next_support_pose_event_].time<=imucur_.time) {
    const auto& e=support_pose_events_[next_support_pose_event_++];
    auto same=std::find_if(combined.begin(),combined.end(),[&](const JointTimedEvent& q){return q.time==e.time;});
    if(same!=combined.end()) same->support.push_back(e);
    else {JointTimedEvent q;q.time=e.time;q.support.push_back(e);combined.push_back(q);}
  }
  std::stable_sort(combined.begin(),combined.end(),[](const JointTimedEvent& a,const JointTimedEvent& b){return a.time<b.time;});
}
void GIEngine::processSupportPoseEvent(const SupportPoseEvent& e) {
  if(e.time!=timestamp_ || e.time!=pvacur_.time) throw std::runtime_error("SUPPORT_POSE_EXACT_STATE_TIME");
  ++support_pose_counts_.event_rows;
  if(e.type=="REVOKE") {
    ++support_pose_counts_.revocations;
    if(support_pose_applied_ids_.count(e.clone_id) && !support_pose_revoked_.count(e.clone_id))
      support_pose_revocations_.push_back({e.time,e.clone_id});
    if(support_pose_active_ && support_pose_start_.clone_id==e.clone_id) retireSupportPose();
    recordSupportPose(e,"GEOMETRY_SOURCE_REVOKED");return;
  }
  if(e.type=="RETIRE") {
    ++support_pose_counts_.retires;
    if(support_pose_active_ && support_pose_start_.clone_id==e.clone_id) retireSupportPose();
    recordSupportPose(e,"CLOSED_NORMAL_PAST_VALID_INFORMATION_RETAINED");return;
  }
  const auto& c=options_.support_pose_config;
  if(e.type=="START") {
    ++support_pose_counts_.starts;
    if(support_pose_active_) throw std::runtime_error("SUPPORT_POSE_OVERLAPPING_INTERVALS");
    const auto current=supportPoseJointState();
    const auto joint=pose_clone::augment(current.covariance,current.mean,pose_clone::augmentationJacobian(pvacur_.pos_blh_rad_m));
    support_pose_start_=e;
    for(auto& point:support_pose_start_.positions_body_frd) point=multiply(c.foot_frd_to_engine_body,point);
    support_pose_cbe_=multiply(Earth::cne(pvacur_.pos_blh_rad_m),pvacur_.cbn);
    support_pose_position_ecef_=Earth::blh2ecef(pvacur_.pos_blh_rad_m);
    support_pose_active_=true;setSupportPoseJointState(joint);
    recordSupportPose(e,"POSE_CLONE_CREATED");return;
  }
  ++support_pose_counts_.ends;
  if(!support_pose_active_ || e.clone_id!=support_pose_start_.clone_id) {
    ++support_pose_counts_.rejected;recordSupportPose(e,"NO_MATCHING_POSE_CLONE");return;
  }
  const auto first=support_pose_start_;
  if(e.episode_i!=first.episode_i || e.episode_j!=first.episode_j || e.foot_i!=first.foot_i || e.foot_j!=first.foot_j ||
     !(e.time>first.time)) throw std::runtime_error("SUPPORT_POSE_EPISODE_CONTRACT");
  std::vector<Vec3> current=e.positions_body_frd;
  for(auto& point:current) point=multiply(c.foot_frd_to_engine_body,point);
  const double length_change=std::fabs(norm(subtract(current[0],current[1]))-
      norm(subtract(first.positions_body_frd[0],first.positions_body_frd[1])));
  const double point_radius=std::sqrt(16.26623619623813)*2*c.point_sigma_m;
  if(length_change>point_radius) {
    ++support_pose_counts_.rejected;recordSupportPose(e,"FOOT_LENGTH_GEOMETRY_MISMATCH");retireSupportPose();return;
  }
  if(support_pose_revoked_.count(e.clone_id)) {
    recordSupportPose(e,"REVOKED_FACTOR_EXCLUDED_FROM_REPLAY");retireSupportPose();return;
  }
  Matrix sigma(12,12);for(int i=0;i<12;++i) sigma(i,i)=c.point_sigma_m*c.point_sigma_m;
  auto model=pose_clone::footModel(first.positions_body_frd,current,support_pose_position_ecef_,
      support_pose_cbe_,pvacur_.cbn,pvacur_.pos_blh_rad_m,sigma,c.imu_lever_body_frd,c.horizontalOnly());
  if(sdk_discrepancy_initialized_) {
    Matrix h(model.H.rows,29);
    for(std::size_t i=0;i<h.rows;++i) for(std::size_t j=0;j<27;++j)
      h(i,j<21?j:j+2)=model.H(i,j);
    model.H=h; // No direct b column; foot updates b only through retained cross blocks.
  }
  const auto prior=supportPoseJointState();
  const auto b_before=sdkDiscrepancyConditionalMean();
  const auto S=add(multiply(multiply(model.H,prior.covariance),transpose(model.H)),model.R);
  const auto whitened=multiply(inverse(S),model.residual);
  double statistic=0;for(std::size_t i=0;i<whitened.size();++i) statistic+=model.residual[i]*whitened[i];
  if(c.mode!="REPLACE_SUPPORT") {
    ++support_pose_counts_.null_ends;recordSupportPose(e,"NULL_POSE_NO_FOOT_UPDATE",false,false,statistic);
  } else if(!std::isfinite(statistic) || statistic>c.nisThreshold()) {
    ++support_pose_counts_.rejected;recordSupportPose(e,c.horizontalOnly()?"WORKING_FOOT_XY_INNOVATION_REJECT":"WORKING_FOOT_XYZ_INNOVATION_REJECT",true,false,statistic);
  } else {
    setSupportPoseJointState(pose_clone::ordinaryUpdate(prior,model.residual,model.H,model.R));
    recordSdkDiscrepancy("FOOT_UPDATE",e.clone_id,e.time,prior,b_before,statistic,model.residual);
    stateFeedback();
    ++support_pose_counts_.accepted;support_pose_applied_ids_.insert(e.clone_id);
    recordSupportPose(e,c.horizontalOnly()?"SUPPORT_XY_JOINT_UPDATE":"SUPPORT_XYZ_JOINT_UPDATE",true,true,statistic);
  }
  retireSupportPose();
}
void GIEngine::finalizeSupportPoseStream() {
  if(!supportPoseEnabled()) return;
  while(next_support_pose_event_<support_pose_events_.size()) {
    ++support_pose_counts_.unconsumed;recordSupportPose(support_pose_events_[next_support_pose_event_++],"UNCONSUMED_OUTSIDE_IMU_SUPPORT");
  }
  retireSupportPose();
}
void GIEngine::writeSupportPoseDiagnostics(const std::string& output) const {
  if(!supportPoseEnabled()) return;
  std::ofstream out(std::filesystem::path(output)/"SUPPORT_POSE_EVENTS.csv");
  const auto& c=options_.support_pose_config;
  out<<"event_time_s,state_time_s,event_type,clone_id,attempted,accepted,reason,statistic,observed_axes,measurement_dimension,nis_threshold\n"<<std::setprecision(17);
  for(const auto& e:support_pose_diagnostics_)
    out<<e.time<<','<<e.state_time<<','<<e.type<<','<<e.clone_id<<','<<e.attempted<<','<<e.accepted<<','<<e.reason<<','<<e.statistic
       <<','<<c.observed_axes<<','<<c.measurementDimension()<<','<<c.nisThreshold()<<'\n';
}
std::vector<double> GIEngine::sdkDiscrepancyConditionalMean() const {
  auto result=sdk_discrepancy_mean_;
  for(std::size_t i=0;i<2;++i) result[i]+=sdk_discrepancy_error_[i];
  return result;
}
void GIEngine::recordSdkDiscrepancy(const std::string& kind,const std::string& identity,double source_time,
                                  const pose_clone::Gaussian& prior,const std::vector<double>& before,
                                  double nis,const std::vector<double>& innovation) {
  if(!sdkDiscrepancyEnabled()) return;
  SdkDiscrepancyDiagnostic d;
  d.time=timestamp_;d.source_time=source_time;d.kind=kind;d.identity=identity;d.nis=nis;
  d.initialized=sdk_discrepancy_initialized_;d.before=before;d.after=sdkDiscrepancyConditionalMean();
  d.bb=sdk_discrepancy_cov_;d.innovation=innovation;
  d.current_increment.resize(21);
  for(std::size_t i=0;i<21;++i) d.current_increment[i]=dx_[i]-prior.mean[i];
  for(double x:sdk_discrepancy_cross_.data) d.cross_norm+=x*x;
  for(double x:sdk_discrepancy_clone_cross_.data) d.clone_cross_norm+=x*x;
  d.cross_norm=std::sqrt(d.cross_norm);d.clone_cross_norm=std::sqrt(d.clone_cross_norm);
  sdk_discrepancy_diagnostics_.push_back(std::move(d));
}
void GIEngine::writeSdkDiscrepancyDiagnostics(const std::string& output) const {
  if(!sdkDiscrepancyEnabled()) return;
  std::ofstream out(std::filesystem::path(output)/"SDK_DISCREPANCY_EVENTS.csv");
  out<<std::setprecision(17)<<"time,source_time,kind,identity,initialized,b_forward_before,b_right_before,b_forward_after,b_right_after,Pbb00,Pbb01,Pbb11,Pxb_frobenius,Pbclone_frobenius,nis,innovation_dimensions";
  for(int i=0;i<6;++i) out<<",innovation_"<<i;
  out<<",delta_p_N_m,delta_p_E_m,delta_p_D_m,delta_v_N_mps,delta_v_E_mps,delta_v_D_mps,delta_phi_N_rad,delta_phi_E_rad,delta_phi_D_rad,delta_ba_x_mps2,delta_ba_y_mps2,delta_ba_z_mps2\n";
  for(const auto& d:sdk_discrepancy_diagnostics_) {
    out<<d.time<<','<<d.source_time<<','<<d.kind<<','<<std::quoted(d.identity)<<','<<d.initialized;
    for(double x:d.before) out<<','<<x;for(double x:d.after) out<<','<<x;
    out<<','<<d.bb(0,0)<<','<<d.bb(0,1)<<','<<d.bb(1,1)<<','<<d.cross_norm<<','<<d.clone_cross_norm<<','<<d.nis<<','<<d.innovation.size();
    for(std::size_t i=0;i<6;++i) out<<','<<(i<d.innovation.size()?d.innovation[i]:0.0);
    for(int i=0;i<3;++i) out<<','<<-d.current_increment[P_ID+i];
    for(int i=0;i<3;++i) out<<','<<-d.current_increment[V_ID+i];
    for(int i=0;i<3;++i) out<<','<<d.current_increment[PHI_ID+i];
    for(int i=0;i<3;++i) out<<','<<d.current_increment[BA_ID+i];out<<'\n';
  }
  std::ofstream summary(std::filesystem::path(output)/"SDK_DISCREPANCY_SUMMARY.json");
  summary<<std::setprecision(17)<<"{\n  \"mode\": \"joint_constant\",\n  \"initialized\": "<<(sdk_discrepancy_initialized_?"true":"false")
    <<",\n  \"seed_count\": "<<sdk_discrepancy_seed_count_<<",\n  \"seed_source_time\": "<<sdk_discrepancy_seed_source_time_
    <<",\n  \"seed_identity\": "<<std::quoted(sdk_discrepancy_seed_identity_)
    <<",\n  \"final_b_mps\": ["<<sdk_discrepancy_mean_[0]<<','<<sdk_discrepancy_mean_[1]<<']'
    <<",\n  \"final_Pbb\": ["<<sdk_discrepancy_cov_(0,0)<<','<<sdk_discrepancy_cov_(0,1)<<','<<sdk_discrepancy_cov_(1,0)<<','<<sdk_discrepancy_cov_(1,1)<<']'
    <<",\n  \"process_noise_Qb\": 0,\n  \"source_cross_N\": \"zero_working_assumption_uncalibrated\",\n  \"seed_is_navigation_update\": false,\n  \"diagnostic_increment\": \"conditional_error_mean_change_mapped_to_nominal_feedback_tangent_before_reset\",\n  \"replay_includes_complete_b_state\": true\n}\n";
}
}
