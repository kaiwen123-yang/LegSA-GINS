"""CLEAN5 sequence-window adapter around the unchanged Canonical statistics.

This module never invokes an evaluator or reads a raw reference. The caller
supplies completed evaluator artifacts, sealed solver identities, header-only
Canonical schemas, and the frozen sequence window.
"""
from __future__ import annotations

import csv
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

from ..canonical541 import offline_eval_aggregate as canonical
from ..manifest import sha256_file
from .runtime_config import METHODS

PAIRWISE_DEFINITIONS = (
    ("full_vs_no_SA","F04","A04"), ("full_vs_strong","F04","F03"),
    ("strong_vs_basic","F03","F02"), ("basic_vs_single","F02","F01"),
    ("no_SA_vs_strong","A04","F03"), ("no_SA_vs_basic","A04","F02"),
)
CANONICAL_CSV_NAMES = (
    "UNIQUE_EVALUATION_RESULTS.csv","LOGICAL_EVALUATION_RESULTS.csv",
    "UNIQUE_METHOD_SUMMARY.csv","LOGICAL_METHOD_SUMMARY.csv",
    "PAIRWISE_CASE_LEVEL.csv","PAIRWISE_SUMMARY.csv","MODULE_ACTION_SUMMARY.csv",
    "RUNTIME_SUMMARY.csv","METRIC_COVERAGE_REPORT.csv",
)
SEGMENT_FIELDS = (
    "run_id","method_id","effective_configuration_id","dataset_id","case_id",
    "segment_id","metric_name","unit","rmse","p95_abs","max_abs","count","signed_mean",
    "time_start","time_end","sequence_window_start_s","sequence_window_end_s",
    "degradation_window_start_s","degradation_window_end_s","secondary_run_epoch_count",
)
RESULT_OVERRIDE_FIELDS = ("output_epoch_count","coverage_ratio","reference_epoch_count")
SEGMENT_METRICS = (
    ("horizontal","horizontal_err_m","m",False),
    ("position_3d","position_3d_err_m","m",False),
    ("up","err_u_m","m",True), ("yaw","yaw_err_deg","deg",True),
)


def _window(window):
    start,end = float(window["t_start"]),float(window["t_end"])
    if not math.isfinite(start) or not math.isfinite(end) or start>=end:
        raise ValueError("Sequence V2 window must be finite and ordered")
    return start,end


def _nonnegative_count(value, role):
    if isinstance(value,bool) or not isinstance(value,(int,np.integer)) or value<0:
        raise ValueError(role+" must be a nonnegative integer")
    return int(value)


def compute_sequence_result(registry, case_meta, output_root, eval_dir, *, window,
                            reference_epoch_count, evaluation_runtime, evaluation_invoked,
                            wrapper_runtime_seconds=None, wrapper_exit_code=None):
    """Retain every original result field except the three authorized counts.

    In particular, unmatched_epoch_count is checked against the corrected
    sequence denominator and never rewritten. Native runtime/exit-code fields
    remain native; corresponding wrapper fields are additional provenance.
    """
    start,end = _window(window)
    reference_count = _nonnegative_count(reference_epoch_count,"reference_epoch_count")
    row = canonical._compute_result(registry,case_meta,Path(output_root),Path(eval_dir),
                                   reference_count,evaluation_runtime,evaluation_invoked)
    nav = canonical._read_numeric_table(Path(output_root)/"KF_GINS_Navresult.nav")
    if nav.shape[1]<2:
        raise ValueError("NAV lacks its original time column")
    times = pd.to_numeric(nav.iloc[:,1],errors="coerce").to_numpy(dtype=float)
    if not np.isfinite(times).all() or np.any(np.diff(times)<=0):
        raise ValueError("Original NAV time must be finite and strictly increasing")
    count = int(np.sum((times>=start)&(times<=end)))
    matched = _nonnegative_count(row["matched_epoch_count"],"matched_epoch_count")
    if row["unmatched_epoch_count"] != max(0,count-matched):
        raise ValueError("Original unmatched_epoch_count disagrees with corrected output-minus-matched; unauthorized fourth override refused")
    row.update(output_epoch_count=count,reference_epoch_count=reference_count,
               coverage_ratio=matched/count if count else None)
    if wrapper_runtime_seconds is not None:
        runtime = canonical._float(wrapper_runtime_seconds)
        if runtime is None or runtime<0:
            raise ValueError("Wrapper runtime must be finite and nonnegative")
        wrapper_runtime_seconds = runtime
    if wrapper_exit_code is not None and (isinstance(wrapper_exit_code,bool) or not isinstance(wrapper_exit_code,int)):
        raise ValueError("Wrapper exit code must be an integer or unavailable")
    row.update(dataset_id=registry.get("dataset_id"),wrapper_runtime_seconds=wrapper_runtime_seconds,
               wrapper_exit_code=wrapper_exit_code,sequence_window_start_s=start,sequence_window_end_s=end,
               sequence_count_override_fields_json=json.dumps(RESULT_OVERRIDE_FIELDS))
    return row


def _event_parameters(case_meta):
    text = case_meta.get("degradation_parameters_json") or "{}"
    params = json.loads(text) if isinstance(text,str) else dict(text)
    if not isinstance(params,dict):
        raise ValueError("Frozen degradation parameters must be an object")
    secondary = params.get("secondary_runs",[])
    if not isinstance(secondary,list):
        raise ValueError("Frozen secondary_runs must be a list")
    for interval in secondary:
        if not isinstance(interval,(list,tuple)) or len(interval)!=2:
            raise ValueError("Frozen secondary run must have two unchanged endpoints")
        left,right = (float(value) for value in interval)
        if not math.isfinite(left) or not math.isfinite(right) or left>=right:
            raise ValueError("Frozen secondary interval must be finite and ordered")
    return params,len(secondary)


def segment_rows(errors_frame, *, registry, dataset_id, window, case_meta):
    """Use original norm/axis statistics on fixed input-defined segments.

    Outside is pre union post. Secondary intervals are counted and preserved;
    they never form an exclusion mask or an event-window replacement.
    """
    if dataset_id not in {"BY2H","BY2O"}:
        raise ValueError("Only BY2H/BY2O sequence segment tables are authorized")
    start,end = _window(window)
    required = {"time",*(spec[1] for spec in SEGMENT_METRICS)}
    if not required<=set(errors_frame.columns):
        raise ValueError("Evaluator error frame lacks frozen segment fields")
    times = pd.to_numeric(errors_frame["time"],errors="coerce").to_numpy(dtype=float)
    if not np.isfinite(times).all() or np.any(np.diff(times)<=0):
        raise ValueError("Evaluator error time must be finite and strictly increasing")
    full = (times>=start)&(times<=end)
    params,_ = _event_parameters(case_meta)
    secondary_mask = np.zeros(len(times),dtype=bool)
    for left,right in params.get("secondary_runs",[]):
        secondary_mask |= (times>=float(left))&(times<=float(right))
    event_start,event_end = canonical._event_window(case_meta)
    if dataset_id=="BY2H":
        if params:
            raise ValueError("BY2H has no frozen degradation event")
        masks = {"full":full}
    else:
        if event_start is None or event_end is None or not start<=event_start<event_end<=end:
            raise ValueError("BY2O requires its frozen event wholly inside the sequence window")
        for left,right in params.get("secondary_runs",[]):
            if not start<=float(left)<float(right)<=end:
                raise ValueError("Secondary event must remain wholly inside the sequence window")
        pre,during,post = full&(times<event_start),full&(times>=event_start)&(times<=event_end),full&(times>event_end)
        masks = {"pre":pre,"during":during,"post":post,"outside":pre|post,"full":full}
    rows = []
    for segment,mask in masks.items():
        for metric,field,unit,signed in SEGMENT_METRICS:
            values = pd.to_numeric(errors_frame[field],errors="coerce").to_numpy(dtype=float)
            selected_time,selected_values = times[mask],values[mask]
            stats = (canonical._axis_stats if signed else canonical._norm_stats)(selected_time,selected_values)
            finite = np.isfinite(selected_values)
            count = int(np.sum(finite))
            rows.append({"run_id":registry["run_id"],"method_id":registry["method_id"],
                "effective_configuration_id":registry.get("effective_profile",registry.get("effective_configuration_id")),
                "dataset_id":dataset_id,"case_id":registry["case_id"],"segment_id":segment,
                "metric_name":metric,"unit":unit,"rmse":stats["rmse"],
                "p95_abs":stats["p95_absolute" if signed else "p95"],
                "max_abs":stats["max_absolute" if signed else "max"],"count":count,
                "signed_mean":stats["signed_mean"] if signed else None,
                "time_start":float(selected_time[finite][0]) if count else None,
                "time_end":float(selected_time[finite][-1]) if count else None,
                "sequence_window_start_s":start,"sequence_window_end_s":end,
                "degradation_window_start_s":event_start,"degradation_window_end_s":event_end,
                "secondary_run_epoch_count":int(np.sum(secondary_mask[mask]&finite))})
    return rows


def pairwise_rows(logical):
    """Canonical delta and descriptive formulas for six fixed single-case pairs."""
    if len({row["case_id"] for row in logical})!=1:
        raise ValueError("CLEAN5 summaries describe one natural case per sequence")
    index = {row["method_id"]:row for row in logical}
    if len(index)!=len(logical):
        raise ValueError("Logical method identity is duplicated")
    cases,summaries = [],[]
    for comparison,candidate_id,reference_id in PAIRWISE_DEFINITIONS:
        if candidate_id not in index or reference_id not in index:
            raise ValueError("A fixed CLEAN5 pair is missing a method")
        candidate,reference = index[candidate_id],index[reference_id]
        for metric in canonical.PAIRWISE_METRICS:
            cv,rv = canonical._float(candidate.get(metric)),canonical._float(reference.get(metric))
            if cv is None or rv is None:
                continue
            delta = cv-rv
            relative = delta/abs(rv)*100 if rv!=0 else None
            win,tie,loss = int(delta<-1e-12),int(abs(delta)<=1e-12),int(delta>1e-12)
            cases.append({"comparison":comparison,"candidate_method_id":candidate_id,
                "reference_method_id":reference_id,"metric_name":metric,"case_id":candidate["case_id"],
                "degradation_id":candidate.get("degradation_id"),"case_family":candidate.get("case_family"),
                "seed_id":candidate.get("seed_id"),"candidate_value":cv,"reference_value":rv,
                "delta_candidate_minus_reference":delta,"relative_change_percent":relative,
                "candidate_better":bool(win),"tie":bool(tie)})
            for scope,family in (("overall","ALL"),("family",str(candidate.get("case_family")))):
                summaries.append({"comparison":comparison,"metric_name":metric,"scope":scope,"family":family,
                    "paired_sample_count":1,"mean_delta_candidate_minus_reference":delta,
                    "median_delta_candidate_minus_reference":delta,"std_delta":0.0,"p10_delta":delta,"p90_delta":delta,
                    "mean_relative_change_percent":relative,"median_relative_change_percent":relative,
                    "win_count":win,"tie_count":tie,"loss_count":loss,"win_rate":float(win),
                    "seed_direction_consistency":None,"worst_negative_case":candidate["case_id"],
                    "best_positive_case":candidate["case_id"],
                    "delta_definition":"candidate_minus_reference; negative_is_better",
                    "confidence_interval_status":"NOT_AVAILABLE_SINGLE_CASE",
                    "confidence_interval_lower":None,"confidence_interval_upper":None,
                    "wilcoxon_status":"NOT_AVAILABLE_SINGLE_CASE","wilcoxon_statistic":None,"wilcoxon_pvalue":None,
                    "seed_inference_status":"NOT_AVAILABLE_NATURAL_SEQUENCE_NO_SEEDS"})
    return cases,summaries


def _validate_identity(unique, logical_registry, segments, dataset):
    if dataset not in {"BY2H","BY2O"} or len(unique)!=5 or len(logical_registry)!=7:
        raise ValueError("Sequence tables require exactly five unique and seven logical identities")
    by_method = {row["method_id"]:row for row in unique}
    if set(by_method)!=set(METHODS) or len({row["run_id"] for row in unique})!=5:
        raise ValueError("Unique evaluation method/run identities differ")
    if len({row["case_id"] for row in unique})!=1 or any(row.get("dataset_id")!=dataset for row in unique):
        raise ValueError("Sequence evaluation dataset/case identity differs")
    logical_methods = {row["method_id"]:row for row in logical_registry}
    if set(logical_methods)!={*METHODS,"A01","A02"}:
        raise ValueError("Logical identities must include exactly the two frozen aliases")
    for method,profile in METHODS.items():
        if by_method[method].get("effective_configuration_id")!=profile:
            raise ValueError("Unique effective profile differs")
        logical = logical_methods[method]
        if (logical.get("run_id")!=by_method[method]["run_id"] or logical.get("effective_profile")!=profile
                or logical.get("case_id")!=by_method[method]["case_id"]
                or str(logical.get("execution_alias")).lower()!="false"):
            raise ValueError("Logical result refers to another unique profile")
    for alias,method in (("A01","F04"),("A02","F03")):
        logical = logical_methods[alias]
        if (logical.get("run_id")!=by_method[method]["run_id"]
                or logical.get("effective_profile")!=METHODS[method]
                or str(logical.get("execution_alias")).lower()!="true"
                or logical.get("alias_of")!=method or logical.get("case_id")!=by_method[method]["case_id"]):
            raise ValueError("Frozen logical alias does not refer to its sole unique run")
    expected_segments = {"full"} if dataset=="BY2H" else {"pre","during","post","outside","full"}
    expected = {(row["run_id"],segment,metric[0]) for row in unique for segment in expected_segments for metric in SEGMENT_METRICS}
    actual = [(row["run_id"],row["segment_id"],row["metric_name"]) for row in segments]
    if len(actual)!=len(set(actual)) or set(actual)!=expected:
        raise ValueError("Segment rows are missing, duplicated, or outside the fixed matrix")
    by_run = {row["run_id"]:row for row in unique}
    units = {spec[0]:spec[2] for spec in SEGMENT_METRICS}
    for row in segments:
        source = by_run[row["run_id"]]
        if (row.get("method_id")!=source["method_id"] or row.get("dataset_id")!=dataset
                or row.get("case_id")!=source["case_id"]
                or row.get("effective_configuration_id")!=source["effective_configuration_id"]
                or row.get("unit")!=units[row["metric_name"]]):
            raise ValueError("Segment identity or metric unit differs from its unique run")
        count = _nonnegative_count(row["count"],"segment count")
        secondary = _nonnegative_count(row["secondary_run_epoch_count"],"secondary_run_epoch_count")
        if secondary>count:
            raise ValueError("Secondary epoch count exceeds the retained segment count")


def field_definitions():
    return {"schema_version":"paper_rebuild.clean5.evaluation_field_definitions.v1",
        "original_statistics_source":"canonical541.offline_eval_aggregate._compute_result (called unchanged)",
        "authorized_original_field_overrides":list(RESULT_OVERRIDE_FIELDS),
        "output_epoch_count":"Original NAV column 1 count in closed sequence V2 [t_start,t_end]",
        "reference_epoch_count":"Caller count under the same frozen V2 reference window",
        "coverage_ratio":"matched_epoch_count / corrected output_epoch_count; unavailable for zero output",
        "unmatched_epoch_count":"Original value preserved; gate requires equality to max(0,corrected output count-matched count)",
        "native_solver_runtime_seconds":"Original RUN_MANIFEST runtime_seconds; unavailable stays unavailable",
        "wrapper_runtime_seconds":"Additional sealed CLEAN5_FORMAL_RUN_MANIFEST runtime_seconds; never substitutes native field",
        "wrapper_exit_code":"Additional sealed wrapper exit code; never substitutes solver_returncode",
        "segment_masks":{"pre":"time < main start","during":"main start <= time <= main end",
            "post":"time > main end","outside":"pre union post","full":"closed sequence V2 window"},
        "segment_statistics":"Unchanged Canonical _norm_stats for horizontal/position_3d; _axis_stats for signed up/yaw",
        "p95_abs":"NumPy 95th percentile of finite absolute errors, original Canonical helper",
        "count":"Finite metric samples in each selected segment; no interpolation or missing-sample reconstruction",
        "signed_mean":"Original signed axis mean for up/yaw; unavailable for norm metrics",
        "secondary_run_epoch_count":"Finite metric samples within this segment and the union of frozen closed secondary intervals; all samples remain included",
        "pairwise_delta":"candidate minus reference; negative is better for the frozen error metrics",
        "single_case_inference":"CI/Wilcoxon NOT_AVAILABLE; no bootstrap, seed resampling, or significance claim",
        "reference_identity":"Fixposition same-source offline reference, not independent ground truth",
        "diagonal_consistency":"STD diagonal diagnostic, not full-covariance NEES",
        "unsupported_velocity":"Unavailable because the frozen reference supplies no velocity contract",
        "recovery_time":"Unavailable without a frozen recovery rule; no threshold is invented",
        "header_policy":"Caller-supplied Canonical header names/order retained as prefix; only additional columns appended"}


def build_tables(unique, logical_registry, segments, *, metadata):
    dataset = metadata["dataset_id"]
    _validate_identity(unique,logical_registry,segments,dataset)
    logical = canonical._logical_rows(logical_registry,unique)
    pair_cases,pair_summary = pairwise_rows(logical)
    numeric_unique,numeric_logical = canonical._numeric_fields(unique),canonical._numeric_fields(logical)
    tables = {"UNIQUE_EVALUATION_RESULTS.csv":[dict(row) for row in unique],
        "LOGICAL_EVALUATION_RESULTS.csv":logical,
        "UNIQUE_METHOD_SUMMARY.csv":canonical._summary_rows(unique,("method_id","effective_configuration_id"),numeric_unique),
        "LOGICAL_METHOD_SUMMARY.csv":canonical._summary_rows(logical,("method_id","effective_configuration_id"),numeric_logical),
        "PAIRWISE_CASE_LEVEL.csv":pair_cases,"PAIRWISE_SUMMARY.csv":pair_summary,
        "MODULE_ACTION_SUMMARY.csv":canonical._summary_rows(logical,("method_id","case_family"),
            [field for field in numeric_logical if field in canonical.MODULE_SCALARS or field=="source_aware_touch_rate"]),
        "WINDOW_SEGMENT_SUMMARY.csv":[dict(row) for row in segments]}
    runtime_metrics = [field for field in ("solver_runtime_seconds","evaluation_runtime_seconds","wrapper_runtime_seconds")
        if any(canonical._float(row.get(field)) is not None for row in unique)]
    runtime_rows = []
    for groups in (("method_id",),("case_family",),("method_id","case_family")):
        runtime_rows.extend(canonical._summary_rows(unique,groups,runtime_metrics))
    runtime_rows.append({"method_id":"ALL","case_family":"ALL","metric_name":"total_wall_time_seconds",
                         "count":len(unique),"mean":metadata.get("total_wall_time_seconds"),
                         "total_cpu_time_seconds":metadata.get("total_cpu_time_seconds")})
    tables["RUNTIME_SUMMARY.csv"] = runtime_rows
    coverage = canonical._coverage_report(unique)
    for row in coverage:
        if row["metric_name"] in {"wrapper_runtime_seconds","wrapper_exit_code"}:
            row["source_fields"] = "sealed CLEAN5_FORMAL_RUN_MANIFEST.json"
        elif row["metric_name"] in RESULT_OVERRIDE_FIELDS:
            row["source_fields"] = "frozen sequence V2 window plus original NAV and caller reference count"
    tables["METRIC_COVERAGE_REPORT.csv"] = coverage
    completed = sum(row.get("evaluation_status")=="COMPLETED" for row in unique)
    finite = sum(str(row.get("finite_output")).lower()=="true" for row in unique)
    summary = {**dict(metadata),"schema_version":"paper_rebuild.clean5.final_evaluation_summary.v1",
        "terminal_status":"PASS_SEQUENCE_EVALUATION_AND_AGGREGATE" if completed==finite==5 else "PARTIAL_SEQUENCE_EVALUATION_AND_AGGREGATE",
        "unique_evaluated":completed,"logical_evaluated":sum(row.get("evaluation_status")=="COMPLETED" for row in logical),
        "unique_run_count":5,"logical_result_count":7,"evaluation_failures":5-completed,
        "nonfinite_unique_count":5-finite,"aggregate_completed":True,"plotting_executed":False,
        "pairwise_comparisons":[item[0] for item in PAIRWISE_DEFINITIONS],"paired_case_count_per_comparison":1,
        "statistical_inference_status":"NOT_AVAILABLE_SINGLE_CASE","reference_is_independent_ground_truth":False,
        "alignment_or_search_used":False,"output_correction_used":False,"epoch_deleted_for_metric":False}
    return {"csv_tables":tables,"FINAL_EVALUATION_SUMMARY.json":summary,"FIELD_DEFINITIONS.json":field_definitions()}


def write_tables(output_root, tables, *, canonical_headers):
    """Write only this adapter's named files with exclusive, prefix-stable I/O."""
    root = Path(output_root)
    if root.exists() or root.is_symlink() or any(parent.is_symlink() for parent in root.parents):
        raise FileExistsError("Aggregation output root already exists or has a symlink ancestor")
    csv_tables = tables["csv_tables"]
    expected_names = {*CANONICAL_CSV_NAMES,"WINDOW_SEGMENT_SUMMARY.csv"}
    if set(csv_tables)!=expected_names:
        raise ValueError("Unexpected aggregate file set")
    headers = {}
    for name,rows in csv_tables.items():
        prefix = list(SEGMENT_FIELDS if name=="WINDOW_SEGMENT_SUMMARY.csv" else canonical_headers[name])
        if not prefix or len(prefix)!=len(set(prefix)) or any(not isinstance(field,str) or not field for field in prefix):
            raise ValueError("Canonical header must contain distinct nonempty field names")
        headers[name] = prefix+[field for field in canonical._fields_union(rows) if field not in prefix]
    # All schemas and JSON payloads are checked before creating output files.
    json_text = {name:json.dumps(tables[name],ensure_ascii=False,sort_keys=True,indent=2,allow_nan=False)+"\n"
                 for name in ("FINAL_EVALUATION_SUMMARY.json","FIELD_DEFINITIONS.json")}
    root.mkdir(parents=True)
    files = {}
    for name,rows in csv_tables.items():
        path = root/name
        with path.open("x",encoding="utf-8",newline="") as handle:
            writer = csv.DictWriter(handle,fieldnames=headers[name])
            writer.writeheader()
            writer.writerows({key:canonical._csv_value(row.get(key)) for key in headers[name]} for row in rows)
        files[name] = {"path":str(path),"sha256":sha256_file(path),"bytes":path.stat().st_size,
                       "row_count":len(rows),"header":headers[name]}
    for name,text in json_text.items():
        path = root/name
        with path.open("x",encoding="utf-8") as handle:
            handle.write(text)
        files[name] = {"path":str(path),"sha256":sha256_file(path),"bytes":path.stat().st_size}
    return {"status":"AGGREGATE_FILES_WRITTEN","files":files}
