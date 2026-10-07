#!/usr/bin/env python3
"""NMB1 source-only SDK coordinate consistency, with reusable exact-time motion cache.
No reference, GNSS, native state, time/frame fit or generated navigation provider.
"""
from pathlib import Path
import argparse,hashlib,json,re,sys,time
import numpy as np
ROOT=Path(__file__).resolve().parents[3]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'scripts/paper_rebuild')]
from clean6_hv_frame_audit import direction_diagnostics

def main():
 p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--source',type=Path,required=True);a=p.parse_args()
 out=a.output;out.mkdir(parents=True,exist_ok=False);started=time.monotonic()
 source=a.source
 base=1767571200;offset=-1100000000;lo=40621.403808498384;hi=40972.56780471802
 meta=dict(source=str(source),base_time_unix_s=base,body_offset_ns=offset,window=[lo,hi],
      selection='all native window plus 0.1 s source boundary support',reference_reads=0,native_calls=0,
      time_fit=False,frame_fit=False,nav_reads=0,velocity_as_truth=False,
      source_fields=['stamp','error_code','rpy','position','velocity','gyroscope','foot_position_body','foot_speed_body','foot_force'])
 (out/'PLAN.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2)+'\n')
 blob=source.read_bytes();meta['source_sha256']=hashlib.sha256(blob).hexdigest();meta['source_bytes']=len(blob)
 assert meta['source_sha256']=='01d20699dff81fa0f8f13ee8b5d8956d30e1cd64ed59176a4bb65bfc768ec157'
 stamp=re.compile(r'^stamp:\n  sec: (\d+)\n  nanosec: (\d+)',re.M)
 error=re.compile(r'^error_code: ([^\n]+)',re.M)
 spec={'rpy':('  ',3),'gyroscope':('  ',3),'position':('',3),'velocity':('',3),'foot_position_body':('',12),'foot_speed_body':('',12),'foot_force':('',4)}
 patterns={k:re.compile(r'^'+ind+k+r':\n((?:'+ind+r'- [^\n]*(?:\n|$)){'+str(n)+'})',re.M) for k,(ind,n) in spec.items()}
 native_ns=[];source_rows=[];data={k:[] for k in spec};fail=[];message_count=0
 for row,msg in enumerate(blob.decode('utf8').replace('\r\n','\n').split('\n---'),1):
  m=stamp.search(msg)
  if m is None:continue
  message_count+=1;ns=(int(m[1])-base)*1000000000+int(m[2])+offset;t=ns/1e9
  if not lo-.1<=t<=hi+.1:continue
  try:
   e=error.search(msg);assert e and int(e[1].strip())==0
   values={k:[float(x.strip()[2:]) for x in patterns[k].search(msg)[1].splitlines()] for k in spec}
   assert all(len(values[k])==spec[k][1] and np.isfinite(values[k]).all() for k in spec)
  except (AssertionError,ValueError,TypeError) as exc:fail.append(dict(source_row=row,native_time=t,reason=type(exc).__name__));continue
  native_ns.append(ns);source_rows.append(row)
  for k in spec:data[k].append(values[k])
 ns=np.asarray(native_ns,np.int64);t=ns/1e9;v={k:np.asarray(x) for k,x in data.items()}
 assert np.all(np.diff(ns)>0)
 # The old BY audit's internal direction calculation is reused verbatim.
 raw=np.column_stack((t,v['rpy'],v['position'],v['velocity']))
 report=direction_diagnostics(raw,(lo,hi))
 meta.update(source_messages=message_count,cache_rows=len(t),source_faults=fail,
      frame_hypotheses='raw velocity in SDK position frame versus Rz(yaw)Ry(pitch)Rx(roll) times raw velocity',
      SDK_internal_consistency_only=True,not_independent_accuracy=True)
 sign=np.array([1.,-1.,-1.])
 np.savez_compressed(out/'NMB1_FULL_SOURCE_MOTION.npz',native_ns=ns,times=t,
      source_rows=np.asarray(source_rows),gyro_frd=v['gyroscope']*sign,velocity_frd=v['velocity']*sign,
      rpy_flu=v['rpy'],position_sdk=v['position'],foot_position_body_frd=v['foot_position_body'].reshape(-1,4,3)*sign,
      foot_speed_body_frd=v['foot_speed_body'].reshape(-1,4,3)*sign,foot_force=v['foot_force'],metadata=json.dumps(meta))
 result=dict(metadata=meta,direction=report,wall_s=time.monotonic()-started)
 (out/'READOUT.json').write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
 print(json.dumps(dict(rows=len(t),faults=len(fail),moving=report['moving_ge_0_3_both'],wall_s=result['wall_s']),indent=2))
if __name__=='__main__':main()
