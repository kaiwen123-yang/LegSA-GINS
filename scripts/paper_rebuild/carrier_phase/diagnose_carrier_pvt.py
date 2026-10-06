#!/usr/bin/env python3
"""Seven sealed carrier/PVT observation comparisons; neither observation is truth."""
from pathlib import Path
import argparse,bisect,csv,hashlib,json,math
import numpy as np

def load(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def csvread(p):return list(csv.DictReader(p.open()))
def rotation(lat,lon):
 sl,cl,so,co=np.sin(lat),np.cos(lat),np.sin(lon),np.cos(lon)
 return np.array([[-sl*co,-sl*so,cl],[-so,co,0],[-cl*co,-cl*so,-sl]])
def compare(car,pvt,R):
 def angle(a,b):return float(np.rad2deg(np.arctan2(np.linalg.norm(np.cross(a,b)),a@b)))
 c,p=R@car,R@pvt
 cb,pb=float(np.rad2deg(np.arctan2(c[1],c[0]))),float(np.rad2deg(np.arctan2(p[1],p[0])))
 return {'angle_3d_deg':angle(car,pvt),'angle_3d_in_common_NED_deg':angle(c,p),
 'horizontal_baseline_azimuth_difference_deg':(cb-pb+180)%360-180,
 'carrier_baseline_azimuth_deg':cb,'pvt_baseline_azimuth_deg':pb,
 'carrier_horizontal_projection_m':float(np.linalg.norm(c[:2])),
 'pvt_horizontal_projection_m':float(np.linalg.norm(p[:2])),
 'carrier_baseline_inclination_deg':float(np.rad2deg(np.arctan2(-c[2],np.linalg.norm(c[:2])))),
 'pvt_baseline_inclination_deg':float(np.rad2deg(np.arctan2(-p[2],np.linalg.norm(p[:2])))),
 'vector_difference_m':float(np.linalg.norm(car-pvt))}
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--scratch',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);a=ap.parse_args()
 src=a.scratch/'FULL_SPAN_PARTIAL/CARRIER_PARTIAL_0001.csv'
 carriers=[x for x in csvread(src) if x['valid']=='1'];assert len(carriers)==7
 plan=load(a.scratch/'NAVIGATION_BODY_HV_01/PLAN.json')
 sidecar=a.scratch/'NAVIGATION_BODY_HV_01/INPUTS/DUAL_PVT_BASELINE3D.csv'
 pvt=csvread(sidecar);pt=[float(x['time']) for x in pvt]
 R=np.array(plan['dual_pvt_lineage']['ecef_to_fixed_ned'])
 assert np.max(np.abs(R@R.T-np.eye(3)))<1e-12 and np.linalg.det(R)>0
 arrays={};diags={};pvt_diags={}
 inputs={str(src.relative_to(a.scratch)):sha(src),str(sidecar.relative_to(a.scratch)):sha(sidecar),
   'NAVIGATION_BODY_HV_01/PLAN.json':sha(a.scratch/'NAVIGATION_BODY_HV_01/PLAN.json')}
 for mode,stage in [('off','NAVIGATION_HV_OFF_01'),('body','NAVIGATION_BODY_HV_01')]:
  folder=a.scratch/stage/'NATIVE/C3_PARTIAL_CARRIER_VECTOR'
  path=folder/'BASELINE3D_DIAGNOSTICS.csv';diags[mode]={float(x['time']):x for x in csvread(path) if x['valid']=='1'}
  arrays[mode]=np.loadtxt(folder/'KF_GINS_Navresult.nav',comments='%',ndmin=2)
  inputs[str(path.relative_to(a.scratch))]=sha(path)
  inputs[str((folder/'KF_GINS_Navresult.nav').relative_to(a.scratch))]=sha(folder/'KF_GINS_Navresult.nav')
  path=a.scratch/stage/'NATIVE/C1_DUAL_PVT_VECTOR/BASELINE3D_DIAGNOSTICS.csv'
  pvt_diags[mode]={float(x['time']):x for x in csvread(path) if x['valid']=='1'}
  inputs[str(path.relative_to(a.scratch))]=sha(path)
 results=[]
 for row in carriers:
  t=float(row['measurement_time']);start=round(t-1.998)
  casepath=a.scratch/'FULL_SPAN_PARTIAL/cases'/f'partial_{start:07.2f}.json'
  case=load(casepath);inputs[str(casepath.relative_to(a.scratch))]=sha(casepath)
  assert case['measurement']['valid'] and case['measurement']['measurement_time']==t
  car=np.array([float(row[k]) for k in ['b_ecef_x','b_ecef_y','b_ecef_z']])
  raw=np.array(case['admission']['epochs'][-1]['primary']['baseline_center_m'])
  cov=np.array(case['admission']['epochs'][-1]['primary']['baseline_covariance_m2'])
  reported=np.array(case['measurement']['covariance_ecef_m2'])
  floor=(.35*case['measurement']['angular_floor_rad'])**2
  assert np.allclose(reported,cov+floor*np.eye(3),rtol=1e-12,atol=1e-14)
  past=bisect.bisect_right(pt,t)-1;future=past+1
  assert pt[past]<=t<pt[future] and int(pvt[past]['valid'])==int(pvt[future]['valid'])==1
  rec={'measurement_time_s':t,'case_id':case['case_id'],'raw_conditional_GLS_length_m':float(np.linalg.norm(raw)),
   'published_length_constrained_m':float(np.linalg.norm(car)),
   'raw_conditional_std_principal_mm':(np.sqrt(np.linalg.eigvalsh(cov))*1000).tolist(),
   'working_std_with_floor_principal_mm':(np.sqrt(np.linalg.eigvalsh(reported))*1000).tolist(),
   'floor_variance_m2':floor,'raw_conditional_baseline_ecef_m':raw.tolist(),
   'published_baseline_ecef_m':car.tolist(),'N_truth_known':False,'comparisons':{},'native':{}}
  for name,idx in [('past_only',past),('nearest_plus_2ms_OFFLINE_ONLY',future)]:
   r=pvt[idx];fixed=np.array([float(r[k]) for k in ['b_n','b_e','b_d']]);ecef=R.T@fixed
   cmp=compare(car,ecef,R)
   assert abs(cmp['angle_3d_deg']-cmp['angle_3d_in_common_NED_deg'])<1e-10
   cmp.update(pvt_time_s=pt[idx],pvt_minus_carrier_time_s=pt[idx]-t,
      pvt_available_at_carrier_time=pt[idx]<=t,pvt_length_m=float(np.linalg.norm(ecef)),
      pvt_working_isotropic_std_mm=1000*math.hypot(float(r['pAcc1']),float(r['pAcc2'])),
      pvt_fixed_NED_m=fixed.tolist(),pvt_ecef_m=ecef.tolist())
   rec['comparisons'][name]=cmp
  for mode in ['off','body']:
   d=diags[mode][t];nav=arrays[mode];ni=np.searchsorted(nav[:,1],t,side='right')-1
   Rc=rotation(np.deg2rad(nav[ni,2]),np.deg2rad(nav[ni,3]))
   z=np.array([float(d[k]) for k in ['z_n_m','z_e_m','z_d_m']])
   pp=rec['comparisons']['past_only'];pv=np.array(pp['pvt_ecef_m'])
   current=compare(car,pv,Rc)
   pdiag=pvt_diags[mode][pt[past]]
   pz=np.array([float(pdiag[k]) for k in ['z_n_m','z_e_m','z_d_m']])
   assert np.max(np.abs(pz-pp['pvt_fixed_NED_m']))<1e-12
   rec['native'][mode]={'carrier_accepted':int(d['accepted']),'carrier_rejected':int(d['rejected']),
     'carrier_reason':d['reason'],'carrier_NIS_3dof':float(d['nis_actual_innovation']),
     'carrier_qa_R_scale':float(d['qa_R_scale']),'carrier_sa_R_scale':float(d['sa_R_scale']),
     'past_pvt_C1_accepted':int(pdiag['accepted']),'past_pvt_C1_reason':pdiag['reason'],
     'past_pvt_C1_NIS_3dof':float(pdiag['nis_actual_innovation']),
     'carrier_native_observed_current_NED_m':z.tolist(),
     'R_current_from_latest_NAV_time_s':float(nav[ni,1]),
     'R_current_anchor_age_s':t-float(nav[ni,1]),
     'carrier_native_z_minus_Rcurrent_ecef_norm_m':float(np.linalg.norm(z-Rc@car)),
     'carrier_native_z_minus_Rfixed_ecef_norm_m':float(np.linalg.norm(z-R@car)),
     'past_compare_in_current_NED':current,
     'fixed_vs_current_azimuth_difference_of_differences_deg':current['horizontal_baseline_azimuth_difference_deg']-pp['horizontal_baseline_azimuth_difference_deg']}
  results.append(rec)
 out={'scope':'SEVEN_ENGINEERING_VALID_PARTIAL_CARRIER_VECTORS_OBSERVATION_CONSISTENCY_ONLY',
 'parent_population':{'all_windows':120,'engineering_valid_carrier_rows':7,'failed_or_unresolved_rows':113},
 'reference_reads':0,'raw_payload_reads':0,'search_calls':0,'native_calls':0,'evaluator_calls':0,
 'time_policy':'primary past-only nearest 198 ms; secondary +2 ms PVT offline-only, never fed to any provider/selection/gate/solver',
 'physical_quantity':'GNSS2-minus-GNSS1 baseline vector; horizontal projection azimuth is not Euler body yaw',
 'coordinate_policy':'sidecar fixed NED -> ECEF using archived orthogonal R transpose; both vectors then same fixed/current NED',
 'fixed_NED_origin_ecef_m':plan['dual_pvt_lineage']['origin_ecef_m'],
 'ecef_to_fixed_NED':R.tolist(),
 'C1_existing_frame_approximation':'native C1 uses sidecar fixed NED directly as local NED; tiny site-dependent rotation difference quantified, not repaired or retuned here',
 'neither_observation_is_truth':True,'pvt_carrier_errors_are_not_assumed_independent':True,
 'source_sha256':inputs,'records':results}
 a.output.mkdir(parents=True,exist_ok=True)
 out['coordinate_numerical_checks']={
  'max_native_carrier_z_minus_current_NED_from_last_NAV_m':max(z['carrier_native_z_minus_Rcurrent_ecef_norm_m'] for r in results for z in r['native'].values()),
  'max_native_current_NED_minus_fixed_NED_m':max(z['carrier_native_z_minus_Rfixed_ecef_norm_m'] for r in results for z in r['native'].values()),
  'max_comparison_azimuth_change_fixed_vs_current_deg':max(abs(z['fixed_vs_current_azimuth_difference_of_differences_deg']) for r in results for z in r['native'].values())}
 out['sparsity']={}
 for mode in ['off','body']:
  times=[r['measurement_time_s'] for r in results if r['native'][mode]['carrier_accepted']]
  out['sparsity'][mode]={'accepted_times_s':times,'first_update_delay_after_66_s':times[0]-66,
   'last_update_to_end340_s':340-times[-1],
   'max_gap_between_accepted_updates_s':max(np.diff(times)),
   'max_interval_without_accepted_carrier_in_full_window_s':max(np.diff([66,*times,340]))}
 out['interpretation']='Large availability deficit is directly observed; a sparse-only causal attribution is not established. No 90/180 degree reversal is found, but degree-scale vector/inclination discrepancies persist even in the +2ms offline comparison.'
 (a.output/'CARRIER_PVT_OBSERVATION_DIAGNOSIS.json').write_text(json.dumps(out,indent=2,ensure_ascii=False,allow_nan=False)+'\n')
 lines=['# 七条部分载波基线与双位置基线的一致性诊断','',
 '只读既有载波/PVT侧车、保存的条件解与 native 诊断；不读参考或原始载荷，不改参数，不新增搜索、导航或评价。完整母体为 120 窗，7 条工程合格与 113 条失败/未决保持原样。本表包含全部 7 条合格观测，包括滤波拒绝的观测。','',
 '严格当时可用的 PVT 早 198.000 ms；最近 PVT 则晚 2.000 ms。后者只作离线观测一致性对照，不用于 provider、筛星、门限或解算，不称“真实方向误差”。两种观测可能共享 GNSS 误差，不假设独立，也不把任何一方当真值。','',
 '坐标：双位置侧车原为固定原点 NED，通过所存正交矩阵的转置转回 ECEF，再与载波统一转到相同 NED。3D 夹角在 ECEF/NED 下数值相同。当前 NED 与固定 NED 的局部近似也已量化：native 载波 z 与按最后可用 NAV 位置重建的当前 NED 相差不足 5e-10 m；当前/固定 NED 向量差最大约 8.11 µm，比较方位差的变化不足 0.000077°。这些坐标微差不能解释下面的数度差异。原 C1 直接使用固定 NED 侧车的局部近似保持不变。','',
 '“方位”均指横向基线的水平投影方位，不把含滚转/俯仰的横向基线方位直接解释为机体 Euler yaw。','',
 '| 时间 (s) | 原始条件 GLS 长度 (m) | 条件标准差主轴 (mm) | Past 3D夹角 (°) | Past 方位差 (°) | +2ms 3D夹角 (°) | +2ms 方位差 (°) |',
 '|---|---:|---|---:|---:|---:|---:|']
 for r in results:
  pp=r['comparisons']['past_only'];nn=r['comparisons']['nearest_plus_2ms_OFFLINE_ONLY']
  st='/'.join(f'{v:.2f}' for v in r['raw_conditional_std_principal_mm'])
  lines.append(f"| {r['measurement_time_s']:.3f} | {r['raw_conditional_GLS_length_m']:.6f} | {st} | {pp['angle_3d_deg']:.3f} | {pp['horizontal_baseline_azimuth_difference_deg']:.3f} | {nn['angle_3d_deg']:.3f} | {nn['horizontal_baseline_azimuth_difference_deg']:.3f} |")
 lines += ['','发布向量均约束到名义 0.350 m；原始固定整数 GLS 长度为 0.32394–0.35520 m，所以不能用发布长度恰等于 0.35 m 来证明观测准确。表内标准差是已选整数条件下的三个协方差主轴标准差，不包括错误整数风险；传给滤波的协方差还叠加原定 1.5° 工程下限。完整 JSON 同时保留 PVT 原始长度/pAcc 工作标准差及载波原始/发布向量。','',
 '| 时间 (s) | HV-off native | HV-off NIS (3 dof) | Body native | Body NIS (3 dof) |',
 '|---|---|---:|---|---:|']
 for r in results:
  no,nb=r['native']['off'],r['native']['body']
  lines.append(f"| {r['measurement_time_s']:.3f} | {no['carrier_reason']} | {no['carrier_NIS_3dof']:.6f} | {nb['carrier_reason']} | {nb['carrier_NIS_3dof']:.6f} |")
 lines += ['',
 'NIS 是各自滤波状态及协方差下的创新统计量，不等于载波与 PVT 的方向差，也不是整数正确性检验。同一条 155.998 s 观测在 off 接受、body 拒绝，301.998 s 则相反；这些差异来自已有状态/协方差与固定门控，不是本次改动。原始 NIS/QA/SA 因子及同时刻之前的 C1 PVT 接受记录均保存在 JSON。','',
 '能够确认的主要问题是支持极稀疏：两组各仅 5 次实际部分载波更新，而同次实验双位置向量有 1,302 次。第一次载波更新都在启动约 70 s 后；body 两次接受之间最长空缺 130 s，off 最后一次接受后到终点约 168 s。载波替换掉高频双位置航向之后，这些长空缺直接存在。','',
 '同时，观测自身并非完全一致：+2ms 对照的 3D 夹角仍为 1.32–8.46°，水平基线方位差最大绝对值 5.43°。171.998 s 的差异主要体现为基线倾角（约 7.86°差），并非等量 yaw 差；169.998 s 仍有约 5.43°水平方位差。没有发现 90°/180°翻转或明显坐标符号错误，但不能排除个别观测对姿态产生不利影响。','',
 '因此：稀疏是明确且严重的限制，“退化全部或主要由稀疏造成”仍缺隔离因果证据。本诊断不能决定载波/PVT 谁更准确，不能校准实际相位 Q，也不支持放宽现有门限。后续定位应同时保留可用率问题与少数基线方向/倾角不一致这两条线索。']
 (a.output/'CARRIER_PVT_OBSERVATION_DIAGNOSIS.md').write_text('\n'.join(lines)+'\n')
 for x in results:
  print(round(x['measurement_time_s'],3),'Lraw',round(x['raw_conditional_GLS_length_m'],5),
   'anglespast/next',round(x['comparisons']['past_only']['angle_3d_deg'],3),round(x['comparisons']['nearest_plus_2ms_OFFLINE_ONLY']['angle_3d_deg'],3),
   'azpast/next',round(x['comparisons']['past_only']['horizontal_baseline_azimuth_difference_deg'],3),round(x['comparisons']['nearest_plus_2ms_OFFLINE_ONLY']['horizontal_baseline_azimuth_difference_deg'],3),
   'gate',[x['native'][m]['carrier_accepted'] for m in ['off','body']])
if __name__=='__main__':main()
