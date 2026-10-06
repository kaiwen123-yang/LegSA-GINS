#!/usr/bin/env python3
"""Compare sealed trials without solving, evaluating, or reading reference payload."""
from pathlib import Path
import argparse,csv,hashlib,json
import numpy as np
import pandas as pd
import yaml

CASES=("C0_SCALAR","C1_DUAL_PVT_VECTOR","C2_FULL_CARRIER_VECTOR","C3_PARTIAL_CARRIER_VECTOR")
DOMAINS={"full_66_340","before_carrier_66_100","carrier_scope_100_340"}
METRICS=("H_RMSE_m","V_RMSE_m","D3_RMSE_m","yaw_RMSE_deg")
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read(path):return json.loads(Path(path).read_text())
def write_csv(path,rows):
 with path.open("w",newline="") as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator="\n");w.writeheader();w.writerows(rows)
def main():
 ap=argparse.ArgumentParser()
 ap.add_argument("--trial",nargs=2,action="append",metavar=("LABEL","PATH"),required=True)
 ap.add_argument("--new",required=True);ap.add_argument("--baseline",required=True)
 ap.add_argument("--expect-identical-controls",nargs="*",default=[],choices=CASES)
 ap.add_argument("--producer-summary",type=Path)
 ap.add_argument("--require-zero-carrier",nargs="*",default=[],choices=CASES)
 ap.add_argument("--output",type=Path,required=True)
 ap.add_argument("--prefix",default="")
 a=ap.parse_args()
 if "/" in a.prefix or "\\" in a.prefix:raise ValueError("PREFIX_MUST_BE_A_FILENAME_PREFIX")
 trials={label:Path(path) for label,path in a.trial}
 if len(trials)!=len(a.trial) or len(trials)<2 or a.new not in trials or a.baseline not in trials or a.new==a.baseline:
  raise ValueError("UNIQUE_TRIAL_LABELS_NEW_AND_BASELINE_REQUIRED")
 a.output.mkdir(parents=True,exist_ok=True)
 metrics=[];counts=[];receipts=[];identities={};plans={};seals={};all_native=set();all_match=set()
 for label,stage in trials.items():
  plan=read(stage/"PLAN.json");seal=read(stage/"ALL_NATIVE_SEALED.json");eval_seal=read(stage/"EVALUATION_COMPLETE.json")
  plans[label]=plan
  if seal["status"]!="SEALED" or len(seal["records"])!=4 or seal["solver_calls"]!=4 or eval_seal["evaluator_calls"]!=4:
   raise ValueError("FOUR_COMPLETE_SEALED_ARMS_REQUIRED")
  assert seal["plan_sha256"]==eval_seal["plan_sha256"]==sha(stage/"PLAN.json")
  assert eval_seal["native_seal_sha256"]==sha(stage/"ALL_NATIVE_SEALED.json")
  for block in [seal,eval_seal]:
   for rel,digest in block["files"].items():assert sha(stage/rel)==digest
  seals[label]={f:sha(stage/f) for f in ["PLAN.json","ALL_NATIVE_SEALED.json","EVALUATION_COMPLETE.json","NAVIGATION_RESULTS.csv"]}
  data=pd.read_csv(stage/"NAVIGATION_RESULTS.csv")
  assert len(data)==12 and set(data.case)==set(CASES) and set(data.domain)==DOMAINS
  assert len(data[["case","domain"]].drop_duplicates())==12
  for row in data.to_dict("records"):metrics.append({"trial":label,**row})
  for rec in seal["records"]:
   case=rec["case"];native=stage/"NATIVE"/case
   manifest=read(native/"RUN_MANIFEST.json")
   nav=np.loadtxt(native/"KF_GINS_Navresult.nav",comments="%",ndmin=2)
   std=np.loadtxt(native/"KF_GINS_STD.txt",comments="%",ndmin=2)
   assert np.array_equal(nav[:,1],std[:,0])
   native_time=hashlib.sha256(nav[:,1].copy().tobytes()).hexdigest()
   assert native_time==rec["time_keys_sha256"]
   ev=stage/"EVALUATION"/case
   error_times=pd.read_csv(ev/"FROZEN_EVALUATOR/error_series.csv",usecols=["time"]).time.to_numpy()
   matched_time=hashlib.sha256(error_times.copy().tobytes()).hexdigest()
   info=read(ev/"EVALUATOR_RESULT.json")
   assert info["audit"]["passed"] and info["audit"]["trace_open_count"]==1
   assert rec["online_reference_opens"]==0 and rec["forbidden_legacy_velocity_opens"]==0
   assert rec["body_velocity_events"]["causal_and_unique_source_timestamps"]
   assert plan["hv_mode"]=="body" and manifest["go2_horizontal_velocity_frame"]=="body_frd"
   all_native.add(native_time);all_match.add(matched_time)
   identities[label,case]={k:rec[k]["sha256"] for k in ("nav","std")}
   declared=plan["external_carrier_gates"].get(case)
   diag_path=native/"BASELINE3D_DIAGNOSTICS.csv";accept=None;accepted_times=None
   if diag_path.exists():
    diag=pd.read_csv(diag_path);accepted_times=diag.loc[diag.accepted==1,"time"].to_list()
    accept=len(accepted_times);assert accept==manifest["baseline3d_accept_count"]
   counts.append({"trial":label,"case":case,"output_epochs":len(nav),"matched_epochs":len(error_times),
    "carrier_provider_rows":declared["rows"] if declared else None,
    "carrier_provider_valid_epochs":declared["valid_rows"] if declared else None,
    "native_vector_accepts":accept,
    "yaw_dispatch_not_vector_accepts":manifest["yaw_update_count"],
    "body_updates":manifest["go2_horizontal_velocity_update_count"],
    "RP_updates":manifest["go2_roll_pitch_update_count"],"RD_updates":manifest["raw_doppler_update_count"],
    "native_reference_reads":0,"offline_reference_reads":1,
    "native_time_sha256":native_time,"matched_time_sha256":matched_time})
   receipts.append({"trial":label,"case":case,"native_identity":identities[label,case],
    "run_manifest_sha256":sha(native/"RUN_MANIFEST.json"),
    "body_event_audit":rec["body_velocity_events"],
    "carrier_accepted_times_s":accepted_times if declared else None})
 assert len(all_native)==1 and len(all_match)==1
 # A changed source record is legitimate only for the carrier observations.
 reference=plans[a.baseline]
 for label,plan in plans.items():
  assert plan["binary"]["sha256"]==reference["binary"]["sha256"]
  assert plan["dual_pvt_input"]["sha256"]==reference["dual_pvt_input"]["sha256"]
  assert {k:v["sha256"] for k,v in plan["active_shared_inputs"].items()}=={k:v["sha256"] for k,v in reference["active_shared_inputs"].items()}
  excluded={"outputpath","go2_body_velocity_prior_path","baseline3d_path","external_carrier_baseline_path"}
  for row,base in zip(plan["runs"],reference["runs"]):
   assert row["case"]==base["case"]
   config=yaml.safe_load(Path(row["config"]["path"]).read_text())
   previous=yaml.safe_load(Path(base["config"]["path"]).read_text())
   assert {k:v for k,v in config.items() if k not in excluded}=={k:v for k,v in previous.items() if k not in excluded}
 for case in a.require_zero_carrier:
  matched=next(c for c in counts if c["trial"]==a.new and c["case"]==case)
  assert matched["carrier_provider_valid_epochs"]==0 and matched["native_vector_accepts"]==0
 exact={case:identities[a.new,case]==identities[a.baseline,case] for case in a.expect_identical_controls}
 if not all(exact.values()):raise ValueError("EXPECTED_IDENTICAL_NAV_STD_CONTROL_FAILED")
 deltas=[]
 for row in [r for r in metrics if r["trial"]==a.new]:
  for old_label in trials:
   if old_label==a.new:continue
   previous=next(r for r in metrics if r["trial"]==old_label and r["case"]==row["case"] and r["domain"]==row["domain"])
   assert previous["epochs"]==row["epochs"] and previous["first_time"]==row["first_time"] and previous["last_time"]==row["last_time"]
   delta={"new_trial":a.new,"comparison_trial":old_label,"case":row["case"],"domain":row["domain"],"epochs":row["epochs"]}
   for metric in METRICS:
    delta[metric+"_new"]=row[metric];delta[metric+"_comparison"]=previous[metric]
    delta[metric+"_difference"]=row[metric]-previous[metric]
   deltas.append(delta)
 for filename,rows in [("RESULTS.csv",metrics),("RUN_COUNTS.csv",counts),("DIFFERENCES.csv",deltas)]:
  write_csv(a.output/(a.prefix+filename),rows)
 producer=None
 if a.producer_summary:
  producer={"sha256":sha(a.producer_summary),"source_filename":a.producer_summary.name,
            "source_top_level_fields":sorted(read(a.producer_summary))}
 result={"new_trial":a.new,"baseline":a.baseline,"trial_labels":list(trials),
  "new_native_calls":4,"new_evaluator_calls":4,"reused_navigation_runs_for_comparison":4*(len(trials)-1),
  "new_searches":0,"reference_payload_reads_by_this_script":0,
  "complete_output_hashes_verified":True,"all_trials_identical_native_STD_and_matched_time_support":True,
  "expected_control_NAV_STD_byte_identity":exact,"required_zero_carrier_cases":a.require_zero_carrier,
  "common_binary_PVT_and_auxiliary_input_hashes":True,"configs_equal_except_copied_input_output_paths":True,
  "integer_truth_available":False,"reference_is_independent_truth":False,
  "tracking_epochs_not_independent_integer_fixes":True,"seals":seals,"receipts":receipts,
  "run_counts":counts,"full_span_metrics":[r for r in metrics if r["domain"]=="full_66_340"],
  "new_trial_vs_previous_differences":deltas}
 if producer:
  # Keep the source receipt untouched. Only public transport paths are aliases.
  result["producer_receipt"]=producer
 text=json.dumps(result,indent=2,ensure_ascii=False,allow_nan=False)
 for path in sorted({str(p.parent) for p in trials.values()},key=len,reverse=True):text=text.replace(path,"<CARRIER_SCRATCH>")
 text=text.replace(str(Path(__file__).resolve().parents[3]),"<CODE_ROOT>")
 (a.output/(a.prefix+"SUMMARY.json")).write_text(text+"\n")
 lines=["# 连续跟踪导航完整比较","",
  "完整窗口 66–340 s，另保留原定 66–100 s 和 100–340 s 子域；没有只统计载波有效时刻。本轮新增 4 次 native 和封存后的 4 次离线评价；其余版本结果仅复用。",
  "",
  "| 版本 | 输入 | H RMSE (m) | V RMSE (m) | Yaw RMSE (deg) | valid 历元 | native 向量接受 |",
  "|---|---|---:|---:|---:|---:|---:|"]
 for row in [r for r in metrics if r["domain"]=="full_66_340"]:
  count=next(c for c in counts if c["trial"]==row["trial"] and c["case"]==row["case"])
  lines.append(f"| {row['trial']} | {row['case']} | {row['H_RMSE_m']:.6f} | {row['V_RMSE_m']:.6f} | {row['yaw_RMSE_deg']:.6f} | {count['carrier_provider_valid_epochs'] if count['carrier_provider_valid_epochs'] is not None else 'NA'} | {count['native_vector_accepts'] if count['native_vector_accepts'] is not None else 'NA（标量）'} |")
 partial_new=next(r for r in metrics if r["trial"]==a.new and r["case"]==CASES[3] and r["domain"]=="full_66_340")
 partial_old=next(r for r in metrics if r["trial"]==a.baseline and r["case"]==CASES[3] and r["domain"]=="full_66_340")
 pvt_new=next(r for r in metrics if r["trial"]==a.new and r["case"]==CASES[1] and r["domain"]=="full_66_340")
 pc=next(r for r in counts if r["trial"]==a.new and r["case"]==CASES[3])
 po=next(r for r in counts if r["trial"]==a.baseline and r["case"]==CASES[3])
 accepted=next(r for r in receipts if r["trial"]==a.new and r["case"]==CASES[3])["carrier_accepted_times_s"]
 longest_gap=float(max(np.diff([66.,*accepted,340.]))) if accepted else 274.
 relation=lambda new,old: "更低" if new<old else ("更高" if new>old else "相同")
 pvt_relation=("相对双位置向量对照，本轮载波的航向 RMSE "+
               relation(partial_new["yaw_RMSE_deg"],pvt_new["yaw_RMSE_deg"])+"，水平 RMSE "+
               relation(partial_new["H_RMSE_m"],pvt_new["H_RMSE_m"])+"。")
 lines+=["",
  f"本轮部分载波共有 {pc['carrier_provider_valid_epochs']} 个 valid 输入历元，native 接受 {pc['native_vector_accepts']} 次；{a.baseline} 对应为 {po['carrier_provider_valid_epochs']} 个 / {po['native_vector_accepts']} 次。全时段 yaw RMSE 由 {partial_old['yaw_RMSE_deg']:.6f}° 变为 {partial_new['yaw_RMSE_deg']:.6f}°，H 由 {partial_old['H_RMSE_m']:.6f} m 变为 {partial_new['H_RMSE_m']:.6f} m。双位置向量链仍为 yaw {pvt_new['yaw_RMSE_deg']:.6f}°、H {pvt_new['H_RMSE_m']:.6f} m，{pvt_relation}",
  "",
  f"增加更新没有消除长缺测：完整窗口中最长没有接受载波更新的间隔仍为 {longest_gap:.3f} s。精确接受时刻保留在 SUMMARY；这些历元来自共享整数和短时相邻观测，不能解释为同数量的独立正确固定或已校准完整性。这里报告的是固定输入/门限下的本次点估计，不额外挑选成功区间或调整参数。",
  "",
  "控制 NAV/STD 字节一致性："+", ".join(f"{k}=PASS" for k in exact)+"。",
  "",
  "各版本共享二进制、PVT与辅助输入的 hash；全部链原始/STD/评价时间键相同。RUN_COUNTS 分开列 valid 历元、native 接受及 body/RP/RD 更新数；DIFFERENCES 给出本轮相对每个旧版本的三域差值。密集跟踪使用共享整数，历元数量不能当作独立成功固定次数或校准的错误固定概率。",
  "",
  "参考为 Fixposition 派生结果，非独立真值；整数没有真实标签。初始条件非 AR 冷启动，参数没有按本轮结果调整；墙钟搜索延迟未注入导航状态时间。"]
 (a.output/(a.prefix+"READOUT.md")).write_text("\n".join(lines)+"\n")
 print(json.dumps({"status":"PASS","new":a.new,"metric_rows":len(metrics),"delta_rows":len(deltas),"controls":exact}))
if __name__=="__main__":main()
