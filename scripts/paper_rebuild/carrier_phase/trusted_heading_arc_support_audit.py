#!/usr/bin/env python3
"""Saved-input arc support audit; no y/N decision use and no search/admission.
Case JSON is parsed whole, so candidate/output fields may be read as bytes.
Only subset_selection fields are used. NPZ requests A/B/Q; y is not used.
"""
from __future__ import annotations
import argparse, csv, gzip, hashlib, io, json, math, subprocess, traceback
from collections import Counter, defaultdict
from pathlib import Path
import numpy as np

FAMILY="GPS_GAL_BDS_DUAL"
def emit(p,obj):
    p.write_text(json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False)+"\n",encoding="utf-8")
def load_json(p):
    data=p.read_bytes()
    return json.loads(data),hashlib.sha256(data).hexdigest()
def edge(label):
    v=json.loads(label)
    if not isinstance(v,list) or len(v)!=4 or not all(isinstance(x,str) and x for x in v):
        raise ValueError("invalid explicit DD arc label")
    a,b=(v[0],v[1]),(v[2],v[3])
    if group(a)!=group(b) or a[0]==b[0]:raise ValueError("cross-group/self DD")
    for sig,arc in (a,b):
        tokens=json.loads(arc)
        if len(tokens)!=2 or any(not isinstance(t,str) or not t.startswith(f"{rx}|{sig}|arc=")
                                for rx,t in enumerate(tokens,1)):
            raise ValueError("unrecognized saved physical SD token")
    return a,b
def group(node):
    gnss,sv,sig,freq=map(int,node[0].split(":"))
    return gnss,sig,freq
def gtext(g):return ":".join(map(str,g))
def components(labels):
    adj=defaultdict(set)
    for lab in labels:
        a,b=edge(lab);adj[a].add(b);adj[b].add(a)
    if len({n[0] for n in adj})!=len(adj):raise ValueError("multiple concurrent old arcs for signal")
    seen=set();out=[]
    for root in sorted(adj):
        if root in seen:continue
        todo=[root];comp=set()
        while todo:
            n=todo.pop()
            if n in comp:continue
            comp.add(n);todo.extend(adj[n]-comp)
        seen|=comp;out.append(tuple(sorted(comp)))
    return tuple(out)
def geometry(B,Q,phase_rows):
    count=len(phase_rows)
    rank=int(np.linalg.matrix_rank(B[phase_rows])) if count else 0
    white=np.linalg.solve(np.linalg.cholesky(Q),B)
    if np.linalg.matrix_rank(white)!=3:
        return dict(phase_rows=count,phase_rank=rank,ready=False,trace_m2=None,
                    lambda_max_m2=None,information_condition=None)
    info=white.T@white
    C=np.linalg.solve(info,np.eye(3));C=(C+C.T)/2
    eigen=np.linalg.eigvalsh(C)
    if not np.isfinite(C).all() or eigen[0]<=0:raise ValueError("invalid geometric covariance")
    return dict(phase_rows=count,phase_rank=rank,ready=(count>=4 and rank==3),
                trace_m2=float(np.trace(C)),lambda_max_m2=float(eigen[-1]),
                information_condition=float(np.linalg.cond(info)))
def current_vectors(labels):
    m=len(labels);vectors={};pivots={}
    for k,lab in enumerate(labels):
        a,b=edge(lab);g=group(a)
        if g in pivots and pivots[g]!=b:raise ValueError("non-star current group")
        pivots[g]=b;vectors[b]=np.zeros(m)
        v=np.zeros(m);v[k]=1.;vectors[a]=v
    return vectors,pivots
def projected_geometry(model,comps,alive):
    labels,B,Q=model["labels"],model["B"],model["Q"]
    m=len(labels);vectors,_=model["vectors_pivots"]
    phase=[];pairs=[];groups=Counter()
    for comp in comps:
        nodes=sorted(set(comp)&alive&set(vectors))
        if len(nodes)<2:continue
        pivot=nodes[0]
        for target in nodes[1:]:
            phase.append(vectors[target]-vectors[pivot])
            pairs.append((target,pivot));groups[gtext(group(target))]+=1
    U=np.zeros((m+len(phase),2*m));U[:m,:m]=np.eye(m)
    if phase:U[m:,m:]=np.asarray(phase)
    transformed_B=U@B;transformed_Q=U@Q@U.T
    value=geometry(transformed_B,transformed_Q,list(range(m,m+len(phase))))
    full=model["full_geometry"]
    value["trace_loss_vs_all_current_N_known"]=value["trace_m2"]/full["trace_m2"] if value["trace_m2"] and full["trace_m2"] else None
    value["lambda_max_loss_vs_all_current_N_known"]=value["lambda_max_m2"]/full["lambda_max_m2"] if value["lambda_max_m2"] and full["lambda_max_m2"] else None
    # Complete known-current phase data is an optimistic information upper bound.
    for k in ["trace_loss_vs_all_current_N_known","lambda_max_loss_vs_all_current_N_known"]:
        if value[k] is not None and value[k]<1-1e-7:raise ValueError("projection gained impossible information")
    value["groups"]=dict(groups);value["relations"]=pairs
    return value
def physical_failures(alive,t,event_index):
    lost={}
    for n in sorted(alive):
        tokens=json.loads(n[1]);why=[]
        for rx,token in enumerate(tokens,1):
            e=event_index.get((t,rx,n[0]))
            if e is None:why.append(f"RX{rx}:MISSING_ARC_EVENT");continue
            valid=e["eligible"] and e["temporal_link_qualified"] and e["arc_token"]==token
            if not valid:
                reasons=list(e["reasons"])
                if e["arc_token"]!=token:reasons.append("ARC_TOKEN_CHANGED")
                if not e["eligible"]:reasons.append("INELIGIBLE")
                if not e["temporal_link_qualified"]:reasons.append("LINK_NOT_QUALIFIED")
                why.extend(f"RX{rx}:{x}" for x in sorted(set(reasons)))
        if why:lost[n]=why
    return lost
def first_class(lost_pivot,lost_target,model_missing):
    if lost_pivot and lost_target:return "PIVOT_AND_TARGET_PHYSICAL_ARC_LOSS"
    if lost_pivot:return "PIVOT_PHYSICAL_ARC_LOSS"
    if lost_target:return "TARGET_PHYSICAL_ARC_LOSS"
    if model_missing:return "PHYSICAL_ARCS_CONTINUE_MODEL_QUALIFICATION_LOSS"
    return "PIVOT_COORDINATE_ONLY"
def run(args):
    out=args.output.resolve();out.mkdir(parents=True,exist_ok=False)
    report=args.report.resolve();report.mkdir(parents=True,exist_ok=True)
    root=Path(__file__).resolve().parents[3]
    state=dict(status="RUNNING",completed_windows=0,search_calls=0,admission_calls=0,
               glrt_calls=0,native_calls=0,evaluator_calls=0,reference_reads=0)
    emit(out/"STATE.json",state)
    try:
        stage=args.carrier_root.resolve();dense=stage/"DENSE_SELECTED_FRONTEND";prepared=stage/"REAL_100_340_V2"
        contract,csha=load_json(dense/"INPUT_CONTRACT.json")
        summary,ssha=load_json(dense/"SUMMARY_0001.json")
        plan,psha=load_json(prepared/"PLAN.json")
        if contract["model_plan_sha256"]!=psha:raise ValueError("prepared PLAN pin mismatch")
        if contract["family"]!=FAMILY or contract["likelihood"]!="selected-support":raise ValueError("unexpected input family/likelihood")
        ids=summary["attempted_case_ids"]
        expected=[f"partial_{100+i/5:07.2f}" for i in range(1191)]
        if ids!=expected:raise ValueError("registered 1191-window sequence mismatch")
        records=plan["records"]
        if len(records)!=1200 or plan["sequence"]!="BY2" or plan["window_s"]!=[100.,340.]:
            raise ValueError("fixed 1200-epoch input mismatch")
        times=[float(x["time_s"]) for x in records]
        if any(abs(t-times[0]-.2*k)>.01 for k,t in enumerate(times)):raise ValueError("input epoch cadence")
        events,esha=load_json(prepared/"ARC_EVENTS.json")
        event_index={}
        for e in events:
            k=(float(e["time_s"]),int(e["rx"]),e["signal"])
            if k in event_index:raise ValueError("duplicate arc event key")
            event_index[k]=e
        events_count=len(events);del events
        models=[];model_errors={};model_pins={}
        for k,record in enumerate(records):
            item=record["families"].get(FAMILY)
            if not item or item.get("status")!="BUILT":
                models.append(None);continue
            try:
                labels=tuple(item["ambiguity_labels"]);m=len(labels)
                payload=(prepared/item["file"]).read_bytes()
                model_pins[item["file"]]=hashlib.sha256(payload).hexdigest()
                with np.load(io.BytesIO(payload),allow_pickle=False) as data:
                    A=np.asarray(data["A"],float);B=np.asarray(data["B"],float);Q=np.asarray(data["Q"],float)
                if A.shape!=(2*m,m) or B.shape!=(2*m,3) or Q.shape!=(2*m,2*m):
                    raise ValueError("model shape")
                if not all(np.isfinite(a).all() for a in (A,B,Q)):raise ValueError("nonfinite input design/Q")
                if np.any(A[:m]) or np.any(A[m:]-np.diag(np.diag(A[m:]))):raise ValueError("nonstandard native ambiguity design")
                model=dict(labels=labels,B=B,Q=Q,metadata=item["metadata"],
                           vectors_pivots=current_vectors(labels),
                           full_geometry=geometry(B,Q,list(range(m,2*m))))
                models.append(model)
            except Exception as exc:
                model_errors[str(k)]=str(exc);models.append(None)
        identity=dict(schema="trusted_heading_arc_support_input_audit.v1",
            execution_commit=subprocess.check_output(["git","rev-parse","HEAD"],cwd=root,text=True).strip(),
            script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            source_paths=dict(carrier_root=str(stage),prepared_plan=str(prepared/"PLAN.json"),
                              case_root=str(dense/"cases"),arc_events=str(prepared/"ARC_EVENTS.json")),
            input_contract_sha256=csha,summary_sha256=ssha,plan_sha256=psha,arc_events_sha256=esha,
            original_execution_commit=summary["execution_commit"],npz_fields_requested=["A","B","Q"],
            case_json_whole_parsed=True,case_N_y_status_not_used=True,
            case_fields_used=["case_id","window_start_s","subset_selection"],
            model_loading_errors=model_errors,model_npz_sha256=model_pins)
        emit(out/"INPUT_IDENTITY.json",identity)
        rows=[];first_counts=Counter();physical_reason_counts=Counter();selected_groups=Counter()
        case_failures={};case_pins={}
        with gzip.open(out/"WINDOW_DETAILS.jsonl.gz","wt",encoding="utf-8") as details:
            for i,cid in enumerate(ids):
                row=dict(case_id=cid,window_start_s=100+i/5,status="AUDITED")
                try:
                    rec,sha=load_json(dense/"cases"/(cid+".json"));case_pins[cid]=sha
                    if rec["case_id"]!=cid or abs(rec["window_start_s"]-(100+i/5))>1e-9:
                        raise ValueError("case identity")
                    sel=rec["subset_selection"];labels=tuple(sel["selected_labels"])
                    if sel["status"]!="READY" or len(labels)!=6:raise ValueError("unexpected saved selection support")
                    if max(abs(a-b) for a,b in zip(sel["selection_times"],times[i:i+5]))>1e-9:
                        raise ValueError("saved selection times")
                    if len(sel["selection_times"])!=5 or sel["selected_at"]!=times[i+4]:raise ValueError("selection epoch identity")
                    if any(not set(labels)<=set(models[j]["labels"]) for j in range(i,i+5)):
                        raise ValueError("selection labels not continuous in original five models")
                    comps=components(labels);initial={n for c in comps for n in c}
                    pivots={edge(l)[1] for l in labels};targets={edge(l)[0] for l in labels}
                    alive=set(initial);slot_details=[];first=None;lost_history={}
                    group_counts=Counter(gtext(group(edge(l)[0])) for l in labels);selected_groups.update(group_counts)
                    for j in range(i+5,i+10):
                        t=times[j];model=models[j]
                        lost=physical_failures(alive,t,event_index)
                        lost_history.update(lost);alive-=set(lost)
                        missing=sorted(set(labels)-set(model["labels"])) if model else list(labels)
                        model_nodes=set(model["vectors_pivots"][0]) if model else set()
                        absent_model=sorted(alive-model_nodes)
                        if missing and first is None:
                            lp=sorted(set(lost_history)&pivots);lt=sorted(set(lost_history)&targets)
                            classification=first_class(lp,lt,absent_model) if model else "CURRENT_MODEL_UNAVAILABLE"
                            first=dict(time_s=t,slot=j-(i+5),classification=classification,
                                missing_labels=missing,lost_pivots=lp,lost_targets=lt,
                                physical_loss_reasons=[dict(node=n,reasons=lost_history[n]) for n in sorted(lost_history)],
                                continuous_nodes_not_in_model=absent_model)
                            for reasons in lost_history.values():
                                physical_reason_counts.update(set(reasons))
                        metrics=projected_geometry(model,comps,alive) if model else None
                        slot_details.append(dict(time_s=t,original_labels_preserved=not missing,
                            alive_original_nodes=len(alive),lost_nodes=[dict(node=n,reasons=w) for n,w in sorted(lost.items())],
                            conditional_geometry=metrics,current_model_available=model is not None))
                    first_kind=first["classification"] if first else "ORIGINAL_LABEL_SUPPORT_COMPLETE"
                    gm=[d["conditional_geometry"] for d in slot_details]
                    complete_geometry=all(x is not None and x["ready"] for x in gm)
                    finite=[x for x in gm if x is not None]
                    row.update(selected_at=sel["selected_at"],selection_end_s=times[i+4],
                        validation_end_s=times[i+9],selected_dd_count=len(labels),original_node_count=len(initial),
                        exact_original_labels_complete=first is None,first_failure_time_s=first["time_s"] if first else None,
                        first_failure_class=first_kind,first_lost_pivot_count=len(first["lost_pivots"]) if first else 0,
                        first_lost_target_count=len(first["lost_targets"]) if first else 0,
                        first_model_qualification_missing_nodes=len(first["continuous_nodes_not_in_model"]) if first else 0,
                        min_conditional_phase_rows=min(x["phase_rows"] for x in finite) if len(finite)==5 else None,
                        min_conditional_phase_rank=min(x["phase_rank"] for x in finite) if len(finite)==5 else None,
                        all_five_conditional_geometry_ready=complete_geometry,
                        recovered_support_upper_bound=bool(first and complete_geometry),
                        final_alive_original_nodes=len(alive),
                        max_trace_loss_vs_all_current_N_known=max((x["trace_loss_vs_all_current_N_known"] for x in finite
                            if x["trace_loss_vs_all_current_N_known"] is not None), default=None),
                        max_lambda_loss_vs_all_current_N_known=max((x["lambda_max_loss_vs_all_current_N_known"] for x in finite
                            if x["lambda_max_loss_vs_all_current_N_known"] is not None), default=None),
                        selected_groups=json.dumps(group_counts,sort_keys=True),
                        final_conditional_phase_groups=json.dumps(gm[-1]["groups"],sort_keys=True) if gm[-1] else None)
                    first_counts[first_kind]+=1
                    details.write(json.dumps(dict(case_id=cid,selection_labels=labels,components=comps,
                        first_failure=first,future_slots=slot_details),ensure_ascii=False,allow_nan=False)+"\n")
                except Exception as exc:
                    case_failures[cid]=str(exc);row.update(status="AUDIT_ERROR",audit_error=str(exc))
                    details.write(json.dumps(dict(case_id=cid,audit_error=str(exc)))+"\n")
                rows.append(row)
                if (i+1)%200==0 or i+1==1191:
                    state["completed_windows"]=i+1;emit(out/"STATE.json",state)
                    print(json.dumps(dict(completed=i+1,total=1191,audit_errors=len(case_failures))),flush=True)
        emit(out/"CASE_INPUT_PINS.json",case_pins)
        audited=[r for r in rows if r["status"]=="AUDITED"]
        summary_out=dict(schema="trusted_heading_arc_support_audit.v1",
            status="ALL_WINDOWS_AUDITED" if not case_failures and not model_errors else "COMPLETED_WITH_AUDIT_ERRORS",
            fixed_windows=1191,model_epochs=1200,arc_event_records=events_count,
            first_failure_class_counts=dict(first_counts),
            exact_original_labels_complete=sum(r["exact_original_labels_complete"] for r in audited),
            original_label_failure_windows=sum(not r["exact_original_labels_complete"] for r in audited),
            all_five_conditional_geometry_ready=sum(r["all_five_conditional_geometry_ready"] for r in audited),
            recovered_support_upper_bound=sum(r["recovered_support_upper_bound"] for r in audited),
            support_upper_bound_by_failure_class=dict(Counter(r["first_failure_class"] for r in audited if r["recovered_support_upper_bound"])),
            first_loss_endpoint_reason_counts=dict(physical_reason_counts),
            selection_group_occurrences=dict(selected_groups),case_errors=case_failures,model_errors=model_errors,
            original_frontend_execution_commit=identity["original_execution_commit"],
            input_contract_sha256=csha,plan_sha256=psha,script_sha256=identity["script_sha256"],
            execution_commit=identity["execution_commit"],
            code_used_for_classification="standalone topology and input geometry; no production solver/admission imports",
            N_y_or_existing_output_status_used=False,whole_case_json_parsed=True,
            interpretation="conditional support/geometry upper bound; not acceptance, correct FIX, or navigation effect",
            search_calls=0,admission_calls=0,glrt_calls=0,native_calls=0,evaluator_calls=0,reference_reads=0)
        fieldnames=list(dict.fromkeys(k for row in rows for k in row))
        with (out/"RESULTS.csv").open("w",newline="",encoding="utf-8") as f:
            writer=csv.DictWriter(f,fieldnames=fieldnames,lineterminator="\n");writer.writeheader()
            for row in rows:writer.writerow({k:"NA" if v is None else v for k,v in row.items()})
        emit(out/"SUMMARY.json",summary_out)
        for filename,source in [("ARC_SUPPORT_AUDIT_RESULTS.csv",out/"RESULTS.csv"),("ARC_SUPPORT_AUDIT_SUMMARY.json",out/"SUMMARY.json")]:
            target=report/filename
            if target.exists():raise ValueError("refusing to overwrite "+str(target))
            target.write_bytes(source.read_bytes())
        state.update(status=summary_out["status"],audit_errors=len(case_failures))
        emit(out/"STATE.json",state)
        print(json.dumps(summary_out,ensure_ascii=False),flush=True)
    except Exception as exc:
        state.update(status="AUDIT_TECHNICAL_FAILURE",exception=str(exc),traceback=traceback.format_exc())
        emit(out/"STATE.json",state);raise
def main():
    p=argparse.ArgumentParser()
    for name in ["carrier-root","output","report"]:p.add_argument("--"+name,type=Path,required=True)
    run(p.parse_args())
if __name__=="__main__":main()
