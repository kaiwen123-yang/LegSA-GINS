"""P03 bounded orchestration and fixed-source decompositions, synthetic fixtures only."""
import json
from pathlib import Path
from types import SimpleNamespace
import numpy as np
import pytest
import yaml
from legsa_gins.paper_rebuild.clean5_imu_parity import runtime,evaluation,runner
from legsa_gins.paper_rebuild.clean5_parity.decomposition import METRICS
from legsa_gins.paper_rebuild.manifest import sha256_file

ORDER=[(v,m) for v in ('V2i','V2s','V2is') for m in ('F03','A04')]


def test_exact_run_order_and_no_extra_variant():
    assert runtime.run_order({'p03':{'run_order':ORDER}})==ORDER
    for order in (ORDER[::-1],ORDER[:-1],ORDER+[('V4','A04')]):
        with pytest.raises(ValueError):runtime.run_order({'p03':{'run_order':order}})


def test_decomposition_fixed_endpoints_preserves_prior_rows():
    old=[{'term':'old','source_row':'P02:2','horizontal_rmse_m':123.}]
    rows=[]
    for variant in ('V2','V2i','V2s','V2is'):
        for method in ('F01','F03','A04'):
            rows.append({'run_id':variant+method,'variant_id':variant,'method_id':method,'source_row':variant+method,**{m:float(len(variant)) for m in METRICS}})
    rows.append({'variant_id':'EXTERNAL','method_id':'EXT05C','source_row':'EXT:3',**{m:1. for m in METRICS}})
    result=evaluation.append_decomposition(old,{'v2':rows,'v3':rows},selected_variant='V2is')
    assert result[0]==old[0] and len(result)==16
    residual=result[-1]
    assert residual['left_source_row']=='V2isA04' and residual['right_source_row']=='EXT:3'
    assert residual['horizontal_rmse_m']==3.
    with pytest.raises(ValueError):evaluation.append_decomposition(old,{'v2':rows},selected_variant='V2s')
    changed=[dict(rows[0])];changed[0]['horizontal_rmse_m']+=1e-12
    with pytest.raises(ValueError):evaluation.assert_frozen_numbers([rows[0]],changed)


def test_new_eval_gate_does_not_count_old_evaluations():
    records=[{'run_id':v+m} for v,m in ORDER]
    valid={'new_run_gates':[{'version':version,'run_id':r['run_id'],'status':'COMPLETED'} for version in ('v2','v3') for r in records],
        'original_numeric_fields_unchanged':True,'body_frame_bias':{version:[{'run_id':r['run_id'],'status':'AVAILABLE'} for r in records] for version in ('v2','v3')}}
    assert runner.evaluation_gate(valid,records)['pass']
    valid['new_run_gates'][0]['status']='UNAVAILABLE'
    assert not runner.evaluation_gate(valid,records)['pass']


def test_solver_failure_stops_after_one_and_seals_without_retry(tmp_path,monkeypatch):
    from legsa_gins.paper_rebuild.clean5_parity import scheduling
    stage=tmp_path/'stage';stage.mkdir();provider=tmp_path/'provider';provider.write_text('synthetic')
    executable=tmp_path/'solver';executable.write_text('not executed')
    source=tmp_path/'source.yaml';source.write_text('starttime: 66\nendtime: 340\n')
    original_sha=runtime.sha256_file
    monkeypatch.setattr(runtime,'sha256_file',lambda p:runtime.EXE_SHA if Path(p)==executable else original_sha(p))
    config_source={'runtime_config':str(source),'runtime_config_sha256':sha256_file(source)}
    contract={'p03':{'run_order':ORDER},'frozen_runtime':{'original_configs':{'F03':config_source,'A04':config_source}}}
    paths={k:{'path':str(provider),'sha256':sha256_file(provider)} for k in
           ('imupath','gnsspath','raw_doppler_factor_path','go2_attitude_prior_path','go2_horizontal_velocity_prior_path')}
    bundle={'variants':{v:{'providers':paths} for v in ('V2i','V2s','V2is')}}
    monkeypatch.setattr(runtime,'bind_config',lambda text,replacements:(yaml.safe_dump(replacements),[]))
    monkeypatch.setattr(runtime,'expected_counts',lambda cfg:{'eligible_rows':1})
    monkeypatch.setattr(runtime,'frozen_parameter_hash',lambda text:'synthetic')
    monkeypatch.setattr(runtime,'audit_solver_openat',lambda *args,**kwargs:{'pass':True})
    monkeypatch.setattr(scheduling,'audit_scheduling',lambda **kwargs:{'status':'UNAVAILABLE'})
    calls=[]
    def fail(command,**kwargs):
        calls.append(command);return SimpleNamespace(returncode=2,stdout='',stderr='synthetic native failure')
    monkeypatch.setattr(runtime,'run_process_group',fail)
    registry=SimpleNamespace(code_root=tmp_path,raw_root=tmp_path/'raw',clean_root=tmp_path)
    records=runtime.run_ladder(registry=registry,stage_root=stage,contract=contract,provider_bundle=bundle,executable=executable,code_commit='synthetic')
    assert len(calls)==len(records)==1
    assert records[0]['terminal_status']=='FAILED_NATIVE_SOLVER'
    seal=json.loads((stage/'04_PARITY_SEAL/PARITY_OUTPUT_SEAL.json').read_text())
    assert seal['run_count']==1 and seal['completed_count']==0
    assert records[0]['provider_family']=='CLEAN5_PARITY_V2i'
    assert seal['data_mode']=='real_by2_raw' and seal['synthetic_data_used'] is False and seal['semisynthetic_data_used'] is False
    with pytest.raises(FileExistsError):runtime.run_ladder(registry=registry,stage_root=stage,contract=contract,provider_bundle=bundle,executable=executable,code_commit='synthetic')
    assert len(calls)==1


@pytest.mark.parametrize('transform_fails',[False,True])
def test_only_twelve_new_evaluations_and_prior_metrics_are_unchanged(tmp_path,monkeypatch,transform_fails):
    import pandas as pd
    from legsa_gins.paper_rebuild.clean5_sequence.evaluation_tables import CANONICAL_CSV_NAMES
    prior_pairs=[('V0-18','A04'),('V1','F01'),('V1','F03'),('V1','A04'),('V2','F01'),('V2','F03'),('V2','A04'),
                 ('V2e','F01'),('V0','F01'),('V0','F03'),('V0','A04'),('EXTERNAL','LC01'),('EXTERNAL','EXT05C')]
    prior_rows=[];prior_bias=[]
    for variant,method in prior_pairs:
        missing=variant=='V2e';run_id='OLD_'+variant+'_'+method
        prior_rows.append({'run_id':run_id,'variant_id':variant,'method_id':method,'source_row':'P02:'+run_id,
            'code_commit':'prior','evaluation_status':'UNAVAILABLE' if missing else 'COMPLETED',
            'evaluator_contract':'evaluator_contract_v2',**{m:'UNAVAILABLE' if missing else 123.456 for m in METRICS}})
        prior_bias.append({'run_id':run_id,'variant_id':variant,'method_id':method,'status':'UNAVAILABLE' if missing else 'AVAILABLE',
                           'forward_signed_mean_m':123.456,'count':2})
    reference={'rows':{'v2':prior_rows,'v3':prior_rows},'body_frame_bias':{'v2':prior_bias,'v3':prior_bias},
        'run_gates':[],'decomposition':[{'term':'ORIGINAL_P02','source_row':'P02:line','horizontal_rmse_m':3.14}],
        'baseline_median_m':.36,'trace_sha256':'synthetic'}
    frozen=tmp_path/'prior.json';frozen.write_text(json.dumps(reference))
    monkeypatch.setattr(evaluation,'load_reference',lambda *args:(reference,{'path':str(frozen),'sha256':sha256_file(frozen)}))
    monkeypatch.setattr(evaluation,'canonical_headers',lambda *args:{n:['run_id'] for n in CANONICAL_CSV_NAMES})
    monkeypatch.setattr(evaluation.canonical,'_compute_result',lambda *args,**kwargs:{})
    stage=tmp_path/'stage';stage.mkdir();records=[]
    for variant,method in ORDER:
        run_id=variant+'_'+method;root=tmp_path/run_id;root.mkdir()
        nav=np.zeros((2,11));nav[:,1]=[66.,67.];nav[:,2:5]=[40.,116.,30.]
        navpath=root/'KF_GINS_Navresult.nav';stdpath=root/'KF_GINS_STD.txt'
        np.savetxt(navpath,nav);np.savetxt(stdpath,np.ones((2,10)))
        records.append({'variant_id':variant,'method_id':method,'run_id':run_id,'terminal_status':'COMPLETED',
            'output_root':str(root),'nav_path':str(navpath),'std_path':str(stdpath),
            'nav_sha256':sha256_file(navpath),'std_sha256':sha256_file(stdpath)})
    calls=[]
    def fake_evaluate(**kwargs):
        calls.append(kwargs);out=kwargs['outdir'];out.mkdir(parents=True)
        pd.DataFrame({'time':[66.,67.],'err_n_m':[1.,1.],'err_e_m':[2.,2.],'err_u_m':[3.,3.],
            'horizontal_err_m':[np.sqrt(5)]*2,'position_3d_err_m':[np.sqrt(14)]*2,
            'roll_err_deg':[0.,0.],'pitch_err_deg':[0.,0.],'yaw_err_deg':[0.,0.]}).to_csv(out/'error_series.csv',index=False)
        return {'runtime_seconds':.1,'capture':{'consistency':{'passed':True},'reference_epoch_count':2,
           'selected_columns':{'time':'time','lat':'lat','lon':'lon','height':'height','roll':'roll','pitch':'pitch','yaw':'yaw'}}}
    monkeypatch.setattr(evaluation,'evaluate',fake_evaluate)
    if transform_fails:
        def fail_transform(*args):raise ValueError('synthetic transform gate failed before evaluate')
        monkeypatch.setattr(evaluation,'transform_nav',fail_transform)
    registry=SimpleNamespace(code_root=tmp_path,clean_root=tmp_path,raw_root=tmp_path/'raw',sequences={'BY2':SimpleNamespace(trace_path=tmp_path/'raw/trace')})
    contract={'p03':{'run_order':ORDER},'evaluation':{'v2_sha256':evaluation.EVALUATOR_SHA256,'base_time':1772784000,
        'window_seconds':[66.,340.],'trace_sha256':'synthetic','evaluator_path':'unused','canonical_attempt':'unused'}}
    result=evaluation.evaluate_ladder(registry=registry,stage_root=stage,contract=contract,run_records=records,code_commit='new',baseline_median_m=.36)
    if transform_fails:
        assert len(calls)==result['new_evaluation_count']==6
        assert result['planned_new_evaluation_count']==result['new_evaluation_gate_count']==12
        assert all(not g['evaluation_invoked'] for g in result['new_run_gates'] if g['version']=='v3')
        assert all(not r['evaluation_invoked'] for r in result['rows']['v3'][13:])
        return
    assert len(calls)==result['new_evaluation_count']==12 and result['new_completed_evaluation_count']==12
    assert all('OLD_' not in str(c['outdir']) for c in calls)
    assert all(len(result['rows'][v])==19 for v in ('v2','v3'))
    for version in ('v2','v3'):
        assert result['rows'][version][0]['horizontal_rmse_m']==123.456
        assert result['rows'][version][0]['code_commit']=='prior'
        assert result['rows'][version][0]['p02_source_row'].startswith('P02:')
        assert result['rows'][version][7]['horizontal_rmse_m']=='UNAVAILABLE'
    assert result['decomposition'][0]==reference['decomposition'][0]
    assert json.loads(frozen.read_text())==reference


def test_provider_phase_generator_owns_exactly_one_bundle_write(tmp_path,monkeypatch):
    from legsa_gins.paper_rebuild.clean5_imu_parity import providers
    calls=[];bundle={'variants':{},'data_mode':'synthetic_test_fixture'}
    def generate(**kwargs):
        calls.append(kwargs)
        output=kwargs['stage_root']/'02_PARITY_PROVIDERS';output.mkdir()
        with (output/'PARITY_PROVIDER_BUNDLE.json').open('x') as f:json.dump(bundle,f)
        return bundle
    monkeypatch.setattr(providers,'generate_providers',generate)
    # Any write via the runner would duplicate the exclusive generator write.
    monkeypatch.setattr(runner,'write_json',lambda *args,**kwargs:pytest.fail('runner must not rewrite provider bundle'))
    returned=runner.generate_provider_phase(registry=object(),stage=tmp_path,contract={},code_commit='synthetic')
    assert returned==bundle and len(calls)==1
    assert json.loads((tmp_path/'02_PARITY_PROVIDERS/PARITY_PROVIDER_BUNDLE.json').read_text())==bundle
