"""Independent selected-message raw and frame-metadata audit. No science loader or alignment."""
from pathlib import Path
import ast,collections,csv,hashlib,io,json,math,re,struct,zipfile
import numpy as np
from profile_candidates import ZIP,OUT,zcsv,dist,save,csvsave
prior={x['member']:x for x in json.loads((OUT/'ZIP_RAW_SELECTED_PROFILE.json').read_text())}
def payload(row,cls,msgid):
 b=ast.literal_eval(row['data'])
 assert isinstance(b,bytes) and b[:4]==bytes([181,98,cls,msgid])
 assert len(b)==struct.unpack_from('<H',b,4)[0]+8
 a=c=0
 for v in b[2:-2]:a=(a+v)&255;c=(c+a)&255
 assert b[-2:]==bytes([a,c]);return b[6:-2]
def audit_raw(z,name):
 h,f,rows=zcsv(z,name);errors=collections.Counter();versions=collections.Counter();weeks=collections.Counter();leaps=collections.Counter();rec=collections.Counter();signals=collections.Counter();trk=collections.Counter();sfr=collections.Counter();times=[];epochs={};measurement_n=0;finite=collections.Counter();pr4=cp4=0;sfcount=rawcount=0;epochdup=0
 for row in rows:
  if row['name']=='UBX-RXM-SFRBX':
   try:
    p=payload(row,2,19);assert len(p)>=8 and len(p)==8+4*p[4];sfr[str((p[0],p[2],p[6],p[4]))]+=1;sfcount+=1
   except Exception:errors['SFRBX_INVALID']+=1
  if row['name']!='UBX-RXM-RAWX':continue
  try:
   p=payload(row,2,21);assert len(p)>=16 and len(p)==16+32*p[11]
  except Exception:errors['RAWX_BYTE_CHECK_OR_NUMMEAS_LENGTH']+=1;continue
  tow=struct.unpack_from('<d',p,0)[0];week=struct.unpack_from('<H',p,8)[0];versions[str(p[13])]+=1;weeks[str(week)]+=1;leaps[str(struct.unpack_from('<b',p,10)[0])]+=1;rec[str(p[12])]+=1;times.append(week*604800+tow);rawcount+=1
  good_pr=set();good_cp=set();pr=cp=0
  for j in range(p[11]):
   off=16+j*32;prm,cpm,dop=struct.unpack_from('<ddf',p,off);key=tuple(p[off+20:off+24]);signals[str((key[0],key[2],key[3]))]+=1;flag=p[off+30];trk[str(flag)]+=1;measurement_n+=1
   for n,v in [('prMes_m',prm),('cpMes_cycles',cpm),('doMes_Hz',dop)]:
    finite[n+'_finite']+=math.isfinite(v);finite[n+'_nonzero_finite']+=math.isfinite(v) and v!=0
   if flag&1 and math.isfinite(prm):good_pr.add(key);pr+=1
   if flag&2 and math.isfinite(cpm) and p[off+28]&15!=15:good_cp.add(key);cp+=1
  pr4+=pr>=4;cp4+=cp>=4
  k=(week,tow);epochdup+=k in epochs;epochs[k]={'pr':good_pr,'cp':good_cp}
 f.close();assert h.h.hexdigest()==prior[name]['sha256'] and h.bytes==prior[name]['bytes']
 return dict(member=name,sha256=h.h.hexdigest(),bytes=h.bytes,RAWX_checked=rawcount,SFRBX_checked=sfcount,decode_issues=dict(errors),RAWX_versions=dict(versions),GPS_week_counts=dict(weeks),leapS_counts=dict(leaps),recStat_counts=dict(rec),clock_reset_flag_messages=sum(v for k,v in rec.items()if int(k)&2),RAWX_clock_dt_s=dist(np.diff(times)),backward_RAWX_time=int(np.count_nonzero(np.diff(times)<0)),duplicate_RAWX_epoch_keys=epochdup,RAWX_measurements=measurement_n,finite_field_counts=dict(finite),tracking_flags=dict(trk),signals=dict(signals),epochs_at_least4_prValid=pr4,epochs_at_least4_cpValid_finite_std=cp4,SFRBX_gnss_signal_version_words=dict(sfr),scope='All RAWX/SFRBX bytes/checksum/declared groups verified; no ephemeris decoding, AR, DOP geometry, RINEX or estimator'),epochs
raw=[];pairs=[];tf=[];ur=[]
with zipfile.ZipFile(ZIP)as z:
 folders=[x.filename for x in z.infolist()if x.is_dir()]
 for folder in folders:
  print('SUPPLEMENT_START '+folder,flush=True)
  a,e1=audit_raw(z,folder+'gnss1-raw.csv');b,e2=audit_raw(z,folder+'gnss2-raw.csv');raw+=[a,b];common=e1.keys()&e2.keys()
  prs=[len(e1[k]['pr']&e2[k]['pr'])for k in common];cps=[len(e1[k]['cp']&e2[k]['cp'])for k in common]
  pairs.append(dict(folder=folder,RAWX_exact_week_tow_pairs=len(common),common_prValid_signals=dist(prs),common_cpValid_finite_std_signals=dist(cps),epochs_at_least4_common_pr=sum(v>=4 for v in prs),epochs_at_least4_common_cp=sum(v>=4 for v in cps),pairing_rule='exact binary week/rcvTow values; signal tuple gnss/sv/sig/freq; no interpolation'))
  for base in ['tf.csv','tf_static.csv']:
   h,f,rs=zcsv(z,folder+base);edges=collections.Counter();constants=collections.defaultdict(set);row_n=0
   for row in rs:
    row_n+=1
    for block in re.split(r', header:',row['transforms']):
     parent=re.search(r'(?<!child_)frame_id:\s*"([^"\n]*)"',block);child=re.search(r'child_frame_id:\s*"([^"\n]*)"',block)
     if parent and child:
      edge=(parent[1],child[1]);edges[edge]+=1
      if not any(x in edge for x in ('ECEF','ENU','VISION','IMUH')):
       constants[edge].add(re.sub(r'^.*?transform:', '',block,flags=re.S).strip(' ]'))
   f.close();tf.append(dict(member=folder+base,sha256=h.h.hexdigest(),bytes=h.bytes,rows=row_n,edge_counts={str(k):v for k,v in edges.items()},candidate_rigid_transforms={str(k):sorted(v)for k,v in constants.items()},scope='frame graph identities; dynamic navigation transforms not used for alignment or metrics'))
  h,f,rs=zcsv(z,folder+'userio-raw.csv');names=collections.Counter();tfmsg=collections.Counter();tfissues=collections.Counter();n=0
  for row in rs:
   n+=1;names[row.get('name','')]+=1
   if row.get('name','').startswith('FP_A-TF'):
    try:
     b=ast.literal_eval(row['data']);s=b.decode('ascii').strip();body,chk=s[1:].split('*');cc=0
     for x in body.encode('ascii'):cc^=x
     assert cc==int(chk,16);v=body.split(',');assert v[0]=='FP' and v[1]=='TF';tfmsg[','.join(v[2:])]+=1
    except Exception:tfissues['TF_BYTE_OR_ASCII_CHECKSUM']+=1
  f.close();ur.append(dict(member=folder+'userio-raw.csv',sha256=h.h.hexdigest(),bytes=h.bytes,rows=n,message_counts=dict(names),TF_messages=dict(tfmsg),TF_issues=dict(tfissues),scope='message names and TF metadata only; odometry/reference values not decoded'))
  save('ZIP_RAWX_FULL_FIELDS_PROFILE.json',raw);save('ZIP_RAWX_EXACT_PAIR_PROFILE.json',pairs);save('ZIP_FRAME_GRAPH_PROFILE.json',tf);save('ZIP_USERIO_METADATA_PROFILE.json',ur)
save('SUPPLEMENT_SCOPE.json',dict(helper_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),native_executions=0,evaluator_executions=0,offset_fitting=0,members_extracted=0,RAWX_members=len(raw),frame_members=len(tf),userio_members=len(ur),raw_member_hashes_match_prior_full_stream=True))
