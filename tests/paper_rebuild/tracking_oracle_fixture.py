"""Pure NumPy SD-to-DD truth fixture, independent of carrier implementation.

Originally constructed for an independent tracking review. Generates arrays in
memory only; no scratch files, environment variables, production imports or
integer-search calls are required.
"""
import numpy as np

L = .35
WAVE = 299792458. / 1575.42e6


def normalize(v):
    v = np.asarray(v, float)
    return v / np.linalg.norm(v, axis=-1, keepdims=True)


def rotation_z(angle):
    c, s = np.cos(angle), np.sin(angle)
    return np.array([[c, -s, 0.], [s, c, 0.], [0., 0., 1.]])


def observations(units, baseline, sd_integers, code_sigma, phase_sigma):
    # Independently construct receiver single differences, including common
    # receiver clocks, BEFORE satellite-minus-pivot differencing.
    size = len(units)
    d = np.column_stack((-np.ones(size-1), np.eye(size-1)))
    sd_code = -units @ baseline + 15.
    sd_phase = -units @ baseline + WAVE * sd_integers + 39.
    y = np.r_[d @ sd_code, d @ sd_phase]
    b = np.vstack((-d @ units, -d @ units))
    a = np.vstack((np.zeros((size-1, size-1)), WAVE*np.eye(size-1)))
    sdq = np.diag(np.r_[np.full(size, code_sigma**2),
                        np.full(size, phase_sigma**2)])
    transform = np.block([[d, np.zeros_like(d)], [np.zeros_like(d), d]])
    return y, a, b, transform @ sdq @ transform.T, d @ sd_integers


def gls(y, a, b, q, integers):
    # Independent dense GLS via Cholesky whitening. Never calls admission,
    # faults, sphere solver, integer search, or a model builder.
    lower = np.linalg.cholesky(q)
    design = np.linalg.solve(lower, b)
    target = np.linalg.solve(lower, y-a @ integers)
    estimate = np.linalg.lstsq(design, target, rcond=None)[0]
    residual = target-design @ estimate
    covariance = np.linalg.solve(design.T @ design, np.eye(3))
    return estimate, float(residual @ residual), covariance


def generate_oracle_payload():
    units = normalize([[.2,.3,.9], [.8,.1,.5], [-.4,.6,.7],
                       [.1,-.8,.6], [-.8,-.1,.5], [.5,.6,.3]])
    sd_integers = np.array([3,9,-2,12,1,7])
    times = np.arange(10)*.2
    records=[]; payload={}
    for k,t in enumerate(times):
        # True moving body baseline; each epoch needs its own nuisance b_k.
        angle = .6*t
        baseline = L*np.array([np.cos(angle)*np.cos(.2*np.sin(t)),
                               np.sin(angle)*np.cos(.2*np.sin(t)), np.sin(.2*np.sin(t))])
        u = units @ rotation_z(.0002*t).T
        y,a,b,q,n = observations(u,baseline,sd_integers,1.,.002)
        fit,cost,cov = gls(y,a,b,q,n)
        wrong=n.copy();wrong[0]+=1
        wrong_fit,wrong_cost,_=gls(y,a,b,q,wrong)
        records.append({"time_s":float(t),"baseline_truth_m":baseline.tolist(),
                        "fixed_true_N_error_m":float(np.linalg.norm(fit-baseline)),
                        "fixed_true_N_cost":cost,"wrong_target_plus1_cost":wrong_cost})
        for name,value in (("y",y),("A",a),("B",b),("Q",q),("N_true",n),
                           ("b_true",baseline),("Cb",cov)):
            payload[f"moving_{k:02d}_{name}"]=value
    assert max(r["fixed_true_N_error_m"] for r in records)<1e-10
    assert min(r["wrong_target_plus1_cost"] for r in records)>100

    # Deliberate geometric ambiguity: B*d = lambda*deltaN and both b and
    # b-d have the same length. A wrong N may fit phase exactly under
    # another physical orientation; weak code can leave a tiny GLS cost.
    displacement=.3
    delta=np.array([1,0,1,0])
    x=np.r_[.7, .7-WAVE*delta/displacement]
    phi=np.array([.2, 1.2, 2.3, 3.4, 4.7])
    yz=np.sqrt(1-x*x)
    ambiguous_units=np.column_stack((x,yz*np.cos(phi),yz*np.sin(phi)))
    chord=np.array([displacement,0.,0.])
    ambiguous=[]
    for k,t in enumerate(times):
        baseline=np.array([displacement/2, np.sqrt(L*L-displacement**2/4)*np.cos(.6*t),
                            np.sqrt(L*L-displacement**2/4)*np.sin(.6*t)])
        y,a,b,q,n=observations(ambiguous_units,baseline,np.array([2,7,-3,1,9]),5.,.002)
        wrong=n+delta
        alternate=baseline-chord
        phase=len(delta)
        phase_identity=float(np.max(np.abs(a[phase:]@n+b[phase:]@baseline
                                            -a[phase:]@wrong-b[phase:]@alternate)))
        fit,cost,cov=gls(y,a,b,q,wrong)
        angle=np.degrees(np.arccos(np.clip(baseline@alternate/(L*L),-1,1)))
        ambiguous.append({"time_s":float(t),"wrong_N_cost":cost,
                          "wrong_N_unconstrained_length_error_m":abs(float(np.linalg.norm(fit))-L),
                          "true_and_alternative_phase_difference_m":phase_identity,
                          "alternative_orientation_difference_deg":float(angle)})
        assert phase_identity<1e-13
        assert abs(np.linalg.norm(alternate)-L)<1e-14
        assert cost<.01
        for name,value in (("y",y),("A",a),("B",b),("Q",q),("N_true",n),
                           ("N_wrong",wrong),("b_true",baseline),("b_alternative",alternate)):
            payload[f"alias_{k:02d}_{name}"]=value
    return payload
