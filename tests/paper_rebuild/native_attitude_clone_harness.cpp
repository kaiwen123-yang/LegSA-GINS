// Synthetic-only local harness. No real input paths, navigation CLI, or references.
#include "legsa_v23_port_core/factors/attitude_clone.hpp"
#include "legsa_v23_port_core/factors/foot_pair_events.hpp"
#include "legsa_v23_port_core/kf_gins/gi_engine.hpp"
#include "legsa_v23_port_core/common/earth.hpp"
#include "legsa_v23_port_core/common/rotation.hpp"
#include "legsa_v23_port_core/fileio/file_saver.hpp"
#include "legsa_v23_port_core/config/port_config_loader.hpp"
#include <iostream>
#include <iomanip>
#include <fstream>
#include <filesystem>
#include <limits>
#include <cmath>
#include <stdexcept>
using namespace legsa_v23_port_core;
namespace ac=legsa_v23_port_core::attitude_clone;
void need(bool c,const char* m){if(!c)throw std::runtime_error(m);}
Matrix mat(int n,int m){Matrix a(n,m);for(double& x:a.data)need(bool(std::cin>>x),"read matrix");return a;}
std::vector<double> vec(int n){std::vector<double>a(n);for(double& x:a)need(bool(std::cin>>x),"read vector");return a;}
Vec3 v3(){auto a=vec(3);return {a[0],a[1],a[2]};}
Matrix3 m3(){Matrix3 a;for(auto&row:a)for(double&x:row)need(bool(std::cin>>x),"read3");return a;}
void val(const Matrix&a){std::cout<<'[';for(std::size_t i=0;i<a.rows;++i){if(i)std::cout<<',';std::cout<<'[';for(std::size_t j=0;j<a.cols;++j){if(j)std::cout<<',';std::cout<<a(i,j);}std::cout<<']';}std::cout<<']';}
void val(const std::vector<double>&a){std::cout<<'[';for(std::size_t i=0;i<a.size();++i){if(i)std::cout<<',';std::cout<<a[i];}std::cout<<']';}
void val(const Matrix3&a){Matrix q(3,3);for(int i=0;i<3;++i)for(int j=0;j<3;++j)q(i,j)=a[i][j];val(q);}
void val(const Vec3&a){val(std::vector<double>(a.begin(),a.end()));}
bool first=true;
template<class T>void out(const char*k,const T&a){if(!first)std::cout<<',';first=false;std::cout<<'"'<<k<<"\":";val(a);}
void num(const char*k,double a){if(!first)std::cout<<',';first=false;std::cout<<'"'<<k<<"\":"<<a;}
void gaussian(const ac::Gaussian&s){out("P",s.covariance);out("mean",s.mean);}
PortOptions opts(std::string mode="NULL_CLONE"){
 PortOptions o;o.runtime_contract="research_experiment";o.starttime=1;
 o.qa_fallback_config.enable_qa_fallback=false;o.qa_fallback_config.qa_active_mode=false;
 o.algorithm_id="NATIVE_ATTITUDE_CLONE_SYNTHETIC";
 o.init_pos_std_m={.5,.6,.7};o.init_vel_std_mps={.1,.15,.2};o.init_att_std_rad={.1,.12,.14};
 o.init_imu_error_std.gyrbias={.01,.01,.01};o.init_imu_error_std.accbias={.02,.02,.02};
 o.init_imu_error_std.gyrscale={0,0,0};o.init_imu_error_std.accscale={0,0,0};
 o.imunoise.gyrscale_std={0,0,0};o.imunoise.accscale_std={0,0,0};
 auto&c=o.attitude_clone_config;c.mode=mode;
 if(mode!="off"){c.events_path="SYNTHETIC_NO_INPUT_OPEN";c.position_source_id="generated";
 c.position_gnss_input_status="declared_no";c.covariance_source_id="synthetic_Sigma6";
 c.covariance_assumption="caller_working_second_moment";c.frame_source_id="synthetic_body";
 c.availability_policy="source_time_replay_assumption";c.foot_frd_to_engine_body=identityMatrix3();}
 return o;
}
NavState state(){NavState s;s.time=1;s.pos_blh_rad_m={.6,1.3,35};s.euler_rad={.2,-.1,.3};return s;}
FootPairEvent foot(double t,std::string type,std::string id="c1",std::string ep="e0"){
 FootPairEvent e;e.time=e.available_time=t;e.type=type;e.clone_id=id;e.reason="synthetic";
 e.source_time=type=="RETIRE"?std::numeric_limits<double>::quiet_NaN():t;
 if(type!="RETIRE"){e.endpoint_id=ep;e.foot_i="FR";e.foot_j="FL";e.episode_i="f1";e.episode_j="f2";e.direction_body_frd={.4,-.2,.1};
 if(type=="END")e.difference_covariance=scale(identityMatrix(6),.0008);}
 return e;
}
void init(GIEngine&e,const std::vector<FootPairEvent>&fs={},bool set=true){
 if(set)e.setFootPairEvents(fs);e.initialize(state());ImuData x;x.time=1;x.dt=.01;e.addImuData(x,true);
}
void step(GIEngine&e,double t,const std::vector<GnssData>&gs={}){
 ImuData x;x.time=t;x.dt=t-e.timestamp();x.dtheta={.001*x.dt,-.002*x.dt,.003*x.dt};
 x.dvel={0,0,-Earth::gravity(e.navState().pos_blh_rad_m)*x.dt};
 e.addImuData(x);e.newImuProcessWithEvents(gs);
}
void counts(const GIEngine&e,const char*prefix){
 auto c=e.attitudeCloneCounts();std::string p(prefix);
 auto n=[&](const char*k,double v){auto key=p+k;num(key.c_str(),v);};
 n("source",c.source_rows);n("events",c.event_rows);n("starts",c.starts);n("ends",c.ends);
 n("retires",c.retires);n("rejected",c.rejected_events);n("innovation_reject",c.innovation_rejects);
 n("updates",c.pair_updates);n("skips",c.pair_skips);n("null",c.null_ends);n("joint",c.ordinary_joint_updates);
 n("resets",c.full_resets);n("initial",c.late_initial_events);n("terminal",c.unconsumed_terminal);n("outside",c.unconsumed_outside_imu);
 n("gnss_updates",e.updateCount());n("RD",e.rawDopplerUpdateCount());n("RP",e.go2AttitudeWeakPriorUpdateCount());
 n("HV",e.go2VelocityDiagnosticPriorUpdateCount());n("SA",e.sourceAwareEvaluationCount());
 n("active",e.attitudeCloneActive()?1:0);n("time",e.timestamp());
}
void nav(const GIEngine&e,const char*k){const auto&s=e.navState();std::vector<double>a;for(auto*v:{&s.pos_blh_rad_m,&s.vel_ned_mps,&s.euler_rad})a.insert(a.end(),v->begin(),v->end());out(k,a);}
void diagnostics(GIEngine&e,const PortOptions&o,const std::string&dir){
 std::filesystem::create_directories(dir);e.writeAttitudeCloneDiagnostics(dir);
 auto final=o;final.attitude_clone_counts=e.attitudeCloneCounts();FileSaver::writeRunManifest(dir,final);
}
void aids(GIEngine&e){
 Go2AttitudeWeakPriorStatus ps;ps.solver_enabled=true;ps.provider_status="available";
 Go2AttitudeWeakPriorMeasurement p;p.time=1.001;p.source_status="active";p.quality_flag="nominal";e.setGo2AttitudeWeakPriors({p},ps);
 RawDopplerFactorStatus rs;rs.solver_enabled=true;rs.provider_status="available";
 RawDopplerVelocityMeasurement d;d.time=1.001;d.source_time=1.001;d.provider_status="available";d.sat_count=8;e.setRawDopplerVelocityMeasurements({d},rs);
 Go2VelocityDiagnosticPriorStatus vs;vs.solver_enabled=true;vs.provider_status="available";vs.controlled_activation=true;
 Go2VelocityDiagnosticPriorMeasurement v;v.time=1.001;v.source_status="active";v.quality_flag="nominal";e.setGo2VelocityDiagnosticPriors({v},vs);
}
void engine(const std::string&kind,const std::string&dir){
 if(kind=="propagate"){
  GIEngine e(opts());init(e,{foot(1.01,"START")});step(e,1.01);out("before",e.jointAttitudeCovariance());
  auto phi=mat(21,21),q=mat(21,21);e.EKFPredict(phi,q);out("P",e.jointAttitudeCovariance());counts(e,"");return;
 }
 if(kind=="retire"){
  GIEngine e(opts());init(e,{foot(1.01,"START"),foot(2,"RETIRE")});step(e,1.01);out("before",e.jointAttitudeCovariance());
  e.finalizeFootPairStream();out("P",e.jointAttitudeCovariance());counts(e,"");diagnostics(e,opts(),dir);return;
 }
 if(kind=="frozen"){
  auto o=opts("PAIR_YOUNG");GIEngine e(o);init(e,{foot(1.01,"START"),foot(1.12,"END","c1","e1")});
  step(e,1.05);Matrix h(1,21);h(0,6)=1;h(0,9)=.2;e.EKFUpdate({.001},h,scale(identityMatrix(1),.1));
  e.stateFeedback();step(e,1.13);out("P",e.jointAttitudeCovariance());out("scale",e.navState().imu_error.gyrscale);
  counts(e,"");diagnostics(e,o,dir);return;
 }
 if(kind=="large" || kind=="invalid"){
  auto end=foot(1.12,"END","c1","e1");if(kind=="large")end.direction_body_frd={100,0,0};else end.episode_i="changed";
  for(const auto&mode:{"NULL_CLONE","PAIR_YOUNG"}){
   auto o=opts(mode);o.raw_doppler_config.enable_raw_doppler=true;o.go2_attitude_prior_config.enable_go2_attitude_weak_prior=true;
   o.go2_velocity_prior_diagnostic_config.enable_go2_velocity_prior_diagnostic=true;
   o.go2_velocity_prior_diagnostic_config.enable_go2_horizontal_velocity_prior=true;
   o.source_aware_policy_config.enable_source_aware_weighting=true;
   GIEngine e(o);init(e,{foot(1.01,"START"),end,foot(1.21,"START","c2","e2"),foot(1.22,"RETIRE","c2")});aids(e);
   step(e,1.25);std::string m(mode);out((m+"P").c_str(),e.jointAttitudeCovariance());nav(e,(m+"nav").c_str());
   counts(e,mode);diagnostics(e,o,dir+"/"+mode);
  }return;
 }
 if(kind=="timing"){
  GIEngine with(opts()),without(opts());
  init(with,{foot(1.01,"START"),foot(1.12,"END","c1","e1"),foot(1.21,"START","c2","e0")});init(without);
  GnssData g;g.time=1.01;g.isvalid=true;g.validity_explicit=true;g.has_position=true;g.has_velocity=g.has_yaw=false;
  g.blh_rad_m=state().pos_blh_rad_m;g.std_ned_m={1,1,1};
  step(with,1.01,{g});step(without,1.01,{g});
  out("with",with.jointAttitudeCovariance());out("without",without.jointAttitudeCovariance());
  out("blh",with.navState().pos_blh_rad_m);counts(with,"atstart_");
  step(with,1.22);counts(with,"final_");diagnostics(with,opts(),dir);return;
 }
 if(kind=="boundaries"){
  GIEngine e(opts());init(e,{foot(1,"START"),foot(1.12,"END","c1","e1"),foot(2,"RETIRE"),
                           foot(2.1,"START","c2","e2")});step(e,1.2);
  auto before=e.getCovariance();auto t=e.timestamp();e.finalizeFootPairStream();
  need(before==e.getCovariance()&&t==e.timestamp(),"cleanup altered current state");
  counts(e,"");out("P",e.jointAttitudeCovariance());diagnostics(e,opts(),dir);return;
 }
 if(kind=="off"){
  auto a=opts("off"),b=a;GIEngine x(a),y(b);init(x,{},false);init(y,{},false);
  step(x,1.1);step(y,1.1);need(x.getCovariance()==y.getCovariance(),"off covariance mismatch");
  need(x.navState().euler_rad==y.navState().euler_rad,"off nominal mismatch");
  x.writeAttitudeCloneDiagnostics(dir);num("default_off",PortOptions{}.attitude_clone_config.mode=="off");
  num("shape",x.jointAttitudeCovariance().rows);bool rejected=false;
  try{x.setFootPairEvents({});}catch(...){rejected=true;}num("off_set_rejected",rejected);counts(x,"");return;
 }
 throw std::runtime_error("unknown engine case");
}
int main(int argc,char**argv){
 try{
  need(argc>=2,"operation");std::cout<<std::setprecision(17)<<'{';std::string op=argv[1];
  if(op=="augment"){auto p=mat(21,21);auto m=vec(21);auto j=mat(3,21);gaussian(ac::augment(p,m,j));}
  else if(op=="ordinary"||op=="young"||op=="young_diag"||op=="safe"){
   int n,k;std::cin>>n>>k;auto p=mat(n,n);auto m=vec(n);auto h=mat(k,n);auto r=mat(k,k);auto z=vec(k);
   ac::Gaussian s{p,m};
   if(op=="ordinary")gaussian(ac::ordinaryUpdate(s,z,h,r));
   if(op=="young"){auto w=vec(21);auto a=ac::youngUpdate(s,z,h,r,w);gaussian(a.state);num("applied",a.applied);num("epsilon",a.epsilon);num("prior",a.prior_score);num("score",a.bound_score);}
   if(op=="young_diag"){
     auto w=vec(21);ac::YoungDiagnostics d;auto a=ac::youngUpdate(s,z,h,r,w,&d);
     gaussian(a.state);num("applied",a.applied);num("epsilon",a.epsilon);num("prior",a.prior_score);num("score",a.bound_score);
     num("T",d.T);num("J",d.J);Matrix candidates(d.candidates.size(),5);
     for(std::size_t i=0;i<d.candidates.size();++i){const auto& c=d.candidates[i];candidates(i,0)=c.epsilon;candidates(i,1)=c.score;candidates(i,2)=c.comparison_score;candidates(i,3)=c.tie;candidates(i,4)=c.selected_at_step;}
     out("candidates",candidates);
    }
    if(op=="safe"){auto a=ac::safeInnovation(s,z,h,r);num("statistic",a.statistic);num("passed",a.passed);}
  }else if(op=="reset"){int n;std::cin>>n;auto p=mat(n,n);auto m=vec(n);auto gp=m3();gaussian(ac::reset({p,m},gp));}
  else if(op=="model"){auto d0=v3(),d1=v3();auto c0=m3(),cbn=m3();auto blh=v3();auto s=mat(6,6);
   auto a=ac::pairModel(d0,d1,c0,cbn,blh,s);out("H",a.H);out("R",a.R);out("z",a.residual);out("J",ac::augmentationJacobian(blh));out("K",ac::nedFrameConnection(blh));}
  else if(op=="weights"){out("weights",ac::fixedCurrentWeights(mat(21,21)));}
  else if(op=="read"){auto c=opts().attitude_clone_config;c.events_path=argv[2];auto rows=readFootPairEvents(c);num("rows",rows.size());num("retire_no_source",rows.size()&&std::isnan(rows.back().source_time));}
  else if(op=="config"){auto o=PortConfigLoader::loadYamlLike(argv[2]);num("mode_on",o.attitude_clone_config.mode!="off");}
  else{need(argc>=3,"engine outputdir");engine(op,argv[2]);}
  std::cout<<"}\n";return 0;
 }catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 2;}
}
