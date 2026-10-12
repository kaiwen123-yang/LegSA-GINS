"""Equivalent global directions under the same proprioceptive data."""
from pathlib import Path
import json,sys,subprocess,shutil
import numpy as np,pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import FancyArrowPatch
from PIL import Image
OUT=Path(__file__).parent
SRC=OUT/'source_data'
SK=Path('/mnt/c/Users/ykw/.codex/skills/nature-figure/scripts')
sys.path.insert(0,str(SK))
from audit_panel_alignment import require_matplotlib_panel_alignment
for n in ['source_data','preview','qa']:(OUT/n).mkdir(exist_ok=True)
plt.rcParams.update({'font.family':'sans-serif','font.sans-serif':['Arial','Liberation Sans','DejaVu Sans'],'font.size':8,'axes.labelsize':8,'axes.titlesize':8.5,'xtick.labelsize':8,'ytick.labelsize':8,'legend.fontsize':8,'legend.frameon':False,'axes.spines.top':False,'axes.spines.right':False,'axes.linewidth':.6,'xtick.direction':'out','ytick.direction':'out','xtick.major.size':2.5,'ytick.major.size':2.5,'pdf.fonttype':42,'svg.fonttype':'none','path.simplify':False,'savefig.facecolor':'white'})
COL={-150:'#8A8F98',-100:'#E76F51',-50:'#8A8F98',0:'#2563EB',50:'#8A8F98',100:'#009E9A',150:'#8A8F98'}
LS={-150:':',-100:'--',-50:'-.',0:'-',50:(0,(3,1,1,1)),100:'-.',150:(0,(6,2))}
runs={int(p.name.split('_')[-1].split('.')[0]):pd.read_csv(p) for p in SRC.glob('native_initial_yaw_*.csv.gz')}
assert len(runs)==7 and all(len(d)==63277 for d in runs.values())
base=runs[0];anchor=base[['local_x_m','local_y_m','local_z_m']].to_numpy();time=base.elapsed_s.to_numpy()
fig=plt.figure(figsize=(174/25.4,126/25.4))
gs=fig.add_gridspec(2,2,left=.10,right=.975,bottom=.115,top=.83,wspace=.36,hspace=.65,height_ratios=[3.6,1])
a=fig.add_subplot(gs[0,0]);b=fig.add_subplot(gs[0,1]);c=fig.add_subplot(gs[1,:])
res=pd.DataFrame({'elapsed_s':time});summary=[]
for yaw in [-150,-50,50,150,-100,100,0]:
 d=runs[yaw];assert np.array_equal(d.timestamp_ns.to_numpy(),base.timestamp_ns.to_numpy())
 p=d[['local_x_m','local_y_m','local_z_m']].to_numpy();ang=np.deg2rad(yaw);rot=np.array([[np.cos(ang),np.sin(ang),0],[-np.sin(ang),np.cos(ang),0],[0,0,1]])
 q=p@rot.T;delta=np.linalg.norm(q-anchor,axis=1);res[f'yaw_{yaw:+04d}_position_difference_m']=delta
 dyaw=(d.unwrapped_yaw_deg.to_numpy()-d.unwrapped_yaw_deg.iloc[0])-(base.unwrapped_yaw_deg.to_numpy()-base.unwrapped_yaw_deg.iloc[0]);res[f'yaw_{yaw:+04d}_increment_difference_deg']=dyaw
 main=yaw in [-100,0,100];lw=1.15 if main else .65;zorder=5 if main else 2
 a.plot(p[:,0],p[:,1],color=COL[yaw],ls=LS[yaw],lw=lw,zorder=zorder)
 b.plot(q[:,0],q[:,1],color=COL[yaw],ls=LS[yaw],lw=lw,zorder=zorder)
 a.plot(p[-1,0],p[-1,1],marker='o',ms=3,color=COL[yaw],zorder=zorder)
 if yaw!=0:c.plot(time,delta/1e-7,color=COL[yaw],ls=LS[yaw],lw=1.0 if main else .65,zorder=zorder)
 summary.append({'initial_yaw_deg':yaw,'states':len(d),'position_residual_max_m':float(delta.max()),'heading_increment_residual_max_deg':float(abs(dyaw).max()),'first_native_yaw_deg':float(d.unwrapped_yaw_deg.iloc[0]),'same_timestamps':True})
# The arrows are known initial Euler-yaw directions, not course inferred from paths.
for yaw in [-100,0,100]:
 ang=np.deg2rad(yaw);end=(46*np.cos(ang),46*np.sin(ang));a.annotate('',xy=end,xytext=(0,0),arrowprops={'arrowstyle':'-|>','mutation_scale':10,'color':COL[yaw],'lw':1.4},zorder=10)
for ax in [a,b]:
 # Same metric limits and physical scaling in the two main panels.
 ax.set(xlim=(-150,150),ylim=(-150,150),xlabel='Local x (m)',ylabel='Local y (m)');ax.set_xticks([-100,0,100]);ax.set_yticks([-100,0,100]);ax.set_aspect('equal',adjustable='box');ax.plot(0,0,'k*',ms=5,zorder=12)
a.set_title('(a) Different absolute directions',loc='left',pad=5);b.set_title('(b) The same relative path',loc='left',pad=5)
b.text(.97,.05,'All seven paths overlap',transform=b.transAxes,ha='right',va='bottom',fontsize=8,color=COL[0])
c.set(xlim=(time[0],time[-1]),ylim=(-.03,2.05),xlabel='Elapsed time (s)');c.set_ylabel('Position difference\n(10⁻⁷ m)',fontfamily='DejaVu Sans');c.set_xticks([0,100,200,300]);c.set_yticks([0,1,2]);c.set_title('(c) Difference after removing the known rotation',loc='left',pad=5)
maximum=max(x['position_residual_max_m'] for x in summary);c.text(.99,1.15,'Maximum: 1.89 × 10⁻⁷ m',transform=c.transAxes,ha='right',va='bottom',fontsize=8,fontfamily='DejaVu Sans')
handles=[Line2D([],[],color=COL[y],ls=LS[y],lw=1.3,label=f'{y:+d}°' if y else '0°') for y in [-100,0,100]]+[Line2D([],[],color='#8A8F98',lw=.8,label='Other four initial yaws')]
fig.legend(handles=handles,loc='upper center',bbox_to_anchor=(.53,.991),ncol=4,columnspacing=1.1,title='Same IMU and foot-contact inputs',title_fontsize=8.5)
fig.text(.52,.785,'Known rotation\nremoved',ha='center',fontsize=8,color='#444444')
arrow=FancyArrowPatch((.465,.72),(.612,.72),transform=fig.transFigure,arrowstyle='-|>',mutation_scale=11,lw=.8,color='#777777');fig.add_artist(arrow)
name='F04_absolute_direction_relative_motion'
fig.canvas.draw()
require_matplotlib_panel_alignment(fig,axes=[a,b],json_out=str(OUT/'qa'/f'{name}.alignment.json'),
 overlay_svg=str(OUT/'qa'/f'{name}.alignment.svg'),tolerance_pt=1.5,gutter_tolerance_pt=1.5,strict=True)
for ext in ['pdf','svg']:fig.savefig(OUT/(name+'.'+ext))
fig.savefig(OUT/(name+'.png'),dpi=600);fig.savefig(OUT/(name+'.tiff'),dpi=600,pil_kwargs={'compression':'tiff_lzw'});fig.savefig(OUT/'preview'/(name+'.png'),dpi=400)
Image.open(OUT/'preview'/(name+'.png')).convert('L').save(OUT/'preview'/(name+'_gray.png'))
res.to_csv(OUT/'source_data/ALL_NATIVE_ALIGNMENT_RESIDUALS.csv.gz',index=False);pd.DataFrame(summary).to_csv(OUT/'source_data/ALIGNMENT_SUMMARY.csv',index=False)
# Numerical source tables are the byte-identical local copies provided with R2.
qa={}
for tag,args in [('text',['audit_pdf_text.py',str(OUT/(name+'.pdf')),'--min-pt','8','--json']),('collisions',['audit_figure_collisions.py',str(OUT/(name+'.pdf')),'--json-out',str(OUT/'qa'/(name+'.collisions.json'))])]:
 r=subprocess.run([sys.executable,str(SK/args[0]),*args[1:]],capture_output=True,text=True);(OUT/'qa'/(name+'.'+tag+'.log')).write_text(r.stdout+r.stderr);qa[tag]=r.returncode
notes={'id':name,'width_mm':174,'height_mm':126,'minimum_font_pt':8,'caption_zh':'同一自身观测下的全局方向自由度。（a）相同IMU与足端接触数据、七种已知初始航向产生相互旋转的轨迹，突出0°与±100°；起点箭头表示已知初始Euler航向，不由轨迹切线推断。星号为共同起点，圆点为终点。（b）仅消除每次运行已知的初始绕z轴旋转后，七条相对路径重合；无尺度、平移、时间或拟合航向对齐。（c）同一时刻与0°运行相比的三维位置差，纵轴以10⁻⁷ m为单位，所有原生历元保留。最大差约1.9×10⁻⁷ m，解释了（b）曲线在图面上重合的原因。两张主面板使用相同、等比例的任意局部坐标；它们不是地理真值误差。完整接触窗口秩谱和四维全局自由度结果随图保留。','caption_en':'Global heading freedom under identical proprioceptive observations. (a) Seven runs of the same IMU and foot-contact inputs, initialized with different known yaw angles, produce globally rotated trajectories. The 0° and ±100° cases are highlighted; arrows show the known initial Euler-yaw directions, not the trajectory tangents. The star is the common start and dots are endpoints. (b) Removing only the known initial rotation makes all seven relative paths coincide; no fitted yaw, scale, translation or time alignment is applied. (c) Three-dimensional position differences relative to the 0° run at identical native epochs, expressed in units of 10⁻⁷ m. The maximum discrepancy is about 1.9×10⁻⁷ m. Both main panels use the same equal-scale arbitrary local coordinates; these differences are not errors against geographic ground truth. Full structural spectra and rank results accompany the figure.','native_runs':7,'native_rows_per_run':63277,'native_rows_total':sum(len(d) for d in runs.values()),'max_three_dimensional_position_residual_m':maximum,'max_heading_increment_residual_deg':max(x['heading_increment_residual_max_deg'] for x in summary),'alignment':'p_aligned = Rz(-known_initial_yaw) p; native timestamps identical; no fit or translation','arrow_definition':'Body +x projection from known initial conventional Euler yaw; x=cos(yaw), y=sin(yaw); first native yaw values verified in summary','all_native_rows_retained':True,'new_solver_evaluator_provider_calls':0,'source_paths':[str(p) for p in sorted(SRC.glob('*'))],'full_spectral_sources_preserved':True,'audits':qa,'visual_review':'PENDING'}
(OUT/(name+'.json')).write_text(json.dumps(notes,ensure_ascii=False,indent=2));print('Figure4',qa,'max position',maximum,'yaw',notes['max_heading_increment_residual_deg'],flush=True)
