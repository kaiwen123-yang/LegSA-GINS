from pathlib import Path
import argparse,bisect,csv,hashlib,io,json,math,subprocess,datetime

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def wrap(x):return (x+180.0)%360.0-180.0
def rmse(v):return math.sqrt(math.fsum(x*x for x in v)/len(v)) if v else None
def delta(roll,pitch):
    phi,theta=math.radians(roll),math.radians(pitch)
    x,y=-math.sin(theta)*math.sin(phi),math.cos(phi)
    ratio=x*x+y*y
    return (math.degrees(math.atan2(x,y)) if ratio>1e-12 else None),ratio

def geometry_check():
    checks=[]
    for roll,pitch,yaw in [(0,0,0),(0,25,359),(30,0,90),(30,20,1),(-45,35,275),(89.999,50,185),(-70,-35,359)]:
        phi,theta,psi=map(math.radians,(roll,pitch,yaw))
        # Independently rotate [0,-1,0] by Rx, then Ry, then Rz.
        rx=(0.0,-math.cos(phi),-math.sin(phi))
        ry=(math.cos(theta)*rx[0]+math.sin(theta)*rx[2],rx[1],-math.sin(theta)*rx[0]+math.cos(theta)*rx[2])
        rz=(math.cos(psi)*ry[0]-math.sin(psi)*ry[1],math.sin(psi)*ry[0]+math.cos(psi)*ry[1],ry[2])
        oracle=math.degrees(math.atan2(rz[1],rz[0]))+90.0
        d,ratio=delta(roll,pitch)
        error=abs(wrap(oracle-yaw-d));assert error<1e-10
        checks.append({'roll':roll,'pitch':pitch,'yaw':yaw,'absolute_formula_vector_error_deg':error})
    assert delta(90,0)[0] is None
    return checks

def interp(times,values,q):
    if not times[0]<=q<=times[-1]:return None
    i=bisect.bisect_left(times,q)
    if i<len(times) and times[i]==q:return values[i]
    assert 0<i<len(times)
    return values[i-1]+(values[i]-values[i-1])*(q-times[i-1])/(times[i]-times[i-1])

def resolve(alias_path,aliases):
    for alias,root in sorted(aliases.items(),key=lambda item:-len(item[0])):
        if alias_path==alias or alias_path.startswith(alias+'/'):
            return Path(root+alias_path[len(alias):])
    raise ValueError('Unregistered path alias')

def write_json(path,obj):
    with Path(path).open('x',encoding='utf-8') as f:json.dump(obj,f,indent=2,ensure_ascii=False,allow_nan=False)
def write_csv(path,rows):
    with Path(path).open('x',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator='\n');w.writeheader();w.writerows(rows)

p=argparse.ArgumentParser(__doc__)
p.add_argument('mode',choices=('register','run'))
p.add_argument('--repo',type=Path,required=True)
p.add_argument('--stage',type=Path,required=True)
p.add_argument('--roots',type=Path,required=True)
p.add_argument('--native-seal-review',type=Path)
a=p.parse_args();aliases=load(a.roots)['aliases'];code=Path(__file__)
doc=a.repo/'docs/paper_rebuild/EXT_MEASURAND_20261004';old=a.repo/'docs/paper_rebuild/hext/EXT_REPRODUCTION/v2_fix'
registration=a.stage/'PREREGISTRATION.json'
if a.mode=='register':
    assert not a.stage.exists();a.stage.mkdir(parents=True)
    entries=[]
    for seq in ('BY2','BY2H','BY2O'):
        directory=old/'evaluation_results'/seq;spec=load(directory/'SPEC.json')
        metrics=load(directory/'HEADING_METRICS.json')
        entries.append({'sequence':seq,'spec_path':str(directory/'SPEC.json'),'spec_sha256':sha(directory/'SPEC.json'),'errors_path':str(directory/'ERROR_SERIES.csv'),'errors_sha256':sha(directory/'ERROR_SERIES.csv'),'metrics_path':str(directory/'HEADING_METRICS.json'),'metrics_sha256':sha(directory/'HEADING_METRICS.json'),'trace_alias':spec['trace'],'trace_expected_sha256':spec['trace_sha256'],'old_expected_count':{m:metrics[m]['valid']['count'] for m in ('EXT01','EXT02','EXT03')},'original_denominator':{m:metrics[m]['denominator_native_paired_epochs_in_window'] for m in ('EXT01','EXT02','EXT03')}})
    reg={'schema':'nominal_EXT_projected_quantity_post_result_preregistration.v1','registered_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'science_source_sha256':sha(code),'protocol_sha256':sha(doc/'PROTOCOL.md'),'entries':entries,'geometry_checks':geometry_check(),'new_native_invocations':0,'reference_payload_opens_during_registration':0,'coordinate_contract':'Frozen evaluator RP axes and ENU-to-NED saved yaw; nominal body -y baseline; installation not verified','formula':'delta=atan2(-sin(pitch)*sin(roll),cos(roll)); projected_yaw=stored_reference_yaw_ned+delta','policy':'same original native-valid/reference-supported formal keys; no hold/no re-estimation/no fitting/no deletion; unsupported projection separate','gap_refusal_ratio_squared':1e-12,'Euler_recompute_tolerance_deg':1e-9,'reference_reopens_after_all_required_native_seal_review_only':True}
    write_json(registration,reg);print(json.dumps({'status':'REGISTERED_BEFORE_REFERENCE_READ','registration_sha256':sha(registration),'expected_native_valid_formal_count':sum(sum(e['old_expected_count'].values()) for e in entries)}));raise SystemExit
reg=load(registration);assert sha(code)==reg['science_source_sha256'];assert sha(doc/'PROTOCOL.md')==reg['protocol_sha256']
assert a.native_seal_review is not None
review=load(a.native_seal_review);assert review['all_required_new_FGO_natives_sealed'] is True
assert sha(review['reviewed_native_seal_path'])==review['reviewed_native_seal_sha256']
summary=[];error_rows=[];max_old_error_diff=0.0;max_old_rmse_diff=0.0;opened=[]
for entry in reg['entries']:
    for stem in ('spec','errors','metrics'):assert sha(entry[stem+'_path'])==entry[stem+'_sha256']
    trace=resolve(entry['trace_alias'],aliases)
    with trace.open('rb') as f:payload=f.read()
    observed=hashlib.sha256(payload).hexdigest();assert observed==entry['trace_expected_sha256']
    rows=list(csv.DictReader(io.StringIO(payload.decode('utf-8-sig'))));del payload
    times=[float(r['time']) for r in rows];roll=[float(r['roll']) for r in rows];pitch=[float(r['pitch']) for r in rows]
    assert len(times)>1 and all(math.isfinite(x) for xs in (times,roll,pitch) for x in xs)
    assert all(x<y for x,y in zip(times,times[1:]));del rows
    opened.append({'sequence':entry['sequence'],'trace_alias':entry['trace_alias'],'trace_observed_sha256':observed,'trace_opens':1})
    with Path(entry['errors_path']).open(encoding='utf-8-sig',newline='') as f:old_rows=list(csv.DictReader(f))
    metrics=load(entry['metrics_path'])
    for method in ('EXT01','EXT02','EXT03'):
        selected=[r for r in old_rows if r['method_id']==method]
        assert len(selected)==entry['original_denominator'][method]
        admitted=[r for r in selected if r['valid']=='1' and r['reference_supported']=='1']
        assert len(admitted)==entry['old_expected_count'][method]
        errors_euler=[];errors_projected=[];quantity_deltas=[];min_projection=None;unsupported=0
        for row in admitted:
            q=float(row['time_unix_s']);phi=interp(times,roll,q);theta=interp(times,pitch,q)
            assert phi is not None and theta is not None
            d,ratio=delta(phi,theta);psi=float(row['reference_yaw_ned_deg']);estimate=float(row['native_body_yaw_deg'])
            e=wrap(estimate-psi);difference=abs(wrap(e-float(row['error_valid_deg'])))
            assert difference<=reg['Euler_recompute_tolerance_deg'];max_old_error_diff=max(max_old_error_diff,difference)
            errors_euler.append(e);min_projection=ratio if min_projection is None else min(min_projection,ratio)
            if d is None:unsupported+=1;ep=None
            else:ep=wrap(estimate-(psi+d));errors_projected.append(ep);quantity_deltas.append(d)
            error_rows.append({'sequence':entry['sequence'],'method':method,'time_key_us':row['time_key_us'],'old_error_deg':e,'nominal_projected_error_deg':ep,'nominal_quantity_delta_deg':d,'reference_horizontal_projection_ratio_squared':ratio,'nominal_projection_supported':d is not None})
        old_rmse=rmse(errors_euler);expected=float(metrics[method]['valid']['rmse_deg']);diff=abs(old_rmse-expected);assert diff<=1e-9;max_old_rmse_diff=max(max_old_rmse_diff,diff)
        summary.append({'sequence':entry['sequence'],'method':method,'original_denominator':len(selected),'original_scored_count':len(admitted),'nominal_projected_scored_count':len(errors_projected),'nominal_undefined_count':unsupported,'old_Euler_RMSE_deg':old_rmse,'nominal_projected_RMSE_deg':rmse(errors_projected),'quantity_delta_RMSE_deg':rmse(quantity_deltas),'quantity_delta_max_abs_deg':max(map(abs,quantity_deltas),default=None),'minimum_reference_projection_ratio_squared':min_projection,'interpretation':'conditional nominal geometry/shared-GNSS reference; not surveyed mounting or independent truth'})
    for stem in ('spec','errors','metrics'):assert sha(entry[stem+'_path'])==entry[stem+'_sha256']
write_csv(a.stage/'SUMMARY.csv',summary);write_csv(a.stage/'DERIVED_ERRORS.csv',error_rows)
receipt={'schema':'nominal_EXT_projected_quantity_result.v1','status':'ALL_FIXED_KEYS_AND_OLD_METRICS_REPRODUCED','preregistration_sha256':sha(registration),'source_sha256':sha(code),'native_seal_review_sha256':sha(a.native_seal_review),'reference_reads':opened,'new_native_invocations':0,'old_scored_keys':len(error_rows),'old_error_max_diff_deg':max_old_error_diff,'old_rmse_max_diff_deg':max_old_rmse_diff,'old_files_written':0,'summary_sha256':sha(a.stage/'SUMMARY.csv'),'derived_errors_sha256':sha(a.stage/'DERIVED_ERRORS.csv'),'conclusion_scope':'Nominal -y geometry and frozen RP frame; actual antenna ordering/axis/mount not calibrated; no algorithm rank or universal unsuitability proof'}
write_json(a.stage/'RESULT_RECEIPT.json',receipt);print(json.dumps({'status':receipt['status'],'rows':len(error_rows),'maximum_old_metric_difference_deg':max_old_rmse_diff,'summary':summary}))
