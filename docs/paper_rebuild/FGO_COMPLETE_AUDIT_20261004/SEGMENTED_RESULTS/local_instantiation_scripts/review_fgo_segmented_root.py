from pathlib import Path
import argparse,csv,json,hashlib,math,statistics
P=argparse.ArgumentParser();P.add_argument('--stage',type=Path,required=True);P.add_argument('--roots',type=Path,required=True);P.add_argument('--out',type=Path,required=True);A=P.parse_args()
roots=json.loads(A.roots.read_text())['aliases'];stage=A.stage

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def rows(p):return list(csv.DictReader(p.open()))
def resolve(s):
 for a,r in sorted(roots.items(),key=lambda x:-len(x[0])):
  if s==a or s.startswith(a+'/'):return Path(r+s[len(a):])
 raise ValueError(s)
def vector(r,keys):return tuple(float(r[k]) for k in keys)
def dot(x,y):return math.fsum(a*b for a,b in zip(x,y))
def basis(lat,lon):
 p,l=math.radians(lat),math.radians(lon);sp,cp,sl,cl=math.sin(p),math.cos(p),math.sin(l),math.cos(l)
 return (-sp*cl,-sp*sl,cp),(-sl,cl,0),(-cp*cl,-cp*sl,-sp)
def independent_imu_point(row,lever):
 xyz=vector(row,('x_ecef_m','y_ecef_m','z_ecef_m'));x,y,z=xyz;r=math.hypot(x,y);lon=math.atan2(y,x);lat=math.atan2(z,r*(1-6.6943799901413165e-3))
 for _ in range(15):
  n=6378137/math.sqrt(1-6.6943799901413165e-3*math.sin(lat)**2);lat=math.atan2(z+6.6943799901413165e-3*n*math.sin(lat),r)
 phi,theta,psi=map(math.radians,vector(row,('roll_deg','pitch_deg','yaw_deg')))
 a,b,c=lever;rx=(a,math.cos(phi)*b-math.sin(phi)*c,math.sin(phi)*b+math.cos(phi)*c)
 ry=(math.cos(theta)*rx[0]+math.sin(theta)*rx[2],rx[1],-math.sin(theta)*rx[0]+math.cos(theta)*rx[2])
 ned=(math.cos(psi)*ry[0]-math.sin(psi)*ry[1],math.sin(psi)*ry[0]+math.cos(psi)*ry[1],ry[2])
 bb=basis(math.degrees(lat),math.degrees(lon));return tuple(xyz[j]+math.fsum(ned[k]*bb[k][j] for k in range(3)) for j in range(3))
def quantile(v,q):
 s=sorted(v);p=(len(s)-1)*q;i=int(p);return s[i]+(s[min(i+1,len(s)-1)]-s[i])*(p-i)
def stats(v):
 if not v:return {k:None for k in ('rmse','p50','p95','max')}
 a=[abs(x) for x in v];return {'rmse':math.sqrt(math.fsum(x*x for x in v)/len(v)),'p50':quantile(a,.5),'p95':quantile(a,.95),'max':max(a)}
protocol=json.loads((stage/'PREREGISTRATION.json').read_text());seal=json.loads((stage/'ALL_NATIVE_SEALED.json').read_text());assert seal['new_native_count']==3 and seal['new_native_reference_opens']==seal['reused_original_native_reference_opens']==0
assert sha(stage/'PREREGISTRATION.json')==seal['protocol_sha256'];assert seal['new_evaluator_count_at_seal']==0
geometry_max=0.;point_max=0.;metric_max=0.;common_time_max=0.;metric_count=geometry_count=point_count=0;eval_pins={};support_checks=[]
for seq in ('BY2','BY2H','BY2O'):
 d=stage/'evaluation'/seq;e=json.loads((d/'EVALUATION.json').read_text());assert e['reference_read_count']==1 and e['output_interpolation'] is False and e['physical_point']=='GNSS1_ANTENNA';assert e['native_seal_sha256']==sha(stage/'ALL_NATIVE_SEALED.json')
 eval_pins[seq]={'evaluation_json_sha256':sha(d/'EVALUATION.json'),'metrics_csv_sha256':sha(d/'METRICS.csv')};bb=basis(*e['anchor_llh_deg_m'][:2]);native={}
 for method,binding in e['native_bindings'].items():
  p=resolve(binding['path']);assert sha(p/'RUN.json')==binding['run_json_sha256'];rr=json.loads((p/'RUN.json').read_text())
  for n,h in rr['output_hashes'].items():assert sha(p/n)==h
  native[method]={float(r['time_rel_s']):r for r in rows(p/'STATES.csv')}
 for role in ('PRIMARY_DYNAMIC_ONLY','SECONDARY_ALL_VALID_POSITION'):
  tables={};lookups={}
  for method in ('OISAM','WEN_TC','GNC'):
   er=rows(d/(method+'_'+role+'_ERRORS.csv'));tr=rows(d/(method+'_'+role+'_TRAJECTORY.csv'));assert len(er)==len(tr);tables[method]=er;lookups[method]={}
   for x,y in zip(er,tr):
    t=float(x['time']);assert t==float(y['time']);s=native[method][t];v=int(x['valid'])==1;assert v==(int(y['valid'])==1)
    nvalid=float(s['valid'])>0 and all(math.isfinite(float(s[k])) for k in ('x_ecef_m','y_ecef_m','z_ecef_m'))
    if method=='OISAM':nvalid=nvalid and all(math.isfinite(float(s[k])) for k in ('roll_deg','pitch_deg','yaw_deg')) and (role!='PRIMARY_DYNAMIC_ONLY' or (int(s['dynamic_valid'])==1 and int(s['prior_only'])==0))
    assert v==(nvalid and e['reference_time_min_s']<=t<=e['reference_time_max_s'])
    if not v:
     assert not all(math.isfinite(float(x[k] or 'nan')) for k in ('err_n_m','err_e_m','err_u_m'));continue
    if method=='OISAM':expected=independent_imu_point(s,protocol['lever_imu_to_gnss1_frd_m'])
    else:expected=vector(s,('x_ecef_m','y_ecef_m','z_ecef_m'))
    saved=vector(y,('x_ecef_m','y_ecef_m','z_ecef_m'));pm=max(abs(a-b) for a,b in zip(expected,saved));assert pm<=5e-8,(seq,method,'point',pm);point_max=max(point_max,pm);point_count+=3
    truth=vector(y,('truth_x_ecef_m','truth_y_ecef_m','truth_z_ecef_m'));diff=tuple(a-b for a,b in zip(saved,truth));ned=tuple(dot(diff,b) for b in bb);oracle=(ned[0],ned[1],-ned[2],math.hypot(*ned[:2]),math.sqrt(dot(ned,ned)));actual=vector(x,('err_n_m','err_e_m','err_u_m','horizontal_err_m','position_3d_err_m'));gm=max(abs(a-b) for a,b in zip(oracle,actual));assert gm<=1e-10,(seq,method,'frame',gm);geometry_max=max(geometry_max,gm);geometry_count+=5
    l,r,span=map(float,(x['reference_left_s'],x['reference_right_s'],x['reference_bracket_span_s']));assert l<=t<=r and abs((r-l)-span)<1e-12
    key=round(t)
    if abs(t-key)<=.005:assert key not in lookups[method];lookups[method][key]=x
   if method!='OISAM':assert not any(k.startswith('yaw_') for k in er[0])
  keys=sorted(set.intersection(*(set(x) for x in lookups.values())));assert keys==e['common_nominal_keys'][role]
  for key in keys:
   tt=[float(lookups[m][key]['time']) for m in lookups];spread=max(tt)-min(tt);assert spread<=.010+1e-12;common_time_max=max(common_time_max,spread)
  for row in [x for x in e['rows'] if x['support_role']==role]:
   method=row['method_id'];valid=[x for x in tables[method] if int(x['valid'])==1];subset=valid if row['support']=='OWN_VALID' else [lookups[method][k] for k in keys]
   assert row['matched_epoch_count']==len(subset);assert row['missing_or_invalid_count']==row['expected_epoch_count']-len(subset);assert abs(row['coverage_fraction']-len(subset)/row['expected_epoch_count'])<1e-15
   if role=='PRIMARY_DYNAMIC_ONLY' and method=='OISAM':assert all(int(x['prior_only'])==0 for x in subset)
   for name,col,unit in [('horizontal','horizontal_err_m','m'),('vertical','err_u_m','m'),('position_3d','position_3d_err_m','m')]+([('yaw','yaw_err_deg','deg')] if method=='OISAM' else []):
    values=stats([float(x[col]) for x in subset])
    for stat,v in values.items():
     target=row[name+'_'+stat+'_'+unit]
     if v is None:assert target is None
     else:dm=abs(v-target);assert dm<=1e-9,(seq,method,name,stat,dm);metric_max=max(metric_max,dm)
     metric_count+=1
   support_checks.append({k:row[k] for k in ('sequence_id','method_id','support_role','support','expected_epoch_count','matched_epoch_count')})
receipt={'schema':'root.independent.fgo.segmented.review.v1','all_checks_passed':True,'source_sha256':sha(Path(__file__)),'stage_id':stage.name,'native_seal_sha256':sha(stage/'ALL_NATIVE_SEALED.json'),'preregistration_sha256':sha(stage/'PREREGISTRATION.json'),'evaluation_pins':eval_pins,'independent_statistic_fields_checked':metric_count,'metric_max_difference':metric_max,'independent_frame_fields_checked':geometry_count,'frame_max_difference_m':geometry_max,'independent_native_point_fields_checked':point_count,'native_point_max_difference_m':point_max,'common_actual_time_max_spread_s':common_time_max,'support_rows_checked':support_checks,'reference_payload_reads':0,'pipeline_imports':0,'native_invocations':0,'evaluator_invocations':0,'comparison_rank_claim':False,'reference_truth_or_interpolation_not_independently_rederived':True,'yaw_checks':'saved error distributions/statistics only; no independent reference yaw reread'}
A.out.write_text(json.dumps(receipt,ensure_ascii=False,indent=2,allow_nan=False)+'\n');print(json.dumps({k:v for k,v in receipt.items() if k!='support_rows_checked'}))

