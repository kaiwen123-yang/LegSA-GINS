#!/usr/bin/env python3
"""Bounded, synthetic-observation qualification on saved GPS L1 geometry.

prepare reads input-model fields only; it never imports/calls a candidate solver.
run executes at most 12 registered candidate calls, with no truth given to either
solver, no real observation y, no reference, and no navigation/evaluator call.
"""
from __future__ import annotations

import argparse
import csv
from dataclasses import asdict, is_dataclass
import gzip
import hashlib
import json
import math
import os
from pathlib import Path
import sys
import time

for _key in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ[_key] = '1'
import numpy as np

REPO = Path(__file__).resolve().parents[3]
SEQUENCES = ('BY2', 'BY2H', 'BY2O')
WAVELENGTH = 299792458.0 / 1575.42e6
LENGTH = .350
SCHEMA = 'ar_v3_classic_qualification.v1'
SOURCES = (
    'src/legsa_gins/paper_rebuild/horizontal_literature/ext01_clambda.py',
    'src/legsa_gins/paper_rebuild/horizontal_literature/ext02_cwls.py',
    'src/legsa_gins/paper_rebuild/horizontal_literature/reproduction_ext02.py',
)
GEOMETRY_KEYS = ('pivot', 'satellites', 'ambiguity_design_m', 'baseline_design',
                 'covariance_m2', 'receiver_order', 'dd_sign_convention', 'phase_convention')
SCENARIOS = (
    {'id': 'DIRECTION_A_NOISELESS', 'direction_ecef': [.6, .8, 0.], 'bounded_noise': False},
    {'id': 'DIRECTION_B_BOUNDED_SD_NOISE', 'direction_ecef': [-.36, .48, .8], 'bounded_noise': True},
)


def plain(x):
    if is_dataclass(x): return plain(asdict(x))
    if isinstance(x, np.ndarray): return plain(x.tolist())
    if isinstance(x, np.generic): return plain(x.item())
    if isinstance(x, dict): return {str(k): plain(v) for k, v in x.items()}
    if isinstance(x, (tuple, list)): return [plain(v) for v in x]
    if isinstance(x, float) and not math.isfinite(x): return None
    return x


def digest_file(p):
    h = hashlib.sha256()
    with Path(p).open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''): h.update(chunk)
    return h.hexdigest()


def canonical(x):
    return json.dumps(plain(x), sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def write_json(path, value):
    with Path(path).open('x', encoding='utf-8', newline='\n') as f:
        json.dump(plain(value), f, ensure_ascii=False, indent=2, allow_nan=False)
        f.write('\n')


def evidence_relative(sequence):
    return f'runs/{sequence}__EXT01__RAW_REPRO_V2__TECH_RETRY_2/EPOCH_EVIDENCE.jsonl.gz'


def first_saved_model(root, sequence):
    """Do not use saved valid/status/solver/yaw/ambiguities to choose the row."""
    relative = evidence_relative(sequence)
    with gzip.open(Path(root) / relative, 'rt', encoding='utf-8') as f:
        for line_number, line in enumerate(f, 1):
            entry = json.loads(line)
            if not isinstance(entry.get('model'), dict): continue
            model = {k: entry['model'][k] for k in GEOMETRY_KEYS}
            return {
                'sequence': sequence, 'source': '<EXT_REPRO_V2_RETRY_ROOT>/' + relative,
                'source_line_1based': line_number,
                'source_line_sha256': hashlib.sha256(line.encode()).hexdigest(),
                'epoch_index': entry['epoch_index'], 'gps_week': entry['gps_week'],
                'gps_tow_seconds': entry['gps_tow_seconds'],
                'geometry_sha256': hashlib.sha256(canonical(model)).hexdigest(),
                'model': model,
            }
    raise ValueError(f'{sequence}: no saved input model; no substitution permitted')


def identity(i):
    return tuple(i[k] for k in ('gnss_id', 'sv_id', 'sig_id', 'freq_id'))


def geometry_qualification(model):
    """Analytical checks only; reconstruct common-pivot SD variance and LOS."""
    m = len(model['satellites'])
    a = np.asarray(model['ambiguity_design_m'], float)
    b = np.asarray(model['baseline_design'], float)
    q = np.asarray(model['covariance_m2'], float)
    ids = [identity(i) for i in model['satellites']] + [identity(model['pivot'])]
    if len(set(ids)) != len(ids) or any((i[0], i[2], i[3]) != (0, 0, 0) for i in ids):
        raise ValueError('expected unique GPS L1 C/A identities')
    if m < 3 or a.shape != (2*m, m) or b.shape != (2*m, 3) or q.shape != (2*m, 2*m):
        raise ValueError('saved model shape mismatch')
    if not all(np.isfinite(x).all() for x in (a, b, q)):
        raise ValueError('nonfinite saved model')
    if model['receiver_order'] != 'GNSS2_MINUS_GNSS1': raise ValueError('receiver order')
    if model['dd_sign_convention'] != '(GNSS2-GNSS1)_SATELLITE_MINUS_PIVOT':
        raise ValueError('DD sign convention')
    if model['phase_convention'] != 'CPMES_AS_REPORTED_NO_SECOND_HALF_CYCLE_SHIFT':
        raise ValueError('phase convention')
    if not np.allclose(a, np.vstack((np.zeros((m,m)), WAVELENGTH*np.eye(m))), rtol=0, atol=1e-15):
        raise ValueError('ambiguity wavelength or row order mismatch')
    h = b[:m]
    if not np.array_equal(h, b[m:]): raise ValueError('code and phase geometry differ')
    singular = np.linalg.svd(h, compute_uv=False)
    rank = int(np.linalg.matrix_rank(h))
    if rank != 3: raise ValueError('code geometry rank deficient; uniqueness cannot be asserted')
    np.linalg.cholesky(q)
    if not np.allclose(q, q.T, rtol=0, atol=1e-14): raise ValueError('asymmetric Q')
    if np.any(q[:m,m:] != 0): raise ValueError('saved covariance is not expected code/phase block form')
    d = np.column_stack((np.eye(m), -np.ones(m)))
    sd_variances = []
    for block in (q[:m,:m], q[m:,m:]):
        pivot_variance = float(block[0,1])
        v = np.r_[np.diag(block)-pivot_variance, pivot_variance]
        if np.any(v <= 0) or not np.allclose(d @ np.diag(v) @ d.T, block, rtol=1e-12, atol=1e-18):
            raise ValueError('shared-pivot covariance reconstruction mismatch')
        sd_variances.append(v)
    # H_s = u_p - u_s, with all u unit length. Thus 2 H_s.u_p = |H_s|^2.
    pivot_los = np.linalg.lstsq(h, .5*np.sum(h*h, axis=1), rcond=None)[0]
    los = np.vstack((pivot_los-h, pivot_los))
    unit_error = float(np.max(abs(np.linalg.norm(los, axis=1)-1)))
    if unit_error > 1e-8: raise ValueError('saved DD rows not compatible with reconstructed unit LOS')
    return {'dd_count': m, 'code_rank': rank, 'code_singular_values': singular,
            'los_unit_error': unit_error, 'los_targets_then_pivot': los,
            'sd_variance_code_m2': sd_variances[0], 'sd_variance_phase_m2': sd_variances[1],
            'covariance_offdiagonal_nonzero': int(np.count_nonzero(q-np.diag(np.diag(q)))),
            'zero_noise_uniqueness': 'rank(H_code)=3 => unique b from code; lambda != 0 => unique N'}


def make_case(saved, scenario):
    model = saved['model']; check = geometry_qualification(model)
    h = np.asarray(model['baseline_design'], float)[:check['dd_count']]
    los = np.asarray(check['los_targets_then_pivot'])
    direction = np.asarray(scenario['direction_ecef'], float)
    if abs(np.linalg.norm(direction)-1) > 1e-14: raise ValueError('direction not unit')
    baseline = LENGTH * direction
    sv = np.array([i['sv_id'] for i in model['satellites']] + [model['pivot']['sv_id']])
    sd_integer = (7*sv+3) % 11 - 5
    # Independent physical range differences. RX1=-b/2, RX2=+b/2; equal
    # transmitter radius is a synthetic choice, not a reconstruction of orbit.
    satellites = 24_000_000.0 * los
    ranges1 = np.linalg.norm(satellites + baseline/2, axis=1)
    ranges2 = np.linalg.norm(satellites - baseline/2, axis=1)
    sd_range = -2*(satellites @ baseline)/(ranges1+ranges2)
    nc = 1e-3 * ((sv % 5)-2)/2 if scenario['bounded_noise'] else np.zeros(len(sv))
    npcy = 2e-4 * ((sv % 7)-3)/3 if scenario['bounded_noise'] else np.zeros(len(sv))
    # Large receiver-common terms deliberately cancel in satellite DD.
    sd_code = sd_range + 123.0 + nc
    sd_phase = sd_range/WAVELENGTH + sd_integer + 7.25 + npcy
    code = sd_code[:-1]-sd_code[-1]
    phase_m = WAVELENGTH*(sd_phase[:-1]-sd_phase[-1])
    y = np.r_[code, phase_m]
    truth_n = sd_integer[:-1]-sd_integer[-1]
    a = np.asarray(model['ambiguity_design_m'],float)
    b = np.asarray(model['baseline_design'],float)
    expected_noise = np.r_[nc[:-1]-nc[-1], WAVELENGTH*(npcy[:-1]-npcy[-1])]
    forward_error = float(np.max(abs(y-(a@truth_n+b@baseline+expected_noise))))
    if forward_error > 1e-11: raise ValueError('independent physical forward sign/unit mismatch')
    return {'case_id': saved['sequence']+'__'+scenario['id'], 'sequence':saved['sequence'],
            'scenario':scenario, 'input':{'y':y,'A':a,'B':b,'Q':model['covariance_m2'],'length_m':LENGTH},
            'synthetic_truth':{'integer_dd':truth_n,'baseline_ecef_m':baseline},
            'diagnostic':{'forward_model_max_error_m':forward_error,
                          'max_abs_code_dd_noise_m':float(np.max(abs(expected_noise[:len(truth_n)]))),
                          'max_abs_phase_dd_noise_cycles':float(np.max(abs(expected_noise[len(truth_n):]/WAVELENGTH))),
                          'noiseless_unique_joint_optimum':not scenario['bounded_noise']},
            'geometry_sha256':saved['geometry_sha256']}


def prepare(args):
    saved = [first_saved_model(args.evidence_root, s) for s in SEQUENCES]
    qualifications = {s['sequence']:geometry_qualification(s['model']) for s in saved}
    plan = {'schema':SCHEMA, 'status':'REGISTER_BEFORE_ANY_SEARCH',
            'data_mode':'SYNTHETIC_OBSERVATIONS_CONDITIONED_ON_SAVED_REAL_GEOMETRY',
            'synthetic_data_used':True, 'semisynthetic_geometry_used':True,
            'reference_used':False, 'real_observation_y_used':False,
            'methods':['EXT01_CURRENT_STRICT_CILS','EXT02_REPRODUCTION_CWLS'],
            'maximum_candidate_calls':12, 'native_navigation_calls':0, 'evaluator_calls':0,
            'settings':{'length_m':LENGTH,'lambda_seed_count':8,'strict_node_limit':100000,
                        'ext01_timeout_seconds':30.0,'cwls_call_timeout_seconds':30.0},
            'lambda_library':{'alias':'<EXT_REPRO_BUILD>/lib/librtklib_legsa.so',
                              'sha256':digest_file(args.lambda_library)},
            'source_pins':{s:digest_file(REPO/s) for s in SOURCES},
            'diagnostic_script_sha256':digest_file(__file__),
            'selection_policy':'first saved input-model record, no solver/status/error selection; full history, not evaluation-window performance',
            'sources':saved,'geometry_qualifications':qualifications,
            'cases':[make_case(s,c) for s in saved for c in SCENARIOS],
            'not_claims':['real-data accuracy','true real ambiguities','CWLS global certificate',
                          'noise-only ablation','historical V2 source-equivalent rerun','Gaussian calibration']}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    write_json(args.output,plan)
    print(json.dumps({'plan':str(args.output),'cases':len(plan['cases']),
                      'search_calls':0,'dd_counts':{s:q['dd_count'] for s,q in qualifications.items()}}))


def metric_cost(y,a,b,q,n,baseline):
    r = y-a@np.asarray(n)-b@np.asarray(baseline)
    return float(r @ np.linalg.solve(q,r))


def independent_wrapped(y,b,q,baseline):
    m=len(y)//2
    phase_cycles=(y[m:]-b[m:]@baseline)/WAVELENGTH
    integer=np.array([math.ceil(float(v)-.5) for v in phase_cycles],dtype=np.int64)
    r=np.r_[y[:m]-b[:m]@baseline, WAVELENGTH*(phase_cycles-integer)]
    return float(r @ np.linalg.solve(q,r)), integer


def invariant_checks(case, cm):
    """Objective algebra only. No candidate generator or optimization calls."""
    x=case['input']; y,a,b,q=(np.asarray(x[k],float) for k in ('y','A','B','Q'))
    m=a.shape[1]; n=np.asarray(case['synthetic_truth']['integer_dd'],int)
    base=np.asarray(case['synthetic_truth']['baseline_ecef_m'],float)
    perm=np.r_[np.arange(m,2*m),np.arange(m)]
    errors={'adapter_y':float(max(np.max(abs(cm.phase_cycles-y[m:]/WAVELENGTH)),
                                 np.max(abs(cm.code_cycles-y[:m]/WAVELENGTH)))),
            'adapter_B':float(np.max(abs(cm.design_cycles_per_m-b[:m]/WAVELENGTH))),
            'adapter_full_Q':float(np.max(abs(cm.covariance_phase_code_cycles2-q[np.ix_(perm,perm)]/WAVELENGTH**2)))}
    # Test at an off-truth parameter too; invariance is not just the zero residual.
    probe_b=base+np.array([.01,-.02,.015]); probe_n=n.copy(); probe_n[0]+=1
    j=metric_cost(y,a,b,q,probe_n,probe_b)
    reverse=metric_cost(-y,a,b,q,-probe_n,-probe_b)
    # New pivot = old first target; rows are old targets 1..m-1, then old pivot.
    t=np.vstack((np.eye(m)[1:]-np.eye(m)[0],-np.eye(m)[0]))
    t2=np.block([[t,np.zeros((m,m))],[np.zeros((m,m)),t]])
    ar=np.vstack((np.zeros((m,m)),WAVELENGTH*np.eye(m)))
    repivot=metric_cost(t2@y,ar,t2@b,t2@q@t2.T,t@probe_n,probe_b)
    rc=np.r_[(y[m:]-b[m:]@probe_b)/WAVELENGTH-probe_n,(y[:m]-b[:m]@probe_b)/WAVELENGTH]
    cycle_cost=float(rc@np.linalg.solve(q[np.ix_(perm,perm)]/WAVELENGTH**2,rc))
    errors.update(receiver_reversal_cost_error=abs(reverse-j),repivot_cost_error=abs(repivot-j),
                  metric_cycles_cost_error=abs(cycle_cost-j),probe_cost=j)
    if max(errors[k] for k in ('adapter_y','adapter_B','adapter_full_Q'))>1e-10:
        raise ValueError('metric-to-cycle adapter mismatch')
    if max(errors[k] for k in ('receiver_reversal_cost_error','repivot_cost_error','metric_cycles_cost_error'))>1e-8*max(1,j):
        raise ValueError('full-Q/sign/pivot objective invariance failure')
    return errors


class CallTimeout(Exception): pass


def bounded_call(function, seconds):
    """Linux SIGALRM bounds the wrapper, never fabricates a solver certificate."""
    import signal
    def expired(_sig,_frame): raise CallTimeout('registered candidate-call timeout')
    previous=signal.signal(signal.SIGALRM,expired)
    signal.setitimer(signal.ITIMER_REAL,seconds)
    try: return function()
    finally:
        signal.setitimer(signal.ITIMER_REAL,0)
        signal.signal(signal.SIGALRM,previous)


def run(args):
    plan=json.loads(args.plan.read_text())
    if plan['schema']!=SCHEMA or len(plan['cases'])*2!=12: raise ValueError('plan schema/budget')
    if plan['methods']!=['EXT01_CURRENT_STRICT_CILS','EXT02_REPRODUCTION_CWLS'] or plan['maximum_candidate_calls']!=12:
        raise ValueError('registered method order/call ceiling changed')
    if digest_file(__file__)!=plan['diagnostic_script_sha256']: raise ValueError('script changed after plan')
    if digest_file(args.lambda_library)!=plan['lambda_library']['sha256']: raise ValueError('lambda identity')
    for f,digest in plan['source_pins'].items():
        if digest_file(REPO/f)!=digest: raise ValueError('source changed: '+f)
    for saved in plan['sources']:
        actual=first_saved_model(args.evidence_root,saved['sequence'])
        if canonical(actual)!=canonical(saved): raise ValueError('saved model/source line changed')
    # Reconstruct observations from geometry only and match the registered cases.
    expected=[make_case(s,c) for s in plan['sources'] for c in SCENARIOS]
    if canonical(expected)!=canonical(plan['cases']): raise ValueError('case generator/plan mismatch')
    args.output.mkdir(parents=True,exist_ok=False)
    sys.path.insert(0,str(REPO/'src'))
    from legsa_gins.paper_rebuild.horizontal_literature import ext01_clambda as cl
    from legsa_gins.paper_rebuild.horizontal_literature import reproduction_ext02 as cw
    settings=plan['settings']; rows=[]; details=[]
    ledger=args.output/'CALLS.jsonl'
    with ledger.open('x',encoding='utf-8',newline='\n') as log:
        for case in plan['cases']:
            x=case['input']; y,a,b,q=(np.asarray(x[k],float) for k in ('y','A','B','Q'))
            m=a.shape[1]; truth=case['synthetic_truth']
            cm=cw.adapt_metric_double_differences(code_m=y[:m],phase_m=y[m:],design_m_per_m=b,
                covariance_code_phase_m2=q,wavelength_m=WAVELENGTH,baseline_length_m=LENGTH)
            checks=invariant_checks(case,cm)
            chol=np.linalg.cholesky(q); design=np.column_stack((a,b))
            mw=np.linalg.solve(chol,design); yw=np.linalg.solve(chol,y)
            ls=np.linalg.lstsq(mw,yw,rcond=None)[0]
            float_residual=float(np.linalg.norm(yw-mw@ls)**2)
            true_cost=metric_cost(y,a,b,q,truth['integer_dd'],truth['baseline_ecef_m'])
            for method in plan['methods']:
                row={'case_id':case['case_id'],'sequence':case['sequence'],'method':method,
                     'synthetic':True,'status':'NOT_COMPLETED','failure_code':None,
                     'integer_recovered':None,'baseline_error_m':None,'angle_error_deg':None,
                     'reported_objective':None,'independent_raw_cost':None,'objective_identity_error':None,
                     'truth_point_cost':true_cost,'candidate_minus_truth_point_cost':None,
                     'global_optimum_certified':None,'ambiguity_accepted':None,
                     'true_real_integer_known':False,'duration_s':None}
                log.write(json.dumps({'event':'BEGIN','ordinal':len(rows)+1,'case_id':case['case_id'],'method':method})+'\n');log.flush();os.fsync(log.fileno())
                started=time.monotonic(); detail={'case_id':case['case_id'],'method':method,'invariants':checks}
                input_before=tuple(v.tobytes() for v in (y,a,b,q))
                try:
                    if method.startswith('EXT01'):
                        result=bounded_call(lambda:cl.solve_clambda(y,a,b,q,length_m=LENGTH,
                            lambda_bridge_path=args.lambda_library,strict=True,
                            initial_candidate_count=settings['lambda_seed_count'],
                            strict_node_limit=settings['strict_node_limit'],
                            timeout_seconds=settings['ext01_timeout_seconds']),settings['ext01_timeout_seconds']+2)
                        detail['result']=plain(result)
                        row['global_optimum_certified']=bool(result.global_optimum_certified)
                        if result.best is None:
                            row['failure_code']=result.failure_code or result.termination_reason
                            row['status']='NO_RETURNED_CANDIDATE'
                        else:
                            n=np.asarray(result.best.ambiguity); baseline=np.asarray(result.best.baseline)
                            row['reported_objective']=float(result.best.objective)
                            raw_cost=metric_cost(y,a,b,q,n,baseline)
                            row['objective_identity_error']=abs(raw_cost-float_residual-result.best.objective)
                    else:
                        result=bounded_call(lambda:cw.solve_cwls(cm),settings['cwls_call_timeout_seconds'])
                        # No global certificate is defined by this candidate-pool method.
                        detail['result']=plain(result)
                        n=np.asarray(result.integer_ambiguities);baseline=np.asarray(result.baseline_vector_m)
                        row['reported_objective']=float(result.objective)
                        raw_cost=metric_cost(y,a,b,q,n,baseline)
                        wrapped,wrapped_n=independent_wrapped(y,b,q,baseline)
                        row['objective_identity_error']=abs(wrapped-result.objective)
                        detail['wrapped_integer_agreement']=bool(np.array_equal(wrapped_n,n))
                    if row['status']!='NO_RETURNED_CANDIDATE':
                        row['status']='CANDIDATE_RETURNED'
                        row['integer_recovered']=bool(np.array_equal(n,truth['integer_dd']))
                        row['baseline_error_m']=float(np.linalg.norm(baseline-truth['baseline_ecef_m']))
                        cross=np.linalg.norm(np.cross(baseline,truth['baseline_ecef_m']))
                        dot=float(baseline@np.asarray(truth['baseline_ecef_m']))
                        row['angle_error_deg']=math.degrees(math.atan2(float(cross),dot))
                        row['independent_raw_cost']=raw_cost
                        row['candidate_minus_truth_point_cost']=raw_cost-true_cost
                        row['length_error_m']=abs(float(np.linalg.norm(baseline))-LENGTH)
                        row['noiseless_zero_lower_bound_attained']=bool(not case['scenario']['bounded_noise'] and raw_cost<1e-8)
                        detail['returned_integer']=n.tolist();detail['returned_baseline']=baseline.tolist()
                except Exception as exc:
                    row['status']='CALL_FAILED';row['failure_code']=getattr(exc,'code',type(exc).__name__)
                    detail['exception']=str(exc)
                    for name in ('candidate_diagnostics','candidate_pool'):
                        if hasattr(exc,name): detail[name]=plain(getattr(exc,name))
                detail['input_arrays_unchanged']=input_before==tuple(v.tobytes() for v in (y,a,b,q))
                if not detail['input_arrays_unchanged']:
                    row['status']='INPUT_MUTATION_DETECTED';row['failure_code']='INPUT_MUTATION'
                row['duration_s']=time.monotonic()-started
                rows.append(row);details.append(detail)
                log.write(json.dumps(plain({'event':'END','ordinal':len(rows),'row':row}),allow_nan=False)+'\n');log.flush();os.fsync(log.fileno())
    columns=list(dict.fromkeys(k for row in rows for k in row))
    with (args.output/'RESULTS.csv').open('x',encoding='utf-8',newline='') as f:
        writer=csv.DictWriter(f,columns,lineterminator='\n');writer.writeheader();writer.writerows(rows)
    write_json(args.output/'DETAILS.json',details)
    write_json(args.output/'COMPLETE.json',{'schema':SCHEMA,'status':'ALL_REGISTERED_CALLS_TERMINAL',
        'calls':len(rows),'plan_sha256':digest_file(args.plan),'data_mode':plan['data_mode'],
        'reference_reads':0,'real_observation_y_used':False,'native_navigation_calls':0,'evaluator_calls':0,
        'counts':{s:sum(r['status']==s for r in rows) for s in sorted({r['status'] for r in rows})},
        'interpretation':'synthetic kernel/adapter diagnostic only; not real performance or general CWLS certificate'})
    print(json.dumps({'output':str(args.output),'calls':len(rows)}))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='command',required=True)
    for name in ('prepare','run'):
        p=sub.add_parser(name);p.add_argument('--evidence-root',type=Path,required=True)
        p.add_argument('--lambda-library',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
        if name=='run': p.add_argument('--plan',type=Path,required=True)
    args=parser.parse_args()
    (prepare if args.command=='prepare' else run)(args)


if __name__=='__main__': main()
