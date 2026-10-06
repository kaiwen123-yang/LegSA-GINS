#!/usr/bin/env python3
"""Frozen synthetic carrier-admission design. No raw data or reference inputs.

The first five clean epochs select N once per independent seed. Paired future
conditions change only epochs 5..9. Calibration is diagnostic, never threshold
training. Truth files are separate from selection and admission input files.
"""
from __future__ import annotations
import argparse
from dataclasses import asdict, is_dataclass
import hashlib
import json
from pathlib import Path
import numpy as np

LENGTH_M = 0.350
CODE_SIGMA_M = 0.50
PHASE_SIGMA_M = 0.004
SELECTION_EPOCHS = 5
FUTURE_EPOCHS = 5
CONDITIONS = ("CLEAN", "TARGET_QUARTER", "PIVOT_QUARTER", "UNDETECTED_SLIP",
              "TEMPORAL_RHO08", "INSUFFICIENT_SUPPORT", "TWO_SIGNAL_BIASES")
LAYERS = ("M3", "M4", "M9_MULTIFREQUENCY")
WAVELENGTHS = (299792458.0/1575.42e6, 299792458.0/1227.60e6,
               299792458.0/1575.42e6)
# Independent across all layer/split/case IDs, never reused from the prior study.
SEED_BASE = 2026100800
CALIBRATION_PER_LAYER = 8
HELDOUT_PER_LAYER = 16
TOTAL_SOLVER_CALLS = 72
SEED_LIBRARY_SHA256 = "28c25b1cc7fade9b956bfdf77005de8fcb0a382c8411ae6e608c83b82bff53f2"

def serial(v):
    if is_dataclass(v): return serial(asdict(v))
    if isinstance(v, np.ndarray): return v.tolist()
    if isinstance(v, np.generic): return v.item()
    if isinstance(v, Path): return str(v)
    if isinstance(v, dict): return {str(k): serial(x) for k,x in v.items()}
    if isinstance(v, (tuple,list)): return [serial(x) for x in v]
    return v

def digest(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def write_new(path, value):
    with Path(path).open("x", encoding="utf-8") as f:
        json.dump(serial(value), f, indent=2, allow_nan=False)
        f.write("\n")

def cases():
    rows=[]
    for split,count,offset in [("CALIBRATION",8,0),("HELDOUT",16,8)]:
        for layer_index,layer in enumerate(LAYERS):
            for index in range(count):
                serial_index=layer_index*24+offset+index
                rows.append({"case_id":f"{split}_{layer}_{index:02d}",
                             "split":split,"layer":layer,"index":index,
                             "seed":SEED_BASE+serial_index})
    return rows

def geometry(layer):
    m = 4 if layer=="M4" else 3
    satellites=np.array([[.7,.2,-.3],[-.5,.6,-.5],[.2,-.8,-.5],[-.7,-.3,-.4]])[:m]
    satellites=satellites/np.linalg.norm(satellites,axis=1)[:,None]
    pivot=np.array([0.,0.,-1.])
    h=-(satellites-pivot)
    groups=[{"group_id":"GPS:L1", "gnss_id":0,"sig_id":0,
             "wavelength_m":WAVELENGTHS[0],"H":h,
             "target_ids":[f"GPS{j+1}:L1" for j in range(m)],"pivot_id":"GPS19:L1"}]
    if layer=="M9_MULTIFREQUENCY":
        groups.append({"group_id":"GPS:L2","gnss_id":0,"sig_id":3,
                       "wavelength_m":WAVELENGTHS[1],"H":h.copy(),
                       "target_ids":[f"GPS{j+1}:L2" for j in range(m)],"pivot_id":"GPS19:L2"})
        angle=np.deg2rad(70.)
        rotation=np.array([[np.cos(angle),-np.sin(angle),0.],
                           [np.sin(angle),np.cos(angle),0.],[0.,0.,1.]])
        groups.append({"group_id":"GAL:E1","gnss_id":2,"sig_id":0,
                       "wavelength_m":WAVELENGTHS[2],"H":h@rotation.T,
                       "target_ids":[f"GAL{j+1}:E1" for j in range(m)],"pivot_id":"GAL19:E1"})
    return groups

def design(case):
    groups=geometry(case["layer"]);g=len(groups);per=len(groups[0]["target_ids"]);m=g*per
    wave=np.concatenate([np.full(per,x["wavelength_m"]) for x in groups])
    h=np.vstack([x["H"] for x in groups])
    A=np.vstack([np.zeros((m,m)),np.diag(wave)]);B=np.vstack([h,h])
    # Receiver 2 minus 1 SDs, then target minus pivot. Q keeps shared-pivot DD
    # correlations and GPS L1/L2 correlations, including pivot cross-correlation.
    frequency_correlation=np.eye(g)
    if g>1: frequency_correlation[0,1]=frequency_correlation[1,0]=.35
    dd=np.eye(per)+np.ones((per,per))
    shape=np.kron(frequency_correlation,dd)
    Q=np.zeros((2*m,2*m));Q[:m,:m]=2*CODE_SIGMA_M**2*shape
    Q[m:,m:]=2*PHASE_SIGMA_M**2*shape
    rng=np.random.default_rng(case["seed"])
    z=rng.normal(size=(10,2,g,per+1))
    def raw_to_noise(raw):
        correlated=np.einsum("ab,tkbs->tkas",np.linalg.cholesky(frequency_correlation),raw)
        diffs=(correlated[:,:,:,1:]-correlated[:,:,:,:1]).reshape(10,2,m)
        return np.concatenate([np.sqrt(2)*CODE_SIGMA_M*diffs[:,0],
                               np.sqrt(2)*PHASE_SIGMA_M*diffs[:,1]],axis=1)
    noise=raw_to_noise(z)
    seed_index=case["seed"]-SEED_BASE
    k=np.arange(10)
    yaw=np.deg2rad(-160+(37*seed_index)%320)+(np.deg2rad(18+6*(seed_index%7)))*k/9
    tilt=np.deg2rad(7)*np.sin(.6*k+.17*seed_index)
    truth_b=LENGTH_M*np.column_stack([np.cos(yaw)*np.cos(tilt),
                                     np.sin(yaw)*np.cos(tilt),np.sin(tilt)])
    truth_n=np.array([2,-1,4,0] if per==4 else [2,-1,4])
    truth_n=np.concatenate([truth_n+3*i for i in range(g)])
    labels=tuple(f'{group["group_id"]}:{target}:pivot={group["pivot_id"]}:rx1arc0:rx2arc0'
                 for group in groups for target in group["target_ids"])
    clean=truth_b@B.T+truth_n@A.T+noise
    fault_group=min(1,g-1);target=fault_group*per
    templates=[]
    for gi,group in enumerate(groups):
        for j,identity in enumerate(group["target_ids"]):
            direction=np.zeros(2*m);direction[m+gi*per+j]=group["wavelength_m"]
            templates.append({"signal_id":"SD:"+identity,"group_id":group["group_id"],
                              "kind":"TARGET","direction_m_per_cycle":direction})
        direction=np.zeros(2*m);direction[m+gi*per:m+(gi+1)*per]=-group["wavelength_m"]
        templates.append({"signal_id":"SD:"+group["pivot_id"],"group_id":group["group_id"],
                          "kind":"PIVOT","direction_m_per_cycle":direction})
    base_meta={"synthetic":True,"frame":"NED","receiver_order":"RX2_MINUS_RX1",
               "DD_sign":"TARGET_MINUS_PIVOT",
               "phase_templates":templates,
               "signal_identity_scope":"Synthetic satellite identities; no actual orbit or receiver log.",
               "groups":[{k:v for k,v in x.items() if k!="H"} for x in groups],
               "working_covariance":"full within epoch, independent epochs",
               "single_receiver_code_sigma_m":CODE_SIGMA_M,
               "single_receiver_phase_sigma_m":PHASE_SIGMA_M}
    def block(epoch,y,keep=None):
        keep=np.arange(2*m) if keep is None else np.asarray(keep,int)
        meta=serial(base_meta)
        meta["phase_templates"]=[dict(x,direction_m_per_cycle=np.asarray(x["direction_m_per_cycle"])[keep])
                                 for x in templates]
        return {"time_s":float(.2*epoch),"y":y[keep],"A":A[keep],"B":B[keep],
                "Q":Q[np.ix_(keep,keep)],"ambiguity_labels":labels,"metadata":meta}
    selection=[block(k,clean[k]) for k in range(5)]
    conditions={}; truths={}
    for name in CONDITIONS:
        values=clean.copy();actual_n=np.tile(truth_n,(10,1));keep=None
        if name=="TARGET_QUARTER": values[5:,m+target]+=.25*wave[target]
        if name=="PIVOT_QUARTER": values[5:,m+target:m+target+per]-=.25*wave[target]
        if name=="UNDETECTED_SLIP":
            actual_n[5:,target]+=1;values[5:,m+target]+=wave[target]
        if name=="TEMPORAL_RHO08":
            correlated=z.copy()
            for epoch in range(5,10):
                correlated[epoch]=.8*correlated[epoch-1]+np.sqrt(1-.8**2)*z[epoch]
            values=truth_b@B.T+truth_n@A.T+raw_to_noise(correlated)
        if name=="INSUFFICIENT_SUPPORT": keep=np.array([0,1,m,m+1])
        if name=="TWO_SIGNAL_BIASES":
            values[5:,m+target]+=.25*wave[target]
            values[5:,m+target+1]-=.40*wave[target+1]
        assert np.array_equal(values[:5],clean[:5])
        conditions[name]=[block(k,values[k],keep) for k in range(5,10)]
        truths[name]={"integer_by_epoch":actual_n[5:],"baseline_m":truth_b[5:],
                      "model_truth_representable_across_selection_and_future":name!="UNDETECTED_SLIP",
                      "mean_observation_model_exact":name not in ("TARGET_QUARTER","PIVOT_QUARTER","TWO_SIGNAL_BIASES"),
                      "temporal_covariance_model_exact":name!="TEMPORAL_RHO08",
                      "sufficient_known_phase_rows":name!="INSUFFICIENT_SUPPORT"}
    return {"selection":selection,"future":conditions,
            "truth":{"selection_integer":truth_n,"selection_baseline_m":truth_b[:5],
                     "conditions":truths},
            "metadata":{"case":case,"dd_count":m,"frequency_correlation":frequency_correlation,
                        "phase_sigma_units":"0.004 m, engineering assumption; NOT 0.004 cycles",
                        "length_m":LENGTH_M,"fault_group_index":fault_group,
                        "fault_target_column":target,
                        "baseline_yaw_change_deg":float(np.rad2deg(yaw[-1]-yaw[0]))}}

def protocol():
    return {
        "stage":"CARRIER_ROBUSTNESS_20261006",
        "status":"DESIGN_ONLY_NO_CILS_EXECUTED",
        "maximum_CILS_calls":72,
        "cases":cases(),"conditions":CONDITIONS,
        "split":{"calibration":24,"heldout":48,
                 "independent_base_noise_units":72,"paired_future_conditions":504,
                 "threshold_training":False,
                 "calibration_role":"Model/implementation diagnostic only; cannot change any threshold, parameter, case, or heldout seed."},
        "candidate_selection":"Exactly one clean 5-epoch CILS call per seed; best/second and active labels frozen before future validation.",
        "future_validation":"Five strictly later epochs; frozen N; separate 3D b_k each epoch. Never choose a replacement candidate, extend the horizon, or re-search integers from future outcomes.",
        "admission_policy":{"nominal_total_type_I_alpha":.01,"bonferroni_alpha_each":.005,
                            "residual_gate":"Sum free-baseline GLS residual cost versus chi-square(sum(n_k-3)).",
                            "length_gate":"Sum sphere projection penalties versus chi-square(3K); each penalty bounded by true-baseline Gaussian Mahalanobis distance.",
                            "conditions":"Known Gaussian working Q and correctly specified mean; alpha is not false-fix probability.",
                            "threshold_adjustment":"Forbidden on both calibration and heldout.",
                            "meaning":"SHADOW_ACCEPTED is experimental gate output, not production integer FIX or calibrated integrity."},
        "models":{"layers":LAYERS,"length_m":LENGTH_M,"single_receiver_code_sigma_m":CODE_SIGMA_M,
                  "single_receiver_phase_sigma_m":PHASE_SIGMA_M,
                  "phase_sigma_provenance":"Fixed engineering 4 mm, NOT receiver RAWX 0.004 cycles floor.",
                  "GPS_L1_L2_raw_SD_correlation":.35,
                  "working_Q":"Exact generated within-epoch DD covariance, including shared pivot and GPS cross-frequency terms; solver assumes independent epochs.",
                  "motion":"18..54 deg continuous yaw rotation and sinusoidal 7 deg tilt over 1.8 s; independent b_k in solver.",
                  "integers":"Fixed known per-group [2,-1,4] (+3 per later group); M4 [2,-1,4,0].",
                  "fault_timing":"All perturbations start at epoch index 5, after candidate selection. First five matrices/observations shared bitwise across conditions.",
                  "pivot_fault":"RX2 pivot +0.25 cycles => every phase DD of that signal group shifts -0.25 lambda.",
                  "slip":"Target RX2 +1 cycle from epoch index 5 without arc reset: no constant N can represent the entire selection+validation window.",
                  "temporal_rho08":"Only future segment follows AR(1), seeded by last selection-epoch latent noise; marginal Q unchanged, cross-epoch dependence unmodeled.",
                  "insufficient_support":"Only two target code/phase rows retained; known phase count=2, must remain unresolved.",
                  "two_faults":"Two different RX2 target signals have +0.25 and -0.40 cycles; retain single-fault-model mismatch."},
        "separation":{"selection_inputs":"First five blocks only; no truth or future file is passed to CILS worker.",
                      "validation_inputs":"Frozen best/second and five future blocks; truth is separate and opened only for final outcome labeling.",
                      "real_data_reads":0,"reference_reads":0,"new_RP_or_navigation_integration":False},
        "reporting":{"outcomes":["correct shadow acceptance","wrong shadow acceptance","rejected/unresolved","unrepresentable shared-integer truth","baseline angle error even when integer-correct"],
                     "accuracy_units":"Per-condition independent seed denominator: 48 heldout total, 16 per layer; never pool 336 paired heldout conditions as IID.",
                     "intervals":"Wilson interval per condition (and per layer) for observed shadow wrong-acceptance proportion; observed wrong acceptance is not a calibrated future integrity guarantee.",
                     "no_discard":"Retain timeout/no-certificate/unsupported/multiple-fault cases."},
        "budgets":{"node_limit":100000,"initial_lambda_candidates":8,"solver_timeout_s":20.,
                   "process_group_timeout_s":25.,"stage_walltime_s":1950.},
        "library_sha256":SEED_LIBRARY_SHA256}

def prepare(output: Path):
    output.mkdir(parents=True,exist_ok=False)
    for name in ("selection_inputs","future_inputs","truth"): (output/name).mkdir()
    p=protocol()
    for row in p["cases"]:
        data=design(row);case_id=row["case_id"]
        for folder,payload in [("selection_inputs",{"case":row,"blocks":data["selection"],"metadata":data["metadata"]}),
                               ("future_inputs",{"case":row,"conditions":data["future"],"metadata":data["metadata"]}),
                               ("truth",{"case":row,"truth":data["truth"]})]:
            path=output/folder/(case_id+".json");write_new(path,payload)
            row[folder+"_file"]=str(path.relative_to(output));row[folder+"_sha256"]=digest(path)
    p["generator_sha256"]=digest(__file__)
    write_new(output/"PLAN.json",p)
    return p

def source_pins(code):
    paths=list((code/"src/legsa_gins/paper_rebuild/carrier_phase").glob("*.py"))
    paths += [code/"src/legsa_gins/paper_rebuild/horizontal_literature/ext01_clambda.py",
              code/"src/legsa_gins/paper_rebuild/horizontal_literature/shared_raw_backend.py",
              code/"scripts/paper_rebuild/carrier_phase/robustness_trial.py"]
    return {str(p.relative_to(code)):digest(p) for p in sorted(paths)}

def from_block(value):
    from legsa_gins.paper_rebuild.carrier_phase.temporal import EpochBlock
    return EpochBlock(value["time_s"],np.asarray(value["y"]),np.asarray(value["A"]),
                      np.asarray(value["B"]),np.asarray(value["Q"]),
                      tuple(value["ambiguity_labels"]),value["metadata"])

def append_json(path,value):
    with Path(path).open("a",encoding="utf-8") as f:
        f.write(json.dumps(serial(value),allow_nan=False)+"\n");f.flush()

def worker(model,result,library):
    import time,traceback
    from legsa_gins.paper_rebuild.carrier_phase.temporal import assemble_epochs
    from legsa_gins.paper_rebuild.carrier_phase.solver import solve_temporal
    payload=json.loads(model.read_text())
    blocks=[from_block(b) for b in payload["blocks"]]
    start=time.monotonic()
    try:
        p=assemble_epochs(blocks,length_m=LENGTH_M)
        solved=solve_temporal(p,library,initial_candidates=8,node_limit=100000,
                              timeout_s=20.,distinct_ambiguity_labels=blocks[-1].ambiguity_labels)
        output={"status":"TERMINAL","case":payload["case"],"result":solved,
                "labels":p.ambiguity_labels,"active_labels":blocks[-1].ambiguity_labels,
                "selected_at":blocks[-1].time_s,"elapsed_s":time.monotonic()-start,
                "selection_input_sha256":digest(model),
                "future_or_truth_files_read":False}
    except Exception as exc:
        output={"status":"EXCEPTION","case":payload["case"],
                "exception":type(exc).__name__,"message":str(exc),
                "traceback":traceback.format_exc(),"elapsed_s":time.monotonic()-start,
                "selection_input_sha256":digest(model),"future_or_truth_files_read":False}
    write_new(result,output)

def freeze_prepare(code,output,library):
    if digest(library)!=SEED_LIBRARY_SHA256:raise ValueError("LAMBDA binary hash mismatch")
    plan=prepare(output)
    # prepare() first stores the design; registered execution additionally pins
    # code and library without mutating the design artifact.
    execution={"plan_sha256":digest(output/"PLAN.json"),"source_pins":source_pins(code),
               "library_sha256":digest(library),"maximum_solver_calls":72,
               "execution_ready":True,
               "thresholds_frozen_before_calibration":True,
               "all_truth_opened_only_after_admission_seal":True}
    write_new(output/"EXECUTION_REGISTRATION.json",execution)
    return execution

def check_registration(code,output,library):
    plan=json.loads((output/"PLAN.json").read_text())
    registration=json.loads((output/"EXECUTION_REGISTRATION.json").read_text())
    if digest(output/"PLAN.json")!=registration["plan_sha256"]:raise ValueError("plan changed")
    if source_pins(code)!=registration["source_pins"]:raise ValueError("registered source changed")
    if digest(library)!=registration["library_sha256"]:raise ValueError("library changed")
    if len(plan["cases"])!=72 or registration["maximum_solver_calls"]!=72:raise ValueError("budget mismatch")
    return plan,registration

def run_selections(code,output,library):
    import os,signal,subprocess,sys,time
    plan,registration=check_registration(code,output,library)
    (output/"selection_results").mkdir();(output/"logs").mkdir()
    start=time.monotonic();calls=0;results={}
    for row in plan["cases"]:
        check_registration(code,output,library)
        model=output/row["selection_inputs_file"]
        if digest(model)!=row["selection_inputs_sha256"]:raise ValueError("selection model changed")
        out=output/"selection_results"/(row["case_id"]+".json")
        if time.monotonic()-start>=1950.:
            write_new(out,{"status":"NOT_EXECUTED_STAGE_WALLTIME","case":row})
        else:
            cmd=[sys.executable,str(Path(__file__).resolve()),"worker",
                 "--model",str(model),"--result",str(out),"--library",str(library)]
            calls+=1
            append_json(output/"SELECTION_LEDGER.jsonl",{"event":"START","call":calls,
                        "case_id":row["case_id"],"model_sha256":digest(model)})
            timed_out=False;begin=time.monotonic()
            with (output/"logs"/(row["case_id"]+".stdout")).open("wb") as so, (output/"logs"/(row["case_id"]+".stderr")).open("wb") as se:
                proc=subprocess.Popen(cmd,stdout=so,stderr=se,start_new_session=True)
                try:proc.wait(timeout=max(.1,min(25.,1950.-(time.monotonic()-start))))
                except subprocess.TimeoutExpired:
                    timed_out=True
                    try:os.killpg(proc.pid,signal.SIGKILL)
                    except ProcessLookupError:pass
                    proc.wait()
            if not out.exists():
                write_new(out,{"status":"PROCESS_TIMEOUT" if timed_out else "PROCESS_FAILURE",
                              "case":row,"returncode":proc.returncode,"elapsed_s":time.monotonic()-begin})
            append_json(output/"SELECTION_LEDGER.jsonl",{"event":"END","call":calls,
                        "case_id":row["case_id"],"result_sha256":digest(out),
                        "returncode":proc.returncode})
        rec=json.loads(out.read_text());results[str(out.relative_to(output))]=digest(out)
        print(json.dumps({"case_id":row["case_id"],"status":rec["status"],
                          "certified":rec.get("result",{}).get("certificate",{}).get("global_optimum_certified",False)}),flush=True)
    check_registration(code,output,library)
    write_new(output/"SELECTION_SEAL.json",{"solver_calls":calls,"planned_solver_calls":72,
              "elapsed_s":time.monotonic()-start,"files":results,
              "plan_sha256":digest(output/"PLAN.json"),
              "registration_sha256":digest(output/"EXECUTION_REGISTRATION.json"),
              "future_scoring_calls_before_seal":0,"truth_files_opened":0})

def persistent_fault_diagnostic(blocks,integers):
    from legsa_gins.paper_rebuild.carrier_phase.temporal import assemble_epochs
    from legsa_gins.paper_rebuild.carrier_phase.faults import (
        PhaseFaultMap,PhaseFaultHypothesis,fixed_integer_gls,single_fault_glrt)
    from legsa_gins.paper_rebuild.carrier_phase.observations import SignalIdentity
    temporal=assemble_epochs(blocks,length_m=LENGTH_M)
    templates=blocks[0].metadata["phase_templates"]
    names=[t["signal_id"] for t in templates]
    if any([t["signal_id"] for t in b.metadata["phase_templates"]]!=names for b in blocks):
        raise ValueError("persistent fault identities changed")
    columns=np.vstack([np.column_stack([t["direction_m_per_cycle"]
                        for t in b.metadata["phase_templates"]]) for b in blocks])
    groups={g["group_id"]:g for g in blocks[0].metadata["groups"]}
    labels=blocks[0].ambiguity_labels
    hypotheses=[]
    for t in templates:
        g=groups[t["group_id"]];is_pivot=t["kind"]=="PIVOT"
        sv=19 if is_pivot else g["target_ids"].index(t["signal_id"].split(":",1)[1])+1
        identity=SignalIdentity(g["gnss_id"],sv,g["sig_id"],0)
        pivot=SignalIdentity(g["gnss_id"],19,g["sig_id"],0)
        affected=tuple(labels[j] for j in range(len(labels))
                       if np.any(blocks[0].A[np.asarray(t["direction_m_per_cycle"])!=0,j]!=0))
        hypotheses.append(PhaseFaultHypothesis(t["signal_id"],identity,
                           (g["gnss_id"],g["sig_id"],0),pivot,is_pivot,"sd",
                           g["wavelength_m"],affected))
    fmap=PhaseFaultMap(columns,tuple(hypotheses),tuple(range(len(temporal.y))),len(temporal.y))
    fit=fixed_integer_gls(temporal,integers)
    diagnosis=single_fault_glrt(fit,fmap,family_alpha=.01)
    return {"scope":"One persistent scalar SD-signal cycle bias over five epochs; independent b_k. Diagnostics only, no repair/admission feedback.",
            "fixed_integer_gls":{"residual_cost":fit.residual_cost,"residual_df":fit.residual_df,
               "rank":fit.baseline_rank,"nuisance_dimension":fit.nuisance_dimension},
            "diagnosis":diagnosis}

def validate_frozen(output,code,library):
    from legsa_gins.paper_rebuild.carrier_phase.admission import (
        FrozenCandidate,AdmissionConfig,CausalAdmissionSession)
    from legsa_gins.paper_rebuild.horizontal_literature.ext01_clambda import constrained_baseline
    plan,registration=check_registration(code,output,library)
    seal=json.loads((output/"SELECTION_SEAL.json").read_text())
    for path,expected in seal["files"].items():
        if digest(output/path)!=expected:raise ValueError("sealed selection changed")
    (output/"admission_results").mkdir();results={}
    for row in plan["cases"]:
        check_registration(code,output,library)
        selected=json.loads((output/"selection_results"/(row["case_id"]+".json")).read_text())
        future_path=output/row["future_inputs_file"]
        if digest(future_path)!=row["future_inputs_sha256"]:raise ValueError("future model changed")
        future=json.loads(future_path.read_text())
        r=selected.get("result",{});cert=r.get("certificate",{})
        eligible=cert.get("global_optimum_certified",False) and r.get("best") is not None and r.get("second") is not None
        for condition in CONDITIONS:
            out=output/"admission_results"/(row["case_id"]+"__"+condition+".json")
            if not eligible:
                record={"case":row,"condition":condition,"status":"UNRESOLVED_CANDIDATE_SEARCH",
                        "shadow_accepted":False,"truth_files_read":0}
            else:
                labels=tuple(selected["labels"]);active=tuple(selected["active_labels"])
                primary=FrozenCandidate.from_mapping("best",selected["selected_at"],
                           dict(zip(labels,r["best"]["ambiguity"])),active,row["case_id"])
                second=FrozenCandidate.from_mapping("second",selected["selected_at"],
                           dict(zip(labels,r["second"]["ambiguity"])),active,row["case_id"])
                session=CausalAdmissionSession(primary,second,AdmissionConfig())
                blocks=[from_block(b) for b in future["conditions"][condition]]
                for b in blocks:session.observe(b)
                decision=session.finalize()
                baselines=[]
                for ep in decision.epochs:
                    fit=ep.primary
                    baselines.append(None if fit is None else constrained_baseline(
                        np.array(fit.baseline_center_m),np.array(fit.baseline_covariance_m2),LENGTH_M).baseline)
                record={"case":row,"condition":condition,"status":decision.status,
                        "shadow_accepted":decision.shadow_accepted,"decision":decision,
                        "primary_sphere_baselines_m":baselines,
                        "fault_diagnostic":persistent_fault_diagnostic(blocks,primary.integers),
                        "truth_files_read":0}
            write_new(out,record);results[str(out.relative_to(output))]=digest(out)
        print(json.dumps({"validated":row["case_id"],"paired_conditions":7}),flush=True)
    check_registration(code,output,library)
    write_new(output/"ADMISSION_SEAL.json",{"files":results,"conditions":len(results),
               "selection_seal_sha256":digest(output/"SELECTION_SEAL.json"),
               "registration_sha256":digest(output/"EXECUTION_REGISTRATION.json"),
               "new_integer_search_calls":0,"truth_files_opened":0,
               "threshold_changes":0,"shadow_only":True})

def wilson(k,n):
    if n==0:return None
    z=1.959963984540054;p=k/n;den=1+z*z/n
    center=(p+z*z/(2*n))/den
    half=z*np.sqrt(p*(1-p)/n+z*z/(4*n*n))/den
    return {"level":.95,"lower":max(0.,float(center-half)),"upper":min(1.,float(center+half)),
            "method":"two-sided Wilson; fixed-design simulation proportion, not field integrity"}

def summarize(output,code,library):
    import csv
    from collections import Counter
    plan,registration=check_registration(code,output,library)
    admission_seal=json.loads((output/"ADMISSION_SEAL.json").read_text())
    for path,expected in admission_seal["files"].items():
        if digest(output/path)!=expected:raise ValueError("sealed admission changed")
    rows=[]
    for case in plan["cases"]:
        p=output/case["truth_file"]
        if digest(p)!=case["truth_sha256"]:raise ValueError("truth changed")
        truth=json.loads(p.read_text())["truth"]
        selected=json.loads((output/"selection_results"/(case["case_id"]+".json")).read_text())
        best=selected.get("result",{}).get("best")
        selection_correct=None if not best else bool(np.array_equal(best["ambiguity"],truth["selection_integer"]))
        for condition in CONDITIONS:
            rec=json.loads((output/"admission_results"/(case["case_id"]+"__"+condition+".json")).read_text())
            t=truth["conditions"][condition];future_correct=None
            if best:future_correct=bool(np.all(np.array(t["integer_by_epoch"])==np.asarray(best["ambiguity"])))
            representable=t["model_truth_representable_across_selection_and_future"]
            accepted=rec["shadow_accepted"]
            if not representable:
                outcome="UNREPRESENTABLE_SHADOW_ACCEPTED" if accepted else "UNREPRESENTABLE_NOT_ACCEPTED"
            elif accepted:outcome="CORRECT_INTEGER_SHADOW_ACCEPTED" if future_correct else "WRONG_INTEGER_SHADOW_ACCEPTED"
            else:outcome="NOT_ACCEPTED"
            predicted=rec.get("primary_sphere_baselines_m",[])
            angles=[]
            for k,b in enumerate(predicted):
                if b is not None:
                    value=np.dot(np.asarray(b),np.asarray(t["baseline_m"])[k])/LENGTH_M**2
                    angles.append(float(np.rad2deg(np.arccos(np.clip(value,-1.,1.)))))
            fd=rec.get("fault_diagnostic",{}).get("diagnosis",{})
            rows.append({"case_id":case["case_id"],"split":case["split"],"layer":case["layer"],
                         "seed":case["seed"],"condition":condition,"status":rec["status"],
                         "outcome":outcome,"shadow_accepted":accepted,
                         "selection_integer_correct":selection_correct,
                         "future_integer_correct":future_correct,
                         "model_truth_representable":representable,
                         "mean_observation_model_exact":t["mean_observation_model_exact"],
                         "temporal_covariance_model_exact":t["temporal_covariance_model_exact"],
                         "baseline_angle_epoch_count":len(angles),
                         "baseline_angle_rmse_deg":float(np.sqrt(np.mean(np.square(angles)))) if angles else None,
                         "baseline_angle_max_deg":max(angles) if angles else None,
                         "GLRT_reject_any":any(s["nominal_reject_null"] for s in fd.get("scores",[])),
                         "GLRT_best_hypotheses":json.dumps(fd.get("best_hypotheses",[])),
                         "accepted_integer_measurement":False})
    with (output/"RESULTS.csv").open("x",newline="",encoding="utf-8") as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator="\n");writer.writeheader();writer.writerows(rows)
    groups={}
    for split in ("CALIBRATION","HELDOUT"):
        for condition in CONDITIONS:
            for layer in (*LAYERS,"ALL_LAYERS"):
                part=[r for r in rows if r["split"]==split and r["condition"]==condition
                      and (layer=="ALL_LAYERS" or r["layer"]==layer)]
                compatible=[r for r in part if r["model_truth_representable"]]
                wrong=sum(r["outcome"]=="WRONG_INTEGER_SHADOW_ACCEPTED" for r in compatible)
                groups[f"{split}/{condition}/{layer}"]={
                    "independent_seed_count":len(part),"outcomes":dict(Counter(r["outcome"] for r in part)),
                    "statuses":dict(Counter(r["status"] for r in part)),
                    "representable_seed_count":len(compatible),"wrong_integer_shadow_accepted":wrong,
                    "wrong_shadow_acceptance_wilson":wilson(wrong,len(compatible)),
                    "unrepresentable_shadow_accepted":sum(r["outcome"]=="UNREPRESENTABLE_SHADOW_ACCEPTED" for r in part),
                    "mean_baseline_angle_rmse_deg":float(np.mean([r["baseline_angle_rmse_deg"] for r in part if r["baseline_angle_rmse_deg"] is not None])) if any(r["baseline_angle_rmse_deg"] is not None for r in part) else None,
                    "GLRT_reject_any":sum(r["GLRT_reject_any"] for r in part)}
    summary={"planned_solver_calls":72,
             "actual_solver_calls":json.loads((output/"SELECTION_SEAL.json").read_text())["solver_calls"],
             "paired_conditions":len(rows),"heldout_independent_seeds":48,"calibration_independent_seeds":24,
             "threshold_changes":0,"groups":groups,
             "limits":["Per-condition denominators only; paired conditions are not independent.",
                       "Per-layer Wilson intervals are primary. ALL_LAYERS pools independent but nonidentical fixed geometries: its Wilson interval is a descriptive approximation, not calibrated coverage or field false-fix risk.",
                       "Integer-correct shadow acceptance may still have biased baseline angle.",
                       "Unmodeled slip makes one shared integer vector incompatible across selection and future; kept separate.",
                       "No GLRT phase correction or candidate replacement; no navigation integration."],
             "raw_payload_reads":0,"reference_reads":0}
    write_new(output/"SUMMARY.json",summary)
    files={str(p.relative_to(output)):digest(p) for p in sorted(output.rglob("*")) if p.is_file()}
    write_new(output/"FINAL_SEAL.json",{"files":files,"source_pins_unchanged":source_pins(code)==registration["source_pins"],
              "solver_calls":summary["actual_solver_calls"],"truth_access":"After ADMISSION_SEAL only"})
    print(json.dumps({"solver_calls":summary["actual_solver_calls"],"conditions":len(rows),"status":"SEALED"}),flush=True)

def main():
    p=argparse.ArgumentParser();sub=p.add_subparsers(dest="command",required=True)
    q=sub.add_parser("prepare");q.add_argument("--output",type=Path,required=True)
    q.add_argument("--code",type=Path,required=True);q.add_argument("--library",type=Path,required=True)
    q=sub.add_parser("protocol");q.add_argument("--output",type=Path,required=True)
    q=sub.add_parser("worker");q.add_argument("--model",type=Path,required=True)
    q.add_argument("--result",type=Path,required=True);q.add_argument("--library",type=Path,required=True)
    for name in ("select","validate","summarize"):
        q=sub.add_parser(name);q.add_argument("--output",type=Path,required=True)
        q.add_argument("--code",type=Path,required=True);q.add_argument("--library",type=Path,required=True)
    a=p.parse_args()
    if a.command=="prepare":
        print(json.dumps({"execution_registration":freeze_prepare(a.code,a.output,a.library),"CILS_calls":0}))
    elif a.command=="protocol":write_new(a.output,protocol())
    elif a.command=="worker":worker(a.model,a.result,a.library)
    elif a.command=="select":run_selections(a.code,a.output,a.library)
    elif a.command=="validate":validate_frozen(a.output,a.code,a.library)
    elif a.command=="summarize":summarize(a.output,a.code,a.library)
if __name__=="__main__":main()
