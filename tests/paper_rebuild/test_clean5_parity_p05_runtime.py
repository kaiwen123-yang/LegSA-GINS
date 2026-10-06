import json
from pathlib import Path
import pytest

@pytest.mark.parametrize('failure_phase', ['SUBPROCESS','STRACE_AUDIT','COUNTER_AUDIT','OUTPUT_VALIDATION','SCHEDULING_AUDIT'])
def test_attempt_exception_keeps_manifest_artifacts_and_seal(tmp_path, monkeypatch, failure_phase):
    """Mocks only: one launch attempt, no subsequent run, immutable failure evidence."""
    from types import SimpleNamespace
    import yaml
    from legsa_gins.paper_rebuild.clean5_parity_p05 import runtime as rt
    from legsa_gins.paper_rebuild.clean5_parity import scheduling
    executable=tmp_path/'mock_executable';executable.write_text('never executed')
    input_path=tmp_path/'input';input_path.write_text('synthetic fixture')
    roles=['imupath','gnsspath','raw_doppler_factor_path','go2_attitude_prior_path','go2_horizontal_velocity_prior_path']
    providers={k:{'path':str(input_path),'sha256':rt.sha256_file(input_path)} for k in roles}
    source=tmp_path/'source.yaml';source.write_text(yaml.safe_dump({**rt.NATIVE_IDENTITY,**{k:str(input_path) for k in roles},'abstd':[77.8]*3,'vrw':[.077]*3,'initbastd':[77.8]*3,'arw':[.985]*3,'gbstd':[9.38]*3}))
    spec={'source_config':{'runtime_config':str(source),'runtime_config_sha256':rt.sha256_file(source)},'window_seconds':[66,340],
          'cells':[{'cell_id':str(i),'abstd_mGal':a,'vrw_mps_sqrt_hour':v} for i,(a,v) in enumerate(rt.GRID)]}
    contract={'p05':spec}
    bundle={'variants':{'V2is':{'providers':providers}}}
    registry=SimpleNamespace(code_root=tmp_path,raw_root=tmp_path,clean_root=tmp_path,sequences={'BY2':SimpleNamespace(data_mode='synthetic_test')})
    stage=tmp_path/'stage';stage.mkdir();calls=[]
    monkeypatch.setattr(rt,'EXE_SHA',rt.sha256_file(executable))
    monkeypatch.setattr(rt,'resolve',lambda path,registry:source)
    monkeypatch.setattr(rt,'bind_config',lambda text,replacements:(yaml.safe_dump({**yaml.safe_load(text),**replacements},default_flow_style=None),{}))
    monkeypatch.setattr(rt,'frozen_parameter_hash',lambda text:'mock_parameter_hash')
    monkeypatch.setattr(rt,'expected_counts',lambda cfg:{'mock':1})
    def fail():raise RuntimeError('synthetic injected failure')
    def process(command,**kwargs):
        calls.append(command)
        root=Path(command[command.index('--output-dir')+1])
        (root/'actual_partial_output').write_text('must be sealed')
        if failure_phase=='SUBPROCESS':fail()
        (root/'RUN_MANIFEST.json').write_text('{}')
        (root/'KF_GINS_Navresult.nav').write_text('synthetic')
        (root/'KF_GINS_STD.txt').write_text('synthetic')
        return SimpleNamespace(returncode=0,stdout='mock stdout',stderr='')
    monkeypatch.setattr(rt,'run_process_group',process)
    monkeypatch.setattr(rt,'audit_solver_openat',lambda *a,**k:fail() if failure_phase=='STRACE_AUDIT' else {'pass':True})
    monkeypatch.setattr(rt,'check_counters',lambda *a,**k:fail() if failure_phase=='COUNTER_AUDIT' else {'pass':True,'actual':{'mock':1}})
    monkeypatch.setattr(rt,'validate_run_outputs',lambda *a,**k:fail() if failure_phase=='OUTPUT_VALIDATION' else {})
    def schedule(**kwargs):
        root=kwargs['output_root'];root.mkdir(parents=True)
        (root/'partial_audit.json').write_text('{}')
        if failure_phase=='SCHEDULING_AUDIT':fail()
        return {'status':'SCHEDULING_AUDIT_COMPLETE'}
    monkeypatch.setattr(scheduling,'audit_scheduling',schedule)
    records=rt.run_ladder(registry=registry,stage_root=stage,contract=contract,provider_bundle=bundle,executable=executable,code_commit='synthetic_test')
    assert len(calls)==len(records)==1
    record=records[0]
    assert record['terminal_status']==f'FAILED_{failure_phase}_EXCEPTION'
    assert record['exit_code']==(None if failure_phase=='SUBPROCESS' else 0)
    assert record['process_completion_available']==(failure_phase!='SUBPROCESS')
    assert record['retry_count']==0
    root=Path(record['output_root'])
    assert json.loads((root/'PARITY_RUN_MANIFEST.json').read_text())==record
    seal=json.loads((stage/'04_PARITY_SEAL/PARITY_OUTPUT_SEAL.json').read_text())
    assert seal['records']==records and seal['run_count']==1 and seal['completed_count']==0
    assert seal['all_native_success'] is False
    assert len(list((stage/'03_PARITY_RUNS').iterdir()))==1
    for relative,digest in seal['files_sha256'].items():assert rt.sha256_file(stage/relative)==digest
    assert any(p.endswith('/actual_partial_output') for p in seal['files_sha256'])
    assert any(p.endswith('/partial_audit.json') for p in seal['files_sha256'])
