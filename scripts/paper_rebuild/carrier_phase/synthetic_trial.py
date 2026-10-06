#!/usr/bin/env python3
"""Bounded dynamic-baseline known-integer trials. No real/raw/reference inputs."""
from __future__ import annotations
from pathlib import Path
from dataclasses import asdict,is_dataclass
from collections import Counter,defaultdict
import argparse,csv,hashlib,json,math,os,signal,subprocess,sys,time,traceback
import numpy as np
from legsa_gins.paper_rebuild.carrier_phase.temporal import EpochBlock,assemble_epochs,with_scalar_prior
from legsa_gins.paper_rebuild.carrier_phase.solver import solve_temporal

LENGTH=.350
LAMBDA=.190293672798365
LIB_SHA="28c25b1cc7fade9b956bfdf77005de8fcb0a382c8411ae6e608c83b82bff53f2"
SEEDS=tuple(2026100700+i for i in range(10))
PREFIXES=(1,5,10)
VARIANTS=("SLIP_NEW_ARC","SLIP_UNMODELED","QUARTER_CYCLE","CORRELATED_RHO08","RP_NOMINAL","RP_BIAS")
TIMEOUT=20.
PROCESS_TIMEOUT=25.
WALLTIME=1250.
def serial(x):
    if is_dataclass(x):return serial(asdict(x))
    if isinstance(x,np.ndarray):return x.tolist()
    if isinstance(x,np.generic):return x.item()
    if isinstance(x,Path):return str(x)
    if isinstance(x,dict):return {str(k):serial(v) for k,v in x.items()}
    if isinstance(x,(list,tuple)):return [serial(v) for v in x]
    return x
def emit(p,value):
    with Path(p).open("x",encoding="utf8") as f:json.dump(serial(value),f,indent=2,allow_nan=False);f.write("\n")
def digest(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def append(p,value):
    with Path(p).open("a",encoding="utf8") as f:f.write(json.dumps(serial(value),allow_nan=False)+"\n");f.flush()
def revision(code):return subprocess.check_output(["git","rev-parse","HEAD"],cwd=code,text=True).strip()
def pins(code):
    names=["src/legsa_gins/paper_rebuild/carrier_phase/temporal.py",
           "src/legsa_gins/paper_rebuild/carrier_phase/solver.py",
           "src/legsa_gins/paper_rebuild/horizontal_literature/ext01_clambda.py",
           "scripts/paper_rebuild/carrier_phase/synthetic_trial.py"]
    return {name:digest(code/name) for name in names}
def records():
    return ([{"case_id":f"S{i:02d}_NOMINAL_K{k:02d}","seed_index":i,"seed":seed,"variant":"NOMINAL","epochs":k}
             for i,seed in enumerate(SEEDS) for k in PREFIXES]
            +[{"case_id":f"S{i:02d}_{variant}_K10","seed_index":i,"seed":SEEDS[i],"variant":variant,"epochs":10}
              for i in range(3) for variant in VARIANTS])

def design(row):
    i=row["seed_index"];m=4 if i%2==0 else 3
    # Physical, below-horizon-sign NED LOS: pivot overhead and four satellites.
    satellite=np.array([[.7,.2,-.3],[-.5,.6,-.5],[.2,-.8,-.5],[-.7,-.3,-.4]])[:m]
    satellite/=np.linalg.norm(satellite,axis=1)[:,None]
    H=-(satellite-np.array([0.,0.,-1.]))
    A=np.vstack((np.zeros((m,m)),LAMBDA*np.eye(m)));B=np.vstack((H,H))
    C=np.eye(m)+np.ones((m,m));Q=np.zeros((2*m,2*m))
    Q[:m,:m]=2*.5**2*C;Q[m:,m:]=2*.004**2*C
    k=np.arange(10);yaw=np.deg2rad(-150+31*i+(40+12*i)*k/9)
    tilt=np.deg2rad(7)*np.sin(.7*k+.2*i)
    truth=LENGTH*np.column_stack((np.cos(yaw)*np.cos(tilt),np.sin(yaw)*np.cos(tilt),np.sin(tilt)))
    integer=np.array([2,-1,4,0])[:m]
    rng=np.random.default_rng(row["seed"]);Z=rng.normal(size=(10,2*m))
    noise=Z@np.linalg.cholesky(Q).T
    if row["variant"]=="CORRELATED_RHO08":
        T=.8**np.abs(k[:,None]-k[None,:]);noise=np.linalg.cholesky(T)@Z@np.linalg.cholesky(Q).T
    truth_integer=np.tile(integer,(10,1))
    if row["variant"] in ("SLIP_NEW_ARC","SLIP_UNMODELED"):truth_integer[5:,0]+=1
    y=truth@B.T+truth_integer@A.T+noise
    if row["variant"]=="QUARTER_CYCLE":y[5:,m]+=.25*LAMBDA
    labels=[tuple(f"GPS:L1:sv{j+1}:pivot0:arc0" for j in range(m)) for _ in range(10)]
    if row["variant"]=="SLIP_NEW_ARC":
        for epoch in range(5,10):labels[epoch]=(labels[epoch][0].replace("arc0","arc1"),)+labels[epoch][1:]
    true_roll=-np.arcsin(truth[:,2]/LENGTH)
    rp_noise=np.random.default_rng(row["seed"]+100000).normal(size=10)*(.03/LENGTH)
    rp_fault=(1 if i%2==0 else -1)*math.asin(.15/LENGTH) if row["variant"]=="RP_BIAS" else 0.
    measured_roll=true_roll+rp_noise+rp_fault;z=-LENGTH*np.sin(measured_roll)
    blocks=[]
    for epoch in range(row["epochs"]):
        block=EpochBlock(.2*epoch,y[epoch],A,B,Q,labels[epoch],{"synthetic":True})
        if row["variant"] in ("RP_NOMINAL","RP_BIAS"):
            block=with_scalar_prior(block,np.array([0.,0.,1.]),z[epoch],.03,name="conditional_RP_vertical")
        blocks.append(block)
    return blocks,truth[:row["epochs"]],truth_integer[:row["epochs"]],{
        "dd_count":m,"true_yaw_deg":np.rad2deg(yaw[:row["epochs"]]),
        "true_roll_deg":np.rad2deg(true_roll[:row["epochs"]]),
        "measured_roll_deg":np.rad2deg(measured_roll[:row["epochs"]]),
        "RP_bias_deg":math.degrees(rp_fault),"RP_vertical_z_m":z[:row["epochs"]],
        "model_truth_representable":row["variant"]!="SLIP_UNMODELED",
        "noise_temporally_independent":row["variant"]!="CORRELATED_RHO08",
        "assumed_Q_temporally_independent":True,
        "trajectory_endpoint_displacement_m":float(np.linalg.norm(truth[row["epochs"]-1]-truth[0]))}

def prepare(code,out,library):
    out.mkdir(parents=True,exist_ok=False)
    if digest(library)!=LIB_SHA:raise ValueError("pinned LAMBDA library mismatch")
    matrix_dir=out/"models";matrix_dir.mkdir()
    cases=records()
    for row in cases:
        blocks,truth,truth_integer,meta=design(row)
        problem=assemble_epochs(blocks,length_m=LENGTH)
        payload={"row":row,"metadata":meta,"truth_baselines":truth,"truth_integer_by_epoch":truth_integer,
                 "blocks":[{"time_s":b.time_s,"y":b.y,"A":b.A,"B":b.B,"Q":b.Q,
                            "ambiguity_labels":b.ambiguity_labels,"metadata":b.metadata} for b in blocks]}
        path=matrix_dir/(row["case_id"]+".json");emit(path,payload)
        row["model_file"]=str(path.relative_to(out));row["model_sha256"]=digest(path)
        row["global_integer_dimension"]=problem.ambiguity_count
    plan={
        "stage":"CARRIER_TEMPORAL_SYNTHETIC_V1","execution_commit":revision(code),
        "source_pins":pins(code),"overlay_policy":"Tracked commit plus explicit source hashes; newly written runner may be uncommitted.",
        "library_sha256":LIB_SHA,"cases":cases,"maximum_solver_calls":48,
        "budgets":{"solver_timeout_s":TIMEOUT,"process_group_timeout_s":PROCESS_TIMEOUT,
                   "stage_walltime_s":WALLTIME,"node_limit":100000,"initial_lambda_candidates":8},
        "design":{"length_m":LENGTH,"wavelength_m":LAMBDA,"new_independent_noise_seeds":SEEDS,
                  "base_noise_units":10,"prefixes":PREFIXES,"DD_dimension_by_seed":"4 for even index, 3 for odd index",
                  "COV":"DD code=2*(0.5m)^2*(I+11T), phase=2*(0.004m)^2*(I+11T), assumed epoch block diagonal.",
                  "noise_values":"Engineering floor values inherited from prior RAWX experiments; not calibrated stochastic truth.",
                  "motion":"Every 10-epoch trajectory has changing yaw and vertical tilt; separate free b_k in solver.",
                  "paired_variants":"First three base seeds, same raw standardized Gaussian draw; six variants each.",
                  "integer":"[2,-1,4,0][:m]; slip +1 on first DD from epoch index 5.",
                  "RP":"Reported roll=true(-asin(bD/L))+independent Gaussian(0,0.03/L rad); pitch=0. Added z=-L*sin(roll), model sigma=0.03m.",
                  "RP_fault":"Fixed signed asin(0.15/0.35) rad, + for even seed index and - for odd.",
                  "quarter_cycle":"Add +0.25 wavelength to first phase DD at epochs 5..9; true integers unchanged.",
                  "correlated_noise":"Generate AR(1) rho=.8 across epochs with same standardized draw; solver still assumes independent Q.",
                  "slip_without_arc":"Truth is not representable by shared N; report this explicitly and per-epoch equality.",
                  "class_mode":"Full integer vector (default), active-class solver feature is not used in this matrix."},
        "outputs":["PLAN.json","models/*.json","LEDGER.jsonl","results/*.json","RESULTS.csv","SUMMARY.json","SEAL.json"],
        "support":"All 48 planned calls retained, including process timeout, no certificate and model failure. No replacement or parameter search.",
        "meaning":"Global objective certificate is not an integer acceptance/FIX guarantee. Known-integer and baseline angle assessed separately.",
        "no_reads":["raw GNSS data","real estimated results","fused reference","V3 output"]}
    emit(out/"PLAN.json",plan);return plan

def worker(a):
    payload=json.loads(a.model.read_text());row=payload["row"]
    blocks=[EpochBlock(b["time_s"],np.array(b["y"]),np.array(b["A"]),np.array(b["B"]),np.array(b["Q"]),
                       tuple(b["ambiguity_labels"]),b["metadata"]) for b in payload["blocks"]]
    truth=np.array(payload["truth_baselines"]);true_n=np.array(payload["truth_integer_by_epoch"])
    p=assemble_epochs(blocks,length_m=LENGTH);start=time.monotonic()
    try:
        result=solve_temporal(p,a.library,initial_candidates=8,node_limit=100000,timeout_s=TIMEOUT)
        record={"case":row,"status":"TERMINAL","result":result,"metadata":payload["metadata"],
                "elapsed_s":time.monotonic()-start,"truth_baselines":truth,
                "truth_integer_by_epoch":true_n,"ambiguity_labels":p.ambiguity_labels}
        if result.best is not None:
            predicted=np.array([[result.best.ambiguity[p.ambiguity_labels.index(label)] for label in block.ambiguity_labels] for block in blocks])
            eq=np.all(predicted==true_n,axis=1)
            normalized=np.sum(result.best.baselines*truth,axis=1)/LENGTH**2
            angle=np.rad2deg(np.arccos(np.clip(normalized,-1.,1.)))
            yaw=np.rad2deg(np.arctan2(result.best.baselines[:,1],result.best.baselines[:,0])-np.arctan2(truth[:,1],truth[:,0]))
            yaw=(yaw+180)%360-180
            record["candidate_diagnostics"]={"integer_all_epochs_correct":bool(eq.all()),
                "integer_epoch_fraction_correct":float(eq.mean()),"baseline_angle_deg":angle,
                "angle_rmse_deg":float(np.sqrt(np.mean(angle**2))),"angle_max_deg":float(angle.max()),
                "yaw_rmse_deg":float(np.sqrt(np.mean(yaw**2))),
                "certified_truth_class":("CORRECT" if eq.all() else "WRONG") if result.global_optimum_certified else "UNRESOLVED",
                "model_truth_representable":payload["metadata"]["model_truth_representable"]}
        else:record["candidate_diagnostics"]={"certified_truth_class":"UNRESOLVED"}
    except Exception as exc:
        record={"case":row,"status":"EXCEPTION","exception":type(exc).__name__,"message":str(exc),
                "traceback":traceback.format_exc(),"elapsed_s":time.monotonic()-start}
    emit(a.result,record)

def flatten(row,record):
    d=record.get("candidate_diagnostics",{});r=record.get("result",{});c=r.get("certificate",{})
    return {"case_id":row["case_id"],"seed":row["seed"],"variant":row["variant"],"epochs":row["epochs"],
            "global_integer_dimension":row["global_integer_dimension"],"status":record["status"],
            "certified":c.get("global_optimum_certified",False),"truth_class":d.get("certified_truth_class","UNRESOLVED"),
            "model_truth_representable":record.get("metadata",{}).get("model_truth_representable",row["variant"]!="SLIP_UNMODELED"),
            "integer_epoch_fraction_correct":d.get("integer_epoch_fraction_correct"),
            "angle_rmse_deg":d.get("angle_rmse_deg"),"angle_max_deg":d.get("angle_max_deg"),
            "yaw_rmse_deg":d.get("yaw_rmse_deg"),"elapsed_s":record.get("elapsed_s"),
            "termination_reason":c.get("termination_reason",record.get("message")),
            "expanded_nodes":c.get("expanded_nodes"),"integer_leaves":c.get("integer_leaves"),
            "best_full_cost":r.get("best",{}).get("full_residual_cost") if r.get("best") else None,
            "second_full_cost":r.get("second",{}).get("full_residual_cost") if r.get("second") else None,
            "objective_identity_error":r.get("best",{}).get("objective_identity_error") if r.get("best") else None}

def run(a):
    plan=prepare(a.code,a.output,a.library)
    (a.output/"results").mkdir();(a.output/"logs").mkdir()
    start=time.monotonic();rows=[];solver_calls=0
    for row in plan["cases"]:
        if pins(a.code)!=plan["source_pins"]:raise ValueError("registered source changed during execution")
        model=a.output/row["model_file"]
        if digest(model)!=row["model_sha256"]:raise ValueError("registered model changed")
        result=a.output/"results"/(row["case_id"]+".json")
        if time.monotonic()-start>=WALLTIME:
            record={"status":"NOT_EXECUTED_STAGE_WALLTIME","case":row}
            emit(result,record);rows.append(flatten(row,record));continue
        command=[sys.executable,str(Path(__file__).resolve()),"worker","--model",str(model),
                 "--result",str(result),"--library",str(a.library)]
        append(a.output/"LEDGER.jsonl",{"event":"START","case_id":row["case_id"],"call":solver_calls+1,
                                       "elapsed_stage_s":time.monotonic()-start})
        solver_calls+=1;call_start=time.monotonic()
        with (a.output/"logs"/(row["case_id"]+".stdout")).open("wb") as stdout, (a.output/"logs"/(row["case_id"]+".stderr")).open("wb") as stderr:
            process=subprocess.Popen(command,stdout=stdout,stderr=stderr,start_new_session=True)
            timed_out=False
            try:process.wait(timeout=min(PROCESS_TIMEOUT,WALLTIME-(time.monotonic()-start)))
            except subprocess.TimeoutExpired:
                timed_out=True;os.killpg(process.pid,signal.SIGKILL);process.wait()
        if not result.exists():
            record={"status":"PROCESS_TIMEOUT" if timed_out else "PROCESS_FAILURE",
                    "case":row,"returncode":process.returncode,"elapsed_s":time.monotonic()-call_start}
            emit(result,record)
        record=json.loads(result.read_text());flat=flatten(row,record);rows.append(flat)
        append(a.output/"LEDGER.jsonl",{"event":"END","case_id":row["case_id"],"call":solver_calls,
                                       "returncode":process.returncode,"result_sha256":digest(result)})
        print(json.dumps(flat,allow_nan=False),flush=True)
    with (a.output/"RESULTS.csv").open("x",newline="") as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator="\n");writer.writeheader();writer.writerows(rows)
    groups=defaultdict(list)
    for row in rows:groups[f'{row["variant"]}_K{row["epochs"]}'].append(row)
    summary={"planned":48,"solver_calls":solver_calls,"execution_commit":plan["execution_commit"],
             "elapsed_s":time.monotonic()-start,"source_pins":plan["source_pins"],
             "counts":dict(Counter(r["truth_class"] for r in rows)),"groups":{}}
    for group,values in groups.items():
        angles=[x["angle_rmse_deg"] for x in values if x["certified"]]
        summary["groups"][group]={"support":len(values),"counts":dict(Counter(x["truth_class"] for x in values)),
          "certified":sum(x["certified"] for x in values),"certified_angle_rmse_mean_deg":float(np.mean(angles)) if angles else None,
          "certified_angle_rmse_max_deg":max(angles) if angles else None}
    emit(a.output/"SUMMARY.json",summary)
    files={str(p.relative_to(a.output)):digest(p) for p in sorted(a.output.rglob("*")) if p.is_file()}
    emit(a.output/"SEAL.json",{"files":files,"source_pins_unchanged":pins(a.code)==plan["source_pins"],
                              "solver_calls":solver_calls,"execution_commit":plan["execution_commit"]})
    print(json.dumps(summary,allow_nan=False),flush=True)

def main():
    p=argparse.ArgumentParser();sub=p.add_subparsers(dest="mode",required=True)
    q=sub.add_parser("run");q.add_argument("--code",type=Path,required=True);q.add_argument("--output",type=Path,required=True)
    q.add_argument("--library",type=Path,required=True)
    q=sub.add_parser("worker");q.add_argument("--model",type=Path,required=True);q.add_argument("--result",type=Path,required=True)
    q.add_argument("--library",type=Path,required=True)
    a=p.parse_args();run(a) if a.mode=="run" else worker(a)
if __name__=="__main__":main()
