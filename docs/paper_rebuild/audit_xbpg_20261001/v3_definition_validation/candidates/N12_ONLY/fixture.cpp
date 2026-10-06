// New synthetic tests through the actual public GIEngine update path.
// No provider/config/reference is read. The same source runs against both libraries.
#include "legsa_v23_port_core/kf_gins/gi_engine.hpp"
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <iostream>
using namespace legsa_v23_port_core;
namespace fs=std::filesystem;
using mechanism_observer::Json;

void scenario(const fs::path& root,const std::string& name){
  const auto out=root/name;fs::create_directories(out);
  setenv("LEGSA_V3_OBSERVER_DIR",(out/"observer").c_str(),1);
  setenv("LEGSA_V3_OBSERVER_RUN_ID",name.c_str(),1);
  PortOptions o;o.data_mode="synthetic_fixture_only";o.synthetic_data_used=true;
  o.clean_final_v23_parity_mode=true;o.antlever_m={0,0,0};
  o.enable_receiver_velocity_update=true;o.enable_dual_yaw_update=true;o.yaw_scheme_C_enabled=true;
  o.source_aware_policy_config.enable_source_aware_weighting=name!="sa_off"&&name!="rd_saoff_gate";
  o.source_aware_policy_config.source_aware_mode="lsim_oim";
  o.source_aware_policy_config.source_aware_use_innovation_covariance=name!="fallback_no_S";
  o.raw_doppler_config.enable_raw_doppler=name=="rd_saoff_gate";
  o.go2_attitude_prior_config.enable_go2_attitude_weak_prior=false;
  o.go2_velocity_prior_diagnostic_config.enable_go2_velocity_prior_diagnostic=false;
  GIEngine e(o);NavState s;s.pos_blh_rad_m={.5,1,10};s.vel_ned_mps={1,2,3};e.initialize(s);
  Matrix p(RANK,RANK,0);for(std::size_t i=0;i<RANK;++i)p(i,i)=1;
  if(name=="correlated_S"){p(V_ID+1,V_ID+1)=2;p(V_ID+2,V_ID+2)=3;p(V_ID,V_ID+1)=p(V_ID+1,V_ID)=.6;p(V_ID+1,V_ID+2)=p(V_ID+2,V_ID+1)=.2;}
  // Public synthetic prediction: Phi=0, Qd=p sets a known P and zero dx.
  // This fixture-only setup is not a change to the solver or a real input.
  e.EKFPredict(Matrix(RANK,RANK,0),p);
  if(name!="dx_zero"&&name!="yaw_hard_gate"&&name!="rd_saoff_gate"){
    Matrix h(3,RANK,0),r(3,3,0);for(int i=0;i<3;++i){h(i,V_ID+i)=1;r(i,i)=1;}
    const std::vector<double> z=name=="dz_equals_Hdx"?std::vector<double>{1,0,0}:std::vector<double>{4,-2,1};
    e.EKFUpdate(z,h,r); // accumulated conditional mean; deliberately no feedback yet.
  }
  if(name=="rd_saoff_gate"){
    RawDopplerVelocityMeasurement r;r.time=1;r.source_time=1;r.velocity_ned_mps={50,0,0};r.std_ned_mps={.05,.05,.05};r.provider_status="available";r.quality="nominal";r.sat_count=8;
    RawDopplerFactorStatus rs;rs.solver_enabled=true;rs.provider_status="available";e.setRawDopplerVelocityMeasurements({r},rs);
  }
  const int attempts=name=="two_sequential_SA"?2:1;
  for(int n=0;n<attempts;++n){
    GnssData g;g.time=1+.2*n;g.validity_explicit=true;g.has_position=false;g.has_velocity=true;g.has_yaw=false;
    const Vec3 raw=name=="dz_equals_Hdx"?Vec3{.5,0,0}:Vec3{3,-1.5,.8};
    g.vel_ned_mps={s.vel_ned_mps[0]-raw[0],s.vel_ned_mps[1]-raw[1],s.vel_ned_mps[2]-raw[2]};g.vel_std_mps={.1,.2,.3};
    if(name=="yaw_hard_gate"||name=="rd_saoff_gate"){
      g.has_velocity=false;g.has_yaw=true;g.yaw_deg=90;g.yaw_rad=90*D2R;g.yaw_std_deg=20;g.yaw_std_rad=20*D2R;
    }
    e.addGnssData(g);e.gnssUpdate();
  }
  e.stateFeedback();
  const auto nav=e.getNavState();
  std::ofstream f(out/"SCIENTIFIC_STATE.json");
  f<<Json().add("position",nav.pos_blh_rad_m).add("velocity",nav.vel_ned_mps).add("rpy",nav.euler_rad)
    .add("P_flat_row_major",e.getCovariance()).add("gnss_count",e.updateCount()).add("RV",e.velocityUpdateCount())
    .add("yaw_attempt",e.yawUpdateCount()).add("yaw_reject",e.yawRejectCount()).add("RD",e.rawDopplerUpdateCount())
    .add("RD_reject",e.rawDopplerRejectCount()).add("RP",e.go2AttitudeWeakPriorUpdateCount())
    .add("HV",e.go2VelocityDiagnosticPriorUpdateCount()).str()<<'\n';
}

int main(int argc,char** argv){
  if(argc!=2)return 2;
  try{
    fs::path out=argv[1];if(fs::exists(out))throw std::runtime_error("refuse fixture output reuse");
    fs::create_directories(out);
    for(const auto& name:{"dx_zero","dz_equals_Hdx","sequential_general","correlated_S","fallback_no_S","sa_off","two_sequential_SA","yaw_hard_gate","rd_saoff_gate"})scenario(out,name);
    std::cout<<"9 new synthetic scenarios complete; no real inputs\n";return 0;
  }catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}
}
