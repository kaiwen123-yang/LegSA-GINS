"""Two complete nonlinear source conditionals from the completed b5 source seal."""
import argparse
import csv
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import shutil
import sys
import time


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


parser = argparse.ArgumentParser()
parser.add_argument('--repo', type=Path, required=True)
parser.add_argument('--cohort', type=Path, required=True)
parser.add_argument('--output-root', type=Path, required=True)
args = parser.parse_args()
csv.field_size_limit(10**8)
record = json.loads((args.cohort/'run_status.json').read_text())
snapshot = args.cohort/'SOURCE_SNAPSHOT'
for relative, expected in record['source_sha256'].items():
    if digest(snapshot/relative) != expected:
        raise ValueError('Source seal mismatch: '+relative)
args.output_root.mkdir()
shutil.copytree(snapshot, args.output_root/'SOURCE_SNAPSHOT')
sys.path.insert(0, str(args.repo/'src'))
import legsa_gins.paper_rebuild
package_name = 'legsa_gins.paper_rebuild.joint_navigation'
joint_path = snapshot/'src/legsa_gins/paper_rebuild/joint_navigation'
spec = importlib.util.spec_from_file_location(package_name, joint_path/'__init__.py',
                                            submodule_search_locations=[str(joint_path)])
package = importlib.util.module_from_spec(spec)
sys.modules[package_name] = package
spec.loader.exec_module(package)
from legsa_gins.paper_rebuild.joint_navigation.navigator import JointNavigator
from legsa_gins.paper_rebuild.joint_navigation.synthetic import generate_scene
spec = importlib.util.spec_from_file_location('pinned_runner', snapshot/'scripts/paper_rebuild/run_support_carrier_joint.py')
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)
np = runner.np
timeline = list(csv.DictReader((args.cohort/'input_timeline.csv').open()))
observed = next(row for row in timeline if float(row['time_s']) == 65.)
arcs = tuple(sorted(foot['arc_id'] for foot in json.loads(observed['feet'])))
first_use = {arc: min(float(row['time_s']) for row in timeline
                     if arc in {foot['arc_id'] for foot in json.loads(row['feet'])}) for arc in arcs}
group_id = 'support:'+'|'.join(arcs)
scene = generate_scene(duration_s=record['duration_s'], seed=record['seed'])
scene['metadata']['support_inference'] = record['support_inference']
runner.write_input_timeline(args.output_root/'input_timeline.csv', runner.input_timeline(scene['events']))
if (args.output_root/'input_timeline.csv').read_bytes() != (args.cohort/'input_timeline.csv').read_bytes():
    raise ValueError('Different input event timeline')
runner.write_json(args.output_root/'sensor_metadata.json', scene['metadata'])
runner.write_json(args.output_root/'evaluation_metadata.json', scene['evaluation_metadata'])
fixed_rows = runner.read_rows(args.cohort/'U3/navigation.csv')
fixed = {}
for row in fixed_rows:
    if row['selected_support_model'] != 'fixed':
        raise ValueError('Completed U3 is not an uninterrupted H0 comparator')
    j = row['selected_branch']
    fixed[row['time_s']] = dict(score=row['candidate_costs'][j],
                               integer_lineage=row['candidate_local_directions'][j]['integer_lineage'], row=row)

# Recover H0 row identity from actual input/physical-label availability, not
# truth or errors. All labels persist in this pinned navigator's graph.
known, fingerprint, count, expected = set(), '', 0, []
for index, event in enumerate(scene['events']):
    t, rows, block = float(event['time_s']), [], event.get('carrier')
    if index:
        for name in ('gnss_position', 'gnss_velocity'):
            if event.get(name) is not None:
                rows.extend(f'{name}:{t:.9f}:{axis}' for axis in range(3))
        if block is not None:
            unknown = [j for j, label in enumerate(block.ambiguity_labels) if label not in known]
            selected = np.ones(len(block.y), bool)
            if unknown:
                selected &= np.all(np.asarray(block.A)[:, unknown] == 0., axis=1)
            rows.extend(f'raw_code_carrier:{t:.9f}:row{j}' for j in np.flatnonzero(selected))
    rows = tuple(rows)
    if rows:
        fingerprint = hashlib.sha256((fingerprint+repr((index, rows))).encode()).hexdigest()
    count += len(rows)
    expected.append(dict(rows=rows, fingerprint=fingerprint, count=count))
    if block is not None:
        known.update(block.ambiguity_labels)

status = dict(status='RUNNING', process_id=os.getpid(), started_unix_s=time.time(),
    source_cohort=str(args.cohort), source_git_commit=record['git_commit'], source_sha256=record['source_sha256'],
    script_sha256=digest(Path(__file__)), source_binding='EVERY_JOINT_MODULE_IMPORTED_FROM_VERIFIED_SOURCE_SNAPSHOT',
    completed_models=[], models=['common_translation_release', 'relative_release'],
    selected_observation_time_s=65., observed_arc_ids=arcs, observed_arc_first_use_s=first_use,
    policy_scope='FULL_HISTORY_CONDITIONAL_FROM_FIRST_USE;NO_TRUTH_FAULT_TIME_SUPPLIED',
    modes_run=['U3_monitor_support_false'], H0_rerun=False,
    H0_navigation_sha256=digest(args.cohort/'U3/navigation.csv'),
    input_timeline_sha256=digest(args.cohort/'input_timeline.csv'),
    H0_row_fingerprint_scope='DERIVED_FROM_IDENTICAL_EVENTS_AND_PINNED_PERSISTENT_LABEL_RULE;NOT_ORIGINAL_SAVED_FINGERPRINT')
runner.write_json(args.output_root/'run_status.json', status)
landmarks = {65., 67., 70., 77., 78., 90.}
comparison = {}
try:
    for model in status['models']:
        policy = [dict(group_id=group_id, arc_ids=arcs, mode=model, effective_from=-math.inf)]
        nav = JointNavigator(scene['metadata'], mode='U3', monitor_support=False, support_models=policy)
        target = args.output_root/model
        target.mkdir()
        captured = []
        start = time.monotonic()
        identity = 'g0:'+group_id+':'+model
        with (target/'predictive_trace.jsonl').open('w', buffering=1) as trace:
            def capture(index, event, output, _policy, _integers):
                rows = tuple(nav.reference_rows[index])
                reference = expected[index]
                if rows != reference['rows'] or nav.predictive_rows_fingerprint != reference['fingerprint']:
                    raise ValueError(f'External row identity mismatch at event {index}')
                selected = nav.branches[output['selected_branch']]
                if selected.predictive_row_count != reference['count']:
                    raise ValueError(f'External row count mismatch at event {index}')
                t = float(event['time_s'])
                h0 = fixed[t]
                same_lineage = runner.json_value(selected.integer_lineage) == h0['integer_lineage']
                candidate = dict(event_index=index, time_s=t, predictive_score=selected.predictive_score,
                    predictive_row_count=selected.predictive_row_count,
                    predictive_rows_fingerprint=nav.predictive_rows_fingerprint, event_row_ids=rows,
                    integer_lineage=selected.integer_lineage, H0_same_integer_lineage=same_lineage,
                    p=output['p'], v=output['v'], rpy_rad=output['rpy_rad'], bias=output['bias'],
                    fixed_score=h0['score'], raw_delta_vs_fixed=selected.predictive_score-h0['score'],
                    penalized_delta_vs_fixed=selected.predictive_score+nav.model_edit_cost-h0['score'],
                    model_edit_cost=nav.model_edit_cost,
                    branches=[dict(integer_lineage=b.integer_lineage, score=b.predictive_score,
                                   rows=b.predictive_row_count) for b in nav.branches])
                alternatives = h0['row']['candidate_local_directions']
                for j, alternative in enumerate(alternatives):
                    if alternative['support_model'] == identity:
                        published = h0['row']['candidate_costs'][j]
                        candidate.update(gaussian_penalized_score=published,
                            gaussian_raw_score=published-nav.model_edit_cost,
                            gaussian_raw_delta_vs_fixed=published-nav.model_edit_cost-h0['score'],
                            gaussian_penalized_delta_vs_fixed=published-h0['score'],
                            nonlinear_minus_gaussian_raw=selected.predictive_score-(published-nav.model_edit_cost))
                trace.write(json.dumps(runner.json_value(candidate), allow_nan=False)+'\n')
                captured.append(candidate)
                if t in landmarks:
                    print(model, 't', t, 'raw_delta', candidate['raw_delta_vs_fixed'],
                          'penalized_delta', candidate['penalized_delta_vs_fixed'],
                          'rows', selected.predictive_row_count, 'same_lineage', same_lineage, flush=True)
            result = nav.run(scene['events'], output_callback=capture)
        runner.write_rows(target/'navigation.csv', result['rows'])
        runner.write_json(target/'decisions.json', result['decisions'])
        runner.write_json(target/'estimator_summary.json', result['summary'])
        metrics, arrays = runner.evaluate_rows(result['rows'], scene['truth'], scene['evaluation_metadata'])
        metrics['runtime_wall_s'] = time.monotonic()-start
        runner.write_json(target/'metrics.json', metrics)
        np.savez_compressed(target/'offline_error_series.npz', **arrays)
        fields = ['time_s', 'predictive_score', 'fixed_score', 'raw_delta_vs_fixed', 'penalized_delta_vs_fixed',
                  'predictive_row_count', 'predictive_rows_fingerprint', 'H0_same_integer_lineage',
                  'gaussian_raw_score', 'gaussian_raw_delta_vs_fixed', 'gaussian_penalized_delta_vs_fixed',
                  'nonlinear_minus_gaussian_raw']
        with (target/'score_comparison.csv').open('w', newline='') as file:
            writer = csv.DictWriter(file, fields, extrasaction='ignore'); writer.writeheader(); writer.writerows(captured)
        comparison[model] = dict(identity=identity, policy=policy,
            duration_wall_s=metrics['runtime_wall_s'], final=captured[-1],
            landmarks=[row for row in captured if row['time_s'] in landmarks],
            gaussian_score_available_rows=sum('gaussian_raw_score' in row for row in captured),
            earliest_raw_better_time_s=next((row['time_s'] for row in captured if row['raw_delta_vs_fixed'] < -1e-8), None),
            earliest_penalized_better_time_s=next((row['time_s'] for row in captured if row['penalized_delta_vs_fixed'] < -1e-8), None),
            all_external_frontiers_equal=True, all_post_first_use_integer_lineages_equal=all(
                row['H0_same_integer_lineage'] for row in captured if row['time_s'] >= min(first_use.values())))
        status['completed_models'].append(model)
        runner.write_json(args.output_root/'run_status.json', status)
        runner.write_json(args.output_root/'SCORE_COMPARISON.json', comparison)
        print('COMPLETED', model, metrics['runtime_wall_s'], flush=True)
    imported = {name: dict(path=module.__file__, sha256=digest(Path(module.__file__)))
                for name, module in sys.modules.items() if name.startswith(package_name) and getattr(module, '__file__', None)}
    for name, entry in imported.items():
        if not Path(entry['path']).is_relative_to(joint_path):
            raise ValueError('Unpinned joint module: '+name)
    runner.write_json(args.output_root/'IMPORTED_SOURCE_IDENTITY.json', imported)
    status.update(status='COMPLETED', finished_unix_s=time.time())
    runner.write_json(args.output_root/'run_status.json', status)
except BaseException as error:
    status.update(status='FAILED', error_type=type(error).__name__, error=str(error), finished_unix_s=time.time())
    runner.write_json(args.output_root/'run_status.json', status)
    raise
