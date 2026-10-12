from pathlib import Path
import pandas as pd,numpy as np,json
ROOT=Path('/mnt/g/LegSA-GINS-project'); OUT=Path(__file__).parent
REPO=Path('/home/kaiwen/research/LegSA-GINS-WORKTREES/audit-code-xbpg-20261001')
POSE=REPO/'docs/paper_rebuild/GPSS_V3_FIGURES_20261008/redesign_20261009/data'
NAV=ROOT/'V3五问题论文组图_20261011/navigation/data'
rows=[]
for s,start in [('BY2',66),('BY2H',413),('BY2O',3186)]:
 d=pd.read_csv(POSE/(s+'_display_pose.csv.gz'));print(s,list(d),flush=True)
 print(d.head(1).to_dict('records'),flush=True)
 t=d.time_s.to_numpy();h=np.rad2deg(np.unwrap(np.deg2rad(d.heading_truth_ned_deg)))
 rec=[]
 for beg in np.arange(start+10,t[-1]-30,5):
  a=np.searchsorted(t,beg);b=np.searchsorted(t,beg+20)
  xy=d[['east_truth_m','north_truth_m']].to_numpy()
  dist=np.linalg.norm(xy[b]-xy[a]);turn=abs(h[b]-h[a])
  if turn>=60 and dist>=2:rec.append({'sequence':s,'lo':float(beg),'hi':float(beg+20),'elapsed_lo':float(beg-start),'turn_deg':float(turn),'displacement_m':float(dist)})
 print('candidate turns',rec[:8],flush=True);rows.extend(rec[:8])
 q=pd.read_csv(NAV/(s+'_COMMON_SEGMENTED_HEADING.csv.gz'));print('common',s,len(q),list(q),q.head(2).to_dict('records'),flush=True)
n=pd.read_csv(NAV/'LC_NATIVE_TABLE_READ.csv'); print(n[['sequence_id','method_id','start_convention','evaluation_status','error_series_source']].to_string(index=False),flush=True)
for _,r in n.iterrows():
 p=Path(r.error_series_source)
 files=list(p.glob('*.csv*')) if p.is_dir() else []
 print('PATH',r.sequence_id,r.method_id,r.start_convention,str(p),p.exists(),[x.name for x in files],flush=True)
 if files:
  q=pd.read_csv(files[0],nrows=2);print(list(q),q.to_dict('records'),flush=True)
(OUT/'candidate_events.json').write_text(json.dumps(rows,indent=2))
