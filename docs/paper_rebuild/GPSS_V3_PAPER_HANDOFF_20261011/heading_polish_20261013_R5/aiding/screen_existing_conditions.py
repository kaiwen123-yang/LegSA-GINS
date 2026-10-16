"""Inventory all registered conditions using saved metrics, logs and retained series."""
from pathlib import Path
import json
import pandas as pd,numpy as np
P=Path(__file__).resolve().parent
T=Path('/mnt/g/LegSA-GINS-project/V3正文精修_20261012_R3/aiding/tables')
ROOT=Path('/mnt/g/LegSA-GINS-project/clean_rebuild_202607/stages/CLEAN8_PROTOCOL_V3/03_NATIVE')
core=pd.read_csv(T/'CORE5951.csv');defs=pd.read_csv(T/'ALL61_PHYSICAL_INPUT_MAP.csv');av=pd.read_csv(T/'ERROR_SERIES_AVAILABILITY6468.csv')
records=[];sources=[]
for _,definition in defs.iterrows():
    typ=definition.degradation_type_id;cid='C00_clean_normal' if typ=='CLEAN' else typ+'_seed_00'
    chosen=core[core.case_id.eq(cid)&core.internal_method_id.isin(['F04','A04'])].set_index('internal_method_id')
    assert set(chosen.index)=={'F04','A04'}
    full=chosen.loc['F04'];off=chosen.loc['A04'];run=ROOT/full.run_id
    if not run.exists():run=ROOT/'V3R_CONTINUATION'/full.run_id
    weight=run/'SOURCE_AWARE_WEIGHT_TRACE.csv.gz'
    if not weight.exists():weight=run/'SOURCE_AWARE_WEIGHT_TRACE.csv'
    full_series=Path(av.loc[av.run_id.eq(full.run_id),'path'].iloc[0]);off_series=Path(av.loc[av.run_id.eq(off.run_id),'path'].iloc[0])
    row={'type':typ,'condition_name':definition.degradation_type_name,'physical_input_group':definition.physical_input_group,'active_path':bool(definition.registered_active_measurement_path),'duplicate_of':definition.physical_duplicate_of,'case_id':cid,'full_run':full.run_id,'off_run':off.run_id,'full_status':full.evaluation_status,'off_status':off.evaluation_status,'full_yaw_rmse_deg':full.yaw_rmse_deg,'off_yaw_rmse_deg':off.yaw_rmse_deg,'yaw_reduction_deg':off.yaw_rmse_deg-full.yaw_rmse_deg,'full_H_rmse_m':full.horizontal_rmse_m,'off_H_rmse_m':off.horizontal_rmse_m,'full_series_exists':full_series.exists(),'off_series_exists':off_series.exists(),'actual_weight_trace_exists':weight.exists(),'weight_trace_rows':0,'native_directory':str(run),'full_series_path':str(full_series),'off_series_path':str(off_series),'trace_path':str(weight),'parameters_json':definition.degradation_parameters_json,'exposure_note':definition.exposure_note}
    if weight.exists():
        d=pd.read_csv(weight)
        row['weight_trace_rows']=len(d)
        for source,q in d.groupby('source_id'):
            q=q[(q.time>=66)&(q.time<=186)]
            if len(q):
                sources.append({'type':typ,'case_id':cid,'source_id':source,'first120_rows':len(q),'multiplier_median':q.combined_R_scale.median(),'multiplier_min':q.combined_R_scale.min(),'multiplier_max':q.combined_R_scale.max(),'innovation_median_native_unit':q.residual_norm.median(),'innovation_max_native_unit':q.residual_norm.max(),'base_R_trace_median_native_unit2':q.base_R_trace.median()})
    variants=core[core.degradation_type_id.eq(typ)&core.internal_method_id.isin(['F04','A04'])]
    for method,label in [('F04','full'),('A04','off')]:
        x=variants[variants.internal_method_id.eq(method)]
        row[label+'_registered']=len(x);row[label+'_completed']=int(x.evaluation_status.eq('COMPLETED').sum());row[label+'_conditional_median_yaw_deg']=x.yaw_rmse_deg.median() if x.yaw_rmse_deg.notna().any() else np.nan
    records.append(row)
out=pd.DataFrame(records);out.to_csv(P/'ALL61_CONDITION_SCREEN.csv',index=False);pd.DataFrame(sources).to_csv(P/'ALL61_FIRST120_SOURCE_BEHAVIOUR.csv',index=False)
print(out[['type','physical_input_group','full_status','full_yaw_rmse_deg','off_yaw_rmse_deg','yaw_reduction_deg','full_H_rmse_m','off_H_rmse_m','full_series_exists','off_series_exists','actual_weight_trace_exists']].to_string(index=False))
(P/'SCREENING_RECEIPT.json').write_text(json.dumps({'registered_types_read':len(out),'core_rows_read':len(core),'full_weight_logs_read':int(out.actual_weight_trace_exists.sum()),'full_log_rows_read':int(out.weight_trace_rows.sum()),'complete_paired_seed00_series':int((out.full_series_exists&out.off_series_exists).sum()),'selection_not_based_on_max_gain':'All fixed seed00 rows read before choosing physical mechanisms; excluded no-active-path controls and duplicate conditions remain listed.','solver_calls':0,'provider_calls':0,'evaluator_calls':0},indent=2),encoding='utf8')
