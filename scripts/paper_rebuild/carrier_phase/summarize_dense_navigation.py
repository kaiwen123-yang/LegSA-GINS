#!/usr/bin/env python3
"""Combine two dense-cadence navigation trials with the nine saved earlier versions."""
from pathlib import Path
import argparse,csv,hashlib,json,subprocess,sys
NEW=("DENSE_SELECTED_TRACKING","DENSE_SELECTED_SERIAL")
OLD={"V1":"NAVIGATION_BODY_HV_01","V2":"NAVIGATION_BODY_HV_V2","TRACKING_V2":"NAVIGATION_TRACKING_V2","PARTIAL6":"NAVIGATION_PARTIAL6","SERIAL_LATENCY_PARTIAL6":"NAVIGATION_SERIAL_LATENCY_PARTIAL6"}
OLD.update({k:"NAVIGATION_"+k for k in ("NATIVE_FULL6_TRACKING","NATIVE_FULL6_SERIAL","SELECTED_LIKELIHOOD_TRACKING","SELECTED_LIKELIHOOD_SERIAL")})
CASES=("C0_SCALAR","C1_DUAL_PVT_VECTOR","C2_FULL_CARRIER_VECTOR","C3_PARTIAL_CARRIER_VECTOR")
PREFIX="DENSE_NAVIGATION_"
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
    current="DENSE_SELECTED_SERIAL"
    cmd=[sys.executable,str(a.code/"scripts/paper_rebuild/carrier_phase/compare_navigation_trials.py")]
    for name,path in trials.items():cmd+=["--trial",name,str(path)]
    cmd+=["--new",current,"--baseline","PARTIAL6","--expect-identical-controls",*CASES[:3],
          "--require-zero-carrier",CASES[2],"--output",str(generic)]
    subprocess.run(cmd,cwd=a.code,check=True)
    data=read(generic/"SUMMARY.json")
    rows=csvread(generic/"RESULTS.csv");counts=csvread(generic/"RUN_COUNTS.csv")
    assert len(rows)==132 and len(counts)==44 and len(csvread(generic/"DIFFERENCES.csv"))==120
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
                                 cost_field=stream["cost_field"],zero_cost_components=stream["zero_cost_components"],
                                 opportunity_cadence=stream["opportunity_cadence_by_mode"]["partial"],
                                 simulated_cils_attempts_started=mode["simulated_cils_attempts_started"],
                                 presearch_unavailable_no_cils=mode["presearch_unavailable_no_cils"],
                                 serviced_cost_sources=mode["serviced_cost_sources"])
        full=next(v for v in counts if v["trial"]==name and v["case"]==CASES[2])
        assert int(full["carrier_provider_valid_epochs"])==int(full["native_vector_accepts"])==0
    assert phases[NEW[0]]["prepare"]["start_unix"]>=read(a.scratch/"DENSE_SELECTED_DRIVER/COMPLETE.json")["unix"]
    contrasts=[]
    metrics=("H_RMSE_m","V_RMSE_m","D3_RMSE_m","yaw_RMSE_deg","yaw_max_abs_deg")
    for name in NEW:
        for row in [v for v in rows if v["trial"]==name and v["case"]==CASES[3]]:
            for reference,case in [("SELECTED_LIKELIHOOD_TRACKING",CASES[3]),("SELECTED_LIKELIHOOD_SERIAL",CASES[3]),(name,CASES[1])]:
                other=next(v for v in rows if v["trial"]==reference and v["case"]==case and v["domain"]==row["domain"])
                assert all(row[k]==other[k] for k in ("epochs","first_time","last_time"))
                item={"trial":name,"case":CASES[3],"reference_trial":reference,"reference_case":case,"domain":row["domain"],"epochs":row["epochs"]}
                for key in metrics:
                    item[key]=float(row[key]);item[key+"_reference"]=float(other[key]);item[key+"_difference"]=float(row[key])-float(other[key])
                contrasts.append(item)
    assert len(contrasts)==18
    a.output.mkdir(parents=True,exist_ok=True)
    for n in ("RESULTS.csv","RUN_COUNTS.csv","DIFFERENCES.csv"):
        with (a.output/(PREFIX+n)).open("xb") as f:f.write((generic/n).read_bytes())
    csvwrite(a.output/(PREFIX+"NEW_C3_CONTRASTS.csv"),contrasts)
    data.update(new_trial=current,new_trials=list(NEW),new_native_calls=8,new_evaluator_calls=8,
                reused_navigation_runs_for_comparison=36,new_searches=0,
                scope_of_new_searches="Navigation/controller only; one separately registered upstream frontend executes at most 1191 search attempts.",
                upstream_trials=upstream,expected_control_NAV_STD_byte_identity_all_new_variants=controls,
                all_11_versions_44_chains_same_time_support=True,actual_phase_ledger=phases,
                likelihood_equivalence_claimed=False,dense_native_kernel_uses_selected_observation_likelihood=True,
                selected_likelihood_changes_observation_model=True,serial_replays_use_each_trial_own_recorded_costs=True,
                default_current_development_variant=current,default_is_not_a_production_FIX_claim=True,
                counts_distinguish_new_runs_and_reused_runs=True,
                original_generic_derivation_summary_sha256=sha(generic/"SUMMARY.json"),aggregation_script_sha256=sha(__file__))
    data["unique_upstream_acquisition_groups"]=["DENSE_SELECTED"]
    data["unique_upstream_search_calls"]=sum(read(a.scratch/(group+"_FRONTEND")/"SUMMARY_0001.json")["new_search_calls"] for group in data["unique_upstream_acquisition_groups"])
    data["upstream_search_count_scope"]="One upstream group with 1191 registered opportunities; actual calls exclude presearch failures. Per-stream repeated acquisition counts identify lineage and must not be added again."
    text=json.dumps(data,indent=2,ensure_ascii=False,allow_nan=False).replace(str(a.scratch),"<CARRIER_SCRATCH>").replace(str(a.code),"<CODE_ROOT>")
    with (a.output/(PREFIX+"SUMMARY.json")).open("x") as f:f.write(text+"\n")
    def metric(name,case=CASES[3]):return next(v for v in rows if v["trial"]==name and v["case"]==case and v["domain"]=="full_66_340")
    def count(name,case=CASES[3]):return next(v for v in counts if v["trial"]==name and v["case"]==case)
    desc={"DENSE_SELECTED_TRACKING":"RAWX 5 Hz 机会；native kernel；不计搜索延迟",
          "DENSE_SELECTED_SERIAL":"RAWX 5 Hz 机会；native kernel；计自身记录搜索耗时"}
    lines=["# RAWX 频率重新获取：十一版本导航比较","",
      "本轮新增两变体、8 次 native 与 8 次冻结离线评价。每个变体四个 native 全部封存并通过控制检查后才评价；此前九版本的 36 条链只读复用。十一版本、44 条链使用相同完整时间支持，不按载波成功时刻筛选。名义窗口 66–340 s，实际输出 66.005054–339.997056 s；结束时刻由输入清单的最后 IMU 样本确定。",
      "",
      "DENSE_SELECTED 在原 1200 个 RAWX 历元上登记 1191 个重叠两秒窗，每窗仍为五个选择和五个未来验证历元，只将机会间隔从 2 s 改为 0.2 s。采用预选观测似然及已核对的 native 球面内核，cap 6/min 4、观测协方差、门限和导航链固定。此处列出的当前开发变体 DENSE_SELECTED_SERIAL 表示本轮含耗时的登记变体，不按评价指标选优，也不表示生产固定验收。",
      "",
      "| 主对照/变体 | 含义 | H RMSE (m) | V RMSE (m) | yaw RMSE (deg) | 最大绝对 yaw (deg) | valid | native 接纳 |",
      "|---|---|---:|---:|---:|---:|---:|---:|"]
    pvt=metric(current,CASES[1]);pc=count(current,CASES[1])
    lines.append(f"| C1 双位置向量 | 所有新变体共同、字节一致 | {float(pvt['H_RMSE_m']):.6f} | {float(pvt['V_RMSE_m']):.6f} | {float(pvt['yaw_RMSE_deg']):.6f} | {float(pvt['yaw_max_abs_deg']):.6f} | NA | {pc['native_vector_accepts']} |")
    for name in ("SELECTED_LIKELIHOOD_TRACKING","SELECTED_LIKELIHOOD_SERIAL",*NEW):
        v=metric(name);c=count(name)
        label=desc.get(name,"原 2 s 机会；Python；"+("计自身记录搜索耗时" if name.endswith("_SERIAL") else "不计搜索延迟"))
        lines.append(f"| {name} / C3 | {label} | {float(v['H_RMSE_m']):.6f} | {float(v['V_RMSE_m']):.6f} | {float(v['yaw_RMSE_deg']):.6f} | {float(v['yaw_max_abs_deg']):.6f} | {c['carrier_provider_valid_epochs']} | {c['native_vector_accepts']} |")
    serial=upstream[current]
    dense=read(a.scratch/"DENSE_SELECTED_FRONTEND/SUMMARY_0001.json")
    lines+=["",
      f"前端登记 1191 个窗口，实际 C-ILS 调用 {dense['new_search_calls']} 次；tracking 与 serial 复用同一批候选，不再搜索。本导航控制器新增 C-ILS 为 0。串行调度动作：{json.dumps(serial['service_actions'],ensure_ascii=False)}；到达处理：{json.dumps(serial['arrival_actions'],ensure_ascii=False)}；窗口结束仍等待 {len(serial['pending_at_end'])} 个结果。显式无 C-ILS 的选择前不可用与真正搜索启动分别计数，忙时仍按原规则丢弃。",
      "",
      "两新变体的 C0/C1/C2 NAV 与 STD 均和 PARTIAL6 对应控制字节一致。RESULTS 保留十一版本四臂三域（132 行）；RUN_COUNTS 保留 44 条链；DIFFERENCES 保留当前含耗时变体对其余十版本的三域差值（120 行）；NEW_C3_CONTRASTS 列出两新 C3 对原 selected-likelihood tracking、serial 和同变体 C1 的比较（18 行）。",
      "",
      "SERIAL 使用本次每窗自身记录的证书耗时；无证书失败采用保存的正调用耗时，显式选择前失败记零 C-ILS 工作。单 worker busy-drop/noqueue，晚到结果逐历史历元追赶且只输出当前测量。TRACKING 不计搜索延迟。准备、验证、GLRT、追赶、tracking、IO、导航和资源争用成本仍计零，SERIAL 也不是硬件实时验证。原两秒机会使用 Python 内核，本轮使用已核对的 native 内核；串行差异不能全部归因为机会密度。",
      "",
      "导航二进制、body HV、P/RV/RD/RP、初始化、评价器和噪声门固定。没有按参考误差筛选观测、选择候选或调整参数；参考是 Fixposition 派生结果，非独立真值。重叠窗口和连续历元共享原始观测与整数，不能把更多测试、认证或更新当成等数量独立正确固定或校准的全程错固定风险。"]
    with (a.output/(PREFIX+"READOUT.md")).open("x") as f:f.write("\n".join(lines)+"\n")
    audit={"status":"PASS","scope":"Saved navigation outputs, full time support, exact controls, invocation order and source/input pins; no new CILS or independent reference truth.",
        "controller_sha256":sha(a.controller/"driver.py"),"controller_registration_sha256":sha(a.controller/"REGISTRATION.json"),
        "upstream_complete_receipt_sha256":sha(a.controller/"UPSTREAM_COMPLETE_RECEIPT.json"),
        "new_native_calls":8,"new_evaluator_calls":8,"reused_navigation":36,"versions":11,"chains":44,
        "control_byte_identity":controls,"phase_ledger":phases,
        "upstream_checks":{k:read(a.controller/k/"FRONTEND_READY.json") for k in NEW}}
    public=json.dumps(audit,indent=2,ensure_ascii=False,allow_nan=False).replace(str(a.scratch),"<CARRIER_SCRATCH>").replace(str(a.code),"<CODE_ROOT>")
    with (a.output/(PREFIX+"AUDIT.json")).open("x") as f:f.write(public+"\n")
    outputs=sorted(a.output.glob(PREFIX+"*"))
    for p in outputs:
        assert "/home/kaiwen" not in p.read_text() and "/mnt/g/" not in p.read_text()
    emit(a.controller/"FINAL_PUBLIC_REPORTS_SEALED.json",{"status":"SEALED","files":{p.name:sha(p) for p in outputs},"new_native":8,"new_evaluator":8,"reused_navigation":36})
    print(json.dumps({"status":"PASS","versions":11,"chains":44,"new_native":8,"new_evaluator":8,"metrics":132,"default_current":current}))
if __name__=="__main__":main()
