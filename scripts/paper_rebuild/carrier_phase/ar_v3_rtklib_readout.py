#!/usr/bin/env python3
"""Read-only derivation from the sealed single RTKLIB diagnostic replay.

No solver/evaluator imports or subprocess invocation. Keeps the frozen failed
first parser intact. Clock-aware joins use RTKLIB's saved receiver-1 $CLK ns and
the 1 ms interval implied by independently rounded 3-decimal time tags.
"""
from __future__ import annotations
import argparse
import collections
import csv
import importlib.util
import json
from pathlib import Path
import re

def derive(args):
    root, stage = args.code_root.resolve(), args.stage.resolve()
    frozen = root/"scripts/paper_rebuild/carrier_phase/ar_v3_rtklib_diagnostic.py"
    spec=importlib.util.spec_from_file_location("frozen_rtklib_parser", frozen)
    m=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    plan=m.read(stage/"PLAN.json")
    receipt=m.read(stage/"EXECUTION_RECEIPT.json")
    assert receipt["status"]=="PASS_SCIENTIFIC_BYTES_IDENTICAL"
    assert m.sha(frozen)==plan["protected_inputs_sha256"][str(frozen)]
    for name, expected in receipt["output_sha256"].items():
        assert m.sha(stage/"RUN"/name)==expected, name
    failure = {
        "stage": "DERIVATION_ATTEMPT01", "native_failed": False,
        "exception": "AssertionError: Output without trace epoch",
        "frozen_parser_sha256": m.sha(frozen),
        "reason": "original derivation incorrectly equated receiver-local observation time and clock-corrected solution time",
        "repair": "new read-only parser joins via saved receiver-1 clock; original runner and all native products unchanged",
        "additional_native_calls": 0,
    }
    m.write(stage/"DERIVATION_ATTEMPT01_FAILURE.json", failure)
    with (stage/"RUN/solution.pos.trace").open(errors="replace") as f:
        epochs=m.parse_trace(f)
    bykey={e["key"]:e for e in epochs}
    rows=m.pos_rows(stage/"RUN/solution.pos")
    clocks={}
    status={}
    for line in (stage/"RUN/solution.pos.stat").read_text().splitlines():
        c=line.split(",")
        if c[0]=="$CLK":
            k=m.key(c[1],c[2])
            assert k not in clocks and c[4]=="1", line
            clocks[k]=float(c[5])   # rtkpos.c:251-253: sol.dtr[0]*1e9, receiver 1
            status[k]=int(c[3])
    assert set(clocks)==set(rows)
    for k,r in rows.items():
        assert status[k]==r["q"]
    extras={}
    for line in (stage/"RUN/solution.pos").read_text().splitlines():
        if not line.strip() or line.startswith("%"):
            continue
        c=line.split(",")
        extras[m.key(c[0],c[1])]={"ratio_output": float(c[-1]), "output_satellites": int(c[6])}
    current=None
    with (stage/"RUN/solution.pos.trace").open(errors="replace") as f:
        for lineno,line in enumerate(f,1):
            mark=m.EPOCH_RE.search(line)
            if mark:
                current=bykey[m.time_key(mark[1])]
                current.update(relative_solver_entered=False, execution_errors=[], ar_dd_dimension=None,
                               ratio_trace=None, objective_best_trace=None, objective_second_trace=None)
                continue
            if current is None:
                continue
            if "relpos  :" in line:
                current["relative_solver_entered"]=True
            ratio=re.search(r"(?:validation ok|validation failed) \(nb=(\d+) ratio=([-\d.e+]+) s=([-\d.e+]+)/([-\d.e+]+)",line)
            if ratio:
                current.update(ar_dd_dimension=int(ratio[1]), ratio_trace=float(ratio[2]),
                               objective_best_trace=float(ratio[3]), objective_second_trace=float(ratio[4]))
            for token in ["point pos error", "base station position error", "time sync error",
                          "no common satellite", "no double-differenced residual", "filter error",
                          "initial base station position error", "rover initial position error"]:
                if token in line:
                    current["execution_errors"].append({"category":token,"trace_line":lineno,
                                                        "message":line.rstrip()})
    trace_numeric={e["key"]:(int(e["key"].split(":")[0])*604800000+
                              int(e["key"].split(":")[1])) for e in epochs}
    output_to_trace={}
    join_errors=[]
    join_deltas=[]
    for k,r in rows.items():
        w,t=map(int,k.split(":"))
        raw_estimated_ms=t+clocks[k]*1e-6
        options=[tk for tk,v in trace_numeric.items() if abs((v-w*604800000)-raw_estimated_ms)<=1.000001]
        if len(options)!=1:
            join_errors.append({"output_key":k,"clock_ns":clocks[k],
                                "candidate_trace_keys":options,"reason":"no_unique_time_interval_overlap"})
            continue
        output_to_trace[k]=options[0]
        join_deltas.append(raw_estimated_ms-(trace_numeric[options[0]]-w*604800000))
    assert not join_errors, join_errors
    assert len(set(output_to_trace.values()))==len(output_to_trace)
    ordered=[trace_numeric[v] for v in output_to_trace.values()]
    assert all(b>a for a,b in zip(ordered,ordered[1:])), "nonmonotonic mapping"
    trace_to_output={v:k for k,v in output_to_trace.items()}
    output=[]
    for e in epochs:
        outkey=trace_to_output.get(e["key"])
        r=rows.get(outkey)
        dd=e["dd_calls"]
        residuals=e["large_residuals"]
        row={
            "observation_week_tow_ms_key":e["key"], "observation_time_gpst":e["time"],
            "observation_relative_s":int(e["key"].split(":")[1])/1000-plan["pos_time_base_tow_s"],
            "output_key":outkey, "output_present":r is not None,
            "output_relative_s":None if r is None else r["tow"]-plan["pos_time_base_tow_s"],
            "receiver1_clock_ns":None if r is None else clocks[outkey],
            "q":None if r is None else r["q"],
            "baseline_length_m":None if r is None else r["baseline_length_m"],
            "ratio_output":None if r is None else extras[outkey]["ratio_output"],
            "relative_solver_entered":e["relative_solver_entered"],
            "ar_attempted":e["ar_attempted"],"ar_result":e["ar_result"],
            "ar_dd_dimension":e["ar_dd_dimension"],"ratio_trace":e["ratio_trace"],
            "successful_float_update_constbl_added_calls":sum(x["stage"]=="FLOAT_UPDATE" and x["constbl"]=="ADDED" for x in dd),
            "successful_float_update_constbl_skipped_calls":sum(x["stage"]=="FLOAT_UPDATE" and x["constbl"]=="SKIPPED_NONLINEARITY" for x in dd),
            "float_postfit_constbl_added_calls":sum(x["stage"]=="FLOAT_POSTFIT" and x["constbl"]=="ADDED" for x in dd),
            "float_postfit_constbl_skipped_calls":sum(x["stage"]=="FLOAT_POSTFIT" and x["constbl"]=="SKIPPED_NONLINEARITY" for x in dd),
            "fixed_postfit_constbl_added_calls":sum(x["stage"]=="FIXED_POSTFIT" and x["constbl"]=="ADDED" for x in dd),
            "float_large_residual_count":sum(x["stage"]=="FLOAT_POSTFIT" for x in residuals),
            "fixed_large_residual_count":sum(x["stage"]=="FIXED_POSTFIT" for x in residuals),
            "fixed_large_length_residual_count":sum(x["stage"]=="FIXED_POSTFIT" and x["baseline_constraint"] for x in residuals),
            "execution_error_categories":"|".join(x["category"] for x in e["execution_errors"]),
            "trace_start_line":e["trace_start_line"]}
        output.append(row)
    def subset_summary(subset):
        q1=[r for r in subset if r["q"]==1]
        bad=[r for r in q1 if r["fixed_large_length_residual_count"]>0]
        return {
            "trace_epoch_count":len(subset),
            "output_rows":sum(r["output_present"] for r in subset),
            "q_counts":dict(collections.Counter(str(r["q"]) for r in subset)),
            "relative_solver_entered_count":sum(r["relative_solver_entered"] for r in subset),
            "ar_result_counts":dict(collections.Counter(r["ar_result"] for r in subset)),
            "q1_with_any_fixed_large_residual":sum(r["fixed_large_residual_count"]>0 for r in q1),
            "q1_with_fixed_large_length_residual":len(bad),
            "q1_large_length_also_float_update_skipped":sum(r["successful_float_update_constbl_skipped_calls"]>0 for r in bad),
            "q1_large_length_also_float_update_added":sum(r["successful_float_update_constbl_added_calls"]>0 for r in bad),
            "q1_all_float_update_skipped":sum(r["successful_float_update_constbl_skipped_calls"]>0 for r in q1),
            "q1_all_float_update_added":sum(r["successful_float_update_constbl_added_calls"]>0 for r in q1),
            "q1_max_abs_length_residual_m":max((abs(r["baseline_length_m"]-.35) for r in q1),default=None),
            "q1_large_length_ratio_minmax":[min((r["ratio_output"] for r in bad),default=None),
                                            max((r["ratio_output"] for r in bad),default=None)],
        }
    summary={
        "status":"PASS_READ_ONLY_CLOCK_AWARE_DERIVATION", "native_receipt":receipt,
        "registration_commit":m.read(stage/"EXECUTION_STARTED.json")["registration_commit"],
        "derivation_attempt01":failure,
        "derivation_script_sha256":m.sha(Path(__file__)),
        "derivation_scope":"sealed original native outputs and source semantics; no reference, no estimator",
        "clock_join":{
            "receiver1_source":"first observation file GNSS2 is RTKLIB rover receiver 1; not physical GNSS1",
            "clock_field":"$CLK fifth data field: sol.dtr[0]*1e9 in nanoseconds",
            "formula":"raw observation time = clock-corrected output time + rover clock ns * 1e-9",
            "clock_source":"rtkpos.c:251-253; pntpos.c:408-409",
            "time_tolerance_basis":"two independently rounded millisecond tags, interval sum <=1 ms; plus 1e-6 ms numerical margin",
            "matching_uses_heading_or_reference":False,
            "output_count":len(rows),"clock_count":len(clocks),
            "unique_matched_output_count":len(output_to_trace),
            "strict_monotonicity":True,
            "unmatched_output_rows":join_errors,
            "trace_epochs_without_output_count":len(epochs)-len(output_to_trace),
            "trace_epochs_without_output_explicit_csv": "RTKLIB_EPOCH_DIAGNOSTICS.csv output_present=False",
            "max_abs_raw_reconstructed_minus_trace_time_ms":max(abs(x) for x in join_deltas)},
        "full_native":subset_summary(output),
        "observation_time_66_340":subset_summary([r for r in output if 66<=r["observation_relative_s"]<=340]),
        "execution_error_counts":dict(collections.Counter(x["category"] for e in epochs for x in e["execution_errors"])),
        "spp_chi_square_failure_counts":dict(collections.Counter(x["category"] for e in epochs
              for x in e["execution_errors"] if "chi-square error" in x["message"])),
        "relative_solver_entered_but_no_AR_rows":[r for r in output if r["relative_solver_entered"] and not r["ar_attempted"]],

        "dd_call_counts":dict(collections.Counter(x["stage"]+":"+x["constbl"] for e in epochs for x in e["dd_calls"])),
        "ar_pass_without_fixed_postfit_rows":[r for r in output if r["ar_result"]=="RATIO_PASS_AND_FIXED_CONDITIONING_SUCCESS" and r["fixed_postfit_constbl_added_calls"]==0],
        "trace_quantization":"branch identity exact; numerical fields rounded by original RTKLIB trace formats",
        "conclusion_boundary":"trace proves execution mechanisms, not unique physical cause, correct integers, calibrated false-fix risk or counterfactual benefit of a repair",
    }
    doc=root/"docs/paper_rebuild/AR_V3_RESEARCH_20261006"
    for name,content in [("RTKLIB_EPOCH_DIAGNOSTICS.csv",output),
                         ("RTKLIB_Q1_LARGE_LENGTH_DIAGNOSTICS.csv",[r for r in output if r["q"]==1 and r["fixed_large_length_residual_count"]>0])]:
        with (doc/name).open("w",newline="") as f:
            w=csv.DictWriter(f,fieldnames=list(output[0]),lineterminator="\n")
            w.writeheader();w.writerows(content)
    m.write(stage/"TRACE_DETAIL_CLOCK_JOINED.json",epochs)
    m.write(stage/"SUMMARY_CLOCK_JOINED.json",summary)
    m.write(doc/"RTKLIB_DIAGNOSTIC_SUMMARY.json",m.public(summary,plan["aliases"]))
    readout_receipt={
        "command":["python3", str(Path(__file__).resolve()), "--code-root", str(root), "--stage", str(stage)],
        "script_sha256":m.sha(Path(__file__)),
        "native_execution_receipt_sha256":m.sha(stage/"EXECUTION_RECEIPT.json"),
        "native_plan_sha256":m.sha(stage/"PLAN.json"),
        "native_calls_added_by_derivation":0,
        "evaluator_calls_added_by_derivation":0,
        "protected_output_hashes_rechecked":receipt["output_sha256"],
        "derived_files_sha256":{name:m.sha(doc/name) for name in
            ["RTKLIB_EPOCH_DIAGNOSTICS.csv","RTKLIB_Q1_LARGE_LENGTH_DIAGNOSTICS.csv",
             "RTKLIB_DIAGNOSTIC_SUMMARY.json"]}}
    m.write(doc/"RTKLIB_DERIVATION_RECEIPT.json",m.public(readout_receipt,plan["aliases"]))
    print(json.dumps(m.public(summary,plan["aliases"]),indent=2,ensure_ascii=False))

if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--code-root",type=Path,required=True)
    p.add_argument("--stage",type=Path,required=True)
    derive(p.parse_args())
