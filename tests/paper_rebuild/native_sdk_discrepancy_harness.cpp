// One synthetic chain: nuisance-seed batch oracle, both clone orders, full-state replay.
#include "legsa_v23_port_core/kf_gins/gi_engine.hpp"
#include "legsa_v23_port_core/factors/body_velocity_model.hpp"
#include "legsa_v23_port_core/runtime/support_pose_replay.hpp"
#include "legsa_v23_port_core/common/earth.hpp"
#include "legsa_v23_port_core/common/rotation.hpp"
#include <algorithm>
#include <cmath>
#include <filesystem>
#include <iomanip>
#include <iostream>
using namespace legsa_v23_port_core;
namespace pc=legsa_v23_port_core::pose_clone;
void need(bool v,const char* m){if(!v)throw std::runtime_error(m);}
double difference(const Matrix&a,const Matrix&b){need(a.rows==b.rows&&a.cols==b.cols,"matrix size");double x=0;for(std::size_t i=0;i<a.data.size();++i)x=std::max(x,std::abs(a.data[i]-b.data[i]));return x;}
double difference(const std::vector<double>&a,const std::vector<double>&b){need(a.size()==b.size(),"vector size");double x=0;for(std::size_t i=0;i<a.size();++i)x=std::max(x,std::abs(a[i]-b[i]));return x;}
namespace legsa_v23_port_core {
struct SdkDiscrepancyTestAccess {
 static pc::Gaussian joint(const GIEngine&e){return e.supportPoseJointState();}
 static void set(GIEngine&e,const pc::Gaussian&s){e.setSupportPoseJointState(s);}
 static void at(GIEngine&e,double t){e.timestamp_=e.pvacur_.time=t;}
 static void support(GIEngine&e,const SupportPoseEvent&s){at(e,s.time);e.processSupportPoseEvent(s);}
 static void sdk(GIEngine&e,double t){at(e,t);e.applyBodyVelocityPriorForTime(t);}
 static std::vector<double> b(const GIEngine&e){return e.sdkDiscrepancyConditionalMean();}
 static void retire(GIEngine&e){e.retireSupportPose();}
 static std::size_t diagnostic(const GIEngine&e){return e.sdk_discrepancy_diagnostics_.size();}
 static std::string seedId(const GIEngine&e){return e.sdk_discrepancy_seed_identity_;}
 static double lastSdk(const GIEngine&e){return e.research_last_body_hv_attempt_time_;}
};
}
using Access=SdkDiscrepancyTestAccess;
SupportPoseEvent endpoint(double t,const std::string& type) {
 SupportPoseEvent e;e.time=e.available_time=e.source_time=t;e.type=type;e.clone_id="a";
 e.foot_i="FL";e.foot_j="RR";e.episode_i="FL:0";e.episode_j="RR:0";
 e.positions_body_frd={makeVec3(.2,.15,.3),makeVec3(-.2,-.15,.3)};return e;
}
PortOptions options(const std::string& mode="REPLACE_SUPPORT") {
 PortOptions o;o.runtime_contract="research_experiment";o.support_pose_config.mode=mode;
 o.support_pose_config.observed_axes="body0_xyz";o.support_pose_config.events_path="synthetic";
 o.support_pose_config.foot_frd_to_engine_body=identityMatrix3();o.starttime=0;
 o.init_vel_std_mps={.4,.4,.4};o.init_att_std_rad={.03,.03,.1};
 o.dual_antenna_measurement_model="baseline3d";o.baseline3d_source="external_carrier";
 o.baseline3d_body_vector_m={0,.24,0};o.baseline3d_length_m=.24;
 auto& c=o.go2_velocity_prior_diagnostic_config;c.enable_go2_velocity_prior_diagnostic=true;
 c.enable_go2_horizontal_velocity_prior=true;c.go2_horizontal_velocity_frame="body_frd";
 c.go2_body_velocity_discrepancy_mode="joint_constant";c.go2_body_velocity_update_period_s=.01;
 return o;
}
NavState initial(){NavState n;n.time=0;n.pos_blh_rad_m={.55,1.2,80};n.vel_ned_mps={.2,.06,0};return n;}
void provider(GIEngine&e) {
 std::vector<Go2VelocityDiagnosticPriorMeasurement> samples;
 for(int i=1;i<=80;++i){Go2VelocityDiagnosticPriorMeasurement s;s.time=.01*i;s.observation_frame="body_frd";
 s.velocity_body_frd_mps={.27+.002*std::sin(i),.04,0};s.std_body_frd_mps={.2,.2,999};s.source_status="active";samples.push_back(s);}
 Go2VelocityDiagnosticPriorStatus status;status.solver_enabled=true;status.provider_status="available";e.setGo2VelocityDiagnosticPriors(samples,status);
}
void print(const Matrix&a){std::cout<<'[';for(std::size_t i=0;i<a.rows;++i){if(i)std::cout<<',';std::cout<<'[';for(std::size_t j=0;j<a.cols;++j){if(j)std::cout<<',';std::cout<<a(i,j);}std::cout<<']';}std::cout<<']';}
void print(const std::vector<double>&a){std::cout<<'[';for(std::size_t i=0;i<a.size();++i){if(i)std::cout<<',';std::cout<<a[i];}std::cout<<']';}
void gaussian(const pc::Gaussian&s){std::cout<<"{\"P\":";print(s.covariance);std::cout<<",\"mean\":";print(s.mean);std::cout<<'}';}
struct Run {GIEngine engine;std::vector<double> prefix_b;};
Run replay(const std::string& out,bool excluded) {
 const std::vector<SupportPoseEvent> source={endpoint(.02,"START"),endpoint(.12,"END"),endpoint(.2,"REVOKE")};
 GIEngine e(options());provider(e);e.setSupportPoseEvents(source);const auto n=initial();e.initialize(n);
 if(excluded)e.setRevokedSupportFactorIds({"a"});SupportPoseReplay wrapper(!excluded,source);
 ImuData first;first.time=0;first.dt=.01;first.dvel={0,0,-Earth::gravity(n.pos_blh_rad_m)*.01};e.addImuData(first,true);
 std::vector<double> prefix;
 for(int tick=1;tick<=80;++tick){ImuData imu=first;imu.time=tick*.01;imu.compensated=false;
  wrapper.beforeInterval(e,(tick-1)*.01,imu);e.addImuData(imu);std::vector<GnssData> events;
  if(tick==8||tick==16||tick==30){GnssData g;g.time=imu.time;g.isvalid=true;g.validity_explicit=true;
   g.has_position=g.has_velocity=g.has_yaw=false;g.auxiliary_updates_allowed=false;
   g.baseline3d.present=g.baseline3d.valid=true;g.baseline3d.source="external_carrier";
   g.baseline3d.measurement_time=g.baseline3d.decision_available_time=g.time;
   g.baseline3d.ecef_m=multiply(Earth::cne(n.pos_blh_rad_m),makeVec3(-.006,.239925,0));
   g.baseline3d.covariance_ecef_m2=scale(identityMatrix3(),.0001);events.push_back(g);}
  e.newImuProcessWithEvents(events);wrapper.afterInterval(e,(tick-1)*.01,imu,events);
  if(tick==12)prefix=Access::b(e);
 }
 std::filesystem::create_directories(out);wrapper.writeDiagnostics(out);e.writeSdkDiscrepancyDiagnostics(out);
 e.writeSupportPoseDiagnostics(out);e.writeBodyVelocityDiagnostics(out);return {e,prefix};
}
int main(int argc,char**argv){try {
 std::cout<<std::setprecision(17);const std::string out=argv[1];
 // Batch oracle data: free b prior, first SDK, independent anchor, second SDK.
 Matrix l(21,21);std::vector<double> mean(21);
 for(int i=0;i<21;++i){mean[i]=.001*(i-9);for(int j=0;j<21;++j)l(i,j)=(i==j?.2+.003*i:0)+.002*std::sin(i+2*j);}
 const Matrix p=multiply(l,transpose(l));pc::Gaussian prior{p,mean};
 GIEngine seed_engine(options("SDK_NULL"));provider(seed_engine);seed_engine.initialize(initial());Access::set(seed_engine,prior);
 auto model=buildBodyVelocity2dModel(seed_engine.navState(),{.27,.04,0},{.2,.2,999});
 auto seeded=seedBodyVelocityDiscrepancy(prior,model.H,model.R);
 Matrix anchor(2,23);anchor(0,P_ID)=1;anchor(0,V_ID)=.3;anchor(1,V_ID+1)=1;
 Matrix ra(2,2);ra(0,0)=.006;ra(1,1)=.009;std::vector<double> za{.03,-.02};
 const auto anchored=pc::ordinaryUpdate(seeded,za,anchor,ra);
 Matrix h2=model.H;h2(0,PHI_ID+2)+=.2;h2(1,V_ID)+=.1;
 Matrix fullh=bodyVelocityDiscrepancyJacobian(h2,23),r2=scale(model.R,.7);std::vector<double> z2{.06,-.03};
 const auto posterior=pc::ordinaryUpdate(anchored,z2,fullh,r2);
 need(fullh(0,21)==-1 && fullh(1,22)==-1,"additive b derivative sign");
 std::cout<<"{\"prior\":";gaussian(prior);std::cout<<",\"H1\":";print(model.H);std::cout<<",\"R1\":";print(model.R);
 std::cout<<",\"seed\":";gaussian(seeded);std::cout<<",\"anchor_H\":";print(anchor);std::cout<<",\"anchor_R\":";print(ra);
 std::cout<<",\"anchor_z\":";print(za);std::cout<<",\"H2\":";print(fullh);std::cout<<",\"R2\":";print(r2);std::cout<<",\"z2\":";print(z2);
 std::cout<<",\"posterior\":";gaussian(posterior);
 // First seed with existing clone must preserve the complete old27 marginal.
 Access::support(seed_engine,endpoint(.02,"START"));const auto before=Access::joint(seed_engine);
 const auto sa_before=seed_engine.sourceAwareEvaluationCount();Access::sdk(seed_engine,.03);const auto after=Access::joint(seed_engine);
 double seed_delta=0;for(std::size_t i=0;i<27;++i){const auto ii=i<21?i:i+2;seed_delta=std::max(seed_delta,std::abs(before.mean[i]-after.mean[ii]));
  for(std::size_t j=0;j<27;++j)seed_delta=std::max(seed_delta,std::abs(before.covariance(i,j)-after.covariance(ii,j<21?j:j+2)));}
 need(seed_delta==0,"seed altered navigation/clone marginal");
 need(seed_engine.go2VelocityDiagnosticPriorUpdateCount()==0 && seed_engine.sourceAwareEvaluationCount()==sa_before,"seed double counted");
 // Other order: 21->23 seed followed by actual START produces 29 with J Pxb.
 GIEngine order(options("SDK_NULL"));provider(order);order.initialize(initial());Access::set(order,prior);Access::sdk(order,.01);
 const auto current=Access::joint(order);const auto expected=pc::augment(current.covariance,current.mean,pc::augmentationJacobian(order.navState().pos_blh_rad_m));
 Access::support(order,endpoint(.02,"START"));const auto joint=Access::joint(order);need(difference(joint.covariance,expected.covariance)==0,"seed/start joint cross");
 Matrix phi=identityMatrix(21),q(21,21);for(int i=0;i<3;++i){phi(i,3+i)=.1;phi(6+i,9+i)=.03;}for(int i=0;i<21;++i)q(i,i)=1e-7;
 const auto expected_propagated=pc::propagate(joint,phi,q);order.EKFPredict(phi,q);const auto propagated=Access::joint(order);
 const double prop_diff=difference(propagated.covariance,expected_propagated.covariance);need(prop_diff<2e-15,"joint propagation cross");
 auto resetting=propagated;resetting.mean.assign(29,0);resetting.mean[6]=.04;resetting.mean[7]=-.03;resetting.mean[8]=.02;
 resetting.mean[21]=.007;resetting.mean[22]=-.006;resetting.mean[26]=-.02;resetting.mean[27]=.01;resetting.mean[28]=.03;
 Access::set(order,resetting);const auto b_before=Access::b(order);order.stateFeedback();const auto reset=Access::joint(order);
 need(difference(b_before,Access::b(order))<1e-16,"b additive feedback lost");
 Access::retire(order);const auto marginal=Access::joint(order);double retire_delta=0;
 for(int i=0;i<23;++i)for(int j=0;j<23;++j)retire_delta=std::max(retire_delta,std::abs(marginal.covariance(i,j)-reset.covariance(i,j)));
 need(retire_delta==0 && marginal.mean.size()==23,"retirement lost b marginal");
 std::cout<<",\"seed_old27_marginal_max_change\":"<<seed_delta<<",\"seed_no_SA_evaluation\":true,\"START_23_to_29_exact\":true,\"propagation_max_abs\":"<<prop_diff;
 std::cout<<",\"reset_before\":";gaussian(resetting);std::cout<<",\"reset_after\":";gaussian(reset);std::cout<<",\"retire_23_marginal_max_change\":"<<retire_delta;
 // Actual 0.5s whole-engine replay, with SDK seeded before foot and carrier retained.
 auto actual=replay(out+"/replay",false);auto control=replay(out+"/never_consumed",true);
 const double fullp=difference(Access::joint(actual.engine).covariance,Access::joint(control.engine).covariance);
 const double bdiff=difference(Access::b(actual.engine),Access::b(control.engine));
 const double prefixdiff=difference(actual.prefix_b,control.prefix_b);
 const double vdiff=norm(subtract(actual.engine.navState().vel_ned_mps,control.engine.navState().vel_ned_mps));
 need(fullp<1e-12&&bdiff<1e-12&&vdiff<1e-12&&prefixdiff>1e-7,"full b replay restoration");
 need(actual.engine.supportPoseCounts().accepted==0&&actual.engine.baseline3dCounts().accepted==3,"replay factor acceptance");
 need(Access::seedId(actual.engine)==Access::seedId(control.engine)&&Access::lastSdk(actual.engine)==Access::lastSdk(control.engine),"replay source identity");
 std::cout<<",\"replay_full23_P_max_difference\":"<<fullp<<",\"replay_b_max_difference\":"<<bdiff<<",\"replay_v_difference\":"<<vdiff
          <<",\"pre_revoke_b_difference\":"<<prefixdiff<<",\"replay_carrier_acceptances\":"<<actual.engine.baseline3dCounts().accepted<<",\"pass_native_chain\":true}\n";
 return 0;
 }catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 1;}}
