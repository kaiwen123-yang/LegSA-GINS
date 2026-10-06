"""Actual pinned author-model checks; synthetic arrays never performance rows."""
import json
import os
from pathlib import Path
import subprocess
import numpy as np
import pytest

gtsam=pytest.importorskip("gtsam")
from legsa_gins.paper_rebuild.fgo_comparison.obgins_preintegration import EarthPreintegration,pack_state,UPSTREAM_COMMIT
from legsa_gins.paper_rebuild.fgo_comparison.oisam import OiSAMGraph,run_inputs
from legsa_gins.paper_rebuild.fgo_comparison.oisam_inputs import SequenceInput

ROOT=Path(__file__).resolve().parents[2]

def config():
    return json.loads((ROOT/"configs/paper_rebuild/fgo_comparison/OISAM_PAPER_CONTRACT_20261004.json").read_text())

def body_motion(cfg,steps=100):
    dt=np.resize([.008,.011,.009,.012],steps)
    rate=np.array([.012,-.023,.15]); force=np.array([.3,-.2,-9.8])
    return [(float(t),rate*t,force*t) for t in dt]

def state0():
    return (gtsam.Pose3(gtsam.Rot3.Ypr(.5,-.03,.02),np.array([1.,2.,-.4])),
            np.array([2.,.3,-.2]),gtsam.imuBias.ConstantBias(np.array([.02,-.03,.01]),np.array([.001,-.002,.003])))

def model(cfg=None):
    cfg=cfg or config(); pieces=body_motion(cfg)
    return EarthPreintegration(cfg,[40.,116.,40.],9.8,*state0(),0.,pieces,pieces[0])

@pytest.fixture(scope="module")
def direct_oracle(tmp_path_factory):
    upstream=os.environ.get("LEGSA_OBGINS_UPSTREAM")
    if not upstream:
        pytest.fail("actual author-model tests require LEGSA_OBGINS_UPSTREAM; do not silently skip")
    upstream=Path(upstream)
    assert subprocess.check_output(["git","rev-parse","HEAD"],cwd=upstream,text=True).strip()==UPSTREAM_COMMIT
    binary=tmp_path_factory.mktemp("obgins_oracle")/"oracle"
    subprocess.run(["g++","-std=c++17","-O2","-DNDEBUG","-I"+str(upstream),"-I/usr/include/eigen3",
        str(ROOT/"tests/paper_rebuild/obgins_oracle.cc"),str(upstream/"src/preintegration/preintegration_base.cc"),
        str(upstream/"src/preintegration/preintegration_earth.cc"),"-o",str(binary)],check=True)
    return binary

def test_actual_pinned_author_prediction_and_residual_match_bridge(direct_oracle):
    cfg=config(); cfg["accel_white_noise_mps_sqrt_s"]=[.1]*3; cfg["accel_bias_stationary_std_mps2"]=[.02]*3
    pieces=body_motion(cfg); a=state0(); instance=EarthPreintegration(cfg,[40,116,40],9.8,*a,0,pieces,pieces[0])
    station=np.array([np.deg2rad(40),np.deg2rad(116),40.])
    params=np.r_[station,9.8,cfg["bias_correlation_time_s"],cfg["gyro_white_noise_rad_sqrt_s"],.1,cfg["gyro_bias_stationary_std_radps"],.02]
    seed=np.r_[0.,pieces[0][0],pieces[0][1],pieces[0][2]]
    values=[*params,*pack_state(*a),*seed,len(pieces)]
    t=0.
    for dt,theta,vel in pieces:
        t+=dt; values.extend([t,dt,*theta,*vel])
    result=subprocess.run([str(direct_oracle)],input=" ".join(map(str,values)),text=True,capture_output=True,check=True)
    oracle=np.fromstring(result.stdout,sep=" ")
    b=instance.predict()
    np.testing.assert_allclose(pack_state(*b),oracle[:16],rtol=1e-13,atol=1e-13)
    np.testing.assert_allclose(instance.evaluate(*a,*b,jacobian=False),oracle[16:],rtol=1e-8,atol=1e-9)

@pytest.mark.parametrize("node",[0,1])
def test_upstream_analytic_jacobian_in_exact_gtsam_chart(node):
    instance=model(); states=[*state0(),*instance.predict()]
    residual,blocks=instance.evaluate(*states)
    analytic=np.hstack(blocks[node*3:node*3+3])
    numeric=np.zeros_like(analytic)
    for j in range(15):
        eps=1e-7 if j<6 else 1e-8
        d=np.eye(15)[j]*eps
        outputs=[]
        for sign in (1,-1):
            values=list(states); base=node*3
            values[base]=values[base].retract(sign*d[:6])
            values[base+1]=values[base+1]+sign*d[6:9]
            b=values[base+2]
            values[base+2]=gtsam.imuBias.ConstantBias(b.accelerometer()+sign*d[9:12],b.gyroscope()+sign*d[12:15])
            outputs.append(instance.evaluate(*values,jacobian=False))
        numeric[:,j]=(outputs[0]-outputs[1])/(2*eps)
    # Upstream retains first-order bias correction; this check is at its anchor.
    np.testing.assert_allclose(analytic,numeric,rtol=2e-4,atol=2e-4)


def test_covariance_is_joint_positive_and_bias_cross_terms_are_not_discarded():
    instance=model()
    assert np.linalg.eigvalsh(instance.covariance).min()>0
    assert np.linalg.norm(instance.covariance[:9,9:])>0
    np.testing.assert_allclose(instance.covariance,instance.covariance.T,atol=1e-14)


def row(t):
    return np.array([t,40.,116.,40.,.02,.02,.03,0.,0.,0.,.05,.05,.05,20.,1.5,1.,1.,1.])

def static_imu(end=50):
    ts=np.arange(0.,end+.005,.01); u=np.zeros((len(ts),7)); u[:,0]=ts; u[:,6]=-9.801554354839126*.01
    return u

def test_strict_real_contract_consumes_only_one_yaw_then_exposes_gap():
    cfg=config(); imu=static_imu(8.)
    imu=imu[(imu[:,0]<3.2)|(imu[:,0]>3.5)]
    nodes=[(float(t),row(t),t) for t in range(1,8)]
    inputs=SequenceInput("BY2",np.array([row(t) for t in range(1,8)]),imu,nodes,{})
    records=[]; events=[]
    result=run_inputs(inputs,cfg,records.append,events.append)
    assert result["A1_yaw_initialization_count"]==1
    assert result["mandatory_input_failure"].startswith("IMU_GAP")
    assert all(r[10]==0 for r in records if r[0]>=4)
    assert all(np.isnan(r[1:10]).all() for r in records if r[0]>=4)
    assert any(e.get("reason")=="AFTER_INPUT_GAP_NO_REINITIALIZATION" for e in events)


def test_continuous_synthetic_chain_really_runs_oisam_ajswr_and_marginalization():
    cfg=config(); imu=static_imu(44.)
    nodes=[(float(t),row(t),t) for t in range(1,44)]
    inputs=SequenceInput("BY2",np.array([row(t) for t in range(1,44)]),imu,nodes,{})
    states=[]; events=[]; result=run_inputs(inputs,cfg,states.append,events.append)
    assert result["A1_yaw_initialization_count"]==1 and result["mandatory_input_failure"] is None
    assert result["finite_nodes"]==len(nodes)
    assert result["core_counts"]["incremental_updates"]>0
    assert result["core_counts"]["marginalized_nodes"]>0
    assert result["core_counts"]["window_triggers"]>0
    assert any("OISAM_INCREMENTAL" in e["mode"] for e in events)
