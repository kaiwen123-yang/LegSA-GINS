"""Independent saved-payload arithmetic/identity check; no pipeline imports or GT opens."""
import argparse
import csv
import datetime
import hashlib
import json
import pathlib
import zipfile
import numpy as np
import pandas as pd

p = argparse.ArgumentParser()
p.add_argument('--stage', required=True)
p.add_argument('--out', required=True)
args = p.parse_args()
stage, out = pathlib.Path(args.stage), pathlib.Path(args.out)
def sha(path):
    h = hashlib.sha256()
    with pathlib.Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024*1024), b''):
            h.update(chunk)
    return h.hexdigest()
def load(path):
    return json.loads(pathlib.Path(path).read_text())
roots = load(stage/'LOCAL_ROOTS.json')['aliases']
def resolve(value):
    for key, root in roots.items(): value = value.replace(key, root)
    return pathlib.Path(value)
protocol = load(stage/'PREREGISTRATION.json')
seal, complete = load(stage/'ALL_NATIVE_SEALED.json'), load(stage/'ALL_OFFLINE_COMPLETE.json')
assert complete['native_seal_sha256'] == sha(stage/'ALL_NATIVE_SEALED.json')
assert complete['protocol_sha256'] == seal['protocol_sha256'] == sha(stage/'PREREGISTRATION.json')
assert complete['new_offline_count'] == 3 and complete['metric_row_count'] == 36
assert complete['total_actual_offline_reference_payload_opens'] == 3
assert seal['new_native_count'] == 3 and seal['reused_original_full_batch_native_count'] == 6
assert seal['new_native_reference_opens'] == seal['reused_original_native_reference_opens'] == 0
scientific_pins = {stage/'ALL_NATIVE_SEALED.json': sha(stage/'ALL_NATIVE_SEALED.json'),
                   stage/'ALL_OFFLINE_COMPLETE.json': sha(stage/'ALL_OFFLINE_COMPLETE.json'),
                   stage/'PREREGISTRATION.json': sha(stage/'PREREGISTRATION.json')}
code = pathlib.Path(roots['<CODE_ROOT>'])
source_inventory = {str(f.relative_to(code)) for f in (code/'src/legsa_gins').rglob('*.py')}
source_inventory.update(str(f.relative_to(code)) for f in (code/'src/legsa_gins/paper_rebuild/fgo_comparison').iterdir() if f.suffix in ('.cc', '.c'))
assert source_inventory == set(protocol['execution_source_hashes'])
for name, digest in protocol['execution_source_hashes'].items(): assert sha(code/name) == digest
assert len(source_inventory) == 872
for key in ('method_config', 'execution_contract'):
    assert sha(code/protocol[key+'_path']) == protocol[key+'_sha256']
for key in ('native_controller', 'preparation_helper', 'registration_helper'):
    filename = {'native_controller': 'run_fgo_segmented_native.py', 'preparation_helper': 'prepare_fgo_segmented.py', 'registration_helper': 'freeze_fgo_segmented.py'}[key]
    assert sha(out/filename) == protocol[key+'_sha256']
library = pathlib.Path(roots['<FGO_BUILD>'])/'libobgins_bridge.so'
assert sha(library) == protocol['bridge_sha256']
assert sha(library.with_suffix('.build.json')) == protocol['bridge_build_receipt_sha256']
for name, digest in load(library.with_suffix('.build.json'))['source_sha256'].items(): assert sha(name) == digest
run_inputs, failures, block_rows = {}, [], []
zip_members = 0
for sequence, methods in seal['comparison_identities'].items():
    for method, binding in methods.items():
        directory = resolve(binding['path'])
        assert sha(directory/'RUN.json') == binding['run_json_sha256']
        assert sha(directory/'ACCESS.json') == binding['access_sha256']
        run = load(directory/'RUN.json')
        scientific_pins[directory/'RUN.json'] = binding['run_json_sha256']
        for name, digest in run['output_hashes'].items():
            assert sha(directory/name) == digest
            scientific_pins[directory/name] = digest
        access = load(directory/'ACCESS.json')
        assert access.get('actual_reference_opens', access.get('reference_payload_opens')) == 0
        if method == 'OISAM':
            assert access['actual_reference_open_attempts'] == 0
            expected = {**protocol['execution_source_hashes'],
                        protocol['method_config_path']: protocol['method_config_sha256'],
                        protocol['execution_contract_path']: protocol['execution_contract_sha256']}
            with zipfile.ZipFile(directory/'SOURCE_SNAPSHOT.zip') as archive:
                assert len(archive.namelist()) == len(expected) == 874
                assert set(archive.namelist()) == set(expected)
                for name, digest in expected.items(): assert hashlib.sha256(archive.read(name)).hexdigest() == digest
                zip_members += len(expected)
            blocks = load(directory/'BLOCKS.json')
            assert len(blocks) == len(protocol['block_plan'][sequence]) == run['attempted_blocks']
            for block, plan in zip(blocks, protocol['block_plan'][sequence]):
                for key in plan: assert block[key] == plan[key]
                assert block['attempted'] and block['actual_rows'] == block['scheduled_nodes']
                assert len(block['initializations']) <= 1
                block_rows.append({'sequence': sequence, 'block_id': block['block_id'],
                    'scheduled_nodes': block['scheduled_nodes'], 'prior_only_count': block['prior_only_count'],
                    'dynamic_valid_nodes': block['dynamic_valid_nodes'],
                    'initialization_s': block['initializations'][0]['start_s'] if block['initializations'] else None,
                    'singleton_prior_only': block['singleton_prior_only'],
                    'numerical_failure': block['execution']['numerical_failure']})
                for init in block['initializations']:
                    assert init['reference_used'] is False and init['prior_only_output_is_dynamic_solution'] is False
                    assert init['initial_body_rate']['effective_timestamp_rel_s'] <= init['start_s']
                    assert init['gnss_provider_time_rel_s'] == init['start_s']
        else:
            assert access['passed'] is True
            for name, digest in run['implementation_source_hashes'].items(): assert sha(directory/'SOURCE_SNAPSHOT'/name) == digest
        run_inputs[sequence, method] = pd.read_csv(directory/'STATES.csv')

differences, support_rows, checked_statistics = [], [], []
roles = ('PRIMARY_DYNAMIC_ONLY', 'SECONDARY_ALL_VALID_POSITION')
for item in complete['sequences']:
    sequence = item['sequence']; directory = stage/'evaluation'/sequence
    for name, digest in item['output_hashes'].items():
        assert sha(directory/name) == digest; scientific_pins[directory/name] = digest
    evaluation = load(directory/'EVALUATION.json')
    expected_count = protocol['formal_denominators'][sequence]
    errors = {}; key_maps = {}
    for role in roles:
        errors[role], key_maps[role] = {}, {}
        for method in ('OISAM', 'WEN_TC', 'GNC'):
            e = pd.read_csv(directory/(method+'_'+role+'_ERRORS.csv'))
            errors[role][method] = e
            tt = e.time.to_numpy(float); valid = e.valid.to_numpy(int) == 1
            assert np.all(np.diff(tt) > 0) and len(set(np.rint(tt))) == len(tt)
            assert np.isfinite(e.loc[valid, ['err_n_m', 'err_e_m', 'err_u_m', 'horizontal_err_m', 'position_3d_err_m']].to_numpy()).all()
            assert not np.isfinite(e.loc[~valid, ['err_n_m', 'err_e_m', 'err_u_m', 'horizontal_err_m', 'position_3d_err_m']].to_numpy()).any()
            assert np.all(e.loc[valid, 'reference_left_s'] <= e.loc[valid, 'time'])
            assert np.all(e.loc[valid, 'reference_right_s'] >= e.loc[valid, 'time'])
            assert np.allclose(e.reference_right_s-e.reference_left_s, e.reference_bracket_span_s, rtol=0, atol=1e-12)
            if method == 'OISAM' and role == 'PRIMARY_DYNAMIC_ONLY': assert not (e.loc[valid, 'prior_only'] > 0).any()
            keys = np.rint(tt).astype(int)
            indices = np.flatnonzero(valid & (np.abs(tt-keys) <= .005))
            key_maps[role][method] = {int(keys[i]): int(i) for i in indices}
            if method == 'OISAM' and role == 'PRIMARY_DYNAMIC_ONLY':
                for r in e.loc[~valid].to_dict('records'):
                    failures.append({'sequence': sequence, 'time_s': r['time'], 'classification': 'PRIOR_ONLY_EXCLUDED' if r['prior_only'] else r['native_status'], 'block_id': r['block_id'], 'denominator_retained': True})
        common = sorted(set.intersection(*(set(v) for v in key_maps[role].values())))
        assert common == evaluation['common_nominal_keys'][role]
        for row in [r for r in evaluation['rows'] if r['support_role'] == role]:
            e = errors[role][row['method_id']]
            if row['support'] == 'COMMON_THREE_TIME_KEYS':
                e = e.iloc[[key_maps[role][row['method_id']][key] for key in common]]
            valid = e.valid.to_numpy(int) == 1
            assert row['expected_epoch_count'] == expected_count
            assert row['matched_epoch_count'] == int(valid.sum())
            assert row['missing_or_invalid_count'] == expected_count-int(valid.sum())
            assert abs(row['coverage_fraction']-int(valid.sum())/expected_count) < 1e-15
            support_rows.append({k: row[k] for k in ('sequence_id', 'method_id', 'support_role', 'support', 'expected_epoch_count', 'matched_epoch_count', 'missing_or_invalid_count')})
            for name, column, unit in [('horizontal', 'horizontal_err_m', 'm'), ('vertical', 'err_u_m', 'm'), ('position_3d', 'position_3d_err_m', 'm'), ('yaw', 'yaw_err_deg', 'deg')]:
                if column not in e: continue
                x = e[column].to_numpy(float); x = x[np.isfinite(x)]
                for statistic in ('rmse', 'p50', 'p95', 'max'):
                    actual = float(np.sqrt(np.mean(x*x))) if statistic == 'rmse' else float(np.percentile(np.abs(x), 50 if statistic == 'p50' else 95)) if statistic != 'max' else float(np.max(np.abs(x)))
                    key = name+'_'+statistic+'_'+unit; saved = row[key]
                    delta = abs(actual-saved); differences.append(delta)
                    assert delta <= 1e-10
                    checked_statistics.append({'sequence': sequence, 'method': row['method_id'], 'role': role, 'support': row['support'], 'metric': key, 'saved': saved, 'recomputed': actual, 'absolute_difference': delta})

normal_checks = []
target_directory = stage/'runs/BY2O/OISAM/SEGMENTED_DIAGNOSTIC/TARGET_DIAGNOSTICS'
for phase in ('CERES_INITIAL', 'CERES_FINAL', 'STEP_OUTPUT'):
    meta = load(target_directory/('3286_'+phase+'.json'))
    with np.load(target_directory/('3286_'+phase+'.npz'), allow_pickle=False) as data:
        matrix = data['scaled_normal']; eig = np.linalg.eigvalsh((matrix+matrix.T)/2)
        assert matrix.shape == (meta['dimension'], meta['dimension'])
        assert np.isfinite(matrix).all() and np.isfinite(data['scaled_rhs']).all()
        assert np.allclose(eig, data['eigenvalues'], atol=1e-12, rtol=1e-10)
        positive = eig[eig > eig[-1]*1e-12]
        assert len(positive) == meta['scaled_normal_rank_relative_1e_12']
        condition = eig[-1]/positive[0]
        # The smallest eigenvalue is ~2e-6; a few 1e-15 eigensolver roundoff
        # changes its inverse by ~1e-9 relative. This is a saved-NPZ arithmetic
        # tolerance, never a solver/support/score admission threshold.
        condition_difference = abs(condition/meta['scaled_normal_condition_positive']-1)
        assert condition_difference < 1e-8
        assert abs(sum(v['residual_squared_sum'] for v in meta['factors'].values())/2-meta['factor_half_squared_residual_cost']) < 1e-12
        normal_checks.append({'phase': phase, 'dimension': len(eig), 'rank': len(positive), 'condition': condition, 'condition_relative_recompute_difference': condition_difference, 'cost': meta['factor_half_squared_residual_cost']})
event = load(target_directory/'TARGET_EVENT.json')
assert event['actual_time_rel_s'] == 3286 and event['nonlinear_solution_usable'] is True
assert event['nonlinear_status'] == 'TerminationType.NO_CONVERGENCE' and event['nonlinear_iterations'] == 20
for path, digest in scientific_pins.items(): assert sha(path) == digest
for name, digest in protocol['execution_source_hashes'].items(): assert sha(code/name) == digest
out.mkdir(exist_ok=True)
def write_csv(filename, rows):
    with (out/filename).open('x', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)
write_csv('FGO_SEGMENTED_INDEPENDENT_STATISTICS.csv', checked_statistics)
write_csv('FGO_SEGMENTED_INDEPENDENT_SUPPORT.csv', support_rows)
write_csv('FGO_SEGMENTED_INDEPENDENT_BLOCKS.csv', block_rows)
write_csv('FGO_SEGMENTED_COMPLETE_UNAVAILABLE_TIMELINE.csv', failures)
receipt = {'schema': 'fgo.segmented.saved-payload.independent-review.v1', 'all_checks_passed': True,
           'verified_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
           'script_sha256': sha(__file__), 'stage': str(stage), 'registered_commit': protocol['registered_commit'],
           'protocol_sha256': sha(stage/'PREREGISTRATION.json'), 'native_seal_sha256': sha(stage/'ALL_NATIVE_SEALED.json'),
           'offline_complete_sha256': sha(stage/'ALL_OFFLINE_COMPLETE.json'),
           'source872_before_after_match': True, 'new_source_snapshot_members_checked': zip_members,
           'comparison_native_identities_checked': 9, 'metric_rows': len(support_rows),
           'statistics_checked': len(checked_statistics), 'maximum_statistic_absolute_difference': max(differences),
           'block_rows': len(block_rows), 'formal_primary_unavailable_rows': len(failures),
           'normal_npz_checks': normal_checks, 'target3286_usable_but_not_converged': True,
           'raw_reference_payload_opens': 0, 'solver_calls': 0, 'evaluator_calls': 0,
           'scope': 'saved errors/statistics/support/source/snapshot/initialization/normal-matrix identities; independent physical-coordinate review by root is separate',
           'output_csv_sha256': {name: sha(out/name) for name in ('FGO_SEGMENTED_INDEPENDENT_STATISTICS.csv', 'FGO_SEGMENTED_INDEPENDENT_SUPPORT.csv', 'FGO_SEGMENTED_INDEPENDENT_BLOCKS.csv', 'FGO_SEGMENTED_COMPLETE_UNAVAILABLE_TIMELINE.csv')}}
with (out/'FGO_SEGMENTED_INDEPENDENT_REVIEW.json').open('x') as stream: json.dump(receipt, stream, indent=2, ensure_ascii=False); stream.write('\n')
print(json.dumps(receipt, ensure_ascii=False))
