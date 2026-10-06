"""Read-only machine stream profile. No provider, estimator, evaluator, resampling or offset search."""
from pathlib import Path
import argparse,collections,csv,datetime,hashlib,io,json,math,re,struct,zipfile,ast
import numpy as np
ROOT=Path('G:/LegSA-GINS-project/data/raw/XB_PG/2026-01-05')
OUT=Path(__file__).resolve().parent
ZIP=ROOT/'fixpositon数据/vrtk2_a87c6e_2026-01-05-11-16-59_minimal.zip'
BODY=ROOT/'高层数据'
sha=lambda p:hashlib.file_digest(p.open('rb'),'sha256').hexdigest()
def save(name,x):(OUT/name).write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8',newline='\n')
def csvsave(name,rows):
 if not rows:return
 keys=list(dict.fromkeys(k for r in rows for k in r))
 with (OUT/name).open('w',encoding='utf-8',newline='') as f:
  w=csv.DictWriter(f,fieldnames=keys,lineterminator='\n');w.writeheader();w.writerows(rows)
def utc(t):
 try:return datetime.datetime.fromtimestamp(t,datetime.timezone.utc).isoformat()
 except:return None
class Stat:
 def __init__(self):self.n=0;self.nonfinite=0;self.zero=0;self.lo=None;self.hi=None;self.s=0.;self.s2=0.
 def add(self,v):
  if not math.isfinite(v):self.nonfinite+=1;return
  self.n+=1;self.zero+=v==0;self.lo=v if self.lo is None else min(self.lo,v);self.hi=v if self.hi is None else max(self.hi,v);self.s+=v;self.s2+=v*v
 def result(self):return dict(finite_n=self.n,nonfinite_n=self.nonfinite,zero_n=self.zero,min=self.lo,max=self.hi,mean=self.s/self.n if self.n else None,std=math.sqrt(max(0,self.s2/self.n-(self.s/self.n)**2)) if self.n else None)
def dist(v):
 a=np.asarray(v,dtype=float);a=a[np.isfinite(a)]
 return dict(n=len(a),min=float(a.min()),p01=float(np.quantile(a,.01)),p50=float(np.median(a)),p95=float(np.quantile(a,.95)),p99=float(np.quantile(a,.99)),max=float(a.max())) if len(a) else {'n':0}
EXPECTED={'quaternion':4,'gyroscope':3,'accelerometer':3,'rpy':3,'position':3,'velocity':3,'range_obstacle':4,'foot_force':4,'foot_position_body':12,'foot_speed_body':12}
def parse_block(lines):
 r={};key=None;issues=[]
 for l in lines:
  s=l.strip()
  if s.startswith('- '):
   if key is not None:
    try:r.setdefault(key,[]).append(float(s[2:].strip()))
    except ValueError:issues.append('INVALID_LIST_NUMBER:'+key)
   continue
  m=re.match(r'^([a-zA-Z_]\w*):\s*(.*?)\s*$',s)
  if m:
   k,v=m.groups()
   if not v:key=k;continue
   key=None
   try:r[k]=int(v) if k in ('sec','nanosec') else float(v)
   except ValueError:issues.append('NONNUMERIC_SCALAR:'+k)
 return r,issues
def euler(q,order):
 w,x,y,z=q if order=='wxyz' else [q[3],q[0],q[1],q[2]]
 n=math.sqrt(w*w+x*x+y*y+z*z)
 if not math.isfinite(n) or n==0:return None
 w,x,y,z=[v/n for v in (w,x,y,z)]
 return [math.atan2(2*(w*x+y*z),1-2*(x*x+y*y)),math.asin(max(-1,min(1,2*(w*y-z*x)))),math.atan2(2*(w*z+x*y),1-2*(y*y+z*z))]
def profile_body(path):
 before=(path.stat().st_size,path.stat().st_mtime_ns);h=hashlib.sha256();nbytes=0;nlines=0;blocks=[];prefix=[];frames=0;with_stamp=0;bad=collections.Counter();stats=collections.defaultdict(Stat);lengths=collections.defaultdict(collections.Counter);missing=collections.Counter();modes=collections.defaultdict(collections.Counter);dt=[];gaps=[];segments=[];clock=None;first=None;last=None;segment_start=None;segment_n=0;duplicate=0;reset=0;repeated=collections.Counter();previous={};qn=[];cons={o:np.zeros(3) for o in ['wxyz','xyzw']};cons_n=0;events=[];prev_acc=None;prev_t=None;complete_required=0;frame_line=1
 def consume(block,line):
  nonlocal frames,with_stamp,clock,first,last,segment_start,segment_n,duplicate,reset,cons_n,prev_acc,prev_t,complete_required
  r,err=parse_block(block)
  if 'sec' not in r and 'nanosec' not in r:return
  frames+=1;bad.update(err)
  if 'sec' not in r or 'nanosec' not in r or not 0<=r.get('nanosec',-1)<1e9:bad['INVALID_OR_MISSING_STAMP']+=1;return
  ns=r['sec']*1000000000+r['nanosec'];t=ns/1e9;with_stamp+=1
  if first is None:first=t;segment_start=t
  if clock is not None:
   delta=(ns-clock)/1e9;dt.append(delta)
   if delta==0:duplicate+=1
   if delta<0:
    reset+=1;segments.append(dict(file=path.name,start=segment_start,end=last,rows=segment_n,termination='BACKWARD_CLOCK'));segment_start=t;segment_n=0
   if delta>.1:gaps.append(dict(file=path.name,previous_t=last,next_t=t,dt=delta,frame=frames,line=line))
  clock=ns;last=t;segment_n+=1
  good=True
  for k,num in EXPECTED.items():
   v=r.get(k);lengths[k][len(v) if isinstance(v,list) else -1]+=1
   if not isinstance(v,list) or len(v)!=num:missing[k]+=1;good=False;continue
   for i,value in enumerate(v):stats[k+'_'+str(i)].add(value)
   if previous.get(k)==v:repeated[k]+=1
   previous[k]=v
  complete_required+=good
  for k,v in r.items():
   if isinstance(v,(int,float)) and k not in ('sec','nanosec'):stats[k].add(float(v));modes[k][str(v)]+=1 if k in ('error_code','mode','gait_type') else 0
  q=r.get('quaternion',[]);rp=r.get('rpy',[])
  if len(q)==4 and all(math.isfinite(v) for v in q):qn.append(math.sqrt(sum(v*v for v in q)))
  if len(q)==4 and len(rp)==3 and all(math.isfinite(v) for v in q+rp):
   es={o:euler(q,o) for o in cons}
   if all(es.values()):
    for o,er in es.items():cons[o]+=np.square([(a-b+math.pi)%(2*math.pi)-math.pi for a,b in zip(er,rp)])
    cons_n+=1
  acc=r.get('accelerometer',[])
  if len(acc)==3 and all(math.isfinite(v) for v in acc):
   stats['accelerometer_norm'].add(math.sqrt(sum(v*v for v in acc)))
   if prev_acc is not None and prev_t<t and t-prev_t<=.02 and t-first<=30:
    j=math.sqrt(sum((a-b)**2 for a,b in zip(acc,prev_acc)))/(t-prev_t);events.append((j,t,frames))
   prev_acc=acc;prev_t=t
  vel=r.get('velocity',[])
  if len(vel)==3 and all(math.isfinite(v) for v in vel):stats['velocity_norm'].add(math.sqrt(sum(v*v for v in vel)))
 with path.open('rb') as f:
  for raw in f:
   h.update(raw);nbytes+=len(raw);nlines+=1
   try:l=raw.decode('utf-8').rstrip('\r\n')
   except UnicodeDecodeError:l=raw.decode('utf-8',errors='replace').rstrip('\r\n');bad['UTF8_DECODE_ERROR_LINES']+=1
   if nlines<=5:prefix.append(l)
   if l.strip()=='---':consume(blocks,frame_line);blocks=[];frame_line=nlines+1
   else:blocks.append(l)
  if blocks:consume(blocks,frame_line)
 if segment_n:segments.append(dict(file=path.name,start=segment_start,end=last,rows=segment_n,termination='EOF'))
 assert before==(path.stat().st_size,path.stat().st_mtime_ns) and nbytes==path.stat().st_size
 selected=[]
 for jerk,t,frame in sorted(events,reverse=True):
  if all(abs(t-x['time'])>=.5 for x in selected):selected.append(dict(file=path.name,time=t,relative_to_first_s=t-first,jerk=jerk,frame=frame,rule='largest raw acceleration jerk in first30s; no offset or estimator selection'))
  if len(selected)==8:break
 fields=[dict(file=path.name,field=k,**s.result()) for k,s in sorted(stats.items())]
 profile=dict(file=path.name,bytes=nbytes,sha256=h.hexdigest(),physical_lines=nlines,frames=frames,timestamp_rows=with_stamp,complete_expected_fields_rows=complete_required,first_t=first,last_t=last,first_utc_interpretation=utc(first),last_utc_interpretation=utc(last),elapsed_s=last-first if first is not None else None,positive_dt=dist([x for x in dt if x>0]),duplicate_timestamp_rows=duplicate,backward_clock_rows=reset,gaps_gt_0p1_n=len(gaps),issues=dict(bad),missing_or_bad_lengths=dict(missing),list_length_distributions={k:dict(v) for k,v in lengths.items()},repeated_consecutive_vectors=dict(repeated),mode_counts={k:dict(v) for k,v in modes.items() if any(v.values())},quaternion_norm=dist(qn),quat_to_rpy_assumed_rad_rmse={o:(np.sqrt(v/cons_n)).tolist() if cons_n else None for o,v in cons.items()},quat_to_rpy_compare_n=cons_n,source_file_metadata_unchanged=True,terminal_prefix=prefix,audit_scope='FULL_BYTE_STREAM_MACHINE_PROFILE_NOT_MANUAL_EVERY_LINE_READ')
 return profile,fields,segments,gaps,selected
class HashReader(io.RawIOBase):
 def __init__(self,f):self.f=f;self.h=hashlib.sha256();self.bytes=0
 def readable(self):return True
 def readinto(self,b):
  v=self.f.read(len(b));b[:len(v)]=v;self.h.update(v);self.bytes+=len(v);return len(v)
 def close(self):self.f.close();super().close()
def zcsv(z,name):
 h=HashReader(z.open(name));f=io.TextIOWrapper(io.BufferedReader(h),encoding='utf-8',newline='');return h,f,csv.DictReader(f)
def numeric(s):
 try:v=float(s);return v if math.isfinite(v) else None
 except:return None
def profile_member(z,name):
 h,f,rows=zcsv(z,name);cols=rows.fieldnames;n=0;times=collections.defaultdict(list);qual=collections.defaultdict(collections.Counter);bad=0;field_stats=collections.defaultdict(Stat)
 for r in rows:
  n+=1
  if None in r:bad+=1
  for k in ['Time','header.stamp.secs','header.stamp.nsecs','stamp.secs','stamp.nsecs','time_gps_tow']:
   v=numeric(r.get(k))
   if v is not None and k in ('Time','time_gps_tow'):times[k].append(v)
  if r.get('header.stamp.secs') is not None:
   a=numeric(r.get('header.stamp.secs'));b=numeric(r.get('header.stamp.nsecs'))
   if a is not None and b is not None:times['measurement_header'].append(a+b*1e-9)
  for k in ['fix_type','fix_ok','pos_valid','msg_valid','time_gps_ok','utc_ok','rel_valid','ant_state','child_frame_id','header.frame_id','fusion_status','gnss1_fix','gnss2_fix','imu_bias_status','imu_noise_status']:
   if k in r:qual[k][r[k]]+=1
  for k in ['pos_acc_h','pos_acc_v','sol_num_sat','sol_pdop','orientation.x','orientation.y','orientation.z','orientation.w','angular_velocity.x','angular_velocity.y','angular_velocity.z','linear_acceleration.x','linear_acceleration.y','linear_acceleration.z']:
   v=numeric(r.get(k))
   if v is not None:field_stats[k].add(v)
 f.close();info=z.getinfo(name);assert h.bytes==info.file_size
 return dict(member=name,bytes=h.bytes,sha256=h.h.hexdigest(),rows=n,columns=cols,malformed_csv_rows=bad,times={k:dict(first=v[0],last=v[-1],first_utc=utc(v[0]) if k!='time_gps_tow' else None,last_utc=utc(v[-1]) if k!='time_gps_tow' else None,span=v[-1]-v[0],dt=dist(np.diff(v)),backward=int(np.count_nonzero(np.diff(v)<0)),duplicate=int(np.count_nonzero(np.diff(v)==0))) for k,v in times.items() if v},quality={k:dict(v) for k,v in qual.items()},field_stats={k:v.result() for k,v in field_stats.items()},scope='CSV_MACHINE_TIME_AND_QUALITY_PROFILE_NO_REFERENCE_POSITION_OR_ATTITUDE_COMPARISON')
def raw_profile(z,name):
 h,f,rows=zcsv(z,name);counts=collections.Counter();bad=collections.Counter();rx=[];pvt={};hp={};monver=[]
 for r in rows:
  if None in r:bad['CSV_ROW_WIDTH']+=1
  msg=r.get('name','');counts[msg]+=1
  t=numeric(r.get('Time'))
  if t is not None:rx.append(t)
  if msg not in ('UBX-NAV-PVT','UBX-NAV-HPPOSECEF','UBX-MON-VER'):continue
  try:b=ast.literal_eval(r['data']);assert isinstance(b,bytes) and b[:2]==b'\xb5\x62';length=struct.unpack_from('<H',b,4)[0];assert len(b)==length+8
  except Exception:bad['BYTE_FORMAT_OR_LENGTH:'+msg]+=1;continue
  a=c=0
  for v in b[2:-2]:a=(a+v)&255;c=(c+a)&255
  if b[-2:]!=bytes([a,c]):bad['CHECKSUM:'+msg]+=1;continue
  payload=b[6:-2]
  if msg=='UBX-MON-VER':monver.append(payload.decode('ascii',errors='replace').replace('\x00','|'));continue
  if msg=='UBX-NAV-PVT' and len(payload)>=92:
   itow=struct.unpack_from('<I',payload,0)[0];fix=payload[20];flags=payload[21];v=struct.unpack_from('<iii',payload,48);pvt[itow]=dict(time=t,fix=fix,gps_fix_ok=bool(flags&1),carrier=(flags>>6)&3,vel_mps=[x*.001 for x in v],year=struct.unpack_from('<H',payload,4)[0],month=payload[6],day=payload[7])
  elif msg=='UBX-NAV-HPPOSECEF' and len(payload)==28:
   itow=struct.unpack_from('<I',payload,4)[0];xyz=struct.unpack_from('<iii',payload,8);high=struct.unpack_from('<bbb',payload,20);hp[itow]=dict(time=t,ecef=[a*.01+b*.0001 for a,b in zip(xyz,high)],flag=payload[23],pAcc_raw=struct.unpack_from('<I',payload,24)[0])
  else:bad['UNEXPECTED_PAYLOAD_LENGTH:'+msg]+=1
 f.close();assert h.bytes==z.getinfo(name).file_size
 summary=dict(member=name,bytes=h.bytes,sha256=h.h.hexdigest(),message_counts=dict(counts),byte_decode_issues=dict(bad),receive_clock=dict(first=rx[0],last=rx[-1],first_utc=utc(rx[0]),last_utc=utc(rx[-1]),dt=dist(np.diff(rx))) if rx else None,PVT_unique_itow=len(pvt),HP_unique_itow=len(hp),PVT_fix_carrier_counts=dict(collections.Counter(str((v['fix'],v['gps_fix_ok'],v['carrier'])) for v in pvt.values())),HP_flag_counts=dict(collections.Counter(str(v['flag']) for v in hp.values())),PVT_speed_mps=dist([math.sqrt(sum(x*x for x in v['vel_mps'])) for v in pvt.values()]),MON_VER=monver,scope='RAW_SELECTED_MESSAGE_MACHINE_AUDIT; allbytes hashed, only PVT/HP/MONVER interpreted')
 return summary,pvt,hp
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--part',choices=['body','zip','all'],default='all');args=ap.parse_args()
 if args.part in ('body','all'):
  ps=[];fs=[];ss=[];gs=[];es=[]
  for p in [BODY/f'{n}{i}.txt' for n in ['nmb','xb'] for i in range(1,5)]:
   print('BODY_START '+p.name,flush=True);r,f,s,g,e=profile_body(p);ps.append(r);fs+=f;ss+=s;gs+=g;es+=e;save('BODY_FILE_PROFILE.json',ps);print('BODY_DONE '+p.name+' frames='+str(r['frames'])+' sha='+r['sha256'],flush=True)
  csvsave('BODY_FIELD_STATS.csv',fs);csvsave('BODY_CLOCK_SEGMENTS.csv',ss);csvsave('BODY_GAPS.csv',gs);csvsave('BODY_EVENTS_DIAGNOSTIC.csv',es)
 if args.part in ('zip','all'):
  before=(ZIP.stat().st_size,ZIP.stat().st_mtime_ns);z=zipfile.ZipFile(ZIP);inventory=[dict(member=i.filename,bytes=i.file_size,compressed_bytes=i.compress_size,CRC32=f'{i.CRC:08x}',directory=i.is_dir()) for i in z.infolist()];csvsave('ZIP_MEMBER_INVENTORY.csv',inventory);profiles=[];raw=[];pairs=[];small=[]
  folders=[i.filename for i in z.infolist() if i.is_dir()]
  for folder in folders:
   print('ZIP_START '+folder,flush=True)
   for base in ['gnss1-status.csv','gnss2-status.csv','imu-data.csv','user_io-out-odom_status.csv']:
    name=folder+base
    if name in z.namelist():profiles.append(profile_member(z,name))
   for base in ['tf_static.csv','ntrip-info.csv']:
    name=folder+base
    if name in z.namelist():
     b=z.read(name);small.append(dict(member=name,sha256=hashlib.sha256(b).hexdigest(),bytes=len(b),text=b.decode('utf-8',errors='strict')))
   a,p1,h1=raw_profile(z,folder+'gnss1-raw.csv');b,p2,h2=raw_profile(z,folder+'gnss2-raw.csv');raw.extend([a,b]);common=sorted(h1.keys()&h2.keys());lengths=[];eligible=[]
   for k in common:
    length=math.sqrt(sum((x-y)**2 for x,y in zip(h2[k]['ecef'],h1[k]['ecef'])));lengths.append(length)
    q1=p1.get(k,{});q2=p2.get(k,{})
    if q1.get('gps_fix_ok') and q2.get('gps_fix_ok') and q1.get('carrier')==2 and q2.get('carrier')==2 and not(h1[k]['flag']&1 or h2[k]['flag']&1):eligible.append(length)
   pairs.append(dict(folder=folder,HP_exact_itow_pairs=len(common),HP_all_pair_length_m=dist(lengths),HP_PVT_exact_both_fixed_valid_pairs=len(eligible),HP_both_fixed_length_m=dist(eligible),not_selected_by_reference=True))
   save('ZIP_METADATA_PROFILE.json',profiles);save('ZIP_RAW_SELECTED_PROFILE.json',raw);save('ZIP_BASELINE_SOURCE_PROFILE.json',pairs);save('ZIP_SMALL_METADATA.json',small);print('ZIP_DONE '+folder,flush=True)
  z.close();container_hash=sha(ZIP);assert before==(ZIP.stat().st_size,ZIP.stat().st_mtime_ns);save('ZIP_CONTAINER_IDENTITY.json',dict(path=str(ZIP),bytes=ZIP.stat().st_size,sha256=container_hash,members=len(inventory),source_metadata_unchanged=True,no_members_extracted=True,reference_payload_used_for_alignment=False,scientific_executions=0,profiler_sha256=sha(Path(__file__))))
