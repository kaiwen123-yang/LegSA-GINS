#!/usr/bin/env python3
"""Read only this candidate's NEW synthetic outputs; never executes a binary."""
import csv
import hashlib
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
CODE = HERE.parents[5]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def csv_write(path, rows):
    with path.open('w', newline='') as stream:
        w = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator='\n')
        w.writeheader()
        w.writerows(rows)


def main():
    aliases = json.loads((CODE/'configs/paper_rebuild/V3_DEFINITION_ROOTS.local.json').read_text())['aliases']
    build_root = Path(aliases['<VALIDATION_BUILD_ROOT>'])
    output = build_root/'N09_RP_ONLY_fixture_v1'
    checks, scenarios = [], []
    def check(name, key, passed, details=''):
        checks.append(dict(scenario=name, check=key, status='PASS' if passed else 'FAIL', details=details))
    names = sorted(p.name for p in (output/'candidate_on').iterdir() if p.is_dir())
    check('ALL', '31_expected_scenarios', len(names)==31)
    negative = {'disabled','solver_off','no_rows','no_match','inactive','zero_std','nan_std',
                'tolerance_outside','tie_last_inactive','closest_inactive','no_gnss','implicit_validity'}
    negative.update(n for n in names if n.startswith('valid_'))
    fields = ['step','timestamp','state.time']
    for field in ['position_blh_rad_m','velocity_ned_mps','rpy_rad']:
        fields.extend(f'{field}[{i}]' for i in range(3))
    fields.extend(['qbn.w','qbn.x','qbn.y','qbn.z'])
    fields.extend(f'Cbn[{i},{j}]' for i in range(3) for j in range(3))
    for field in ['gyr_bias','acc_bias','gyr_scale','acc_scale']:
        fields.extend(f'{field}[{i}]' for i in range(3))
    fields.extend(f'P[{i},{j}]' for i in range(21) for j in range(21))
    event_total = 0
    for name in names:
        d = output/'candidate_on'/name
        baseline = output/'baseline'/name
        off = output/'candidate_off'/name
        values = list(csv.DictReader((d/'COUNTERS.csv').open()))
        last = {k:int(v) for k,v in values[-1].items() if k!='scenario'}
        science = [[float(x) for x in row if x!=''] for row in csv.reader((d/'STATE.csv').open())]
        base_science = [[float(x) for x in row if x!=''] for row in csv.reader((baseline/'STATE.csv').open())]
        check(name,'3_steps_full_state_and_441_P_values',len(science)==3 and all(len(row)==len(fields) for row in science),f'{len(fields)} fields per row including step')
        check(name,'all_saved_scientific_values_finite',all(math.isfinite(x) for row in science for x in row))
        check(name,'observer_on_off_state_byte_identity',(d/'STATE.csv').read_bytes()==(off/'STATE.csv').read_bytes())
        check(name,'observer_on_off_counter_byte_identity',(d/'COUNTERS.csv').read_bytes()==(off/'COUNTERS.csv').read_bytes())
        check(name,'observer_disabled_creates_no_event_log',not (off/'observer').exists())
        baseline_equal = (d/'STATE.csv').read_bytes()==(baseline/'STATE.csv').read_bytes()
        oracle = d/'ORACLE_STATE.csv'
        if name in negative:
            check(name,'negative_control_full_state_P_byte_identity_to_baseline',baseline_equal)
            old=list(csv.DictReader((baseline/'COUNTERS.csv').open()))
            keys=['propagations','gnss_updates','position_updates','rv_updates','yaw_attempts','rd_updates','rp_updates','rp_rejects','hv_updates']
            check(name,'negative_control_original_scientific_counters_unchanged',all(a[k]==b[k] for a,b in zip(values,old) for k in keys))
        else:
            check(name,'original_res_template_oracle_full_state_P_byte_identity',oracle.exists() and oracle.read_bytes()==(d/'STATE.csv').read_bytes())
        events=[json.loads(line) for line in (d/'observer/events.jsonl').open()]
        event_total += len(events)
        check(name,'jsonl_begin_end_sequence',events[0]['event']=='OBSERVER_BEGIN' and events[-1]['event']=='OBSERVER_END' and [r['event_seq'] for r in events]==list(range(1,len(events)+1)) and events[-1]['data']['prior_event_count']==len(events)-1)
        check(name,'arrival_remains_unknown',all(e['available_time']=='UNKNOWN' for e in events))
        by_kind={kind:[r for r in events if r['event']==kind] for kind in {r['event'] for r in events}}
        snapshots=lambda kind:[r['data']['snapshot'] for r in by_kind.get(kind,[])]
        check(name,'post_IMU_covariance_diagnostic_3_no_writes',len(snapshots('COVARIANCE_HEALTH'))==3 and all(r['dimension']==21 and r['filter_matrix_modified'] is False for r in snapshots('COVARIANCE_HEALTH')))
        check(name,'post_IMU_full_P_numerical_diagnostic',all(r['status']=='POSITIVE_DEFINITE_WITHIN_FIXED_NUMERIC_DIAGNOSTIC' for r in snapshots('COVARIANCE_HEALTH')))
        valid = name.startswith('valid_') or name=='implicit_validity'
        no_gnss = name=='no_gnss'
        qualified = name not in negative
        count = 2 if name=='same_time_new_identity' else 1
        rejected = name.startswith('rejected_')
        expected_inputs=0 if no_gnss else 2 if name in {'same_time_new_identity','superseded_pending'} else 1
        expected = dict(input_records=expected_inputs,consumed_records=expected_inputs,
                        superseded_records=int(name=='superseded_pending'),pending=0,
                        invalid_records=0 if valid or no_gnss else expected_inputs,
                        opportunities=0 if valid or no_gnss else count,
                        eligible=count if qualified else 0,attempts=count if qualified else 0,
                        accepted=count if qualified and not rejected else 0,
                        rejected=count if rejected else 0,skipped=1 if not valid and not no_gnss and not qualified else 0,
                        feedbacks=count if qualified else 0,
                        rp_only_consumed=0 if valid or no_gnss else count)
        check(name,'independent_counter_contract',all(last[k]==v for k,v in expected.items()),json.dumps({'expected':expected,'recorded':{k:last[k] for k in expected}},sort_keys=True))
        mapping={'RP_ONLY_INPUT':'input_records','RP_ONLY_OPPORTUNITY':'opportunities',
                 'RP_ONLY_ATTEMPT':'attempts','RP_ONLY_RESULT':'attempts','RP_ONLY_FEEDBACK':'feedbacks',
                 'RP_ONLY_CONSUMED':'consumed_records','RP_ONLY_SKIPPED':'skipped'}
        check(name,'independent_event_counts_match_counters',all(len(by_kind.get(event,[]))==last[k] for event,k in mapping.items()))
        if not valid:
            check(name,'no_GNSS_or_other_source_update',all(last[k]==0 for k in ['gnss_updates','position_updates','rv_updates','yaw_attempts','rd_updates','hv_updates']) and not by_kind.get('GNSS_UPDATE_ENTRY'))
            check(name,'invalid_source_is_never_marked_valid',all(r['gnss']['isvalid'] is False and r['gnss']['flags_or'] is False for r in snapshots('RP_ONLY_INPUT')))
            attempts=by_kind.get('MEASUREMENT_ATTEMPT',[])
            check(name,'only_original_RP_helper_attempts',len(attempts)==last['attempts'] and all(r['data']['context']['source']=='go2_attitude_roll_pitch' for r in attempts))
            check(name,'qualification_probe_does_not_evaluate_policy',len(by_kind.get('SA_EVALUATION',[]))==last['attempts'])
            check(name,'exactly_one_feedback_after_entered_branch',len(by_kind.get('FEEDBACK_BEFORE',[]))==last['attempts'] and len(by_kind.get('FEEDBACK_AFTER',[]))==last['attempts'])
            check(name,'feedback_clears_dx',all(all(v==0 for v in r['dx']) for r in snapshots('FEEDBACK_AFTER')))
            if not qualified:
                check(name,'no_eligible_RP_whole_propagation_no_split',last['propagations']==3 and not by_kind.get('IMU_SPLIT_BEFORE'))
        if qualified:
            for opportunity in by_kind['RP_ONLY_OPPORTUNITY']:
                ident=opportunity['data']['snapshot']['input_id']
                end=next(r for r in by_kind['RP_ONLY_CONSUMED'] if r['data']['snapshot']['input_id']==ident and r['event_seq']>opportunity['event_seq'])
                seq=[r['event'] for r in events if opportunity['event_seq']<r['event_seq']<end['event_seq'] and r['event'] in {'PROPAGATION_BEFORE','RP_ONLY_ATTEMPT','FEEDBACK_BEFORE'}]
                res=opportunity['data']['snapshot']['rp_only_res']
                expected_seq={1:['RP_ONLY_ATTEMPT','FEEDBACK_BEFORE','PROPAGATION_BEFORE'],2:['PROPAGATION_BEFORE','RP_ONLY_ATTEMPT','FEEDBACK_BEFORE'],3:['PROPAGATION_BEFORE','RP_ONLY_ATTEMPT','FEEDBACK_BEFORE','PROPAGATION_BEFORE']}[res]
                check(name,f'res{res}_input{ident}_original_order',seq==expected_seq,json.dumps(seq))
            if rejected:
                check(name,'original_SA_rejection_preserved',all(r['reason']=='SOURCE_AWARE_REJECT' and not r['accepted'] for r in snapshots('MEASUREMENT_DECISION')) and last['rp_rejects']==1)
            else:
                check(name,'actual_original_helper_acceptance',last['rp_updates']==count)
            selections=snapshots('MEASUREMENT_SELECTED')
            probe=next(r for r in snapshots('RP_ONLY_INPUT') if r['preinnovation_qualified'])
            expected_row=1 if name=='tie_last' else 0
            check(name,'original_selected_row_matches_qualification',all(r['data']['context']['row_id']==expected_row for r in by_kind.get('MEASUREMENT_SELECTED',[])) and all(r['time']==probe['candidate_time'] for r in selections))
        if name in {'tie_last_inactive','closest_inactive'}:
            check(name,'do_not_prefilter_inactive_nearest_row',snapshots('RP_ONLY_INPUT')[0]['candidate_row_id']==1 and snapshots('RP_ONLY_INPUT')[0]['qualification_reason']=='INACTIVE_OR_NONPOSITIVE_STD')
        if name=='future_pending':
            check(name,'future_not_consumed_before_event',values[0]['pending']=='1' and values[0]['opportunities']=='0' and values[1]['pending']=='0')
        diffs=[(row_index,field,a,b) for row_index,(aa,bb) in enumerate(zip(science,base_science),1) for field,a,b in zip(fields,aa,bb) if a!=b]
        first=diffs[0] if diffs else None
        scenarios.append(dict(scenario=name,baseline_state_byte_identical=baseline_equal,oracle_applicable=oracle.exists(),
                              oracle_state_byte_identical=oracle.read_bytes()==(d/'STATE.csv').read_bytes() if oracle.exists() else 'NOT_APPLICABLE',
                              first_different_step=first[0] if first else '',first_different_field=first[1] if first else '',
                              candidate_value=first[2] if first else '',baseline_value=first[3] if first else '',
                              difference=first[2]-first[3] if first else '',
                              **{k:last[k] for k in ['gnss_updates','rp_updates','rp_rejects','opportunities','eligible','attempts','accepted','rejected','feedbacks']},
                              source_path=f'<VALIDATION_BUILD_ROOT>/N09_RP_ONLY_fixture_v1/candidate_on/{name}',
                              data_mode='synthetic_fixture_only',synthetic_data_used=True,semisynthetic_data_used=False))
    copy_rows=list(csv.DictReader((HERE/'SOURCE_COPY_FILES.csv').open()))
    original=Path(aliases['<OBSERVED_SOURCE>'])
    check('ALL','original_observed_source_156_members_unchanged',len(copy_rows)==156 and all(sha(original/r['member'])==r['observed_source_sha256'] for r in copy_rows))
    common_paths=['include/legsa_v23_port_core/kf_gins/covariance_diagnostics.hpp','src/kf_gins/gi_engine.cpp','src/kf_gins/gi_observer.cpp']
    candidate=build_root/'source_N09_RP_ONLY'
    check('ALL','common_targets_no_symlink_inside_candidate',all(not (candidate/'cpp/legsa_v23_port_core'/p).is_symlink() and (candidate/'cpp/legsa_v23_port_core'/p).resolve().is_relative_to(candidate.resolve()) for p in common_paths))
    commands=json.loads((HERE/'COMMANDS.json').read_text())
    check('ALL','4_build_3_fixture_commands_completed',len(commands)==7 and all(r['exit_code']==0 for r in commands) and sum(r['synthetic_native_process'] for r in commands)==3)
    csv_write(HERE/'FIXTURE_CHECKS.csv',checks)
    csv_write(HERE/'FIXTURE_SCENARIOS.csv',scenarios)
    file_rows=[]
    for p in sorted(output.rglob('*')):
        if p.is_file():file_rows.append(dict(source_path='<VALIDATION_BUILD_ROOT>/'+str(p.relative_to(build_root)),bytes=p.stat().st_size,sha256=sha(p),data_mode='synthetic_fixture_only'))
    csv_write(HERE/'FIXTURE_FILES.csv',file_rows)
    receipt=dict(status='PASS' if all(r['status']=='PASS' for r in checks) else 'FAIL',
                 checks=len(checks),passed=sum(r['status']=='PASS' for r in checks),
                 failed=sum(r['status']=='FAIL' for r in checks),synthetic_native_processes=3,
                 native_process_failures=sum(r['synthetic_native_process'] and r['exit_code']!=0 for r in commands),
                 native_retries=0,real_native_processes=0,evaluator_processes=0,
                 scenarios_per_process=31,scenario_executions=93,oracle_engines_per_process=13,
                 additional_oracle_engine_instances=39,observed_event_rows=event_total,
                 negative_control_scenarios=len(negative),oracle_scenarios=13,
                 reference_reads=0,real_provider_reads=0,
                 data_mode='synthetic_fixture_only',synthetic_data_used=True,semisynthetic_data_used=False,
                 scope='New pure synthetic checks only; real candidate identities not executed by this worker')
    (HERE/'FIXTURE_RECEIPT.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(json.dumps(receipt))
    for row in checks:
        if row['status']=='FAIL':print('FAIL',row)
    return int(receipt['failed']>0)


if __name__=='__main__':
    raise SystemExit(main())
