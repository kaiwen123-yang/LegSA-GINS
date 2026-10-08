#!/usr/bin/env python3
"""Evaluate one declared profile extension on an existing no-foot Gaussian chart.

No nonlinear optimization, navigation, or reference evaluation is performed.
The requested grid must include the old minimum, evaluated once as a numerical
cache-equivalence check. Other old points are reused, never re-estimated.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import time

import gtsam
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src'))
from legsa_gins.paper_rebuild.joint_navigation.real_data import By2InputConfig, load_by2_events
from legsa_gins.paper_rebuild.joint_navigation.support_motion_likelihood import (
    MotionParameters, evaluate_support_motion_likelihood, prepare_support_motion_likelihood,
    summarize_support_motion_profile)
from calibrate_support_motion import _json, _save, _grid
from read_support_motion_profile import displacement_variance


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def identity(row):
    return float(row['velocity_sigma_mps']), float(row['tau_s'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-root', type=Path, required=True)
    parser.add_argument('--output-root', type=Path, required=True)
    parser.add_argument('--sigma-grid', type=_grid, required=True)
    parser.add_argument('--tau-grid', type=_grid, required=True)
    args = parser.parse_args()
    source, output = args.source_root.resolve(), args.output_root.resolve()
    original_status = read(source / 'CALIBRATION_STATUS.json')
    original = read(source / 'SUPPORT_MOTION_PROFILE.json')
    chart = read(source / 'NOFOOT_SOURCE_CHART.json')
    saved_policy = read(source / 'SOURCE_POLICY.json')
    points = [(sigma, tau) for sigma in sorted(set(args.sigma_grid))
              for tau in sorted(set(args.tau_grid))]
    check_point = identity(original['grid_minimum'])
    if check_point not in points:
        raise ValueError('declared extension must include the old minimum for one cache-equivalence check')
    output.mkdir(parents=True, exist_ok=False)
    started = time.monotonic()
    status = dict(status='PREPARING_SAVED_GAUSSIAN_CHART', source_root=str(source),
        input_config=original_status['input_config'], requested_extension_points=points,
        numerical_equivalence_point=check_point, original_profile_rows=len(original['rows']),
        reference_reads=0, nonlinear_optimizations=0, navigation_calls=0,
        automatic_parameter_freeze=False, extension_round=1,
        extension_scope='ONE_PREDECLARED_BOUNDARY_EXTENSION_NO_AUTOMATIC_CONTINUATION')
    _save(output / 'CALIBRATION_STATUS.json', status)
    try:
        config = By2InputConfig(**{key: Path(value) if key.endswith('_path') else value
                                 for key, value in status['input_config'].items()})
        inputs = load_by2_events(config)
        graph = gtsam.GaussianFactorGraph()
        graph.deserialize((source / 'NOFOOT_GAUSSIAN_GRAPH.txt').read_text())
        values = gtsam.Values()
        values.deserialize((source / 'NOFOOT_LINEARIZATION_VALUES.txt').read_text())
        problem = prepare_support_motion_likelihood(graph, values, inputs['events'],
            foot_sigma_m=float(inputs['metadata'].get('foot_sigma', .01)),
            foot_tau_s=float(inputs['metadata'].get('foot_correlation_tau_s', .08)),
            policy=saved_policy['policy'], source_scope=chart)
        _save(output / 'NOFOOT_SOURCE_CHART.json', chart)
        _save(output / 'SOURCE_POLICY.json', dict(policy=list(problem.policy), scope=problem.source_scope))
        _save(output / 'INPUT_SUMMARY.json', inputs['input_summary'])
        status.update(status='EVALUATING_DECLARED_EXTENSION', preparation_elapsed_s=time.monotonic()-started)
        _save(output / 'CALIBRATION_STATUS.json', status)
        old_rows = {identity(row): row for row in original['rows']}
        combined = dict(old_rows)
        new_rows, equality = [], None
        # Validate the restored chart before spending work on the eight new points.
        ordered = [check_point] + [point for point in points if point != check_point]
        for point in ordered:
            if point in old_rows and point != check_point:
                continue
            point_started = time.monotonic()
            row = evaluate_support_motion_likelihood(problem, MotionParameters(*point))
            row['evaluation_elapsed_s'] = time.monotonic()-point_started
            if point == check_point:
                compared = ('restricted_objective', 'residual_cost', 'integrated_log_normalization')
                equality = {key: dict(original=old_rows[point][key], restored=row[key],
                    difference=row[key]-old_rows[point][key],
                    equal=bool(np.isclose(row[key], old_rows[point][key], rtol=1e-10, atol=1e-8)))
                    for key in compared}
                _save(output / 'CACHE_EQUIVALENCE.json', dict(point=point, fields=equality,
                    relative_tolerance=1e-10, absolute_tolerance=1e-8))
                if not all(item['equal'] for item in equality.values()):
                    raise ValueError('restored Gaussian chart did not reproduce the original profile point')
            else:
                combined[point] = row
            new_rows.append(row)
            _save(output / 'EXTENSION_EVALUATED_ROWS.json', new_rows)
            print(json.dumps(_json(dict(point=point, **row))), flush=True)
        profile = summarize_support_motion_profile(problem, list(combined.values()),
            deviance_width=original['relative_deviance_width'])
        profile.update(grid_design='ORIGINAL_49_POINTS_PLUS_ONE_DECLARED_LOCAL_EXTENSION',
            source_profile=str(source / 'SUPPORT_MOTION_PROFILE.json'),
            original_rows_reused=len(original['rows']), newly_added_rows=len(combined)-len(old_rows),
            equivalence_point_evaluated_once=check_point,
            constant_velocity_limit_not_excluded=profile['grid_minimum']['tau_s'] == max(args.tau_grid),
            original_profile_and_cache_overwritten=False)
        best = profile['grid_minimum']
        profile['twelve_second_per_axis_displacement_std_m'] = float(np.sqrt(displacement_variance(12., best)))
        _save(output / 'SUPPORT_MOTION_PROFILE.json', profile)
        _save(output / 'SUPPORT_MOTION_WORKING_MODEL.json', dict(
            support_motion_model=profile['support_motion_model'],
            qualification_scope=profile['identification_status'],
            working_value_selection='MINIMUM_OF_ONE_DECLARED_SOURCE_ONLY_EXTENSION_NOT_NAVIGATION_ERROR',
            automatic_parameter_freeze=False, probability_calibration_complete=False,
            calibration_window_s=original_status['requested_window_s'], source_policy='SOURCE_POLICY.json'))
        status.update(status='COMPLETED_SOURCE_ONLY_EXTENSION_NOT_AUTOMATIC_FREEZE',
            likelihood_evaluations=len(new_rows), cache_equivalence_passed=True,
            total_merged_profile_rows=len(combined), newly_added_rows=len(combined)-len(old_rows),
            grid_minimum=best, identification_status=profile['identification_status'],
            tau_identified=False, constant_velocity_limit_not_excluded=profile['constant_velocity_limit_not_excluded'],
            twelve_second_per_axis_displacement_std_m=profile['twelve_second_per_axis_displacement_std_m'])
    except Exception as error:
        status.update(status='FAILED_NO_PARAMETER_FREEZE', error_type=type(error).__name__, error=str(error))
        raise
    finally:
        status['elapsed_s'] = time.monotonic()-started
        _save(output / 'CALIBRATION_STATUS.json', status)
        print(json.dumps(_json(status), ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
