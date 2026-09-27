#!/usr/bin/env python3
"""R1/R2 on the immutable DG01 satellite/pivot identity set."""
from dg01r_common import *

def clock_at(d,t):
 i=int(np.searchsorted(d.itow.to_numpy(),t))
 if i<len(d) and d.itow.iloc[i]==t:return float(d.bias_ns.iloc[i])*1e-9,'exact'
 if i==0 or i==len(d):return np.nan,'missing_no_bracket'
 a,b=d.iloc[i-1],d.iloc[i]
 if b.itow-a.itow>1000:return np.nan,'missing_gap_gt1s'
 return float(a.bias_ns+(b.bias_ns-a.bias_ns)*(t-a.itow)/(b.itow-a.itow))*1e-9,'interpolated'

def geom(ep,g,sv,t,pr,r):
 rho=pr
 for _ in range(4):
  x=satellite(ep,g,sv,t,rho)
  if x is None:return np.nan
  rho=float(np.linalg.norm(x-r))
 return rho

def run(s):
 m=load(f'{s}_INTER_DETAIL.csv.gz');d=load(f'{s}_FRACTIONAL_DD_DETAIL.csv.gz');d['sequence']=s
 hp=[load(f'{s}_R{r}_hp.csv.gz').set_index('itow') for r in [1,2]]
 clocks=[load(f'{s}_R{r}_clock.csv.gz').sort_values('itow').drop_duplicates('itow') for r in [1,2]]
 ep=nav_ephemeris(s);lookup={(x.time,x.gnss,x.signal,x.sv):x for x in m.itertuples()};endpoints=set()
 for x in d.itertuples():endpoints.update([(x.time,x.gnss,x.signal,x.sv),(x.time,x.gnss,x.signal,x.pivot)])
 m['sub_disagree']=m.sub_half_1!=m.sub_half_2;m['D4_endpoint']=[(x.time,x.gnss,x.signal,x.sv) in endpoints for x in m.itertuples()]
 fields=['time','gnss','sv','signal','frequency_id','tracking_1','tracking_2','cp_valid_1','cp_valid_2','half_valid_1','half_valid_2','sub_half_1','sub_half_2','sub_disagree','D4_endpoint'];write(f'{s}_FLAGS_DETAIL.csv.gz',m[fields])
 flags=[]
 nonpivot=m.merge(d[['time','gnss','signal','sv']],on=['time','gnss','signal','sv'],how='inner',validate='one_to_one')
 for scope,data in [('all_common',m),('D4_endpoint_unique',m[m.D4_endpoint]),('D4_nonpivot',nonpivot)]:
  for key,g in data.groupby(['gnss','signal','frequency_id']):
   base=dict(sequence=s,scope=scope,gnss=key[0],signal=key[1],frequency_id=key[2],source=f'{s}_FLAGS_DETAIL.csv.gz')
   flags.append(dict(**base,kind='summary',n=len(g),sub_disagree_n=int(g.sub_disagree.sum()),sub_disagree_fraction=g.sub_disagree.mean()))
   for comb,h in g.groupby(['tracking_1','tracking_2']):flags.append(dict(**base,kind='combination',tracking_1=comb[0],tracking_2=comb[1],cpValid_1=bool(comb[0]&2),cpValid_2=bool(comb[1]&2),halfCyc_1=bool(comb[0]&4),halfCyc_2=bool(comb[1]&4),subHalfCyc_1=bool(comb[0]&8),subHalfCyc_2=bool(comb[1]&8),n=len(h),sub_disagree_n=int(h.sub_disagree.sum()),sub_disagree_fraction=h.sub_disagree.mean()))
 epochs=[];cd={}
 for t,e in m.groupby('time',sort=True):
  x=e.iloc[0];c1,a=clock_at(clocks[0],int(x.itow_1));c2,b=clock_at(clocks[1],int(x.itow_2));cd[t]=(c1,c2);epochs.append(dict(sequence=s,time=t,itow_1=x.itow_1,itow_2=x.itow_2,clk1_s=c1,clk2_s=c2,delta_clk_s=c2-c1,clock1_source=a,clock2_source=b,D4_used=t in set(d.time)))
 ec=pd.DataFrame(epochs);write(f'{s}_CLOCK_DETAIL.csv.gz',ec)
 cache={};out=[];maxerr=0.
 def endpoint(x,r1,r2,c1,c2):
  key=(x.time,x.gnss,x.signal,x.sv)
  if key in cache:return cache[key]
  g,sv=int(x.gnss),int(x.sv);X=satellite(ep,g,sv,float(x.tow_1),float(x.pseudorange_m_1));oldrho=np.linalg.norm(X-r2)-np.linalg.norm(X-r1)
  newrho=geom(ep,g,sv,x.tow_2-c2,x.pseudorange_m_2,r2)-geom(ep,g,sv,x.tow_1-c1,x.pseudorange_m_1,r1) if np.isfinite(c1+c2) else np.nan
  zerorho=geom(ep,g,sv,x.tow_2,x.pseudorange_m_2,r2)-geom(ep,g,sv,x.tow_1,x.pseudorange_m_1,r1)
  rate=(geom(ep,g,sv,x.tow_1+.05,x.pseudorange_m_1,r1)-geom(ep,g,sv,x.tow_1-.05,x.pseudorange_m_1,r1))/.1
  value=(oldrho,newrho,zerorho,rate,x.carrier_cycles_2-x.carrier_cycles_1,int(x.sub_half_2)-int(x.sub_half_1));cache[key]=value;return value
 for x in d.itertuples():
  a=lookup[(x.time,x.gnss,x.signal,x.sv)];p=lookup[(x.time,x.gnss,x.signal,x.pivot)]
  h1=hp[0].loc[a.itow_1];h2=hp[1].loc[a.itow_2];assert abs(h1.time-x.time-x.hp_time_minus_raw_s)<1e-6
  r1=h1[['x','y','z']].to_numpy(float);r2=h2[['x','y','z']].to_numpy(float);c1,c2=cd[x.time];v=endpoint(a,r1,r2,c1,c2);pv=endpoint(p,r1,r2,c1,c2);lam=299792458./x.frequency_hz;phase=v[4]-pv[4]
  r0=(v[0]-pv[0])/lam-phase;maxerr=max(maxerr,abs(r0-x.raw_cycles));r1v=(v[1]-pv[1])/lam-phase;delta_phase=.5*(v[5]-pv[5]);mismatch=bool(v[5] or pv[5])
  out.append(dict(sequence=s,time=x.time,gnss=x.gnss,signal=x.signal,frequency_hz=x.frequency_hz,sv=x.sv,pivot=x.pivot,fix_group=x.fix_group,R0=x.fractional_cycles,R1=float(wrap(r1v)),R2A=float(wrap(r1v)) if not mismatch else np.nan,R2B=float(wrap(r1v-delta_phase)),ZERO_CLOCK=float(wrap((v[2]-pv[2])/lam-phase)),clock_geometry_change_cycles=(v[1]-pv[1]-v[2]+pv[2])/lam,delta_clk_s=c2-c1,clock_first_order_abs_cycles=abs((v[3]-pv[3])*(c2-c1))/lam,sv_sub_disagree=bool(v[5]),pivot_sub_disagree=bool(pv[5]),phase_half_normalization_cycles=delta_phase))
 assert maxerr<1e-6,(s,maxerr)
 q=pd.DataFrame(out);write(f'{s}_DD_VERSIONS.csv.gz',q);rows=[]
 for scope,g in [('all_paired_RAWX',ec),('D4_used_epochs',ec[ec.D4_used])]:
  rows.append(dict(sequence=s,scope=scope,**stats(g.delta_clk_s),max_abs_s=g.delta_clk_s.abs().max(),median_ms=g.delta_clk_s.median()*1000,p05_ms=g.delta_clk_s.quantile(.05)*1000,p95_ms=g.delta_clk_s.quantile(.95)*1000,max_abs_ms=g.delta_clk_s.abs().max()*1000,n_registered=len(g),R1_missing_DD=int(q.R1.isna().sum()),max_first_order_DD_cycles=q.clock_first_order_abs_cycles.max(),max_exact_clock_geometry_cycles=q.clock_geometry_change_cycles.abs().max(),R0_identity_max_error_cycles=maxerr,source=f'{s}_CLOCK_DETAIL.csv.gz;{s}_DD_VERSIONS.csv.gz',**{f'R{r}_{mode}':int(g[f'clock{r}_source'].eq(mode).sum()) for r in [1,2] for mode in ['exact','interpolated','missing_no_bracket','missing_gap_gt1s']}))
 log(f'{s} R0 identity max_error={maxerr:.3g}, R1 finite={q.R1.notna().sum()}/{len(q)}');return q,rows,flags

def main():
 allq=[];clock=[];flags=[]
 for s in SEQ:
  q,c,f=run(s);allq.append(q);clock+=c;flags+=f
 d=pd.concat(allq,ignore_index=True);write('DD_ALL_VERSIONS.csv.gz',d);write('DG01R_CLOCK_OFFSET.csv',clock,True);write('DG01R_HALFCYC_FLAGS.csv',flags,True)
 peaks=[]
 for version in ['R0','R1','R2A','R2B','ZERO_CLOCK']:
  z=d.rename(columns={version:'fractional_cycles'});write(f'DG01R_FRACTIONAL_DD_{version}.csv',summarize(z,version),True)
  for (s,fix),g in z[(z.gnss==0)&(z.signal==3)].groupby(['sequence','fix_group']):
   a=g.fractional_cycles.dropna().to_numpy();h,_=np.histogram(a,bins=np.linspace(-.5,.5,41));peaks.append(dict(sequence=s,fix_group=fix,version=version,n=len(a),positive_edge_n=int((a>=.45).sum()),negative_edge_n=int((a<=-.45).sum()),edge_n=int((abs(a)>=.45).sum()),edge_fraction=float(np.mean(abs(a)>=.45)) if len(a) else np.nan,max_005_cycle_fraction=float(np.max(h+np.roll(h,1))/len(a)) if len(a) else np.nan,source='DD_ALL_VERSIONS.csv.gz'))
 write('DG01R_L2C_PEAKS.csv',peaks,True);save_sources();log('DONE R1 R2')
if __name__=='__main__':main()
