#!/usr/bin/env python3
"""Combine sealed native/full-likelihood and selected-likelihood navigation trials."""
from pathlib import Path
import argparse,csv,hashlib,json,subprocess,sys
NEW=("NATIVE_FULL6_TRACKING","NATIVE_FULL6_SERIAL","SELECTED_LIKELIHOOD_TRACKING","SELECTED_LIKELIHOOD_SERIAL")
OLD={"V1":"NAVIGATION_BODY_HV_01","V2":"NAVIGATION_BODY_HV_V2","TRACKING_V2":"NAVIGATION_TRACKING_V2","PARTIAL6":"NAVIGATION_PARTIAL6","SERIAL_LATENCY_PARTIAL6":"NAVIGATION_SERIAL_LATENCY_PARTIAL6"}
CASES=("C0_SCALAR","C1_DUAL_PVT_VECTOR","C2_FULL_CARRIER_VECTOR","C3_PARTIAL_CARRIER_VECTOR")
PREFIX="NATIVE_SELECTED_NAVIGATION_"
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def csvread(p):
    with p.open() as f:return list(csv.DictReader(f))
def csvwrite(p,rows):
    with p.open("x",newline="") as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator="\n");w.writeheader();w.writerows(rows)
def emit(p,value):
    with p.open("x") as f:json.dump(value,f,indent=2,ensure_ascii=False,allow_nan=False);f.write("\n")
def main():
    ap=argparse.ArgumentParser()
    for key in ("code","scratch","controller","output"):ap.add_argument("--"+key,type=Path,required=True)
    a=ap.parse_args()
    generic=a.controller/"GENERIC_DERIVATION"
    assert not generic.exists()
    trials={**{k:a.scratch/v for k,v in OLD.items()},**{k:a.scratch/("NAVIGATION_"+k) for k in NEW}}
    current="SELECTED_LIKELIHOOD_SERIAL"
    cmd=[sys.executable,str(a.code/"scripts/paper_rebuild/carrier_phase/compare_navigation_trials.py")]
    for name,path in trials.items():cmd+=["--trial",name,str(path)]
    cmd+=["--new",current,"--baseline","PARTIAL6","--expect-identical-controls",*CASES[:3],
          "--require-zero-carrier",CASES[2],"--output",str(generic)]
    subprocess.run(cmd,cwd=a.code,check=True)
    data=read(generic/"SUMMARY.json")
    rows=csvread(generic/"RESULTS.csv");counts=csvread(generic/"RUN_COUNTS.csv")
    assert len(rows)==108 and len(counts)==36 and len(csvread(generic/"DIFFERENCES.csv"))==96
    base=read(trials["PARTIAL6"]/"ALL_NATIVE_SEALED.json")
    controls={};phases={};upstream={}
    for name in NEW:
        seal=read(trials[name]/"ALL_NATIVE_SEALED.json")
        ev=read(trials[name]/"EVALUATION_COMPLETE.json")
        controls[name]={}
        for case in CASES[:3]:
            x=next(v for v in seal["records"] if v["case"]==case)
            b=next(v for v in base["records"] if v["case"]==case)
            controls[name][case]=all(x[k]["sha256"]==b[k]["sha256"] for k in ("nav","std"))
        assert all(controls[name].values())
        d=a.controller/name
        phases[name]={phase:{"start_unix":read(d/(phase+"_INVOCATION.json"))["unix"],
                            "end_unix":read(d/(phase+"_RESULT.json"))["unix"],
                            "returncode":read(d/(phase+"_RESULT.json"))["returncode"]} for phase in ("prepare","native","evaluate")}
        assert all(v["returncode"]==0 for v in phases[name].values())
        assert phases[name]["native"]["end_unix"]<phases[name]["evaluate"]["start_unix"]
        assert seal["solver_calls"]==ev["evaluator_calls"]==4
        prefix=name.rsplit("_",1)[0]
        acq=read(a.scratch/(prefix+"_FRONTEND")/"SUMMARY_0001.json")
        stream=read(a.scratch/name/"SUMMARY.json")
        mode=stream["modes"]["partial"]
        upstream[name]={"likelihood":acq["input_contract"]["likelihood"],"sphere_backend":acq["input_contract"]["sphere_backend"],
            "acquisition_new_search_calls":acq["new_search_calls"],"acquisition_cases":acq["modes"]["partial"]["cases"],
            "valid_epochs":mode["valid_experimental_measurements"],"events":mode["events"],
            "recorded_cost_availability":name.endswith("_SERIAL"),"summary_sha256":sha(a.scratch/name/"SUMMARY.json")}
        if name.endswith("_SERIAL"):
            upstream[name].update(service_actions=mode["service_actions"],arrival_actions=mode["arrival_actions"],pending_at_end=mode["pending_at_end"],
                                 cost_field=stream["cost_field"],zero_cost_components=stream["zero_cost_components"])
        full=next(v for v in counts if v["trial"]==name and v["case"]==CASES[2])
        assert int(full["carrier_provider_valid_epochs"])==int(full["native_vector_accepts"])==0
    assert phases[NEW[0]]["prepare"]["start_unix"]>=read(a.scratch/"NATIVE_AND_SELECTED_DRIVER/COMPLETE.json")["unix"]
    contrasts=[]
    metrics=("H_RMSE_m","V_RMSE_m","D3_RMSE_m","yaw_RMSE_deg","yaw_max_abs_deg")
    for name in NEW:
        for row in [v for v in rows if v["trial"]==name and v["case"]==CASES[3]]:
            for reference,case in [("PARTIAL6",CASES[3]),("SERIAL_LATENCY_PARTIAL6",CASES[3]),(name,CASES[1])]:
                other=next(v for v in rows if v["trial"]==reference and v["case"]==case and v["domain"]==row["domain"])
                assert all(row[k]==other[k] for k in ("epochs","first_time","last_time"))
                item={"trial":name,"case":CASES[3],"reference_trial":reference,"reference_case":case,"domain":row["domain"],"epochs":row["epochs"]}
                for key in metrics:
                    item[key]=float(row[key]);item[key+"_reference"]=float(other[key]);item[key+"_difference"]=float(row[key])-float(other[key])
                contrasts.append(item)
    assert len(contrasts)==36
    a.output.mkdir(parents=True,exist_ok=True)
    for n in ("RESULTS.csv","RUN_COUNTS.csv","DIFFERENCES.csv"):
        with (a.output/(PREFIX+n)).open("xb") as f:f.write((generic/n).read_bytes())
    csvwrite(a.output/(PREFIX+"NEW_C3_CONTRASTS.csv"),contrasts)
    data.update(new_trial=current,new_trials=list(NEW),new_native_calls=16,new_evaluator_calls=16,
                reused_navigation_runs_for_comparison=20,new_searches=0,
                scope_of_new_searches="Navigation/controller only; two separately registered upstream frontends each execute their own search budget.",
                upstream_trials=upstream,expected_control_NAV_STD_byte_identity_all_new_variants=controls,
                all_9_versions_36_chains_same_time_support=True,actual_phase_ledger=phases,
                likelihood_equivalence_claimed=False,native_kernel_uses_original_full_nuisance_likelihood=True,
                selected_likelihood_changes_observation_model=True,serial_replays_use_each_trial_own_recorded_costs=True,
                default_current_development_variant=current,default_is_not_a_production_FIX_claim=True,
                counts_distinguish_new_runs_and_reused_runs=True,
                original_generic_derivation_summary_sha256=sha(generic/"SUMMARY.json"),aggregation_script_sha256=sha(__file__))
    data["unique_upstream_acquisition_groups"]=["NATIVE_FULL6","SELECTED_LIKELIHOOD"]
    data["unique_upstream_search_calls"]=sum(read(a.scratch/(group+"_FRONTEND")/"SUMMARY_0001.json")["new_search_calls"] for group in data["unique_upstream_acquisition_groups"])
    data["upstream_search_count_scope"]="240 unique calls across two upstream groups; per-stream repeated acquisition counts identify lineage and must not be added again."
    text=json.dumps(data,indent=2,ensure_ascii=False,allow_nan=False).replace(str(a.scratch),"<CARRIER_SCRATCH>").replace(str(a.code),"<CODE_ROOT>")
    with (a.output/(PREFIX+"SUMMARY.json")).open("x") as f:f.write(text+"\n")
    def metric(name,case=CASES[3]):return next(v for v in rows if v["trial"]==name and v["case"]==case and v["domain"]=="full_66_340")
    def count(name,case=CASES[3]):return next(v for v in counts if v["trial"]==name and v["case"]==case)
    desc={"NATIVE_FULL6_TRACKING":"原完整 likelihood + native kernel；不计搜索延迟",
          "NATIVE_FULL6_SERIAL":"原完整 likelihood + native kernel；计自身记录搜索耗时",
          "SELECTED_LIKELIHOOD_TRACKING":"预选观测 likelihood；Python；不计搜索延迟",
          "SELECTED_LIKELIHOOD_SERIAL":"预选观测 likelihood；Python；计自身记录搜索耗时"}
    lines=["# 完整似然加速与预选观测似然：九版本导航比较","",
      "前端两项试验各新增 120 次搜索，共 240 次，tracking/serial 只复用各自前端结果，不重复计为新搜索。本导航控制器新增 C-ILS 为 0。本轮实际新增 16 次 native 与 16 次冻结离线评价；每个变体四个 native 全部封存并通过控制检查后才评价。已有五版本的 20 次导航仅复用。九版本、36 条链均有共同的 56,642 个原始/STD/评价时间键；完整名义窗口 66–340 s，实际输出 66.005054–339.997056 s，未按载波成功时刻筛选。",
      "",
      "本轮预先指定的当前开发变体是 SELECTED_LIKELIHOOD_SERIAL，不按下表指标选优，也不等于生产方法验收。NATIVE_FULL6 保留原完整观测似然及 nuisance 整数，只换可选球面内核；SELECTED_LIKELIHOOD 先选择观测支持再构造新的似然，属于不同模型，不能称为等价加速。",
      "",
      "| 主对照/新变体 | 含义 | H RMSE (m) | V RMSE (m) | yaw RMSE (deg) | 最大绝对 yaw (deg) | valid | native 接纳 |",
      "|---|---|---:|---:|---:|---:|---:|---:|"]
    pvt=metric(current,CASES[1]);pc=count(current,CASES[1])
    lines.append(f"| C1 双位置向量 | 四新变体共同、字节一致 | {float(pvt['H_RMSE_m']):.6f} | {float(pvt['V_RMSE_m']):.6f} | {float(pvt['yaw_RMSE_deg']):.6f} | {float(pvt['yaw_max_abs_deg']):.6f} | NA | {pc['native_vector_accepts']} |")
    for name in NEW:
        v=metric(name);c=count(name)
        lines.append(f"| {name} / C3 | {desc[name]} | {float(v['H_RMSE_m']):.6f} | {float(v['V_RMSE_m']):.6f} | {float(v['yaw_RMSE_deg']):.6f} | {float(v['yaw_max_abs_deg']):.6f} | {c['carrier_provider_valid_epochs']} | {c['native_vector_accepts']} |")
    lines+=["","四个新变体的 C0/C1/C2 NAV 与 STD 均和 PARTIAL6 对应控制字节一致。全量 RESULTS 保留九版本四臂三域（108 行）；RUN_COUNTS 保留 36 条链；DIFFERENCES 保留当前开发变体对其余八版本的三域差值（96 行）；NEW_C3_CONTRASTS 列出四个新 C3 对 PARTIAL6、原串行 PARTIAL6 和同变体 C1 的比较（36 行）。",
      "","SERIAL 使用各自完整试验的原 certificate.elapsed_s，单 worker busy-drop/noqueue，晚到结果经逐历史历元追赶且仅输出当前测量。没有从少量基准外推运行费用。TRACKING 仍是不计计算延迟的回放；两类结果不能混称实时效果。准备、验证、GLRT、追赶、tracking、IO、导航和资源争用成本仍计零，SERIAL 也不是硬件实时验证。",
      "","本轮只改变登记的前端模型/计算实现与可用时间流，导航二进制、body HV、P/RV/RD/RP、初始化、评价器和噪声门固定。没有按参考误差筛选观测、选择候选或调整参数；评价参考是 Fixposition 派生结果，非独立真值。真实整数没有标签，连续历元共享整数，认证或更新数量不能解释为同数量的正确固定、校准完整性或泛化证据。"]
    with (a.output/(PREFIX+"READOUT.md")).open("x") as f:f.write("\n".join(lines)+"\n")
    outputs=sorted(a.output.glob(PREFIX+"*"))
    for p in outputs:
        assert "/home/kaiwen" not in p.read_text() and "/mnt/g/" not in p.read_text()
    emit(a.controller/"FINAL_PUBLIC_REPORTS_SEALED.json",{"status":"SEALED","files":{p.name:sha(p) for p in outputs},"new_native":16,"new_evaluator":16,"reused_navigation":20})
    print(json.dumps({"status":"PASS","versions":9,"chains":36,"new_native":16,"new_evaluator":16,"metrics":108,"default_current":current}))
if __name__=="__main__":main()
