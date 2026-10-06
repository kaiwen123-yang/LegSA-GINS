"""Native analytical regressions; link the actual solver library, not a Python clone."""
from pathlib import Path
import os
import subprocess

import pytest


def test_conditional_sequential_innovation_and_inactive_axis(tmp_path):
    library = os.environ.get('LEGSA_NATIVE_TEST_LIBRARY')
    if not library or not Path(library).is_file():
        pytest.skip('set LEGSA_NATIVE_TEST_LIBRARY to the freshly built native library')
    root = Path(__file__).resolve().parents[2] / 'cpp/legsa_v23_port_core'
    source = tmp_path/'probe.cpp'
    source.write_text('''#include <bits/stdc++.h>
#define private public
#include "legsa_v23_port_core/kf_gins/gi_engine.hpp"
#undef private
#include "legsa_v23_port_core/common/rotation.hpp"
using namespace legsa_v23_port_core;
int main() {
  PortOptions o; o.source_aware_policy_config.enable_source_aware_weighting=true;
  o.source_aware_policy_config.source_aware_mode="lsim_oim";
  GIEngine engine(o); engine.Cov_=identityMatrix(RANK); engine.dx_.assign(RANK,0.);
  Matrix H(1,RANK,0.);H(0,0)=1.;Matrix R(1,1,1.);
  engine.EKFUpdate({4.},H,R); // dx=2, P=1/2
  source_aware::SourceMetadata m;Matrix scaled;
  auto result=engine.applySourceAwareWeighting(m.source,m,{2.},H,R,scaled);
  if(std::abs(result.nis)>1e-14 || std::abs(result.residual_norm)>1e-14) return 1;
  source_aware::SourceAwarePolicy policy(o.source_aware_policy_config);
  m.source=source_aware::MeasurementSource::kGo2HorizontalVelocity;
  m.std_xyz=makeVec3(.1,.2,999.);
  m.active_dimensions=2;
  source_aware::ObservationInnovation innovation;
  auto horizontal=policy.evaluate(m,innovation);
  if(horizontal.lsim_R_scale!=1.) return 2;
  m.active_dimensions=3;
  if(policy.evaluate(m,innovation).lsim_R_scale<=1.) return 3;
  GIEngine lever(o);lever.Cov_=identityMatrix(RANK);lever.dx_.assign(RANK,0.);
  lever.pvacur_.cbn=identityMatrix3();lever.pvacur_.vel_ned_mps=makeVec3(0.,0.,0.);
  lever.imucur_.dt=.01;lever.imucur_.dtheta=makeVec3(0.,0.,.004);
  lever.imuerror_.gyrbias=makeVec3(0.,0.,.4);lever.options_.antlever_m=makeVec3(.3,.2,-.1);
  GnssData g;g.has_velocity=true;g.vel_ned_mps=makeVec3(0.,0.,0.);g.vel_std_mps=makeVec3(1.,1.,1.);
  lever.applyVelocityUpdate(g);
  for(double value:lever.dx_) if(std::abs(value)>1e-14) return 4;
  const Vec3 rate=makeVec3(.1,-.3,.7);
  lever.imuerror_.gyrscale=makeVec3(.01,-.02,.03);
  auto jac=lever.antennaVelocityJacobian(rate);
  const Vec3 base=multiply(lever.pvacur_.cbn,cross(rate,lever.options_.antlever_m));
  const double eps=1e-6;
  for(int axis=0;axis<3;++axis) {
    Vec3 biased=rate;biased[axis]-=eps;
    Vec3 truth=multiply(lever.pvacur_.cbn,cross(biased,lever.options_.antlever_m));
    for(int row=0;row<3;++row) if(std::abs((base[row]-truth[row])/eps-jac(row,BG_ID+axis))>1e-9) return 5;
    Vec3 scaled=rate;scaled[axis]*=(1.+lever.imuerror_.gyrscale[axis])/(1.+lever.imuerror_.gyrscale[axis]+eps);
    truth=multiply(lever.pvacur_.cbn,cross(scaled,lever.options_.antlever_m));
    for(int row=0;row<3;++row) if(std::abs((base[row]-truth[row])/eps-jac(row,SG_ID+axis))>1e-6) return 6;
  }
  o.stage_id="IMU_V3_TIME_CONTRACT_FIX_20261004";
  GIEngine heading(o);
  for(const Vec3 angles : {makeVec3(.3,.4,.7),makeVec3(-.4,.6,-3.14),makeVec3(0.,0.,1.5)}) {
    heading.pvacur_.cbn=Rotation::euler2matrix(angles);
    const double predicted=heading.dualAntennaYawPrediction();
    const Matrix derivative=heading.dualAntennaYawJacobian();
    for(int axis=0;axis<3;++axis) {
      Vec3 delta=makeVec3(0.,0.,0.);delta[axis]=eps;
      const Matrix3 actual=multiply(Rotation::quaternion2matrix(Rotation::rotvec2quaternion(delta)),heading.pvacur_.cbn);
      const Vec3 vector=multiply(actual,makeVec3(0.,-1.,0.));
      const double observed=std::atan2(vector[1],vector[0])+.5*std::acos(-1.);
      if(std::abs(Rotation::wrapRad(predicted-observed)/eps-derivative(0,PHI_ID+axis))>2e-6) return 7;
    }
  }
  heading.pvacur_.cbn=Rotation::euler2matrix(makeVec3(.5*std::acos(-1.),0.,0.));
  try {heading.dualAntennaYawPrediction();return 8;} catch(const std::runtime_error&) {}
  GIEngine legacy(PortOptions{});legacy.pvacur_.euler_rad=makeVec3(.3,.4,1.2);
  if(legacy.dualAntennaYawPrediction()!=1.2 || legacy.dualAntennaYawJacobian()(0,PHI_ID)!=0.) return 9;
  std::cout<<"conditional_innovation=0; inactive_D_ignored; active_D_checked\\n";
}''')
    exe = tmp_path/'probe'
    subprocess.run(['g++','-std=c++17','-I'+str(root/'include'),str(source),library,'-o',str(exe)],check=True)
    result=subprocess.run([str(exe)],capture_output=True,text=True)
    assert result.returncode == 0, result.stdout+result.stderr
