"""Independent saved-matrix audit; never imports or calls the carrier solver."""
from __future__ import annotations
import argparse, csv, hashlib, json
from pathlib import Path
import numpy as np

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()

def audit(root: Path, docs: Path):
    files = {}
    def read(p):
        files[str(p)] = sha(p)
        return json.loads(p.read_text())
    def model(p):
        files[str(p)] = sha(p)
        with np.load(p, allow_pickle=False) as z:
            return {k: z[k].copy() for k in ("y", "A", "B", "Q")}
    def require(test, reason):
        if not test: raise AssertionError(reason)
    def close(a,b,reason,atol=2e-6,rtol=2e-8):
        require(np.isfinite([a,b]).all() and abs(a-b)<=atol+rtol*abs(b),reason)
    records=[];future=[];windows=[];maxima={}
    def err(name, val): maxima[name]=max(maxima.get(name,0.),float(abs(val)))
    def assemble(blocks,labels_by_epoch):
        labels=list(dict.fromkeys(s for ls in labels_by_epoch for s in ls))
        nobs=sum(len(b["y"]) for b in blocks); m=len(labels)
        y=np.empty(nobs);A=np.zeros((nobs,m));B=np.zeros((nobs,3*len(blocks)));Q=np.zeros((nobs,nobs))
        off=0; ranks=[];qmins=[];qasyms=[]
        for k,(b,ls) in enumerate(zip(blocks,labels_by_epoch)):
            n=len(b["y"]); sl=slice(off,off+n)
            require(b["A"].shape==(n,len(ls)) and b["B"].shape==(n,3) and b["Q"].shape==(n,n),"dimensions")
            require(all(np.isfinite(v).all() for v in b.values()),"finite model")
            require(len(set(ls))==len(ls),"duplicate local label")
            q=b["Q"];qasym=float(np.max(np.abs(q-q.T)))
            require(qasym<=1e-10*max(1.,np.max(np.abs(q))),"Q asymmetry")
            np.linalg.cholesky(q);qmins.append(float(np.linalg.eigvalsh(q)[0]));qasyms.append(qasym)
            ranks.append(int(np.linalg.matrix_rank(b["B"])))
            require(ranks[-1]==3,"epoch B rank")
            y[sl]=b["y"];A[np.ix_(range(off,off+n),[labels.index(s) for s in ls])]=b["A"]
            B[sl,3*k:3*k+3]=b["B"];Q[sl,sl]=q
            off+=n
        L=np.linalg.cholesky(Q)
        yw=np.linalg.solve(L,y);Aw=np.linalg.solve(L,A);Bw=np.linalg.solve(L,B)
        X=np.column_stack((Aw,Bw));u,s,vt=np.linalg.svd(X,full_matrices=False)
        rank=int(np.sum(s>np.finfo(float).eps*max(X.shape)*s[0]))
        require(rank==X.shape[1],"joint float rank")
        xf=vt.T@((u.T@yw)/s);cov=(vt.T/(s*s))@vt
        ff=float(np.linalg.norm(yw-X@xf)**2)
        return dict(y=y,A=A,B=B,Q=Q,L=L,yw=yw,Aw=Aw,Bw=Bw,labels=labels,xf=xf,cov=cov,float_cost=ff,rank=rank,condition=float(s[0]/s[-1]),qmin=min(qmins),qasym=max(qasyms),epoch_ranks=ranks)
    for trial in ["REAL_80_82_V1","REAL_100_102_V2"]:
        base=root/trial; plan=read(base/"PLAN.json")
        require(plan["real_integer_truth_available"] is False and plan["reference_reads"]==0 and plan["accepted_integer_measurement"] is False,"plan scope")
        length=float(plan["baseline_length_m"]); times=[e["time_s"] for e in plan["records"]]
        require(np.all(np.diff(times)>0) and len(times)==10,"chronology")
        matrices={}; groups={}
        for family in plan["families"]:
            matrices[family]=[model(base/e["families"][family]["file"]) for e in plan["records"]]
            groups[family]=[[g["key"] for g in e["families"][family]["groups"]] for e in plan["records"]]
            require(all(e["families"][family]["status"]=="BUILT" for e in plan["records"]),"epoch eligibility")
        current={}
        for mode in ["SOLVE","SOLVE_ACTIVE"]:
            agg=read(base/mode/"RESULTS.json")
            require(len(agg["records"])==(9 if mode=="SOLVE" else 6),"result count")
            require(agg["reference_reads"]==0 and agg["real_integer_truth_available"] is False,"aggregate scope")
            public=docs/f"{trial}_{mode}.json"
            require(read(public)==agg,"public solve copy")
            ledgerp=base/mode/"LEDGER.jsonl";files[str(ledgerp)]=sha(ledgerp)
            ledger=[json.loads(s) for s in ledgerp.read_text().splitlines() if s]
            for event in ["SOLVE_START","SOLVE_END"]:
                ev=[(v["family"],v["prefix_epochs"]) for v in ledger if v["event"]==event]
                require(sorted(ev)==sorted((v["family"],v["prefix_epochs"]) for v in agg["records"]),"ledger count/identity")
            for result in agg["records"]:
                family=result["family"];p=result["prefix_epochs"];tag=f"{trial}/{mode}/{family}_{p:02d}"
                require(read(base/mode/f"{family}_{p:02d}.json")==result,"individual/aggregate")
                labels_each=[e["families"][family]["ambiguity_labels"] for e in plan["records"][:p]]
                m=assemble(matrices[family][:p],labels_each);labels=m["labels"]
                require(result["ambiguity_labels"]==labels and len(labels)==result["ambiguities"],"global label identity")
                require(result["observations"]==len(m["y"]) and result["baseline_epochs"]==p and result["endpoint_time_s"]==times[p-1],"model support")
                require(result["actual_group_keys_by_epoch"]==groups[family][:p],"actual groups")
                require(result["status"]=="CERTIFIED_CANDIDATE" and result["accepted_integer_measurement"] is False,"candidate boundary")
                cert=result["certificate"]
                require(cert["global_optimum_certified"] is True and cert["integer_acceptance_test_defined"] is False and cert["candidate_cap_applied"] is False,"certificate boundary")
                scope=cert.get("certificate_scope")
                if scope is None:
                    require(trial=="REAL_80_82_V1" and mode=="SOLVE","unexpected absent scope")
                elif mode=="SOLVE_ACTIVE":
                    require(scope=="two_best_selected_integer_classes" and cert["distinct_ambiguity_labels"]==labels_each[-1],"active scope/labels")
                else: require(scope=="two_best_full_integer_vectors" and cert["distinct_ambiguity_labels"]==labels,"full scope/labels")
                close(m["float_cost"],result["float_residual_cost"],"float cost")
                close(m["condition"],result["float_condition_number"],"condition")
                err("float_cost_absolute_error",m["float_cost"]-result["float_residual_cost"])
                costs=[];candidate_audit={}
                for side in ["best","second"]:
                    c=result[side];n=np.asarray(c["ambiguity"]);b=np.asarray(c["baselines"],float)
                    require(n.shape==(len(labels),) and n.dtype.kind in "iu" and np.max(np.abs(n))<=2**53-1,"integer shape/value")
                    require(b.shape==(p,3) and np.isfinite(b).all(),"baseline shape")
                    residual=m["y"]-m["A"]@n-m["B"]@b.ravel()
                    direct=float(np.linalg.norm(np.linalg.solve(m["L"],residual))**2)
                    dn=n-m["xf"][:len(labels)]
                    ambiguity=float(dn@np.linalg.solve(m["cov"][:len(labels),:len(labels)],dn))
                    center=np.linalg.lstsq(m["Bw"],m["yw"]-m["Aw"]@n,rcond=None)[0]
                    penalty=float(np.linalg.norm(m["Bw"]@(b.ravel()-center))**2)
                    lengtherr=float(np.max(np.abs(np.linalg.norm(b,axis=1)-length)))
                    require(lengtherr<1e-10,"sphere length")
                    for key,v in [("full_residual_cost",direct),("ambiguity_cost",ambiguity),("length_constraint_cost",penalty),("reduced_cost",ambiguity+penalty),("float_residual_cost",m["float_cost"])]:
                        close(v,c[key],tag+"/"+side+"/"+key)
                        err(key+"_absolute_error",v-c[key])
                    close(direct,m["float_cost"]+ambiguity+penalty,"objective decomposition")
                    close(lengtherr,c["maximum_length_error_m"],"reported length error",atol=1e-14,rtol=0)
                    err("maximum_length_error_m",lengtherr)
                    candidate_audit[side]={"direct_residual_cost":direct,"ambiguity_cost":ambiguity,"sphere_increment_cost":penalty,"decomposition_error":direct-m["float_cost"]-ambiguity-penalty,"maximum_length_error_m":lengtherr}
                    costs.append(direct)
                require(costs[0]<=costs[1]+1e-6,"candidate order")
                all_diff=[labels[i] for i,(a,b) in enumerate(zip(result["best"]["ambiguity"],result["second"]["ambiguity"])) if a!=b]
                active_diff=[s for s in all_diff if s in labels_each[-1]]
                require(bool(all_diff) and (mode!="SOLVE_ACTIVE" or bool(active_diff)),"candidate distinction")
                for side in ["best","second"]: close(cert[side+"_reduced_cost"],result[side]["reduced_cost"],"certificate incumbent")
                if cert["termination_reason"]=="GLOBAL_BOUND_CERTIFIED":
                    require(cert["frontier_lower_bound"]+1e-7>=cert["second_reduced_cost"],"frontier lower bound")
                else: require(cert["termination_reason"]=="GLOBAL_ENUMERATION_EXHAUSTED" and cert["frontier_lower_bound"] is None,"terminal certificate")
                records.append({"trial":trial,"mode":mode,"family":family,"prefix_epochs":p,"status":"PASS","recorded_global_certificate":True,"recorded_certificate_scope":scope,"scope_interpretation":"full integer vectors (legacy missing scope field)" if scope is None else scope,"observation_count":len(m["y"]),"integer_dimension":len(labels),"active_integer_dimension":len(labels_each[-1]),"joint_columns":len(labels)+3*p,"joint_rank":m["rank"],"joint_condition_number":m["condition"],"minimum_epoch_Q_eigenvalue":m["qmin"],"maximum_Q_asymmetry":m["qasym"],"full_difference_count":len(all_diff),"active_difference_count":len(active_diff),"active_differing_labels":active_diff,"candidates":candidate_audit})
                current[(mode,family,p)]=result
        fobj=read(base/"FUTURE_ACTIVE/FUTURE_RESULTS.json")
        require(len(fobj["records"])==3 and fobj["raw_payload_reads"]==0 and fobj["reference_reads"]==0 and fobj["integer_search_calls"]==0,"future scope")
        for f in fobj["records"]:
            family=f["family"];decision=f["decision_prefix"];selected=current[("SOLVE_ACTIVE",family,decision)]
            require(f["decision_time_s"]==times[decision-1] and f["integer_selection_uses_future"] is False and f["accepted_integer_measurement"] is False,"future causal boundary")
            maps={}
            for side in ["best","second"]:
                cand=dict(zip(selected["ambiguity_labels"],selected[side]["ambiguity"]))
                smap={}
                for item in f["candidate_results"][side]["scores"]:
                    require(item["status"]=="SCORED","unexpected future score unavailable")
                    score=item["score"];t=score["time_s"];k=times.index(t)
                    require(k>=decision and t>f["decision_time_s"],"future strict time")
                    block=matrices[family][k];ls=plan["records"][k]["families"][family]["ambiguity_labels"]
                    keep=score["rows_retained"]; withheld=score["rows_withheld"];unknown=[s for s in ls if s not in cand]
                    require(score["unknown_labels"]==unknown and sorted(keep+withheld)==list(range(len(block["y"]))) and len(set(keep+withheld))==len(block["y"]),"future row/label support")
                    ui=[j for j,s in enumerate(ls) if s not in cand]
                    expected=[i for i in range(len(block["y"])) if not any(block["A"][i,j]!=0 for j in ui)]
                    require(keep==expected,"future withheld dependency")
                    n=np.array([cand.get(s,0) for s in ls]);b=np.array(score["baseline_m"])
                    q=block["Q"][np.ix_(keep,keep)]
                    residual=(block["y"]-block["A"]@n-block["B"]@b)[keep]
                    wr=np.linalg.solve(np.linalg.cholesky(q),residual);cost=float(wr@wr)
                    close(cost,score["residual_cost"],"future direct cost")
                    require(np.allclose(wr,score["whitened_residuals"],atol=2e-7,rtol=2e-8),"future saved residual")
                    close(abs(np.linalg.norm(b)-length),score["length_error_m"],"future length",atol=1e-14,rtol=0)
                    require(np.linalg.matrix_rank(block["B"][keep])==3 and score["baseline_rank"]==3,"future B rank")
                    err("future_residual_cost_absolute_error",cost-score["residual_cost"])
                    smap[t]=(tuple(keep),cost)
                require(len(smap)==f["candidate_results"][side]["scored_epochs"]==5,"future scored count")
                close(sum(v[1] for v in smap.values()),f["candidate_results"][side]["residual_cost_sum"],"future own sum")
                maps[side]=smap
            common=[t for t in maps["best"] if t in maps["second"] and maps["best"][t][0]==maps["second"][t][0]]
            cmp=f["common_support_comparison"]
            require(len(common)==5 and common==cmp["common_times"] and cmp["complete_matching_support"] is True,"future paired support")
            first=sum(maps["best"][t][1] for t in common);second=sum(maps["second"][t][1] for t in common)
            close(first,cmp["first_cost"],"future common first");close(second,cmp["second_cost"],"future common second")
            gap=second-first;close(gap,cmp["second_minus_first"],"future gap");close(gap,f["future_cost_gap_second_minus_best"],"future headline gap")
            future.append({"trial":trial,"family":family,"common_scored_epochs":len(common),"rows_identical_between_candidates":True,"first_cost":first,"second_cost":second,"second_minus_first":gap,"status":f["comparison_status"],"accepted_integer_measurement":False})
        windows.append({"trial":trial,"recorded_source_commit":plan["source_commit"],"prepare_snapshot_status":plan.get("prepare_snapshot_status","not present in PLAN"),"epoch_count":len(times),"actual_groups_by_epoch":groups,"raw_pairing":plan["pairing"],"real_integer_truth_available":False})
    metrics=docs/"REAL_METRICS.csv";files[str(metrics)]=sha(metrics)
    rows=list(csv.DictReader(metrics.open()))
    require(len(rows)==30,"metrics row count")
    idx={(r["trial"],r["mode"],r["family"],r["prefix_epochs"]):r for r in records}
    require(len(idx)==30,"unique result identity")
    for row in rows:
        rr=idx[(row["trial"],row["mode"],row["family_requested"],int(row["prefix_epochs"]))]
        require(row["global_objective_certificate"]=="True" and row["accepted_integer_measurement"]=="False","metrics boundary")
        close(float(row["best_full_cost"]),rr["candidates"]["best"]["direct_residual_cost"],"metrics best")
        close(float(row["second_full_cost"]),rr["candidates"]["second"]["direct_residual_cost"],"metrics second")
    summary=read(docs/"REAL_SUMMARY.json")
    require(summary["real_solver_calls"]==30 and summary["global_objective_certificates"]==30,"summary counts")
    require(summary["real_integer_truth_available"] is False and summary["reference_reads"]==0 and summary["navigation_integration"] is False and summary["cross_family_objective_comparison_valid"] is False,"summary claim boundaries")
    csv_keys={(r["trial"],r["mode"],r["family_requested"],int(r["prefix_epochs"])) for r in rows}
    summary_runs=[r for t in summary["trials"] for r in t["runs"]]
    require(len(summary_runs)==30 and {(r["trial"],r["mode"],r["family_requested"],r["prefix_epochs"]) for r in summary_runs}==csv_keys,"summary identities")
    for row in summary_runs:
        rr=idx[(row["trial"],row["mode"],row["family_requested"],row["prefix_epochs"])]
        require(row["status"]=="CERTIFIED_CANDIDATE" and row["global_objective_certificate"] is True and row["accepted_integer_measurement"] is False,"summary candidate boundary")
        require(row["integer_dimension"]==rr["integer_dimension"] and row["observations"]==rr["observation_count"],"summary dimensions")
        close(row["best_full_cost"],rr["candidates"]["best"]["direct_residual_cost"],"summary best")
        close(row["second_full_cost"],rr["candidates"]["second"]["direct_residual_cost"],"summary second")
        close(row["objective_gap"],rr["candidates"]["second"]["direct_residual_cost"]-rr["candidates"]["best"]["direct_residual_cost"],"summary gap")
    for trial_summary in summary["trials"]:
        ww=next(v for v in windows if v["trial"]==trial_summary["trial"])
        require(trial_summary["pairing"]==ww["raw_pairing"],"summary pair metadata")
        require(len(trial_summary["actual_groups_by_epoch"])==10,"summary epoch count")
        for k,ep in enumerate(trial_summary["actual_groups_by_epoch"]):
            for family,v in ep["families"].items():
                require(v["groups"]==ww["actual_groups_by_epoch"][family][k],"summary actual groups")
    for rel,expected in summary["input_result_sha256"].items():
        pp=root/rel
        require(sha(pp)==expected,"summary input hash")
        files[str(pp)]=expected
    futurecsv=docs/"FUTURE_METRICS.csv";files[str(futurecsv)]=sha(futurecsv)
    future_rows=list(csv.DictReader(futurecsv.open()))
    require(len(future_rows)==len(summary["future_comparisons"])==12,"future aggregate count")
    active_rows=[r for r in future_rows if r["mode"]=="FUTURE_ACTIVE"]
    active_summary=[r for r in summary["future_comparisons"] if r["mode"]=="FUTURE_ACTIVE"]
    require(len(active_rows)==len(active_summary)==6,"future active aggregate count")
    for source in [active_rows,active_summary]:
        for row in source:
            rr=next(r for r in future if r["trial"]==row["trial"] and r["family"]==row["family_requested"])
            close(float(row["best_cost"]),rr["first_cost"],"future aggregate best")
            close(float(row["second_cost"]),rr["second_cost"],"future aggregate second")
            close(float(row["future_gap"]),rr["second_minus_first"],"future aggregate gap")
            require(row["status"]==rr["status"],"future aggregate status")
    return {"audit_status":"PASS_SAVED_MATRIX_NUMERICAL_AND_SUPPORT_REVIEW","scope":{"solver_records":30,"best_second_candidates_recomputed":60,"unique_saved_epoch_npz":60,"active_future_comparisons":6,"saved_future_candidate_epoch_residuals_recomputed":60,"integer_search_calls":0,"native_calls":0,"evaluator_calls":0,"raw_or_reference_payload_reads":0,"read_inputs":"Saved PLAN/NPZ/result/ledger/public aggregate files only; metadata paths are not opened.","global_certificate_statement":"30/30 saved solver records claim a global optimum for their stated model/objective and selection scope; this audit verifies numerical consistency and scope, not a second integer-tree search.","limitations":["No known real integer truth, acceptance threshold or failure-risk calibration.","Baseline length feasibility and lower candidate cost do not establish correct ambiguity or heading.","Two short windows of one sequence; overlapping prefixes and repeated full/active variants are not independent trials.","Working Q is block diagonal across epochs and uses the archived cross-signal model; SPD is a mathematical check, not physical calibration.","V1 legacy full-vector results omit an explicit certificate_scope field; their legacy full-vector interpretation is recorded separately.","No reconstruction or verification of satellite ephemeris, raw decoding or physical time synchronization in this audit."]},"numerical_tolerances":{"objective_absolute":2e-6,"objective_relative":2e-8,"length_absolute_m":1e-10},"maxima":maxima,"windows":windows,"records":records,"future_common_support":future,"aggregate_checks":{"REAL_METRICS_rows":len(rows),"public_solve_jsons_equal_scratch":True,"individual_results_equal_aggregate":True,"ledger_start_end_identities_match":True,"REAL_SUMMARY_counts_support_costs_pins_verified":True,"FUTURE_METRICS_rows":len(future_rows),"FUTURE_ACTIVE_aggregates_verified":6,"legacy_future_comparisons":"Six V1 categorized comparisons retain the prior INDEPENDENT_REVIEW audit; this final residual reconstruction covers the six ACTIVE comparisons."},"input_sha256":files}

if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--scratch-root",type=Path,required=True);p.add_argument("--docs",type=Path,required=True);args=p.parse_args()
    report=audit(args.scratch_root,args.docs)
    report["review_script_sha256"]=sha(Path(__file__))
    raw=args.scratch_root/"FINAL_REAL_REVIEW_RAW.json"
    raw.write_text(json.dumps(report,indent=2,ensure_ascii=False,allow_nan=False)+"\n")
    code_root=Path(__file__).resolve().parents[3]
    aliases=[(str(args.scratch_root.resolve()),"<CARRIER_SCRATCH>"),(str(code_root),"<CODE_ROOT>")]
    def public_value(value):
        if isinstance(value,str):
            for path,alias in aliases: value=value.replace(path,alias)
            return value
        if isinstance(value,dict): return {public_value(k):public_value(v) for k,v in value.items()}
        if isinstance(value,list): return [public_value(v) for v in value]
        return value
    report=public_value(report)
    report["serialization"]={"public_paths":"<CODE_ROOT>/<CARRIER_SCRATCH> aliases; artifact hash values unchanged.","raw_receipt":"<CARRIER_SCRATCH>/FINAL_REAL_REVIEW_RAW.json","raw_receipt_sha256":sha(raw),"public_receipt_differs_from_raw":True}
    out=args.docs/"FINAL_REAL_REVIEW.json";out.write_text(json.dumps(report,indent=2,ensure_ascii=False,allow_nan=False)+"\n")
    print(json.dumps({"output":str(out),"sha256":sha(out),"status":report["audit_status"],"maxima":report["maxima"],"future":report["future_common_support"]},indent=2))
