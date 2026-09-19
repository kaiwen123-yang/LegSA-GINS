"""Synthetic control regression only; no native/evaluator launch or raw/trace access."""
from copy import deepcopy
import json
from pathlib import Path
import pytest
from legsa_gins.paper_rebuild.hext import t5bc_runtime as rt
from legsa_gins.paper_rebuild.hext import t5bc_execution as ex
from legsa_gins.paper_rebuild.hext import t5bc_continuation as c

REASON='FAIL_CLEAN1_METHOD_CONTRACT_MISMATCH: actual formal module activation counters mismatch'

@pytest.fixture
def boundary(tmp_path,monkeypatch):
    (tmp_path/'imu').write_text('0 0\n1 0\n2 0\n')
    (tmp_path/'gnss').write_text('1 '+ '0 '*16+'0\n1.5 '+'0 '*16+'0\n')
    (tmp_path/'sidecar').write_text('time,b_n,b_e,b_d,pAcc1,pAcc2,valid\n1,,,,,,0\n1.5,,,,,,0\n')
    (tmp_path/'PORT_RUNTIME_LOOP_TRACE.csv').write_text('loop_index,timestamp_after_process\n0,1\n1,2\n')
    (tmp_path/'PORT_GNSS_UPDATE_TRACE.csv').write_text('position_update,velocity_update,yaw_update,yaw_mode\n1,1,0,NONE\n')
    (tmp_path/'stderr.log').write_text('legsa_v23_port_core_demo failed: '+REASON+'\n')
    cfg={'imupath':str(tmp_path/'imu'),'gnsspath':str(tmp_path/'gnss'),'baseline3d_path':str(tmp_path/'sidecar'),
         'starttime':0,'endtime':2,'enable_dual_yaw':True}
    monkeypatch.setattr(rt,'expected_counts',lambda *_:{'dual_yaw_attempt_count':0,'position_update_count':1,
        'receiver_velocity_update_count':1,'last_processed_imu_time':2})
    return tmp_path,cfg

@pytest.mark.parametrize('prefix',['','legsa_v23_port_core_demo failed: '])
def test_exact_bare_or_fixed_prefix(boundary,prefix):
    root,cfg=boundary;(root/'stderr.log').write_text(prefix+REASON+'\n')
    result=rt.classify_heading_failure(root,cfg,variant='B3')
    assert result['passed'] and result['classification']==c.NOT_APPLICABLE
    assert not (root/'RUN_MANIFEST.json').exists()

@pytest.mark.parametrize('text',['other: '+REASON,REASON+' suffix',REASON+'\nsecond error',
    'legsa_v23_port_core_demo failed: '+REASON+' extra','legsa_v23_port_core_demo failed: other'])
def test_reject_other_errors(boundary,text):
    root,cfg=boundary;(root/'stderr.log').write_text(text)
    assert not rt.classify_heading_failure(root,cfg,variant='B3')['passed']

@pytest.mark.parametrize('change',['loop','attempt','position','velocity','valid','disabled','diagnostic_attempt'])
def test_positive_evidence_required(boundary,change):
    root,cfg=boundary
    if change=='loop':(root/'PORT_RUNTIME_LOOP_TRACE.csv').write_text('loop_index,timestamp_after_process\n0,1\n')
    elif change=='valid':(root/'sidecar').write_text('time,b_n,b_e,b_d,pAcc1,pAcc2,valid\n1,0,0,0,0,0,1\n1.5,,,,,,0\n')
    elif change=='disabled':cfg['enable_dual_yaw']=False
    elif change=='diagnostic_attempt':(root/'BASELINE3D_DIAGNOSTICS.csv').write_text('attempt\n1\n')
    else:
        values={'attempt':'1,1,1','position':'0,1,0','velocity':'1,0,0'}[change]
        (root/'PORT_GNSS_UPDATE_TRACE.csv').write_text('position_update,velocity_update,yaw_update,yaw_mode\n'+values+',NONE\n')
    assert not rt.classify_heading_failure(root,cfg,variant='B3')['passed']


def test_old_seal_remains_hard_stop_and_bytes_immutable(tmp_path):
    rt._write(tmp_path/'HARD_STOP.json',{'status':'HARD_STOP'})
    record=rt._seal(tmp_path,{'status':'HARD_STOP'},filename='T5BC_NATIVE_SUMMARY.json')
    before=ex._inventory(tmp_path)
    assert c.verify_sealed_hard_stop(record['native_summary'])['status']=='HARD_STOP'
    assert before==ex._inventory(tmp_path)
    with pytest.raises(RuntimeError,match='HARD_STOP_SLOT'):
        ex.verify_terminal(tmp_path,'T5BC_NATIVE_SUMMARY.json')
    (tmp_path/'HARD_STOP.json').write_text('{}')
    with pytest.raises(RuntimeError,match='MEMBER_HASH'):
        c.verify_sealed_hard_stop(record['native_summary'])


def test_remainder_exact_and_old_slots_cannot_be_reserved_again(tmp_path):
    ids=['identity1','identity2'];matrix=[f'run{i}' for i in range(259)]
    registry={'native':dict.fromkeys(ids+matrix[:60])}
    remaining=c.remaining_ids({'identity_native':ids,'matrix_native':matrix},registry)
    assert len(remaining)==199 and not remaining & set(registry['native'])
    ledger=tmp_path/'ledger'
    kwargs=dict(kind='matrix_native',budget=259,contract_sha256='a'*64)
    rt.reserve_slot(ledger,matrix[0],matrix,**kwargs)
    with pytest.raises(RuntimeError,match='NO_RETRY'):
        rt.reserve_slot(ledger,matrix[0],matrix,**kwargs)
    registry['native']['extra']=None
    with pytest.raises(RuntimeError):c.remaining_ids({'identity_native':ids,'matrix_native':matrix},registry)


def test_controller_consumes_only_199_new_slots(tmp_path,monkeypatch):
    from types import SimpleNamespace
    obj=c.Continuation.__new__(c.Continuation)
    obj.scratch=tmp_path/rt.STAGE;obj.scratch.mkdir()
    obj.archive=tmp_path/'archive';obj.state=obj.scratch/'09_HANDOFF/CONTINUATION_R';obj.state.mkdir(parents=True)
    obj.freeze='f'*40;obj.new_digest='b'*64;obj.old_digest='a'*64
    obj.execution_summary_path=obj.state/'FINAL_EXECUTION_SUMMARY.json'
    specs={}
    for i in range(259):
        rid=c.D57 if i==59 else f'run{i:03}'
        specs[rid]=dict(run_id=rid,sequence_id='BY2',configuration_id='F04',variant='B3',subset_case_id=f'D{i}',
            data_roles=dict(data_mode='synthetic',synthetic_data_used=True,semisynthetic_data_used=False),output_relpath=f'05_NATIVE_SUBSET61/slot{i}/B3')
    ids=list(specs);obj.allowed={'matrix_native':ids,'identity_native':['id1','id2']}
    obj.remaining=set(ids[60:]);obj.budgets={'matrix_native':259,'identity_native':2,'evaluator':518}
    obj.new_contract={'registered_runs':specs};obj.contexts={'BY2':None};obj.evaluator={'path':'never_execute'}
    oldnative={rid:{'path':str(tmp_path/rid),'sha256':'a'*64} for rid in [*ids[:60],'id1','id2']}
    oldeval={rid+'__'+v:{'path':str(tmp_path/(rid+v)),'sha256':'a'*64} for rid in ids[:59] for v in ('v3','v2')}
    obj.registry={'native':oldnative,'evaluations':oldeval};obj.registry_ref={'path':'fixture','sha256':'a'*64}
    obj.git_receipt={};obj.verify_old=lambda:None;obj._checkpoint_new=lambda label:label
    obj.read_terminal=lambda ref,root,filename: dict(status=c.NOT_APPLICABLE if root==obj.scratch/specs[c.D57]['output_relpath'] else 'COMPLETED',failure_classification=c.NOT_APPLICABLE)
    calls=[]
    monkeypatch.setattr(ex,'archive_tree_bounded',lambda *a,**k:{'status':'ARCHIVE_VERIFIED'})
    def native(ctx,**kw):
        rid=kw['run_spec']['run_id'];assert rid in obj.remaining;calls.append(('native',rid))
        root=kw['output_root'];root.mkdir(parents=True)
        row=rt.reserve_slot(kw['launch_ledger'],rid,ids,kind='matrix_native',budget=259,contract_sha256=obj.new_digest)
        rt._write(root/'LAUNCH_RESERVATION.json',row)
        return rt._seal(root,dict(run_id=rid,status='COMPLETED',failure_classification='NONE'),filename='T5BC_NATIVE_SUMMARY.json')
    def evaluate(ctx,path,**kw):
        rid=kw['run_spec']['run_id'];assert rid in obj.remaining;eid=rid+'__'+kw['version'];calls.append(('evaluator',eid))
        root=kw['output_root'];root.mkdir(parents=True)
        row=rt.reserve_slot(kw['launch_ledger'],eid,[r+'__'+v for r in ids for v in ('v3','v2')],kind='evaluator',budget=518,contract_sha256=obj.new_digest)
        rt._write(root/'LAUNCH_RESERVATION.json',row)
        return rt._seal(root,dict(run_id=eid,status='COMPLETED',evaluation_invoked=True),filename='T5BC_EVALUATION_SUMMARY.json')
    monkeypatch.setattr(rt,'run_native',native);monkeypatch.setattr(rt,'evaluate_native',evaluate)
    result=obj.execute_remaining()
    assert sum(k=='native' for k,_ in calls)==199
    assert sum(k=='evaluator' for k,_ in calls)==398
    assert result['budget_reserved']=={'identity_native':2,'matrix_native':259,'evaluator':514}
    assert len(result['native_terminals'])==261 and len(result['evaluation_terminals'])==518
    assert result['native_terminals'][c.D57]==oldnative[c.D57]
    assert not (obj.scratch/'LAUNCH_LEDGERS').exists()


def test_not_applicable_excluded_from_summary_failure_count():
    from legsa_gins.paper_rebuild.hext import t5bc_reporting as report
    cases=['ok','no_heading'];rows=[]
    for variant in (report.FROZEN,*report.SUBSET_VARIANTS):
        for case in cases:
            na=variant=='B3' and case=='no_heading'
            rows.append(dict(case_id=case,variant=variant,evaluation_status='NOT_APPLICABLE' if na else 'COMPLETED',
                failure_classification=c.NOT_APPLICABLE if na else 'NONE',yaw_rmse_deg='UNAVAILABLE' if na else 1,
                h_rmse_m='UNAVAILABLE' if na else 2))
    results=report.subset_absolute_summary(rows,case_ids=cases)
    b3=[r for r in results if r['variant']=='B3']
    assert all(r['available_count']==1 and r['not_applicable_count']==1 and r['failure_count']==0 for r in b3)
