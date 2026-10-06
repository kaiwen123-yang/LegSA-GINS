// Follow-up experiments justified by findings in native_audit.cpp. The initial
// fixture is retained byte-for-byte so its receipt remains reproducible.
#define main native_initial_main
#include "native_audit.cpp"
#undef main
#include "legsa_v23_port_core/fileio/file_saver.hpp"
#include "legsa_v23_port_core/factors/go2_weak_prior_loader.hpp"
#include "legsa_v23_port_core/factors/raw_doppler_factor_loader.hpp"

double choleskyMinPivot(const Matrix& p) {
  Matrix l(p.rows,p.cols); double minimum=1e99;
  for(std::size_t i=0;i<p.rows;++i) for(std::size_t j=0;j<=i;++j) {
    double v=p(i,j); for(std::size_t k=0;k<j;++k)v-=l(i,k)*l(j,k);
    if(i==j) { minimum=std::min(minimum,v); if(!(v>0) || !std::isfinite(v)) return v; l(i,j)=std::sqrt(v); }
    else l(i,j)=v/l(j,j);
  }
  return minimum;
}

void positionSteps() {
  const auto s=state(); const auto base=measure("position",s);
  for(double step:{1e-2,1e-3,1e-4,1e-5,1e-6}) {
    double error=0,reference=0,squared=0,referenceSquared=0;
    for(int c=0;c<3;++c) {
      auto p=measure("position",s,PHI_ID+c,step),m=measure("position",s,PHI_ID+c,-step);
      for(int r=0;r<3;++r) {double fd=(p.dz[r]-m.dz[r])/(2*step),d=fd-base.H(r,PHI_ID+c);
        error=std::max(error,std::fabs(d));reference=std::max(reference,std::fabs(fd));squared+=d*d;referenceSquared+=fd*fd;}
    }
    emit("position_attitude_step_"+std::to_string(step)+"_maxabs",error);
    emit("position_attitude_step_"+std::to_string(step)+"_frobenius_relative",std::sqrt(squared/referenceSquared));
  }
}

void asynchronousLever() {
  for(double time:{1.0,1.5,2.0}) {
    auto o=opts();o.enable_dual_yaw_update=false;o.enable_receiver_velocity_update=true;
    o.raw_doppler_config.enable_raw_doppler=false;o.go2_attitude_prior_config.enable_go2_attitude_weak_prior=false;
    o.go2_velocity_prior_diagnostic_config.enable_go2_velocity_prior_diagnostic=false;
    o.init_imu_error.gyrbias={0.4,-0.3,0.2};
    GIEngine e(o);auto initial=state({0,0,0});initial.vel_ned_mps={0,0,0};e.initialize(initial);
    ImuData previous;previous.time=1;previous.dt=1;previous.dtheta=o.init_imu_error.gyrbias;
    previous.dvel={0,0,-Earth::gravity(initial.pos_blh_rad_m)};e.addImuData(previous,true);
    GnssData g;g.time=time;g.validity_explicit=true;g.has_position=false;g.has_yaw=false;g.has_velocity=true;g.vel_ned_mps={0,0,0};g.vel_std_mps={100,100,100};e.addGnssData(g);
    auto current=previous;current.time=2;current.compensated=false;e.addImuData(current);e.newImuProcess();
    double norm=0;for(int r=0;r<3;++r)for(int c=0;c<3;++c)norm+=audit_H(r,PHI_ID+c)*audit_H(r,PHI_ID+c);
    emit("update_time_"+std::to_string(time)+"_Hphi_frobenius",std::sqrt(norm));
    emit("update_time_"+std::to_string(time)+"_captured_residual_norm",std::sqrt(std::inner_product(audit_dz.begin(),audit_dz.end(),audit_dz.begin(),0.0)));
  }
}

void horizontalSentinel() {
  for(bool disabled:{false,true}) {
    auto o=opts();o.source_aware_policy_config.enable_source_aware_weighting=true;o.source_aware_policy_config.source_aware_mode="lsim_only";
    o.go2_velocity_prior_diagnostic_config.go2_horizontal_velocity_prior_vertical_disabled=disabled;
    GIEngine e(o);e.initialize(state());sources(e);e.applyGo2VelocityDiagnosticPriorForTime(1);
    emit(std::string("hv_R00_vertical_disabled_")+(disabled?"true":"false"),audit_R(0,0));
  }
}

void consistency() {
  constexpr int trials=2000;std::mt19937_64 generator(20261001);std::normal_distribution<double> normal;
  auto o=opts();o.antlever_m={0,0,0};double nis=0,nees=0,minimum=1e99,posteriorErrorSum[3]={};
  const Vec3 variance={0.25,1,4};
  for(int k=0;k<trials;++k) {
    GIEngine e(o);auto initial=state({0,0,0});initial.vel_ned_mps={normal(generator),normal(generator),normal(generator)};e.initialize(initial);e.setCovarianceMatrix(identityMatrix(RANK));
    GnssData g;g.time=1;for(int j=0;j<3;++j){g.vel_ned_mps[j]=std::sqrt(variance[j])*normal(generator);g.vel_std_mps[j]=std::sqrt(variance[j])-0.05;}
    e.applyVelocityUpdate(g);for(int j=0;j<3;++j)nis+=audit_dz[j]*audit_dz[j]/(1+variance[j]);
    e.stateFeedback();auto p=e.covarianceMatrix();minimum=std::min(minimum,choleskyMinPivot(p));
    for(int j=0;j<3;++j){double error=e.navState().vel_ned_mps[j];nees+=error*error/p(V_ID+j,V_ID+j);posteriorErrorSum[j]+=error;}
  }
  emit("independent_trials",trials);emit("measurement_dof",3);emit("velocity_state_dof",3);
  emit("ungated_mean_NIS",nis/trials);emit("velocity_posterior_mean_NEES",nees/trials);emit("posterior_min_cholesky_pivot",minimum);
  emit("theoretical_mean",3);emit("mean_two_sided_approx_95pct_halfwidth",1.96*std::sqrt(6.0/trials));
  for(int j=0;j<3;++j)emit("posterior_velocity_mean_axis_"+std::to_string(j),posteriorErrorSum[j]/trials);
}

void saverFailures(const std::string& root) {
  std::filesystem::create_directories(root);
  std::vector<double> covariance(RANK,1);covariance[0]=-1;covariance[1]=std::numeric_limits<double>::quiet_NaN();covariance[PHI_ID]=0.01;covariance[PHI_ID+1]=0.04;covariance[PHI_ID+2]=0.09;
  FileSaver::writeStd(root,{covariance});
  std::ifstream f(std::filesystem::path(root)/"LegSA_PORT_STD.csv");std::string line;std::getline(f,line);std::getline(f,line);std::cout<<"std_negative_nan_row="<<line<<'\n';
  std::filesystem::create_directories(std::filesystem::path(root)/"LegSA_PORT_NAV.nav");
  bool threw=false;try{FileSaver::writeNav(root,{state()});}catch(...){threw=true;}
  emit("nav_writer_open_failure_throws",threw);
  auto y=measure("yaw",state());double exactvar=0;double eps=1e-5;
  for(int c=0;c<3;++c){auto a=measure("yaw",state(),PHI_ID+c,eps),b=measure("yaw",state(),PHI_ID+c,-eps);double d=Rotation::wrapRad(a.dz[0]-b.dz[0])/(2*eps);exactvar+=d*d*covariance[PHI_ID+c];}
  emit("reported_yaw_std_deg",std::sqrt(covariance[PHI_ID+2])*R2D);emit("propagated_euler_yaw_std_deg",std::sqrt(exactvar)*R2D);
}

void missingProviderNumbers(const std::string& root) {
  std::filesystem::create_directories(root);auto rpPath=std::filesystem::path(root)/"missing_rp.csv";
  {std::ofstream f(rpPath);f<<"time,source_status\n1,active\n";}
  auto o=opts();auto loaded=Go2WeakPriorLoader::loadCsv(rpPath.string(),o.go2_attitude_prior_config);
  GIEngine e(o);e.initialize(state());e.setGo2AttitudeWeakPriors(loaded.measurements,loaded.status);e.applyGo2AttitudeWeakPriorForTime(1);
  emit("missing_rp_roll_pitch_loaded_as_zero",loaded.measurements.at(0).roll_rad==0&&loaded.measurements.at(0).pitch_rad==0);
  emit("missing_rp_roll_pitch_native_updates",e.go2AttitudeWeakPriorUpdateCount());
  auto rdPath=std::filesystem::path(root)/"missing_rd.csv";auto& c=o.raw_doppler_config;
  c.formal_lineage_required=true;c.raw_doppler_backend_id="synthetic_audit";c.raw_doppler_backend_source_files="fixture";c.raw_doppler_backend_source_hashes=std::string(64,'a');c.covariance_policy="known_fixture";
  c.helper_executable_hash=c.obs_source_hash=c.nav_source_hash=c.conversion_config_hash=std::string(64,'a');
  {std::ofstream f(rdPath);f<<"time,source_time,vn,ve,vd,std_vn,std_ve,std_vd,sat_count,gdop_like,provider_status,valid,raw_doppler_backend_id,obs_source_hash,nav_source_hash,conversion_config_hash,covariance_policy,quality\n1,1,,,,1,1,1,8,1,available,true,synthetic_audit,"<<c.obs_source_hash<<','<<c.nav_source_hash<<','<<c.conversion_config_hash<<",known_fixture,nominal\n";}
  auto rd=RawDopplerFactorLoader::loadCsv(rdPath.string(),c);GIEngine r(o);r.initialize(state());r.setRawDopplerVelocityMeasurements(rd.measurements,rd.status);r.applyRawDopplerUpdateForTime(1);
  emit("missing_formal_rd_vn_ve_vd_loaded_as_zero",norm(rd.measurements.at(0).velocity_ned_mps)==0);emit("missing_formal_rd_native_updates",r.rawDopplerUpdateCount());
}

int main(int argc,char**argv){try{
  if(argc<2)return 2;std::string m=argv[1];
  if(m=="position_steps")positionSteps();else if(m=="async_lever")asynchronousLever();else if(m=="hv_sentinel")horizontalSentinel();else if(m=="consistency")consistency();else if(m=="saver")saverFailures(argv[2]);else if(m=="missing_provider")missingProviderNumbers(argv[2]);else return 3;
  return 0;
}catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 1;}}
