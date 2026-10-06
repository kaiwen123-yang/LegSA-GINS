#include "legsa_v23_port_core/factors/body_velocity_model.hpp"
#include <cmath>
#include <stdexcept>
namespace legsa_v23_port_core {
BodyVelocity2dModel buildBodyVelocity2dModel(const NavState& state, const Vec3& velocity,
                                            const Vec3& stddev) {
  for(int i=0;i<2;++i) if(!std::isfinite(velocity[i]) || !std::isfinite(stddev[i]) || !(stddev[i]>0.0))
    throw std::runtime_error("BODY_HV_INVALID_MODEL_INPUT");
  BodyVelocity2dModel result;
  const auto cnb=transpose(state.cbn);
  result.prediction=multiply(cnb,state.vel_ned_mps);
  result.residual={result.prediction[0]-velocity[0],result.prediction[1]-velocity[1]};
  result.H=Matrix(2,RANK,0.0);result.R=Matrix(2,2,0.0);
  // stateFeedback: v <- v-dv, C <- Exp(phi) C. Residual = predicted-observed.
  const auto attitude=scale(multiply(cnb,skew(state.vel_ned_mps)),-1.0);
  for(int i=0;i<2;++i){
    result.R(i,i)=stddev[i]*stddev[i];
    for(int j=0;j<3;++j){result.H(i,V_ID+j)=cnb[i][j];result.H(i,PHI_ID+j)=attitude[i][j];}
  }
  return result;
}
} // namespace legsa_v23_port_core
