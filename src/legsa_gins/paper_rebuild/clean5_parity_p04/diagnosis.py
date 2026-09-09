"""P-04 read-only BY2 diagnostics from pinned existing errors, NAV and STD."""
from __future__ import annotations
import csv
import json
from pathlib import Path
import numpy as np
import pandas as pd
import yaml
from ...input_generation.imu_txt_builder import parse_sportmodestate_text,euler_rpy_deg_to_matrix,_matvec
from ..manifest import sha256_file
from ..clean5_parity.input_audit import verify_raw,decode_receiver,csv_rows
from .diagnosis_math import correlation,spectrum,bands,phase_bins,consistency,classify


def resolve(value,registry):
    for k in ['clean_root','raw_root','code_root']:value=str(value).replace('<'+k.upper()+'>',str(getattr(registry,k)))
    return Path(value)


def pinned(spec,registry):
    p=resolve(spec['path'],registry)
    if p.is_symlink() or sha256_file(p)!=spec['sha256']:raise ValueError('Diagnosis source identity mismatch '+str(p))
    return p


def write_json(path,value):
    with Path(path).open('x',encoding='utf8') as f:json.dump(value,f,ensure_ascii=False,indent=2,allow_nan=False)


def write_csv(path,rows):
    if isinstance(rows,pd.DataFrame):
        with Path(path).open('x',encoding='utf8',newline='') as f:rows.to_csv(f,index=False)
    else:
        with Path(path).open('x',encoding='utf8',newline='') as f:
            names=list(dict.fromkeys(k for r in rows for k in r));w=csv.DictWriter(f,fieldnames=names);w.writeheader();w.writerows(rows)


def numeric(path):
    with Path(path).open() as f:lines=[s for s in f if s.strip() and not s.lstrip().startswith(('%','#'))]
    from io import StringIO
    return pd.read_csv(StringIO(''.join(lines)),sep=r'\s+',header=None).to_numpy(float)


def exact_indices(source_time,target_time,tolerance=1e-7):
    s,t=np.asarray(source_time,float),np.asarray(target_time,float)
    if np.any(np.diff(s)<=0):raise ValueError('Nonmonotonic exact alignment source')
    j=np.clip(np.searchsorted(s,t),0,len(s)-1);p=np.maximum(j-1,0);j=np.where(abs(s[p]-t)<abs(s[j]-t),p,j)
    if np.any(abs(s[j]-t)>tolerance):raise ValueError('NAV/STD exact alignment failed')
    return j


def static_noise(registry,frozen_config):
    body=registry.sequences['BY2'].body_path;lock=verify_raw(registry,registry.sequences['BY2'],[body]);frames=parse_sportmodestate_text(body,max_messages=1000)
    if len(frames)!=1000:raise ValueError('Static noise requires exact first1000 complete messages')
    t=np.array([r['stamp_sec']*10**9+r['stamp_nanosec'] for r in frames],dtype=np.int64);dt=np.diff(t)*1e-9
    if np.any(dt<=0):raise ValueError('Invalid static dt')
    rot=euler_rpy_deg_to_matrix(-1,0,0);force=np.array([_matvec(rot,[r['accelerometer'][0],-r['accelerometer'][1],-r['accelerometer'][2]]) for r in frames]);gyro=np.array([_matvec(rot,[r['gyroscope'][0],-r['gyroscope'][1],-r['gyroscope'][2]]) for r in frames])
    text=Path(frozen_config).read_text();cfg=yaml.safe_load(text);tokens={k:next(s for s in text.splitlines() if s.split(':',1)[0].strip()==k) for k in ['arw','vrw','gbstd','abstd','corrtime']}
    vrw=force.std(axis=0)*np.sqrt(dt.mean())*60;arw=gyro.std(axis=0)*np.sqrt(dt.mean())*180/np.pi*60
    ratios=np.r_[vrw/np.array(cfg['vrw']),arw/np.array(cfg['arw'])]
    return {'data_mode':'real_by2_raw','synthetic_data_used':False,'semisynthetic_data_used':False,'report_only':True,'trace_used':False,'raw_source':lock,
        'sample_count':1000,'dt_mean_s':float(dt.mean()),'std_ddof':0,'frame':'FLU to FRD; RzRyRx [-1,0,0] degrees',
        'force_std_mps2':force.std(axis=0).tolist(),'gyro_std_radps':gyro.std(axis=0).tolist(),
        'implied_vrw_mps_sqrth':vrw.tolist(),'implied_arw_deg_sqrth':arw.tolist(),
        'frozen_vrw_mps_sqrth':cfg['vrw'],'frozen_arw_deg_sqrth':cfg['arw'],
        'vrw_ratio':(vrw/np.array(cfg['vrw'])).tolist(),'arw_ratio':(arw/np.array(cfg['arw'])).tolist(),
        'factor10_condition':bool(np.any((ratios>=10)|(ratios<=.1))),'parameter_tokens':tokens,
        'formula':'sample population std * sqrt(mean integer-nanosecond dt); SI density *60 to per sqrt hour, gyro additionally *180/pi',
        'boundary':'Fixed first1000 input-side descriptive noise proxy; includes non-white motion/bias effects; not independent noise identification or automatic tuning'}


def trace_velocity(path,base_time):
    frame=pd.read_csv(path);required=['time','lat','lon','height']
    if any(c not in frame for c in required):raise ValueError('Frozen trace columns unavailable')
    vals=frame[required].to_numpy(float)
    if not np.isfinite(vals).all() or np.any(np.diff(vals[:,0])<=0):raise ValueError('Trace incomplete/nonmonotonic; no epoch deletion')
    t=vals[:,0]-base_time;lat,lon=np.deg2rad(vals[:,1]),np.deg2rad(vals[:,2]);h=vals[:,3];a=6378137.;e2=6.6943799901413165e-3
    r=a/np.sqrt(1-e2*np.sin(lat)**2);xyz=np.column_stack(((r+h)*np.cos(lat)*np.cos(lon),(r+h)*np.cos(lat)*np.sin(lon),(r*(1-e2)+h)*np.sin(lat)))
    l,o=lat[0],lon[0];R=np.array([[-np.sin(l)*np.cos(o),-np.sin(l)*np.sin(o),np.cos(l)],[-np.sin(o),np.cos(o),0]])
    ne=(xyz-xyz[0])@R.T;position=np.column_stack((ne,h));v=np.column_stack([np.gradient(position[:,k],t,edge_order=1) for k in range(3)])
    return t,v,{'native_count':len(t),'max_gap_s':float(np.diff(t).max()),'derivative':'numpy.gradient native irregular times, central interior, first-order endpoints; no smoothing',
        'vertical':'native ellipsoidal height derivative, positive Up','horizontal':'fixed first-trace-point tangent N/E ECEF coordinate derivative',
        'status':'DERIVED_TRACE_DIFFERENCE_DIAGNOSTIC_ONLY','independent_velocity_truth':False}


def run_diagnosis(registry,contract,output_root,code_commit):
    spec=contract['p04']['diagnosis'];out=Path(output_root)/'01_ANALYSIS';out.mkdir(parents=True,exist_ok=False)
    all_specs=[spec['trace'],spec['frozen_config']]+[s[k] for s in spec['sources'] for k in ['error_series','nav','std','updates','manifest'] if s.get(k)]
    for source in all_specs:pinned(source,registry)
    frozen=pinned(spec['frozen_config'],registry);noise=static_noise(registry,frozen)
    if spec.get('static_noise'):
        original=json.loads(pinned(spec['static_noise'],registry).read_text())
        if noise!=original:raise ValueError('Preregistered raw noise calculation changed')
    tt,tv,tinfo=trace_velocity(pinned(spec['trace'],registry),1772784000.)
    write_csv(out/'TRACE_NATIVE_DIFFERENCE_VELOCITY.csv',pd.DataFrame({'time':tt,'north_mps':tv[:,0],'east_mps':tv[:,1],'up_mps':tv[:,2]}))
    seq=registry.sequences['BY2'];raw=seq.fix_root/'gnss1-raw.csv';status=seq.fix_root/'gnss1-status.csv';raw_locks=verify_raw(registry,seq,[raw,status]);_,pvt=decode_receiver(raw)
    weeks={int(float(r['time_gps_wno'])) for r in csv_rows(status)}
    if len(weeks)!=1:raise ValueError('Unexpected GPS week span')
    week=weeks.pop();keys=sorted(pvt);pt=np.array([315964800+week*604800+k/1000-18-1772784000 for k in keys]);pdv=np.array([pvt[k]['velocity_mps'][2] for k in keys]);mask=(pt>=66)&(pt<=340)&(pt>=tt[0])&(pt<=tt[-1]);pred=-np.interp(pt[mask],tt,tv[:,2]);delta=pdv[mask]-pred
    pvt_noise={'status':'AVAILABLE','count':int(mask.sum()),'std_mps':float(delta.std()),'mean_mps':float(delta.mean()),'rmse_mps':float(np.sqrt(np.mean(delta**2))),
        'sign':'PVT velD minus negative native-height derivative','support':'same iTOW UTC epoch; frozen 66..340 window; no shift search','raw_sources':raw_locks,'reference_velocity_status':'DERIVED_TRACE_DIFFERENCE_DIAGNOSTIC_ONLY'}
    write_csv(out/'PVT_MINUS_TRACE_VERTICAL_VELOCITY.csv',pd.DataFrame({'time':pt[mask],'PVT_velD_mps':pdv[mask],'trace_derived_down_mps':pred,'difference_mps':delta}))
    runs=[];cons_rows=[];band_rows=[];corr_rows=[];phase_rows=[];nis=[]
    for source in spec['sources']:
        rid=source['run_id'];folder=out/rid;folder.mkdir();err=pd.read_csv(pinned(source['error_series'],registry));err=err[(err.time>=66)&(err.time<=340)].copy();t=err.time.to_numpy(float)
        if not len(t) or not np.isfinite(err.to_numpy(float)).all() or np.any(np.diff(t)<=0):raise ValueError('Invalid frozen error support '+rid)
        nav=numeric(pinned(source['nav'],registry));ix=exact_indices(nav[:,1],t);navv=nav[ix,5:8].copy();navv[:,2]*=-1
        if t[0]<tt[0] or t[-1]>tt[-1]:raise ValueError('Trace derivative extrapolation refused')
        refv=np.column_stack([np.interp(t,tt,tv[:,k]) for k in range(3)])
        sp,acf,fft=spectrum(t,err.err_u_m);write_csv(folder/'ACF.csv',acf);write_csv(folder/'FFT.csv',fft)
        run={'run_id':rid,**sp,'sources':source,'classification_basis':'preregistered descriptive operational labels, not causal proof'};coupling={}
        for axis,col in [('u','err_u_m'),('n','err_n_m'),('e','err_e_m')]:
            bd,slow,fast=bands(t,err[col]);band_rows.append({'run_id':rid,'axis':axis,**bd})
            write_csv(folder/('BANDS_'+axis+'.csv'),pd.DataFrame({'time':t,'error':err[col],'slow_10s_centered':slow,'fast_residual':fast}))
            if axis=='u':run['up_bands']=bd
            for name,values in [('roll',err.roll_err_deg),('pitch',err.pitch_err_deg),('nav_up',navv[:,2]),('trace_up',refv[:,2])]:
                co=correlation(err[col],values);corr_rows.append({'run_id':rid,'axis':axis,'correlate':name,**co})
                if axis=='u':coupling[name]=co['r']
        phase={'status':'UNAVAILABLE','reason':'actual GNSS update timestamps not retained'}
        if source.get('updates'):
            updates=pd.read_csv(pinned(source['updates'],registry));selected=updates[updates.position_update==1]
            phase,pr=phase_bins(t,err.err_u_m,selected.gnss_time);phase_rows.extend({'run_id':rid,**r} for r in pr)
            missing=['innovation_n','innovation_e','innovation_d','predicted_innovation_covariance']
            innovation={'run_id':rid,'status':'UNAVAILABLE','NIS':'UNAVAILABLE','innovation_acf_lags_1_5':'UNAVAILABLE','height_innovation_vs_err_u':'UNAVAILABLE','missing_fields':missing,'available_fields':list(updates.columns),'reason':'Only residual norms retained; no vector or covariance substitution permitted'}
            if rid=='F02_V0':
                manifest=json.loads(pinned(source['manifest'],registry).read_text());run['no_RV_control_verified']=manifest['enable_receiver_velocity_update'] is False and int(updates.velocity_update.sum())==0
                if not run['no_RV_control_verified']:raise ValueError('F02 is not no-RV control')
        else:innovation={'run_id':rid,'status':'UNAVAILABLE','reason':'No PORT_GNSS_UPDATE_TRACE.csv retained'}
        nis.append(innovation);over=False
        if rid in ['V0_A04','V2_A04']:
            std=numeric(pinned(source['std'],registry));si=exact_indices(std[:,0],t)
            if std.shape[1]!=22:raise ValueError('STD mapping expected22 columns')
            for group,columns,errors in [('position',[1,2,3],np.column_stack([err.err_n_m,err.err_e_m,err.err_u_m])),('velocity',[4,5,6],navv-refv),('attitude',[7,8,9],err[['roll_err_deg','pitch_err_deg','yaw_err_deg']].to_numpy(float))]:
                for k,column in enumerate(columns):
                    axis=(['n','e','u'] if group!='attitude' else ['roll','pitch','yaw'])[k];cs=consistency(errors[:,k],std[si,column]);cons_rows.append({'run_id':rid,'group':group,'axis':axis,**cs,'reference_status':'DERIVED_TRACE_DIFFERENCE_DIAGNOSTIC_ONLY' if group=='velocity' else 'EXISTING_FROZEN_ERRORS'})
                    sigma=std[si,column];normal=np.full(len(t),np.nan);valid=np.isfinite(errors[:,k])&np.isfinite(sigma)&(sigma>0);normal[valid]=np.abs(errors[valid,k])/sigma[valid]
                    write_csv(folder/('CONSISTENCY_'+group+'_'+axis+'.csv'),pd.DataFrame({'time':t,'signed_error':errors[:,k],'predicted_std':sigma,'abs_error_over_std':normal,'valid_std':valid}))
                    if group=='position' and axis=='u':
                        over=cs['valid_n']>0 and cs['median_std']<=.1 and cs['error_rmse']>=.1 and cs['median_abs_error_over_std']>3;run['up_consistency']=cs
            run['A2_classification']='OVERCONFIDENT' if over else 'NOT_OVERCONFIDENT_BY_PREREGISTERED_RULE'
        run.update(phase=phase,up_correlation=coupling,overconfident=over,classification=classify(overconfident=over,phase=phase,coupling=coupling,slow_fraction=run['up_bands']['slow_variance_fraction'],pvt_noise=pvt_noise['std_mps']));runs.append(run)
        write_json(folder/'DIAGNOSIS.json',run)
    trigger=any(r['overconfident'] for r in runs) and noise['factor10_condition']
    result={'status':'COMPLETED','code_commit':code_commit,'data_mode':'real_by2_raw','synthetic_data_used':False,'semisynthetic_data_used':False,'trace_used_online':False,'solver_invocations':0,'evaluator_invocations':0,'reference_velocity':tinfo,'runs':runs,'consistency':cons_rows,'bands':band_rows,'correlations':corr_rows,'update_phase_bins':phase_rows,'innovations':nis,'static_noise':noise,'pvt_velocity_difference':pvt_noise,'V2n_triggered':trigger,'V2n_status':'REGISTERED_NOT_EXECUTED' if trigger else 'NOT_TRIGGERED','V2n_execution_count':0,'fit_used':False,'epoch_deleted_for_metric':False}
    for name,rows in [('CONSISTENCY.csv',cons_rows),('BANDS.csv',band_rows),('CORRELATIONS.csv',corr_rows),('UPDATE_PHASE_BINS.csv',phase_rows)]:write_csv(out/name,rows)
    write_json(out/'INNOVATION_AVAILABILITY.json',nis);write_json(out/'STATIC_NOISE.json',noise);write_json(out/'VERTICAL_DIAGNOSIS.json',result)
    for source in all_specs:pinned(source,registry)
    return result
