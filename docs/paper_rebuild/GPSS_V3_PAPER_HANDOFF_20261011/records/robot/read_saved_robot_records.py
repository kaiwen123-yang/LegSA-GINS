"""Read saved records only. Does not import or invoke providers/estimators/evaluators."""
from pathlib import Path
import ast, csv, hashlib, io, json, struct, zipfile

OUT = Path(__file__).resolve().parent
REPO = Path(r"\\wsl.localhost\Ubuntu-22.04\home\kaiwen\research\LegSA-GINS-WORKTREES\audit-code-xbpg-20261001")
DOC = REPO / 'docs/paper_rebuild'
STAGE = Path('G:/LegSA-GINS-project/clean_rebuild_202607/stages')
H = STAGE / 'CLEAN4_BY2_HORIZONTAL_LITERATURE_COMPARISON/07_LSE01_HARTLEY_CONTACT_INEKF'
C9 = STAGE / 'CLEAN9_EXTERNAL_COMPARISON'
sources = []
evidence = {}
experiments = []
curves = []

def register(p, depth, purpose, content=None):
    p = Path(p)
    if not p.exists():
        sources.append(dict(path=str(p),read_depth='PATH_CHECK_ONLY',purpose=purpose,exists=False,sha256='',bytes=''))
        return
    b = p.read_bytes() if content is None else content
    sources.append(dict(path=str(p),read_depth=depth,purpose=purpose,exists=True,sha256=hashlib.sha256(b).hexdigest(),bytes=len(b)))
    return b

def j(p, purpose):
    b = register(p, 'FULL_JSON_FIELDS', purpose)
    return json.loads(b.decode('utf-8-sig')) if b else None

def table(p,purpose):
    b = register(p, 'FULL_CSV_ROWS', purpose)
    return list(csv.DictReader(io.StringIO(b.decode('utf-8-sig')))) if b else []

def textfile(p,purpose):
    b = register(p,'FULL_TEXT_READ',purpose)
    return b.decode('utf-8-sig') if b else ''

def series(p,purpose):
    rows=table(p,purpose)
    x=dict(path=str(p),rows=len(rows),columns=list(rows[0]) if rows else [],first=rows[0] if rows else {},last=rows[-1] if rows else {})
    curves.append(x)
    return x

def npz_header(p,purpose):
    b=register(p,'FULL_FILE_HASH_NPY_HEADERS_ONLY',purpose)
    if not b: return None
    answer={}
    with zipfile.ZipFile(io.BytesIO(b)) as z:
        for name in z.namelist():
            with z.open(name) as f:
                f.read(6); ver=tuple(f.read(2))
                n=struct.unpack('<H' if ver==(1,0) else '<I',f.read(2 if ver==(1,0) else 4))[0]
                answer[name]=ast.literal_eval(f.read(n).decode('latin1').strip())
    return answer

for rel in ['AGENTS.md','docs/paper_rebuild/ACTIVE_CONTEXT.md','docs/paper_rebuild/DATA_ROLES.md','docs/paper_rebuild/METHOD_SCOPE.md','docs/paper_rebuild/EXPERIMENT_PROTOCOL.md','docs/paper_rebuild/LEGACY_DENYLIST.md','docs/paper_rebuild/CLAIM_BOUNDARY.md','docs/paper_rebuild/NEXT_ACTIONS.md']:
    textfile(REPO/rel,'entry and historical supersession context; AGENTS completed terminal takes precedence')

for fn in ['LSE01_H5_BY2_NATIVE_REPORT.md','LSE01_H6R_FULL_PRECISION_RECOVERY_REPORT.md','LSE01_FINAL_CLAIM_BOUNDARY.md','LSE01_H6_GAUGE_AND_OBSERVABILITY_REPORT.md']:
    textfile(H/'11_REPORT'/fn,'historical structural verification and later reference-evaluation boundary')
for fn in ['HARTLEY_OBSERVABILITY_CONTRACT.md','HARTLEY_IDEAL_OBSERVABILITY_DERIVATION.md']:
    textfile(H/'01_PAPER_REVIEW'/fn,'analytic gauge derivation and sensor-set scope')

evidence['h5_runs']=[]
for folder in sorted((H/'08_BY2_NATIVE').glob('0[1-4]_*')):
    d=j(folder/'NATIVE_SUMMARY.json','original native state/propagation counts and algorithm identity')
    config=textfile(folder/'NATIVE_CONFIG.cfg','exact H5 frozen noise and initialisation parameters')
    evidence['h5_runs'].append(dict(path=str(folder),summary=d,config=config))
    experiments.append(dict(experiment_id=d['run_id'],family='H5_native',sequence='BY2',status='COMPLETED_NATIVE',version=d.get('code_commit'),parameters=config.replace('\n','; '),result_summary=f"state_rows={d['state_rows']}; Eq61={d['eq61_calls']}; finite/rotation/covariance gates passed",source=str(folder/'NATIVE_SUMMARY.json'),curve_path=str(folder/'NAV.csv'),paper_role='proprioceptive implementation and sensitivity; no reference accuracy in this stage'))
series(H/'08_BY2_NATIVE/01_PRIMARY_GO2_ALLAN_EQ61_FK10MM/NAV.csv','retained 63277-row native state curve schema and support')

groot=H/'09_GAUGE_ENSEMBLE_R1_FULL_PRECISION_CONTACT'
evidence['gauge_rows']=table(groot/'09_EQUIVALENCE/H6R_GAUGE_EQUIVALENCE_SUMMARY.csv','all six transformed initial-yaw runs full-precision residuals')
evidence['gauge_members']=[]
for folder in sorted(groot.glob('0[1-7]_*')):
    member=j(folder/'MEMBER_FREEZE.json','full-precision revision provenance and noncontact parity')
    arrays=npz_header(folder/'CONTACT_STATE_FLOAT64.npz','retained real full-precision contact array shapes; no recalculation')
    evidence['gauge_members'].append(dict(path=str(folder),member=member,npz_arrays=arrays))
for row in evidence['gauge_rows']:
    experiments.append(dict(experiment_id=row['run_id'],family='H6R_gauge',sequence='BY2',status='PASS_GAUGE_EQUIVALENCE',version='dee32bea365e4a3b478a35d4dd198894375c5dab',parameters=f"initial_yaw_deg={row['initial_yaw_deg']}; same recorded proprioceptive inputs",result_summary=f"state_rows={row['state_rows']}; max_position_difference_m={row['position_difference_m_max']}; max_contact_difference_m={row['maximum_matched_contact_position_difference_m_max']}; pass={row['pass']}",source=str(groot/'09_EQUIVALENCE/H6R_GAUGE_EQUIVALENCE_SUMMARY.csv'),curve_path=str(H/'09_GAUGE_ENSEMBLE'/next(k.name for k in groot.glob('0[1-7]_*') if k.name.endswith(row['run_id'].replace('H6R_','')))/'NAV.csv'),paper_role='same observations admit globally rotated states; supports absolute-heading necessity'))
ob=H/'10_OBSERVABILITY_R1'
evidence['windows']=table(ob/'00_WINDOW_REUSE/H6_OBSERVABILITY_WINDOW_SELECTION.csv','input-only fixed window definitions and contact topology')
evidence['rank_rows']=table(ob/'01_IDEAL_BIAS_FREE/OBSERVABILITY_RANK_SENSITIVITY_R1.csv','all 30 rank/nullity rows at 0.1x/1x/10x threshold')
evidence['nullspace']=j(ob/'01_IDEAL_BIAS_FREE/OBSERVABILITY_NULLSPACE_SUMMARY_R1.json','known gauge, finite-window rank, model dimensions')
evidence['singular_rows']=table(ob/'01_IDEAL_BIAS_FREE/OBSERVABILITY_SINGULAR_VALUES_R1.csv','retained singular spectrum for publication replot')
evidence['weak_directions']=table(ob/'02_BIAS_AUGMENTED/BIAS_AUGMENTED_WEAK_DIRECTION_SUMMARY_R1.csv','bias-dominated weak directions distinct from exact gauges')
for row in evidence['rank_rows']:
    experiments.append(dict(experiment_id=f"H6R_{row['model']}_{row['window_id']}_T{row['tolerance_multiplier']}",family='H6R_observability_saved_analysis',sequence='BY2',status='COMPLETED_STRUCTURAL_ANALYSIS',version='H6R full precision',parameters=f"window={row['window_id']}; tolerance_multiplier={row['tolerance_multiplier']}",result_summary=f"rank={row['rank']}; nullity={row['nullity']}; gauge_residual={row['gauge_to_numerical_nullspace_residual']}",source=str(ob/'01_IDEAL_BIAS_FREE/OBSERVABILITY_RANK_SENSITIVITY_R1.csv'),curve_path=str(ob/'01_IDEAL_BIAS_FREE/OBSERVABILITY_SINGULAR_VALUES_R1.csv'),paper_role='analytic and numerical absolute-yaw/global-position gauge confirmation'))

for rel in ['src/legsa_gins/paper_rebuild/horizontal_literature/hartley_h6.py','src/legsa_gins/paper_rebuild/horizontal_literature/hartley_h6r.py','src/legsa_gins/paper_rebuild/hext/hx02_relative_pose_evaluation.py','src/legsa_gins/paper_rebuild/hext/hx02d_reference_free.py','src/legsa_gins/paper_rebuild/hext/hx02e_official_driver.cpp']:
    textfile(REPO/rel,'read source; interpretation concentrates on gauge/measurement/SVD, body velocity formula, alignment, and official-driver inputs; no execution')

evidence['official_contract']=j(REPO/'configs/paper_rebuild/hext/HX02E/CONTRACT.json','official library identity, sequence mapping, evaluation frames')
evidence['hx02_ports']=[]
for run in sorted((C9/'HX02_FIVE_CATEGORY/RUNS').glob('*HARTLEY*')):
    done=j(run/'DONE.json','historical port per-run completion or initialisation failure')
    config=textfile(run/'native/run/NATIVE_CONFIG.cfg','historical port parameter and static-initialisation contract')
    failure=j(run/'FAILURE.json','registered port failure') if (run/'FAILURE.json').exists() else None
    textfile(run/'native/NATIVE_stderr.log','precise native failure or empty-success stderr')
    ev=run/'eval/RELATIVE_POSE/OUTPUT'
    metrics=j(ev/'RELATIVE_POSE_METRICS.json','historical port original relative-pose metrics') if (ev/'RELATIVE_POSE_METRICS.json').exists() else None
    err=next(ev.glob('RELATIVE_POSE_ERROR_SERIES_*.csv'),None) if ev.exists() else None
    if err: series(err,'retained historical port error series; keep separate from official library')
    evidence['hx02_ports'].append(dict(path=str(run),done=done,failure=failure,metrics=metrics,config=config))
    m=metrics or {}
    experiments.append(dict(experiment_id=run.name,family='HX02_historical_port',sequence=run.name.split('__')[0],status=done['status'],version=done['provenance']['code_commit'],parameters=config.replace('\n','; '),result_summary=json.dumps(m if m else failure,ensure_ascii=False),source=str(run/'DONE.json'),curve_path=str(err) if err else '',paper_role='historical adaptation results and initialisation failure; separate from official-library rows'))
evidence['official_configs']={c:textfile(REPO/f'configs/paper_rebuild/hext/HX02E/{c}.cfg','exact OFF-LIT / OFF-DEF noise and initial covariance') for c in ['OFF-LIT','OFF-DEF']}
evidence['official_runs']=[]
for run in sorted((DOC/'hext/HX02E/RUNS').glob('*')):
    d=j(run/'RESULT.json','per-run official native receipt, sanity and relative-pose metrics')
    metrics=j(run/'eval/OUTPUT/RELATIVE_POSE_METRICS.json','original saved evaluator metric fields')
    s=series(run/f"eval/OUTPUT/RELATIVE_POSE_ERROR_SERIES_{d['config']}.csv",'full saved relative-error time series and scored support')
    textfile(run/'native_stdout.log','native terminal stdout')
    archived=C9/'HX02E_HARTLEY_OFFICIAL/RUNS'/run.name/'NAV.csv'
    if archived.exists(): series(archived,'actual retained official native trajectory; first/last row and count')
    else: register(archived,'PATH_CHECK_ONLY','native trajectory archive lookup; missing here is not unexecuted')
    evidence['official_runs'].append(dict(path=str(run),run=d,metrics=metrics,curve=s,native_path=str(archived)))
    m=d['metrics']
    experiments.append(dict(experiment_id=d['run_id'],family='HX02E_official',sequence=d['sequence'],status=d['failure_flag'],version=d['code_commit'],parameters=evidence['official_configs'][d['config']].replace('\n','; '),result_summary=f"H_RMSE_m={m['horizontal_rmse_m']}; yaw_RMSE_deg={m['yaw_rmse_deg']}; position_drift_m_per_100m={m['position_drift_m_per_100m']}; yaw_drift_deg_per_min={m['heading_drift_deg_per_min']}; scored={m['scored_epochs']}",source=str(run/'RESULT.json'),curve_path=s['path'],paper_role='application-level relative-drift evidence after first-10s per-branch alignment'))

evidence['leg_dr']=[]
for seq in ['BY2','BY2H','BY2O']:
    run=DOC/'hext/HX05/LEG_DR'/seq
    d=j(run/'RESULT.json','per-sequence retained LEG-DR integration/evaluation record')
    s=series(run/'eval/OUTPUT/RELATIVE_POSE_ERROR_SERIES_LEG-DR.csv','full saved LEG-DR error curves')
    evidence['leg_dr'].append(dict(sequence=seq,record=d,curve=s))
    m=d['metrics']
    experiments.append(dict(experiment_id='LEG-DR_'+seq,family='HX05_input_reference',sequence=seq,status='COMPLETED_INPUT_DIAGNOSTIC',version=d['code_commit'],parameters='v_body=-mean_contact(omega cross foot_position + foot_speed); onboard rpy rotation; 3D trapezoids; no contact gap interpolation',result_summary=f"H_RMSE_m={m['horizontal_rmse_m']}; yaw_RMSE_deg={m['yaw_rmse_deg']}; position_drift_m_per_100m={m['position_drift_m_per_100m']}; scored={m['scored_epochs']}",source=str(run/'RESULT.json'),curve_path=s['path'],paper_role='conditional kinematic input diagnostic; not independent absolute-heading information'))

evidence['hx02d']={}
for seq in ['BY2','BY2O']:
    base=DOC/'hext/HX02D/EXECUTION_V2'
    evidence['hx02d'][seq]={'B':j(base/f'B_REFERENCE_FREE/{seq}/OUTPUT/B_TABLES.json','saved reference-free input and native diagnostic statistics'),'C':j(base/f'C_REFERENCE/{seq}/OUTPUT/C_TABLES.json','SDK integrals, leg integrals and reference-relative diagnostic results')}
evidence['hx02d']['decomposition']=j(DOC/'hext/HX02D/EXECUTION_V2/B_SAVED_STATE_READOUT/B2_STATE_DECOMPOSITION.json','saved-state gyro-bias/contact yaw decomposition; no filter rerun')
for p in (DOC/'hext/HX02D/EXECUTION_V2/B_SAVED_STATE_READOUT').glob('*1S.csv'):
    series(p,'existing one-second component time histories')
for rel in ['hext/HX02D/JUDGMENT_ZH.md','hext/HX02E/HX02E_RESULTS.md','hext/HX05/HX05_CLOSEOUT.md','hext/HX05_PREREG.md','TIM_EVIDENCE_20261005/sdk_and_metrology/OFFICIAL_INTERFACE_AND_AUTHOR_FACTS.md','TIM_EVIDENCE_20261005/sdk_and_metrology/README.md','TIM_EVIDENCE_20261005/comparisons/COMPARISON_ACCEPTANCE_REPORT.md','JOURNAL_REFRAME_20261004/story/manuscript_restructured_r2.md']:
    textfile(DOC/rel,'historical interpretation, source identity changes and manuscript placement')
evidence['acceptance_matrix']=table(DOC/'TIM_EVIDENCE_20261005/comparisons/METHOD_ACCEPTANCE_MATRIX.csv','locate historical LEG_DR input-summary mismatch against original HX05 formula')

def writecsv(name,rows):
    fields=list(dict.fromkeys(k for row in rows for k in row))
    with (OUT/name).open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)

writecsv('SOURCES_READ.csv',sources)
writecsv('EXPERIMENTS.csv',experiments)
writecsv('CURVE_INVENTORY.csv',[dict(path=x['path'],rows=x['rows'],columns=';'.join(x['columns']),first_json=json.dumps(x['first'],ensure_ascii=False),last_json=json.dumps(x['last'],ensure_ascii=False)) for x in curves])
(OUT/'READOUT.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'source_files':len(sources),'experiment_records':len(experiments),'curve_files':len(curves),'new_solver_calls':0,'new_evaluator_calls':0,'new_provider_calls':0},ensure_ascii=False))
