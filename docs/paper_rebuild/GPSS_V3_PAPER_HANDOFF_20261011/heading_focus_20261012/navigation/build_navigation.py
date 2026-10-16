"""Heading-first figures from saved outputs; no estimator/evaluator execution."""
from pathlib import Path
import json,sys,subprocess,shutil
import numpy as np,pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Rectangle
from matplotlib.ticker import MaxNLocator
from PIL import Image

ROOT=Path('/mnt/g/LegSA-GINS-project');OUT=Path(__file__).resolve().parent
NAV=ROOT/'V3五问题论文组图_20261011/navigation/data'
OLD=ROOT/'V3论文组图_20261008/redesign_20261009/figures/data'
REPO=Path('/home/kaiwen/research/LegSA-GINS-WORKTREES/audit-code-xbpg-20261001')
POSE=REPO/'docs/paper_rebuild/GPSS_V3_FIGURES_20261008/redesign_20261009/data'
for p in ['data','preview','qa']:(OUT/p).mkdir(exist_ok=True)
SEQ=['BY2','BY2H','BY2O'];START={'BY2':66,'BY2H':413,'BY2O':3186};DUR={'BY2':274,'BY2H':270,'BY2O':377}
SCENE={'BY2':'Nominal walking','BY2H':'Large body motion','BY2O':'Antenna obstruction'}
COL={'F04':'#0072B2','LC01':'#D55E00','LC01-S':'#D55E00','EXT05C':'#8B6D9C','EXT05C-S':'#8B6D9C','OISAM':'#009E73','LC01-BR':'#C19B29'}
LS={'F04':'-','LC01':'--','LC01-S':':','EXT05C':'--','EXT05C-S':':','OISAM':'-.','LC01-BR':'-.'}
NAME={'F04':'LegSA-GINS','LC01':'Dual-pos. IEKF (LIT)','LC01-S':'Dual-pos. IEKF (cal.)','EXT05C':'Single-pos. IEKF (LIT)','EXT05C-S':'Single-pos. IEKF (cal.)','OISAM':'OiSAM (reinitialized)','LC01-BR':'Baseline-retaining IEKF'}
METHODS=['F04','LC01','LC01-S','EXT05C','EXT05C-S','OISAM']
plt.rcParams.update({'font.family':'sans-serif','font.sans-serif':['Arial','Liberation Sans','DejaVu Sans'],'font.size':8,'axes.labelsize':8,'axes.titlesize':8.5,'xtick.labelsize':8,'ytick.labelsize':8,'legend.fontsize':8,'legend.frameon':False,'axes.spines.top':False,'axes.spines.right':False,'axes.linewidth':.6,'xtick.direction':'out','ytick.direction':'out','xtick.major.size':2.5,'ytick.major.size':2.5,'pdf.fonttype':42,'svg.fonttype':'none','path.simplify':False,'savefig.facecolor':'white'})
SOURCES=[];PROFILE=[]
def read(p):
 p=Path(p);d=pd.read_csv(p);SOURCES.append(str(p));PROFILE.append({'path':str(p),'rows':len(d),'columns':list(d),'missing':d.isna().sum().to_dict()});return d
def line(ax,t,y,gap=.101,**kw):
 t=np.asarray(t);y=np.asarray(y)
 for ids in np.split(np.arange(len(t)),np.flatnonzero(np.diff(t)>gap)+1):
  if len(ids):ax.plot(t[ids],y[ids],**kw)
def panel(ax,k,title):ax.set_title(f'({k}) {title}',loc='left',pad=5)
def tidy(ax,n=4):
 ax.xaxis.set_major_locator(MaxNLocator(n));ax.yaxis.set_major_locator(MaxNLocator(n));ax.tick_params(pad=2)
def export(fig,name,meta):
 fig.canvas.draw();fig.savefig(OUT/(name+'.pdf'));fig.savefig(OUT/(name+'.svg'));fig.savefig(OUT/(name+'.png'),dpi=600)
 fig.savefig(OUT/(name+'.tiff'),dpi=600,pil_kwargs={'compression':'tiff_lzw'})
 fig.savefig(OUT/'preview'/(name+'.png'),dpi=300)
 Image.open(OUT/'preview'/(name+'.png')).convert('L').save(OUT/'preview'/(name+'_gray.png'))
 scripts=Path('/mnt/c/Users/ykw/.codex/skills/nature-figure/scripts')
 qa={}
 for tag,args in [('text',['audit_pdf_text.py',str(OUT/(name+'.pdf')),'--min-pt','8','--json']),('collisions',['audit_figure_collisions.py',str(OUT/(name+'.pdf')),'--json-out',str(OUT/'qa'/(name+'.collisions.json'))])]:
  r=subprocess.run([sys.executable,str(scripts/args[0]),*args[1:]],capture_output=True,text=True);(OUT/'qa'/(name+'.'+tag+'.log')).write_text(r.stdout+r.stderr);qa[tag]=r.returncode
 meta.update({'width_mm':174,'height_mm':fig.get_figheight()*25.4,'min_font_pt':8,'source_paths':sorted(set(SOURCES)),'new_solver_evaluator_provider_calls':0,'frozen_v3':'7d43b9af26120ed5dde21f53e515386361072ba6','audits':qa,'visual_review':'PENDING'})
 (OUT/(name+'.json')).write_text(json.dumps(meta,ensure_ascii=False,indent=2));plt.close(fig);print(name,qa,flush=True)
def nearest(d,targets,key='time',tol=.005):
 t=d[key].to_numpy();ix=np.searchsorted(t,targets);a=np.clip(ix-1,0,len(t)-1);b=np.clip(ix,0,len(t)-1);ids=np.where(np.abs(t[a]-targets)<=np.abs(t[b]-targets),a,b)
 return ids,np.abs(t[ids]-targets)<=tol,np.abs(t[ids]-targets)

def fig3():
 # Turn selection uses ONLY reference pose, and is frozen before loading errors.
 events=[];poses={}
 for s in SEQ:
  d=read(POSE/(s+'_display_pose.csv.gz'));poses[s]=d;t=d.time_s.to_numpy();h=np.rad2deg(np.unwrap(np.deg2rad(d.heading_truth_ned_deg)));xy=d[['east_truth_m','north_truth_m']].to_numpy()
  if s!='BY2O':
   for lo in np.arange(START[s]+10,t[-1]-30,5):
    a=np.searchsorted(t,lo);b=np.searchsorted(t,lo+20);turn=abs(h[b]-h[a]);dist=np.linalg.norm(xy[b]-xy[a])
    if turn>=60 and dist>=2:break
   hi=lo+20;label='Reference-confirmed turn';rule='First 20-s window on a 5-s grid after initial 10s with absolute net reference heading change >=60 degrees and endpoint displacement >=2m; no estimated errors used.'
   active=[lo-START[s],hi-START[s]]
  else:
   lo=START[s]+173.94;hi=START[s]+235.95;label='First registered obstruction';rule='Registered first obstruction [183.94,225.95]s with 10s before and after; source prepare_external.py.';active=[183.94,225.95];a=np.searchsorted(t,lo);b=np.searchsorted(t,hi);turn=abs(h[b]-h[a]);dist=np.linalg.norm(xy[b]-xy[a])
  events.append({'sequence':s,'label':label,'start_s':float(lo),'end_s':float(hi),'elapsed_start_s':float(lo-START[s]),'elapsed_end_s':float(hi-START[s]),'active_elapsed_start_s':active[0],'active_elapsed_end_s':active[1],'net_reference_turn_deg':float(turn),'endpoint_displacement_m':float(dist),'selection':rule})
 pd.DataFrame(events).to_csv(OUT/'data/F03_EVENT_WINDOWS.csv',index=False)
 fig=plt.figure(figsize=(174/25.4,205/25.4));outer=fig.add_gridspec(3,2,width_ratios=[1,1.45],left=.095,right=.985,bottom=.07,top=.915,wspace=.43,hspace=.58)
 for row,(s,e) in enumerate(zip(SEQ,events)):
  d=poses[s];z=d[d.time_s.between(e['start_s'],e['end_s'])].copy();rel=z.time_s-START[s]
  ax=fig.add_subplot(outer[row,0]);origin=z[['east_truth_m','north_truth_m']].iloc[0].to_numpy()
  for key,c,ls,lw in [('truth','#333333','--',1.0),('legsa',COL['F04'],'-',.9)]:
   xx=z['east_'+key+'_m'].to_numpy()-origin[0];yy=z['north_'+key+'_m'].to_numpy()-origin[1]
   # Break spatial path at native time gaps.
   for ids in np.split(np.arange(len(z)),np.flatnonzero(np.diff(z.time_s)>.101)+1):
    if len(ids):ax.plot(xx[ids],yy[ids],color=c,ls=ls,lw=lw)
   n=5 if s!='BY2O' else 4;tt=np.linspace(z.time_s.iloc[0]+1,z.time_s.iloc[-1]-1,n);idx=np.searchsorted(z.time_s,tt);theta=np.deg2rad(z['heading_'+key+'_ned_deg'].to_numpy()[idx]);extent=max(np.ptp(xx),np.ptp(yy));arrowlen=max(.15,.12*extent)
   ax.quiver(xx[idx],yy[idx],arrowlen*np.sin(theta),arrowlen*np.cos(theta),angles='xy',scale_units='xy',scale=1,color=c,width=.008,alpha=.85,zorder=6)
  ax.scatter(0,0,s=20,facecolors='white',edgecolors='#333333',zorder=7);ax.set_aspect('equal',adjustable='datalim');ax.set(xlabel='East from event start (m)',ylabel='North from event start (m)');tidy(ax,3);panel(ax,chr(97+row*3),SCENE[s])
  # Small context map uses the full route; no misleading centimetre path inset.
  ins=ax.inset_axes([.65,.05,.33,.30]);ins.plot(d.east_truth_m,d.north_truth_m,color='#B6B6B6',lw=.55);ins.plot(z.east_truth_m,z.north_truth_m,color=COL['F04'],lw=1.2);ins.set_aspect('equal',adjustable='datalim');ins.set_xticks([]);ins.set_yticks([]);ins.set_title('Full route',fontsize=8,pad=1)
  inner=outer[row,1].subgridspec(2,1,height_ratios=[1.45,1],hspace=.35);ay=fig.add_subplot(inner[0]);ap=fig.add_subplot(inner[1],sharex=ay)
  for m in ['LC01','LC01-S','F04']:
   q=read(OLD/f'C01_{s}_{m}_saved_errors.csv.gz');q=q[q.elapsed_s.between(e['elapsed_start_s'],e['elapsed_end_s'])]
   for aa,k,scale in [(ay,'yaw_err_deg',1),(ap,'horizontal_err_m',100)]:line(aa,q.elapsed_s,q[k]*scale,color=COL[m],ls=LS[m],lw=1.0 if m=='F04' else .7,alpha=1 if m=='F04' else .85,zorder=5 if m=='F04' else 3)
  ay.axhline(0,color='#B8B8B8',lw=.5);ay.set_ylabel('Heading error (°)');ap.set_ylabel('Position error (cm)');ap.set_xlabel('Elapsed time (s)');ay.tick_params(labelbottom=False)
  for aa in [ay,ap]:
   aa.set_xlim(e['elapsed_start_s'],e['elapsed_end_s']);tidy(aa,3)
   if s=='BY2O':aa.axvspan(183.94,225.95,color='#E5E5E5',zorder=0)
  panel(ay,chr(98+row*3),f"{e['label']}: {e['elapsed_start_s']:.0f}–{e['elapsed_end_s']:.0f} s")
  ap.set_title('('+chr(99+row*3)+') Position error',loc='left',fontsize=8,pad=2)
 handles=[Line2D([],[],color='#333333',ls='--',label='Reference route / heading')]+[Line2D([],[],color=COL[m],ls=LS[m],label=NAME[m]) for m in ['F04','LC01','LC01-S']]
 fig.legend(handles=handles,loc='upper center',bbox_to_anchor=(.53,.989),ncol=2,columnspacing=1.5,handlelength=2.5)
 export(fig,'F03_event_routes_and_heading',{'events':events,'caption_zh':'三种场景中与实际运动事件对应的轨迹及航向误差。左列在米尺度展示事件期间参考与本文的局部轨迹，等长箭头为机身航向，小窗定位完整路线；右列上方展示本文与两种双位置IEKF的航向误差，下方给出同一事件的位置误差。前两行使用仅由参考姿态确认的首个20秒转弯；第三行展示首个登记遮挡及前后各10秒，灰色表示实际遮挡。空间误差很小时轨迹重合是预期现象，右列以角度和厘米直接量化。误差保留各方法冻结评价契约，局部窗口不用于重新定义全窗排名。','caption_en':'Event-aligned routes and navigation errors. The left column shows metre-scale local reference and LegSA-GINS trajectories with body-heading arrows and a small full-route locator. The right panels show heading and horizontal-position errors for LegSA-GINS and both dual-position IEKF parameter settings during the same event. The first two events are the first reference-confirmed 20-s turns; the third spans the first registered antenna obstruction with 10 s of context on each side. Gray shading denotes the registered obstruction. Equal-length arrows encode body direction, not speed. Frozen evaluation contracts are retained; event selection does not use estimator errors.','position_contract':'Local reference and V3 at archived POI. External horizontal errors retain frozen own evaluator contract; no external coordinate path reconstructed.','no_curve_smoothing':True})

def natural_common():
 tab=read(NAV/'LC_NATIVE_TABLE_READ.csv');tab.to_csv(OUT/'data/LC_ALL16_NATIVE_RECORDS.csv',index=False)
 tables={};stats=[];support=[]
 for s in SEQ:
  q=read(NAV/(s+'_COMMON_SEGMENTED_HEADING.csv.gz')).rename(columns={'v3_yaw_err_deg':'F04','oisam_yaw_err_deg':'OISAM'})
  allgood=np.ones(len(q),bool)
  for m in ['LC01','LC01-S','EXT05C','EXT05C-S']:
   row=tab[(tab.sequence_id==s)&(tab.method_id==m)&(tab.start_convention==('CONTRACT_START' if s=='BY2H' else 'FILE_START'))].iloc[0]
   p=Path(row.error_series_source);p=p/'error_series.csv.gz' if (p/'error_series.csv.gz').exists() else p/'error_series.csv';d=read(p).sort_values('time');ix,good,dt=nearest(d,q.nominal.to_numpy());q[m]=d.yaw_err_deg.to_numpy()[ix];q[m+'_time']=d.time.to_numpy()[ix];q[m+'_dt']=dt;allgood&=good
   support.append({'sequence':s,'method':m,'start_convention':row.start_convention,'evaluation_status':row.evaluation_status,'own_output_rows':len(d),'existing_v3_oisam_common':len(q),'matched_within_5ms':int(good.sum()),'max_dt_s':float(dt[good].max()),'source':str(p)})
  q['all_methods_supported']=allgood;q.to_csv(OUT/'data'/f'{s}_ALL_MATCH_ATTEMPTS.csv',index=False);q=q[allgood].copy();tables[s]=q;q.to_csv(OUT/'data'/f'{s}_COMMON_HEADING.csv.gz',index=False)
  for m in METHODS:stats.append({'sequence':s,'method':m,'matched_epochs':len(q),'heading_rmse_deg':float(np.sqrt(np.mean(q[m]**2))),'absolute_heading_median_deg':float(np.median(abs(q[m]))),'absolute_heading_p95_deg':float(np.percentile(abs(q[m]),95)),'absolute_heading_max_deg':float(np.max(abs(q[m]))),'scope':'Figure-only common nominal support; not replacement frozen native RMSE'})
 pd.DataFrame(stats).to_csv(OUT/'data/F09_COMMON_HEADING_STATISTICS.csv',index=False);pd.DataFrame(support).to_csv(OUT/'data/F09_MATCH_SUPPORT.csv',index=False)
 return tables,tab

def fig9():
 tables,tab=natural_common();fig,axs=plt.subplots(4,2,figsize=(174/25.4,222/25.4),gridspec_kw={'width_ratios':[1.5,1]});fig.subplots_adjust(left=.10,right=.982,bottom=.095,top=.888,wspace=.34,hspace=.73)
 for row,s in enumerate(SEQ):
  q=tables[s];ax=axs[row,0];ec=axs[row,1]
  for m in METHODS[1:]+['F04']:
   line(ax,q.elapsed_s,q[m],gap=1.001,color=COL[m],ls=LS[m],lw=1.15 if m=='F04' else .8,zorder=6 if m=='F04' else 3)
   v=np.sort(abs(q[m].to_numpy()));ec.step(np.r_[0,v],np.r_[0,np.arange(1,len(v)+1)/len(v)],where='post',color=COL[m],ls=LS[m],lw=1.2 if m=='F04' else 1,zorder=6 if m=='F04' else 3)
  ax.axhline(0,color='#B8B8B8',lw=.5);ax.set(xlim=(0,DUR[s]),xlabel='Elapsed time (s)',ylabel='Heading error (°)');tidy(ax,4)
  if s=='BY2O':
   for lo,hi in [(183.94,225.95),(309.94,322.94)]:ax.axvspan(lo,hi,color='#E7E7E7',zorder=0)
  ec.set(xlim=(0,max(float(np.max(abs(q[m]))) for m in METHODS)*1.03),ylim=(0,1.02),xlabel='Absolute heading error (°)',ylabel='Cumulative probability');ec.set_yticks([0,.5,1]);ec.xaxis.set_major_locator(MaxNLocator(4))
  panel(ax,chr(97+row*2),SCENE[s]);panel(ec,chr(98+row*2),f'Common epochs: n = {len(q)}')
  # A fixed 0–10-degree interval is part of the ECDF display, not an excluded tail.
  if ec.get_xlim()[1]>20:
   ins=ec.inset_axes([.46,.17,.49,.42])
   for m in METHODS[1:]+['F04']:
    v=np.sort(abs(q[m].to_numpy()));ins.step(np.r_[0,v],np.r_[0,np.arange(1,len(v)+1)/len(v)],where='post',color=COL[m],ls=LS[m],lw=.9)
   ins.set(xlim=(0,10),ylim=(0,1));ins.set_xticks([0,5,10]);ins.set_yticks([0,1]);ins.tick_params(labelsize=8,pad=1);ins.set_title('0–10°',fontsize=8,pad=1)
 # Keep the interruption protocol a separate, explicit condition block.
 ax=axs[3,0];pairs=read(NAV/'A2_ALL18_MATCHED_RESULTS.csv');duration_origin=196.2
 for m in ['LC01','EXT05C','LC01-BR','F04']:
  d=read(NAV/(m+'_A2_20s_seed00.csv.gz'));d=d[d.time.between(duration_origin-5,duration_origin+35)]
  line(ax,d.time-duration_origin,d.yaw_err_deg,color=COL[m],ls=LS[m],lw=1.15 if m=='F04' else .8,zorder=5 if m=='F04' else 3)
 ax.axvspan(0,20,color='#E7E7E7',zorder=0);ax.axvline(20,color='#888888',lw=.6);ax.axhline(0,color='#B8B8B8',lw=.5);ax.set(xlim=(-5,35),xlabel='Time from position interruption (s)',ylabel='Heading error (°)');tidy(ax,4);panel(ax,'g','Position interruption: 20 s')
 ax.annotate('Positions return',xy=(20,.99),xytext=(.98,1.10),xycoords=('data','axes fraction'),textcoords='axes fraction',ha='right',va='bottom',fontsize=8,arrowprops={'arrowstyle':'-','lw':.6,'color':'#666666'})
 ec=axs[3,1];mm=['F04','LC01','EXT05C','LC01-BR']
 for i,m in enumerate(mm):
  vals=pairs[m+'_yaw_rmse_deg'].to_numpy();ys=np.linspace(-.12,.12,len(vals))+i;ec.scatter(vals,ys,s=16,color=COL[m],edgecolors='white',linewidth=.25,zorder=3);ec.plot([np.median(vals)]*2,[i-.19,i+.19],color='#222222',lw=1,zorder=4)
 ec.set_yticks(range(4),['LegSA-GINS','Dual-pos.','Single-pos.','Baseline kept']);ec.tick_params(axis='y',length=0);ec.set_ylim(3.5,-.5);ec.set_xlabel('Whole-run heading RMSE (°)');ec.set_xlim(0,None);ec.xaxis.set_major_locator(MaxNLocator(4));panel(ec,'h','All 18 interruption cases')
 handles=[Line2D([],[],color=COL[m],ls=LS[m],lw=1.2,label=NAME[m]) for m in METHODS]
 fig.legend(handles=handles,loc='upper center',bbox_to_anchor=(.54,.99),ncol=2,columnspacing=1.3,handlelength=2.8)
 fig.text(.10,.025,'Gold dash-dot in (g): baseline-retaining IEKF. Gray bands: registered interruption / obstruction.',fontsize=8)
 pairs.to_csv(OUT/'data/F09_ALL18_INTERRUPTION_CASES.csv',index=False)
 mapping=[]
 for _,r in tab.iterrows():
  primary=r.start_convention==('CONTRACT_START' if r.sequence_id=='BY2H' else 'FILE_START');mapping.append({'method':r.method_id,'sequence':r.sequence_id,'configuration':r.config,'start':r.start_convention,'status':r.evaluation_status,'destination':'F09 a–f common heading' if primary else 'LC_ALL16_NATIVE_RECORDS.csv: alternate-start sensitivity, all failures retained','reason':'primary registered start' if primary else 'not mixed with primary initialization'})
 mapping.extend([{'method':'LC01-BR','destination':'F09 g–h; all 18 registered interruptions','reason':'No natural-trial identity invented'},{'method':'OiSAM single initialization','destination':'OUTPUT_INTERVALS.csv and V3_OISAM_COMMON_POINT.csv companion','reason':'Reinitialized dynamic protocol plotted in a–f; original early stop retained separately'},{'method':'OiSAM recorded-gap reinitialization','destination':'F09 a–f','reason':'Dynamic heading common nominal support, excludes prior-only states'},{'method':'GINav','destination':'GINAV_ACTUAL_RESULTS.csv','reason':'Only two valid H epochs; B/O speed-gate failure; no reliable whole-run yaw curve'},{'method':'TC-FGO / GNC-FGO','destination':'FGO_GNSS1_ALL36_RESULTS.csv supplementary position comparison','reason':'No matched self-estimated attitude output appropriate for heading main figure'}])
 pd.DataFrame(mapping).to_csv(OUT/'data/METHOD_DESTINATIONS.csv',index=False)
 for f in ['GINAV_ACTUAL_RESULTS.csv','FGO_GNSS1_ALL36_RESULTS.csv','OUTPUT_INTERVALS.csv','V3_OISAM_COMMON_POINT.csv','DEGRADATION_EXTERNAL_TABLE_R2.csv','DEGRADATION_PAIRED_R2.csv']:
  shutil.copy2(NAV/f,OUT/'data'/f)
 export(fig,'F09_heading_comparison',{'common_epochs':{s:len(q) for s,q in tables.items()},'matching':'Existing V3/OiSAM dynamic nominal pairs; nearest retained IEKF error epoch within 5ms of same nominal second; intersect all four IEKF supports; no interpolation. All methods within at most10ms pairwise.','caption_zh':'航向精度的解级滤波与因子图比较。（a–f）三条自然记录中，本文、双位置和单位置IEKF的文献/标定参数，以及按既定IMU数据段重新初始化的OiSAM，在全部方法共同支持的名义时刻上的有符号航向误差与绝对误差累积分布。误差定义均为机体NED航向相对参考的环绕角差；不混合位置参考点。灰带表示登记遮挡，缺少动态输出处断线。自然比较使用原登记起点，大幅运动的双位置IEKF几何审查例外在完整表保留。（g）首个登记20秒位置中断中的航向过程，金色点划线为保留基线IEKF；本文保留可用方向和机身辅助。（h）全部18个中断布置的整窗航向RMSE，每点一个案例，短黑线为中位数。自然与中断两类实验使用各自既定输入协议；无误差优化选窗。','caption_en':'Heading accuracy across solution-level filtering and factor-graph methods. (a–f) Signed heading errors and absolute-error ECDFs at common nominal dynamic epochs for LegSA-GINS, the literature/calibrated dual- and single-position IEKFs, and OiSAM reinitialized on predeclared recorded-IMU blocks. Curves break where dynamic output is unavailable; gray spans denote registered antenna obstruction. Native initialization conventions and the large-motion geometric-audit exception are retained in the full companion table. (g) The first registered 20-s position interruption, including the baseline-retaining IEKF in gold; LegSA-GINS retains available direction and body-motion aids. (h) Whole-run heading RMSE for all 18 registered interruptions; each point is a case and black ticks are medians. Natural and interrupted conditions retain their respective input protocols.','selection':'Entire common natural support; first registered interruption; all18 conditions','source_metric_status':'New descriptive figure statistics on saved yaw errors; no frozen source metrics overwritten','no_failure_rows_removed':True})

if __name__=='__main__':
 for x in sys.argv[1:] or ['3','9']:{'3':fig3,'9':fig9}[x]()
 (OUT/'SOURCE_PROFILE.json').write_text(json.dumps(PROFILE,ensure_ascii=False,indent=2));(OUT/'SOURCE_PATHS.json').write_text(json.dumps(sorted(set(SOURCES)),ensure_ascii=False,indent=2))
