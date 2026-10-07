#include "legsa_v23_port_core/kf_gins/gi_engine.hpp"
#include "legsa_v23_port_core/common/earth.hpp"
#include "legsa_v23_port_core/common/rotation.hpp"
#include <algorithm>
#include <cmath>
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <limits>
#include <stdexcept>

namespace legsa_v23_port_core {
namespace {
void require(bool ok,const char* message) {if(!ok) throw std::runtime_error(message);}
}
attitude_clone::Gaussian GIEngine::attitudeJointState() const {
  if(!attitude_clone_active_) return {Cov_,dx_};
  Matrix p(24,24);std::vector<double> mean(24);
  for(std::size_t i=0;i<21;++i) {
    mean[i]=dx_[i];
    for(std::size_t j=0;j<21;++j) p(i,j)=Cov_(i,j);
    for(std::size_t j=0;j<3;++j) p(i,21+j)=p(21+j,i)=attitude_clone_cross_(i,j);
  }
  for(std::size_t i=0;i<3;++i) {
    mean[21+i]=attitude_clone_error_[i];
    for(std::size_t j=0;j<3;++j) p(21+i,21+j)=attitude_clone_cov_(i,j);
  }
  return {p,mean};
}
Matrix GIEngine::jointAttitudeCovariance() const {return attitudeJointState().covariance;}

void GIEngine::setAttitudeJointState(const attitude_clone::Gaussian& state) {
  const std::size_t size=attitude_clone_active_?24:21;
  require(state.mean.size()==size && state.covariance.rows==size && state.covariance.cols==size,
          "ATTITUDE_CLONE_JOINT_STATE_SIZE");
  for(double x:state.mean) require(std::isfinite(x),"ATTITUDE_CLONE_NONFINITE_MEAN");
  for(double x:state.covariance.data) require(std::isfinite(x),"ATTITUDE_CLONE_NONFINITE_COVARIANCE");
  for(std::size_t i=0;i<21;++i) {
    dx_[i]=state.mean[i];
    for(std::size_t j=0;j<21;++j) Cov_(i,j)=state.covariance(i,j);
    if(attitude_clone_active_) for(std::size_t j=0;j<3;++j)
      attitude_clone_cross_(i,j)=state.covariance(i,21+j);
  }
  if(attitude_clone_active_) for(std::size_t i=0;i<3;++i) {
    attitude_clone_error_[i]=state.mean[21+i];
    for(std::size_t j=0;j<3;++j) attitude_clone_cov_(i,j)=state.covariance(21+i,21+j);
  }
}
void GIEngine::requireFrozenCloneBlocks() const {
  if(!jointCloneEnabled()) return;
  require(attitude_clone_weights_.size()==21,"ATTITUDE_CLONE_WEIGHTS_NOT_INITIALIZED");
  for(std::size_t i=0;i<21;++i) if(attitude_clone_weights_[i]==0.0) {
    require(dx_[i]==0.0,"ATTITUDE_CLONE_FROZEN_MEAN_ACTIVATED");
    for(std::size_t j=0;j<21;++j)
      require(Cov_(i,j)==0.0 && Cov_(j,i)==0.0,"ATTITUDE_CLONE_FROZEN_COV_ACTIVATED");
    if(attitude_clone_active_) for(std::size_t j=0;j<3;++j)
      require(attitude_clone_cross_(i,j)==0.0,"ATTITUDE_CLONE_FROZEN_CROSS_ACTIVATED");
  }
}
void GIEngine::setFootPairEvents(const std::vector<FootPairEvent>& events) {
  require(!initialized_,"FOOT_PAIR_SOURCE_MUST_BE_SET_BEFORE_INITIALIZATION");
  require(options_.attitude_clone_config.mode!="off","FOOT_PAIR_OFF_INPUT_FORBIDDEN");
  double last=-std::numeric_limits<double>::infinity();
  for(const auto& e:events) {
    require(std::isfinite(e.time) && e.time>last && e.available_time==e.time &&
            (e.type=="RETIRE" ? std::isnan(e.source_time) : e.source_time==e.time),
            "FOOT_PAIR_STREAM_TIME_CONTRACT");
    require(!e.clone_id.empty() && !e.reason.empty(),"FOOT_PAIR_STREAM_IDENTITY");
    require(e.type=="START" || e.type=="END" || e.type=="RETIRE","FOOT_PAIR_STREAM_ACTION");
    last=e.time;
  }
  const char* passive=std::getenv("LEGSA_FOOT_INFORMATION_DIAGNOSTICS");
  require(!passive || std::string(passive)=="0" || std::string(passive)=="1",
          "FOOT_INFORMATION_DIAGNOSTIC_FLAG_MUST_BE_0_OR_1");
  foot_information_diagnostics_enabled_=passive && std::string(passive)=="1";
  foot_events_=events;
}
void GIEngine::recordFootEvent(const FootPairEvent& e,const std::string& action,bool applied,double epsilon,
                               double prior_score,double bound_score,double safe_innovation) {
  foot_event_diagnostics_.push_back({e.time,timestamp_,e.source_time,e.type,e.clone_id,e.endpoint_id,
                                     action,applied,epsilon,prior_score,bound_score,safe_innovation});
}
void GIEngine::retireAttitudeClone() {
  // Cov_ and dx_ already ARE the current marginal. No Schur complement.
  attitude_clone_active_=false;
  attitude_clone_owner_="NONE";
  attitude_clone_cross_=Matrix(21,3);attitude_clone_cov_=Matrix(3,3);
  attitude_clone_error_={0.0,0.0,0.0};
}
void GIEngine::processFootPairEvent(const FootPairEvent& e) {
  require(options_.attitude_clone_config.mode!="off","FOOT_PAIR_EVENT_WHILE_OFF");
  require(e.time==timestamp_ && e.time==pvacur_.time && e.available_time==e.time &&
          (e.type=="RETIRE" ? std::isnan(e.source_time) : e.source_time==e.time),
          "FOOT_PAIR_MUST_BIND_EXACT_CURRENT_POSE");
  ++attitude_clone_counts_.event_rows;
  for(double x:dx_) require(x==0.0,"FOOT_PAIR_START_END_REQUIRES_COMPLETED_FEEDBACK");
  const auto& config=options_.attitude_clone_config;
  auto reject=[&](const char* reason) {
    ++attitude_clone_counts_.rejected_events;recordFootEvent(e,reason);retireAttitudeClone();
  };
  if(e.type=="RETIRE") {
    ++attitude_clone_counts_.retires;
    if(!attitude_clone_active_ || e.clone_id!=attitude_clone_start_.clone_id) {
      reject("RETIRE_NO_MATCHING_ACTIVE_CLONE");return;
    }
    recordFootEvent(e,"SOURCE_RETIRED");retireAttitudeClone();return;
  }
  require(!e.endpoint_id.empty() && !e.foot_i.empty() && !e.foot_j.empty() && e.foot_i!=e.foot_j &&
          !e.episode_i.empty() && !e.episode_j.empty(),"FOOT_PAIR_ENDPOINT_IDENTITIES_REQUIRED");
  require(std::isfinite(norm(e.direction_body_frd)) && norm(e.direction_body_frd)>1e-10,
          "FOOT_PAIR_DIRECTION_INVALID");
  if(!foot_used_endpoint_ids_.insert(e.endpoint_id).second) {reject("ENDPOINT_ALREADY_CONSUMED");return;}
  if(e.type=="START") {
    ++attitude_clone_counts_.starts;
    if(attitude_clone_active_) {reject("START_WHILE_ACTIVE_NO_REPLACEMENT");return;}
    if(!attitude_clone_used_ids_.insert(e.clone_id).second) {reject("RETIRED_CLONE_ID_NOT_REUSABLE");return;}
    const auto augmented=attitude_clone::augment(Cov_,dx_,attitude_clone::augmentationJacobian(pvacur_.pos_blh_rad_m));
    attitude_clone_start_=e;
    attitude_clone_start_.direction_body_frd=multiply(config.foot_frd_to_engine_body,e.direction_body_frd);
    attitude_clone_cbe_=multiply(Earth::cne(pvacur_.pos_blh_rad_m),pvacur_.cbn);
    attitude_clone::requireRotation(attitude_clone_cbe_,"START_CBE");
    attitude_clone_active_=true;attitude_clone_owner_="FOOT";setAttitudeJointState(augmented);
    recordFootEvent(e,"CLONE_CREATED_DETERMINISTIC");return;
  }
  require(e.type=="END","FOOT_PAIR_UNKNOWN_ACTION");
  ++attitude_clone_counts_.ends;
  if(!attitude_clone_active_ || e.clone_id!=attitude_clone_start_.clone_id) {
    reject("END_NO_MATCHING_ACTIVE_CLONE");return;
  }
  const auto& first=attitude_clone_start_;
  const double dt=e.time-first.time;
  if(!(dt>=0.1-1e-10 && dt<=0.15+1e-10) || e.foot_i!=first.foot_i || e.foot_j!=first.foot_j ||
      e.episode_i!=first.episode_i || e.episode_j!=first.episode_j) {
    reject("END_INTERVAL_OR_CONTACT_EPISODE_MISMATCH");return;
  }
  // Whole-interval support is a producer/source contract, not certified by matching tokens alone.
  Matrix frame(6,6);setBlock(frame,0,0,config.foot_frd_to_engine_body);setBlock(frame,3,3,config.foot_frd_to_engine_body);
  const Matrix sigma=multiply(multiply(frame,e.difference_covariance),transpose(frame));
  const auto model=attitude_clone::pairModel(first.direction_body_frd,
      multiply(config.foot_frd_to_engine_body,e.direction_body_frd),attitude_clone_cbe_,pvacur_.cbn,
      pvacur_.pos_blh_rad_m,sigma);
  const auto safe=attitude_clone::safeInnovation(attitudeJointState(),model.residual,model.H,model.R);
  if(!safe.passed) {
    ++attitude_clone_counts_.innovation_rejects;
    recordFootEvent(e,"WORKING_SAFE_INNOVATION_REJECT",false,0,0,0,safe.statistic);
    retireAttitudeClone();return;
  }
  if(config.mode=="NULL_CLONE") {
    ++attitude_clone_counts_.null_ends;
    recordFootEvent(e,"NULL_CLONE_NO_PAIR_UPDATE",false,0,0,0,safe.statistic);
    retireAttitudeClone();return;
  }
  const auto prior=attitudeJointState();
  attitude_clone::YoungDiagnostics passive;
  const auto result=attitude_clone::youngUpdate(prior,model.residual,model.H,model.R,
                                               attitude_clone_weights_,
                                               foot_information_diagnostics_enabled_?&passive:nullptr);
  if(foot_information_diagnostics_enabled_)
    foot_information_diagnostics_.push_back({e.time,prior,model,passive,result.applied,result.epsilon});
  if(result.applied) {
    setAttitudeJointState(result.state);
    stateFeedback();  // Same full feedback/reset implementation as every original observation.
    ++attitude_clone_counts_.pair_updates;
  } else ++attitude_clone_counts_.pair_skips;
  recordFootEvent(e,result.applied?"PAIR_YOUNG_UPDATED":"PAIR_YOUNG_EXACT_SKIP",result.applied,
                  result.epsilon,result.prior_score,result.bound_score,safe.statistic);
  retireAttitudeClone();
  requireFrozenCloneBlocks();
}
void GIEngine::newImuProcessWithEvents(const std::vector<GnssData>& events) {
  std::vector<JointTimedEvent> combined;
  for(const auto& e:events) combined.push_back({e.time,true,e,{}});
  if(options_.attitude_clone_config.mode!="off") {
    if(!foot_stream_started_) {
      // The first IMU is initialization only. No historical pose is invented for earlier foot records.
      while(next_foot_event_<foot_events_.size() && foot_events_[next_foot_event_].time<=imupre_.time) {
        const auto& e=foot_events_[next_foot_event_++];
        ++attitude_clone_counts_.late_initial_events;
        attitude_clone_used_ids_.insert(e.clone_id);
        if(!e.endpoint_id.empty()) foot_used_endpoint_ids_.insert(e.endpoint_id);
        recordFootEvent(e,"UNCONSUMED_INITIAL_POSE_SUPPORT");
      }
      foot_stream_started_=true;
    }
    while(next_foot_event_<foot_events_.size() && foot_events_[next_foot_event_].time<=imucur_.time) {
      const auto& e=foot_events_[next_foot_event_++];
      require(e.time>=imupre_.time,"FOOT_PAIR_EVENT_ALREADY_STALE");
      auto same=std::find_if(combined.begin(),combined.end(),[&](const JointTimedEvent& q){return q.time==e.time;});
      if(same!=combined.end()) same->feet.push_back(e);
      else combined.push_back({e.time,false,GnssData{}, {e}});
    }
    std::stable_sort(combined.begin(),combined.end(),[](const JointTimedEvent& a,const JointTimedEvent& b){return a.time<b.time;});
  }
  appendSupportPoseEvents(combined);
  appendArcTimedEvents(combined);
  processExactJointEvents(combined);
}
void GIEngine::finalizeFootPairStream() {
  if(options_.attitude_clone_config.mode=="off") return;
  while(next_foot_event_<foot_events_.size()) {
    const auto& e=foot_events_[next_foot_event_++];
    if(e.type=="RETIRE") {
      ++attitude_clone_counts_.unconsumed_terminal;recordFootEvent(e,"UNCONSUMED_TERMINAL_CLEANUP");
    } else {
      ++attitude_clone_counts_.unconsumed_outside_imu;recordFootEvent(e,"UNCONSUMED_OUTSIDE_IMU_SUPPORT");
    }
  }
  // The clone's disappearance at end of file changes no current marginal or NAV sample.
  retireAttitudeClone();
}
void GIEngine::writeAttitudeCloneDiagnostics(const std::string& output_dir) const {
  if(options_.attitude_clone_config.mode=="off") return;
  std::ofstream out(std::filesystem::path(output_dir)/"ATTITUDE_CLONE_EVENTS.csv");
  require(out.good(),"ATTITUDE_CLONE_DIAGNOSTIC_OPEN");
  out<<"event_time_s,state_time_s,source_time_s,event_type,clone_id,endpoint_id,action,updated,epsilon,prior_weighted_trace,bound_weighted_trace,safe_innovation,safe_threshold\n";
  out<<std::setprecision(17);
  for(const auto& e:foot_event_diagnostics_) {
    out<<e.event_time<<','<<e.state_time<<',';
    if(std::isfinite(e.source_time)) out<<e.source_time;
    out<<','<<e.type<<','<<e.clone_id<<','<<e.endpoint_id<<','
       <<e.action<<','<<e.applied<<','<<e.epsilon<<','<<e.prior_score<<','<<e.bound_score<<',';
    if(e.safe_innovation>=0.0) out<<e.safe_innovation;
    out<<','<<attitude_clone::kSafeInnovationThreshold<<'\n';
  }
  if(foot_information_diagnostics_enabled_) {
    std::ofstream inputs(std::filesystem::path(output_dir)/"FOOT_INFORMATION_INPUTS.jsonl");
    require(inputs.good(),"FOOT_INFORMATION_DIAGNOSTIC_OPEN");
    inputs<<std::setprecision(17);
    auto vector=[&](const std::vector<double>& values) {
      inputs<<'[';
      for(std::size_t i=0;i<values.size();++i) {if(i) inputs<<',';inputs<<values[i];}
      inputs<<']';
    };
    for(const auto& d:foot_information_diagnostics_) {
      inputs<<"{\"schema\":1,\"event_time_s\":"<<d.event_time<<",\"P\":";
      vector(d.prior.covariance.data);inputs<<",\"mean\":";vector(d.prior.mean);
      inputs<<",\"H\":";vector(d.model.H.data);inputs<<",\"R\":";vector(d.model.R.data);
      inputs<<",\"dz\":";vector(d.model.residual);inputs<<",\"weights\":";vector(attitude_clone_weights_);
      inputs<<",\"T\":"<<d.young.T<<",\"J\":";
      if(d.young.J_available) inputs<<d.young.J;else inputs<<"null";
      inputs<<",\"applied\":"<<(d.applied?"true":"false")
            <<",\"selected_epsilon\":"<<d.selected_epsilon<<",\"candidates\":[";
      for(std::size_t i=0;i<d.young.candidates.size();++i) {
        const auto& c=d.young.candidates[i];if(i) inputs<<',';
        inputs<<"{\"epsilon\":"<<c.epsilon<<",\"score\":"<<c.score
              <<",\"comparison_score\":"<<c.comparison_score<<",\"tie\":"<<c.tie
              <<",\"selected_at_step\":"<<(c.selected_at_step?"true":"false")<<'}';
      }
      inputs<<"]}\n";
    }
    require(inputs.good(),"FOOT_INFORMATION_DIAGNOSTIC_WRITE");
  }
  std::ofstream weights(std::filesystem::path(output_dir)/"ATTITUDE_CLONE_FIXED_WEIGHTS.csv");
  require(weights.good(),"ATTITUDE_CLONE_WEIGHTS_OPEN");
  weights<<"current_error_coordinate,initial_block_inverse_mean_variance_weight\n";
  weights<<std::setprecision(17);
  for(std::size_t i=0;i<attitude_clone_weights_.size();++i) weights<<i<<','<<attitude_clone_weights_[i]<<'\n';
}
}  // namespace legsa_v23_port_core
