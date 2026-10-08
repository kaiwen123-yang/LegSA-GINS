#!/usr/bin/env python3
"""Read a completed source profile's implications for actual support durations.

This reads existing calibration artifacts and the same original BY source
events. It runs no navigator, evaluator, optimization, fit, or reference read.
The profile contour is a declared working range, not a confidence region.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src'))
from legsa_gins.paper_rebuild.joint_navigation.real_data import By2InputConfig, load_by2_events
from legsa_gins.paper_rebuild.joint_navigation.support_motion import support_motion_transition


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def duration_statistics(values):
    array = np.asarray(values, float)
    if not len(array):
        return dict(count=0, positive_count=0, quantiles_s=None)
    quantiles = np.quantile(array, [0., .25, .5, .75, .95, 1.])
    return dict(count=len(array), positive_count=int(np.count_nonzero(array > 0)),
                quantiles_s=dict(zip(('minimum', 'p25', 'median', 'p75', 'p95', 'maximum'),
                                    map(float, quantiles))))


def displacement_variance(duration, parameters):
    """Per world-axis Var[s(T)] with s(0)=0 and stationary u(0).

    Using the shared exact transition avoids cancellation of the analytic
    2*sigma^2*tau*[T-tau*(1-exp(-T/tau))] formula at very small T.
    """
    sigma, tau = float(parameters['velocity_sigma_mps']), float(parameters['tau_s'])
    transition, process_covariance = support_motion_transition(duration, sigma, tau)
    initial_velocity = transition[:3, 3:]
    total = process_covariance[:3, :3] + sigma*sigma*(initial_velocity @ initial_velocity.T)
    variance = float(total[0, 0])
    if not math.isfinite(variance) or variance < 0:
        raise ValueError('shared OU model produced invalid displacement variance')
    return variance


def prediction_range(duration, supported, grid_minimum):
    variances = [displacement_variance(duration, p) for p in supported]
    low, high = min(variances), max(variances)
    return dict(duration_s=float(duration), per_axis_variance_range_m2=[low, high],
                per_axis_std_range_m=[math.sqrt(low), math.sqrt(high)],
                grid_minimum_per_axis_std_m=math.sqrt(displacement_variance(duration, grid_minimum)),
                standard_deviation_ratio=(math.sqrt(high/low) if low > 0 else None),
                ratio_scope=('FINITE' if low > 0 else 'ZERO_LOWER_VARIANCE_RATIO_UNDEFINED'),
                vector_3d_rms_range_m=[math.sqrt(3*low), math.sqrt(3*high)])


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--calibration-root', type=Path, required=True)
    parser.add_argument('--output-root', type=Path, required=True)
    args = parser.parse_args(argv)
    calibration = args.calibration_root.resolve()
    paths = {name: calibration/name for name in (
        'CALIBRATION_STATUS.json', 'SUPPORT_MOTION_PROFILE.json', 'NOFOOT_SOURCE_CHART.json')}
    status, profile, chart = [read(paths[name]) for name in paths]
    if status['status'] != 'COMPLETED_SOURCE_ONLY_PROFILE_NOT_AUTOMATIC_FREEZE':
        raise ValueError('readout requires the completed source profile; do not infer pending results')
    width = float(profile['relative_deviance_width'])
    supported = [row for row in profile['rows'] if float(row['relative_deviance']) <= width]
    if not supported:
        raise ValueError('completed profile has no parameter pair in its declared working contour')
    config = dict(status['input_config'])
    for field in ('body_path', 'imu_path', 'gnss_path', 'carrier_plan_path',
                  'calibration_model_path', 'imu_noise_profile_path'):
        config[field] = Path(config[field])
    inputs = load_by2_events(By2InputConfig(**config))
    # Same complete, nonoverlapping source policies used by the fit.
    policies = profile['policy']
    arc_group = {}
    groups = {}
    for part in policies:
        name = str(part['group_id'])
        if name in groups:
            raise ValueError('duplicate source-group identity in saved policy')
        groups[name] = dict(group_id=name, arc_ids=list(part['arc_ids']), times=set(),
                            per_time_arcs={}, observations=0)
        for arc in part['arc_ids']:
            if arc in arc_group:
                raise ValueError('saved calibration partition reuses a source arc')
            arc_group[arc] = name
    arc_times, eligible_rows, unassigned = {}, 0, 0
    for event in inputs['events']:
        timestamp = float(event['time_s'])
        for foot in event.get('feet', []):
            if not foot.get('support_eligible', True):
                continue
            eligible_rows += 1
            arc = str(foot['arc_id'])
            arc_times.setdefault(arc, set()).add(timestamp)
            name = arc_group.get(arc)
            if name is None:
                unassigned += 1
                continue
            group = groups[name]
            group['times'].add(timestamp)
            group['per_time_arcs'].setdefault(timestamp, set()).add(arc)
            group['observations'] += 1
    if eligible_rows != profile['scope']['foot_observations']:
        raise ValueError('reloaded eligible foot count differs from the fitted profile')
    rows = []
    for group in groups.values():
        times = sorted(group['times'])
        if not times:
            raise ValueError('saved policy contains a group with no actual calibration observations')
        span = times[-1]-times[0]
        simultaneous = sorted(t for t, arcs in group['per_time_arcs'].items() if len(arcs) >= 2)
        rows.append(dict(group_id=group['group_id'], arc_ids=group['arc_ids'],
            group_size=len(group['arc_ids']), first_observation_s=times[0], last_observation_s=times[-1],
            observation_span_s=span, original_foot_rows=group['observations'], distinct_observed_epochs=len(times),
            epochs_with_at_least_two_observed_members=len(simultaneous),
            multi_member_observation_extent_s=(simultaneous[-1]-simultaneous[0] if simultaneous else None),
            member_arc_spans_s={arc:max(arc_times[arc])-min(arc_times[arc]) for arc in group['arc_ids']},
            displacement_prediction=prediction_range(span, supported, profile['grid_minimum'])))
    actual_spans = [r['observation_span_s'] for r in rows]
    arc_spans = [max(times)-min(times) for times in arc_times.values()]
    horizon = 12.0  # Predeclared complete receiver-P/V gap, not selected from errors.
    target = prediction_range(horizon, supported, profile['grid_minimum'])
    unresolved_seeds = [r for r in chart['seeds'] if not r.get('stationary', False)]
    boundary = bool(profile['profile_touches_grid_boundary'])
    fixed_supported = bool(profile['fixed_model_supported'])
    limitations = [
        'The complete across-time and across-group Gaussian navigation covariance was used by the fit.',
        'The fit remains conditional on one local no-foot GNSS1/PV/IMU chart; seed optimization does not certify global direction uniqueness.',
        'Source grouping is an arc-disjoint calibration partition, not labels of true sliding or independent encoder kinematics.',
        'A group observation extent spans first through last original measurement, including missing/subset observations; it is not a continuously observed multi-foot contact interval.',
        'Predictions integrate the declared OU law from zero displacement and stationary velocity; they are process uncertainty, not navigation-error or slip-truth estimates.',
        'The declared relative-deviance width is not a calibrated confidence region.',
    ]
    if boundary:
        limitations.append('The profile touches its evaluated grid boundary; its finite prediction range is truncated, not a measured upper bound.')
    if fixed_supported:
        limitations.append('The fixed model lies in the working contour; tau has no data meaning at zero process variance.')
    if unresolved_seeds:
        limitations.append('One or more yaw-seed optimizations are unfinished/nonstationary; their larger current costs do not exclude their eventual local modes.')
    support_duration = max(actual_spans) if actual_spans else 0.
    if support_duration < horizon:
        limitations.append('The 12-second prediction extrapolates beyond every calibrated group observation span.')
    report = dict(status='COMPLETED_PROFILE_IMPLICATION_READOUT_NO_FREEZE',
        created_at_utc=datetime.now(timezone.utc).isoformat(), calibration_root=str(calibration),
        calibration_artifact_sha256={name:digest(path) for name,path in paths.items()},
        readout_implementation_sha256=digest(Path(__file__).resolve()),
        shared_process_implementation_sha256=digest(ROOT/'src/legsa_gins/paper_rebuild/joint_navigation/support_motion.py'),
        source_window_s=status['requested_window_s'], source_event_count=len(inputs['events']),
        original_eligible_foot_rows=eligible_rows, unassigned_foot_rows=unassigned,
        group_size_histogram=dict(Counter(r['group_size'] for r in rows)),
        group_observation_span_statistics=duration_statistics(actual_spans),
        individual_arc_observation_span_statistics=duration_statistics(arc_spans),
        group_span_statistics_by_size={str(size):duration_statistics([r['observation_span_s'] for r in rows if r['group_size']==size])
                                       for size in sorted({r['group_size'] for r in rows})},
        declared_profile_width=width, supported_parameter_pair_count=len(supported),
        supported_parameters=[dict(velocity_sigma_mps=p['velocity_sigma_mps'],tau_s=p['tau_s'],
                                   relative_deviance=p['relative_deviance']) for p in supported],
        actual_group_predictions=rows, target_gap_prediction=target,
        target_horizon_exceeds_every_observed_group=horizon > support_duration,
        target_horizon_with_direct_group_span_coverage=sum(span >= horizon for span in actual_spans),
        local_chart=dict(chosen_seed_yaw_deg=chart['chosen_seed_yaw_deg'],
                         stationary_seed_count=sum(bool(s.get('stationary',False)) for s in chart['seeds']),
                         unfinished_seed_count=len(unresolved_seeds), seeds=chart['seeds'],
                         global_direction_uniqueness_proven=False),
        profile_touches_grid_boundary=boundary, fixed_model_supported=fixed_supported,
        identification_status=profile['identification_status'],
        parameter_freeze_decision='NOT_MADE_BY_READOUT',
        twelve_second_prediction_is_empirical_precision_bound=False,
        limitations=limitations, reference_reads=0, navigation_calls=0,evaluator_calls=0,new_fits=0)
    output=args.output_root.resolve()
    output.mkdir(parents=True,exist_ok=False)
    (output/'PROFILE_IMPLICATIONS.json').write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    span_stats=report['group_observation_span_statistics']['quantiles_s']
    lo,hi=target['per_axis_std_range_m']
    lines=['# 支撑共同运动profile的来源约束', '',
           f"来源窗口：{status['requested_window_s']} s；足观测 {eligible_rows} 条，支撑组 {len(rows)} 个。",
           f"组大小分布：{report['group_size_histogram']}；每组仅按原观测首末时刻计算跨度，缺包不切弧。", '',
           f"组跨度 minimum/median/p95/maximum：{span_stats['minimum']:.6g} / {span_stats['median']:.6g} / {span_stats['p95']:.6g} / {span_stats['maximum']:.6g} s。", '',
           f"已评估profile工作支持域包含 {len(supported)} 个参数对；边界截断：{boundary}；固定模型仍在工作域：{fixed_supported}。",
           f"在预声明12 s缺口，世界单轴共同位移预测标准差范围为 **{lo:.6g}–{hi:.6g} m**；网格最优参数为 {target['grid_minimum_per_axis_std_m']:.6g} m。",
           f"实际跨度达到12 s的组：{report['target_horizon_with_direct_group_span_coverage']}；该预测超出全部实测组跨度：{report['target_horizon_exceeds_every_observed_group']}。", '',
           f"无足图驻定种子 {report['local_chart']['stationary_seed_count']}，未驻定/未完成种子 {len(unresolved_seeds)}；选中种子 {chart['chosen_seed_yaw_deg']}°，仅代表一个局部条件图。", '',
           '以上是过程模型预测不确定度，不能解释为真实滑移幅度或导航精度。工作域不是校准置信区间；碰到边界时范围被网格截断。单足短弧不能独立证明多足长期共同运动规律。', '',
           '本读出不决定冻结，不新增拟合、导航、评价或参考读取；应先判断当前来源是否约束了目标长弧预测，再选择有明确范围的工作模型。每组跨度及全部支持参数对见JSON。', '']
    (output/'PROFILE_IMPLICATIONS.md').write_text('\n'.join(lines),encoding='utf-8')
    print(json.dumps(dict(status=report['status'],output_root=str(output),
                         group_count=len(rows),target_gap_prediction=target,
                         profile_touches_grid_boundary=boundary,parameter_freeze_decision='NOT_MADE_BY_READOUT'),
                     ensure_ascii=False,allow_nan=False),flush=True)


if __name__ == '__main__':
    main()
