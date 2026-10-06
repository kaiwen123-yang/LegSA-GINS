#!/usr/bin/env python3
"""Four-chain BY2 carrier integration replay; prepare/native/evaluate are separate.

Reference payload is read only by the frozen evaluator child after all native
outputs have been sealed. Shared old initialization is not an AR cold start.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import io
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import time

import numpy as np
import pandas as pd
import yaml

STAGE_ID = "CARRIER_INTEGRATION_20261006"
INPUT_KEYS = ("imupath", "gnsspath", "raw_doppler_factor_path", "go2_attitude_prior_path")
CASES = ("C0_SCALAR", "C1_DUAL_PVT_VECTOR", "C2_FULL_CARRIER_VECTOR", "C3_PARTIAL_CARRIER_VECTOR")
VARIANT_KEYS = {
    "case_id", "run_id", "run_label", "outputpath", "dual_antenna_measurement_model",
    "baseline3d_source", "baseline3d_path", "external_carrier_baseline_path",
}
CARRIER_COLUMNS = ["measurement_time", "decision_available_time", "b_ecef_x",
    "b_ecef_y", "b_ecef_z", "cov_xx", "cov_xy", "cov_xz", "cov_yx", "cov_yy",
    "cov_yz", "cov_zx", "cov_zy", "cov_zz", "valid"]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def emit(path, value):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x") as f:
        json.dump(value, f, ensure_ascii=False, indent=2, allow_nan=False)
        f.write("\n")


def read(path):
    return json.loads(Path(path).read_text())


def pin(path):
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise ValueError("PIN_REQUIRES_REGULAR_FILE:" + str(path))
    return {"path": str(path), "sha256": sha(path)}


def check_pin(item):
    if sha(item["path"]) != item["sha256"]:
        raise ValueError("PIN_CHANGED:" + item["path"])
    return Path(item["path"])


def clone_config(payload, fields):
    """Replace unique complete config lines, append declared new keys only."""
    result = payload
    changes = []
    for key, value in fields.items():
        rx = re.compile(rb"(?m)^([ \t]*" + re.escape(key.encode()) +
                        rb"[ \t]*:[ \t]*)([^\r\n]*)(\r?\n|$)")
        found = list(rx.finditer(result))
        if len(found) > 1:
            raise ValueError("DUPLICATE_CONFIG_KEY:" + key)
        token = json.dumps(value, ensure_ascii=False, allow_nan=False).encode()
        if found:
            m = found[0]
            before = m.group(2).decode()
            result = result[:m.start(2)] + token + result[m.end(2):]
        else:
            before = None
            result += (b"" if result.endswith(b"\n") else b"\n") + key.encode() + b": " + token + b"\n"
        changes.append({"field": key, "before": before, "after": value})
    return result, changes


def common_contract(configs):
    if len(configs) != len(CASES):
        raise ValueError("FOUR_CASES_REQUIRED")
    normalized = [{k: v for k, v in c.items() if k not in VARIANT_KEYS} for c in configs]
    if any(v != normalized[0] for v in normalized[1:]):
        raise ValueError("NONHEADING_CONFIG_DIFFERENCE")
    c = normalized[0]
    if (c["algorithm_id"] != "AB1110" or c["ablation_variant"] != "AB1110"
            or c["enable_go2_horizontal_velocity_prior"] is not False
            or c["enable_go2_velocity_prior_diagnostic"] is not False
            or c["runtime_contract"] != "research_experiment"
            or c["dual_yaw_prediction_model"] != "lateral_projection"):
        raise ValueError("COMMON_RESEARCH_CONTRACT")
    for key in ("enable_receiver_velocity", "enable_raw_doppler", "enable_source_aware",
                "enable_go2_roll_pitch_prior"):
        if c[key] is not True:
            raise ValueError("COMMON_ACTIVE_SOURCE_REQUIRED:" + key)
    for case, config in zip(CASES, configs):
        expected = "scalar" if case == CASES[0] else "baseline3d"
        if config.get("case_id") != case or config.get("dual_antenna_measurement_model") != expected:
            raise ValueError("FOUR_ARM_MODEL_IDENTITY")
        if case == CASES[1] and config.get("baseline3d_source") != "dual_pvt":
            raise ValueError("PVT_ARM_SOURCE_IDENTITY")
        if case in CASES[2:] and config.get("baseline3d_source") != "external_carrier":
            raise ValueError("CARRIER_ARM_SOURCE_IDENTITY")
    if configs[2]["external_carrier_baseline_path"] == configs[3]["external_carrier_baseline_path"]:
        raise ValueError("FULL_PARTIAL_MUST_HAVE_SEPARATE_SOURCE_FILES")
    return {"identical_outside_heading_and_output_identity": True,
            "HV_disabled_in_all_four": True, "algorithm_id": "AB1110",
            "shared_input_roles": list(INPUT_KEYS),
            "same_shared_initialization_not_AR_cold_start": True}


def carrier_audit(path):
    with Path(path).open(newline="") as f:
        rd = csv.DictReader(f)
        if rd.fieldnames != CARRIER_COLUMNS:
            raise ValueError("EXTERNAL_CARRIER_COLUMN_CONTRACT")
        rows = list(rd)
    times = []; valid = 0
    for row in rows:
        t, a = float(row["measurement_time"]), float(row["decision_available_time"])
        if not np.isfinite([t, a]).all() or t != a or t < 100.0 or t > 340.0:
            raise ValueError("EXTERNAL_CARRIER_AVAILABILITY_TIME")
        times.append(t)
        if row["valid"] not in ("0", "1"):
            raise ValueError("EXTERNAL_CARRIER_VALIDITY")
        if row["valid"] == "0":
            continue
        vector = np.array([float(row[x]) for x in CARRIER_COLUMNS[2:5]])
        covariance = np.array([float(row[x]) for x in CARRIER_COLUMNS[5:14]]).reshape(3, 3)
        if (not np.isfinite(vector).all() or not np.isfinite(covariance).all()
                or not np.allclose(covariance, covariance.T, rtol=0, atol=1e-12)
                or np.linalg.eigvalsh(covariance).min() <= 0):
            raise ValueError("EXTERNAL_CARRIER_FINITE_SPD")
        valid += 1
    if len(times) > 1 and not np.all(np.diff(times) > 0):
        raise ValueError("EXTERNAL_CARRIER_ORDER_OR_DUPLICATE")
    return {"rows": len(rows), "valid_rows": valid, "invalid_rows": len(rows)-valid,
            "first_s": times[0] if times else None, "last_s": times[-1] if times else None,
            "reference_used": False, "decision_equals_measurement_time": True}


def reuse_dual_pvt(root, gnss_path, dest):
    """Reuse the unchanged small sidecar, validating saved raw observation lineage."""
    root = Path(root); metadata = read(root / "PROVIDER_MANIFEST.json")
    prepared_path = root / "PREPARED_RAW_MANIFEST.json"
    if sha(prepared_path) != metadata["prepared_raw_manifest"]["sha256"]:
        raise ValueError("PVT_PREPARED_MANIFEST_PIN")
    prepared = read(prepared_path); source = root / "B3/baseline3d.csv"
    if sha(source) != metadata["providers"]["B3"]["sha256"]:
        raise ValueError("PVT_SIDECAR_PIN")
    if prepared["pinned_r5_source"]["sha256"] != sha(gnss_path):
        raise ValueError("PVT_CURRENT_GNSS18_IDENTITY")
    if (prepared["sequence_id"] != "BY2" or prepared["interpolation_used"]
            or prepared["synthetic_data_used"] or prepared["semisynthetic_data_used"]):
        raise ValueError("PVT_SOURCE_ROLE")
    from legsa_gins.paper_rebuild.hext.t5bc_runtime import validate_sidecar
    gate = validate_sidecar(Path(gnss_path).read_bytes(), source.read_bytes(), manifest=prepared)
    # The archive retains the same contents at a new root; do not open obsolete
    # scratch paths recorded inside old manifests or rehash whole raw logs.
    obs_path = root.parents[1] / "01_CALIBRATION/BY2/RAW_OBSERVATIONS/OBSERVATION_MANIFEST.json"
    if sha(obs_path) != prepared["observation_manifest"]["sha256"]:
        raise ValueError("PVT_OBSERVATION_MANIFEST_PIN")
    obs = read(obs_path)
    if obs["trace_used_online"] or obs["trace_open_count"] != 0:
        raise ValueError("PVT_REFERENCE_ROLE")
    with Path(dest).open("xb") as f:
        f.write(source.read_bytes())
    return {"source": pin(source), "provider_manifest": pin(root/"PROVIDER_MANIFEST.json"),
            "prepared_manifest": pin(prepared_path), "observation_manifest": pin(obs_path),
            "raw_source_hashes_inherited_not_rehashed": prepared["raw_source_hashes"],
            "origin_ecef_m": obs["origin_ecef_m"], "ecef_to_fixed_ned": obs["ecef_to_ned"],
            "gate": gate, "covariance_rule": "native k_b^2*(pAcc1^2+pAcc2^2) * I",
            "k_b": 1.0, "historical_calibrated_k_b_reused": False,
            "fixed_NED_origin": "first simultaneous GNSS1 HP position before start",
            "source_position_messages_not_carrier_AR": True}


def source_pins(code):
    paths = list((code/"cpp/legsa_v23_port_core").rglob("*.cpp"))
    paths += list((code/"cpp/legsa_v23_port_core").rglob("*.hpp"))
    paths += [Path(__file__), code/"src/legsa_gins/paper_rebuild/protocol_v3/evaluation_process.py",
              code/"src/legsa_gins/paper_rebuild/clean5_parity/evaluation.py"]
    return {str(p.relative_to(code)): sha(p) for p in paths}


def prepare(a):
    stage = a.stage; stage.mkdir(parents=True, exist_ok=False)
    prior = read(a.prior_prereg)
    seq = prior["sequences"]["BY2"]
    run = next(r for r in prior["runs"] if r["sequence_id"] == "BY2" and r["method_id"] == "F04")
    if len(run["children"]) != 1 or seq["gaps"] or seq["window"] != [66.0, 340.0]:
        raise ValueError("BY2_SINGLE_CONTIGUOUS_COMMON_WINDOW_REQUIRED")
    original = check_pin(run["children"][0]["config"])
    original_bytes = original.read_bytes(); base = yaml.safe_load(original_bytes)
    # Pin the active shared providers and binary, without opening the reference.
    inputs = {k: pin(base[k]) for k in INPUT_KEYS}
    binary = pin(a.binary); checker = pin(a.config_check)
    inp = stage/"INPUTS"; inp.mkdir()
    pvt = inp/"DUAL_PVT_BASELINE3D.csv"
    pvt_lineage = reuse_dual_pvt(a.dual_pvt_root, base["gnsspath"], pvt)
    carriers = {}; carrier_gates = {}; carrier_sources = {}
    for case, source in [(CASES[2], a.carrier_full), (CASES[3], a.carrier_partial)]:
        path = inp/(case + ".csv")
        with path.open("xb") as f: f.write(Path(source).read_bytes())
        carriers[case] = path
        carrier_gates[case] = carrier_audit(path)
        carrier_sources[case] = pin(source)
    runs=[]; configs=[]; configdir=stage/"CONFIGS"; configdir.mkdir()
    for case in CASES:
        fields = {
            "stage_id": STAGE_ID, "protocol_id": "EXPERIMENTAL_CARRIER_VS_POSITION_HEADING",
            "case_id": case, "run_id": case, "run_label": case,
            "runtime_contract": "research_experiment", "runtime_role": "experimental_navigation_solver",
            "algorithm_id": "AB1110", "ablation_variant": "AB1110",
            "enable_go2_horizontal_velocity_prior": False,
            "enable_go2_velocity_prior_diagnostic": False,
            "outputpath": str(stage/"NATIVE"/case),
            "dual_yaw_prediction_model": "lateral_projection",
            "baseline3d_length_m": .35, "baseline3d_k_b": 1.,
            "baseline3d_body_vector_m": [0., -.35, 0.],
            "dual_antenna_measurement_model": "scalar" if case == CASES[0] else "baseline3d",
        }
        if case == CASES[1]:
            fields.update(baseline3d_source="dual_pvt", baseline3d_path=str(pvt))
        if case in carriers:
            fields.update(baseline3d_source="external_carrier", external_carrier_baseline_path=str(carriers[case]))
        payload, changes = clone_config(original_bytes, fields)
        config = configdir/(case+".yaml"); config.write_bytes(payload)
        configs.append(yaml.safe_load(payload))
        runs.append({"case": case, "config": pin(config), "changes": changes})
    gate = common_contract(configs)
    completed = subprocess.run([str(a.config_check), *[r["config"]["path"] for r in runs]],
                               capture_output=True, text=True)
    emit(stage/"CONFIG_LOADER_CHECK.json", {"returncode": completed.returncode,
        "stdout": completed.stdout, "stderr": completed.stderr, "solver_invocations": 0,
        "checker": checker})
    if completed.returncode != 0:
        raise RuntimeError("CONFIG_LOADER_REJECTED_NO_NATIVE")
    plan = {"schema": "carrier_navigation_trial.v1", "stage": STAGE_ID,
        "source_prior_prereg": pin(a.prior_prereg), "source_config": pin(original),
        "source_sha256": source_pins(a.code), "binary": binary, "checker": checker,
        "sequence": seq, "runs": runs, "active_shared_inputs": inputs,
        "common_contract": gate, "dual_pvt_input": pin(pvt), "dual_pvt_lineage": pvt_lineage,
        "external_carrier_inputs": {k: pin(v) for k, v in carriers.items()},
        "external_carrier_sources": carrier_sources,
        "external_carrier_gates": carrier_gates,
        "solver_budget": len(CASES), "evaluator_budget": len(CASES), "starttime": base["starttime"],
        "endtime": base["endtime"], "reference_reads_in_prepare": 0,
        "initialization": {"source": base["common_initialization_source"],
            "dual_yaw_used": base["common_initialization_dual_yaw_used"],
            "unchanged_across_cases": True, "AR_cold_start": False},
        "comparison_scope": "common AB1110 (HV off), not complete unchanged V3 F04",
        "evaluation_frame": "frozen v3 antenna-midpoint transform; all non-LLH tokens unchanged",
        "real_integer_truth_available": False}
    emit(stage/"PLAN.json", plan)
    print("PREPARED_4_CONFIGS_NO_NATIVE_NO_REFERENCE", flush=True)


def checked_plan(a):
    plan=read(a.stage/"PLAN.json")
    for rel, value in plan["source_sha256"].items():
        if sha(a.code/rel) != value:
            raise ValueError("SCIENTIFIC_SOURCE_CHANGED:"+rel)
    for item in [plan["binary"], plan["source_prior_prereg"], plan["source_config"],
                 *plan["active_shared_inputs"].values(), plan["dual_pvt_input"],
                 *plan["external_carrier_inputs"].values(), *[r["config"] for r in plan["runs"]]]:
        check_pin(item)
    return plan



def manifest_checks(manifest, case):
    if (manifest.get("runtime_contract") != "research_experiment"
            or manifest.get("algorithm_id") != "AB1110"
            or manifest.get("run_id") != case
            or manifest.get("dual_yaw_prediction_model") != "lateral_projection"
            or manifest.get("go2_horizontal_velocity_update_count") != 0):
        raise ValueError("NATIVE_EFFECTIVE_RESEARCH_CONTRACT")
    if manifest.get("research_RD_RP_policy") != "past_only_each_source_timestamp_attempted_at_most_once":
        raise ValueError("NATIVE_RD_RP_CAUSAL_CONTRACT")
    if case != CASES[0] and (manifest.get("dual_antenna_measurement_model") != "baseline3d"
            or manifest.get("baseline3d_scalar_yaw_observation_used") is not False):
        raise ValueError("NATIVE_VECTOR_SOURCE_EXCLUSIVITY")
    if case in CASES[2:] and (manifest.get("baseline3d_source") != "external_carrier"
            or manifest.get("external_carrier_valid_is_trusted_FIX") is not False
            or manifest.get("external_carrier_k_b_used") is not False):
        raise ValueError("NATIVE_CARRIER_IDENTITY")
    return {k: v for k, v in manifest.items() if k.endswith("_count")
            or k in ("cov_health_status", "runtime_contract", "research_RD_RP_policy",
                     "research_event_schedule", "baseline3d_frame_contract")}


def launch(argv, cwd, output, timeout=1200):
    env={**os.environ, "OMP_NUM_THREADS":"1", "OPENBLAS_NUM_THREADS":"1", "MKL_NUM_THREADS":"1"}
    with (output/"stdout.log").open("x") as out, (output/"stderr.log").open("x") as err:
        child=subprocess.Popen(argv,cwd=cwd,env=env,stdout=out,stderr=err,start_new_session=True)
        try:
            return child.wait(timeout=timeout), False
        except subprocess.TimeoutExpired:
            os.killpg(child.pid, signal.SIGKILL); child.wait()
            return child.returncode, True


def native(a):
    from legsa_gins.paper_rebuild.clean5_sequence.io_audit import audited_open_records
    plan=checked_plan(a); records=[]
    for r in plan["runs"]:
        out=a.stage/"NATIVE"/r["case"]; out.mkdir(parents=True,exist_ok=False)
        argv=["strace","-f","-qq","-s","4096","-e","trace=openat,execve",
              "-o",str(out/"OPENAT.strace"),plan["binary"]["path"],
              "--config",r["config"]["path"],"--output-dir",str(out)]
        emit(out/"INVOCATION.json",{"argv":argv,"plan_sha256":sha(a.stage/"PLAN.json"),
                                   "time_unix":time.time(),"solver_call_reserved":True})
        started=time.monotonic(); code,timed_out=launch(argv,a.code,out)
        opens=audited_open_records(out/"OPENAT.strace",a.code)
        tr=sum(x["path"]==plan["sequence"]["trace_path"] for x in opens)
        rec={"case":r["case"],"returncode":code,"timed_out":timed_out,
             "runtime_seconds":time.monotonic()-started,"online_reference_opens":tr,
             "status":"COMPLETED" if code==0 and not timed_out and tr==0 else "FAILED"}
        if rec["status"]=="COMPLETED":
            manifest=read(out/"RUN_MANIFEST.json")
            rec["runtime_checks"]=manifest_checks(manifest,r["case"])
            rec["runtime_manifest"]=pin(out/"RUN_MANIFEST.json")
            nav=np.loadtxt(out/"KF_GINS_Navresult.nav",ndmin=2,comments="%")
            std=np.loadtxt(out/"KF_GINS_STD.txt",ndmin=2,comments="%")
            if len(nav)!=len(std) or not np.isfinite(nav).all() or not np.isfinite(std).all():
                raise ValueError("NAV_STD_FINITE_OR_SUPPORT")
            if not np.all(np.diff(nav[:,1])>0):
                raise ValueError("NAV_TIME_ORDER")
            rec.update(output_rows=len(nav),first_time=float(nav[0,1]),last_time=float(nav[-1,1]),
                time_keys_sha256=hashlib.sha256(nav[:,1].copy().tobytes()).hexdigest(),
                nav=pin(out/"KF_GINS_Navresult.nav"),std=pin(out/"KF_GINS_STD.txt"))
        emit(out/"RESULT.json",rec); records.append(rec)
        print(r["case"],rec["status"],flush=True)
        if rec["status"]!="COMPLETED":
            raise RuntimeError("NATIVE_FAILED_PRESERVED_NO_RETRY")
    if len({r["time_keys_sha256"] for r in records})!=1:
        raise ValueError("NAV_SHARED_TIME_SUPPORT")
    emit(a.stage/"ALL_NATIVE_SEALED.json",{"status":"SEALED","plan_sha256":sha(a.stage/"PLAN.json"),
        "solver_calls":len(CASES),"records":records,"reference_reads":0,
        "files":{str(p.relative_to(a.stage)):sha(p) for p in (a.stage/"NATIVE").rglob("*") if p.is_file()}})
    print("ALL_4_NATIVE_SEALED",flush=True)


def evaluate(a):
    from legsa_gins.paper_rebuild.clean5_parity.evaluation import transform_nav, write_transformed_nav
    from legsa_gins.paper_rebuild.protocol_v3.evaluation_process import evaluate as evaluator, EVALUATOR_SHA256
    plan=checked_plan(a); seal=read(a.stage/"ALL_NATIVE_SEALED.json")
    if seal["status"]!="SEALED" or seal["plan_sha256"]!=sha(a.stage/"PLAN.json") or len(seal["records"])!=len(CASES):
        raise ValueError("COMPLETE_NATIVE_SEAL_REQUIRED")
    for rel,d in seal["files"].items():
        if sha(a.stage/rel)!=d: raise ValueError("NATIVE_SEAL_CHANGED:"+rel)
    if sha(a.evaluator)!=EVALUATOR_SHA256:raise ValueError("FROZEN_EVALUATOR_IDENTITY")
    seq=plan["sequence"]; results=[]; supports=[]
    for r in seal["records"]:
        nav=check_pin(r["nav"]); std=check_pin(r["std"])
        out=a.stage/"EVALUATION"/r["case"]; out.mkdir(parents=True,exist_ok=False)
        target=out/"EVAL_NAV.nav"
        numeric=np.loadtxt(nav,ndmin=2,comments="%")
        write_transformed_nav(nav,target,transform_nav(numeric,seq["baseline_median_m"]))
        result=evaluator(evaluator=a.evaluator,trace=Path(seq["trace_path"]),nav=target,std=std,
            outdir=out/"FROZEN_EVALUATOR",base_time=seq["base_time"],window=seq["window"],
            trace_sha256=seq["trace_sha256"],code_root=a.code,raw_root=Path(seq["raw_root"]),
            clean_root=a.clean_root,instrument=True,consistency_policy="canonical_v2_wgs84_full_support")
        emit(out/"EVALUATOR_RESULT.json",result)
        if not result["audit"]["passed"] or not result["capture"]["consistency"]["passed"]:
            raise ValueError("EVALUATOR_AUDIT_OR_CONSISTENCY")
        errors=pd.read_csv(out/"FROZEN_EVALUATOR/error_series.csv")
        t=errors.time.to_numpy(); supports.append(hashlib.sha256(t.copy().tobytes()).hexdigest())
        for name,mask in [("full_66_340",np.ones(len(t),dtype=bool)),
                          ("before_carrier_66_100",t<100),("carrier_scope_100_340",t>=100)]:
            if not mask.any():raise ValueError("EMPTY_REGISTERED_EVALUATION_DOMAIN")
            row={"case":r["case"],"domain":name,"epochs":int(mask.sum()),
                 "first_time":float(t[mask][0]),"last_time":float(t[mask][-1])}
            for col,key in [("horizontal_err_m","H_RMSE_m"),("err_u_m","V_RMSE_m"),
                            ("position_3d_err_m","D3_RMSE_m"),("yaw_err_deg","yaw_RMSE_deg")]:
                v=errors[col].to_numpy()[mask]
                row[key]=float(np.sqrt(np.mean(v*v)))
                row[key.replace("RMSE","max_abs")]=float(np.max(np.abs(v)))
            results.append(row)
    if len(set(supports))!=1:raise ValueError("EVALUATION_SHARED_TIME_SUPPORT")
    with (a.stage/"NAVIGATION_RESULTS.csv").open("x",newline="") as f:
        writer=csv.DictWriter(f,fieldnames=list(results[0]),lineterminator="\n")
        writer.writeheader();writer.writerows(results)
    emit(a.stage/"EVALUATION_COMPLETE.json",{"evaluator_calls":len(CASES),"rows":len(results),
        "plan_sha256":sha(a.stage/"PLAN.json"),"native_seal_sha256":sha(a.stage/"ALL_NATIVE_SEALED.json"),
        "same_matched_time_keys":True,"reference":"receiver-derived evaluation reference; not independent truth",
        "files":{str(p.relative_to(a.stage)):sha(p) for p in (a.stage/"EVALUATION").rglob("*") if p.is_file()}})
    print("ALL_4_EVALUATED",flush=True)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("phase",choices=["prepare","native","evaluate"])
    for key in ("stage","code","prior-prereg","binary","config-check","dual-pvt-root",
                "carrier-full","carrier-partial","evaluator","clean-root"):
        parser.add_argument("--"+key,type=Path,required=key in ("stage","code"))
    a=parser.parse_args()
    if os.uname().sysname!="Linux":raise RuntimeError("Ubuntu WSL required")
    globals()[a.phase](a)


if __name__=="__main__":main()
