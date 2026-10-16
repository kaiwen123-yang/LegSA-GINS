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
NAV=OUT/'data'
OLD=ROOT/'V3论文组图_20261008/redesign_20261009/figures/data'
REPO=Path('/home/kaiwen/research/LegSA-GINS-WORKTREES/audit-code-xbpg-20261001')
POSE=REPO/'docs/paper_rebuild/GPSS_V3_FIGURES_20261008/redesign_20261009/data'
for p in ['data','preview','qa']:(OUT/p).mkdir(exist_ok=True)
SEQ=['BY2','BY2H','BY2O'];START={'BY2':66,'BY2H':413,'BY2O':3186};DUR={'BY2':274,'BY2H':270,'BY2O':377}
SCENE={'BY2':'Nominal walking','BY2H':'Large body motion','BY2O':'Antenna obstruction'}
COL={'F04':'#2563EB','LC01':'#E76F51','LC01-S':'#E76F51','EXT05C':'#8B5CF6','EXT05C-S':'#8B5CF6','OISAM':'#009E9A','LC01-BR':'#64748B','WEN_TC':'#197A69','GNC':'#8B5CF6'}
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
 fig.canvas.draw()
 scripts=Path('/mnt/c/Users/ykw/.codex/skills/nature-figure/scripts');sys.path.insert(0,str(scripts))
 from audit_panel_alignment import require_matplotlib_panel_alignment
 if name.startswith('F03'):
  options={'axes':fig.axes,'panel_ids':list('abcdefghi'),'column_groups':[['a','d','g'],['b','e','h'],['c','f','i']], 'exemptions':[{'panels':['a','d','g'],'checks':['panel-width'],'reason':'Spatial route spans both error rows; equal metric scale maintained; compare route column separately from wider time-series column.'}]}
 else:
  options={'axes':fig.axes,'panel_ids':list('abcdefgh'),'row_groups':[['a','b'],['c','d'],['e','f'],['g','h']],'column_groups':[['a','c','e','g'],['b','d','f','h']],'exemptions':[{'panels':list('abcdefgh'),'checks':['panel-width'],'reason':'The signed-error time series intentionally has 1.5 times the ECDF width; identical spans within each column remain comparable.'}]}
 align=require_matplotlib_panel_alignment(fig,json_out=OUT/'qa'/(name+'.alignment.json'),overlay_svg=OUT/'qa'/(name+'.alignment.svg'),tolerance_pt=1.5,gutter_tolerance_pt=1.5,strict=True,**options)
 fig.savefig(OUT/(name+'.pdf'));fig.savefig(OUT/(name+'.svg'));fig.savefig(OUT/(name+'.png'),dpi=600)
 fig.savefig(OUT/(name+'.tiff'),dpi=600,pil_kwargs={'compression':'tiff_lzw'})
 fig.savefig(OUT/'preview'/(name+'.png'),dpi=400)
 Image.open(OUT/'preview'/(name+'.png')).convert('L').save(OUT/'preview'/(name+'_gray.png'))
 qa={}
 for tag,args in [('text',['audit_pdf_text.py',str(OUT/(name+'.pdf')),'--min-pt','8','--json']),('collisions',['audit_figure_collisions.py',str(OUT/(name+'.pdf')),'--json-out',str(OUT/'qa'/(name+'.collisions.json'))])]:
  r=subprocess.run([sys.executable,str(scripts/args[0]),*args[1:]],capture_output=True,text=True);(OUT/'qa'/(name+'.'+tag+'.log')).write_text(r.stdout+r.stderr);qa[tag]=r.returncode
 meta.update({'width_mm':174,'height_mm':fig.get_figheight()*25.4,'min_font_pt':8,'preview_dpi':400,'source_paths':sorted(set(SOURCES)),'new_solver_evaluator_provider_calls':0,'frozen_v3':'7d43b9af26120ed5dde21f53e515386361072ba6','audits':qa,'alignment':align['verdict'],'visual_review':'PENDING'})
 (OUT/(name+'.json')).write_text(json.dumps(meta,ensure_ascii=False,indent=2));plt.close(fig);print(name,qa,flush=True)
def nearest(d,targets,key='time',tol=.005):
 t=d[key].to_numpy();ix=np.searchsorted(t,targets);a=np.clip(ix-1,0,len(t)-1);b=np.clip(ix,0,len(t)-1);ids=np.where(np.abs(t[a]-targets)<=np.abs(t[b]-targets),a,b)
 return ids,np.abs(t[ids]-targets)<=tol,np.abs(t[ids]-targets)


def natural_common():
 # Reuse exactly the R2 common-support tables, without rematching/evaluation.
 return {s:read(NAV/(s+'_COMMON_HEADING.csv.gz')) for s in SEQ},read(NAV/'LC_ALL16_NATIVE_RECORDS.csv')

def fig9():
 tables,tab=natural_common();fig=plt.figure(figsize=(174/25.4,212/25.4));grid=fig.add_gridspec(4,2,left=.10,right=.982,bottom=.11,top=.89,width_ratios=[1.5,1],height_ratios=[1,1,1,1.15],wspace=.34,hspace=.86)
 axs=np.array([[fig.add_subplot(grid[r,c]) for c in range(2)] for r in range(4)])
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
   ins.set(xlim=(0,10),ylim=(0,1));ins.set_xticks([0,5,10]);ins.set_yticks([1]);ins.tick_params(labelsize=8,pad=1);ins.set_title('0–10°',fontsize=8,pad=1)
 # Keep the interruption protocol a separate, explicit condition block.
 ax=axs[3,0];pairs=read(NAV/'F09_ALL18_INTERRUPTION_CASES.csv');duration_origin=196.2
 for m in ['LC01','EXT05C','LC01-BR','F04']:
  d=read(NAV/(m+'_A2_20s_seed00.csv.gz'));d=d[d.time.between(duration_origin-5,duration_origin+35)]
  line(ax,d.time-duration_origin,d.yaw_err_deg,color=COL[m],ls=LS[m],lw=1.15 if m=='F04' else .8,zorder=5 if m=='F04' else 3)
 ax.axvspan(0,20,color='#E7E7E7',zorder=0);ax.axvline(20,color='#888888',lw=.6);ax.axhline(0,color='#B8B8B8',lw=.5);ax.set(xlim=(-5,35),xlabel='Time from position interruption (s)',ylabel='Heading error (°)');tidy(ax,4);panel(ax,'g','Position interruption: 20 s')
 ax.annotate('Positions return',xy=(20,.99),xytext=(.98,1.10),xycoords=('data','axes fraction'),textcoords='axes fraction',ha='right',va='bottom',fontsize=8,arrowprops={'arrowstyle':'-','lw':.6,'color':'#666666'})
 ec=axs[3,1];mm=['F04','LC01','EXT05C','LC01-BR']
 full_names=['LegSA-GINS','Dual-position IEKF','Single-position IEKF','IEKF with retained baseline']
 for i,m in enumerate(mm):
  vals=pairs[m+'_yaw_rmse_deg'].to_numpy();assert len(vals)==18
  ys=np.linspace(-.09,.09,len(vals))+i;ec.scatter(vals,ys,s=14,color=COL[m],edgecolors='white',linewidth=.25,zorder=3);ec.plot([np.median(vals)]*2,[i-.14,i+.14],color='#111827',lw=1.5,zorder=4)
  ec.text(.015,i-.24,full_names[i],transform=ec.get_yaxis_transform(),ha='left',va='bottom',fontsize=8)
 ec.set_yticks([]);ec.set_ylim(3.48,-.75);ec.set_xlabel('Whole-run heading RMSE (°)');ec.set_xlim(0,None);ec.xaxis.set_major_locator(MaxNLocator(4));panel(ec,'h','18 position-interruption cases')
 ec.text(.5,-.43,'18 cases per method\nDots: cases; black mark: median',transform=ec.transAxes,ha='center',va='top',fontsize=8)
 handles=[Line2D([],[],color=COL[m],ls=LS[m],lw=1.2,label=NAME[m]) for m in METHODS]+[Line2D([],[],color=COL['LC01-BR'],ls=LS['LC01-BR'],lw=1.2,label='Baseline-retaining IEKF (g,h)')]
 fig.legend(handles=handles,loc='upper center',bbox_to_anchor=(.54,.993),ncol=2,columnspacing=1.3,handlelength=2.8,labelspacing=.35)
 # The old panel (i) becomes a clearly labelled, same-GNSS1-point table next to
 # the new trajectory group. Its nine values and all36 source rows are retained.
 fgo=read(NAV/'FGO_GNSS1_ALL36_RESULTS.csv');common=fgo[(fgo.support_role=='PRIMARY_DYNAMIC_ONLY')&(fgo.support=='COMMON_THREE_TIME_KEYS')].copy()
 assert len(common)==9 and common.horizontal_rmse_m.notna().all() and (common.horizontal_rmse_m>0).all()
 # Companion tables are exact R2 copies; do not reserialize their original values.
 coverage=fgo[(fgo.support_role=='PRIMARY_DYNAMIC_ONLY')&(fgo.support=='OWN_VALID')][['sequence_id','method_id','status','input_layer','attitude_is_estimated','physical_point','expected_epoch_count','actual_epoch_count','finite_epoch_count','matched_epoch_count','coverage_fraction','yaw_rmse_deg','horizontal_rmse_m']].copy()
 mapping=[]
 for _,r in tab.iterrows():
  primary=r.start_convention==('CONTRACT_START' if r.sequence_id=='BY2H' else 'FILE_START');mapping.append({'method':r.method_id,'sequence':r.sequence_id,'configuration':r.config,'start':r.start_convention,'status':r.evaluation_status,'destination':'F09 a–f common heading' if primary else 'LC_ALL16_NATIVE_RECORDS.csv: alternate-start sensitivity, all failures retained','reason':'primary registered start' if primary else 'not mixed with primary initialization'})
 mapping.extend([{'method':'LC01-BR','destination':'F09 g–h; all 18 registered interruptions','reason':'No natural-trial identity invented'},{'method':'OiSAM single initialization','destination':'OUTPUT_INTERVALS.csv and V3_OISAM_COMMON_POINT.csv companion','reason':'Reinitialized dynamic protocol plotted in a–f; original early stop retained separately'},{'method':'OiSAM recorded-gap reinitialization','destination':'F09 a–f heading; F11 companion GNSS1 position table','reason':'Dynamic heading common nominal support, excludes prior-only states; antenna position uses its own registered three-FGO support'},{'method':'GINav','destination':'GINAV_ACTUAL_RESULTS.csv','reason':'Only two valid H epochs; B/O speed-gate failure; no reliable whole-run yaw curve'},{'method':'TC-FGO / GNC-FGO','destination':'F11 companion METHOD_POSITION_TABLE.csv; full FGO_GNSS1_ALL36_RESULTS.csv','reason':'Existing runs do not estimate attitude. Full-window position outputs are retained, not portrayed as yaw outputs.'}])
 pd.DataFrame(mapping).to_csv(OUT/'data/METHOD_DESTINATIONS.csv',index=False)
 for f in ['GINAV_ACTUAL_RESULTS.csv','FGO_GNSS1_ALL36_RESULTS.csv','OUTPUT_INTERVALS.csv','V3_OISAM_COMMON_POINT.csv','DEGRADATION_EXTERNAL_TABLE_R2.csv','DEGRADATION_PAIRED_R2.csv']:
  if (NAV/f).resolve()!=(OUT/'data'/f).resolve():shutil.copy2(NAV/f,OUT/'data'/f)
 export(fig,'F09_heading_comparison',{
  'common_epochs':{s:len(q) for s,q in tables.items()},
  'matching':'Exact saved R2 common-support tables; no rematching or interpolation. Original nominal matching and at most10ms pairwise separation retained.',
  'caption_zh':'滤波与因子图方法的航向精度。（a–f）三条自然记录的有符号航向误差及绝对误差累计分布，六种配置使用共同动态时刻274/267/367点。灰带表示登记遮挡，缺少动态输出处断线。（g）首个登记20秒位置中断中的航向误差；20秒时位置观测恢复。（h）同一常规记录上全部18个位置中断条件：10秒和20秒各九个布置。每个点代表一个条件的全窗航向RMSE，黑色短线为18个条件的中位数。四个完整方法名称直接写在对应点列上方。旧版(i)的FGO定位指标移到新轨迹组配表，保留相同GNSS1评价点、共同支持及原始输入说明。',
  'caption_en':'Heading accuracy across filtering and factor-graph methods. (a–f) Signed heading errors and absolute-error ECDFs at the saved common dynamic epochs (274/267/367) for six configurations. Gray shading marks registered obstruction; missing dynamic outputs break curves. (g) Heading error during the first registered20-s position interruption, with position observations returning at20s. (h) All18 registered interruption conditions on the nominal recording: nine placements at10s and nine at20s. Each dot is a whole-run heading RMSE for one condition; the black mark is the median over18 conditions. Full method names are placed directly above their point rows. The previous FGO position panel is preserved as a companion table to the trajectory figure, retaining its common GNSS1 point, temporal support and input definitions.',
  'selection':'All original natural common epochs and all18 registered interruption conditions retained.',
  'source_metric_status':'R2 saved input/error tables reused exactly; no new evaluation or thresholding.',
  'no_failure_rows_removed':True,
  'old_panel_i_destination':'METHOD_POSITION_TABLE.csv and METHOD_POSITION_TABLE.md, indexed by new F11 trajectory group',
  'FGO_common_position_counts':{'BY2':274,'BY2H':267,'BY2O':369},
  'FGO_method_state':'TC-FGO/GNC-FGO do not estimate yaw; no yaw is filled or plotted for these methods.',
  'R3_change':'Panel h uses complete method names and explicit dot/median definitions; old i becomes a clear table.'})


if __name__=='__main__':
 for x in sys.argv[1:] or ['9']:{'9':fig9}[x]()
 (OUT/'SOURCE_PROFILE.json').write_text(json.dumps(PROFILE,ensure_ascii=False,indent=2));(OUT/'SOURCE_PATHS.json').write_text(json.dumps(sorted(set(SOURCES)),ensure_ascii=False,indent=2))
