#!/usr/bin/env python3
"""Frozen NMB1 foot-pair relative direction, source-only diagnostic.
No NAV/reference, native/evaluator, fitting, reselection, or fusion update.
"""
from pathlib import Path
from collections import Counter
import argparse, csv, hashlib, json, math, re, time
import numpy as np
from scipy.spatial.transform import Rotation

I3 = np.eye(3)
POINT_SIGMA = .01
FOOT_ORDER = ['FR', 'FL', 'RR', 'RL']
ANTENNA = np.array([0., -.35, 0.])


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save_json(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False)+'\n')


def read_csv(path):
    with Path(path).open() as stream:
        return list(csv.DictReader(stream))


def save_csv(path, rows):
    keys = list(dict.fromkeys(k for row in rows for k in row))
    with path.open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=keys)
        writer.writeheader()
        writer.writerows(rows)


def stats(values):
    a = np.asarray(values, float)
    if not len(a):
        return {'n': 0}
    return dict(n=len(a), mean=float(a.mean()), median=float(np.median(a)),
                p95=float(np.quantile(a, .95)), abs_p95=float(np.quantile(abs(a), .95)),
                min=float(a.min()), max=float(a.max()), rms=float(np.sqrt(np.mean(a*a))))


def skew(v):
    x, y, z = v
    return np.array([[0., -z, y], [z, 0., -x], [-y, x, 0.]])


def vector(row, foot):
    return np.array([float(row['r_'+foot+'_body_frd_'+ax+'_m']) for ax in 'xyz'])


def add_vector(row, prefix, value):
    row.update({prefix+'_'+ax: float(v) for ax, v in zip('xyz', value)})


def add_matrix(row, prefix, value):
    row.update({prefix+'_'+str(i)+str(j): float(value[i, j])
                for i in range(value.shape[0]) for j in range(value.shape[1])})


def tangent(u):
    # Coordinate construction, not a measured axis or a data-dependent gate.
    seed = I3[:, int(np.argmin(abs(u)))]
    t1 = seed-u*np.dot(u, seed)
    t1 /= np.linalg.norm(t1)
    return np.column_stack((t1, np.cross(u, t1)))


def true(value):
    return str(value).lower() in ('true', '1')


def config_value(text, key):
    value = re.search(r'^'+re.escape(key)+r':\s*(.+)$', text, re.M).group(1)
    return json.loads(value)


def run(args):
    begun = time.monotonic()
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=False)
    provider = Path(args.provider)
    paths = dict(events=provider/'SUPPORT_POSE_EVENTS.csv',
                 endpoint_identity=provider/'ENDPOINT_RAW_IDENTITY.csv',
                 interval_identity=provider/'INTERVAL_IDENTITY.csv',
                 provider_manifest=provider/'MANIFEST.json',
                 cache=Path(args.source_cache), imu=Path(args.imu),
                 config=Path(args.config), carrier=Path(args.carrier),
                 frontend_epochs=Path(args.frontend_epochs),
                 partial_domains=Path(args.partial_domains),
                 motion_domains=Path(args.motion_domains),
                 protocol_slots=Path(args.protocol_slots))
    pins = {key: dict(path=str(path), sha256=sha(path)) for key, path in paths.items()}
    events = read_csv(paths['events'])
    identities = {(r['clone_id'], r['event_type']): r for r in read_csv(paths['endpoint_identity'])}
    original_intervals = {r['clone_id']: r for r in read_csv(paths['interval_identity'])}
    manifest = json.loads(paths['provider_manifest'].read_text())
    window = manifest['native_window']
    gap = max(manifest['longest_position_intervals'], key=lambda r: r['duration_s'])
    gaplo, gaphi = gap['t0_s'], gap['t1_s']
    cfg = paths['config'].read_text()
    arw = np.asarray(config_value(cfg, 'arw'))*math.pi/180/60
    gbstd = np.asarray(config_value(cfg, 'gbstd'))*math.pi/180/3600
    corrtime = float(config_value(cfg, 'corrtime'))*3600
    assert np.array_equal(arw, np.repeat(.985*math.pi/180/60, 3))
    assert np.array_equal(gbstd, np.repeat(9.38*math.pi/180/3600, 3))
    assert corrtime == 3600.
    plan = dict(schema='foot_differential_direction_source.v1',
        input_pins=pins, script_sha256=sha(__file__), native_window=window,
        gap_window=[gaplo, gaphi], expected_END=481, expected_gap_END=242,
        selection='all original END; original endpoints/tokens/length contradictions retained',
        residual='f=D*(r_i1-r_j1)-(r_i0-r_j0); D maps body1 to body0',
        endpoint_order=['r_i0', 'r_j0', 'r_i1', 'r_j1'],
        endpoint_covariance='Sigma12=sigma_p^2 I12 working model; A=[-I,I,D,-D]; W=A Sigma12 A^T',
        point_sigma_m=POINT_SIGMA, antenna_body_m=ANTENNA.tolist(),
        relative_H='-skew(D*b1) for physical left relative rotation in body0',
        imu_rotation='right product Exp(dtheta) from source-row START+1 through END; no future source sample',
        imu_not_native_D='no coning, Earth/transport, estimated bias or state feedback; inherited Rx(-1 deg) and removed prefix gyro mean retained',
        white_gyro='Qtheta=sum Dpre diag(arw^2) Dpre^T dt; first-order continuous white-noise sensitivity only',
        bias='gbstd/corrtime recorded; gbstd*duration is a stationary short-interval scale, not native posterior or extra scored prior',
        unknown_cross='SDK foot/gyro shared processing and removed gyro-mean temporal dependence are uncalibrated',
        noise=dict(arw_rad_sqrt_s=arw.tolist(), gbstd_rad_s=gbstd.tolist(), corrtime_s=corrtime),
        coordinate_contract='historical engine working body frame for IMU, original FRD foot identity mapping; no frame correction',
        partial='existing domain/protocol source only; no Gaussian yaw replacement or synthetic anchor',
        NAV_reads=0, reference_reads=0, raw_scans=0, native_calls=0, evaluator_calls=0,
        new_rejections=0, fits=0, source_direction_is_truth=False)
    save_json(out/'PLAN.json', plan)

    with np.load(paths['cache']) as data:
        ns = data['native_ns'].copy()
        source_rows = data['source_rows'].copy()
        feet = data['foot_position_body_frd'].copy()
        metadata = json.loads(str(data['metadata']))
    imu = np.loadtxt(paths['imu'], ndmin=2)
    # Provider drops the first source sample (no prior dt); original source row is 1-based.
    indices = source_rows.astype(int)-2
    assert np.all((indices >= 0) & (indices < len(imu)))
    time_error = imu[indices, 0]-ns/1e9
    assert np.max(abs(time_error)) < 1e-6  # Unix-double identity tolerance, not a selection gate.
    assert np.all(np.diff(source_rows) == 1)
    ns_index = {int(n): k for k, n in enumerate(ns)}
    carrier = read_csv(paths['carrier'])
    epochs = read_csv(paths['frontend_epochs'])
    partial = read_csv(paths['partial_domains'])
    motion = read_csv(paths['motion_domains'])
    protocol = read_csv(paths['protocol_slots'])
    assert len(carrier) == len(epochs) == len(protocol) == 1756
    assert all(float(a['measurement_time']) == float(b['time_s']) and int(a['valid']) == int(b['valid'])
               for a, b in zip(carrier, epochs))
    carrier_times = np.array([float(r['measurement_time']) for r in carrier if true(r['valid'])])
    partial_times = np.array([float(r['time_s']) for r in partial])
    starts = {}
    rows = []
    dependency_rows = []
    endpoint_uses = Counter()
    imu_uses = Counter()
    alignment = []
    max_endpoint_error = 0.
    max_W_error = 0.
    for end in events:
        if end['event_type'] == 'START':
            starts[end['clone_id']] = end
            continue
        if end['event_type'] != 'END':
            continue
        cid = end['clone_id']
        start = starts[cid]
        id0, id1 = identities[(cid, 'START')], identities[(cid, 'END')]
        n0, n1 = int(id0['native_stamp_ns']), int(id1['native_stamp_ns'])
        t0, t1 = n0/1e9, n1/1e9
        row = dict(clone_id=cid, t0_s=t0, t1_s=t1, native_ns0=n0, native_ns1=n1,
            dt_source_s=(n1-n0)/1e9, foot_i=end['foot_i'], foot_j=end['foot_j'],
            episode_i=end['episode_i'], episode_j=end['episode_j'],
            endpoint_id0=start['endpoint_id'], endpoint_id1=end['endpoint_id'],
            original_END_reason=end['reason'], inside_gap=bool(t0>=gaplo and t1<=gaphi),
            status='AVAILABLE_GYRO_CONDITIONAL', newly_rejected=False)
        rows.append(row)
        for key in ['foot_i', 'foot_j', 'episode_i', 'episode_j']:
            assert start[key] == end[key]
        if n0 not in ns_index or n1 not in ns_index:
            row.update(status='UNAVAILABLE', reason='MISSING_EXACT_SOURCE_ENDPOINT')
            continue
        k0, k1 = ns_index[n0], ns_index[n1]
        s0, s1 = int(source_rows[k0]), int(source_rows[k1])
        assert s0 == int(id0['raw_source_row']) and s1 == int(id1['raw_source_row'])
        i0, i1 = s0-2, s1-2
        F0 = np.stack([vector(start, 'i'), vector(start, 'j')])
        F1 = np.stack([vector(end, 'i'), vector(end, 'j')])
        selected = [FOOT_ORDER.index(end['foot_i']), FOOT_ORDER.index(end['foot_j'])]
        point_error = max(float(abs(F0-feet[k0, selected]).max()), float(abs(F1-feet[k1, selected]).max()))
        max_endpoint_error = max(max_endpoint_error, point_error)
        assert point_error == 0.
        D = I3.copy()
        Qg = np.zeros((3, 3))
        for k in range(i0+1, i1+1):
            Qg += D@np.diag(arw*arw)@D.T*imu[k, 7]
            D = D@Rotation.from_rotvec(imu[k, 1:4]).as_matrix()
            imu_uses[k+1] += 1
        duration = float(imu[i0+1:i1+1, 7].sum())
        b0, b1 = F0[0]-F0[1], F1[0]-F1[1]
        l0, l1 = float(np.linalg.norm(b0)), float(np.linalg.norm(b1))
        if min(l0, l1) == 0:
            row.update(status='UNAVAILABLE', reason='ZERO_PAIR_BASELINE')
            continue
        a = D@b1
        u0, u1, u = b0/l0, b1/l1, a/l1
        T = tangent(u0)
        C = np.column_stack((u0, T))
        f = a-b0
        A = np.hstack((-I3, I3, D, -D))
        W = A@(POINT_SIGMA**2*np.eye(12))@A.T
        max_W_error = max(max_W_error, float(abs(W-4*POINT_SIGMA**2*I3).max()))
        H = -skew(a)
        Sg = W+H@Qg@H.T
        J = H.T@np.linalg.solve(W, H)
        Jg = H.T@np.linalg.solve(Sg, H)
        eig = np.linalg.eigvalsh(J)
        eigg = np.linalg.eigvalsh(Jg)
        rank = int(np.sum(eig > eig[-1]*1e-10))
        # Normalized direction is rank two. It is not a third independent factor.
        B0 = (I3-np.outer(u0,u0))/l0
        B1 = D@(I3-np.outer(u1,u1))/l1
        An = np.hstack((-B0, B0, B1, -B1))
        Wn = An@(POINT_SIGMA**2*np.eye(12))@An.T
        q = u-u0
        Hg = -skew(u)
        Sn = Wn+Hg@Qg@Hg.T
        ft = T.T@f
        qt = T.T@q
        ntcov = T.T@Wn@T
        ntcovg = T.T@Sn@T
        abc = D@ANTENNA
        antunit = abc/np.linalg.norm(abc)
        cosweak = float(np.clip(abs(np.dot(u, antunit)), 0, 1))
        legacy = original_intervals[cid]
        length_change = l1-l0
        assert abs(abs(length_change)-float(legacy['pair_length_change_m'])) < 1e-12
        rotation_deg = float(np.linalg.norm(Rotation.from_matrix(D).as_rotvec())*180/np.pi)
        row.update(pair=end['foot_i']+'-'+end['foot_j'], point_sigma_m=POINT_SIGMA,
            imu_first_source_row=s0+1, imu_last_source_row=s1,
            imu_first_line_1based=i0+2, imu_last_line_1based=i1+1,
            imu_increment_rows=i1-i0, dt_imu_s=duration,
            dt_imu_minus_source_s=duration-(n1-n0)/1e9,
            point_cache_max_difference_m=point_error, baseline0_m=l0, baseline1_m=l1,
            length_change_m=length_change, length_change_std_working_m=2*POINT_SIGMA,
            length_change_standardized=length_change/(2*POINT_SIGMA),
            original_length_limit_m=float(legacy['geometry_working_limit_m']),
            original_length_contradiction=true(legacy['geometry_working_contradiction']),
            gyro_rotation_deg=rotation_deg, residual_norm_m=float(np.linalg.norm(f)),
            radial_residual_m=float(u0@f), tangent1_m=float(ft[0]), tangent2_m=float(ft[1]),
            tangent_norm_m=float(np.linalg.norm(ft)),
            direction_angle_deg=float(np.arctan2(np.linalg.norm(np.cross(u0,u)),np.dot(u0,u))*180/np.pi),
            normalized_tangent1=float(qt[0]), normalized_tangent2=float(qt[1]),
            endpoint_only_3d_quadratic=float(f@np.linalg.solve(W,f)),
            endpoint_plus_white_gyro_3d_quadratic=float(f@np.linalg.solve(Sg,f)),
            normalized_2d_quadratic=float(qt@np.linalg.solve(ntcov,qt)),
            normalized_2d_plus_white_gyro_quadratic=float(qt@np.linalg.solve(ntcovg,qt)),
            relative_information_rank=rank, relative_eigen0=float(eig[0]),
            relative_eigen1=float(eig[1]), relative_eigen2=float(eig[2]),
            relative_eigen1_white_gyro=float(eigg[1]),
            relative_eigen2_white_gyro=float(eigg[2]),
            weak_axis_residual=float(np.linalg.norm(J@u)),
            relative_observable_std_deg=float(1/np.sqrt(eig[1])*180/np.pi),
            gyro_white_std_deg=float(np.sqrt(np.trace(Qg)/3)*180/np.pi),
            stationary_bias_short_interval_scale_deg=float(np.max(gbstd)*duration*180/np.pi),
            foot_to_white_gyro_information_ratio=float(eig[1]*np.trace(Qg)/3),
            baseline_weak_axis_acute_angle_deg=float(np.arccos(cosweak)*180/np.pi),
            antenna_weak_axis_in_foot_observed_plane_fraction=1-cosweak*cosweak,
            body0_down_rotation_information=float(J[2,2]),
            body0_down_is_not_absolute_yaw=True,
            valid_carrier_times_inside_interval=int(np.sum((carrier_times>=t0)&(carrier_times<=t1))),
            partial_domain_records_inside_interval=int(np.sum((partial_times>=t0)&(partial_times<=t1))))
        for name, value in [('baseline0_body0_m',b0),('baseline1_body1_m',b1),
                            ('rotated_baseline1_body0_m',a),('residual_body0_m',f),
                            ('weak_axis_body0',u),('tangent_basis1_body0',T[:,0]),
                            ('tangent_basis2_body0',T[:,1]),('antenna_weak_axis_body0',antunit)]:
            add_vector(row,name,value)
        for name, value in [('D',D),('W_endpoint_m2',W),('Q_gyro_white_rad2',Qg),
                            ('S_endpoint_white_m2',Sg),('J_relative_rad_inv2',J),
                            ('radial_tangent_cov_m2',C.T@Sg@C),
                            ('normalized_tangent_cov',ntcov),
                            ('normalized_tangent_white_cov',ntcovg)]:
            add_matrix(row,name,value)
        dep = dict(clone_id=cid, episode_i=start['episode_i'], episode_j=start['episode_j'],
            endpoint_id0=start['endpoint_id'], endpoint_id1=end['endpoint_id'],
            gyro_input_sha256=pins['imu']['sha256'], gyro_source_first=s0+1, gyro_source_last=s1,
            conditional_rotation_only=True, additional_gyro_factor=False,
            unknown_SDK_foot_gyro_cross=True, inherited_prefix_mean_global_dependency=True,
            dependency_scope='foot endpoints+both tokens; gyro conditional evidence has separate source dependency; independent carrier has no invented foot dependency')
        dependency_rows.append(dep)
        for event in (start,end):
            for foot in (end['foot_i'],end['foot_j']):
                endpoint_uses[event['endpoint_id']+'|'+foot] += 1
        alignment.append(dict(clone_id=cid,source_row0=s0,source_row1=s1,
            native_ns0=n0,native_ns1=n1,IMU_line0=i0+1,IMU_line1=i1+1,
            IMU_time_minus_source0_s=float(imu[i0,0]-t0),
            IMU_time_minus_source1_s=float(imu[i1,0]-t1)))

    assert len(rows) == 481
    assert sum(r['inside_gap'] for r in rows) == 242
    groups = {}
    stats_rows = []
    metrics = ['dt_source_s','baseline0_m','baseline1_m','length_change_m','residual_norm_m',
        'radial_residual_m','tangent_norm_m','direction_angle_deg','gyro_rotation_deg',
        'endpoint_only_3d_quadratic','endpoint_plus_white_gyro_3d_quadratic',
        'normalized_2d_quadratic','relative_eigen1','relative_eigen2','relative_observable_std_deg',
        'gyro_white_std_deg','stationary_bias_short_interval_scale_deg',
        'foot_to_white_gyro_information_ratio','baseline_weak_axis_acute_angle_deg',
        'antenna_weak_axis_in_foot_observed_plane_fraction']
    for label, sub in [('FULL',rows),('GAP',[r for r in rows if r['inside_gap']])]:
        available = [r for r in sub if r['status']=='AVAILABLE_GYRO_CONDITIONAL']
        summary = dict(total_END_denominator=len(sub),available=len(available),
            status_counts=dict(Counter(r['status'] for r in sub)),
            pair_counts=dict(Counter(r['pair'] for r in available)),
            rank_counts=dict(Counter(r['relative_information_rank'] for r in available)),
            original_length_contradictions=sum(r['original_length_contradiction'] for r in available),
            newly_rejected=0, covered_interval_duration_s=sum(r['dt_source_s'] for r in sub),
            intervals_containing_valid_carrier=sum(r['valid_carrier_times_inside_interval']>0 for r in available),
            intervals_containing_partial_domain_record=sum(r['partial_domain_records_inside_interval']>0 for r in available),
            statistics={m:stats([r[m] for r in available]) for m in metrics})
        groups[label]=summary
        for pair in ['ALL']+sorted(set(r['pair'] for r in available)):
            pp=available if pair=='ALL' else [r for r in available if r['pair']==pair]
            for m in metrics:
                stats_rows.append(dict(window=label,pair=pair,metric=m,**stats([r[m] for r in pp])))
    boundaries=[]
    policy_cols=[k for k in protocol[0] if k.endswith('_qualified')]
    for label,lo,hi in [('FULL',window[0],window[1]),('GAP',gaplo,gaphi)]:
        cc=[r for r in carrier if lo<=float(r['measurement_time'])<=hi]
        pp=[r for r in partial if lo<=float(r['time_s'])<=hi]
        mm=[r for r in motion if lo<=float(r['time_s'])<=hi]
        qq=[r for r in protocol if lo<=float(r['time_s'])<=hi]
        b=dict(window=label,carrier_slot_rows=len(cc),carrier_valid=sum(true(r['valid']) for r in cc),
            partial_domain_records=len(pp),partial_unique_times=len(set(r['time_s'] for r in pp)),
            raw_single_nonfull=sum(true(r['raw_single_nonfull']) for r in mm),
            unsigned_single_nonfull=sum(true(r['unsigned_single_nonfull']) for r in mm),
            directed_single_nonfull=sum(true(r['directed_single_nonfull']) for r in mm),
            actual_partial_gaussian_information_created=False,absolute_anchor_added=False)
        b.update({k+'_slots':sum(true(r[k]) for r in qq) for k in policy_cols})
        boundaries.append(b)
    summary=dict(schema=plan['schema'],status='COMPLETE_SOURCE_ONLY',windows=groups,
        frontend_boundaries=boundaries,cache_source_metadata=metadata,
        alignment=dict(cache_rows=len(ns),IMU_rows=len(imu),
            source_row_to_IMU_zero_index_offset=-2,
            full_cache_time_rounding_max_abs_s=float(abs(time_error).max()),
            endpoint_cache_max_abs_m=max_endpoint_error,
            covariance_formula_max_abs_m2=max_W_error,
            endpoint_point_keys=len(endpoint_uses),
            endpoint_point_keys_reused=sum(v>1 for v in endpoint_uses.values()),
            gyro_increment_rows_used=len(imu_uses),
            gyro_increment_rows_reused=sum(v>1 for v in imu_uses.values())),
        inference='rank2 relative direction only; no unanchored absolute yaw increment; no calibrated stochastic independence or navigation efficacy',
        NAV_reads=0,reference_reads=0,raw_scans=0,native_calls=0,evaluator_calls=0,new_rejections=0,
        wall_s=time.monotonic()-begun)
    save_csv(out/'INTERVALS.csv',rows)
    save_csv(out/'SOURCE_ALIGNMENT.csv',alignment)
    save_csv(out/'DEPENDENCIES.csv',dependency_rows)
    save_csv(out/'SUMMARY_METRICS.csv',stats_rows)
    save_csv(out/'FRONTEND_BOUNDARIES.csv',boundaries)
    save_json(out/'SUMMARY.json',summary)
    save_json(out/'OUTPUT_SEAL.json',dict(files={p.name:sha(p) for p in sorted(out.iterdir()) if p.is_file()},
        input_pins=pins,script_sha256=sha(__file__)))
    print(json.dumps(dict(status=summary['status'],windows={k:dict(END=v['total_END_denominator'],
        available=v['available'],rank=v['rank_counts'],length_contradictions=v['original_length_contradictions'],
        angle_deg=v['statistics']['direction_angle_deg'],weak_angle_deg=v['statistics']['baseline_weak_axis_acute_angle_deg'],
        relative_std_deg=v['statistics']['relative_observable_std_deg']) for k,v in groups.items()},
        frontend_boundaries=boundaries,alignment=summary['alignment'],wall_s=summary['wall_s']),indent=2))


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for key in ['provider','source-cache','imu','config','carrier','frontend-epochs',
                'partial-domains','motion-domains','protocol-slots','output']:
        parser.add_argument('--'+key, required=True)
    run(parser.parse_args())

