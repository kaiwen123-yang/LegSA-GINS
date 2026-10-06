// Synthetic audit harness. Production source is unchanged. Private access is
// test-only; the runner inserts one capture-only hook in a scratch GIEngine copy.
#include <algorithm>
#include <array>
#include <chrono>
#include <cmath>
#include <cstddef>
#include <deque>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <limits>
#include <map>
#include <numeric>
#include <random>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>
#define private public
#include "legsa_v23_port_core/kf_gins/gi_engine.hpp"
#undef private
#include "legsa_v23_port_core/common/earth.hpp"
#include "legsa_v23_port_core/common/rotation.hpp"
#include "legsa_v23_port_core/factors/go2_weak_prior_factor.hpp"
#include "legsa_v23_port_core/fileio/gnss_file_loader.hpp"
#include "legsa_v23_port_core/fileio/imu_file_loader.hpp"
#include "legsa_v23_port_core/config/port_config_loader.hpp"
using namespace legsa_v23_port_core;
namespace legsa_v23_port_core {
Matrix audit_H, audit_R;
std::vector<double> audit_dz;
void audit_capture(const std::vector<double>& dz, const Matrix& H, const Matrix& R) {
  audit_dz = dz; audit_H = H; audit_R = R;
}
}
void emit(const std::string& key, double value) { std::cout << key << '=' << std::setprecision(17) << value << '\n'; }
NavState state(Vec3 rpy = {0.3,0.4,1.1}) {
  NavState s; s.time=1; s.pos_blh_rad_m={0.5,1.0,20}; s.vel_ned_mps={1,2,0.1};
  s.euler_rad=rpy; s.qbn=Rotation::euler2quaternion(rpy); s.cbn=Rotation::quaternion2matrix(s.qbn); return s;
}
PortOptions opts() {
  PortOptions p; p.data_mode="synthetic_audit"; p.synthetic_data_used=true;
  p.antlever_m={0.03,0.03,-0.30}; p.init_att_std_rad={0.1,0.1,0.1};
  p.raw_doppler_config.enable_raw_doppler=true;
  p.raw_doppler_config.raw_doppler_residual_gate_mps=100;
  p.go2_attitude_prior_config.enable_go2_attitude_weak_prior=true;
  p.go2_velocity_prior_diagnostic_config.enable_go2_velocity_prior_diagnostic=true;
  p.go2_velocity_prior_diagnostic_config.enable_go2_horizontal_velocity_prior=true;
  return p;
}
void sources(GIEngine& e, double time=1.0, std::size_t count=1) {
  RawDopplerVelocityMeasurement rd; rd.time=time; rd.velocity_ned_mps={1,2,0.1}; rd.sat_count=8; rd.provider_status="available";
  RawDopplerFactorStatus rs; rs.provider_status="available"; rs.solver_enabled=true;
  std::vector<RawDopplerVelocityMeasurement> ds(count,rd);
  for(std::size_t i=1;i<count;++i) ds[i].time=100+i;
  e.setRawDopplerVelocityMeasurements(ds,rs);
  Go2AttitudeWeakPriorMeasurement rp; rp.time=time; rp.source_status="active"; rp.roll_rad=0.3; rp.pitch_rad=0.4;
  Go2AttitudeWeakPriorStatus ps; ps.provider_status="available"; ps.solver_enabled=true;
  e.setGo2AttitudeWeakPriors({rp},ps);
  Go2VelocityDiagnosticPriorMeasurement hv; hv.time=time; hv.source_status="active"; hv.velocity_ned_mps={1,2,0.1};
  Go2VelocityDiagnosticPriorStatus hs; hs.provider_status="available"; hs.solver_enabled=true;
  e.setGo2VelocityDiagnosticPriors({hv},hs);
}
struct Capture { Matrix H,R; std::vector<double> dz; };
Capture measure(const std::string& kind, NavState s, int axis=-1, double delta=0) {
  auto o=opts();
  if(axis>=int(BG_ID) && axis<int(BG_ID+3)) o.init_imu_error.gyrbias[axis-BG_ID]=-delta;
  if(axis>=int(SG_ID) && axis<int(SG_ID+3)) o.init_imu_error.gyrscale[axis-SG_ID]=-delta;
  GIEngine e(o); e.initialize(s); sources(e);
  ImuData i; i.dt=0.01; i.time=1; i.dtheta={0.005,-0.004,0.01}; e.addImuData(i,true);
  if(axis>=int(PHI_ID) && axis<int(PHI_ID+3)) {
    Vec3 phi{}; phi[axis-PHI_ID]=-delta;
    e.pvacur_.qbn=Rotation::multiply(Rotation::rotvec2quaternion(phi),s.qbn);
    e.pvacur_.cbn=Rotation::quaternion2matrix(e.pvacur_.qbn);
    e.pvacur_.euler_rad=Rotation::matrix2euler(e.pvacur_.cbn);
  }
  if(axis>=0 && axis<3) { Vec3 p{}; p[axis]=delta; e.pvacur_.pos_blh_rad_m=add(s.pos_blh_rad_m,multiply(Earth::DRi(s.pos_blh_rad_m),p)); }
  if(axis>=int(V_ID) && axis<int(V_ID+3)) e.pvacur_.vel_ned_mps[axis-V_ID]+=delta;
  GnssData g; g.time=1; g.isvalid=true; g.blh_rad_m=s.pos_blh_rad_m; g.yaw_rad=s.euler_rad[2];
  g.vel_ned_mps=s.vel_ned_mps;
  audit_H=Matrix(); audit_dz.clear();
  if(kind=="position") e.applyPositionUpdate(g);
  else if(kind=="rv") e.applyVelocityUpdate(g);
  else if(kind=="rd") e.applyRawDopplerUpdateForTime(1);
  else if(kind=="rp") e.applyGo2AttitudeWeakPriorForTime(1);
  else if(kind=="hv") e.applyGo2VelocityDiagnosticPriorForTime(1);
  else if(kind=="yaw") e.applyYawUpdate(g);
  else if(kind=="basic_yaw") e.applyBasicDualYawUpdate(g);
  return {audit_H,audit_R,audit_dz};
}
void jacobians() {
  const auto s=state();
  for(const std::string kind: {"position","rv","rd","rp","hv","yaw","basic_yaw"}) {
    auto base=measure(kind,s); double ab=0, rel=0, bias=0, scaleerr=0;
    for(int col=0; col<int(RANK); ++col) {
      const double h=col<3?0.01:1e-6;
      auto plus=measure(kind,s,col,h), minus=measure(kind,s,col,-h);
      for(std::size_t row=0;row<base.dz.size();++row) {
        double d=plus.dz[row]-minus.dz[row];
        if(kind=="rp" || kind=="yaw" || kind=="basic_yaw") d=Rotation::wrapRad(d);
        const double fd=d/(2*h), err=std::fabs(fd-base.H(row,col));
        if(col>=int(BG_ID)&&col<int(BG_ID+3)) bias=std::max(bias,err);
        else if(col>=int(SG_ID)&&col<int(SG_ID+3)) scaleerr=std::max(scaleerr,err);
        else { ab=std::max(ab,err); rel=std::max(rel,err/std::max(1e-9,std::fabs(fd))); }
      }
    }
    emit(kind+"_max_abs_error",ab); emit(kind+"_max_relative_error_floor1e9",rel);
    emit(kind+"_gyro_bias_abs_error",bias); emit(kind+"_gyro_scale_abs_error",scaleerr);
  }
  Baseline3dMeasurement ob; ob.valid=true; ob.pacc1_m=ob.pacc2_m=0.02;
  ob.ned_m=multiply(s.cbn,Vec3{0,-0.35,0});
  auto b=buildBaseline3dModel(s.cbn,ob,0.35,1); double err=0,gauge=0;
  for(int a=0;a<3;++a) {
    Vec3 v{};v[a]=1e-6;
    auto cp=multiply(Rotation::quaternion2matrix(Rotation::rotvec2quaternion(scale(v,-1))),s.cbn);
    auto cm=multiply(Rotation::quaternion2matrix(Rotation::rotvec2quaternion(v)),s.cbn);
    auto p=buildBaseline3dModel(cp,ob,0.35,1), m=buildBaseline3dModel(cm,ob,0.35,1);
    for(int r=0;r<3;++r)err=std::max(err,std::fabs((p.residual_m[r]-m.residual_m[r])/2e-6-b.H(r,PHI_ID+a)));
  }
  for(int r=0;r<3;++r) { double z=0;for(int c=0;c<3;++c)z+=b.H(r,PHI_ID+c)*b.predicted_m[c];gauge=std::max(gauge,std::fabs(z)); }
  emit("b3_jacobian_max_abs",err); emit("b3_axis_nullspace_max_abs",gauge);
  emit("lateral_plus90_minus_euler_yaw_deg",Rotation::wrapRad(std::atan2(ob.ned_m[1],ob.ned_m[0])+kPi/2-s.euler_rad[2])*R2D);
  auto tilted=state({0.3,75*D2R,1.1}); auto rp=measure("rp",tilted); auto plus=measure("rp",tilted,PHI_ID,1e-6),minus=measure("rp",tilted,PHI_ID,-1e-6);
  emit("rp_75deg_cap_derivative_error",(plus.dz[0]-minus.dz[0])/2e-6-rp.H(0,PHI_ID));
  for(const auto& rpy: {Vec3{0,0,179.99*D2R},Vec3{0,0,-179.99*D2R},Vec3{0.3,0,1.1}}) {
    auto n=state(rpy); auto ba=measure("yaw",n); double er=0;
    for(int c=0;c<3;++c) {auto p=measure("yaw",n,PHI_ID+c,1e-6),m=measure("yaw",n,PHI_ID+c,-1e-6);er=std::max(er,std::fabs(Rotation::wrapRad(p.dz[0]-m.dz[0])/2e-6-ba.H(0,PHI_ID+c)));}
    emit("yaw_horizontal_or_zero_pitch_abs",er);
  }
}
void numeric() {
  Matrix m(2,2); m(0,2)=42;emit("column_oob_mutated_next_row",m(1,0)==42);
  for(double v:{1e-16,1e-14,1.0}) {try {auto x=inverse(scale(identityMatrix(2),v));emit("inverse_scale_"+std::to_string(v),x(0,0));}catch(const std::exception&){emit("inverse_1e16_identity_rejected",v==1e-16);}}
  Matrix nan=identityMatrix(2);nan(0,0)=std::numeric_limits<double>::quiet_NaN();
  auto inv=inverse(nan);emit("inverse_nan_returned_nonfinite",!std::isfinite(inv(0,0)));
  auto q=Rotation::normalize(Quaternion{1e308,1e308,0,0});emit("huge_quaternion_normalized_norm",std::hypot(q.w,q.x));
  for(double pitch: {87.0,88.0,89.0,90.0,-88.0}) {
    auto c=Rotation::euler2matrix({0.7,pitch*D2R,1.1});auto ec=Rotation::euler2matrix(Rotation::matrix2euler(c));double e=0;
    for(int r=0;r<3;++r)for(int col=0;col<3;++col)e=std::max(e,std::fabs(c[r][col]-ec[r][col]));
    emit("euler_reconstruction_max_matrix_error_pitch_"+std::to_string(pitch),e);
  }
  GIEngine e(opts());e.initialize(state());Matrix bad=identityMatrix(RANK);bad(0,1)=bad(1,0)=2;e.setCovarianceMatrix(bad);
  emit("indefinite_covariance_checkCov_pass",e.checkCov());bad(0,1)=std::numeric_limits<double>::quiet_NaN();e.setCovarianceMatrix(bad);emit("offdiagonal_nan_checkCov_pass",e.checkCov());
}
void scheduler() {
  GIEngine e(opts());e.initialize(state());sources(e,1.01);GnssData g;g.time=1;g.validity_explicit=true;g.has_position=g.has_velocity=g.has_yaw=false;
  e.addGnssData(g);e.gnssUpdate();emit("all_gnss_invalid_rd_count",e.rawDopplerUpdateCount());emit("all_gnss_invalid_rp_count",e.go2AttitudeWeakPriorUpdateCount());emit("all_gnss_invalid_hv_count",e.go2VelocityDiagnosticPriorUpdateCount());
  for(double t:{1.0,1.005}) {g.time=t;g.isvalid=true; e.gnssUpdate(g);}
  emit("future_single_record_rd_consumptions",e.rawDopplerUpdateCount());emit("future_single_record_rp_consumptions",e.go2AttitudeWeakPriorUpdateCount());emit("future_single_record_hv_consumptions",e.go2VelocityDiagnosticPriorUpdateCount());
  emit("isToUpdate_imu_1_1p01_obs_1p0105",e.isToUpdate(1,1.01,1.0105));
  ImuData prev,cur;prev.time=cur.time=1;cur.dt=0.01;cur.dtheta={1,0,0};auto mid=e.imuInterpolate(prev,cur,1);emit("duplicate_imu_interpolate_nonfinite",!std::isfinite(mid.dtheta[0]));
}
void nisreset() {
  auto o=opts();o.source_aware_policy_config.enable_source_aware_weighting=true;o.source_aware_policy_config.source_aware_mode="lsim_oim";
  GIEngine e(o);e.initialize(state());e.Cov_=identityMatrix(RANK);e.dx_[V_ID]=1;
  Matrix h(1,RANK);h(0,V_ID)=1;Matrix r(1,1,1),scaled;source_aware::SourceMetadata md;md.source=source_aware::MeasurementSource::kReceiverVelocity;
  auto result=e.applySourceAwareWeighting(md.source,md,{1},h,r,scaled);emit("sa_reported_nis_dz1_hdx1",result.nis);emit("actual_innovation_nis_dz1_hdx1",0);
  e.dx_[PHI_ID]=0.1;auto before=e.getCovariance();e.stateFeedback();double diff=0;for(std::size_t i=0;i<before.size();++i)diff=std::max(diff,std::fabs(before[i]-e.getCovariance()[i]));emit("stateFeedback_covariance_change",diff);
}
void performance() {
  for(std::size_t n:{100u,10000u,100000u}) {
    GIEngine e(opts());e.initialize(state());sources(e,1,n);const auto a=std::chrono::steady_clock::now();
    for(int i=0;i<30;++i)e.applyRawDopplerUpdateForTime(1);
    emit("rd_30_updates_provider_rows_"+std::to_string(n)+"_ms",std::chrono::duration<double,std::milli>(std::chrono::steady_clock::now()-a).count());
  }
}
void integration() {
  for(const std::string name:{"static","translation","tilt_rotation","all_gnss_dropout"}) {
    auto o=opts();o.enable_receiver_velocity_update=false;o.enable_dual_yaw_update=false;GIEngine e(o);
    auto truth=state(name=="tilt_rotation"?Vec3{0.3,0.4,1.1}:Vec3{0,0,0});truth.time=0;truth.vel_ned_mps=name=="translation"?Vec3{1,0,0}:Vec3{};e.initialize(truth);sources(e,0);
    double maxsym=0,mindiag=1e99,maxvel=0;bool finite=true;
    for(int k=0;k<=1000;++k){
      ImuData i;i.time=k*0.01;i.dt=0.01;
      Vec3 earth=Earth::iewn(truth.pos_blh_rad_m);Vec3 omega=multiply(transpose(truth.cbn),earth);if(name=="tilt_rotation")omega[2]+=0.1;
      i.dtheta=scale(omega,i.dt);i.dvel=scale(multiply(transpose(truth.cbn),Vec3{0,0,-Earth::gravity(truth.pos_blh_rad_m)}),i.dt);
      if(k==0){e.addImuData(i,true);continue;}
      if(k%20==0){GnssData g;g.time=i.time;g.validity_explicit=true;g.has_position=name!="all_gnss_dropout";g.has_velocity=g.has_yaw=false;g.blh_rad_m=add(truth.pos_blh_rad_m,multiply(Earth::DRi(truth.pos_blh_rad_m),scale(truth.vel_ned_mps,i.time)));g.std_ned_m={0.1,0.1,0.1};e.addGnssData(g);}
      e.addImuData(i);e.newImuProcess();auto c=e.covarianceMatrix();
      for(int r=0;r<int(RANK);++r){mindiag=std::min(mindiag,c(r,r));for(int col=0;col<int(RANK);++col){finite&=std::isfinite(c(r,col));maxsym=std::max(maxsym,std::fabs(c(r,col)-c(col,r)));}}
      for(double v:e.navState().pos_blh_rad_m)finite&=std::isfinite(v);
      maxvel=std::max(maxvel,norm(e.navState().vel_ned_mps));
      if(name=="tilt_rotation") {truth.qbn=Rotation::multiply(truth.qbn,Rotation::rotvec2quaternion({0,0,0.001}));truth.cbn=Rotation::quaternion2matrix(truth.qbn);}
    }
    emit(name+"_finite",finite);emit(name+"_cov_symmetry_max",maxsym);emit(name+"_cov_diagonal_min",mindiag);emit(name+"_max_speed",maxvel);emit(name+"_position_updates",e.positionUpdateCount());emit(name+"_propagations",e.propagationCount());
  }
}
int main(int argc,char**argv){try {
  if(argc<2)return 2;std::string mode=argv[1];
  if(mode=="jacobians")jacobians();else if(mode=="numeric")numeric();else if(mode=="scheduler")scheduler();else if(mode=="nisreset")nisreset();else if(mode=="performance")performance();else if(mode=="integration")integration();
  else if(mode=="wrap")emit("wrap",Rotation::wrapRad(std::stod(argv[2])));
  else if(mode=="wrap2pi")emit("wrap2pi",Rotation::wrap2Pi(std::stod(argv[2])));
  else if(mode=="loader") {auto i=ImuFileLoader::loadSevenColumn(argv[2]);auto g=GnssFileLoader::loadFifteenColumn(argv[3]);emit("imu_rows",i.size());emit("gnss_rows",g.size());if(!g.empty())emit("lat_native",g.front().blh_rad_m[0]);if(i.size()>1)emit("last_dt",i.back().dt);}
  else if(mode=="config") {auto o=PortConfigLoader::loadYamlLike(argv[2]);emit("endtime",o.endtime);emit("starttime",o.starttime);emit("dual_yaw",o.enable_dual_yaw_update);emit("lever0",o.antlever_m[0]);std::cout<<"imu_path="<<o.imu_path<<'\n';}
  else return 3;return 0;
}catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 1;}}
