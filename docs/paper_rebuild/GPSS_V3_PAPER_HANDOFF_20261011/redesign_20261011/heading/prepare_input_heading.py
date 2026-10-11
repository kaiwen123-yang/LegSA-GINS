"""A figure-layer observation comparison from frozen providers and saved reference display data."""
from pathlib import Path
import json,hashlib
import numpy as np,pandas as pd
O=Path(__file__).parent; (O/'source_data').mkdir(exist_ok=True)
R=Path('/mnt/g/LegSA-GINS-project/V3五问题论文组图_20261011/heading')
refpath=Path('/mnt/g/LegSA-GINS-project/V3论文组图_20261008/redesign_20261009/figures/data/P02_heading_display_values.csv.gz')
ref=pd.read_csv(refpath);rows=[];profile=[];allmatch=[]
for seq,t0,t1 in [('BY2',66.,340.),('BY2H',413.,683.),('BY2O',3186.,3563.)]:
 paths=json.loads((O/(seq+'_input_path.json')).read_text());p=Path(paths['provider']);d=Path(paths['native']);tp=d/'PORT_GNSS_UPDATE_TRACE.csv.gz'
 if not tp.exists():tp=d/'PORT_GNSS_UPDATE_TRACE.csv'
 inp=pd.read_csv(p,sep=r'\s+',header=None,comment='#');x=inp[(inp[0]>=t0)&(inp[0]<t1)].copy();valid=x[17].eq(1);tr=pd.read_csv(tp)
 rf=ref[ref.sequence.eq(seq)];rt=rf.time_s.to_numpy();rv=rf.truth_heading_display_deg.to_numpy();assert np.all(np.diff(rt)>0);tx=x[0].to_numpy();ix=np.searchsorted(rt,tx);left=np.maximum(0,ix-1);right=np.minimum(len(rt)-1,ix)
 ok=(tx>=rt[0])&(tx<=rt[-1])&((rt[right]-rt[left])<=.1)
 ry=np.interp(tx,rt,rv);error=(x[13].to_numpy()-ry+180)%360-180;error[~ok|~valid.to_numpy()]=np.nan
 # GNSS provider tokens are stored at receiver epoch time; no fitted shift or bias.
 bytime={round(float(a),6):b for a,b in zip(tr.gnss_time,tr.yaw_mode)};mode=[bytime.get(round(float(t),6),'NOT_DISPATCHED') for t in tx];accepted=np.isin(mode,['NORMAL','DOWNWEIGHT']);attempt=tr.yaw_mode.isin(['NORMAL','DOWNWEIGHT','REJECT']).sum()
 out=pd.DataFrame({'sequence':seq,'receiver_time_s':tx,'elapsed_s':tx-t0,'input_heading_deg':x[13].to_numpy(),'input_heading_valid':valid.to_numpy(),'reference_heading_unwrapped_deg':ry,'reference_supported':ok,'reference_left_time_s':rt[left],'reference_right_time_s':rt[right],'reference_bracket_s':rt[right]-rt[left],'input_error_deg':error,'yaw_mode':mode,'accepted':accepted})
 out.to_csv(O/'source_data'/f'{seq}_input_heading_figure_match.csv.gz',index=False)
 er=error[np.isfinite(error)];ac=error[accepted&np.isfinite(error)]
 row={'sequence':seq,'method':'Position-derived input','available':int(valid.sum()),'denominator':len(x),'coverage_percent':float(100*valid.mean()),'scored':len(er),'rmse_deg':float(np.sqrt(np.mean(er**2))),'median_abs_deg':float(np.median(np.abs(er))),'p95_abs_deg':float(np.percentile(np.abs(er),95)),'accepted':int(accepted.sum()),'attempted':int(attempt),'accepted_scored':len(ac),'accepted_rmse_deg':float(np.sqrt(np.mean(ac**2))),'accepted_coverage_percent':float(100*accepted.mean())};rows.append(row)
 print(row)
 profile.append({'sequence':seq,'provider':str(p),'provider_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'native_trace':str(tp),'native_trace_rows':len(tr),'original_input_rows':len(inp),'formal_window':[t0,t1],'valid_unscored':int((valid&~ok).sum()),'reference_max_supported_bracket_s':float((rt[right]-rt[left])[ok].max())})
 allmatch.append(out)
pd.DataFrame(rows).to_csv(O/'source_data/INPUT_HEADING_SUMMARY.csv',index=False)
(O/'INPUT_HEADING_MATCH_PROTOCOL.json').write_text(json.dumps({'purpose':'New figure-layer observation statistics; frozen evaluation tables are not modified.','reference':str(refpath),'reference_sha256':hashlib.sha256(refpath.read_bytes()).hexdigest(),'heading_convention':'Frozen GNSS18 scalar NED body heading; saved reference heading uses 90 - ENU yaw. Both wrap at 360 degrees.','reference_alignment':'Linear interpolation of saved already-unwrapped reference heading at receiver time. No extrapolation; reference bracket <= 0.1 s; no optimized time/angle offset.','error':'wrap(input heading - reference heading) in [-180,180)','support':'Input valid denominator is all original receiver epochs in [formal_start, formal_end), reproducing native expected input counts 1370/1350/1885. Error uses finite valid reference-supported input only. Accepted means native NORMAL or DOWNWEIGHT update.','provider_columns':'0=time_s,13=yaw_deg,14=yaw_std_deg,15=position_valid,16=velocity_valid,17=yaw_valid; checked against original providers and GNSS loader.','difference_from_external':'External retained evaluator times are approximately receiver epoch minus 0.002 s and have their own saved validity; this figure compares processing routes on the same recording/window, not identical timestamps or a common support winner.','solver_calls':0,'evaluator_calls':0,'provider_calls':0,'source_profile':profile},ensure_ascii=False,indent=2))
