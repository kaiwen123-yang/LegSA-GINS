"""Read all retained coordinates; project for display only, without fitting."""
from pathlib import Path
import hashlib,json
import numpy as np,pandas as pd
R=Path('/mnt/g/LegSA-GINS-project');O=Path(__file__).parent;D=O/'data';D.mkdir(exist_ok=True)
C=R/'clean_rebuild_202607/stages';N=R/'V3五问题论文组图_20261011/navigation/data';F=R/'V3论文组图_20261008/focused_20261011/comparison/data'
REPO=Path('/home/kaiwen/research/LegSA-GINS-WORKTREES/audit-code-xbpg-20261001');POSE=REPO/'docs/paper_rebuild/GPSS_V3_FIGURES_20261008/redesign_20261009/data'
STRICT=Path('/home/kaiwen/research/LegSA-GINS-SCRATCH/FGO_REPRODUCTION_FIX_20261004/FGO_REPRODUCTION_FINAL_20261004T054410Z')
SEG=C/'FGO_SEGMENTED_DIAGNOSTIC_20261004T100449Z'
SEQ=['BY2','BY2H','BY2O'];START={'BY2':66,'BY2H':413,'BY2O':3186};END={'BY2':340,'BY2H':683,'BY2O':3563};BASE={'BY2':1772784000.,'BY2H':1772784000.,'BY2O':1772780400.}
RAW={'BY2':('by2','08-00-54'),'BY2H':('by3','08-06-39'),'BY2O':('by1','07-52-22')}
readlog=[];inventory=[];checks=[];refs={};frames={}
def read(p,**kw):
 p=Path(p);d=pd.read_csv(p,**kw);readlog.append({'source':str(p),'rows':len(d),'columns':';'.join(map(str,d.columns))});return d
def xyz(llh):
 la,lo=np.deg2rad(llh[:,0]),np.deg2rad(llh[:,1]);h=llh[:,2];e2=6.6943799901413165e-3;n=6378137/np.sqrt(1-e2*np.sin(la)**2)
 return np.column_stack(((n+h)*np.cos(la)*np.cos(lo),(n+h)*np.cos(la)*np.sin(lo),(n*(1-e2)+h)*np.sin(la)))
def rot(llh):
 la,lo=np.deg2rad(llh[:2]);sl,cl,so,co=np.sin(la),np.cos(la),np.sin(lo),np.cos(lo)
 return np.array([[-so,co,0],[-sl*co,-sl*so,cl],[cl*co,cl*so,sl]])
def refl(s,t):
 g=refs[s];return np.column_stack([np.interp(t,g.time,g[k]) for k in ['lat','lon','alt']])
def projected(s,p):
 origin,rotation=frames[s];return (p-origin)@rotation.T
def save(s,m,t,p,point,status,source,protocol,valid=None,block=None,extra=None):
 t=np.asarray(t);valid=np.ones(len(t),bool) if valid is None else np.asarray(valid,bool)
 mask=(t>=START[s])&(t<=END[s]);t=t[mask];p=np.asarray(p)[mask];valid=valid[mask]&np.isfinite(p).all(axis=1);en=projected(s,p)
 d=pd.DataFrame({'time_s':t,'elapsed_s':t-START[s],'east_m':en[:,0],'north_m':en[:,1],'up_m':en[:,2],'valid':valid})
 if block is not None:d['block_id']=np.asarray(block)[mask]
 path=D/(s+'__'+m+'.csv.gz');d.to_csv(path,index=False)
 vv=d[d.valid];inventory.append({'sequence':s,'method':m,'point':point,'status':status,'full_window_start':START[s],'full_window_end':END[s],'native_rows_read':len(mask),'in_window_rows':len(d),'finite_display_rows':len(vv),'first_output_s':float(vv.time_s.min()) if len(vv) else None,'last_output_s':float(vv.time_s.max()) if len(vv) else None,'source':str(source),'protocol':protocol,'display_data':path.name,'extras':json.dumps(extra or {})})
 return d

for s in SEQ:
 raw,stamp=RAW[s];stem=f'vrtk2_a87c6e_2026-03-06-{stamp}_minimal';rp=R/f'data/raw/BY2_BY3/2026-03-06/fixption数据/2026.3.6/{raw}/{stem}/trace_{stem}.csv'
 q=read(rp)
 eroot=C/'CLEAN8_PROTOCOL_V3/04_EVALUATION'/('RUN_00004' if s=='BY2' else f'V3R_CONTINUATION/SEQUENCE_{s}_F04')/'v3'
 capture=json.loads((eroot/'FROZEN_EVALUATOR/EVALUATOR_CAPTURE.json').read_text());cols=capture['selected_columns']
 g=pd.DataFrame({'time':pd.to_numeric(q[cols['time']],errors='coerce')-(0 if 'aligned_time' in cols['time'].lower() else BASE[s]),**{a:pd.to_numeric(q[cols[b]],errors='coerce') for a,b in [('lat','lat'),('lon','lon'),('alt','height'),('roll','roll'),('pitch','pitch'),('yaw','yaw')]}}).dropna().sort_values('time').reset_index(drop=True)
 assert np.all(np.diff(g.time)>0);refs[s]=g
 anchor=refl(s,np.array([START[s]]))[0];frames[s]=(xyz(anchor[None,:])[0],rot(anchor))
 gf=g[g.time.between(START[s],END[s])];save(s,'REFERENCE_POI',gf.time,xyz(gf[['lat','lon','alt']].to_numpy()),'POI_MIDPOINT','REFERENCE',rp,'raw reference; registered columns; no fit')
 er=read(F/(s+'_V3_POI_full.csv.gz'));tt=er.time.to_numpy();llh=refl(s,tt);rr=rot(llh[0]);pp=xyz(llh)+er[['err_e_m','err_n_m','err_u_m']].to_numpy()@rr
 saved=save(s,'F04',tt,pp,'POI_MIDPOINT','COMPLETED',F/(s+'_V3_POI_full.csv.gz'),'exact inverse of retained signed ENU error with same LLH reference interpolation; no fit')
 old=read(POSE/(s+'_display_pose.csv.gz'));assert np.array_equal(tt,old.time_s)
 native_display=(pp-xyz(llh[[0]])[0])@rr.T
 delta=np.max(np.abs(native_display[:,:2]-old[['east_legsa_m','north_legsa_m']].to_numpy()));checks.append({'method':'F04','sequence':s,'check':'parity with existing display coordinates','max_abs_difference_m':float(delta)});assert delta<2e-6
 # Strict OiSAM already contains the exact evaluated POI and same-point truth.
 p=STRICT/'evaluation'/s/'OISAM_TRAJECTORY.csv';q=read(p);valid=q.valid.to_numpy()>0
 save(s,'OISAM_STRICT',q.time,q[['x_ecef_m','y_ecef_m','z_ecef_m']].to_numpy(),'POI_MIDPOINT','ONE_INITIALIZATION',p,'all original finite evaluated states; no reinitialization',valid)
 # All GNSS1 routes have archived transformed ECEF trajectories and truth.
 for m in ['OISAM','WEN_TC','GNC']:
  p=SEG/'evaluation'/s/(m+'_PRIMARY_DYNAMIC_ONLY_TRAJECTORY.csv');q=read(p)
  ep=SEG/'evaluation'/s/(m+'_PRIMARY_DYNAMIC_ONLY_ERRORS.csv');e=read(ep);assert np.array_equal(q.time,e.time)
  save(s,'OISAM_RESTART' if m=='OISAM' else m,q.time,q[['x_ecef_m','y_ecef_m','z_ecef_m']].to_numpy(),'GNSS1_ANTENNA','REGISTERED_DYNAMIC_OUTPUTS',p,'registered GNSS1 point, initialization-only excluded; own native support',q.valid>0,e.block_id if 'block_id' in e else None)
 p=STRICT/'evaluation'/s/'TRUTH_GNSS1_ANTENNA.csv';q=read(p);save(s,'REFERENCE_GNSS1',q.time,q[['x_ecef_m','y_ecef_m','z_ecef_m']].to_numpy(),'GNSS1_ANTENNA','REFERENCE',p,'archived same-point reference')

tab=read(N/'LC_NATIVE_TABLE_READ.csv')
for _,row in tab.iterrows():
 s,m,init=row.sequence_id,row.method_id,row.start_convention
 if s=='BY2' and m in ['LC01','EXT05C']:
  stem='LC01_EXT05A' if m=='LC01' else 'EXT05C';p=C/'CLEAN5_DEGSUBSET_BY2/09_HORIZONTAL_V3'/stem/'EVAL_NAV_V3.nav'
 else:p=C/'CLEAN7_HEXT_EXTERNAL_SEQUENCES/06_V3_NAV_INPUTS'/f'{s}__{m}__{init}'/'EVALUATOR_INPUT.nav'
 nav=read(p,sep=r'\s+',header=None,comment='%').to_numpy(float)
 expected=row.evaluator_nav_sha256 if pd.notna(row.evaluator_nav_sha256) else None
 actual=hashlib.sha256(p.read_bytes()).hexdigest()
 # Alternate failed source has its own registered transform manifest and no evaluated metric row.
 if expected is not None and str(expected) not in ['UNAVAILABLE','']:
  assert actual==expected,(s,m,init,'native hash mismatch')
 pp=xyz(nav[:,2:5]);method=m if init==('CONTRACT_START' if s=='BY2H' else 'FILE_START') else m+'_ALT'
 save(s,method,nav[:,1],pp,'POI_MIDPOINT',row.evaluation_status,p,'previously registered v3 point-transformed NAV; no new point correction',extra={'initialization':init,'geometric_audit_status':row.geometric_audit_status,'sha256':actual})
 if row.error_series_source!='UNAVAILABLE':
  ep=Path(row.error_series_source);ep=ep/('error_series.csv.gz' if (ep/'error_series.csv.gz').exists() else 'error_series.csv');e=read(ep);tt=e.time.to_numpy();idx=np.searchsorted(nav[:,1],tt);idx=np.clip(idx,0,len(nav)-1);prev=np.maximum(idx-1,0);idx=np.where(abs(nav[prev,1]-tt)<abs(nav[idx,1]-tt),prev,idx);assert np.max(abs(nav[idx,1]-tt))<1e-6
  llh=refl(s,tt);rr=rot(llh[0]);difference=(pp[idx]-xyz(llh))@rr.T;err=e[['err_e_m','err_n_m','err_u_m']].to_numpy();maxdiff=float(np.max(abs(difference-err)));checks.append({'sequence':s,'method':method,'check':'direct registered NAV minus reference equals saved signed error','max_abs_difference_m':maxdiff});assert maxdiff<2e-5,(s,m,init,maxdiff)

# GINav raw ECEF is an INS/IMU point, not the GNSS1 point named in its input file.
ex=read(N/'EXPERIMENTS.csv')
for _,row in ex[ex.method.str.contains('GINav',na=False)].iterrows():
 s=row.sequence;nr=Path(row.native_record);p=nr.parent/'NAV/GINAV_STANDARD_NAV.csv';q=read(p);ev=json.loads(Path(row.error_series).read_text())
 save(s,'GINAV_NATIVE',q.relative_time_s,q[['ecef_x_m','ecef_y_m','ecef_z_m']].to_numpy(),'NATIVE_INS_IMU',row.status,p,'all finite original emitted ECEF; fixed geographic projection only; do not score against POI',q.state_finite.to_numpy(),extra={'finite_window_rows':ev['coverage']['valid_rows_in_window'],'nominal_slots':ev['coverage']['expected_integer_epochs'],'first_violation':ev['bounded_gate'].get('first_violation'),'split_gap_s':1.5})

# Relative-only estimators retain their own native gauges; do not align them
# to the geographic methods merely to make the paths look similar.
for s in SEQ:
 for m in ['OFF-LIT','OFF-DEF','LEG-DR']:
  if m=='LEG-DR':p=C/'CLEAN9_EXTERNAL_COMPARISON/HX05_CLOSEOUT/RUNS'/s/'NAV.csv'
  else:
   suffix={'BY2':'C00','BY2H':'CONTRACT_START','BY2O':'FILE_START'}[s]
   p=C/'CLEAN9_EXTERNAL_COMPARISON/HX02E_HARTLEY_OFFICIAL/RUNS'/f'{s}__HARTLEY_OFFICIAL__{m}__{suffix}'/'NAV.csv'
  q=read(p);tt=q.timestamp_ns.to_numpy(np.float64)*1e-9-BASE[s];mask=(tt>=START[s])&(tt<=END[s])
  d=pd.DataFrame({'time_s':tt[mask],'elapsed_s':tt[mask]-START[s],'local_x_m':q.px.to_numpy()[mask],'local_y_m':q.py.to_numpy()[mask],'local_z_m':q.pz.to_numpy()[mask]})
  path=D/(s+'__'+m+'_LOCAL.csv.gz');d.to_csv(path,index=False)
  inventory.append({'sequence':s,'method':m,'point':'NATIVE_LOCAL_IMU','status':'RELATIVE_ONLY_COMPLETED','native_rows_read':len(q),'in_window_rows':len(d),'finite_display_rows':len(d),'first_output_s':float(d.time_s.min()),'last_output_s':float(d.time_s.max()),'source':str(p),'protocol':'native local frame as emitted; no yaw/translation fitting; not an absolute geographic comparison','display_data':path.name})
pd.DataFrame(inventory).to_csv(D/'TRAJECTORY_COVERAGE.csv',index=False);pd.DataFrame(readlog).to_csv(D/'COORDINATE_SOURCES_READ.csv',index=False);pd.DataFrame(checks).to_csv(D/'COORDINATE_PARITY_CHECKS.csv',index=False)
(D/'COORDINATE_PROTOCOL.json').write_text(json.dumps({'anchor':{s:{'ecef_origin_m':o.tolist(),'ecef_to_enu':r.tolist()} for s,(o,r) in frames.items()},'transform':'Same WGS84 ECEF->ENU projection per scene, origin at the original POI reference at formal-window start. No method-specific translation/rotation fitted.','new_solver_evaluator_provider_calls':0,'partial_outputs_preserved':True,'GINav_point':'INS/IMU native point; display separately from common POI/GNSS1 groups'},indent=2))
print('Prepared',len(inventory),'coordinate sources;',len(checks),'parity checks;',len(readlog),'source reads',flush=True)
