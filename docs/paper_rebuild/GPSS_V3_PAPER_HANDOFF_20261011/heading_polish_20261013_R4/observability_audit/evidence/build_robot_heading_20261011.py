"""Publication figure from seven archived native runs and saved observability spectra."""
from pathlib import Path
import os,sys,json,hashlib
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import ConnectionPatch
from profile_robot import load,OUT

from paper_style import setup,export

runs,spec,rank,win,eq,profile=load()
setup()
plt.rcParams.update({'font.size':8,'axes.labelsize':8.5,'axes.titlesize':9,'legend.fontsize':8,'path.simplify':False})
NAME='R01_proprioception_absolute_heading'
colors={-150:'#BDBDBD',-100:'#D55E00',-50:'#BDBDBD',0:'#0072B2',50:'#BDBDBD',100:'#795548',150:'#BDBDBD'}
styles={-150: (0,(1,2)),-100:(0,(5,2)),-50:(0,(3,1,1,1)),0:'-',50:(0,(5,1,1,1)),100:(0,(2,2)),150:(0,(8,2))}
fig=plt.figure(figsize=(174/25.4,130/25.4))
gs=fig.add_gridspec(2,2,left=.075,right=.985,bottom=.105,top=.845,wspace=.27,hspace=.50,width_ratios=[1.08,1])
a=fig.add_subplot(gs[:,0]); b=fig.add_subplot(gs[0,1]); c=fig.add_subplot(gs[1,1])
for ax,letter,title in [(a,'a','Estimated trajectories'),(b,'b','Heading evolution'),(c,'c','Unconstrained directions')]:
    ax.set_title(f'({letter}) {title}',loc='left',pad=5,fontweight='normal')
    ax.tick_params(length=3)
handles=[]
for yaw,r in sorted(runs.items()):
    f=r['frame'];color=colors[yaw];ls=styles[yaw]
    main=yaw in [-100,0,100]
    level=3 if main else 1
    a.plot(f.px,f.py,color=color,ls=ls,lw=1.15 if main else .60,rasterized=True,zorder=level)
    a.plot(f.px.iloc[-1],f.py.iloc[-1],marker='o',ms=3 if main else 2.3,color=color,zorder=level+1)
    b.plot(r['t'],r['psi'],color=color,ls=ls,lw=.9 if main else .60,rasterized=True,zorder=level)
    handles.append(Line2D([],[],color=color,ls=ls,lw=1.1 if main else .70,label=f'{yaw:+d}°' if yaw else '0°'))
a.plot(0,0,marker='o',color='#222222',ms=3)
a.set_xlabel('Arbitrary world x (m)');a.set_ylabel('Arbitrary world y (m)')
a.set_xlim(-115,115);a.set_ylim(-145,145);a.set_aspect('equal',adjustable='datalim')
a.set_xticks([-100,0,100]);a.set_yticks([-100,0,100])
b.set_xlabel('Elapsed time (s)');b.set_ylabel('Unwrapped yaw (°)')
b.set_xlim(0,305.197970657);b.set_xticks([0,100,200,300]);b.set_yticks([-500,0,500,1000]);b.set_ylim(-660,1370)
fig.legend(handles=handles,loc='upper center',bbox_to_anchor=(.5,.997),ncol=7,handlelength=2.25,columnspacing=1.1,title='Initial yaw in the local frame',title_fontsize=8.5)

# The input-selected largest-excitation two-contact window; no result-based choice.
w=win[win.window_id.eq('WIN003')].iloc[0]
lo=int(w.start_row);hi=int(w.end_row)+1
t0=float(runs[0]['t'][lo]);t1=float(runs[0]['t'][hi-1])
b.axvspan(t0,t1,color='#A8A8A8',alpha=.2,lw=0)
zoom=b.inset_axes([.12,.62,.40,.28])
for yaw,r in sorted(runs.items()):
    tt=r['t'][lo:hi]-t0
    inc=r['psi'][lo:hi]-r['psi'][lo]
    main=yaw in [-100,0,100]
    zoom.plot(tt,inc,color=colors[yaw],ls=styles[yaw],lw=.9 if main else .6,rasterized=True,zorder=3 if main else 1)
allinc=np.concatenate([r['psi'][lo:hi]-r['psi'][lo] for r in runs.values()])
zoom.set_xlim(-.01,t1-t0+.01);zoom.set_ylim(allinc.min()-.15,allinc.max()+.15)
zoom.set_xticks([0,.2]);zoom.set_yticks([0,2,4]);zoom.tick_params(labelsize=6.5,length=2,pad=2)
zoom.set_xlabel('Time in window (s)',fontsize=6.5,labelpad=1)
zoom.set_ylabel('Δyaw (°)',fontsize=6.5,labelpad=1)
zoom.set_title(f'{t0:.2f}–{t1:.2f} s',fontsize=6.5,pad=2)

selection=spec[spec.model.eq('BIAS_AUGMENTED_REAL_TRAJECTORY')&spec.normalization.eq('RAW_STRUCTURAL')]
markers=['o','s','^','v','D'];linetypes=['-', '--','-', '--',':']
specplot=[]
for j,(wid,g) in enumerate(selection.groupby('window_id',sort=True)):
    vals=np.sort(g.singular_value.to_numpy())
    assert np.all(vals>0)
    norm=vals/vals.max(); ncontact=int(win.loc[win.window_id.eq(wid),'contact_count'].iloc[0])
    co='#0072B2' if ncontact==4 else '#D55E00'
    c.plot(np.arange(1,len(norm)+1),norm,color=co,ls=linetypes[j],marker=markers[j],ms=2.7,lw=.75,mfc='white',mew=.6)
    specplot.extend({'window':wid,'contact_count':ncontact,'ascending_mode_index':i+1,'sigma_over_sigma_max':float(v)} for i,v in enumerate(norm))
c.set_yscale('log');c.set_ylim(1e-19,5);c.set_xlim(.5,27.5)
c.set_xticks([1,4,10,20,27]);c.set_yticks([1e-18,1e-12,1e-6,1])
c.set_ylabel('σ / σmax');c.set_xlabel('Mode index, smallest first')
c.axvspan(.5,4.5,color='#EAEAEA',zorder=0)
c.axhline(1e-9,color='#777777',lw=.65,ls=(0,(2,2)),zorder=0)
c.text(8,2e-17,'3 translations + 1 yaw',fontsize=7.5)
c.legend(handles=[Line2D([],[],color='#0072B2',lw=.9,marker='o',mfc='white',label='4 contacts'),Line2D([],[],color='#D55E00',lw=.9,marker='^',mfc='white',label='2 contacts')],loc='center right',bbox_to_anchor=(.99,.36),handlelength=1.6,fontsize=7)

source=OUT/'source_data';source.mkdir(exist_ok=True)
pd.DataFrame(specplot).to_csv(source/'observability_spectrum_plotted.csv',index=False)
rank.to_csv(source/'observability_rank_all_thresholds.csv',index=False)
win.to_csv(source/'input_selected_windows.csv',index=False)
eq.to_csv(source/'gauge_equivalence_summary.csv',index=False)
for yaw,r in sorted(runs.items()):
    f=r['frame'];pd.DataFrame({'timestamp_ns':f.timestamp_ns,'elapsed_s':r['t'],'local_x_m':f.px,'local_y_m':f.py,'local_z_m':f.pz,'unwrapped_yaw_deg':r['psi']}).to_csv(source/f'native_initial_yaw_{yaw:+04d}.csv.gz',index=False,compression='gzip')
cap_en='Absolute heading freedom under proprioceptive sensing. (a) Seven stored runs of the same IMU and foot-contact data, initialized at yaw angles from −150° to +150°, give rotated trajectories in an arbitrary local frame. The 0° and ±100° runs are highlighted; dots denote the common start and individual endpoints. (b) Their unwrapped yaw histories retain the initial offsets. The inset shows yaw increments over an input-selected 0.216 s two-contact interval; all seven curves overlap. (c) The saved observability spectra of the bias-augmented model for five preselected contact intervals, each divided by its own largest singular value and ordered from smallest to largest. Two four-contact and three two-contact windows contain 27 and 21 state dimensions, respectively. The first four singular directions fall below the relative rank threshold (dashed line, 10⁻⁹), consistently with three global translations and one global yaw degree of freedom. Different markers denote different windows. Removing only each run’s initial rotation gives a maximum position discrepancy of 1.90 × 10⁻⁷ m. The experiment demonstrates equivalent global orientations under the same proprioceptive observations.'
cap_zh='机器人自身观测下的绝对航向自由度。（a）同一组 IMU 与足端接触数据的七次已保存运行，初始航向覆盖 −150° 至 +150°，在任意局部坐标系中形成相互旋转的轨迹。彩色突出 0° 与 ±100°，圆点表示共同起点与各轨迹终点。（b）展开后的航向演化保留初始方向差异；插图为预先根据输入选定的 0.216 s 双接触窗口内航向增量，七条曲线重合。（c）含偏置模型在五个预选接触窗口的已保存可观测性奇异值，分别除以各自最大奇异值，并按从小到大排序。两段四接触与三段双接触窗口分别对应 27 维和 21 维状态；前四个方向均低于相对秩阈值（虚线，10⁻⁹），对应三维全局平移与一维全局航向自由度。不同标记表示不同窗口。仅消除各运行初始旋转后，最大位置差为 1.90 × 10⁻⁷ m。该组实验验证同一自身观测下全局方向的等价性。'
meaning='读图顺序：左图说明同样自身观测可以对应多个全局方向；右上说明初始方向差异在时间中保留，而局部航向变化相同；右下给出这一现象的结构来源。它支持论文对外部绝对方向约束的需求。'
notes={'claim':'The IMU/contact system constrains relative motion but has a global yaw gauge freedom.','native_points':profile['native_points_read'],'all_native_rows_plotted':True,'absolute_yaw_definition':'degrees(unwrap(atan2(R10,R00))); conventional local Euler yaw, opposite the archived angle around the downward gravity vector.','trajectory_frame':'arbitrary local x/y; not geodetic East/North','inset_definition':'psi(t)-psi(t_window_start), input-selected highest-excitation two-contact interval WIN003','inset_original_rows':[lo,hi-1],'inset_elapsed_s':[t0,t1],'spectrum':'all singular values of the stored bias-augmented raw structural model; per-window largest-value normalization; ascending rank does not denote matching physical modes across dimensions','other_read_spectra':'bias-free and column-normalized diagnostic spectra fully read in profile, not drawn to avoid repeating the same structural claim','native_relative_yaw_difference_max_deg':max(x['relative_yaw_difference_max_deg'] for x in profile['native_runs']),'solver_evaluator_provider_calls':[0,0,0]}
record=export(fig,OUT,NAME,caption_en=cap_en,caption_zh=cap_zh,meaning_zh=meaning,sources=[x['path'] for x in profile['full_reads']],technical_notes=notes,axes=[a,b,c])
(OUT/'CAPTIONS.md').write_text('# 机器人自身观测与绝对航向\n\n'+cap_zh+'\n\n'+cap_en+'\n\n'+meaning+'\n',encoding='utf-8')
