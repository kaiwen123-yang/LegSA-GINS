#!/usr/bin/env python3
"""Saved-output-only V1/V2 comparison on identical full navigation supports."""
import argparse,csv,hashlib,json
from pathlib import Path
import numpy as np
import pandas as pd
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text())
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--scratch',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);a=ap.parse_args()
 driver=a.scratch/'NAVIGATION_DRIVER_V2'
 done=read(driver/'COMPLETE.json');assert done['status']=='COMPLETE'
 exact=read(driver/'V1_V2_CONTROLS_EXACT.json');assert exact['C0_C1_NAV_STD_byte_identical']
 front=a.scratch/'FRONTEND_V2_PILOT';pilot=read(front/'SUMMARY_0001.json');complete=read(front/'SUMMARY_0002.json')
 assert pilot['new_search_calls']==20 and complete['new_search_calls']==220 and complete['reused_cases']==20
 assert all(complete['modes'][m]['cases']==120 for m in ['full','partial'])
 frontend={'unique_CILS_calls':240,'pilot_calls':20,'later_new_calls':220,'later_reused_cases':20,
  'modes':{m:{k:v for k,v in complete['modes'][m].items() if k!='csv'} for m in ['full','partial']},
  'model_unavailable_status_cases':sum(n for m in complete['modes'].values() for k,n in m['statuses'].items() if 'MODEL_UNAVAILABLE' in k),
  'pilot_summary_sha256':sha(front/'SUMMARY_0001.json'),'complete_summary_sha256':sha(front/'SUMMARY_0002.json'),
  'execution_commit_pilot':pilot['execution_commit'],'execution_commit_completion':complete['execution_commit'],
  'same_source_files_in_both_contracts':pilot['input_contract']['source_files']==complete['input_contract']['source_files']}
 assert frontend['same_source_files_in_both_contracts']
 tables=[];counts=[];seals={};keys=[];receipts=[]
 for version,folder in [('V1','NAVIGATION_BODY_HV_01'),('V2','NAVIGATION_BODY_HV_V2')]:
  stage=a.scratch/folder;plan=read(stage/'PLAN.json');seal=read(stage/'ALL_NATIVE_SEALED.json');evseal=read(stage/'EVALUATION_COMPLETE.json')
  assert seal['status']=='SEALED' and len(seal['records'])==4
  assert seal['plan_sha256']==evseal['plan_sha256']==sha(stage/'PLAN.json')
  assert evseal['native_seal_sha256']==sha(stage/'ALL_NATIVE_SEALED.json')
  for block in [seal,evseal]:
   for rel,value in block['files'].items():assert sha(stage/rel)==value
  seals[folder]={k:sha(stage/k) for k in ['PLAN.json','ALL_NATIVE_SEALED.json','EVALUATION_COMPLETE.json','NAVIGATION_RESULTS.csv']}
  frame=pd.read_csv(stage/'NAVIGATION_RESULTS.csv');assert len(frame)==12
  for row in frame.to_dict('records'):tables.append({'version':version,**row})
  for rec in seal['records']:
   case=rec['case'];path=stage/'NATIVE'/case;manifest=read(path/'RUN_MANIFEST.json')
   nav=np.loadtxt(path/'KF_GINS_Navresult.nav',comments='%',ndmin=2)
   std=np.loadtxt(path/'KF_GINS_STD.txt',comments='%',ndmin=2)
   assert np.array_equal(nav[:,1],std[:,0])
   errdir=stage/'EVALUATION'/case/'FROZEN_EVALUATOR'
   t=pd.read_csv(errdir/'error_series.csv',usecols=['time']).time.to_numpy()
   keys.append(hashlib.sha256(t.copy().tobytes()).hexdigest())
   ev=read(stage/'EVALUATION'/case/'EVALUATOR_RESULT.json')
   assert ev['audit']['trace_open_count']==1 and ev['audit']['passed'] and rec['online_reference_opens']==0
   assert rec['forbidden_legacy_velocity_opens']==0 and rec['body_velocity_events']['causal_and_unique_source_timestamps']
   bp=path/'BASELINE3D_DIAGNOSTICS.csv';times=[]
   if bp.exists():
    b=pd.read_csv(bp);times=b.loc[b.accepted==1,'time'].to_list()
    assert len(times)==manifest['baseline3d_accept_count']
   declared=plan['external_carrier_gates'].get(case)
   counts.append({'version':version,'case':case,'epochs':rec['output_rows'],
      'carrier_candidates':declared['valid_rows'] if declared else None,
      'vector_accepted':len(times) if bp.exists() else None,
      'yaw_dispatch_not_vector_accept':manifest['yaw_update_count'],
      'body_velocity_updates':manifest['go2_horizontal_velocity_update_count'],
      'RP_updates':manifest['go2_roll_pitch_update_count'],'RD_updates':manifest['raw_doppler_update_count'],
      'native_reference_reads':0,'offline_reference_reads':1,
      'native_time_key_sha256':rec['time_keys_sha256'],'matched_time_key_sha256':keys[-1]})
   receipts.append({'version':version,'case':case,
      'carrier_accepted_times_s':times if declared else None,
      'nav_sha256':rec['nav']['sha256'],'std_sha256':rec['std']['sha256'],
      'run_manifest_sha256':sha(path/'RUN_MANIFEST.json'),
      'body_event_audit':rec['body_velocity_events']})
 assert len(set(keys))==1 and len({x['native_time_key_sha256'] for x in counts})==1
 changes=[]
 for row in [r for r in tables if r['version']=='V2']:
  old=next(r for r in tables if r['version']=='V1' and r['case']==row['case'] and r['domain']==row['domain'])
  c={'case':row['case'],'domain':row['domain'],'epochs':row['epochs']}
  for key in ['H_RMSE_m','V_RMSE_m','D3_RMSE_m','yaw_RMSE_deg']:
   c[key+'_V1']=old[key];c[key+'_V2']=row[key];c[key+'_V2_minus_V1']=row[key]-old[key]
  changes.append(c)
 for name,rows in [('NAVIGATION_V2_RESULTS.csv',tables),('NAVIGATION_V2_RUN_COUNTS.csv',counts),('NAVIGATION_V2_CHANGE.csv',changes)]:
  with (a.output/name).open('w',newline='') as f:
   writer=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator='\n');writer.writeheader();writer.writerows(rows)
 summary={'new_native_calls':4,'new_evaluator_calls':4,'V1_reused_for_comparison_only':4,
  'new_search_calls_by_navigation':0,'frontend_v2':frontend,'all_four_native_before_any_V2_reference_reads':True,
  'V2_native_reference_reads':0,'V2_offline_reference_reads':4,'all_hashes_verified':True,
  'all_eight_same_nav_std_and_matched_time_support':True,'C0_C1_NAV_STD_byte_identical_to_V1':True,
  'integer_truth_available':False,'reference_is_independent_truth':False,
  'comparison_is_complete_V2_lifecycle_not_single_factor_ablation':True,
  'seals':seals,'counts':counts,'receipts':receipts,'changes':changes}
 (a.output/'NAVIGATION_V2_SUMMARY.json').write_text(json.dumps(summary,indent=2,ensure_ascii=False,allow_nan=False)+'\n')
 lines=['# V2 完整 body 速度导航比较','',
 '本轮新增 4 次 native 和 4 次冻结离线评价，上一轮 V1 四条 body 导航仅复用比较。窗口仍为 66–340 s；全部四条 native 封存后才读取参考。','',
 'V1/V2 二进制与 IMU/P/RV/RD/RP/body 速度/PVT 侧车内容一致，C0/C1 的 NAV/STD 逐字节相同，排除了非载波链的意外改变。全部八条 NAV、STD 和评价匹配时间键一致；完整输出各 56,642 个历元。','',
 '| 输入 | 版本 | H RMSE (m) | V RMSE (m) | Yaw RMSE (deg) | 工程载波候选数 | native向量接受数 |',
 '|---|---|---:|---:|---:|---:|---:|']
 for row in [r for r in tables if r['domain']=='full_66_340']:
  c=next(c for c in counts if c['version']==row['version'] and c['case']==row['case'])
  lines.append(f"| {row['case']} | {row['version']} | {row['H_RMSE_m']:.6f} | {row['V_RMSE_m']:.6f} | {row['yaw_RMSE_deg']:.6f} | {c['carrier_candidates'] if c['carrier_candidates'] is not None else 'NA'} | {c['vector_accepted'] if c['vector_accepted'] is not None else 'NA（标量）'} |")
 lines+=['',
 'V2 前端全量为 0/120 条工程合格，部分为 6/120 条；完整 240 次原始搜索由先期 20 次和本次新增 220 次组成，后段复用先期 20 个结果而非再搜索。全量终态为：104 次活动弧改变、9 次残差拒绝、5 次残差与长度共同拒绝、2 次相位 GLRT 拒绝。部分终态为：60 次活动弧改变、22 次 GLRT 拒绝、17 次残差拒绝、7 次长度拒绝、5 次搜索未获所需证书、3 次残差与长度共同拒绝、6 条候选；模型缺失终态为 0。',
 '',
 'V2 两份前端汇总绑定的 source_snapshot 相同；后段执行提交 12487e2 仅对应文档推进，未改变在途科学输入合同。可用模型增多不等于更可靠的整数或更多已知正确 FIX。',
 '',
 '全时段结果没有改善：全量载波 yaw RMSE 为 2.756924°（V1 2.748727°），部分为 2.557707°（V1 2.479564°）；部分的 H RMSE 为 0.102334 m（V1 0.102216 m）。C0/C1 分别仍为 1.712163°/1.620834°。V2 全量 0 次、部分 4 次实际向量更新；V1 分别为 1 次/5 次。载波两链仍未超越双位置航向，不能把前端模型可用率改进直接写成导航收益。',
 '',
 '完整 CSV 保留全部 66–340、66–100、100–340 三域的 H/V/3D/yaw RMSE 与最大绝对误差，不仅统计载波被接受时刻。新增 CHANGE CSV 列明每域 V2−V1；RUN_COUNTS 分开列候选数、向量实际接受、body/RP/RD 更新，不能把 yaw 调度计数当载波接受。','',
 'V2 更新的是既定因果 NAV 前缀、SPP anchor 生命周期与 pivot 可用性处理后的完整输入链；不是仅改变一个部分模糊度参数的消融。共同初始化仍非 AR 冷启动；1.5°下限、body sigma=0.2 m/s/scale=1、原门限均未改变。','',
 '工程候选与 native 接受均不是已知正确整数；参考来自 Fixposition，非独立真值。轨迹评价仍为因果数据支持的离线回放，未模拟 CILS 墙钟计算延迟。']
 (a.output/'NAVIGATION_V2_READOUT.md').write_text('\n'.join(lines)+'\n')
 for c in [x for x in changes if x['domain']=='full_66_340']:
  print(c['case'],'H',c['H_RMSE_m_V2'],'yaw',c['yaw_RMSE_deg_V2'],'delta_yaw',c['yaw_RMSE_deg_V2_minus_V1'])
 print('PASS 4 new native / 4 new eval / 24 comparison rows')
if __name__=='__main__':main()
