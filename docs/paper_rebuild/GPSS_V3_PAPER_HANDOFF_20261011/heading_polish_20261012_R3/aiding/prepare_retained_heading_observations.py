"""Read frozen inputs and join existing reference matches; no provider/evaluator run."""
from pathlib import Path
import json,hashlib,shutil
import pandas as pd,numpy as np
P=Path(__file__).resolve().parent
ROOT=Path('/mnt/g/LegSA-GINS-project/clean_rebuild_202607/stages/CLEAN8_PROTOCOL_V3')
REF=Path('/mnt/g/LegSA-GINS-project/V3正文重绘_20261011/heading/source_data/BY2_input_heading_figure_match.csv.gz')
r=pd.read_csv(REF);refcols=['receiver_time_s','reference_heading_unwrapped_deg','reference_supported','reference_left_time_s','reference_right_time_s','reference_bracket_s']
r=r[refcols].copy();r['time_key']=r.receiver_time_s.round(6);assert r.time_key.is_unique
r.to_csv(P/'data/F10_EXISTING_REFERENCE_MATCHES.csv.gz',index=False,compression='gzip')
summaries=[]
for cid,rid in [('D31_seed_00','RUN_02985'),('D33_seed_00','RUN_03183'),('D35_seed_00','RUN_03381')]:
    run=ROOT/'03_NATIVE/V3R_CONTINUATION'/rid
    cfg=(run/'V3_RUNTIME_CONFIG.yaml').read_text();line=next(x for x in cfg.splitlines() if x.startswith('gnsspath:'))
    src=Path(line.split('"')[1]);rec=json.loads((run/'V3_NATIVE_SUMMARY.json').read_text())
    digest=hashlib.sha256(src.read_bytes()).hexdigest();assert digest==rec['provider_hashes']['gnsspath']
    shutil.copy2(src,P/'data'/f'{rid}_ORIGINAL_GNSS18.gnss')
    tr=pd.read_csv(run/'PORT_GNSS_UPDATE_TRACE.csv');tr['time_key']=tr.gnss_time.round(6);assert tr.time_key.is_unique
    a=pd.read_csv(src,sep=r'\s+',header=None);assert len(a.columns)==18
    x=a[(a[0]>=66)&(a[0]<340)].copy()
    z=pd.DataFrame({'receiver_time_s':x[0].to_numpy(),'elapsed_s':x[0].to_numpy()-66,'input_heading_deg':x[13].to_numpy(),'input_heading_std_deg':x[14].to_numpy(),'input_heading_valid':x[17].eq(1).to_numpy()})
    z['time_key']=z.receiver_time_s.round(6);z=z.merge(r.drop(columns='receiver_time_s'),on='time_key',how='left',validate='one_to_one',indicator='reference_match')
    z=z.merge(tr[['time_key','yaw_update','yaw_mode']],on='time_key',how='left',validate='one_to_one')
    supported=z.reference_match.eq('both')&z.reference_supported.fillna(False).astype(bool)
    z['display_supported']=z.input_heading_valid&supported
    z['input_error_deg']=(z.input_heading_deg-z.reference_heading_unwrapped_deg+180)%360-180
    z.loc[~z.display_supported,'input_error_deg']=np.nan
    z['native_heading_used']=z.yaw_update.eq(1)
    z.to_csv(P/'data'/f'{cid}_OBSERVATION_ERROR.csv.gz',index=False,compression='gzip')
    er=z.loc[z.display_supported,'input_error_deg'].to_numpy()
    summaries.append({'case_id':cid,'run_id':rid,'runtime_config_path':str(run/'V3_RUNTIME_CONFIG.yaml'),'original_gnss_path':str(src),'original_sha256':digest,'recorded_native_sha256':rec['provider_hashes']['gnsspath'],'hash_match':True,'original_rows':len(a),'window_rows':len(x),'valid_input_rows':int(z.input_heading_valid.sum()),'invalid_input_rows':int((~z.input_heading_valid).sum()),'reference_key_matches':int(z.reference_match.eq('both').sum()),'reference_key_unmatched':int(z.reference_match.ne('both').sum()),'valid_unscored_rows':int((z.input_heading_valid&~supported).sum()),'scored_rows':len(er),'input_error_rmse_deg_figure_layer':float(np.sqrt(np.mean(er*er))),'native_trace_rows':len(tr),'native_heading_used':int(z.native_heading_used.sum()),'not_dispatched':int(z.yaw_update.isna().sum()),'actual_gnss_updates_without_heading':int(z.yaw_update.eq(0).sum())})
pd.DataFrame(summaries).to_csv(P/'tables/F10_OBSERVATION_MATCH_COUNTS.csv',index=False)
protocol={'status':'DERIVED_FROM_SAVED_INPUT_AND_EXISTING_REFERENCE_MATCHES','new_statistics':'figure-layer observation-error samples and coverage counts; frozen navigation metrics unchanged','provider_columns_0_based':{'0':'receiver time, seconds','13':'body NED heading, degrees','14':'heading std, degrees','17':'heading validity 0/1'},'heading_convention':'Same frozen scalar body NED heading as previous observation comparison. Saved reference uses 90 deg minus ENU yaw, already unwrapped. Error is wrap(input-reference) to [-180,180).','join':'Exact existing receiver-time key rounded to 6 decimals; one-to-one left join. No new interpolation, extrapolation, time shift or fitted rotation. All input rows retained; unavailable or unsupported error shown as NaN.','reference_source':str(REF),'reference_sha256':hashlib.sha256(REF.read_bytes()).hexdigest(),'reference_support':'Reuse saved reference_supported and bracket fields; no support optimized per method.','solver_calls':0,'provider_calls':0,'evaluator_calls':0,'cases':summaries}
(P/'F10_OBSERVATION_MATCH_PROTOCOL.json').write_text(json.dumps(protocol,ensure_ascii=False,indent=2),encoding='utf8')
print(pd.DataFrame(summaries)[['case_id','window_rows','valid_input_rows','invalid_input_rows','reference_key_unmatched','valid_unscored_rows','scored_rows','actual_gnss_updates_without_heading','input_error_rmse_deg_figure_layer']].to_string(index=False))
