"""HX-03R-1: arithmetic on retained evaluation products; no evaluator imports."""
import csv
import hashlib
import io
import json
import os
from pathlib import Path
import sys

OUT = Path(__file__).resolve().parent
W = Path('/home/kaiwen/research/LegSA-GINS-WORKTREES/clean3-math-repair')
STAGES = Path('/mnt/g/LegSA-GINS-project/clean_rebuild_202607/stages')
HX03 = STAGES / 'CLEAN9_EXTERNAL_COMPARISON/HX03_DEGRADATION'
V3 = STAGES / 'CLEAN8_PROTOCOL_V3'
READS = {}

def guard(event, args):
    if event == 'open' and isinstance(args[0], (str, bytes, os.PathLike)):
        p = Path(os.fsdecode(args[0])).absolute()
        if '/data/raw/' in str(p) or p.suffix.lower() in ('.nav', '.bag', '.fpl') or p.name.startswith('trace_vrtk'):
            raise RuntimeError('Forbidden source open: ' + str(p))
        mode, flags = args[1], args[2]
        write = (isinstance(mode, str) and any(c in mode for c in 'wax+')) or (isinstance(flags, int) and flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC))
        if write and OUT not in p.parents:
            raise RuntimeError('Write outside diagnostic output: ' + str(p))
    if event in ('subprocess.Popen', 'os.system', 'os.exec', 'os.posix_spawn'):
        raise RuntimeError('Child execution forbidden')

sys.addaudithook(guard)
import numpy as np
import pandas as pd

def short(p):
    return str(p).replace(str(HX03), '$HX03').replace(str(V3), '$V3').replace(str(W), '$W')

def data(p):
    b = p.read_bytes()
    READS[short(p)] = hashlib.sha256(b).hexdigest()
    return b

def js(p):
    return json.loads(data(p))

def write_json(name, obj):
    (OUT / name).write_text(json.dumps(obj, indent=2, ensure_ascii=False, allow_nan=False) + '\n')

def write_csv(name, rows):
    with (OUT / name).open('w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator='\n')
        writer.writeheader()
        writer.writerows(rows)

def dist(values):
    a = np.array(values, dtype=float)
    return {'n': len(a), 'min': float(a.min()), 'median': float(np.median(a)), 'p95': float(np.percentile(a, 95)), 'max': float(a.max())} if len(a) else {'n': 0, 'min': None, 'median': None, 'p95': None, 'max': None}

def regress(rows, field):
    x = np.array([r[field] for r in rows]); y = np.array([r['audit_horizontal_max_m'] for r in rows])
    slope, intercept = np.linalg.lstsq(np.column_stack((x, np.ones(len(x)))), y, rcond=None)[0]
    pred = slope*x + intercept
    return {'n': len(x), 'x': field, 'y': 'audit_horizontal_max_m', 'slope': float(slope), 'intercept': float(intercept), 'r2': float(1 - np.sum((y-pred)**2)/np.sum((y-y.mean())**2)), 'scope': 'cross-run maxima; epochs not necessarily coincident; not a time-offset test'}

def summary_values(s):
    return {'frozen_yaw_rmse_deg': s['attitude']['yaw_rmse_deg'],
            'frozen_horizontal_rmse_m': s['position']['horizontal_rmse_m'],
            'frozen_up_rmse_m': s['position']['up_rmse_m'],
            'frozen_yaw_p95_deg': s['attitude']['yaw_p95_deg']}

table_path = HX03 / '90_AGGREGATE/DEGRADATION_EXTERNAL_TABLE.csv'
table = list(csv.DictReader(io.StringIO(data(table_path).decode('utf-8-sig'))))
selected = [(line, r) for line, r in enumerate(table, 2) if r['failure_class'] == 'UNAVAILABLE_EVALUATION_FAILED']
physical = {}
records = []
for line, row in selected:
    source = row['source_run_dir']
    run = Path(source.replace('$HX03', str(HX03)))
    if source not in physical:
        manifest = js(run / 'OUTPUT_HASHES.json')
        p = run / 'eval/v3/OUTPUT'
        s, c, cfg = (js(p / name) for name in ('summary.json', 'EVALUATOR_CAPTURE.json', 'CAPTURE_CONFIG.json'))
        result = js(run / 'eval/v3/EVALUATION_RESULT.json')
        err = pd.read_csv(io.BytesIO(data(p / 'error_series.csv')))
        v2 = run / 'eval/v2/OUTPUT'
        c2, s2, cfg2 = (js(v2 / name) for name in ('EVALUATOR_CAPTURE.json', 'summary.json', 'CAPTURE_CONFIG.json'))
        for rel, expected in manifest.items():
            path = short(run / rel)
            if path in READS:
                assert READS[path] == expected, ('Archive hash mismatch', path)
        a = c['consistency']
        assert a['passed'] is False and result['row']['metrics_admitted'] is False
        assert not cfg.get('consistency_policy') and not cfg2.get('consistency_policy')
        assert result['capture']['consistency'] == a
        assert a['matched_epoch_count'] == s['meta']['num_samples'] == len(err)
        assert c['evaluator_sha256'] == 'aa0492482b6467cdd701bc8882aca11c4170bbe2e7c6bb5f932679dc204978da'
        v = summary_values(s)
        h, u, yaw = (err[k].to_numpy(float) for k in ('horizontal_err_m', 'err_u_m', 'yaw_err_deg'))
        t = err.time.to_numpy(float)
        dt = np.diff(t)
        assert np.all(dt > 0) and np.isfinite(err.to_numpy(float)).all()
        check = {'series_recheck_yaw_rmse_deg': float(np.sqrt(np.mean(yaw*yaw))),
                 'series_recheck_horizontal_rmse_m': float(np.sqrt(np.mean(h*h))),
                 'series_recheck_up_rmse_m': float(np.sqrt(np.mean(u*u))),
                 'series_recheck_yaw_p95_deg': float(np.percentile(np.abs(yaw), 95))}
        rels = [abs(check[k.replace('frozen_', 'series_recheck_')]-val)/max(abs(val), 1e-300) for k, val in v.items()]
        assert max(rels) <= 1e-10
        j = int(np.argmax(h))
        dn = np.diff(err.err_n_m.to_numpy(float)); de = np.diff(err.err_e_m.to_numpy(float))
        max_rate = float(np.max(np.hypot(dn, de)/dt))
        d = {**v, **check,
             'series_recheck_max_relative_difference': max(rels),
             'observer_yaw_rmse_deg': '', 'observer_horizontal_rmse_m': '', 'observer_up_rmse_m': '', 'observer_yaw_p95_deg': '',
             'observer_metrics_status': 'UNAVAILABLE_NOT_RETAINED',
             'audit_horizontal_max_m': a['horizontal_max_m'], 'audit_up_max_m': a['up_max_m'], 'audit_yaw_max_deg': a['yaw_max_deg'],
             'matched_epoch_count': a['matched_epoch_count'],
             'max_discrepancy_time_s': '', 'horizontal_error_at_max_discrepancy_m': '', 'error_rate_at_max_discrepancy_mps': '', 'equivalent_time_offset_s': '',
             'argmax_status': 'UNAVAILABLE_NOT_RETAINED',
             'audit_hmax_over_frozen_hrmse': a['horizontal_max_m']/v['frozen_horizontal_rmse_m'],
             'observer_h_rmse_lower_bound_m': max(0.0, v['frozen_horizontal_rmse_m']-a['horizontal_max_m']),
             'observer_h_rmse_upper_bound_m': v['frozen_horizontal_rmse_m']+a['horizontal_max_m'],
             'observer_vs_frozen_h_rmse_relative_difference': '',
             'frozen_horizontal_max_m': float(h[j]), 'frozen_horizontal_max_time_s': float(t[j]),
             'frozen_horizontal_error_vector_secant_rate_max_mps': max_rate,
             'error_series_dt_median_s': float(np.median(dt)), 'error_series_dt_p95_s': float(np.percentile(dt,95)),
             'audit_policy': 'default_local_sphere',
             'v2_audit_horizontal_max_m': c2['consistency']['horizontal_max_m'],
             'v2_audit_up_max_m': c2['consistency']['up_max_m'],
             'v2_audit_yaw_max_deg': c2['consistency']['yaw_max_deg'],
             'v2_audit_passed': c2['consistency']['passed'],
             'v2_frozen_horizontal_rmse_m': s2['position']['horizontal_rmse_m'],
             'summary_source': short(p/'summary.json'), 'capture_source': short(p/'EVALUATOR_CAPTURE.json'),
             'error_series_source': short(p/'error_series.csv'), 'v2_capture_source': short(v2/'EVALUATOR_CAPTURE.json')}
        physical[source] = d
        print('retained run', len(physical), flush=True)
    records.append({'table_line': line, **{k: row[k] for k in ('case_id','family','type','seed','method','config','input_identity_note','source_run_dir')}, **physical[source]})

selection = js(OUT / 'CONTROL_SELECTION.json')
controls = []
for r in selection['selected']:
    p = Path(r['resolved_error_series_source'])
    s, c, cfg = (js(p/name) for name in ('summary.json','EVALUATOR_CAPTURE.json','CAPTURE_CONFIG.json'))
    a = c['consistency']
    assert a['policy'] == cfg['consistency_policy'] == 'canonical_v2_wgs84_full_support'
    assert a['passed'] is True
    v = summary_values(s)
    assert np.isclose(v['frozen_horizontal_rmse_m'], r['horizontal_rmse_m'], rtol=1e-12, atol=0)
    controls.append({**{k:r[k] for k in ('run_id','method_id','case_id','evaluator_contract')}, **v,
        'audit_horizontal_max_m': a['horizontal_max_m'], 'audit_up_max_m': a['up_max_m'], 'audit_yaw_max_deg': a['yaw_max_deg'],
        'matched_epoch_count': a['matched_epoch_count'], 'audit_hmax_over_frozen_hrmse': a['horizontal_max_m']/v['frozen_horizontal_rmse_m'],
        'audit_policy': a['policy'], 'audit_passed': a['passed'], 'summary_source': short(p/'summary.json'), 'capture_source': short(p/'EVALUATOR_CAPTURE.json')})

fields = ['frozen_horizontal_rmse_m','frozen_horizontal_max_m','audit_horizontal_max_m','audit_up_max_m','audit_yaw_max_deg','audit_hmax_over_frozen_hrmse','series_recheck_max_relative_difference','error_series_dt_median_s','error_series_dt_p95_s']
def stats(rows):
    return {k:dist([r[k] for r in rows]) for k in fields if k in rows[0]}

unique = list(physical.values())
counts = {}
for r in records:
    key = r['type'] + '/' + r['method']
    counts[key] = counts.get(key, 0) + 1
statistics = {'logical_rows':len(records), 'unique_physical_runs':len(unique), 'counts_by_type_method':counts,
    'logical':stats(records), 'unique':stats(unique), 'controls':stats(controls),
    'equivalent_time_offset_s':dist([]), 'observer_vs_frozen_h_rmse_relative_difference':dist([]),
    'unique_cross_run_regressions':[regress(unique,k) for k in ('frozen_horizontal_max_m','frozen_horizontal_rmse_m','frozen_horizontal_error_vector_secant_rate_max_mps')],
    'audit_failure_counts_unique': {k:sum(r[k] > threshold for r in unique) for k,threshold in [('audit_horizontal_max_m',.01),('audit_up_max_m',.01),('audit_yaw_max_deg',.01)]},
    'v2_failed_unique':sum(not r['v2_audit_passed'] for r in unique),
    'missing_observer_metrics_logical':len(records), 'missing_argmax_logical':len(records),
    'native_calls':0,'evaluator_calls':0,'reference_opens':0,
    'diagnostic_scope':'retained summary/error-series/capture statistics only; no NAV or reference reconstruction'}
assert len(records) == 146 and len(unique) == 113 and len(controls) == 20
write_csv('D12_DIAGNOSIS.csv', records)
write_csv('V3_D03_D04_CONTROLS.csv', controls)
write_json('DIAGNOSTIC_STATISTICS.json', statistics)
write_json('INPUT_HASHES.json', READS)
print(json.dumps(statistics, ensure_ascii=False, indent=2), flush=True)
