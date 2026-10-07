"""A conditional minimax witness for unrestricted state/noise cross moments.

All errors are centered on the declared prior mean, before the tested innovation.
P and R are working marginal moments; their physical validity is not certified.
For V=R-H P H.T PSD, n=-H e+v gives C=-P H.T and innovation r=v.
For any fixed linear correction K, loss is T+tr(W K V K.T), at least T.
This is a countermodel inside an unrestricted PSD cross class, not actual SDK C.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time
import numpy as np

ROOT=Path(__file__).resolve().parents[3]
SCRIPT='scripts/paper_rebuild/carrier_phase/foot_unknown_cross_certificate.py'
PLAN='docs/paper_rebuild/TRUSTED_HEADING_CONTINUATION_20261007/FOOT_UNKNOWN_CROSS_REAL_PLAN.json'
EPS=np.finfo(float).eps


def require(ok,message):
    if not ok: raise ValueError(message)


def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def psd_qualification(a,name):
    a=np.asarray(a,dtype=float)
    require(a.ndim==2 and a.shape[0]==a.shape[1] and len(a)>0,name+': square nonempty')
    require(np.isfinite(a).all(),name+': finite')
    diagonal=np.diag(a)
    require(np.all(diagonal>=0),name+': negative diagonal')
    zero=diagonal==0
    require(not np.any(a[zero]!=0) and not np.any(a[:,zero]!=0),name+': zero-variance row is not zero')
    scales=np.sqrt(np.where(diagonal>0,diagonal,1.))
    normalized=a/scales[:,None]/scales[None,:]
    require(np.isfinite(normalized).all(),name+': finite normalized matrix')
    tol=128*EPS*len(a)*max(1.,float(np.max(np.abs(normalized))))
    asym=float(np.max(np.abs(normalized-normalized.T)))
    require(asym<=tol,name+': nonsymmetric')
    vals=np.linalg.eigvalsh((normalized+normalized.T)*.5)
    require(np.isfinite(vals).all(),name+': finite spectrum')
    require(float(vals[0])>=-tol,name+': not working PSD')
    return dict(normalized_min_eigenvalue=float(vals[0]),normalized_tolerance=float(tol),
                normalized_symmetry_error=asym,
                scope='roundoff-tolerant working PSD qualification; no matrix clipping/loading')


def witness_check(P,H,R,weights,*,centered_model,conditioning_id):
    require(centered_model is True,'center known prior/measurement means before applying the covariance witness')
    require(isinstance(conditioning_id,str) and conditioning_id.strip(),'same frozen conditioning information identity required')
    P=np.asarray(P,float);H=np.asarray(H,float);R=np.asarray(R,float);w=np.asarray(weights,float)
    pq=psd_qualification(P,'P');rq=psd_qualification(R,'R')
    require(H.shape==(len(R),len(P)) and np.isfinite(H).all(),'H shape/finite')
    require(w.shape==(len(P),) and np.isfinite(w).all() and np.all(w>=0),'PSD diagonal W required')
    # Complete original P is used, including every small positive mode.
    D=H@P@H.T; V=R-D; C=-P@H.T
    T=float(np.dot(w,np.diag(P)))
    require(np.isfinite(D).all() and np.isfinite(V).all() and np.isfinite(C).all() and np.isfinite(T),'finite direct moment arithmetic')
    dscale=np.maximum(np.diag(R),np.maximum(np.diag(D),0.))
    scales=np.sqrt(np.where(dscale>0,dscale,1.))
    rn=R/scales[:,None]/scales[None,:]
    dn=D/scales[:,None]/scales[None,:]
    vn=V/scales[:,None]/scales[None,:]
    require(all(np.isfinite(a).all() for a in (rn,dn,vn)),'finite normalized moment arithmetic')
    scale=max(1.,float(np.max(np.abs(rn))),float(np.max(np.abs(dn))))
    tol=float(128*EPS*len(R)*scale)
    asym=float(np.max(np.abs(vn-vn.T)))
    vals=np.linalg.eigvalsh((vn+vn.T)*.5)
    direct_vals=np.linalg.eigvalsh((V+V.T)*.5)
    require(np.isfinite(vals).all() and np.isfinite(direct_vals).all(),'finite V spectra')
    smallest=float(vals[0])
    if asym>tol: status='UNRESOLVED_NUMERICAL_SYMMETRY'
    elif np.array_equal(V,np.zeros_like(V)): status='WITNESS_EXACT_ZERO_REMAINDER'
    elif smallest>tol: status='WITNESS_STRICT_WORKING_MARGIN'
    elif smallest < -tol: status='CONDITION_NOT_SATISFIED'
    else: status='UNRESOLVED_PSD_BOUNDARY'
    supported=status.startswith('WITNESS_')
    return dict(status=status,witness_supported=supported,
        T=T,
        V_min_eigenvalue_direct=float(direct_vals[0]),
        V_min_eigenvalue_normalized=smallest,V_normalized_tolerance=tol,
        V_normalized_margin_in_tolerances=smallest/tol,V_normalized_symmetry_error=asym,
        adversarial_C_frobenius_norm=float(np.linalg.norm(C)),
        innovation_state_cross_max_abs=float(np.max(np.abs(P@H.T+C))),
        P_qualification=pq,R_qualification=rq,
        centered_model=True,conditioning_id=conditioning_id,
        minimax_trace_working_class=(T if supported else None),
        skip_uniqueness_established=False,actual_cross_identified=False,physical_marginals_qualified=False,
        implication='fixed linear K; PSD weighted trace; unrestricted joint-PSD cross class only',
        no_guarantee_of_gain_if_condition_fails=True)


def emit(path,value):
    with Path(path).open('x') as f:json.dump(value,f,indent=2);f.write('\n')


def run(commit):
    plan_path=ROOT/PLAN;plan=json.loads(plan_path.read_text())
    require(plan['status']=='FROZEN_READY_FOR_SINGLE_EXECUTION','registered status')
    require(plan['events']==2510 and plan['offline_processes']==1,'fixed budget')
    require([(x['id'],x['events']) for x in plan['sequences']]==[('BY2',687),('BY2H',666),('BY2O',1157)],'fixed three-sequence full denominator')
    for rel,digest in plan['source_pins'].items():
        f=ROOT/rel;require(sha(f)==digest,'source hash '+rel)
        require(f.read_bytes()==subprocess.check_output(['git','show',commit+':'+rel],cwd=ROOT),'source commit '+rel)
    require(plan_path.read_bytes()==subprocess.check_output(['git','show',commit+':'+PLAN],cwd=ROOT),'plan commit')
    scratch=ROOT.parent.parent/'LegSA-GINS-SCRATCH'/'TRUSTED_HEADING_CONTINUATION_20261007'
    old=scratch/'FOOT_INFORMATION_TRIAL_ATTEMPT01';out=scratch/'FOOT_UNKNOWN_CROSS_ATTEMPT01'
    require(not out.exists(),'no alternative stage or retry')
    require(sha(old/'ALL_NATIVE_SEALED.json')==plan['native_seal_sha256'],'native seal')
    require(sha(old/'READOUT_COMPLETE.json')==plan['readout_complete_sha256'],'readout seal')
    native_seal=json.loads((old/'ALL_NATIVE_SEALED.json').read_text())
    for spec in plan['sequences']:
        require(native_seal['files']['NATIVE/'+spec['id']+'/FOOT_INFORMATION_INPUTS.jsonl']==spec['dump_sha256'],'dump must bind original native seal')
    out.mkdir();started=time.monotonic();rows=[];summaries=[]
    try:
        for spec in plan['sequences']:
            sid=spec['id'];source=old/'NATIVE'/sid/'FOOT_INFORMATION_INPUTS.jsonl'
            qualification=old/'READOUT'/sid/'EVENT_DIAGNOSTICS.jsonl'
            require(sha(source)==spec['dump_sha256'] and sha(qualification)==spec['qualification_sha256'],'sealed inputs')
            events=[json.loads(line) for line in source.read_text().splitlines()]
            quals=[json.loads(line) for line in qualification.read_text().splitlines()]
            require(len(events)==len(quals)==spec['events'],'complete event denominator')
            local=[]
            for event,qual in zip(events,quals):
                require(time.monotonic()-started<=60,'fixed 60s readout budget')
                require(event['event_time_s']==qual['event_time_s'],'exact event time')
                require(qual['spectral_full_model_qualified'],'old P/full-model qualification')
                result=witness_check(np.asarray(event['P']).reshape(24,24),
                    np.asarray(event['H']).reshape(3,24),np.asarray(event['R']).reshape(3,3),
                    np.r_[event['weights'],np.zeros(3)],centered_model=True,
                    conditioning_id=sid+':ORIGINAL_END_PRIOR_BEFORE_FOOT_UPDATE')
                record=dict(sequence=sid,event_time_s=event['event_time_s'],**result)
                rows.append(record);local.append(record)
            from collections import Counter
            summaries.append(dict(sequence=sid,events=len(local),statuses=dict(Counter(r['status'] for r in local)),
                min_direct_V_eigenvalue=min(r['V_min_eigenvalue_direct'] for r in local),
                min_normalized_V_eigenvalue=min(r['V_min_eigenvalue_normalized'] for r in local),
                min_roundoff_margin_multiple=min(r['V_normalized_margin_in_tolerances'] for r in local)))
        require(len(rows)==2510,'all events retained')
        with (out/'EVENT_WITNESSES.jsonl').open('x') as f:
            for row in rows:f.write(json.dumps(row,separators=(',',':'))+'\n')
        result=dict(status='COMPLETE_CONDITIONAL_WORKING_CLASS_DIAGNOSIS',registration_commit=commit,
            events=len(rows),sequences=summaries,elapsed_s=time.monotonic()-started,
            new_native_calls=0,new_evaluator_calls=0,raw_reads=0,reference_reads=0,
            source_dumps=3,old_qualification_tables=3,
            actual_C_identified=False,physical_error_bound_established=False,
            output_sha256={'EVENT_WITNESSES.jsonl':sha(out/'EVENT_WITNESSES.jsonl')})
        emit(out/'SUMMARY.json',result);emit(out/'COMPLETE.json',dict(summary_sha256=sha(out/'SUMMARY.json')))
        print(json.dumps(result),flush=True)
    except BaseException as exc:
        emit(out/'FAILED.json',dict(error=repr(exc),processed_events=len(rows),no_retry=True));raise


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--registration-commit',required=True)
    run(parser.parse_args().registration_commit)
