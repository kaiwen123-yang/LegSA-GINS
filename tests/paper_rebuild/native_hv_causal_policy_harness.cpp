// Bounded synthetic integration only: six process modes, no providers or references.
#include "legsa_v23_port_core/kf_gins/gi_engine.hpp"
#include "legsa_v23_port_core/config/port_config_loader.hpp"
#include "legsa_v23_port_core/fileio/file_saver.hpp"
#include <cmath>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <limits>
#include <stdexcept>
#include <string>
#include <vector>
using namespace legsa_v23_port_core;
void need(bool v,const char* m){if(!v)throw std::runtime_error(m);}
struct Calls {std::size_t loaders=0,initializes=0,setters=0,direct_ned=0,exact_steps=0,legacy_steps=0,feedbacks=0;} calls;
namespace legsa_v23_port_core {
struct NedHvSourceTestAccess {
 static void apply(GIEngine& e,double trigger,double state) {
  // Isolated selector/gate probe. Production scheduling is covered separately.
  e.timestamp_=state;e.pvacur_.time=state;e.applyGo2VelocityDiagnosticPriorForTime(trigger);
 }
};
}
PortOptions options(bool causal=true) {
 PortOptions o;o.runtime_contract="research_experiment";o.starttime=1.;o.algorithm_id="HV_SYNTHETIC";
 o.enable_receiver_velocity_update=false;o.enable_dual_yaw_update=false;o.disable_source_aware=true;
 o.init_pos_std_m={.5,.6,.7};o.init_vel_std_mps={.1,.15,.2};o.init_att_std_rad={.1,.12,.14};
 o.init_imu_error_std.gyrscale={0,0,0};o.init_imu_error_std.accscale={0,0,0};
 o.imunoise.gyrscale_std={0,0,0};o.imunoise.accscale_std={0,0,0};
 auto& c=o.go2_velocity_prior_diagnostic_config;c.enable_go2_velocity_prior_diagnostic=true;
 c.enable_go2_horizontal_velocity_prior=true;c.go2_horizontal_velocity_frame="ned";
 c.go2_horizontal_velocity_prior_source_aware_enabled=false;
 if(causal)c.go2_velocity_prior_time_policy="causal_unique_latest";
 return o;
}
NavState initial(){NavState s;s.time=1.;s.pos_blh_rad_m={.6,1.3,35.};s.vel_ned_mps={1.2,-.3,.1};s.euler_rad={.2,-.1,.3};return s;}
void initialize(GIEngine& e){++calls.initializes;e.initialize(initial());ImuData i;i.time=1.;i.dt=.01;e.addImuData(i,true);}
Go2VelocityDiagnosticPriorMeasurement row(double t){Go2VelocityDiagnosticPriorMeasurement r;r.time=t;r.source_status="active";
 r.quality_flag="nominal";r.velocity_ned_mps={.8,.1,0};r.std_ned_mps={.2,.3,999};return r;}
void attach(GIEngine& e,const std::vector<Go2VelocityDiagnosticPriorMeasurement>& rows){
 ++calls.setters;Go2VelocityDiagnosticPriorStatus s;s.solver_enabled=true;s.provider_status="available";e.setGo2VelocityDiagnosticPriors(rows,s);
}
void apply(GIEngine& e,double t){++calls.direct_ned;NedHvSourceTestAccess::apply(e,t,t);}
void feedback(GIEngine& e){++calls.feedbacks;e.stateFeedback();}
void exactStep(GIEngine& e,double t,const std::vector<GnssData>& g={}){++calls.exact_steps;ImuData i;i.time=t;i.dt=.01;i.dvel={0,0,-.098};e.addImuData(i);e.newImuProcessWithEvents(g);}
void legacyStep(GIEngine& e,double t,GnssData g){++calls.legacy_steps;ImuData i;i.time=t;i.dt=.01;i.dvel={0,0,-.098};e.addImuData(i);e.addGnssData(g);e.newImuProcess();}
GnssData gnss(double t){GnssData g;g.time=t;g.isvalid=true;g.validity_explicit=true;g.has_position=true;g.has_velocity=false;g.has_yaw=false;g.blh_rad_m=initial().pos_blh_rad_m;g.std_ned_m={1.,1.,1.};return g;}
std::string content(const std::filesystem::path& p){std::ifstream f(p,std::ios::binary);need(f.good(),"missing synthetic output");return std::string(std::istreambuf_iterator<char>(f),{});}
void save(GIEngine& e,PortOptions o,const std::filesystem::path& dir,const std::vector<NavState>& nav={},const std::vector<std::vector<double>>& cov={}) {
 std::filesystem::create_directories(dir);
 FileSaver::writeExactCompatible(dir.string(),nav.empty()?std::vector<NavState>{e.navState()}:nav,
   cov.empty()?std::vector<std::vector<double>>{e.getCovariance()}:cov);
 e.writeNedVelocitySourceDiagnostics(dir.string());e.writeBodyVelocityDiagnostics(dir.string());e.writeHeadingSourceDiagnostics(dir.string());
 o.go2_velocity_prior_diagnostic_status=e.go2VelocityDiagnosticPriorStatus();FileSaver::writeRunManifest(dir.string(),o);
}
void sameFiles(const std::filesystem::path&a,const std::filesystem::path&b){
 std::size_t na=0,nb=0;for(const auto& e:std::filesystem::directory_iterator(a)){++na;need(content(e.path())==content(b/e.path().filename()),"legacy output bytes differ");}
 for(const auto&e:std::filesystem::directory_iterator(b)){(void)e;++nb;}need(na==nb,"legacy file set differs");
}
template<class F>void rejects(F f,const std::string& token){bool caught=false;try{f();}catch(const std::exception&e){caught=true;need(std::string(e.what()).find(token)!=std::string::npos,"wrong rejection reason");}need(caught,"required rejection absent");}
std::string config(const std::string& policy="") {
 return "runtime_contract: research_experiment\nstage_id: SYNTHETIC_HV_LOCAL\nprotocol_id: SYNTHETIC_ONLY\ncase_id: SYNTHETIC_ONLY\nrun_id: SYNTHETIC_HV\nrun_label: SYNTHETIC_HV\ndata_mode: synthetic_local_fixture\nalgorithm_id: AB0001\ncommon_initialization: true\ncommon_initialization_dual_yaw_used: true\ncommon_initialization_source: synthetic_declared_initializer\nenable_dual_yaw: true\nenable_receiver_velocity: true\nenable_raw_doppler: false\nenable_source_aware: false\nenable_go2_roll_pitch_prior: false\nenable_go2_horizontal_velocity_prior: true\ngo2_position_truth_claim: false\ngo2_velocity_truth_claim: false\ngo2_yaw_truth_claim: false\ngo2_contact_truth_claim: false\n"+
  (policy.empty()?std::string{}:"go2_velocity_prior_time_policy: "+policy+"\n");
}
PortOptions load(const std::filesystem::path& p,const std::string& s){std::ofstream f(p);f<<s;f.close();++calls.loaders;return PortConfigLoader::loadYamlLike(p.string());}
void guards(const std::filesystem::path& out){
 auto d=load(out/"default.yaml",config());need(d.go2_velocity_prior_diagnostic_config.go2_velocity_prior_time_policy=="legacy_absolute_nearest","default policy drift");
 auto c=load(out/"causal.yaml",config("causal_unique_latest"));GIEngine valid(c);
 need(c.go2_velocity_prior_diagnostic_config.enable_go2_velocity_prior_diagnostic,"loader HV must enable diagnostic");
 rejects([&]{load(out/"unknown.yaml",config("wrong"));},"NED_HV_UNKNOWN_TIME_POLICY");
 rejects([&]{load(out/"body.yaml",config("causal_unique_latest")+"go2_horizontal_velocity_frame: body_frd\n");},"NED_HV_CAUSAL_POLICY_REQUIRES_RESEARCH_HORIZONTAL_NED");
 for(int i=0;i<7;++i){auto o=options();auto&v=o.go2_velocity_prior_diagnostic_config;
  if(i==0)o.runtime_contract="legacy";if(i==1)v.enable_go2_horizontal_velocity_prior=false;
  if(i==2)v.go2_horizontal_velocity_frame="body_frd";if(i==3)v.go2_horizontal_velocity_prior_mode="full_3d";
  if(i==4)v.go2_horizontal_velocity_prior_vertical_disabled=false;if(i==5)v.go2_velocity_prior_time_tolerance_sec=-.1;
  if(i==6)v.enable_go2_velocity_prior_diagnostic=false;
  rejects([&]{GIEngine e(o);},"NED_HV_CAUSAL_POLICY_REQUIRES_RESEARCH_HORIZONTAL_NED");}
 auto o=options();o.go2_velocity_prior_diagnostic_config.go2_velocity_prior_time_policy="wrong";
 rejects([&]{GIEngine e(o);},"NED_HV_UNKNOWN_TIME_POLICY");
 GIEngine e(options());initialize(e);auto bad=row(1.);bad.observation_frame="body_frd";
 rejects([&]{attach(e,{bad});},"NED_HV_SOURCE_FRAME_MISMATCH");
 rejects([&]{apply(e,std::numeric_limits<double>::quiet_NaN());},"NED_HV_NONFINITE_UPDATE_TIME");
 need(e.nedVelocitySourceEvents().empty(),"invalid clock emitted row");
}
void selection(const std::filesystem::path& out){
 auto o=options();GIEngine e(o);initialize(e);auto disabled=row(1.048);disabled.update_flag=false;
 attach(e,{row(1.031),row(1.06),row(1.04),row(1.04),row(.9),row(std::numeric_limits<double>::quiet_NaN()),disabled});
 apply(e,1.05);need(e.nedVelocitySourceEvents().back().vector_index==3,"latest/tie not final index");
 auto first=e.nedVelocitySourceEvents().back();need(first.future_candidate_skips==1&&first.nonfinite_time_skips==1&&first.accepted,"future/nonfinite contract");
 apply(e,1.055);need(e.go2VelocityDiagnosticPriorUpdateCount()==1&&e.nedVelocitySourceEvents().back().used_or_older_candidate_skips==3,"duplicate/older replay");
 apply(e,1.065);need(e.nedVelocitySourceEvents().back().vector_index==1&&e.go2VelocityDiagnosticPriorUpdateCount()==2,"future row not later eligible");
 apply(e,1.2);need(!e.nedVelocitySourceEvents().back().source_present,"stale sample selected");
 auto b=options();b.go2_velocity_prior_diagnostic_config.go2_velocity_prior_time_tolerance_sec=.125;
 GIEngine boundary(b);initialize(boundary);attach(boundary,{row(.875)});apply(boundary,1.);need(boundary.go2VelocityDiagnosticPriorUpdateCount()==1,"inclusive tolerance boundary");
 b.go2_velocity_prior_diagnostic_config.go2_velocity_prior_time_tolerance_sec=0.;GIEngine zero(b);initialize(zero);attach(zero,{row(1.)});apply(zero,1.);need(zero.go2VelocityDiagnosticPriorUpdateCount()==1,"zero tolerance exact sample");
 save(e,o,out/"selected");
}
void consumption(const std::filesystem::path& out){
 auto o=options();GIEngine e(o);initialize(e);auto invalid=row(1.04);invalid.source_status="inactive";
 attach(e,{row(1.03),invalid,row(1.06)});apply(e,1.05);
 need(e.go2VelocityDiagnosticPriorRejectCount()==1&&e.nedVelocitySourceEvents().back().consumed,"invalid selected row not consumed");
 apply(e,1.055);need(e.go2VelocityDiagnosticPriorRejectCount()==1&&e.go2VelocityDiagnosticPriorUpdateCount()==0,"provider reject refunded or older fallback");
 apply(e,1.065);need(e.go2VelocityDiagnosticPriorUpdateCount()==1,"newer sample blocked after rejection");
 auto w=options();w.disable_source_aware=false;w.go2_velocity_prior_diagnostic_config.go2_horizontal_velocity_prior_source_aware_enabled=true;
 w.source_aware_policy_config.enable_source_aware_weighting=true;w.source_aware_policy_config.source_aware_mode="lsim_oim";w.source_aware_policy_config.source_aware_reject_extreme=true;
 GIEngine weighted(w);initialize(weighted);auto huge=row(1.04);huge.velocity_ned_mps={1e6,1e6,0};attach(weighted,{huge});
 apply(weighted,1.05);need(weighted.nedVelocitySourceEvents().back().reason=="source_aware_reject"&&weighted.sourceAwareEvaluationCount()==1,"SA rejection fixture not reached");
 apply(weighted,1.055);need(weighted.sourceAwareEvaluationCount()==1&&weighted.go2VelocityDiagnosticPriorUpdateCount()==0,"SA reject retried");
 save(e,o,out/"provider");save(weighted,w,out/"weight");
}
void generation(const std::filesystem::path& out){
 auto o=options();GIEngine e(o);initialize(e);attach(e,{row(1.04)});apply(e,1.05);
 const auto first=e.nedVelocitySourceEvents().back();feedback(e);apply(e,1.055);
 need(e.go2VelocityDiagnosticPriorUpdateCount()==1&&e.nedVelocitySourceEvents().back().generation==first.generation,"feedback reset consumption");
 initialize(e);apply(e,1.05);need(e.go2VelocityDiagnosticPriorUpdateCount()==2&&e.nedVelocitySourceEvents().back().generation==first.generation+1,"initialize generation reset missing");
 auto replacement=row(1.04);replacement.velocity_ned_mps={.4,.2,0};attach(e,{replacement});apply(e,1.05);
 need(e.go2VelocityDiagnosticPriorUpdateCount()==1&&e.nedVelocitySourceEvents().back().generation==first.generation+2,"replacement generation reset missing");
 const auto counts=e.go2VelocityDiagnosticPriorStatus().ned_time_policy_counts;
 need(counts.selected_attempts==3&&counts.generations==4,"generation counters not cumulative");save(e,o,out/"generations");
}
void legacyBody(const std::filesystem::path& out){
 auto a=options(false),b=a;b.go2_velocity_prior_diagnostic_config.go2_velocity_prior_time_policy="legacy_absolute_nearest";
 GIEngine ea(a),eb(b);initialize(ea);initialize(eb);attach(ea,{row(.96),row(1.06)});attach(eb,{row(.96),row(1.06)});
 for(double t:{1.05,1.055}){apply(ea,t);apply(eb,t);feedback(ea);feedback(eb);
  need(ea.getCovariance()==eb.getCovariance()&&ea.navState().vel_ned_mps==eb.navState().vel_ned_mps,"default/explicit legacy state differs");}
 need(ea.go2VelocityDiagnosticPriorUpdateCount()==2&&ea.nedVelocitySourceEvents().empty(),"legacy future/reuse path changed");
 save(ea,a,out/"default");save(eb,b,out/"explicit");sameFiles(out/"default",out/"explicit");
 need(!std::filesystem::exists(out/"default/NED_VELOCITY_SOURCE_EVENTS.csv"),"default new diagnostic emitted");
 need(content(out/"default/RUN_MANIFEST.json").find("go2_velocity_prior_time_policy")==std::string::npos,"default manifest changed");
 a.go2_velocity_prior_diagnostic_config.go2_horizontal_velocity_frame="body_frd";
 a.go2_velocity_prior_diagnostic_config.go2_body_velocity_prior_path="SYNTHETIC_IN_MEMORY_BODY";b=a;
 b.go2_velocity_prior_diagnostic_config.go2_velocity_prior_time_policy="legacy_absolute_nearest";
 GIEngine ba(a),bb(b);initialize(ba);initialize(bb);auto body=row(1.19);body.observation_frame="body_frd";
 body.velocity_body_frd_mps={.8,.1,0};body.std_body_frd_mps={.2,.3,0};attach(ba,{body});attach(bb,{body});
 std::vector<NavState> na,nb;std::vector<std::vector<double>> ca,cb;
 for(int i=1;i<=20;++i){double t=1.+.01*i;exactStep(ba,t);exactStep(bb,t);na.push_back(ba.navState());nb.push_back(bb.navState());ca.push_back(ba.getCovariance());cb.push_back(bb.getCovariance());}
 need(ba.go2VelocityDiagnosticPriorUpdateCount()==1&&bb.go2VelocityDiagnosticPriorUpdateCount()==1,"body timer changed");
 save(ba,a,out/"body_default",na,ca);save(bb,b,out/"body_explicit",nb,cb);sameFiles(out/"body_default",out/"body_explicit");
}
ArcSourceEvent arc(double t,const std::string& role){ArcSourceEvent e;e.sequence_id="SYNTHETIC";e.block_id="SYNTHETIC:BLOCK:0";
 e.endpoint_id=role;e.role=role;e.source_time=e.replay_time=t;e.source_time_bits_hex=arcSourceTimeBits(t);e.epoch_index=role=="START"?0:4;return e;}
void integration(const std::filesystem::path& out){
 auto o=options();auto&a=o.arc_clone_config;a.mode="NULL_ARC_DIAGNOSTIC";a.events_path="SYNTHETIC_IN_MEMORY_ARC";
 a.events_sha256=std::string(64,'a');a.manifest_sha256=std::string(64,'b');a.source_time_scale_id="SYNTHETIC_EXACT_TIME";
 a.time_mapping_source_id="SYNTHETIC_IDENTITY";a.availability_policy="source_time_replay_assumption";
 GIEngine e(o);e.setArcSourceEvents({arc(1.002,"START"),arc(1.009,"END")});initialize(e);attach(e,{row(1.004),row(1.006)});
 exactStep(e,1.01,{gnss(1.005),gnss(1.007),gnss(1.008)});e.finalizeArcSourceStream();
 need(e.go2VelocityDiagnosticPriorUpdateCount()==2&&e.arcJointPriors().size()==1,"exact GNSS/ARC integration missing");
 std::size_t hv=0;for(const auto& event:e.arcConditioningEvents())if(event.source_tag=="GO2_VELOCITY_DIAGNOSTIC"){
  ++hv;need(event.state_time==(hv==1?1.005:1.007),"HV ledger not exact state time");}
 need(hv==2&&e.nedVelocitySourceEvents().size()==3,"HV exact queue/reuse accounting");
 for(const auto& event:e.nedVelocitySourceEvents())if(event.accepted)need(event.source_time<=event.trigger_time&&event.source_time<=event.state_time,"future update admitted");
 save(e,o,out/"exact");e.writeArcCloneDiagnostics((out/"exact").string());
 // Legacy res=1 snaps a trigger to the previous IMU state. timestamp_ is already
 // advanced to the next IMU, so the causal guard must use pvacur_.time instead.
 auto n=options();GIEngine snapped(n);initialize(snapped);const double offset=TIME_ALIGN_ERR*.5;
 need(offset>0.&&offset<.01,"unexpected alignment constant");attach(snapped,{row(1.+offset*.5)});
 legacyStep(snapped,1.01,gnss(1.+offset));
 need(snapped.go2VelocityDiagnosticPriorUpdateCount()==0,"near-boundary future-to-state sample accepted");
 need(snapped.nedVelocitySourceEvents().size()==1,"near-boundary GNSS did not dispatch HV");
 const auto first=snapped.nedVelocitySourceEvents().back();
 need(first.state_time==1.&&first.trigger_time==1.+offset&&!first.consumed&&first.future_trigger_candidate_skips==0&&first.future_state_candidate_skips==1,"trigger/state clock gate wrong");
 legacyStep(snapped,1.02,gnss(1.01));
 need(snapped.go2VelocityDiagnosticPriorUpdateCount()==1,"future-to-state candidate was prematurely consumed");
 save(snapped,n,out/"snapped");
}
int main(int argc,char**argv){try{
 need(argc==3,"usage: harness case outputdir");std::string mode=argv[1];std::filesystem::path out=argv[2];
 std::filesystem::create_directories(out);
 if(mode=="guards")guards(out);else if(mode=="selection")selection(out);else if(mode=="consumption")consumption(out);
 else if(mode=="generation")generation(out);else if(mode=="legacy_body")legacyBody(out);else if(mode=="integration")integration(out);else throw std::runtime_error("unknown fixed case");
 std::cout<<"{\"case\":\""<<mode<<"\",\"status\":\"PASS\",\"loader_calls\":"<<calls.loaders<<",\"initialize_calls\":"<<calls.initializes
  <<",\"setter_calls\":"<<calls.setters<<",\"direct_ned_calls\":"<<calls.direct_ned<<",\"exact_steps\":"<<calls.exact_steps
  <<",\"legacy_steps\":"<<calls.legacy_steps<<",\"manual_feedback_calls\":"<<calls.feedbacks<<"}\n";return 0;
 }catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 1;}}
