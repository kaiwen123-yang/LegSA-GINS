#!/usr/bin/env python3
# Fixed input-only 12-window selection support diagnostic; no future or navigation.
from __future__ import annotations
import argparse
from collections import Counter
from dataclasses import asdict, is_dataclass
import csv
import gzip
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys
import time
import traceback

import numpy as np
from scipy.stats import chi2
from legsa_gins.paper_rebuild.carrier_phase import candidate_envelope as envelope_module
from legsa_gins.paper_rebuild.carrier_phase.candidate_envelope import (
    enumerate_candidate_envelope, filter_length_necessary_support)
from legsa_gins.paper_rebuild.carrier_phase.partial import PartialPolicy
from legsa_gins.paper_rebuild.carrier_phase.selected_likelihood import prepare_selected_likelihood
from legsa_gins.paper_rebuild.horizontal_literature.shared_raw_backend import ecef_to_geodetic
from shadow_replay import load_model

ROOT = Path(__file__).resolve().parents[3]
PLAN_REL = 'docs/paper_rebuild/TRUSTED_HEADING_20261006/CANDIDATE_ENVELOPE_PILOT_PLAN.json'
SCRIPT_REL = 'scripts/paper_rebuild/carrier_phase/candidate_envelope_pilot.py'


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def clean(value):
    if is_dataclass(value):
        return clean(asdict(value))
    if isinstance(value, np.ndarray):
        return clean(value.tolist())
    if isinstance(value, np.generic):
        return clean(value.item())
    if isinstance(value, dict):
        return {str(k): clean(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [clean(v) for v in value]
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def emit(path, value):
    Path(path).write_text(json.dumps(clean(value), ensure_ascii=False, indent=2,
                                   allow_nan=False) + '\n')


def require(condition, reason):
    if not condition:
        raise RuntimeError(reason)


def verify_file(path, expected):
    require(isinstance(expected, str) and len(expected) == 64,
            'missing registered SHA256: ' + str(path))
    require(digest(path) == expected, 'SHA256 mismatch: ' + str(path))


def verify_registration(commit, config):
    require(len(commit) == 40 and all(c in '0123456789abcdef' for c in commit),
            'full registration commit required')
    for relative in (PLAN_REL, SCRIPT_REL):
        registered = subprocess.check_output(['git', 'show', commit + ':' + relative], cwd=ROOT)
        require(registered == (ROOT / relative).read_bytes(),
                'registration bytes mismatch: ' + relative)
    require(config['source_pins'], 'empty registered source pins')
    for relative, expected in config['source_pins'].items():
        path = (ROOT / relative).resolve()
        require(path.is_relative_to(ROOT), 'source pin escapes repository')
        verify_file(path, expected)
        registered = subprocess.check_output(['git', 'show', commit + ':' + relative], cwd=ROOT)
        require(hashlib.sha256(registered).hexdigest() == expected,
                'source pin not present in registration commit: ' + relative)


def fixed_windows(records, config):
    spec = config['input']
    require(len(records) == spec['records'] == 1200, 'saved record count mismatch')
    starts = spec['start_indices']
    require(starts == list(range(0, 1200, 100)), 'fixed input-only windows changed')
    require(spec['selection_epochs'] == 5 and spec['future_epochs_executed'] == 0,
            'selection-only scope changed')
    times = np.asarray([r['time_s'] for r in records], float)
    require(np.isfinite(times).all() and np.all(np.diff(times) > 0),
            'invalid saved model times')
    require(np.max(np.abs(np.diff(times) - .2)) <= .01,
            'saved model cadence outside original policy')
    return [(start, records[start:start+5]) for start in starts]


def axes_from_anchor(anchor):
    latitude, longitude, _ = ecef_to_geodetic(anchor)
    return np.asarray([[-math.sin(latitude)*math.cos(longitude),
                        -math.sin(latitude)*math.sin(longitude), math.cos(latitude)],
                       [-math.sin(longitude), math.cos(longitude), 0.]])


def width_deg(arc):
    return None if arc is None else math.degrees(arc.width_rad)


def counters_template():
    return dict(enumeration_api_calls=0, decorrelation_api_entries=0,
        length_filter_calls=0, existing_CILS_calls=0, sphere_optimization_calls=0,
        raw_UBX_reads=0, reference_reads=0, navigation_calls=0, evaluator_calls=0,
        retries=0, replacement_windows=0, future_epochs_processed=0)


def run(args):
    config = json.loads((ROOT / PLAN_REL).read_text())
    verify_registration(args.registration_commit, config)
    prepared = Path(args.prepared).resolve()
    audit_path = Path(args.input_audit).resolve()
    output = Path(args.output).resolve()
    require(not output.exists(), 'output must be new; no resume or retry')
    verify_file(prepared / 'PLAN.json', config['input']['prepared_plan_sha256'])
    verify_file(audit_path, config['input']['model_pins_manifest_sha256'])
    saved = json.loads((prepared / 'PLAN.json').read_text())
    audit = json.loads(audit_path.read_text())
    require(audit['plan_sha256'] == config['input']['prepared_plan_sha256'],
            'audit/prepared source mismatch')
    require(saved['sequence'] == config['input']['sequence'], 'sequence mismatch')
    require(saved['window_s'] == config['input']['window_s'], 'saved window mismatch')
    require(saved['baseline_length_m'] == config['input']['baseline_length_m'], 'length mismatch')
    windows = fixed_windows(saved['records'], config)
    family = config['input']['family']
    library = Path(saved['lambda_library']).resolve()
    verify_file(library, config['input']['lambda_library_sha256'])
    input_pins = {str(prepared/'PLAN.json'): digest(prepared/'PLAN.json'),
                  str(audit_path): digest(audit_path), str(library): digest(library)}
    for _, records in windows:
        for record in records:
            entry = record['families'].get(family, {})
            if entry.get('status') != 'BUILT':
                continue
            relative = entry['file']
            path = (prepared / relative).resolve()
            require(path.is_relative_to(prepared), 'model path escapes prepared source')
            expected = audit['model_npz_sha256'].get(relative)
            verify_file(path, expected)
            input_pins[str(path)] = expected
    output.mkdir(parents=True, exist_ok=False)
    emit(output/'INPUT_IDENTITY.json', dict(registration_commit=args.registration_commit,
         plan_sha256=digest(ROOT/PLAN_REL), source_pins=config['source_pins'],
         input_pins=input_pins, fixed_start_indices=config['input']['start_indices']))
    emit(output/'EXECUTION_PLAN.json', config)
    counts = counters_template()
    rows = []
    started = time.monotonic()
    bridge = envelope_module.RTKLIBLambdaBridge
    # Count the bridge entry only; this wrapper never changes arguments/results.
    class CountedBridge(bridge):
        def decorrelate(self, *positional, **keywords):
            counts['decorrelation_api_entries'] += 1
            return super().decorrelate(*positional, **keywords)
    envelope_module.RTKLIBLambdaBridge = CountedBridge
    try:
        with gzip.open(output/'DETAILS.jsonl.gz', 'wt', encoding='utf-8', newline='\n') as details:
            for start, records in windows:
                window_started = time.monotonic()
                row = dict(start_index=start, first_selection_s=records[0]['time_s'],
                    selected_at_s=records[-1]['time_s'], status='NOT_STARTED', reason='',
                    enumeration_called=False, selected_integer_dimension=None,
                    scalar_observation_dimension=None, raw_cost_threshold=None,
                    raw_support_complete=False, raw_observed_candidate_count=0,
                    length_status='NOT_CALLED', length_support_complete=False,
                    length_retained_candidate_count=None, raw_arc_width_deg=None,
                    length_arc_width_deg=None, raw_full_circle=None, length_full_circle=None,
                    expanded_nodes=0, integer_leaves=0, api_wall_s=0.,
                    api_reported_s=None, api_over_30s=False, length_filter_wall_s=0.,
                    preparation_wall_s=None, decorrelation_api_entries=0)
                detail = dict(start_index=start)
                before_decorrelation = counts['decorrelation_api_entries']
                try:
                    models = tuple(load_model(prepared, record, family) for record in records)
                    policy = PartialPolicy(**{key: config['selection'][key] for key in
                        ('selection_epochs', 'min_ambiguities', 'max_ambiguities',
                         'epoch_interval_s', 'time_tolerance_s')})
                    selected = prepare_selected_likelihood(models,
                        length_m=config['input']['baseline_length_m'], policy=policy)
                    detail['selection'] = selected.selection
                    detail['supports'] = selected.supports
                    row['status'] = selected.selection.status
                    if selected.ready:
                        problem = selected.problem
                        axes = axes_from_anchor(records[-1]['anchor_ecef_m'])
                        n = len(problem.y)
                        threshold = float(chi2.ppf(config['threshold']['nominal_working_coverage'], n))
                        detail.update(selected_plan_fingerprint=selected.fingerprint,
                            local_NE_axes_ecef=axes, anchor_role='SAVED_RAW_CODE_LINEARIZATION_ANCHOR')
                        row.update(selected_integer_dimension=len(problem.ambiguity_labels),
                            scalar_observation_dimension=n, raw_cost_threshold=threshold)
                        row['preparation_wall_s'] = time.monotonic()-window_started
                        counts['enumeration_api_calls'] += 1
                        require(counts['enumeration_api_calls'] <= 12, 'enumeration budget violated')
                        row['enumeration_called'] = True
                        api_start = time.monotonic()
                        try:
                            result = enumerate_candidate_envelope(problem, threshold,
                                lambda_library=library, horizontal_axes=axes, target_epoch=-1,
                                node_limit=config['budget']['node_limit_per_call'],
                                candidate_limit=config['budget']['candidate_limit_per_call'],
                                timeout_s=config['budget']['timeout_s_per_call'],
                                **{key: config['threshold'][key] for key in
                                   ('max_condition_number', 'absolute_cost_guard', 'relative_numerical_guard')})
                        finally:
                            row['api_wall_s'] = time.monotonic()-api_start
                            row['api_over_30s'] = row['api_wall_s'] > config['budget']['timeout_s_per_call']
                        detail['raw_envelope'] = result
                        row.update(status=result.status, reason=result.termination_reason,
                            raw_support_complete=result.numerical_support_complete,
                            raw_observed_candidate_count=len(result.candidates),
                            raw_arc_width_deg=width_deg(result.azimuth_outer_arc),
                            raw_full_circle=None if result.azimuth_outer_arc is None else result.azimuth_outer_arc.full_circle,
                            expanded_nodes=result.expanded_nodes, integer_leaves=result.integer_leaves,
                            api_reported_s=result.elapsed_s)
                        counts['length_filter_calls'] += 1
                        length_start = time.monotonic()
                        try:
                            length = filter_length_necessary_support(problem, result)
                        finally:
                            row['length_filter_wall_s'] = time.monotonic()-length_start
                        detail['length_necessary_support'] = length
                        row.update(length_status=length.status,
                            length_support_complete=length.necessary_support_complete,
                            length_retained_candidate_count=len(length.retained_candidates),
                            length_arc_width_deg=width_deg(length.azimuth_outer_arc),
                            length_full_circle=None if length.azimuth_outer_arc is None else length.azimuth_outer_arc.full_circle)
                    else:
                        row['reason'] = 'PRESELECTION_UNAVAILABLE_NO_REPLACEMENT'
                except Exception as exc:
                    row.update(status='WINDOW_EXCEPTION', reason=type(exc).__name__+': '+str(exc))
                    detail['exception_traceback'] = traceback.format_exc()
                row['decorrelation_api_entries'] = counts['decorrelation_api_entries']-before_decorrelation
                row['window_wall_s'] = time.monotonic()-window_started
                rows.append(row)
                details.write(json.dumps(clean(dict(row=row, **detail)), ensure_ascii=False,
                                         allow_nan=False)+'\n')
                details.flush()
                with (output/'RESULTS.csv').open('w', newline='', encoding='utf-8') as stream:
                    writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator='\n')
                    writer.writeheader(); writer.writerows(rows)
                emit(output/'PROGRESS.json', dict(terminal_windows=len(rows), expected_windows=12,
                     calls=counts, last=row, elapsed_s=time.monotonic()-started))
                print(json.dumps(clean(dict(terminal_windows=len(rows), **row)), ensure_ascii=False), flush=True)
        verify_registration(args.registration_commit, config)
        for path, expected in input_pins.items():
            verify_file(path, expected)
        require(len(rows) == 12 and counts['enumeration_api_calls'] <= 12
                and counts['decorrelation_api_entries'] <= 12, 'final call accounting mismatch')
        summary = dict(status='COMPLETE_FIXED12_DIAGNOSTIC', registration_commit=args.registration_commit,
            expected_windows=12, terminal_windows=len(rows), calls=counts,
            raw_status_counts=dict(Counter(row['status'] for row in rows)),
            length_status_counts=dict(Counter(row['length_status'] for row in rows)),
            raw_complete_windows=sum(row['raw_support_complete'] for row in rows),
            length_complete_windows=sum(row['length_support_complete'] for row in rows),
            api_over_30s_windows=sum(row['api_over_30s'] for row in rows),
            total_execution_wall_s=time.monotonic()-started,
            acceptance_defined=False, navigation_qualification_defined=False,
            integer_truth_available=False, physical_coverage_probability=None,
            baseline_azimuth_not_robot_yaw=True, sphere_survivor_feasibility_proved=False,
            scope='fixed developmental saved inputs; no future, reference, navigation or prior',
            timing_limit='cooperative enumeration timer; preprocessing/BLAS/decorrelation are not hard-preempted')
        emit(output/'SUMMARY.json', summary)
        emit(output/'OUTPUT_SEAL.json', {p.name:digest(p) for p in sorted(output.iterdir()) if p.is_file()})
        emit(output/'COMPLETE.json', dict(status=summary['status'], summary_sha256=digest(output/'SUMMARY.json'),
             output_seal_sha256=digest(output/'OUTPUT_SEAL.json')))
    except BaseException as exc:
        emit(output/'ABORTED.json', dict(status='ABORTED_NO_RETRY', error=repr(exc), calls=counts,
             terminal_windows=len(rows), traceback=traceback.format_exc()))
        raise
    finally:
        envelope_module.RTKLIBLambdaBridge = bridge


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepared', required=True)
    parser.add_argument('--input-audit', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--registration-commit', required=True)
    run(parser.parse_args())


if __name__ == '__main__':
    main()
