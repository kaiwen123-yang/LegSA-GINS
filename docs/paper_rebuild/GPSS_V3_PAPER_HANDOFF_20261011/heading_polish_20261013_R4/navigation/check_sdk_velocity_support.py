"""Bounded read-only check of the one BY2O velocity-provider source bundle."""
from pathlib import Path
import hashlib,json
import numpy as np,pandas as pd
R=Path('/mnt/g/LegSA-GINS-project');O=Path(__file__).parent;D=O/'data';start=3186.
native=R/'clean_rebuild_202607/stages/CLEAN8_PROTOCOL_V3/03_NATIVE/V3R_CONTINUATION/SEQUENCE_BY2O_F04'
manifest=json.loads((native/'RUN_MANIFEST.json').read_text());source=Path(manifest['actual_solver_input_paths']['go2_horizontal_velocity_weak_prior']);bundle=json.loads((source.parent/'PROVIDER_BUNDLE.json').read_text());body_path=Path(bundle['body_support']['path']);hv_sha256=hashlib.sha256(source.read_bytes()).hexdigest();assert hv_sha256==bundle['provider_hashes']['go2_horizontal_velocity_prior_path']
windows=[('Registered obstruction',183.94,225.95),('Former local detail',199.945,209.945),('Recovery motion',228.,233.)]
minimum=start+min(x[1] for x in windows);maximum=start+max(x[2] for x in windows)
parts=[]
for chunk in pd.read_csv(source,chunksize=10000):
 parts.append(chunk[chunk.time.between(minimum,maximum)])
 if chunk.time.iloc[-1]>maximum:break
hv=pd.concat(parts,ignore_index=True);hv['elapsed_s']=hv.time-start
# This is the pre-rotation SDK body/rpy support saved by the SAME provider
# bundle, not a second run, reference stream or new raw-text parser execution.
assert hashlib.sha256(body_path.read_bytes()).hexdigest()==bundle['body_support']['sha256']
with np.load(body_path) as packet:all_body=packet['body'];body=all_body[(all_body[:,0]>=minimum)&(all_body[:,0]<=maximum)].copy()
assert body.shape[1]==6
assert len(body)==len(hv) and np.max(abs(body[:,0]-hv.time.to_numpy()))<1e-9
sdk=pd.DataFrame(body,columns=['time','roll_rad','pitch_rad','sdk_vx','sdk_vy','sdk_vz']);sdk['elapsed_s']=sdk.time-start
hv['horizontal_prior_speed_mps']=np.hypot(hv.vn,hv.ve);sdk['sdk_speed_3d_mps']=np.linalg.norm(body[:,3:6],axis=1);sdk['sdk_xy_norm_mps']=np.linalg.norm(body[:,3:5],axis=1)
records=[]
for label,lo,hi in windows:
 a=hv[hv.elapsed_s.between(lo,hi)];b=sdk[sdk.elapsed_s.between(lo,hi)];t=a.elapsed_s.to_numpy();entry={'interval':label,'start_s':lo,'end_s':hi,'rows':len(a),'first_elapsed_s':float(t[0]),'last_elapsed_s':float(t[-1]),'time_strictly_increasing':bool(np.all(np.diff(t)>0)),'median_dt_s':float(np.median(np.diff(t))),'max_dt_s':float(np.max(np.diff(t)))}
 for field in ['valid','go2_source_valid','a1_heading_valid','update_flag','quality_flag','confidence_level','reason_codes','source_status']:
  entry[field+'_counts']={str(k):int(v) for k,v in a[field].value_counts(dropna=False).items()}
 for key,vals in [('prior_horizontal',a.horizontal_prior_speed_mps.to_numpy()),('sdk_raw_3d',b.sdk_speed_3d_mps.to_numpy()),('sdk_raw_xy',b.sdk_xy_norm_mps.to_numpy())]:
  entry.update({key+'_median_mps':float(np.median(vals)),key+'_p95_mps':float(np.percentile(vals,95)),key+'_max_mps':float(vals.max()),key+'_exact_zero_count':int(np.sum(vals==0)),key+'_nonfinite_count':int(np.sum(~np.isfinite(vals))),key+'_fraction_below_0p05_mps':float(np.mean(vals<.05)),key+'_fraction_below_0p10_mps':float(np.mean(vals<.10))})
 records.append(entry)
hv.to_csv(D/'OBSTRUCTION_HV_PROVIDER_WINDOW.csv.gz',index=False);sdk.to_csv(D/'OBSTRUCTION_SDK_BODY_WINDOW.csv.gz',index=False)
result={'scope':'Single BY2O/F04 velocity-provider bundle, windows183.94–233s only; no raw-body text, other sequences, solver or evaluator read/execution','native_config':str(native/'V3_RUNTIME_CONFIG.yaml'),'manifest':str(native/'RUN_MANIFEST.json'),'actual_hv_source':str(source),'body_support_source':str(body_path),'original_raw_body_source':bundle['raw_source_hashes']['body'],'body_support_sha256_matches_bundle':True,'row_identity_HV_to_body_max_abs_time_s':float(np.max(abs(body[:,0]-hv.time.to_numpy()))),'body_support_columns':['time','roll_rad','pitch_rad','sdk_vx','sdk_vy','sdk_vz'],'prior_semantics':'K_HV=1/0.962142 times FLU->FRD roll/pitch plus historicalA1-yaw rotation, horizontal component only. valid=go2_source_valid AND a1_heading_valid. MissingA1 sets valid/update_flag false and reason, not zero vn/ve. Vertical prior vd is intentionally disabled0, not a physical vertical-speed measurement.','default_zero_semantics':'Body parser represents missing velocity fields by NaN; body support generation retains only fully finite timestamp/rpy/velocity rows. Stored pre-rotation SDK values are checked here; none assumed accurate ground truth.','quality_flag_semantics':'clean_raw_go2_weak_auxiliary / weak_auxiliary is provider policy, not an independent sensor solution-quality certificate. go2_source_valid is source-side eligibility; valid also includes direction support.','reference_use':'No reference position/attitude/velocity used to compute these SDK norms','records':records,'new_solver_evaluator_provider_calls':0}
result['HV_sha256_matches_original_provider_bundle']=True;result['HV_sha256']=hv_sha256;result['generation_code_read_only']={'prior':'src/legsa_gins/paper_rebuild/clean6_sensor_v21/providers.py:154–194,361–370','missing_field_parser':'scripts/paper_rebuild/clean6_hv_frame_audit.py:46–75','finite_source_selection':'scripts/paper_rebuild/clean6_hv_a1_yaw_diagnostic.py:64–74'}
(O/'OBSTRUCTION_SDK_CORROBORATION.json').write_text(json.dumps(result,ensure_ascii=False,indent=2));pd.DataFrame(records).to_csv(O/'OBSTRUCTION_SDK_CORROBORATION.csv',index=False)
print(json.dumps(records,ensure_ascii=False,indent=2))
