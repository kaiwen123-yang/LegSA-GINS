"""Read-only selection geometry/support diagnostic; no observed y or N is used."""
from pathlib import Path
from collections import Counter,defaultdict
from dataclasses import asdict,replace
import argparse,csv,hashlib,json,subprocess,time,os
import numpy as np
from legsa_gins.paper_rebuild.carrier_phase import partial
from legsa_gins.paper_rebuild.carrier_phase.multignss import MultiGnssEpoch,GroupDD
from legsa_gins.paper_rebuild.horizontal_literature.shared_raw_backend import SignalIdentity

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def write_json(path,obj):
    with path.open("x") as f:json.dump(obj,f,indent=2,allow_nan=False)
def write_csv(path,rows):
    with path.open("x",newline="") as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator="\n")
        writer.writeheader();writer.writerows(rows)
def forbidden(*args,**kwargs):raise AssertionError("NO_SEARCH_OR_SCIENTIFIC_GATE_CALL_AUTHORIZED")
partial.solve_temporal=forbidden;partial.solve_partial=forbidden


def load_geometry(root,row,family):
    entry=row["families"].get(family,{})
    if entry.get("status")!="BUILT":raise ValueError("MODEL_UNAVAILABLE")
    with np.load(root/entry["file"]) as z:
        # Deliberately NEVER access z['y']: diagnostic cannot use phase/code residuals.
        a,b,q=(z[key].copy() for key in ("A","B","Q"))
    y=np.zeros(a.shape[0]);labels=tuple(entry["ambiguity_labels"]);m=len(labels)
    groups=[];offset=0
    for g in entry["groups"]:
        pivot=SignalIdentity(**g["pivot"]);satellites=tuple(SignalIdentity(**s) for s in g["satellites"])
        cc=tuple(range(offset,offset+len(satellites)));rr=cc+tuple(i+m for i in cc)
        groups.append(GroupDD(tuple(g["key"]),pivot,satellites,y[list(rr)],a[np.ix_(rr,cc)],
            b[list(rr)],q[np.ix_(rr,rr)],tuple(labels[i] for i in cc),rr,cc))
        offset+=len(satellites)
    if offset!=m:raise ValueError("GROUP_DIMENSION_MISMATCH")
    return MultiGnssEpoch(float(row["time_s"]),y,a,b,q,labels,tuple(groups),entry["metadata"])


def geometry(model,labels):
    support=partial.partial_support_rows(model,labels)
    rr=list(support.rows_retained);phase=list(support.phase_rows_retained)
    rank=int(np.linalg.matrix_rank(model.B[phase])) if phase else 0
    result={"complete_selected":not support.missing_selected_labels,"missing_count":len(support.missing_selected_labels),
        "phase_rows":len(phase),"phase_rank":rank,"retained_rows":len(rr),
        "supported":not support.missing_selected_labels and len(phase)>=4 and rank==3,
        "sigma3d_m":None,"sigma_max_axis_m":None,"logdet_Cb_m6":None}
    cb=None
    if result["supported"]:
        q=model.Q[np.ix_(rr,rr)];w=np.linalg.solve(np.linalg.cholesky(q),model.B[rr])
        _,s,vt=np.linalg.svd(w,full_matrices=False)
        if s[-1]<=np.finfo(float).eps*max(w.shape)*s[0]:raise ValueError("FULL_BASELINE_RANK_FAILURE")
        cb=(vt.T/(s*s))@vt
        result.update(sigma3d_m=float(np.sqrt(np.trace(cb))),
            sigma_max_axis_m=float(np.sqrt(np.linalg.eigvalsh(cb)[-1])),
            logdet_Cb_m6=float(np.linalg.slogdet(cb)[1]))
    return result,cb


def distribution(values):
    values=np.asarray([v for v in values if v is not None],float)
    return {"n":len(values),"median":float(np.median(values)) if len(values) else None,
        "p95":float(np.quantile(values,.95)) if len(values) else None,
        "min":float(values.min()) if len(values) else None,"max":float(values.max()) if len(values) else None}


def run(a):
    plan=json.loads((a.trial/"PLAN.json").read_text());summary=json.loads(a.summary.read_text())
    contract=summary["input_contract"];family=contract["family"]
    if sha(a.trial/"PLAN.json")!=contract["model_plan_sha256"]:raise ValueError("PLAN_IDENTITY_CHANGED")
    partial_path=a.code/"src/legsa_gins/paper_rebuild/carrier_phase/partial.py"
    if sha(partial_path)!=contract["source_files"][str(partial_path.relative_to(a.code))]:raise ValueError("FROZEN_SELECTION_RULE_CHANGED")
    policy=partial.PartialPolicy(**contract["partial_policy"])
    assert policy.min_ambiguities==4 and policy.max_ambiguities==8
    cases=sorted(a.frontend.joinpath("cases").glob("partial_*.json"))
    assert len(cases)==120==summary["modes"]["partial"]["cases"]
    job={"execution_commit":subprocess.check_output(["git","rev-parse","HEAD"],cwd=a.code,text=True).strip(),
      "trial":str(a.trial),"plan_sha256":sha(a.trial/"PLAN.json"),"summary":str(a.summary),
      "partial_source_sha256":sha(partial_path),"script_sha256":sha(__file__),"sizes":[4,6,8],
      "base_policy":asdict(policy),"family":family,"windows":120,
      "arrays_read":["A","B","Q"],"y_accessed":False,"synthetic_y_placeholder":True,
      "source_reference_reads":0,"new_CILS_calls":0,"admission_calls":0,"navigation_calls":0,
      "conditional_covariance":"free baseline given hypothetical correct selected N; all code + covered phase rows; principal Q",
      "future_support_is_integer_success":False,"selection_uses_future":False}
    write_json(a.output/"CONTRACT.json",job)
    all_windows=[];all_epochs=[];selection_records=[];group_counts=Counter();group_windows=Counter()
    paired=[];match8=0;nested=0;cov_order_checks=0
    for number,path in enumerate(cases,1):
        original=json.loads(path.read_text());start=float(original["window_start_s"])
        assert original["input_contract"]==job["plan_sha256"]
        rows=[r for r in plan["records"] if start<=r["time_s"]<start+2.]
        if len(rows)!=10:raise ValueError("ORIGINAL_FIXED_WINDOW_MISSING")
        select=tuple(load_geometry(a.trial,r,family) for r in rows[:5])
        # Select all three policies BEFORE even opening future model arrays.
        choices={n:partial.preselect_partial_labels(select,replace(policy,max_ambiguities=n)) for n in (4,6,8)}
        if choices[8].selected_labels!=tuple(original["subset_selection"]["selected_labels"]):
            raise ValueError("MAX8_LABEL_PARITY_FAILED")
        match8+=1
        assert choices[8].selected_labels[:len(choices[6].selected_labels)]==choices[6].selected_labels
        assert choices[6].selected_labels[:len(choices[4].selected_labels)]==choices[4].selected_labels
        nested+=1
        future=[]
        for row in rows[5:]:
            try:future.append(load_geometry(a.trial,row,family))
            except ValueError:future.append(None)
        window_metrics={}
        for size,choice in choices.items():
            selected=choice.selected_labels
            selection_records.append({"case":original["case_id"],"max_ambiguities":size,
                "status":choice.status,"selected_labels":selected,"group_counts":choice.selected_group_counts})
            for key,count in choice.selected_group_counts:
                group_counts[(size,*key)]+=count;group_windows[(size,*key)]+=1
            metrics=[]
            for k,model in enumerate((*select,*future)):
                phase="selection" if k<5 else "future"
                if model is None:
                    value={"complete_selected":False,"missing_count":len(selected),"phase_rows":0,"phase_rank":0,
                        "retained_rows":0,"supported":False,"sigma3d_m":None,"sigma_max_axis_m":None,"logdet_Cb_m6":None};cb=None
                else:value,cb=geometry(model,selected)
                epoch={"case":original["case_id"],"start_s":start,"max_ambiguities":size,"part":phase,
                    "slot":k%5,"time_s":rows[k]["time_s"],"model_available":model is not None,**value}
                all_epochs.append(epoch);metrics.append((epoch,cb))
            window_metrics[size]=metrics
            sel=[x[0] for x in metrics[:5]];fut=[x[0] for x in metrics[5:]]
            failed=[r for r in fut if not r["supported"]]
            all_windows.append({"case":original["case_id"],"start_s":start,"max_ambiguities":size,
                "selection_status":choice.status,"selected_count":len(selected),
                "selected_group_counts":json.dumps({":".join(map(str,k)):v for k,v in choice.selected_group_counts},sort_keys=True),
                "future_all_models":all(r["model_available"] for r in fut),
                "future_all_selected_labels":all(r["complete_selected"] for r in fut),
                "future_all_phase_rank":all(r["phase_rows"]>=4 and r["phase_rank"]==3 for r in fut),
                "future_all_supported":choice.ready and all(r["supported"] for r in fut),
                "future_supported_slots":sum(r["supported"] for r in fut),
                "future_first_failure_s":failed[0]["time_s"] if failed else None,
                "selection_worst_sigma3d_m":max((r["sigma3d_m"] for r in sel if r["sigma3d_m"] is not None),default=None),
                "selection_worst_sigma_max_axis_m":max((r["sigma_max_axis_m"] for r in sel if r["sigma_max_axis_m"] is not None),default=None),
                "future_worst_sigma3d_m":max((r["sigma3d_m"] for r in fut),default=None) if all(r["supported"] for r in fut) else None})
        for k in range(10):
            if not all(window_metrics[n][k][0]["supported"] for n in (4,6,8)):continue
            reference=window_metrics[8][k][0]
            for size in (4,6):
                row,cb=window_metrics[size][k];cb8=window_metrics[8][k][1]
                minimum=float(np.linalg.eigvalsh(cb-cb8)[0]);scale=max(float(np.linalg.norm(cb)),1e-20)
                if minimum< -1e-8*scale:raise ValueError("NESTED_PRINCIPAL_COVARIANCE_ORDER_VIOLATION")
                cov_order_checks+=1
                paired.append({"case":original["case_id"],"max_ambiguities":size,"part":row["part"],"time_s":row["time_s"],
                    "sigma3d_ratio_to8":row["sigma3d_m"]/reference["sigma3d_m"],
                    "sigma_max_axis_ratio_to8":row["sigma_max_axis_m"]/reference["sigma_max_axis_m"],
                    "min_eig_Cb_difference_m2":minimum})
        if number%20==0:print(json.dumps({"windows_done":number,"total":120}),flush=True)
    write_csv(a.output/"WINDOWS.csv",all_windows);write_csv(a.output/"EPOCH_GEOMETRY.csv",all_epochs)
    write_csv(a.output/"MATCHED_GEOMETRY_RATIOS.csv",paired)
    groups=[{"max_ambiguities":k[0],"gnss_id":k[1],"signal_id":k[2],"freq_id":k[3],
      "selected_dd_count":v,"windows_with_group":group_windows[k]} for k,v in sorted(group_counts.items())]
    write_csv(a.output/"SELECTION_GROUP_COUNTS.csv",groups)
    write_json(a.output/"SELECTED_LABELS.json",selection_records)
    summaries={}
    for size in (4,6,8):
        w=[r for r in all_windows if r["max_ambiguities"]==size]
        summaries[str(size)]={"windows":len(w),"ready":sum(r["selection_status"]=="READY" for r in w),
          "future_all_selected_labels":sum(r["future_all_selected_labels"] for r in w),
          "future_all_phase_rank":sum(r["future_all_phase_rank"] for r in w),
          "future_all_supported":sum(r["future_all_supported"] for r in w),
          "future_supported_slots":sum(r["future_supported_slots"] for r in w),
          "selection_worst_sigma3d_m":distribution(r["selection_worst_sigma3d_m"] for r in w),
          "selection_worst_sigma_max_axis_m":distribution(r["selection_worst_sigma_max_axis_m"] for r in w)}
        if size<8:
            for part in ("selection","future"):
                p=[r for r in paired if r["max_ambiguities"]==size and r["part"]==part]
                summaries[str(size)][part+"_matched_sigma3d_ratio_to8"]=distribution(r["sigma3d_ratio_to8"] for r in p)
                summaries[str(size)][part+"_matched_max_axis_ratio_to8"]=distribution(r["sigma_max_axis_ratio_to8"] for r in p)
    masks={n:{r["case"] for r in all_windows if r["max_ambiguities"]==n and r["future_all_supported"]} for n in (4,6,8)}
    report={**job,"max8_original_label_parity":match8,"nested_subset_windows":nested,
      "nested_conditional_covariance_order_checks":cov_order_checks,"results":summaries,
      "paired_window_support":{"4_gain_over8":len(masks[4]-masks[8]),"4_loss_vs8":len(masks[8]-masks[4]),
         "6_gain_over8":len(masks[6]-masks[8]),"6_loss_vs8":len(masks[8]-masks[6]),
         "all_three_supported_windows":len(masks[4]&masks[6]&masks[8])},
      "warnings":["future support is not integer correctness or admission success",
        "geometry covariance is conditional on hypothetical true N and working Q; no integer/anchor/phase fault error budget",
        "same recorded windows and nested subsets are paired; this is not independent statistical replication",
        "all diagnostics retained; no new candidate search or best-output selection performed"]}
    write_json(a.output/"SUMMARY.json",report)
    print(json.dumps(report["results"],indent=2),flush=True)

if __name__=="__main__":
    if os.uname().sysname!="Linux":raise RuntimeError("run geometry diagnostics in Ubuntu WSL")
    p=argparse.ArgumentParser()
    for key in ("code","trial","frontend","summary","output"):p.add_argument("--"+key,type=Path,required=True)
    run(p.parse_args())
