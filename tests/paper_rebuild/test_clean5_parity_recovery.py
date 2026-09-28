"""Synthetic recovery fixtures only; never launches a real provider or solver."""
import json
from pathlib import Path
import pytest
from legsa_gins.paper_rebuild.clean5_parity import recovery as r
from legsa_gins.paper_rebuild.clean5_parity.runner import args_parser
from legsa_gins.paper_rebuild.manifest import sha256_file


def dump(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value))


def fixture(tmp_path,monkeypatch):
    stage=tmp_path/'stage';stage.mkdir()
    original=stage/'01_PARITY_EXECUTION_AUDIT/code_validation/PRE_EXECUTION_CONTRACT.yaml'
    original.parent.mkdir(parents=True);original.write_text('synthetic_test_only: true\n')
    monkeypatch.setattr(r,'ORIGINAL_CONTRACT_SHA',sha256_file(original))
    provider=stage/'02_PARITY_PROVIDERS/V0-18/PARITY.gnss';provider.parent.mkdir(parents=True)
    provider.write_text('synthetic_test_only\n')
    bundle={'code_commit':r.ORIGINAL_COMMIT,'variants':{'V0-18':{'providers':{'gnsspath':{'path':str(provider),'sha256':sha256_file(provider)}}}}}
    bp=stage/'02_PARITY_PROVIDERS/PARITY_PROVIDER_BUNDLE.json';dump(bp,bundle)
    monkeypatch.setattr(r,'ORIGINAL_BUNDLE_SHA',sha256_file(bp))
    records=[]
    for index,(variant,method) in enumerate(r.RUN_ORDER[:2]):
        run_id=f'CLEAN5_PARITY_{variant}_{method}';root=stage/'03_PARITY_RUNS'/run_id;root.mkdir(parents=True)
        (root/'PARITY_RUNTIME_CONFIG.yaml').write_text('synthetic_test_only: true\n')
        dump(root/'RUN_MANIFEST.json',{'synthetic_test_only':True})
        for name in ['KF_GINS_Navresult.nav','KF_GINS_STD.txt']:(root/name).write_text('synthetic_test_only\n')
        row={'run_id':run_id,'output_root':str(root),'terminal_status':'COMPLETED' if index==0 else 'FAILED_COUNTER_AUDIT',
             'code_commit':r.ORIGINAL_COMMIT,'exit_code':0,'strace_audit':{'pass':True}}
        dump(root/'PARITY_RUN_MANIFEST.json',row);records.append(row)
    files={p.relative_to(stage).as_posix():sha256_file(p) for p in (stage/'03_PARITY_RUNS').rglob('*') if p.is_file()}
    dump(stage/'P02_EXECUTION_STARTED.json',{'code_commit':r.ORIGINAL_COMMIT,'contract_sha256':r.ORIGINAL_CONTRACT_SHA})
    dump(stage/'P02_TERMINAL.json',{'code_commit':r.ORIGINAL_COMMIT,'status':'PARTIAL','run_count':2,'runs':records})
    seal=stage/'04_PARITY_SEAL/PARITY_OUTPUT_SEAL.json';dump(seal,{'code_commit':r.ORIGINAL_COMMIT,'run_count':2,'records':records,'files_sha256':files})
    monkeypatch.setattr(r,'ORIGINAL_SEAL_SHA',sha256_file(seal))
    monkeypatch.setattr(r,'expected_counts',lambda cfg:{'position_update_count':273})
    monkeypatch.setattr(r,'check_counters',lambda *args:{'pass':True,'actual':{'position_update_count':273}})
    monkeypatch.setattr(r,'validate_run_outputs',lambda *args:{'nav_rows':3,'std_rows':3,'finite':True})
    return stage


def test_revalidation_is_separate_and_prior_native_is_not_rerun(tmp_path,monkeypatch):
    stage=fixture(tmp_path,monkeypatch)
    before={p:sha256_file(p) for p in stage.rglob('*') if p.is_file()}
    bundle,records=r.prepare_continuation(stage=stage,contract_sha256='new_audit_contract',code_commit='new_freeze',state={})
    assert all(sha256_file(p)==digest for p,digest in before.items())
    assert [x['terminal_status'] for x in records]==['COMPLETED','COMPLETED']
    assert records[1]['original_terminal_status']=='FAILED_COUNTER_AUDIT'
    assert records[1]['native_rerun'] is False
    assert records[1]['nav_sha256']==sha256_file(records[1]['nav_path'])
    assert records[1]['code_commit']==r.ORIGINAL_COMMIT
    assert records[1]['revalidation_code_commit']=='new_freeze'
    with pytest.raises(FileExistsError):
        r.prepare_continuation(stage=stage,contract_sha256='new',code_commit='new',state={})


@pytest.mark.parametrize('mutation',['run','provider','extra','terminal'])
def test_recovery_rejects_tampering_before_any_write(tmp_path,monkeypatch,mutation):
    stage=fixture(tmp_path,monkeypatch)
    if mutation=='run':
        next((stage/'03_PARITY_RUNS').rglob('KF_GINS_STD.txt')).write_text('changed')
    elif mutation=='provider':
        (stage/'02_PARITY_PROVIDERS/V0-18/PARITY.gnss').write_text('changed')
    elif mutation=='extra':
        (stage/'03_PARITY_RUNS/unsealed.txt').write_text('extra')
    else:
        p=stage/'P02_TERMINAL.json';data=json.loads(p.read_text());data['status']='PASS';dump(p,data)
    with pytest.raises(RuntimeError):
        r.prepare_continuation(stage=stage,contract_sha256='new',code_commit='new',state={})
    assert not (stage/'P02_CONTINUATION_STARTED.json').exists()
    assert not (stage/'01_PARITY_EXECUTION_AUDIT/continuation').exists()


def test_cli_resume_flag_is_explicit():
    parsed=args_parser().parse_args(['--code-root','/tmp/code','--code-freeze-commit','x',
        '--paths-config','/tmp/local','--executable','/tmp/exe','--resume-unexecuted'])
    assert parsed.resume_unexecuted
