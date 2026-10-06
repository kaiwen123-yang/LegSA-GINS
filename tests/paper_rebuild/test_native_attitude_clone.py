"""Exactly sixteen synthetic native-clone qualification cases; no real inputs."""
import csv,json,os,subprocess,time
from pathlib import Path
import numpy as np
import pytest
from scipy.spatial.transform import Rotation
STAGE=Path(os.environ["NATIVE_CLONE_TEST_STAGE"])
BIN=STAGE/"native_attitude_clone_harness"
RNG=np.random.default_rng(61060724)

def text(*args):
    return " ".join(format(float(x),".17g") for a in args for x in np.asarray(a).reshape(-1))
def call(op,*args,path=None,fail=False):
    command=[str(BIN),op,str(path or STAGE/("diag_"+op))]
    p=subprocess.run(command,input=text(*args),text=True,capture_output=True)
    with (STAGE/"HARNESS_INVOCATIONS.jsonl").open("a") as f:
        f.write(json.dumps(dict(op=op,command=command,returncode=p.returncode,stdout=p.stdout,stderr=p.stderr))+"\n")
    if fail:
        assert p.returncode!=0,p.stdout
        return p.stderr
    assert p.returncode==0,p.stderr
    return json.loads(p.stdout)
def array(o,key):return np.array(o[key],float)
def exp(a):return Rotation.from_rotvec(a).as_matrix()
def skew(v):return np.array([[0,-v[2],v[1]],[v[2],0,-v[0]],[-v[1],v[0],0.]])
def ned(q):
    a,b,_=q;s,c=np.sin(a),np.cos(a);sl,cl=np.sin(b),np.cos(b)
    return np.array([[-s*cl,-sl,-c*cl],[-s*sl,cl,-c*sl],[c,0,-s]])
def dri(q):
    e=0.0066943799901413156;a=6378137.;t=1-e*np.sin(q[0])**2
    rn=a/np.sqrt(t);rm=a*(1-e)/t**1.5
    return np.diag([1/(rm+q[2]),1/((rn+q[2])*np.cos(q[0])),-1.])
def geometry():
    d0=np.array([.4,-.2,.1]);d1=np.array([.42,-.13,.16])
    return d0,d1,exp([.3,.2,-.1]),exp([-.2,.1,.35]),np.array([.6,1.3,35.]),np.eye(6)*.001
def model(g=None):return call("model",*(g or geometry()))
def native(name):return call(name)
def latent(n,seed=71):
    r=np.random.default_rng(seed);f=.03*r.normal(size=(n,n))+.2*np.eye(n)
    return f,f@f.T,np.linspace(-.015,.015,n)
def qr_posterior(f,m,h,z,r):
    l=np.linalg.cholesky(r);a=np.vstack([np.eye(f.shape[1]),np.linalg.solve(l,h@f)])
    b=np.r_[np.zeros(f.shape[1]),np.linalg.solve(l,z-h@m)]
    q,u=np.linalg.qr(a,mode="reduced");v=np.linalg.solve(u,np.eye(len(u)))
    return m+f@np.linalg.solve(u,q.T@b),f@v@v.T@f.T
def measurement(op,p,m,h,r,z,*tail):return call(op,[len(m),len(z)],p,m,h,r,z,*tail)

def test_01_deterministic_clone_latent():
    f,p,m=latent(21);j=np.zeros((3,21));j[:,6:9]=exp([.2,-.3,.1]);j[:,:3]=np.diag([1e-7,2e-7,0])
    o=call("augment",p,m,j);lf=np.vstack([f,j@f])
    np.testing.assert_allclose(o["P"],lf@lf.T,rtol=2e-14,atol=2e-17)
    np.testing.assert_allclose(o["mean"],np.r_[m,j@m],atol=1e-17)
    a=np.c_[-j,np.eye(3)]
    np.testing.assert_allclose(a@array(o,"P")@a.T,0,atol=5e-17)
    assert np.linalg.matrix_rank(o["P"])==21

def test_02_native_current_only_prediction():
    phi=np.eye(21);phi[:3,3:6]=.2*np.eye(3);phi[6:9,9:12]=-.2*np.eye(3)
    q=np.zeros((21,21));q[:15,:15]=np.diag(np.linspace(1e-7,4e-7,15))
    o=call("propagate",phi,q);p=array(o,"before")
    a=np.eye(24);a[:21,:21]=phi;n=np.zeros((24,24));n[:21,:21]=q
    np.testing.assert_allclose(o["P"],a@p@a.T+n,atol=2e-16)
    np.testing.assert_array_equal(array(o,"P")[21:,21:],p[21:,21:])

def test_03_ordinary_full_gain_latent_QR():
    f,p,m=latent(24);h=np.zeros((3,24));h[:,:3]=np.eye(3);h[:,6:9]=skew([.4,-.2,.1])
    r=np.diag([.002,.003,.004]);z=np.array([.05,-.02,.03])
    o=measurement("ordinary",p,m,h,r,z);mm,pp=qr_posterior(f,m,h,z,r)
    np.testing.assert_allclose(o["mean"],mm,atol=2e-15)
    np.testing.assert_allclose(o["P"],pp,atol=2e-16)
    assert np.linalg.norm(array(o,"mean")[21:]-m[21:])>1e-5
    assert np.linalg.norm(array(o,"P")[:21,21:]-p[:21,21:])>1e-4

def test_04_complete_reset_retraction_FD():
    f,p,m=latent(24);m[6:9]=[.25,-.17,.35];m[21:]=[-.2,.1,.3];gp=np.diag([1.00003,.99997,1])
    o=call("reset",[24],p,m,gp)
    def new(e):
        y=e.copy();y[:3]=gp@e[:3]
        for k in (6,21):y[k:k+3]=(Rotation.from_rotvec(m[k:k+3]+e[k:k+3])*Rotation.from_rotvec(-m[k:k+3])).as_rotvec()
        return y
    h=1e-7;g=np.column_stack([(new(h*d)-new(-h*d))/(2*h) for d in np.eye(24)])
    np.testing.assert_allclose(o["P"],g@p@g.T,atol=1e-10,rtol=1e-8)
    np.testing.assert_array_equal(o["mean"],np.zeros(24))
    assert np.linalg.norm(array(o,"P")[:21,21:]-p[:21,21:])>1e-4

def test_05_retire_marginal_not_conditioning():
    o=native("retire");p=array(o,"before")
    np.testing.assert_array_equal(o["P"],p[:21,:21])
    conditional=p[:21,:21]-p[:21,21:]@np.linalg.solve(p[21:,21:],p[21:,:21])
    assert np.linalg.norm(array(o,"P")-conditional)>.01
    assert o["terminal"]==1 and o["active"]==0 and o["time"]==1.01

def test_06_pair_nonzero_gauge_and_feedback_FD():
    g=geometry();d0,d1,c0,cbn,q,s=g;o=model(g);e=ned(q)
    def residual(a,b):return d0-(exp(b)@c0).T@e@(exp(a)@cbn)@d1
    step=1e-7;dc=np.column_stack([(residual(step*u,np.zeros(3))-residual(-step*u,np.zeros(3)))/(2*step) for u in np.eye(3)])
    dk=np.column_stack([(residual(np.zeros(3),step*u)-residual(np.zeros(3),-step*u))/(2*step) for u in np.eye(3)])
    h=array(o,"H");np.testing.assert_allclose(h[:,6:9],-dc,atol=1e-9)
    np.testing.assert_allclose(h[:,21:],-dk,atol=1e-9)
    gauge=np.zeros((24,3));gauge[6:9]=e.T;gauge[21:]=np.eye(3)
    np.testing.assert_allclose(h@gauge,0,atol=2e-16)
    assert np.linalg.norm(o["z"])>.01 and np.linalg.matrix_rank(h,tol=1e-12)==2

def test_07_NED_connection_augmentation_FD():
    g=geometry();d0,d1,c0,cbn,q,s=g;o=model(g);e=ned(q);D=dri(q);h=1e-2
    k=np.column_stack([Rotation.from_matrix(ned(q+D@(h*u))@ned(q-D@(h*u)).T).as_rotvec()/(2*h) for u in np.eye(3)])
    np.testing.assert_allclose(o["K"],k,atol=2e-14,rtol=1e-7)
    j=array(o,"J");np.testing.assert_allclose(j[:,:3],-k,atol=2e-14)
    np.testing.assert_allclose(j[:,6:9],e,atol=1e-16)
    f=np.column_stack([(d0-c0.T@ned(q-D@(h*u))@cbn@d1 - (d0-c0.T@ned(q+D@(h*u))@cbn@d1))/(2*h) for u in np.eye(3)])
    np.testing.assert_allclose(array(o,"H")[:,:3],-f,atol=1e-14,rtol=1e-6)

def test_08_full_endpoint_covariance_frame_domains():
    d0,d1,c0,cbn,q,_=geometry();a=np.random.default_rng(82).normal(size=(6,6))*.01;s=a@a.T
    frame=exp([.1,-.2,.3]);t=np.kron(np.eye(2),frame)
    o=model((frame@d0,frame@d1,c0,cbn,q,t@s@t.T))
    l=np.c_[np.eye(3),-c0.T@ned(q)@cbn]
    np.testing.assert_allclose(o["R"],l@t@s@t.T@l.T,atol=4e-19)
    assert np.linalg.norm(l@(t@s@t.T-np.diag(np.diag(t@s@t.T)))@l.T)>1e-5
    bad=np.eye(6);bad[0,0]=-1
    assert "NOT_PSD" in call("model",d0,d1,c0,cbn,q,bad,fail=True)
    badrot=c0.copy();badrot[0,0]+=.1
    assert "SO3" in call("model",d0,d1,badrot,cbn,q,s,fail=True)

def test_09_Young_bound_actual_nonzero_cross():
    p=np.eye(24);m=np.zeros(24);h=np.zeros((3,24));h[:,6:9]=np.eye(3);r=np.eye(3)*.000082
    o=measurement("young",p,m,h,r,[.01,-.02,.03],np.ones(21))
    assert o["applied"]==1
    eps=o["epsilon"];k=p@h.T@np.linalg.inv(h@p@h.T+r/eps);a=np.eye(24)-k@h
    # Known synthetic measurement noise D*x+.001*u shares x; signs both covered.
    for sign in (-1,1):
        d=sign*.009*h
        actual=(a-k@d)@(a-k@d).T+1e-6*k@k.T
        assert np.linalg.eigvalsh(array(o,"P")-actual).min()>-2e-12
    assert o["score"]<o["prior"]

def test_10_fixed_weights_SKIP_not_inflation():
    p=np.eye(24);m=np.linspace(-.01,.01,24);h=np.zeros((3,24));r=np.eye(3)
    a=measurement("young",p,m,h,r,[1,2,3],np.ones(21))
    assert a["applied"]==0 and a["epsilon"]==0
    np.testing.assert_array_equal(a["P"],p);np.testing.assert_array_equal(a["mean"],m)
    h[:,6:9]=np.eye(3);r*=1e-6
    a=measurement("young",p,m,h,r,[0,0,0],np.ones(21))
    b=measurement("young",p,m,h,r,[20,-10,30],np.ones(21))
    assert a["epsilon"]==b["epsilon"]
    np.testing.assert_array_equal(a["P"],b["P"])
    diag=np.repeat([1.,2.,3.,4.,5.,0.,0.],3)
    w=call("weights",np.diag(diag))["weights"]
    np.testing.assert_allclose(w,np.repeat([1.,.5,1/3,.25,.2,0,0],3),atol=0)

def test_11_native_frozen_scale():
    o=native("frozen");p=array(o,"P")
    np.testing.assert_array_equal(p[15:21],np.zeros((6,21)))
    np.testing.assert_array_equal(p[:,15:21],np.zeros((21,6)))
    np.testing.assert_array_equal(o["scale"],np.zeros(3))
    assert o["joint"]==1 and o["resets"]>=1

def test_12_large_innovation_failclosed():
    o=native("large")
    np.testing.assert_array_equal(o["NULL_CLONEP"],o["PAIR_YOUNGP"])
    np.testing.assert_array_equal(o["NULL_CLONEnav"],o["PAIR_YOUNGnav"])
    for m in ("NULL_CLONE","PAIR_YOUNG"):
        assert o[m+"innovation_reject"]==1 and o[m+"updates"]==0 and o[m+"active"]==0
        rows=list(csv.DictReader((STAGE/"diag_large"/m/"ATTITUDE_CLONE_EVENTS.csv").open()))
        reject=[r for r in rows if r["action"]=="WORKING_SAFE_INNOVATION_REJECT"]
        assert len(reject)==1 and float(reject[0]["safe_innovation"])>16.26623619623813
    p=np.eye(24);h=np.zeros((3,24));h[:,6:9]=np.eye(3);r=np.eye(3);z=np.array([2,3,4.]);m=np.zeros(24);m[6:9]=[1,1,1]
    a=measurement("safe",p,m,h,r,z)
    assert a["statistic"]==pytest.approx((z-h@m)@np.linalg.solve(2*(h@p@h.T+r),z-h@m))

def test_13_exact_time_GNSS_before_clone_and_identity():
    o=native("timing");p=array(o,"without");q=np.array(o["blh"]);g=list(geometry());g[4]=q;j=array(model(tuple(g)),"J")
    a=np.vstack([np.eye(21),j])
    np.testing.assert_allclose(o["with"],a@p@a.T,atol=2e-16)
    assert o["atstart_gnss_updates"]==1 and o["atstart_starts"]==1 and o["atstart_time"]==1.01
    assert o["final_rejected"]==1 and o["final_active"]==0
    rows=list(csv.DictReader((STAGE/"diag_timing"/"ATTITUDE_CLONE_EVENTS.csv").open()))
    assert rows[-1]["action"]=="ENDPOINT_ALREADY_CONSUMED"
    assert all(float(r["event_time_s"])==float(r["state_time_s"]) for r in rows)
    manifest=json.loads((STAGE/"diag_timing"/"RUN_MANIFEST.json").read_text())
    assert manifest["attitude_clone_source_rows"]==3 and manifest["attitude_clone_consumed_event_rows"]==3

def test_14_invalid_END_RETIRE_no_aux():
    o=native("invalid")
    np.testing.assert_array_equal(o["NULL_CLONEP"],o["PAIR_YOUNGP"])
    np.testing.assert_array_equal(o["NULL_CLONEnav"],o["PAIR_YOUNGnav"])
    for m in ("NULL_CLONE","PAIR_YOUNG"):
        assert o[m+"events"]==4 and o[m+"rejected"]==1 and o[m+"retires"]==1
        assert o[m+"active"]==0
        assert all(o[m+k]==0 for k in ("gnss_updates","RD","RP","HV","SA"))

def csvfile(path,rows):
    fields="event_time_s available_time_s event_type clone_id source_time_s endpoint_id foot_i foot_j episode_i episode_j d_body_frd_x_m d_body_frd_y_m d_body_frd_z_m reason".split()+[f"sigma_{i}{j}" for i in range(6) for j in range(6)]
    with path.open("w") as f:
        w=csv.DictWriter(f,fields,lineterminator="\n");w.writeheader();w.writerows(rows)
def test_15_support_boundaries_blank_timer_source(tmp_path):
    o=native("boundaries")
    assert o["source"]==4 and o["initial"]==1 and o["events"]==1 and o["terminal"]==1 and o["outside"]==1
    assert o["time"]==1.2 and o["active"]==0 and len(o["P"])==21
    p=tmp_path/"retire.csv";csvfile(p,[dict(event_time_s=2,available_time_s=2,event_type="RETIRE",clone_id="c",reason="timer")])
    a=call("read",path=p);assert a["rows"]==1 and a["retire_no_source"]==1

def test_16_default_off_and_malformed_contracts(tmp_path):
    o=native("off");assert o["default_off"]==1 and o["off_set_rejected"]==1 and o["shape"]==21
    assert not (STAGE/"diag_off"/"ATTITUDE_CLONE_EVENTS.csv").exists()
    p=tmp_path/"bad.csv";base=dict(event_time_s=2,available_time_s=2,event_type="RETIRE",clone_id="c",reason="timer")
    csvfile(p,[base,{**base,"event_time_s":1,"available_time_s":1}]);assert "TIME_ORDER" in call("read",path=p,fail=True)
    csvfile(p,[{**base,"source_time_s":2}]);assert "NO_MEASUREMENT_SOURCE" in call("read",path=p,fail=True)
    csvfile(p,[{**base,"available_time_s":1.9}]);assert "REPLAY" in call("read",path=p,fail=True)
    cfg=tmp_path/"bad.cfg";cfg.write_text("runtime_contract: research_experiment\nattitude_clone_mode: NULL_CLONE\nfoot_pair_body_frd_to_engine_body: [1,0,0,0,1,0,0,0,1] garbage\n")
    assert "FRAME_TRAILING" in call("config",path=cfg,fail=True)
