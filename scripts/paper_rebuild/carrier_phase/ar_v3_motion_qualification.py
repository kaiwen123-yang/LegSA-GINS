#!/usr/bin/env python3
"""Registered two-epoch mechanism diagnostics; prepare/pin perform zero searches.

The synthetic truth is used by the generator and readout only. Candidate solvers
receive only epoch matrices, integer labels, fixed length and an angle interval.
The finite-domain oracle below is explicitly a ZERO-PHASE-RESIDUAL submodel,
not a global nonlinear-profile oracle for finite-weight CILS.
"""
from __future__ import annotations
import argparse
from dataclasses import asdict, is_dataclass
import csv
import hashlib
import importlib.util
import itertools
import json
import math
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
for _name in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):
    os.environ[_name]='1'
import numpy as np

REPO=Path(__file__).resolve().parents[3]
SCHEMA='ar_v3_motion_qualification.v1'
LENGTH=.35
WAVELENGTH=299792458./1575.42e6
METHODS=('INDEPENDENT_SPHERES','PAIR_MOTION_INTERVAL')
SOURCE_FILES=(
 'src/legsa_gins/paper_rebuild/carrier_phase/temporal.py',
 'src/legsa_gins/paper_rebuild/carrier_phase/solver.py',
 'src/legsa_gins/paper_rebuild/carrier_phase/motion_pair.py',
 'src/legsa_gins/paper_rebuild/carrier_phase/native_sphere.py',
 'src/legsa_gins/paper_rebuild/horizontal_literature/ext01_clambda.py',
 'scripts/paper_rebuild/carrier_phase/ar_v3_classic_qualification.py',
)


def plain(x):
    if is_dataclass(x): return plain(asdict(x))
    if isinstance(x,np.ndarray): return plain(x.tolist())
    if isinstance(x,np.generic): return plain(x.item())
    if isinstance(x,dict): return {str(k):plain(v) for k,v in x.items()}
    if isinstance(x,(tuple,list)): return [plain(v) for v in x]
    if isinstance(x,float) and not math.isfinite(x): return None
    return x


def canonical(x):
    return json.dumps(plain(x),sort_keys=True,separators=(',',':'),allow_nan=False).encode()


def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path,value,*,replace=False):
    with Path(path).open('w' if replace else 'x',encoding='utf-8',newline='\n') as stream:
        json.dump(plain(value),stream,ensure_ascii=False,indent=2,allow_nan=False)
        stream.write('\n')


def rotation(axis,angle):
    u=np.asarray(axis,float);u=u/np.linalg.norm(u)
    x,y,z=u; k=np.array([[0.,-z,y],[z,0.,-x],[-y,x,0.]])
    return np.eye(3)+math.sin(angle)*k+(1-math.cos(angle))*(k@k)


def angle(a,b):
    a=np.asarray(a,float);b=np.asarray(b,float)
    return math.atan2(float(np.linalg.norm(np.cross(a,b))),float(a@b))


def frame(first):
    u=first/np.linalg.norm(first);t=np.eye(3)[int(np.argmin(abs(u)))];t-=u*(u@t);t/=np.linalg.norm(t)
    return np.column_stack((u,t,np.cross(u,t)))


def body_relative(first,second,*,axial_rotation=False):
    # Generator-only R0 aligns body x with the initial baseline. Only the
    # resulting relative angle/error interval is delivered to the solver.
    f=frame(np.asarray(first,float));v=f.T@np.asarray(second,float)/LENGTH
    if axial_rotation: rel=rotation([1.,0.,0.],math.pi/2)
    else:
        axis=np.cross([1.,0.,0.],v)
        rel=np.eye(3) if np.linalg.norm(axis)<1e-14 else rotation(axis,angle([1.,0.,0.],v))
    return f,rel


def dd_range(los,baseline):
    # RX2 - RX1; symmetric endpoints. Difference-of-squares avoids subtracting
    # ~24 Mm ranges. These ranges are synthetic, not actual ephemerides.
    satellites=24_000_000.*np.asarray(los,float)
    b=np.asarray(baseline,float)
    distances1=np.linalg.norm(satellites+b/2,axis=1)
    distances2=np.linalg.norm(satellites-b/2,axis=1)
    single=-2*(satellites@b)/(distances1+distances2)
    return single[:-1]-single[-1]


def make_epoch(los,q,baseline,integer,*,other=None,sd_noise=None):
    los=np.asarray(los,float);m=len(los)-1
    h=los[-1]-los[:-1]
    geom=dd_range(los,baseline)
    if other is not None:
        code=.5*(geom+dd_range(los,other));phase=geom+WAVELENGTH*np.asarray(integer)
        code_noise=code-geom;phase_noise=np.zeros(m)
    else:
        if sd_noise is None:raise ValueError('saved-geometry noise must be registered explicitly')
        nc=np.asarray(sd_noise['code_m'],float);npmetres=np.asarray(sd_noise['phase_m'],float)
        if nc.shape!=(m+1,) or npmetres.shape!=(m+1,):raise ValueError('SD noise dimensions')
        code_noise=nc[:-1]-nc[-1];phase_noise=npmetres[:-1]-npmetres[-1]
        code=geom+code_noise;phase=geom+WAVELENGTH*np.asarray(integer)+phase_noise
    a=np.vstack((np.zeros((m,m)),WAVELENGTH*np.eye(m)))
    b=np.vstack((h,h));y=np.r_[code,phase]
    forward_error=np.max(abs(geom-h@np.asarray(baseline)))
    if forward_error>1e-12: raise ValueError('range/linearization sign or unit mismatch')
    return {'time_s':0.,'y':y,'A':a,'B':b,'Q':q,
            'ambiguity_labels':[f'GPS_L1_SD_TARGET_{i}_MINUS_PIVOT_arc0' for i in range(m)],
            'metadata':{'baseline_frame':'ECEF','synthetic':True}}, {
            'unit_los_error':float(np.max(abs(np.linalg.norm(los,axis=1)-1))),
            'range_linearized_difference_max_m':float(forward_error),
            'code_noise_m':code_noise,'phase_noise_m':phase_noise,'registered_sd_noise':sd_noise}


def build_case(name,los1,los2,q,baselines,integer,*,alias=None,wrong_prior=False,
               epsilon_rad=math.radians(.25),axial_rotation=False,role='',sd_noise=None):
    blocks=[];diags=[]
    for k,los in enumerate((los1,los2)):
        other=None if alias is None else np.asarray(alias['baselines'])[k]
        block,diag=make_epoch(los,q,baselines[k],integer,other=other,
                              sd_noise=None if sd_noise is None else sd_noise[k])
        block['time_s']=k*.2;blocks.append(block);diags.append(diag)
    initial,relative=body_relative(*baselines,axial_rotation=axial_rotation)
    beta=angle([1.,0.,0.],relative@np.array([1.,0.,0.]))
    if wrong_prior:
        supplied_relative=np.eye(3);supplied_beta=0.;epsilon_rad=math.radians(1.)
    else: supplied_relative=relative;supplied_beta=beta
    lo=max(0.,supplied_beta-epsilon_rad);hi=min(math.pi,supplied_beta+epsilon_rad)
    truth={'integer_dd':integer,'baselines_ecef_m':baselines,'initial_R0_generator_only':initial,
           'relative_body_rotation_true':relative,'true_baseline_angle_rad':angle(*baselines),
           'alias':alias}
    return {'case_id':name,'role':role,'epochs':blocks,
            'constraint':{'beta_lower_rad':lo,'beta_upper_rad':hi,'source_id':'SYNTHETIC_RELATIVE_ROTATION_'+name},
            'prior_generation':{'body_baseline_m':[LENGTH,0.,0.],
                                'relative_body_rotation_supplied':supplied_relative,'epsilon_rad':epsilon_rad,
                                'unknown_initial_rotation_to_solver':True,'wrong_prior':wrong_prior},
            'synthetic_truth':truth,'diagnostics':diags}


def generate_cases(classic):
    # Same unit-LOS geometry, same pivot, exact integer reflection alias in the
    # plane-wave DD model: H*(.3 ex)=lambda*(1,1,1,0).
    x=-WAVELENGTH/.3
    targets=[[x,y,math.sqrt(1-x*x-y*y)] for y in (-.5,0.,.5)]
    targets.append([0.,.4,math.sqrt(1-.4**2)])
    los=np.asarray(targets+[[0.,0.,1.]])
    m=4;d=np.column_stack((np.eye(m),-np.ones(m)))
    q=np.zeros((2*m,2*m));q[:m,:m]=d@np.diag(np.full(m+1,.5**2))@d.T
    q[m:,m:]=d@np.diag(np.full(m+1,.003**2))@d.T
    n=np.array([2,-1,1,0]);shift=np.array([.3,0.,0.]);nd=np.array([1,1,1,0])
    s=math.sqrt(LENGTH**2-.15**2)
    def pair(theta): return np.array([[.15,s,0.],[.15,s*math.cos(theta),s*math.sin(theta)]])
    cases=[]
    for name,theta,wrong,axial,eps in (
        ('REFLECTION_60_CORRECT',math.pi/3,False,False,math.radians(.25)),
        ('REFLECTION_60_WRONG_PRIOR',math.pi/3,True,False,math.radians(.25)),
        ('STATIC_CORRECT',0.,False,False,math.radians(.25)),
        ('AXIAL_ROTATION_90_CORRECT',0.,False,True,math.radians(.25)),
        ('NEAR_ZERO_CORRECT',1e-4,False,False,1e-5),
    ):
        bs=pair(theta);alias={'integer_dd':n+nd,'baselines':bs-shift,'translation_m':shift}
        cases.append(build_case(name,los,los,q,bs,n,alias=alias,wrong_prior=wrong,
                      axial_rotation=axial,epsilon_rad=eps,role='UNIT_LOS_REFLECTION_COUNTEREXAMPLE'))
    source=next(x for x in classic['sources'] if x['sequence']=='BY2')
    check=classic['geometry_qualifications']['BY2']
    saved_los=np.asarray(check['los_targets_then_pivot'],float)
    saved_q=np.asarray(source['model']['covariance_m2'],float)
    # One registered realization reused by all three saved-geometry scenarios.
    # Phase variances are already m^2: never multiply the phase noise by lambda.
    standard=np.random.default_rng(20261007).standard_normal((2,2,len(saved_los)))
    sd_noise=[{'code_m':standard[k,0]*np.sqrt(check['sd_variance_code_m2']),
               'phase_m':standard[k,1]*np.sqrt(check['sd_variance_phase_m2'])} for k in range(2)]
    sv=np.array([i['sv_id'] for i in source['model']['satellites']]+[source['model']['pivot']['sv_id']])
    sd=(7*sv+3)%11-5;integer=sd[:-1]-sd[-1]
    b1=LENGTH*np.array([.6,.8,0.]);b2=rotation([.3,-.4,.8],math.radians(20.))@b1
    satrot=rotation([1.,2.,-1.],1e-4)
    moved_los=saved_los@satrot.T
    for name,second,wrong in (
        ('SAVED_BY2_SAME_H_NOISE',saved_los,False),
        ('SAVED_BY2_CHANGED_H_NOISE',moved_los,False),
        ('SAVED_BY2_CHANGED_H_WRONG_PRIOR',moved_los,True),
    ):
        cases.append(build_case(name,saved_los,second,saved_q,np.array([b1,b2]),integer,
                     wrong_prior=wrong,role='SAVED_GEOMETRY_SYNTHETIC_OBSERVATIONS',sd_noise=sd_noise))
    return cases, {'source':source['source'],'source_line_1based':source['source_line_1based'],
                   'source_line_sha256':source['source_line_sha256'],'geometry_sha256':source['geometry_sha256'],
                   'real_observation_y_used':False,'artificial_satellite_direction_change_rad':1e-4,
                   'noise_seed':20261007,'noise_draw_shape':[2,2,len(saved_los)],
                   'noise_draw_axes':['epoch','code_then_phase','targets_then_pivot'],
                   'noise_model':'independent SD Gaussian with saved working variances; not real-noise calibration',
                   'sd_variance_code_m2':check['sd_variance_code_m2'],
                   'sd_variance_phase_m2':check['sd_variance_phase_m2']}


def stack_numeric(case):
    blocks=case['epochs'];m=len(blocks[0]['ambiguity_labels']);counts=[len(b['y']) for b in blocks]
    y=np.concatenate([np.asarray(b['y'],float) for b in blocks]);a=np.vstack([b['A'] for b in blocks])
    b=np.zeros((len(y),6));q=np.zeros((len(y),len(y)));offset=0
    for k,e in enumerate(blocks):
        size=counts[k];b[offset:offset+size,3*k:3*k+3]=e['B'];q[offset:offset+size,offset:offset+size]=e['Q'];offset+=size
    return y,a,b,q,m


def raw_cost(case,n,bs):
    y,a,b,q,_=stack_numeric(case);r=y-a@np.asarray(n)-b@np.asarray(bs).reshape(-1)
    return float(r@np.linalg.solve(q,r))


def preparation_checks(case):
    truth=case['synthetic_truth'];bs=np.asarray(truth['baselines_ecef_m']);n=np.asarray(truth['integer_dd'])
    lo,hi=(case['constraint'][key] for key in ('beta_lower_rad','beta_upper_rad'))
    beta=angle(*bs);inside=lo-1e-12<=beta<=hi+1e-12
    out={'truth_pair_in_interval':bool(inside),'truth_pair_raw_cost':raw_cost(case,n,bs),
         'truth_angle_rad':beta,'relative_prior_error_bound_rad':case['prior_generation']['epsilon_rad']}
    if inside==case['prior_generation']['wrong_prior']:raise ValueError('wrong/correct prior does not have intended exclusion')
    alias=truth['alias']
    if alias is not None:
        bn=np.asarray(alias['baselines']);nn=np.asarray(alias['integer_dd'])
        errors=[]
        for e,b0,bn0 in zip(case['epochs'],bs,bn):
            m=len(n);h=np.asarray(e['B'])[m:]
            errors.append(float(np.max(abs(WAVELENGTH*n+h@b0-WAVELENGTH*nn-h@bn0))))
        out.update(alias_phase_prediction_difference_max_m=max(errors),
                   alias_angle_difference_rad=abs(angle(*bn)-beta),
                   alias_length_error_m=float(np.max(abs(np.linalg.norm(bn,axis=1)-LENGTH))),
                   alias_pair_raw_cost=raw_cost(case,nn,bn),
                   alias_pair_in_interval=bool(lo-1e-12<=angle(*bn)<=hi+1e-12))
        out['alias_point_cost_difference']=abs(out['truth_pair_raw_cost']-out['alias_pair_raw_cost'])
        if max(errors)>1e-12 or out['alias_angle_difference_rad']>1e-12 or out['alias_point_cost_difference']>1e-8:
            raise ValueError('registered reflection identity failed')
    noise_quadratic=[]
    for e,diag in zip(case['epochs'],case['diagnostics']):
        injected=np.r_[diag['code_noise_m'],diag['phase_noise_m']]
        noise_quadratic.append(float(injected@np.linalg.solve(np.asarray(e['Q']),injected)))
        h=np.asarray(e['B'])[:len(n)]
        if np.linalg.matrix_rank(h)!=3:raise ValueError('rank deficient prepared geometry')
        np.linalg.cholesky(np.asarray(e['Q']))
    out.update(known_injected_noise_quadratic_by_epoch=noise_quadratic,
               known_injected_noise_quadratic_total=sum(noise_quadratic),
               working_model_residual_quadratic_at_truth=out['truth_pair_raw_cost'],
               noise_quadratic_dimension=sum(len(e['y']) for e in case['epochs']))
    return out


def prepare(args):
    classic=json.loads(args.classic_plan.read_text());cases,source=generate_cases(classic)
    checks={c['case_id']:preparation_checks(c) for c in cases}
    plan={'schema':SCHEMA,'status':'PREPARED_NO_SEARCH_AWAITING_SOURCE_FREEZE_AND_REGISTRATION',
          'methods':METHODS,'maximum_search_calls':16,'fixed_integer_bound_checks':256,
          'reference_reads':0,'real_observation_y_used':False,'native_navigation_calls':0,'evaluator_calls':0,
          'data_mode':'SYNTHETIC_MECHANISM_WITH_UNIT_LOS_AND_SAVED_REAL_GEOMETRY',
          'classic_plan_sha256':sha(args.classic_plan),'saved_geometry_source':source,
          'settings':{'length_m':LENGTH,'wavelength_m':WAVELENGTH,'initial_candidates':8,'node_limit':100000,
                      'timeout_s':60.,'timeout_enforcement':'internal elapsed checks plus SIGALRM; deferred during C calls, not process-level hard preemption',
                      'sphere_backend':'python','refine_iterations':0,
                      'bound_check_seed':20261006,'bound_pairs_per_case':32},
          'finite_domain_oracle':{'case_id':cases[0]['case_id'],'integer_offsets':[-1,0,1],
               'domain_cardinality':81,'model':'EXACT_ZERO_PHASE_RESIDUAL_SUBMODEL_NOT_FINITE_WEIGHT_CILS',
               'phase_tolerance_m':1e-10,'length_tolerance_m':1e-9,
               'outside_bound':'joint float objective + min coordinate outside-integer distance squared / Qaa_ii'},
          'source_pins':{},'diagnostic_script_sha256':None,'lambda_library_sha256':None,
          'preparation_checks':checks,'cases':cases,
          'go_no_go':{'navigation_expansion_allowed':None,
             'navigation_policy':'conditional on positive R6 evidence then successful R7 local risk qualification',
             'ordering_evidence_required':'new separated generated integer after an old certified wrong winner or unresolved old search, on correctly specified saved-geometry cases',
             'wrong_prior_safety_validated':False,
             'positive_result_action':'continue R7 local risk design/checks, then proceed if qualified',
             'negative_result_action':'current finite mechanism evidence insufficient for expansion; not universal impossibility',
             'not_evidence':['higher ratio alone','smaller candidate set','zero-noise full-rank code recovery','upper-cost ordering without separation']}}
    args.output.parent.mkdir(parents=True,exist_ok=True);write_json(args.output,plan)
    print(json.dumps({'cases':len(cases),'search_calls':0,'prepared':str(args.output)}))


def pin(args):
    plan=json.loads(args.plan.read_text())
    if plan['schema']!=SCHEMA:raise ValueError('schema')
    plan['source_pins']={name:sha(REPO/name) for name in SOURCE_FILES}
    plan['diagnostic_script_sha256']=sha(__file__);plan['lambda_library_sha256']=sha(args.lambda_library)
    plan['status']='PINNED_FOR_REGISTRATION_NO_SEARCH'
    write_json(args.plan,plan,replace=True)
    print(json.dumps({'source_files':len(SOURCE_FILES),'search_calls':0,'plan_sha256':sha(args.plan)}))


def make_problem(case):
    from legsa_gins.paper_rebuild.carrier_phase.temporal import EpochBlock,assemble_epochs
    blocks=[EpochBlock(float(e['time_s']),*[np.array(e[k],float,copy=True) for k in ('y','A','B','Q')],
                       tuple(e['ambiguity_labels']),dict(e['metadata'])) for e in case['epochs']]
    return assemble_epochs(blocks,length_m=LENGTH)


def fixed_domain_oracle(case):
    """No integer solver or sphere optimization: 81 exact phase-equation fits."""
    y,a,b,q,m=stack_numeric(case);truth=case['synthetic_truth'];center=np.asarray(truth['integer_dd'],int)
    accepted=[];lo=case['constraint']['beta_lower_rad'];hi=case['constraint']['beta_upper_rad']
    for offset in itertools.product((-1,0,1),repeat=m):
        n=center+offset;bs=[];phase_error=0.
        for e in case['epochs']:
            h=np.asarray(e['B'])[m:];rhs=np.asarray(e['y'])[m:]-WAVELENGTH*n
            point=np.linalg.lstsq(h,rhs,rcond=None)[0];bs.append(point)
            phase_error=max(phase_error,float(np.max(abs(h@point-rhs))))
        bs=np.array(bs);length_error=float(np.max(abs(np.linalg.norm(bs,axis=1)-LENGTH)))
        if phase_error<=1e-10 and length_error<=1e-9 and lo-1e-12<=angle(*bs)<=hi+1e-12:
            accepted.append({'integer':n,'baselines':bs,'raw_cost':raw_cost(case,n,bs),
                             'phase_error_m':phase_error,'length_error_m':length_error})
    chol=np.linalg.cholesky(q);design=np.linalg.solve(chol,np.column_stack((a,b)));wy=np.linalg.solve(chol,y)
    u,s,vt=np.linalg.svd(design,full_matrices=False)
    if np.min(s)<=np.finfo(float).eps*max(design.shape)*s[0]:raise ValueError('oracle full GLS rank')
    estimate=vt.T@((u.T@wy)/s);cov=(vt.T/(s*s))@vt
    residual=wy-design@estimate;floor=float(residual@residual)
    ahat=estimate[:m];lower=center-1;upper=center+1
    distances=np.minimum(np.maximum(ahat-(lower-1),0.),np.maximum((upper+1)-ahat,0.))
    outside=floor+float(np.min(distances**2/np.diag(cov)[:m]))
    witness=raw_cost(case,truth['integer_dd'],truth['baselines_ecef_m'])
    return {'model_scope':'ZERO_PHASE_RESIDUAL_SUBMODEL_ONLY','domain_lower':lower,'domain_upper':upper,
            'enumerated_integer_points':3**m,'feasible_zero_phase_points':accepted,
            'full_finite_weight_CILS_global_optimum_certified':False,
            'outside_box_full_CILS_lower_bound':outside,'known_feasible_raw_upper':witness,
            'outside_box_excluded_below_witness':bool(outside>witness+1e-8*(1+abs(witness)))}


def bound_checks(plan):
    from legsa_gins.paper_rebuild.carrier_phase.motion_pair import PairMotionConstraint,PairEvaluator
    rng=np.random.default_rng(plan['settings']['bound_check_seed']);records=[]
    for case in plan['cases']:
        problem=make_problem(case);constraint=PairMotionConstraint(**case['constraint'])
        evaluator=PairEvaluator(problem,constraint)
        for j in range(plan['settings']['bound_pairs_per_case']):
            integer=np.asarray(case['synthetic_truth']['integer_dd'])+rng.integers(-1,2,problem.ambiguity_count)
            u=rng.normal(size=3);u/=np.linalg.norm(u);t=rng.normal(size=3);t-=u*(u@t);t/=np.linalg.norm(t)
            beta=float(rng.uniform(constraint.beta_lower_rad,constraint.beta_upper_rad))
            pair=LENGTH*np.array([u,math.cos(beta)*u+math.sin(beta)*t])
            candidate=evaluator(integer,refine_iterations=0)
            raw=raw_cost(case,integer,pair);lower=evaluator.floating.residual_objective+candidate.lower_reduced_cost
            upper=raw_cost(case,integer,candidate.baselines)
            identity=abs(upper-candidate.raw_upper_cost)
            tolerance=2e-6+2e-8*max(1.,abs(raw),abs(upper))
            passed=lower<=raw+tolerance and identity<=tolerance
            records.append({'case_id':case['case_id'],'pair_index':j,'integer':integer,
                            'raw_feasible_cost':raw,'motion_raw_lower':lower,'raw_upper_identity_error':identity,
                            'pass':bool(passed)})
    return {'registered_pairs':256,'evaluated_pairs':len(records),'passed':all(x['pass'] for x in records),
            'scope':'finite falsification checks, not a proof over every integer or baseline','records':records}


class CallTimeout(Exception):pass


def bounded_call(function):
    def expired(_sig,_frame):raise CallTimeout('registered 60-second candidate slot expired')
    previous=signal.signal(signal.SIGALRM,expired);signal.setitimer(signal.ITIMER_REAL,60.)
    try:return function()
    finally:signal.setitimer(signal.ITIMER_REAL,0.);signal.signal(signal.SIGALRM,previous)


def run(args):
    plan=json.loads(args.plan.read_text())
    if (plan['schema']!=SCHEMA or plan['status']!='PINNED_FOR_REGISTRATION_NO_SEARCH'
        or len(plan['cases'])!=8 or plan['methods']!=list(METHODS) or plan['maximum_search_calls']!=16):
        raise ValueError('unregistered or altered plan')
    if sha(__file__)!=plan['diagnostic_script_sha256'] or sha(args.lambda_library)!=plan['lambda_library_sha256']:
        raise ValueError('runner or lambda identity changed')
    if set(plan['source_pins'])!=set(SOURCE_FILES):raise ValueError('missing scientific source pins')
    for name,digest in plan['source_pins'].items():
        if sha(REPO/name)!=digest:raise ValueError('changed scientific source: '+name)
    if len(args.registration_commit)!=40 or any(c not in '0123456789abcdef' for c in args.registration_commit):
        raise ValueError('explicit registration commit required')
    # Bind the actual payload to the registration commit, not merely a hex label.
    committed_plan=subprocess.check_output(['git','show',args.registration_commit+':docs/paper_rebuild/AR_V3_RESEARCH_20261006/MOTION_PAIR_PREREGISTRATION.json'],cwd=REPO)
    committed_runner=subprocess.check_output(['git','show',args.registration_commit+':scripts/paper_rebuild/carrier_phase/ar_v3_motion_qualification.py'],cwd=REPO)
    if committed_plan!=args.plan.read_bytes() or committed_runner!=Path(__file__).read_bytes():
        raise ValueError('plan or runner bytes differ from registration commit')
    for name,digest in plan['source_pins'].items():
        committed_source=subprocess.check_output(['git','show',args.registration_commit+':'+name],cwd=REPO)
        if hashlib.sha256(committed_source).hexdigest()!=digest:raise ValueError('source not pinned in registration commit: '+name)
    args.output.mkdir(parents=True,exist_ok=False);sys.path.insert(0,str(REPO/'src'))
    from legsa_gins.paper_rebuild.carrier_phase.solver import solve_temporal
    from legsa_gins.paper_rebuild.carrier_phase.motion_pair import PairMotionConstraint,solve_motion_pair
    try:
        checks=bound_checks(plan);write_json(args.output/'BOUND_CHECKS.json',checks)
        oracle=fixed_domain_oracle(plan['cases'][0]);write_json(args.output/'FINITE_DOMAIN_ORACLE.json',oracle)
    except Exception as exc:
        write_json(args.output/'COMPLETE.json',{'status':'STOP_PRESEARCH_DIAGNOSTIC_FAILURE','calls':0,
             'failure':type(exc).__name__+': '+str(exc),'registration_commit':args.registration_commit,'no_retry':True})
        raise
    if not checks['passed']:
        write_json(args.output/'COMPLETE.json',{'status':'STOP_BOUND_CHECK_FAILURE','calls':0,'no_retry':True})
        return
    rows=[];details=[]
    settings=plan['settings']
    with (args.output/'CALLS.jsonl').open('x',encoding='utf-8',newline='\n') as ledger:
        for case in plan['cases']:
            truth=case['synthetic_truth'];constraint=PairMotionConstraint(**case['constraint'])
            for method in METHODS:
                problem=make_problem(case);before=tuple(x.tobytes() for x in (problem.y,problem.A,problem.B,problem.Q))
                row={'case_id':case['case_id'],'method':method,'status':'NOT_COMPLETED','failure':None,
                     'global_old_certificate':None,'new_integer_winner_separated':None,'new_integer_top_two_separated':None,
                     'best_is_generated_integer':None,'best_raw_cost':None,'best_pair_angle_rad':None,
                     'truth_pair_in_interval':plan['preparation_checks'][case['case_id']]['truth_pair_in_interval'],
                     'elapsed_s':None,'integer_acceptance_defined':False,'true_real_integer_known':False}
                ordinal=len(rows)+1;ledger.write(json.dumps({'event':'BEGIN','ordinal':ordinal,'case_id':case['case_id'],'method':method})+'\n');ledger.flush();os.fsync(ledger.fileno())
                started=time.monotonic();detail={'case_id':case['case_id'],'method':method}
                try:
                    kw={'initial_candidates':settings['initial_candidates'],'node_limit':settings['node_limit'],
                        'timeout_s':settings['timeout_s'],'sphere_library':None}
                    if method=='INDEPENDENT_SPHERES':
                        result=bounded_call(lambda:solve_temporal(problem,args.lambda_library,**kw))
                        row['global_old_certificate']=bool(result.certificate.global_optimum_certified)
                        row['termination_reason']=result.certificate.termination_reason
                    else:
                        result=bounded_call(lambda:solve_motion_pair(problem,constraint,args.lambda_library,
                                            refine_iterations=settings['refine_iterations'],**kw))
                        row['new_integer_winner_separated']=bool(result.integer_winner_separated)
                        row['new_integer_top_two_separated']=bool(result.integer_top_two_separated)
                        row['termination_reason']=result.termination_reason
                    detail['result']=plain(result)
                    if result.best is None: row['status']='NO_CANDIDATE'
                    else:
                        best=result.best;row['status']='RETURNED_CANDIDATE'
                        row['best_is_generated_integer']=bool(np.array_equal(best.ambiguity,truth['integer_dd']))
                        row['best_raw_cost']=raw_cost(case,best.ambiguity,best.baselines)
                        row['best_pair_angle_rad']=angle(*best.baselines)
                        detail['returned_integer']=plain(best.ambiguity)
                        detail['truth_point_raw_cost']=raw_cost(case,truth['integer_dd'],truth['baselines_ecef_m'])
                except Exception as exc:
                    row['status']='TIMEOUT' if isinstance(exc,CallTimeout) else 'FAILED'
                    row['failure']=type(exc).__name__+': '+str(exc)
                row['elapsed_s']=time.monotonic()-started
                unchanged=before==tuple(x.tobytes() for x in (problem.y,problem.A,problem.B,problem.Q))
                detail['input_arrays_unchanged']=unchanged
                if not unchanged:row['status']='FAILED_INPUT_MUTATION';row['failure']='numeric input mutated'
                rows.append(row);details.append(detail)
                ledger.write(json.dumps({'event':'END','ordinal':ordinal,'row':row},allow_nan=False)+'\n');ledger.flush();os.fsync(ledger.fileno())
                print(json.dumps({'completed':len(rows),'budget':16,'case_id':case['case_id'],'method':method,'status':row['status']}),flush=True)
    columns=list(dict.fromkeys(k for row in rows for k in row))
    with (args.output/'RESULTS.csv').open('x',encoding='utf-8',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=columns,lineterminator='\n');writer.writeheader();writer.writerows(rows)
    write_json(args.output/'DETAILS.json',details)
    improved=[]
    for case in plan['cases']:
        if case['role']!='SAVED_GEOMETRY_SYNTHETIC_OBSERVATIONS' or case['prior_generation']['wrong_prior']:continue
        old,new=[x for x in rows if x['case_id']==case['case_id']]
        new_evidence=(new['new_integer_winner_separated'] is True and new['best_is_generated_integer'] is True)
        old_wrong=(old['global_old_certificate'] is True and old['best_is_generated_integer'] is False)
        old_unresolved=(not old['global_old_certificate'] and old['status'] in ('RETURNED_CANDIDATE','NO_CANDIDATE','TIMEOUT'))
        if new_evidence and (old_wrong or old_unresolved):
            improved.append({'case_id':case['case_id'],'reason':'OLD_CERTIFIED_WRONG_TO_NEW_SEPARATED_GENERATED_INTEGER' if old_wrong
                             else 'OLD_SEARCH_UNRESOLVED_TO_NEW_SEPARATED_GENERATED_INTEGER'})
    write_json(args.output/'COMPLETE.json',{'schema':SCHEMA,'status':'ALL_REGISTERED_SLOTS_TERMINAL','calls':len(rows),
       'registration_commit':args.registration_commit,'plan_sha256':sha(args.plan),'reference_reads':0,
       'native_navigation_calls':0,'evaluator_calls':0,'real_observation_y_used':False,
       'counts':{s:sum(r['status']==s for r in rows) for s in sorted({r['status'] for r in rows})},
       'ordering_evidence_cases':improved,'wrong_prior_safety_validated':False,
       'navigation_expansion_allowed':None if improved else False,
       'navigation_policy':'pending local risk qualification in R7' if improved else 'not supported by this finite experiment',
       'recommendation':'CONTINUE_R7_LOCAL_RISK_DESIGN_AND_CHECKS' if improved else 'FINITE_MECHANISM_EVIDENCE_INSUFFICIENT_FOR_EXPANSION',
       'interpretation':'conditional synthetic mechanism check, not real V3 performance or accepted integers'})


def main():
    parser=argparse.ArgumentParser(description=__doc__);sub=parser.add_subparsers(dest='command',required=True)
    prep=sub.add_parser('prepare');prep.add_argument('--classic-plan',type=Path,required=True);prep.add_argument('--output',type=Path,required=True)
    freeze=sub.add_parser('pin');freeze.add_argument('--plan',type=Path,required=True);freeze.add_argument('--lambda-library',type=Path,required=True)
    execute=sub.add_parser('run');execute.add_argument('--plan',type=Path,required=True);execute.add_argument('--lambda-library',type=Path,required=True)
    execute.add_argument('--registration-commit',required=True);execute.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();{'prepare':prepare,'pin':pin,'run':run}[args.command](args)


if __name__=='__main__':main()
