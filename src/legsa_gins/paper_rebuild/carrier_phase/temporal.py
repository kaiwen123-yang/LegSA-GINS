"""Temporal carrier model: shared arc integers and independent per-epoch baselines."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Sequence
import numpy as np

class TemporalModelError(ValueError):
    pass

def positive_definite(value, name):
    q=np.asarray(value,dtype=float)
    if q.ndim!=2 or q.shape[0]!=q.shape[1] or not np.isfinite(q).all():
        raise TemporalModelError(f"{name}: invalid finite square covariance")
    scale=max(float(np.max(np.abs(q))),np.finfo(float).tiny)
    if np.max(np.abs(q-q.T))>1e-10*scale:
        raise TemporalModelError(f"{name}: covariance is not symmetric")
    q=(q+q.T)*.5
    try:np.linalg.cholesky(q)
    except np.linalg.LinAlgError as ex:raise TemporalModelError(f"{name}: covariance is not positive definite") from ex
    return q

@dataclass(frozen=True)
class EpochBlock:
    time_s: float
    y: np.ndarray
    A: np.ndarray
    B: np.ndarray
    Q: np.ndarray
    ambiguity_labels: tuple[str,...]
    metadata: dict=field(default_factory=dict)
    @property
    def ambiguity_design(self):return self.A
    @property
    def baseline_design(self):return self.B
    @property
    def covariance(self):return self.Q

@dataclass(frozen=True)
class TemporalProblem:
    y: np.ndarray
    A: np.ndarray
    B: np.ndarray
    Q: np.ndarray
    times: np.ndarray
    ambiguity_labels: tuple[str,...]
    row_slices: tuple[slice,...]
    baseline_slices: tuple[slice,...]
    lengths: np.ndarray
    metadata: tuple[dict,...]
    @property
    def epoch_count(self):return len(self.times)
    @property
    def ambiguity_count(self):return len(self.ambiguity_labels)

@dataclass(frozen=True)
class TemporalFloat:
    ambiguity: np.ndarray
    baselines: np.ndarray
    covariance: np.ndarray
    covariance_aa: np.ndarray
    covariance_ba: np.ndarray
    conditional_covariance_b: np.ndarray
    conditional_gain: np.ndarray
    residual_objective: float
    whitened_y: np.ndarray
    whitened_A: np.ndarray
    whitened_B: np.ndarray
    numerical_rank: int
    condition_number: float
    @property
    def baseline(self):return self.baselines.reshape(-1)

def _coerce(block):
    if isinstance(block,EpochBlock):return block
    return EpochBlock(float(block.time_s),np.asarray(block.y),
        np.asarray(block.ambiguity_design),np.asarray(block.baseline_design),
        np.asarray(block.covariance),tuple(block.ambiguity_labels),
        dict(getattr(block,"metadata",{})))

def assemble_epochs(blocks:Sequence[EpochBlock],length_m:float=.350,*,temporal_covariance=None)->TemporalProblem:
    blocks=tuple(_coerce(b) for b in blocks)
    if not blocks or not np.isfinite(length_m) or length_m<=0:
        raise TemporalModelError("nonempty epochs and positive baseline length required")
    times=np.array([b.time_s for b in blocks],float)
    if not np.isfinite(times).all() or np.any(np.diff(times)<=0):
        raise TemporalModelError("epoch time keys must be finite and strictly increasing")
    labels=[];counts=[];validated=[]
    for b in blocks:
        y=np.asarray(b.y,float);aa=np.asarray(b.A,float);bb=np.asarray(b.B,float);qq=positive_definite(b.Q,"epoch Q")
        if (y.ndim!=1 or aa.shape!=(len(y),len(b.ambiguity_labels)) or bb.shape!=(len(y),3)
                or qq.shape!=(len(y),len(y)) or not np.isfinite(y).all()
                or not np.isfinite(aa).all() or not np.isfinite(bb).all()):
            raise TemporalModelError("epoch observation/design dimensions or values invalid")
        if len(set(b.ambiguity_labels))!=len(b.ambiguity_labels) or any(not isinstance(s,str) or not s for s in b.ambiguity_labels):
            raise TemporalModelError("ambiguity labels must be nonempty unique strings within an epoch")
        if not b.ambiguity_labels:raise TemporalModelError("at least one carrier ambiguity required")
        for label in b.ambiguity_labels:
            if label not in labels:labels.append(label)
        counts.append(len(y));validated.append((y,aa,bb,qq))
    offsets=np.r_[0,np.cumsum(counts)]
    rows=tuple(slice(int(offsets[k]),int(offsets[k+1])) for k in range(len(blocks)))
    bs=tuple(slice(3*k,3*k+3) for k in range(len(blocks)))
    y=np.concatenate([v[0] for v in validated])
    A=np.zeros((len(y),len(labels)));B=np.zeros((len(y),3*len(blocks)));Q=np.zeros((len(y),len(y)))
    column={v:i for i,v in enumerate(labels)}
    for k,(b,v) in enumerate(zip(blocks,validated)):
        rr=rows[k]
        A[np.ix_(np.arange(rr.start,rr.stop),[column[s] for s in b.ambiguity_labels])]=v[1]
        B[rr,bs[k]]=v[2];Q[rr,rr]=v[3]
    if temporal_covariance is not None:
        full=positive_definite(temporal_covariance,"full temporal Q")
        if full.shape!=Q.shape:raise TemporalModelError("full temporal covariance dimensions mismatch")
        for rr in rows:
            if not np.allclose(full[rr,rr],Q[rr,rr],rtol=1e-10,atol=1e-14):
                raise TemporalModelError("full covariance changes a registered epoch marginal")
        Q=full
    return TemporalProblem(y,A,B,Q,times,tuple(labels),rows,bs,np.full(len(blocks),length_m),tuple(dict(b.metadata) for b in blocks))

def with_scalar_prior(block:EpochBlock,direction,value:float,sigma:float,*,name="scalar_prior")->EpochBlock:
    b=_coerce(block);d=np.asarray(direction,float)
    if d.shape!=(3,) or not np.isfinite(d).all() or not np.isfinite(value) or not np.isfinite(sigma) or sigma<=0:
        raise TemporalModelError("invalid scalar prior")
    y=np.r_[b.y,value];Q=np.zeros((len(y),len(y)));Q[:-1,:-1]=b.Q;Q[-1,-1]=sigma*sigma
    metadata=dict(b.metadata);metadata.setdefault("appended_priors",[]);metadata["appended_priors"]=list(metadata["appended_priors"])+[{"name":name,"sigma":sigma,"value":value}]
    return EpochBlock(b.time_s,y,np.vstack([b.A,np.zeros((1,len(b.ambiguity_labels)))]),np.vstack([b.B,d]),Q,b.ambiguity_labels,metadata)

def has_cross_epoch_covariance(problem:TemporalProblem)->bool:
    # Any represented cross block is unsupported by the separable sphere solver.
    for k,a in enumerate(problem.row_slices):
        for b in problem.row_slices[k+1:]:
            if np.any(problem.Q[a,b]!=0.) or np.any(problem.Q[b,a]!=0.):return True
    return False

def joint_float(problem:TemporalProblem)->TemporalFloat:
    Q=positive_definite(problem.Q,"Q")
    chol=np.linalg.cholesky(Q)
    yw=np.linalg.solve(chol,problem.y);Aw=np.linalg.solve(chol,problem.A);Bw=np.linalg.solve(chol,problem.B)
    X=np.column_stack([Aw,Bw])
    if len(yw)<X.shape[1]:raise TemporalModelError("temporal float system underdetermined")
    u,s,vt=np.linalg.svd(X,full_matrices=False)
    tol=np.finfo(float).eps*max(X.shape)*s[0]
    rank=int(np.sum(s>tol))
    if rank!=X.shape[1]:raise TemporalModelError(f"temporal float rank deficient: {rank}/{X.shape[1]}")
    v=vt.T;estimate=v@((u.T@yw)/s);cov=(v/(s*s))@v.T
    m=problem.ambiguity_count
    # Compute conditional baseline covariance directly from B, avoiding subtraction
    # of the large ambiguity-marginal covariance (a cancellation-prone Schur step).
    ub,sb,vbt=np.linalg.svd(Bw,full_matrices=False);vb=vbt.T
    if np.any(sb<=np.finfo(float).eps*max(Bw.shape)*sb[0]):raise TemporalModelError("baseline design rank deficient")
    cb=(vb/(sb*sb))@vb.T
    gain=-((vb/sb)@ub.T)@Aw
    residual=yw-X@estimate
    return TemporalFloat(estimate[:m],estimate[m:].reshape(-1,3),(cov+cov.T)*.5,
        positive_definite(cov[:m,:m],"Qaa"),cov[m:,:m],positive_definite(cb,"Qb|a"),gain,
        float(residual@residual),yw,Aw,Bw,rank,float(s[0]/s[-1]))

def conditional_baselines(floating:TemporalFloat,integer)->np.ndarray:
    n=np.asarray(integer,float)
    if n.shape!=floating.ambiguity.shape:raise TemporalModelError("integer dimension mismatch")
    return (floating.baseline+floating.conditional_gain@(n-floating.ambiguity)).reshape(-1,3)
