#!/usr/bin/env python3
"""Stage-B conditional fixed-N diagnostics. No integer search or acceptance.
Real execution requires the frozen commit; unit oracles use synthetic arrays only.
"""
from __future__ import annotations
import argparse,csv,gzip,hashlib,io,json,math,subprocess,sys,time,traceback
from collections import Counter
from dataclasses import asdict,is_dataclass,replace
from pathlib import Path
import numpy as np
from scipy.stats import chi2

REPO=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(REPO/"src"))
from legsa_gins.paper_rebuild.carrier_phase.admission import FrozenCandidate
from legsa_gins.paper_rebuild.carrier_phase.arc_relations import FrozenIntegerGraph,SdArcNode
from legsa_gins.paper_rebuild.carrier_phase.arc_projection import transport_epoch
from legsa_gins.paper_rebuild.carrier_phase.multignss import MultiGnssEpoch,GroupDD,raw
from legsa_gins.paper_rebuild.carrier_phase.temporal import assemble_epochs,model_fingerprint,TemporalModelError
from legsa_gins.paper_rebuild.carrier_phase.faults import (
    PhaseFaultMap,build_phase_fault_map,stack_phase_fault_maps,fixed_integer_gls,single_fault_glrt)
from legsa_gins.paper_rebuild.carrier_phase.sensitivity import analyze_phase_fault_sensitivity
from legsa_gins.paper_rebuild.horizontal_literature.ext01_clambda import constrained_baseline
from trusted_heading_arc_support_audit import physical_failures

FAMILY="GPS_GAL_BDS_DUAL"
LENGTH=.35
ALPHA=.01
MISS=.05
BUDGET=14292
WALL_S=1800.
PLAN=REPO/"docs/paper_rebuild/TRUSTED_HEADING_20261006/PROJECTED_FIXED_N_PLAN.md"
EXPECTED_CONTRACT="90fe236dd4a8aeb0477c925dc2140d7050197fcf3c7577e5850183120b5008f6"
EXPECTED_PLAN="4eeb5f4536d0ac20e1ed68247d123ef5798980b0bfc6bed723fc09b54563c82e"
EXPECTED_AUDIT_CSV="83e5dd6533c66a1a285ae858860f4e7e2b3bda85d15c14aefcad3412314aaa7e"

def serial(v):
    if is_dataclass(v):return serial(asdict(v))
    if isinstance(v,np.ndarray):return serial(v.tolist())
    if isinstance(v,np.generic):return serial(v.item())
    if isinstance(v,dict):return {str(k):serial(x) for k,x in v.items()}
    if isinstance(v,(list,tuple)):return [serial(x) for x in v]
    if isinstance(v,float) and not math.isfinite(v):raise ValueError("nonfinite diagnostic serialization")
    return v

def digest(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(p,expected=None):
    data=Path(p).read_bytes();sha=hashlib.sha256(data).hexdigest()
    if expected is not None and sha!=expected:raise ValueError("input SHA mismatch: "+str(p))
    return json.loads(data),sha
def emit(p,obj):p.write_text(json.dumps(serial(obj),ensure_ascii=False,indent=2,allow_nan=False)+"\n")
def revision():return subprocess.check_output(["git","rev-parse","HEAD"],cwd=REPO,text=True).strip()
def source_snapshot():
    result={}
    for module in tuple(sys.modules.values()):
        name=getattr(module,"__file__",None)
        if name:
            path=Path(name).resolve()
            if path.suffix==".py" and path.is_relative_to(REPO):
                result[str(path.relative_to(REPO))]=digest(path)
    result[str(PLAN.relative_to(REPO))]=digest(PLAN)
    return dict(sorted(result.items()))
def neutral():
    return dict(accepted_integer_measurement=False,false_fix_probability=None,
                all_alternatives_covered=False,search_certificate_transferred=False)

def restore_pair(case,times):
    """No future observation is inspected when restoring these original N."""
    selection=case["subset_selection"];labels=tuple(selection["selected_labels"])
    if (len(times)!=10 or len(labels)!=6 or selection["status"]!="READY"
            or tuple(selection["selection_times"])!=tuple(times[:5])
            or selection["selected_at"]!=times[4]):
        raise ValueError("original selection keys/support mismatch")
    saved=case["frozen_candidates"]
    if len(saved)!=2:raise ValueError("exactly two frozen candidates required")
    pair=tuple(FrozenCandidate(**x) for x in saved)
    if (pair[0].candidate_id!="partial_primary" or pair[1].candidate_id!="partial_competitor"
            or any(c.selected_at!=times[4] or c.active_labels!=labels for c in pair)
            or pair[0].source_id!=pair[1].source_id
            or pair[0].source_id!="SELECTED_OBSERVATION_MARGINAL_Q_V1:"+case["selected_likelihood_plan_fingerprint"]+":"+case["case_id"]):
        raise ValueError("frozen candidate identity mismatch")
    search=case["search"]
    if not search["certificate"]["global_optimum_certified"]:raise ValueError("original search uncertified")
    if tuple(search["all_labels"])!=labels:raise ValueError("original search-label order mismatch")
    for c,side,fp in zip(pair,["best","second"],["primary_fingerprint","competitor_fingerprint"]):
        if (c.integers!=dict(zip(labels,search[side]["ambiguity"]))
                or c.fingerprint!=case["admission"][fp]
                or len(search[side]["ambiguity"])!=len(labels)):
            raise ValueError("candidate values/fingerprint disagree with original search")
    if pair[0].integers==pair[1].integers:raise ValueError("original active candidates already equal")
    return pair

def load_model(prepared,record,pins):
    entry=record["families"].get(FAMILY,{})
    if entry.get("status")!="BUILT":raise ValueError("registered model unavailable")
    filename=entry["file"];path=(prepared/filename).resolve()
    if not path.is_relative_to(prepared.resolve()):raise ValueError("model path escapes prepared root")
    payload=path.read_bytes()
    if hashlib.sha256(payload).hexdigest()!=pins[filename]:raise ValueError("model SHA differs from stage A")
    with np.load(io.BytesIO(payload),allow_pickle=False) as z:
        y,A,B,Q=[np.asarray(z[k],float) for k in ("y","A","B","Q")]
    labels=tuple(entry["ambiguity_labels"]);m=len(labels);groups=[];offset=0
    for saved in entry["groups"]:
        pivot=raw.SignalIdentity(**saved["pivot"])
        sats=tuple(raw.SignalIdentity(**v) for v in saved["satellites"])
        cc=tuple(range(offset,offset+len(sats)));rr=cc+tuple(i+m for i in cc)
        groups.append(GroupDD(tuple(saved["key"]),pivot,sats,y[list(rr)],
            A[np.ix_(rr,cc)],B[list(rr)],Q[np.ix_(rr,rr)],
            tuple(labels[i] for i in cc),rr,cc))
        offset+=len(sats)
    if offset!=m:raise ValueError("native group shape mismatch")
    return MultiGnssEpoch(record["time_s"],y,A,B,Q,labels,tuple(groups),entry["metadata"])

def transport_fault_map(original,view):
    """Keep every physical column, including an exactly cancelled new pivot."""
    base=build_phase_fault_map(original)
    U=view.observation_transform;matrix=U@base.matrix
    labels=view.model.ambiguity_labels;A=view.model.A
    hypotheses=[]
    for j,h in enumerate(base.hypotheses):
        affected=tuple(label for k,label in enumerate(labels)
                       if np.any((A[:,k]!=0)&(matrix[:,j]!=0)))
        hypotheses.append(replace(h,affected_ambiguity_labels=affected))
    return PhaseFaultMap(matrix,tuple(hypotheses),tuple(range(len(matrix))),len(matrix))

def fixed_diagnostic(model,integers,fmap,counters,*,epoch_count,slot_lengths=None):
    counters["fixed_n_gls_attempts"]+=1
    if counters["fixed_n_gls_attempts"]>BUDGET:raise ValueError("GLS budget exceeded")
    fit=fixed_integer_gls(model,integers)
    if fit.unknown_labels or fit.rows_withheld:raise ValueError("projected model has unknown N or silently withheld rows")
    counters["fixed_n_gls_completed"]+=1
    out=dict(status="DIAGNOSTIC_COMPLETE",residual_cost=fit.residual_cost,
        residual_df=fit.residual_df,rank=fit.baseline_rank,rows_retained=fit.rows_retained,
        bhat=fit.bhat,Cb=fit.Cb,epoch_count=epoch_count,**neutral())
    if fit.baseline_rank!=3*epoch_count or fit.residual_df<=0:
        out.update(status="INSUFFICIENT_SUPPORT",reason="rank/df insufficient")
        return out
    if slot_lengths is None:
        if epoch_count!=1:raise ValueError("joint length must use independent per-epoch fits")
        counters["sphere_calls"]+=1
        sphere=constrained_baseline(fit.bhat,fit.Cb,LENGTH)
        baseline=np.asarray(sphere.baseline,float)
        residual=model.y-model.A@np.array([integers[x] for x in model.ambiguity_labels])-model.B@baseline
        raw_cost=float(residual@np.linalg.solve(model.Q,residual))
        penalty=float((baseline-fit.bhat)@np.linalg.solve(fit.Cb,baseline-fit.bhat))
        error=abs(raw_cost-fit.residual_cost-penalty)
        if error>1e-6*(1+raw_cost):raise ValueError("raw sphere/GLS objective identity failed")
        out.update(sphere_baseline=baseline,sphere_full_cost=raw_cost,objective_identity_error=error)
    else:
        if len(slot_lengths)!=epoch_count:raise ValueError("joint length count mismatch")
        penalty=float(sum(slot_lengths))
    out.update(length_penalty=penalty,length_df=3*epoch_count,
        residual_threshold=float(chi2.isf(ALPHA/2,fit.residual_df)),
        length_threshold=float(chi2.isf(ALPHA/2,3*epoch_count)),
        residual_nominal_p=float(chi2.sf(fit.residual_cost,fit.residual_df)),
        length_conservative_nominal_p=float(chi2.sf(penalty,3*epoch_count)))
    out["residual_flag"]=out["residual_cost"]>out["residual_threshold"]
    out["length_flag"]=out["length_penalty"]>out["length_threshold"]
    counters["glrt_calls"]+=1
    fault=single_fault_glrt(fit,fmap,family_alpha=ALPHA)
    counters["sensitivity_calls"]+=1
    sensitivity=analyze_phase_fault_sensitivity(fit,fmap,family_alpha=ALPHA,miss_probability=MISS)
    out.update(fault=serial(fault),sensitivity=serial(sensitivity),
        phase_fault_flag=any(s.nominal_reject_null for s in fault.scores),
        unobservable_columns=len(fault.unobservable_hypotheses),
        unbounded_mdb_columns=sum(s.detectable_amplitude_unbounded for s in sensitivity.scores),
        minimum_finite_mdb_cycles=min((s.mdb_cycles for s in sensitivity.scores if s.mdb_cycles is not None),default=None),
        maximum_finite_mdb_epoch_bias_m=max((s.mdb_max_epoch_bias_norm_m for s in sensitivity.scores
                                           if s.mdb_max_epoch_bias_norm_m is not None),default=None))
    return out

def diagnose_window(pair,models,event_index,counters):
    if len(models)!=5 or any(m is None for m in models):raise ValueError("five fixed future models required")
    if any(abs(m.time_s-(pair[0].selected_at+.2*(i+1)))>.01 for i,m in enumerate(models)):
        raise ValueError("future slots moved or precede candidate")
    graphs=[FrozenIntegerGraph.from_candidate(c) for c in pair]
    kept=[[],[]];maps=[[],[]];values=[{},{}];fits=[[],[]];slots=[]
    for model in models:
        alive={(n.signal,n.arc) for component in graphs[0].components for n,_ in component}
        losses=physical_failures(alive,model.time_s,event_index)
        qualified=[SdArcNode(*n) for n in sorted(alive-set(losses))]
        graphs=[g.advance(qualified,time_s=model.time_s) for g in graphs]
        views=[transport_epoch(model,g) for g in graphs]
        if (not np.array_equal(views[0].observation_transform,views[1].observation_transform)
                or (views[0].model is None)!=(views[1].model is None)):
            raise ValueError("candidate-dependent observation support forbidden")
        slot=dict(time_s=model.time_s,retired=[dict(node=n,reasons=v) for n,v in sorted(losses.items())],
                  phase_rows=views[0].phase_rows,phase_rank=views[0].phase_rank,
                  source_model_fingerprint=views[0].original_model_fingerprint,
                  U=views[0].observation_transform,projections=[],diagnostics=[])
        if views[0].model is None:
            slot.update(status="INSUFFICIENT_SUPPORT",projection_merged=None)
            slots.append(slot);continue
        for attr in ("y","A","B","Q"):
            if not np.array_equal(getattr(views[0].model,attr),getattr(views[1].model,attr)):
                raise ValueError("two candidates do not use identical numeric observation model")
        if views[0].model.ambiguity_labels!=views[1].model.ambiguity_labels:
            raise ValueError("two candidates label supports differ")
        for k,view in enumerate(views):
            integers=dict(view.relation_projection.integer_items)
            for label,value in integers.items():
                if label in values[k] and values[k][label]!=value:raise ValueError("frozen relation changed across slots")
                values[k][label]=value
            fmap=transport_fault_map(model,view)
            d=fixed_diagnostic(view.model,integers,fmap,counters,epoch_count=1)
            kept[k].append(view.model);maps[k].append(fmap);fits[k].append(d)
            slot["projections"].append(dict(origin=pair[k].fingerprint,integer_items=list(integers.items()),
                                            model_fingerprint=model_fingerprint(view.model)))
            slot["diagnostics"].append(d)
        slot.update(status="DIAGNOSTIC_COMPLETE",
                    projection_merged=views[0].relation_projection.integer_items==views[1].relation_projection.integer_items)
        slots.append(slot)
    complete=all(len(x)==5 for x in kept) and all(d["status"]=="DIAGNOSTIC_COMPLETE" for side in fits for d in side)
    joint=[]
    if complete:
        for k in range(2):
            problem=assemble_epochs(kept[k],LENGTH)
            fmap=stack_phase_fault_maps(maps[k],persistent=True)
            d=fixed_diagnostic(problem,values[k],fmap,counters,epoch_count=5,
                               slot_lengths=[v["length_penalty"] for v in fits[k]])
            error=abs(d["residual_cost"]-sum(v["residual_cost"] for v in fits[k]))
            if error>1e-7*(1+d["residual_cost"]):raise ValueError("joint GLS differs from independent-baseline slot sum")
            d["slot_sum_residual_identity_error"]=error
            joint.append(d)
    geometry_ready=all(s["phase_rows"]>=4 and s["phase_rank"]==3 for s in slots)
    return dict(status="DIAGNOSTIC_COMPLETE" if complete and geometry_ready else "INSUFFICIENT_SUPPORT",
                slots=slots,joint=joint,geometry_ready=geometry_ready,
                projection_merged_slots=sum(s.get("projection_merged") is True for s in slots),
                all_five_projections_merged=complete and all(s.get("projection_merged") is True for s in slots),
                candidate_fingerprints=[c.fingerprint for c in pair],**neutral())

def flat_result(case_id,result,stratum):
    row=dict(case_id=case_id,status=result["status"],
        original_label_failure=stratum["exact_original_labels_complete"]=="False",
        stage_A_support_upper_bound=stratum["recovered_support_upper_bound"]=="True",
        geometry_ready=result.get("geometry_ready"),
        projection_merged_slots=result.get("projection_merged_slots"),
        all_five_projections_merged=result.get("all_five_projections_merged"),**neutral())
    for k,side in enumerate(("primary","competitor")):
        ds=[s["diagnostics"][k] for s in result.get("slots",[]) if len(s.get("diagnostics",[]))==2]
        for flag in ("residual_flag","length_flag","phase_fault_flag"):
            row[side+"_slot_"+flag+"_count"]=sum(d.get(flag,False) for d in ds) if ds else None
        jd=result.get("joint",[])
        for key in ("residual_cost","residual_df","length_penalty","residual_flag","length_flag",
                    "phase_fault_flag","unobservable_columns","unbounded_mdb_columns",
                    "maximum_finite_mdb_epoch_bias_m"):
            row[side+"_joint_"+key]=jd[k].get(key) if len(jd)==2 else None
    if "error" in result:row["error"]=result["error"]
    return row

def counts():return dict(fixed_n_gls_attempts=0,fixed_n_gls_completed=0,sphere_calls=0,
                        glrt_calls=0,sensitivity_calls=0,cils_calls=0,admission_calls=0,
                        native_calls=0,evaluator_calls=0,reference_reads=0)

def run(args):
    if revision()!=args.execution_commit:raise ValueError("execution commit mismatch before data access")
    out=args.output.resolve();out.mkdir(parents=True,exist_ok=False)
    started=time.monotonic();counters=counts();sources=source_snapshot()
    state=dict(status="RUNNING",completed_windows=0,execution_commit=args.execution_commit,counters=counters)
    emit(out/"STATE.json",state)
    try:
        root=args.carrier_root.resolve();dense=root/"DENSE_SELECTED_FRONTEND";prepared=root/"REAL_100_340_V2"
        audit=args.audit_root.resolve()
        contract,csha=load(dense/"INPUT_CONTRACT.json",EXPECTED_CONTRACT)
        plan,psha=load(prepared/"PLAN.json",EXPECTED_PLAN)
        identity,_=load(audit/"INPUT_IDENTITY.json")
        casepins,_=load(audit/"CASE_INPUT_PINS.json")
        oldsummary,summarysha=load(dense/"SUMMARY_0001.json",identity["summary_sha256"])
        if digest(audit/"RESULTS.csv")!=EXPECTED_AUDIT_CSV:raise ValueError("stage A stratum table changed")
        strata={r["case_id"]:r for r in csv.DictReader((audit/"RESULTS.csv").open())}
        ids=[f"partial_{100+i/5:07.2f}" for i in range(1191)]
        if (oldsummary["attempted_case_ids"]!=ids or set(strata)!=set(ids) or set(casepins)!=set(ids)
                or len(plan["records"])!=1200 or plan["window_s"]!=[100.,340.]
                or plan["sequence"]!="BY2" or contract["family"]!=FAMILY
                or contract["alpha"]!=ALPHA or contract["length_m"]!=LENGTH
                or sum(r["exact_original_labels_complete"]=="False" for r in strata.values())!=535
                or sum(r["recovered_support_upper_bound"]=="True" for r in strata.values())!=516):
            raise ValueError("fixed window/parameter/stratum identity mismatch")
        events,esha=load(prepared/"ARC_EVENTS.json",identity["arc_events_sha256"])
        event_index={(float(e["time_s"]),int(e["rx"]),e["signal"]):e for e in events}
        if len(event_index)!=len(events):raise ValueError("duplicate arc event key")
        del events
        records=plan["records"];times=[float(r["time_s"]) for r in records]
        if any(abs(t-times[0]-.2*k)>.01 for k,t in enumerate(times)):raise ValueError("original cadence changed")
        models=[load_model(prepared,r,identity["model_npz_sha256"]) for r in records]
        emit(out/"INPUT_RECEIPT.json",dict(execution_commit=args.execution_commit,source_files=sources,
            contract_sha256=csha,plan_sha256=psha,arc_events_sha256=esha,summary_sha256=summarysha,
            audit_input_identity_sha256=digest(audit/"INPUT_IDENTITY.json"),
            audit_case_pins_sha256=digest(audit/"CASE_INPUT_PINS.json"),audit_csv_sha256=EXPECTED_AUDIT_CSV,
            carrier_root=str(root),audit_root=str(audit),script_sha256=digest(__file__),
            original_execution_commit=oldsummary["execution_commit"],**neutral()))
        rows=[]
        with gzip.open(out/"DETAILS.jsonl.gz","wt",encoding="utf-8") as f:
            for i,cid in enumerate(ids):
                if time.monotonic()-started>WALL_S:
                    result=dict(status="NOT_RUN_WALL_BUDGET",**neutral())
                else:
                    try:
                        case,_=load(dense/"cases"/(cid+".json"),casepins[cid])
                        if (case["case_id"]!=cid or case["window_start_s"]!=100+i/5
                                or case["input_contract"]!=EXPECTED_PLAN):
                            raise ValueError("case identity mismatch")
                        pair=restore_pair(case,times[i:i+10])
                        result=diagnose_window(pair,models[i+5:i+10],event_index,counters)
                        if result["geometry_ready"]!=(strata[cid]["all_five_conditional_geometry_ready"]=="True"):
                            raise ValueError("production graph geometry disagrees with independent stage A")
                        result["original_selection"]=dict(
                            candidate_source=pair[0].source_id,selected_at=pair[0].selected_at,
                            best_full_cost=case["search"]["best"]["full_residual_cost"],
                            second_full_cost=case["search"]["second"]["full_residual_cost"],
                            certificate_scope=case["search"]["certificate"]["certificate_scope"],
                            selected_likelihood_plan_fingerprint=case["selected_likelihood_plan_fingerprint"],
                            case_sha256=casepins[cid])
                    except Exception as exc:
                        result=dict(status="INPUT_ERROR",error=str(exc),traceback=traceback.format_exc(),**neutral())
                row=flat_result(cid,result,strata[cid]);rows.append(row)
                f.write(json.dumps(serial(dict(case_id=cid,**result)),ensure_ascii=False,allow_nan=False)+"\n")
                if (i+1)%50==0 or i==1190:
                    f.flush();state.update(completed_windows=i+1);emit(out/"STATE.json",state)
                    print(json.dumps(dict(completed=i+1,counters=counters)),flush=True)
        fields=list(dict.fromkeys(k for row in rows for k in row))
        with (out/"RESULTS.csv").open("w",newline="",encoding="utf-8") as f:
            writer=csv.DictWriter(f,fieldnames=fields,lineterminator="\n");writer.writeheader()
            for row in rows:writer.writerow({k:"NA" if v is None else v for k,v in row.items()})
        grouped={}
        for name,selected in [("all_1191",rows),("original_failure_535",[r for r in rows if r["original_label_failure"]]),
                              ("support_upper_bound_516",[r for r in rows if r["stage_A_support_upper_bound"]])]:
            grouped[name]=dict(denominator=len(selected),statuses=dict(Counter(r["status"] for r in selected)),
                all_five_projection_merged=sum(r["all_five_projections_merged"] is True for r in selected),
                joint_primary_flags={key:sum(r.get("primary_joint_"+key) is True for r in selected)
                                     for key in ("residual_flag","length_flag","phase_fault_flag")},
                joint_primary_supported=sum(r.get("primary_joint_residual_cost") is not None for r in selected))
        summary=dict(schema="projected_fixed_n_diagnostic.v1",status="EXECUTION_COMPLETE",
            source_identity_unchanged=source_snapshot()==sources,head_unchanged=revision()==args.execution_commit,
            fixed_windows=1191,strata=grouped,counters=counters,elapsed_s=time.monotonic()-started,
            temporal_covariance="INDEPENDENT_EPOCH_WORKING_ASSUMPTION_NOT_SELECTION_CALIBRATION",
            unknown_other_integer_alternatives="NOT_ENUMERATED",**neutral())
        if not summary["source_identity_unchanged"] or not summary["head_unchanged"]:
            summary["status"]="EXECUTED_WITH_IDENTITY_CHANGE"
        emit(out/"SUMMARY.json",summary)
        state.update(status=summary["status"]);emit(out/"STATE.json",state)
        emit(out/"OUTPUT_SEAL.json",{x.name:digest(x) for x in out.iterdir() if x.is_file()})
        print(json.dumps(summary),flush=True)
    except Exception as exc:
        state.update(status="TECHNICAL_FAILURE",error=str(exc),traceback=traceback.format_exc())
        emit(out/"STATE.json",state);raise

def main():
    p=argparse.ArgumentParser()
    for name in ("carrier-root","audit-root","output"):p.add_argument("--"+name,type=Path,required=True)
    p.add_argument("--execution-commit",required=True)
    run(p.parse_args())
if __name__=="__main__":main()
