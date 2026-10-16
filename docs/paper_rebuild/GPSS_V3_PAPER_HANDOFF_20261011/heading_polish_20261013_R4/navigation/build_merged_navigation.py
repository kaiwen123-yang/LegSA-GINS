"""One scene-wise figure: full routes, same-point moving details, heading."""
from pathlib import Path
import sys,json,subprocess,shutil
import numpy as np,pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from PIL import Image
O=Path(__file__).parent;D=O/'data';R=Path('/mnt/g/LegSA-GINS-project');R3=R/'V3正文精修_20261012_R3/navigation/data';YAW=R/'V3正文精修_20261012_R3/navigation_comparison/data';SK=Path('/mnt/c/Users/ykw/.codex/skills/nature-figure/scripts')
sys.path.insert(0,str(SK));from audit_panel_alignment import require_matplotlib_panel_alignment
for p in ['preview','qa']:(O/p).mkdir(exist_ok=True)
SEQ=['BY2','BY2H','BY2O'];SCENE={'BY2':'Nominal walking','BY2H':'Large body motion','BY2O':'Antenna obstruction'}
COL={'REFERENCE_POI':'#111827','F04':'#2563EB','LC01':'#E76F51','LC01-S':'#E76F51','EXT05C':'#8B5CF6','EXT05C-S':'#8B5CF6','OISAM_RESTART_POI':'#009E9A','WEN_TC':'#197A69','GNC':'#8B5CF6'}
LS={'REFERENCE_POI':(0,(4,2)),'F04':'-','LC01':'--','LC01-S':':','EXT05C':'--','EXT05C-S':':','OISAM_RESTART_POI':'-.','WEN_TC':(0,(6,2)),'GNC':'-'}
NAME={'REFERENCE_POI':'Reference','F04':'LegSA-GINS','LC01':'Dual-pos. IEKF (LIT)','LC01-S':'Dual-pos. IEKF (cal.)','EXT05C':'Single-pos. IEKF (LIT)','EXT05C-S':'Single-pos. IEKF (cal.)','OISAM_RESTART_POI':'OiSAM (reinitialized)','WEN_TC':'TC-FGO','GNC':'GNC-FGO'}
POI=['LC01','LC01-S','EXT05C','EXT05C-S','OISAM_RESTART_POI','F04'];ALL=['WEN_TC','GNC']+POI
plt.rcParams.update({'font.family':'sans-serif','font.sans-serif':['Arial','Liberation Sans','DejaVu Sans'],'font.size':8,'axes.labelsize':8,'axes.titlesize':8.5,'xtick.labelsize':8,'ytick.labelsize':8,'legend.fontsize':8,'legend.frameon':False,'axes.spines.top':False,'axes.spines.right':False,'axes.linewidth':.6,'xtick.direction':'out','ytick.direction':'out','xtick.major.size':2.5,'ytick.major.size':2.5,'pdf.fonttype':42,'svg.fonttype':'none','path.simplify':False,'savefig.facecolor':'white'})
cache={};uses=[]
def data(s,m):
 key=(s,m)
 if key not in cache:
  path=(D if m=='OISAM_RESTART_POI' else R3)/f'{s}__{m}.csv.gz';cache[key]=pd.read_csv(path);assert np.all(np.diff(cache[key].time_s.to_numpy())>0)
 return cache[key].copy()
def route(ax,d,m,origin=(0,0),scale=1,detail=False):
 v=d.valid.to_numpy(bool);x=(d.east_m.to_numpy()-origin[0])*scale;y=(d.north_m.to_numpy()-origin[1])*scale;x[~v]=np.nan;y[~v]=np.nan
 gap=1.001 if m.startswith('OISAM') or m in ['WEN_TC','GNC'] else .101;br=np.flatnonzero(np.diff(d.time_s)>gap)+1
 if 'block_id' in d:br=np.unique(np.r_[br,np.flatnonzero(np.diff(d.block_id.fillna(-1))!=0)+1])
 ax.plot(np.insert(x,br,np.nan),np.insert(y,br,np.nan),color=COL[m],ls=LS[m],lw=1.05 if m in ['F04','REFERENCE_POI'] else .72,rasterized=detail,zorder=6 if m=='F04' else 5 if m=='REFERENCE_POI' else 3)
 if m=='GNC' and len(d):
  # Marker redundancy only; the complete path above retains every source row.
  marker=np.arange(0,len(d),20);marker=marker[v[marker]];ax.scatter(x[marker],y[marker],color=COL[m],marker='D',s=6,linewidths=0,zorder=4)
fig,axs=plt.subplots(3,3,figsize=(174/25.4,190/25.4),gridspec_kw={'width_ratios':[1.15,.92,1.28]});fig.subplots_adjust(left=.085,right=.99,bottom=.075,top=.865,wspace=.54,hspace=.55)
windows=[]
for i,s in enumerate(SEQ):
 lo,hi=(40.,140.) if s!='BY2O' else (154.945,254.945);a,b=(88.,92.) if s!='BY2O' else (228.,233.);center=(a+b)/2
 ref=data(s,'REFERENCE_POI');t=ref.elapsed_s.to_numpy();assert np.all(np.diff(t)>0);centre=np.array([np.interp(center,t,ref[k]) for k in ['east_m','north_m']])
 ax=axs[i,0]
 for m in ALL+['REFERENCE_POI']:
  q=data(s,m);route(ax,q,m);uses.append({'sequence':s,'panel':'full_route','method':m,'source_rows':len(q),'finite_rows_plotted':int(q.valid.sum()),'point':'GNSS1_ANTENNA' if m in ['WEN_TC','GNC'] else 'POI_MIDPOINT','selection':'complete original evaluation window; no common-time clipping'})
 ax.scatter(*centre,marker='s',s=25,facecolors='none',edgecolors='#475569',lw=.75,zorder=8);ax.set_aspect('equal',adjustable='datalim');ax.set(xlabel='East (m)',ylabel='North (m)');ax.locator_params(nbins=3);ax.set_title(f'({chr(97+i*3)}) '+SCENE[s],loc='left',pad=5)
 ax=axs[i,1]
 for m in POI+['REFERENCE_POI']:
  q=data(s,m);q=q[q.elapsed_s.between(a,b)];route(ax,q,m,origin=centre,scale=100,detail=True);uses.append({'sequence':s,'panel':'POI_spatial_detail','method':m,'source_rows':len(q),'finite_rows_plotted':int(q.valid.sum()),'point':'POI_MIDPOINT','selection':f'fixed reference-defined interval {a}–{b}s; true spatial viewport; no error magnification'})
 ax.set(xlim=(-75,75),ylim=(-75,75),xlabel='East offset (cm)',ylabel='North offset (cm)');ax.set_aspect('equal',adjustable='datalim');ax.set_xticks([-50,0,50]);ax.set_yticks([-50,0,50]);ax.set_title(f'({chr(98+i*3)}) '+('Recovery detail' if s=='BY2O' else 'POI spatial detail'),loc='left',pad=5);ax.text(.02,.97,f'{a:g}–{b:g} s',transform=ax.transAxes,va='top',fontsize=8)
 ax=axs[i,2];q=pd.read_csv(YAW/(s+'_COMMON_HEADING.csv.gz'));q.to_csv(D/(s+'_COMMON_HEADING.csv.gz'),index=False);z=q[q.elapsed_s.between(lo,hi)];tt=z.elapsed_s.to_numpy();br=np.flatnonzero(np.diff(tt)>1.001)+1
 for m in ['LC01','LC01-S','EXT05C','EXT05C-S','OISAM_RESTART_POI','F04']:
  field='OISAM' if m=='OISAM_RESTART_POI' else m;ax.plot(np.insert(tt,br,np.nan),np.insert(z[field].to_numpy(),br,np.nan),color=COL[m],ls=LS[m],lw=1.1 if m=='F04' else .75,zorder=6 if m=='F04' else 3);uses.append({'sequence':s,'panel':'100s_heading','method':m,'source_rows':len(q),'finite_rows_plotted':len(z),'point':'body NED yaw','selection':'same six-method nominal dynamic support as approved F09; fixed100s display window'})
 ax.axhline(0,color='#B0B0B0',lw=.5);ax.axvspan(a,b,color='#DDE7F2',zorder=0)
 if s=='BY2O':ax.axvspan(183.94,225.95,color='#E5E7EB',zorder=0)
 ax.set(xlim=(lo,hi),xlabel='Elapsed time (s)',ylabel='Heading error (°)');ax.locator_params(nbins=3);ax.set_title(f'({chr(99+i*3)}) 100-s heading error',loc='left',pad=5)
 windows.append({'sequence':s,'heading_start_s':lo,'heading_end_s':hi,'heading_duration_s':hi-lo,'detail_start_s':a,'detail_end_s':b,'detail_centre_s':center,'detail_east_reference_m':centre[0],'detail_north_reference_m':centre[1],'selection':'BY2/H: prior fixed88–92s reference-defined turning neighbourhood. BY2O: first5s recovery interval after registered obstruction with reference displacement>=2m and median1s chord speed>=0.3m/s; no estimate error inspected.','local_methods_point':'POI_MIDPOINT','full_route_point_note':'TC/GNC at native registered GNSS1; all other main trajectories at POI; overview only, not same-point precision ranking.'})
legend=['REFERENCE_POI','F04','LC01','LC01-S','EXT05C','EXT05C-S','OISAM_RESTART_POI','WEN_TC','GNC'];handles=[Line2D([],[],color=COL[m],ls=LS[m],marker='D' if m=='GNC' else None,markersize=3,lw=1,label=NAME[m]) for m in legend]
fig.legend(handles=handles,loc='upper center',bbox_to_anchor=(.53,.998),ncol=3,columnspacing=1.1,handlelength=2.5,labelspacing=.55)
fig.canvas.draw()
for i,w in enumerate(windows):w['rendered_detail_xlim_cm']=list(axs[i,1].get_xlim());w['rendered_detail_ylim_cm']=list(axs[i,1].get_ylim())
name='F03_integrated_routes_and_heading';ids=list('abcdefghi')
alignment=require_matplotlib_panel_alignment(fig,axes=list(axs.flat),panel_ids=ids,json_out=O/'qa'/(name+'.alignment.json'),overlay_svg=O/'qa'/(name+'.alignment.svg'),tolerance_pt=1.5,gutter_tolerance_pt=1.5,exemptions=[{'panels':ids,'checks':['panel-width'],'reason':'Intentional column roles: complete route and100s heading receive more width than the physical POI detail. Repeated column widths/heights and gutters are still checked.'}],strict=True)
for ext in ['pdf','svg']:fig.savefig(O/(name+'.'+ext),dpi=600)
fig.savefig(O/(name+'.png'),dpi=600);fig.savefig(O/(name+'.tiff'),dpi=600,pil_kwargs={'compression':'tiff_lzw'});fig.savefig(O/'preview'/(name+'.png'),dpi=400);Image.open(O/'preview'/(name+'.png')).convert('L').save(O/'preview'/(name+'_gray.png'))
pd.DataFrame(uses).to_csv(D/'FIGURE_SOURCE_COUNTS.csv',index=False);pd.DataFrame(windows).to_csv(D/'F03_EVENT_WINDOWS.csv',index=False)
audits={}
for tag,args in [('text',['audit_pdf_text.py',str(O/(name+'.pdf')),'--min-pt','8','--json']),('collisions',['audit_figure_collisions.py',str(O/(name+'.pdf')),'--json-out',str(O/'qa'/(name+'.collisions.json'))])]:
 r=subprocess.run([sys.executable,str(SK/args[0]),*args[1:]],capture_output=True,text=True);(O/'qa'/(name+'.'+tag+'.log')).write_text(r.stdout+r.stderr);audits[tag]=r.returncode
meta={'id':name,'width_mm':174,'height_mm':190,'min_font_pt':8,'preview_dpi':400,'caption_zh':'三场景导航路线、同点空间局部与航向误差的合图。每行依次展示完整评价窗的地理路线、由参考运动确定的POI局部、以及固定100秒的航向误差。全路图纳入所有主导航输出；本文、IEKF和恢复OiSAM在POI中点，TC/GNC保留原GNSS1位置，因此全路只作空间概览，不作同点精度排名。厘米局部全部统一POI；OiSAM仅用自身估计姿态与已有登记杆臂作显示点变换，没有使用参考姿态。遮挡局部采用参考确认的228–233秒恢复运动，不再将近静止点团称作运动路线。右列使用与图9相同的六方法共同动态时刻；TC/GNC没有自估计航向，不画伪航向曲线。常规/大幅运动的100秒窗口为40–140秒，遮挡为154.945–254.945秒；灰带是原登记遮挡183.94–225.95秒，淡蓝带对应空间细节时间。所有原生轨迹点及共同支持记录保留，缺口断线。','caption_en':'Integrated navigation routes, same-point spatial details and heading errors for three recordings. Each row shows the complete geographic route, a reference-defined POI detail, and a fixed100-s heading interval. The overview includes all principal navigation outputs: LegSA-GINS, IEKFs and reinitialized OiSAM use the POI midpoint, whereas TC/GNC retain their registered GNSS1 positions; it is therefore a spatial overview rather than a same-point accuracy ranking. Every centimetre-scale detail is at the POI. OiSAM point transport uses only its own estimated attitude and the previously registered lever arm, never reference attitude. The obstruction detail covers reference-confirmed recovery motion at228–233s instead of a nearly stationary interval. Heading uses the same six-method common dynamic support as Fig.9; no heading is invented for TC/GNC. The100-s windows are40–140s for the first two records and154.945–254.945s for obstruction. Gray shading marks the registered183.94–225.95s obstruction; pale blue identifies the spatial-detail interval. All native route points and common-support records are retained, with breaks at gaps.','replaces':['R3_F03_100s_routes_with_spatial_detail','R3_F11_full_trajectory_comparison'],'F11_disposition':'Move old separated-point full-route plate to supplement/archive; do not repeat as a second main figure.','all_route_methods':ALL,'local_poi_methods':POI,'TC_GNC_yaw':'not estimated; no heading curve','windows':windows,'source_roots':{'R3_coordinates':str(R3),'F09_common_heading':str(YAW)},'alignment':alignment['verdict'],'audits':audits,'new_solver_evaluator_provider_calls':0,'frozen_metrics_changed':False,'visual_review':'PENDING'}
(O/(name+'.json')).write_text(json.dumps(meta,ensure_ascii=False,indent=2));print(json.dumps({'figure':name,'audits':audits,'alignment':alignment['verdict']}))
