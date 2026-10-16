from pathlib import Path
import pandas as pd,json,numpy as np
ROOT=Path('/mnt/g/LegSA-GINS-project/clean_rebuild_202607/stages/CLEAN8_PROTOCOL_V3/03_NATIVE/V3R_CONTINUATION')
TAB=Path('/mnt/g/LegSA-GINS-project/V3正文精修_20261012_R3/aiding/tables')
P=Path(__file__).resolve().parent
rec=[]
for case,run in [('Position noise','RUN_01401'),('Bad heading uncertainty','RUN_03678'),('Position and velocity conflict','RUN_05757')]:
    d=pd.read_csv(ROOT/run/'SOURCE_AWARE_WEIGHT_TRACE.csv.gz')
    for source,s in d.groupby('source_id'):
        for lo,hi in [(0,10),(10,120),(120,274)]:
            q=s[(s.time-66>=lo)&(s.time-66<hi)]
            rec.append({'condition':case,'source':source,'start_s':lo,'end_s':hi,'rows':len(q),'R_min':q.combined_R_scale.min(),'R_median':q.combined_R_scale.median(),'R_max':q.combined_R_scale.max(),'innovation_norm_median':q.residual_norm.median(),'innovation_norm_max':q.residual_norm.max(),'base_R_trace_median':q.base_R_trace.median(),'LSIM_median':q.lsim_R_scale.median(),'OIM_median':q.oim_R_scale.median()})
pd.DataFrame(rec).to_csv(P/'TRACE_PROFILE.csv',index=False)
print(pd.DataFrame(rec)[pd.DataFrame(rec).source.isin(['receiver_position','dual_antenna_yaw','go2_horizontal_velocity'])].to_string(index=False))
p=pd.read_csv(TAB/'ALL2164_ORIGINAL_ABLATION_PAIRS.csv');p=p[p.module.eq('SA')]
stats=[]
for typ in ['D15','D38','D59','ALL']:
    z=p if typ=='ALL' else p[p.degradation_type_id.eq(typ)]
    q=z[z.joint_finite];gain=q.ablation_yaw_rmse_deg-q.candidate_yaw_rmse_deg
    stats.append({'condition':typ,'registered':len(z),'joint_completed':len(q),'gain_median_deg':gain.median(),'gain_Q25_deg':gain.quantile(.25),'gain_Q75_deg':gain.quantile(.75),'full_lower_yaw':int((gain>1e-9).sum()),'equal_yaw_at_1e_9':int((abs(gain)<=1e-9).sum()),'full_higher_yaw':int((gain< -1e-9).sum()),'full_only_completed':int((z.candidate_status.eq('COMPLETED')&~z.ablation_status.eq('COMPLETED')).sum()),'both_failed':int((~z.candidate_status.eq('COMPLETED')&~z.ablation_status.eq('COMPLETED')).sum())})
pd.DataFrame(stats).to_csv(P/'PAIR_PROFILE.csv',index=False)
print(pd.DataFrame(stats).to_string(index=False))
