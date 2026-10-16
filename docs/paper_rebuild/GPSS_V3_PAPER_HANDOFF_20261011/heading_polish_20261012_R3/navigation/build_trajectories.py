"""R3: 100-second event plots and all retained native trajectory families."""
from pathlib import Path
import sys,json,subprocess
import numpy as np,pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from PIL import Image
O=Path(__file__).parent;D=O/'data';R=Path('/mnt/g/LegSA-GINS-project');SK=Path('/mnt/c/Users/ykw/.codex/skills/nature-figure/scripts')
sys.path.insert(0,str(SK));from audit_panel_alignment import require_matplotlib_panel_alignment
for p in ['preview','qa']:(O/p).mkdir(exist_ok=True)
SEQ=['BY2','BY2H','BY2O'];START={'BY2':66,'BY2H':413,'BY2O':3186};END={'BY2':340,'BY2H':683,'BY2O':3563}
SCENE={'BY2':'Nominal walking','BY2H':'Large body motion','BY2O':'Antenna obstruction'}
COL={'REFERENCE_POI':'#111827','REFERENCE_GNSS1':'#111827','F04':'#2563EB','LC01':'#E76F51','LC01-S':'#E76F51','EXT05C':'#8B5CF6','EXT05C-S':'#8B5CF6','OISAM_STRICT':'#009E9A','OISAM_RESTART':'#009E9A','WEN_TC':'#197A69','GNC':'#8B5CF6','GINAV_NATIVE':'#A855A1','OFF-LIT':'#E76F51','OFF-DEF':'#009E9A','LEG-DR':'#8B5CF6'}
LS={'F04':'-','LC01':'--','LC01-S':':','EXT05C':'--','EXT05C-S':':','OISAM_STRICT':'-.','OISAM_RESTART':'-.','WEN_TC':'--','GNC':':','REFERENCE_POI':(0,(4,2)),'REFERENCE_GNSS1':(0,(4,2))}
NAME={'F04':'LegSA-GINS','LC01':'Dual-pos. IEKF (LIT)','LC01-S':'Dual-pos. IEKF (cal.)','EXT05C':'Single-pos. IEKF (LIT)','EXT05C-S':'Single-pos. IEKF (cal.)','OISAM_STRICT':'OiSAM (single init.)','OISAM_RESTART':'OiSAM (reinitialized)','WEN_TC':'TC-FGO','GNC':'GNC-FGO','REFERENCE_POI':'Reference','REFERENCE_GNSS1':'Reference'}
plt.rcParams.update({'font.family':'sans-serif','font.sans-serif':['Arial','Liberation Sans','DejaVu Sans'],'font.size':8,'axes.labelsize':8,'axes.titlesize':8.5,'xtick.labelsize':8,'ytick.labelsize':8,'legend.fontsize':8,'legend.frameon':False,'axes.spines.top':False,'axes.spines.right':False,'axes.linewidth':.6,'xtick.direction':'out','ytick.direction':'out','xtick.major.size':2.5,'ytick.major.size':2.5,'pdf.fonttype':42,'svg.fonttype':'none','path.simplify':False,'savefig.facecolor':'white'})
cov=pd.read_csv(D/'TRAJECTORY_COVERAGE.csv');cache={}
def data(s,m):
 key=(s,m)
 if key not in cache:
  cache[key]=pd.read_csv(D/f'{s}__{m}.csv.gz')
  assert np.all(np.diff(cache[key].time_s.to_numpy())>0),'native coordinate timestamps must increase'
 return cache[key].copy()
def plotxy(ax,d,m,offset=(0,0),scale=1,lw=None,gap=None,mark=False,**kw):
 v=d['valid'].to_numpy(bool) if 'valid' in d else np.ones(len(d),bool)
 xx=(d.east_m.to_numpy()-offset[0])*scale;yy=(d.north_m.to_numpy()-offset[1])*scale
 xx[~v]=np.nan;yy[~v]=np.nan
 threshold=gap if gap is not None else (1.001 if m.startswith('OISAM') or m in ['WEN_TC','GNC'] else .101)
 breaks=np.flatnonzero(np.diff(d.time_s)>threshold)+1
 if 'block_id' in d:breaks=np.unique(np.r_[breaks,np.flatnonzero(np.diff(d.block_id.fillna(-1))!=0)+1])
 c=COL.get(m,'#64748B');ls=LS.get(m,'-');w=lw or (1.0 if m=='F04' else .7)
 ax.plot(np.insert(xx,breaks,np.nan),np.insert(yy,breaks,np.nan),color=c,ls=ls,lw=w,**kw)
 if mark and np.any(v):
  k=np.flatnonzero(v);ax.scatter(xx[k[0]],yy[k[0]],s=16,facecolors='white',edgecolors=c,zorder=6);ax.scatter(xx[k[-1]],yy[k[-1]],s=20,marker='x',color=c,zorder=6)
def panel(ax,l,t):ax.set_gid(l);ax.set_title(f'({l}) {t}',loc='left',pad=5)
def save(fig,name,axes,zh,en,notes):
 fig.canvas.draw();align=require_matplotlib_panel_alignment(fig,axes=axes,json_out=O/'qa'/(name+'.alignment.json'),overlay_svg=O/'qa'/(name+'.alignment.svg'),tolerance_pt=1.5,gutter_tolerance_pt=1.5,strict=True)
 for ext in ['pdf','svg']:fig.savefig(O/(name+'.'+ext),dpi=600)
 fig.savefig(O/(name+'.png'),dpi=600);fig.savefig(O/(name+'.tiff'),dpi=600,pil_kwargs={'compression':'tiff_lzw'});fig.savefig(O/'preview'/(name+'.png'),dpi=400)
 Image.open(O/'preview'/(name+'.png')).convert('L').save(O/'preview'/(name+'_gray.png'))
 audits={}
 for tag,args in [('text',['audit_pdf_text.py',str(O/(name+'.pdf')),'--min-pt','8','--json']),('collisions',['audit_figure_collisions.py',str(O/(name+'.pdf')),'--json-out',str(O/'qa'/(name+'.collisions.json'))])]:
  q=subprocess.run([sys.executable,str(SK/args[0]),*args[1:]],capture_output=True,text=True);(O/'qa'/(name+'.'+tag+'.log')).write_text(q.stdout+q.stderr);audits[tag]=q.returncode
 meta={'id':name,'width_mm':174,'height_mm':fig.get_figheight()*25.4,'min_font_pt':8,'preview_dpi':400,'caption_zh':zh,'caption_en':en,'notes':notes,'alignment':align['verdict'],'audits':audits,'new_solver_evaluator_provider_calls':0,'visual_review':'PENDING'}
 (O/(name+'.json')).write_text(json.dumps(meta,ensure_ascii=False,indent=2));plt.close(fig);print(name,audits,flush=True)

def fig3():
 fig,axs=plt.subplots(3,3,figsize=(174/25.4,190/25.4));fig.subplots_adjust(left=.085,right=.99,bottom=.075,top=.89,wspace=.60,hspace=.57)
 events=[];old=R/'V3论文组图_20261008/redesign_20261009/figures/data'
 for row,s in enumerate(SEQ):
  lo,hi=(40,140) if s!='BY2O' else (154.945,254.945);center=90. if s!='BY2O' else 204.945
  zlo,zhi=(88.,92.) if s!='BY2O' else (199.945,209.945);half=.5 if s!='BY2O' else .2
  ref=data(s,'REFERENCE_POI');native=data(s,'F04');q=ref[ref.elapsed_s.between(lo,hi)];origin=q[['east_m','north_m']].iloc[0].to_numpy();zc=np.array([np.interp(START[s]+center,ref.time_s,ref[k]) for k in ['east_m','north_m']])
  ax=axs[row,0]
  for m in ['REFERENCE_POI','F04']:
   d=data(s,m);d=d[d.elapsed_s.between(lo,hi)];plotxy(ax,d,m,offset=origin,lw=1 if m=='F04' else .7,mark=m=='F04')
  ax.scatter(*(zc-origin),marker='s',s=32,facecolors='none',edgecolors='#475569',lw=.7,zorder=8)
  ax.set_aspect('equal',adjustable='datalim');ax.set(xlabel='East (m)',ylabel='North (m)');ax.locator_params(nbins=3);panel(ax,chr(97+row*3),SCENE[s])
  # The local view is a true fixed physical box, without shifting one method.
  ax=axs[row,1]
  for m in ['REFERENCE_POI','LC01','LC01-S','F04']:
   d=data(s,m);d=d[d.elapsed_s.between(zlo,zhi)];plotxy(ax,d,m,offset=zc,scale=100,lw=1. if m=='F04' else .8,rasterized=True)
  ax.set(xlim=(-half*100,half*100),ylim=(-half*100,half*100),xlabel='East offset (cm)',ylabel='North offset (cm)');ax.set_aspect('equal',adjustable='box');ax.set_xticks([-half*100,0,half*100]);ax.set_yticks([-half*100,0,half*100]);panel(ax,chr(98+row*3),f'{2*half:g} m spatial view')
  ax.text(.02,.02,f'{zlo:g}–{zhi:g} s',transform=ax.transAxes,fontsize=8,va='bottom')
  ax=axs[row,2]
  for m in ['LC01','LC01-S','F04']:
   d=pd.read_csv(old/f'C01_{s}_{m}_saved_errors.csv.gz');d=d[d.elapsed_s.between(lo,hi)];tt=d.elapsed_s.to_numpy();yy=d.yaw_err_deg.to_numpy();breaks=np.flatnonzero(np.diff(tt)>.101)+1
   ax.plot(np.insert(tt,breaks,np.nan),np.insert(yy,breaks,np.nan),color=COL[m],ls=LS[m],lw=1.0 if m=='F04' else .65)
  ax.axhline(0,color='#B8B8B8',lw=.5)
  if s=='BY2O':ax.axvspan(183.94,225.95,color='#E5E7EB',zorder=0)
  ax.set(xlim=(lo,hi),xlabel='Elapsed time (s)',ylabel='Heading error (°)');ax.locator_params(nbins=3);panel(ax,chr(99+row*3),'100-s heading error')
  events.append({'sequence':s,'elapsed_start_s':lo,'elapsed_end_s':hi,'duration_s':hi-lo,'center_s':center,'zoom_source_start_s':zlo,'zoom_source_end_s':zhi,'spatial_halfwidth_m':half,'zoom_reference_east_m':zc[0],'zoom_reference_north_m':zc[1],'selection':'Fixed100s context around prior reference turn90s / registered obstruction midpoint204.945s; physical box centered on reference only; no method-error selection','zoom_crop':'All source samples in the fixed4s /10s interval retained; plotted axes clip to the stated1m /0.4m physical square; no error magnification'})
 fig.legend(handles=[Line2D([],[],color=COL[m],ls=LS[m],lw=1,label=NAME[m]) for m in ['REFERENCE_POI','F04','LC01','LC01-S']],loc='upper center',bbox_to_anchor=(.54,.99),ncol=2,columnspacing=1.3,handlelength=2.4)
 pd.DataFrame(events).to_csv(D/'F03_EVENT_WINDOWS.csv',index=False)
 save(fig,'F03_100s_routes_with_spatial_detail',list(axs.flat),'100秒事件路线、真实空间局部差距与同窗航向误差。三行依次为常规行走、大幅机身运动记录和遮挡记录。左列显示100秒完整片段，中列按固定参考中心展示1m或0.4m真实空间方框，坐标单位厘米；不同方法没有相对平移或误差倍率。方框来源分别为固定88–92秒和199.945–209.945秒数据，视窗外按空间轴裁剪。右列为同100秒航向误差，灰色仅标记实际登记遮挡。局部窗口由原参考事件和固定时长确定。','100-s event trajectories, physical spatial details and heading errors. Rows correspond to nominal walking, large-body-motion and obstruction records. Left: the entire100-s segment. Middle: a fixed1-m or0.4-m spatial square centred on the reference event position, with centimetre axes and no method-dependent shift or error magnification. Original samples from fixed88–92s or199.945–209.945s intervals are clipped only by the stated spatial viewport. Right: heading errors over the same100s; gray shading indicates the registered obstruction. All windows follow fixed reference-event rules.',{'events':events,'geographic_point':'All spatial curves use the previously registered POI midpoint','all100s_samples_retained':True,'new_absolute_alignment':False})

def fig11():
 fig,axs=plt.subplots(3,2,figsize=(174/25.4,211/25.4));fig.subplots_adjust(left=.09,right=.99,bottom=.065,top=.80,wspace=.30,hspace=.46)
 methods=[['LC01','LC01-S','EXT05C','EXT05C-S','OISAM_STRICT','F04'],['WEN_TC','GNC','OISAM_RESTART']];zooms=[]
 for row,s in enumerate(SEQ):
  for col,mm in enumerate(methods):
   ax=axs[row,col];refname='REFERENCE_POI' if col==0 else 'REFERENCE_GNSS1';ref=data(s,refname)
   for m in [refname]+mm:plotxy(ax,data(s,m),m,lw=1.0 if m=='F04' else .65,mark=m.startswith('OISAM'))
   ax.set_aspect('equal',adjustable='datalim');ax.set(xlabel='East (m)',ylabel='North (m)');ax.locator_params(nbins=3);panel(ax,chr(97+row*2+col),SCENE[s]+(' · POI' if col==0 else ' · GNSS1'));ax.set_title(f'({chr(97+row*2+col)}) '+SCENE[s]+(' · POI' if col==0 else ' · GNSS1'),loc='left',pad=16)
   center=90. if s!='BY2O' else 204.945;zc=np.array([np.interp(START[s]+center,ref.time_s,ref[k]) for k in ['east_m','north_m']]);half=.5 if s!='BY2O' else .2;zlo,zhi=(center-2,center+2) if s!='BY2O' else (center-5,center+5)
   # Centimetre differences need an inset in the POI column. The FGO paths
   # differ visibly at metre scale, so an overlaid second map adds no evidence.
   if col==0:
    ins=ax.inset_axes([.44,.42,.34,.29])
    for m in [refname]+mm:
     d=data(s,m);d=d[d.elapsed_s.between(zlo,zhi)];plotxy(ins,d,m,offset=zc,scale=100,lw=.8,rasterized=True)
    v=half*100;ins.set(xlim=(-v,v),ylim=(-v,v));ins.set_aspect('equal',adjustable='box');ins.set_xticks([-v,v]);ins.set_yticks([-v,v]);ins.tick_params(labelsize=8,pad=1);ins.set_title('Offsets (cm)',fontsize=8,pad=6)
    ax.scatter(*zc,marker='s',s=25,facecolors='none',edgecolors='#475569',lw=.6,zorder=8)
    own=data(s,'OISAM_STRICT');n=int(own.valid.sum());ax.text(.0,1.005,f'OiSAM: {n}/{END[s]-START[s]+1} epochs',transform=ax.transAxes,fontsize=8,va='bottom')
    zooms.append({'sequence':s,'point':'POI_MIDPOINT','center_elapsed_s':center,'source_start_s':zlo,'source_end_s':zhi,'physical_halfwidth_m':half,'selection':'same fixed reference event center asF03; method errors not read for selection'})
 left=['REFERENCE_POI']+methods[0];right=methods[1]
 fig.legend(handles=[Line2D([],[],color=COL[m],ls=LS[m],lw=1,label=NAME[m]) for m in left],loc='upper center',bbox_to_anchor=(.34,.99),ncol=2,columnspacing=.8,handlelength=2.3,labelspacing=.55)
 fig.legend(handles=[Line2D([],[],color=COL[m],ls=LS[m],lw=1,label=NAME[m]) for m in right],loc='upper center',bbox_to_anchor=(.82,.97),ncol=1,handlelength=2.3,labelspacing=.55)
 pd.DataFrame(zooms).to_csv(D/'F11_SPATIAL_WINDOWS.csv',index=False)
 save(fig,'F11_full_trajectory_comparison',list(axs.flat),'全部自然评价窗中的导航轨迹，按真实评价点分列。左列在POI中点显示本文、单/双位置IEKF文献与标定参数，以及单次初始化OiSAM的全部有效轨迹；右列在GNSS1天线点显示按记录缺口重新初始化的OiSAM、TC-FGO和GNC-FGO。参考线使用同一评价点；缺测和重新初始化块边界断线。OiSAM圆圈为首个动态输出，叉号为最后动态输出，左列文字保留输出分母。小窗围绕固定参考事件位置显示真实局部坐标差，没有拟合旋转/平移或人为放大误差。所有原生有效点均保留；零动态输出的方法不虚构轨迹。GINav原生IMU部分输出和相对里程计另页展示。','Navigation trajectories across the complete natural evaluation windows, separated by physical point. Left: LegSA-GINS, the literature/calibrated single- and dual-position IEKFs, and single-initialization OiSAM at the POI midpoint. Right: recorded-gap-reinitialized OiSAM, TC-FGO and GNC-FGO at GNSS1. Each reference uses the same point. Curves break across output gaps and initialization-block boundaries. Circles and crosses identify OiSAM first and last dynamic outputs; the left panels retain output counts over the full nominal windows. Insets show true spatial differences around fixed reference-defined event locations, without fitted rotations, translations or error magnification. All finite native outputs are retained; no trajectory is invented for zero dynamic support. Native GINav partial outputs and relative-only estimators are shown separately.',{'point_groups':['POI_MIDPOINT','GNSS1_ANTENNA'],'all_scenes_full_window':True,'methods':methods,'zoom_windows':zooms,'source':'data/TRAJECTORY_COVERAGE.csv plus coordinate parity tables'})

def partial():
 fig,axs=plt.subplots(1,3,figsize=(174/25.4,78/25.4));fig.subplots_adjust(left=.09,right=.99,bottom=.19,top=.78,wspace=.45)
 for j,s in enumerate(SEQ):
  ax=axs[j];ref=data(s,'REFERENCE_POI');plotxy(ax,ref,'REFERENCE_POI',lw=.6,alpha=.45)
  d=data(s,'GINAV_NATIVE');plotxy(ax,d,'GINAV_NATIVE',gap=1.5,mark=True,lw=.8);ax.scatter(d.east_m,d.north_m,color=COL['GINAV_NATIVE'],s=9,zorder=5)
  ax.set_aspect('equal',adjustable='datalim');ax.set(xlabel='East (m)',ylabel='North (m)');ax.locator_params(nbins=3);panel(ax,chr(97+j),SCENE[s]);ax.text(.03,.95,f'{int(d.valid.sum())}/{END[s]-START[s]+1} output epochs',transform=ax.transAxes,va='top',fontsize=8)
 fig.legend(handles=[Line2D([],[],color='#111827',ls='--',label='POI reference route (context)'),Line2D([],[],color=COL['GINAV_NATIVE'],marker='o',label='GINav native IMU position',markersize=3)],loc='upper center',bbox_to_anchor=(.54,.99),ncol=1,labelspacing=.3)
 save(fig,'S11_GINav_partial_trajectories',list(axs),'GINav原生INS/IMU点的部分输出。圆圈标首个输出，叉号标最后输出，全部有限点保留，超过1.5秒间隔断线。三条记录分别仅77/275、2/271、5/378个输出；常规与遮挡记录触发原速度界限失败。淡灰POI参考路线只作地理背景，评价点不同，不用于计算本图位置误差。图中没有把部分输出称作完整运行。','Partial GINav outputs at the native INS/IMU point. Circles and crosses identify first and last emitted outputs; all finite points are retained and gaps exceeding1.5s break the curves. Output support is77/275,2/271 and5/378; nominal and obstruction runs triggered the original speed-bound failure. The faint POI reference route provides geographic context only because the physical point differs; it is not used to score these plots.',{'native_point':'INS_IMU','reference_role':'POI context only; no same-point accuracy claim','all_finite_emitted_points':True})

def relative():
 fig,axs=plt.subplots(3,3,figsize=(174/25.4,174/25.4));fig.subplots_adjust(left=.09,right=.99,bottom=.075,top=.945,wspace=.45,hspace=.45)
 for i,s in enumerate(SEQ):
  for j,m in enumerate(['OFF-LIT','OFF-DEF','LEG-DR']):
   d=pd.read_csv(D/f'{s}__{m}_LOCAL.csv.gz');ax=axs[i,j];tt=d.time_s.to_numpy();br=np.flatnonzero(np.diff(tt)>.101)+1;ax.plot(np.insert(d.local_x_m,br,np.nan),np.insert(d.local_y_m,br,np.nan),color=COL[m],lw=.8);ax.plot(d.local_x_m.iloc[0],d.local_y_m.iloc[0],'o',mfc='white',mec=COL[m],ms=4);ax.plot(d.local_x_m.iloc[-1],d.local_y_m.iloc[-1],'x',color=COL[m],ms=4)
   ax.set_aspect('equal',adjustable='datalim');ax.set(xlabel='Native local x (m)',ylabel='Native local y (m)');ax.locator_params(nbins=3);panel(ax,chr(97+i*3+j),SCENE[s]+'\n'+{'OFF-LIT':'Contact InEKF: LIT','OFF-DEF':'Contact InEKF: default','LEG-DR':'Contact kinematics'}[m])
 save(fig,'S11_native_relative_trajectories',list(axs.flat),'相对状态估计方法的原生局部轨迹。各行对应三条场景记录，各列为官方接触InEKF文献参数、示例参数、接触运动学积分。各方法保留自身局部坐标和初始方向，不额外拟合到地理参考，因此本图是完整输出形状与范围展示，而非同一绝对坐标中的精度比较。圆圈和叉号分别为评价窗内首末状态；相关一次10秒对齐的误差评价在既有相对运动表中保留。','Native local trajectories of the relative-motion estimators. Rows denote the three recordings; columns show the official contact InEKF with literature and default settings and contact-kinematic integration. Every method retains its own native local gauge, without a new fit to the geographic reference. These panels show complete output shape and extent rather than absolute-position accuracy in one shared frame. Circles and crosses mark the first and last in-window states. The previously evaluated one-time10-s alignment errors remain in the companion relative-motion results.',{'new_fit_applied':False,'coordinate_gauges':'native per method, no cross-method absolute ranking','all_native_in_window_rows_retained':True})

if __name__=='__main__':
 for arg in sys.argv[1:] or ['3','11','partial','relative']:{'3':fig3,'11':fig11,'partial':partial,'relative':relative}[arg]()
