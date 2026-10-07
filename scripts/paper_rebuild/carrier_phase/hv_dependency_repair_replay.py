#!/usr/bin/env python3
"""One bounded metadata-check repair: reuse completed BY2, execute five remaining calls."""
import argparse
import copy
import json
from pathlib import Path
import subprocess
import traceback
import hv_dependency_replay as dep

h, replay, ROOT = dep.h, dep.replay, dep.ROOT
PLAN = dep.D/'HV_DEPENDENCY_POLICY_REAL_REPAIR01_PLAN.json'
BUDGET = dict(native_calls=5, reused_native_calls=1, evaluator_calls=0,
    compile_calls=0, prepare_calls=0, config_clones=0, provider_payload_hash_passes=0,
    reused_output_seal_passes=1, new_output_seals=5, dependency_structural_summaries=3,
    causal_event_summaries=3, dependency_event_summaries=3,
    phase_information_calls=0, raw_reads=0, reference_reads=0, automatic_retries=0)


def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--registration-commit',required=True)
    args=parser.parse_args(); reg=h.read(PLAN)
    h.require(reg['status']=='REGISTERED_READY_SINGLE_EXECUTION' and reg['budgets']==BUDGET,'fixed five-call repair budget')
    h.require(PLAN.read_bytes()==subprocess.check_output(['git','show',args.registration_commit+':'+str(PLAN.relative_to(ROOT))],cwd=ROOT),'registered repair plan')
    h.source_check(reg,args.registration_commit)
    aliases=reg['aliases']; first=h.expand(reg['first_stage'],aliases); stage=h.expand(reg['stage'],aliases)
    h.require(stage==first/'REPAIR01' and not stage.exists(),'single repair subdirectory; no replacement')
    metadata={k:h.read(replay.check_metadata(pin,aliases)) for k,pin in reg['metadata_pins'].items()}
    original=metadata['first_plan']; failure=metadata['first_failure']; pre=metadata['first_pre_hash']
    h.require(original['status']=='REGISTERED_READY_SINGLE_EXECUTION' and original['stage']==reg['first_stage'] and original['aliases']==aliases,'original frozen attempt identity')
    h.require(failure['calls_started']==[dict(ordinal=1,sequence_id='BY2',arm='CAUSAL')] and failure['completed_output_records']==0 and 'one old HV path in qualified loader echo' in failure['error'],'only registered manifest-type failure')
    h.require(original['binary']==reg['binary'] and original['provider_inputs']==reg['provider_inputs'],'same binary and all21 inputs')
    h.require(original['ordered_calls']==[dict(arm=a,sequence_id=s) for a in ('CAUSAL','DEPENDENCY') for s in replay.SIDS],'same six-call scientific order')
    h.require(reg['ordered_calls']==original['ordered_calls'][1:],'only five unexecuted calls')
    q=metadata['qualification_complete']; prepared=metadata['prepared_plan']; loader=metadata['loader_complete']; old=metadata['old_seal']
    h.require(q['status']=='PASS_LOCAL_AND_FULL_DEPENDENCY_METADATA_PREPARATION' and q['binary']==reg['binary'],'qualified native binary unchanged')
    h.require(all(reg['source_pins'].get(k)==v for k,v in q['source_pins'].items()),'all locally qualified native/preparation sources unchanged')
    h.require(pre['complete'] and len(pre['files'])==21 and pre['bytes_hashed']==199841096,'completed original one-pass provider check')
    declared={str(h.expand(p['path'],aliases)):(p['size_bytes'],p['sha256']) for p in reg['provider_inputs']}
    witnessed={p['path']:(p['size_bytes'],p['sha256']) for p in pre['files']}
    h.require(len(declared)==21 and witnessed==declared and all(p['sha256']==p['expected_sha256'] for p in pre['files']),'inherit exact21 hashed identities without repeat payload reads')
    for path,(size,sha) in declared.items(): h.require(Path(path).stat().st_size==size,'input stat identity')
    for key in ('prepared_plan','loader_complete','old_seal','qualification_complete'):
        h.require(reg['metadata_pins'][key]==original['metadata_pins'][key],'same inherited metadata identity')
    h.require(tuple(x['sequence_id'] for x in prepared['runs'])==replay.SIDS and prepared['total_blocks']==921 and prepared['total_endpoints']==1842,'same full schedule')
    h.require(loader['prepared_plan_sha256']==reg['metadata_pins']['prepared_plan']['sha256'],'same loader receipt')
    for run,lrec in zip(prepared['runs'],loader['records']):
        for role in ('config','events','manifest'): replay.check_metadata(run[role],aliases)
        replay.check_metadata(lrec['echo'],aliases)
    controls={x['sequence_id']:x['config'] for x in original['control_configs']}
    augmented={x['sequence_id']:x['provider'] for x in original['augmented_providers']}
    configs={x['sequence_id']:x['config'] for x in reg['dependency_configs']}
    for spec in original['dependency_configs']:
        pin=configs[spec['sequence_id']]
        h.require(h.expand(pin['path'],aliases)==first/'CONFIGS'/(spec['sequence_id']+'_dependencies.yaml') and all(pin[k]==spec[k] for k in ('sha256','size_bytes')),'reuse exact two-line cloned config')
    for pin in [*controls.values(),*configs.values()]: replay.check_metadata(pin,aliases)
    for aug in original['augmented_providers']: replay.check_metadata(aug['manifest'],aliases)
    binary=replay.check_metadata(reg['binary'],aliases); replay.check_metadata(reg['strace'],aliases)
    process=metadata['reused_process']; access=metadata['reused_access']; invocation=metadata['reused_invocation']
    h.require(process['returncode']==0 and not process['timed_out'] and process['retry']==0,'first native process succeeded')
    h.require(access['passed'] and access['exact_native_exec_passed'] and access['all_declared_run_inputs_opened'],'first native read-only access passed')
    h.require(invocation['sequence_id']=='BY2' and invocation['arm']=='CAUSAL' and invocation['binary']==reg['binary'] and invocation['config']==controls['BY2'] and invocation['environment']=={**replay.ENV,'LEGSA_ARC_NATIVE_TELEMETRY':'1'},'completed first call identity')
    h.require(not replay.CALLS and not replay.HASH_PASSES,'fresh repair process bookkeeping')
    stage.mkdir(); replay.emit(stage/'REGISTERED_PLAN.json',reg)
    records=[]; identities=[]
    try:
        run=prepared['runs'][0]; out=first/'BY2__CAUSAL/OUT'
        seal=replay.seal_outputs(out,run['window']); manifest=h.read(out/'RUN_MANIFEST.json')
        dep.manifest_gate(manifest,run,loader['records'][0],aliases,h.expand(run['providers'][dep.HV_KEY]['path'],aliases),dep.OLD_POLICY)
        previous=next(x for x in old['outputs'] if x['sequence_id']=='BY2' and x['arm']=='CAUSAL')
        h.require(seal['files']==previous['seal']['files'],'completed BY2 passes corrected full45 control gate first part')
        replay.emit(stage/'REUSED_BY2_OUTPUT_SEAL.json',seal)
        records.append(dict(sequence_id='BY2',arm='CAUSAL',out=out,seal=seal,manifest=manifest,reused=True))
        identities.append(dict(sequence_id='BY2',files=15,status='PASS_REUSED_BY2_OLD_CAUSAL_ALL_FILE_BYTE_IDENTITY'))
        print('BY2 CAUSAL REUSED_AND_ALL15_IDENTICAL',flush=True)
        for call in reg['ordered_calls']:
            sid,arm=call['sequence_id'],call['arm']; index=replay.SIDS.index(sid)
            run,lrec=prepared['runs'][index],loader['records'][index]; active=copy.deepcopy(run)
            active['config']=controls[sid] if arm=='CAUSAL' else configs[sid]
            if arm=='DEPENDENCY': active['providers'][dep.HV_KEY]=augmented[sid]
            dest,out=replay.launch(reg,aliases,stage,active,arm,'1',binary,len(replay.CALLS)+1)
            seal=replay.seal_outputs(out,run['window']); manifest=h.read(out/'RUN_MANIFEST.json')
            dep.manifest_gate(manifest,run,lrec,aliases,h.expand(active['providers'][dep.HV_KEY]['path'],aliases),dep.OLD_POLICY if arm=='CAUSAL' else dep.POLICY)
            replay.emit(dest/'OUTPUT_SEAL.json',seal)
            records.append(dict(sequence_id=sid,arm=arm,out=out,seal=seal,manifest=manifest,reused=False))
            if arm=='CAUSAL':
                previous=next(x for x in old['outputs'] if x['sequence_id']==sid and x['arm']=='CAUSAL')
                h.require(seal['files']==previous['seal']['files'],'remaining old causal15file identity')
                identities.append(dict(sequence_id=sid,files=15,status='PASS_OLD_CAUSAL_ALL_FILE_BYTE_IDENTITY'))
            else:
                control=next(x for x in records if x['sequence_id']==sid and x['arm']=='CAUSAL')
                h.require(set(seal['files'])==set(control['seal']['files']) and seal['files']['ARC_IMU_SEGMENTS.csv']==control['seal']['files']['ARC_IMU_SEGMENTS.csv'],'same file set and physical IMU segments')
                h.require(seal['numeric_serialization_health']==control['seal']['numeric_serialization_health'],'same sample time support')
            print(sid,arm,'SEALED',flush=True)
        h.require(len(replay.CALLS)==5 and len(records)==6 and sum(x['files'] for x in identities)==45,'one reused plus five new calls')
        h.source_check(reg,args.registration_commit); replay.check_metadata(reg['binary'],aliases)
        for pin in reg['metadata_pins'].values(): replay.check_metadata(pin,aliases)
        for pin in [*controls.values(),*configs.values()]: replay.check_metadata(pin,aliases)
        for path,(size,sha) in declared.items(): h.require(Path(path).stat().st_size==size,'postread input stat')
        replay.emit(stage/'ALL_NATIVE_SEALED.json',dict(status='ALL_SIX_SEALED_THREE_CAUSAL_CONTROLS_IDENTICAL_FIRST_FAILURE_RETAINED',registration_commit=args.registration_commit,first_attempt_registration_commit=reg['first_registration_commit'],new_calls=replay.CALLS,reused_native_calls=1,total_native_calls_across_attempts=6,control_identities=identities,binary=reg['binary'],first_failure=reg['metadata_pins']['first_failure'],outputs=[dict(sequence_id=x['sequence_id'],arm=x['arm'],path=str(x['out']),seal=x['seal'],reused=x['reused']) for x in records]))
        summaries=[]
        for run in prepared['runs']:
            record=next(x for x in records if x['sequence_id']==run['sequence_id'] and x['arm']=='DEPENDENCY')
            summary=replay.structure_summary(run,record,record,aliases)
            summary['causal_source_decisions']=dep.causal_log_summary(record,summary)
            summary['recorded_dependency_decisions']=dep.dependency_log_summary(record)
            summary['source_time_audit_is_report_only_no_zero_gate']=False
            summary['source_time_zero_gate_scope']='NED-HV and declared historical GNSS18 dependency row times only; other sources report only'
            summaries.append(summary)
        h.require(sum(x['source_blocks'] for x in summaries)==921 and sum(x['prior_rows'] for x in summaries)==918,'full scheduled support')
        result=dict(status='COMPLETE_RECORDED_DEPENDENCY_POLICY_FIRST_METADATA_FAILURE_RETAINED',registration_commit=args.registration_commit,first_attempt_registration_commit=reg['first_registration_commit'],new_native_calls=5,reused_native_calls=1,total_native_calls_across_attempts=6,repeated_native_calls=0,evaluator_calls=0,phase_information_calls=0,automatic_retries=0,control_identities=identities,dependency_sequences=summaries,full_provider_rows=222359,provider_payload_hash_passes_across_attempts=1,post_provider_payload_hash_performed=False,actual_arrival_qualified=False,raw_receiver_time_qualified=False,physical_independence_qualified=False,phase_fusion=False,first_failure_retained=True,seal_sha256=h.digest(stage/'ALL_NATIVE_SEALED.json'))
        replay.emit(stage/'COMPLETE.json',result); print(result['status'],flush=True)
    except BaseException as exc:
        replay.emit(stage/'FAILED.json',dict(error=repr(exc),traceback=traceback.format_exc(),calls_started=replay.CALLS,completed_output_records=len(records),automatic_retries=0))
        raise


if __name__=='__main__':
    main()
