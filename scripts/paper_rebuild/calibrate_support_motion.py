#!/usr/bin/env python3
"""Fit the finite common-motion working model using source-only BY events.

All original GNSS1 P/V and IMU factors are built without foot factors or raw
carrier conditioning, then optimized as one graph. One complete Gaussian chart
provides cross-time state uncertainty to a joint restricted foot likelihood.
This offline development computation is not a causal navigation result.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import sys
import time

import gtsam
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from legsa_gins.paper_rebuild.joint_navigation.real_data import By2InputConfig, load_by2_events
from legsa_gins.paper_rebuild.joint_navigation.branch import NavigationBranch
from legsa_gins.paper_rebuild.joint_navigation.support_motion_likelihood import (
    prepare_support_motion_likelihood, profile_support_motion)


def _json(value):
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, np.ndarray):
        return _json(value.tolist())
    if isinstance(value, dict):
        return {str(k):_json(v) for k,v in value.items()}
    if isinstance(value, (list,tuple)):
        return [_json(v) for v in value]
    if isinstance(value, np.generic):
        return _json(value.item())
    return value


def _save(path, value):
    path.write_text(json.dumps(_json(value), ensure_ascii=False, indent=2, allow_nan=False)+'\n', encoding='utf-8')


def _grid(text):
    return [float(x) for x in text.split(',')]


def _stationarity(linear, values):
    # Column-scaled gradient using only each original sparse factor block.
    zeros = values.zeroVectors()
    norms = {k:np.zeros(len(zeros.at(k))) for k in values.keys()}
    for j in range(linear.size()):
        factor = gtsam.JacobianFactor(linear.at(j))
        matrix, _ = factor.jacobian()
        offset = 0
        for key in factor.keys():
            width = len(norms[key])
            norms[key] += np.sum(matrix[:,offset:offset+width]**2,axis=0)
            offset += width
    gradient = linear.gradientAtZero()
    maximum = 0.
    for key, norm in norms.items():
        if np.any(norm <= 0):
            raise ValueError('source graph has an unobserved state coordinate')
        maximum = max(maximum, float(np.max(np.abs(gradient.at(key))/np.sqrt(norm))))
    residual_norm = math.sqrt(2*float(linear.error(values.zeroVectors())))
    return maximum/max(1.,residual_norm)


def build_nofoot_source_graph(inputs, yaw_seeds_deg, max_iterations, gradient_tolerance):
    """No online publication or init claim: one source-only full-batch chart."""
    events = [dict(event, carrier=None, feet=[]) for event in inputs['events']]
    if not events:
        raise ValueError('no source events')
    metadata = dict(inputs['metadata'])
    metadata.pop('phase_noise_model', None)
    metadata['lag_s'] = events[-1]['time_s']-events[0]['time_s']+1.
    reports, accepted = [], []
    for yaw in yaw_seeds_deg:
        branch = NavigationBranch(metadata, use_foot=False)
        for index,event in enumerate(events):
            branch.step(event,index,defer_optimize=True,
                        initial_rotation=gtsam.Rot3.Rz(math.radians(yaw)) if index == 0 else None)
        params = gtsam.LevenbergMarquardtParams()
        params.setMaxIterations(max_iterations)
        params.setRelativeErrorTol(1e-9)
        params.setAbsoluteErrorTol(1e-9)
        optimizer = gtsam.LevenbergMarquardtOptimizer(branch.window.graph,branch.window.values,params)
        values = optimizer.optimize()
        linear = branch.window.graph.linearize(values)
        stationarity = _stationarity(linear,values)
        report = dict(seed_yaw_deg=yaw, initial_seed_is_prior=False,
                      nonlinear_cost=float(branch.window.graph.error(values)),
                      iterations=optimizer.iterations(), iteration_budget=max_iterations,
                      scaled_relative_gradient=stationarity,
                      stationary=stationarity <= gradient_tolerance,
                      factors=branch.window.graph.size(), state_dimension=values.dim(),
                      original_factors_only=True, marginalized_variables=branch.window.marginalized_total)
        reports.append(report)
        if report['stationary']:
            accepted.append((report['nonlinear_cost'],branch.window.graph,values,report))
    if not accepted:
        return None,None,dict(status='NO_STATIONARY_NOFOOT_SOURCE_CHART',seeds=reports)
    accepted.sort(key=lambda item:item[0])
    best = accepted[0]
    return best[1],best[2],dict(status='LOCAL_NOFOOT_SOURCE_CHART',seeds=reports,
        chosen_seed_yaw_deg=best[3]['seed_yaw_deg'], selected_by='GNSS1_PV_IMU_OBJECTIVE_ONLY',
        global_direction_uniqueness_proven=False,
        near_optimal_seed_count=sum(2*(item[0]-best[0]) <= 5.991464547107982 for item in accepted),
        foot_factors_consumed=0, raw_carrier_factors_consumed=0, reference_reads=0,
        original_factors_only=True, state_uncertainty='FULL_ONCE_LINEARIZED_GRAPH',
        chart_scope='CONDITIONAL_LOCAL_MODE_NOT_GLOBAL_NAVIGATION_SUPPORT')


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('body','imu','gnss','carrier-plan','calibration-model'):
        parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--noise-profile',type=Path,default=ROOT/'configs/paper_rebuild/horizontal_literature/hartley/stage_payload/04_METHOD_CONTRACTS/GO2_IMU_ALLAN_90MIN_RECOVERED_V1.yaml')
    parser.add_argument('--start',type=float,required=True)
    parser.add_argument('--end',type=float,required=True)
    parser.add_argument('--key-dt',type=float,default=.1)
    parser.add_argument('--sigma-grid',type=_grid,default=_grid('0,.005,.01,.02,.05,.1,.2'))
    parser.add_argument('--tau-grid',type=_grid,default=_grid('.02,.05,.1,.2,.5,1,2,5'))
    parser.add_argument('--yaw-seeds-deg',type=_grid,default=_grid('0,90,180,270'))
    parser.add_argument('--max-iterations',type=int,default=100)
    parser.add_argument('--gradient-tolerance',type=float,default=1e-6)
    parser.add_argument('--profile-width',type=float,default=5.991464547107982)
    parser.add_argument('--support-policy',type=Path)
    parser.add_argument('--output-root',type=Path,required=True)
    args=parser.parse_args(argv)
    args.output_root.mkdir(parents=True,exist_ok=False)
    started=time.monotonic()
    report=dict(status='READING_SOURCE_EVENTS',started_at_utc=datetime.now(timezone.utc).isoformat(),
                requested_window_s=[args.start,args.end],reference_reads=0,evaluator_calls=0,
                navigation_results_produced=False,foot_factors_used_for_source_state=0,
                sigma_grid=args.sigma_grid,tau_grid=args.tau_grid,
                implementation_sha256={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()
                    for p in [Path(__file__).resolve(),ROOT/'src/legsa_gins/paper_rebuild/joint_navigation/support_motion_likelihood.py']})
    _save(args.output_root/'CALIBRATION_STATUS.json',report)
    try:
        config=By2InputConfig(args.body,args.imu,args.gnss,args.carrier_plan,args.calibration_model,
                              args.noise_profile,start_s=args.start,end_s=args.end,key_dt_s=args.key_dt)
        report['input_config']=asdict(config)
        inputs=load_by2_events(config)
        _save(args.output_root/'INPUT_SUMMARY.json',inputs['input_summary'])
        report['status']='BUILDING_NOFOOT_COMPLETE_SOURCE_GRAPH'
        _save(args.output_root/'CALIBRATION_STATUS.json',report)
        graph,values,chart=build_nofoot_source_graph(inputs,args.yaw_seeds_deg,
                                                    args.max_iterations,args.gradient_tolerance)
        _save(args.output_root/'NOFOOT_SOURCE_CHART.json',chart)
        if graph is None:
            report.update(status=chart['status'],parameter_profile_available=False,
                          automatic_parameter_freeze=False)
        else:
            policy=None if args.support_policy is None else json.loads(args.support_policy.read_text())
            if isinstance(policy,dict):
                policy=policy['policy']
            problem=prepare_support_motion_likelihood(graph,values,inputs['events'],
                foot_sigma_m=float(inputs['metadata'].get('foot_sigma',.01)),
                foot_tau_s=float(inputs['metadata'].get('foot_correlation_tau_s',.08)),
                policy=policy,source_scope=chart)
            (args.output_root/'NOFOOT_GAUSSIAN_GRAPH.txt').write_text(graph.linearize(values).serialize())
            (args.output_root/'NOFOOT_LINEARIZATION_VALUES.txt').write_text(values.serialize())
            _save(args.output_root/'SOURCE_POLICY.json',dict(policy=list(problem.policy),scope=problem.source_scope))
            report['status']='EVALUATING_DECLARED_PROFILE'
            _save(args.output_root/'CALIBRATION_STATUS.json',report)
            profile=profile_support_motion(problem,args.sigma_grid,args.tau_grid,deviance_width=args.profile_width)
            _save(args.output_root/'SUPPORT_MOTION_PROFILE.json',profile)
            _save(args.output_root/'SUPPORT_MOTION_WORKING_MODEL.json',dict(
                support_motion_model=profile['support_motion_model'],
                qualification_scope=profile['identification_status'],
                working_value_selection=profile['working_value_selection'],
                automatic_parameter_freeze=False,probability_calibration_complete=False,
                calibration_window_s=[args.start,args.end],source_policy='SOURCE_POLICY.json'))
            report.update(status='COMPLETED_SOURCE_ONLY_PROFILE_NOT_AUTOMATIC_FREEZE',
                          identification_status=profile['identification_status'],
                          parameter_profile_available=True,automatic_parameter_freeze=False)
    except Exception as error:
        report.update(status='FAILED_NO_PARAMETER_FREEZE',error_type=type(error).__name__,error=str(error))
        raise
    finally:
        report['elapsed_s']=time.monotonic()-started
        _save(args.output_root/'CALIBRATION_STATUS.json',report)
        print(json.dumps(_json(report),ensure_ascii=False,allow_nan=False),flush=True)


if __name__ == '__main__':
    main()
