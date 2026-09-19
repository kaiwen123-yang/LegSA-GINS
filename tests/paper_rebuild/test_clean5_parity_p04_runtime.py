"""Synthetic orchestration checks; no real solver or evaluator invocation."""
import hashlib
import json
from pathlib import Path
import pytest
from legsa_gins.paper_rebuild.clean5_parity_p04.runtime import run_order, verify_bundle
from legsa_gins.paper_rebuild.clean5_parity_p04.runner import forbidden_diagnostic_executions, validate_seal


def test_exact_eight_run_order_rejects_repeats_or_expansion():
    order=[[d,v,m] for d in ('BY2H','BY2O') for v,m in
           [('V1','A04'),('V2','A04'),('V2is','A04'),('V2is','F03')]]
    contract={'p04':{'run_order':order}}
    assert len(run_order(contract))==8
    assert run_order(contract,'BY2O')==[tuple(x[1:]) for x in order[4:]]
    for changed in (order+[order[0]], order[:-1]+[order[0]], order[::-1]):
        with pytest.raises(ValueError):run_order({'p04':{'run_order':changed}})


def test_diagnostic_exec_gate_distinguishes_metadata_from_execution():
    initial='12 execve("/usr/bin/python3", ["python3", "-B", "/snapshot/clean5_run_parity_p04.py", "--executable", "/code/legsa_v23_port_core_demo"], 0x0) = 0'
    solver='13 execve("/code/legsa_v23_port_core_demo", ["legsa_v23_port_core_demo", "--config", "x"], 0x0) = 0'
    evaluator='14 execve("/usr/bin/python3", ["python3", "-B", "/archive/evaluate_nav_trace_kfgins_v2.py", "--base_time", "1772780400"], 0x0) = 0'
    assert forbidden_diagnostic_executions([initial])==[]
    assert forbidden_diagnostic_executions([initial,solver,evaluator])==[solver,evaluator]


def test_provider_role_and_hash_gate(tmp_path):
    p=tmp_path/'input';p.write_text('pinned')
    keys=['imupath','gnsspath','raw_doppler_factor_path','go2_attitude_prior_path','go2_horizontal_velocity_prior_path']
    inputs={k:{'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for k in keys}
    bundle={'variants':{v:{'providers':dict(inputs)} for v in ['V1','V2','V2is']}}
    verify_bundle(bundle)
    p.write_text('changed')
    with pytest.raises(ValueError,match='hash mismatch'):verify_bundle(bundle)


def test_output_seal_detects_post_seal_mutation(tmp_path):
    d=tmp_path/'04_PARITY_SEAL';d.mkdir();artifact=tmp_path/'nav';artifact.write_text('frozen')
    records=[{'run_id':'test'}]
    seal={'records':records,'files_sha256':{'nav':hashlib.sha256(artifact.read_bytes()).hexdigest()}}
    (d/'PARITY_OUTPUT_SEAL.json').write_text(json.dumps(seal))
    assert validate_seal(tmp_path,records)['file_count']==1
    artifact.write_text('mutated')
    with pytest.raises(ValueError,match='changed'):validate_seal(tmp_path,records)


@pytest.mark.parametrize('failure_phase', ['SUBPROCESS','STRACE_AUDIT','COUNTER_AUDIT','OUTPUT_VALIDATION','SCHEDULING_AUDIT'])
def test_attempt_exception_keeps_manifest_artifacts_and_seal(tmp_path, monkeypatch, failure_phase):
    """Mocks only: one launch attempt, no subsequent run, immutable failure evidence."""
    from types import SimpleNamespace
    import yaml
    from legsa_gins.paper_rebuild.clean5_parity_p04 import runtime as rt
    from legsa_gins.paper_rebuild.clean5_parity import scheduling
    executable=tmp_path/'mock_executable';executable.write_text('never executed')
    input_path=tmp_path/'input';input_path.write_text('synthetic fixture')
    roles=['imupath','gnsspath','raw_doppler_factor_path','go2_attitude_prior_path','go2_horizontal_velocity_prior_path']
    providers={k:{'path':str(input_path),'sha256':rt.sha256_file(input_path)} for k in roles}
    source=tmp_path/'source.yaml';source.write_text(yaml.safe_dump({**rt.NATIVE_IDENTITY,**{k:str(input_path) for k in roles}}))
    spec={'original_configs':{m:{'runtime_config':str(source),'runtime_config_sha256':rt.sha256_file(source)} for m in ['A04','F03']},'window_seconds':[413,683]}
    contract={'p04':{'sequences':{'BY2H':spec},'run_order':[[d,v,m] for d in ['BY2H','BY2O'] for v,m in [('V1','A04'),('V2','A04'),('V2is','A04'),('V2is','F03')]]}}
    bundle={'dataset_id':'BY2H','variants':{v:{'providers':providers,'provider_family':'synthetic_fixture'} for v in ['V1','V2','V2is']}}
    registry=SimpleNamespace(code_root=tmp_path,raw_root=tmp_path,clean_root=tmp_path,sequences={'BY2H':SimpleNamespace(data_mode='synthetic_test')})
    stage=tmp_path/'stage';stage.mkdir();calls=[]
    monkeypatch.setattr(rt,'EXE_SHA',rt.sha256_file(executable))
    monkeypatch.setattr(rt,'resolve',lambda path,registry:source)
    monkeypatch.setattr(rt,'bind_config',lambda text,replacements:(yaml.safe_dump({**yaml.safe_load(text),**replacements}),{}))
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
    records=rt.run_ladder(registry=registry,stage_root=stage,contract=contract,provider_bundle=bundle,executable=executable,code_commit='synthetic_test',dataset='BY2H')
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
