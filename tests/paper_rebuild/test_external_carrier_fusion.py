"""Artificial C++ fusion-contract checks. All builds/runs belong in Ubuntu WSL.
No raw/reference inputs, no native scientific navigation run, no covariance tuning.
"""
import csv
import json
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
HEADER = "measurement_time,decision_available_time,b_ecef_x,b_ecef_y,b_ecef_z,cov_xx,cov_xy,cov_xz,cov_yx,cov_yy,cov_yz,cov_zx,cov_zy,cov_zz,valid\n"
VALID = "1,1,0,-0.35,0,0.0004,0.0001,0,0.0001,0.0009,0.0002,0,0.0002,0.0016,1\n"
HARNESS = r'''
#include "legsa_v23_port_core/baseline3d.hpp"
#include "legsa_v23_port_core/common/earth.hpp"
#include "legsa_v23_port_core/common/rotation.hpp"
#include "legsa_v23_port_core/config/port_config_loader.hpp"
#include "legsa_v23_port_core/fileio/gnss_file_loader.hpp"
#include "legsa_v23_port_core/fileio/file_saver.hpp"
#include "legsa_v23_port_core/kf_gins/gi_engine.hpp"
#include <cmath>
#include <iomanip>
#include <iostream>
#include <stdexcept>
using namespace legsa_v23_port_core;
void need(bool ok,const char* msg) {if(!ok) throw std::runtime_error(msg);}
NavState state(Vec3 rpy=makeVec3(0,0,0)) {
 NavState s;s.pos_blh_rad_m=makeVec3(.6,1.1,20);s.euler_rad=rpy;
 s.qbn=Rotation::euler2quaternion(rpy);s.cbn=Rotation::quaternion2matrix(s.qbn);return s;
}
PortOptions opts() {
 PortOptions o;o.dual_antenna_measurement_model="baseline3d";o.baseline3d_source="external_carrier";
 o.baseline3d_length_m=.35;o.baseline3d_body_vector_m=makeVec3(0,-.35,0);
 o.enable_receiver_velocity_update=false;o.init_att_std_rad=makeVec3(.1,.1,.1);return o;
}
GnssData observation(const NavState&s,double t) {
 GnssData d;d.time=t;d.validity_explicit=true;d.has_position=d.has_velocity=d.has_yaw=false;
 d.auxiliary_updates_allowed=false;d.baseline3d.source="external_carrier";
 d.baseline3d.measurement_time=d.baseline3d.decision_available_time=t;
 d.baseline3d.present=d.baseline3d.valid=true;
 d.baseline3d.ecef_m=multiply(Earth::cne(s.pos_blh_rad_m),multiply(s.cbn,makeVec3(0,-.35,0)));
 d.baseline3d.covariance_ecef_m2=Matrix3{{{{.0004,.0001,0}},{{.0001,.0009,.0002}},{{0,.0002,.0016}}}};
 return d;
}
void math() {
 double worst=0;
 for(auto rpy:{makeVec3(0,0,0),makeVec3(.4,-.3,1.2),makeVec3(-.7,.6,-2.8)}) {
  auto s=state(rpy);auto obs=observation(s,1).baseline3d;
  auto m=buildExternalCarrierBaseline3dModel(s.cbn,s.pos_blh_rad_m,obs,opts().baseline3d_body_vector_m);
  need(norm(m.residual_m)<1e-15,"ECEF/NED or GNSS2-1 sign");
  // Full covariance inverse rotation recovers every supplied off-diagonal.
  Matrix3 rn{};for(int i=0;i<3;++i)for(int j=0;j<3;++j)rn[i][j]=m.R(i,j);
  auto re=multiply(multiply(Earth::cne(s.pos_blh_rad_m),rn),transpose(Earth::cne(s.pos_blh_rad_m)));
  for(int i=0;i<3;++i)for(int j=0;j<3;++j)need(std::abs(re[i][j]-obs.covariance_ecef_m2[i][j])<2e-18,"covariance lost offdiag");
  for(int j=0;j<3;++j){Vec3 p{};p[j]=1e-6;
   auto cp=multiply(Rotation::quaternion2matrix(Rotation::rotvec2quaternion(scale(p,-1))),s.cbn);
   auto cm=multiply(Rotation::quaternion2matrix(Rotation::rotvec2quaternion(p)),s.cbn);
   auto rp=buildExternalCarrierBaseline3dModel(cp,s.pos_blh_rad_m,obs,opts().baseline3d_body_vector_m).residual_m;
   auto rm=buildExternalCarrierBaseline3dModel(cm,s.pos_blh_rad_m,obs,opts().baseline3d_body_vector_m).residual_m;
   for(int i=0;i<3;++i)worst=std::max(worst,std::abs((rp[i]-rm[i])/2e-6-m.H(i,PHI_ID+j)));
  }
  // Swapping receivers negates both ECEF/body baselines; covariance is unchanged.
  auto swapped=obs;swapped.ecef_m=scale(obs.ecef_m,-1);
  auto sm=buildExternalCarrierBaseline3dModel(s.cbn,s.pos_blh_rad_m,swapped,makeVec3(0,.35,0));
  need(norm(sm.residual_m)<1e-15,"receiver swap mismatch");
  for(int i=0;i<3;++i)for(int j=0;j<3;++j)need(sm.R(i,j)==m.R(i,j),"swap covariance");
 }
 need(worst<1e-9,"feedback-convention Jacobian");
 // At equator/prime meridian N=z, E=y, D=-x, providing an independent axis oracle.
 auto s=state();s.pos_blh_rad_m=makeVec3(0,0,0);
 auto obs=observation(s,1).baseline3d;
 need(obs.ecef_m[0]==0&&obs.ecef_m[1]==-.35&&obs.ecef_m[2]==0,"FLU +Y -> FRD -Y");
 std::cout<<"jacobian_error="<<worst<<'\n';
}
void events(const std::string& out) {
 auto o=opts();o.go2_attitude_prior_config.enable_go2_attitude_weak_prior=true;
 GIEngine e(o);auto s=state();e.initialize(s);
 Go2AttitudeWeakPriorStatus status;status.solver_enabled=true;status.provider_status="available";
 Go2AttitudeWeakPriorMeasurement prior;prior.time=1.004;prior.source_status="active";
 e.setGo2AttitudeWeakPriors({prior},status);
 ImuData first;first.time=1;first.dt=.005;e.addImuData(first,true);
 ImuData next;next.time=1.005;next.dt=.005;next.dvel=makeVec3(0,0,-Earth::gravity(s.pos_blh_rad_m)*.005);
 e.addImuData(next);
 auto a=observation(s,1.0005),b=observation(s,1.004),invalid=observation(s,1.005);
 invalid.baseline3d.valid=false;invalid.baseline3d.reason="provider_invalid";
 e.newImuProcessWithEvents({a,b,invalid});
 need(e.baseline3dCounts().attempts==2&&e.baseline3dCounts().accepted==2,"dropped close events");
 need(e.baseline3dCounts().invalid==1,"invalid event counted as fix");
 need(e.go2AttitudeWeakPriorUpdateCount()==0,"carrier-only duplicate RP update");
 need(e.positionUpdateCount()==0&&e.velocityUpdateCount()==0,"fabricated PV");
 need(e.timestamp()==1.005&&e.checkCov(),"wrong final time/cov");
 auto rows=e.baseline3dDiagnostics();need(rows[0].time==1.0005&&rows[1].time==1.004,"early timestamp snapping");
 next.time=1.010;e.addImuData(next);e.newImuProcessWithEvents({});
 need(e.baseline3dCounts().attempts==2,"consumed twice");
 e.writeBaseline3dDiagnostics(out);
 o.baseline3d_counts=e.baseline3dCounts();FileSaver::writeRunManifest(out,o);
 bool rejected=false;next.time=1.015;e.addImuData(next);
 try {e.newImuProcessWithEvents({observation(s,1.016)});}catch(const std::runtime_error&){rejected=true;}
 need(rejected,"future observation accepted");
}
void scalar() {
 auto a=opts();a.dual_antenna_measurement_model="scalar";a.baseline3d_source="dual_pvt";
 a.stage_id="IMU_V3_TIME_CONTRACT_FIX_20261004";
 auto b=a;b.stage_id="arbitrary_new_experiment";b.dual_yaw_prediction_model="lateral_projection";
 auto s=state(makeVec3(.3,-.2,1));GIEngine ea(a),eb(b);ea.initialize(s);eb.initialize(s);
 auto d=observation(s,1);d.isvalid=d.has_yaw=true;
 auto bn=multiply(s.cbn,makeVec3(0,-1,0));d.yaw_rad=std::atan2(bn[1],bn[0])+kPi/2+.01;d.yaw_std_rad=.03;
 auto db=d;ea.gnssUpdate(d);eb.gnssUpdate(db);ea.stateFeedback();eb.stateFeedback();
 for(int i=0;i<3;++i)need(ea.navState().euler_rad[i]==eb.navState().euler_rad[i],"explicit scalar model drift");
 need(ea.getCovariance()==eb.getCovariance(),"explicit scalar covariance drift");
}
void measured_dt_split() {
 auto o=opts();GIEngine e(o);auto s=state();e.initialize(s);
 ImuData first;first.time=0;first.dt=.01;e.addImuData(first,true);
 ImuData next;next.time=.01;next.dt=.009999;
 next.dvel=makeVec3(0,0,-Earth::gravity(s.pos_blh_rad_m)*next.dt);e.addImuData(next);
 // Valid loader tolerance: elapsed differs from measured dt by one microsecond.
 // An elapsed-based split would leave -0.5 us and trigger the old 10 ms fallback.
 auto d=observation(s,.0099995);e.newImuProcessWithEvents({d});
 need(e.timestamp()==.01&&e.propagationCount()==2,"wrong near-end splitting");
 need(norm(e.navState().vel_ned_mps)<1e-4,"negative dt remainder/fallback propagation");
 need(e.checkCov(),"near-end covariance");
}
void invalid_equivalence() {
 auto o=opts();GIEngine absent(o),invalid(o);auto s=state();absent.initialize(s);invalid.initialize(s);
 ImuData imu;imu.time=1;imu.dt=.005;absent.addImuData(imu,true);invalid.addImuData(imu,true);
 for(int i=1;i<=4;++i){
  imu.time=1+.005*i;imu.dtheta=makeVec3(.0001*i,-.0002,.00005);imu.dvel=makeVec3(.002,.001,-.049);
  absent.addImuData(imu);invalid.addImuData(imu);
  auto d=observation(s,imu.time-.002);d.baseline3d.valid=false;d.baseline3d.reason="provider_invalid";
  absent.newImuProcessWithEvents({});invalid.newImuProcessWithEvents({d});
  need(absent.getCovariance()==invalid.getCovariance(),"invalid event split propagation covariance");
  need(absent.navState().pos_blh_rad_m==invalid.navState().pos_blh_rad_m&&
       absent.navState().vel_ned_mps==invalid.navState().vel_ned_mps&&
       absent.navState().euler_rad==invalid.navState().euler_rad,"invalid event changed NAV");
 }
 need(absent.propagationCount()==invalid.propagationCount()&&invalid.updateCount()==0,"invalid event counted update");
 need(invalid.baseline3dCounts().invalid==4&&absent.baseline3dCounts().invalid==0,"missing diagnostics");
}
void causal_aids() {
 auto o=opts();o.runtime_contract="research_experiment";
 o.go2_attitude_prior_config.enable_go2_attitude_weak_prior=true;
 o.raw_doppler_config.enable_raw_doppler=true;
 GIEngine e(o);auto s=state();e.initialize(s);
 ImuData imu;imu.time=1;imu.dt=.005;e.addImuData(imu,true);
 Go2AttitudeWeakPriorStatus ps;ps.solver_enabled=true;ps.provider_status="available";
 Go2AttitudeWeakPriorMeasurement p;p.time=1.004;p.source_status="active";p.quality_flag="nominal";
 e.setGo2AttitudeWeakPriors({p},ps);
 RawDopplerFactorStatus rs;rs.solver_enabled=true;rs.provider_status="available";
 RawDopplerVelocityMeasurement rd;rd.time=1.004;rd.source_time=1.004;rd.provider_status="available";rd.sat_count=8;
 e.setRawDopplerVelocityMeasurements({rd},rs);
 for(double t:{1.003,1.004,1.005}){
  auto d=observation(s,t);d.auxiliary_updates_allowed=true;e.addGnssData(d);e.gnssUpdate();e.stateFeedback();
  need(e.go2AttitudeWeakPriorUpdateCount()==(t<1.004?0:1),"RP future/repeat");
  need(e.rawDopplerUpdateCount()==(t<1.004?0:1),"RD future/repeat");
 }
}
int main(int argc,char**argv){try{std::string m=argv[1];std::cout<<std::setprecision(17);
 if(m=="math")math();else if(m=="events")events(argv[2]);else if(m=="scalar")scalar();else if(m=="causal_aids")causal_aids();else if(m=="invalid_equivalence")invalid_equivalence();else if(m=="measured_dt_split")measured_dt_split();
 else if(m=="load"){for(auto&r:GnssFileLoader::loadExternalCarrier(argv[2],argv[3]))std::cout<<r.time<<','<<r.has_position<<','<<r.has_velocity<<','<<r.has_yaw<<','<<r.baseline3d.present<<','<<r.baseline3d.valid<<','<<r.auxiliary_updates_allowed<<'\n';}
 else if(m=="config"){auto o=PortConfigLoader::loadYamlLike(argv[2]);FileSaver::writeRunManifest(argv[3],o);}
 else return 2;return 0;}catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 1;}}
'''

@pytest.fixture(scope="module")
def harness(tmp_path_factory):
    build = tmp_path_factory.mktemp("external_carrier_cpp")
    subprocess.run(["cmake", "-S", str(ROOT / "cpp"), "-B", str(build), "-DCMAKE_BUILD_TYPE=Release"], check=True, capture_output=True)
    subprocess.run(["cmake", "--build", str(build), "--target", "legsa_v23_port_core", "-j4"], check=True, capture_output=True)
    source = build / "test.cpp"
    source.write_text(HARNESS)
    exe = build / "test"
    subprocess.run(["c++", "-std=c++17", "-O2", "-I", str(ROOT / "cpp/legsa_v23_port_core/include"), str(source), str(build / "liblegsa_v23_port_core.a"), "-o", str(exe)], check=True)
    return exe

def run(harness, *args, ok=True):
    p = subprocess.run([str(harness), *map(str, args)], capture_output=True, text=True)
    assert (p.returncode == 0) == ok, p.stdout + p.stderr
    return p

def test_full_covariance_frames_receiver_swap_and_jacobian(harness):
    run(harness, "math")

def test_exact_event_queue_no_duplicate_aids_invalid_not_fix(harness, tmp_path):
    run(harness, "events", tmp_path)
    rows = list(csv.DictReader((tmp_path / "BASELINE3D_DIAGNOSTICS.csv").open()))
    assert len(rows) == 3 and all(None not in r for r in rows)
    assert rows[0]["source"] == "external_carrier"
    assert rows[0]["pAcc1_m"] == rows[0]["pAcc2_m"] == ""
    assert float(rows[0]["R_ne"]) != 0
    m = json.loads((tmp_path / "RUN_MANIFEST.json").read_text())
    assert m["external_carrier_valid_is_trusted_FIX"] is False
    assert m["external_carrier_pacc_used"] is False
    assert m["actual_solver_input_roles"]["dual_antenna_baseline3d"] == "experimental_external_carrier_baseline_full_covariance"

def test_explicit_projected_yaw_reproduces_existing_equation(harness):
    run(harness, "scalar")

def write_inputs(tmp_path, carrier=VALID):
    g, c = tmp_path / "gnss.txt", tmp_path / "carrier.csv"
    g.write_text("1 30 120 0 1 1 1 0 0 0 1 1 1 99 1 1 0 1\n2 30 120 0 1 1 1 0 0 0 1 1 1 88 1 0 1 1\n")
    c.write_text(HEADER + carrier)
    return g, c

def test_loader_exact_union_source_replacement_and_invalid(harness, tmp_path):
    g, c = write_inputs(tmp_path, VALID + VALID.replace("1,1,", "1.0005,1.0005,", 1) + "3,3,,,,,,,,,,,,,0\n")
    lines = run(harness, "load", g, c).stdout.splitlines()
    assert lines == ["1,1,0,0,1,1,1", "1.0004999999999999,0,0,0,1,1,0", "2,0,1,0,0,0,1", "3,0,0,0,1,0,0"]

@pytest.mark.parametrize("bad,reason", [
    (VALID.replace("1,1,", "1,1.1,", 1), "DELAYED_OR_FUTURE"),
    (VALID.replace("1,1,", "1.1,1,", 1), "DELAYED_OR_FUTURE"),
    (VALID + VALID, "TIMES_NOT_STRICTLY"),
    (VALID.replace("0.0004", "nan"), "NONFINITE"),
    (VALID.replace("0.0001", "0.0002", 1), "NOT_SYMMETRIC"),
    (VALID.replace("0.0004", "-0.0004"), "NOT_SPD"),
    (VALID.replace("0,-0.35,0", "0,0,0"), "ZERO_BASELINE"),
    (VALID.replace("0.0004", ""), "stod"),
])
def test_external_input_fail_closed(harness, tmp_path, bad, reason):
    g, c = write_inputs(tmp_path, bad)
    assert reason in run(harness, "load", g, c, ok=False).stderr

RESEARCH = """runtime_contract: research_experiment
stage_id: arbitrary_stage
protocol_id: arbitrary_protocol
case_id: arbitrary_case
run_id: run001
run_label: run001
data_mode: real_clean
algorithm_id: strong_dual_yaw_EKF
enable_dual_yaw: true
enable_receiver_velocity: true
enable_raw_doppler: false
enable_source_aware: false
enable_go2_roll_pitch_prior: false
enable_go2_horizontal_velocity_prior: false
go2_position_truth_claim: false
go2_velocity_truth_claim: false
go2_yaw_truth_claim: false
go2_contact_truth_claim: false
common_initialization: true
common_initialization_dual_yaw_used: true
common_initialization_source: declared_sensor_initialization
dual_yaw_prediction_model: lateral_projection
"""
EXTERNAL = """dual_antenna_measurement_model: baseline3d
baseline3d_source: external_carrier
external_carrier_baseline_path: carrier.csv
baseline3d_body_vector_m: [0, -0.35, 0]
"""

def test_generic_research_identity_and_no_fake_pacc(harness, tmp_path):
    cfg = tmp_path / "cfg"
    cfg.write_text(RESEARCH + EXTERNAL)
    run(harness, "config", cfg, tmp_path / "out")
    m = json.loads((tmp_path / "out/RUN_MANIFEST.json").read_text())
    assert m["runtime_contract"] == "research_experiment"
    assert m["external_carrier_body_vector_frd_m"] == [0, -.35, 0]
    assert m["actual_solver_input_paths"]["dual_antenna_baseline3d"] == "carrier.csv"

@pytest.mark.parametrize("change,reason", [
    ("trace_used_online: true\n", "forbidden input"),
    ("enable_raw_doppler: true\n", "flags do not match"),
    ("baseline3d_body_vector_m: [0,0,0]\n", "INVALID_BODY_VECTOR"),
    ("baseline3d_body_vector_m: [0,-.35,0,1]\n", "INVALID_BODY_VECTOR"),
])
def test_research_does_not_bypass_scientific_gates(harness, tmp_path, change, reason):
    cfg = tmp_path / "cfg"
    cfg.write_text(RESEARCH + EXTERNAL + change)
    assert reason in run(harness, "config", cfg, tmp_path / "out", ok=False).stderr


def test_research_rd_rp_past_only_and_once_per_timestamp(harness):
    run(harness, "causal_aids")


def test_external_loader_does_not_read_commercial_yaw_tokens(harness, tmp_path):
    g, c = write_inputs(tmp_path)
    g.write_text(g.read_text().replace("99 1 1 0 1", "NO_YAW NO_STD 1 0 NO_FLAG").replace("88 1 0 1 1", "NO_YAW NO_STD 0 1 NO_FLAG"))
    rows = run(harness, "load", g, c).stdout.splitlines()
    assert len(rows) == 2 and rows[0] == "1,1,0,0,1,1,1"


def test_invalid_carrier_is_exactly_equivalent_to_no_measurement(harness):
    run(harness, "invalid_equivalence")


def test_measured_dt_near_end_event_does_not_create_negative_remainder(harness):
    run(harness, "measured_dt_split")
