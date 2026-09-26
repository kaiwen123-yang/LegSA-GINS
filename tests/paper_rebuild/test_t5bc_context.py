"""Synthetic wiring and mocked Git only; no actual Git/data/native/evaluator calls."""
from copy import deepcopy
import hashlib
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

from legsa_gins.paper_rebuild.hext import t5bc_context as c
from legsa_gins.paper_rebuild.hext import t5bc_runtime as rt


@pytest.fixture
def design(tmp_path):
    code=Path(c.__file__).resolve().parents[4]
    contract=yaml.safe_load((code/c.CONTRACT).read_text())
    index=yaml.safe_load((code/'configs/paper_rebuild/hext/T5BC_FROZEN_SOURCE_INDEX.yaml').read_text())
    roots={key:tmp_path/key for key in ('code_root','clean_root','raw_root','handoff_root')}
    roots['t5bc_scratch']=tmp_path/rt.STAGE
    contract=c.resolve_aliases(contract,roots);index=c.resolve_aliases(index,roots)
    contexts={seq:SimpleNamespace(sequence_id=seq,window=(66.,340.),base_time=1772784000.,
        trace=roots['raw_root']/(seq+'_NEVER_READ.csv'),trace_sha256='a'*64) for seq in c.SEQUENCES}
    metadata={case:{'source_registry_row':{'case_id':case,'method_id':'F04'},'case_meta':{'anchor':123.}} for case in c.CASES}
    args=dict(contract=contract,index=index,contexts=contexts,scratch_root=roots['t5bc_scratch'],
        code_freeze='a'*40,selections={seq:{'k_b':1.2,'k':2.3,'sigma_deg':4.5} for seq in c.SEQUENCES},
        raw_hashes={seq:{str(roots['raw_root']/(seq+'.csv')):'b'*64} for seq in c.SEQUENCES},
        subset_metadata=metadata,execution_control={})
    return args


def test_planned_registration_exact_matrix_roles_model_and_frozen_eval_length(design):
    result=c.build_registered_contract(**design)
    assert len(result['registered_runs'])==261 and len(result['registered_evaluator_ids'])==518
    runs=result['registered_runs']
    assert runs['BY2__F04__R5__C00_clean_normal']['data_roles']['data_mode']=='real_clean'
    assert runs['BY2__F04__R5__D01_seed_00']['data_roles']['semisynthetic_data_used'] is True
    assert runs['BY2__F02__B3__SEQUENCE']['baseline3d']['baseline3d_length_m']==.35
    assert runs['BY2__F02__B3__SEQUENCE']['baseline_median_m']==.356191491865984
    assert 'prepared_gnss' not in runs['BY2__F02__IDENTITY__SEQUENCE']
    assert runs['BY2__F04__B3__D37_seed_00']['frozen_echo_witness']['classification']=='DERIVED_EXPECTED_OPTIONS_FROM_BYTE_IDENTICAL_CONFIG'
    assert all(item['prepared_gnss']['sha256'] is None for item in runs.values() if item['variant']!='IDENTITY')


def test_registration_hydration_does_not_change_scientific_identity(design):
    planned=c.build_registered_contract(**design)
    bundles={}
    for seq,case in [(seq,None) for seq in c.SEQUENCES]+[('BY2',case) for case in c.CASES]:
        refs=c.planned_provider_refs(design['scratch_root'],seq,case)
        for reference in refs.values():reference['sha256']='c'*64
        bundles[case or seq]=refs
    prepared=c.build_registered_contract(**design,provider_bundles=bundles)
    assert rt.scientific_contract_sha256(planned)==rt.scientific_contract_sha256(prepared)
    bundles['BY2']['B3_GNSS']['path']+='unexpected'
    with pytest.raises(ValueError,match='path differs'):
        c.build_registered_contract(**design,provider_bundles=bundles)


def test_no_subset_selection_or_unready_fallback(design):
    design['contract']['execution_ready']=False
    with pytest.raises(PermissionError,match='DRAFT'):c.build_registered_contract(**design)
    design['contract']['execution_ready']=True
    design['contract']['matrix']['subset']['case_ids'].pop()
    with pytest.raises(ValueError,match='exact frozen 61'):c.build_registered_contract(**design)


def test_entrypoint_phase_order_is_calibration_identity_provider_matrix():
    context=c.Context.__new__(c.Context);calls=[]
    for name in ('calibration','identity','providers','matrix'):
        setattr(context,name,lambda name=name:(calls.append(name) or {'status':name}))
    result=context.execute('all')
    assert calls==list(result)==['calibration','identity','providers','matrix']


def test_mocked_git_receipt_requires_remote_and_actual_blob_equality(tmp_path,monkeypatch):
    code=tmp_path/'code';code.mkdir()
    files=[c.CONTRACT,c.ENTRYPOINT,c.REGISTRY,c.CALIBRATED_CONTRACT,Path('src/synthetic.py'),Path('src/legsa_gins/paper_rebuild/publication/style.py')]
    records=[]
    for relative in files:
        path=code/relative;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(b'synthetic source\n')
        payload=path.read_bytes();blob=hashlib.sha1(b'blob '+str(len(payload)).encode()+b'\0'+payload).hexdigest()
        records.append('100644 blob '+blob+'\t'+relative.as_posix())
    monkeypatch.setattr(c.execution,'_source_files',lambda:{code/'src/synthetic.py'})
    calls=[];remote=['a'*40]
    def fake(argv,**kwargs):
        calls.append(argv)
        if argv[1:]==['rev-parse','HEAD']:return 'a'*40+'\n'
        if argv[1]=='ls-remote':return remote[0]+'\trefs/heads/stage/clean3-math-repair\n'
        if argv[1]=='diff':return ''
        if argv[1]=='ls-tree':return '\n'.join(records)
        pytest.fail('unexpected mocked Git command')
    monkeypatch.setattr(c.subprocess,'check_output',fake)
    receipt=c.git_freeze_receipt(code,'a'*40)
    assert receipt['status']=='PASS_CODE_FREEZE_PUSHED' and len(receipt['source_sha256'])==6
    (code/'src/synthetic.py').write_bytes(b'uncommitted')
    with pytest.raises(RuntimeError,match='UNFROZEN_SOURCE'):c.git_freeze_receipt(code,'a'*40)
    remote[0]='b'*40
    with pytest.raises(RuntimeError,match='NOT_CURRENT_AND_PUSHED'):c.git_freeze_receipt(code,'a'*40)


def test_draft_context_refuses_before_git_or_local_config(tmp_path,monkeypatch):
    path=tmp_path/'draft.yaml';path.write_text('execution_ready: false\npreregistered: false\n')
    monkeypatch.setattr(c,'git_freeze_receipt',lambda *_a,**_k:pytest.fail('no Git for draft'))
    with pytest.raises(PermissionError,match='DRAFT'):
        c.Context('a'*40,local_config=tmp_path/'does_not_exist',contract_path=path)


def test_calibration_summary_has_all_six_main_and_check_rows():
    scalar={seq:{'reports':[{'lag_ms':lag,'status':'AVAILABLE','z':{'sigma_deg':2.,'k':3.,'pair_count':10},
                            'euler':{'sigma_deg':4.}} for lag in (1000,200)]} for seq in c.SEQUENCES}
    vector={seq:{'reports':[{'lag_ms':lag,'status':'AVAILABLE','k_b':5.,'sample_covariance_m2':[[1,0,0],[0,1,0],[0,0,1]]}
                            for lag in (1000,200)]} for seq in c.SEQUENCES}
    rows=c.calibration_summary_rows(scalar,vector)
    assert len(rows)==6 and sum(row['applied'] for row in rows)==1
    assert all(row['sigma_deg']==2. and row['k']==3. and row['k_b']==5. for row in rows)
    assert all(row['scalar_z_pair_count']==10 and row['scalar_euler_sigma_deg']==4. for row in rows)


def test_calibration_plot_child_reads_summary_only(tmp_path,monkeypatch):
    import json
    summary=tmp_path/'summary.csv';summary.write_text('sequence_id,lag_ms,sigma_deg,k,k_b\nBY2,1000,2,3,4\n')
    root=tmp_path/'FIGURES';calls=[]
    def fake(argv,**kwargs):
        calls.append((argv,kwargs));saved={}
        for ext in ('png','pdf','svg'):
            path=root/('T5BC_CALIBRATION.'+ext);path.write_bytes(b'synthetic plot file')
            saved[ext]=str(path);saved[ext+'_sha256']=hashlib.sha256(path.read_bytes()).hexdigest()
        return SimpleNamespace(stdout=json.dumps(saved))
    monkeypatch.setattr(c.subprocess,'run',fake)
    ref=c.render_calibration_snapshot(summary,root,code_root=tmp_path)
    assert Path(ref['path']).is_file() and len(calls)==1
    assert calls[0][0][-2:]==[str(summary),str(root)]
