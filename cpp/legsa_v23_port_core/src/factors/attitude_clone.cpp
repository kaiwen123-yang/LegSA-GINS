#include "legsa_v23_port_core/factors/attitude_clone.hpp"
#include "legsa_v23_port_core/common/earth.hpp"
#include "legsa_v23_port_core/common/rotation.hpp"
#include <algorithm>
#include <cmath>
#include <limits>
#include <stdexcept>

namespace legsa_v23_port_core::attitude_clone {
namespace {
void require(bool condition, const std::string& message) {
  if (!condition) throw std::runtime_error("ATTITUDE_CLONE_" + message);
}
void finite(const Matrix& a, const char* name) {
  require(a.data.size() == a.rows * a.cols, std::string(name) + "_STORAGE");
  for (double x : a.data) require(std::isfinite(x), std::string(name) + "_NONFINITE");
}
void finite(const std::vector<double>& a, const char* name) {
  for (double x : a) require(std::isfinite(x), std::string(name) + "_NONFINITE");
}
Matrix symmetrize(const Matrix& a) { return scale(add(a,transpose(a)),0.5); }
Matrix solveSpd(const Matrix& input, const Matrix& rhs) {
  require(input.rows==input.cols && rhs.rows==input.rows,"SPD_SOLVE_DIMENSION");
  finite(input,"SPD_INPUT"); finite(rhs,"SPD_RHS");
  const Matrix s=symmetrize(input);
  Matrix l(s.rows,s.cols);
  for (std::size_t i=0;i<s.rows;++i) {
    for (std::size_t j=0;j<=i;++j) {
      double v=s(i,j);
      for (std::size_t k=0;k<j;++k) v-=l(i,k)*l(j,k);
      if (i==j) {
        require(std::isfinite(v) && v>0.0,"INNOVATION_NOT_SPD_NO_LOADING");
        l(i,j)=std::sqrt(v);
      } else l(i,j)=v/l(j,j);
    }
  }
  Matrix x=rhs;
  for (std::size_t c=0;c<x.cols;++c) {
    for (std::size_t i=0;i<x.rows;++i) {
      for (std::size_t j=0;j<i;++j) x(i,c)-=l(i,j)*x(j,c);
      x(i,c)/=l(i,i);
    }
    for (std::size_t i=x.rows;i-->0;) {
      for (std::size_t j=i+1;j<x.rows;++j) x(i,c)-=l(j,i)*x(j,c);
      x(i,c)/=l(i,i);
    }
  }
  finite(x,"SPD_SOLUTION");
  return x;
}
void validate(const Gaussian& s) {
  require(s.mean.size()==kCurrent || s.mean.size()==kJoint,"STATE_DIMENSION");
  finite(s.mean,"STATE_MEAN");
  require(s.covariance.rows==s.mean.size() && s.covariance.cols==s.mean.size(),"STATE_COV_DIMENSION");
  finite(s.covariance,"STATE_COV");
}
std::vector<double> corrected(const Gaussian& s, const std::vector<double>& dz,
                              const Matrix& h,const Matrix& gain) {
  auto innovation=dz;
  const auto hm=multiply(h,s.mean);
  for (std::size_t i=0;i<dz.size();++i) innovation[i]-=hm[i];
  auto out=s.mean;
  const auto increment=multiply(gain,innovation);
  for (std::size_t i=0;i<out.size();++i) out[i]+=increment[i];
  finite(out,"UPDATED_MEAN");
  return out;
}
double score(const Matrix& p,const std::vector<double>& weights) {
  require(weights.size()==kCurrent,"WEIGHT_DIMENSION");
  double r=0.0;
  for (std::size_t i=0;i<kCurrent;++i) {
    require(std::isfinite(weights[i]) && weights[i]>=0.0,"WEIGHT_DOMAIN");
    r+=weights[i]*p(i,i);
  }
  require(std::isfinite(r) && r>=0.0,"WEIGHTED_TRACE_DOMAIN");
  return r;
}
void validateMeasurement(const Gaussian& s,const std::vector<double>& z,const Matrix& h,const Matrix& r) {
  validate(s);
  require(h.cols==s.mean.size() && h.rows>0 && z.size()==h.rows &&
          r.rows==h.rows && r.cols==h.rows,"MEASUREMENT_DIMENSION");
  finite(z,"MEASUREMENT"); finite(h,"JACOBIAN");
}
}  // namespace

Matrix symmetricPsd(const Matrix& value,std::size_t size,const char* name) {
  require(value.rows==size && value.cols==size,std::string(name)+"_DIMENSION");
  finite(value,name);
  double scale_value=0.0;
  for(double x:value.data) scale_value=std::max(scale_value,std::fabs(x));
  const double tol=128.0*std::numeric_limits<double>::epsilon()*static_cast<double>(size)*
      std::max(scale_value,std::numeric_limits<double>::min());
  for(std::size_t i=0;i<size;++i) for(std::size_t j=0;j<size;++j)
    require(std::fabs(value(i,j)-value(j,i))<=tol,std::string(name)+"_NOT_SYMMETRIC");
  // Complete diagonal-pivoted PSD elimination. It validates but does not load,
  // clip eigenvalues, or replace the supplied matrix with a factor reconstruction.
  Matrix work=symmetrize(value);
  for(std::size_t k=0;k<size;++k) {
    std::size_t pivot=k;
    for(std::size_t i=k;i<size;++i) {
      require(work(i,i)>=-tol,std::string(name)+"_NOT_PSD");
      if(work(i,i)>work(pivot,pivot)) pivot=i;
    }
    if(work(pivot,pivot)<=tol) {
      for(std::size_t i=k;i<size;++i) for(std::size_t j=k;j<size;++j)
        require(std::fabs(work(i,j))<=tol,std::string(name)+"_SINGULAR_CROSS_NOT_PSD");
      break;
    }
    if(pivot!=k) {
      for(std::size_t j=0;j<size;++j) std::swap(work(k,j),work(pivot,j));
      for(std::size_t i=0;i<size;++i) std::swap(work(i,k),work(i,pivot));
    }
    const double d=work(k,k);
    for(std::size_t i=k+1;i<size;++i) for(std::size_t j=i;j<size;++j) {
      work(i,j)-=work(i,k)*work(j,k)/d;
      work(j,i)=work(i,j);
    }
  }
  return symmetrize(value);
}

void requireRotation(const Matrix3& c,const char* name) {
  const Matrix3 ct=multiply(transpose(c),c);
  for(std::size_t i=0;i<3;++i) for(std::size_t j=0;j<3;++j)
    require(std::isfinite(c[i][j]) && std::fabs(ct[i][j]-(i==j?1.0:0.0))<=1e-10,
            std::string(name)+"_NOT_SO3");
  const double det=c[0][0]*(c[1][1]*c[2][2]-c[1][2]*c[2][1])
      -c[0][1]*(c[1][0]*c[2][2]-c[1][2]*c[2][0])
      +c[0][2]*(c[1][0]*c[2][1]-c[1][1]*c[2][0]);
  require(std::fabs(det-1.0)<=1e-10,std::string(name)+"_NOT_POSITIVE_ROTATION");
}

Matrix3 leftResetJacobian(const Vec3& a) {
  const double theta=norm(a);
  require(std::isfinite(theta) && theta<kPi,"RESET_CORRECTION_DOMAIN");
  const double t2=theta*theta;
  const double first=theta<1e-4 ? 0.5-t2/24.0+t2*t2/720.0 : (1.0-std::cos(theta))/t2;
  const double second=theta<1e-4 ? 1.0/6.0-t2/120.0+t2*t2/5040.0 :
      (theta-std::sin(theta))/(theta*t2);
  const Matrix3 k=skew(a);
  return add(add(identityMatrix3(),scale(k,first)),scale(multiply(k,k),second));
}

Matrix3 nedFrameConnection(const Vec3& blh) {
  for(double x:blh) require(std::isfinite(x),"BLH_NONFINITE");
  const Matrix3 dri=Earth::DRi(blh);
  require(std::fabs(std::cos(blh[0]))>1e-8,"NED_POLE_DOMAIN");
  Matrix3 k=zeroMatrix3();
  // dE/dlatitude * E^T has axial vector -East; dE/dlongitude has +ECEF z.
  k[0][0]=std::sin(blh[1])*dri[0][0];
  k[1][0]=-std::cos(blh[1])*dri[0][0];
  k[2][1]=dri[1][1];
  for(const auto& row:k) for(double x:row) require(std::isfinite(x),"NED_CONNECTION_NONFINITE");
  return k;
}

Matrix augmentationJacobian(const Vec3& blh) {
  Matrix j(3,kCurrent);
  setBlock(j,0,P_ID,scale(nedFrameConnection(blh),-1.0));
  setBlock(j,0,PHI_ID,Earth::cne(blh));
  return j;
}

Gaussian augment(const Matrix& current,const std::vector<double>& mean,const Matrix& j) {
  require(mean.size()==kCurrent && j.rows==3 && j.cols==kCurrent,"AUGMENT_DIMENSION");
  finite(mean,"AUGMENT_MEAN"); finite(j,"AUGMENT_J");
  const Matrix p=symmetricPsd(current,kCurrent,"CURRENT_PRIOR");
  Matrix a(kJoint,kCurrent);
  for(std::size_t i=0;i<kCurrent;++i) a(i,i)=1.0;
  for(std::size_t i=0;i<3;++i) for(std::size_t q=0;q<kCurrent;++q) a(kCurrent+i,q)=j(i,q);
  return {symmetrize(multiply(multiply(a,p),transpose(a))),multiply(a,mean)};
}

Gaussian ordinaryUpdate(const Gaussian& s,const std::vector<double>& z,const Matrix& h,const Matrix& r) {
  validateMeasurement(s,z,h,r);
  const Matrix covariance=symmetricPsd(r,r.rows,"ORDINARY_R");
  const Matrix pht=multiply(s.covariance,transpose(h));
  const Matrix gain=transpose(solveSpd(add(multiply(h,pht),covariance),transpose(pht)));
  const Matrix a=subtract(identityMatrix(s.mean.size()),multiply(gain,h));
  Matrix post=add(multiply(multiply(a,s.covariance),transpose(a)),multiply(multiply(gain,covariance),transpose(gain)));
  return {symmetrize(post),corrected(s,z,h,gain)};
}

Gaussian reset(const Gaussian& s,const Matrix3& position_reset) {
  validate(s);
  Matrix g=identityMatrix(s.mean.size());
  for(const auto& row:position_reset) for(double x:row) require(std::isfinite(x),"POSITION_RESET_NONFINITE");
  setBlock(g,0,0,position_reset);
  setBlock(g,PHI_ID,PHI_ID,leftResetJacobian({s.mean[6],s.mean[7],s.mean[8]}));
  if(s.mean.size()==kJoint)
    setBlock(g,kCurrent,kCurrent,leftResetJacobian({s.mean[21],s.mean[22],s.mean[23]}));
  Matrix post=multiply(multiply(g,s.covariance),transpose(g));
  finite(post,"RESET_COV");
  return {symmetrize(post),std::vector<double>(s.mean.size(),0.0)};
}

std::vector<double> fixedCurrentWeights(const Matrix& p) {
  symmetricPsd(p,kCurrent,"INITIAL_WEIGHT_P");
  std::vector<double> w(kCurrent,0.0);
  for(std::size_t block=0;block<7;++block) {
    const std::size_t k=3*block;
    const double v=(p(k,k)+p(k+1,k+1)+p(k+2,k+2))/3.0;
    require(std::isfinite(v) && v>=0.0,"INITIAL_WEIGHT_VARIANCE");
    if(v==0.0) {
      require(k>=SG_ID,"ONLY_SCALE_BLOCK_MAY_HAVE_ZERO_WEIGHT");
      for(std::size_t i=k;i<k+3;++i) for(std::size_t j=0;j<kCurrent;++j)
        require(p(i,j)==0.0 && p(j,i)==0.0,"FROZEN_WEIGHT_BLOCK_HAS_CROSS");
    } else {
      require(std::isfinite(1.0/v),"INITIAL_WEIGHT_OVERFLOW");
      for(std::size_t i=k;i<k+3;++i) w[i]=1.0/v;
    }
  }
  return w;
}

SafeInnovation safeInnovation(const Gaussian& s,const std::vector<double>& z,const Matrix& h,const Matrix& r) {
  validateMeasurement(s,z,h,r);
  require(z.size()==3,"SAFE_INNOVATION_REQUIRES_THREE_COMPONENTS");
  const Matrix covariance=symmetricPsd(r,3,"SAFE_INNOVATION_R");
  const Matrix safe=scale(add(multiply(multiply(h,s.covariance),transpose(h)),covariance),2.0);
  const auto hm=multiply(h,s.mean);Matrix innovation(3,1);
  for(std::size_t i=0;i<3;++i) innovation(i,0)=z[i]-hm[i];
  const Matrix weighted=solveSpd(safe,innovation);
  double statistic=0.0;for(std::size_t i=0;i<3;++i) statistic+=innovation(i,0)*weighted(i,0);
  require(std::isfinite(statistic) && statistic>=0.0,"SAFE_INNOVATION_DOMAIN");
  return {statistic,statistic<=kSafeInnovationThreshold};
}

YoungResult youngUpdate(const Gaussian& s,const std::vector<double>& z,const Matrix& h,const Matrix& input_r,
                        const std::vector<double>& weights, YoungDiagnostics* diagnostics) {
  validateMeasurement(s,z,h,input_r);
  if(diagnostics) *diagnostics=YoungDiagnostics{};
  require(s.mean.size()==kJoint,"PAIR_REQUIRES_ACTIVE_CLONE");
  const Matrix r=symmetricPsd(input_r,input_r.rows,"PAIR_R");
  const double prior=score(s.covariance,weights);
  YoungResult best{s,false,0.0,prior,prior};
  const Matrix pht=multiply(s.covariance,transpose(h));
  const Matrix hph=multiply(h,pht);
  Matrix selected_gain;
  // Candidate selection uses covariance/geometry only. dz/mean are not used to choose epsilon.
  for(double epsilon:{1.0/64.0,1.0/16.0,1.0/4.0,1.0,4.0}) {
    const Matrix gain=transpose(solveSpd(add(hph,scale(r,1.0/epsilon)),transpose(pht)));
    const Matrix a=subtract(identityMatrix(kJoint),multiply(gain,h));
    Matrix bound=scale(add(multiply(multiply(a,s.covariance),transpose(a)),
                           scale(multiply(multiply(gain,r),transpose(gain)),1.0/epsilon)),1.0+epsilon);
    bound=symmetrize(bound); finite(bound,"YOUNG_BOUND");
    const double value=score(bound,weights);
    const double tie=64.0*std::numeric_limits<double>::epsilon()*
        std::max({1.0,std::fabs(value),std::fabs(best.bound_score)});
    if(diagnostics) diagnostics->candidates.push_back({epsilon,value,best.bound_score,tie,
                                                       value < best.bound_score-tie});
    if(value < best.bound_score-tie) {
      best.state.covariance=bound;
      best.applied=true;best.epsilon=epsilon;best.bound_score=value;selected_gain=gain;
    }
  }
  if(best.applied) best.state.mean=corrected(s,z,h,selected_gain);
  if(diagnostics) {
    // J = tr(R^-1 H P W P H^T); current21 weights are the original fixed weights.
    Matrix d(h.rows,h.rows);
    for(std::size_t i=0;i<kCurrent;++i) for(std::size_t a=0;a<h.rows;++a)
      for(std::size_t b=0;b<h.rows;++b) d(a,b)+=weights[i]*pht(i,a)*pht(i,b);
    diagnostics->T=prior;
    try {
      const auto rd=solveSpd(r,d);
      for(std::size_t a=0;a<h.rows;++a) diagnostics->J+=rd(a,a);
      diagnostics->J_available=std::isfinite(diagnostics->J);
    } catch(const std::runtime_error&) {
      // An unavailable J diagnostic must not turn a previously legal update into a failure.
      diagnostics->J_available=false;
    }
  }
  return best;
}

PairModel pairModel(const Vec3& d0,const Vec3& d1,const Matrix3& c0,const Matrix3& cbn,
                    const Vec3& blh,const Matrix& sigma) {
  requireRotation(c0,"CLONE_CBE"); requireRotation(cbn,"CURRENT_CBN");
  require(norm(d0)>1e-10 && norm(d1)>1e-10 && std::isfinite(norm(d0)) && std::isfinite(norm(d1)),
          "PAIR_SEPARATION_DOMAIN");
  const Matrix3 e=Earth::cne(blh),c1=multiply(e,cbn),relative=multiply(transpose(c0),c1);
  const Vec3 u1=multiply(c1,d1);
  const Vec3 residual=subtract(d0,multiply(relative,d1));
  const Matrix3 b=multiply(transpose(c0),skew(u1));
  Matrix h(3,kJoint);
  setBlock(h,0,P_ID,multiply(b,nedFrameConnection(blh)));
  setBlock(h,0,PHI_ID,scale(multiply(b,e),-1.0));
  setBlock(h,0,kCurrent,b);
  Matrix l(3,6);
  setBlock(l,0,0,identityMatrix3());setBlock(l,0,3,scale(relative,-1.0));
  Matrix r=multiply(multiply(l,symmetricPsd(sigma,6,"DIFFERENCE_SIGMA")),transpose(l));
  return {{residual[0],residual[1],residual[2]},h,symmetrize(r)};
}
}  // namespace legsa_v23_port_core::attitude_clone
