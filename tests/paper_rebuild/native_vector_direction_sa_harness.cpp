// One concentrated actual-policy check; synthetic geometry is not navigation evidence.
#include "legsa_v23_port_core/baseline3d.hpp"
#include "legsa_v23_port_core/common/earth.hpp"
#include "legsa_v23_port_core/common/rotation.hpp"
#include "legsa_v23_port_core/source_aware/source_aware_policy.hpp"
#include <algorithm>
#include <cmath>
#include <iomanip>
#include <iostream>
#include <stdexcept>
using namespace legsa_v23_port_core;
namespace sa = legsa_v23_port_core::source_aware;
void need(bool value, const char* message) { if (!value) throw std::runtime_error(message); }
double difference(const Matrix& a, const Matrix& b) {
  need(a.rows == b.rows && a.cols == b.cols, "matrix dimensions");
  double out = 0;
  for (std::size_t i = 0; i < a.data.size(); ++i) out = std::max(out, std::abs(a.data[i] - b.data[i]));
  return out;
}
Matrix dynamic(const Matrix3& a) { Matrix out(3,3); setBlock(out,0,0,a); return out; }
double trace(const Matrix& a) { double out=0; for (std::size_t i=0;i<a.rows;++i) out+=a(i,i); return out; }
void print(const Matrix& a) {
  std::cout << '[';
  for (std::size_t i=0;i<a.rows;++i) {
    if (i) std::cout << ','; std::cout << '[';
    for (std::size_t j=0;j<a.cols;++j) { if(j) std::cout<<','; std::cout<<a(i,j); }
    std::cout << ']';
  }
  std::cout << ']';
}
sa::SourceAwarePolicyConfig config(bool legacy=false) {
  sa::SourceAwarePolicyConfig c;
  c.enable_source_aware_weighting=true; c.source_aware_mode="lsim_oim";
  if (legacy) c.source_aware_policy_version="legacy_generic_source_aware";
  return c;
}
sa::SourceWeightResult evaluate(const sa::SourceMetadata& m, const sa::ObservationInnovation& i,
                               bool legacy=false) {
  sa::SourceAwarePolicy policy(config(legacy)); return policy.evaluate(m,i);
}
sa::SourceMetadata metadata(const Matrix& R, bool vector) {
  sa::SourceMetadata m; m.source=sa::MeasurementSource::kDualAntennaYaw;
  m.std_xyz={std::sqrt(R(0,0)),std::sqrt(R(1,1)),std::sqrt(R(2,2))};
  m.scalar_yaw_std_available=!vector;
  // Old proxy exists only in the counterexample. Vector leaves the unused default untouched.
  if (!vector) m.yaw_std_rad=std::sqrt(R(0,0))/.35;
  m.provider_status="external_carrier_experimental"; return m;
}
sa::ObservationInnovation innovation(const Baseline3dModel& m, double residual_scale=1) {
  const auto HPHT=multiply(multiply(m.H,scale(identityMatrix(21),.0009)),transpose(m.H));
  const auto S=add(HPHT,m.R);
  sa::ObservationInnovation out; out.residual={m.residual_m[0]*residual_scale,m.residual_m[1]*residual_scale,m.residual_m[2]*residual_scale};
  const auto solved=multiply(inverse(S),out.residual);
  for (std::size_t j=0;j<3;++j) out.nis+=out.residual[j]*solved[j];
  out.residual_norm=norm(scale(m.residual_m,residual_scale));
  out.base_R_trace=trace(m.R); out.hph_trace=trace(HPHT); out.innovation_cov_trace=trace(S);
  out.dof=3; out.normalized_innovation=std::sqrt(out.nis/3); out.used_innovation_covariance=true;
  return out;
}
Matrix attitudeH(const Baseline3dModel& m) {
  Matrix out(3,3); for(std::size_t i=0;i<3;++i) for(std::size_t j=0;j<3;++j) out(i,j)=m.H(i,PHI_ID+j);
  return out;
}
int main() { try {
  std::cout<<std::setprecision(17);
  const auto C=Rotation::euler2matrix({.25,-.18,.38}); // tilted, nonzero yaw
  const auto U=Rotation::euler2matrix({.30,0,0});
  const auto Q=Rotation::euler2matrix({0,0,kPi/2}); // passive horizontal coordinate relabelling
  Matrix3 eigen{}; eigen[0][0]=.0001; eigen[1][1]=.16; eigen[2][2]=.0004;
  const auto R=multiply(multiply(U,eigen),transpose(U));
  const Vec3 body={0,-.35,0}, blh={.55,1.2,80}, residual={.001,-.009,.006};
  const auto observed=subtract(multiply(C,body),residual);
  const auto E=Earth::cne(blh);
  auto makeModel=[&](const Matrix3& rotation) {
    Baseline3dMeasurement o; o.source="external_carrier"; o.present=o.valid=true;
    o.ecef_m=multiply(E,multiply(rotation,observed));
    o.covariance_ecef_m2=multiply(multiply(E,multiply(multiply(rotation,R),transpose(rotation))),transpose(E));
    return buildExternalCarrierBaseline3dModel(multiply(rotation,C),blh,o,body);
  };
  const auto a=makeModel(identityMatrix3()), b=makeModel(Q);
  const auto ia=innovation(a), ib=innovation(b);
  const auto olda=evaluate(metadata(a.R,false),ia), oldb=evaluate(metadata(b.R,false),ib);
  const auto ma=metadata(a.R,true), mb=metadata(b.R,true);
  const auto va=evaluate(ma,ia), vb=evaluate(mb,ib);
  need(olda.lsim_R_scale==1 && oldb.lsim_R_scale==6,"old proxy did not exhibit 1/6 coordinate dependence");
  need(va.lsim_R_scale==1 && vb.lsim_R_scale==1 && va.combined_R_scale==vb.combined_R_scale,"vector policy not equivariant");
  need(va.metadata_summary.find("scalar_yaw_std_available=false;yaw_std_rad=NOT_APPLICABLE")!=std::string::npos,"vector trace invented scalar sigma");
  need(ma.yaw_std_rad==D2R,"vector bypass replaced sigma with zero");
  const auto q=dynamic(Q), h=attitudeH(a), hr=attitudeH(b);
  const auto tensor=multiply(multiply(transpose(h),inverse(scale(a.R,va.combined_R_scale))),h);
  const auto tensorr=multiply(multiply(transpose(hr),inverse(scale(b.R,vb.combined_R_scale))),hr);
  const auto transported=multiply(multiply(q,tensor),transpose(q));
  const double covariance_error=difference(b.R,multiply(multiply(q,a.R),transpose(q)));
  const double tensor_error=difference(tensorr,transported);
  need(covariance_error<1e-12 && tensor_error<1e-8,"full tensor lost under coordinate change");
  need(std::abs(ia.nis-ib.nis)<1e-10,"NIS changed under passive coordinates");
  need(norm(a.residual_m)>0 && std::abs(a.predicted_m[2])>.01,"degenerate untilted fixture");

  // Exact legacy scalar boundaries; defaults remain applicable.
  sa::SourceMetadata scalar; scalar.source=sa::MeasurementSource::kDualAntennaYaw;
  need(scalar.scalar_yaw_std_available,"scalar default changed");
  scalar.yaw_std_rad=15*D2R; const auto s15=evaluate(scalar,ia);
  scalar.yaw_std_rad=(15+1e-8)*D2R; const auto s15p=evaluate(scalar,ia);
  scalar.yaw_std_rad=30*D2R; const auto s30=evaluate(scalar,ia);
  scalar.yaw_std_rad=(30+1e-8)*D2R; const auto s30p=evaluate(scalar,ia);
  need(s15.lsim_R_scale==1 && s15p.lsim_R_scale==2 && s30.lsim_R_scale==2 && s30p.lsim_R_scale==6,"N6B scalar thresholds changed");
  scalar.yaw_std_rad=3*D2R; const auto legacy3=evaluate(scalar,ia,true);
  scalar.yaw_std_rad=4*D2R; const auto legacy4=evaluate(scalar,ia,true);
  need(legacy3.lsim_R_scale==1 && legacy4.lsim_R_scale==8,"legacy scalar threshold changed");
  need(evaluate(mb,ib,true).lsim_R_scale==1,"legacy vector scalar rule not skipped");

  // Only scalar sigma applicability changes: source qualification and OIM remain active.
  auto bad=ma; bad.valid=false; const auto invalid=evaluate(bad,ia);
  bad=ma; bad.time_diff_sec=.3; const auto stale=evaluate(bad,ia);
  bad=ma; bad.quality_flag="degraded"; const auto quality=evaluate(bad,ia);
  bad=ma; bad.rel_valid=false; const auto antenna=evaluate(bad,ia);
  bad=ma; bad.covariance_available=false; const auto missing=evaluate(bad,ia);
  need(invalid.rejected && !invalid.accepted,"vector invalid source was accepted");
  need(stale.lsim_R_scale==2.5 && quality.lsim_R_scale==1.5 && antenna.lsim_R_scale==2 && missing.lsim_R_scale==1.5,"vector non-sigma LSIM suppressed");
  const double multiplier=1.8/ia.normalized_innovation;
  const auto noisy_a=innovation(a,multiplier), noisy_b=innovation(b,multiplier);
  const auto oa=evaluate(ma,noisy_a), ob=evaluate(mb,noisy_b);
  need(noisy_a.nis<11.34 && oa.oim_R_scale>1 && oa.lsim_R_scale==1,"reachable OIM action suppressed");
  need(std::abs(oa.combined_R_scale-ob.combined_R_scale)<1e-12,"OIM not coordinate invariant");
  std::cout<<"{\"status\":\"PASS\",\"synthetic_only\":true,\"checks\":1,\"native_solver_runs\":0,"
           <<"\"old_proxy_sigma_deg\":["<<std::sqrt(a.R(0,0))/.35*R2D<<','<<std::sqrt(b.R(0,0))/.35*R2D<<"],"
           <<"\"old_proxy_lsim_scales\":["<<olda.lsim_R_scale<<','<<oldb.lsim_R_scale<<"],"
           <<"\"vector_lsim_scales\":["<<va.lsim_R_scale<<','<<vb.lsim_R_scale<<"],"
           <<"\"nonzero_residual_norm_m\":"<<norm(a.residual_m)<<",\"predicted_down_m\":"<<a.predicted_m[2]<<','
           <<"\"covariance_equivariance_max_abs\":"<<covariance_error<<",\"information_equivariance_max_abs\":"<<tensor_error<<','
           <<"\"nis_coordinate_difference\":"<<std::abs(ia.nis-ib.nis)<<",\"NIS\":"<<ia.nis<<','
           <<"\"scalar_N6B_boundary_scales\":["<<s15.lsim_R_scale<<','<<s15p.lsim_R_scale<<','<<s30.lsim_R_scale<<','<<s30p.lsim_R_scale<<"],"
           <<"\"scalar_legacy_3_4deg_scales\":["<<legacy3.lsim_R_scale<<','<<legacy4.lsim_R_scale<<"],"
           <<"\"vector_invalid_rejected\":true,\"vector_stale_scale\":"<<stale.lsim_R_scale<<",\"vector_quality_scale\":"<<quality.lsim_R_scale<<','
           <<"\"vector_antenna_scale\":"<<antenna.lsim_R_scale<<",\"vector_covariance_missing_scale\":"<<missing.lsim_R_scale<<','
           <<"\"vector_OIM_scale\":"<<oa.oim_R_scale<<",\"OIM_NIS\":"<<noisy_a.nis<<','
           <<"\"R\":";print(a.R);std::cout<<",\"R_rotated\":";print(b.R);
  std::cout<<",\"attitude_information\":";print(tensor);std::cout<<",\"attitude_information_rotated\":";print(tensorr);
  std::cout<<",\"vector_metadata_summary\":\""<<va.metadata_summary<<"\"}\n";
  return 0;
} catch(const std::exception& e) { std::cerr<<e.what()<<'\n'; return 1; } }
