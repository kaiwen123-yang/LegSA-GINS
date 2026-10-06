#!/usr/bin/env python3
"""Zero-CILS covariance mechanism replay with producer/checker truth separation."""
from __future__ import annotations
import argparse,hashlib,json,csv,importlib.util
from dataclasses import asdict,is_dataclass
from pathlib import Path
import numpy as np

VARIANTS=("CLEAN_REUSED","RHO08_REUSED_SELECTION_DEPENDENT","RHO08_NEW_INDEPENDENT_FUTURE")
PREFIX="CARRIER_JOINT_FUTURE_V1|"
RHO=.8
LENGTH=.35
REGISTRATION_COMMIT="d7887ed"

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text())
def serial(x):
    if is_dataclass(x):return serial(asdict(x))
    if isinstance(x,np.ndarray):return x.tolist()
    if isinstance(x,np.generic):return x.item()
    if isinstance(x,Path):return str(x)
    if isinstance(x,dict):return {str(k):serial(v) for k,v in x.items()}
    if isinstance(x,(tuple,list)):return [serial(v) for v in x]
    return x
def emit(p,v):
    with Path(p).open("x",encoding="utf-8") as f:json.dump(serial(v),f,indent=2,allow_nan=False);f.write("\n")
def future_seed(case_id):return int(hashlib.sha256((PREFIX+case_id).encode("utf-8")).hexdigest()[:16],16)
def temporal_covariance(epoch_Q,rho):
    q=np.asarray(epoch_Q,float)
    if not np.isfinite(rho) or abs(rho)>=1:raise ValueError("stationary AR1 requires abs(rho)<1")
    return np.kron(rho**np.abs(np.arange(5)[:,None]-np.arange(5)[None,:]),q)
def ar1_coefficients(rho,*,selection_linked):
    if selection_linked:
        out=np.zeros((5,6));out[0,0]=rho;out[0,1]=np.sqrt(1-rho*rho)
        for k in range(1,5):out[k]=rho*out[k-1];out[k,k+1]=np.sqrt(1-rho*rho)
    else:
        out=np.zeros((5,5));out[0,0]=1.
        for k in range(1,5):out[k]=rho*out[k-1];out[k,k]=np.sqrt(1-rho*rho)
    return out
def independent_future_noise(case_id,epoch_Q):
    q=np.asarray(epoch_Q,float);np.linalg.cholesky(q)
    innovations=np.random.default_rng(future_seed(case_id)).normal(size=(5,len(q)))
    latent=ar1_coefficients(RHO,selection_linked=False)@innovations
    return latent@np.linalg.cholesky(q).T,innovations,latent
def source_pins(code):
    ps=list((code/"src/legsa_gins/paper_rebuild/carrier_phase").glob("*.py"))
    ps += [code/"scripts/paper_rebuild/carrier_phase/followup_covariance.py",
           code/"scripts/paper_rebuild/carrier_phase/robustness_trial.py",
           code/"src/legsa_gins/paper_rebuild/horizontal_literature/ext01_clambda.py",
           code/"src/legsa_gins/paper_rebuild/horizontal_literature/shared_raw_backend.py"]
    return {str(p.relative_to(code)):sha(p) for p in sorted(ps)}
def block(v):
    from legsa_gins.paper_rebuild.carrier_phase.temporal import EpochBlock
    return EpochBlock(v["time_s"],np.array(v["y"]),np.array(v["A"]),np.array(v["B"]),
                      np.array(v["Q"]),tuple(v["ambiguity_labels"]),v["metadata"])
def check_original(stage):
    p=read(stage/"PLAN.json");r=read(stage/"EXECUTION_REGISTRATION.json")
    s=read(stage/"SELECTION_SEAL.json");a=read(stage/"ADMISSION_SEAL.json")
    assert sha(stage/"PLAN.json")==r["plan_sha256"]==s["plan_sha256"]
    assert sha(stage/"EXECUTION_REGISTRATION.json")==s["registration_sha256"]==a["registration_sha256"]
    assert sha(stage/"SELECTION_SEAL.json")==a["selection_seal_sha256"]
    for x in (s,a):
        assert all(sha(stage/k)==v for k,v in x["files"].items())
    return p

def produce(stage,output):
    """Explicitly authorized producer reads truth to generate means, never to fit."""
    plan=check_original(stage)
    assert len(plan["cases"])==72 and len({r["case_id"] for r in plan["cases"]})==72
    output.mkdir(parents=True,exist_ok=False)
    for name in ("fresh_inputs","producer_noise"): (output/name).mkdir()
    manifest={};truth_reads=0;input_hashes={}
    for case in plan["cases"]:
        futpath=stage/case["future_inputs_file"];truthpath=stage/case["truth_file"]
        assert sha(futpath)==case["future_inputs_sha256"] and sha(truthpath)==case["truth_sha256"]
        original=read(futpath);truth=read(truthpath)["truth"];truth_reads+=1
        clean=original["conditions"]["CLEAN"];q=np.asarray(clean[0]["Q"])
        assert all(np.array_equal(b["Q"],q) for b in clean)
        noise,innovations,latent=independent_future_noise(case["case_id"],q)
        true_n=np.asarray(truth["selection_integer"]);true_b=np.asarray(truth["conditions"]["CLEAN"]["baseline_m"])
        future=[]
        for k,old in enumerate(clean):
            v=dict(old)
            v["y"]=np.asarray(old["A"])@true_n+np.asarray(old["B"])@true_b[k]+noise[k]
            meta=dict(v["metadata"]);meta["noise_provenance"]="independent future-only AR1 producer; no selection noise"
            v["metadata"]=meta;future.append(v)
        out=output/"fresh_inputs"/(case["case_id"]+".json")
        emit(out,{"case":case,"blocks":future,
                  "provenance":{"seed":future_seed(case["case_id"]),"seed_rule":PREFIX,
                    "rho":RHO,"first_latent_independent_standard_normal":True,
                    "selection_noise_used":False,"Q_estimated_from_samples":False,
                    "truth_used_by_producer_only":True}})
        npz=output/"producer_noise"/(case["case_id"]+".npz")
        np.savez_compressed(npz,innovations=innovations,latent=latent,noise_m=noise)
        manifest[str(out.relative_to(output))]=sha(out);manifest[str(npz.relative_to(output))]=sha(npz)
        input_hashes[case["future_inputs_file"]]=sha(futpath);input_hashes[case["truth_file"]]=sha(truthpath)
    emit(output/"PRODUCER_SEAL.json",{"files":manifest,"truth_file_reads_by_producer":truth_reads,
         "new_future_realizations":72,"new_CILS_calls":0,"registration_commit":REGISTRATION_COMMIT,
         "generator_sha256":sha(__file__),"input_hashes":input_hashes,
         "source_PLAN_sha256":sha(stage/"PLAN.json"),"seed_rule":PREFIX+" + exact case_id; first 16 hex -> int",
         "stationary_future_Q":"rho^abs(i-j) kron original epoch Q","selection_noise_used":False})
    print(json.dumps({"producer_truth_reads":truth_reads,"new_future":72,"CILS":0}))

def prepare(stage,output,code):
    plan=check_original(stage);producer=read(output/"PRODUCER_SEAL.json")
    assert producer["source_PLAN_sha256"]==sha(stage/"PLAN.json")
    assert all(sha(output/k)==v for k,v in producer["files"].items())
    replay=[{"case_id":r["case_id"],"variant":v} for r in plan["cases"] for v in VARIANTS]
    selected_hashes={f"selection_results/{r['case_id']}.json":sha(stage/"selection_results"/(r["case_id"]+".json")) for r in plan["cases"]}
    future_hashes={r["future_inputs_file"]:sha(stage/r["future_inputs_file"]) for r in plan["cases"]}
    old_admission_hashes={f"admission_results/{r['case_id']}__{c}.json":sha(stage/"admission_results"/(r["case_id"]+"__"+c+".json")) for r in plan["cases"] for c in ("CLEAN","TEMPORAL_RHO08")}
    registration={"stage":"CARRIER_ROBUSTNESS_COVARIANCE_FOLLOWUP","source_pins":source_pins(code),
          "producer_seal_sha256":sha(output/"PRODUCER_SEAL.json"),
          "original_plan_sha256":sha(stage/"PLAN.json"),"selected_hashes":selected_hashes,
          "original_future_hashes":future_hashes,"original_admission_hashes":old_admission_hashes,
          "joint_calls":216,"new_IID_calls":72,"old_IID_reused":144,"CILS_calls":0,
          "replays":replay,"alpha_total":.01,"threshold_adjustments":0,
          "sensitivity_cases":[next(r["case_id"] for r in plan["cases"] if r["split"]=="CALIBRATION" and r["layer"]==layer) for layer in ("M3","M4","M9_MULTIFREQUENCY")],
          "provenance":"Post-result mechanism extension; all reused cohort labels are developmental, not new heldout cohorts.",
          "conditions":{"CLEAN_REUSED":{"rho":0.,"selection_independent":True,"IID_source":"reuse sealed CLEAN"},
             "RHO08_REUSED_SELECTION_DEPENDENT":{"rho":.8,"selection_independent":False,"IID_source":"reuse sealed TEMPORAL_RHO08","policy":"statistics only; force UNRESOLVED_SELECTION_DEPENDENCE"},
             "RHO08_NEW_INDEPENDENT_FUTURE":{"rho":.8,"selection_independent":True,"IID_source":"new same-future misspecified independence comparator"}},
          "Q_provenance":"Analytic generator Q only, not inferred from noise samples, truth residuals, accepted cases or failures.",
          "old_rho_generator_verification":"Future recursion uses last selection noise: coefficients [.8, .6] then AR1. Future marginal Toeplitz, cross-cov to last selection = [.8,.8^2,...,.8^5] tensor epoch Q.",
          "truth_separation":"Producer reads truth solely for mean generation; checker zero truth reads; final label evaluation occurs only after CHECKER_SEAL."}
    emit(output/"FOLLOWUP_PLAN.json",registration)
    return registration

def checked_plan(stage,output,code):
    p=read(output/"FOLLOWUP_PLAN.json")
    assert sha(stage/"PLAN.json")==p["original_plan_sha256"]
    assert source_pins(code)==p["source_pins"]
    assert sha(output/"PRODUCER_SEAL.json")==p["producer_seal_sha256"]
    for category in ("selected_hashes","original_future_hashes","original_admission_hashes"):
        assert all(sha(stage/k)==v for k,v in p[category].items())
    return p

def frozen_pair(selected,case_id):
    from legsa_gins.paper_rebuild.carrier_phase.admission import FrozenCandidate
    labels=selected["labels"];active=tuple(selected["active_labels"])
    result=selected.get("result",{})
    if (not labels or len(set(labels))!=len(labels)
        or result.get("certificate",{}).get("global_optimum_certified") is not True
        or any(not isinstance(result.get(name),dict) or len(result[name].get("ambiguity",[]))!=len(labels)
               for name in ("best","second"))):
        raise ValueError("certified two-candidate labels/dimensions required before zip")
    return tuple(FrozenCandidate.from_mapping(name,selected["selected_at"],
             dict(zip(labels,selected["result"][name]["ambiguity"])),active,case_id) for name in ("best","second"))
def old_baselines(decision):
    from legsa_gins.paper_rebuild.horizontal_literature.ext01_clambda import constrained_baseline
    out=[]
    for ep in decision.epochs:
        f=ep.primary
        out.append(None if f is None else constrained_baseline(np.array(f.baseline_center_m),np.array(f.baseline_covariance_m2),LENGTH).baseline)
    return out
def joint_baselines(decision):
    from legsa_gins.paper_rebuild.horizontal_literature.ext01_clambda import constrained_baseline
    if decision.primary is None:return []
    return [constrained_baseline(np.array(g.baseline_center_m),np.array(g.baseline_covariance_m2),LENGTH).baseline for g in decision.primary.length_gates]

def persistent_map(blocks):
    from legsa_gins.paper_rebuild.carrier_phase.faults import PhaseFaultMap,PhaseFaultHypothesis
    from legsa_gins.paper_rebuild.carrier_phase.observations import SignalIdentity
    templates=blocks[0].metadata["phase_templates"];names=[t["signal_id"] for t in templates]
    assert all([t["signal_id"] for t in b.metadata["phase_templates"]]==names for b in blocks)
    matrix=np.vstack([np.column_stack([t["direction_m_per_cycle"] for t in b.metadata["phase_templates"]]) for b in blocks])
    groups={g["group_id"]:g for g in blocks[0].metadata["groups"]};hyp=[]
    for t in templates:
        g=groups[t["group_id"]];pivot=t["kind"]=="PIVOT"
        sv=19 if pivot else g["target_ids"].index(t["signal_id"].split(":",1)[1])+1
        signal=SignalIdentity(g["gnss_id"],sv,g["sig_id"],0);pivot_id=SignalIdentity(g["gnss_id"],19,g["sig_id"],0)
        affected=tuple(blocks[0].ambiguity_labels[j] for j in range(len(blocks[0].ambiguity_labels))
                 if np.any(blocks[0].A[np.asarray(t["direction_m_per_cycle"])!=0,j]!=0))
        hyp.append(PhaseFaultHypothesis(t["signal_id"],signal,(g["gnss_id"],g["sig_id"],0),
                   pivot_id,pivot,"sd",g["wavelength_m"],affected,"synthetic_rx1arc0_rx2arc0"))
    return PhaseFaultMap(matrix,tuple(hyp),tuple(range(len(matrix))),len(matrix))

def check(stage,output,code):
    from legsa_gins.paper_rebuild.carrier_phase.joint_admission import JointCausalAdmissionSession,JointAdmissionConfig
    from legsa_gins.paper_rebuild.carrier_phase.admission import CausalAdmissionSession,AdmissionConfig
    from legsa_gins.paper_rebuild.carrier_phase.temporal import assemble_epochs
    from legsa_gins.paper_rebuild.carrier_phase.faults import fixed_integer_gls
    from legsa_gins.paper_rebuild.carrier_phase.sensitivity import analyze_phase_fault_sensitivity
    p=checked_plan(stage,output,code);oldplan=read(stage/"PLAN.json")
    for name in ("joint_results","new_iid_results","sensitivity_results"):(output/name).mkdir()
    files={};counter=0;iid_new=0
    for case in oldplan["cases"]:
        checked_plan(stage,output,code)
        selected=read(stage/"selection_results"/(case["case_id"]+".json"))
        assert selected["result"]["certificate"]["global_optimum_certified"] is True
        pair=frozen_pair(selected,case["case_id"])
        old_future=read(stage/case["future_inputs_file"])["conditions"]
        for variant in VARIANTS:
            if variant=="RHO08_NEW_INDEPENDENT_FUTURE":
                fresh=output/"fresh_inputs"/(case["case_id"]+".json")
                producer=read(output/"PRODUCER_SEAL.json")
                assert sha(fresh)==producer["files"][str(fresh.relative_to(output))]
                values=read(fresh)["blocks"]
            else:
                values=old_future["CLEAN" if variant=="CLEAN_REUSED" else "TEMPORAL_RHO08"]
            blocks=[block(x) for x in values];q=blocks[0].Q
            assert all(np.array_equal(x.Q,q) for x in blocks)
            cfg=p["conditions"][variant]
            futureQ=temporal_covariance(q,cfg["rho"])
            session=JointCausalAdmissionSession(*pair,future_covariance=futureQ,
                    covariance_source_id="REGISTERED_GENERATOR_"+variant,
                    config=JointAdmissionConfig(selection_independent_working_model=cfg["selection_independent"]))
            for b in blocks:session.observe(b)
            decision=session.finalize();counter+=1
            out=output/"joint_results"/(case["case_id"]+"__"+variant+".json")
            emit(out,{"case":case,"variant":variant,"decision":decision,
                      "marginal_sphere_baselines_m":joint_baselines(decision),
                      "baselines_are_joint_sphere_optimum":False,
                      "selected_result_sha256":sha(stage/"selection_results"/(case["case_id"]+".json")),
                      "input_truth_reads":0,"integer_search_calls":0})
            files[str(out.relative_to(output))]=sha(out)
            if variant=="RHO08_NEW_INDEPENDENT_FUTURE":
                iid=CausalAdmissionSession(*pair,AdmissionConfig())
                for b in blocks:iid.observe(b)
                d=iid.finalize();iid_new+=1
                io=output/"new_iid_results"/(case["case_id"]+".json")
                emit(io,{"case":case,"decision":d,"primary_sphere_baselines_m":old_baselines(d),
                         "comparator_assumption":"Intentionally assumes epoch independence on the same correlated fresh future.",
                         "actual_epoch_independence":False,"actual_selection_independence":True,
                         "truth_file_reads":0,"integer_search_calls":0})
                files[str(io.relative_to(output))]=sha(io)
        if case["case_id"] in p["sensitivity_cases"]:
            blocks=[block(x) for x in old_future["CLEAN"]]
            temporal=assemble_epochs(blocks,length_m=LENGTH)
            fit=fixed_integer_gls(temporal,pair[0].integers)
            fmap=persistent_map(blocks)
            sensitivity=analyze_phase_fault_sensitivity(fit,fmap)
            so=output/"sensitivity_results"/(case["case_id"]+".json")
            emit(so,{"case":case,"scope":"CLEAN future geometry/Q only; no truth and no selection by residual size.",
                     "sensitivity":sensitivity,"signal_hypotheses":fmap.hypotheses,
                     "truth_file_reads":0,"integer_search_calls":0})
            files[str(so.relative_to(output))]=sha(so)
        print(json.dumps({"case_complete":case["case_id"],"joint_calls":counter,"new_IID_calls":iid_new}),flush=True)
    checked_plan(stage,output,code)
    assert counter==216 and iid_new==72
    emit(output/"CHECKER_SEAL.json",{"files":files,"joint_calls":counter,"new_IID_calls":iid_new,
           "old_IID_reused":144,"sensitivity_models":3,"checker_truth_file_reads":0,
           "CILS_calls":0,"plan_sha256":sha(output/"FOLLOWUP_PLAN.json"),
           "producer_seal_sha256":sha(output/"PRODUCER_SEAL.json")})

def angle_summary(predicted,truth):
    if not predicted:return None,None
    b=np.asarray([x for x in predicted if x is not None])
    if len(b)!=len(truth):return None,None
    dot=np.sum(b*np.asarray(truth),axis=1)/LENGTH**2
    angles=np.rad2deg(np.arccos(np.clip(dot,-1.,1.)))
    return float(np.sqrt(np.mean(angles**2))),float(np.max(angles))

def summarize(stage,output,code,docs):
    from collections import Counter
    p=checked_plan(stage,output,code);seal=read(output/"CHECKER_SEAL.json")
    assert sha(output/"FOLLOWUP_PLAN.json")==seal["plan_sha256"]
    assert all(sha(output/k)==v for k,v in seal["files"].items())
    old=read(stage/"PLAN.json");rows=[];truth_reads=0
    for case in old["cases"]:
        truthpath=stage/case["truth_file"];assert sha(truthpath)==case["truth_sha256"]
        truth=read(truthpath)["truth"];truth_reads+=1
        selected=read(stage/"selection_results"/(case["case_id"]+".json"))
        correct=bool(np.array_equal(selected["result"]["best"]["ambiguity"],truth["selection_integer"]))
        for variant in VARIANTS:
            joint=read(output/"joint_results"/(case["case_id"]+"__"+variant+".json"))
            jd=joint["decision"]
            if variant=="RHO08_NEW_INDEPENDENT_FUTURE":
                iid=read(output/"new_iid_results"/(case["case_id"]+".json"))
            else:
                c="CLEAN" if variant=="CLEAN_REUSED" else "TEMPORAL_RHO08"
                iid=read(stage/"admission_results"/(case["case_id"]+"__"+c+".json"))
            idc=iid["decision"]
            jangle,jmax=angle_summary(joint["marginal_sphere_baselines_m"],truth["conditions"]["CLEAN"]["baseline_m"])
            iangle,imax=angle_summary(iid["primary_sphere_baselines_m"],truth["conditions"]["CLEAN"]["baseline_m"])
            rows.append({"case_id":case["case_id"],"original_split":case["split"],"layer":case["layer"],
              "variant":variant,"integer_correct":correct,"joint_status":jd["status"],
              "joint_shadow_accepted":jd["shadow_accepted"],"iid_status":idc["status"],
              "iid_shadow_accepted":idc["shadow_accepted"],
              "joint_selection_independence":jd["selection_independent_working_model"],
              "joint_residual_cost":jd["primary"]["residual_cost"] if jd["primary"] else None,
              "joint_residual_df":jd["primary"]["residual_df"] if jd["primary"] else None,
              "joint_residual_pass":jd["primary"]["residual_pass"] if jd["primary"] else None,
              "joint_length_pass":jd["primary"]["length_pass"] if jd["primary"] else None,
              "iid_residual_cost":idc["primary"]["residual_cost"] if idc["primary"] else None,
              "joint_marginal_projection_angle_rmse_deg":jangle,"joint_marginal_projection_angle_max_deg":jmax,
              "iid_sphere_angle_rmse_deg":iangle,"iid_sphere_angle_max_deg":imax,
              "joint_false_fix_probability":None,"accepted_integer_measurement":False})
    def write_csv(path,records):
        with path.open("x",encoding="utf-8",newline="") as f:
            writer=csv.DictWriter(f,fieldnames=list(records[0]),lineterminator="\n");writer.writeheader();writer.writerows(records)
    write_csv(output/"FOLLOWUP_RESULTS.csv",rows)
    sensitivity_rows=[]
    for case_id in p["sensitivity_cases"]:
        r=read(output/"sensitivity_results"/(case_id+".json"))
        hyp={x["key"]:x for x in r["signal_hypotheses"]}
        for score in r["sensitivity"]["scores"]:
            h=hyp[score["key"]]
            sensitivity_rows.append({"case_id":case_id,"layer":r["case"]["layer"],
              "signal":score["key"],"pivot":h["is_pivot"],"status":score["status"],
              "wavelength_m":h["wavelength_m"],"information_cycles_inverse2":score["information_cycles_inverse2"],
              "mdb_cycles":score["mdb_cycles"],"mdb_max_epoch_bias_norm_m":score["mdb_max_epoch_bias_norm_m"],
              "mdb_per_epoch_bias_norm_m":json.dumps(score["mdb_per_epoch_bias_norm_m"]),
              "baseline_gain_m_per_cycle":json.dumps(score["baseline_gain_m_per_cycle"]),
              "per_epoch_gain_norm_m_per_cycle":json.dumps(score["per_epoch_gain_norm_m_per_cycle"]),
              "unbounded":score["detectable_amplitude_unbounded"],
              "observational_aliases":json.dumps(score["observational_aliases"])})
    assert len(sensitivity_rows)==21
    write_csv(output/"SYNTHETIC_SENSITIVITY.csv",sensitivity_rows)
    groups={}
    for original_split in ("CALIBRATION","HELDOUT","ALL_REUSED"):
        for layer in ("M3","M4","M9_MULTIFREQUENCY","ALL_LAYERS"):
            for variant in VARIANTS:
                part=[r for r in rows if (original_split=="ALL_REUSED" or r["original_split"]==original_split)
                      and (layer=="ALL_LAYERS" or r["layer"]==layer) and r["variant"]==variant]
                item={"cases":len(part),"all_are_reused_development_cases":True}
                for method in ("joint","iid"):
                    accepted=[r for r in part if r[method+"_shadow_accepted"]]
                    angle_key="joint_marginal_projection_angle_rmse_deg" if method=="joint" else "iid_sphere_angle_rmse_deg"
                    item[method]={"statuses":dict(Counter(r[method+"_status"] for r in part)),
                      "correct_shadow_accepted":sum(r["integer_correct"] for r in accepted),
                      "wrong_shadow_accepted":sum(not r["integer_correct"] for r in accepted),
                      "rejected":sum(r[method+"_status"].startswith(("REJECTED","JOINT_REJECTED")) for r in part),
                      "unresolved":sum("UNRESOLVED" in r[method+"_status"] for r in part),
                      "accepted_correct_angle_rmse_mean_deg":float(np.mean([r[angle_key] for r in accepted if r["integer_correct"]])) if any(r["integer_correct"] for r in accepted) else None,
                      "accepted_wrong_angle_rmse_mean_deg":float(np.mean([r[angle_key] for r in accepted if not r["integer_correct"]])) if any(not r["integer_correct"] for r in accepted) else None}
                item["decision_changes"]=dict(Counter((r["iid_status"]+" -> "+r["joint_status"]) for r in part))
                groups[f"{original_split}/{layer}/{variant}"]=item
    summary={"scope":"Post-result developmental mechanism replay; no new AR cohort or calibrated field risk.",
          "counts":{"joint_validations":216,"new_same_future_IID_validations":72,"reused_IID_decisions":144,
                    "new_independent_future_realizations":72,"new_CILS_calls":0,"sensitivity_models":3,"all_signal_columns":21,
                    "producer_truth_file_reads":72,"checker_truth_file_reads":0,"post_seal_evaluator_truth_file_reads":truth_reads},
          "groups":groups,"limitations":[
           "Old rho08 future marginal Q is correct but selection dependence remains; all its joint decisions are UNRESOLVED_SELECTION_DEPENDENCE.",
           "New future AR1 begins independently of selection; oracle Q is analytically generated, not a fitted or physically validated model.",
           "Joint path uses K Bonferroni marginal length tests, IID path uses a summed length penalty; differences cannot be assigned solely to Q.",
           "Marginal sphere projections are angle diagnostics, not a global joint product-of-spheres optimum.",
           "Same frozen candidate/geometry across paired methods; original split labels persist only for provenance.",
           "Sensitivity MDB and baseline bias are model-derived, not protection levels or observed physical fault attribution."],
          "source_hashes":{f:sha(output/f) for f in ("PRODUCER_SEAL.json","FOLLOWUP_PLAN.json","CHECKER_SEAL.json","FOLLOWUP_RESULTS.csv","SYNTHETIC_SENSITIVITY.csv")}}
    emit(output/"FOLLOWUP_SUMMARY.json",summary)
    files={str(x.relative_to(output)):sha(x) for x in sorted(output.rglob("*")) if x.is_file() and x.name!="DRIVER.log"}
    emit(output/"FOLLOWUP_FINAL_SEAL.json",{"files":files,"source_pins_unchanged":source_pins(code)==p["source_pins"],
              "excluded_live_log":"DRIVER.log","new_CILS_calls":0})
    docs.mkdir(parents=True,exist_ok=True)
    for source,target in [("FOLLOWUP_RESULTS.csv","COVARIANCE_FOLLOWUP_RESULTS.csv"),
                          ("SYNTHETIC_SENSITIVITY.csv","SYNTHETIC_SENSITIVITY.csv"),
                          ("FOLLOWUP_SUMMARY.json","COVARIANCE_FOLLOWUP_SUMMARY.json")]:
        dest=docs/target
        if dest.exists():raise FileExistsError(dest)
        dest.write_bytes((output/source).read_bytes())
    print(json.dumps({"status":"FOLLOWUP_SEALED","joint":216,"new_IID":72,"new_CILS":0}))

def main():
    parser=argparse.ArgumentParser();sub=parser.add_subparsers(dest="command",required=True)
    for name in ("produce","prepare","check","summarize"):
        q=sub.add_parser(name);q.add_argument("--stage",type=Path,required=True);q.add_argument("--output",type=Path,required=True)
        if name!="produce":q.add_argument("--code",type=Path,required=True)
        if name=="summarize":q.add_argument("--docs",type=Path,required=True)
    a=parser.parse_args()
    if a.command=="produce":produce(a.stage,a.output)
    elif a.command=="prepare":print(json.dumps(prepare(a.stage,a.output,a.code),indent=2))
    elif a.command=="check":check(a.stage,a.output,a.code)
    else:summarize(a.stage,a.output,a.code,a.docs)
if __name__=="__main__":main()
