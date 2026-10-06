#!/usr/bin/env python3
"""DG01: checked raw-message decoding only; no navigation runtime imports."""
import os
os.environ.update(OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1')
import ast,csv,json,hashlib,struct,math,datetime
from pathlib import Path
import numpy as np
import pandas as pd
import yaml
W=Path(__file__).resolve().parents[2]
CFG=yaml.safe_load((W/'configs/paper_rebuild/DATA_PATHS.CLEAN3R4.local.yaml').read_text())['paths']
C=Path(CFG['clean_root']);O=C/'stages/CLEAN10_GNSS_RAW_DIAGNOSTIC/DG01';R=W/'docs/paper_rebuild/hext/DG01'
HX=C/'stages/CLEAN9_EXTERNAL_COMPARISON/HX02_FIVE_CATEGORY'
SEQ={'BY2':(1772784000.,66.,340.),'BY2H':(1772784000.,413.,683.),'BY2O':(1772780400.,3186.,3563.)}
SOURCES={}
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def read(p):
 p=Path(p).resolve();s=str(p).lower()
 if any(x in s for x in ['trace','.bag','.fpl']):raise RuntimeError('FORBIDDEN_INPUT '+str(p))
 SOURCES[str(p)]={'sha256':sha(p),'bytes':p.stat().st_size};return p
def save_sources():
 p=O/'INPUT_SHA256.json';d=json.loads(p.read_text()) if p.exists() else {};d.update(SOURCES);p.write_text(json.dumps(d,indent=2)+'\n')
def log(s):
 with (O/'PROGRESS.txt').open('a') as f:f.write(datetime.datetime.now(datetime.timezone.utc).isoformat()+' '+s+'\n')
 print(s,flush=True)
def write(name,data,repo=False):
 df=data if isinstance(data,pd.DataFrame) else pd.DataFrame(data)
 df.to_csv((R if repo else O)/name,index=False,lineterminator='\n',float_format='%.17g')
def utc(week,tow,leap=18):return 315964800.+week*604800.+tow-leap
def frame(data):
 b=ast.literal_eval(data)
 if not isinstance(b,bytes) or not b.startswith(b'\xb5\x62'):return None
 n=int.from_bytes(b[4:6],'little');assert len(b)==n+8,('UBX length',len(b),n)
 a=c=0
 for v in b[2:-2]:a=(a+v)&255;c=(c+a)&255
 assert b[-2:]==bytes([a,c]),'UBX checksum'
 return b[2],b[3],b[6:-2]
def freq(g,s,f):
 table={(0,0):1575.42e6,(0,3):1227.60e6,(0,4):1227.60e6,(1,0):1575.42e6,(2,0):1575.42e6,(2,1):1575.42e6,(2,5):1207.14e6,(2,6):1207.14e6,(3,0):1561.098e6,(3,1):1561.098e6,(3,2):1207.14e6,(3,3):1207.14e6,(5,0):1575.42e6,(5,4):1227.60e6,(5,5):1227.60e6}
 if g==6:return (1602e6+(f-7)*.5625e6) if s==0 else (1246e6+(f-7)*.4375e6) if s==2 else np.nan
 return table.get((g,s),np.nan)
def decode(seq,receiver,path,status_path):
 base,start,end=SEQ[seq];status=pd.read_csv(read(status_path));week=int(status.time_gps_wno.iloc[0]);leap=18
 inv=[];obs=[];nav=[];hp=[];sat=[];sig=[];rel=[];clock=[];names={};bad={}
 with read(path).open() as f:
  for row in csv.DictReader(f):
   name=row['name'];ts=float(row['Time'])-base;entry=names.setdefault(name,[0,0,ts,ts]);entry[0]+=1;entry[1]+=start<=ts<=end;entry[3]=ts
   try:v=frame(row['data'])
   except (AssertionError,ValueError,SyntaxError):bad[name]=bad.get(name,0)+1;continue
   if v is None:continue
   cl,mid,p=v
   if (cl,mid)==(2,0x15):
    tow,w,ls,n,flags,ver,_=struct.unpack_from('<dHbBBB2s',p);assert len(p)==16+n*32
    t=utc(w,tow,ls)-base
    # Keep entire streams so first in-window lock/arc has previous context.
    for i in range(n):
     pr,cp,dop,g,sv,s,fr,lock,cno,prs,cps,dos,trk,_=struct.unpack_from('<ddfBBBBHBBBBBB',p,16+32*i)
     obs.append([t,tow,w,g,sv,s,fr,pr,cp,dop,lock,cno,prs&15,cps&15,dos&15,trk,flags,freq(g,s,fr)])
   elif cl==1:
    itow=struct.unpack_from('<I',p,4 if mid in [0x13,0x3c] else 0)[0];t=utc(week,itow*.001,leap)-base
    if mid==7:
     nav.append([t,itow,(p[21]>>6)&3,p[23],struct.unpack_from('<I',p,40)[0]*.001,struct.unpack_from('<I',p,44)[0]*.001,struct.unpack_from('<i',p,48)[0]*.001,struct.unpack_from('<i',p,52)[0]*.001,struct.unpack_from('<i',p,60)[0]*.001,struct.unpack_from('<i',p,64)[0]*1e-5])
    elif mid==0x13:
     xyz=np.array(struct.unpack_from('<iii',p,8))*.01+np.array(struct.unpack_from('<bbb',p,20))*.0001
     hp.append([t,itow,*xyz,struct.unpack_from('<I',p,24)[0]*.0001,not bool(p[3]&1)])
    elif mid==0x35:
     for j in range(p[5]):
      g,sv,cno,elev,az,res,flags=struct.unpack_from('<BBBbhhI',p,8+12*j);sat.append([t,itow,g,sv,cno,elev,az,bool(flags&8)])
    elif mid==0x43:
     for j in range(p[5]):
      g,sv,s,fr,prres,cno,quality,corr,iono,flags,_=struct.unpack_from('<BBBBhBBBBHI',p,8+16*j)
      sig.append([t,itow,g,sv,s,fr,cno,quality,corr,iono,bool(flags&8),bool(flags&16),bool(flags&128)])
    elif mid==0x3c and len(p)==64 and p[0]==1:
     flags=struct.unpack_from('<I',p,60)[0];length=struct.unpack_from('<i',p,20)[0]*.01+struct.unpack_from('<b',p,35)[0]*.0001
     rel.append([t,itow,struct.unpack_from('<H',p,2)[0],length,length-.35,struct.unpack_from('<i',p,24)[0]*1e-5,(flags>>3)&3,bool(flags&(1<<8)),bool(flags&4)])
    elif mid==0x22:clock.append([t,itow,*struct.unpack_from('<iiII',p,4)])
 cols={'obs':'time tow week gnss sv signal frequency_id pseudorange_m carrier_cycles doppler_hz lock_ms cno_dbhz pr_std cp_std do_std tracking receiver_status frequency_hz','nav':'time itow carrSoln numSV hAcc_m vAcc_m vn_mps ve_mps speed_mps course_deg','hp':'time itow x y z pAcc_m valid','sat':'time itow gnss sv cno_dbhz elevation_deg azimuth_deg svUsed','sig':'time itow gnss sv signal frequency_id cno_dbhz quality corrSource ionoModel prUsed crUsed crCorrUsed','rel':'time itow ref_station length_m length_minus_035_m heading_deg carrSoln heading_valid position_valid','clock':'time itow bias_ns drift_nsps time_accuracy_ns frequency_accuracy_psps'}
 for name,rows in [('obs',obs),('nav',nav),('hp',hp),('sat',sat),('sig',sig),('rel',rel),('clock',clock)]:
  df=pd.DataFrame(rows,columns=cols[name].split());write(f'{seq}_R{receiver}_{name}.csv.gz',df)
 for name,x in names.items():inv.append(dict(sequence=seq,receiver=receiver,stream='raw',message_or_field=name,count_full=x[0],count_window=x[1],rate_hz=x[1]/(end-start),first_stamp=x[2],last_stamp=x[3],bad_checksum_or_length=bad.get(name,0),source=alias(path)))
 st=status['sys_stamp.secs']+status['sys_stamp.nsecs']*1e-9-base;mask=st.between(start,end)
 for col in status.columns:inv.append(dict(sequence=seq,receiver=receiver,stream='status',message_or_field=col,count_full=int(status[col].notna().sum()),count_window=int(status.loc[mask,col].notna().sum()),rate_hz=int(status.loc[mask,col].notna().sum())/(end-start),first_stamp=float(st.iloc[0]),last_stamp=float(st.iloc[-1]),bad_checksum_or_length=0,source=alias(status_path)))
 status.insert(0,'relative_sys_time',st);write(f'{seq}_R{receiver}_status.csv.gz',status)
 return inv
def alias(p):return str(p).replace(str(W),'<W>').replace(str(C),'<CLEAN_ROOT>').replace(CFG['raw_root'],'<RAW_ROOT>').replace(CFG['hx02_external_root'],'<EXTERNAL_ROOT>')
def run_dir(seq,method):return next((HX/'RUNS').glob(seq+'__'+method+'__*'))
def load(seq,receiver,kind):return pd.read_csv(O/f'{seq}_R{receiver}_{kind}.csv.gz',float_precision='round_trip')
def main():
 O.mkdir(parents=True,exist_ok=True);R.mkdir(parents=True,exist_ok=True);log('START raw decode after registration commit')
 pins=json.loads((O/'DG01_RAW_PINS.json').read_text())
 for x in pins:
  if sha(x['path'])!=x['expected']:raise RuntimeError('RAW_HASH_MISMATCH '+x['path'])
 inv=[]
 for seq in SEQ:
  for rec in [1,2]:
   p={x['stream']:x['path'] for x in pins if x['sequence']==seq and x['receiver']==rec};inv+=decode(seq,rec,p['raw'],p['status']);log(f'DECODED {seq} R{rec}')
 write('DG01_MESSAGE_INVENTORY.csv',inv,True);save_sources();log('DONE raw decode')
if __name__=='__main__':
 try:main()
 except Exception as e:
  (O/'HARD_STOP.json').write_text(json.dumps({'stage':'raw_decode','error':repr(e)},indent=2)+'\n');raise
