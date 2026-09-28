"""Header regression and bounded-publication tests; no real reference inputs."""
import copy
import json
import os
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from legsa_gins.paper_rebuild.clean5_parity import external_completion as completion
from legsa_gins.paper_rebuild.clean5_parity.evaluation import (
    write_transformed_nav,transform_nav,_external_evaluate,write_version_tables,_csv,EVALUATOR_SHA256)
from legsa_gins.paper_rebuild.clean5_parity.decomposition import METRICS,build_decomposition
from legsa_gins.paper_rebuild.clean5_sequence.evaluation_tables import CANONICAL_CSV_NAMES
from legsa_gins.paper_rebuild.manifest import sha256_file


def test_percent_and_hash_headers_preserve_nonposition_tokens(tmp_path):
    source=tmp_path/'source.nav';target=tmp_path/'out.nav'
    source.write_text('% index time lat_deg lon_deg height ...\n# comment\n\n0 66.000000000 40 116 30 0 0 0 0 0 0\n')
    before=source.read_bytes();nav=np.array([[0,66,40,116,30,0,0,0,0,0,0]],float)
    moved=transform_nav(nav,.36)
    write_transformed_nav(source,target,moved)
    tokens=target.read_text().split()
    assert tokens[:2]==['0','66.000000000']
    assert tokens[5:]==['0']*6
    np.testing.assert_array_equal(np.loadtxt(target)[2:5],moved[0,2:5])
    assert source.read_bytes()==before
    with pytest.raises(FileExistsError):write_transformed_nav(source,target,moved)
    for bad in (np.zeros((2,11)),np.zeros((1,12))):
        with pytest.raises(ValueError):write_transformed_nav(source,tmp_path/'bad',bad)
    moved[0,10]=1
    with pytest.raises(ValueError,match='non-position'):write_transformed_nav(source,tmp_path/'bad',moved)
    assert not (tmp_path/'bad').exists()


def test_preserve_publish_refuses_changed_original(tmp_path):
    current=tmp_path/'current';current.mkdir();(current/'a.csv').write_bytes(b'original\n')
    audit=tmp_path/'audit';audit.mkdir();preserved=audit/'pre'
    hashes=completion.preserve_aggregate(current,preserved)
    prepared=audit/'prepared';prepared.mkdir();(prepared/'a.csv').write_bytes(b'completed\n')
    (current/'a.csv').write_bytes(b'user change\n')
    with pytest.raises(RuntimeError,match='publication refused'):
        completion.publish_aggregate(current=current,prepared=prepared,preserved=preserved,expected_hashes=hashes,audit_root=audit)
    assert (current/'a.csv').read_bytes()==b'user change\n'
    assert (preserved/'a.csv').read_bytes()==b'original\n'


def test_preserve_publish_keeps_byte_snapshot(tmp_path):
    current=tmp_path/'current';current.mkdir();(current/'a.csv').write_bytes(b'original\n')
    audit=tmp_path/'audit';audit.mkdir();preserved=audit/'pre'
    hashes=completion.preserve_aggregate(current,preserved)
    prepared=audit/'prepared';prepared.mkdir();(prepared/'a.csv').write_bytes(b'completed\n')
    result=completion.publish_aggregate(current=current,prepared=prepared,preserved=preserved,expected_hashes=hashes,audit_root=audit)
    assert result['changed_files']==['a.csv']
    assert (current/'a.csv').read_bytes()==b'completed\n'
    assert (preserved/'a.csv').read_bytes()==b'original\n'


def test_bounded_completion_only_two_external_calls(tmp_path,monkeypatch):
    stage=tmp_path/'stage';stage.mkdir();out=stage/'08_AGGREGATE';out.mkdir();(out/'v3').mkdir()
    (stage/'07_OFFLINE_EVALUATION/v3').mkdir(parents=True)
    p01dir=stage/'00_PARITY_TARGET_AND_AUDITS';p01dir.mkdir()
    names=['CLEAN5_PARITY_V0-18_A04','CLEAN5_PARITY_V1_F01','CLEAN5_PARITY_V1_F03','CLEAN5_PARITY_V1_A04',
           'CLEAN5_PARITY_V2_F01','CLEAN5_PARITY_V2_F03','CLEAN5_PARITY_V2_A04','CLEAN5_PARITY_V2e_F01',
           'V0_F01','V0_F03','V0_A04','LC01','EXT05C']
    variants=['V0-18','V1','V1','V1','V2','V2','V2','V2e','V0','V0','V0','EXTERNAL','EXTERNAL']
    methods=['A04','F01','F03','A04','F01','F03','A04','F01','F01','F03','A04','LC01','EXT05C']
    summary={'code_commit':'prior','baseline_median_m':.36,'rows':{},'body_frame_bias':{},'run_gates':[],
             'status':'COMPLETED_WITH_UNAVAILABLE','evaluator_sha256':EVALUATOR_SHA256,'trace_sha256':completion.TRACE_SHA}
    headers={n:['method_id'] for n in CANONICAL_CSV_NAMES}
    for version in ('v2','v3'):
        rows=[];bias=[]
        for name,variant,method in zip(names,variants,methods):
            missing=variant=='V2e' or (version=='v3' and variant=='EXTERNAL')
            reason='Solver unavailable: FAILED_NATIVE_COUNTER_CONTRACT' if variant=='V2e' else 'NAV row parser disagreement'
            row={'run_id':name,'method_id':method,'variant_id':variant,'code_commit':'prior',
                 'evaluator_contract':'evaluator_contract_'+version,'evaluation_status':'UNAVAILABLE' if missing else 'COMPLETED',
                 'case_id':'C00_clean_normal','dataset_id':'BY2','matched_epoch_count':2,**{m:'UNAVAILABLE' if missing else 1. for m in METRICS}}
            br={'run_id':name,'variant_id':variant,'method_id':method,'code_commit':'prior','status':'UNAVAILABLE' if missing else 'AVAILABLE'}
            if missing:row['unavailable_reason']=reason;br['unavailable_reason']=reason
            rows.append(row);bias.append(br)
            summary['run_gates'].append({'version':version,'run_id':name,'status':row['evaluation_status'],'reason':reason if missing else None})
        write_version_tables(target=out if version=='v2' else out/'v3',rows=rows,bias=bias,headers=headers)
        summary['rows'][version]=rows;summary['body_frame_bias'][version]=bias
    summary['decomposition']=build_decomposition(summary['rows']['v2'],summary['rows']['v3'])
    _csv(out/'PARITY_DECOMPOSITION.csv',summary['decomposition'])
    (out/'FINAL_EVALUATION_SUMMARY.json').write_text(json.dumps(summary))
    (out/'v3/FINAL_EVALUATION_SUMMARY.json').write_text('{}')
    terminal={'status':'PARTIAL','evaluation':copy.deepcopy(summary),'code_commit':'prior','run_count':8,'completed_runs':7}
    (stage/'P02_CONTINUED_TERMINAL.json').write_text(json.dumps(terminal))
    evaluator=tmp_path/'evaluator.py';evaluator.write_text('never called')
    raw=tmp_path/'raw';raw.mkdir();trace=raw/'trace.csv';trace.write_text('never read')
    p01={'evaluator':{'sha256':EVALUATOR_SHA256,'trace_sha256':completion.TRACE_SHA},'methods':{}}
    nav=np.zeros((2,11));nav[:,1]=[66.,67.];nav[:,2:5]=[40.,116.,30.]
    for method in completion.EXTERNAL_IDS:
        parent=tmp_path/'external';root=parent/method;root.mkdir(parents=True)
        path=root/'EXACT_EVALUATOR_INPUT.nav';np.savetxt(path,nav,header='% header',comments='')
        p01['methods'][method]={'source_table':str(parent/'table.csv'),'method_id':method,
            'continuity':{'evaluator_nav_sha256':sha256_file(path)}}
    (p01dir/'A_TARGET_EXTRACTION.json').write_text(json.dumps(p01))
    monkeypatch.setattr(completion,'execution_state',lambda *args:{'code_commit':'new'})
    monkeypatch.setattr(completion,'_validate_inputs',lambda *args,**kwargs:(terminal,{'baseline_median_m':.36}))
    monkeypatch.setattr(completion,'canonical_headers',lambda *args:headers)
    original_sha=completion.sha256_file
    monkeypatch.setattr(completion,'sha256_file',lambda p:EVALUATOR_SHA256 if Path(p)==evaluator else original_sha(p))
    calls=[]
    def fake_external(**kwargs):
        calls.append(kwargs);dest=kwargs['outdir'];dest.mkdir(parents=True)
        errors=pd.DataFrame({'time':[66.,67.],'err_n_m':[1.,1.],'err_e_m':[2.,2.],'err_u_m':[3.,3.],
           'horizontal_err_m':[np.sqrt(5)]*2,'position_3d_err_m':[np.sqrt(14)]*2,
           'roll_err_deg':[0.,0.],'pitch_err_deg':[0.,0.],'yaw_err_deg':[0.,0.]})
        errors.to_csv(dest/'error_series.csv',index=False)
        return {'audit':{'passed':True},'runtime_seconds':.1,'capture':{'consistency':{'passed':True},'reference_epoch_count':2,
                'selected_columns':{'time':'time','lat':'lat','lon':'lon','height':'height','roll':'roll','pitch':'pitch','yaw':'yaw'}}}
    monkeypatch.setattr(completion,'_external_evaluate',fake_external)
    registry=SimpleNamespace(code_root=tmp_path,raw_root=raw,clean_root=tmp_path,sequences={'BY2':SimpleNamespace(trace_path=trace)})
    settings={'v2_sha256':EVALUATOR_SHA256,'trace_sha256':completion.TRACE_SHA,'base_time':1772784000,
              'window_seconds':[66.,340.],'evaluator_path':str(evaluator),'trace_path':str(trace),'canonical_attempt':str(tmp_path)}
    before=completion._tree_hashes(out)
    result=completion.complete_external(registry=registry,stage_root=stage,contract={'evaluation':settings},code_commit='new')
    assert len(calls)==2
    assert result['status']=='COMPLETED_WITH_V2E_NATIVE_FAILURE' and result['code_commit']=='new'
    assert result['evaluation']['rows']['v2']==summary['rows']['v2']
    for row in result['evaluation']['rows']['v3']:
        if row['run_id'] in completion.EXTERNAL_IDS:assert row['evaluation_status']=='COMPLETED' and 'unavailable_reason' not in row
        else:assert row['code_commit']=='prior'
    assert completion._tree_hashes(stage/'09_EXTERNAL_COMPLETION_AUDIT/PRE_COMPLETION_AGGREGATE')==before
    assert json.loads((stage/'P02_CONTINUED_TERMINAL.json').read_text())==terminal
    with pytest.raises(FileExistsError):completion.complete_external(registry=registry,stage_root=stage,contract={'evaluation':settings},code_commit='new')


def test_exact_external_no_std_synthetic_smoke(tmp_path):
    value=os.environ.get('LEGSA_EXACT_EVALUATOR')
    if not value:pytest.skip('LEGSA_EXACT_EVALUATOR enables synthetic-only archived evaluator smoke')
    evaluator=Path(value);assert sha256_file(evaluator)==EVALUATOR_SHA256
    repo=Path(__file__).resolve().parents[2]
    raw=tmp_path/'synthetic_raw';clean=tmp_path/'synthetic_clean';raw.mkdir();clean.mkdir()
    times=np.arange(66.,71.);lat=40.+(times-66)*1e-6;lon=116.+(times-66)*1e-6;alt=np.full(5,30.)
    trace=raw/'trace.csv';nav=clean/'synthetic.nav'
    pd.DataFrame({'time':times,'lat':lat,'lon':lon,'height':alt,'roll':np.zeros(5),'pitch':np.zeros(5),'yaw':np.full(5,90.)}).to_csv(trace,index=False)
    np.savetxt(nav,np.column_stack((np.zeros(5),times,lat+1e-8,lon+1e-8,alt+.002,np.zeros((5,6)))))
    registry=SimpleNamespace(code_root=repo,raw_root=raw,clean_root=clean)
    result=_external_evaluate(evaluator=evaluator,trace=trace,nav=nav,outdir=clean/'evaluation',registry=registry,
                              settings={'base_time':0.,'trace_sha256':sha256_file(trace)})
    assert result['audit']['passed'] and result['audit']['trace_open_count']==result['audit']['raw_open_count']==1
    assert '--std' not in result['audit']['argv']
    assert result['capture']['trace_handle_hash_count']==1
    assert result['capture']['selected_columns']=={'time':'time','lat':'lat','lon':'lon','height':'height','roll':'roll','pitch':'pitch','yaw':'yaw'}
    assert result['capture']['consistency']['passed']


def test_header_fix_matches_canonical_parser_ulp_without_tolerance(tmp_path):
    from legsa_gins.paper_rebuild.canonical541 import offline_eval_aggregate as canonical
    source=tmp_path/'precision.nav'
    source.write_text('% header\n0 66.001035213470459 39.98482985253808 116.34312812098969 41.77999215293676 0 0 0 0.9004752449568363 -0.7942504551064933 1.3239770781292135\n')
    nav=canonical._read_numeric_table(source).to_numpy(float)
    changed=transform_nav(nav,.356)
    target=tmp_path/'out.nav';write_transformed_nav(source,target,changed)
    before=source.read_text().splitlines()[1].split();after=target.read_text().split()
    assert all(before[i]==after[i] for i in (0,1,5,6,7,8,9,10))
    wrong=changed.copy();wrong[0,10]=np.nextafter(wrong[0,10],np.inf)
    with pytest.raises(ValueError,match='non-position'):write_transformed_nav(source,tmp_path/'wrong.nav',wrong)
