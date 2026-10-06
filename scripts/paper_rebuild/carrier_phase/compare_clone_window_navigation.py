#!/usr/bin/env python3
"""Derived clone attribution only; never open reference or invoke algorithms."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import sys
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parent))
import compare_full_window_navigation as base
ROOT=Path(__file__).resolve().parents[3]
SEQUENCES=base.SEQUENCES
ARMS=("NULL_CLONE","PAIR_YOUNG")
require=base.require
metrics=base.metrics
number=base.number

def delta_row(sequence,support,role,current,control,current_arm,control_arm,count=None):
    """Zero-tolerance values are reported, not substituted for V3 tolerances."""
    row={"sequence_id":sequence,"support":support,"effect_role":role,
         "current_arm":current_arm,"control_arm":control_arm,"matched_count":count}
    passed=[]
    for key in base.METRICS+base.MAXIMA:
        x,b=number(current.get(key)),number(control.get(key))
        d=None if x is None or b is None else x-b
        row.update({"current_"+key:x,"control_"+key:b,"delta_"+key:d,
                    "strict_improved_"+key:None if d is None else d<0,
                    "zero_tolerance_nondegraded_"+key:None if d is None else d<=0})
        if key in base.METRICS:passed.append(None if d is None else d<=0)
    row["all_nine_zero_tolerance_nondegraded"]=False if False in passed else None if None in passed else True
    return row

def attribution_gate(v3_rows,coverage,effects):
    pair={x["sequence_id"]:x for x in v3_rows if x["arm"]=="PAIR_YOUNG" and x["support"]=="FULL_AVAILABLE_FROZEN"}
    cov={x["sequence_id"]:x["coverage_nondegraded"] for x in coverage if x["arm"]=="PAIR_YOUNG"}
    values=[pair.get(s,{}).get("all_metric_nondegraded") for s in SEQUENCES]+[cov.get(s) for s in SEQUENCES]
    nd=False if False in values else None if None in values else True
    qualifying=[s for s in SEQUENCES if pair.get(s,{}).get("yaw_rmse_relative_reduction") is not None and
                pair[s]["yaw_rmse_relative_reduction"]>=.05]
    A=None if nd is None else bool(nd and len(qualifying)>=2)
    full={x["sequence_id"]:x for x in effects if x["effect_role"]=="FOOT_PAIR_CONDITIONAL_EFFECT" and x["support"]=="FULL_AVAILABLE_FROZEN"}
    common={x["sequence_id"]:x for x in effects if x["effect_role"]=="FOOT_PAIR_CONDITIONAL_EFFECT" and x["support"]=="COMMON_PAIR_NULL_EXACT_KEYS"}
    attributable=[]
    for s in qualifying:
        f,c=full.get(s,{}),common.get(s,{})
        if (f.get("strict_improved_yaw_rmse_deg") is True and
            c.get("strict_improved_yaw_rmse_deg") is True and c.get("same_complete_error_keys") is True):
            attributable.append(s)
    paired_support=all(common.get(s,{}).get("same_complete_error_keys") is True for s in SEQUENCES)
    return {"all_sequence_nondegradation_vs_original_V3":nd,"A_original_V3_contract":A,
        "A_sequences_at_least_5_percent_yaw_reduction":qualifying,
        "A_qualifying_sequences_with_positive_PAIR_vs_NULL_yaw_effect":attributable,
        "PAIR_NULL_complete_common_error_support":paired_support,
        "recommend_for_human_review_under_this_contract":bool(A and len(attributable)>=2 and paired_support),
        "zero_tolerance_PAIR_NULL_nondegradation_is_reported_separately":True,
        "reset_or_scheduler_only_gain_is_not_foot_gain":True,
        "B":None,"B_reason":"NO_REGISTERED_RAW_CARRIER_FAULT_RECOVERY_CASES_IN_THIS_TRIAL",
        "integer_correctness":None,"false_fix_probability":None,"velocity_truth_metrics":None,
        "reference_is_independent_truth":False,"main_replacement_authorized":False}

def stage_metadata(stage,arms):
    stage=Path(stage).resolve()
    n=base.read_json(stage/"ALL_NATIVE_SEALED.json");e=base.read_json(stage/"EVALUATION_COMPLETE.json")
    require(n["status"]=="SEALED" and e["status"]=="COMPLETE","all outputs must reach terminal seal")
    require(e["native_seal_sha256"]==base.digest(stage/"ALL_NATIVE_SEALED.json") and
            e["plan_sha256"]==n["plan_sha256"]==base.digest(stage/"PLAN.json"),"stage seal chain")
    ids={s+"__"+a for s in SEQUENCES for a in arms}
    nr={x["run_id"]:x for x in n["records"]};er={x["run_id"]:x for x in e["records"]}
    require(set(nr)==set(er)==ids and len(n["records"])==len(e["records"])==6,"six identities/denominator")
    return stage,n,e,nr,er

def load_run(stage,native,evaluation,n,e,spec,lock,cache):
    rid=n["run_id"];sid=n["sequence_id"];arm=n["arm"]
    require(e["run_id"]==rid and e["sequence_id"]==sid and e["arm"]==arm,"run identity")
    def artifact(item,seal):
        path=Path(item["path"]);path=path if path.is_absolute() else stage/path
        require(path.resolve().is_relative_to(stage),"result outside stage")
        rel=str(path.resolve().relative_to(stage))
        require(seal["files"].get(rel)==item["sha256"],"artifact missing from seal: "+rel)
        return base.checked_artifact(item,stage,cache)
    nt=base.nav_times(artifact(n["nav"],native)) if n.get("nav") else np.array([],float)
    if n.get("nav"):
        require(len(nt)==n["output_rows"] and hashlib.sha256(np.asarray(nt,dtype="<f8").tobytes()).hexdigest()==n["time_keys_sha256"],"NAV support pin")
        artifact(n["std"],native)
    window=spec["full_window_s"]
    require(not len(nt) or window[0]<=nt[0]<=nt[-1]<=window[1],"full original window")
    result=base.read_json(artifact(e["result"],evaluation));row=result.get("row",{})
    require(row.get("run_id")==rid and row.get("sequence_id")==sid and row.get("arm")==arm,"evaluation identity")
    epin=e.get("error_series")
    if epin:
        require(result.get("error_series")==epin and result["audit"]["passed"] and row["evaluation_status"]=="COMPLETED" and
                n["status"]=="COMPLETED" and row["metrics_admitted"] is True,"evaluation qualification")
        transform=result["transform"]
        require(transform["baseline_median_m"]==spec["evaluation"]["baseline_median_m"] and
                transform["changed_columns_zero_based"]==[2,3,4] and not transform["std_transformed"],"physical evaluation point")
        require(result["capture"]["trace_sha256"]==spec["evaluation"]["reference"]["sha256"] and
                row["evaluator_sha256"]==lock["evaluator"]["sha256"] and row["evaluator_contract"]=="evaluator_contract_v3" and
                row["source_nav_sha256"]==n["nav"]["sha256"] and row["std_sha256"]==n["std"]["sha256"],"reference/evaluator/source identity")
        errors=base.errors_from_rows(base.read_csv(artifact(epin,evaluation)))
        require(np.isin(errors["time"],nt).all() and len(errors["time"])==int(row["matched_epoch_count"]),"matched exact support")
    else:
        errors=base.empty_errors();row={}
    return {"errors":errors,"row":row,"native_times":nt,"native":n,"has_error_series":bool(epin)}

def coverage_row(sid,arm,item,old,facts,window):
    nt=item["native_times"];et=item["errors"]["time"];ot=old["time"]
    missing_n=np.setdiff1d(ot,nt,assume_unique=True);missing_e=np.setdiff1d(ot,et,assume_unique=True)
    old_complete=int(facts["unmatched_epoch_count"])==0
    return {"run_id":sid+"__"+arm,"sequence_id":sid,"arm":arm,"native_status":item["native"]["status"],
        "native_output_rows":len(nt),"matched_error_rows":len(et),"unmatched_native_rows":len(nt)-len(et),
        "initial_output_gap_s":float(nt[0]-window[0]) if len(nt) else None,
        "terminal_output_gap_s":float(window[1]-nt[-1]) if len(nt) else None,
        "longest_between_output_sample_s":float(np.max(np.diff(nt))) if len(nt)>1 else None,
        "matched_per_native_output":len(et)/len(nt) if len(nt) else None,
        "v3_actual_matched_keys":len(ot),"missing_v3_actual_keys_in_new_native":len(missing_n),
        "missing_v3_actual_keys_in_new_errors":len(missing_e),
        "extra_new_native_keys":len(np.setdiff1d(nt,ot,assume_unique=True)),
        "v3_grid_is_complete_old_output":old_complete,
        "coverage_nondegraded":bool(not len(missing_n) and not len(missing_e) and len(nt) and item["has_error_series"]) if old_complete else None,
        "absolute_heading_available_coverage":None,
        "absolute_heading_coverage_reason":"PROPAGATION_IS_NOT_MEASUREMENT_AVAILABILITY",
        "integer_accuracy":None,"velocity_truth_rmse":None}

def paired_effects(sid,current,control,role,current_arm,control_arm,label):
    cm,rm=base.common_errors(current["errors"],control["errors"])
    full=delta_row(sid,"FULL_AVAILABLE_FROZEN",role,current["row"],control["row"],current_arm,control_arm)
    common=delta_row(sid,label,role,metrics(cm),metrics(rm),current_arm,control_arm,len(cm["time"]))
    common.update(current_full_matched_count=len(current["errors"]["time"]),control_full_matched_count=len(control["errors"]["time"]),
        missing_control_error_keys=len(np.setdiff1d(control["errors"]["time"],current["errors"]["time"],assume_unique=True)),
        extra_current_error_keys=len(np.setdiff1d(current["errors"]["time"],control["errors"]["time"],assume_unique=True)),
        same_complete_error_keys=bool(current["has_error_series"] and control["has_error_series"] and
            np.array_equal(current["errors"]["time"],control["errors"]["time"])))
    return [full,common]

def run(args):
    stage,n,e,nr,er=stage_metadata(args.stage,ARMS)
    previous,pn,pe,pnr,per=stage_metadata(args.baseline_stage,base.ARMS)
    plan=base.read_json(stage/"PLAN.json")
    require(plan["schema"]=="trusted_heading.clone_window_navigation.v1" and Path(plan["reused_stage"]).resolve()==previous,"clone/previous stage binding")
    for name,item in plan["reused_stage_pins"].items():
        require(Path(item["path"]).resolve()==previous/name and base.digest(previous/name)==item["sha256"],"reused metadata identity")
    lockp=ROOT/"docs/paper_rebuild/AR_V3_RESEARCH_20261006/V3_BASELINE_LOCK.json"
    factsp=ROOT/"docs/paper_rebuild/AR_V3_RESEARCH_20261006/V3_BASELINE_METRICS.csv"
    require(base.digest(lockp)==base.V3_LOCK_SHA256 and base.digest(factsp)==base.V3_FACTS_SHA256,"V3 facts/lock identity")
    lock=base.read_json(lockp);facts={x["sequence_id"]:x for x in base.read_csv(factsp)}
    require(set(facts)==set(SEQUENCES),"V3 facts sequences");specs={x["sequence_id"]:x for x in lock["sequences"]}
    cache={};v3rows=[];coverage=[];effects=[];events=[];equality=[];inputs={}
    for sid in SEQUENCES:
        spec=specs[sid];fact=facts[sid]
        require(fact["source_result_sha256"]==spec["evaluation"]["result"]["sha256"],"immutable facts value identity")
        op=spec["evaluation"]["retained_error_series"]
        oldpath=Path(op["path"].replace("<V3_ROOT>",str(Path(args.v3_root).resolve())))
        require(base.digest(oldpath)==op["sha256"],"old retained error series identity")
        old=base.errors_from_rows(base.read_csv(oldpath))
        require(len(old["time"])==int(fact["matched_epoch_count"]),"V3 matched count")
        items={arm:load_run(stage,n,e,nr[sid+"__"+arm],er[sid+"__"+arm],spec,lock,cache) for arm in ARMS}
        prior=load_run(previous,pn,pe,pnr[sid+"__CARRIER_FALLBACK"],per[sid+"__CARRIER_FALLBACK"],spec,lock,cache)
        events.append({"run_id":spec["run_id"],"sequence_id":sid,"arm":"ORIGINAL_V3",
            "support":"FULL_OLD_MATCHED_KEYS","channels":[base.event_summary(old["time"],old,c,spec["full_window_s"]) for c in base.CHANNELS]})
        for arm,item in items.items():
            errors=item["errors"];nt=item["native_times"]
            coverage.append(coverage_row(sid,arm,item,old,fact,spec["full_window_s"]))
            v3rows.append(base.comparison_row(sid,arm,"FULL_AVAILABLE_FROZEN",item["row"],fact,len(errors["time"])))
            oo,nn=base.common_errors(old,errors)
            v3rows.append(base.comparison_row(sid,arm,"COMMON_V3_MATCHED_EXACT_KEYS",metrics(nn),metrics(oo),len(oo["time"])))
            events.append({"run_id":sid+"__"+arm,"sequence_id":sid,"arm":arm,
                "support":"UNION_OF_ACTUAL_OLD_MATCHED_AND_NEW_NATIVE_KEYS",
                "channels":[base.event_summary(np.union1d(old["time"],nt),errors,c,spec["full_window_s"]) for c in base.CHANNELS]})
        for current,control,role,ca,ra,label in [
            (items["PAIR_YOUNG"],items["NULL_CLONE"],"FOOT_PAIR_CONDITIONAL_EFFECT","PAIR_YOUNG","NULL_CLONE","COMMON_PAIR_NULL_EXACT_KEYS"),
            (items["NULL_CLONE"],prior,"BACKEND_RESET_AND_EVENT_EFFECT","NULL_CLONE","REUSED_CARRIER_FALLBACK","COMMON_NULL_PREVIOUS_EXACT_KEYS"),
            (items["PAIR_YOUNG"],prior,"TOTAL_NEW_VS_PREVIOUS","PAIR_YOUNG","REUSED_CARRIER_FALLBACK","COMMON_PAIR_PREVIOUS_EXACT_KEYS")]:
            effects.extend(paired_effects(sid,current,control,role,ca,ra,label))
        # Common-three-keys additive decomposition, never a full-window replacement.
        keys=np.intersect1d(np.intersect1d(prior["errors"]["time"],items["NULL_CLONE"]["errors"]["time"]),items["PAIR_YOUNG"]["errors"]["time"])
        mm={a:metrics(base.subset_errors(x["errors"],keys)) for a,x in {"PREVIOUS":prior,**items}.items()}
        decomposition={"sequence_id":sid,"support":"COMMON_PREVIOUS_NULL_PAIR_EXACT_KEYS","effect_role":"ADDITIVE_ATTRIBUTION",
                       "matched_count":len(keys)}
        for key in base.METRICS+base.MAXIMA:
            b,z,y=(number(mm[a].get(key)) for a in ("PREVIOUS","NULL_CLONE","PAIR_YOUNG"))
            decomposition.update({"backend_delta_"+key:None if b is None or z is None else z-b,
                "pair_delta_"+key:None if z is None or y is None else y-z,
                "total_delta_"+key:None if b is None or y is None else y-b})
        effects.append(decomposition)
        zero=nr[sid+"__PAIR_YOUNG"]["foot_diagnostics"]["pair_updates"]==0
        same_nav=nr[sid+"__PAIR_YOUNG"]["nav"]["sha256"]==nr[sid+"__NULL_CLONE"]["nav"]["sha256"]
        same_std=nr[sid+"__PAIR_YOUNG"]["std"]["sha256"]==nr[sid+"__NULL_CLONE"]["std"]["sha256"]
        require(not zero or (same_nav and same_std),"zero-update NULL/PAIR identity violation")
        equality.append({"sequence_id":sid,"zero_pair_updates":zero,"nav_byte_equal":same_nav,"std_byte_equal":same_std,
                         "required_identity_passed":same_nav and same_std if zero else None})
    gate=attribution_gate(v3rows,coverage,effects)
    out=Path(args.out);out.mkdir(parents=True,exist_ok=False)
    base.write_csv(out/"V3_COMPARISONS.csv",v3rows);base.write_csv(out/"ATTRIBUTION_DIFFERENCES.csv",effects)
    base.write_csv(out/"COVERAGE.csv",coverage);base.write_csv(out/"ZERO_UPDATE_IDENTITY.csv",equality)
    result={"schema":"trusted_heading.clone_navigation_comparison.v1",
        "inputs":{"clone_plan_sha256":base.digest(stage/"PLAN.json"),"clone_native_seal_sha256":base.digest(stage/"ALL_NATIVE_SEALED.json"),
                  "clone_evaluation_complete_sha256":base.digest(stage/"EVALUATION_COMPLETE.json"),
                  "reused_plan_sha256":base.digest(previous/"PLAN.json"),"reused_native_seal_sha256":base.digest(previous/"ALL_NATIVE_SEALED.json"),
                  "reused_evaluation_complete_sha256":base.digest(previous/"EVALUATION_COMPLETE.json"),
                  "v3_lock_sha256":base.digest(lockp),"v3_facts_sha256":base.digest(factsp)},
        "source_sha256":base.digest(Path(__file__)),"pure_metrics_source_sha256":base.digest(Path(base.__file__)),
        "gate":gate,"events":events,"zero_update_identity":equality,"reference_reads":0,"solver_calls":0,"evaluator_calls":0,
        "scope":"DERIVED_SEALED_EVALUATION_ONLY","missing_metrics_are_NA":True,
        "common_support_not_a_full_window_substitute":True,"foot_effect_is_conditional_working_model_not_independence_proof":True}
    (out/"COMPARISON.json").write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)+"\n")
    return result

if __name__=="__main__":
    p=argparse.ArgumentParser()
    for name in ("stage","baseline-stage","v3-root","out"):p.add_argument("--"+name,required=True)
    run(p.parse_args())
