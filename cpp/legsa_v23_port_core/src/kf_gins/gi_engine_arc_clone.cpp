#include "legsa_v23_port_core/kf_gins/gi_engine.hpp"
#include "legsa_v23_port_core/common/earth.hpp"
#include <algorithm>
#include <cmath>
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <stdexcept>

namespace legsa_v23_port_core {
namespace {
void require(bool ok,const char* message) {if(!ok) throw std::runtime_error(message);}
void quoted(std::ostream& out,const std::string& text) {
  out<<'"';for(unsigned char c:text) {
    if(c=='"' || c=='\\') out<<'\\'<<c;
    else if(c<32) {const char* hex="0123456789abcdef";out<<"\\u00"<<hex[c>>4]<<hex[c&15];}
    else out<<c;
  } out<<'"';
}
void scalar(std::ostream& out,double x) {if(std::isfinite(x)) out<<x;else out<<"null";}
void matrix(std::ostream& out,const Matrix& m) {
  out<<'[';for(std::size_t i=0;i<m.rows;++i) {if(i) out<<',';out<<'[';
    for(std::size_t j=0;j<m.cols;++j) {if(j) out<<',';scalar(out,m(i,j));}out<<']';}out<<']';
}
void matrix3(std::ostream& out,const Matrix3& m) {
  out<<'[';for(std::size_t i=0;i<3;++i) {if(i) out<<',';out<<'[';
    for(std::size_t j=0;j<3;++j) {if(j) out<<',';scalar(out,m[i][j]);}out<<']';}out<<']';
}
template<class T> void vector(std::ostream& out,const T& v) {
  out<<'[';for(std::size_t i=0;i<v.size();++i) {if(i) out<<',';scalar(out,v[i]);}out<<']';
}
void finite(const Matrix& m) {for(double x:m.data) require(std::isfinite(x),"ARC_NONFINITE_SNAPSHOT");}
void event(std::ostream& out,const ArcSourceEvent& e) {
  out<<"{\"sequence_id\":";quoted(out,e.sequence_id);out<<",\"block_id\":";quoted(out,e.block_id);
  out<<",\"endpoint_id\":";quoted(out,e.endpoint_id);out<<",\"role\":";quoted(out,e.role);
  out<<",\"source_time_s\":";scalar(out,e.source_time);out<<",\"source_time_bits_hex\":";quoted(out,e.source_time_bits_hex);
  out<<",\"replay_execution_time_s\":";scalar(out,e.replay_time);
  out<<",\"actual_available_time_s\":null,\"availability_mode\":";quoted(out,e.availability_mode);
  out<<",\"epoch_index\":"<<e.epoch_index<<",\"endpoint_model_fingerprint\":";quoted(out,e.endpoint_model_fingerprint);out<<'}';
}
}
bool GIEngine::jointCloneEnabled() const {
  return options_.attitude_clone_config.mode!="off" || options_.arc_clone_config.mode!="off";
}
void GIEngine::setArcSourceEvents(const std::vector<ArcSourceEvent>& events) {
  require(!initialized_,"ARC_SOURCE_MUST_BE_SET_BEFORE_INITIALIZATION");
  require(options_.arc_clone_config.mode!="off","ARC_OFF_INPUT_FORBIDDEN");
  validateArcSourceEvents(events);
  const char* flag=std::getenv("LEGSA_ARC_NATIVE_TELEMETRY");
  require(!flag || std::string(flag)=="0" || std::string(flag)=="1","ARC_TELEMETRY_FLAG_MUST_BE_0_OR_1");
  arc_native_telemetry_enabled_=flag && std::string(flag)=="1";
  arc_events_=events;
}
void GIEngine::initializeArcDiagnostics() {
  next_arc_event_=0;arc_dispatch_ordinal_=0;arc_state_sample_count_=0;
  arc_stream_started_=false;arc_stream_finalized_=false;
  arc_clone_counts_=ArcCloneCounts{};arc_clone_counts_.source_rows=arc_events_.size();
  arc_lifecycle_events_.clear();arc_conditioning_events_.clear();arc_imu_segments_.clear();arc_joint_priors_.clear();
  arc_active_prior_=ArcJointPrior{};
  for(const auto& e:arc_events_) {
    if(e.role=="START") {ArcLifecycleEvent row;row.start=e;arc_lifecycle_events_.push_back(row);}
    else {arc_lifecycle_events_.back().end=e;arc_lifecycle_events_.back().has_end=true;}
  }
  arc_clone_counts_.source_blocks=arc_lifecycle_events_.size();
}
void GIEngine::recordArcConditioning(const std::string& kind,const std::string& source_tag,
                                     const std::string& provider_measurement_identity) {
  if(options_.arc_clone_config.mode=="off") return;
  ArcConditioningEvent e;e.ordinal=arc_conditioning_events_.size()+1;
  e.update_ordinal=arc_clone_counts_.ordinary_updates;e.reset_ordinal=arc_clone_counts_.full_resets;
  e.state_time=timestamp_;e.kind=kind;e.source_tag=source_tag;e.clone_owner=attitude_clone_owner_;
  e.provider_measurement_identity=provider_measurement_identity;
  if(attitude_clone_active_ && attitude_clone_owner_=="ARC") e.block_id=arc_active_prior_.start.block_id;
  arc_conditioning_events_.push_back(e);
}
void GIEngine::recordArcImuSegment(const ImuData& previous,const ImuData& segment) {
  if(options_.arc_clone_config.mode=="off") return;
  ArcImuSegment s;s.ordinal=++arc_clone_counts_.imu_segments;
  s.start_time=previous.time;s.end_time=segment.time;s.measured_dt=segment.dt;
  s.dtheta=segment.dtheta;s.dvel=segment.dvel;s.input_compensated=segment.compensated;
  arc_imu_segments_.push_back(s);
}
std::string GIEngine::arcConditioningInformationId() const {
  const auto& c=options_.arc_clone_config;
  return options_.run_id+":"+c.events_sha256+":"+c.manifest_sha256+":U"+
    std::to_string(arc_clone_counts_.ordinary_updates)+":R"+std::to_string(arc_clone_counts_.full_resets)+
    ":L"+std::to_string(arc_conditioning_events_.size())+":T"+arcSourceTimeBits(timestamp_);
}
void GIEngine::appendArcTimedEvents(std::vector<JointTimedEvent>& combined) {
  if(options_.arc_clone_config.mode=="off") return;
  require(!arc_stream_finalized_,"ARC_STREAM_ALREADY_FINALIZED");
  if(!arc_stream_started_) {
    while(next_arc_event_<arc_events_.size() && arc_events_[next_arc_event_].source_time<=imupre_.time) {
      const auto& e=arc_events_[next_arc_event_++];
      auto row=std::find_if(arc_lifecycle_events_.begin(),arc_lifecycle_events_.end(),
                          [&](const ArcLifecycleEvent& q){return q.start.block_id==e.block_id;});
      require(row!=arc_lifecycle_events_.end(),"ARC_INITIAL_BLOCK_IDENTITY");
      if(row->status=="PENDING") {row->status="UNCOVERED_INITIAL_STATE";++arc_clone_counts_.uncovered_initial;}
      ++arc_clone_counts_.event_rows;
      recordArcConditioning("UNCOVERED_INITIAL_STATE",e.role+":"+e.block_id);
    }
    arc_stream_started_=true;
  }
  while(next_arc_event_<arc_events_.size() && arc_events_[next_arc_event_].source_time<=imucur_.time) {
    const auto& e=arc_events_[next_arc_event_++];
    require(e.source_time>=imupre_.time,"ARC_EVENT_ALREADY_STALE");
    auto same=std::find_if(combined.begin(),combined.end(),[&](const JointTimedEvent& q){return q.time==e.source_time;});
    if(same!=combined.end()) same->arcs.push_back(e);
    else combined.push_back({e.source_time,false,GnssData{},{},{e}});
  }
  std::stable_sort(combined.begin(),combined.end(),[](const JointTimedEvent& a,const JointTimedEvent& b){return a.time<b.time;});
}
void GIEngine::processArcSourceEvent(const ArcSourceEvent& e) {
  require(options_.arc_clone_config.mode!="off","ARC_EVENT_WHILE_OFF");
  require(!arc_stream_finalized_,"ARC_EVENT_AFTER_FINALIZE");
  require(e.source_time==timestamp_ && e.source_time==pvacur_.time && e.replay_time==e.source_time &&
          arcSourceTimeBits(e.source_time)==e.source_time_bits_hex,"ARC_MUST_BIND_EXACT_CURRENT_POSE");
  require(std::isnan(e.actual_available_time) && e.availability_mode=="SOURCE_TIME_REPLAY_ASSUMPTION",
          "ARC_AVAILABILITY_MUST_REMAIN_UNKNOWN");
  for(double x:dx_) require(x==0.0,"ARC_REQUIRES_COMPLETED_FEEDBACK");
  for(double x:attitude_clone_error_) require(x==0.0,"ARC_REQUIRES_COMPLETED_CLONE_FEEDBACK");
  auto row=std::find_if(arc_lifecycle_events_.begin(),arc_lifecycle_events_.end(),
                      [&](const ArcLifecycleEvent& q){return q.start.block_id==e.block_id;});
  require(row!=arc_lifecycle_events_.end(),"ARC_UNKNOWN_BLOCK");
  const auto& expected=e.role=="START"?row->start:row->end;
  require(e.sequence_id==expected.sequence_id && e.endpoint_id==expected.endpoint_id &&
          e.source_time_bits_hex==expected.source_time_bits_hex && e.epoch_index==expected.epoch_index &&
          e.endpoint_model_fingerprint==expected.endpoint_model_fingerprint,"ARC_DISPATCH_SCHEDULE_IDENTITY");
  ++arc_clone_counts_.event_rows;++arc_dispatch_ordinal_;
  if(e.role=="START") {
    require(!attitude_clone_active_ && row->status=="PENDING" && e.endpoint_id==row->start.endpoint_id,
            "ARC_START_REUSE_OR_ACTIVE_OWNER");
    ++arc_clone_counts_.starts;
    arc_active_lifecycle_=static_cast<std::size_t>(row-arc_lifecycle_events_.begin());
    arc_active_prior_=ArcJointPrior{};auto& p=arc_active_prior_;p.start=e;p.start_state_time=timestamp_;p.start_P21=Cov_;
    p.J0=attitude_clone::augmentationJacobian(pvacur_.pos_blh_rad_m);p.start_blh=pvacur_.pos_blh_rad_m;
    p.start_C0=multiply(Earth::cne(pvacur_.pos_blh_rad_m),pvacur_.cbn);
    attitude_clone::requireRotation(p.start_C0,"ARC_START_C0");
    p.start_update_ordinal=arc_clone_counts_.ordinary_updates;p.start_reset_ordinal=arc_clone_counts_.full_resets;
    const auto augmented=attitude_clone::augment(Cov_,dx_,p.J0);
    attitude_clone_cbe_=p.start_C0;attitude_clone_active_=true;attitude_clone_owner_="ARC";
    setAttitudeJointState(augmented);requireFrozenCloneBlocks();
    row->status="ACTIVE";row->clone_owner="ARC";row->clone_created=true;
    row->start_dispatch_phase="POST_ALL_EXISTING_UPDATES_AT_TIMESTAMP";
    row->dispatch_phase="START_DISPATCHED_END_PENDING";
    row->start_state_time=timestamp_;row->start_update_ordinal=p.start_update_ordinal;
    row->start_reset_ordinal=p.start_reset_ordinal;row->start_dispatch_ordinal=arc_dispatch_ordinal_;
    row->start_state_sample_count=arc_state_sample_count_;
    recordArcConditioning("ARC_START","DETERMINISTIC_ECEF_AUGMENTATION");return;
  }
  require(e.role=="END" && row->has_end && e.endpoint_id==row->end.endpoint_id,"ARC_END_IDENTITY");
  row->end_dispatch_phase="POST_ALL_EXISTING_UPDATES_AT_TIMESTAMP";
  row->end_state_time=timestamp_;row->end_update_ordinal=arc_clone_counts_.ordinary_updates;
  row->end_reset_ordinal=arc_clone_counts_.full_resets;row->end_dispatch_ordinal=arc_dispatch_ordinal_;
  row->end_state_sample_count=arc_state_sample_count_;
  if(row->status=="UNCOVERED_INITIAL_STATE") {
    row->dispatch_phase="END_DISPATCHED_START_UNCOVERED";
    recordArcConditioning("ARC_END_UNCOVERED_INITIAL","NO_HISTORICAL_POSE_INVENTED");return;
  }
  require(attitude_clone_active_ && attitude_clone_owner_=="ARC" && row->status=="ACTIVE" &&
          arc_active_lifecycle_==static_cast<std::size_t>(row-arc_lifecycle_events_.begin()),"ARC_END_WITHOUT_ACTIVE_OWNER");
  auto& p=arc_active_prior_;p.end=e;p.end_state_time=timestamp_;
  const auto joint=attitudeJointState();p.P24=joint.covariance;p.dx24=joint.mean;
  p.clone_C0_given_end=attitude_clone_cbe_;p.current_cbn=pvacur_.cbn;p.current_blh=pvacur_.pos_blh_rad_m;
  p.current_C1=multiply(Earth::cne(p.current_blh),p.current_cbn);
  attitude_clone::requireRotation(p.clone_C0_given_end,"ARC_END_C0");
  attitude_clone::requireRotation(p.current_C1,"ARC_END_C1");
  p.J1=attitude_clone::augmentationJacobian(p.current_blh);p.B6=Matrix(6,24);
  for(std::size_t i=0;i<3;++i) {p.B6(i,21+i)=1.0;
    for(std::size_t j=0;j<21;++j) p.B6(3+i,j)=p.J1(i,j);}
  p.P6=multiply(multiply(p.B6,p.P24),transpose(p.B6));
  finite(p.P24);finite(p.J1);finite(p.B6);finite(p.P6);
  p.end_update_ordinal=arc_clone_counts_.ordinary_updates;p.end_reset_ordinal=arc_clone_counts_.full_resets;
  p.conditioning_ordinal=arc_conditioning_events_.size();p.conditioning_information_id=arcConditioningInformationId();
  arc_joint_priors_.push_back(p);  // Both arms compute/store the identical complete snapshot.
  ++arc_clone_counts_.ends;++arc_clone_counts_.covered_blocks;++arc_clone_counts_.retires;
  row->status="COVERED_END_PRIOR";row->dispatch_phase="POST_ALL_EXISTING_UPDATES_AT_TIMESTAMP";
  recordArcConditioning("ARC_END","CURRENT_MARGINAL_RETIRE_NO_PHASE_UPDATE");
  retireAttitudeClone();requireFrozenCloneBlocks();
}
void GIEngine::finalizeArcSourceStream() {
  if(options_.arc_clone_config.mode=="off") return;
  require(!arc_stream_finalized_,"ARC_DUPLICATE_FINALIZE");
  for(auto& row:arc_lifecycle_events_) if(row.status=="PENDING" || row.status=="ACTIVE") {
    if(row.status=="ACTIVE") row.dispatch_phase="START_DISPATCHED_END_UNCOVERED";
    row.status="UNCOVERED_TERMINAL";++arc_clone_counts_.uncovered_terminal;
  }
  if(attitude_clone_active_) {
    require(attitude_clone_owner_=="ARC","ARC_FINALIZE_WRONG_OWNER");
    recordArcConditioning("ARC_TERMINAL_RETIRE","NO_EXTRA_PROPAGATION_OR_NAV_SAMPLE");
    ++arc_clone_counts_.retires;retireAttitudeClone();
  }
  next_arc_event_=arc_events_.size();arc_stream_finalized_=true;
  require(arc_clone_counts_.covered_blocks+arc_clone_counts_.uncovered_initial+arc_clone_counts_.uncovered_terminal==
          arc_clone_counts_.source_blocks,"ARC_FINAL_BLOCK_DENOMINATOR");
}
void GIEngine::writeArcCloneDiagnostics(const std::string& output_dir) const {
  if(options_.arc_clone_config.mode=="off") return;
  require(arc_stream_finalized_,"ARC_WRITE_REQUIRES_FINALIZE");
  const std::filesystem::path dir(output_dir);
  std::ofstream life(dir/"ARC_LIFECYCLE.csv");require(life.good(),"ARC_LIFECYCLE_OPEN");life<<std::setprecision(17);
  life<<"sequence_id,block_id,start_endpoint_id,end_endpoint_id,start_epoch_index,end_epoch_index,start_source_time_s,end_source_time_s,start_source_time_bits_hex,end_source_time_bits_hex,start_replay_execution_time_s,end_replay_execution_time_s,actual_available_time_s,availability_mode,start_model_fingerprint,end_model_fingerprint,start_state_time_s,end_state_time_s,status,clone_owner_at_creation,clone_created,planned_clone_owner,dispatch_phase,start_dispatch_phase,end_dispatch_phase,start_update_ordinal,end_update_ordinal,start_reset_ordinal,end_reset_ordinal,start_dispatch_ordinal,end_dispatch_ordinal,start_state_sample_count,end_state_sample_count\n";
  for(const auto& q:arc_lifecycle_events_) {
    life<<q.start.sequence_id<<','<<q.start.block_id<<','<<q.start.endpoint_id<<','<<(q.has_end?q.end.endpoint_id:"")<<','<<q.start.epoch_index<<',';
    if(q.has_end) life<<q.end.epoch_index;life<<','<<q.start.source_time<<',';
    if(q.has_end) life<<q.end.source_time;life<<','<<q.start.source_time_bits_hex<<','<<(q.has_end?q.end.source_time_bits_hex:"")<<','<<q.start.replay_time<<',';
    if(q.has_end) life<<q.end.replay_time;
    life<<",,SOURCE_TIME_REPLAY_ASSUMPTION,"<<q.start.endpoint_model_fingerprint<<','<<(q.has_end?q.end.endpoint_model_fingerprint:"")<<',';
    if(std::isfinite(q.start_state_time)) life<<q.start_state_time;life<<',';
    if(std::isfinite(q.end_state_time)) life<<q.end_state_time;
    life<<','<<q.status<<','<<q.clone_owner<<','<<q.clone_created<<",ARC,"<<q.dispatch_phase<<','
        <<q.start_dispatch_phase<<','<<q.end_dispatch_phase<<','<<q.start_update_ordinal<<','<<q.end_update_ordinal<<','
        <<q.start_reset_ordinal<<','<<q.end_reset_ordinal<<','<<q.start_dispatch_ordinal<<','<<q.end_dispatch_ordinal<<','
        <<q.start_state_sample_count<<','<<q.end_state_sample_count<<'\n';
  }
  std::ofstream ledger(dir/"ARC_CONDITIONING_EVENTS.jsonl");require(ledger.good(),"ARC_LEDGER_OPEN");ledger<<std::setprecision(17);
  for(const auto& e:arc_conditioning_events_) {
    ledger<<"{\"ordinal\":"<<e.ordinal<<",\"update_ordinal\":"<<e.update_ordinal<<",\"reset_ordinal\":"<<e.reset_ordinal
          <<",\"state_time_s\":"<<e.state_time<<",\"state_time_bits_hex\":";quoted(ledger,arcSourceTimeBits(e.state_time));
    ledger<<",\"kind\":";quoted(ledger,e.kind);ledger<<",\"source_tag\":";quoted(ledger,e.source_tag);
    ledger<<",\"clone_owner\":";quoted(ledger,e.clone_owner);ledger<<",\"block_id\":";quoted(ledger,e.block_id);
    ledger<<",\"provider_measurement_identity\":";quoted(ledger,e.provider_measurement_identity);
    ledger<<",\"actual_available_time_s\":null,\"phase_state_cross\":\"UNKNOWN\"}\n";
  }
  std::ofstream segments(dir/"ARC_IMU_SEGMENTS.csv");require(segments.good(),"ARC_SEGMENT_OPEN");segments<<std::setprecision(17);
  segments<<"ordinal,start_time_s,end_time_s,measured_dt_s,dtheta_x,dtheta_y,dtheta_z,dvel_x,dvel_y,dvel_z,input_compensated\n";
  for(const auto& s:arc_imu_segments_) {segments<<s.ordinal<<','<<s.start_time<<','<<s.end_time<<','<<s.measured_dt;
    for(double x:s.dtheta) segments<<','<<x;for(double x:s.dvel) segments<<','<<x;segments<<','<<s.input_compensated<<'\n';}
  require(life.good() && ledger.good() && segments.good(),"ARC_COMMON_DIAGNOSTIC_WRITE");
  if(!arc_native_telemetry_enabled_) return;  // The sole arm-dependent branch, after all mathematics.
  std::ofstream out(dir/"ARC_JOINT_PRIORS.jsonl");require(out.good(),"ARC_PRIOR_OPEN");out<<std::setprecision(17);
  for(const auto& p:arc_joint_priors_) {
    out<<"{\"schema_version\":1,\"run_id\":";quoted(out,options_.run_id);
    out<<",\"arc_source_events_sha256\":";quoted(out,options_.arc_clone_config.events_sha256);
    out<<",\"arc_schedule_manifest_sha256\":";quoted(out,options_.arc_clone_config.manifest_sha256);
    out<<",\"source_time_scale_id\":";quoted(out,options_.arc_clone_config.source_time_scale_id);
    out<<",\"source_time_mapping_id\":";quoted(out,options_.arc_clone_config.time_mapping_source_id);
    out<<",\"pin_validation\":\"DECLARED_PINS_EXTERNAL_RUNNER_VERIFICATION_REQUIRED\",\"config_binary_provider_hash_binding\":\"EXTERNAL_SEALED_RUN_RECEIPT_REQUIRED\",\"start\":";event(out,p.start);
    out<<",\"end\":";event(out,p.end);out<<",\"start_state_time_s\":"<<p.start_state_time<<",\"end_state_time_s\":"<<p.end_state_time;
    out<<",\"conditioning_information_id\":";quoted(out,p.conditioning_information_id);
    out<<",\"conditioning_ordinal\":"<<p.conditioning_ordinal<<",\"start_update_ordinal\":"<<p.start_update_ordinal
       <<",\"end_update_ordinal\":"<<p.end_update_ordinal<<",\"start_reset_ordinal\":"<<p.start_reset_ordinal
       <<",\"end_reset_ordinal\":"<<p.end_reset_ordinal;
    out<<",\"dispatch_phase\":\"POST_ALL_EXISTING_UPDATES_AT_TIMESTAMP\",\"actual_available_time_s\":null,\"phase_state_cross\":\"UNKNOWN\""
       <<",\"error_order\":\"current21_P_V_PHI_BG_BA_SG_SA_then_ECEF_clone3\",\"error_units\":\"m_mps_rad_radps_mps2_dimensionless_dimensionless_rad\""
       <<",\"error_convention\":\"position_velocity_estimate_minus_true_attitude_and_clone_positive_left_truth_from_nominal_bias_scale_true_minus_nominal\""
       <<",\"prior_scope\":\"INHERITED_WORKING_MODEL_CONDITIONAL_ON_EXECUTED_PREFIX_NOT_CALIBRATED_TRUTH\"";
    out<<",\"start_P21\":";matrix(out,p.start_P21);out<<",\"J0\":";matrix(out,p.J0);
    out<<",\"start_C0\":";matrix3(out,p.start_C0);out<<",\"start_blh\":";vector(out,p.start_blh);
    out<<",\"P24\":";matrix(out,p.P24);out<<",\"dx24\":";vector(out,p.dx24);
    out<<",\"clone_C0_given_end\":";matrix3(out,p.clone_C0_given_end);out<<",\"current_cbn\":";matrix3(out,p.current_cbn);
    out<<",\"current_blh\":";vector(out,p.current_blh);out<<",\"current_C1\":";matrix3(out,p.current_C1);
    out<<",\"J1\":";matrix(out,p.J1);out<<",\"B6\":";matrix(out,p.B6);out<<",\"P6\":";matrix(out,p.P6);out<<"}\n";
  }
  require(out.good(),"ARC_PRIOR_WRITE");
}
}  // namespace legsa_v23_port_core
