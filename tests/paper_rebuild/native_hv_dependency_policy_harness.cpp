// Registered synthetic-only qualification: eight fixed modes. No real providers.
#include "legsa_v23_port_core/kf_gins/gi_engine.hpp"
#include "legsa_v23_port_core/config/port_config_loader.hpp"
#include "legsa_v23_port_core/factors/go2_weak_prior_loader.hpp"
#include "legsa_v23_port_core/fileio/file_saver.hpp"
#include <cmath>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <limits>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>
using namespace legsa_v23_port_core;
constexpr const char* POLICY="causal_recorded_dependencies_unique_latest";
constexpr const char* SCHEMA="HV_CALIBRATED_GNSS18_TIME_V1";
void need(bool value,const char* reason){if(!value)throw std::runtime_error(reason);}
struct Calls {
 std::size_t config_loaders=0,provider_loaders=0,initializes=0,setters=0;
 std::size_t direct_ned=0,exact_steps=0,legacy_steps=0,feedbacks=0;
} calls;
namespace legsa_v23_port_core {
struct NedHvSourceTestAccess {
 static void apply(GIEngine& e,double trigger,double state){
  // Deliberately isolated selector probe. Real scheduling is tested below.
  e.timestamp_=state;e.pvacur_.time=state;e.applyGo2VelocityDiagnosticPriorForTime(trigger);
 }
};
}
PortOptions options(const std::string& policy=POLICY){
 PortOptions o;o.runtime_contract="research_experiment";o.starttime=1.;o.algorithm_id="HV_DEPENDENCY_SYNTHETIC";
 o.enable_receiver_velocity_update=false;o.enable_dual_yaw_update=false;o.disable_source_aware=true;
 o.init_pos_std_m={.5,.6,.7};o.init_vel_std_mps={.1,.15,.2};o.init_att_std_rad={.1,.12,.14};
 o.init_imu_error_std.gyrscale={0,0,0};o.init_imu_error_std.accscale={0,0,0};
 o.imunoise.gyrscale_std={0,0,0};o.imunoise.accscale_std={0,0,0};
 auto& c=o.go2_velocity_prior_diagnostic_config;c.enable_go2_velocity_prior_diagnostic=true;
 c.enable_go2_horizontal_velocity_prior=true;c.go2_horizontal_velocity_frame="ned";
 c.go2_horizontal_velocity_prior_source_aware_enabled=false;c.go2_velocity_prior_time_policy=policy;
 need(c.go2_velocity_prior_time_tolerance_sec==.08,"inherited tolerance changed");return o;
}
NavState initial(){NavState s;s.time=1.;s.pos_blh_rad_m={.6,1.3,35.};s.vel_ned_mps={1.2,-.3,.1};s.euler_rad={.2,-.1,.3};return s;}
void initialize(GIEngine& e){++calls.initializes;e.initialize(initial());ImuData i;i.time=1.;i.dt=.01;e.addImuData(i,true);}
Go2VelocityDiagnosticPriorMeasurement row(double t,std::size_t index,double ready){
 Go2VelocityDiagnosticPriorMeasurement r;r.time=t;r.source_status="active";r.quality_flag="nominal";
 r.velocity_ned_mps={.8,.1,0};r.std_ned_mps={.2,.3,999};
 r.dependency_schema=SCHEMA;r.dependency_metadata_available=true;r.dependency_supported=true;
 r.dependency_source_row_index=index;r.dependency_source_time_bits_hex=arcSourceTimeBits(t);
 r.dependency_ready_source_time_s=ready;return r;
}
void attach(GIEngine& e,const std::vector<Go2VelocityDiagnosticPriorMeasurement>& rows){
 ++calls.setters;Go2VelocityDiagnosticPriorStatus s;s.solver_enabled=true;s.provider_status="available";
 e.setGo2VelocityDiagnosticPriors(rows,s);
}
void apply(GIEngine& e,double trigger,double state){++calls.direct_ned;NedHvSourceTestAccess::apply(e,trigger,state);}
void apply(GIEngine& e,double t){apply(e,t,t);}
void feedback(GIEngine& e){++calls.feedbacks;e.stateFeedback();}
const NedVelocitySourceEvent& last(const GIEngine& e){need(!e.nedVelocitySourceEvents().empty(),"missing decision");return e.nedVelocitySourceEvents().back();}
void exactStep(GIEngine& e,double t,const std::vector<GnssData>& g){
 ++calls.exact_steps;ImuData i;i.time=t;i.dt=.01;i.dvel={0,0,-.098};e.addImuData(i);e.newImuProcessWithEvents(g);
}
void legacyStep(GIEngine& e,double t,GnssData g){
 ++calls.legacy_steps;ImuData i;i.time=t;i.dt=.01;i.dvel={0,0,-.098};e.addImuData(i);e.addGnssData(g);e.newImuProcess();
}
GnssData gnss(double t){
 GnssData g;g.time=t;g.isvalid=true;g.validity_explicit=true;g.has_position=true;g.has_velocity=false;g.has_yaw=false;
 g.blh_rad_m=initial().pos_blh_rad_m;g.std_ned_m={1.,1.,1.};return g;
}
template<class F>void rejects(F f,const std::string& token){
 bool caught=false;try{f();}catch(const std::exception& e){caught=true;need(std::string(e.what()).find(token)!=std::string::npos,"wrong rejection reason");}
 need(caught,"required rejection absent");
}
std::string content(const std::filesystem::path& p){
 std::ifstream f(p,std::ios::binary);need(f.good(),"missing synthetic output");return std::string(std::istreambuf_iterator<char>(f),{});
}
void write(const std::filesystem::path& p,const std::string& s){std::ofstream f(p);f<<s;need(f.good(),"synthetic fixture write failed");}
std::string number(double x){std::ostringstream s;s<<std::setprecision(17)<<x;return s.str();}
void sameFiles(const std::filesystem::path& a,const std::filesystem::path& b){
 std::size_t na=0,nb=0;for(const auto& e:std::filesystem::directory_iterator(a)){
  ++na;need(content(e.path())==content(b/e.path().filename()),"paired output bytes differ");
 }
 for(const auto& e:std::filesystem::directory_iterator(b)){(void)e;++nb;}need(na==nb,"paired output file set differs");
}
void save(GIEngine& e,PortOptions o,const std::filesystem::path& out){
 std::filesystem::create_directories(out);
 FileSaver::writeExactCompatible(out.string(),{e.navState()},{e.getCovariance()});
 e.writeNedVelocitySourceDiagnostics(out.string());e.writeBodyVelocityDiagnostics(out.string());e.writeHeadingSourceDiagnostics(out.string());
 o.go2_velocity_prior_diagnostic_status=e.go2VelocityDiagnosticPriorStatus();FileSaver::writeRunManifest(out.string(),o);
}
const std::string BASE_HEADER="time,vn,ve,vd,std_vn,std_ve,std_vd,source_status,quality_flag,update_flag";
const std::string DEP_HEADER="dependency_schema,dependency_source_row_index,dependency_source_time_bits_hex,dependency_supported,dependency_ready_source_time_s";
std::string base(double t){return number(t)+",0.8,0.1,0,0.2,0.3,999,active,nominal,1";}
std::string dep(double t,std::size_t i,double ready){return std::string(SCHEMA)+","+std::to_string(i)+","+arcSourceTimeBits(t)+",1,"+number(ready);}
std::string csv(const std::string& tail){return BASE_HEADER+","+DEP_HEADER+"\n"+base(1.04)+","+tail+"\n";}
Go2VelocityDiagnosticPriorLoadResult loadCsv(const std::filesystem::path& p,const std::string& text,const PortOptions& o){
 write(p,text);++calls.provider_loaders;return Go2WeakPriorLoader::loadVelocityDiagnosticCsv(p.string(),o.go2_velocity_prior_diagnostic_config);
}
PortOptions loadConfig(const std::filesystem::path& p,const std::string& extra=""){
 const std::string s="runtime_contract: research_experiment\nstage_id: HV_DEPENDENCY_LOCAL\nprotocol_id: SYNTHETIC_ONLY\ncase_id: SYNTHETIC_ONLY\nrun_id: HV_DEPENDENCY\nrun_label: HV_DEPENDENCY\ndata_mode: synthetic_local_fixture\nalgorithm_id: AB0001\ncommon_initialization: true\ncommon_initialization_dual_yaw_used: true\ncommon_initialization_source: synthetic_declared_initializer\nenable_dual_yaw: true\nenable_receiver_velocity: true\nenable_raw_doppler: false\nenable_source_aware: false\nenable_go2_roll_pitch_prior: false\nenable_go2_horizontal_velocity_prior: true\ngo2_position_truth_claim: false\ngo2_velocity_truth_claim: false\ngo2_yaw_truth_claim: false\ngo2_contact_truth_claim: false\ngo2_velocity_prior_time_policy: "+std::string(POLICY)+"\n";
 write(p,s+extra);++calls.config_loaders;return PortConfigLoader::loadYamlLike(p.string());
}
void identity(const std::filesystem::path& out){
 auto parsed=loadConfig(out/"new_mode.yaml");need(parsed.go2_velocity_prior_diagnostic_config.go2_velocity_prior_time_policy==POLICY,"new config mode lost");
 rejects([&]{loadConfig(out/"body_invalid.yaml","go2_horizontal_velocity_frame: body_frd\n");},"NED_HV_CAUSAL_POLICY_REQUIRES_RESEARCH_HORIZONTAL_NED");
 auto o=options();GIEngine e(o);initialize(e);
 // Blank physical lines do not consume a native vector index. Missing/unknown
 // metadata and unsupported rows remain present and cannot default ready to zero.
 std::string rows=BASE_HEADER+","+DEP_HEADER+"\n"+base(1.01)+",,,,,\n\n"+base(1.02)+",UNKNOWN_SCHEMA,garbage,bad,wrong,bad\n"+
  base(1.03)+","+SCHEMA+",2,"+arcSourceTimeBits(1.03)+",0,\n"+base(1.04)+","+dep(1.04,3,1.05)+"\n";
 auto loaded=loadCsv(out/"mixed.csv",rows,o);
 need(loaded.measurements.size()==4&&loaded.measurements[2].dependency_source_row_index==2,"native physical row index drift");
 need(!loaded.measurements[0].dependency_metadata_available&&!loaded.measurements[1].dependency_metadata_available,"unknown metadata became available");
 need(loaded.measurements[2].dependency_metadata_available&&!loaded.measurements[2].dependency_supported,"unsupported declaration lost");
 need(loaded.measurements[3].velocity_ned_mps==row(1.04,3,1.05).velocity_ned_mps,"metadata modified source values");
 attach(e,{loaded.measurements[0],loaded.measurements[1],loaded.measurements[2]});apply(e,1.05);
 need(!last(e).source_present&&!last(e).consumed&&last(e).dependency_missing_candidate_skips==2&&last(e).dependency_unsupported_candidate_skips==1,"unavailable dependencies consumed or defaulted ready");
 attach(e,loaded.measurements);apply(e,1.05);
 need(last(e).accepted&&last(e).vector_index==3&&last(e).dependency_missing_candidate_skips==2&&last(e).dependency_unsupported_candidate_skips==1,"metadata eligibility accounting");
 need(last(e).selected_dependency_schema==SCHEMA&&last(e).selected_dependency_ready_source_time_s==1.05,"selected dependency identity lost");
 const std::string prefix=std::string(SCHEMA)+",0,"+arcSourceTimeBits(1.04)+",";
 struct Bad {std::string tail,reason;};
 const std::vector<Bad> bad={
  {std::string(SCHEMA)+",x,"+arcSourceTimeBits(1.04)+",1,1.05","ROW_INDEX_INVALID"},
  {dep(1.04,1,1.05),"ROW_INDEX_MISMATCH"},
  {std::string(SCHEMA)+",0,xyz,1,1.05","SOURCE_TIME_BITS_INVALID"},
  {std::string(SCHEMA)+",0,"+arcSourceTimeBits(1.03)+",1,1.05","SOURCE_TIME_BITS_MISMATCH"},
  {prefix+"true,1.05","SUPPORTED_INVALID"},
  {prefix+"1,","READY_INVALID"},{prefix+"1,nan","READY_INVALID"},{prefix+"1,inf","READY_INVALID"},
  {prefix+"1,1.05trailing","READY_INVALID"},{prefix+"1,1.03","READY_INVALID"},
  {prefix+"0,1.05","UNSUPPORTED_READY_MUST_BE_EMPTY"}
 };
 for(std::size_t i=0;i<bad.size();++i)rejects([&]{loadCsv(out/("malformed_"+std::to_string(i)+".csv"),csv(bad[i].tail),o);},"NED_HV_DEPENDENCY_"+bad[i].reason);
 rejects([&]{loadCsv(out/"missing_field.csv",BASE_HEADER+",dependency_schema\n"+base(1.04)+","+SCHEMA+"\n",o);},"NED_HV_DEPENDENCY_FIELD_MISSING");
 rejects([&]{loadCsv(out/"width.csv",csv(dep(1.04,0,1.05)).substr(0,csv(dep(1.04,0,1.05)).size()-1)+",extra\n",o);},"NED_HV_DEPENDENCY_KNOWN_SCHEMA_ROW_WIDTH_MISMATCH");
 rejects([&]{loadCsv(out/"duplicate.csv",BASE_HEADER+","+DEP_HEADER+",time\n"+base(1.04)+","+dep(1.04,0,1.05)+",1.04\n",o);},"NED_HV_DEPENDENCY_DUPLICATE_OR_EMPTY_HEADER");
 for(int i=0;i<6;++i){
  auto broken=row(1.06,0,1.06);std::string reason;
  if(i==0){broken.dependency_metadata_available=false;reason="SCHEMA_STATE_MISMATCH";}
  if(i==1){broken.dependency_source_row_index=1;reason="ROW_INDEX_MISMATCH";}
  if(i==2){broken.dependency_source_time_bits_hex=arcSourceTimeBits(1.05);reason="SOURCE_TIME_BITS_MISMATCH";}
  if(i==3){broken.dependency_ready_source_time_s=std::numeric_limits<double>::quiet_NaN();reason="READY_INVALID";}
  if(i==4){broken.dependency_ready_source_time_s=1.05;reason="READY_INVALID";}
  if(i==5){broken.dependency_schema="UNKNOWN_SCHEMA";reason="SCHEMA_STATE_MISMATCH";}
  rejects([&]{attach(e,{broken});},"NED_HV_DEPENDENCY_"+reason);
 }
 save(e,o,out/"decisions");
}
void clocks(const std::filesystem::path& out){
 auto o=options();GIEngine e(o);initialize(e);attach(e,{row(1.04,0,1.05)});
 const double before=std::nextafter(1.05,-std::numeric_limits<double>::infinity());
 apply(e,1.05,before);need(!last(e).consumed&&last(e).dependency_future_state_candidate_skips==1&&last(e).dependency_future_trigger_candidate_skips==0,"state clock dependency gate failed");
 apply(e,before,1.05);need(!last(e).consumed&&last(e).dependency_future_trigger_candidate_skips==1&&last(e).dependency_future_state_candidate_skips==0,"trigger clock dependency gate failed");
 apply(e,1.05);need(last(e).accepted&&last(e).consumed,"equal ready/trigger/state should be eligible");
 GIEngine next(o);initialize(next);const double after=std::nextafter(1.05,std::numeric_limits<double>::infinity());
 attach(next,{row(1.04,0,after)});apply(next,1.05);
 need(!last(next).consumed&&last(next).dependency_future_candidate_skips==1&&last(next).dependency_future_trigger_candidate_skips==1&&last(next).dependency_future_state_candidate_skips==1,"one ULP dependency lead admitted");
 apply(next,after);need(last(next).accepted,"waiting dependency was consumed before readiness");
 save(e,o,out/"dual_clock");save(next,o,out/"one_ulp");
}
void expiry(const std::filesystem::path& out){
 auto o=options();GIEngine wait(o);initialize(wait);attach(wait,{row(1.,0,1.02)});
 apply(wait,1.01);need(!last(wait).consumed,"waiting consumed");apply(wait,1.02);need(last(wait).accepted,"ready within original age not accepted");
 GIEngine expired(o);initialize(expired);attach(expired,{row(1.,0,1.125)});
 apply(expired,1.04);need(last(expired).dependency_future_candidate_skips==1&&!last(expired).consumed,"expiry fixture did not first wait");
 apply(expired,1.125);need(!last(expired).source_present&&!last(expired).consumed&&expired.go2VelocityDiagnosticPriorUpdateCount()==0,"readiness extended old source tolerance");
 // A binary-exact tolerance boundary avoids confusing decimal subtraction with
 // an inclusive comparison. Default .08 remains unchanged in all other probes.
 auto b=o;b.go2_velocity_prior_diagnostic_config.go2_velocity_prior_time_tolerance_sec=.125;
 GIEngine boundary(b);initialize(boundary);attach(boundary,{row(.875,0,1.)});apply(boundary,1.);
 need(last(boundary).accepted,"inclusive source-age boundary failed");
 save(wait,o,out/"wait");save(expired,o,out/"expired");save(boundary,b,out/"boundary");
}
void selection(const std::filesystem::path& out){
 auto o=options();GIEngine e(o);initialize(e);auto disabled=row(1.049,4,1.049);disabled.update_flag=false;
 auto missing=row(1.048,5,1.048);missing.dependency_schema="";missing.dependency_metadata_available=false;
 attach(e,{row(1.03,0,1.04),row(1.04,1,1.05),row(1.04,2,1.05),row(1.045,3,1.08),disabled,missing});
 apply(e,1.05);need(last(e).accepted&&last(e).vector_index==2&&last(e).dependency_future_candidate_skips==1,"latest among ready rows/tie failed");
 apply(e,1.06);need(!last(e).source_present&&last(e).used_or_older_candidate_skips==3,"older row replayed while latest unready");
 apply(e,1.08);need(last(e).accepted&&last(e).vector_index==3&&e.go2VelocityDiagnosticPriorUpdateCount()==2,"newly ready latest failed");
 save(e,o,out/"selection");
}
void watermark(const std::filesystem::path& out){
 auto o=options();GIEngine e(o);initialize(e);
 attach(e,{row(1.04,0,1.05),row(1.04,1,1.07),row(1.03,2,1.07),row(1.06,3,1.075)});
 apply(e,1.05);need(last(e).accepted&&last(e).vector_index==0,"ready duplicate selection failed");
 apply(e,1.07);need(!last(e).source_present&&last(e).used_or_older_candidate_skips==3,"late-ready duplicate/older source revived");
 apply(e,1.075);need(last(e).accepted&&last(e).vector_index==3&&e.go2VelocityDiagnosticPriorUpdateCount()==2,"watermark blocked truly newer source");
 save(e,o,out/"watermark");
}
void rejection(const std::filesystem::path& out){
 auto o=options();GIEngine e(o);initialize(e);auto invalid=row(1.04,1,1.05);invalid.source_status="inactive";
 attach(e,{row(1.03,0,1.05),invalid,row(1.06,2,1.065)});apply(e,1.05);
 need(last(e).source_present&&last(e).vector_index==1&&last(e).consumed&&!last(e).accepted&&e.go2VelocityDiagnosticPriorRejectCount()==1,"provider rejection not consumed");
 apply(e,1.055);need(!last(e).source_present&&e.go2VelocityDiagnosticPriorRejectCount()==1&&e.go2VelocityDiagnosticPriorUpdateCount()==0,"provider reject refunded/fell back");
 apply(e,1.065);need(last(e).accepted&&last(e).vector_index==2,"new source did not recover after provider rejection");
 auto w=o;w.disable_source_aware=false;w.go2_velocity_prior_diagnostic_config.go2_horizontal_velocity_prior_source_aware_enabled=true;
 w.source_aware_policy_config.enable_source_aware_weighting=true;w.source_aware_policy_config.source_aware_mode="lsim_oim";w.source_aware_policy_config.source_aware_reject_extreme=true;
 GIEngine weighted(w);initialize(weighted);auto huge=row(1.04,0,1.05);huge.velocity_ned_mps={1e6,1e6,0};attach(weighted,{huge});
 apply(weighted,1.05);need(last(weighted).reason=="source_aware_reject"&&last(weighted).consumed&&weighted.sourceAwareEvaluationCount()==1,"real SA rejection not reached");
 apply(weighted,1.055);need(!last(weighted).source_present&&weighted.sourceAwareEvaluationCount()==1&&weighted.go2VelocityDiagnosticPriorUpdateCount()==0,"SA rejection retried");
 save(e,o,out/"provider");save(weighted,w,out/"source_aware");
}
void generation(const std::filesystem::path& out){
 auto o=options();GIEngine e(o);initialize(e);attach(e,{row(1.04,0,1.04),row(1.07,1,1.07)});
 apply(e,1.05);const auto generation0=last(e).generation;feedback(e);apply(e,1.055);
 need(!last(e).source_present&&last(e).generation==generation0,"feedback reset consumed source");
 auto bad=row(1.06,0,1.06);bad.dependency_source_time_bits_hex=arcSourceTimeBits(1.04);
 rejects([&]{attach(e,{bad});},"NED_HV_DEPENDENCY_SOURCE_TIME_BITS_MISMATCH");
 apply(e,1.08);need(last(e).accepted&&last(e).vector_index==1&&last(e).generation==generation0,"failed setter mutated source/generation");
 initialize(e);apply(e,1.05);
 need(last(e).accepted&&last(e).generation==generation0+1&&e.go2VelocityDiagnosticPriorUpdateCount()==3,"initialize generation reset failed");
 auto replacement=row(1.04,0,1.04);replacement.velocity_ned_mps={.4,.2,0};attach(e,{replacement});apply(e,1.05);
 need(last(e).accepted&&last(e).generation==generation0+2&&e.go2VelocityDiagnosticPriorUpdateCount()==1,"explicit replacement generation failed");
 const auto counts=e.go2VelocityDiagnosticPriorStatus().ned_time_policy_counts;
 need(counts.selected_attempts==4&&counts.generations==4,"cumulative generation counts wrong");save(e,o,out/"generation");
}
ArcSourceEvent arc(double t,const std::string& role){
 ArcSourceEvent e;e.sequence_id="SYNTHETIC";e.block_id="SYNTHETIC:BLOCK:0";e.endpoint_id=role;e.role=role;
 e.source_time=e.replay_time=t;e.source_time_bits_hex=arcSourceTimeBits(t);e.epoch_index=role=="START"?0:4;return e;
}
PortOptions arcOptions(const std::string& policy){
 auto o=options(policy);auto& a=o.arc_clone_config;a.mode="NULL_ARC_DIAGNOSTIC";a.events_path="SYNTHETIC_IN_MEMORY_ARC";
 a.events_sha256=std::string(64,'a');a.manifest_sha256=std::string(64,'b');a.source_time_scale_id="SYNTHETIC_EXACT_TIME";
 a.time_mapping_source_id="SYNTHETIC_IDENTITY";a.availability_policy="source_time_replay_assumption";return o;
}
void setArc(GIEngine& e){e.setArcSourceEvents({arc(1.002,"START"),arc(1.009,"END")});}
void checkExactLedger(const GIEngine& e,const std::vector<double>& expected_times,const std::vector<double>& expected_sources){
 std::size_t hv=0;bool end=false;std::size_t last_hv_ordinal=0;
 for(const auto& event:e.arcConditioningEvents()){
  if(event.source_tag=="GO2_VELOCITY_DIAGNOSTIC"){
   need(hv<expected_times.size()&&event.state_time==expected_times[hv],"wrong accepted-HV ledger time");
   need(event.provider_measurement_identity=="SOURCE_TIME_BITS:"+arcSourceTimeBits(expected_sources.at(hv))+":VECTOR_INDEX:"+std::to_string(hv),"HV source identity mismatch");
   last_hv_ordinal=event.ordinal;++hv;
  }
  if(event.kind=="ARC_END"){end=true;need(event.ordinal>last_hv_ordinal,"ARC END preceded executed HV");}
 }
 need(hv==expected_times.size()&&end&&e.arcJointPriors().size()==1,"exact ARC/HV conditioning missing");
}
void compatibilityIntegration(const std::filesystem::path& out){
 // Old modes ignore even malformed extra metadata. Compare actual production
 // loaders, states, covariance and complete old diagnostic/manifest file bytes.
 for(const std::string policy:{"legacy_absolute_nearest","causal_unique_latest"}){
  auto o=options(policy);
  const std::string plain=BASE_HEADER+"\n"+base(1.04)+"\n"+base(1.06)+"\n";
  const std::string extra=BASE_HEADER+","+DEP_HEADER+"\n"+base(1.04)+","+SCHEMA+",bad,bad,bad,bad\n"+
   base(1.06)+","+SCHEMA+",bad,bad,bad,bad\n";
  auto a=loadCsv(out/(policy+"_plain.csv"),plain,o),b=loadCsv(out/(policy+"_extra.csv"),extra,o);
  need(a.measurements.size()==2&&b.measurements.size()==2&&!b.measurements[0].dependency_metadata_available,"old loader interpreted new metadata");
  GIEngine ea(o),eb(o);initialize(ea);initialize(eb);attach(ea,a.measurements);attach(eb,b.measurements);
  for(double t:{1.05,1.055}){apply(ea,t);apply(eb,t);feedback(ea);feedback(eb);
   need(ea.getCovariance()==eb.getCovariance()&&ea.navState().vel_ned_mps==eb.navState().vel_ned_mps,"old mode changed by new metadata");
  }
  save(ea,o,out/(policy+"_plain"));save(eb,o,out/(policy+"_extra"));
  sameFiles(out/(policy+"_plain"),out/(policy+"_extra"));
  const auto olddir=out/(policy+"_plain");
  if(policy=="causal_unique_latest"){
   need(ea.go2VelocityDiagnosticPriorUpdateCount()==1,"causal compatibility fixture did not consume once");
   need(content(olddir/"NED_VELOCITY_SOURCE_EVENTS.csv").find("dependency_")==std::string::npos,"old causal CSV gained columns");
  }else{
   need(ea.go2VelocityDiagnosticPriorUpdateCount()==2&&ea.nedVelocitySourceEvents().empty(),"legacy selection/reuse drift");
   need(!std::filesystem::exists(olddir/"NED_VELOCITY_SOURCE_EVENTS.csv"),"legacy gained causal writer");
  }
 }
 // All-ready declarations must leave scientific operations exactly identical to
 // the old causal policy in the same binary. Policy-specific metadata may differ.
 auto co=arcOptions("causal_unique_latest"),no=arcOptions(POLICY);GIEngine control(co),allready(no);
 setArc(control);setArc(allready);initialize(control);initialize(allready);
 const std::vector<Go2VelocityDiagnosticPriorMeasurement> rows={row(1.004,0,1.004),row(1.006,1,1.006)};
 attach(control,rows);attach(allready,rows);
 const std::vector<GnssData> gs={gnss(1.005),gnss(1.007),gnss(1.008)};
 exactStep(control,1.01,gs);exactStep(allready,1.01,gs);control.finalizeArcSourceStream();allready.finalizeArcSourceStream();
 need(control.go2VelocityDiagnosticPriorUpdateCount()==2&&allready.go2VelocityDiagnosticPriorUpdateCount()==2,"all-ready path not exercised");
 checkExactLedger(control,{1.005,1.007},{1.004,1.006});checkExactLedger(allready,{1.005,1.007},{1.004,1.006});
 std::filesystem::create_directories(out/"control_science");std::filesystem::create_directories(out/"allready_science");
 FileSaver::writeExactCompatible((out/"control_science").string(),{control.navState()},{control.getCovariance()});
 FileSaver::writeExactCompatible((out/"allready_science").string(),{allready.navState()},{allready.getCovariance()});
 control.writeArcCloneDiagnostics((out/"control_science").string());allready.writeArcCloneDiagnostics((out/"allready_science").string());
 sameFiles(out/"control_science",out/"allready_science");
 // Delayed recorded dependencies change selection before the same genuine GNSS
 // and ARC queue; they never generate an asynchronous update at ready_time.
 GIEngine delayed(no);setArc(delayed);initialize(delayed);attach(delayed,{row(1.004,0,1.006),row(1.006,1,1.009)});
 exactStep(delayed,1.01,gs);delayed.finalizeArcSourceStream();
 need(delayed.go2VelocityDiagnosticPriorUpdateCount()==1&&delayed.nedVelocitySourceEvents().size()==3,"dependency-delayed exact queue wrong");
 need(!delayed.nedVelocitySourceEvents()[0].consumed&&delayed.nedVelocitySourceEvents()[1].accepted&&!delayed.nedVelocitySourceEvents()[2].consumed,"delayed event consumption wrong");
 checkExactLedger(delayed,{1.007},{1.004});
 save(delayed,no,out/"delayed");delayed.writeArcCloneDiagnostics((out/"delayed").string());
 // Existing res=1 scheduling snaps GNSS to previous IMU state. A source itself
 // may be past while its dependency lies between actual state and GNSS trigger.
 auto n=options();GIEngine snapped(n);initialize(snapped);const double offset=TIME_ALIGN_ERR*.5;
 need(offset>0.&&offset<.01,"unexpected time alignment constant");
 attach(snapped,{row(1.,0,1.+offset*.5)});legacyStep(snapped,1.01,gnss(1.+offset));
 need(snapped.nedVelocitySourceEvents().size()==1,"snapped GNSS did not dispatch HV");
 const auto first=last(snapped);
 need(first.state_time==1.&&first.trigger_time==1.+offset&&!first.consumed&&first.future_candidate_skips==0&&
  first.dependency_future_trigger_candidate_skips==0&&first.dependency_future_state_candidate_skips==1,"dependency state-clock guard not reached");
 legacyStep(snapped,1.02,gnss(1.01));need(last(snapped).accepted&&snapped.go2VelocityDiagnosticPriorUpdateCount()==1,"snapped waiting dependency consumed early");
 save(snapped,n,out/"snapped");
}
int main(int argc,char** argv){try{
 need(argc==3,"usage: harness fixed_case synthetic_outputdir");std::string mode=argv[1];std::filesystem::path out=argv[2];
 std::filesystem::create_directories(out);
 if(mode=="identity")identity(out);else if(mode=="clocks")clocks(out);else if(mode=="expiry")expiry(out);
 else if(mode=="selection")selection(out);else if(mode=="watermark")watermark(out);else if(mode=="rejection")rejection(out);
 else if(mode=="generation")generation(out);else if(mode=="compatibility_integration")compatibilityIntegration(out);
 else throw std::runtime_error("unknown fixed case");
 std::cout<<"{\"case\":\""<<mode<<"\",\"status\":\"PASS\",\"config_loader_calls\":"<<calls.config_loaders
  <<",\"provider_loader_calls\":"<<calls.provider_loaders<<",\"initialize_calls\":"<<calls.initializes<<",\"setter_calls\":"<<calls.setters
  <<",\"direct_ned_calls\":"<<calls.direct_ned<<",\"exact_steps\":"<<calls.exact_steps<<",\"legacy_steps\":"<<calls.legacy_steps
  <<",\"manual_feedback_calls\":"<<calls.feedbacks<<"}\n";return 0;
 }catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}
}
