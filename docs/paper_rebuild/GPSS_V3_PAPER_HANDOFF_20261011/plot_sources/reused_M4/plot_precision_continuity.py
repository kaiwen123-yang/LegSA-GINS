"""Matched saved errors and actual output intervals for the two navigation systems."""
from pathlib import Path
import sys, json, os
import numpy as np
import pandas as pd
from matplotlib.lines import Line2D
from matplotlib.patches import Rectangle

STYLE=Path('/home/kaiwen/research/LegSA-GINS-WORKTREES/audit-code-xbpg-20261001/docs/paper_rebuild/GPSS_V3_FIGURES_20261008/redesign_20261009')
sys.path.insert(0,str(STYLE))
from paper_style import setup,panel,export,plt,MM

OUT=Path(__file__).resolve().parent
DATA=OUT/'data'
setup()
COL={'V3':'#0072B2','OISAM_STRICT':'#D55E00','OISAM_SEGMENTED':'#009E73'}
LS={'V3':'-','OISAM_STRICT':'--','OISAM_SEGMENTED':(0,(4,1,1,1))}
METHODS=['V3','OISAM_STRICT','OISAM_SEGMENTED']
NAMES=['LegSA-GINS','OiSAM-FGO','OiSAM-FGO (gap reinitialization)']
SEQS=['BY2','BY2H','BY2O']
LENGTH={'BY2':274.,'BY2H':270.,'BY2O':377.}
LABELS={'BY2':'Nominal\nwalking','BY2H':'Large body\nmotion','BY2O':'Antenna\nobstruction'}

def main():
    paired={s:pd.read_csv(DATA/(s+'_COMMON_POI.csv.gz')) for s in SEQS}
    intervals=pd.read_csv(DATA/'OUTPUT_INTERVALS.csv')
    epochs=pd.read_csv(DATA/'OUTPUT_EPOCHS.csv.gz')
    gaps=pd.read_csv(DATA/'GAPS.csv')
    metrics=pd.read_csv(DATA/'EXISTING_COMMON_POI_METRICS.csv')
    for s,n in [('BY2',274),('BY2H',0),('BY2O',54)]:
        assert len(paired[s])==n
        if n:
            assert paired[s].elapsed_s.is_monotonic_increasing
            assert np.isfinite(paired[s].select_dtypes('number').to_numpy()).all()

    fig=plt.figure(figsize=(174*MM,175*MM))
    boxes=[(.125,.69,.37,.225),(.615,.69,.37,.225),
           (.125,.38,.37,.225),(.615,.38,.37,.225),
           (.125,.075,.50,.215),(.815,.075,.17,.215)]
    axes=[fig.add_axes(box) for box in boxes]
    for ax,gid in zip(axes,'abcdef'):ax.set_gid(gid)
    for col,s in enumerate(['BY2','BY2O']):
        d=paired[s]
        for row,quantity in enumerate(['horizontal_err_m','yaw_err_deg']):
            ax=axes[row*2+col]
            for m,prefix in [('OISAM_STRICT','oisam'),('V3','v3')]:
                ax.plot(d.elapsed_s,d[prefix+'_'+quantity],color=COL[m],ls=LS[m],lw=.95,
                        marker='o' if m=='V3' else 's',ms=1.65 if s=='BY2O' else 1.2,
                        markerfacecolor='white' if m=='OISAM_STRICT' else COL[m],mew=.45,
                        markevery=1 if s=='BY2O' else 7,zorder=3 if m=='V3' else 2)
            ax.set_xlim(0,274 if s=='BY2' else 55)
            ax.set_xticks([0,100,200] if s=='BY2' else [0,15,30,45])
            ax.tick_params(pad=3)
            if row==0:
                ax.set_ylim(0,.48 if s=='BY2' else .095)
                ax.set_yticks([0,.15,.30,.45] if s=='BY2' else [0,.03,.06,.09])
                panel(ax,'ab'[col],'Nominal walking' if s=='BY2' else 'Antenna obstruction (initial)')
                if col==0:ax.set_ylabel('Horizontal error (m)')
            else:
                ax.axhline(0,color='#999999',ls=':',lw=.6,zorder=0)
                ax.set_ylim((-7.5,10) if s=='BY2' else (-3.5,4.2))
                ax.set_yticks([-5,0,5,10] if s=='BY2' else [-3,0,3])
                panel(ax,'cd'[col])
                if col==0:ax.set_ylabel('Heading error (°)')
                ax.set_xlabel('Elapsed time (s)')

    availability=axes[4]
    centers={'BY2':7.6,'BY2H':4.1,'BY2O':.6}
    offsets={'V3':.8,'OISAM_STRICT':0.,'OISAM_SEGMENTED':-.8}
    for s in SEQS:
        for m in METHODS:
            y=centers[s]+offsets[m]
            selected=intervals[(intervals.sequence==s)&(intervals.method==m)]
            if not selected.empty:
                availability.plot([0,LENGTH[s]],[y,y],color='#E8E8E8',lw=1.5,zorder=0,solid_capstyle='butt')
            for _,r in selected.iterrows():
                availability.plot([r.elapsed_start_s,r.elapsed_end_s],[y,y],
                  color=COL[m],ls='-',lw=2.4,solid_capstyle='butt')
            if selected.empty:
                availability.text(120,y,'No output',fontsize=7.3,color='#666666',ha='center',va='center')
        priors=epochs[(epochs.sequence==s)&(epochs.method=='OISAM_SEGMENTED')&
                      (epochs.in_window==True)&(epochs.prior_only==1)]
        availability.scatter(priors.elapsed_s,np.full(len(priors),centers[s]-.8),s=15,
                             facecolors='white',edgecolors=COL['OISAM_SEGMENTED'],lw=.8,zorder=5)
    availability.set_ylim(-.8,9.2);availability.set_xlim(0,390)
    availability.set_xticks([0,100,200,300]);availability.set_yticks([centers[s] for s in SEQS],[LABELS[s] for s in SEQS])
    availability.tick_params(axis='y',length=0,labelsize=7.6,pad=5)
    availability.spines['left'].set_visible(False)
    availability.set_xlabel('Elapsed time (s)')
    panel(availability,'e','Available output')
    availability.add_patch(Rectangle((52,-.43),8,2.06,facecolor='none',edgecolor='#444444',lw=.65,zorder=6))

    zoom=axes[5]
    focus=intervals[intervals.sequence=='BY2O']
    for j,m in enumerate(METHODS):
        y=2-j
        zoom.plot([52,60],[y,y],color='#E8E8E8',lw=1.5,zorder=0)
        for _,r in focus[focus.method==m].iterrows():
            if r.elapsed_end_s<52 or r.elapsed_start_s>60:continue
            zoom.plot([max(52,r.elapsed_start_s),min(60,r.elapsed_end_s)],[y,y],
                      color=COL[m],ls='-',lw=2.4,solid_capstyle='butt')
        if m!='V3':
            valid=epochs[(epochs.sequence=='BY2O')&(epochs.method==m)&(epochs.valid==1)&
                         (epochs.prior_only==0)&(epochs.elapsed_s>=52)&(epochs.elapsed_s<=60)]
            zoom.scatter(valid.elapsed_s,np.full(len(valid),y),color=COL[m],marker='s' if m=='OISAM_STRICT' else '^',s=12,zorder=4)
    priors=epochs[(epochs.sequence=='BY2O')&(epochs.method=='OISAM_SEGMENTED')&
                  (epochs.prior_only==1)&(epochs.elapsed_s>=52)&(epochs.elapsed_s<=60)]
    zoom.scatter(priors.elapsed_s,np.zeros(len(priors)),s=24,facecolors='white',edgecolors=COL['OISAM_SEGMENTED'],lw=.9,zorder=5)
    source_gap=gaps[(gaps.sequence=='BY2O')&(gaps.method=='SOURCE_IMU')].iloc[0]
    left=float(source_gap.left_s)-3186.;right=float(source_gap.right_s)-3186.
    zoom.axvspan(left,right,color='#D8D8D8',alpha=.65,lw=0,zorder=0)
    zoom.set_xlim(52,60);zoom.set_xticks([52,56,60]);zoom.set_ylim(-.8,2.8)
    zoom.set_yticks([2,1,0],['LegSA-GINS','OiSAM-FGO','Reinitialized'])
    zoom.tick_params(axis='y',length=0,labelsize=7.4,pad=4)
    zoom.spines['left'].set_visible(False);zoom.set_xlabel('Elapsed time (s)',fontsize=8)
    panel(zoom,'f','Gap detail')

    handles=[Line2D([],[],color=COL[m],ls=LS[m],lw=1.3,label=n) for m,n in zip(METHODS,NAMES)]
    fig.legend(handles=handles,loc='upper center',bbox_to_anchor=(.555,.991),ncol=3,
               columnspacing=1.35,handlelength=2.6,handletextpad=.6)
    en=('Accuracy and output continuity of LegSA-GINS and OiSAM-FGO. '
        '(a–d) Horizontal positioning and heading errors at the same evaluation point and matched times: '
        '274 epochs during nominal walking and 54 epochs at the beginning of the antenna-obstruction trial. '
        'The error curves use OiSAM with a single initialization. '
        '(e) Available output over each complete trial for LegSA-GINS, OiSAM with a single initialization, '
        'and OiSAM reinitialized at recorded IMU gaps. Open circles on the reinitialized OiSAM row mark initialization-only states; '
        'line segments mark available dynamic output. Within each trial the rows follow the legend order. '
        '(f) Enlargement of the boxed interval in the antenna-obstruction trial; gray shading marks the first IMU input gap. '
        'Elapsed time is measured from the start of each evaluation window.')
    zh=('LegSA-GINS与OiSAM-FGO的精度及输出连续性。（a–d）在同一评价点与匹配时刻比较水平定位和航向误差：'
        '常规行走为274个历元，单侧天线遮挡记录起始阶段为54个历元；精度曲线采用仅初始化一次的OiSAM。'
        '（e）三条完整记录中，LegSA-GINS、仅初始化一次的OiSAM，以及在实测IMU缺口处分段重新初始化的OiSAM的输出时段。'
        '重新初始化的OiSAM行中，空心圆表示仅初始化的状态，线段表示有效动态输出；每个场景内三行按图例顺序排列。'
        '（f）放大单侧天线遮挡记录中方框标出的时段，灰带表示首次IMU输入缺口。时间均相对于各评价窗口起点。')
    notes={'claim':'Accuracy on shared support and continuity over the full trial must be read together.',
           'precision_support':{'BY2':274,'BY2H':0,'BY2O':54},
           'position_point':'POI_MIDPOINT; strict OiSAM and frozen V3, as already evaluated.',
           'all_common_points_drawn':True,'curve_smoothing':False,
           'paired_error_columns':['horizontal_err_m','yaw_err_deg'],
           'availability':'All saved finite dynamic output, split at actual timestamp gaps; prior-only states are separate markers.',
           'interval_plot_definition':'Consecutive valid timestamps connected only within the archived cadence threshold (V3 0.1s; OiSAM 1.001s); no hold across a gap.',
           'availability_zoom':{'sequence':'BY2O','elapsed_window_s':[52,60],'selection':'First recorded input gap, independent of error magnitude','imu_gap_elapsed_s':[left,right]},
           'panel_axis_scales':'Within each scenario methods share axes; position and heading limits differ between scenarios and are explicitly ticked.',
           'strict_vs_segmented':'Segmented accuracy at GNSS1 is not mixed into the POI precision panels; it contributes full-trial availability only.',
           'new_solver_calls':0,'new_evaluator_calls':0,'new_provider_calls':0,
           'metrics_verification':'COMMON_METRIC_VERIFICATION.csv matches all admitted existing RMSE values to <1e-12.'}
    result=export(fig,OUT,'F02_precision_and_continuity',caption_en=en,caption_zh=zh,
      meaning_zh='上部比较相同时刻的精度，下部交代这些时刻覆盖了多少实际运行时间；右下放大首次输入缺口后的输出变化。',
      sources=[DATA/(s+'_COMMON_POI.csv.gz') for s in SEQS]+[DATA/'OUTPUT_EPOCHS.csv.gz',DATA/'OUTPUT_INTERVALS.csv',DATA/'GAPS.csv',DATA/'EXISTING_COMMON_POI_METRICS.csv'],
      technical_notes=notes,axes=axes,row_groups=[['a','b'],['c','d'],['e','f']],column_groups=[['a','c'],['b','d']],
      exemptions=[{'panels':['e','f'],'checks':['panel-width'],'reason':'Whole-trial context and eight-second detail have intentionally different widths.'}])
    (OUT/'CAPTION.md').write_text('# 精度与输出连续性\n\n'+en+'\n\n'+zh+'\n',encoding='utf-8')

if __name__=='__main__':main()
