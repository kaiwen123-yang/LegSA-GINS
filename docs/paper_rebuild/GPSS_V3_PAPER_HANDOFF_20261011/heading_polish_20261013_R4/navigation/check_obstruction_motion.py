from pathlib import Path
import numpy as np,pandas as pd,json
O=Path(__file__).parent;D=Path('/mnt/g/LegSA-GINS-project/V3正文精修_20261012_R3/navigation/data');s='BY2O'
d=pd.read_csv(D/f'{s}__REFERENCE_POI.csv.gz');t=d.elapsed_s.to_numpy();xy=d[['east_m','north_m']].to_numpy()
rows=[]
def report(label,lo,hi):
 mask=(t>=lo)&(t<=hi);z=xy[mask];tt=t[mask];sec=np.arange(lo,hi+.0001,1.);q=np.column_stack([np.interp(sec,t,xy[:,j]) for j in range(2)]);speed=np.linalg.norm(np.diff(q,axis=0),axis=1);endpoints=np.column_stack([np.interp([lo,hi],t,xy[:,j]) for j in range(2)])
 r={'label':label,'start_s':lo,'end_s':hi,'native_reference_rows':int(mask.sum()),'net_displacement_m':float(np.linalg.norm(z[-1]-z[0])),'exact_interval_endpoint_displacement_m':float(np.linalg.norm(endpoints[-1]-endpoints[0])),'east_range_m':float(np.ptp(z[:,0])),'north_range_m':float(np.ptp(z[:,1])),'native_path_length_m':float(np.linalg.norm(np.diff(z,axis=0),axis=1).sum()),'one_second_reference_speed_median_mps':float(np.median(speed)),'one_second_reference_speed_p95_mps':float(np.quantile(speed,.95)),'one_second_reference_speed_max_mps':float(speed.max()),'one_second_samples':len(speed)};rows.append(r);return r
report('R3 full100s',154.945,254.945);report('R3 static spatial detail',199.945,209.945);report('Registered obstruction',183.94,225.95)
candidates=[]
for lo in np.arange(226.,250.,1.):
 hi=lo+5
 if hi>254.945:break
 sec=np.arange(lo,hi+1);q=np.column_stack([np.interp(sec,t,xy[:,j]) for j in range(2)]);speed=np.linalg.norm(np.diff(q,axis=0),axis=1)
 if np.linalg.norm(q[-1]-q[0])>=2 and np.median(speed)>=.3:
  candidates.append({'start_s':float(lo),'end_s':float(hi),'displacement_m':float(np.linalg.norm(q[-1]-q[0])),'median_speed_mps':float(np.median(speed))})
if candidates:report('First reference-moving recovery5s',candidates[0]['start_s'],candidates[0]['end_s'])
pd.DataFrame(rows).to_csv(O/'OBSTRUCTION_REFERENCE_MOTION.csv',index=False)
(O/'OBSTRUCTION_DIAGNOSIS.json').write_text(json.dumps({'diagnostics':rows,'motion_selection_rule':'First5s interval after registered obstruction end225.95s, on1s grid, endpoint displacement>=2m and median1s reference chord speed>=0.3m/s; method estimates not inspected','candidate_windows':candidates,'R3_coordinate_parity_max_m':3.889587082972491e-9,'why_cloud':'The old fixed10s detail lies inside a nearly stationary reference interval; centimetre coordinate errors/jitter dominate the very small reference motion. It is not an estimate/reference point-conversion bug.'},ensure_ascii=False,indent=2))
print(json.dumps({'rows':rows,'first_recovery':candidates[:1]},ensure_ascii=False,indent=2))
