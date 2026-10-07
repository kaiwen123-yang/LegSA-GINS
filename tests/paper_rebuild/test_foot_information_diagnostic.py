"""Eight preregistered synthetic-only passive foot-information qualification cases."""
import importlib.util,json,os,subprocess
from pathlib import Path
import numpy as np
import pytest
ROOT=Path(__file__).resolve().parents[2]
SPEC=importlib.util.spec_from_file_location("foot_info",ROOT/"scripts/paper_rebuild/carrier_phase/foot_information_diagnostic.py")
INFO=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(INFO)
STAGE=Path(os.environ["NATIVE_CLONE_TEST_STAGE"])
BIN=STAGE/"native_attitude_clone_harness"
OLD=Path(os.environ["OLD_FOOT_HARNESS"])

def run(binary,op,path,values=(),diagnostics=False):
    env=os.environ.copy();env["LEGSA_FOOT_INFORMATION_DIAGNOSTICS"]="1" if diagnostics else "0"
    text=" ".join(format(float(v),".17g") for a in values for v in np.asarray(a).reshape(-1))
    p=subprocess.run([str(binary),op,str(path)],input=text,text=True,capture_output=True,env=env)
    with (STAGE/"FOOT_DIAGNOSTIC_INVOCATIONS.jsonl").open("a") as f:
        f.write(json.dumps(dict(binary=str(binary),op=op,path=str(path),diagnostics=diagnostics,returncode=p.returncode,stdout=p.stdout,stderr=p.stderr))+"\n")
    assert p.returncode==0,p.stderr
    return p.stdout,json.loads(p.stdout)

def measurement(p,h,r,w,diag=True):
    return run(BIN,"young_diag" if diag else "young",STAGE/"matrix",([24,3],p,np.zeros(24),h,r,[.001,-.002,.003],w))[1]

def rankone(lam):
    p=np.zeros((24,24));p[0,0]=p[1,1]=1
    h=np.zeros((3,24));h[0,0]=1
    return p,h,np.diag([1/lam,1,1]),np.r_[1.,1.,np.zeros(19)]

def test_01_rank2_passive_cost_native_grid_exact():
    p=np.eye(24);h=np.zeros((3,24));h[0,0]=h[1,1]=1;r=np.eye(3)*.25;w=np.ones(21)
    o=measurement(p,h,r,w);plain=measurement(p,h,r,w,False)
    for key in plain:assert o[key]==plain[key]
    d=INFO.diagnose(p,h,r,w)
    assert d["T"]==21 and d["J"]==8 and d["continuous_condition"]=="CONTINUOUS_NO_IMPROVEMENT"
    assert d["information_rank"]==2 and o["applied"]==0
    np.testing.assert_allclose(np.array(o["candidates"])[:,1],[x["score"] for x in d["grid"]],rtol=2e-11,atol=2e-12)
    assert o["T"]==d["T"] and o["J"]==d["J"]

def test_02_J_criterion_boundary_zero_and_convexity():
    for lam,kind in [(1.,"CONTINUOUS_NO_IMPROVEMENT"),(2.,"NUMERICAL_BOUNDARY_J_EQUAL_T"),(3.,"CONTINUOUS_IMPROVEMENT")]:
        d=INFO.diagnose(*rankone(lam));assert d["continuous_condition"]==kind
        def f(t):return 1/(1+t*(lam-1))+1/(1-t)
        q=1e-6
        assert (f(q)-f(0))/q==pytest.approx(2-lam,abs=6e-6)
        assert f(.3+q)-2*f(.3)+f(.3-q)>=-1e-14
    p,h,r,w=rankone(3);d=INFO.diagnose(p,h,r,np.zeros(21))
    assert d["J_over_T"] is None and d["continuous_condition"]=="ZERO_SCORE_NO_IMPROVEMENT"

def test_03_analytic_grid_miss_no_parameter_change():
    p,h,r,w=rankone(2.001);d=INFO.diagnose(p,h,r,w);native=measurement(p,h,r,w)
    a=np.sqrt(1.001);opt=(a-1)/(1.001+a)
    assert native["applied"]==0 and d["continuous_condition"]=="CONTINUOUS_IMPROVEMENT"
    assert d["continuous_bracket"][0]<=opt<=d["continuous_bracket"][1]
    assert d["continuous_omega"]==pytest.approx(opt,abs=2e-12)
    assert d["continuous_reduction"]>0 and opt<1/65

def test_04_singular_dense_clone_support_CI_oracle():
    rng=np.random.default_rng(61060724);base=np.eye(15)+.1*rng.normal(size=(15,15))
    factor=np.vstack([base,np.zeros((6,15)),.2*rng.normal(size=(3,15))]);p=factor@factor.T
    h=np.zeros((3,24));h[:2]=rng.normal(size=(2,24));h[2]=h[0]+h[1]
    r=np.array([[.5,.1,0],[.1,.7,.1],[0,.1,.9]]);w=np.r_[np.linspace(.5,1.5,15),np.zeros(6)]
    d=INFO.diagnose(p,h,r,w);native=measurement(p,h,r,w)
    assert d["rank_P_support"]==15 and d["rank_H"]==2 and d["information_rank"]==2
    U=factor.T@h.T@np.linalg.solve(r,h@factor);W=np.diag(np.r_[w,0,0,0])
    for index,e in enumerate(INFO.EPSILON):
        om=e/(1+e);B=factor@np.linalg.solve((1-om)*np.eye(15)+om*U,factor.T)
        expected=np.trace(W@B)
        assert d["grid"][index]["score"]==pytest.approx(expected,rel=2e-11,abs=2e-12)
        assert native["candidates"][index][1]==pytest.approx(expected,rel=2e-11,abs=2e-12)
    assert abs(d["J_spectral_error"])<1e-9 and abs(d["T_spectral_error"])<1e-11

def test_05_unknown_cross_cancellation_and_full_reset():
    p,h,_,w=rankone(1);r=np.eye(3)*2;C=-p@h.T
    joint=np.block([[p,C],[C.T,r]])
    assert np.linalg.eigvalsh(joint).min()>-2e-12
    d=INFO.diagnose(p,h,r,w);assert d["continuous_condition"]=="CONTINUOUS_NO_IMPROVEMENT"
    rng=np.random.default_rng(711);G=np.eye(24)+.01*rng.normal(size=(24,24))
    for e in INFO.EPSILON:
        K=np.linalg.solve(h@p@h.T+r/e,h@p).T;F=np.eye(24)-K@h
        actual=F@p@F.T+K@r@K.T-F@C@K.T-K@C.T@F.T
        upper=(1+e)*(F@p@F.T+K@r@K.T/e)
        assert np.linalg.eigvalsh(actual-p).min()>-2e-12
        assert np.linalg.eigvalsh(G@(upper-actual)@G.T).min()>-2e-12
    assert np.linalg.eigvalsh(np.array([[.2,.1],[.1,0.]])).min()<0

def test_06_native_on_off_identity_and_passive_dump(tmp_path):
    a,plain=run(BIN,"frozen",tmp_path/"off")
    b,logged=run(BIN,"frozen",tmp_path/"on",diagnostics=True)
    assert a==b
    for name in ["ATTITUDE_CLONE_EVENTS.csv","ATTITUDE_CLONE_FIXED_WEIGHTS.csv","RUN_MANIFEST.json"]:
        assert (tmp_path/"off"/name).read_bytes()==(tmp_path/"on"/name).read_bytes()
    assert not (tmp_path/"off"/"FOOT_INFORMATION_INPUTS.jsonl").exists()
    rows=[json.loads(x) for x in (tmp_path/"on"/"FOOT_INFORMATION_INPUTS.jsonl").read_text().splitlines()]
    assert len(rows)==1
    x=rows[0];d=INFO.diagnose(x["P"],x["H"],x["R"],x["weights"],x["candidates"])
    assert x["T"]==pytest.approx(d["T"],rel=2e-11,abs=2e-12)
    assert x["J"]==pytest.approx(d["J"],rel=2e-11,abs=2e-12)
    assert max(abs(a["native_score_error"]) for a in d["grid"])<2e-12

def test_07_readout_roundtrip_and_domains(tmp_path):
    run(BIN,"frozen",tmp_path/"native",diagnostics=True)
    source=tmp_path/"native/FOOT_INFORMATION_INPUTS.jsonl";out=tmp_path/"out"
    receipt=INFO.readout(source,out);assert receipt["events"]==1 and receipt["reference_reads"]==0
    row=json.loads((out/"EVENT_DIAGNOSTICS.jsonl").read_text());assert row["diagnostic_only_no_state_update"]
    with pytest.raises(ValueError,match="new output"):INFO.readout(source,out)
    p,h,r,w=rankone(1)
    with pytest.raises(ValueError,match="positive definite"):INFO.diagnose(p,h,np.zeros((3,3)),w)
    bad=p.copy();bad[0,0]=-1
    with pytest.raises(ValueError,match="not PSD"):INFO.diagnose(bad,h,r,w)
    with pytest.raises(ValueError,match="weights"):INFO.diagnose(p,h,r,-w)

def test_08_old_sealed_harness_exact_engine_outputs(tmp_path):
    for op in ["frozen","large","invalid","timing","boundaries","off"]:
        old,_=run(OLD,op,tmp_path/(op+"_old"));new,_=run(BIN,op,tmp_path/(op+"_new"))
        assert old==new,op


def test_09_tiny_positive_variance_high_weight_no_false_gain():
    p=np.zeros((24,24));p[0,0]=1.;p[1,1]=1e-16
    h=np.zeros((3,24));r=np.eye(3);w=np.r_[1.,1e16,np.zeros(19)]
    d=INFO.diagnose(p,h,r,w)
    assert d["T"]==2 and d["J"]==0 and d["continuous_condition"]=="CONTINUOUS_NO_IMPROVEMENT"
    assert d["continuous_score"]==2 and d["continuous_reduction"]==0
    assert d["rank_P_support"]==2 and d["discarded_positive_P_eigenvalues"]==[]
    assert d["spectral_full_model_qualified"] and not d["continuous_beats_original_skip_tie"]
    assert d["fixed_grid_zero_noise_cap_below_first_cost"] is None

def test_10_coordinate_units_and_native_action_tamper(tmp_path):
    p,h,r,w=rankone(3.);base=INFO.diagnose(p,h,r,w)
    scales=np.ones(24);scales[0]=1e-8;scales[1]=1e6
    transformed=INFO.diagnose(p*np.outer(scales,scales),h/scales,r,w/scales[:21]**2)
    for key in ["T","J","continuous_score","continuous_omega"]:
        assert transformed[key]==pytest.approx(base[key],rel=2e-11,abs=2e-12)
    assert transformed["continuous_condition"]==base["continuous_condition"]
    run(BIN,"frozen",tmp_path/"native",diagnostics=True)
    original=json.loads((tmp_path/"native/FOOT_INFORMATION_INPUTS.jsonl").read_text())
    result=INFO.diagnose(original["P"],original["H"],original["R"],original["weights"],original["candidates"])
    assert INFO.verify_native(original,result)["full_P_grid_action_verified"]
    broken=json.loads(json.dumps(original));broken["candidates"][0]["selected_at_step"]=not broken["candidates"][0]["selected_at_step"]
    with pytest.raises(ValueError,match="candidate action"):INFO.verify_native(broken,result)
    broken=json.loads(json.dumps(original));broken["selected_epsilon"]=4.
    with pytest.raises(ValueError,match="final action"):INFO.verify_native(broken,result)
