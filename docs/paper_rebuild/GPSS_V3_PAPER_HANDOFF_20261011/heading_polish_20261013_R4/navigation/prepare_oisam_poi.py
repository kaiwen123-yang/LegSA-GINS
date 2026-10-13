"""Apply the already registered physical-point transform to OiSAM's own pose."""
from pathlib import Path
import json
import numpy as np,pandas as pd
O=Path(__file__).parent;D=O/'data';D.mkdir(exist_ok=True)
R=Path('/mnt/g/LegSA-GINS-project');R3=R/'V3正文精修_20261012_R3/navigation/data';F=R/'V3论文组图_20261008/focused_20261011/comparison/data';C=R/'clean_rebuild_202607/stages/CLEAN7_HEXT_EXTERNAL_SEQUENCES'
frame=json.loads((R3/'COORDINATE_PROTOCOL.json').read_text())['anchor'];records=[]
def llh(position):
 x,y,z=np.asarray(position).T;lon=np.arctan2(y,x);p=np.hypot(x,y);lat=np.arctan2(z,p*(1-6.6943799901413165e-3))
 for _ in range(12):
  n=6378137/np.sqrt(1-6.6943799901413165e-3*np.sin(lat)**2);h=p/np.cos(lat)-n;lat=np.arctan2(z,p*(1-6.6943799901413165e-3*n/(n+h)))
 return np.column_stack((lat,lon,h))
def cne(lat,lon):
 sl,cl,so,co=np.sin(lat),np.cos(lat),np.sin(lon),np.cos(lon)
 return np.stack((-sl*co,-so,-cl*co,-sl*so,co,-cl*so,cl,np.zeros_like(cl),-sl),axis=-1).reshape((-1,3,3))
def body(rpy):
 r,p,y=np.deg2rad(rpy).T;cr,sr,cp,sp,cy,sy=np.cos(r),np.sin(r),np.cos(p),np.sin(p),np.cos(y),np.sin(y)
 return np.stack((cy*cp,cy*sp*sr-sy*cr,cy*sp*cr+sy*sr,sy*cp,sy*sp*sr+cy*cr,sy*sp*cr-cy*sr,-sp,cp*sr,cp*cr),axis=-1).reshape((-1,3,3))
for s in ['BY2','BY2H','BY2O']:
 state_path=F/(s+'_OISAM_SEGMENTED_states.csv.gz');states=pd.read_csv(state_path)
 existing_path=R3/(s+'__OISAM_RESTART.csv.gz');existing=pd.read_csv(existing_path)
 start={'BY2':66,'BY2H':413,'BY2O':3186}[s];end={'BY2':340,'BY2H':683,'BY2O':3563}[s]
 states=states[states.time_rel_s.between(start,end)].copy();assert np.array_equal(states.time_rel_s.to_numpy(),existing.time_s.to_numpy())
 init='CONTRACT_START' if s=='BY2H' else 'FILE_START';method='LC01-S' if s=='BY2' else 'LC01'
 manifest=C/'06_V3_NAV_INPUTS'/f'{s}__{method}__{init}'/'TRANSFORM_MANIFEST.json';registered=json.loads(manifest.read_text());baseline=registered['baseline_median_m'];lever=np.asarray(registered['lever_frd_m'])
 assert np.allclose(lever,[.03,.03-baseline/2,-.30],atol=1e-15)
 p=states[['x_ecef_m','y_ecef_m','z_ecef_m']].to_numpy();angles=states[['roll_deg','pitch_deg','yaw_deg']].to_numpy();native_llh=llh(p);rotation=np.einsum('nij,njk->nik',cne(native_llh[:,0],native_llh[:,1]),body(angles))
 antenna=p+np.einsum('nij,j->ni',rotation,np.array([.03,.03,-.30]));poi=p+np.einsum('nij,j->ni',rotation,lever)
 anchor=np.asarray(frame[s]['ecef_origin_m']);enu=np.asarray(frame[s]['ecef_to_enu']);ant_enu=(antenna-anchor)@enu.T;poi_enu=(poi-anchor)@enu.T
 good=existing.valid.to_numpy(bool);parity=float(np.max(np.linalg.norm(ant_enu[good]-existing.loc[good,['east_m','north_m','up_m']].to_numpy(),axis=1)))
 assert parity<2e-6,(s,parity)
 result=existing.copy();result[['east_m','north_m','up_m']]=poi_enu;result.to_csv(D/(s+'__OISAM_RESTART_POI.csv.gz'),index=False)
 strict_parity=None
 if s=='BY2':
  strict=pd.read_csv(R3/(s+'__OISAM_STRICT.csv.gz'));a=result[result.valid];b=strict[strict.valid];joined=a.merge(b,on='time_s',suffixes=('_new','_strict'))
  dif=np.column_stack([joined[k+'_new']-joined[k+'_strict'] for k in ['east_m','north_m','up_m']]);strict_parity=float(np.linalg.norm(dif,axis=1).max());assert len(joined)==275 and strict_parity<2e-6
 records.append({'sequence':s,'source_pose':str(state_path),'original_gnss1_trajectory':str(existing_path),'registered_transform_manifest':str(manifest),'baseline_m':baseline,'lever_imu_to_poi_body_m':lever.tolist(),'method_attitude_used':'Own OiSAM roll/pitch/yaw only; no reference attitude','source_in_window_states':len(states),'dynamic_states':int(good.sum()),'reconstructed_gnss1_vs_original_max_difference_m':parity,'BY2_poi_vs_existing_strict_max_difference_m':strict_parity,'new_navigation_metrics':0,'source_metric_files_changed':False})
(D/'OISAM_POI_TRANSFORM_CHECKS.json').write_text(json.dumps({'purpose':'Display-only reuse of the registered physical point transform for the existing reinitialized OiSAM pose','new_solver_evaluator_provider_calls':0,'records':records},ensure_ascii=False,indent=2))
print(json.dumps(records,ensure_ascii=False,indent=2))
