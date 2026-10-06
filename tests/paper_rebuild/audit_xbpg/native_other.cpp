// New counterexamples for the two OTHER targets. No port-core replacement.
#include "legsa_gins/filter/legsa_filter.hpp"
#include "legsa_gins/filter/diag_covariance.hpp"
#include "legsa_v23_core/common/rotation.hpp"
#include "legsa_v23_core/common/earth.hpp"
#include "legsa_v23_core/filter/error_state_matrices.hpp"
#include "legsa_v23_core/mechanization/ins_mechanization.hpp"
#include "legsa_v23_core/runtime/legsa_v23_engine.hpp"
#include <algorithm>
#include <cmath>
#include <iomanip>
#include <iostream>

void emit(const char* key, double value) { std::cout << key << '=' << std::setprecision(17) << value << '\n'; }

int main() {
  namespace old = legsa_gins;
  old::types::LegSAFilterState initial;
  initial.pva.blh_rad_m={0.5,1.0,10.0};
  old::types::DiagCovariance21 covariance;
  covariance.diag.fill(1.0);
  old::filter::LegSAFilter filter;
  filter.initialize(initial,covariance);
  old::types::LegSAImuSample previous, current;
  previous.tow=0.0;current.tow=1.0;current.dt=1.0;
  filter.predict(previous,current);
  emit("old_predict_covariance_unchanged",filter.getCovariance().diag==covariance.diag);
  filter.initialize(initial,covariance);
  old::types::ReceiverNativeMeasurement future;
  future.tow=2.0;future.has_velocity=true;future.vel_ned_mps={10,0,0};future.vel_std_mps={0.1,0.1,0.1};
  filter.process({previous,current},{future});
  emit("old_future_measurement_time",future.tow);
  emit("old_last_imu_time",current.tow);
  emit("old_final_state_time",filter.getState().pva.tow);
  emit("old_final_north_velocity",filter.getState().pva.vel_ned_mps.x);

  namespace v23=legsa_v23_core;
  v23::PVAState state;
  state.pos_blh_rad_m={0.5,1.0,10.0};state.euler_rpy_rad={0.3,0.4,0.9};
  v23::IMUData imu;imu.dt=0.01;imu.dvel={0.02,-0.03,-0.098};
  v23::GINSOptions options;
  const auto matrices=v23::buildErrorStateMatrices(state,imu,options,v23::diagonalNoiseMatrix(1e-6));
  const auto q=v23::Rotation::euler2quaternion(state.euler_rpy_rad);
  double max_error=0.0;
  constexpr double step=1e-6;
  for(std::size_t column=0;column<3;++column){
    v23::Vector3 direction{};direction[column]=step;
    auto plus=v23::Rotation::quaternion2matrix(v23::Rotation::multiply(v23::Rotation::rotvec2quaternion(direction),q));
    direction[column]=-step;
    auto minus=v23::Rotation::quaternion2matrix(v23::Rotation::multiply(v23::Rotation::rotvec2quaternion(direction),q));
    for(std::size_t row=0;row<3;++row){
      double derivative=0.0;
      for(std::size_t k=0;k<3;++k) derivative-=(v23::matrix3At(plus,row,k)-v23::matrix3At(minus,row,k))*imu.dvel[k]/(2*step*imu.dt);
      max_error=std::max(max_error,std::abs(derivative-v23::matrix21At(matrices.F,v23::V_ID+row,v23::PHI_ID+column)));
    }
  }
  emit("v23_F_velocity_phi_maxabs_fd_error",max_error);
  emit("v23_F_fd_step_rad",step);
  imu.dtheta={0,0,0};imu.dvel={0,0,0};
  const auto zero=v23::buildErrorStateMatrices(state,imu,options,v23::diagonalNoiseMatrix(1e-6));
  double vsa=0,phisg=0;
  for(std::size_t row=0;row<3;++row)for(std::size_t column=0;column<3;++column){
    vsa+=std::pow(v23::matrix21At(zero.F,v23::V_ID+row,v23::SA_ID+column),2);
    phisg+=std::pow(v23::matrix21At(zero.F,v23::PHI_ID+row,v23::SG_ID+column),2);
  }
  emit("v23_zero_input_F_v_scale_frobenius",std::sqrt(vsa));
  emit("v23_zero_input_F_phi_scale_frobenius",std::sqrt(phisg));

  state.euler_rpy_rad={0,0,0};state.vel_ned_mps={0,0,0};
  v23::IMUData before,now;now.dt=0.01;now.dtheta={0,0,0.02};now.dvel={1,0,0};
  v23::PVAState next;
  v23::INSMechanization::insMech(state,next,before,now);
  emit("v23_rotating_specific_force_east_increment",next.vel_ned_mps[1]);
  emit("analytic_constant_rate_east_increment",(1-std::cos(0.02))/0.02);

  options.init_state=state;options.init_pos_std={1,1,1};options.init_vel_std={1,1,1};options.init_att_std={0.1,0.1,0.1};
  options.measurement_update_implemented=true;options.state_feedback_implemented=true;
  v23::LegSAV23Engine engine(options);engine.initialize();
  for(double time:{0.25,0.5,0.75}){
    v23::GNSSData gnss;gnss.time=time;gnss.blh=state.pos_blh_rad_m;gnss.std={1,1,1};gnss.has_yaw=true;gnss.yaw_deg=0;gnss.yaw_std_deg=1;gnss.isvalid=true;
    engine.addGnssData(gnss);
  }
  for(int i=0;i<3;++i){
    v23::IMUData sample;sample.time=i;sample.dt=i==0?0:1;sample.dvel={0,0,-v23::Earth::gravity(state.pos_blh_rad_m)[2]*sample.dt};
    engine.addImuData(sample);engine.newImuProcess();
  }
  auto final_options=engine.getRunOptions();
  emit("v23_in_window_gnss_records",3);
  emit("v23_consumed_yaw_records",final_options.yaw_normal_count+final_options.yaw_downweight_count+final_options.yaw_reject_count);
  emit("v23_final_time",engine.timestamp());
}
