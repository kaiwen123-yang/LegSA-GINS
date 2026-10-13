"""R5: full routes with wide, grouped, complete-extent spatial details."""
from pathlib import Path
import json,sys,subprocess
import numpy as np,pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Rectangle
from PIL import Image
O=Path(__file__).parent;D=O/'data';R=Path('/mnt/g/LegSA-GINS-project');R3=R/'V3正文精修_20261012_R3/navigation/data';R4=R/'V3正文精修_20261013_R4/navigation/data';SK=Path('/mnt/c/Users/ykw/.codex/skills/nature-figure/scripts')
for p in [D,O/'preview',O/'qa']:p.mkdir(exist_ok=True)
sys.path.insert(0,str(SK));from audit_panel_alignment import require_matplotlib_panel_alignment
SEQ=['BY2','BY2H','BY2O'];SCENE={'BY2':'Nominal walking','BY2H':'Large body motion','BY2O':'Antenna obstruction'}
COL={'REFERENCE_POI':'#111111','F04':'#004B9B','LC01':'#B13A17','LC01-S':'#006F6B','EXT05C':'#7E1E1E','EXT05C-S':'#6D28A8','OISAM_RESTART_POI':'#006782','WEN_TC':'#17632E','GNC':'#B0005A'}
LS={'REFERENCE_POI':(0,(5,2)),'F04':'-','LC01':(0,(6,2)),'LC01-S':(0,(2,1)),'EXT05C':(0,(6,2)),'EXT05C-S':(0,(2,1)),'OISAM_RESTART_POI':'-.','WEN_TC':(0,(7,2)),'GNC':'-'}
NAME={'REFERENCE_POI':'Truth','F04':'LegSA-GINS','LC01':'Dual-pos. IEKF (LIT)','LC01-S':'Dual-pos. IEKF (cal.)','EXT05C':'Single-pos. IEKF (LIT)','EXT05C-S':'Single-pos. IEKF (cal.)','OISAM_RESTART_POI':'OiSAM (reinitialized)','WEN_TC':'TC-FGO','GNC':'GNC-FGO'}
ALL=['WEN_TC','GNC','LC01','LC01-S','EXT05C','EXT05C-S','OISAM_RESTART_POI','F04'];GROUPS=[('Dual-position IEKF',['LC01','LC01-S']),('Single-position IEKF',['EXT05C','EXT05C-S']),('OiSAM (reinitialized)',['OISAM_RESTART_POI'])]
plt.rcParams.update({'font.family':'sans-serif','font.sans-serif':['Arial','Liberation Sans','DejaVu Sans'],'font.size':8,'axes.labelsize':8,'axes.titlesize':8.5,'xtick.labelsize':8,'ytick.labelsize':8,'legend.fontsize':8,'legend.frameon':False,'axes.spines.top':False,'axes.spines.right':False,'axes.linewidth':.7,'xtick.direction':'out','ytick.direction':'out','xtick.major.size':2.5,'ytick.major.size':2.5,'pdf.fonttype':42,'svg.fonttype':'none','path.simplify':False,'savefig.facecolor':'white'})
cache={};count=[];limits=[]
def read(s,m):
 k=(s,m)
 if k not in cache:
  p=(R4 if m=='OISAM_RESTART_POI' else R3)/f'{s}__{m}.csv.gz';cache[k]=pd.read_csv(p);assert np.all(np.diff(cache[k].time_s.to_numpy())>0)
 return cache[k].copy()
def line(ax,q,m,origin=(0,0),scale=1,detail=False,record=None):
 valid=q.valid.to_numpy(bool);xx=(q.east_m.to_numpy()-origin[0])*scale;yy=(q.north_m.to_numpy()-origin[1])*scale;xx[~valid]=np.nan;yy[~valid]=np.nan
 gap=1.001 if m.startswith('OISAM') or m in ['WEN_TC','GNC'] else .101;br=np.flatnonzero(np.diff(q.time_s)>gap)+1
 if 'block_id' in q:br=np.unique(np.r_[br,np.flatnonzero(np.diff(q.block_id.fillna(-1))!=0)+1])
 lw=1.35 if m=='F04' else 1.05 if detail else .75
 ax.plot(np.insert(xx,br,np.nan),np.insert(yy,br,np.nan),color=COL[m],ls=LS[m],lw=lw,zorder=6 if m=='F04' else 4 if m=='REFERENCE_POI' else 5)
 if m=='GNC' and len(q):
  ii=np.arange(0,len(q),20);ii=ii[valid[ii]];ax.scatter(xx[ii],yy[ii],s=5,marker='D',color=COL[m],linewidth=0,zorder=7)
 if record is not None:count.append({**record,'method':m,'rows_in_source_window':len(q),'finite_points':int(valid.sum())})

fig=plt.figure(figsize=(174/25.4,226/25.4));outer=fig.add_gridspec(3,2,width_ratios=[1,1.82],left=.082,right=.985,bottom=.063,top=.865,wspace=.26,hspace=.27)
main_axes=[];detail_axes=[];ids=[]
for i,s in enumerate(SEQ):
 start,end=(40.,140.) if s!='BY2O' else (154.945,254.945);lo,hi=(88.,92.) if s!='BY2O' else (228.,233.);center=(lo+hi)/2
 ref=read(s,'REFERENCE_POI');tc=ref.elapsed_s.to_numpy();origin=np.array([np.interp(center,tc,ref[k]) for k in ['east_m','north_m']])
 ax=fig.add_subplot(outer[i,0]);main_axes.append(ax);ids.append(chr(97+2*i))
 for m in ALL+['REFERENCE_POI']:line(ax,read(s,m),m,record={'sequence':s,'role':'full_route','group':'overview'})
 context=ref[ref.elapsed_s.between(start,end)];ax.plot(context.east_m,context.north_m,color='#111111',lw=1.55,ls=(0,(5,2)),zorder=8)
 ax.scatter(context.east_m.iloc[0],context.north_m.iloc[0],s=18,facecolors='white',edgecolors='#111111',zorder=9);ax.scatter(context.east_m.iloc[-1],context.north_m.iloc[-1],s=18,marker='s',facecolors='white',edgecolors='#111111',zorder=9)
 ax.set_aspect('equal',adjustable='datalim');ax.set(xlabel='East (m)' if i==2 else '',ylabel='North (m)');ax.locator_params(nbins=3)
 ax.set_title(f'({chr(97+2*i)}) {SCENE[s]}\nContext: {start:g}–{end:g} s',loc='left',pad=3,fontsize=8)
 # All compared local points define one shared extent per scene. No viewport crop.
 local={}
 for m in ['REFERENCE_POI','F04','LC01','LC01-S','EXT05C','EXT05C-S','OISAM_RESTART_POI']:
  q=read(s,m);local[m]=q[q.elapsed_s.between(lo,hi)]
 cloud=np.vstack([(q.loc[q.valid,['east_m','north_m']].to_numpy()-origin)*100 for q in local.values()]);raw_min=cloud.min(0);raw_max=cloud.max(0);mid=(raw_min+raw_max)/2
 inner=outer[i,1].subgridspec(3,1,hspace=.36)
 row_axes=[]
 for j,(label,members) in enumerate(GROUPS):
  az=fig.add_subplot(inner[j]);row_axes.append(az);detail_axes.append(az);ids.append(f'{chr(98+2*i)}{j+1}')
  for m in ['REFERENCE_POI']+members+['F04']:line(az,local[m],m,origin,100,True,{'sequence':s,'role':'complete_local_segment','group':label})
  title=(f'({chr(98+2*i)}) POI detail: {lo:g}–{hi:g} s\n' if j==0 else '')+label
  az.set_title(title,loc='left',pad=1,fontsize=8,linespacing=1.55 if j==0 else 1.2)
  az.tick_params(labelbottom=j==2,pad=1);az.locator_params(axis='x',nbins=4);az.locator_params(axis='y',nbins=3)
  if j==1:az.set_ylabel('North offset (cm)')
  if j==2:az.set_xlabel('East offset (cm)',labelpad=2)
 # Match geometry to the long strip, then expand only (never crop) to equal metre scale.
 fig.canvas.draw();box=row_axes[0].get_position();ratio=box.width*174/(box.height*226)
 required=raw_max-raw_min+np.array([20.,8.]);sx=max(required[0],required[1]*ratio);sy=sx/ratio
 for az in row_axes:
  az.set_xlim(mid[0]-sx/2,mid[0]+sx/2);az.set_ylim(mid[1]-sy/2,mid[1]+sy/2);az.set_aspect('equal',adjustable='box')
  az.set_yticks([-10,0,10] if s=='BY2O' else [-20,0,20])
  assert cloud[:,0].min()>=az.get_xlim()[0] and cloud[:,0].max()<=az.get_xlim()[1]
  assert cloud[:,1].min()>=az.get_ylim()[0] and cloud[:,1].max()<=az.get_ylim()[1]
 # The ROI box has the exact physical bounds of the full-extent local panels.
 xy0=origin+np.array([mid[0]-sx/2,mid[1]-sy/2])/100
 main_axes[-1].add_patch(Rectangle(xy0,sx/100,sy/100,fill=False,edgecolor='#111111',lw=.95,zorder=10))
 main_axes[-1].annotate('Detail',xy=origin,xytext=(.60,.44),textcoords='axes fraction',fontsize=8,ha='center',arrowprops={'arrowstyle':'->','lw':.65,'color':'#111111'},zorder=11)
 limits.append({'sequence':s,'local_start_s':lo,'local_end_s':hi,'context_start_s':start,'context_end_s':end,'raw_extent_min_cm':raw_min.tolist(),'raw_extent_max_cm':raw_max.tolist(),'display_xlim_cm':list(row_axes[0].get_xlim()),'display_ylim_cm':list(row_axes[0].get_ylim()),'same_extent_for_all_three_groups':True,'points_outside_view':0,'local_plot_width_mm':box.width*174,'local_plot_height_mm':box.height*226,'physical_aspect_ratio':ratio})
order=['REFERENCE_POI','F04','LC01','LC01-S','EXT05C','EXT05C-S','OISAM_RESTART_POI','WEN_TC','GNC']
fig.legend(handles=[Line2D([],[],color=COL[m],ls=LS[m],marker='D' if m=='GNC' else None,markersize=3,lw=1.2,label=NAME[m]) for m in order],loc='upper center',bbox_to_anchor=(.54,.999),ncol=3,columnspacing=1.0,handlelength=2.7,labelspacing=.55)
fig.canvas.draw();name='F03_integrated_routes_and_heading'
# Comparable groups: overview columns, and each local-method row across scenes.
axes=[];names=[]
for i in range(3):
 axes.append(main_axes[i]);names.append(chr(97+2*i))
 for j in range(3):axes.append(detail_axes[i*3+j]);names.append(f'{chr(98+2*i)}{j+1}')
alignment=require_matplotlib_panel_alignment(fig,axes=axes,panel_ids=names,column_groups=[['a','c','e'],['b1','d1','f1'],['b2','d2','f2'],['b3','d3','f3']],json_out=O/'qa'/(name+'.alignment.json'),overlay_svg=O/'qa'/(name+'.alignment.svg'),tolerance_pt=1.5,gutter_tolerance_pt=1.5,strict=True)
for ext in ['pdf','svg']:fig.savefig(O/(name+'.'+ext),dpi=600)
fig.savefig(O/(name+'.png'),dpi=600);fig.savefig(O/(name+'.tiff'),dpi=600,pil_kwargs={'compression':'tiff_lzw'});fig.savefig(O/'preview'/(name+'.png'),dpi=400);Image.open(O/'preview'/(name+'.png')).convert('L').save(O/'qa'/(name+'_gray.png'))
pd.DataFrame(count).to_csv(D/'SOURCE_POINT_COUNTS.csv',index=False);pd.DataFrame(limits).to_csv(D/'LOCAL_EXTENTS_AND_WINDOWS.csv',index=False)
audits={}
for tag,args in [('text',['audit_pdf_text.py',str(O/(name+'.pdf')),'--min-pt','8','--json']),('collisions',['audit_figure_collisions.py',str(O/(name+'.pdf')),'--json-out',str(O/'qa'/(name+'.collisions.json'))])]:
 q=subprocess.run([sys.executable,str(SK/args[0]),*args[1:]],capture_output=True,text=True);(O/'qa'/(name+'.'+tag+'.log')).write_text(q.stdout+q.stderr);audits[tag]=q.returncode
meta={'id':name,'title_zh':'完整路线与按方法分组的空间细节','claim_zh':'在完整路线覆盖接近时，按方法组放大的同点空间曲线显示真实局部差异；航向优劣由图9单独检验。','width_mm':174,'height_mm':226,'minimum_font_pt':8,'preview_dpi':400,'all_main_configurations':ALL,'groups':GROUPS,'no_local_point_cropping':True,'source_point_counts':'data/SOURCE_POINT_COUNTS.csv','source_R3_directory':str(R3),'source_R4_directory':str(R4),'windows':limits,'color_palette':COL,'alignment':alignment['verdict'],'audits':audits,'new_solver_evaluator_provider_calls':0,'frozen_metrics_changed':False,'visual_review':'PENDING'}
(O/(name+'.json')).write_text(json.dumps(meta,ensure_ascii=False,indent=2));print(json.dumps({'figure':name,'audits':audits,'alignment':alignment['verdict'],'local_width_mm':[v['local_plot_width_mm'] for v in limits],'clipped_points':0}))
