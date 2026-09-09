"""Mock process orchestration and real table formulas; no native or archived execution."""
from pathlib import Path
from types import SimpleNamespace
import csv
import json
import numpy as np
import pandas as pd
import pytest
from legsa_gins.paper_rebuild.clean5_calibrated import evaluation as ev


def test_trace_metadata_does_not_open_payload_and_pin_refuses_raw(tmp_path,monkeypatch):
    raw=tmp_path/'raw';raw.mkdir();trace=raw/'trace.csv';trace.write_text('must not read')
    reg=SimpleNamespace(raw_root=raw,clean_root=tmp_path,code_root=tmp_path,sequences={'BY2':SimpleNamespace(trace_path=trace)})
    real=Path.open
    def guard(self,*args,**kwargs):
        if self==trace:raise AssertionError('controller trace content open')
        return real(self,*args,**kwargs)
    monkeypatch.setattr(Path,'open',guard)
    pin={'path':str(trace),'sha256':'a'*64}
    assert ev.trace_metadata(pin,reg,'BY2')==trace
    with pytest.raises(ValueError,match='Raw payload'):ev.pinned(pin,reg)


@pytest.mark.parametrize('fail_first',[False,True])
def test_fifteen_identities_thirty_evals_and_six_fixed_pairs(tmp_path,monkeypatch,fail_first):
    stage=tmp_path/'stage';stage.mkdir();raw=tmp_path/'raw';raw.mkdir();source=tmp_path/'evaluator';source.write_text('synthetic fixture only')
    nav=tmp_path/'nav';std=tmp_path/'std';a=np.ones((5,11));a[:,1]=np.arange(66,71);b=np.ones((5,10));b[:,0]=np.arange(66,71)
    np.savetxt(nav,a);np.savetxt(std,b)
    ds={};seq={};bundles={}
    for d in ev.DATASETS:
        trace=raw/(d+'.csv');trace.write_text('do not read')
        ds[d]={'window_seconds':[66,70],'base_time':123,'trace':{'path':str(trace),'sha256':'a'*64},'baseline_median_m':.3,
            'case_meta':{'degradation_parameters_json':json.dumps({'start_s':67,'end_s':68,'secondary_runs':[[69,70]]}) if d=='BY2O' else '{}'}}
        seq[d]=SimpleNamespace(trace_path=trace);bundles[d]={'baseline_median_m':.3}
    records=[]
    for d in ev.DATASETS:
        for m in ev.METHODS:records.append({'dataset_id':d,'method_id':m,'run_id':'CLEAN5_CALIBRATED_'+d+'_'+m,'case_id':d,'effective_profile':m,'variant_id':'V2s','terminal_status':'COMPLETED','nav_path':str(nav),'nav_sha256':ev.sha256_file(nav),'std_path':str(std),'std_sha256':ev.sha256_file(std),'output_root':str(tmp_path),'counters':{}})
    registry=SimpleNamespace(code_root=tmp_path,clean_root=tmp_path,raw_root=raw,sequences=seq)
    contract={'sequences':ds,'evaluator':{'path':str(source),'sha256':ev.sha256_file(source)}}
    monkeypatch.setattr(ev,'EVALUATOR_SHA256',contract['evaluator']['sha256'])
    monkeypatch.setattr(ev,'transform_nav',lambda a,b:a);monkeypatch.setattr(ev,'write_transformed_nav',lambda before,after,array:np.savetxt(after,array))
    monkeypatch.setattr(ev,'body_frame_bias',lambda errors,nav:{'forward_signed_mean_m':1.})
    errors=pd.DataFrame({'time':np.arange(66,71),**{k:np.arange(1,6,dtype=float) for k in ['err_u_m','err_n_m','err_e_m','roll_err_deg','pitch_err_deg','yaw_err_deg','horizontal_err_m','position_3d_err_m']}})
    monkeypatch.setattr(ev.canonical,'_read_error_series',lambda path:errors)
    monkeypatch.setattr(ev,'frozen_sensor_rows',lambda *a:[{'axis':d,'s':1.03} for d in ['north','east','down']])
    monkeypatch.setattr(ev,'frozen_main_references',lambda *a:[{'frozen_reference_dataset_id':d,'method_id':m} for d in ev.DATASETS for m in ev.METHODS])
    monkeypatch.setattr(ev,'external_references',lambda *a:[{'method_id':'EXT05C','reference_reused':True},{'method_id':'LC01','reference_reused':True}])
    from legsa_gins.paper_rebuild.clean5_calibrated import robustness
    monkeypatch.setattr(robustness,'robustness_check',lambda **kw:{'new_outcome_created':False})
    calls=[]
    def evaluate(**kwargs):
        calls.append(kwargs)
        if fail_first:raise RuntimeError('injected mock failure')
        return {'runtime_seconds':0.,'capture':{'selected_columns':{'time':'time','lat':'lat','lon':'lon','height':'height','roll':'roll','pitch':'pitch','yaw':'yaw'},'consistency':{'passed':True},'reference_epoch_count':5}}
    monkeypatch.setattr(ev,'evaluate',evaluate)
    actual_open=Path.open
    def guard(self,*args,**kwargs):
        if self in [s.trace_path for s in seq.values()]:raise AssertionError('controller trace open')
        return actual_open(self,*args,**kwargs)
    monkeypatch.setattr(Path,'open',guard)
    out=ev.evaluate_chain(registry=registry,contract=contract,stage_root=stage,records=records,bundles=bundles,code_commit='mock_fixture')
    assert out['status']==('PARTIAL' if fail_first else 'COMPLETED')
    assert out['evaluator_invocation_count']==len(calls)==(1 if fail_first else 30)
    assert len(out['rows']['v2'])==len(out['rows']['v3'])==15
    assert len(list((stage/'07_OFFLINE_EVALUATION').rglob('EVAL_TERMINAL.json')))==30
    if not fail_first:
        for d in ev.DATASETS:
            rows=list(csv.DictReader((stage/d/'08_AGGREGATE/PAIRWISE_CASE_LEVEL.csv').open()))
            assert {r['comparison'] for r in rows}=={p[0] for p in ev.PAIRWISE_DEFINITIONS}
        rows=list(csv.DictReader((stage/'BY2O/08_AGGREGATE/WINDOW_SEGMENT_SUMMARY.csv').open()))
        assert {r['segment_id'] for r in rows}=={'pre','during','post','outside','full'}
        assert all(r['count']=='3' for r in rows if r['segment_id']=='outside')
        assert all(r['secondary_run_epoch_count']=='2' for r in rows if r['segment_id']=='outside')
        assert all(r['consistency_status']=='ORIGINAL_IMU_STD_DIAGNOSTIC_ONLY' for r in out['rows']['v3'])


def test_failure_tables_cover_every_profile_and_preserve_existing(tmp_path):
    stage=tmp_path/'stage';stage.mkdir()
    registry=SimpleNamespace(code_root=tmp_path,clean_root=tmp_path,raw_root=tmp_path/'raw')
    existing=stage/'08_AGGREGATE';existing.mkdir();p=existing/'UNIQUE_EVALUATION_RESULTS.csv';p.write_text('preserved\n')
    out=ev.evaluate_failure_tables(registry=registry,contract={},stage_root=stage,records=[],code_commit='mock',reason='pre_solver gate')
    assert p.read_text()=='preserved\n'
    rows=list(csv.DictReader((existing/'v3/UNIQUE_EVALUATION_RESULTS.csv').open()))
    assert len(rows)==15 and {(r['dataset_id'],r['method_id']) for r in rows}=={(d,m) for d in ev.DATASETS for m in ev.METHODS}
    assert all(r['up_rmse_m']=='UNAVAILABLE' and r['solver_terminal_status']=='NOT_EXECUTED' for r in rows)


def test_missing_native_manifest_failure_identity_keeps_all_rows_and_parameter_hash(tmp_path):
    registry=SimpleNamespace(code_root=tmp_path,clean_root=tmp_path,raw_root=tmp_path/'raw')
    job={'dataset_id':'BY2','method_id':'F01','run_id':'CLEAN5_CALIBRATED_BY2_F01','case_id':'C00_clean_normal',
         'terminal_status':'FAILED_NATIVE_MANIFEST_MISSING','counters':'UNAVAILABLE_NATIVE_MANIFEST_NOT_WRITTEN',
         'frozen_parameter_hash':'actual calibrated hash','reference_frozen_parameter_hash':'old frozen hash'}
    record=ev.identity(job,'v2','mock')
    assert record['counter_status']=='UNAVAILABLE_NATIVE_MANIFEST_NOT_WRITTEN'
    assert record['actual_parameter_hash']=='actual calibrated hash'
    assert record['reference_frozen_parameter_hash']=='old frozen hash'
    ev.evaluate_failure_tables(registry=registry,contract={},stage_root=tmp_path,records=[job],code_commit='mock',reason='native manifest missing')
    for relative in ['08_AGGREGATE/UNIQUE_EVALUATION_RESULTS.csv','08_AGGREGATE/v3/UNIQUE_EVALUATION_RESULTS.csv']:
        rows=list(csv.DictReader((tmp_path/relative).open()))
        assert len(rows)==15 and rows[0]['counter_status']=='UNAVAILABLE_NATIVE_MANIFEST_NOT_WRITTEN'
        assert rows[0]['actual_parameter_hash']=='actual calibrated hash'
        assert all(r['up_rmse_m']=='UNAVAILABLE' for r in rows)


def test_sensor_model_projection_preserves_committed_scalars(tmp_path):
    import yaml
    model={'axis_order':['north','east','down'],'s':1.0308,'g_local_mps2':9.80,'axes':{}}
    for i,axis in enumerate(model['axis_order']):
        model['axes'][axis]={'status':'CALIBRATED','vrw_mps_sqrt_hour':9.+i,'abstd_mGal':4000.+i,'q_m2ps3':.02+i,'c_m2ps2':-.01+i,'nonempty_window_count':4,'ols_lag_count':6}
    path=tmp_path/'model.yaml';path.write_text(yaml.safe_dump(model))
    reg=SimpleNamespace(code_root=tmp_path,clean_root=tmp_path,raw_root=tmp_path/'raw')
    rows=ev.frozen_sensor_rows({'model':{'path':str(path),'sha256':ev.sha256_file(path)}},reg)
    assert len(rows)==3
    for row in rows:
        assert all(row[k]==v for k,v in model['axes'][row['axis']].items())
        assert row['s']==model['s'] and row['refit_invoked'] is False
