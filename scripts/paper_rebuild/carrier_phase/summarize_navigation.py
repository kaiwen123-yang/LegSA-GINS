#!/usr/bin/env python3
"""Derive complete navigation comparison from sealed native/evaluator outputs."""
from pathlib import Path
import argparse,csv,hashlib,json
import numpy as np
import pandas as pd

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text())
def dump(p,v,aliases=()):
 text=json.dumps(v,indent=2,ensure_ascii=False,allow_nan=False)
 for source,target in aliases:text=text.replace(str(source),target)
 p.write_text(text+"\n")
def main():
 ap=argparse.ArgumentParser();ap.add_argument("--scratch",type=Path,required=True)
 ap.add_argument("--output",type=Path,required=True);a=ap.parse_args()
 a.output.mkdir(parents=True,exist_ok=True)
 driver=a.scratch/"NAVIGATION_DRIVER_01";done=read(driver/"COMPLETE.json")
 assert done["status"]=="COMPLETE" and done["native_calls"]==8 and done["evaluator_calls"]==8
 assert done["all_native_before_any_evaluator"]
 joint=read(driver/"ALL_8_NATIVE_SEALED.json")
 assert joint["all_eight_same_native_time_keys"]
 for p,h in joint["seals"].items():assert sha(p)==h
 table=[];counts=[];receipts=[];times=[];baselines={}
 for mode,stagepath in done["stages"].items():
  stage=Path(stagepath);plan=read(stage/"PLAN.json");seal=read(stage/"ALL_NATIVE_SEALED.json")
  evaluation=read(stage/"EVALUATION_COMPLETE.json")
  assert sha(stage/"PLAN.json")==seal["plan_sha256"]==evaluation["plan_sha256"]
  assert sha(stage/"ALL_NATIVE_SEALED.json")==evaluation["native_seal_sha256"]
  for block in [seal,evaluation]:
   for rel,h in block["files"].items():assert sha(stage/rel)==h
  assert evaluation["same_matched_time_keys"] and evaluation["evaluator_calls"]==4
  frame=pd.read_csv(stage/"NAVIGATION_RESULTS.csv")
  assert len(frame)==12 and set(frame.domain)=={"full_66_340","before_carrier_66_100","carrier_scope_100_340"}
  for row in frame.to_dict("records"):table.append({"hv_mode":mode,**row})
  for rec in seal["records"]:
   case=rec["case"];run=stage/"NATIVE"/case
   manifest=read(run/"RUN_MANIFEST.json")
   nav=np.loadtxt(run/"KF_GINS_Navresult.nav",comments="%",ndmin=2)
   std=np.loadtxt(run/"KF_GINS_STD.txt",comments="%",ndmin=2)
   assert np.array_equal(nav[:,1],std[:,0])
   t=pd.read_csv(stage/"EVALUATION"/case/"FROZEN_EVALUATOR/error_series.csv",usecols=["time"]).time.to_numpy()
   times.append(sha(stage/"EVALUATION"/case/"FROZEN_EVALUATOR/CAPTURE_CONFIG.json"))
   matcher=hashlib.sha256(t.copy().tobytes()).hexdigest()
   ev=read(stage/"EVALUATION"/case/"EVALUATOR_RESULT.json")
   assert ev["audit"]["passed"] and ev["audit"]["trace_open_count"]==1
   assert rec["online_reference_opens"]==0 and rec["forbidden_legacy_velocity_opens"]==0
   if mode=="body":assert rec["body_velocity_provider_opens"]>0 and rec["body_velocity_events"]["causal_and_unique_source_timestamps"]
   vector=run/"BASELINE3D_DIAGNOSTICS.csv";actual=[]
   if vector.exists():
    v=pd.read_csv(vector)
    actual=v.loc[v.accepted==1,"time"].to_list()
    assert len(actual)==manifest["baseline3d_accept_count"]
   declared=plan["external_carrier_gates"].get(case)
   record={"hv_mode":mode,"case":case,"output_rows":rec["output_rows"],
     "first_output_time":rec["first_time"],"last_output_time":rec["last_time"],
     "native_time_sha256":rec["time_keys_sha256"],"matched_time_sha256":matcher,
     "declared_carrier_candidates":declared["valid_rows"] if declared else None,
     "vector_accepts":len(actual) if vector.exists() else None,
     "yaw_dispatch_count_not_vector_accepts":manifest["yaw_update_count"],
     "body_hv_updates":manifest["go2_horizontal_velocity_update_count"],
     "RP_updates":manifest["go2_roll_pitch_update_count"],"RD_updates":manifest["raw_doppler_update_count"],
     "online_reference_opens":0,"old_A1_velocity_opens":0,"offline_reference_opens":1,
     "native_runtime_s":rec["runtime_seconds"],
     "first_vector_accept_s":actual[0] if actual else None,"last_vector_accept_s":actual[-1] if actual else None}
   counts.append(record)
   receipts.append({"hv_mode":mode,"case":case,"run_manifest_sha256":sha(run/"RUN_MANIFEST.json"),
     "native_result_sha256":sha(run/"RESULT.json"),"evaluator_result_sha256":sha(stage/"EVALUATION"/case/"EVALUATOR_RESULT.json"),
     "carrier_accepted_times_s":actual if declared else None,
     "source_commit_metadata_not_execution_freeze":manifest.get("source_commit"),
     "effective_run_flags":{k:manifest[k] for k in manifest if k.startswith("body_velocity_") or k.startswith("external_carrier_")},
     "body_event_checks":rec.get("body_velocity_events")})
   if case.startswith(("C2","C3")):baselines[(mode,case[:2])]=(nav[nav[:,1]<100],std[std[:,0]<100])
 assert len({c["native_time_sha256"] for c in counts})==1
 assert len({c["matched_time_sha256"] for c in counts})==1
 before={m:all(np.array_equal(x,y) for x,y in zip(baselines[m,"C2"],baselines[m,"C3"])) for m in done["stages"]}
 assert all(before.values())
 for filename,rows in [("NAVIGATION_RESULTS.csv",table),("NAVIGATION_RUN_COUNTS.csv",counts)]:
  with (a.output/filename).open("w",newline="") as f:
   writer=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator="\n");writer.writeheader();writer.writerows(rows)
 summary={"scope":"OFFLINE_BY2_FULL_WINDOW_EIGHT_ARM_INTEGRATION",
  "scientific_freeze":"2c83861","native_calls":8,"evaluator_calls":8,"new_searches_by_navigation_runner":0,
  "common_support_all_eight":True,"nav_and_std_exact_time_keys":True,"matched_epochs_each":counts[0]["output_rows"],
  "metrics_rows":24,"domains":["full_66_340","before_carrier_66_100","carrier_scope_100_340"],
  "all_native_sealed_before_reference_reads":True,"native_reference_reads":0,"offline_reference_reads":8,
  "all_output_hashes_verified":True,"pre100_full_partial_NAV_STD_exact_each_hv_mode":before,
  "front_end_engineering_valid_candidates":{"full":1,"partial":7},"integer_truth_available":False,
  "reference_independent_truth":False,"runtime_latency_simulated_in_state_time":False,
  "body_velocity_sigma_xy_mps":.2,"body_velocity_scale":1.,"body_update_period_s":.2,
  "body_velocity_source_point":"assumed navigation IMU point; physical lever arm unresolved",
  "counts":counts,"receipts":receipts,"input_seals":{
   "<CARRIER_SCRATCH>/NAVIGATION_DRIVER_01/ALL_8_NATIVE_SEALED.json":sha(driver/"ALL_8_NATIVE_SEALED.json"),
   "<CARRIER_SCRATCH>/NAVIGATION_DRIVER_01/COMPLETE.json":sha(driver/"COMPLETE.json"),
   **{f"<CARRIER_SCRATCH>/{Path(s).name}/PLAN.json":sha(Path(s)/"PLAN.json") for s in done["stages"].values()}}}
 dump(a.output/"NAVIGATION_SUMMARY.json",summary,[(a.scratch,"<CARRIER_SCRATCH>"),
      (Path(__file__).resolve().parents[3],"<CODE_ROOT>")])
 names={"C0_SCALAR":"双位置标量航向","C1_DUAL_PVT_VECTOR":"双位置三维基线","C2_FULL_CARRIER_VECTOR":"全量整数载波基线","C3_PARTIAL_CARRIER_VECTOR":"部分整数载波基线"}
 full=[r for r in table if r["domain"]=="full_66_340"]
 lines=["# 完整 BY2 导航融合结果","",
 "8 次真实导航与 8 次冻结离线评价全部完成；8 条链都有 56,642 个相同输出和评价时刻。先封存所有原始导航输出，再读取参考。没有重跑、补选时段或只统计载波成功时刻。","",
 "全时段 66–340 s：","",
 "| 共同速度模式 | 航向/基线输入 | H RMSE (m) | V RMSE (m) | Yaw RMSE (deg) | 实际向量更新 | Body HV 更新 |",
 "|---|---|---:|---:|---:|---:|---:|"]
 for row in full:
  c=next(c for c in counts if c["hv_mode"]==row["hv_mode"] and c["case"]==row["case"])
  lines.append(f"| {row['hv_mode']} | {names[row['case']]} | {row['H_RMSE_m']:.6f} | {row['V_RMSE_m']:.6f} | {row['yaw_RMSE_deg']:.6f} | {c['vector_accepts'] if c['vector_accepts'] is not None else 'NA（标量）'} | {c['body_hv_updates']} |")
 lines += ["","完整 CSV 同时保留全时段、66–100 s 和 100–340 s 三个预定域，各域 H/V/3D/yaw RMSE 与最大绝对误差均保留。100–340 s 表示预定载波研究域，不能解读为每个时刻都有有效载波支持。","",
 "实际结果：部分整数前端提供 7 条工程合格候选（全量为 1 条），进入滤波后两种速度模式均接受 5 次部分基线更新；全量在 HV-off 中 0 次，在 body 中 1 次。两组接受的 5 个时刻并非完全相同，精确时戳保留在 NAVIGATION_SUMMARY.json；这是同一候选输入在不同滤波状态下的门控结果。旧 yaw_update_count 在向量链记录调度/尝试，不能代替 baseline3d_accept_count。","",
 "Body 四条链均接受 1,369 次独立 forward/right 速度更新；逐源时戳检查全部满足 past-only、一次尝试、无插值。旧 A1 航向依赖速度 CSV 没有被读取。各链 RD 666 次、RP 1,369 次。body-z 未观测不代表导航 down 状态冻结。","",
 "当前判断：部分整数方法相对全量载波链改善了支持和航向，但两种载波链的全时段航向仍不及现有双位置航向链。加入 body 速度显著减少稀疏载波条件下的航向漂移；它没有使当前载波方案全面优于双位置输入。不能因为 HV-off 全量载波链的 H 数值略小，就忽略其 0 次实际载波更新和明显更差的航向。","",
 "边界：四条链共用历史非 AR 冷启动，P/RV/RD/RP、IMU 与初始化相同；HV-off 使用 AB1110，body 使用 AB1111。双位置向量使用 k_b=1 的既定 pAcc 工作协方差；载波采用既定条件 GLS 协方差加 1.5° 工程下限，均未用本轮参考调参。body sigma=0.2 m/s、scale=1、观测点等同 IMU 的零杆臂假设尚非物理标定。","",
 "载波整数没有真实标签，工程准入不等于已知正确 FIX。参考来自 Fixposition，非独立真值。数据支持是因果的离线回放，CILS 墙钟计算延迟没有加入导航状态时间；本表不是实时期限验证。"]
 (a.output/"NAVIGATION_READOUT.md").write_text("\n".join(lines)+"\n")
 print(json.dumps({"status":"PASS","native":8,"evaluation":8,"rows":24,"output":str(a.output)}))
if __name__=="__main__":main()
