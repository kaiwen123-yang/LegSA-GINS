#!/usr/bin/env python3
"""Read existing RTKLIB configurations/solutions and method validity only."""
from dg01_analysis import *
EXT=Path(CFG['hx02_external_root'])/'RTKLIB'
MANUAL='https://www.rtklib.com/prog/manual_2.4.2.pdf'
COMMENTS={
'pos1-posmode':'Moving-base selects an epoch-wise base SPP and relative solution; matches manual E.7(7).',
'pos1-elmask':'Elevation mask; manual documents purpose but no universal platform-optimal value.',
'pos1-snrmask':'Legacy prefix: options.c searchopt uses substring matching, so this resolves to first key pos1-snrmask_r, NOT an unknown-key rejection. Value 0 disables rover mask; base mask defaults off.',
'pos1-snrmask_r':'Explicit rover enable switch; zero/off disables mask.',
'pos1-snrmask_b':'Explicit base enable switch; default off.',
'pos1-snrmask_L1':'No effective threshold while enable switches off.',
'pos1-snrmask_L2':'No effective threshold while enable switches off.',
'pos1-snrmask_L5':'No effective threshold while enable switches off.',
'pos1-navsys':'33 = GPS(1) + BeiDou(32). GLONASS is excluded despite being tracked by receivers.',
'pos1-frequency':'Two frequencies requested; not all tracked signals/systems are used.',
'pos1-dynamics':'Off: no dynamic motion model enabled; no universal manual requirement to turn on for this platform.',
'pos2-armode':'Continuous: ambiguities persist between epochs; this is not fix-and-hold.',
'pos2-gloarmode':'Off, and GLONASS is not selected by navsys; cannot attribute these solution results to GLONASS AR.',
'pos2-bdsarmode':'BeiDou ambiguity resolution enabled.',
'pos2-arthres':'Ratio validation threshold. No data-tuned alternative proposed.',
'pos2-arlockcnt':'Minimum lock count for ambiguity eligibility; explicit zero.',
'pos2-arminfix':'Consecutive fixed count used by hold logic; not proof of hold under continuous AR.',
'pos2-arelmask':'Ambiguity fixing elevation mask; no data-tuned change.',
'pos2-elmaskhold':'Hold elevation mask; default zero, hold requires corresponding AR mode.',
'pos2-baselen':'Positive prescribed baseline activates the moving-base constraint path; rtkpos.c constbl may skip each update for its nonlinearity/covariance check.',
'pos2-basesig':'Constraint standard deviation in metres. It is configured, not independently surveyed by this task.',
'pos2-rejionno':'Innovation rejection threshold; retains existing value.',
'pos2-maxage':'Maximum differential age; not the measured epoch separation. Retain value without optimization.',
'out-solstatic':'all requests all static output epochs; this is a moving-base run.',
'out-outstat':'off: residual/state log unavailable from this setting; suggest residual logging only in a separately authorized future run.',
'ant2-postype':'single: initial base position from SPP; moving-base estimates base position each epoch.'}
DEFAULT={'pos1-snrmask_r':'off','pos1-snrmask_b':'off','pos1-snrmask_L1':'0,0,0,0,0,0,0,0,0','pos1-snrmask_L2':'0,0,0,0,0,0,0,0,0','pos1-snrmask_L5':'0,0,0,0,0,0,0,0,0','pos2-elmaskhold':'0'}
def audit():
 for path in [EXT/'src/options.c',EXT/'src/rtkpos.c',EXT/'src/rtkcmn.c']:read(path)
 rows=[];diffs=[]
 for s in SEQ:
  p=read(run_dir(s,'RTKLIB')/'native/RTKLIB_UNMODIFIED_MOVING_BASE.conf');txt=p.read_text();pairs={l.split('=',1)[0].strip():l.split('=',1)[1].split('#')[0].strip() for l in txt.splitlines() if '=' in l and not l.startswith('#')}
  for key,note in COMMENTS.items():
   value=pairs.get(key,DEFAULT.get(key,'UNAVAILABLE'));origin='explicit' if key in pairs else '2.4.3 source default'
   if key=='pos1-snrmask_r' and 'pos1-snrmask' in pairs:value=pairs['pos1-snrmask'];origin='legacy prefix resolves here'
   rows.append(dict(sequence=s,option=key,recorded_value=pairs.get(key,'ABSENT'),effective_value=value,origin=origin,comparison=note,source=alias(p),manual=MANUAL,source_code='RTKLIB/src/options.c;rtkpos.c;rtkcmn.c'))
  changed=re.sub(r'^pos1-snrmask\s*=.*$', 'pos1-snrmask_r    =off\npos1-snrmask_b    =off',txt,flags=re.M)
  changed=re.sub(r'^out-outstat\s*=.*$','out-outstat        =residual',changed,flags=re.M)
  if 'pos2-elmaskhold' not in pairs:changed+='pos2-elmaskhold    =0\n'
  diffs+=list(difflib.unified_diff(txt.splitlines(True),changed.splitlines(True),fromfile=s+'/recorded.conf',tofile=s+'/SUGGESTED_NOT_EXECUTED.conf'))
 write('DG01_RTKLIB_CONFIG_AUDIT.csv',rows,True)
 header='# Recommendations only; NOT executed. No numerical tuning.\n# Explicit equivalent SNR switches and hold default; enable residual log for a future separately authorized run.\n# Keep baseline length/sigma, AR ratio, constellations and dynamics unchanged.\n# Baseline constraint is configured; execution frequency cannot be recovered without diagnostics.\n'
 (R/'RECOMMENDED_RTKLIB_MOVINGBASE_CONFIG.diff').write_text(header+''.join(diffs))
def motion(s):
 n=load(s,1,'nav').sort_values('time');dt=n.time.diff();rate=((n.course_deg.diff()+180)%360-180)/dt;n['course_rate_degps']=rate.where(dt.gt(0)&dt.le(1));n['motion']=np.where(n.speed_mps<.2,'low_speed',np.where(n.course_rate_degps.isna(),'unknown',np.where(abs(n.course_rate_degps)>10,'course_turning','translating')));return n
def outcomes():
 rows=[];possummary=[];detail=[]
 for s in SEQ:
  n=motion(s);fix=pd.read_csv(O/f'{s}_FIX_DETAIL.csv.gz');base,start,end=SEQ[s]
  for method in ['EXT01','EXT02','EXT03','EXT04','RTKLIB']:
   for p in sorted((run_dir(s,method)/'native/HX02_HEADING_TABLES').glob('*.csv')):
    d=pd.read_csv(read(p));d['time']=d.time_unix_s-base;d=inside(d,s);idx=nearest(d.time,n.time);d['motion']=[n.motion.iloc[i] if i>=0 else 'unknown' for i in idx];d['sequence']=s;d['method']=p.stem.replace('HX02_HEADING_TABLE_','');d['block20']=np.floor((d.time-start)/20)
    for label,g in d.groupby('motion'):rows.append(dict(sequence=s,method=d.method.iloc[0],grouping='motion',group=label,n=len(g),valid_n=int(g.valid.sum()),valid_fraction=g.valid.mean(),source=alias(p)))
    for block,g in d.groupby('block20'):rows.append(dict(sequence=s,method=d.method.iloc[0],grouping='time20s',group=str(int(block)),n=len(g),valid_n=int(g.valid.sum()),valid_fraction=g.valid.mean(),source=alias(p)))
    rows.append(dict(sequence=s,method=d.method.iloc[0],grouping='full',group='all',n=len(d),valid_n=int(d.valid.sum()),valid_fraction=d.valid.mean(),source=alias(p)));detail.append(d)
  p=read(run_dir(s,'RTKLIB')/'native/RTKLIB_UNMODIFIED_MOVING_BASE.pos');raw=[]
  for line in p.read_text().splitlines():
   if not line.strip() or line.startswith('%'):continue
   x=line.split(',');raw.append([utc(int(x[0]),float(x[1]))-base,int(x[5]),float(x[13]),float(x[14])])
  d=pd.DataFrame(raw,columns=['time','Q','age_s','ratio']);d=inside(d,s);idx=nearest(d.time,fix.time);d['nav_matched']=idx>=0;d['both_fixed']=[bool(fix.both_fixed.iloc[i]) if i>=0 else False for i in idx];d['sequence']=s
  for q in sorted(set([1,2,5])|set(d.Q)):
   g=d[d.Q==q];matched=g[g.nav_matched];possummary.append(dict(sequence=s,Q=q,n_pos=len(d),n_Q=len(g),fraction_Q=len(g)/len(d) if len(d) else np.nan,n_nav_matched=len(matched),both_fixed_n=int(matched.both_fixed.sum()),both_fixed_fraction=matched.both_fixed.mean(),source=alias(p)))
  write(f'{s}_RTKLIB_POS_DETAIL.csv.gz',d)
 write('DG01_VALIDITY_MOTION.csv',rows,True);write('DG01_RTKLIB_Q_OVERLAP.csv',possummary,True);write('METHOD_VALIDITY_DETAIL.csv.gz',pd.concat(detail,ignore_index=True))
def main():
 log('START configuration and existing validity audit');audit();outcomes();save_sources();log('DONE D6-D7')
if __name__=='__main__':main()
