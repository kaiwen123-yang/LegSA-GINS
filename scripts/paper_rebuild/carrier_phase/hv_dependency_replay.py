#!/usr/bin/env python3
"""Six registered replays: unchanged causal controls, then dependency eligibility.

No provider values are generated here. All 21 provider files are hashed once
before native execution; native access traces enforce read-only input access.
There is no post-run provider payload rehash and no retry after any failure.
"""
import argparse
import copy
import csv
import hashlib
import json
import math
from pathlib import Path
import re
import subprocess
import traceback
import arc_native_replay as replay
import arc_native_real as h
from hv_causal_policy_replay import causal_log_summary

ROOT = Path(__file__).resolve().parents[3]
D = ROOT/'docs/paper_rebuild/TRUSTED_HEADING_CONTINUATION_20261007'
PLAN = D/'HV_DEPENDENCY_POLICY_REAL_PLAN.json'
SCRIPT = 'scripts/paper_rebuild/carrier_phase/hv_dependency_replay.py'
STAGE_REL = 'TRUSTED_HEADING_CONTINUATION_20261007/HV_DEPENDENCY_POLICY_REAL_ATTEMPT01'
OLD_REL = 'TRUSTED_HEADING_CONTINUATION_20261007/HV_CAUSAL_POLICY_REAL_ATTEMPT01'
OLD_POLICY = 'causal_unique_latest'
POLICY = 'causal_recorded_dependencies_unique_latest'
KEY = 'go2_velocity_prior_time_policy'
HV_KEY = 'go2_horizontal_velocity_prior_path'
SCHEMA = 'HV_CALIBRATED_GNSS18_TIME_V1'
ADDED = ['dependency_schema', 'dependency_source_row_index', 'dependency_source_time_bits_hex',
         'dependency_supported', 'dependency_ready_source_time_s']
COUNTERS = ['dependency_missing_candidate_skips', 'dependency_unsupported_candidate_skips',
            'dependency_future_candidate_skips', 'dependency_future_trigger_candidate_skips',
            'dependency_future_state_candidate_skips']
FIXED_BUDGET = dict(native_calls=6, evaluator_calls=0, compile_calls=0, loader_only_calls=0,
    prepare_calls=0, phase_math_calls=0, information_readout_calls=0, raw_reads=0,
    reference_reads=0, provider_hash_passes=1, provider_unique_files=21,
    original_provider_unique_files=18, original_provider_bytes=120200614,
    config_text_clones=3, control_byte_identity_files=45, native_timeout_s=1200,
    dependency_structural_summaries=3, causal_event_summaries=3,
    dependency_event_summaries=3, automatic_retries=0)


def original_pin(pin):
    return {key: pin[key] for key in ('path', 'sha256', 'size_bytes')}


def hash_inputs_once(reg, aliases, stage):
    h.require(not replay.HASH_PASSES, 'provider hash pass already attempted')
    replay.HASH_PASSES.append('PRE')
    rows = []; total = 0
    try:
        for pin in reg['provider_inputs']:
            path = h.expand(pin['path'], aliases)
            h.require(path.stat().st_size == pin['size_bytes'], 'provider size before hash')
            digest = hashlib.sha256(); count = 0
            with path.open('rb') as stream:
                while count < pin['size_bytes']:
                    chunk = stream.read(min(1024*1024, pin['size_bytes']-count))
                    h.require(chunk, 'provider truncated during sole hash pass')
                    count += len(chunk); digest.update(chunk)
            total += count
            row = dict(path=str(path), size_bytes=count, expected_sha256=pin['sha256'], sha256=digest.hexdigest())
            rows.append(row)
            h.require(path.stat().st_size == pin['size_bytes'] and row['sha256'] == pin['sha256'], 'provider identity changed')
        h.require(len(rows) == 21 and total == reg['budgets']['provider_hash_bytes_max'], 'complete one-pass provider budget')
    finally:
        replay.emit(stage/'PRE_PROVIDER_HASHES.json', dict(pass_name='PRE', files=rows, bytes_hashed=total,
            complete=len(rows)==21 and all(x['sha256']==x['expected_sha256'] for x in rows), post_payload_rehash=False))


def clone_config(original, target, replacement_hv, expected):
    payload = original.read_bytes(); lines = payload.splitlines(keepends=True)
    found = {KEY: 0, HV_KEY: 0}; output = []
    replacements = {KEY: POLICY, HV_KEY: str(replacement_hv)}
    for line in lines:
        match = re.match(rb'^([A-Za-z0-9_]+):[ \t]*(.*?)(\r?\n)?$', line)
        name = match[1].decode('ascii') if match else ''
        if name not in replacements:
            output.append(line); continue
        found[name] += 1
        if name == KEY:
            h.require(match[2].decode().strip() == OLD_POLICY, 'original causal policy line')
        value = replacements[name]
        h.require(not any(c in value for c in '\r\n#'), 'literal registered config value')
        output.append(name.encode()+b': '+value.encode()+(match[3] or b''))
    h.require(found == {KEY: 1, HV_KEY: 1}, 'exactly two registered config-key replacements')
    changed = b''.join(output)
    h.require(sum(a != b for a, b in zip(lines, output)) == 2 and len(lines) == len(output), 'all other config line bytes unchanged')
    h.require(hashlib.sha256(changed).hexdigest() == expected['sha256'] and len(changed) == expected['size_bytes'], 'registered two-line config identity')
    with target.open('xb') as stream: stream.write(changed)
    return dict(path=str(target), sha256=expected['sha256'], size_bytes=len(changed))


def manifest_gate(manifest, run, loader_record, aliases, active_hv, policy):
    # Reuse all 53 scientific fields and ARC metadata, changing only the declared HV input path.
    old_hv = str(h.expand(run['providers'][HV_KEY]['path'], aliases))
    expected = h.read(h.expand(loader_record['echo']['path'], aliases))['actual_solver_input_paths']
    h.require(isinstance(expected, list) and expected.count(old_hv) == 1, 'one old HV path in qualified loader echo')
    expected_active = [str(active_hv) if value == old_hv else value for value in expected]
    h.require(manifest['actual_solver_input_paths'] == expected_active, 'only HV path differs from qualified inputs')
    adapted = dict(manifest); adapted['actual_solver_input_paths'] = expected
    replay.manifest_gate(adapted, run, loader_record, '1', aliases)
    h.require(manifest.get(KEY) == policy, 'actual selected policy echo')


def dependency_log_summary(record):
    with (record['out']/'NED_VELOCITY_SOURCE_EVENTS.csv').open() as stream:
        reader = csv.DictReader(stream)
        h.require(reader.fieldnames[-7:] == ['selected_dependency_schema', 'selected_dependency_ready_source_time_s', *COUNTERS], 'new-policy-only diagnostic suffix')
        rows = list(reader)
    h.require(rows, 'retain every dependency policy decision')
    totals = dict.fromkeys(COUNTERS, 0); selected = 0; accepted = 0; unselected = 0
    ready_lags = []; margins = []
    for row in rows:
        values = {}
        for key in COUNTERS:
            h.require(re.fullmatch(r'[0-9]+', row[key]) is not None, 'nonnegative dependency visit count')
            values[key] = int(row[key]); totals[key] += values[key]
        union = values['dependency_future_candidate_skips']
        a, b = values['dependency_future_trigger_candidate_skips'], values['dependency_future_state_candidate_skips']
        h.require(max(a,b) <= union <= a+b, 'dependency future union counts')
        h.require(row['actual_available_time_s'] == '', 'actual arrival remains unknown')
        if row['source_present'] == '0':
            unselected += 1
            h.require(row['selected_dependency_schema'] == row['selected_dependency_ready_source_time_s'] == '', 'unselected dependency stays unavailable')
            continue
        h.require(row['source_present'] == row['consumed'] == '1' and row['selected_dependency_schema'] == SCHEMA, 'selected known dependency is consumed')
        source, ready, trigger, state = (float(row[k]) for k in ('source_time', 'selected_dependency_ready_source_time_s', 'trigger_time', 'state_time'))
        h.require(all(math.isfinite(x) for x in (source,ready,trigger,state)) and source <= ready <= trigger and ready <= state, 'selected dependency satisfies source and both executed clocks')
        selected += 1; accepted += int(row['accepted'] == '1')
        ready_lags.append(ready-source); margins.append(min(trigger,state)-ready)
    manifest = record['manifest']
    h.require(manifest.get('go2_ned_dependency_schema') == SCHEMA, 'declared dependency schema')
    for key, total in totals.items():
        h.require(manifest['go2_ned_'+key] == total, 'manifest dependency visits: '+key)
    h.require(selected == manifest['go2_ned_source_selected_attempts'] and accepted == manifest['go2_velocity_prior_update_count'], 'dependency selection/acceptance counts')
    return dict(decision_rows=len(rows), selected=selected, accepted=accepted, unselected=unselected,
        candidate_visit_totals=totals, maximum_selected_ready_minus_source_s=max(ready_lags, default=None),
        minimum_selected_execution_minus_ready_s=min(margins, default=None),
        ready_scope='HV_AND_HISTORICAL_CALIBRATED_GNSS18_REPORTED_ROW_TIMES_ONLY',
        actual_arrival_qualified=False, raw_receiver_time_qualified=False,
        counter_semantics='candidate scan visits, not unique or independent samples')


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('--registration-commit', required=True)
    args = parser.parse_args(); reg = h.read(PLAN)
    h.require(reg['schema'] == 'hv_dependency_policy.real/v1' and reg['status'] == 'REGISTERED_READY_SINGLE_EXECUTION', 'registered executable dependency plan')
    expected_budget = {**FIXED_BUDGET, 'provider_bytes_per_hash_pass': 199841096, 'provider_hash_bytes_max': 199841096}
    h.require(reg['budgets'] == expected_budget, 'fixed finite budget')
    h.require(reg['environment_common'] == replay.ENV and reg['telemetry_flag'] == '1', 'same native environment')
    h.require(reg['ordered_calls'] == [dict(arm=a, sequence_id=s) for a in ('CAUSAL','DEPENDENCY') for s in replay.SIDS], 'six fixed calls, old causal identity first')
    h.require(PLAN.read_bytes() == subprocess.check_output(['git','show',args.registration_commit+':'+str(PLAN.relative_to(ROOT))], cwd=ROOT), 'registered plan bytes')
    h.require(SCRIPT in reg['source_pins'], 'active runner pinned')
    h.source_check(reg, args.registration_commit)
    aliases = reg['aliases']; stage = h.expand(reg['stage'], aliases)
    h.require(reg['stage'] == '<SCRATCH_ROOT>/'+STAGE_REL and not stage.exists(), 'one unique attempt; no retry')
    h.require(h.expand('<CODE_ROOT>',aliases) == ROOT and h.expand('<SCRATCH_ROOT>',aliases) == (ROOT.parent.parent/'LegSA-GINS-SCRATCH').resolve(), 'fixed workspace aliases')
    metadata = {key:h.read(replay.check_metadata(pin,aliases)) for key,pin in reg['metadata_pins'].items()}
    prepared = metadata['prepared_plan']; loader = metadata['loader_complete']
    old = metadata['old_seal']; qualified = metadata['qualification_complete']
    old_stage = h.expand('<SCRATCH_ROOT>/'+OLD_REL, aliases)
    h.require(h.expand(reg['metadata_pins']['old_seal']['path'],aliases) == old_stage/'ALL_NATIVE_SEALED.json', 'fixed old causal seal')
    h.require(old['status'] == 'ALL_SIX_SEALED_THREE_LEGACY_IDENTITIES_PASS', 'old causal run sealed')
    old_controls = [x for x in old['outputs'] if x['arm'] == 'CAUSAL']
    h.require(tuple(x['sequence_id'] for x in old_controls) == replay.SIDS and all(len(x['seal']['files']) == 15 for x in old_controls), 'three old causal controls and 45 files')
    h.require(prepared['aliases'] == aliases and tuple(x['sequence_id'] for x in prepared['runs']) == replay.SIDS and prepared['total_blocks'] == 921 and prepared['total_endpoints'] == 1842, 'unchanged full three-window schedule')
    h.require(loader['status'] == 'COMPLETE_THREE_LOADER_QUALIFICATIONS_ONE_REUSED_TWO_NEW' and loader['prepared_plan_sha256'] == reg['metadata_pins']['prepared_plan']['sha256'] and tuple(x['sequence_id'] for x in loader['records']) == replay.SIDS, 'original configuration qualification chain')
    h.require(qualified['status'] == 'PASS_LOCAL_AND_FULL_DEPENDENCY_METADATA_PREPARATION' and qualified['python_cases'] == 8 and qualified['native_cases'] == 8 and qualified['native_real_calls'] == qualified['evaluator_calls'] == qualified['automatic_retries'] == 0, 'eight Python and eight native synthetic qualifications')
    h.require(all(x['returncode'] == 0 and not x['timeout'] for x in qualified['calls']) and len(qualified['case_results']) == 8 and all(x['status'] == 'PASS' for x in qualified['case_results']), 'qualification complete without hidden failure')
    h.require(replay.normalized(qualified['binary'],aliases) == replay.normalized(reg['binary'],aliases), 'same qualified candidate binary')
    h.require(all(reg['source_pins'].get(path) == sha for path,sha in qualified['source_pins'].items()), 'all locally qualified sources remain in current freeze')
    h.require(tuple(x['sequence_id'] for x in qualified['providers']) == replay.SIDS and len(qualified['input_reads']) == 6, 'complete preparation receipt')
    read_pins = {x['role']:x for x in qualified['input_reads']}
    h.require(len(read_pins) == 6 and all(x['physical_read_passes'] == 1 for x in read_pins.values()), 'one preparation read per input')
    h.require(tuple(x['sequence_id'] for x in reg['control_configs']) == tuple(x['sequence_id'] for x in reg['dependency_configs']) == tuple(x['sequence_id'] for x in reg['augmented_providers']) == replay.SIDS, 'fixed config/provider mapping')
    controls = {}; augmented = {}; extra_metadata = []
    for run, lrec, control, aug, receipt in zip(prepared['runs'],loader['records'],reg['control_configs'],reg['augmented_providers'],qualified['providers']):
        sid = run['sequence_id']
        h.require(len(lrec['original_scientific_echo']) == 53, 'all 53 original scientific fields')
        for role in ('config','events','manifest'): replay.check_metadata(run[role],aliases)
        replay.check_metadata(lrec['echo'],aliases)
        control_path = replay.check_metadata(control['config'],aliases)
        h.require(control_path == old_stage/'CONFIGS'/(sid+'_causal.yaml'), 'old causal configuration path retained')
        old_config_pin = old['execution_evidence']['CONFIGS/'+sid+'_causal.yaml']
        h.require({k:control['config'][k] for k in ('sha256','size_bytes')} == old_config_pin, 'old sealed causal configuration bytes')
        controls[sid] = control['config']; extra_metadata.append(control['config'])
        manifest_path = replay.check_metadata(aug['manifest'],aliases); manifest = h.read(manifest_path)
        provider_path = h.expand(aug['provider']['path'],aliases)
        h.require(provider_path == h.expand(receipt['path'],aliases) and manifest_path == provider_path.parent/'MANIFEST.json' and manifest == receipt['manifest'], 'qualification output manifest binding')
        h.require({k:aug['provider'][k] for k in ('sha256','size_bytes')} == manifest['derived_csv'], 'qualified augmented CSV identity')
        h.require(manifest['schema'] == SCHEMA and manifest['sequence_id'] == sid and manifest['appended_fields'] == ADDED, 'five appended dependency columns')
        n = manifest['provider_rows']
        h.require(manifest['prefix_preserved_rows'] == manifest['original_flags_consistency_checked_rows'] == n and manifest['supported_rows']+manifest['unsupported_rows'] == n and manifest['ready_empty_rows'] == manifest['unsupported_rows'], 'all provider rows and flags retained')
        h.require(manifest['original_field_bytes_preserved'] is True and manifest['original_order_and_line_endings_preserved'] is True and manifest['metadata_only'] is True and manifest['velocity_recomputed'] is False and manifest['source_values_or_flags_changed'] is False, 'metadata-only input augmentation')
        h.require(replay.normalized(manifest['input_pins']['hv'],aliases) == replay.normalized(run['providers'][HV_KEY],aliases) == replay.normalized(read_pins[sid+':hv'],aliases), 'same original HV generation input')
        h.require(replay.normalized(manifest['input_pins']['historical_gnss'],aliases) == replay.normalized(read_pins[sid+':gnss'],aliases) and all(x['hash_passes'] == 1 for x in manifest['input_pins'].values()), 'historical generating GNSS18 preparation identity')
        h.require(all(reg['source_pins'].get(path) == sha for path,sha in manifest['source_pins'].items()), 'preparation source identity retained')
        augmented[sid] = aug['provider']; extra_metadata.append(aug['manifest'])
    h.require(sum(x['manifest']['provider_rows'] for x in qualified['providers']) == 222359 and sum(x['manifest']['helper_calls'] for x in qualified['providers']) == 28, 'full prepared provider denominator')
    original = {replay.normalized(pin,aliases) for run in prepared['runs'] for pin in [*run['providers'].values(),run['carrier']]}
    h.require(len(original) == 18 and sum(x[2] for x in original) == 120200614, 'original eighteen provider identities')
    closure = original | {replay.normalized(pin,aliases) for pin in augmented.values()}
    declared = [replay.normalized(pin,aliases) for pin in reg['provider_inputs']]
    h.require(len(declared) == len(set(declared)) == 21 and set(declared) == closure and len({x[0] for x in declared}) == 21, 'exact 21-provider scientific read closure')
    h.require(sum(x[2] for x in declared) == expected_budget['provider_hash_bytes_max'], 'fixed one-pass byte budget')
    for path,sha,size in declared: h.require(Path(path).stat().st_size == size, 'provider size before reservation')
    binary = replay.check_metadata(reg['binary'],aliases)
    h.require(replay.check_metadata(reg['strace'],aliases) == Path('/usr/bin/strace'), 'same registered tracer')
    h.require(not replay.CALLS and not replay.HASH_PASSES, 'fresh process bookkeeping')
    stage.mkdir(); replay.emit(stage/'REGISTERED_PLAN.json',reg)
    replay.emit(stage/'RESERVATION.json',dict(registration_commit=args.registration_commit,budget=expected_budget,automatic_retry=False))
    records = []; identities = []; dependent_configs = {}; config_dir = stage/'CONFIGS'
    try:
        hash_inputs_once(reg,aliases,stage)
        config_dir.mkdir()
        for spec in reg['dependency_configs']:
            sid = spec['sequence_id']; target = config_dir/(sid+'_dependencies.yaml')
            dependent_configs[sid] = clone_config(h.expand(controls[sid]['path'],aliases), target, h.expand(augmented[sid]['path'],aliases), spec)
        for arm in ('CAUSAL','DEPENDENCY'):
            for run,lrec in zip(prepared['runs'],loader['records']):
                sid = run['sequence_id']; active = copy.deepcopy(run)
                active['config'] = controls[sid] if arm == 'CAUSAL' else dependent_configs[sid]
                if arm == 'DEPENDENCY': active['providers'][HV_KEY] = augmented[sid]
                dest,out = replay.launch(reg,aliases,stage,active,arm,'1',binary,len(replay.CALLS)+1)
                seal = replay.seal_outputs(out,run['window']); manifest = h.read(out/'RUN_MANIFEST.json')
                manifest_gate(manifest,run,lrec,aliases,h.expand(active['providers'][HV_KEY]['path'],aliases),OLD_POLICY if arm=='CAUSAL' else POLICY)
                replay.emit(dest/'OUTPUT_SEAL.json',seal)
                record = dict(sequence_id=sid,arm=arm,out=out,seal=seal,manifest=manifest); records.append(record)
                if arm == 'CAUSAL':
                    previous = next(x for x in old_controls if x['sequence_id'] == sid)
                    h.require(seal['files'] == previous['seal']['files'], 'old causal fifteen-file byte identity')
                    identities.append(dict(sequence_id=sid,files=15,status='PASS_OLD_CAUSAL_ALL_FILE_BYTE_IDENTITY'))
                else:
                    control = next(x for x in records if x['sequence_id']==sid and x['arm']=='CAUSAL')
                    h.require(set(seal['files']) == set(control['seal']['files']), 'same native output file set')
                    h.require(seal['files']['ARC_IMU_SEGMENTS.csv'] == control['seal']['files']['ARC_IMU_SEGMENTS.csv'], 'same physical IMU segment inputs')
                    h.require(seal['numeric_serialization_health'] == control['seal']['numeric_serialization_health'], 'same NAV/STD/IMUERR sample times and support')
                print(sid,arm,'SEALED',flush=True)
        h.require(len(replay.CALLS) == 6 and sum(x['files'] for x in identities) == 45, 'six calls and 45 control identities')
        h.source_check(reg,args.registration_commit); replay.check_metadata(reg['binary'],aliases)
        for pin in reg['metadata_pins'].values(): replay.check_metadata(pin,aliases)
        for pin in extra_metadata: replay.check_metadata(pin,aliases)
        for run,lrec in zip(prepared['runs'],loader['records']):
            for role in ('config','events','manifest'): replay.check_metadata(run[role],aliases)
            replay.check_metadata(lrec['echo'],aliases)
        for pin in dependent_configs.values(): replay.check_metadata(pin,aliases)
        # No second provider payload pass. Native trace gates reject every input write.
        for path,sha,size in declared: h.require(Path(path).stat().st_size == size, 'provider size after read-only native calls')
        replay.emit(stage/'CONTROL_IDENTITIES.json',identities)
        evidence = [stage/'REGISTERED_PLAN.json',stage/'RESERVATION.json',stage/'PRE_PROVIDER_HASHES.json',stage/'CONTROL_IDENTITIES.json']
        evidence.extend(config_dir.iterdir())
        evidence.extend(x['out'].parent/name for x in records for name in ('INVOCATION.json','PROCESS_RESULT.json','ACCESS_AUDIT.json','OPENAT.strace','stdout.log','stderr.log','OUTPUT_SEAL.json'))
        execution_evidence = {str(path.relative_to(stage)):dict(sha256=h.digest(path),size_bytes=path.stat().st_size) for path in evidence}
        replay.emit(stage/'ALL_NATIVE_SEALED.json',dict(status='ALL_SIX_SEALED_THREE_CAUSAL_CONTROLS_IDENTICAL',registration_commit=args.registration_commit,calls=replay.CALLS,control_identities=identities,binary=reg['binary'],execution_evidence=execution_evidence,provider_payload_hash_passes=1,post_provider_payload_hash_performed=False,outputs=[dict(sequence_id=x['sequence_id'],arm=x['arm'],path=str(x['out']),seal=x['seal']) for x in records]))
        summaries = []
        for run in prepared['runs']:
            record = next(x for x in records if x['sequence_id']==run['sequence_id'] and x['arm']=='DEPENDENCY')
            summary = replay.structure_summary(run,record,record,aliases)
            summary['causal_source_decisions'] = causal_log_summary(record,summary)
            summary['recorded_dependency_decisions'] = dependency_log_summary(record)
            summary['source_time_audit_is_report_only_no_zero_gate'] = False
            summary['source_time_zero_gate_scope'] = 'NED-HV source and declared historical GNSS18 dependency row times against trigger/state; other sources report only'
            summaries.append(summary)
        h.require(sum(x['source_blocks'] for x in summaries) == 921 and sum(x['prior_rows'] for x in summaries) == 918, 'full scheduled denominator and inherited END support')
        replay.emit(stage/'COMPLETE.json',dict(status='COMPLETE_RECORDED_DEPENDENCY_POLICY_NOT_NAVIGATION_GAIN',registration_commit=args.registration_commit,native_calls=6,evaluator_calls=0,phase_information_calls=0,automatic_retries=0,control_identities=identities,dependency_sequences=summaries,full_provider_rows=222359,provider_payload_hash_passes=1,post_provider_payload_hash_performed=False,input_immutability_scope='prehash plus native read-only access audit and post stat; unrelated concurrent writer exclusion not proven',actual_arrival_qualified=False,raw_receiver_time_qualified=False,physical_independence_qualified=False,phase_fusion=False,seal_sha256=h.digest(stage/'ALL_NATIVE_SEALED.json')))
        print('COMPLETE_RECORDED_DEPENDENCY_POLICY_NOT_NAVIGATION_GAIN',flush=True)
    except BaseException as exc:
        replay.emit(stage/'FAILED.json',dict(error=repr(exc),traceback=traceback.format_exc(),calls_started=replay.CALLS,completed_output_records=len(records),provider_hash_passes_started=list(replay.HASH_PASSES),automatic_retries=0,post_provider_payload_hash_performed=False))
        raise


if __name__ == '__main__':
    main()
