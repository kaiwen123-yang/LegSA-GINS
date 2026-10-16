"""Read selected frozen inputs, logs and outcomes after the complete condition screen."""
from pathlib import Path
import hashlib,json,shutil
import numpy as np,pandas as pd
P=Path(__file__).resolve().parent
T=Path('/mnt/g/LegSA-GINS-project/V3正文精修_20261012_R3/aiding/tables')
N=Path('/mnt/g/LegSA-GINS-project/clean_rebuild_202607/stages/CLEAN8_PROTOCOL_V3/03_NATIVE')
for k in ['data','tables','qa','figures','preview']:(P/k).mkdir(exist_ok=True)
screen=pd.read_csv(P/'ALL61_CONDITION_SCREEN.csv');core=pd.read_csv(T/'CORE5951.csv');av=pd.read_csv(T/'ERROR_SERIES_AVAILABILITY6468.csv')
allpairs=pd.read_csv(T/'ALL2164_ORIGINAL_ABLATION_PAIRS.csv')
selected=['D15','D38','D53'];meta=[];input_checks=[];provider_cache={}

def native(rid):
    d=N/rid
    return d if d.exists() else N/'V3R_CONTINUATION'/rid

def provider(rid,key):
    d=native(rid);summary=json.loads((d/'V3_NATIVE_SUMMARY.json').read_text());config=(d/'V3_RUNTIME_CONFIG.yaml').read_text()
    path=Path(next(x for x in config.splitlines() if x.startswith(key+':')).split('"')[1])
    if str(path) not in provider_cache:
        digest=hashlib.sha256(path.read_bytes()).hexdigest();provider_cache[str(path)]=digest
    digest=provider_cache[str(path)];assert digest==summary['provider_hashes'][key]
    input_checks.append({'run_id':rid,'role':key,'path':str(path),'sha256':digest,'native_recorded_sha256':summary['provider_hashes'][key],'hash_match':True})
    return path

def ecef(lla):
    lat=np.deg2rad(lla[:,0]);lon=np.deg2rad(lla[:,1]);h=lla[:,2]
    a=6378137.;e2=6.6943799901413165e-3;n=a/np.sqrt(1-e2*np.sin(lat)**2)
    return np.column_stack([(n+h)*np.cos(lat)*np.cos(lon),(n+h)*np.cos(lat)*np.sin(lon),(n*(1-e2)+h)*np.sin(lat)])

clean_gnss=pd.read_csv(provider('RUN_00004','gnsspath'),sep=r'\s+',header=None)
clean_vel=pd.read_csv(provider('RUN_00004','go2_horizontal_velocity_prior_path'))
for typ in selected:
    s=screen[screen.type.eq(typ)].iloc[0];full=s.full_run;off=s.off_run
    for rid in [full,off]:
        row=av[av.run_id.eq(rid)].iloc[0];d=pd.read_csv(Path(row.path));assert len(d)==56642
        d[['time','yaw_err_deg','horizontal_err_m']].to_csv(P/'data'/f'{rid}_errors.csv.gz',index=False,compression='gzip')
    trpath=native(full)/'SOURCE_AWARE_WEIGHT_TRACE.csv.gz';shutil.copy2(trpath,P/'data'/f'{full}_source_trace.csv.gz');tr=pd.read_csv(trpath)
    upd=pd.read_csv(native(full)/'PORT_GNSS_UPDATE_TRACE.csv');upd.to_csv(P/'data'/f'{full}_update_trace.csv',index=False)
    if typ in ['D15','D38']:
        path=provider(full,'gnsspath');bad=pd.read_csv(path,sep=r'\s+',header=None)
        assert len(bad)==len(clean_gnss)==1510 and np.array_equal(bad[0].round(6),clean_gnss[0].round(6))
        if typ=='D15':
            change=np.linalg.norm(ecef(bad[[1,2,3]].to_numpy())-ecef(clean_gnss[[1,2,3]].to_numpy()),axis=1)
            sigma=np.sqrt((bad[[4,5,6]]**2).sum(axis=1));valid=bad[15].eq(1).to_numpy();unit='m';metric='3D Euclidean change in original position input relative to clean input (WGS84 ECEF distance)'
        else:
            signed=(bad[13].to_numpy()-clean_gnss[13].to_numpy()+180)%360-180;change=np.abs(signed)
            sigma=bad[14].to_numpy();valid=bad[17].eq(1).to_numpy();unit='deg';metric='Absolute wrapped change in scalar NED body-heading input relative to clean input'
        inp=pd.DataFrame({'time':bad[0].to_numpy(),'elapsed_s':bad[0].to_numpy()-66,'input_change_magnitude':change,'reported_std_norm':sigma,'input_valid':valid})
    else:
        path=provider(full,'go2_horizontal_velocity_prior_path');bad=pd.read_csv(path)
        assert len(bad)==len(clean_vel)==63278 and np.array_equal(bad.time.round(9),clean_vel.time.round(9))
        change=np.hypot(bad.vn-clean_vel.vn,bad.ve-clean_vel.ve)
        sigma=np.hypot(bad.std_vn,bad.std_ve);valid=bad.valid.eq(1).to_numpy();unit='m/s';metric='Horizontal NED velocity input change norm relative to the unchanged clean body-velocity prior'
        inp=pd.DataFrame({'time':bad.time,'elapsed_s':bad.time-66,'input_change_magnitude':change,'reported_std_norm':sigma,'input_valid':valid})
    inp.to_csv(P/'data'/f'{typ}_input_change.csv.gz',index=False,compression='gzip')
    display=inp[inp.elapsed_s.between(0,120)]
    stats=core[core.degradation_type_id.eq(typ)&core.internal_method_id.isin(['F04','A04'])]
    stats.to_csv(P/'tables'/f'{typ}_all_nine_original_metrics.csv',index=False)
    exact=stats[stats.case_id.eq(typ+'_seed_00')].set_index('internal_method_id')
    small=tr[tr.time.between(66,186)]
    q=[]
    for src,label in [('receiver_position','Position'),('go2_horizontal_velocity','Body v'),('dual_antenna_yaw','Heading')]:
        v=small.loc[small.source_id.eq(src),'combined_R_scale'];mi,q1,md,q3,ma=v.quantile([0,.25,.5,.75,1])
        q.append({'type':typ,'source':src,'label':label,'n_recorded_updates':len(v),'minimum':mi,'q25':q1,'median':md,'q75':q3,'maximum':ma})
    pd.DataFrame(q).to_csv(P/'tables'/f'{typ}_actual_covariance_summary.csv',index=False)
    row={'type':typ,'case_id':typ+'_seed_00','full_run':full,'off_run':off,'condition_name':s.condition_name,'input_change_definition':metric,'input_unit':unit,'original_input_rows':len(inp),'plotted_time_interval_s':[0,120],'input_display_rows':len(display),'input_display_valid_rows':int(display.input_valid.sum()),'input_display_invalid_rows':int((~display.input_valid).sum()),'input_time_keys_identical_to_clean':True,'input_reference':'existing clean provider, not geographical truth','full_trace_rows':len(tr),'display_source_update_counts':{a['label']:a['n_recorded_updates'] for a in q},'full_window_s':[66,340],'off_yaw_rmse_deg':float(exact.loc['A04','yaw_rmse_deg']),'full_yaw_rmse_deg':float(exact.loc['F04','yaw_rmse_deg']),'yaw_rmse_change_deg':float(exact.loc['F04','yaw_rmse_deg']-exact.loc['A04','yaw_rmse_deg']),'off_H_rmse_m':float(exact.loc['A04','horizontal_rmse_m']),'full_H_rmse_m':float(exact.loc['F04','horizontal_rmse_m']),'H_rmse_change_m':float(exact.loc['F04','horizontal_rmse_m']-exact.loc['A04','horizontal_rmse_m']),'full_completed_of_nine':int(stats[stats.internal_method_id.eq('F04')].evaluation_status.eq('COMPLETED').sum()),'off_completed_of_nine':int(stats[stats.internal_method_id.eq('A04')].evaluation_status.eq('COMPLETED').sum()),'selection':'Fixed seed00, selected by distinct position/heading/body-velocity mechanism and complete retained logs; not by maximum gain.'}
    meta.append(row)
pd.DataFrame([{k:v for k,v in x.items() if not isinstance(v,(list,dict))} for x in meta]).to_csv(P/'tables/THREE_CASE_MAIN_METRICS.csv',index=False)
(P/'SELECTED_CASES.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding='utf8')
(P/'INPUT_PROVENANCE.json').write_text(json.dumps({'inputs':input_checks,'new_derived_quantity':'Input changes relative to existing clean providers plus reported uncertainty and summaries of saved weighting logs. This is not error against truth and not a new native experiment.','new_solver_provider_evaluator_calls':0},ensure_ascii=False,indent=2),encoding='utf8')
weight=allpairs[allpairs.module.eq('SA')];weight.to_csv(P/'tables/ALL541_WEIGHTING_PAIRS.csv',index=False)
selpairs=weight[weight.degradation_type_id.isin(selected)];selpairs.to_csv(P/'tables/SELECTED27_WEIGHTING_PAIRS.csv',index=False)
joint=weight[weight.joint_finite];gain=joint.ablation_yaw_rmse_deg-joint.candidate_yaw_rmse_deg
(P/'OVERALL_SCOPE.json').write_text(json.dumps({'registered':len(weight),'joint_complete':len(joint),'full_lower_yaw':int((gain>0).sum()),'full_higher_yaw':int((gain<0).sum()),'median_yaw_reduction_deg':float(gain.median()),'extra_full_completions':int((weight.candidate_status.eq('COMPLETED')&~weight.ablation_status.eq('COMPLETED')).sum()),'full_source_tables_reference':str(T),'selected_conditions':selected,'native_calls':0},indent=2),encoding='utf8')
print(pd.read_csv(P/'tables/THREE_CASE_MAIN_METRICS.csv')[['type','full_run','off_run','off_yaw_rmse_deg','full_yaw_rmse_deg','off_H_rmse_m','full_H_rmse_m','input_display_rows','input_display_valid_rows']].to_string(index=False))
