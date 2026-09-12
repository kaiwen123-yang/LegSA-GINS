"""A2 known-C00 and synthetic selection gates for the unchanged evaluator.

Raw reference contents are opened only by evaluation_process.evaluate's child.
The parent reads their expected digest from the locked BY2 metadata. Synthetic
inputs and their evaluations remain in the identity attempt and never enter
real-sequence result tables. A2-3 header evidence is joined by the caller.
"""
from __future__ import annotations

import ast
import csv
from hashlib import sha256
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

from ..canonical541 import offline_eval_aggregate as canonical
from ..manifest import sha256_file
from . import evaluation_process
from .generation_audit import selected_lock

TRACE_HEADER = ("time","lat","lon","height","processed_lat","processed_lon","processed_height","yaw","pitch","roll")
EXPECTED_COLUMNS = {key:key for key in ("time","lat","lon","height","yaw","pitch","roll")}
C00 = {"A04":{"run_id":"RUN_00006","directory":"10_INTERNAL_ABLATION_RUNS","profile":"AB1011","yaw_round6":1.934076},
       "F04":{"run_id":"RUN_00004","directory":"08_FULL_ALGORITHM_RUNS","profile":"AB1111","yaw_round6":1.954959}}
METRIC_SUMMARY_PATHS = {
    "horizontal_rmse_m":("position","horizontal_rmse_m"),
    "horizontal_p95_m":("position","horizontal_p95_m"),
    "horizontal_max_m":("position","horizontal_max_m"),
    "position_3d_rmse_m":("position","position_3d_rmse_m"),
    "up_rmse_m":("position","up_rmse_m"),
    "up_p95_absolute_m":("position","vertical_p95_m"),
    "up_max_absolute_m":("position","vertical_max_m"),
    "yaw_rmse_deg":("attitude","yaw_rmse_deg"),
    "yaw_p95_absolute_deg":("attitude","yaw_p95_deg"),
    "yaw_max_absolute_deg":("attitude","yaw_max_deg"),
}
C00_RELATIVE_TOLERANCE = 1e-10
C00_NATIVE_TERMINAL_STATUS = "COMPLETED_EVALUABLE"
SYNTHETIC_POSITION_BOUND_M = 0.001
SYNTHETIC_OFFSET_M = 1000.0
SYNTHETIC_OFFSET_TOLERANCE_M = 0.01
SYNTHETIC_YAW_SHIFT_DEG = 90.0
SYNTHETIC_YAW_TOLERANCE_DEG = 1e-10
ELLIPSOID_A = 6378137.0
ELLIPSOID_E2 = 6.69437999014e-3


def _file_record(path):
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise ValueError("Identity input/output is missing or a symlink: "+str(path))
    return {"path":str(path),"sha256":sha256_file(path),"bytes":path.stat().st_size}


def source_proof(evaluator):
    identity = _file_record(evaluator)
    if identity["sha256"]!=evaluation_process.EVALUATOR_SHA256:
        raise ValueError("Exact archived evaluator SHA256 differs")
    text = Path(evaluator).read_text(encoding="utf-8")
    tree = ast.parse(text)
    node = next(node for node in tree.body if isinstance(node,ast.FunctionDef) and node.name=="load_trace")
    selected_source = "".join(text.splitlines(keepends=True)[node.lineno-1:node.end_lineno])
    roles = {"time_col":"time","lat_col":"lat","lon_col":"lon","alt_col":"height",
             "yaw_col":"yaw","pitch_col":"pitch","roll_col":"roll"}
    resolution = {}
    for assignment in node.body:
        if not isinstance(assignment,ast.Assign) or len(assignment.targets)!=1 or not isinstance(assignment.targets[0],ast.Name):
            continue
        variable = assignment.targets[0].id
        if variable not in roles:
            continue
        if (not isinstance(assignment.value,ast.Call) or not isinstance(assignment.value.func,ast.Name)
                or assignment.value.func.id!="find_col"):
            raise ValueError("Archived column assignment no longer calls find_col")
        candidates = ast.literal_eval(assignment.value.args[0])
        selected = next((column for candidate in candidates for column in TRACE_HEADER
                         if candidate.lower()==column.lower() or candidate.lower() in column.lower()),None)
        role = roles[variable]
        resolution[role] = {"variable":variable,"assignment_source_line":assignment.lineno,
            "candidate_names":candidates,"expected_synthetic_column":selected,
            "source_line_text":text.splitlines()[assignment.lineno-1]}
    if set(resolution)!=set(EXPECTED_COLUMNS):
        raise ValueError("Archived column-selection source proof lacks required assignments")
    return {**identity,"source_function":"load_trace","line_start":node.lineno,"line_end":node.end_lineno,
        "function_source_sha256":sha256(selected_source.encode()).hexdigest(),
        "selection_semantics":"ordered candidate names, then ordered source header; case-insensitive exact-or-substring match",
        "synthetic_header":list(TRACE_HEADER),"expected_selected_columns":EXPECTED_COLUMNS,
        "column_resolution":resolution,"unselected_synthetic_columns":["processed_lat","processed_lon","processed_height"],
        "processed_column_nonselection_reason":"The earlier plain header column satisfies each candidate before its processed counterpart",
        "plain_geodetic_precedes_processed_geodetic":True,
        "time_conversion":"time-base_time unless selected name contains aligned_time",
        "yaw_conversion":"unwrap reference yaw; wrap360(90-yaw_enu); wrap-safe residual",
        "evaluator_modified":False}


def _lla_to_ecef(lat,lon,height):
    phi,lam = math.radians(lat),math.radians(lon)
    normal = ELLIPSOID_A/math.sqrt(1-ELLIPSOID_E2*math.sin(phi)**2)
    return np.array(((normal+height)*math.cos(phi)*math.cos(lam),
                     (normal+height)*math.cos(phi)*math.sin(lam),
                     (normal*(1-ELLIPSOID_E2)+height)*math.sin(phi)),dtype=float)


def _ecef_to_lla(xyz):
    x,y,z = (float(value) for value in xyz)
    p = math.hypot(x,y)
    phi = math.atan2(z,p*(1-ELLIPSOID_E2))
    for _ in range(20):
        normal = ELLIPSOID_A/math.sqrt(1-ELLIPSOID_E2*math.sin(phi)**2)
        height = p/math.cos(phi)-normal
        phi = math.atan2(z,p*(1-ELLIPSOID_E2*normal/(normal+height)))
    normal = ELLIPSOID_A/math.sqrt(1-ELLIPSOID_E2*math.sin(phi)**2)
    return (math.degrees(phi),math.degrees(math.atan2(y,x)),p/math.cos(phi)-normal)


def create_synthetic_inputs(root):
    """Construct exact ECEF straight motion and a fixed Euclidean 1000 m shift."""
    root = Path(root)
    root.mkdir(parents=True,exist_ok=False)
    base_time = 1000.0
    times = np.arange(10.,21.,1.)
    origin = _lla_to_ecef(30.,114.,40.)
    motion = np.array((2.,-1.,.5))
    offset = np.array((1.,2.,3.))/math.sqrt(14)*SYNTHETIC_OFFSET_M
    plain,shifted,yaws = [],[],[]
    for time_value in times:
        point = origin+(time_value-times[0])*motion
        plain.append(_ecef_to_lla(point))
        shifted.append(_ecef_to_lla(point+offset))
        yaws.append(30.+2.*(time_value-times[0]))
    if any(any(left==right for left,right in zip(a,b)) for a,b in zip(plain,shifted)):
        raise ValueError("Synthetic offset must change all three geodetic fields")
    trace_paths = {}
    for variant in ("plain","swap","yaw90"):
        path = root/f"synthetic_reference_{variant}.csv"
        with path.open("x",encoding="utf-8",newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(TRACE_HEADER)
            for time_value,actual,displaced,yaw in zip(times,plain,shifted,yaws):
                first,second = (displaced,actual) if variant=="swap" else (actual,displaced)
                values = [base_time+time_value,*first,*second,yaw+(90. if variant=="yaw90" else 0.),0.,0.]
                writer.writerow(format(value,".17g") for value in values)
        trace_paths[variant] = _file_record(path)
    nav,std = root/"SYNTHETIC_NAV.nav",root/"SYNTHETIC_STD.txt"
    with nav.open("x",encoding="utf-8") as handle:
        for time_value,position,yaw in zip(times,plain,yaws):
            values = [0.,time_value,*position,0.,0.,0.,0.,0.,(90.-yaw)%360.]
            handle.write(" ".join(format(value,".17g") for value in values)+"\n")
    with std.open("x",encoding="utf-8") as handle:
        for time_value in times:
            handle.write(" ".join(format(value,".17g") for value in [time_value,*([1.]*9)])+"\n")
    measured = [float(np.linalg.norm(_lla_to_ecef(*a)-_lla_to_ecef(*b))) for a,b in zip(plain,shifted)]
    record = {"data_mode":"synthetic_evaluator_identity_only","synthetic_data_used":True,
        "semisynthetic_data_used":False,"eligible_for_real_result_tables":False,"base_time":base_time,
        "window":[float(times[0]),float(times[-1])],"row_count":len(times),"trace_header":list(TRACE_HEADER),
        "straight_motion_ecef_mps":motion.tolist(),"yaw_rate_deg_per_s":2.,"trace":trace_paths,
        "nav":_file_record(nav),"std":_file_record(std),"processed_offset_ecef_m":offset.tolist(),
        "processed_offset_target_m":SYNTHETIC_OFFSET_M,"processed_offset_min_m":min(measured),
        "processed_offset_max_m":max(measured),"all_three_geodetic_fields_differ":True}
    evaluation_process.write_json(root/"SYNTHETIC_INPUT_MANIFEST.json",record)
    return record


def _result_metrics(result):
    summary = result["summary"]
    metrics = {field:float(summary[group][key]) for field,(group,key) in METRIC_SUMMARY_PATHS.items()}
    path = Path(result["outdir"])/"error_series.csv"
    frame = pd.read_csv(path,encoding="utf-8-sig")
    required = ("time","position_3d_err_m")
    if not all(key in frame for key in required) or frame.empty:
        raise ValueError("Fresh evaluator CSV lacks finite 3D metrics")
    times = frame.time.to_numpy(dtype=float)
    values = frame.position_3d_err_m.to_numpy(dtype=float)
    if not np.isfinite(times).all() or not np.isfinite(values).all():
        raise ValueError("Fresh evaluator 3D errors are nonfinite")
    stats = canonical._norm_stats(times,values)
    metrics.update(position_3d_p95_m=stats["p95"],position_3d_max_m=stats["max"])
    if len(metrics)!=12 or not all(math.isfinite(value) for value in metrics.values()):
        raise ValueError("Fresh evaluator twelve metrics are nonfinite")
    return metrics


def _capture_gate(result, *, expected_header=None, proof=None):
    capture = result.get("capture") or {}
    if result.get("audit",{}).get("passed") is not True:
        raise ValueError("Evaluator open/write audit did not pass")
    if (capture.get("selected_columns")!=EXPECTED_COLUMNS or capture.get("trace_handle_hash_count")!=1
            or capture.get("observation_only") is not True):
        raise ValueError("Evaluator did not observe the frozen plain column selection")
    if expected_header is not None and capture.get("trace_header")!=list(expected_header):
        raise ValueError("Synthetic reference header changed")
    return {"passed":True,"selected_columns":capture["selected_columns"],
        "actual_column_resolution":{role:{"selected_column":column,
            "assignment_source_line":None if proof is None else proof["column_resolution"][role]["assignment_source_line"]}
            for role,column in capture["selected_columns"].items()},
        "trace_header":capture.get("trace_header"),"trace_handle_hash_count":1,
        "trace_sha256":capture.get("trace_sha256"),"observation_only":True,
        "consistency":capture.get("consistency")}


def _run_record(result):
    return {"audit":result["audit"],"capture":result.get("capture"),"outdir":result["outdir"],
        "summary":_file_record(Path(result["outdir"])/"summary.json"),
        "error_series":_file_record(Path(result["outdir"])/"error_series.csv")}


def run_synthetic(*,registry,evaluator,identity_root,proof):
    root = Path(identity_root)
    result = {"passed":False,"status":"IN_PROGRESS","source_proof":proof,"runs":[],
        "data_mode":"synthetic_evaluator_identity_only","synthetic_data_used":True,
        "eligible_for_real_result_tables":False,"failures":[]}
    try:
        inputs = create_synthetic_inputs(root/"SYNTHETIC_INPUTS")
        result["inputs"] = inputs
        runs = {}
        for name,variant,instrument in (("plain_uninst","plain",False),("plain_inst","plain",True),
                                         ("swap_inst","swap",True),("yaw90_inst","yaw90",True)):
            trace = inputs["trace"][variant]
            run = evaluation_process.evaluate(evaluator=evaluator,trace=trace["path"],nav=inputs["nav"]["path"],
                std=inputs["std"]["path"],outdir=root/"SCRATCH"/name,base_time=inputs["base_time"],window=inputs["window"],
                trace_sha256=trace["sha256"],code_root=registry.code_root,raw_root=registry.raw_root,
                clean_root=registry.clean_root,instrument=instrument)
            runs[name] = run
            record = {"name":name,"variant":variant,"instrumented":instrument,**_run_record(run)}
            result["runs"].append(record)
            if instrument:
                record["selection_gate"] = _capture_gate(run,expected_header=TRACE_HEADER,proof=proof if "column_resolution" in proof else None)
            elif run.get("audit",{}).get("passed") is not True:
                raise ValueError("Uninstrumented evaluator audit failed")
        parity = {}
        for name in ("summary.json","error_series.csv"):
            left,right = Path(runs["plain_uninst"]["outdir"])/name,Path(runs["plain_inst"]["outdir"])/name
            same = left.read_bytes()==right.read_bytes()
            parity[name] = {"byte_identical":same,"uninstrumented_sha256":sha256_file(left),"instrumented_sha256":sha256_file(right)}
            if not same:
                raise ValueError("Observation hook changed baseline evaluator bytes: "+name)
        result["instrumented_uninstrumented_byte_parity"] = parity
        baseline,swapped,yaw = (_result_metrics(runs[name]) for name in ("plain_inst","swap_inst","yaw90_inst"))
        checks = {"plain_nav_matches_plain_columns":all(baseline[key]<=SYNTHETIC_POSITION_BOUND_M for key in
                    ("position_3d_rmse_m","position_3d_p95_m","position_3d_max_m")),
            "swapped_plain_columns_have_1000m_error":all(abs(swapped[key]-SYNTHETIC_OFFSET_M)<SYNTHETIC_OFFSET_TOLERANCE_M for key in
                    ("position_3d_rmse_m","position_3d_p95_m","position_3d_max_m")),
            "yaw_column_plus_90_changes_yaw_error_by_90":all(abs(yaw[key]-SYNTHETIC_YAW_SHIFT_DEG)<=SYNTHETIC_YAW_TOLERANCE_DEG for key in
                    ("yaw_rmse_deg","yaw_p95_absolute_deg","yaw_max_absolute_deg")),
            "baseline_yaw_matches":baseline["yaw_max_absolute_deg"]<=SYNTHETIC_YAW_TOLERANCE_DEG}
        result.update(checks=checks,metrics={"plain":baseline,"swap":swapped,"yaw90":yaw},
            thresholds={"matching_position_max_m":SYNTHETIC_POSITION_BOUND_M,"shift_target_m":SYNTHETIC_OFFSET_M,
                "shift_absolute_tolerance_m":SYNTHETIC_OFFSET_TOLERANCE_M,"yaw_shift_deg":SYNTHETIC_YAW_SHIFT_DEG,
                "yaw_tolerance_deg":SYNTHETIC_YAW_TOLERANCE_DEG})
        if not all(checks.values()):
            raise ValueError("Synthetic trace selection/geometry gate failed")
        result.update(passed=True,status="PASS_SYNTHETIC_COLUMN_SELECTION_AND_HOOK_PARITY")
    except Exception as exc:
        result.update(status="FAIL_SYNTHETIC_IDENTITY")
        result["failures"].append(f"{type(exc).__name__}: {exc}")
    evaluation_process.write_json(root/"A2_2_SYNTHETIC_GATE.json",result)
    return result


def _c00_rows(path):
    selected = {}
    with Path(path).open(encoding="utf-8-sig",newline="") as handle:
        reader = csv.DictReader(handle)
        for number,row in enumerate(reader,2):
            method = row.get("method_id")
            if method not in C00 or row.get("run_id")!=C00[method]["run_id"]:
                continue
            if method in selected or row.get("case_id")!="C00_clean_normal":
                raise ValueError("Frozen C00 identity is duplicated or differs")
            selected[method] = {"row":row,"physical_csv_row":number}
    if set(selected)!=set(C00):
        raise ValueError("Frozen table lacks C00 A04/F04 identities")
    return selected


def compare_c00(metrics, frozen, *, method):
    comparisons = []
    for field,value in metrics.items():
        token = frozen["row"].get(field)
        expected = float(token)
        if not math.isfinite(expected):
            raise ValueError("Frozen C00 metric is nonfinite: "+field)
        difference = abs(value-expected)
        relative = difference/abs(expected) if expected!=0 else (0.0 if value==0 else None)
        passed = value==0 if expected==0 else relative<=C00_RELATIVE_TOLERANCE
        comparisons.append({"field":field,"frozen_token":token,"frozen_value":expected,
            "fresh_value":value,"absolute_difference":difference,"relative_difference":relative,
            "relative_tolerance":C00_RELATIVE_TOLERANCE,"zero_reference_requires_exact_zero":True,
            "passed":passed,"frozen_physical_csv_row":frozen["physical_csv_row"]})
    rounded = round(metrics["yaw_rmse_deg"],6)
    yaw_gate = {"fresh_yaw_rmse_rounded_6":rounded,"required_yaw_rmse_rounded_6":C00[method]["yaw_round6"],
                "passed":rounded==C00[method]["yaw_round6"]}
    return {"passed":len(comparisons)==12 and all(row["passed"] for row in comparisons) and yaw_gate["passed"],
            "metric_comparisons":comparisons,"yaw_round6_gate":yaw_gate}


def _c00_seal(attempt):
    """Read the Canonical seal metadata, selecting only the two C00 inputs."""
    root = Path(attempt)/"11_OUTPUT_SEAL"
    manifest_path,journal_path = root/"OUTPUT_HASH_MANIFEST.csv",root/"OUTPUT_SEAL_JOURNAL.json"
    journal = json.loads(journal_path.read_text(encoding="utf-8"))
    files = {"output_hash_manifest":_file_record(manifest_path),"output_seal_journal":_file_record(journal_path)}
    if (journal.get("schema_version")!="paper_rebuild.canonical541_output_seal.v1"
            or journal.get("passed") is not True or journal.get("sealed_before_offline_trace") is not True
            or journal.get("trace_open_count_before_seal")!=0
            or journal.get("manifest_sha256")!=files["output_hash_manifest"]["sha256"]
            or journal.get("unique_registry_sha256")!=sha256_file(root/"UNIQUE_RUN_TERMINAL_REGISTRY.csv")):
        raise ValueError("Canonical C00 seal journal/manifest/registry integrity mismatch")
    wanted = {item["run_id"] for item in C00.values()}
    names = {"KF_GINS_Navresult.nav","KF_GINS_STD.txt","RUN_MANIFEST.json"}
    selected = {}
    count = 0
    with manifest_path.open(encoding="utf-8-sig",newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            count += 1
            if row.get("run_id") not in wanted or row.get("relative_path") not in names:
                continue
            key = (row["run_id"],row["relative_path"])
            if key in selected:
                raise ValueError("Duplicate C00 file in Canonical seal")
            if row.get("terminal_status")!=C00_NATIVE_TERMINAL_STATUS or str(row.get("sealed_before_trace")).lower()!="true":
                raise ValueError("C00 file lacks evaluable pre-trace seal status")
            selected[key] = {**row,"physical_csv_row":reader.line_num}
    if count!=journal.get("file_count") or set(selected)!={(run,name) for run in wanted for name in names}:
        raise ValueError("Canonical seal lacks the exact six C00 NAV/STD/manifest entries")
    return {"files":files,"selected":selected,"manifest_row_count":count}


def _check_sealed_input(current, sealed, *, output):
    if (Path(sealed["run_root"])!=output or current["sha256"]!=sealed["sha256"]
            or current["bytes"]!=int(sealed["size_bytes"])):
        raise ValueError("C00 input hash/size/path differs from Canonical output seal: "+current["path"])
    return {**current,"seal_sha256":sealed["sha256"],"seal_size_bytes":int(sealed["size_bytes"]),
            "seal_physical_csv_row":sealed["physical_csv_row"],"matches_frozen_seal":True}


def run_known_c00(*,registry,canonical_attempt,evaluator,identity_root,proof=None):
    root,attempt = Path(identity_root),Path(canonical_attempt)
    gate = {"passed":False,"status":"IN_PROGRESS","runs":[],"failures":[],
            "data_mode":"frozen_by2_c00_identity_reproduction_only","synthetic_data_used":False}
    try:
        registry_path = attempt/"11_OUTPUT_SEAL/UNIQUE_RUN_TERMINAL_REGISTRY.csv"
        results_path = attempt/"12_OFFLINE_EVALUATION/UNIQUE_EVALUATION_RESULTS.csv"
        identities,expected = _c00_rows(registry_path),_c00_rows(results_path)
        seal = _c00_seal(attempt)
        gate["frozen_sources"] = {"unique_terminal_registry":_file_record(registry_path),"unique_evaluation_results":_file_record(results_path)}
        gate["canonical_output_seal"] = {**seal["files"],"manifest_row_count":seal["manifest_row_count"],
                                        "validation_scope":"six selected C00 NAV/STD/manifest entries; other payloads not opened"}
        seq = registry.sequences["BY2"]
        lock = selected_lock(registry,seq)
        relative = seq.trace_path.relative_to(registry.raw_root).as_posix()
        trace_sha = lock["rows"][relative]["sha256"]
        gate["raw_reference_identity"] = {"path":str(seq.trace_path),"expected_sha256":trace_sha,
            "hash_lock_path":str(lock["path"]),"hash_lock_sha256":lock["sha256"],"parent_reference_open_count":0}
        for method,item in C00.items():
            output = attempt/item["directory"]/item["run_id"]
            native,frozen = identities[method]["row"],expected[method]["row"]
            if (native.get("effective_profile")!=item["profile"] or frozen.get("effective_configuration_id")!=item["profile"]
                    or Path(native["output_root"])!=output or Path(frozen["output_root"])!=output
                    or native.get("terminal_status")!=C00_NATIVE_TERMINAL_STATUS or frozen.get("evaluation_status")!="COMPLETED"):
                raise ValueError("Frozen C00 terminal/profile/output identity differs: "+method)
            inputs = {name:_check_sealed_input(_file_record(output/name),seal["selected"][(item["run_id"],name)],output=output)
                      for name in ("KF_GINS_Navresult.nav","KF_GINS_STD.txt","RUN_MANIFEST.json")}
            run = evaluation_process.evaluate(evaluator=evaluator,trace=seq.trace_path,nav=output/"KF_GINS_Navresult.nav",
                std=output/"KF_GINS_STD.txt",outdir=root/"SCRATCH"/("C00_"+method),base_time=1772784000.0,
                window=[66.0,340.0],trace_sha256=trace_sha,code_root=registry.code_root,raw_root=registry.raw_root,
                clean_root=registry.clean_root,instrument=True)
            record = {"method_id":method,"run_id":item["run_id"],"inputs":inputs,
                      "frozen_registry_physical_csv_row":identities[method]["physical_csv_row"],**_run_record(run)}
            gate["runs"].append(record)
            record["selection_gate"] = _capture_gate(run,proof=proof)
            record["comparison"] = compare_c00(_result_metrics(run),expected[method],method=method)
            if not record["comparison"]["passed"]:
                raise ValueError("C00 twelve-metric reproduction failed: "+method)
        gate.update(passed=True,status="PASS_KNOWN_C00_TWELVE_METRIC_REPRODUCTION")
    except Exception as exc:
        gate.update(status="FAIL_KNOWN_C00_REPRODUCTION")
        gate["failures"].append(f"{type(exc).__name__}: {exc}")
    evaluation_process.write_json(root/"A2_1_C00_REPRODUCTION_GATE.json",gate)
    return gate


def run_known_and_synthetic(registry,canonical_attempt,evaluator,identity_root):
    root = Path(identity_root)
    if (root.is_symlink() or any(parent.is_symlink() for parent in root.parents)
            or registry.raw_root==root or registry.raw_root in root.parents
            or registry.clean_root not in root.parents):
        raise ValueError("Identity root is not a new confined non-raw output directory")
    for name in ("SYNTHETIC_INPUTS","SCRATCH","A2_2_SYNTHETIC_GATE.json","A2_1_C00_REPRODUCTION_GATE.json"):
        if (root/name).exists() or (root/name).is_symlink():
            raise FileExistsError("Identity attempt exists; no retry or overwrite")
    proof = source_proof(evaluator)
    root.mkdir(parents=True,exist_ok=True)
    synthetic = run_synthetic(registry=registry,evaluator=evaluator,identity_root=root,proof=proof)
    known = run_known_c00(registry=registry,canonical_attempt=canonical_attempt,evaluator=evaluator,identity_root=root,proof=proof) if synthetic["passed"] else None
    passed = synthetic["passed"] and known is not None and known["passed"]
    return {"passed_known_and_synthetic":passed,"ready_for_header_gate":passed,"A2_2":synthetic,"A2_1":known,
        "full_identity_gate":"PENDING_A2_3_HEADER_EVIDENCE" if passed else "FAIL_KNOWN_OR_SYNTHETIC",
        "unexecuted_phases":[] if known is not None else ["A2_1_C00_REPRODUCTION","A2_3_TRACE_HEADER_ONLY"],
        "parent_raw_trace_content_open_count":0,"real_sequence_evaluations_executed":0}


run_identity = run_known_and_synthetic
