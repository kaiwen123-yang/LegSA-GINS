import numpy as np
import pandas as pd
import pytest
from legsa_gins.paper_rebuild.clean5_parity.evaluation import body_to_ned, transform_nav, body_frame_bias
from legsa_gins.paper_rebuild.clean5_parity.decomposition import difference, build_decomposition, METRICS


def test_rotation_axes_and_orthogonality():
    matrices=body_to_ned([[0,0,0],[0,0,90],[90,0,0],[0,90,0],[13,21,33]])
    np.testing.assert_allclose(matrices[0],np.eye(3),atol=1e-15)
    np.testing.assert_allclose(matrices[1]@[1,0,0],[0,1,0],atol=1e-15)
    np.testing.assert_allclose(matrices[2]@[0,1,0],[0,0,1],atol=1e-15)
    np.testing.assert_allclose(matrices[3]@[1,0,0],[0,0,-1],atol=1e-15)
    for matrix in matrices:
        np.testing.assert_allclose(matrix@matrix.T,np.eye(3),atol=1e-14)
        assert np.linalg.det(matrix)==pytest.approx(1.)


def test_transform_equator_known_frd_displacement_and_immutability():
    source=np.zeros((1,11));source[0,1]=66.;original=source.copy()
    out=transform_nav(source,.36)
    # At zero latitude/longitude and zero attitude: N=.03,E=-.15,Up=.30.
    assert out[0,2]==pytest.approx(np.rad2deg(.03/6335439.32729282),abs=1e-12)
    assert out[0,3]==pytest.approx(np.rad2deg(-.15/6378137),abs=1e-12)
    assert out[0,4]==pytest.approx(.30,abs=1e-7)
    np.testing.assert_array_equal(source,original)
    np.testing.assert_array_equal(out[:,[0,1,5,6,7,8,9,10]],source[:,[0,1,5,6,7,8,9,10]])


def test_yaw_90_body_bias_population_std():
    nav=np.zeros((2,11));nav[:,1]=[66,67];nav[:,10]=90
    errors=pd.DataFrame({'time':[66.,67.],'err_n_m':[-1,-3],'err_e_m':[2,4],'err_u_m':[-.1,-.3]})
    row=body_frame_bias(errors,nav)
    assert row['forward_signed_mean_m']==pytest.approx(3)
    assert row['right_signed_mean_m']==pytest.approx(2)
    assert row['up_signed_mean_m']==pytest.approx(-.2)
    assert row['forward_standard_deviation_m']==pytest.approx(1)
    assert row['std_ddof']==0
    errors.loc[0,'time']=66.1
    with pytest.raises(ValueError,match='match original NAV'):body_frame_bias(errors,nav)


def test_unavailable_is_never_numeric_or_substituted():
    valid={m:1. for m in METRICS};valid['source_row']='a:2'
    row=difference('test',valid,None)
    assert row['status']=='UNAVAILABLE'
    assert all(row[m]=='UNAVAILABLE' for m in METRICS)
    rows=build_decomposition([],[])
    assert len(rows)==9
    assert all(r['status']=='UNAVAILABLE' for r in rows)
    right={m:.5 for m in METRICS};right['source_row']='b:3'
    assert difference('test',valid,right)['horizontal_rmse_m']==.5


def test_ladder_available_and_blocked_endpoints_remain_separate(tmp_path, monkeypatch):
    import json
    from types import SimpleNamespace
    from legsa_gins.paper_rebuild.clean5_parity import evaluation as module
    from legsa_gins.paper_rebuild.clean5_sequence.evaluation_tables import CANONICAL_CSV_NAMES
    stage=tmp_path/'stage';audit=stage/'00_PARITY_TARGET_AND_AUDITS';audit.mkdir(parents=True)
    (audit/'A_TARGET_EXTRACTION.json').write_text(json.dumps({'canonical_v0':{},'methods':{}}))
    source=tmp_path/'solver';source.mkdir()
    nav=np.zeros((2,11));nav[:,1]=[66.,67.];nav[:,2:5]=[40.,116.,30.]
    np.savetxt(source/'KF_GINS_Navresult.nav',nav)
    np.savetxt(source/'KF_GINS_STD.txt',np.ones((2,10)))
    invoked=[]
    def fake_evaluate(**kwargs):
        invoked.append(kwargs)
        out=kwargs['outdir'];out.mkdir(parents=True)
        err=pd.DataFrame({'time':[66.,67.],'err_n_m':[1.,1.],'err_e_m':[2.,2.],'err_u_m':[3.,3.],
            'horizontal_err_m':[np.sqrt(5)]*2,'position_3d_err_m':[np.sqrt(14)]*2,
            'roll_err_deg':[0.,0.],'pitch_err_deg':[0.,0.],'yaw_err_deg':[0.,0.]})
        err.to_csv(out/'error_series.csv',index=False)
        return {'capture':{'consistency':{'passed':True},'reference_epoch_count':2,'selected_columns':{'time':'time','lat':'lat','lon':'lon','height':'height','roll':'roll','pitch':'pitch','yaw':'yaw'}},'runtime_seconds':.1}
    monkeypatch.setattr(module,'evaluate',fake_evaluate)
    monkeypatch.setattr(module,'canonical_headers',lambda attempt:{name:['method_id'] for name in CANONICAL_CSV_NAMES})
    registry=SimpleNamespace(code_root=tmp_path,raw_root=tmp_path/'raw',clean_root=tmp_path,
                             sequences={'BY2':SimpleNamespace(trace_path=tmp_path/'raw/trace.csv')})
    contract={'evaluation':{'v2_sha256':module.EVALUATOR_SHA256,'window_seconds':[66.,340.],
        'base_time':1772784000.,'evaluator_path':'unused.py','trace_sha256':'test','canonical_attempt':str(tmp_path)}}
    records=[{'run_id':'V1_A04','variant_id':'V1','method_id':'A04','terminal_status':'COMPLETED','output_root':str(source)},
             {'run_id':'V2e_F01','variant_id':'V2e','method_id':'F01','terminal_status':'FAILED_NATIVE_COUNTER_GATE'}]
    result=module.evaluate_ladder(registry=registry,stage_root=stage,contract=contract,run_records=records,
                                  code_commit='test',baseline_median_m=.36)
    assert len(invoked)==2
    assert result['status']=='COMPLETED_WITH_UNAVAILABLE'
    assert [r['evaluation_status'] for r in result['rows']['v3']]==['COMPLETED','UNAVAILABLE']
    assert all(r['unavailable_reason'].startswith('Solver unavailable') for r in [result['rows']['v2'][1],result['rows']['v3'][1]])
    assert (stage/'08_AGGREGATE/v3/BODY_FRAME_BIAS.csv').is_file()
    np.testing.assert_array_equal(np.loadtxt(source/'KF_GINS_Navresult.nav'),nav)


def test_pairwise_never_joins_different_variants_and_preserves_missing():
    from legsa_gins.paper_rebuild.clean5_parity.evaluation import pairwise_tables
    def row(variant,method,value):
        return {'variant_id':variant,'method_id':method,'source_row':f'{variant}:{method}',
                'evaluator_contract':'evaluator_contract_v2',**{m:value for m in METRICS}}
    rows=[row('V1','F01',1.),row('V1','A04',.5),row('V2','F03',20.),row('V2','A04','UNAVAILABLE')]
    cases,summaries=pairwise_tables(rows)
    assert len(cases)==len(summaries)==8
    assert all(r['comparison'] in ('V1:A04-F01','V2:A04-F03') for r in cases)
    assert all(r['delta_candidate_minus_reference']==-.5 for r in cases if r['variant_id']=='V1')
    assert all(r['status']=='UNAVAILABLE' and r['delta_candidate_minus_reference'] is None
               for r in cases if r['variant_id']=='V2')
