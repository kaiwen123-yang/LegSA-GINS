#!/usr/bin/env python3
"""Six authorized convbin conversions and exact RINEX outer-join comparison."""
from dg01r_common import *
from decimal import Decimal
import gzip,struct

def extract_convert():
 (O/'UBX').mkdir(exist_ok=True);(O/'CONVBIN').mkdir(exist_ok=True);receipts=[]
 conv=Path(PRE['convbin_path']);assert sha(conv)==PRE['convbin_sha256'];read(conv)
 for x in PRE['raw_pins']:read(x['path'])
 for s in SEQ:
  for r in [1,2]:
   raw=next(x for x in PRE['raw_pins'] if x['sequence']==s and x['receiver']==r and x['stream']=='raw');p=read(raw['path']);dst=O/'UBX'/f'{s}_R{r}.ubx';counts=Counter();bad=0;n=0
   with p.open() as f,dst.open('wb') as out:
    for row in csv.DictReader(f):
     t=float(row['Time'])-SEQ[s][0]
     if not SEQ[s][1]<=t<=SEQ[s][2]:continue
     b=ast.literal_eval(row['data'])
     if not isinstance(b,bytes) or not b.startswith(b'\xb5\x62'):continue
     out.write(b);n+=1;counts[row['name']]+=1
     a=c=0
     for v in b[2:-2]:a=(a+v)&255;c=(c+a)&255
     bad+=len(b)!=int.from_bytes(b[4:6],'little')+8 or b[-2:]!=bytes([a,c])
   prefix=O/'CONVBIN'/f'{s}_R{r}';argv=[str(conv),'-r','ubx','-v','3.04','-f','5','-od','-os','-o',str(prefix)+'.obs','-n',str(prefix)+'.nav',str(dst)]
   assert not Path(str(prefix)+'.obs').exists(),'conversion already exists; do not silently rerun'
   with Path(str(prefix)+'.stdout.log').open('wb') as a,Path(str(prefix)+'.stderr.log').open('wb') as b:
    proc=subprocess.run(['strace','-f','-e','trace=openat,execve','-o',str(prefix)+'.syscalls.log',*argv],cwd=O,stdout=a,stderr=b,check=False)
   receipt=dict(sequence=s,receiver=r,raw_source=alias(p),ubx_file=alias(dst),frames=n,bad_checksum_or_length=bad,message_counts=dict(counts),bytes=dst.stat().st_size,ubx_sha256=sha(dst),argv=argv,returncode=proc.returncode,convbin_sha256=sha(conv));receipts.append(receipt);(O/'CONVBIN_RUNS.json').write_text(json.dumps(receipts,indent=2)+'\n')
   assert proc.returncode==0,receipt
   log(f'convbin {s} R{r} frames={n} returncode=0')
 for p in [EXT/'app/consapp/convbin/convbin.c',EXT/'app/consapp/convbin/gcc/makefile',EXT/'src/rcv/ublox.c',EXT/'src/rinex.c',EXT/'src/convrnx.c']:read(p)
 save_sources()

def parse_obs(p):
 lines=read(p).read_text().splitlines();types={};expected={};i=0;sy=None
 while 'END OF HEADER' not in lines[i]:
  l=lines[i]
  if 'SYS / # / OBS TYPES' in l:
   if l[0]!=' ':sy=l[0];expected[sy]=int(l[3:6]);types.setdefault(sy,[])
   types[sy]+=l[7:60].split()
  i+=1
 assert all(len(types[k])==n for k,n in expected.items()),p
 rows={};epochs={};i+=1
 while i<len(lines):
  line=lines[i];line_no=i+1;i+=1
  if not line.startswith('>'):continue
  f=line[1:].split();ymdhm=list(map(int,f[:5]));epoch_us=int(datetime.datetime(*ymdhm,tzinfo=datetime.timezone.utc).timestamp())*1000000+int(Decimal(f[5])*1000000);flag=int(f[6]);n=int(f[7])
  if flag not in [0,1]:i+=n;continue
  epochs[epoch_us]={'line_number':line_no,'raw_epoch_line':line}
  for _ in range(n):
   raw=lines[i];sat=raw[:3];sat_line_no=i+1;i+=1;codes=types[sat[0]];data=raw[3:];raw_lines=[raw]
   while i<len(lines) and lines[i].startswith('   '):data+=lines[i][3:];raw_lines.append(lines[i]);i+=1
   for k,code in enumerate(codes):
    token=data[k*16:(k+1)*16].ljust(16)
    if not token[:14].strip():continue
    key=(epoch_us,sat,code[1:]);q=rows.setdefault(key,dict(epoch_us=epoch_us,satellite=sat,signal=code[1:],line_number=sat_line_no,raw_epoch_line=line,raw_satellite_lines=raw_lines))
    assert code[0] not in q,(p,key,code)
    q[code[0]]=float(token[:14]);q[code[0]+'_token']=token
    if code[0]=='L':q['LLI']=int(token[14]) if token[14].strip() else 0;q['SSI']=int(token[15]) if token[15].strip() else 0
 return rows,epochs,types

def parse_nav(p):
 lines=read(p).read_text().splitlines();i=next(i for i,l in enumerate(lines) if 'END OF HEADER' in l)+1;out=[]
 while i<len(lines):
  l=lines[i]
  if not l.strip():i+=1;continue
  n=4 if l[0] in ['R','S'] else 8;out.append(dict(system=l[0],satellite=l[:3],toc=l[4:23],line_number=i+1,raw_first_line=l,raw_block_lines=lines[i:i+n]));i+=n
 return pd.DataFrame(out)

def crosscheck():
 summaries=[];epochrows=[];navrows=[];examples=[];all_details=[]
 for s in SEQ:
  for r in [1,2]:
   bridge=next(Path(p) for p in PINS if '/'+s+'__RTKLIB__' in p and p.endswith(f'/gnss{r}.obs'));conv=O/'CONVBIN'/f'{s}_R{r}.obs'
   a,ea,ta=parse_obs(bridge);b,eb,tb=parse_obs(conv);base,start,end=SEQ[s]
   def win(t):return start<=t/1e6-18-base<=end
   a={k:v for k,v in a.items() if win(k[0])};b={k:v for k,v in b.items() if win(k[0])};eaw={k:v for k,v in ea.items() if win(k)};ebw={k:v for k,v in eb.items() if win(k)}
   limits=Counter()
   def sample(category,key,x,y):
    signal=key[1][0]+':'+key[2] if len(key)>1 else 'ALL';k=(signal,category)
    if limits[k]>=20:return
    limits[k]+=1;examples.append(dict(sequence=s,receiver=r,signal=signal,category=category,rank=limits[k],key=key,bridge_source=alias(bridge),convbin_source=alias(conv),bridge=x,convbin=y))
   for side,keys,obs in [('bridge_only',set(eaw)-set(ebw),eaw),('convbin_only',set(ebw)-set(eaw),ebw)]:
    for t in sorted(keys):sample('epoch_'+side,(t,),obs[t] if side=='bridge_only' else None,obs[t] if side=='convbin_only' else None)
   epochrows.append(dict(sequence=s,receiver=r,bridge_full_epochs=len(ea),convbin_full_epochs=len(eb),bridge_window_epochs=len(eaw),convbin_window_epochs=len(ebw),common_window_epochs=len(set(eaw)&set(ebw)),bridge_only_epochs=len(set(eaw)-set(ebw)),convbin_only_epochs=len(set(ebw)-set(eaw)),bridge_source=alias(bridge),convbin_source=alias(conv)))
   detail=[]
   for key in sorted(set(a)|set(b)):
    x=a.get(key);y=b.get(key);row=dict(sequence=s,receiver=r,epoch_us=key[0],satellite=key[1],signal=key[2],system=key[1][0],observation_status='common' if x and y else 'bridge_only' if x else 'convbin_only')
    if not x or not y:sample('observation_'+row['observation_status'],key,x,y)
    for field in ['C','L','D','S']:
     xa=x.get(field) if x else None;yb=y.get(field) if y else None;row[field+'_status']='common' if xa is not None and yb is not None else 'bridge_only' if xa is not None else 'convbin_only' if yb is not None else 'neither'
     row[field+'_diff']=yb-xa if xa is not None and yb is not None else np.nan
     if row[field+'_status'] in ['bridge_only','convbin_only']:sample(field+'_'+row[field+'_status'],key,x,y)
     if field in ['C','D','S'] and np.isfinite(row[field+'_diff']) and abs(row[field+'_diff'])>1e-9:sample(field+'_nonzero_difference',key,x,y)
    if row['L_status']=='common':
     frac=float(wrap(row['L_diff']));row['phase_fractional_diff']=frac;row['phase_class']='zero' if abs(frac)<=.0005001 else 'half' if abs(abs(frac)-.5)<=.0005001 else 'other'
     if row['phase_class']!='zero':sample('phase_'+row['phase_class'],key,x,y)
     if abs(row['L_diff'])>1e-9:sample('phase_raw_nonzero',key,x,y)
     for bit in [0,1]:
      row[f'LLI_bit{bit}_different']=int(bool(x['LLI']&(1<<bit))!=bool(y['LLI']&(1<<bit)))
      if row[f'LLI_bit{bit}_different']:sample(f'LLI_bit{bit}_different',key,x,y)
     row['SSI_difference']=y['SSI']-x['SSI']
     if row['SSI_difference']:sample('SSI_nonzero_difference',key,x,y)
    detail.append(row)
   df=pd.DataFrame(detail);write(f'{s}_R{r}_RINEX_DIFFERENCES.csv.gz',df)
   for (sys,sig),g in df.groupby(['system','signal']):
    z=dict(sequence=s,receiver=r,system=sys,signal=sig,n_union=len(g),n_common=int(g.observation_status.eq('common').sum()),bridge_only=int(g.observation_status.eq('bridge_only').sum()),convbin_only=int(g.observation_status.eq('convbin_only').sum()),bridge_source=alias(bridge),convbin_source=alias(conv),detail_source=f'{s}_R{r}_RINEX_DIFFERENCES.csv.gz')
    for field in ['C','L','D','S']:
     for status in ['common','bridge_only','convbin_only']:z[field+'_'+status]=int(g[field+'_status'].eq(status).sum())
     vals=g[field+'_diff'].dropna();z[field+'_nonzero']=int((vals.abs()>1e-9).sum());z[field+'_max_abs_diff']=vals.abs().max();z[field+'_median_diff']=vals.median()
    for cat in ['zero','half','other']:z['phase_fraction_'+cat]=int(g.phase_class.eq(cat).sum()) if 'phase_class' in g else 0
    for bit in [0,1]:z[f'LLI_bit{bit}_different']=int(g.get(f'LLI_bit{bit}_different',pd.Series(dtype=float)).sum())
    z['SSI_nonzero']=int((g.get('SSI_difference',pd.Series(dtype=float)).abs()>0).sum());summaries.append(z)
   navsets={}
   for source,p in [('bridge',bridge.with_suffix('.nav')),('convbin',conv.with_suffix('.nav'))]:
    nv=parse_nav(p);write(f'{s}_R{r}_{source}_NAV_RECORDS.csv.gz',nv)
    navsets[source]={(z['satellite'],z['toc']):z for z in nv.to_dict('records')}
    for sy in ['G','R','E','C','J','S','I']:navrows.append(dict(sequence=s,receiver=r,source=source,system=sy,ephemeris_records=int(nv.system.eq(sy).sum()) if len(nv) else 0,file=alias(p)))
   for source in ['bridge','convbin']:
    other='convbin' if source=='bridge' else 'bridge';counter=Counter()
    for key in sorted(set(navsets[source])-set(navsets[other])):
     sy=key[0][0]
     if counter[sy]>=20:continue
     counter[sy]+=1;examples.append(dict(sequence=s,receiver=r,signal=sy+':NAV',category='nav_'+source+'_only',rank=counter[sy],key=key,bridge_source=alias(bridge.with_suffix('.nav')),convbin_source=alias(conv.with_suffix('.nav')),bridge=navsets['bridge'].get(key),convbin=navsets['convbin'].get(key)))
   log(f'RINEX compared {s} R{r}: epochs {len(eaw)}/{len(ebw)}')
 write('DG01R_RINEX_CROSSCHECK.csv',summaries,True);write('DG01R_RINEX_EPOCHS.csv',epochrows,True);write('DG01R_NAV_COUNTS.csv',navrows,True)
 with gzip.open(O/'RINEX_NONZERO_EXAMPLES.jsonl.gz','wt') as f:
  for x in examples:f.write(json.dumps(x,ensure_ascii=False)+'\n')
 ix=Counter((x['sequence'],x['receiver'],x['signal'],x['category']) for x in examples);write('DG01R_RINEX_EXAMPLE_INDEX.csv',[dict(sequence=k[0],receiver=k[1],signal=k[2],category=k[3],n_saved=v,source='RINEX_NONZERO_EXAMPLES.jsonl.gz') for k,v in sorted(ix.items())],True)
 save_sources();log('DONE R3 comparison')

if __name__=='__main__':
 import argparse
 p=argparse.ArgumentParser();p.add_argument('stage',choices=['convert','compare']);a=p.parse_args()
 extract_convert() if a.stage=='convert' else crosscheck()
