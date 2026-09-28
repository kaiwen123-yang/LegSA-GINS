#!/usr/bin/env python3
"""Registered DG01 diagnostics from decoded observations and existing outputs."""
from dg01_raw import *
from collections import defaultdict
import re,difflib

def stats(x):
 a=np.asarray(x,dtype=float);a=a[np.isfinite(a)]
 if not len(a):return dict(n=0,mean=np.nan,median=np.nan,p05=np.nan,p95=np.nan,std=np.nan,min=np.nan,max=np.nan)
 return dict(n=len(a),mean=float(a.mean()),median=float(np.median(a)),p05=float(np.percentile(a,5)),p95=float(np.percentile(a,95)),std=float(a.std(ddof=1)) if len(a)>1 else np.nan,min=float(a.min()),max=float(a.max()))
def inside(df,s):return df[df.time.between(SEQ[s][1],SEQ[s][2])].copy()
def nearest(t,grid):
 """Unique nearest with strictly less than local half cadence."""
 t=np.asarray(t);g=np.asarray(grid);i=np.searchsorted(g,t);a=np.clip(i-1,0,len(g)-1);b=np.clip(i,0,len(g)-1)
 da=abs(t-g[a]);db=abs(t-g[b]);j=np.where(da<db,a,b);gaps=np.diff(g);left=np.r_[np.inf,gaps];right=np.r_[gaps,np.inf];bound=np.minimum(left,right)[j]/2
 ok=(np.minimum(da,db)<bound)&((da!=db)|(a==b));return np.where(ok,j,-1)
def prepared(s,r):
 o=load(s,r,'obs').sort_values(['gnss','sv','signal','frequency_id','time']);keys=['gnss','sv','signal','frequency_id'];grp=o.groupby(keys,sort=False)
 o['lock_reset']=(o.lock_ms<grp.lock_ms.shift()).fillna(False);o['cp_overflow']=o.cp_std.eq(15);o['cp_valid']=(o.tracking.astype(int)&2)!=0;o['half_valid']=(o.tracking.astype(int)&4)!=0;o['sub_half']=(o.tracking.astype(int)&8)!=0;o['raw_event']=o.lock_reset|o.cp_overflow
 gap=grp.time.diff();o['break_arc']=(o.raw_event|~o.cp_valid|~o.half_valid|gap.gt(1)|gap.le(0)|gap.isna()|((o.receiver_status.astype(int)&2)!=0));o['arc']=o.groupby(keys).break_arc.cumsum()
 n=load(s,r,'nav').sort_values('time').drop_duplicates('itow');idx=nearest(o.time,n.time);o['itow']=np.where(idx>=0,n.itow.to_numpy()[np.maximum(idx,0)],-1)
 st=load(s,r,'sat')[['itow','gnss','sv','elevation_deg','azimuth_deg','svUsed']].drop_duplicates(['itow','gnss','sv']);o=o.merge(st,on=['itow','gnss','sv'],how='left')
 o['elev_bin']=np.floor(o.elevation_deg/10)*10;o.loc[o.elevation_deg==90,'elev_bin']=80;o['cno_bin']=np.floor(o.cno_dbhz/5)*5;o['grid']=np.rint(o.tow/.2).astype(int);o['receiver']=r;o['sequence']=s
 return o
def rinex_lli(s,r):
 p=run_dir(s,'RTKLIB')/'native/SOURCE_BACKEND'/f'gnss{r}.obs';lines=read(p).read_text().splitlines();types={};i=0;lastsys=None
 while 'END OF HEADER' not in lines[i]:
  l=lines[i]
  if 'SYS / # / OBS TYPES' in l:
   sy=l[0] if l[0]!=' ' else lastsys;lastsys=sy;types.setdefault(sy,[]).extend(l[7:60].split())
  i+=1
 out=[];i+=1
 while i<len(lines):
  l=lines[i];i+=1
  if not l.startswith('>'):continue
  f=l[1:].split();y,mo,d,hh,mm=map(int,f[:5]);ss=float(f[5]);t=datetime.datetime(y,mo,d,hh,mm,tzinfo=datetime.timezone.utc).timestamp()+ss-18-SEQ[s][0];n=int(f[7])
  for _ in range(n):
   l=lines[i];i+=1;sv=l[:3];ts=types.get(sv[0],[]);data=l[3:]
   while len(data)<16*len(ts) and i<len(lines) and lines[i].startswith('   '):data+=lines[i][3:];i+=1
   for k,code in enumerate(ts):
    v=data[16*k:16*(k+1)].ljust(16)
    if code.startswith('L') and v[:14].strip():out.append([t,sv,code,int(v[14]) if v[14].strip() else 0])
 df=pd.DataFrame(out,columns=['time','satellite','rinex_signal','lli']);df['slip_lli0']=(df.lli&1)!=0;write(f'{s}_R{r}_RINEX_LLI.csv.gz',df)
 return inside(df,s)
def nav_ephemeris(s):
 ep=defaultdict(list)
 for r in [1,2]:
  p=read(run_dir(s,'RTKLIB')/'native/SOURCE_BACKEND'/f'gnss{r}.nav');lines=p.read_text().splitlines();i=next(i for i,l in enumerate(lines) if 'END OF HEADER' in l)+1
  while i<len(lines):
   l=lines[i];sy=l[0];n=4 if sy in ['R','S'] else 8;block=lines[i:i+n];i+=n
   if sy not in ['G','E','C','J']:continue
   vals=[float(l[j:j+19].replace('D','E')) for j in [23,42,61]]
   for l in block[1:]:
    vals += [float(l[j:j+19].replace('D','E')) if l[j:j+19].strip() else 0 for j in [4,23,42,61]]
   ep[(sy,int(block[0][1:3]))].append(vals)
 return ep
def satellite(ep,g,sv,tow,pr):
 sy={0:'G',2:'E',3:'C',5:'J'}.get(g);e=ep.get((sy,sv),[])
 if not e:return None
 t=tow-pr/299792458.-(14 if sy=='C' else 0);wrap=lambda x:(x+302400)%604800-302400
 v=min(e,key=lambda x:abs(wrap(t-x[11])))
 if abs(wrap(t-v[11]))>7200:return None
 mu=3.986005e14 if sy in ['G','J'] else 3.986004418e14;om=7.2921151467e-5;A=v[10]**2;tk=wrap(t-v[11]);ecc=v[8];M=v[6]+(math.sqrt(mu/A**3)+v[5])*tk;E=M
 for _ in range(15):E=M+ecc*math.sin(E)
 phi=math.atan2(math.sqrt(1-ecc*ecc)*math.sin(E),math.cos(E)-ecc)+v[17];c=math.cos(2*phi);sn=math.sin(2*phi);u=phi+v[7]*c+v[9]*sn;rr=A*(1-ecc*math.cos(E))+v[16]*c+v[4]*sn;inc=v[15]+v[19]*tk+v[12]*c+v[14]*sn
 geo=sy=='C' and (sv<=5 or sv>=59);Omega=v[13]+(v[18] if geo else v[18]-om)*tk-om*v[11];x=rr*math.cos(u);y=rr*math.sin(u);X=x*math.cos(Omega)-y*math.cos(inc)*math.sin(Omega);Y=x*math.sin(Omega)+y*math.cos(inc)*math.cos(Omega);Z=y*math.sin(inc)
 if geo:
  a=om*tk;co=math.cos(a);si=math.sin(a);c5=math.cos(math.radians(-5));s5=math.sin(math.radians(-5));X,Y,Z=X*co+Y*si*c5+Z*si*s5,-X*si+Y*co*c5+Z*co*s5,-Y*s5+Z*c5
 angle=om*pr/299792458.;return np.array([math.cos(angle)*X+math.sin(angle)*Y,-math.sin(angle)*X+math.cos(angle)*Y,Z])
def longest(t,condition,end):
 best=run=0.;last=None
 for i,(x,v) in enumerate(zip(t,condition)):
  if last is None or x-last>1 or not v:run=0
  dt=min(float(t[i+1]-x) if i+1<len(t) else .2, .2,end-x)
  if v:run+=max(dt,0);best=max(best,run)
  last=x
 return best
def signal_quality(s,r,o):
 a=inside(o,s);rows=[];duration=SEQ[s][2]-SEQ[s][1];src=f'{s}_R{r}_obs.csv.gz'
 for key,g in a.groupby(['gnss','signal','frequency_id']):
  fields=dict(sequence=s,receiver=r,gnss=int(key[0]),signal=int(key[1]),frequency_id=int(key[2]),scope='signal',elevation_bin=np.nan,cno_bin=np.nan)
  for metric,col in [('cno_dbhz','cno_dbhz'),('tracked_sv_per_epoch','sv')]:
   vals=g[col] if metric=='cno_dbhz' else g.groupby('time').sv.nunique();rows.append(dict(**fields,metric=metric,**stats(vals),source=src))
  for metric in ['lock_reset','cp_overflow','raw_event']:
   n=int(g[metric].sum());rows.append(dict(**fields,metric=metric,n=len(g),event_count=n,per_window_minute=n/(duration/60),exposure_minutes=g.groupby('sv').time.nunique().sum()*.2/60,source=src))
  for (el,cn),h in g.groupby(['elev_bin','cno_bin'],dropna=False):rows.append(dict(**dict(fields,scope='cno_elevation_bin',elevation_bin=el,cno_bin=cn),metric='cno_dbhz',**stats(h.cno_dbhz),source=src))
 for kind,col in [('nav','hAcc_m'),('hp','pAcc_m')]:rows.append(dict(sequence=s,receiver=r,scope='receiver',metric=col,**stats(inside(load(s,r,kind),s)[col]),source=f'{s}_R{r}_{kind}.csv.gz'))
 pv=inside(load(s,r,'nav'),s)
 for q in [0,1,2,3]:rows.append(dict(sequence=s,receiver=r,scope='NAV_PVT',metric='carrSoln_'+str(q),n=len(pv),event_count=int(pv.carrSoln.eq(q).sum()),fraction=pv.carrSoln.eq(q).mean(),source=f'{s}_R{r}_nav.csv.gz'))
 navsig=inside(load(s,r,'sig'),s);navsig['carrier_and_correction']=navsig.crUsed&navsig.crCorrUsed
 for sys,g in navsig.groupby('gnss'):
  for flag in ['prUsed','crUsed','crCorrUsed','carrier_and_correction']:
   counts=g[g[flag]].groupby('time').sv.nunique().reindex(g.time.unique(),fill_value=0);rows.append(dict(sequence=s,receiver=r,gnss=int(sys),scope='NAV_SIG',metric=flag+'_satellites',**stats(counts),source=f'{s}_R{r}_sig.csv.gz'))
 for sys,g in a.groupby('gnss'):rows.append(dict(sequence=s,receiver=r,gnss=int(sys),scope='system',metric='tracked_satellites',**stats(g.groupby('time').sv.nunique().reindex(a.time.unique(),fill_value=0)),source=src))
 lli=rinex_lli(s,r)
 for (sy,code),g in lli.groupby([lli.satellite.str[0],'rinex_signal']):rows.append(dict(sequence=s,receiver=r,gnss=sy,signal=code,scope='RINEX',metric='LLI_bit0',n=len(g),event_count=int(g.slip_lli0.sum()),per_window_minute=g.slip_lli0.sum()/(duration/60),source=f'{s}_R{r}_RINEX_LLI.csv.gz'))
 return rows
def cmc(s,r,o):
 a=inside(o,s);a=a[a.cp_valid&a.half_valid&~a.cp_overflow&np.isfinite(a.frequency_hz)].copy();a['L']=a.carrier_cycles*299792458/a.frequency_hz;rows=[]
 others=defaultdict(list)
 for x in a.sort_values(['signal','frequency_id']).itertuples():others[(x.time,x.gnss,x.sv)].append(x)
 for x in a.itertuples():
  pool=others[(x.time,x.gnss,x.sv)];j=next((y for y in pool if y.frequency_hz!=x.frequency_hz),None);metric='single_frequency_linear';value=x.pseudorange_m-x.L;secondary=-1;arc2=-1
  if j is not None:
   y=j;gamma=x.frequency_hz**2/y.frequency_hz**2;value=x.pseudorange_m-(1+2/(gamma-1))*x.L+2/(gamma-1)*y.L;metric='dual_frequency_MP';secondary=int(y.signal);arc2=int(y.arc)
  rows.append([x.time,x.gnss,x.sv,x.signal,x.frequency_id,int(x.arc),secondary,arc2,metric,value,x.elevation_deg,x.elev_bin,'primary' if s=='BY2O' and 3369.94<=x.time<=3411.95 else 'outside'])
 d=pd.DataFrame(rows,columns=['time','gnss','sv','signal','frequency_id','arc','second_signal','second_arc','proxy','value','elevation_deg','elev_bin','segment']);d['block60']=np.floor((d.time-SEQ[s][1])/60);d['residual_m']=np.nan
 group=['gnss','sv','signal','frequency_id','arc','second_signal','second_arc','proxy']
 for key,g in d.groupby(group):
  if key[-1]=='dual_frequency_MP':
   if len(g)>=2:d.loc[g.index,'residual_m']=g.value-g.value.mean()
  else:
   for _,h in g.groupby('block60'):
    if len(h)<2:continue
    t=h.time.to_numpy();design=np.column_stack([np.ones(len(t)),t-t.mean()]);d.loc[h.index,'residual_m']=h.value.to_numpy()-design@np.linalg.lstsq(design,h.value.to_numpy(),rcond=None)[0]
 write(f'{s}_R{r}_CMC_DETAIL.csv.gz',d);out=[]
 for key,g in d.groupby(['gnss','sv','signal','frequency_id','proxy','elev_bin','segment'],dropna=False):out.append(dict(sequence=s,receiver=r,**dict(zip(['gnss','sv','signal','frequency_id','proxy','elevation_bin','segment'],key)),**stats(g.residual_m),source=f'{s}_R{r}_CMC_DETAIL.csv.gz'))
 return out
def joint_nav(s):
 a=load(s,1,'nav');b=load(s,2,'nav');j=a.merge(b,on='itow',suffixes=('_1','_2'),validate='one_to_one');j['time']=j.time_1;j=inside(j,s).sort_values('time');j['both_fixed']=(j.carrSoln_1==2)&(j.carrSoln_2==2);j['one_fixed']=(j.carrSoln_1==2)^(j.carrSoln_2==2);j['neither_fixed']=(j.carrSoln_1!=2)&(j.carrSoln_2!=2)
 p=C/'stages/CLEAN7_T5A_HEADING_SENSITIVITY/T5A_R/02_PROVIDER_TABLES'/s/'R5/T5A.gnss';v=pd.read_csv(read(p),sep=r'\s+',header=None,usecols=[0,17],names=['time','yaw_valid']);v['key']=v.time.round(6);j['key']=j.time.round(6);j=j.merge(v[['key','yaw_valid']],on='key',how='left',validate='one_to_one');j['yaw_agree']=j.yaw_valid.eq(j.both_fixed.astype(int));j['sequence']=s
 rows=[]
 for field in ['both_fixed','one_fixed','neither_fixed']:
  rows.append(dict(sequence=s,scope='fix_joint',metric=field,n=len(j),event_count=int(j[field].sum()),fraction=j[field].mean(),longest_s=longest(j.time.to_numpy(),j[field].to_numpy(),SEQ[s][2]),source=f'{s}_FIX_DETAIL.csv.gz'))
 rows.append(dict(sequence=s,scope='yaw_valid',metric='agreement',n=int(j.yaw_valid.notna().sum()),event_count=int(j[j.yaw_valid.notna()].yaw_agree.sum()),fraction=j[j.yaw_valid.notna()].yaw_agree.mean(),missing=int(j.yaw_valid.isna().sum()),source=alias(p)))
 write(f'{s}_FIX_DETAIL.csv.gz',j);return j,rows
def fractional(s,merged):
 hp1=load(s,1,'hp');hp2=load(s,2,'hp');nav1=load(s,1,'nav');nav2=load(s,2,'nav');h=hp1.merge(hp2,on='itow',suffixes=('_1','_2'));h=h.merge(nav1[['itow','carrSoln']],on='itow').rename(columns={'carrSoln':'fix1'}).merge(nav2[['itow','carrSoln']],on='itow').rename(columns={'carrSoln':'fix2'}).sort_values('time_1');ep=nav_ephemeris(s);out=[];miss=defaultdict(int)
 for _,epoch in merged.groupby('grid'):
  t=float(epoch.time_1.iloc[0]);idx=nearest([t],h.time_1)[0]
  if idx<0:miss['no_common_HP_half_grid']+=len(epoch);continue
  row=h.iloc[idx]
  if not(row.valid_1 and row.valid_2):miss['HP_invalid']+=len(epoch);continue
  r1=row[['x_1','y_1','z_1']].to_numpy(float);r2=row[['x_2','y_2','z_2']].to_numpy(float);valid=epoch.cp_valid_1&epoch.cp_valid_2&epoch.half_valid_1&epoch.half_valid_2&~epoch.cp_overflow_1&~epoch.cp_overflow_2;miss['phase_invalid']+=int((~valid).sum());ee=epoch[valid]
  for key,group in ee.groupby(['gnss','signal','frequency_hz_1']):
   entries=[]
   for z in group.itertuples():
    X=satellite(ep,int(z.gnss),int(z.sv),float(z.tow_1),float(z.pseudorange_m_1))
    if X is None:miss['no_Kepler_ephemeris_or_FDMA']+=1;continue
    rho=np.linalg.norm(X-r2)-np.linalg.norm(X-r1);phase=z.carrier_cycles_2-z.carrier_cycles_1;el=min(z.elevation_deg_1,z.elevation_deg_2);entries.append((z.sv,rho,phase,el))
   if len(entries)<2:miss['no_same_wavelength_pivot']+=len(entries);continue
   pivot=sorted(entries,key=lambda x:(-x[3] if np.isfinite(x[3]) else np.inf,x[0]))[0];lam=299792458/key[2];fix='both_fixed' if row.fix1==2 and row.fix2==2 else 'other'
   for sv,rho,phase,el in entries:
    if sv==pivot[0]:continue
    x=(rho-pivot[1])/lam-(phase-pivot[2]);wr=x-np.ceil(x-.5);out.append([t,*key,sv,pivot[0],fix,x,wr,abs(wr),row.time_1-t,el])
 d=pd.DataFrame(out,columns=['time','gnss','signal','frequency_hz','sv','pivot','fix_group','raw_cycles','fractional_cycles','abs_cycles','hp_time_minus_raw_s','elevation_deg']);write(f'{s}_FRACTIONAL_DD_DETAIL.csv.gz',d);summary=[]
 for key,g in d.groupby(['gnss','signal','frequency_hz','fix_group']):
  a=g.fractional_cycles.to_numpy();z=np.mean(np.exp(2j*np.pi*a));summary.append(dict(sequence=s,**dict(zip(['gnss','signal','frequency_hz','fix_group'],key)),**stats(a),p95_abs_cycles=np.percentile(abs(a),95),frac_abs_gt025=float(np.mean(abs(a)>.25)),circular_mean_cycles=np.angle(z)/(2*np.pi),circular_sd_cycles=np.sqrt(-2*np.log(max(abs(z),1e-15)))/(2*np.pi),source=f'{s}_FRACTIONAL_DD_DETAIL.csv.gz'))
 bands=[];d['block20']=np.floor((d.time-SEQ[s][1])/20)
 for key,g in d.groupby(['gnss','signal','fix_group','sv','pivot','block20']):
  a=g.fractional_cycles.to_numpy();z=np.mean(np.exp(2j*np.pi*a));bands.append(dict(sequence=s,**dict(zip(['gnss','signal','fix_group','sv','pivot','block20'],key)),n=len(a),median=float(np.median(a)),circular_mean=np.angle(z)/(2*np.pi),circular_sd=np.sqrt(-2*np.log(max(abs(z),1e-15)))/(2*np.pi)))
 write(f'{s}_FRACTIONAL_STABILITY.csv.gz',bands);return summary,dict(miss)
def inter_receiver(s,a,b):
 keys=['grid','gnss','sv','signal','frequency_id'];a=inside(a,s);b=inside(b,s);j=a.merge(b,on=keys,suffixes=('_1','_2'),validate='one_to_one');j['time']=j.time_1;j['tow_delta_s']=j.tow_2-j.tow_1;j['cno_delta_dbhz']=j.cno_dbhz_2-j.cno_dbhz_1
 rows=[]
 epochs=a[['grid','tow','time']].drop_duplicates().merge(b[['grid','tow','time']].drop_duplicates(),on='grid',suffixes=('_1','_2'),validate='one_to_one');rows.append(dict(sequence=s,scope='paired_epochs',metric='rcvTow_R2_minus_R1_s',**stats(epochs.tow_2-epochs.tow_1),unpaired_R1=a.grid.nunique()-len(epochs),unpaired_R2=b.grid.nunique()-len(epochs),source=f'{s}_INTER_DETAIL.csv.gz'))
 for (gnss,sig,fr),g in j.groupby(['gnss','signal','frequency_id']):
  fields=dict(sequence=s,gnss=gnss,signal=sig,frequency_id=fr,scope='common_signal');rows.append(dict(**fields,metric='CNO_R2_minus_R1',**stats(g.cno_delta_dbhz),source=f'{s}_INTER_DETAIL.csv.gz'))
  for metric in ['lock_reset','cp_overflow','raw_event']:
   union=int((g[metric+'_1']|g[metric+'_2']).sum());both=int((g[metric+'_1']&g[metric+'_2']).sum());rows.append(dict(**fields,metric=metric+'_simultaneous',n=len(g),union_count=union,both_count=both,fraction=both/union if union else np.nan,source=f'{s}_INTER_DETAIL.csv.gz'))
 for gnss,g in j.groupby('gnss'):rows.append(dict(sequence=s,gnss=gnss,scope='common_satellites',metric='count_per_epoch',**stats(g.groupby('grid').sv.nunique()),source=f'{s}_INTER_DETAIL.csv.gz'))
 rows.append(dict(sequence=s,scope='common_satellites_all',metric='count_per_epoch',**stats(j[['grid','gnss','sv']].drop_duplicates().groupby('grid').size().reindex(epochs.grid,fill_value=0)),source=f'{s}_INTER_DETAIL.csv.gz'))
 write(f'{s}_INTER_DETAIL.csv.gz',j);return j,rows
def relpos(s,r):
 d=inside(load(s,r,'rel'),s);rows=[]
 for metric in ['length_m','length_minus_035_m']:
  rows.append(dict(sequence=s,receiver=r,metric=metric,**stats(d[metric]),max_abs=float(d[metric].abs().max()),source=f'{s}_R{r}_rel.csv.gz'))
 for q in [0,1,2,3]:rows.append(dict(sequence=s,receiver=r,metric='carrSoln_'+str(q),n=len(d),count=int(d.carrSoln.eq(q).sum()),fraction=d.carrSoln.eq(q).mean(),source=f'{s}_R{r}_rel.csv.gz'))
 for metric in ['heading_valid','position_valid']:rows.append(dict(sequence=s,receiver=r,metric=metric,n=len(d),count=int(d[metric].sum()),fraction=d[metric].mean(),source=f'{s}_R{r}_rel.csv.gz'))
 for ref,g in d.groupby('ref_station'):rows.append(dict(sequence=s,receiver=r,metric='reference_station_id',value=ref,n=len(g),source=f'{s}_R{r}_rel.csv.gz'))
 return rows
def main():
 log('START D2-D5');sq=[];fix=[];inter=[];dd=[];cm=[];rel=[];missing={}
 for s in SEQ:
  a=prepared(s,1);b=prepared(s,2)
  for r,o in [(1,a),(2,b)]:
   sq+=signal_quality(s,r,o);cm+=cmc(s,r,o);rel+=relpos(s,r);log(f'SIGNAL CMC {s} R{r}')
  j,rows=joint_nav(s);fix+=rows;m,rows=inter_receiver(s,a,b);inter+=rows;rows,mis=fractional(s,m);dd+=rows;missing[s]=mis;log('DD '+s)
 for name,data in [('DG01_SIGNAL_QUALITY.csv',sq),('DG01_FIX_STATUS_TIMELINE.csv',fix),('DG01_INTER_RECEIVER.csv',inter),('DG01_FRACTIONAL_DD.csv',dd),('DG01_CMC.csv',cm),('DG01_RELPOSNED.csv',rel)]:write(name,data,True)
 (O/'DD_UNAVAILABLE.json').write_text(json.dumps(missing,indent=2)+'\n');save_sources();log('DONE D2-D5')
if __name__=='__main__':main()
