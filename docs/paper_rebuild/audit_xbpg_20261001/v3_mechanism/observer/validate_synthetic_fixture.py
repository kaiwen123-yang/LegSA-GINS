#!/usr/bin/env python3
"""Read only isolated synthetic outputs; writes compact observer validation receipt.
Never invokes solver/evaluator; no real input or real retained payload is read.
"""
import collections
import csv
import hashlib
import json
import math
from pathlib import Path
import re


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def main():
    here=Path(__file__).resolve().parent;code=here.parents[4]
    local=json.loads((code/'configs/paper_rebuild/V3_MECHANISM_ROOTS.local.json').read_text())
    base=Path(local['aliases']['<MECHANISM_BUILD_ROOT>']);root=base/'synthetic_fixture_v1'
    checks=[];files=[];counts=collections.Counter();reason_counts=collections.Counter();event_counts=collections.Counter()
    def add(key,ok,details='',source=''):
        checks.append(dict(check_id=key,status='PASS' if ok else 'FAIL',details=str(details),source_path=source))
    def alias(path):return '<MECHANISM_BUILD_ROOT>/'+str(path.relative_to(base))
    refs=sorted((root/'frozen').rglob('*.csv'))
    expected=[str(f.relative_to(root/'frozen')) for f in refs]
    add('science_file_count',len(refs)==19,str(len(refs)))
    for condition in ['observed_off','observed_on']:
        actual=sorted(str(f.relative_to(root/condition)) for f in (root/condition).rglob('*.csv'))
        add(condition+'_exact_science_file_set',actual==expected)
        for original in refs:
            relative=original.relative_to(root/'frozen');other=root/condition/relative
            add(condition+'_byte_identity_'+str(relative),original.read_bytes()==other.read_bytes(),sha(original),alias(other))
    for condition in ['frozen','observed_off']:
        add(condition+'_no_observer_files',not list((root/condition).rglob('events.jsonl')))
    for path in sorted((root/'observed_on').glob('*/observer/events.jsonl')):
        name=path.parents[1].name;source=alias(path);raw=path.read_text();events=[json.loads(l) for l in raw.splitlines()]
        count=collections.Counter(e['event'] for e in events);counts['events']+=len(events);event_counts.update(count)
        add(name+'_continuous_event_sequence',[e['event_seq'] for e in events]==list(range(1,len(events)+1)),len(events),source)
        add(name+'_run_identity',all(e['run_id']==name and e['available_time']=='UNKNOWN' for e in events),source=source)
        add(name+'_begin_end',events[0]['event']=='OBSERVER_BEGIN' and events[-1]['event']=='OBSERVER_END' and events[-1]['data']['prior_event_count']==len(events)-1,source=source)
        add(name+'_precision_contract',events[0]['data']['double_precision']==17 and re.search(r'\d\.\d{15,17}',raw) is not None,source=source)
        def data(e):return e['data']['snapshot']
        def ctx(e):return e['data']['context']
        matrix_count=0
        def matrices(x):
            nonlocal matrix_count
            if isinstance(x,dict):
                if set(('rows','cols','layout','data'))<=x.keys():
                    matrix_count+=1
                    return x['layout']=='row_major' and len(x['data'])==x['rows']*x['cols'] and all(isinstance(v,(int,float)) and math.isfinite(v) for v in x['data'])
                return all(matrices(v) for v in x.values())
            if isinstance(x,list):return all(matrices(v) for v in x)
            return True
        add(name+'_all_matrix_dimensions_and_finite',all(matrices(e) for e in events),source=source);counts['matrices']+=matrix_count
        grouped=collections.defaultdict(list)
        for e in events:grouped[e['event']].append(e)
        add(name+'_all_schedule_branches',set(data(e).get('res') for e in grouped['IMU_OPPORTUNITY'] if data(e).get('initialized'))=={0,1,2,3},source=source)
        schedule_reasons=collections.Counter(data(e)['reason'] for e in grouped['IMU_OPPORTUNITY']);reason_counts.update(schedule_reasons)
        add(name+'_all_flags_false_visible',schedule_reasons['GNSS_ALL_FLAGS_FALSE']>=2,source=source)
        add(name+'_future_not_due_visible',schedule_reasons['NOT_DUE']>=1,source=source)
        add(name+'_completed_input_not_pending_visible',schedule_reasons['GNSS_INPUT_NOT_PENDING']>=1,source=source)
        add(name+'_uninitialized_visible',schedule_reasons['NOT_INITIALIZED']==1,source=source)
        add(name+'_invalid_entry_visible',count['GNSS_UPDATE_BLOCKED']==1,source=source)
        add(name+'_input_original_row_unknown',all(data(e)['original_gnss_row_id']=='UNKNOWN_NOT_PASSED_TO_ENGINE' for e in grouped['GNSS_INPUT']),source=source)
        cfg=data(grouped['CONFIGURATION'][0])
        readiness_fields=['source_aware_go2_readiness_lsim_enabled','source_aware_go2_readiness_low_scale','source_aware_go2_impact_or_rough_scale','source_aware_go2_motion_unknown_scale','source_aware_go2_in_place_turn_scale']
        add(name+'_actual_readiness_config',all(k in cfg for k in readiness_fields),source=source)
        cache={ctx(e)['gnss_input_seq']:data(e)['auxiliary_candidates'] for e in grouped['GNSS_INPUT']}
        map_source={'raw_doppler_velocity':'raw_doppler','go2_attitude_roll_pitch':'go2_roll_pitch','go2_horizontal_velocity':'go2_horizontal_velocity'}
        selected_ok=True
        for e in grouped['MEASUREMENT_SELECTED']:
            c=ctx(e);match=cache[c['gnss_input_seq']][map_source[c['source']]]
            selected_ok &= c['row_id']==match['selected_row_id'] and data(e)['time']==match['selected_input']['time'] and data(e)['actual_match_abs_dt']==match['selected_abs_dt']
        add(name+'_cached_candidate_equals_original_selected_row',selected_ok,count['MEASUREMENT_SELECTED'],source)
        starts={ctx(e)['sa_seq']:e for e in grouped['SA_EVALUATION_BEGIN']}
        ends={ctx(e)['sa_seq']:e for e in grouped['SA_EVALUATION']}
        add(name+'_sa_evaluate_one_begin_one_end',len(starts)==count['SA_EVALUATION_BEGIN'] and len(ends)==count['SA_EVALUATION'] and starts.keys()==ends.keys(),len(ends),source)
        sa_fields=['dz','H','dx_before','P_before','base_R']
        add(name+'_sa_snapshot_unchanged_through_policy',all(all(data(starts[k])[f]==data(e)[f] for f in sa_fields) for k,e in ends.items()),source=source)
        counts['sa_calls']+=len(ends)
        before={ctx(e)['ekf_seq']:e for e in grouped['EKF_BEFORE']};after={ctx(e)['ekf_seq']:e for e in grouped['EKF_AFTER']}
        add(name+'_ekf_sequence_exact_pairs',before.keys()==after.keys() and len(before)==count['EKF_BEFORE'] and len(after)==count['EKF_AFTER'],len(before),source)
        counts['ekf_updates']+=len(before)
        innovation_ok=True
        for k,e in before.items():
            b=data(e);a=data(after[k]);m=len(b['dz'])
            innovation_ok &= len(a['actual_Hdx'])==m and len(a['actual_innovation'])==m and all(a['actual_innovation'][i]==b['dz'][i]-a['actual_Hdx'][i] for i in range(m))
            counts['hdx_nonzero_updates']+=any(abs(v)>1e-12 for v in a['actual_Hdx'])
        add(name+'_actual_innovation_dz_minus_actual_Hdx',innovation_ok,source=source)
        by_attempt={ctx(e)['measurement_attempt_seq']:e for e in grouped['EKF_BEFORE']}
        matched_accepted=0;sa_ekf_ok=True
        for e in ends.values():
            if data(e)['result']['rejected']:continue
            b=by_attempt.get(ctx(e)['measurement_attempt_seq'])
            if b is None:sa_ekf_ok=False;continue
            matched_accepted+=1
            sa_ekf_ok &= all(data(b)[k]==data(e)[k] for k in ('dz','H','dx_before','P_before')) and data(b)['R']==data(e)['effective_R']
        add(name+'_same_attempt_effective_R_and_state_reach_EKF',sa_ekf_ok,matched_accepted,source)
        decision_reasons=collections.Counter(data(e)['reason'] for e in grouped['MEASUREMENT_DECISION']);reason_counts.update(decision_reasons)
        for e in grouped['MEASUREMENT_DECISION']:
            if data(e)['accepted'] and ctx(e)['source'] in map_source:counts['accepted_auxiliary_updates']+=1
        active=sum(data(e)['source_enabled'] for e in ends.values());trace=path.parents[1]/'SOURCE_AWARE_WEIGHT_TRACE.csv'
        trace_rows=list(csv.DictReader(trace.open())) if trace.exists() else []
        add(name+'_original_trace_rows_equal_active_policy_events',len(trace_rows)==active,str(active),source)
        if name=='all_active_sa':
            selections=[ctx(e) for e in grouped['MEASUREMENT_SELECTED'] if ctx(e)['gnss_input_seq']==1]
            add('tie_last_row_ids', {e['source']:e['row_id'] for e in selections}=={'raw_doppler_velocity':1,'go2_attitude_roll_pitch':1,'go2_horizontal_velocity':2},source=source)
            accepted=[(ctx(e)['source'],ctx(e)['row_id']) for e in grouped['MEASUREMENT_DECISION'] if data(e)['accepted'] and ctx(e)['source'] in map_source]
            add('accepted_reuse_is_visible',any(n>1 for n in collections.Counter(accepted).values()),str(collections.Counter(accepted)),source)
            hv=[data(e) for e in ends.values() if ctx(e)['source']=='go2_horizontal_velocity']
            add('hv_2D_R_and_999_metadata_visible',bool(hv) and all(e['base_R']['rows']==2 and e['effective_R']['rows']==2 and e['metadata']['std_xyz'][2]==999 for e in hv),source=source)
            alphas=[data(e)['result'] for e in ends.values() if data(e)['result']['oim_alpha_available']]
            add('actual_oim_alpha_branch_visible',bool(alphas) and all(e['oim_multiplier'] in (1,1.2,1.6) and math.isfinite(e['oim_raw_scale']) for e in alphas),len(alphas),source)
        if name=='sa_off':add('disabled_SA_still_visible_and_unit_R',bool(ends) and all(not data(e)['source_enabled'] and data(e)['result']['combined_R_scale']==1 and data(e)['base_R']==data(e)['effective_R'] for e in ends.values()),source=source)
        if name=='prior_sa_off':add('prior_off_has_EKF_without_fabricated_SA',any(ctx(e)['source']=='go2_horizontal_velocity' for e in before.values()) and not any(ctx(e)['source'] in ('go2_horizontal_velocity','go2_attitude_roll_pitch') for e in ends.values()),source=source)
        files.append(dict(source_path=source,sha256=sha(path),bytes=path.stat().st_size,event_count=len(events),data_mode='synthetic_fixture_only',synthetic_data_used=True,semisynthetic_data_used=False))
    needed=['DISABLED_BY_CONFIG','SOLVER_OR_PROVIDER_NOT_ENABLED','NO_LOADED_ROWS','NO_TIME_MATCH','NO_UPDATE_FLAG_ELIGIBLE_TIME_MATCH','PROVIDER_VALIDITY_LINEAGE_OR_SATELLITE_REJECT','INACTIVE_OR_NONPOSITIVE_STD','INACTIVE_OR_DIAGNOSTIC_OR_TRUTH_CLAIM_REJECT','RAW_DOPPLER_RESIDUAL_GATE_SA_OFF','SOURCE_AWARE_REJECT','YAW_HARD_STD_OR_RESIDUAL_GATE','ACCEPTED']
    for reason in needed:add('return_reason_'+reason,reason_counts[reason]>0,reason_counts[reason])
    add('full_Hdx_nonzero_fixture_coverage',counts['hdx_nonzero_updates']>0,counts['hdx_nonzero_updates'])
    scientific_source=base/'source_observed/cpp/legsa_v23_port_core/src/kf_gins/gi_engine.cpp'
    add('single_original_policy_evaluate_callsite',scientific_source.read_text().count('source_aware_policy_.evaluate(')==1,source=alias(scientific_source))
    observer_source=base/'source_observed/cpp/legsa_v23_port_core/src/kf_gins/gi_observer.cpp'
    add('observer_no_policy_evaluate', '.evaluate(' not in observer_source.read_text(),source=alias(observer_source))
    add('observer_no_live_shadow_inverse_or_multiply',not re.search(r'\b(inverse|multiply)\s*\(',observer_source.read_text()),source=alias(observer_source))
    for original in refs:
        files.append(dict(source_path=alias(original),sha256=sha(original),bytes=original.stat().st_size,event_count='',data_mode='synthetic_fixture_only',synthetic_data_used=True,semisynthetic_data_used=False))
    commands=json.loads((base/'build_logs/COMMANDS.json').read_text())
    native=[r for r in commands if r.get('synthetic_native_process')]
    add('exact_native_fixture_process_count',len(native)==3,str(len(native)))
    add('native_fixture_no_failed_process',all(r['exit_code']==0 for r in native))
    add('all_build_commands_pass',all(r['exit_code']==0 for r in commands))
    with (here/'SYNTHETIC_CHECKS.csv').open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=['check_id','status','details','source_path'],lineterminator='\n');writer.writeheader();writer.writerows(checks)
    with (here/'SYNTHETIC_FILES.csv').open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=['source_path','sha256','bytes','event_count','data_mode','synthetic_data_used','semisynthetic_data_used'],lineterminator='\n');writer.writeheader();writer.writerows(files)
    receipt=dict(data_mode='synthetic_fixture_only',synthetic_data_used=True,semisynthetic_data_used=False,real_native_processes=0,native_fixture_processes=len(native),fixture_subscenarios=33,fixture_failures=sum(r['exit_code']!=0 for r in native),fixture_retries=0,evaluator_processes=0,provider_processes=0,real_input_payload_reads=0,checks=len(checks),passed=sum(r['status']=='PASS' for r in checks),failed=[r for r in checks if r['status']=='FAIL'],counts=dict(counts),event_counts=dict(event_counts),reason_counts=dict(reason_counts),scientific_file_byte_comparisons=38,scientific_noninterference_scope='11 pure-synthetic scenarios in each of 3 native processes; no statement about 11 real objects',validation_script_sha256=sha(Path(__file__)),fixture_source_sha256=sha(here/'synthetic_fixture.cpp'))
    (here/'SYNTHETIC_RECEIPT.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(json.dumps({k:receipt[k] for k in ['checks','passed','failed','counts','native_fixture_processes']},indent=2))
    raise SystemExit(bool(receipt['failed']))
if __name__=='__main__':main()
