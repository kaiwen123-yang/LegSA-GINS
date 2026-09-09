import numpy as np
import pandas as pd
from legsa_gins.paper_rebuild.clean5_parity_p04.evaluation import metrics,decomposition,LADDER,write_tables
from legsa_gins.paper_rebuild.clean5_parity.decomposition import METRICS


def test_generalization_crossversion_and_sameversion_are_distinct():
    rows={v:[] for v in ['v2','v3']}
    for v in rows:
        for d in ['BY2','BY2H','BY2O']:
            for k,(variant,method) in enumerate(LADDER):
                rows[v].append({'dataset_id':d,'variant_id':variant,'method_id':method,'source_row':f'{d}:{v}:{k}',**{m:10-k-(2 if v=='v3' else 0) for m in METRICS}})
    primary,versions=decomposition(rows,{'BY2O':'ONE_RECEIVER_VELOCITY_ROW_CHANGED'})
    assert len(primary)==9 and len(versions)==18
    combined=next(r for r in primary if r['dataset_id']=='BY2' and r['term']=='rate_point_IMU')
    assert combined['horizontal_rmse_m']==4
    assert combined['left_evaluator_contract']=='evaluator_contract_v2' and combined['right_evaluator_contract']=='evaluator_contract_v3'
    same=next(r for r in versions if r['dataset_id']=='BY2' and r['term']=='rate_IMU_same_point_contract')
    assert same['horizontal_rmse_m']==2
    assert all(r['input_exception_confounds']=='ONE_RECEIVER_VELOCITY_ROW_CHANGED' for r in primary if r['dataset_id']=='BY2O')
    assert all(r['time_term_footnote']=='时标项含 RV 同历元重配' for r in primary+versions if r['term']=='time')
    assert all('time_term_footnote' not in r for r in primary+versions if r['term']!='time')


def test_window_denominator_does_not_use_by2_window():
    t=np.array([414.,415.,416.]);nav=np.zeros((5,11));nav[:,1]=[412,414,415,416,684]
    errors=pd.DataFrame({'time':t,**{k:np.ones(3) for k in ['err_n_m','err_e_m','err_u_m','roll_err_deg','pitch_err_deg','yaw_err_deg','horizontal_err_m','position_3d_err_m']}})
    r=metrics(errors,nav,{},[413,683],3)
    assert r['output_epoch_count']==3 and r['coverage_ratio']==1
    assert r['sequence_window_start_s']==413


def test_mixed_dataset_tables_do_not_merge_profiles(tmp_path):
    rows=[]
    for d,value in [('BY2H',1.),('BY2O',4.)]:
        for variant,method in LADDER:
            rows.append({'dataset_id':d,'case_id':d+'_NATURAL','variant_id':variant,'method_id':method,'run_id':d+variant+method,'source_row':'frozen:2','evaluator_contract':'evaluator_contract_v2','evaluation_status':'COMPLETED',**{m:value for m in METRICS}})
    write_tables(tmp_path/'tables',rows,[],[],{})
    summary=pd.read_csv(tmp_path/'tables/UNIQUE_METHOD_SUMMARY.csv')
    assert set(summary.dataset_id)=={'BY2H','BY2O'}
    pairs=pd.read_csv(tmp_path/'tables/PAIRWISE_CASE_LEVEL.csv')
    assert set(pairs.case_id)=={'BY2H_NATURAL','BY2O_NATURAL'}
    pairsummary=pd.read_csv(tmp_path/'tables/PAIRWISE_SUMMARY.csv')
    assert set(pairsummary.seed_inference_status)=={'NOT_AVAILABLE_NATURAL_SEQUENCE_NO_SEEDS'}
    assert 'C00_clean_normal' not in pairs.to_csv(index=False)


def test_frozen_v0_preserves_runtime_and_source_code_identity():
    from legsa_gins.paper_rebuild.clean5_parity_p04.evaluation import reused_frozen_row
    old={'run_id':'ORIGINAL','wrapper_runtime_seconds':'10.3','code_commit':'FROZEN','horizontal_rmse_m':'.2','evaluation_invoked':'True'}
    identity={'run_id':'BY2H_V0_A04','variant_id':'V0','dataset_id':'BY2H','evaluator_contract':'evaluator_contract_v2','code_commit':'P04','wrapper_runtime_seconds':None}
    row=reused_frozen_row(old,identity,'table:2')
    assert row['wrapper_runtime_seconds']=='10.3' and row['code_commit']=='FROZEN'
    assert row['horizontal_rmse_m']=='.2' and row['p04_evaluation_invoked'] is False
    assert row['original_frozen_fields_preserved'] is True
