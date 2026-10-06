"""Publish all sealed rows and three complete saved-payload figures; no GT opens/solver."""
import argparse
import csv
import datetime
import hashlib
import json
import pathlib
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

p = argparse.ArgumentParser(); p.add_argument('--stage', required=True); p.add_argument('--receipts', required=True)
args = p.parse_args(); stage, receipts = pathlib.Path(args.stage), pathlib.Path(args.receipts)
def sha(path): return hashlib.sha256(pathlib.Path(path).read_bytes()).hexdigest()
def load(path): return json.loads(pathlib.Path(path).read_text())
protocol = load(stage/'PREREGISTRATION.json'); seal = load(stage/'ALL_NATIVE_SEALED.json'); complete = load(stage/'ALL_OFFLINE_COMPLETE.json')
root_review = load(receipts/'FGO_SEGMENTED_ROOT_INDEPENDENT_REVIEW.json')
self_review = load(receipts/'FGO_SEGMENTED_INDEPENDENT_REVIEW.json')
assert root_review['all_checks_passed'] and root_review['native_seal_sha256'] == sha(stage/'ALL_NATIVE_SEALED.json')
assert root_review['preregistration_sha256'] == sha(stage/'PREREGISTRATION.json')
assert self_review['all_checks_passed'] and self_review['offline_complete_sha256'] == sha(stage/'ALL_OFFLINE_COMPLETE.json')
assert complete['all_three_offline_complete'] and complete['metric_row_count'] == 36
roots = load(stage/'LOCAL_ROOTS.json')['aliases']
def resolve(value):
    for key, root in roots.items(): value = value.replace(key, root)
    return pathlib.Path(value)
code = pathlib.Path(roots['<CODE_ROOT>'])
pins = {stage/'PREREGISTRATION.json': sha(stage/'PREREGISTRATION.json'), stage/'ALL_NATIVE_SEALED.json': sha(stage/'ALL_NATIVE_SEALED.json'), stage/'ALL_OFFLINE_COMPLETE.json': sha(stage/'ALL_OFFLINE_COMPLETE.json')}
def source_gate():
    for name, digest in protocol['execution_source_hashes'].items(): assert sha(code/name) == digest
    for path, digest in pins.items(): assert sha(path) == digest
source_gate()
for sequence in complete['sequences']:
    for name, digest in sequence['output_hashes'].items():
        path = stage/'evaluation'/sequence['sequence']/name
        assert sha(path) == digest; pins[path] = digest
    assert sha(stage/'evaluation'/sequence['sequence']/'EVALUATION.json') == root_review['evaluation_pins'][sequence['sequence']]['evaluation_json_sha256']
    assert sha(stage/'evaluation'/sequence['sequence']/'METRICS.csv') == root_review['evaluation_pins'][sequence['sequence']]['metrics_csv_sha256']
output = stage/'PUBLICATION'; output.mkdir(exist_ok=False)
def csv_rows(filename, rows):
    fields = list(dict.fromkeys(key for row in rows for key in row))
    with (output/filename).open('x', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields); writer.writeheader(); writer.writerows(rows)
all_rows = []
evaluations = {}
for sequence in protocol['new_native_sequences']:
    evaluations[sequence] = load(stage/'evaluation'/sequence/'EVALUATION.json')
    all_rows.extend(evaluations[sequence]['rows'])
assert len(all_rows) == 36
csv_rows('ALL_36_METRIC_ROWS.csv', all_rows)
for role in ('PRIMARY_DYNAMIC_ONLY', 'SECONDARY_ALL_VALID_POSITION'):
    for support in ('OWN_VALID', 'COMMON_THREE_TIME_KEYS'):
        rows = [row for row in all_rows if row['support_role'] == role and row['support'] == support]
        assert len(rows) == 9
        csv_rows(role+'_'+support+'.csv', rows)
ledger, initialization_rows = [], []
for sequence in protocol['new_native_sequences']:
    methods = {**seal['comparison_identities'][sequence], 'OISAM_STRICT_HISTORICAL':
               {'path': '<FGO_ROOT>/runs/'+sequence+'/OISAM/STRICT', 'run_json_sha256': ''}}
    # Locate the original strict identity from the preserved final stage's actual RUN.
    strict_candidates = list(resolve('<FGO_ROOT>/runs/'+sequence+'/OISAM').glob('*/RUN.json'))
    assert len(strict_candidates) == 1
    methods['OISAM_STRICT_HISTORICAL']['path'] = str(strict_candidates[0].parent)
    methods['OISAM_STRICT_HISTORICAL']['run_json_sha256'] = sha(strict_candidates[0])
    for method, binding in methods.items():
        directory = resolve(binding['path']); run = load(directory/'RUN.json')
        assert sha(directory/'RUN.json') == binding['run_json_sha256']
        for name, digest in run['output_hashes'].items(): assert sha(directory/name) == digest
        states = pd.read_csv(directory/'STATES.csv')
        events = {}
        event_path = directory/'SOLVER_EVENTS.jsonl'
        if event_path.exists():
            for line in event_path.read_text().splitlines():
                event = json.loads(line)
                if 'time_rel_s' in event: events.setdefault(event['time_rel_s'], []).append(event)
        if method == 'OISAM':
            blocks = load(directory/'BLOCKS.json')
            for block in blocks:
                for init in block['initializations']:
                    initialization_rows.append({'sequence': sequence, 'block_id': block['block_id'],
                        'actual_initialization_s': init['start_s'], 'gnss_source_timestamp_s': init['gnss_provider_time_rel_s'],
                        'yaw_deg': init['yaw_deg'], 'yaw_std_deg': init['yaw_std_deg'],
                        'initialization_reason': init['reason'], 'reference_used': False,
                        'body_rate_source_timestamp_s': init['initial_body_rate']['effective_timestamp_rel_s'],
                        'body_rate_age_s': init['initial_body_rate']['age_at_initialization_s'],
                        'body_rate_frd_radps': json.dumps(init['initial_body_rate']['body_rate_frd_radps']),
                        'gnss1_velocity_ned_mps': json.dumps(init['initial_velocity']['gnss1_velocity_ned_mps']),
                        'imu_velocity_ned_mps': json.dumps(init['initial_velocity']['imu_velocity_ned_mps']),
                        'position_llh_deg_m': json.dumps(init['position_llh_deg_m']),
                        'singleton_prior_only': block['singleton_prior_only'], 'is_dynamic_solution': False})
        spec_start = next(row['window_start_s'] for row in all_rows if row['sequence_id'] == sequence)
        spec_end = next(row['window_end_s'] for row in all_rows if row['sequence_id'] == sequence)
        for row in states.to_dict('records'):
            event_items = events.get(row['time_rel_s'], [])
            nonlinear = [e for e in event_items if 'nonlinear_status' in e]
            event = nonlinear[-1] if nonlinear else (event_items[-1] if event_items else {})
            ledger.append({'sequence': sequence, 'identity_role': 'STRICT_SINGLE_INITIALIZATION_HISTORICAL' if method == 'OISAM_STRICT_HISTORICAL' else 'NEW_PREREGISTERED_TRUE_GAP_BLOCKS' if method == 'OISAM' else 'REUSED_FULL_BATCH_NATIVE',
                'method': method, 'time_s': row['time_rel_s'], 'valid': row['valid'], 'status': row['status'],
                'block_id': row.get('block_id'), 'prior_only': row.get('prior_only', int(row['status'] == 'INITIALIZED')),
                'dynamic_valid': row.get('dynamic_valid'), 'inside_original_formal_window': spec_start <= row['time_rel_s'] <= spec_end,
                'nonlinear_status': event.get('nonlinear_status'), 'nonlinear_converged': event.get('nonlinear_converged'),
                'nonlinear_solution_usable': event.get('nonlinear_solution_usable'), 'nonlinear_iterations': event.get('nonlinear_iterations'),
                'event_mode': event.get('mode'), 'event_reason': event.get('reason'),
                'native_run_sha256': binding['run_json_sha256'], 'states_sha256': sha(directory/'STATES.csv')})
csv_rows('ALL_SELECTED_NATIVE_EPOCH_LEDGER.csv', ledger)
csv_rows('ALL_11_INITIALIZATION_RECORDS.csv', initialization_rows)
assert len(initialization_rows) == 11
colors = {'OISAM': '#0072B2', 'WEN_TC': '#D55E00', 'GNC': '#009E73'}
labels = {'OISAM': 'OiSAM: source-gap blocks', 'WEN_TC': 'Wen TC: reused full batch', 'GNC': 'GNC: reused full batch'}
for sequence in protocol['new_native_sequences']:
    evaluation = evaluations[sequence]; role = 'PRIMARY_DYNAMIC_ONLY'
    anchor = np.deg2rad(evaluation['anchor_llh_deg_m'][:2]); lat, lon = anchor
    rotation = np.array([[-np.sin(lat)*np.cos(lon), -np.sin(lat)*np.sin(lon), np.cos(lat)],
                         [-np.sin(lon), np.cos(lon), 0],
                         [-np.cos(lat)*np.cos(lon), -np.cos(lat)*np.sin(lon), -np.sin(lat)]])
    fig, axes = plt.subplots(3, 2, figsize=(13, 12), constrained_layout=True)
    track, horizontal, vertical, position, yaw, support = axes.ravel()
    own_rows = {row['method_id']: row for row in evaluation['rows'] if row['support_role'] == role and row['support'] == 'OWN_VALID'}
    oi_trajectory = pd.read_csv(stage/'evaluation'/sequence/('OISAM_'+role+'_TRAJECTORY.csv'))
    truth_xyz = oi_trajectory[['truth_x_ecef_m', 'truth_y_ecef_m', 'truth_z_ecef_m']].to_numpy(float)
    origin = truth_xyz[0]; truth_local = (truth_xyz-origin)@rotation.T
    track.plot(truth_local[:, 1], truth_local[:, 0], color='.45', linewidth=1, label='Shared GNSS reference: GNSS1')
    for lane, method in enumerate(('OISAM', 'WEN_TC', 'GNC')):
        directory = stage/'evaluation'/sequence
        errors = pd.read_csv(directory/(method+'_'+role+'_ERRORS.csv'))
        trajectory = pd.read_csv(directory/(method+'_'+role+'_TRAJECTORY.csv'))
        xyz = trajectory[['x_ecef_m', 'y_ecef_m', 'z_ecef_m']].to_numpy(float)
        local = (xyz-origin)@rotation.T
        count = own_rows[method]['matched_epoch_count']; expected = own_rows[method]['expected_epoch_count']
        label = labels[method]+f' ({count}/{expected})'
        track.plot(local[:, 1], local[:, 0], color=colors[method], linewidth=.9, label=label)
        horizontal.plot(errors.time, errors.horizontal_err_m, color=colors[method], linewidth=.9, label=label)
        vertical.plot(errors.time, errors.err_u_m, color=colors[method], linewidth=.9)
        position.plot(errors.time, errors.position_3d_err_m, color=colors[method], linewidth=.9)
        valid = errors.valid.to_numpy(int) == 1
        support.scatter(errors.time[valid], np.full(valid.sum(), lane), color=colors[method], s=5)
        support.scatter(errors.time[~valid], np.full((~valid).sum(), lane), color='black', marker='x', s=20)
        if method == 'OISAM':
            yaw.plot(errors.time, errors.yaw_err_deg, color=colors[method], linewidth=.9)
            for init in [r for r in initialization_rows if r['sequence'] == sequence]:
                stamp = init['actual_initialization_s']
                for ax in (horizontal, vertical, position, yaw): ax.axvline(stamp, color='.6', linestyle=':', linewidth=.6)
                if errors.time.min() <= stamp <= errors.time.max(): support.scatter([stamp], [lane], facecolors='none', edgecolors='#E69F00', s=55, zorder=5)
            if sequence == 'BY2O':
                sample = errors[errors.time == 3286]
                yaw.scatter(sample.time, sample.yaw_err_deg, marker='s', facecolors='none', edgecolors='red', s=55, label='3286: usable NO_CONVERGENCE')
    track.set(xlabel='East (m)', ylabel='North (m)', title='Same GNSS1 point; full window'); track.axis('equal'); track.legend(fontsize=7)
    horizontal.set(ylabel='Horizontal error (m)', title='All saved dynamic supports'); horizontal.legend(fontsize=7)
    vertical.set(ylabel='Signed Up error (m)', title='Vertical: no clipping')
    position.set(ylabel='3D error (m)', title='3D: no clipping')
    yaw.set(ylabel='Own OiSAM yaw error (deg)', title='Wen/GNC estimate no attitude score')
    if sequence == 'BY2O': yaw.legend(fontsize=7)
    support.set(yticks=[0,1,2], yticklabels=['OiSAM','Wen TC','GNC'], title='Dots: dynamic valid; x: unavailable/prior; ring: A1 seed', ylim=(-.6,2.6))
    for ax in (horizontal, vertical, position, yaw, support): ax.set_xlabel('Original sequence time (s)'); ax.grid(alpha=.2)
    fig.suptitle(sequence+' | Separate engineering gap diagnostic | Original denominator retained\nGNSS1 physical point, fixed N/E/Up frame; inputs and batch/current-node information differ', fontsize=12)
    fig.savefig(output/(sequence+'_FULL_WINDOW.png'), dpi=160)
    fig.savefig(output/(sequence+'_FULL_WINDOW.pdf'))
    plt.close(fig)
source_gate()
hashes = {path.name: sha(path) for path in sorted(output.iterdir()) if path.is_file()}
files = [path for path in stage.rglob('*') if path.is_file()]; dirs = [path for path in stage.rglob('*') if path.is_dir()]
allocation_proxy = sum((path.stat().st_size+262143)//262144*262144 for path in files)+len(dirs)*262144
assert allocation_proxy <= protocol['new_stage_budget_bytes']
receipt = {'schema': 'fgo.segmented.saved-payload.publication.v1', 'completed_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
    'wrapper_sha256': sha(__file__), 'native_seal_sha256': sha(stage/'ALL_NATIVE_SEALED.json'), 'offline_complete_sha256': sha(stage/'ALL_OFFLINE_COMPLETE.json'),
    'self_independent_review_sha256': sha(receipts/'FGO_SEGMENTED_INDEPENDENT_REVIEW.json'), 'root_independent_review_sha256': sha(receipts/'FGO_SEGMENTED_ROOT_INDEPENDENT_REVIEW.json'),
    'all36metric_rows': 36, 'native_epoch_ledger_rows': len(ledger), 'actual_initializations': 11,
    'new_native_calls': 0, 'new_evaluator_calls': 0, 'raw_reference_payload_opens': 0,
    'source872_before_after_match': True, 'no_output_time_or_score_selection': True, 'no_axis_clip': True,
    'primary_all_prior_only_excluded': True, 'figures_rendered_from_saved_primary_payloads_only': True,
    'allocated_stage_budget_proxy_bytes': allocation_proxy, 'is_actual_windows_allocation_API': False,
    'outputs_sha256': hashes}
with (output/'PUBLICATION_RECEIPT.json').open('x') as stream: json.dump(receipt, stream, ensure_ascii=False, indent=2); stream.write('\n')
print(json.dumps(receipt, ensure_ascii=False))
