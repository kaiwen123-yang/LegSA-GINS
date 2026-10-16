"""Representative time histories and compact summaries of robot aiding."""
from pathlib import Path
import argparse,json
import numpy as np
import pandas as pd
from matplotlib.lines import Line2D
from paper_style import setup,plt,MM,COLORS,line,tidy,panel,export

ROOT=Path('/home/kaiwen/research/LegSA-GINS-WORKTREES/audit-code-xbpg-20261001')
DATA=ROOT/'docs/paper_rebuild/GPSS_V3_PAPER_START_20261008/FIGURE_PLAN_INTERNAL'
AV=pd.read_csv(DATA/'ERROR_SERIES_AVAILABILITY6468.csv')
ADD=pd.read_csv(DATA/'ADD495.csv')
PAIRS=pd.read_csv(DATA/'SINGLEMODULE_CASE_PAIRS2164.csv')
START={'BY2':66,'BY2H':413,'BY2O':3186}
USED=[]

def series(run):
    p=Path(AV.loc[AV.run_id==run,'path'].iloc[0]);USED.append(p)
    return pd.read_csv(p,encoding='utf-8-sig')

def shared_legend(fig, labels=('LegSA-GINS','Without body-velocity aiding')):
    h=[Line2D([],[],color='#0072B2',lw=1.2,label=labels[0]),
       Line2D([],[],color='#D55E00',lw=1.1,ls='--',label=labels[1])]
    fig.legend(handles=h,loc='upper center',bbox_to_anchor=(.54,.995),ncol=2,handlelength=2.5,columnspacing=1.6)

def velocity(out):
    fig,axs=plt.subplots(2,2,figsize=(174*MM,139*MM))
    fig.subplots_adjust(left=.115,right=.985,bottom=.105,top=.885,wspace=.36,hspace=.53)
    shared_legend(fig)
    for col,fam in enumerate(['A1','A2']):
        ax=axs[0,col]
        rows=ADD[(ADD.case_family==fam)&(ADD.duration_s==20)&(ADD.seed_index=='seed_00')]
        t0=float(rows.outage_start_s.iloc[0]);t1=float(rows.outage_end_s.iloc[0])
        zoom_data=[]
        for m,color,ls in [('A06','#D55E00','--'),('F04','#0072B2','-')]:
            r=rows[rows.internal_method_id==m].iloc[0];d=series(r.run_id);keep=(d.time>=t0-5)&(d.time<=t1+15)
            line(ax,d.loc[keep,'time']-t0,d.loc[keep,'horizontal_err_m'],gap=.1,color=color,ls=ls,lw=1.1)
            zoom_data.append((m,color,ls,d))
        ax.axvspan(0,20,facecolor='#E9E9E9',edgecolor='none',linewidth=0,zorder=0)
        ax.set(xlim=(-5,35),xlabel='Time from interruption start (s)',ylabel='Horizontal error (m)')
        tidy(ax,xbins=4);panel(ax,chr(97+col),'All GNSS lost' if fam=='A1' else 'Heading retained')
        if fam=='A2':
            ins=ax.inset_axes([.13,.50,.40,.36])
            for m,color,ls,d in zoom_data:
                keep=(d.time>=t0)&(d.time<=t1)&(d.horizontal_err_m>=0)&(d.horizontal_err_m<=2.5)
                line(ins,d.loc[keep,'time']-t0,d.loc[keep,'horizontal_err_m'],gap=.1,color=color,ls=ls,lw=.85)
            ins.set(xlim=(0,20),ylim=(0,2.5));ins.set_xticks([0,10,20]);ins.set_yticks([0,1,2]);ins.tick_params(labelsize=7)
            ins.set_title('0–2.5 m view',fontsize=7.5,pad=3)
        ax=axs[1,col];dur=[10,20,30] if fam=='A1' else [10,20]
        for i,length in enumerate(dur):
            a=ADD[(ADD.case_family==fam)&(ADD.duration_s==length)&(ADD.internal_method_id=='F04')].sort_values('seed_index')
            b=ADD[(ADD.case_family==fam)&(ADD.duration_s==length)&(ADD.internal_method_id=='A06')].sort_values('seed_index')
            offsets=np.linspace(-.04,.04,9)
            for k in range(9):
                ax.plot([i-.14+offsets[k],i+.14+offsets[k]],[b.horizontal_rmse_m.iloc[k],a.horizontal_rmse_m.iloc[k]],color='#B7B7B7',lw=.6,zorder=1)
            ax.scatter(i-.14+offsets,b.horizontal_rmse_m,s=14,color='#D55E00',marker='s',zorder=3)
            ax.scatter(i+.14+offsets,a.horizontal_rmse_m,s=14,color='#0072B2',marker='o',zorder=3)
        ax.set_yscale('log');ax.set_ylim(.075,65);ax.set_yticks([.1,1,10],['0.1','1','10'])
        ax.set_xticks(range(len(dur)),[str(x) for x in dur]);ax.set_xlim(-.5,len(dur)-.5)
        ax.set(xlabel='Interruption duration (s)',ylabel='Whole-run horizontal RMSE (m)')
        panel(ax,chr(99+col),'Nine interruption placements')
    return export(fig,out,'Q4_body_velocity',
        caption_en='Conditional effect of body-velocity aiding during GNSS interruptions. (a,b) Horizontal error around one 20-s interruption; grey shading marks the interruption. The inset in (b) enlarges the 0–2.5 m range during the interruption. (c,d) Whole-run horizontal RMSE for nine interruption placements per duration on the same recorded route. Lines connect identical placements. Columns show complete GNSS loss and interruption of translational observations with heading retained. Complete GNSS loss also pauses auxiliary updates in the evaluated implementation.',
        caption_zh='机身速度辅助在GNSS中断中的条件作用。（a,b）一处20 s中断及恢复过程的水平误差，灰色为中断区间；（b）插图放大中断期间0–2.5 m误差范围。（c,d）同一实测路线中，每种时长九个中断布置的全窗水平RMSE，细线连接相同布置。两列分别为全部GNSS观测中断与保留航向的平移观测中断。所评价实现中，全部GNSS观测中断同时暂停辅助更新。',
        meaning_zh='先看上排两条误差曲线何时分开，再看下排这种变化是否在九个布置中都出现。',
        sources=[DATA/'ADD495.csv',*USED],axes=list(axs.flat),
        technical_notes={'example':'D61_20s_seed_00 and D62_20s_seed_00','plot_window':'[outage_start-5,outage_end+15]','all_summary_points':90,'method':'F04 versus A06'})

def tilt(out):
    fig,axs=plt.subplots(2,3,figsize=(174*MM,112*MM),sharex='col')
    fig.subplots_adjust(left=.095,right=.985,bottom=.115,top=.86,wspace=.35,hspace=.42)
    shared_legend(fig,('LegSA-GINS','Without tilt aiding'))
    for col,seq in enumerate(START):
        for m,color,ls in [('A05','#D55E00','--'),('F04','#0072B2','-')]:
            subset=AV[(AV.sequence_id==seq)&(AV.method_id==m)]
            subset=subset[subset.case_id=='C00_clean_normal'] if seq=='BY2' else subset[subset.domain=='SEQUENCE']
            d=series(subset.run_id.iloc[0])
            for row,field in enumerate(['roll_err_deg','pitch_err_deg']):
                line(axs[row,col],d.time-START[seq],d[field],gap=.1,color=color,ls=ls,lw=.85)
        for row in range(2):
            ax=axs[row,col];ax.axhline(0,color='#888888',lw=.55,ls=':');tidy(ax,xbins=4,ybins=4)
            ax.set_ylabel(('Roll' if row==0 else 'Pitch')+' error (deg)')
            panel(ax,chr(97+row*3+col),seq)
        axs[1,col].set_xlabel('Time (s)')
    for row in range(2):
        lo=min(axs[row,col].get_ylim()[0] for col in range(3));hi=max(axs[row,col].get_ylim()[1] for col in range(3))
        for col in range(3):axs[row,col].set_ylim(lo,hi)
    return export(fig,out,'S_Q4_tilt_aiding',
        caption_en='Roll and pitch errors with and without robot tilt aiding on BY2, BY2H and BY2O. Each column shows one recording, with roll above and pitch below. The zero-error line represents the reference attitude. All curves use the same fixed parameters and their recorded timestamps.',
        caption_zh='三条实测序列中机身倾角辅助对横滚、俯仰误差的影响。蓝线为完整方法，橙色虚线为关闭倾角辅助；每列对应一个序列，上下分别为横滚和俯仰。',
        meaning_zh='蓝线相对零线更近的区段，就是倾角辅助直接改善机身姿态的时段。',sources=USED,axes=list(axs.flat),technical_notes={'comparison':'F04 versus A05','gap_break_s':.1})

def weighting(out):
    pair=PAIRS[(PAIRS.module=='SA')&(PAIRS.case_id=='D15_seed_00')].iloc[0]
    ds={'LegSA-GINS':series(pair.candidate_run_id),'Without source weighting':series(pair.ablation_run_id)}
    fig,axs=plt.subplots(2,2,figsize=(174*MM,134*MM));fig.subplots_adjust(left=.12,right=.985,bottom=.12,top=.885,wspace=.37,hspace=.57)
    shared_legend(fig,tuple(ds))
    for col,(field,ylabel) in enumerate([('horizontal_err_m','Horizontal error (m)'),('yaw_err_deg','Heading error (deg)')]):
        ax=axs[0,col]
        for label,d in reversed(list(ds.items())):
            line(ax,d.time-66,d[field],gap=.1,color='#0072B2' if label=='LegSA-GINS' else '#D55E00',ls='-' if label=='LegSA-GINS' else '--',lw=.9)
        ax.set(xlabel='Time (s)',ylabel=ylabel);tidy(ax,xbins=4,ybins=4);panel(ax,chr(97+col),'GNSS position noise')
    ax=axs[1,0];vals=[19,13]
    ax.barh([1,0],vals,color=['#D55E00','#0072B2'],height=.5)
    ax.set_yticks([1,0],['Weighting off','LegSA-GINS']);ax.set_xlim(0,22);ax.set_xticks([0,5,10,15,20]);ax.set_xlabel('Divergent runs (out of 541)')
    for y,n in zip([1,0],vals):ax.text(n+.45,y,str(n),va='center',fontsize=9)
    panel(ax,'c','Divergence across 541 cases')
    ax=axs[1,1];d=PAIRS[(PAIRS.module=='SA')&(PAIRS.joint_finite==True)]
    x=d.ablation_horizontal_rmse_m.to_numpy();y=d.candidate_horizontal_rmse_m.to_numpy()
    ax.scatter(x,y,color='#0072B2',s=8,alpha=.6,edgecolors='none',rasterized=True)
    ax.plot([.05,25],[.05,25],ls='--',color='#777777',lw=.7)
    ax.set(xscale='log',yscale='log',xlim=(.05,25),ylim=(.05,25),xlabel='Without weighting: H RMSE (m)',ylabel='LegSA-GINS: H RMSE (m)')
    ax.set_xticks([.1,1,10],['0.1','1','10']);ax.set_yticks([.1,1,10],['0.1','1','10']);panel(ax,'d','Paired positioning errors')
    ax.text(.045,.945,'Median change: +0.98 mm',transform=ax.transAxes,ha='left',va='top',fontsize=8)
    ins=ax.inset_axes([.61,.20,.34,.30]);ins.scatter(x,y,color='#0072B2',s=6,alpha=.6,edgecolors='none',rasterized=True)
    ins.plot([.09,.11],[.09,.11],ls='--',color='#777777',lw=.6);ins.set(xlim=(.094,.104),ylim=(.094,.104));ins.set_xticks([.096,.102]);ins.set_yticks([.096,.102]);ins.tick_params(labelsize=7)
    return export(fig,out,'A03_source_weighting',
        caption_en='Effect of source weighting. (a,b) Position and heading errors after adding GNSS position noise (horizontal 3 m, vertical 5 m). (c) Divergent runs in the 541-case test matrix. (d) Horizontal RMSE in the 513 cases completed by both configurations; points below the dashed line favour LegSA-GINS. The inset enlarges near-nominal results. Weighting reduces divergence and large heading errors, with a small typical positioning cost.',
        caption_zh='来源加权对导航误差和发散次数的影响。上排是加入GNSS位置噪声后的水平误差与航向误差；左下显示541例中的发散次数；右下比较513个双方均完成案例的水平RMSE，虚线下方表示完整方法更好，放大窗展示正常误差量级附近的细小变化。',
        meaning_zh='这张图直接展示加权如何抑制大的航向偏离，以及它同时带来的位置精度取舍。',sources=[DATA/'SINGLEMODULE_CASE_PAIRS2164.csv',*USED],axes=list(axs.flat),
        technical_notes={'representative_case':'D15_seed_00','noise':'Gaussian horizontal sigma 3 m, vertical sigma 5 m; other observations and reported quality unchanged','common_completed':513,'no_valid_heading_each':9,'inset_alignment':'Different-scale nominal-error inset; only four main axes are in comparable layout groups.'})

def main():
    p=argparse.ArgumentParser();p.add_argument('--out',required=True,type=Path);p.add_argument('--only',choices=['velocity','tilt','weighting']);a=p.parse_args();setup()
    for name,fn in [('velocity',velocity),('tilt',tilt),('weighting',weighting)]:
        if a.only in (None,name):USED.clear();fn(a.out)

if __name__=='__main__':main()
