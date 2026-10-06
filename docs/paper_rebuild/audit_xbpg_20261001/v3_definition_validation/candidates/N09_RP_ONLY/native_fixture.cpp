// New N09 synthetic fixtures. No real configuration, provider or trace is read.
// Compile against both the original observed library and this candidate.
#include "legsa_v23_port_core/kf_gins/gi_engine.hpp"
#include <cmath>
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <limits>
#include <memory>
#include <stdexcept>
#include <string>
using namespace legsa_v23_port_core;
namespace fs = std::filesystem;
constexpr double step_dt = 0.03125;

struct Case {
  std::string name;
  int res = 3;
  std::string condition = "accepted";
};
std::vector<Case> cases() {
  std::vector<Case> out;
  for (int r : {1,2,3}) {
    for (const auto& kind : {"accepted", "rejected", "valid_all", "valid_yaw_only"})
      out.push_back({std::string(kind)+"_res"+std::to_string(r),r,kind});
  }
  for (const auto& kind : {"disabled", "solver_off", "no_rows", "no_match", "inactive",
       "zero_std", "nan_std", "tolerance_exact", "tolerance_outside", "tie_last",
       "tie_last_inactive", "closest_inactive", "sa_off", "no_gnss", "future_pending",
       "consume_once", "same_time_new_identity", "superseded_pending", "implicit_validity"})
    out.push_back({kind,3,kind});
  return out;
}
double eventTime(const Case& c) {
  if(c.condition=="future_pending") return 1.0+1.5*step_dt;
  if(c.condition=="same_time_new_identity") return 1.0+step_dt;
  return c.res==1?1.0:c.res==2?1.0+step_dt:1.0+0.5*step_dt;
}
PortOptions options(const Case& c, bool oracle=false) {
  PortOptions o; o.data_mode="synthetic_fixture_only";o.synthetic_data_used=true;
  o.clean_final_v23_parity_mode=true;
  o.init_pos_std_m={2,3,4};o.init_vel_std_mps={.3,.4,.5};o.init_att_std_rad={.03,.04,.05};
  o.antlever_m={.03,.02,-.3};o.init_imu_error.gyrbias={1e-5,-2e-5,3e-5};
  auto& sa=o.source_aware_policy_config;sa.enable_source_aware_weighting=c.condition!="sa_off";
  sa.source_aware_mode="lsim_oim";sa.source_aware_policy_version="clean_v1_conservative_innovation_covariance";
  sa.source_aware_method_family="clean_v1_conservative_quadratic";
  sa.source_aware_reject_extreme=c.condition=="rejected";
  o.go2_attitude_prior_config.enable_go2_attitude_weak_prior=c.condition!="disabled";
  o.go2_attitude_prior_config.go2_attitude_prior_time_tolerance_sec=.03125;
  o.go2_attitude_prior_config.go2_attitude_prior_sourceaware=true;
  o.raw_doppler_config.enable_raw_doppler=!oracle;
  if(oracle){o.enable_dual_yaw_update=false;o.enable_receiver_velocity_update=false;}
  auto& hv=o.go2_velocity_prior_diagnostic_config;
  hv.enable_go2_velocity_prior_diagnostic=!oracle;hv.enable_go2_horizontal_velocity_prior=!oracle;
  hv.go2_diagnostic_prior_only=false;
  return o;
}
NavState initial() {
  NavState s;s.time=1;s.pos_blh_rad_m={.5,1,10};s.vel_ned_mps={.1,-.05,.02};s.euler_rad={.01,-.02,.03};return s;
}
ImuData imu(double time) {
  ImuData i;i.time=time;i.dt=step_dt;i.dtheta={.002,-.001,.0015};i.dvel={.001,.002,-9.8*step_dt};return i;
}
GnssData gnss(const Case& c,double time) {
  GnssData g;g.time=time;g.validity_explicit=c.condition!="implicit_validity";
  g.has_position=g.has_velocity=c.condition=="valid_all";
  g.has_yaw=c.condition=="valid_all"||c.condition=="valid_yaw_only";
  g.isvalid=g.has_position||g.has_velocity||g.has_yaw;
  g.blh_rad_m={.5+1e-8,1+1e-8,10.1};g.std_ned_m={1,1,1};g.vel_ned_mps={.11,-.04,.01};
  g.vel_std_mps={.2,.2,.2};g.yaw_rad=.032;g.yaw_std_rad=.03;g.yaw_deg=g.yaw_rad*R2D;g.yaw_std_deg=g.yaw_std_rad*R2D;return g;
}
void loadRows(GIEngine& e,const Case& c) {
  const double t=eventTime(c);
  Go2AttitudeWeakPriorMeasurement p;p.time=t;p.roll_rad=.04;p.pitch_rad=-.05;
  p.std_roll_rad=p.std_pitch_rad=.02;p.source_status="active";p.quality_flag="nominal";
  std::vector<Go2AttitudeWeakPriorMeasurement> rp{p};
  if(c.condition=="rejected"){rp[0].roll_rad=1.2;rp[0].pitch_rad=-1.1;}
  if(c.condition=="no_rows")rp.clear();
  if(c.condition=="no_match")rp[0].time=t+1;
  if(c.condition=="inactive")rp[0].source_status="inactive";
  if(c.condition=="zero_std")rp[0].std_roll_rad=0;
  if(c.condition=="nan_std")rp[0].std_pitch_rad=std::numeric_limits<double>::quiet_NaN();
  if(c.condition=="tolerance_exact")rp[0].time=t+.03125;
  if(c.condition=="tolerance_outside")rp[0].time=std::nextafter(t+.03125,std::numeric_limits<double>::infinity());
  if(c.condition=="tie_last" || c.condition=="tie_last_inactive") {
    rp={p,p};rp[0].time=t-.015625;rp[0].roll_rad=-.08;rp[1].time=t+.015625;
    if(c.condition=="tie_last_inactive")rp[1].source_status="inactive";
  }
  if(c.condition=="closest_inactive") {rp={p,p};rp[0].time=t+.015625;rp[1].source_status="inactive";}
  Go2AttitudeWeakPriorStatus ps;ps.solver_enabled=c.condition!="solver_off";ps.provider_status="available";
  e.setGo2AttitudeWeakPriors(rp,ps);
  RawDopplerVelocityMeasurement d;d.time=t;d.source_time=t;d.velocity_ned_mps={.1,-.05,.02};
  d.std_ned_mps={.1,.1,.1};d.sat_count=8;d.provider_status="available";d.quality="nominal";
  RawDopplerFactorStatus ds;ds.solver_enabled=true;ds.provider_status="available";
  e.setRawDopplerVelocityMeasurements({d},ds);
  Go2VelocityDiagnosticPriorMeasurement h;h.time=t;h.velocity_ned_mps={.1,-.05,0};
  h.std_ned_mps={.2,.2,999};h.source_status="active";h.quality_flag="nominal";h.diagnostic_only=false;
  Go2VelocityDiagnosticPriorStatus hs;hs.solver_enabled=true;hs.provider_status="available";
  e.setGo2VelocityDiagnosticPriors({h},hs);
}
std::string state(const GIEngine& e) {
  std::ostringstream o;o<<std::setprecision(17);const auto s=e.getNavState();
  auto v=[&](const auto& a){for(const auto x:a)o<<x<<',';};
  o<<e.timestamp()<<','<<s.time<<',';v(s.pos_blh_rad_m);v(s.vel_ned_mps);v(s.euler_rad);
  o<<s.qbn.w<<','<<s.qbn.x<<','<<s.qbn.y<<','<<s.qbn.z<<',';
  for(const auto& row:s.cbn)v(row);
  v(s.imu_error.gyrbias);v(s.imu_error.accbias);v(s.imu_error.gyrscale);v(s.imu_error.accscale);
  v(e.getCovariance());return o.str();
}
// A pure-fixture oracle takes the unchanged valid-GNSS res template. Its sole
// valid bit is yaw, but the yaw update and all auxiliaries except RP are disabled.
// Therefore it performs only the original RP helper plus original feedback and
// pvapre reset. GNSS counters differ intentionally and are NOT compared to N09.
// No such carrier or option change exists in the candidate/runtime patch.
GnssData oracleCarrier(const Case& c,double time) {
  auto g=gnss(c,time);g.validity_explicit=true;g.has_position=g.has_velocity=false;
  g.has_yaw=true;g.isvalid=true;return g;
}
bool isValidCase(const Case& c) {
  return c.condition=="valid_all"||c.condition=="valid_yaw_only"||c.condition=="implicit_validity";
}
bool qualifies(const Case& c) {
  for(const auto& x:{"disabled","solver_off","no_rows","no_match","inactive","zero_std","nan_std","tolerance_outside","tie_last_inactive","closest_inactive","no_gnss"})
    if(c.condition==x)return false;
  return !isValidCase(c);
}
void emitCounters(std::ostream& out,const GIEngine& e,const std::string& name,int step) {
  out<<name<<','<<step<<','<<e.propagationCount()<<','<<e.updateCount()<<','<<e.positionUpdateCount()<<','<<e.velocityUpdateCount()<<','<<e.yawUpdateCount()<<','<<e.rawDopplerUpdateCount()<<','<<e.go2AttitudeWeakPriorUpdateCount()<<','<<e.go2AttitudeWeakPriorRejectCount()<<','<<e.go2VelocityDiagnosticPriorUpdateCount();
#ifdef N09_CANDIDATE
  const auto& s=e.rpOnlySchedulingStatus();
  out<<','<<s.input_records<<','<<s.consumed_records<<','<<s.superseded_records<<','<<s.invalid_records<<','<<s.opportunity_count<<','<<s.eligible_count<<','<<s.attempt_count<<','<<s.accepted_count<<','<<s.rejected_count<<','<<s.skipped_count<<','<<s.feedback_count<<','<<s.rp_only_consumed_count<<','<<s.pending;
#else
  for(int i=0;i<13;++i)out<<",NA";
#endif
  out<<'\n';
}
void run(const fs::path& root,const Case& c,bool observed) {
  const auto dir=root/c.name;fs::create_directory(dir);
  if(observed){setenv("LEGSA_V3_OBSERVER_DIR",(dir/"observer").c_str(),1);setenv("LEGSA_V3_OBSERVER_RUN_ID",c.name.c_str(),1);}
  else {unsetenv("LEGSA_V3_OBSERVER_DIR");unsetenv("LEGSA_V3_OBSERVER_RUN_ID");}
  GIEngine e(options(c));e.initialize(initial());loadRows(e,c);e.addImuData(imu(1),true);
  std::unique_ptr<GIEngine> oracle;
  if(qualifies(c)) {
    unsetenv("LEGSA_V3_OBSERVER_DIR");unsetenv("LEGSA_V3_OBSERVER_RUN_ID");
    oracle=std::make_unique<GIEngine>(options(c,true));oracle->initialize(initial());
    loadRows(*oracle,c);oracle->addImuData(imu(1),true);
  }
  std::ofstream states(dir/"STATE.csv"),counts(dir/"COUNTERS.csv");
  std::ofstream oracle_states;if(oracle)oracle_states.open(dir/"ORACLE_STATE.csv");
  counts<<"scenario,step,propagations,gnss_updates,position_updates,rv_updates,yaw_attempts,rd_updates,rp_updates,rp_rejects,hv_updates,input_records,consumed_records,superseded_records,invalid_records,opportunities,eligible,attempts,accepted,rejected,skipped,feedbacks,rp_only_consumed,pending\n";
  for(int step=1;step<=3;++step) {
    if(step==1 && c.condition!="no_gnss") {
      if(c.condition=="superseded_pending")e.addGnssData(gnss(c,2));
      e.addGnssData(gnss(c,eventTime(c)));
      if(oracle)oracle->addGnssData(oracleCarrier(c,eventTime(c)));
    }
    if(step==2 && c.condition=="same_time_new_identity") {
      e.addGnssData(gnss(c,eventTime(c)));
      if(oracle)oracle->addGnssData(oracleCarrier(c,eventTime(c)));
    }
    e.addImuData(imu(1+step*step_dt));e.newImuProcess();
    states<<step<<','<<state(e)<<'\n';emitCounters(counts,e,c.name,step);
    if(oracle) {
      oracle->addImuData(imu(1+step*step_dt));oracle->newImuProcess();
      oracle_states<<step<<','<<state(*oracle)<<'\n';
    }
  }
}
int main(int argc,char**argv) {
  if(argc!=3){std::cerr<<"usage: fixture OUTPUT observer_on|observer_off\n";return 2;}
  try {
    const fs::path root=argv[1];if(fs::exists(root))throw std::runtime_error("refuse existing fixture output");
    fs::create_directories(root);
    for(const auto& c:cases())run(root,c,std::string(argv[2])=="observer_on");
    std::cout<<"COMPLETED "<<cases().size()<<" new pure synthetic N09 scenarios; real native=0\n";
    return 0;
  } catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}
}
