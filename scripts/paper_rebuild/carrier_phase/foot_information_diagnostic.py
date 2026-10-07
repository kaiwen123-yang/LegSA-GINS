"""Read passive FOOT_INFORMATION_INPUTS only; never execute navigation or change state."""
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path
import numpy as np
EPSILON = (1/64, 1/16, 1/4, 1., 4.)
MACHINE = np.finfo(float).eps

def symmetric(a, name):
    a=np.asarray(a,dtype=float)
    if a.ndim!=2 or a.shape[0]!=a.shape[1] or not np.isfinite(a).all():
        raise ValueError(name+" invalid shape/nonfinite")
    tol=64*MACHINE*len(a)*max(float(np.abs(a).max()),np.finfo(float).tiny)
    if np.max(np.abs(a-a.T))>tol: raise ValueError(name+" nonsymmetric")
    vals,vecs=np.linalg.eigh((a+a.T)*.5)
    if vals[0]<-tol: raise ValueError(name+" not PSD")
    return (a+a.T)*.5,vals,vecs,tol

def diagnose(P,H,R,weights,candidates=None):
    P,pv,pu,ptol=symmetric(np.asarray(P).reshape(24,24),"P")
    H=np.asarray(H,float).reshape(3,24);R=np.asarray(R,float).reshape(3,3)
    R,rv,_,rtol=symmetric(R,"R")
    w=np.asarray(weights,float)
    if w.shape!=(21,) or not np.isfinite(w).all() or np.any(w<0) or not np.isfinite(H).all():
        raise ValueError("invalid H/weights")
    if rv[0]<=0: raise ValueError("R must be positive definite for J/continuous criterion; no jitter")
    W=np.diag(np.r_[w,0.,0.,0.]);pht=P@H.T;A=H@pht;D=pht.T@W@pht
    T=float(np.trace(W@P));J=float(np.trace(np.linalg.solve(R,D)))
    direct_margin=128*MACHINE*24*max(abs(T),abs(J),np.finfo(float).tiny)
    # Unit-normalized factorization retains every positive mode, including a tiny
    # variance with a large score weight. Rank thresholds never remove score mass.
    diagonal=np.diag(P)
    if np.any(diagonal<0):raise ValueError("P negative diagonal")
    nonzero=diagonal>0
    if np.any(P[~nonzero]!=0):raise ValueError("P zero variance has nonzero cross")
    if np.any(nonzero):
        scales=np.sqrt(diagonal[nonzero])
        correlation=P[np.ix_(nonzero,nonzero)]/np.outer(scales,scales)
        correlation,cv,cu,ctol=symmetric(correlation,"P normalized support")
        active=cv>0
        L=np.zeros((24,int(active.sum())))
        L[nonzero]=(cu[:,active]*np.sqrt(cv[active]))*scales[:,None]
        numerical_rank=int((cv>ctol).sum())
    else:
        cv=np.empty(0);ctol=0.;L=np.empty((24,0));numerical_rank=0
    M=L.T@W@L; hl=H@L
    U=hl.T@np.linalg.solve(R,hl)
    if U.size:
        U,lam,lu,utol=symmetric(U,"support information")
        lam=np.maximum(lam,0.)
        m=np.diag(lu.T@M@lu).copy()
        mtol=128*MACHINE*24*max(T,np.finfo(float).tiny)
        if np.min(m)<-mtol: raise ValueError("negative spectral score weight")
        m=np.maximum(m,0.)
    else:
        lam=np.empty(0);m=np.empty(0);utol=0.
    info=lam>utol
    J_spectrum=float(m@lam);T_spectrum=float(m.sum())
    m0=float(m[lam==0].sum());gmax=float(m[lam>0].sum())
    def objective(omega):
        return float(np.sum(m/(1+omega*(lam-1))))
    def full_score(omega):
        if omega==0:return T
        epsilon=omega/(1-omega)
        gain=np.linalg.solve(A+R/epsilon,pht.T).T;F=np.eye(24)-gain@H
        bound=(1+epsilon)*(F@P@F.T+gain@R@gain.T/epsilon)
        return float(np.trace(W@bound))
    def derivative(omega):
        den=1+omega*(lam-1)
        return float(np.sum(m*(1-lam)/den**2))
    grid=[]
    for index,e in enumerate(EPSILON):
        K=np.linalg.solve(A+R/e,pht.T).T;F=np.eye(24)-K@H
        B=(1+e)*(F@P@F.T+K@R@K.T/e)
        f=float(np.trace(W@B));G=float(np.trace(np.linalg.solve(A+R/e,D)))
        row=dict(epsilon=e,score=f,reduction=T-f,G=G,improvement_threshold=e*T/(1+e),completed_square_score=(1+e)*(T-G))
        if candidates is not None:
            old=candidates[index]
            if abs(old["epsilon"]-e)>0:raise ValueError("changed epsilon grid")
            row["native_score"]=float(old["score"])
            row["native_score_error"]=float(old["score"])-f
            row["native_tie"]=float(old["tie"])
        grid.append(row)
    if T==0:
        condition="ZERO_SCORE_NO_IMPROVEMENT";lo=hi=omega=0.;steps=0
    elif J<T-direct_margin:
        condition="CONTINUOUS_NO_IMPROVEMENT";lo=hi=omega=0.;steps=0
    elif J<=T+direct_margin:
        condition="NUMERICAL_BOUNDARY_J_EQUAL_T";lo=hi=omega=0.;steps=0
    else:
        condition="CONTINUOUS_IMPROVEMENT";lo=0.;hi=1-2**-40;steps=0
        if derivative(0)>=0:
            condition="SUPPORT_TRUNCATION_OR_ROUNDOFF_UNRESOLVED";hi=omega=0.
        elif derivative(hi)<=0:
            condition="IMPROVEMENT_MINIMUM_NEAR_OPEN_BOUNDARY";omega=hi
        else:
            for steps in range(1,81):
                middle=(lo+hi)*.5
                if derivative(middle)<0:lo=middle
                else:hi=middle
                if hi-lo<=2e-14:break
            omega=(lo+hi)*.5
    # Report the untruncated full-P objective, never a rank-truncated objective.
    score=full_score(omega);spectral_score=objective(omega)
    consistency_limit=2e-12+2e-11*max(abs(score),1.)
    T_consistency_limit=2e-12+2e-11*max(abs(T),1.)
    J_consistency_limit=2e-12+2e-11*max(abs(J),1.)
    qualified=bool(abs(T_spectrum-T)<=T_consistency_limit and abs(J_spectrum-J)<=J_consistency_limit
               and abs(spectral_score-score)<=consistency_limit and np.isfinite(score))
    if not qualified:
        condition="SPECTRAL_FULL_MODEL_MISMATCH_UNRESOLVED"
        omega=score=lo=hi=None
    return dict(T=T,J=J,J_over_T=(J/T if T>0 else None),J_minus_T=J-T,criterion_margin=direct_margin,
        continuous_condition=condition,continuous_omega=omega,continuous_bracket=[lo,hi],continuous_steps=steps,
        continuous_score=score,continuous_reduction=(T-score if score is not None else None),
        continuous_derivative_bracket=([derivative(lo),derivative(hi)] if lo is not None else None),
        spectral_full_model_qualified=qualified,spectral_objective_at_proposed_weight=spectral_score,
        spectral_consistency_limit=consistency_limit,T_spectral_consistency_limit=T_consistency_limit,J_spectral_consistency_limit=J_consistency_limit,
        continuous_beats_original_skip_tie=(bool(score<T-64*MACHINE*max(1.,abs(T),abs(score))) if score is not None else None),
        diagnostic_only_no_state_update=True,rank_H=int(np.linalg.matrix_rank(H)),rank_P_support=numerical_rank,
        P_factor_columns=L.shape[1],P_normalized_eigenvalues=cv.tolist(),P_normalized_rank_tolerance=ctol,
        P_rank_tolerance=ptol,discarded_positive_P_eigenvalues=[],
        eigenvalues_P=pv.tolist(),information_eigenvalues=lam.tolist(),information_rank=int(info.sum()),
        information_rank_tolerance=utol,spectral_score_weights=m.tolist(),m0_numerical=m0,Gmax_numerical=gmax,
        Gmax=None,fixed_grid_zero_noise_cap_below_first_cost=None,
        zero_noise_cap_reason="Numerical rank/spectrum are reported only; no rank-certification bound is asserted",T_spectral_error=T_spectrum-T,
        J_spectral_error=J_spectrum-J,grid=grid)

def verify_native(record,result):
    if len(record["candidates"])!=5:raise ValueError("native five-candidate grid required")
    if abs(record["T"]-result["T"])>2e-12+2e-11*max(abs(result["T"]),1.):raise ValueError("native T mismatch")
    if record["J"] is not None and (not np.isfinite(record["J"]) or abs(record["J"]-result["J"])>2e-12+2e-11*max(abs(result["J"]),1.)):
        raise ValueError("native J mismatch")
    native_best=float(record["T"]);native_epsilon=0.;recomputed_best=result["T"];recomputed_epsilon=0.
    for old,new in zip(record["candidates"],result["grid"]):
        tolerance=2e-12+2e-11*max(abs(old["score"]),abs(new["score"]),1.)
        if abs(old["score"]-new["score"])>tolerance:raise ValueError("native/full-P candidate score mismatch")
        if old["comparison_score"]!=native_best:raise ValueError("native comparison order mismatch")
        tie=64*MACHINE*max(1.,abs(old["score"]),abs(native_best))
        if abs(old["tie"]-tie)>2e-15*max(tie,np.finfo(float).tiny):raise ValueError("native tie mismatch")
        chosen=old["score"]<native_best-tie
        if chosen!=old["selected_at_step"]:raise ValueError("native candidate action mismatch")
        if chosen:native_best=old["score"];native_epsilon=old["epsilon"]
        tie2=64*MACHINE*max(1.,abs(new["score"]),abs(recomputed_best))
        if new["score"]<recomputed_best-tie2:recomputed_best=new["score"];recomputed_epsilon=new["epsilon"]
    if native_epsilon!=record["selected_epsilon"] or bool(native_epsilon)!=record["applied"]:
        raise ValueError("native final action mismatch")
    if recomputed_epsilon!=native_epsilon:raise ValueError("independent full-P grid action mismatch")
    return dict(native_sequence_verified=True,full_P_grid_action_verified=True)

def readout(source:Path,out:Path):
    if out.exists():raise ValueError("new output directory required")
    raw=source.read_bytes();records=[json.loads(line) for line in raw.splitlines() if line.strip()]
    results=[]
    for record in records:
        if record.get("schema")!=1:raise ValueError("unknown schema")
        result=diagnose(record["P"],record["H"],record["R"],record["weights"],record["candidates"])
        result.update(verify_native(record,result))
        result.update(event_time_s=record["event_time_s"],native_applied=record["applied"],native_epsilon=record["selected_epsilon"],
                      native_T_error=record["T"]-result["T"],native_J_error=(record["J"]-result["J"] if record["J"] is not None else None))
        results.append(result)
    counts={}
    for row in results:counts[row["continuous_condition"]]=counts.get(row["continuous_condition"],0)+1
    receipt=dict(source=str(source),sha256=hashlib.sha256(raw).hexdigest(),events=len(results),conditions=counts,
                 raw_reads=0,reference_reads=0,navigation_calls=0,evaluator_calls=0,
                 interpretation="local working covariance diagnosis, not physical calibration or navigation benefit")
    out.mkdir(parents=True)
    (out/"EVENT_DIAGNOSTICS.jsonl").write_text("".join(json.dumps(x,allow_nan=False)+"\n" for x in results))
    (out/"SUMMARY.json").write_text(json.dumps(receipt,indent=2)+"\n")
    return receipt

def main():
    p=argparse.ArgumentParser();p.add_argument("--input",type=Path,required=True);p.add_argument("--out",type=Path,required=True)
    a=p.parse_args();print(json.dumps(readout(a.input,a.out)))
if __name__=="__main__":main()
