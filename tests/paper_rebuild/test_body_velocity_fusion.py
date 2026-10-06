"""Body-frame fusion unit contract: artificial inputs, no raw/GNSS reference access."""
import csv
import json
import subprocess
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[2]
HEADER = "time,v_forward_mps,v_right_mps,std_forward_mps,std_right_mps,valid,source_status\n"
HARNESS = r'''
#include "legsa_v23_port_core/factors/body_velocity_model.hpp"
#include "legsa_v23_port_core/factors/go2_weak_prior_loader.hpp"
#include "legsa_v23_port_core/common/rotation.hpp"
#include "legsa_v23_port_core/common/earth.hpp"
#include "legsa_v23_port_core/kf_gins/gi_engine.hpp"
#include "legsa_v23_port_core/fileio/file_saver.hpp"
#include <cmath>
#include <iostream>
#include <limits>
#include <stdexcept>
using namespace legsa_v23_port_core;
void need(bool value,const char* message){if(!value)throw std::runtime_error(message);}
NavState state(){NavState s;s.pos_blh_rad_m=makeVec3(.6,1.1,20);s.euler_rad=makeVec3(.2,-.3,.7);s.qbn=Rotation::euler2quaternion(s.euler_rad);s.cbn=Rotation::quaternion2matrix(s.qbn);s.vel_ned_mps=makeVec3(1.3,-.4,.2);return s;}
PortOptions options(){PortOptions o;o.runtime_contract="research_experiment";o.enable_receiver_velocity_update=false;o.enable_dual_yaw_update=false;
 auto&c=o.go2_velocity_prior_diagnostic_config;c.enable_go2_velocity_prior_diagnostic=true;c.enable_go2_horizontal_velocity_prior=true;
 c.go2_horizontal_velocity_frame="body_frd";c.go2_horizontal_velocity_prior_source_aware_enabled=false;
 c.go2_body_velocity_prior_path="declared_body.csv";return o;}
void math(){double worst=0;const double eps=1e-6;auto s=state();
 const Vec3 z=makeVec3(.8,.1,std::numeric_limits<double>::quiet_NaN());const Vec3 stddev=makeVec3(.2,.3,0);
 const auto m=buildBodyVelocity2dModel(s,z,stddev);need(m.H.rows==2&&m.R.rows==2&&m.residual.size()==2,"not two-dimensional");
 need(m.R(0,0)==.2*.2&&m.R(1,1)==.3*.3,"native changed provider std");
 need(std::abs(m.H(0,V_ID+2))>.1,"incorrectly freezes navigation down influence");
 for(int j=0;j<6;++j){auto p=s,n=s;if(j<3){p.vel_ned_mps[j]-=eps;n.vel_ned_mps[j]+=eps;}
  else {Vec3 e{};e[j-3]=eps;p.cbn=multiply(Rotation::quaternion2matrix(Rotation::rotvec2quaternion(e)),s.cbn);
   n.cbn=multiply(Rotation::quaternion2matrix(Rotation::rotvec2quaternion(scale(e,-1))),s.cbn);}
  auto hp=buildBodyVelocity2dModel(p,z,stddev).prediction,hn=buildBodyVelocity2dModel(n,z,stddev).prediction;
  for(int i=0;i<2;++i)worst=std::max(worst,std::abs(-(hp[i]-hn[i])/(2*eps)-m.H(i,j<3?V_ID+j:PHI_ID+j-3)));
 }
 need(worst<1e-9,"body H sign/value");
 auto q=Rotation::quaternion2matrix(Rotation::euler2quaternion(makeVec3(0,0,1.1)));
 auto rotated=s;rotated.cbn=multiply(q,s.cbn);rotated.vel_ned_mps=multiply(q,s.vel_ned_mps);
 auto mr=buildBodyVelocity2dModel(rotated,z,stddev);for(int i=0;i<2;++i)need(std::abs(mr.residual[i]-m.residual[i])<1e-15,"global yaw gauge broken");
 s.vel_ned_mps=makeVec3(0,0,0);auto stopped=buildBodyVelocity2dModel(s,z,stddev);
 for(int i=0;i<2;++i)for(int j=0;j<3;++j)need(stopped.H(i,PHI_ID+j)==0,"stationary absolute yaw information invented");
 std::cout<<worst<<'\n';
}
void attach(GIEngine&e,std::vector<Go2VelocityDiagnosticPriorMeasurement> rows){Go2VelocityDiagnosticPriorStatus st;st.solver_enabled=true;st.provider_status="available";e.setGo2VelocityDiagnosticPriors(rows,st);}
Go2VelocityDiagnosticPriorMeasurement row(double t,bool valid=true){Go2VelocityDiagnosticPriorMeasurement r;r.time=t;r.observation_frame="body_frd";r.source_status=valid?"active":"invalid";r.update_flag=valid;r.diagnostic_only=false;r.velocity_body_frd_mps=makeVec3(.8,.1,0);r.std_body_frd_mps=makeVec3(.2,.2,0);return r;}
void step(GIEngine&e,double t,const std::vector<GnssData>&events={}){ImuData i;i.time=t;i.dt=.01;i.dvel=makeVec3(0,0,-.098);e.addImuData(i);e.newImuProcessWithEvents(events);}
void setup(GIEngine&e){e.initialize(state());ImuData i;i.time=0;i.dt=.01;e.addImuData(i,true);}
void schedule(const std::string&out){auto o=options();GIEngine e(o);setup(e);attach(e,{row(.21),row(.39),row(.59,false)});
 // No GNSS records at all. Future .21 cannot update at .20; .39 updates at .40.
 for(int j=1;j<=65;++j){step(e,j*.01);if(j==20)need(e.go2VelocityDiagnosticPriorUpdateCount()==0,"future body input used");}
 need(e.go2VelocityDiagnosticPriorUpdateCount()==1,"wrong independent timer count");
 need(e.go2VelocityDiagnosticPriorRejectCount()==1,"invalid latest row not consumed/rejected");
 need(e.positionUpdateCount()==0&&e.velocityUpdateCount()==0&&e.yawUpdateCount()==0,"fabricated GNSS updates");
 need(e.checkCov(),"bad covariance");e.writeBodyVelocityDiagnostics(out);FileSaver::writeRunManifest(out,o);
}
void once(){auto o=options();o.go2_velocity_prior_diagnostic_config.go2_body_velocity_update_period_s=.01;GIEngine e(o);setup(e);attach(e,{row(.019)});
 for(int j=1;j<=20;++j)step(e,j*.01);
 need(e.go2VelocityDiagnosticPriorUpdateCount()==1,"same body sample replayed");
}
void no_gnss_double(){auto o=options();GIEngine e(o);setup(e);attach(e,{row(.194)});
 for(int j=1;j<20;++j)step(e,j*.01);
 GnssData g;g.time=.195;g.validity_explicit=true;g.has_position=g.has_velocity=false;g.has_yaw=true;
 step(e,.2,{g});need(e.go2VelocityDiagnosticPriorUpdateCount()==1,"GNSS event duplicates independent body update");
}
void source_aware_case(){auto o=options();o.go2_velocity_prior_diagnostic_config.go2_horizontal_velocity_prior_source_aware_enabled=true;
 o.source_aware_policy_config.enable_source_aware_weighting=true;o.source_aware_policy_config.source_aware_mode="lsim_oim";
 GIEngine e(o);setup(e);auto r=row(.194);r.quality_flag="nominal";attach(e,{r});
 for(int j=1;j<=20;++j)step(e,j*.01);
 need(e.go2VelocityDiagnosticPriorUpdateCount()==1,"SA availability label rejected body provider");
 need(e.sourceAwareEvaluationCount()==1,"SA body factor not evaluated");
}
void disabled(){auto a=options();a.go2_velocity_prior_diagnostic_config.enable_go2_horizontal_velocity_prior=false;
 auto b=a;b.go2_velocity_prior_diagnostic_config.go2_horizontal_velocity_frame="ned";
 GIEngine ea(a),eb(b);setup(ea);setup(eb);attach(ea,{row(.19)});attach(eb,{row(.19)});
 for(int j=1;j<=30;++j){step(ea,j*.01);step(eb,j*.01);
 need(ea.getCovariance()==eb.getCovariance(),"disabled body covariance drift");
 need(ea.navState().pos_blh_rad_m==eb.navState().pos_blh_rad_m&&ea.navState().euler_rad==eb.navState().euler_rad,"disabled body nav drift");}
 need(ea.go2VelocityDiagnosticPriorUpdateCount()==0,"disabled body update");
}
int main(int argc,char**argv){try{std::string mode=argv[1];if(mode=="math")math();else if(mode=="schedule")schedule(argv[2]);else if(mode=="once")once();else if(mode=="no_gnss_double")no_gnss_double();else if(mode=="disabled")disabled();else if(mode=="source_aware")source_aware_case();
 else if(mode=="load"){auto c=options().go2_velocity_prior_diagnostic_config;auto p=Go2WeakPriorLoader::loadBodyVelocityCsv(argv[2],c);std::cout<<p.measurements.size()<<','<<p.status.valid_prior_count<<','<<p.status.solver_enabled<<'\n';}
 else if(mode=="wrong_frame"){auto o=options();GIEngine e(o);setup(e);auto r=row(.19);r.observation_frame="ned";attach(e,{r});step(e,.2);}
 else if(mode=="bad_period"){auto o=options();o.go2_velocity_prior_diagnostic_config.go2_body_velocity_update_period_s=0;GIEngine e(o);}
 else return 2;return 0;}catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 1;}}
'''
@pytest.fixture(scope="module")
def harness(tmp_path_factory):
    build = tmp_path_factory.mktemp("body_hv_cpp")
    subprocess.run(["cmake", "-S", str(ROOT / "cpp"), "-B", str(build), "-DCMAKE_BUILD_TYPE=Release"], check=True, capture_output=True)
    subprocess.run(["cmake", "--build", str(build), "--target", "legsa_v23_port_core", "-j4"], check=True, capture_output=True)
    source=build/"test.cpp";source.write_text(HARNESS);exe=build/"test"
    subprocess.run(["c++", "-std=c++17", "-O2", "-I", str(ROOT/"cpp/legsa_v23_port_core/include"), str(source), str(build/"liblegsa_v23_port_core.a"), "-o", str(exe)], check=True)
    return exe

def run(harness,*args,ok=True):
    p=subprocess.run([str(harness),*map(str,args)],capture_output=True,text=True)
    assert (p.returncode==0)==ok,p.stdout+p.stderr
    return p

@pytest.mark.parametrize("mode",["math","once","no_gnss_double","disabled","source_aware"])
def test_body_observation_and_scheduling(harness,mode):run(harness,mode)

def test_missing_gnss_future_and_invalid_body_inputs(harness,tmp_path):
    run(harness,"schedule",tmp_path)
    rows=list(csv.DictReader((tmp_path/"BODY_VELOCITY_EVENTS.csv").open()))
    assert [r["accepted"] for r in rows]==["0","1","0"]
    assert rows[0]["source_time"]==""
    assert float(rows[1]["source_time"])==.39
    assert float(rows[1]["age_s"])>=0
    assert rows[2]["reason"]=="provider_invalid"
    m=json.loads((tmp_path/"RUN_MANIFEST.json").read_text())
    assert not m["body_velocity_z_observed"] and not m["body_velocity_nav_down_state_frozen"]
    assert m["actual_solver_input_paths"]["go2_horizontal_velocity_weak_prior"]=="declared_body.csv"

@pytest.mark.parametrize("mode",["wrong_frame","bad_period"])
def test_body_contract_failures(harness,mode):run(harness,mode,ok=False)

@pytest.mark.parametrize("rows,expected",[("", "0,0,1"),("1,,,,,0,invalid\n","1,0,1"),("1,1,.2,.2,.3,1,active\n","1,1,1")])
def test_body_loader_all_invalid_is_no_update_not_transport_error(harness,tmp_path,rows,expected):
    p=tmp_path/"body.csv";p.write_text(HEADER+rows)
    assert run(harness,"load",p).stdout.strip()==expected

@pytest.mark.parametrize("rows",["1,1,.2,0,.3,1,active\n","1,nan,.2,.2,.3,1,active\n","1,1,.2,.2,.3,1,invalid\n","1,1,.2,.2,.3,1,active\n1,1,.2,.2,.3,1,active\n"])
def test_body_loader_invalid_fields(harness,tmp_path,rows):
    p=tmp_path/"body.csv";p.write_text(HEADER+rows)
    run(harness,"load",p,ok=False)
