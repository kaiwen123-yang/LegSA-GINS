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
pose_clone::Gaussian seedBodyVelocityDiscrepancy(const pose_clone::Gaussian& prior,
                                                const Matrix& H, const Matrix& Rseed) {
  const std::size_t n=prior.mean.size();
  if((n!=21 && n!=27) || H.rows!=2 || H.cols!=21 || Rseed.rows!=2 || Rseed.cols!=2)
    throw std::runtime_error("SDK_DISCREPANCY_SEED_DIMENSION");
  Matrix h(2,n);for(std::size_t i=0;i<2;++i) for(std::size_t j=0;j<21;++j) h(i,j)=H(i,j);
  const Matrix cross=multiply(prior.covariance,transpose(h));
  const Matrix bb=add(multiply(h,cross),Rseed);
  const auto bm=multiply(h,prior.mean);
  Matrix p(n+2,n+2);std::vector<double> mean(n+2);
  auto index=[](std::size_t i){return i<21?i:i+2;};
  for(std::size_t i=0;i<n;++i) {
    mean[index(i)]=prior.mean[i];
    for(std::size_t j=0;j<n;++j) p(index(i),index(j))=prior.covariance(i,j);
    for(std::size_t j=0;j<2;++j) p(index(i),21+j)=p(21+j,index(i))=cross(i,j);
  }
  for(std::size_t i=0;i<2;++i) {
    mean[21+i]=bm[i];for(std::size_t j=0;j<2;++j) p(21+i,21+j)=bb(i,j);
  }
  return {p,mean};
}
Matrix bodyVelocityDiscrepancyJacobian(const Matrix& H,std::size_t n) {
  if(H.rows!=2 || H.cols!=21 || (n!=23 && n!=29))
    throw std::runtime_error("SDK_DISCREPANCY_H_DIMENSION");
  Matrix result(2,n);
  for(std::size_t i=0;i<2;++i) {
    for(std::size_t j=0;j<21;++j) result(i,j)=H(i,j);
    result(i,21+i)=-1.0;
  }
  return result;
}
} // namespace legsa_v23_port_core
