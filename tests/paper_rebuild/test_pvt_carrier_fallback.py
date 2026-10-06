"""Eight bounded synthetic C++ checks; no raw/reference/native navigation trials."""
import csv
import json
import os
import subprocess
from pathlib import Path
import pytest
from test_external_carrier_fusion import HARNESS as BASE, RESEARCH, EXTERNAL, HEADER, VALID
ROOT=Path(__file__).resolve().parents[2]
EXTRA=r"""
PortOptions priority(const std::string& policy="pvt_priority_fallback") {
 auto o=opts();o.runtime_contract="research_experiment";o.heading_source_policy=policy;
 o.dual_yaw_prediction_model="lateral_projection";return o;
}
GnssData pvt(const NavState& s,double t,bool valid) {
 GnssData d;d.time=t;d.validity_explicit=true;d.pvt_heading_source_present=true;
 d.has_position=d.has_velocity=false;d.has_yaw=valid;d.yaw_std_rad=.03;d.yaw_std_deg=.03*R2D;
 const auto v=multiply(s.cbn,makeVec3(0,-1,0));
 d.yaw_rad=std::atan2(v[1],v[0])+kPi/2;d.yaw_deg=d.yaw_rad*R2D;return d;
}
void init(GIEngine& e,const NavState& s) {
 e.initialize(s);ImuData imu;imu.time=1;imu.dt=.005;e.addImuData(imu,true);
}
void step(GIEngine& e,double t,const std::vector<GnssData>& events) {
 ImuData imu;imu.time=t;imu.dt=t-e.timestamp(); // timestamp after initialize is 1 below
 imu.dtheta=makeVec3(.00003,-.00002,.00001);
 imu.dvel=makeVec3(.0001,.0002,-Earth::gravity(e.navState().pos_blh_rad_m)*imu.dt);
 e.addImuData(imu);e.newImuProcessWithEvents(events);
}
NavState timed_state(Vec3 rpy=makeVec3(0,0,0)){auto s=state(rpy);s.time=1;return s;}
void same(const GIEngine& a,const GIEngine& b) {
 need(a.getCovariance()==b.getCovariance(),"covariance differs");
 need(a.navState().pos_blh_rad_m==b.navState().pos_blh_rad_m &&
      a.navState().vel_ned_mps==b.navState().vel_ned_mps &&
      a.navState().euler_rad==b.navState().euler_rad,"state differs");
 need(a.propagationCount()==b.propagationCount(),"propagation differs");
}
void eligibility() {
 HeadingSourcePolicy p;
 need(!p.arrive(1,false,false,true,true,false).use_carrier,"unknown accepted");
 p.arrive(1.1,true,false,false,false,false);
 need(p.arrive(1.31,false,false,true,true,false).use_carrier,"fresh boundary lost");
 need(!p.arrive(1.3101,false,false,true,true,false).use_carrier,"stale accepted");
 auto d=p.arrive(1.4,true,false,true,true,false);need(d.use_carrier&&!d.use_pvt,"same invalid PVT gap");
 bool blocked=false;try{p.arrive(1.39,true,false,true,true,false);}catch(...){blocked=true;}
 need(blocked,"past event allowed");
}
void hold() {
 HeadingSourcePolicy p;p.arrive(1,true,false,false,false,false);
 auto c=p.arrive(1.198,false,false,true,true,false);need(c.use_carrier,"carrier blocked");p.accepted(c);
 auto d=p.arrive(1.2,true,true,false,false,false);
 need(!d.use_pvt&&d.pvt_source_valid,"2ms recovery source not retained");
 need(!p.arrive(1.202,false,false,true,true,false).use_carrier,"suppressed PVT source ignored");
 need(p.arrive(1.4,true,true,false,false,false).use_pvt,"next cycle suppressed");
 HeadingSourcePolicy rejected;rejected.arrive(1,true,false,false,false,false);
 auto attempt=rejected.arrive(1.198,false,false,true,true,false);need(attempt.use_carrier,"reject fixture");
 need(rejected.arrive(1.2,true,true,false,false,false).use_pvt,"rejected carrier occupied hold");
}
void coincidence() {
 HeadingSourcePolicy p;
 auto a=p.arrive(1,true,true,true,true,false);
 need(a.use_pvt&&!a.use_carrier,"coincident double heading");p.accepted(a);
 p.arrive(1.001,true,false,false,false,false);
 need(!p.arrive(1.005,false,false,true,true,false).use_carrier,"accepted PVT not excluded");
 need(p.arrive(1.011,false,false,true,true,false).use_carrier,"hold extended");
}
void scalar_preservation() {
 scalar(); // Existing old-stage projection equals explicitly selected formula.
 for(const auto& model:{"euler_yaw","lateral_projection"}) {
  auto a=priority("pvt_priority_control");auto b=a;b.heading_source_policy="configured";
  b.dual_antenna_measurement_model="scalar";b.baseline3d_source="dual_pvt";
  a.dual_yaw_prediction_model=b.dual_yaw_prediction_model=model;
  auto s=timed_state(makeVec3(.3,-.2,1));GIEngine ea(a),eb(b);init(ea,s);init(eb,s);
  auto d=pvt(s,1.002,true);d.yaw_rad += .01;
  step(ea,1.005,{d});step(eb,1.005,{d});same(ea,eb);
  need(ea.headingSourceCounts().pvt_accepted==1&&ea.baseline3dCounts().attempts==0,"scalar path not used");
 }
 auto o=opts();need(o.heading_source_policy=="configured","default changed");
 GIEngine e(o);auto s=state();e.initialize(s);auto d=observation(s,1);d.isvalid=true;
 e.gnssUpdate(d);need(e.baseline3dCounts().accepted==1,"default external replacement changed");
}
void aids(GIEngine& e) {
 Go2AttitudeWeakPriorStatus ps;ps.solver_enabled=true;ps.provider_status="available";
 Go2AttitudeWeakPriorMeasurement p;p.time=1.001;p.source_status="active";p.quality_flag="nominal";
 e.setGo2AttitudeWeakPriors({p},ps);
 RawDopplerFactorStatus rs;rs.solver_enabled=true;rs.provider_status="available";
 RawDopplerVelocityMeasurement rd;rd.time=1.001;rd.source_time=1.001;rd.provider_status="available";rd.sat_count=8;
 e.setRawDopplerVelocityMeasurements({rd},rs);
 Go2VelocityDiagnosticPriorStatus vs;vs.solver_enabled=true;vs.provider_status="available";vs.controlled_activation=true;
 Go2VelocityDiagnosticPriorMeasurement v;v.time=1.001;v.source_status="active";v.quality_flag="nominal";
 e.setGo2VelocityDiagnosticPriors({v},vs);
}
void all_valid() {
 auto a=priority("pvt_priority_control"),b=priority();
 for(auto* o:{&a,&b}) {
  o->raw_doppler_config.enable_raw_doppler=true;
  o->go2_attitude_prior_config.enable_go2_attitude_weak_prior=true;
  o->go2_velocity_prior_diagnostic_config.enable_go2_velocity_prior_diagnostic=true;
  o->go2_velocity_prior_diagnostic_config.enable_go2_horizontal_velocity_prior=true;
  o->source_aware_policy_config.enable_source_aware_weighting=true;
 }
 auto s=timed_state();GIEngine control(a),fallback(b),absent(a);init(control,s);init(fallback,s);init(absent,s);
 aids(control);aids(fallback);aids(absent);
 for(int i=0;i<4;++i) {
  double t=1.002+i*.005;auto d=pvt(s,t,true);auto c=observation(s,t+.001);
  step(control,t+.003,{d,c});step(fallback,t+.003,{d,c});step(absent,t+.003,{d});
  same(control,fallback);same(control,absent);
 }
 need(control.headingSourceCounts().pvt_accepted>0,"PVT inactive fixture");
 need(fallback.headingSourceCounts().carrier_attempts==0,"all-valid PVT attempted carrier");
 need(control.rawDopplerUpdateCount()==1 && control.go2AttitudeWeakPriorUpdateCount()==1,"past once aids fixture");
 need(control.go2VelocityDiagnosticPriorUpdateCount()>0,"HV fixture inactive");
 need(control.rawDopplerUpdateCount()==fallback.rawDopplerUpdateCount()&&
      control.go2AttitudeWeakPriorUpdateCount()==fallback.go2AttitudeWeakPriorUpdateCount()&&
      control.go2VelocityDiagnosticPriorUpdateCount()==fallback.go2VelocityDiagnosticPriorUpdateCount()&&
      control.sourceAwareEvaluationCount()==fallback.sourceAwareEvaluationCount()&&
      control.sourceAwareEvaluationCount()==absent.sourceAwareEvaluationCount(),"suppressed carrier triggered aiding/SA");
}
void engine_accept_reject(const std::string& out) {
 auto s=timed_state();auto o=priority();
 // Engine NIS rejection reserves no hold; source recovery is attempted at +2ms.
 GIEngine rejected(o);init(rejected,s);
 auto bad=observation(s,1.003);bad.baseline3d.ecef_m=scale(bad.baseline3d.ecef_m,100);
 step(rejected,1.006,{pvt(s,1.001,false),bad,pvt(s,1.005,true)});
 need(rejected.baseline3dCounts().rejected==1&&rejected.headingSourceCounts().pvt_accepted==1,"NIS reject occupied hold");
 // Accepted carrier excludes near PVT, not its P/V/aux rows. No carrier-only auxiliary call.
 GIEngine accepted(o);init(accepted,s);
 auto recovery=pvt(s,1.005,true);recovery.has_position=true;recovery.blh_rad_m=s.pos_blh_rad_m;
 step(accepted,1.006,{pvt(s,1.001,false),observation(s,1.003),recovery});
 need(accepted.headingSourceCounts().carrier_accepted==1&&accepted.headingSourceCounts().pvt_suppressed==1,"accepted hold not enforced");
 need(accepted.positionUpdateCount()==1&&accepted.velocityUpdateCount()==0,"suppressed PVT lost position");
 need(accepted.headingSourceEvents().back().pvt_source_valid,"PVT source metadata changed by hold");
 accepted.writeHeadingSourceDiagnostics(out);
 o.heading_source_counts=accepted.headingSourceCounts();o.baseline3d_counts=accepted.baseline3dCounts();
 FileSaver::writeRunManifest(out,o);
 // Invalid-only carrier remains exactly equivalent to no event.
 GIEngine invalid(o),empty(o);init(invalid,s);init(empty,s);
 for(int i=1;i<=3;++i) {
  auto d=observation(s,1+.005*i-.002);d.baseline3d.valid=false;
  step(invalid,1+.005*i,{d});step(empty,1+.005*i,{});same(invalid,empty);
 }
 need(invalid.updateCount()==0&&invalid.headingSourceCounts().carrier_bypassed==3,"invalid entered GNSS update");
 // A wholly invalid PVT row does not make a coincident carrier an auxiliary trigger.
 auto ao=priority();ao.raw_doppler_config.enable_raw_doppler=true;
 ao.go2_attitude_prior_config.enable_go2_attitude_weak_prior=true;
 ao.go2_velocity_prior_diagnostic_config.enable_go2_velocity_prior_diagnostic=true;
 ao.go2_velocity_prior_diagnostic_config.enable_go2_horizontal_velocity_prior=true;
 GIEngine coincident(ao);init(coincident,s);aids(coincident);
 auto combined=pvt(s,1.003,false);combined.baseline3d=observation(s,1.003).baseline3d;
 step(coincident,1.005,{combined});
 need(coincident.baseline3dCounts().accepted==1,"coincident carrier fixture");
 need(coincident.rawDopplerUpdateCount()==0&&coincident.go2AttitudeWeakPriorUpdateCount()==0&&
      coincident.go2VelocityDiagnosticPriorUpdateCount()==0,"wholly invalid PVT activated auxiliaries");
 GIEngine invalid_pvt(ao);init(invalid_pvt,s);aids(invalid_pvt);
 combined.baseline3d.valid=false;step(invalid_pvt,1.005,{combined});
 need(invalid_pvt.updateCount()==0&&invalid_pvt.rawDopplerUpdateCount()==0&&
      invalid_pvt.go2AttitudeWeakPriorUpdateCount()==0&&invalid_pvt.go2VelocityDiagnosticPriorUpdateCount()==0,
      "invalid merged event fabricated GNSS/aux update");
 GIEngine yaw_only_recovery(ao);init(yaw_only_recovery,s);aids(yaw_only_recovery);
 step(yaw_only_recovery,1.006,{pvt(s,1.001,false),observation(s,1.003),pvt(s,1.005,true)});
 need(yaw_only_recovery.headingSourceCounts().pvt_suppressed==1&&
      yaw_only_recovery.rawDopplerUpdateCount()==1&&yaw_only_recovery.go2AttitudeWeakPriorUpdateCount()==1&&
      yaw_only_recovery.go2VelocityDiagnosticPriorUpdateCount()==1,
      "suppressed source-valid yaw-only PVT lost original auxiliaries");
}
int main(int argc,char** argv) {
 try {
  std::string m=argv[1];
  if(m=="eligibility")eligibility();else if(m=="hold")hold();else if(m=="coincidence")coincidence();
  else if(m=="scalar_preservation")scalar_preservation();else if(m=="all_valid")all_valid();
  else if(m=="engine_accept_reject")engine_accept_reject(argv[2]);
  else if(m=="load_priority"||m=="load_default") {
   for(auto& d:GnssFileLoader::loadExternalCarrier(argv[2],argv[3],m=="load_priority"))
    std::cout<<d.time<<','<<d.pvt_heading_source_present<<','<<d.has_yaw<<','<<d.yaw_deg<<','<<d.yaw_std_deg<<','<<d.auxiliary_updates_allowed<<'\n';
  } else if(m=="config") {auto o=PortConfigLoader::loadYamlLike(argv[2]);GIEngine e(o);FileSaver::writeRunManifest(argv[3],o);}
  else return 2;
  std::cout<<"PASS\n";return 0;
 }catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}
}
"""

@pytest.fixture(scope="module")
def harness(tmp_path_factory):
    build=Path(os.environ["LEGSA_FALLBACK_BUILD_ROOT"]) if "LEGSA_FALLBACK_BUILD_ROOT" in os.environ else tmp_path_factory.mktemp("fallback_cpp")
    build.mkdir(parents=True,exist_ok=True)
    with (build/"BUILD.log").open("a") as log:
        for command in (["cmake","-S",str(ROOT/"cpp"),"-B",str(build),"-DCMAKE_BUILD_TYPE=Release"],
                        ["cmake","--build",str(build),"--target","legsa_v23_port_core_demo","-j4"]):
            subprocess.run(command,check=True,stdout=log,stderr=subprocess.STDOUT)
        source=build/"test.cpp";source.write_text(BASE.replace("int main(int argc,char**argv)","int legacy_main(int argc,char**argv)")+EXTRA)
        exe=build/"fallback_test"
        subprocess.run(["c++","-std=c++17","-O2","-I",str(ROOT/"cpp/legsa_v23_port_core/include"),str(source),str(build/"liblegsa_v23_port_core.a"),"-o",str(exe)],check=True,stdout=log,stderr=subprocess.STDOUT)
    return exe

def run(exe,*args,ok=True):
    p=subprocess.run([str(exe),*map(str,args)],capture_output=True,text=True)
    with (exe.parent/"INVOCATIONS.jsonl").open("a") as f:
        f.write(json.dumps({"argv":[str(exe),*map(str,args)],"returncode":p.returncode,"stdout":p.stdout,"stderr":p.stderr})+"\n")
    assert (p.returncode==0)==ok,p.stdout+p.stderr
    return p

def test_01_explicit_config_and_default(harness,tmp_path):
    cfg=tmp_path/"config"
    cfg.write_text(RESEARCH+EXTERNAL+"heading_source_policy: pvt_priority_fallback\n")
    run(harness,"config",cfg,tmp_path/"valid")
    manifest=json.loads((tmp_path/"valid/RUN_MANIFEST.json").read_text())
    assert manifest["heading_source_policy"]=="pvt_priority_fallback"
    assert manifest["heading_pvt_freshness_s"]==.21
    assert manifest["heading_accepted_cross_source_exclusion_s"]==.01
    assert manifest["heading_integer_integrity_claim"] is False
    cfg.write_text(RESEARCH+EXTERNAL+"heading_source_policy: pvt_priority_control\n")
    run(harness,"config",cfg,tmp_path/"control")
    for bad in ("heading_source_policy: invalid\n","heading_source_policy: pvt_priority_fallback\ndual_yaw_prediction_model: legacy\n","heading_source_policy: pvt_priority_fallback\nruntime_contract: legacy\n"):
        cfg.write_text(RESEARCH+EXTERNAL+bad)
        run(harness,"config",cfg,tmp_path/"bad",ok=False)
    cfg.write_text(RESEARCH+EXTERNAL)
    run(harness,"config",cfg,tmp_path/"default")
    assert "heading_source_policy" not in json.loads((tmp_path/"default/RUN_MANIFEST.json").read_text())

def test_02_loader_source_fields_and_bad_tokens(harness,tmp_path):
    g,c=tmp_path/"gnss18",tmp_path/"carrier"
    g.write_text("1 30 120 0 1 1 1 0 0 0 1 1 1 23 2 1 0 1\n2 30 120 0 1 1 1 0 0 0 1 1 1 45 3 0 1 0\n")
    c.write_text(HEADER+VALID+"1.5,1.5,,,,,,,,,,,,,0\n")
    rows=run(harness,"load_priority",g,c).stdout.splitlines()[:-1]
    assert rows==["1,1,1,23,2,1","1.5,0,0,0,1,0","2,1,0,45,3,1"]
    g.write_text(g.read_text().replace("23 2 1 0 1","NO_YAW NO_STD 1 0 NO_FLAG"))
    run(harness,"load_default",g,c)
    run(harness,"load_priority",g,c,ok=False)

def test_03_causal_source_eligibility(harness):run(harness,"eligibility")
def test_04_acceptance_only_near_time_exclusion(harness):run(harness,"hold")
def test_05_coincident_priority_and_reverse_exclusion(harness):run(harness,"coincidence")
def test_06_default_and_scalar_formula_preservation(harness):run(harness,"scalar_preservation")
def test_07_all_valid_control_fallback_exact_equality_and_aids(harness):run(harness,"all_valid")
def test_08_engine_acceptance_rejection_and_invalid_bypass(harness,tmp_path):
    run(harness,"engine_accept_reject",tmp_path)
    rows=list(csv.DictReader((tmp_path/"HEADING_SOURCE_EVENTS.csv").open()))
    assert len(rows)==3 and rows[1]["carrier_attempted"]=="1" and rows[1]["accepted"]=="1"
    assert rows[2]["pvt_source_valid"]=="1" and rows[2]["pvt_attempted"]=="0"
    m=json.loads((tmp_path/"RUN_MANIFEST.json").read_text())
    assert m["heading_carrier_accept_count"]==1 and m["heading_pvt_suppressed_count"]==1
