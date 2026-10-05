"""Read-only descriptive receiver-clock pairing and recorded TF configuration."""
import ast,csv,hashlib,json,math,struct,zipfile
from pathlib import Path
from collections import Counter
import numpy as np
from profile_candidates import ZIP,OUT,BODY,zcsv,dist,csvsave,save
prior={x['member']:x for x in json.loads((OUT/'ZIP_RAW_SELECTED_PROFILE.json').read_text())}
def time_rawx(z,name):
 h,f,rs=zcsv(z,name);ts=[]
 for r in rs:
  if r['name']!='UBX-RXM-RAWX':continue
  b=ast.literal_eval(r['data']);p=b[6:-2];assert b[:4]==bytes([181,98,2,21]) and len(p)==16+32*p[11] and len(b)==len(p)+8
  a=c=0
  for v in b[2:-2]:a=(a+v)&255;c=(c+a)&255
  assert b[-2:]==bytes([a,c]);ts.append(struct.unpack_from('<H',p,8)[0]*604800+struct.unpack_from('<d',p,0)[0])
 f.close();assert h.h.hexdigest()==prior[name]['sha256'];return np.array(ts)
clocks=[]
with zipfile.ZipFile(ZIP) as z:
 for d in [i.filename for i in z.infolist()if i.is_dir()]:
  a=time_rawx(z,d+'gnss1-raw.csv');b=time_rawx(z,d+'gnss2-raw.csv');js=np.searchsorted(b,a);deltas=[];within=0
  for t,j in zip(a,js):
   candidates=[k for k in [j-1,j]if 0<=k<len(b)];k=min(candidates,key=lambda k:abs(b[k]-t));delta=b[k]-t;deltas.append(delta);within+=abs(delta)<=.1
  clocks.append(dict(folder=d,GNSS1_epochs=len(a),GNSS2_epochs=len(b),nearest_GNSS2_minus_GNSS1_tow_s=dist(deltas),nearest_abs_delta_s=dist(np.abs(deltas)),pairs_with_abs_delta_le_0p1s=int(within),rule='nearest receiver local RAWX time, descriptive only; 0.1 s fixed diagnostic half nominal5Hz spacing, no observation correction',offset_fitted=False))
save('RAWX_CLOCK_DIAGNOSTIC.json',clocks)
tfs=[]
for u in json.loads((OUT/'ZIP_USERIO_METADATA_PROFILE.json').read_text()):
 edges={}
 for message,n in u['TF_messages'].items():
  v=message.split(',');k=(v[3],v[4]);q=edges.setdefault(k,dict(n=0,vals=set(),weeks=Counter(),tow=[]));q['n']+=n;q['vals'].add(tuple(float(x)for x in v[5:12]));q['weeks'][v[1]]+=n;q['tow'].append(float(v[2]))
 for (a,b),q in edges.items():
  vals=sorted(q['vals']);tfs.append(dict(folder=u['member'].split('/')[0],message_version=2,frame_a=a,frame_b=b,checked_messages=q['n'],unique_transform_count=len(vals),values_tx_ty_tz_qw_qx_qy_qz=json.dumps(vals,separators=(',',':')),first_GPS_tow=min(q['tow']),last_GPS_tow=max(q['tow']),all_identity=all(all(abs(x-y)<1e-12 for x,y in zip(v,(0,0,0,1,0,0,0)))for v in vals),sha256_source=u['sha256'],scope='actual FP_A-TF bytes; no tutorial default substituted'))
csvsave('RECORDED_FP_TF_SUMMARY.csv',tfs)
ends=[]
for f in [BODY/f'{n}{i}.txt' for n in ['nmb','xb'] for i in range(1,5)]:
 with f.open('rb')as h:h.seek(max(0,f.stat().st_size-512));b=h.read()
 ends.append(dict(file=f.name,last512bytes_sha256=hashlib.sha256(b).hexdigest(),tail_utf8=b.decode('utf-8',errors='replace'),scope='selected EOF completeness inspection only'))
save('BODY_EOF_COMPLETENESS.json',ends)
print(json.dumps({'clocks':clocks,'tf':tfs},ensure_ascii=False,indent=2))
