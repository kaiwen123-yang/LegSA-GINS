// Synthetic ARC integration harness; production GIEngine dispatch/update/reset/writers.
// No raw data, references, phase model, integer solver, or navigation CLI replay.
#include "legsa_v23_port_core/factors/arc_source_events.hpp"
#include "legsa_v23_port_core/factors/attitude_clone.hpp"
#include "legsa_v23_port_core/kf_gins/gi_engine.hpp"
#include "legsa_v23_port_core/common/earth.hpp"
#include "legsa_v23_port_core/common/rotation.hpp"
#include "legsa_v23_port_core/fileio/file_saver.hpp"
#include "legsa_v23_port_core/config/port_config_loader.hpp"
#include <cmath>
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <limits>
#include <stdexcept>
#include <string>
#include <vector>
using namespace legsa_v23_port_core;
namespace ac=legsa_v23_port_core::attitude_clone;
void need(bool v,const char* m){if(!v)throw std::runtime_error(m);}
namespace legsa_v23_port_core {
struct ArcNativeTestAccess {
 static void event(GIEngine& e,const ArcSourceEvent& a){e.processArcSourceEvent(a);}
 static ac::Gaussian joint(const GIEngine& e){return e.attitudeJointState();}
 static Matrix3 clone(const GIEngine& e){return e.attitude_clone_cbe_;}
 static std::string owner(const GIEngine& e){return e.attitude_clone_owner_;}
 static void mean(GIEngine& e,const std::vector<double>& v){
  auto s=e.attitudeJointState();need(s.mean.size()==v.size(),"PROBE_MEAN_SHAPE");
  s.mean=v;e.setAttitudeJointState(s);
 }
 // Synthetic math probe only: reserve the already validated END for manual
 // dispatch after production update/reset. Automatic queue order is tested separately.
 static void reserveEndForMathProbe(GIEngine& e){
  need(e.next_arc_event_==1 && e.arc_events_.size()==2 && e.arc_events_[1].role=="END","PROBE_END_RESERVATION");
  e.next_arc_event_=2;
 }
 static void currentCovariance(GIEngine& e){e.setCovarianceMatrix(identityMatrix(21));}
 static void armClippedFeedback(GIEngine& e){
  quality_aware::QAFallbackConfig c;c.qa_active_mode=true;c.recovery_required_consecutive_a1=1;
  c.recovery_max_yaw_correction_deg=1.;
  quality_aware::QAFallbackSupervisor q(c);quality_aware::QAObservation o;
  o.time=1.;o.gnss_pos_available=true;q.evaluate(o);
  o.time=2.;o.a1_available=true;o.a1_relpos_diff_valid=true;q.evaluate(o);
  need(q.lastDecisionRecoveryRampActive(),"PROBE_RECOVERY_NOT_ARMED");
  e.qa_fallback_supervisor_=q;e.dx_[8]=.2;
 }
};
}
bool first=true;
void key(const char* k){if(!first)std::cout<<',';first=false;std::cout<<'"'<<k<<"\":";}
struct Object {bool outer;Object():outer(first){std::cout<<'{';first=true;}~Object(){std::cout<<'}';first=outer;}};
void val(double x){if(std::isfinite(x))std::cout<<x;else std::cout<<"null";}
void val(std::size_t x){std::cout<<x;}
void val(bool x){std::cout<<(x?"true":"false");}
void val(const std::string&s){std::cout<<'"';for(char c:s){if(c=='"'||c=='\\')std::cout<<'\\';if(c=='\n')std::cout<<"\\n";else std::cout<<c;}std::cout<<'"';}
void val(const Matrix&m){std::cout<<'[';for(std::size_t i=0;i<m.rows;++i){if(i)std::cout<<',';std::cout<<'[';for(std::size_t j=0;j<m.cols;++j){if(j)std::cout<<',';val(m(i,j));}std::cout<<']';}std::cout<<']';}
void val(const Matrix3&m){Matrix a(3,3);for(int i=0;i<3;++i)for(int j=0;j<3;++j)a(i,j)=m[i][j];val(a);}
void val(const Vec3&v){std::cout<<'[';for(int i=0;i<3;++i){if(i)std::cout<<',';val(v[i]);}std::cout<<']';}
void val(const ArcJointPrior&);
void val(const ArcLifecycleEvent&);
void val(const ArcConditioningEvent&);
void val(const ArcImuSegment&);
template<class T>void val(const std::vector<T>&v){std::cout<<'[';for(std::size_t i=0;i<v.size();++i){if(i)std::cout<<',';val(v[i]);}std::cout<<']';}
template<class T>void out(const char*k,const T&v){key(k);val(v);}
void val(const ArcJointPrior&p){Object x;
 out("block_id",p.start.block_id);out("start_time",p.start.source_time);out("end_time",p.end.source_time);
 out("information_id",p.conditioning_information_id);out("start_update",p.start_update_ordinal);out("end_update",p.end_update_ordinal);
 out("start_reset",p.start_reset_ordinal);out("end_reset",p.end_reset_ordinal);out("conditioning_ordinal",p.conditioning_ordinal);
 out("start_P21",p.start_P21);out("J0",p.J0);out("P24",p.P24);out("dx24",p.dx24);out("J1",p.J1);out("B6",p.B6);out("P6",p.P6);
 out("start_C0",p.start_C0);out("clone_C0",p.clone_C0_given_end);out("current_cbn",p.current_cbn);out("current_C1",p.current_C1);
 out("start_blh",p.start_blh);out("current_blh",p.current_blh);
}
void val(const ArcLifecycleEvent&e){Object x;
 out("block_id",e.start.block_id);out("start_id",e.start.endpoint_id);out("end_id",e.end.endpoint_id);
 out("status",e.status);out("owner",e.clone_owner);out("clone_created",e.clone_created);out("dispatch_phase",e.dispatch_phase);
 out("start_dispatch_phase",e.start_dispatch_phase);out("end_dispatch_phase",e.end_dispatch_phase);
 out("start_time",e.start.source_time);out("end_time",e.has_end?e.end.source_time:std::numeric_limits<double>::quiet_NaN());
 out("start_state_time",e.start_state_time);out("end_state_time",e.end_state_time);
 out("start_actual_available",e.start.actual_available_time);out("end_actual_available",e.end.actual_available_time);
 out("start_model",e.start.endpoint_model_fingerprint);out("end_model",e.end.endpoint_model_fingerprint);
 out("start_update",e.start_update_ordinal);out("end_update",e.end_update_ordinal);
 out("start_reset",e.start_reset_ordinal);out("end_reset",e.end_reset_ordinal);
 out("start_dispatch",e.start_dispatch_ordinal);out("end_dispatch",e.end_dispatch_ordinal);
 out("start_samples",e.start_state_sample_count);out("end_samples",e.end_state_sample_count);
}
void val(const ArcConditioningEvent&e){Object x;
 out("ordinal",e.ordinal);out("update_ordinal",e.update_ordinal);out("reset_ordinal",e.reset_ordinal);
 out("time",e.state_time);out("kind",e.kind);out("tag",e.source_tag);out("owner",e.clone_owner);
 out("block_id",e.block_id);out("provider_identity",e.provider_measurement_identity);
}
void val(const ArcImuSegment&s){Object x;
 out("ordinal",s.ordinal);out("start",s.start_time);out("end",s.end_time);out("dt",s.measured_dt);
 out("dtheta",s.dtheta);out("dvel",s.dvel);out("compensated",s.input_compensated);
}
PortOptions options(bool enabled=true,bool aids=false){
 PortOptions o;o.runtime_contract="research_experiment";o.starttime=1.;
 o.algorithm_id="ARC_NATIVE_SYNTHETIC";o.run_id="SYNTHETIC_EMPTY_PHASE_MODEL";
 o.disable_source_aware=true; // Keep the production ordinary branch and auxiliary scheduler.
 o.qa_fallback_config.enable_qa_fallback=false;o.qa_fallback_config.qa_active_mode=false;
 o.init_pos_std_m={.5,.6,.7};o.init_vel_std_mps={.1,.15,.2};o.init_att_std_rad={.1,.12,.14};
 o.init_imu_error_std.gyrbias={.01,.01,.01};o.init_imu_error_std.accbias={.02,.02,.02};
 o.init_imu_error_std.gyrscale={0,0,0};o.init_imu_error_std.accscale={0,0,0};
 o.imunoise.gyrscale_std={0,0,0};o.imunoise.accscale_std={0,0,0};
 o.antlever_m={.2,-.1,.05};
 auto& a=o.arc_clone_config;
 if(enabled){a.mode="NULL_ARC_DIAGNOSTIC";a.events_path="SYNTHETIC_SOURCE_ALREADY_IN_MEMORY";
  a.events_sha256=std::string(64,'a');a.manifest_sha256=std::string(64,'b');
  a.source_time_scale_id="GPS_WEEK_TOW__SAVED_LOCAL_BASE";a.time_mapping_source_id="SYNTHETIC_EXACT_LOCAL_MAPPING";
  a.availability_policy="source_time_replay_assumption";}
 if(aids){auto& v=o.go2_velocity_prior_diagnostic_config;
  v.enable_go2_velocity_prior_diagnostic=true;
  v.enable_go2_horizontal_velocity_prior=true;v.go2_horizontal_velocity_frame="body_frd";
  v.go2_body_velocity_update_period_s=.2;v.go2_horizontal_velocity_prior_source_aware_enabled=false;
  o.go2_attitude_prior_config.enable_go2_attitude_weak_prior=true;
  o.go2_attitude_prior_config.go2_attitude_prior_sourceaware=false;}
 return o;
}
NavState initial(){NavState s;s.time=1.;s.pos_blh_rad_m={.6,1.3,35.};s.vel_ned_mps={1.2,-.3,.1};s.euler_rad={.2,-.1,.3};return s;}
ArcSourceEvent arc(double t,const std::string& role,const std::string& block,std::size_t index,bool model=true){
 ArcSourceEvent e;e.sequence_id="SYNTHETIC";e.block_id=block;e.endpoint_id=block+"_"+role;
 e.role=role;e.source_time=e.replay_time=t;e.source_time_bits_hex=arcSourceTimeBits(t);e.epoch_index=index;
 if(model)e.endpoint_model_fingerprint=std::string(64,'c');return e;
}
std::vector<ArcSourceEvent> pair(double t0,double t1,std::string id="B0",std::size_t index=0,bool model=true){
 return {arc(t0,"START",id,index,model),arc(t1,"END",id,index+4,model)};
}
void initialize(GIEngine&e,const std::vector<ArcSourceEvent>& events={},bool set=true){
 if(set)e.setArcSourceEvents(events);e.initialize(initial());ImuData x;x.time=1.;x.dt=.01;e.addImuData(x,true);
}
ImuData measurement(const GIEngine&e,double time){
 ImuData x;x.time=time;x.dt=time-e.timestamp();
 x.dtheta={.001*x.dt,-.002*x.dt,.003*x.dt};x.dvel={0.,0.,-Earth::gravity(e.navState().pos_blh_rad_m)*x.dt};return x;
}
void step(GIEngine&e,double t,const std::vector<GnssData>& obs={}){
 auto x=measurement(e,t);e.addImuData(x);e.newImuProcessWithEvents(obs);
}
GnssData gnss(double t){
 GnssData g;g.time=t;g.isvalid=true;g.validity_explicit=true;g.has_position=true;g.has_velocity=true;g.has_yaw=false;
 g.blh_rad_m=add(initial().pos_blh_rad_m,multiply(Earth::DRi(initial().pos_blh_rad_m),Vec3{.3,-.2,.1}));
 g.std_ned_m={.2,.25,.3};g.vel_ned_mps={.9,-.2,.05};g.vel_std_mps={.1,.12,.2};return g;
}
void providers(GIEngine&e,bool mid=false){
 Go2VelocityDiagnosticPriorStatus vs;vs.solver_enabled=true;vs.controlled_activation=true;vs.provider_status="available";
 std::vector<Go2VelocityDiagnosticPriorMeasurement> velocities;
 for(double t:{1.2,1.6,2.}){Go2VelocityDiagnosticPriorMeasurement v;v.time=t;v.observation_frame="body_frd";
  v.velocity_body_frd_mps={.15,.08,0.};v.std_body_frd_mps={.25,.3,1.};v.source_status="active";v.quality_flag="nominal";v.diagnostic_only=false;
  velocities.push_back(v);}
 e.setGo2VelocityDiagnosticPriors(velocities,vs);
 Go2AttitudeWeakPriorStatus ps;ps.solver_enabled=true;ps.provider_status="available";
 std::vector<Go2AttitudeWeakPriorMeasurement> attitudes;
 for(double t:(mid?std::vector<double>{1.15,1.6,1.95}:std::vector<double>{1.2,1.6,2.})){
  Go2AttitudeWeakPriorMeasurement p;p.time=t;p.roll_rad=.22;p.pitch_rad=-.08;p.source_status="active";p.quality_flag="nominal";attitudes.push_back(p);}
 e.setGo2AttitudeWeakPriors(attitudes,ps);
}
void summary(const GIEngine&e){
 const auto&c=e.arcCloneCounts();out("source_rows",c.source_rows);out("source_blocks",c.source_blocks);out("event_rows",c.event_rows);
 out("starts",c.starts);out("ends",c.ends);out("retires",c.retires);out("covered",c.covered_blocks);
 out("uncovered_initial",c.uncovered_initial);out("uncovered_terminal",c.uncovered_terminal);
 out("ordinary",c.ordinary_updates);out("joint_updates",c.ordinary_joint_updates);out("resets",c.full_resets);
 out("phase_updates",c.phase_updates);out("foot_updates",e.attitudeCloneCounts().pair_updates);out("foot_attempts",e.attitudeCloneCounts().ends);
 out("GNSS",e.updateCount());out("RP",e.go2AttitudeWeakPriorUpdateCount());out("HV",e.go2VelocityDiagnosticPriorUpdateCount());
 out("RD",e.rawDopplerUpdateCount());out("SA",e.sourceAwareEvaluationCount());
 out("active",e.attitudeCloneActive());out("owner",ArcNativeTestAccess::owner(e));out("time",e.timestamp());
 out("P",e.jointAttitudeCovariance());out("lifecycle",e.arcLifecycleEvents());out("conditioning",e.arcConditioningEvents());
 out("segments",e.arcImuSegments());out("priors",e.arcJointPriors());
}
void writers(GIEngine&e,PortOptions o,const std::string&dir,const std::vector<NavState>& nav,
             const std::vector<std::vector<double>>& cov){
 std::filesystem::create_directories(dir);FileSaver::writeExactCompatible(dir,nav,cov);
 e.writeArcCloneDiagnostics(dir);e.writeHeadingSourceDiagnostics(dir);e.writeBodyVelocityDiagnostics(dir);
 e.writeSourceAwareTrace(dir);e.writeQAFallbackTrace(dir);
 o.arc_clone_counts=e.arcCloneCounts();o.arc_native_telemetry_enabled=e.arcNativeTelemetryEnabled();o.heading_source_counts=e.headingSourceCounts();FileSaver::writeRunManifest(dir,o);
}
void ordering(const std::string&dir,bool mid,bool heading_identity=false){
 auto o=options(true,true);
 if(heading_identity){
  o.heading_source_policy="pvt_priority_control";o.baseline3d_source="external_carrier";
  o.dual_antenna_measurement_model="baseline3d";o.dual_yaw_prediction_model="euler_yaw";
  o.baseline3d_length_m=.5;o.enable_dual_yaw_update=true;o.yaw_scheme_C_enabled=true;
 }
 GIEngine e(o);
 auto events=pair(mid?1.15:1.2,mid?1.95:2.);initialize(e,events);providers(e,mid);
 std::vector<NavState> nav;std::vector<std::vector<double>> cov;
 for(int k=0;k<3;++k){double end=std::vector<double>{1.2,1.6,2.}[k];
  double gt=mid?(k==0?1.15:k==2?1.95:1.6):end;
  auto observation=gnss(gt);
   if(heading_identity){
    observation.pvt_heading_source_present=true;observation.auxiliary_updates_allowed=true;
    observation.has_yaw=true;observation.yaw_rad=.3;observation.yaw_deg=.3*R2D;
    observation.yaw_std_rad=.05;observation.yaw_std_deg=.05*R2D;
   }
   step(e,end,{observation});nav.push_back(e.getNavState());cov.push_back(e.getCovariance());}
 e.finalizeArcSourceStream();summary(e);out("samples",nav.size());writers(e,o,dir,nav,cov);
}
void mapping(const std::string&dir){
 auto o=options();
 // This FD fixture explicitly permits all 24 directions. Frozen-scale guards
 // have their own zero-scale fixture; perturbing frozen states would be invalid.
 o.init_imu_error_std.gyrscale={.001,.001,.001};o.init_imu_error_std.accscale={.001,.001,.001};
 GIEngine e(o);initialize(e,pair(1.1,1.9,"MAPPING"));step(e,1.1);
 ArcNativeTestAccess::reserveEndForMathProbe(e);step(e,1.9);
 Matrix h(3,21,0.);h(0,0)=1.;h(0,6)=.3;h(1,1)=1.;h(1,7)=-.2;h(2,3)=1.;h(2,8)=.4;
 Matrix r(3,3,0.);r(0,0)=.003;r(1,1)=.004;r(2,2)=.005;std::vector<double> z{.02,-.03,.015};
 out("before_update_P",e.jointAttitudeCovariance());out("before_update_mean",ArcNativeTestAccess::joint(e).mean);
 out("H21",h);out("R",r);out("z",z);
 e.EKFUpdate(z,h,r);out("after_update_P",e.jointAttitudeCovariance());out("after_update_mean",ArcNativeTestAccess::joint(e).mean);
 out("before_feedback_blh",e.navState().pos_blh_rad_m);
 e.stateFeedback();out("after_feedback_P",e.jointAttitudeCovariance());out("after_feedback_mean",ArcNativeTestAccess::joint(e).mean);
 out("after_feedback_blh",e.navState().pos_blh_rad_m);
 // Each probe copies the actual production state after feedback. Only dx24 is
 // perturbed; production stateFeedback performs both physical pose retractions.
 const GIEngine frozen=e;std::vector<Matrix3> clone_plus,clone_minus,current_plus,current_minus;
 std::vector<double> steps;
 for(int k=0;k<24;++k){double hstep=k<3?.01:1e-7;steps.push_back(hstep);
  for(int sign:{1,-1}){GIEngine probe=frozen;std::vector<double> dx(24,0.);dx[k]=sign*hstep;
   ArcNativeTestAccess::mean(probe,dx);probe.stateFeedback();
   auto cc=ArcNativeTestAccess::clone(probe);auto c1=multiply(Earth::cne(probe.navState().pos_blh_rad_m),probe.navState().cbn);
   (sign==1?clone_plus:clone_minus).push_back(cc);(sign==1?current_plus:current_minus).push_back(c1);}}
 out("fd_steps",steps);out("clone_plus",clone_plus);out("clone_minus",clone_minus);out("current_plus",current_plus);out("current_minus",current_minus);
 ArcNativeTestAccess::event(e,arc(1.9,"END","MAPPING",4));e.finalizeArcSourceStream();summary(e);
 std::filesystem::create_directories(dir);e.writeArcCloneDiagnostics(dir);
}
void guards(){
 auto base=options();auto rejected=[](PortOptions o){try{GIEngine e(o);return std::string();}catch(const std::exception& e){return std::string(e.what());}};
 auto both=base;both.attitude_clone_config.mode="NULL_CLONE";both.attitude_clone_config.events_path="SYNTHETIC_FOOT";
 both.attitude_clone_config.position_source_id="SYNTHETIC_POS";
 both.attitude_clone_config.covariance_source_id="SYNTHETIC_COV";
 both.attitude_clone_config.covariance_assumption="SYNTHETIC_FULL_SIGMA";
 both.attitude_clone_config.frame_source_id="SYNTHETIC_FRD";
 both.attitude_clone_config.position_gnss_input_status="unknown";
 both.attitude_clone_config.availability_policy="source_time_replay_assumption";
 both.attitude_clone_config.foot_frd_to_engine_body=identityMatrix3();
 out("foot_arc_rejected",rejected(both));
 auto qa=base;qa.qa_fallback_config.enable_qa_fallback=true;out("qa_rejected",rejected(qa));
 auto qm=base;qm.quality_state_manager_config.enable_multi_state_qm=true;out("qm_rejected",rejected(qm));
 GIEngine e(base);initialize(e,pair(1.1,1.9));bool covariance=false;
 try{ArcNativeTestAccess::currentCovariance(e);}catch(const std::exception&){covariance=true;}out("current_covariance_rejected",covariance);
 step(e,1.1);Matrix h(1,21,0.);h(0,6)=1.;e.EKFUpdate({.01},h,scale(identityMatrix(1),.1));e.stateFeedback();
 out("frozen_joint_P",e.jointAttitudeCovariance());out("scale",e.navState().imu_error.gyrscale);
 ArcNativeTestAccess::armClippedFeedback(e);bool clipped=false;try{e.stateFeedback();}catch(const std::exception&){clipped=true;}
 out("clipped_feedback_rejected",clipped);
}
int main(int argc,char**argv){
 try{need(argc>=3,"operation/path required");std::cout<<std::setprecision(17);{
  Object root;std::string op=argv[1],path=argv[2];
  if(op=="read"){
   auto c=options().arc_clone_config;c.events_path=path;if(argc>3)c.events_sha256=argv[3];
   auto rows=readArcSourceEvents(c);out("rows",rows.size());std::vector<double> times;bool na=true;
   for(const auto&e:rows){times.push_back(e.source_time);na=na&&std::isnan(e.actual_available_time)&&e.source_time_bits_hex==arcSourceTimeBits(e.source_time);}
   out("times",times);out("all_actual_NA_and_bits_match",na);
  }else if(op=="bad_time_scale"||op=="bad_manifest"){
   auto c=options().arc_clone_config;if(op=="bad_time_scale")c.source_time_scale_id="UNKNOWN";else c.manifest_sha256.clear();
   validateArcCloneConfig(c,"research_experiment");out("incorrectly_accepted",true);
  }else if(op=="off"){
   auto o=options(false);o.arc_clone_config.events_path="THIS_PATH_MUST_NOT_BE_OPENED";
   bool offread=false;try{readArcSourceEvents(o.arc_clone_config);}catch(const std::exception&e){offread=std::string(e.what())=="ARC_OFF_INPUT_READ_FORBIDDEN";}
    out("off_read_rejected",offread);
   GIEngine x(options(false)),y(options(false));initialize(x,{},false);initialize(y,{},false);step(x,1.2);step(y,1.2);
   out("legacy_equal",x.getCovariance()==y.getCovariance()&&x.navState().euler_rad==y.navState().euler_rad);
   x.writeArcCloneDiagnostics(path);out("default_off",PortOptions{}.arc_clone_config.mode=="off");out("P_shape",x.jointAttitudeCovariance().rows);
  }else if(op=="lifecycle"){
   GIEngine e(options());auto a=pair(1.1,1.9,"B0",0,true),b=pair(2.1,2.9,"B1",5,false);a.insert(a.end(),b.begin(),b.end());
   initialize(e,a);step(e,1.9);step(e,2.9);e.finalizeArcSourceStream();summary(e);std::filesystem::create_directories(path);e.writeArcCloneDiagnostics(path);
  }else if(op=="split"){
   GIEngine e(options());const double a=1.123456789012345,b=1.923456741328716;
   initialize(e,pair(a,b));ImuData x;x.time=2.;x.dt=.9375;x.dtheta={.03,-.02,.04};x.dvel={.4,-.2,-8.4};
   out("input_dt",x.dt);out("input_dtheta",x.dtheta);out("input_dvel",x.dvel);
   e.addImuData(x);e.newImuProcessWithEvents({});e.finalizeArcSourceStream();summary(e);
  }else if(op=="ordering_mid"||op=="ordering_end"||op=="identity"){ordering(path,op=="ordering_mid",op=="identity");}
  else if(op=="mapping"){mapping(path);}
  else if(op=="guards"){guards();}
  else if(op=="initial"||op=="terminal"||op=="missing_end"){
   GIEngine e(options());auto events=pair(op=="initial"?.8:1.2,op=="initial"?1.6:3.);
   if(op=="missing_end")events.pop_back();initialize(e,events);step(e,op=="initial"?1.8:1.5);
   auto before=e.getCovariance();auto nav=e.getNavState();auto count=e.propagationCount();e.finalizeArcSourceStream();
   out("cleanup_unchanged",before==e.getCovariance()&&nav.euler_rad==e.navState().euler_rad&&nav.time==e.navState().time&&count==e.propagationCount());
   summary(e);std::filesystem::create_directories(path);e.writeArcCloneDiagnostics(path);
  }else if(op=="duplicate"||op=="unordered"||op=="mismatch"||op=="overlap"){
   auto events=pair(1.2,2.);if(op=="duplicate")events.insert(events.begin(),events.front());
   if(op=="unordered")std::swap(events[0],events[1]);if(op=="mismatch")events[1].block_id="OTHER";
   if(op=="overlap"){auto second=pair(1.3,2.1,"B1",5);events.insert(events.begin()+1,second[0]);events.push_back(second[1]);}
   validateArcSourceEvents(events);out("incorrectly_accepted",true);
  }else throw std::runtime_error("unknown harness operation");
 }std::cout<<'\n';return 0;
 }catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 2;}
}
