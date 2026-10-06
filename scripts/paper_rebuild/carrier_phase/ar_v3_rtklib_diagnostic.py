#!/usr/bin/env python3
"""One registered trace-only replay of archived HX07R/BY2/V0; no evaluator.

prepare/selftest do not execute RTKLIB. run requires the committed registration
and exact original executable, config, observations and navigation hashes.
The only RTKLIB option added is -x 4 (solopt.trace). Original outputs are read-only.
"""
from __future__ import annotations
import argparse
import collections
import csv
import datetime as dt
import hashlib
import json
import math
import os
from pathlib import Path
import re
import signal
import subprocess
import time

SCRIPT_REL = "scripts/paper_rebuild/carrier_phase/ar_v3_rtklib_diagnostic.py"
DOC_REL = "docs/paper_rebuild/AR_V3_RESEARCH_20261006"
EXTERNAL_COMMIT = "180043ee24b6d2b168f98b64be15f69d50046b1a"
SOURCE_REL = ["src/rtkpos.c", "src/ephemeris.c", "src/rcv/ublox.c",
              "src/postpos.c", "app/consapp/rnx2rtkp/rnx2rtkp.c"]
EPOCH_RE = re.compile(r"rtkpos\s*: time=(\d{4}/\d\d/\d\d \d\d:\d\d:\d\d\.\d+) n=(\d+)")
SKIP_RE = re.compile(r"equation nonlinear \(bb=([-\d.e+]+) var=([-\d.e+]+)\)")
APPLY_RE = re.compile(r"baseline len\s+v=\s*([-\d.e+]+) R=\s*([-\d.e+]+)\s+([-\d.e+]+)")
RESID_RE = re.compile(r"large residual \(sat=\s*(\d+)-\s*(\d+) (\w+)\s+v=\s*([-\d.e+]+) sig=([-\d.e+]+)")
GPS_EPOCH = dt.datetime(1980, 1, 6)

def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for b in iter(lambda: f.read(1024 * 1024), b""):
            h.update(b)
    return h.hexdigest()

def read(path):
    return json.loads(Path(path).read_text())

def write(path, obj):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False) + "\n")

def public(obj, aliases):
    txt = json.dumps(obj, ensure_ascii=False, allow_nan=False)
    for real, alias in sorted(aliases.items(), key=lambda kv: -len(kv[0])):
        txt = txt.replace(real, alias)
    return json.loads(txt)

def key(week, tow):
    return f"{int(week)}:{int(round(float(tow) * 1000))}"

def time_key(text):
    delta = (dt.datetime.strptime(text, "%Y/%m/%d %H:%M:%S.%f") - GPS_EPOCH).total_seconds()
    week = int(delta // 604800)
    return key(week, delta - week * 604800)

def pos_rows(path):
    rows = {}
    with Path(path).open() as f:
        for line in f:
            if not line.strip() or line.startswith("%"):
                continue
            cols = [x.strip() for x in line.split(",")]
            assert len(cols) >= 6, line
            k = key(cols[0], cols[1])
            assert k not in rows, k
            xyz = [float(x) for x in cols[2:5]]
            rows[k] = {"week": int(cols[0]), "tow": float(cols[1]), "q": int(cols[5]),
                       "baseline_length_m": math.sqrt(sum(x*x for x in xyz))}
    return rows

def stat_counts(path):
    counts = collections.Counter()
    with Path(path).open() as f:
        for line in f:
            counts[line.split(",", 1)[0].strip()] += 1
    return dict(counts)

def inspect_existing(run):
    rows = pos_rows(run / "solution.pos")
    trace_files = sorted(str(p) for p in run.glob("*.trace"))
    stderr = (run / "stderr.log").read_text(errors="replace")
    return {
        "scope": "existing solution/stat/stderr only; no reference/error_series",
        "scientific_output_rows": len(rows),
        "q_counts": dict(collections.Counter(str(r["q"]) for r in rows.values())),
        "stat_record_counts": stat_counts(run / "solution.pos.stat"),
        "existing_trace_files": trace_files,
        "stderr_has_constbl_or_AR_trace": any(t in stderr for t in
            ["constbl", "equation nonlinear", "resamb_LAMBDA", "ambiguity validation"]),
        "evidence_gap": "status records do not record constbl invocation/application/skips or AR branch reason",
        "q1_max_absolute_length_residual_m": max(abs(r["baseline_length_m"]-.35)
            for r in rows.values() if r["q"] == 1),
        "source_static_facts": [
            "rtkpos.c constbl skips when mean position variance > (0.1*current length)^2",
            "fixed postfit ddres passes P=NULL: constbl var=0; that call adds a residual but no filter update",
            "valpos initializes stat=1 and only logs large residuals, never sets stat=0",
            "resamb_LAMBDA ratio gate is distinct from valpos; Q1 is not independently true integers",
            "satposs already uses receiver observation time minus own P/c minus satellite clock",
            "generic subHalfCyc cannot justify adding 0.5 cycle to cpMes"],
    }

def prepare(args):
    root = args.code_root.resolve()
    clean = args.clean_root.resolve()
    ext = args.external_root.resolve()
    stage = args.stage.resolve()
    assert not stage.exists(), f"Refuse to overwrite {stage}"
    run = clean / "stages/CLEAN9_EXTERNAL_COMPARISON/HX07R/RUNS/BY2_V0"
    cmd = read(run / "COMMAND.json")
    assert cmd["sequence"] == "BY2" and cmd["variant"] == "V0" and cmd["returncode"] == 0
    assert cmd["argv"][5:7] == ["-y", "2"] and "-ts" not in cmd["argv"]
    assert subprocess.check_output(["git", "-C", str(ext), "rev-parse", "HEAD"], text=True).strip() == EXTERNAL_COMMIT
    aliases = {str(root): "<CODE_ROOT>", str(clean): "<CLEAN_ROOT>",
               str(ext): "<RTKLIB>", str(stage): "<RTKLIB_DIAGNOSTIC_STAGE>"}
    pins = {}
    for token, expected in cmd["input_sha256"].items():
        real = token.replace("<CLEAN_ROOT>", str(clean)).replace("<RTKLIB>", str(ext))
        assert sha(real) == expected, real
        pins[real] = expected
    for filename in ["COMMAND.json", "solution.pos", "solution.pos.stat", "stderr.log"]:
        pins[str(run / filename)] = sha(run / filename)
    for rel in SOURCE_REL:
        path = ext / rel
        tracked = subprocess.check_output(["git", "-C", str(ext), "show", f"{EXTERNAL_COMMIT}:{rel}"])
        assert path.read_bytes() == tracked, f"External source differs: {rel}"
        pins[str(path)] = sha(path)
    pins[str(root / SCRIPT_REL)] = sha(root / SCRIPT_REL)
    old = cmd["argv"]
    assert Path(old[0]).resolve().is_relative_to(ext)
    argv = list(old)
    argv[4] = str(stage / "RUN/solution.pos")
    argv[7:7] = ["-x", "4"]
    plan = {
        "schema_version": 1,
        "id": "AR_V3_RESEARCH_20261006_RTKLIB_BY2_V0_TRACE4_ATTEMPT01",
        "purpose": "Causal execution-path diagnosis; not a performance repair or new AR comparison",
        "sequence": "BY2", "variant": "HX07R_V0_UNCHANGED_SCIENCE",
        "external_commit": EXTERNAL_COMMIT,
        "source_copy_or_patch": False, "build_calls": 0,
        "native_budget": 1, "retry_budget": 0, "evaluator_budget": 0,
        "reference_read_budget": 0, "raw_decode_budget": 0,
        "original_run": str(run), "original_argv": old, "argv": argv,
        "diagnostic_only_cli_addition": ["-x", "4"],
        "unchanged_cli": "-y 2 and complete original observation/history, navigation, and config",
        "scientific_equality_gate": "all bytes of solution.pos and solution.pos.stat equal archived HX07R BY2 V0",
        "nominal_original_run_elapsed_s": (dt.datetime.fromisoformat(cmd["end"]) -
                                           dt.datetime.fromisoformat(cmd["start"])).total_seconds(),
        "estimated_cost": "original 4.38s; trace/strace expected seconds to tens of seconds; not runtime benchmark",
        "wall_timeout_s": 240, "trace_disk_cap_bytes": 1000000000,
        "protected_inputs_sha256": pins, "aliases": aliases,
        "thread_environment": cmd["thread_environment"],
        "context_only_window_relative_s": [66.0, 340.0],
        "native_replay_scope": "complete original files; no -ts/-te truncation",
        "pos_time_base_tow_s": 460818.0,
        "planned_diagnostics": [
            "per epoch pre-AR DD constbl added/skipped counts with original trace quantization",
            "LAMBDA branch: attempted/no DD/numerical failure/ratio failed/ratio passed",
            "float and fixed postfit large residual logs, baseline residual separated",
            "join all output Q states and length, without reference or selection by error"],
        "boundaries": [
            "trace is RTKLIB diagnostic output, never commercial reference",
            "do not infer physical integer truth, unique multipath cause, or false-fix probability",
            "do not apply an extra receiver clock correction or generic half-cycle adjustment",
            "a mismatch preserves failed attempt; no automatic rerun and no replacement of old results"]
    }
    existing = inspect_existing(run)
    stage.mkdir(parents=True)
    write(stage / "PLAN.json", plan)
    write(stage / "EXISTING_LOG_AUDIT.json", existing)
    doc = root / DOC_REL
    write(doc / "RTKLIB_EXISTING_LOG_AUDIT.json", public(existing, aliases))
    reg = public(plan, aliases)
    reg["local_plan_sha256"] = sha(stage / "PLAN.json")
    reg["status_at_registration"] = "PREPARED_NATIVE_ZERO"
    write(doc / "RTKLIB_PREREGISTRATION.json", reg)
    print(json.dumps({"status": "PREPARED_NATIVE_ZERO", "stage": str(stage),
                      "plan_sha256": sha(stage/"PLAN.json"), "original_log_audit": existing}, indent=2))

def parse_trace(lines):
    epochs = []
    current = None
    block = None
    for lineno, line in enumerate(lines, 1):
        match = EPOCH_RE.search(line)
        if match:
            current = {"time": match[1], "key": time_key(match[1]), "trace_start_line": lineno,
                       "observations": int(match[2]), "ar_attempted": False,
                       "ar_result": "NOT_ATTEMPTED", "dd_calls": [], "large_residuals": []}
            epochs.append(current)
            block = None
            continue
        if current is None:
            continue
        iteration = re.search(r"x\((\d+)\)=", line)
        if iteration and int(iteration[1]) > 0 and block is not None and not current["ar_attempted"]:
            block["stage"] = "FLOAT_UPDATE"
            block["successful_filter_iteration"] = int(iteration[1])
        if "valpos  :" in line and block is not None and not current["ar_attempted"]:
            block["stage"] = "FLOAT_POSTFIT"
        if "resamb_LAMBDA :" in line:
            current["ar_attempted"] = True
            current["ar_result"] = "ATTEMPTED_NO_TERMINAL_TRACE"
            block = None
        if "ddres   :" in line:
            block = {"dd_call_index": len(current["dd_calls"]) + 1,
                     "stage": "FIXED_POSTFIT" if current["ar_attempted"] else "PRE_AR",
                     "trace_line": lineno, "constbl": "NOT_RECORDED"}
            current["dd_calls"].append(block)
        if block is not None and "constbl :" in line:
            block["constbl"] = "INVOKED"
        match = SKIP_RE.search(line)
        if match and block is not None:
            block.update(constbl="SKIPPED_NONLINEARITY", length_m_printed=float(match[1]),
                         mean_position_variance_m2_printed=float(match[2]), branch_line=lineno)
        match = APPLY_RE.search(line)
        if match and block is not None:
            block.update(constbl="ADDED", length_residual_m_printed=float(match[1]),
                         base_variance_m2_printed=float(match[2]),
                         rover_variance_m2_printed=float(match[3]), branch_line=lineno)
        if "resamb : validation ok" in line:
            current["ar_result"] = "RATIO_PASS_AND_FIXED_CONDITIONING_SUCCESS"
        elif "ambiguity validation failed" in line:
            current["ar_result"] = "RATIO_FAILED"
        elif "no valid double-difference" in line:
            current["ar_result"] = "NO_VALID_DD"
        elif "lambda error" in line:
            current["ar_result"] = "LAMBDA_ERROR"
        match = RESID_RE.search(line)
        if match:
            baseline = int(match[1]) == 0 and int(match[2]) == 0 and match[3] == "C1"
            current["large_residuals"].append({
                "trace_line": lineno, "stage": "FIXED_POSTFIT" if current["ar_attempted"] else "FLOAT_POSTFIT",
                "baseline_constraint": baseline, "sat1": int(match[1]), "sat2": int(match[2]),
                "printed_type": match[3], "residual_m_printed": float(match[4]),
                "sigma_m_printed": float(match[5])})
    keys = [e["key"] for e in epochs]
    assert len(keys) == len(set(keys)), "duplicate rtkpos epoch"
    return epochs

def selftest():
    trace = [
        "3 rtkpos  : time=2026/03/06 08:01:14.000 n=46\n",
        "3 ddres   : dt=0.0 nx=915 ns=23\n",
        "3 constbl : \n",
        "4 baseline len   v=       -0.031 R=0.000000 0.000100\n",
        "4 x(1)=  1 2 3\n",
        "3 ddres   : dt=0.0 nx=915 ns=23\n",
        "3 constbl : equation nonlinear (bb=0.120 var=0.010)\n",
        "3 valpos  : nv=9 thres=4.0\n",
        "3 resamb_LAMBDA : nx=915\n",
        "3 resamb : validation ok (nb=9 ratio=5.0 s=1/5)\n",
        "3 ddres   : dt=0.0 nx=915 ns=23\n",
        "4 baseline len   v=        0.101 R=0.000000 0.000100\n",
        "2 08:01:14.00: large residual (sat= 0- 0 C1 v= 0.101 sig=0.010)\n",
        "3 rtkpos  : time=2026/03/06 08:01:14.200 n=40\n",
        "3 ddres   : dt=0.0 nx=915 ns=20\n",
        "3 resamb_LAMBDA : nx=915\n",
        "2 08:01:14.20: ambiguity validation failed (nb=6 ratio=1.01 s=3/3)\n",
        "3 rtkpos  : time=2026/03/06 08:01:14.400 n=0\n"]
    e = parse_trace(trace)
    assert len(e) == 3 and e[0]["key"] == "2408:460874000"
    assert [x["constbl"] for x in e[0]["dd_calls"]] == ["ADDED", "SKIPPED_NONLINEARITY", "ADDED"]
    assert e[0]["dd_calls"][-1]["stage"] == "FIXED_POSTFIT"
    assert e[0]["dd_calls"][0]["stage"] == "FLOAT_UPDATE"
    assert e[0]["dd_calls"][1]["stage"] == "FLOAT_POSTFIT"
    assert e[0]["large_residuals"][0]["baseline_constraint"]
    assert e[1]["ar_result"] == "RATIO_FAILED"
    assert e[1]["dd_calls"][0]["constbl"] == "NOT_RECORDED"
    assert e[2]["ar_result"] == "NOT_ATTEMPTED" and not e[2]["dd_calls"]
    print("PASS parser selftest: epoch isolation, time key, branch, phase, length residual, AR failure")

def run(args):
    stage = args.stage.resolve()
    plan = read(stage / "PLAN.json")
    root = args.code_root.resolve()
    for real, expected in plan["protected_inputs_sha256"].items():
        assert sha(real) == expected, f"Input/source/script changed: {real}"
    for rel in [SCRIPT_REL, DOC_REL + "/RTKLIB_PREREGISTRATION.json",
                DOC_REL + "/RTKLIB_PLAN.md"]:
        committed = subprocess.check_output(["git", "-C", str(root), "show", f"{args.registration_commit}:{rel}"])
        assert committed == (root / rel).read_bytes(), f"Registration not frozen: {rel}"
    reg = read(root / DOC_REL / "RTKLIB_PREREGISTRATION.json")
    assert reg["local_plan_sha256"] == sha(stage / "PLAN.json")
    assert not (stage / "EXECUTION_STARTED.json").exists(), "One-call budget consumed"
    (stage / "RUN").mkdir()
    write(stage / "EXECUTION_STARTED.json", {
        "registration_commit": args.registration_commit, "PLAN_sha256": sha(stage/"PLAN.json"),
        "started_utc": dt.datetime.now(dt.timezone.utc).isoformat(), "native_call_budget": 1})
    env = os.environ.copy()
    env.update(plan["thread_environment"])
    argv = ["strace", "-f", "-e", "trace=openat,execve", "-o", str(stage/"RUN/OPENAT.strace")] + plan["argv"]
    write(stage/"RUN/INVOCATION.json", {"argv": argv, "registration_commit": args.registration_commit,
                                     "thread_environment": plan["thread_environment"]})
    start = time.monotonic()
    error = None
    with (stage/"RUN/stdout.log").open("wb") as out, (stage/"RUN/stderr.log").open("wb") as err:
        process = subprocess.Popen(argv, cwd=stage/"RUN", env=env, stdout=out, stderr=err, start_new_session=True)
        try:
            while process.poll() is None:
                if time.monotonic()-start > plan["wall_timeout_s"]:
                    raise TimeoutError("registered wall timeout")
                trace = stage/"RUN/solution.pos.trace"
                if trace.exists() and trace.stat().st_size > plan["trace_disk_cap_bytes"]:
                    raise RuntimeError("registered trace disk cap")
                time.sleep(.2)
        except Exception as exc:
            error = repr(exc)
            os.killpg(process.pid, signal.SIGKILL)
            process.wait()
    receipt = {"returncode": process.returncode, "elapsed_instrumented_s": time.monotonic()-start,
               "error": error, "native_calls": 1, "evaluation_calls": 0, "retries": 0,
               "not_an_online_runtime_benchmark": True}
    old = Path(plan["original_run"])
    for filename in ["solution.pos", "solution.pos.stat"]:
        new = stage/"RUN"/filename
        receipt[filename+"_byte_equal"] = new.exists() and new.read_bytes() == (old/filename).read_bytes()
    for real, expected in plan["protected_inputs_sha256"].items():
        assert sha(real) == expected, f"Protected input changed during run: {real}"
    opens = (stage/"RUN/OPENAT.strace").read_text(errors="replace")
    forbidden = [line for line in opens.splitlines() if "openat(" in line and
                 any(s in line.lower() for s in ["trace_vrtk", ".fpl", ".bag", "error_series", ".ubx"])]
    receipt["forbidden_raw_reference_open_lines"] = forbidden
    receipt["output_sha256"] = {p.name: sha(p) for p in (stage/"RUN").iterdir() if p.is_file()}
    passed = (process.returncode == 0 and error is None and not forbidden and
              all(receipt[n+"_byte_equal"] for n in ["solution.pos", "solution.pos.stat"]))
    receipt["status"] = "PASS_SCIENTIFIC_BYTES_IDENTICAL" if passed else "FAILED_PRESERVED_NO_RETRY"
    write(stage/"EXECUTION_RECEIPT.json", receipt)
    write(stage/("COMPLETE.json" if passed else "FAILED.json"), receipt)
    print(json.dumps(receipt, indent=2))
    if not passed:
        raise SystemExit(2)

def summarize(args):
    stage = args.stage.resolve()
    root = args.code_root.resolve()
    plan = read(stage/"PLAN.json")
    receipt = read(stage/"EXECUTION_RECEIPT.json")
    assert receipt["status"] == "PASS_SCIENTIFIC_BYTES_IDENTICAL"
    for name, expected in receipt["output_sha256"].items():
        assert sha(stage/"RUN"/name) == expected
    with (stage/"RUN/solution.pos.trace").open(errors="replace") as f:
        epochs = parse_trace(f)
    rows = pos_rows(stage/"RUN/solution.pos")
    output = []
    for e in epochs:
        r = rows.get(e["key"])
        dd = e["dd_calls"]
        output.append({
            "week_tow_ms_key": e["key"], "time_gpst": e["time"],
            "time_relative_s": (int(e["key"].split(":")[1])/1000 - plan["pos_time_base_tow_s"]),
            "output_present": r is not None, "q": None if r is None else r["q"],
            "baseline_length_m": None if r is None else r["baseline_length_m"],
            "ar_attempted": e["ar_attempted"], "ar_result": e["ar_result"],
            "pre_ar_constbl_added_calls": sum(x["stage"] in {"PRE_AR", "FLOAT_UPDATE", "FLOAT_POSTFIT"} and x["constbl"]=="ADDED" for x in dd),
            "pre_ar_constbl_skipped_calls": sum(x["stage"] in {"PRE_AR", "FLOAT_UPDATE", "FLOAT_POSTFIT"} and x["constbl"]=="SKIPPED_NONLINEARITY" for x in dd),
            "successful_float_update_constbl_added_calls": sum(x["stage"]=="FLOAT_UPDATE" and x["constbl"]=="ADDED" for x in dd),
            "successful_float_update_constbl_skipped_calls": sum(x["stage"]=="FLOAT_UPDATE" and x["constbl"]=="SKIPPED_NONLINEARITY" for x in dd),
            "float_postfit_constbl_added_calls": sum(x["stage"]=="FLOAT_POSTFIT" and x["constbl"]=="ADDED" for x in dd),
            "fixed_postfit_constbl_added_calls": sum(x["stage"]=="FIXED_POSTFIT" and x["constbl"]=="ADDED" for x in dd),
            "float_large_residual_count": sum(x["stage"]=="FLOAT_POSTFIT" for x in e["large_residuals"]),
            "fixed_large_residual_count": sum(x["stage"]=="FIXED_POSTFIT" for x in e["large_residuals"]),
            "fixed_large_length_residual_count": sum(x["stage"]=="FIXED_POSTFIT" and x["baseline_constraint"] for x in e["large_residuals"]),
            "trace_start_line": e["trace_start_line"]})
    assert set(rows).issubset({e["key"] for e in epochs}), "Output without trace epoch"
    summary = {"receipt": receipt, "data_mode": "recorded_raw_gnss",
               "scientific_output_byte_equality": True, "new_evaluation_count": 0,
               "trace_epoch_count": len(epochs), "output_rows": len(rows),
               "ar_result_counts": dict(collections.Counter(r["ar_result"] for r in output)),
               "all_epoch_q_counts": dict(collections.Counter(str(r["q"]) for r in output)),
               "epochs_pre_ar_length_constraint_skipped": sum(r["pre_ar_constbl_skipped_calls"]>0 for r in output),
               "q1_epochs_with_fixed_postfit_large_length_residual": sum(
                   r["q"]==1 and r["fixed_large_length_residual_count"]>0 for r in output),
               "q1_epochs_with_any_fixed_postfit_large_residual": sum(
                   r["q"]==1 and r["fixed_large_residual_count"]>0 for r in output),
               "window": {}, "scope": "all native epochs retained; native timestamp [66,340] separate, not original selected_pairs denominator"}
    for name, subset in [("full_native", output),
                         ("native_time_tag_closed_66_340", [r for r in output if 66<=r["time_relative_s"]<=340])]:
        summary["window"][name] = {
            "epoch_count": len(subset), "q_counts": dict(collections.Counter(str(r["q"]) for r in subset)),
            "ar_result_counts": dict(collections.Counter(r["ar_result"] for r in subset)),
            "q1_large_length_residual_epochs": sum(r["q"]==1 and r["fixed_large_length_residual_count"]>0 for r in subset),
            "q1_length_residual_max_absolute_m": max((abs(r["baseline_length_m"]-.35)
                 for r in subset if r["q"]==1), default=None)}
    write(stage/"TRACE_DETAIL.json", epochs)
    write(stage/"SUMMARY.json", summary)
    doc = root / DOC_REL
    write(doc/"RTKLIB_DIAGNOSTIC_SUMMARY.json", public(summary, plan["aliases"]))
    with (doc/"RTKLIB_EPOCH_DIAGNOSTICS.csv").open("w", newline="") as f:
        w=csv.DictWriter(f, fieldnames=list(output[0]), lineterminator="\n")
        w.writeheader()
        w.writerows(output)
    print(json.dumps(public(summary, plan["aliases"]), indent=2))

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("action", choices=["prepare", "run", "summarize", "selftest"])
    p.add_argument("--code-root", type=Path)
    p.add_argument("--clean-root", type=Path)
    p.add_argument("--external-root", type=Path)
    p.add_argument("--stage", type=Path)
    p.add_argument("--registration-commit")
    args=p.parse_args()
    if args.action=="selftest":
        selftest()
    elif args.action=="prepare":
        assert all([args.code_root, args.clean_root, args.external_root, args.stage])
        prepare(args)
    elif args.action=="run":
        assert all([args.code_root, args.stage, args.registration_commit])
        run(args)
    else:
        assert args.code_root and args.stage
        summarize(args)

if __name__=="__main__":
    main()
