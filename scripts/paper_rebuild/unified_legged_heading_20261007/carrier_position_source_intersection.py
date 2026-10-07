#!/usr/bin/env python3
"""Frozen BY2O carrier/position source intersection; no NAV/reference/evaluator reads."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import numpy as np

SCRATCH = Path('/home/kaiwen/research/LegSA-GINS-SCRATCH')
UNIFIED = SCRATCH / 'UNIFIED_LEGGED_HEADING_20261007'
FRONT = SCRATCH / 'CONTINUOUS_HEADING_20261007/PARTIAL_FULL_WINDOW_01/BY2O'
PILOT = UNIFIED / 'VECTOR_DIRECTION_SA_BY2O_01'
GNSS = SCRATCH / 'CLEAN8_PROTOCOL_V3/02_PROVIDERS/CASES/BY2O__C00_clean_normal__c5212cf72d07afd6d3ae0407fee87f841f2e0d909dfb8c1416bd7f38b0248bb4/GNSS18.gnss'
START, END = 3186.0, 3563.0


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def stats(values):
    a = np.asarray(values, dtype=float)
    return dict(n=len(a), min=float(np.min(a)), median=float(np.median(a)),
                p95=float(np.percentile(a, 95)), max=float(np.max(a)))


def write_csv(path, rows):
    with path.open('w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def main(out):
    out.mkdir(parents=True, exist_ok=False)
    with (FRONT / 'MOTION.csv').open() as f:
        carrier = [r for r in csv.DictReader(f) if r['valid'] == '1' and START <= float(r['measurement_time']) <= END]
    with (FRONT / 'FULL.csv').open() as f:
        full = {float(r['measurement_time']) for r in csv.DictReader(f) if r['valid'] == '1'}
    source = np.loadtxt(GNSS)
    source = source[(source[:, 0] >= START) & (source[:, 0] <= END)]
    assert source.shape[1] == 18
    p = source[source[:, 15] == 1]
    logs, inputs = {}, [GNSS, FRONT / 'MOTION.csv', FRONT / 'FULL.csv']
    for arm in ('LEGACY', 'VECTOR'):
        path = PILOT / arm / 'NATIVE' / f'BY2O__{arm}' / 'SOURCE_AWARE_WEIGHT_TRACE.csv'
        with path.open() as f:
            rows = [r for r in csv.DictReader(f) if r['source_id'] == 'receiver_position']
        accepted = [r for r in rows if r['accepted'] == '1']
        logs[arm] = dict(rows=rows, accepted=accepted, times=np.array([float(r['time']) for r in accepted]))
        inputs.append(path)
    table = []
    for c in carrier:
        t = float(c['measurement_time'])
        k = int(np.searchsorted(p[:, 0], t, side='right') - 1)
        assert 0 <= k < len(p) - 1
        r = dict(carrier_time=t, kind='FULL' if t in full else 'PARTIAL',
                 previous_source_position_time=p[k, 0], next_source_position_time=p[k + 1, 0],
                 previous_source_position_age_s=t - p[k, 0], next_source_position_delay_s=p[k + 1, 0] - t,
                 previous_source_position_valid=int(p[k, 15]), next_source_position_valid=int(p[k + 1, 15]),
                 previous_source_yaw_valid=int(p[k, 17]), next_source_yaw_valid=int(p[k + 1, 17]))
        for side, j in (('previous', k), ('next', k + 1)):
            for axis, std in zip('NED', p[j, 4:7]):
                r[f'{side}_source_sigma_{axis}_m'] = std
        for arm, log in logs.items():
            ai = int(np.searchsorted(log['times'], t, side='right') - 1)
            assert 0 <= ai < len(log['times']) - 1
            for side, j in (('previous', ai), ('next', ai + 1)):
                event = log['accepted'][j]
                et = float(event['time'])
                scale = float(event['combined_R_scale'])
                srcidx = int(np.argmin(abs(p[:, 0] - et)))
                # Only CSV serialization alignment, not an admission or freshness rule.
                assert abs(p[srcidx, 0] - et) < 1e-6
                prefix = f'{arm.lower()}_{side}'
                r[prefix + '_accepted_position_time'] = et
                r[prefix + '_carrier_signed_delay_s'] = et - t
                r[prefix + '_R_scale'] = scale
                for axis, std in zip('NED', p[srcidx, 4:7] * np.sqrt(scale)):
                    r[f'{prefix}_effective_sigma_{axis}_m'] = std
        table.append(r)
    assert len(table) == 285 and sum(r['kind'] == 'FULL' for r in table) == 168
    assert sum(r['kind'] == 'PARTIAL' for r in table) == 117
    ct = np.array([r['carrier_time'] for r in table])
    pt = np.array([r['carrier_time'] for r in table if r['kind'] == 'PARTIAL'])
    gaps = []
    for a, b in zip(p[:-1, 0], p[1:, 0]):
        gaps.append(dict(start=a, end=b, duration_s=b-a,
                         valid_carrier_inside=int(np.sum((ct > a) & (ct < b))),
                         partial_carrier_inside=int(np.sum((pt > a) & (pt < b)))))
    maximum = max(r['duration_s'] for r in gaps)
    literal_max = [r for r in gaps if r['duration_s'] == maximum]
    summary = dict(
        window=[START, END], inputs=[dict(path=str(path), sha256=digest(path)) for path in inputs],
        script_sha256=digest(Path(__file__)), source_rows=len(source),
        source_position_valid=int(np.sum(source[:, 15] == 1)), source_yaw_valid=int(np.sum(source[:, 17] == 1)),
        source_position_first=float(p[0, 0]), source_position_last=float(p[-1, 0]),
        source_position_sigma_m={axis: stats(p[:, 4 + i]) for i, axis in enumerate('NED')},
        source_position_intervals_s=stats(np.diff(p[:, 0])),
        literal_longest_intervals=dict(count=len(literal_max), duration_s=maximum,
            valid_carrier_inside=sum(r['valid_carrier_inside'] for r in literal_max),
            partial_carrier_inside=sum(r['partial_carrier_inside'] for r in literal_max)),
        source_position_invalid_rows=int(np.sum(source[:, 15] == 0)), arms={}, groups={},
        accepted_position_times_identical=bool(np.array_equal(logs['LEGACY']['times'], logs['VECTOR']['times'])),
        read_scope='GNSS18, FULL/MOTION carrier supply, actual receiver_position SA trace only; no NAV/reference/raw/native/evaluator',
        interpretation='Position measurements occur only at their event times. Brackets do not create held position observations. 0.21 s heading freshness is not a position gate. GNSS18 std is working measurement uncertainty, not accuracy truth; raw receiver pAcc is absent.')
    for arm, log in logs.items():
        summary['arms'][arm] = dict(logged=len(log['rows']), accepted=len(log['accepted']),
            first_accepted=float(log['times'][0]), last_accepted=float(log['times'][-1]),
            intervals_s=stats(np.diff(log['times'])), R_scale=stats([float(r['combined_R_scale']) for r in log['accepted']]))
    for kind in ('ALL', 'FULL', 'PARTIAL'):
        rows = [r for r in table if kind == 'ALL' or r['kind'] == kind]
        group = dict(n=len(rows), source_position_valid_both_sides=sum(r['previous_source_position_valid'] and r['next_source_position_valid'] for r in rows),
            previous_source_yaw_invalid=sum(not r['previous_source_yaw_valid'] for r in rows),
            next_source_yaw_invalid=sum(not r['next_source_yaw_valid'] for r in rows),
            exact_position_event_coincidence=int(sum(r['previous_source_position_age_s'] == 0 or r['next_source_position_delay_s'] == 0 for r in rows)))
        for col in rows[0]:
            if ('sigma_' in col or col.endswith('_age_s') or col.endswith('_delay_s') or col.endswith('_R_scale')):
                group[col] = stats([r[col] for r in rows])
        summary['groups'][kind] = group
    write_csv(out / 'CARRIER_POSITION_INTERSECTION.csv', table)
    write_csv(out / 'SOURCE_POSITION_INTERVALS.csv', gaps)
    (out / 'SUMMARY.json').write_text(json.dumps(summary, indent=2) + '\n')
    seal = {path.name: digest(path) for path in sorted(out.iterdir()) if path.is_file()}
    (out / 'OUTPUT_SEAL.json').write_text(json.dumps(seal, indent=2) + '\n')
    print(json.dumps({k: summary[k] for k in ('source_rows', 'source_position_valid', 'source_yaw_valid', 'arms', 'literal_longest_intervals', 'accepted_position_times_identical')}, indent=2))
    for kind, group in summary['groups'].items():
        print(kind, json.dumps({k: v for k, v in group.items() if k in ('n', 'source_position_valid_both_sides', 'previous_source_yaw_invalid', 'next_source_yaw_invalid', 'exact_position_event_coincidence') or k.startswith('previous_source_sigma') or k.startswith('next_source_sigma')}, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', type=Path, required=True)
    main(parser.parse_args().out)
