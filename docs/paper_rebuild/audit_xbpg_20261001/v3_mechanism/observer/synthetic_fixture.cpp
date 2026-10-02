// Pure synthetic fixture; no files are read, no real config/provider is used.
// Compile unchanged against both source_frozen and source_observed libraries.
#include "legsa_v23_port_core/kf_gins/gi_engine.hpp"
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <cstdlib>
#include <string>
using namespace legsa_v23_port_core;
namespace fs=std::filesystem;

PortOptions options(const std::string& name) {
  PortOptions o;o.data_mode="synthetic_fixture_only";o.synthetic_data_used=true;
  o.clean_final_v23_parity_mode=true;o.antlever_m={0.4,-0.2,0.1};
  o.init_pos_std_m={2.0,3.0,4.0};o.init_vel_std_mps={0.5,0.4,0.3};o.init_att_std_rad={0.05,0.04,0.03};
  o.init_imu_error.gyrbias={1e-5,-2e-5,3e-5};o.init_imu_error.accbias={1e-3,2e-3,-1e-3};
  o.init_imu_error.gyrscale={1e-4,2e-4,3e-4};o.init_imu_error.accscale={2e-4,3e-4,4e-4};
  auto& c=o.source_aware_policy_config;c.enable_source_aware_weighting=true;c.source_aware_mode="lsim_oim";
  c.source_aware_enable_rolling_innovation_baseline=true;c.source_aware_rolling_window_size=5;
  c.source_aware_go2_readiness_lsim_enabled=true;
  o.raw_doppler_config.enable_raw_doppler=true;o.raw_doppler_config.raw_doppler_time_tolerance_sec=0.09;
  o.go2_attitude_prior_config.enable_go2_attitude_weak_prior=true;
  o.go2_attitude_prior_config.go2_attitude_prior_time_tolerance_sec=0.07;
  auto& h=o.go2_velocity_prior_diagnostic_config;h.enable_go2_velocity_prior_diagnostic=true;
  h.enable_go2_horizontal_velocity_prior=true;h.go2_diagnostic_prior_only=false;h.go2_velocity_prior_time_tolerance_sec=0.07;
  o.go2_readiness_lsim_metadata_config.enable_go2_readiness_lsim_metadata=true;
  if(name=="disabled_aux") {o.raw_doppler_config.enable_raw_doppler=false;o.go2_attitude_prior_config.enable_go2_attitude_weak_prior=false;h.enable_go2_velocity_prior_diagnostic=false;}
  if(name=="sa_off" || name=="prior_sa_off" || name=="rd_residual_gate")c.enable_source_aware_weighting=false;
  if(name=="prior_sa_off") {o.go2_attitude_prior_config.go2_attitude_prior_sourceaware=false;h.go2_horizontal_velocity_prior_source_aware_enabled=false;}
  if(name=="policy_reject")c.source_aware_reject_extreme=true;
  return o;
}
void rows(GIEngine& e,const std::string& name) {
  RawDopplerVelocityMeasurement r;r.time=.02;r.source_time=.02;r.velocity_ned_mps={.6,-.3,.2};r.std_ned_mps={.05,.06,.07};r.provider_status="available";r.quality="nominal";r.sat_count=8;
  std::vector<RawDopplerVelocityMeasurement> rd{r,r,r};rd[2].time=.2;rd[2].provider_status="invalid";
  Go2AttitudeWeakPriorMeasurement p;p.time=.02;p.roll_rad=.011;p.pitch_rad=-.016;p.source_status="active";p.quality_flag="nominal";
  std::vector<Go2AttitudeWeakPriorMeasurement> rp{p,p,p};rp[2].time=.12;rp[2].source_status="inactive";
  Go2VelocityDiagnosticPriorMeasurement h;h.time=.02;h.velocity_ned_mps={.8,-.4,0};h.std_ned_mps={.4,.5,999};h.source_status="active";h.quality_flag="nominal";h.diagnostic_only=false;h.prior_policy="horizontal_fixture";
  std::vector<Go2VelocityDiagnosticPriorMeasurement> hv{h,h,h,h};hv[0].update_flag=false;hv[3].time=.12;hv[3].go2_velocity_truth_claim=true;
  if(name=="no_rows") {rd.clear();rp.clear();hv.clear();}
  if(name=="no_match") {for(auto& a:rd)a.time=50;for(auto& a:rp)a.time=50;for(auto& a:hv)a.time=50;}
  if(name=="quality_reject") {for(auto& a:rd)a.valid=false;for(auto& a:rp)a.source_status="inactive";for(auto& a:hv)a.go2_velocity_truth_claim=true;}
  if(name=="no_eligible_hv") for(auto& a:hv)a.update_flag=false;
  if(name=="rd_residual_gate") for(auto& a:rd)a.velocity_ned_mps={30,-20,10};
  RawDopplerFactorStatus rs;rs.solver_enabled=name!="source_off";rs.provider_status="available";
  Go2AttitudeWeakPriorStatus ps;ps.solver_enabled=name!="source_off";ps.provider_status="available";
  Go2VelocityDiagnosticPriorStatus hs;hs.solver_enabled=name!="source_off";hs.provider_status="available";
  e.setRawDopplerVelocityMeasurements(rd,rs);e.setGo2AttitudeWeakPriors(rp,ps);e.setGo2VelocityDiagnosticPriors(hv,hs);
  Go2ReadinessLsimMetadataMeasurement m;m.time=.02;m.source_status="active";m.source_valid=true;m.motion_state="UNKNOWN";m.readiness_score=.3;m.readiness_low=true;m.readiness_flag=false;
  Go2ReadinessLsimMetadataStatus ms;ms.solver_enabled=true;ms.provider_status="available";e.setGo2ReadinessLsimMetadata({m},ms);
}
void emit(std::ostream& out,const GIEngine& e,const std::string& name,int step) {
  const auto& s=e.navState();out<<name<<','<<step<<','<<e.timestamp();
  auto values=[&](const auto& v){for(const auto x:v)out<<','<<x;};
  values(s.pos_blh_rad_m);values(s.vel_ned_mps);values(s.euler_rad);
  out<<','<<s.qbn.w<<','<<s.qbn.x<<','<<s.qbn.y<<','<<s.qbn.z;
  for(const auto& v:s.cbn)values(v);
  values(s.imu_error.gyrbias);values(s.imu_error.accbias);values(s.imu_error.gyrscale);values(s.imu_error.accscale);
  values(e.getCovariance());
  out<<','<<e.propagationCount()<<','<<e.updateCount()<<','<<e.positionUpdateCount()<<','<<e.velocityUpdateCount()<<','<<e.yawUpdateCount()<<','<<e.yawNormalCount()<<','<<e.yawDownweightCount()<<','<<e.yawRejectCount()<<','<<e.sourceAwareEvaluationCount()<<','<<e.sourceAwareWeightChangedCount()<<','<<e.rawDopplerUpdateCount()<<','<<e.rawDopplerRejectCount()<<','<<e.go2AttitudeWeakPriorUpdateCount()<<','<<e.go2AttitudeWeakPriorRejectCount()<<','<<e.go2VelocityDiagnosticPriorUpdateCount()<<','<<e.go2VelocityDiagnosticPriorRejectCount()<<','<<e.covHealthFailCount();
  const auto stats=e.sourceAwareStats();out<<','<<stats.trace_row_count;values(stats.update_count_by_source);values(stats.reject_count_by_source);values(stats.scale_p50_by_source);values(stats.scale_p95_by_source);values(stats.scale_max_by_source);out<<'\n';
}
ImuData imu(double t) {ImuData i;i.time=t;i.dt=.01;i.dtheta={1e-5,2e-5,3e-5};i.dvel={1e-5,-2e-5,-.0978};return i;}
void run(const fs::path& output,const std::string& name,bool observe) {
  const auto d=output/name;fs::create_directories(d);
  if(observe) {setenv("LEGSA_V3_OBSERVER_DIR",(d/"observer").c_str(),1);setenv("LEGSA_V3_OBSERVER_RUN_ID",name.c_str(),1);}
  else {unsetenv("LEGSA_V3_OBSERVER_DIR");unsetenv("LEGSA_V3_OBSERVER_RUN_ID");}
  GIEngine e(options(name));e.newImuProcess();NavState s;s.pos_blh_rad_m={.5,1,10};s.vel_ned_mps={.1,-.05,0};s.euler_rad={.01,-.02,.03};e.initialize(s);rows(e,name);e.addImuData(imu(0),true);
  std::ofstream out(d/"SCIENTIFIC_STATE.csv");out<<std::setprecision(17);emit(out,e,name,0);
  for(int step=1;step<=14;++step) {
    const double t=.01*step;GnssData g;g.time=t;g.blh_rad_m={.5+1e-8,1+2e-8,10.4};g.std_ned_m={.2,.3,.4};g.vel_ned_mps={.4,-.2,.1};g.vel_std_mps={.1,.1,.15};g.yaw_rad=.032;g.yaw_std_rad=.02;g.yaw_deg=g.yaw_rad*R2D;g.yaw_std_deg=g.yaw_std_rad*R2D;g.validity_explicit=true;g.has_position=g.has_velocity=g.has_yaw=true;
    if(step==2)g.time=.01;if(step==3)g.time=.025;
    if(step==4 || step==12)g.has_position=g.has_velocity=g.has_yaw=false;
    if(step==5)g.time=.07;if(step==8)g.time=.001;
    if(step==9) {g.yaw_rad=2;g.yaw_deg=g.yaw_rad*R2D;}
    if(step==10) {g.yaw_std_rad=.2;g.yaw_std_deg=.2*R2D;}
    if(step==11)g.vel_ned_mps={10,4,0};
    if(name=="policy_reject") {g.blh_rad_m[0]+=.01;g.vel_ned_mps={100,200,50};}
    if(step!=6 && step!=7 && step!=14)e.addGnssData(g);
    e.addImuData(imu(t));e.newImuProcess();emit(out,e,name,step);
  }
  GnssData blocked;blocked.isvalid=false;e.gnssUpdate(blocked);
  e.writeSourceAwareTrace(d.string());
}
int main(int argc,char** argv) {
  if(argc!=3){std::cerr<<"usage: fixture OUTPUT_DIR observer_on|observer_off\n";return 2;}
  try {const fs::path output=argv[1];if(fs::exists(output)){std::cerr<<"refuse existing output\n";return 3;}
    for(const auto& name:{"all_active_sa","disabled_aux","no_rows","no_match","source_off","sa_off","prior_sa_off","quality_reject","no_eligible_hv","rd_residual_gate","policy_reject"})run(output,name,std::string(argv[2])=="observer_on");
    std::cout<<"COMPLETED 11 pure-synthetic scenarios; 0 real inputs\n";return 0;
  } catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}
}
