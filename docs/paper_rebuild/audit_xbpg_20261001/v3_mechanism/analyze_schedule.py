#!/usr/bin/env python3
"""Read new observer JSONL; no filter/evaluator/provider imports or calls."""
import argparse
import collections
import csv
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
AUX = {'raw_doppler_velocity': 'raw_doppler', 'go2_attitude_roll_pitch': 'go2_roll_pitch',
       'go2_horizontal_velocity': 'go2_horizontal_velocity'}
MAIN = {'receiver_position': 'has_position', 'receiver_velocity': 'has_velocity', 'dual_antenna_yaw': 'has_yaw'}


def event_lines(path):
    with path.open() as stream:
        yield from enumerate(stream, 1)


def write(path, rows):
    if not rows:
        return
    fields = list(dict.fromkeys(k for r in rows for k in r))
    with path.open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fields, lineterminator='\n'); writer.writeheader(); writer.writerows(rows)


def time_branch(previous, current, measurement, tolerance):
    if abs(previous - measurement) < tolerance:
        return 1
    if abs(current - measurement) <= tolerance:
        return 2
    if previous < measurement < current:
        return 3
    return 0


def candidate_quality(source, candidate, config):
    if not candidate.get('match_found'):
        return False
    row = candidate['selected_input']
    if source == 'raw_doppler_velocity':
        return (row['valid'] and row['lineage_valid'] and row['provider_status'] == 'available'
                and row['sat_count'] >= config['raw_doppler_min_sat'])
    if source == 'go2_attitude_roll_pitch':
        return row['source_status'] == 'active' and row['std_roll_rad'] > 0 and row['std_pitch_rad'] > 0
    return (row['update_flag'] and row['source_status'] == 'active' and (row['diagnostic_only'] or config['hv_horizontal_enabled'])
            and not row['go2_velocity_truth_claim'])


def windows(t, group):
    if not 66 <= t <= 340:
        return []
    result = ['full']
    if group in ['A1', 'A2']:
        result.append('before' if t < 196.2 else 'during' if t < 216.2 else 'after')
    return result


def analyze(path, item, output, public):
    config = {}; inputs = {}; attempts = {}; opportunity = collections.Counter(); kinematics = collections.Counter()
    seen = collections.defaultdict(set); summary = collections.defaultdict(collections.Counter)
    examples = {}; events = collections.Counter(); last_seq = 0; roll = []; pitch = []; began = False; ended = False
    source_alias = '<MECHANISM_ROOT>/replays/' + item['run_id'] + '/observed/observer/' + path.name
    for line_number, line in event_lines(path):
        event = json.loads(line); seq = event['event_seq']; assert seq == last_seq + 1; last_seq = seq
        assert event['run_id'] == item['run_id'] and not ended
        name = event['event']; events[name] += 1
        if name == 'OBSERVER_BEGIN':
            assert not began and seq == 1; began = True; continue
        if name == 'OBSERVER_END':
            assert began and event['data']['prior_event_count'] == seq - 1; ended = True; continue
        assert began
        c = event['data']['context']; s = event['data']['snapshot']; gid = c['gnss_input_seq']
        if name == 'CONFIGURATION':
            config = s
        elif name == 'GNSS_INPUT':
            inputs[gid] = {'event_seq': seq, 'line': line_number, 'time': s['effective']['time'],
                           'gnss': s['effective'], 'aux': s['auxiliary_candidates'], 'scheduled': set(),
                           'time_conditions': set(), 'blocked_witness': None}
        elif name == 'IMU_OPPORTUNITY':
            for window in windows(c['imu_current_time'], item['group']):
                opportunity[(window, s['reason'], s.get('res', 0))] += 1
            if gid in inputs and s.get('initialized'):
                record = inputs[gid]
                branch = time_branch(c['imu_previous_time'], c['imu_current_time'], record['time'], config['TIME_ALIGN_ERR'])
                if branch:
                    record['time_conditions'].add(seq)
                if s['res']:
                    record['scheduled'].add(seq)
                if branch and not s['gnss']['flags_or']:
                    record['blocked_witness'] = record['blocked_witness'] or event
        elif name == 'MEASUREMENT_ATTEMPT':
            attempts[c['measurement_attempt_seq']] = {'event_seq': seq, 'source': c['source'], 'time': c['measurement_time'],
                'gnss_input_seq': gid, 'selected_row_id': '', 'accepted': False, 'decision': 'NO_DECISION_RECORDED'}
        elif name == 'MEASUREMENT_SELECTED':
            attempts[c['measurement_attempt_seq']]['selected_row_id'] = c['row_id']
        elif name == 'MEASUREMENT_DECISION':
            rec = attempts[c['measurement_attempt_seq']]
            rec.update(accepted=s['accepted'], decision=s['reason'], decision_event_seq=seq)
            for window in windows(rec['time'], item['group']):
                count = summary[(window, c['source'])]; count['function_entries'] += 1
                selected = rec['selected_row_id'] != '' or c['source'] in MAIN
                count['selected_measurement_attempts'] += selected
                count['accepted' if s['accepted'] else 'not_accepted_function_returns'] += 1
                count['selected_but_rejected'] += bool(selected and not s['accepted'])
                count['no_selected_measurement_returns'] += not selected
                count['decision:' + s['reason']] += 1
                if s['accepted'] and rec['selected_row_id'] != '':
                    row = rec['selected_row_id']; token = (window, c['source'])
                    count['repeated_accepted_same_loaded_row'] += row in seen[token]
                    seen[token].add(row)
                example_key = window + ':' + c['source'] + ':' + s['reason']
                examples.setdefault(example_key, {'event': event, 'attempt': dict(rec), 'source_line': line_number})
        elif name in ['VELOCITY_KINEMATICS', 'RAW_DOPPLER_KINEMATICS']:
            imu = s['imu_at_update']; state = s['state']; bias = math.sqrt(sum(float(x)**2 for x in state['gyr_bias']))
            key = (name, c['res'], imu['compensated'], bias > 0)
            kinematics[key] += 1
            examples.setdefault('N11:' + ':'.join(map(str, key)), {'event': event, 'source_line': line_number})
        elif name == 'YAW_GATE_INPUT':
            state = s['state']; roll.append(state['rpy_rad'][0]); pitch.append(state['rpy_rad'][1])
    assert began and ended and config and inputs and not any(a['decision'] == 'NO_DECISION_RECORDED' for a in attempts.values())
    detailed = []
    for gid, record in inputs.items():
        g = record['gnss']
        for source in [*MAIN, *AUX]:
            if source in MAIN:
                config_enabled = source == 'receiver_position' or config['receiver_velocity_enabled' if source == 'receiver_velocity' else 'dual_yaw_enabled']
                solver_enabled = True; enabled = config_enabled
                present = True; match = True; qualified = bool(g[MAIN[source]]); loaded_id = 'GNSS_INPUT_SEQUENCE:' + str(gid)
            else:
                candidate = record['aux'][AUX[source]]
                config_enabled = candidate['config_enabled']; solver_enabled = candidate['solver_enabled']
                enabled = config_enabled and solver_enabled
                present = candidate['loaded_rows'] > 0; match = candidate['match_found']
                qualified = candidate_quality(source, candidate, config); loaded_id = candidate['selected_row_id']
            blocked = bool(enabled and qualified and record['time_conditions'] and not g['flags_or'])
            one = {'run_id': item['run_id'], 'group': item['group'], 'method_id': item['method_id'],
                   'gnss_input_seq': gid, 'gnss_time': record['time'], 'source': source, 'loaded_input_exists': present,
                   'config_enabled': config_enabled, 'solver_enabled': solver_enabled, 'effective_enabled': enabled,
                   'time_matched_candidate': match, 'preinnovation_quality_qualified': qualified,
                   'selected_loaded_row_id': loaded_id, 'position_valid': g['has_position'], 'velocity_valid': g['has_velocity'],
                   'yaw_valid': g['has_yaw'], 'flags_or': g['flags_or'],
                   'time_condition_without_validity': bool(record['time_conditions']),
                   'actual_gnss_scheduled': bool(record['scheduled']), 'qualified_but_entry_blocked': blocked,
                   'available_time': 'UNKNOWN', 'source_path': source_alias, 'source_event_seq': record['event_seq']}
            detailed.append(one)
            if blocked:
                examples.setdefault('BLOCKED:' + source, {'event': record['blocked_witness'], 'candidate': record['aux'].get(AUX.get(source)), 'input': one})
            for window in windows(record['time'], item['group']):
                count = summary[(window, source)]
                for key, yes in [('gnss_input_events', True), ('source_enabled_input_events', enabled),
                     ('loaded_input_exists_events', present), ('time_matched_candidate_events', match),
                     ('preinnovation_quality_qualified_events', qualified),
                     ('time_condition_without_validity_events', bool(record['time_conditions'])),
                     ('actual_gnss_scheduled_events', bool(record['scheduled'])), ('qualified_but_entry_blocked_events', blocked),
                     ('disabled_by_config_events', not config_enabled),
                     ('config_enabled_solver_unavailable_events', config_enabled and not solver_enabled),
                     ('config_enabled_no_usable_candidate_events', config_enabled and not qualified),
                     ('flags_all_false_events', not g['flags_or'])]:
                    count[key] += int(yes)
    rows = []
    for (window, source), count in sorted(summary.items()):
        rows.append({'run_id': item['run_id'], 'group': item['group'], 'method_id': item['method_id'],
                     'window': window, 'source': source, **count, 'source_path': source_alias,
                     'scope': 'replay_observed; GNSS-input events vs attempts vs IMU opportunities are separate denominators'})
    write(public / (item['run_id'] + '_SCHEDULING.csv'), rows)
    manifest = json.loads((path.parent.parent / 'RUN_MANIFEST.json').read_text())
    counter_keys = {'receiver_position': 'position_update_count', 'receiver_velocity': 'receiver_velocity_update_count',
                    'dual_antenna_yaw': 'dual_yaw_accepted_count', 'raw_doppler_velocity': 'raw_doppler_update_count',
                    'go2_attitude_roll_pitch': 'go2_roll_pitch_update_count',
                    'go2_horizontal_velocity': 'go2_horizontal_velocity_update_count'}
    checks = []
    for source, field in counter_keys.items():
        actual = sum(a['accepted'] for a in attempts.values() if a['source'] == source)
        checks.append({'source': source, 'manifest_field': field, 'recorded_value': manifest[field],
                       'event_accepted_count': actual, 'status': 'EXACT_EQUAL' if actual == manifest[field] else 'MISMATCH'})
    write(public / (item['run_id'] + '_SCHEDULE_COUNTER_CHECKS.csv'), checks)
    assert all(c['status'] == 'EXACT_EQUAL' for c in checks), checks
    write(output / 'GNSS_CANDIDATE_FUNNEL.csv', detailed)
    write(output / 'MEASUREMENT_ATTEMPTS.csv', [{'attempt_seq': k, **v} for k, v in attempts.items()])
    write(public / (item['run_id'] + '_OPPORTUNITIES.csv'),
          [{'window': w, 'reason': r, 'res': res, 'imu_opportunities': n, 'source_path': source_alias}
           for (w, r, res), n in sorted(opportunity.items())])
    write(public / (item['run_id'] + '_KINEMATICS.csv'),
          [{'event_type': n, 'res': r, 'imu_compensated': comp, 'nonzero_gyr_bias': bias, 'events': count,
            'source_path': source_alias, 'scope': 'condition observed; no corrected closed loop'}
           for (n, r, comp, bias), count in sorted(kinematics.items())])
    # Full original event snapshots remain in the isolated analysis root; public index only.
    (output / 'SCHEDULE_WITNESSES.json').write_text(json.dumps(examples, indent=2) + '\n')
    witness_rows = []
    for key, example in examples.items():
        ev = example['event']; ctx = ev['data']['context']
        witness_rows.append({'run_id': item['run_id'], 'witness': key, 'source_path': source_alias,
                             'event_seq': ev['event_seq'], 'gnss_time': ctx['gnss_time'], 'res': ctx['res'],
                             'snapshot_path': '<MECHANISM_ROOT>/analysis/' + item['run_id'] + '/schedule/SCHEDULE_WITNESSES.json',
                             'json_key': key})
    write(public / (item['run_id'] + '_SCHEDULE_WITNESSES.csv'), witness_rows)
    receipt = {'run_id': item['run_id'], 'rows_read': sum(events.values()), 'event_counts': dict(events),
               'stream_complete': True, 'validation_calculation': True, 'native_calls': 0, 'evaluator_calls': 0,
               'data_mode': item['data_mode'], 'synthetic_data_used': False,
               'semisynthetic_data_used': item['semisynthetic_data_used'] == 'True',
               'roll_range_rad_at_yaw_attempt': [min(roll), max(roll)] if roll else None,
               'pitch_range_rad_at_yaw_attempt': [min(pitch), max(pitch)] if pitch else None,
               'baseline_vector': 'NOT_IN_GNSS_STRUCT; not reconstructed from error', 'available_time': 'UNKNOWN'}
    (public / (item['run_id'] + '_SCHEDULE_RECEIPT.json')).write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps({'run_id': item['run_id'], 'events_read': sum(events.values()), 'gnss_inputs': len(inputs), 'attempts': len(attempts)}))


def main():
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('--roots', required=True, type=Path); p.add_argument('--run-id', required=True)
    args = p.parse_args(); aliases = json.loads(args.roots.read_text())['aliases']
    with (HERE / 'DIAGNOSTIC_QUEUE.csv').open() as stream:
        item = next(r for r in csv.DictReader(stream) if r['run_id'] == args.run_id)
    root = Path(aliases['<MECHANISM_ROOT>']); observer = root / 'replays' / args.run_id / 'observed' / 'observer'
    replay = json.loads((observer.parent / 'REPLAY_RECEIPT.json').read_text())
    assert replay['status'] == 'COMPLETED_BYTE_IDENTICAL' and replay['scientific_manifest_match']
    assert replay['observer_identity_status'] == 'BYTE_IDENTICAL' and replay['access_passed']
    files = list(observer.glob('*.jsonl')); assert len(files) == 1, files
    output = root / 'analysis' / args.run_id / 'schedule'; output.mkdir(parents=True, exist_ok=False)
    public = HERE / 'groups' / item['group']; public.mkdir(parents=True, exist_ok=True)
    analyze(files[0], item, output, public)


if __name__ == '__main__':
    main()
