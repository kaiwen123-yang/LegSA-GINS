#!/usr/bin/env python3
"""Six preregistered replays: old-policy identity first, then causal NED-HV."""
import argparse
from collections import Counter
import copy
import csv
import json
import math
from pathlib import Path
import subprocess
import traceback
import arc_native_replay as replay
import arc_native_real as h

ROOT=Path(__file__).resolve().parents[3]
D=ROOT/'docs/paper_rebuild/TRUSTED_HEADING_CONTINUATION_20261007'
PLAN=D/'HV_CAUSAL_POLICY_REAL_PLAN.json'
SCRIPT='scripts/paper_rebuild/carrier_phase/hv_causal_policy_replay.py'
STAGE_REL='TRUSTED_HEADING_CONTINUATION_20261007/HV_CAUSAL_POLICY_REAL_ATTEMPT01'
POLICY='causal_unique_latest'
KEY='go2_velocity_prior_time_policy'
BUDGET=dict(native_calls=6,evaluator_calls=0,compile_calls=0,loader_only_calls=0,
    phase_math_calls=0,information_readout_calls=0,raw_reads=0,reference_reads=0,
    provider_hash_passes=2,provider_unique_files=18,provider_bytes_per_hash_pass=120200614,
    provider_hash_bytes_max=240401228,config_text_clones=3,native_timeout_s=1200,
    causal_structural_summaries=3,causal_event_summaries=3,automatic_retries=0)


def causal_log_summary(record,summary):
    # CSV/ledger contract is frozen with the final producer before registration.
    rows=list(csv.DictReader((record['out']/'NED_VELOCITY_SOURCE_EVENTS.csv').open()))
    h.require(rows,'nonempty causal source decisions')
    accepted=[];selected=[];last_by_generation={};reasons=Counter();generations=set();used_indices=set()
    for row in rows:
        reasons[row['reason']]+=1
        trigger=float(row['trigger_time']);state=float(row['state_time'])
        h.require(math.isfinite(trigger) and math.isfinite(state),'finite actual source clock')
        h.require(replay.bits(trigger)==replay.bits(state),'registered exact-event trigger/state clock identity')
        h.require(row['actual_available_time_s']=='' and row['frame']=='ned','unknown arrival and NED source')
        generations.add(int(row['generation']))
        h.require(row['source_present']==row['consumed'] and row['source_present'] in ('0','1'),'once-attempt consumption identity')
        if row['source_present']=='0':
            h.require(row['accepted']=='0' and all(row[k]=='' for k in ('source_time','trigger_age_s','state_age_s','source_time_bits_hex','vector_index')),'no invented selected source')
            continue
        h.require(row['consumed']=='1','selected source always consumed before gates')
        t=float(row['source_time']);age=float(row['trigger_age_s']);generation=int(row['generation'])
        index=int(row['vector_index']);tol=float(record['manifest']['go2_velocity_prior_time_tolerance_sec'])
        h.require(math.isfinite(t) and t<=trigger and t<=state and 0<=age<=tol,
                  'selected source within both causal clocks and unchanged age')
        h.require(age==trigger-t and float(row['state_age_s'])==state-t and replay.bits(t)==row['source_time_bits_hex'],'exact logged source ages/bits')
        h.require((generation,index) not in used_indices,'selected vector index consumed once');used_indices.add((generation,index))
        h.require(t>last_by_generation.get(generation,-math.inf),'timestamp consumed once without backfill')
        last_by_generation[generation]=t;selected.append((generation,index,t))
        if row['accepted']=='1':accepted.append((replay.bits(t),index,replay.bits(state)))
    observed=[]
    with (record['out']/'ARC_CONDITIONING_EVENTS.jsonl').open() as f:
        for line in f:
            item=json.loads(line)
            if item['kind']=='ORDINARY_UPDATE' and item['source_tag']=='GO2_VELOCITY_DIAGNOSTIC':
                identity=item['provider_measurement_identity'].split(':')
                h.require(len(identity)==4 and identity[0]=='SOURCE_TIME_BITS' and identity[2]=='VECTOR_INDEX','actual HV identity')
                observed.append((identity[1],int(identity[3]),item['state_time_bits_hex']))
    h.require(accepted==observed,'causal log and actual EKF ledger one-to-one')
    audit=summary['reported_provider_source_time_audit'].get('GO2_VELOCITY_DIAGNOSTIC',{})
    h.require(audit.get('update_rows',0)==len(accepted) and all(audit.get(k,0)==0 for k in
        ('identity_unavailable','source_time_after_state_rows','repeated_vector_index_rows','inconsistent_source_time_for_vector_index_rows')),
        'actual accepted HV nonfuture unique source identity')
    h.require(len(generations)==1,'registered runtime has one source generation')
    manifest=record['manifest']
    h.require(manifest['go2_ned_source_selected_attempts']==len(selected) and manifest['go2_velocity_prior_update_count']==len(accepted),'manifest/decision counts')
    h.require(manifest['go2_ned_source_future_candidate_skips']==sum(int(x['future_candidate_skips']) for x in rows) and manifest['go2_ned_source_used_or_older_candidate_skips']==sum(int(x['used_or_older_candidate_skips']) for x in rows),'logged candidate skip counters')
    return dict(attempts=len(rows),selected=len(selected),accepted=len(accepted),reasons=dict(reasons),
        source_generations=sorted(generations),future_candidate_skip_reports=sum(int(x['future_candidate_skips']) for x in rows),used_or_older_candidate_skip_reports=sum(int(x['used_or_older_candidate_skips']) for x in rows),maximum_selected_age_s=max((float(x['trigger_age_s']) for x in rows if x['source_present']=='1'),default=None),
        actual_arrival_qualified=False,reported_trigger_and_state_time_causal=True,
        source_timestamp_once_per_generation=True,accepted_csv_ledger_exact_match=True)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--registration-commit',required=True);args=parser.parse_args()
    reg=h.read(PLAN);h.require(reg['schema']=='hv_causal_policy.real/v1' and reg['status']=='REGISTERED_READY_SINGLE_EXECUTION' and reg['budgets']==BUDGET,'frozen executable plan')
    h.require(reg['environment_common']==replay.ENV and reg['telemetry_flag']=='1','same native environment')
    h.require(reg['ordered_calls']==[dict(arm=a,sequence_id=s) for a in ('LEGACY','CAUSAL') for s in replay.SIDS],'fixed six-call order')
    h.require(PLAN.read_bytes()==subprocess.check_output(['git','show',args.registration_commit+':'+str(PLAN.relative_to(ROOT))],cwd=ROOT),'registered plan')
    h.require(SCRIPT in reg['source_pins'],'active runner must be source pinned')
    h.source_check(reg,args.registration_commit)
    aliases=reg['aliases'];stage=h.expand(reg['stage'],aliases)
    h.require(reg['stage']=='<SCRATCH_ROOT>/'+STAGE_REL and not stage.exists(),'unique finite attempt')
    h.require(h.expand('<CODE_ROOT>',aliases)==ROOT and h.expand('<SCRATCH_ROOT>',aliases)==(ROOT.parent.parent/'LegSA-GINS-SCRATCH').resolve(),'fixed workspace aliases')
    metadata={k:h.read(replay.check_metadata(v,aliases)) for k,v in reg['metadata_pins'].items()}
    prepared=metadata['prepared_plan'];loader=metadata['loader_complete'];old=metadata['old_seal'];local=metadata['local_complete']
    h.require(local['status']=='PASS_SIX_SYNTHETIC_CAUSAL_POLICY_CASES' and local['passed']==6 and local['failed']==0,'local qualification')
    h.require(local['binary']['sha256']==reg['binary']['sha256'],'same locally qualified binary')
    h.require(old['status']=='ALL_SIX_NATIVE_SEALED_AND_THREE_PAIRS_IDENTICAL','old matched reference')
    h.require(tuple(r['sequence_id'] for r in prepared['runs'])==replay.SIDS and tuple(r['sequence_id'] for r in loader['records'])==replay.SIDS and prepared['total_blocks']==921,'original three windows/full blocks')
    h.require(loader['status']=='COMPLETE_THREE_LOADER_QUALIFICATIONS_ONE_REUSED_TWO_NEW' and loader['prepared_plan_sha256']==reg['metadata_pins']['prepared_plan']['sha256'],'existing loader/preparation binding')
    closure={replay.normalized(x,aliases) for run in prepared['runs'] for x in [*run['providers'].values(),run['carrier']]}
    declared=[replay.normalized(x,aliases) for x in reg['provider_inputs']]
    h.require(len(declared)==len(set(declared))==18 and set(declared)==closure,'hashed inputs exactly equal actual six per run')
    for run in prepared['runs']:
        for role in ('config','events','manifest'):replay.check_metadata(run[role],aliases)
    binary=replay.check_metadata(reg['binary'],aliases);stage.mkdir();replay.emit(stage/'REGISTERED_PLAN.json',reg)
    replay.emit(stage/'RESERVATION.json',dict(registration_commit=args.registration_commit,budget=BUDGET))
    records=[];identities=[];pre=False
    try:
        replay.provider_hash_pass(reg,aliases,stage,'PRE');pre=True
        causal_configs={};config_dir=stage/'CONFIGS';config_dir.mkdir()
        for run,spec in zip(prepared['runs'],reg['causal_configs']):
            sid=run['sequence_id'];h.require(sid==spec['sequence_id'],'config order')
            original=h.expand(run['config']['path'],aliases);replay.check_metadata(run['config'],aliases)
            text=original.read_bytes();h.require(KEY.encode() not in text,'new policy absent in original')
            payload=text+(b'' if text.endswith(b'\n') else b'\n')+(KEY+': '+POLICY+'\n').encode()
            target=config_dir/(sid+'_causal.yaml');target.write_bytes(payload)
            pin=h.pin(target);h.require(pin['sha256']==spec['sha256'] and pin['size_bytes']==spec['size_bytes'],'one exact config-line addition')
            causal_configs[sid]=pin
        # All three legacy identities pass before any causal-policy replay.
        for arm in ('LEGACY','CAUSAL'):
            for run,lrec in zip(prepared['runs'],loader['records']):
                active=copy.deepcopy(run)
                if arm=='CAUSAL':active['config']=causal_configs[run['sequence_id']]
                dest,out=replay.launch(reg,aliases,stage,active,arm,'1',binary,len(replay.CALLS)+1)
                seal=replay.seal_outputs(out,run['window']);manifest=h.read(out/'RUN_MANIFEST.json')
                replay.manifest_gate(manifest,run,lrec,'1',aliases)
                replay.emit(dest/'OUTPUT_SEAL.json',seal)
                rec=dict(sequence_id=run['sequence_id'],arm=arm,out=out,seal=seal,manifest=manifest);records.append(rec)
                if arm=='LEGACY':
                    old_output=next(x for x in old['outputs'] if x['sequence_id']==run['sequence_id'] and x['arm']=='ARC_TELEMETRY')
                    h.require(seal['files']==old_output['seal']['files'],'legacy default all existing native bytes changed')
                    identities.append(dict(sequence_id=run['sequence_id'],files=len(seal['files']),status='PASS_LEGACY_ALL_FILE_BYTE_IDENTITY'))
                else:
                    legacy=next(x for x in records if x['sequence_id']==run['sequence_id'] and x['arm']=='LEGACY')
                    h.require(manifest.get(KEY)==POLICY,'actual opt-in policy echo')
                    h.require(seal['files']['ARC_IMU_SEGMENTS.csv']==legacy['seal']['files']['ARC_IMU_SEGMENTS.csv'],'same physical IMU segmentation')
                    h.require(seal['numeric_serialization_health']==legacy['seal']['numeric_serialization_health'],'same NAV/STD/IMUERR time support')
                print(run['sequence_id'],arm,'SEALED',flush=True)
        h.require(len(replay.CALLS)==6,'exactly six native calls completed')
        replay.provider_hash_pass(reg,aliases,stage,'POST')
        h.source_check(reg,args.registration_commit);replay.check_metadata(reg['binary'],aliases)
        for run in prepared['runs']:
            for role in ('config','events','manifest'):replay.check_metadata(run[role],aliases)
        evidence=[stage/'REGISTERED_PLAN.json',stage/'RESERVATION.json',stage/'PRE_PROVIDER_HASHES.json',stage/'POST_PROVIDER_HASHES.json']
        evidence.extend(config_dir.iterdir())
        evidence.extend(x['out'].parent/name for x in records for name in ('INVOCATION.json','PROCESS_RESULT.json','ACCESS_AUDIT.json','OPENAT.strace','stdout.log','stderr.log','OUTPUT_SEAL.json'))
        execution_evidence={str(x.relative_to(stage)):dict(sha256=h.digest(x),size_bytes=x.stat().st_size) for x in evidence}
        replay.emit(stage/'ALL_NATIVE_SEALED.json',dict(status='ALL_SIX_SEALED_THREE_LEGACY_IDENTITIES_PASS',registration_commit=args.registration_commit,
            calls=replay.CALLS,legacy_identities=identities,binary=reg['binary'],execution_evidence=execution_evidence,outputs=[dict(sequence_id=x['sequence_id'],arm=x['arm'],path=str(x['out']),seal=x['seal']) for x in records]))
        summaries=[]
        for run in prepared['runs']:
            rec=next(x for x in records if x['sequence_id']==run['sequence_id'] and x['arm']=='CAUSAL')
            summary=replay.structure_summary(run,rec,rec,aliases)
            summary['causal_source_decisions']=causal_log_summary(rec,summary)
            summary['source_time_audit_is_report_only_no_zero_gate']=False
            summary['source_time_zero_gate_scope']='Registered NED-HV reported trigger/state time and source reuse only; other sources report only'
            summaries.append(summary)
        h.require(sum(x['source_blocks'] for x in summaries)==921 and sum(x['prior_rows'] for x in summaries)==918,'same full temporal support')
        replay.emit(stage/'COMPLETE.json',dict(status='COMPLETE_CAUSAL_NED_HV_POLICY_NOT_NAVIGATION_GAIN',registration_commit=args.registration_commit,native_calls=6,
            evaluator_calls=0,phase_information_calls=0,automatic_retries=0,legacy_identities=identities,causal_sequences=summaries,
            actual_arrival_qualified=False,physical_independence_qualified=False,phase_fusion=False,
            seal_sha256=h.digest(stage/'ALL_NATIVE_SEALED.json')))
        print('COMPLETE_CAUSAL_NED_HV_POLICY_NOT_NAVIGATION_GAIN',flush=True)
    except BaseException as exc:
        post_error=None
        if pre and 'POST' not in replay.HASH_PASSES:
            try:replay.provider_hash_pass(reg,aliases,stage,'POST')
            except BaseException as error:post_error=repr(error)
        replay.emit(stage/'FAILED.json',dict(error=repr(exc),traceback=traceback.format_exc(),calls_started=replay.CALLS,post_error=post_error,automatic_retries=0));raise

if __name__=='__main__':main()
