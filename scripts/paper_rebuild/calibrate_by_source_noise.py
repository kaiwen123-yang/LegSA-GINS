"""Predeclared BY-only restricted noise fit followed by frozen held-out validation."""
from pathlib import Path
import argparse
import dataclasses
import hashlib
import json
import math
import sys
import time
import numpy as np
from scipy import optimize

parser = argparse.ArgumentParser()
parser.add_argument("--config", type=Path, required=True)
parser.add_argument("--declaration", type=Path, required=True)
args = parser.parse_args()
config = json.loads(args.config.read_text())
declaration = json.loads(args.declaration.read_text())
repository = Path(config["repository"])
sys.path.insert(0,str(repository/"src"))
from legsa_gins.paper_rebuild.carrier_phase.temporal import EpochBlock
from legsa_gins.paper_rebuild.joint_navigation.source_noise_likelihood import (
    NoiseParameters, prepare_source_noise_likelihood,evaluate_source_noise_likelihood)
output = Path(config["output_directory"])
output.mkdir(parents=True,exist_ok=True)
plan_path = Path(config["plan_path"])
plan = json.loads(plan_path.read_text())
(output/"PREDECLARATION.json").write_text(json.dumps(declaration,indent=2)+"\n")
started = time.monotonic()

def load_window(bounds):
    blocks,sources,excluded = [],[],[]
    for record in plan["records"]:
        if not bounds[0] <= record["time_s"] < bounds[1]: continue
        family = record["families"]["GPS_GAL_BDS_DUAL"]
        if family["status"] != "BUILT":
            excluded.append({"time_s":record["time_s"],"status":family["status"]});continue
        path = plan_path.parent/family["file"]
        with np.load(path) as z:
            blocks.append(EpochBlock(record["time_s"],z["y"],z["A"],z["B"],z["Q"],
                tuple(family["ambiguity_labels"]),dict(family["metadata"])))
        sources.append({"time_s":record["time_s"],"relative_path":family["file"],
                        "sha256":hashlib.sha256(path.read_bytes()).hexdigest()})
    problem = prepare_source_noise_likelihood(blocks)
    metadata={"declared_bounds_s":bounds,"actual_first_last_s":[blocks[0].time_s,blocks[-1].time_s],
        "epochs":len(blocks),"raw_rows":problem.original_rows,"geometry_rank":problem.geometry_rank,
        "fixed_geometry_contrast_rows":problem.contrast_rows,"integer_rank":problem.integer_rank,
        "source_beta_dimension":len(problem.physical_source_signals),"dof":problem.degrees_of_freedom,
        "excluded_nonbuilt_records":excluded}
    return problem,metadata,sources

def scalars(result):
    return {"residual_cost":result.residual_cost,"degrees_of_freedom":result.degrees_of_freedom,
        "cost_over_dof":result.residual_cost/result.degrees_of_freedom,
        "covariance_log_determinant":result.covariance_log_determinant,
        "integer_information_log_determinant":result.integer_information_log_determinant,
        "restricted_objective":result.restricted_objective}

training,train_meta,train_sources=load_window(declaration["calibration_window_s"])
print("CALIBRATION_INPUT",json.dumps(train_meta),flush=True)
history=[]
def loss(u,tau):
    parameters=NoiseParameters(.01*math.sqrt(float(u[0])),.01*math.sqrt(float(u[1])),float(tau))
    result=evaluate_source_noise_likelihood(training,parameters)
    history.append({"parameters":dataclasses.asdict(parameters),"restricted_objective":result.restricted_objective})
    return result.restricted_objective

m0=loss([0,0],.8)
white_opt=optimize.minimize_scalar(lambda u:loss([u,0],.8),bounds=(0,100),method="bounded",
                                  options={"xatol":1e-5,"maxiter":80})
white_u=float(white_opt.x) if float(white_opt.fun)<m0 else 0.0
white_value=loss([white_u,0],.8)
print("M1",json.dumps({"white_sigma_m":.01*math.sqrt(white_u),"objective":white_value,
      "success":bool(white_opt.success),"nfev":white_opt.nfev}),flush=True)
profile=[]
options={"maxiter":50,"maxfun":180,"ftol":1e-10,"gtol":1e-5}
for tau in declaration["bounded_optimization_declaration"]["tau_profile_s"]:
    candidates=[{"u":[white_u,0.0],"objective":white_value,"origin":"EXACT_M1_ENDPOINT"}]
    for x0 in ([white_u,.1],[0.0,1.0]):
        fitted=optimize.minimize(lambda u:loss(u,tau),x0=x0,method="L-BFGS-B",
                                 bounds=[(0,100),(0,100)],options=options)
        candidates.append({"u":fitted.x.tolist(),"objective":float(fitted.fun),"origin":"LBFGSB",
            "start_u":x0,"success":bool(fitted.success),"message":str(fitted.message),
            "nfev":int(fitted.nfev),"nit":int(fitted.nit)})
    best=min(candidates,key=lambda item:item["objective"])
    row={"tau_s":float(tau),"u":best["u"],"restricted_objective":best["objective"],"attempts":candidates}
    profile.append(row)
    print("TAU_PROFILE",json.dumps({k:row[k] for k in ("tau_s","u","restricted_objective")}),flush=True)
best=min(profile,key=lambda row:row["restricted_objective"])
initial=np.r_[best["u"],math.log(best["tau_s"])]
tau_min,tau_max=declaration["tau_working_domain_s"]
refined=optimize.minimize(lambda x:loss(x[:2],math.exp(float(x[2]))),initial,method="L-BFGS-B",
    bounds=[(0,100),(0,100),(math.log(tau_min),math.log(tau_max))],options=options)
if float(refined.fun)<best["restricted_objective"]:
    beta_u=refined.x[:2];beta_tau=math.exp(float(refined.x[2]));beta_value=float(refined.fun)
else:
    beta_u=np.array(best["u"]);beta_tau=best["tau_s"];beta_value=best["restricted_objective"]
parameters={"M0":NoiseParameters(),"M1":NoiseParameters(.01*math.sqrt(white_u),0,.8),
            "M2":NoiseParameters(.01*math.sqrt(float(beta_u[0])),.01*math.sqrt(float(beta_u[1])),beta_tau)}
train_values={name:scalars(evaluate_source_noise_likelihood(training,par)) for name,par in parameters.items()}
freeze={"status":"FROZEN_BEFORE_VALIDATION_ARRAY_READS","parameters":{n:dataclasses.asdict(p) for n,p in parameters.items()},
    "calibration_results":train_values,"tau_profile":profile,
    "M1_optimizer":{"success":bool(white_opt.success),"message":str(white_opt.message),"nfev":int(white_opt.nfev)},
    "M2_refinement":{"success":bool(refined.success),"message":str(refined.message),"nfev":int(refined.nfev),
                     "nit":int(refined.nit),"u_and_log_tau":refined.x.tolist(),"objective":float(refined.fun)},
    "tau_boundary":abs(beta_tau-tau_min)<1e-6 or abs(beta_tau-tau_max)<1e-6,
    "amplitude_variance_boundary":{"white_at_zero":bool(beta_u[0]<1e-6),"beta_at_zero":bool(beta_u[1]<1e-6),
                                   "white_at_upper":bool(beta_u[0]>100-1e-6),"beta_at_upper":bool(beta_u[1]>100-1e-6)},
    "calibration_evaluations":len(history),"calibration_elapsed_s":time.monotonic()-started,
    "declaration_sha256":hashlib.sha256(args.declaration.read_bytes()).hexdigest()}
freeze_path=output/"CALIBRATED_PARAMETERS.json"
freeze_path.write_text(json.dumps(freeze,indent=2)+"\n")
print("FROZEN",json.dumps({"parameters":freeze["parameters"],"tau_boundary":freeze["tau_boundary"],
                            "evaluations":len(history)}),flush=True)
# Validation arrays are first loaded after the parameter receipt has been written.
validation,validation_meta,validation_sources=load_window(declaration["validation_window_s"])
validation_values={name:scalars(evaluate_source_noise_likelihood(validation,par)) for name,par in parameters.items()}
for name,value in validation_values.items():
    value["objective_delta_from_M0"]=value["restricted_objective"]-validation_values["M0"]["restricted_objective"]
    value["objective_delta_from_M1"]=value["restricted_objective"]-validation_values["M1"]["restricted_objective"]
module=repository/"src/legsa_gins/paper_rebuild/joint_navigation/source_noise_likelihood.py"
receipt={"status":"BOUNDED_BY_RESTRICTED_CALIBRATION_AND_FROZEN_VALIDATION_COMPLETE",
    "calibration_input":train_meta,"validation_input":validation_meta,"frozen_model_fit":freeze,
    "validation_results":validation_values,"elapsed_s":time.monotonic()-started,
    "scope":{"reference_reads":0,"navigation_calls":0,"integer_search_calls":0,"testset_reads":0,
             "acceptance_quantile_changed":False,"calibration_not_global_optimality_certificate":True},
    "interpretation_boundaries":["Parameters are measurement-model fits, not integer fixes or navigation qualification.",
        "Validation cost/DOF is a restricted residual diagnostic after continuous integer nuisance fitting, not causal fixed-integer innovation coverage.",
        "No separate receiver variances can be inferred from indistinguishable SD covariance structures.",
        "A boundary or flat tau profile is not an identified physical correlation time.",
        "Held-out data were not used to refit or select parameters; the10s gap does not prove physical independence.",
        "Any model evidence is conditional on free per-epoch linear baseline geometry and source time/known_sd implementation; beta is not uniquely attributable to multipath.",
        "Variance estimates do not calibrate full integer acceptance probability, tails, or partial-domain exclusion."] ,
    "provenance":{"PLAN_sha256":hashlib.sha256(plan_path.read_bytes()).hexdigest(),
                  "frozen_receipt_sha256":hashlib.sha256(freeze_path.read_bytes()).hexdigest(),
                  "module_sha256":hashlib.sha256(module.read_bytes()).hexdigest(),
                  "script_sha256":hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                  "calibration_sources":train_sources,"validation_sources":validation_sources}}
(output/"SUMMARY.json").write_text(json.dumps(receipt,indent=2)+"\n")
(output/"CALIBRATION_EVALUATIONS.json").write_text(json.dumps(history,indent=2)+"\n")
print("VALIDATION",json.dumps({"input":validation_meta,"results":validation_values,"elapsed_s":receipt["elapsed_s"]}),flush=True)
