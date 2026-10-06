#!/usr/bin/env python3
"""Independently recompute sealed D records; no estimator imports or solver calls."""
from pathlib import Path
import argparse,collections,hashlib,json,math,re
import numpy as np
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text())
def ned(anchor):
    x,y,z=map(float,anchor);lon=math.atan2(y,x);p=math.hypot(x,y)
    f=1/298.257223563;e=f*(2-f);lat=math.atan2(z,p*(1-e))
    for _ in range(20):
        N=6378137/math.sqrt(1-e*math.sin(lat)**2)
        lat=math.atan2(z+e*N*math.sin(lat),p)
    s,c=math.sin(lat),math.cos(lat);sl,cl=math.sin(lon),math.cos(lon)
    return np.array([[-s*cl,-s*sl,c],[-sl,cl,0],[-c*cl,-c*sl,-s]])
def main():
    ap=argparse.ArgumentParser()
    for arg in ["code","stage","out"]:ap.add_argument("--"+arg,type=Path,required=True)
    ap.add_argument("--expected-commit",required=True);a=ap.parse_args()
    p=read(a.stage/"PLAN.json");s=read(a.stage/"SEAL.json");io=read(a.stage/"IO_AUDIT.json")
    reg=read(a.out/"D_PREREGISTRATION.json")
    assert s["execution_commit"]==a.expected_commit
    assert sha(a.stage/"PLAN.json")==s["plan_sha256"]==reg["plan_sha256"]
    assert sha(a.out/"03_D_METHOD_AND_CONTRACT.md")==reg["contract_sha256"]
    assert sha(a.stage/"CALL_LEDGER.jsonl")==s["ledger_sha256"]
    assert sha(a.stage/"IO.strace")==io["trace_sha256"]
    assert io["passed"] and io["exit_code"]==0 and not io["raw_or_reference_open_paths"]
    snapshot={f:sha(a.stage/f) for f in ["PLAN.json","SEAL.json","CALL_LEDGER.jsonl","IO.strace","IO_AUDIT.json"]}
    for rel,h in p["source_pins"].items():assert sha(a.code/rel)==h,rel
    for path,h in p["input_pins"].items():assert sha(path)==h,Path(path).name
    assert p["models"]==reg["models"] and s["calls"]==p["max_calls_total"]==20
    for name,h in s["result_hashes"].items():assert sha(a.stage/"RESULTS"/name)==h,name
    assert len(s["result_hashes"])==20
    assert set(x.name for x in (a.stage/"RESULTS").glob("*.json"))==set(s["result_hashes"])
    ledger=[json.loads(x) for x in (a.stage/"CALL_LEDGER.jsonl").read_text().splitlines()]
    starts=[x for x in ledger if x["event"]=="START"];ends=[x for x in ledger if x["event"]=="END"]
    assert len(starts)==len(ends)==20
    assert [x["event"] for x in ledger]==["START","END"]*20
    assert [x["call"] for x in starts]==[x["call"] for x in ends]==list(range(1,21))
    expected=[]
    for m in p["models"]:expected.extend([(m["case_id"],"A")]+[(m["case_id"],c["name"]) for c in m["conditions"]])
    assert [(x["case_id"],x["method"]) for x in starts]==expected
    roots=read(a.code/"configs/paper_rebuild/EXT_REPRODUCTION_ROOTS.local.json")["aliases"]
    rawroot=roots["<RAW_ROOT>"].rstrip("/");paths=[]
    trace=(a.stage/"IO.strace").read_text()
    for line in trace.splitlines():
        match=re.search(r'\b(?:open|openat)\([^"\n]*"((?:\\.|[^"\\])*)"',line)
        if match:
            enc=match.group(1)
            path=bytes.fromhex(enc.replace("\\x","")).decode("utf-8",errors="replace") if re.fullmatch(r"(?:\\x[0-9a-fA-F]{2})*",enc) else bytes(enc,"utf-8").decode("unicode_escape")
            paths.append(path)
    assert paths  # strace -qq suppresses process exit markers; IO receipt records child exit code.
    forbidden=[x for x in paths if x==rawroot or x.startswith(rawroot+"/") or "/data/raw/" in x or Path(x).name.startswith("trace_vrtk")]
    assert not forbidden
    delta=collections.defaultdict(float)
    def near(label,v,w,tol=1e-7):
        v=np.asarray(v,dtype=float);w=np.asarray(w,dtype=float)
        assert np.all(np.isfinite(v)) and np.all(np.isfinite(w)),label
        err=float(np.max(np.abs(v-w))) if v.size else 0
        delta[label]=max(delta[label],err)
        assert err<=tol,(label,err,tol)
    models={m["case_id"]:m for m in p["models"]};L=p["length_m"];sig=p["prior_sigma_m"];cap=p["kappa2"]
    assert L==.350 and sig==.03 and cap==9
    for m in models.values():
        A=np.array(m["ambiguity_design_m"]);B=np.array(m["baseline_design"]);Q=np.array(m["covariance_m2"])
        bt=np.array(m["true_baseline_ecef_m"]);nt=np.array(m["integer_truth"])
        near("Q_symmetry",Q,Q.T,1e-14)
        noise=np.linalg.cholesky(Q)@np.random.default_rng(m["seed"]).standard_normal(len(Q))
        near("seed_noise",noise,m["gaussian_noise_m"],1e-14)
        y=B@bt+A@nt+noise
        if m["measurement_fault"]!="NONE":
            row=m["phase_fault_row"];assert m["phase_bias_cycles"]==.25 and row==A.shape[1]
            near("phase_bias_m",m["phase_bias_m"],.25*A[row,0],1e-14);y[row]+=m["phase_bias_m"]
        near("synthetic_y",y,m["observation_m"],1e-13)
        R=ned(m["anchor_ecef_m"])
        near("down_axis",R[2],m["down_row_ecef"],1e-12)
        near("truth_ned",R@bt,m["true_baseline_ned_m"],1e-12)
        near("truth_length",np.linalg.norm(bt),L,1e-12)
    def candidate(c,m,cond,branch):
        available=bool(c["candidate_available"])
        assert available==bool(c.get("solver",{}).get("global_optimum_certified",False))
        if not available:return {"available":False,"integer_correct":False}
        sol=c["solver"];assert sol["search_complete"] and sol["termination_reason"]=="GLOBAL_BOUND_CERTIFIED"
        assert not sol["runtime_budget_exhausted"] and not sol["candidate_cap_applied"]
        assert sol["ambiguity_acceptance_test_defined"] is False and sol["ambiguity_accepted"] is None
        b=np.array(c["baseline_ecef_m"]);n=np.array(c["ambiguity"])
        assert np.all(n==np.rint(n)) and c["ambiguity"]==sol["best"]["ambiguity"]
        near("candidate_length",np.linalg.norm(b),L,1e-8)
        near("solver_baseline",b,sol["best"]["baseline"],1e-14)
        A=np.array(m["ambiguity_design_m"]);B=np.array(m["baseline_design"]);Q=np.array(m["covariance_m2"]);y=np.array(m["observation_m"])
        e=y-B@b-A@n;raw=float(e@np.linalg.solve(Q,e))
        near("full_raw_cost",raw,c["raw_whitened_residual_squared"])
        z=-L*math.sin(cond["reported_roll_rad"])*math.cos(cond["reported_pitch_rad"])
        near("RP_value",z,cond["vertical_prior_m"],1e-14)
        R=ned(m["anchor_ecef_m"]);bn=R@b;r=float((bn[2]-z)/sig)
        near("RP_residual",r,c["prior_residual_sigma"],1e-10)
        near("candidate_ned",bn,c["baseline_ned_m"],1e-11)
        bearing=math.degrees(math.atan2(bn[1],bn[0]));angle=(bearing-m["baseline_bearing_ned_deg"]+180)%360-180
        bt=np.array(m["true_baseline_ecef_m"])
        a3=math.degrees(math.acos(np.clip(b@bt/(np.linalg.norm(b)*np.linalg.norm(bt)),-1,1)))
        near("heading_error_deg",angle,c["projected_heading_error_deg"],1e-7)
        near("baseline_angle_deg",a3,c["baseline_angle_error_deg"],1e-5)
        correct=bool(np.array_equal(n,np.array(m["integer_truth"])));assert correct==c["integer_correct"]
        H=np.hstack([A,B]);v=y.copy();V=Q.copy()
        if branch=="B":
            H=np.vstack([H,np.r_[np.zeros(A.shape[1]),R[2]]]);v=np.r_[v,z]
            V=np.zeros((len(Q)+1,len(Q)+1));V[:-1,:-1]=Q;V[-1,-1]=sig**2
        C=np.linalg.cholesky(V);H=np.linalg.solve(C,H);v=np.linalg.solve(C,v)
        minimum=float(np.sum((v-H@np.linalg.lstsq(H,v,rcond=None)[0])**2))
        near("float_minimum",minimum,sol["float_solution"]["residual_objective"],1e-7)
        near("full_vs_reduced_plus_float",raw+(r*r if branch=="B" else 0),sol["best"]["objective"]+minimum,2e-7)
        return {"available":True,"integer_correct":correct,"integer":n.tolist(),"Jraw":raw,"rp_residual_sigma":r,"heading_error_deg":angle,"baseline_angle_deg":a3,"float_minimum":minimum}
    rows=[];seen=set();assert len(s["records"])==12
    for record in s["records"]:
        key=(record["case_id"],record["condition"]["name"]);case,condition=key
        assert key not in seen;seen.add(key)
        m=models[case];cond=record["condition"];assert cond in m["conditions"] and record["integer_truth"]==m["integer_truth"]
        assert read(a.stage/"RESULTS"/(case+"_"+condition+".json"))==record
        cached=read(a.stage/"RESULTS"/(case+"_A.json"));assert s["unique_A"][case]==cached
        for field in ["ambiguity","baseline_ecef_m","raw_whitened_residual_squared","solver","integer_correct"]:assert cached.get(field)==record["A"].get(field)
        aa=candidate(record["A"],m,cond,"A");bb=candidate(record["B"],m,cond,"B")
        keep=aa["available"] and bb["available"] and aa["integer"]==bb["integer"]
        assert keep==record["C_retained"]
        assert bool(keep and bb["integer_correct"])==record["C_correct_retained"]
        assert bool(keep and not bb["integer_correct"])==record["C_wrong_retained"]
        d=record["D"];assert d["available"]==bool(aa["available"] and bb["available"])
        if d["available"]:
            fa=aa["Jraw"]+cap;fb=bb["Jraw"]+bb["rp_residual_sigma"]**2
            branch="B" if fb<fa else "A";chosen=bb if branch=="B" else aa
            eta=bb["Jraw"]-aa["Jraw"];increase=chosen["Jraw"]-aa["Jraw"]
            bounded=chosen["Jraw"]+min(chosen["rp_residual_sigma"]**2,cap)
            assert eta>=-1e-6 and -1e-6<=increase<=cap+1e-6
            assert abs(bb["rp_residual_sigma"])<=3+1e-6 if branch=="B" else abs(aa["rp_residual_sigma"])>=3-1e-6
            assert branch==d["selected_branch"] and chosen["integer"]==d["ambiguity"] and chosen["integer_correct"]==d["integer_correct"]
            fields={"fault_branch_score":fa,"healthy_branch_score":fb,"healthy_minus_fault_score":fb-fa,"raw_cost_increase_B_vs_A":eta,"selected_raw_cost_increase_vs_A":increase,"full_bounded_objective":bounded,"selected_prior_residual_sigma":chosen["rp_residual_sigma"],"projected_heading_error_deg":chosen["heading_error_deg"]}
            for name,value in fields.items():near("D_"+name,value,d[name],2e-7)
            near("D_min_equivalence",bounded,min(fa,fb),2e-7)
            dd={**chosen,"selected_branch":branch,"S_A":fa,"S_B":fb,"eta":eta,"raw_cost_increase":increase}
        else:dd={"available":False,"integer_correct":False}
        rows.append({"case_id":case,"condition":condition,"source_group":m["source_group"],"A":aa,"B":bb,"C_retained":keep,"C_correct_retained":bool(keep and bb["integer_correct"]),"C_wrong_retained":bool(keep and not bb["integer_correct"]),"D":dd})
    assert seen==set((m["case_id"],c["name"]) for m in models.values() for c in m["conditions"])
    assert all(x["candidate"] for x in ends)
    def count(items):
        return {"planned":len(items),"available":sum(x["available"] for x in items),"correct":sum(x["available"] and x["integer_correct"] for x in items),"wrong":sum(x["available"] and not x["integer_correct"] for x in items),"unresolved":sum(not x["available"] for x in items)}
    summary={}
    for cond in ["NOMINAL","RP_BIAS","PHASE_BIAS"]:
        group=[r for r in rows if r["condition"]==cond]
        item={k:count([r[k] for r in group]) for k in ["A","B","D"]}
        item["C"]={"planned":len(group),"retained":sum(r["C_retained"] for r in group),"correct_retained":sum(r["C_correct_retained"] for r in group),"wrong_retained":sum(r["C_wrong_retained"] for r in group),"unresolved":sum(not r["C_retained"] for r in group)}
        for branch in ["A","B"]:item["D_selected_"+branch]=sum(r["D"].get("selected_branch")==branch for r in group)
        item["D_repairs_wrong_A"]=[r["case_id"] for r in group if r["A"]["available"] and not r["A"]["integer_correct"] and r["D"]["integer_correct"]]
        item["D_worsens_correct_A"]=[r["case_id"] for r in group if r["A"]["integer_correct"] and r["D"]["available"] and not r["D"]["integer_correct"]]
        summary[cond]=item
    assert all(sha(a.stage/k)==v for k,v in snapshot.items())
    assert all(sha(a.stage/"RESULTS"/k)==v for k,v in s["result_hashes"].items())
    report={"status":"PASS_INDEPENDENT_RECOMPUTATION","execution_commit":s["execution_commit"],"stage":"<TIM_AR_SCRATCH>/D_PREP02","data_mode":"synthetic_known_integer_real_geometry","independent_of_selector_implementation":True,"solver_calls_by_review":0,"git_calls_by_review":0,"source_pin_count":len(p["source_pins"]),"input_pin_count":len(p["input_pins"]),"result_file_count":20,"ledger_start_end_pairs":20,"logical_rows":12,"unique_measurement_instances":8,"independent_noise_draws":4,"input_output_seals":snapshot,"review_script_sha256":sha(Path(__file__)),"strace_open_attempts_parsed":len(paths),"strace_unique_paths":len(set(paths)),"strace_forbidden_raw_or_reference_paths":[],"io_rule":"Actual RAW_ROOT subtree, /data/raw/ component and known trace_vrtk filename prefix; attempts included.","maximum_recompute_differences":dict(delta),"by_condition":summary,"rows":rows,"global_optimum_scope":"Recorded branch certificates checked; no rerun or independent proof of C-ILS global optimality.","risk_scope":"Four independent noise draws with shared conditions; no statistical risk estimate or real integer validation."}
    with (a.out/"D_INDEPENDENT_REVIEW.json").open("x") as f:json.dump(report,f,ensure_ascii=False,indent=2,allow_nan=False);f.write("\n")
    print(json.dumps({"status":report["status"],"max_differences":dict(delta),"by_condition":summary},ensure_ascii=False))
if __name__=="__main__":main()
