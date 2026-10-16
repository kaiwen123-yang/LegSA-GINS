"""Compact navigation-paper plotting style; technical notes stay outside captions."""
from pathlib import Path
import os, sys, json, subprocess
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator
from PIL import Image
from paper_names import scenario_label, caption_names, apply_figure_names

MM=1/25.4
COLORS={'Truth':'#222222','LegSA-GINS':'#0072B2','IEKF-LIT':'#D55E00','IEKF-S':'#009E73',
        'F04':'#0072B2','F01':'#777777','F03':'#D55E00','A04':'#D55E00','A05':'#009E73','A06':'#D55E00',
        'OiSAM':'#0072B2','Wen':'#D55E00','GNC':'#009E73'}
STYLES={'Truth':'--','LegSA-GINS':'-','IEKF-LIT':'-.','IEKF-S':':','F04':'-','F01':':','F03':'-.',
        'OiSAM':'-','Wen':'--','GNC':'-.'}

def setup():
    plt.rcParams.update({'font.family':'sans-serif','font.sans-serif':['Arial','Liberation Sans','DejaVu Sans'],
        'font.size':8.5,'axes.labelsize':9,'axes.titlesize':9,'xtick.labelsize':8,'ytick.labelsize':8,
        'legend.fontsize':8,'legend.frameon':False,'axes.linewidth':.65,'axes.spines.top':False,
        'axes.spines.right':False,'xtick.direction':'in','ytick.direction':'in','xtick.major.width':.65,
        'ytick.major.width':.65,'xtick.major.size':3,'ytick.major.size':3,'lines.linewidth':1.0,
        'lines.markersize':3,'pdf.fonttype':42,'ps.fonttype':42,'svg.fonttype':'none',
        'savefig.facecolor':'white','axes.facecolor':'white','figure.facecolor':'white',
        'path.simplify':False})

def panel(ax,letter,title=''):
    title=scenario_label(title)
    ax.set_title(f'({letter})'+(' '+title if title else ''),loc='left',fontsize=9,fontweight='normal',pad=5)

def tidy(ax, xbins=5, ybins=4, grid=False):
    if ax.get_xscale()=='linear': ax.xaxis.set_major_locator(MaxNLocator(nbins=xbins))
    if ax.get_yscale()=='linear': ax.yaxis.set_major_locator(MaxNLocator(nbins=ybins))
    if grid: ax.grid(color='#E6E6E6',lw=.45); ax.set_axisbelow(True)

def line(ax,t,y,*,gap=.1,label=None,**kw):
    t=np.asarray(t); y=np.asarray(y)
    parts=np.split(np.arange(len(t)),np.flatnonzero(np.diff(t)>gap)+1)
    for i,ind in enumerate(parts):
        if len(ind): ax.plot(t[ind],y[ind],label=label if i==0 else None,**kw)

def export(fig,out,name,*,caption_en,caption_zh,meaning_zh,sources,technical_notes=None,
           axes=None,row_groups=None,column_groups=None,exemptions=()):
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    qa=out/'qa';qa.mkdir(exist_ok=True)
    scripts=Path(os.environ['NATURE_FIGURE_SCRIPTS'])
    if str(scripts) not in sys.path:sys.path.insert(0,str(scripts))
    from audit_panel_alignment import require_matplotlib_panel_alignment
    apply_figure_names(fig)
    caption_en=caption_names(caption_en,'en')
    caption_zh=caption_names(caption_zh,'zh')
    meaning_zh=caption_names(meaning_zh,'zh')
    fig.canvas.draw()
    opts={'axes':axes,'exemptions':exemptions}
    if row_groups is not None:opts['row_groups']=row_groups
    if column_groups is not None:opts['column_groups']=column_groups
    alignment=require_matplotlib_panel_alignment(fig,json_out=qa/(name+'.alignment.json'),
        tolerance_pt=1.5,gutter_tolerance_pt=1.5,strict=True,**opts)
    fig.savefig(out/(name+'.pdf'),dpi=600)
    fig.savefig(out/(name+'.svg'),dpi=600)
    fig.savefig(out/(name+'.png'),dpi=600)
    preview=out/'preview';preview.mkdir(exist_ok=True)
    fig.savefig(preview/(name+'.png'),dpi=300)
    with Image.open(preview/(name+'.png')) as im: im.convert('L').save(preview/(name+'_gray.png'))
    commands=[('pdf_text',[sys.executable,str(scripts/'audit_pdf_text.py'),str(out/(name+'.pdf')),'--min-pt','5','--json']),
              ('collisions',[sys.executable,str(scripts/'audit_figure_collisions.py'),str(out/(name+'.pdf')),
                             '--json-out',str(qa/(name+'.collisions.json'))])]
    audit={}
    for kind,cmd in commands:
        run=subprocess.run(cmd,text=True,capture_output=True)
        audit[kind]={'returncode':run.returncode,'log':run.stdout+run.stderr}
        (qa/(name+'.'+kind+'.log')).write_text(run.stdout+run.stderr,encoding='utf-8')
    record={'id':name,'caption_en':caption_en,'caption_zh':caption_zh,'meaning_zh':meaning_zh,
            'sources':[str(x) for x in sources],'technical_notes':technical_notes or {},
            'width_mm':fig.get_figwidth()*25.4,'height_mm':fig.get_figheight()*25.4,
            'alignment_status':alignment.get('status',alignment.get('verdict')),
            'audit_returncodes':{k:v['returncode'] for k,v in audit.items()},'visual_review':'PENDING'}
    (out/(name+'.json')).write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    plt.close(fig)
    print(name,record['audit_returncodes'])
    return record

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

"""Read frozen V3 tables and draw Q4/Q5 figures without rerunning estimation."""
from pathlib import Path
import json, shutil, argparse, hashlib
import numpy as np
import pandas as pd
from matplotlib.lines import Line2D
from paper_style import setup, plt, MM, line, tidy, panel, export
import build_aiding_figures as prior

OUT=Path(__file__).resolve().parents[1]
DATA=prior.DATA
TABLES=OUT/'tables'
FIGS=OUT/'figures'
START=prior.START
TRACE=Path('/mnt/g/LegSA-GINS-project/clean_rebuild_202607/stages/CLEAN8_PROTOCOL_V3/03_NATIVE/V3R_CONTINUATION/RUN_01401/SOURCE_AWARE_WEIGHT_TRACE.csv.gz')

def read_tables():
    TABLES.mkdir(exist_ok=True)
    names=['NATURAL33','CORE5951','ADD495','FULL_OUTCOME55','MODULE56','SINGLEMODULE_CASE_PAIRS2164','SA_SIX_EXTRA_COMPLETIONS','CORE_SUMMARY77','ERROR_SERIES_AVAILABILITY6468']
    frames={}
    inventory=[]
    for name in names:
        p=DATA/(name+'.csv')
        frames[name]=pd.read_csv(p)
        shutil.copy2(p,TABLES/p.name)
        inventory.append({'source':str(p),'table':p.name,'rows':len(frames[name]),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
    d=frames['ADD495']
    rows=[]
    for keys,g in d.groupby(['case_family','duration_s','internal_method_id'],sort=True):
        good=g[g.evaluation_status=='COMPLETED']
        r=dict(zip(['case_family','duration_s','internal_method_id'],keys))
        r.update(registered=len(g),completed=len(good),failed=len(g)-len(good))
        for m in ['horizontal_rmse_m','up_rmse_m','yaw_rmse_deg','roll_rmse_deg','pitch_rmse_deg','horizontal_max_m']:
            r[m+'_median']=good[m].median()
            r[m+'_min']=good[m].min()
            r[m+'_max']=good[m].max()
        rows.append(r)
    pd.DataFrame(rows).to_csv(TABLES/'ALL_DURATION_ALL11_SUMMARY.csv',index=False)
    trace=pd.read_csv(TRACE)
    trace.to_csv(TABLES/'D15_SOURCE_WEIGHT_TRACE_ALL.csv',index=False)
    trace.groupby('source_id').agg(n=('time','size'),min_scale=('combined_R_scale','min'),max_scale=('combined_R_scale','max'),source_cap=('source_cap','first')).to_csv(TABLES/'D15_SOURCE_WEIGHT_SUMMARY.csv')
    pd.DataFrame(inventory).to_csv(TABLES/'SOURCE_TABLE_INVENTORY.csv',index=False)
    return frames

def heading():
    prior.USED.clear()
    fig,axs=plt.subplots(2,3,figsize=(174*MM,128*MM))
    fig.subplots_adjust(left=.095,right=.985,bottom=.105,top=.85,wspace=.35,hspace=.55)
    styles=[('F01','#777777',':','Basic GNSS/INS'),('F03','#D55E00','--','Basic + dual-antenna heading'),('F04','#0072B2','-','LegSA-GINS')]
    fig.legend(handles=[Line2D([],[],color=c,ls=ls,lw=1.15,label=label) for _,c,ls,label in styles],loc='upper center',bbox_to_anchor=(.53,.995),ncol=1,handlelength=3)
    windows={'BY2':(125,145),'BY2H':(125,145),'BY2O':(194,214)}
    for col,seq in enumerate(START):
        lo,hi=windows[seq]
        for method,color,ls,label in styles:
            a=prior.AV[(prior.AV.sequence_id==seq)&(prior.AV.method_id==method)]
            a=a[a.case_id=='C00_clean_normal'] if seq=='BY2' else a[a.domain=='SEQUENCE']
            assert len(a)==1
            d=prior.series(a.run_id.iloc[0]);t=d.time-START[seq]
            line(axs[0,col],t,d.yaw_err_deg,gap=.1,color=color,ls=ls,lw=.9)
            keep=(t>=lo)&(t<=hi)
            line(axs[1,col],t[keep],d.yaw_err_deg[keep],gap=.1,color=color,ls=ls,lw=1.0)
        axs[0,col].axvspan(lo,hi,color='#EFEFEF',zorder=-1)
        panel(axs[0,col],chr(97+col),seq)
        panel(axs[1,col],chr(100+col),'Enlarged interval')
        axs[1,col].set_xlim(lo,hi)
        for row in range(2):
            ax=axs[row,col];ax.axhline(0,color='#AAAAAA',lw=.5,zorder=-1)
            ax.set(xlabel='Time (s)',ylabel='Heading error (deg)')
            tidy(ax,xbins=4,ybins=4)
    for row in range(2):
        lo=min(ax.get_ylim()[0] for ax in axs[row]);hi=max(ax.get_ylim()[1] for ax in axs[row])
        for ax in axs[row]:ax.set_ylim(lo,hi)
    return export(fig,FIGS,'S_Q4_heading_information',
        caption_en='Heading errors for basic GNSS/INS, the same basic configuration with dual-antenna heading updates, and LegSA-GINS. Columns correspond to nominal walking, large body motion and single-antenna obstruction. (a–c) Full error histories; shaded intervals are enlarged in (d–f). All three configurations share an initial direction. The first two configurations isolate the addition of the dual-antenna heading chain; LegSA-GINS also includes the other enabled aids.',
        caption_zh='基础GNSS/INS、基础配置加入双天线航向更新以及完整LegSA-GINS的航向误差。三列依次为常规行走、大幅机身运动与单侧天线遮挡。（a–c）完整误差时序，灰色区间在（d–f）放大。三种配置共享初始方向；前两种配置用于解释加入双天线航向链的作用，完整方法还包含其他辅助。',
        meaning_zh='基础配置加入航向链后持续航向误差明显降低，完整方法与该配置的航向曲线接近；二者微小差值不是本文全部收益。',
        sources=prior.USED,axes=list(axs.flat),technical_notes={'methods':['F01','F03','F04'],'windows_elapsed_s':windows,'preserved_all_samples':True,'matched_contract':'original saved evaluator_contract_v3 signed yaw error'})

def weighting(frames):
    prior.USED.clear()
    pair=prior.PAIRS[(prior.PAIRS.module=='SA')&(prior.PAIRS.case_id=='D15_seed_00')].iloc[0]
    ds={'LegSA-GINS':prior.series(pair.candidate_run_id),'Without source weighting':prior.series(pair.ablation_run_id)}
    tr=pd.read_csv(TRACE)
    fig=plt.figure(figsize=(174*MM,188*MM))
    gs=fig.add_gridspec(3,2,height_ratios=[1,0.80,1.12],left=.12,right=.985,bottom=.085,top=.915,wspace=.37,hspace=.65)
    axa=fig.add_subplot(gs[0,0]);axb=fig.add_subplot(gs[0,1]);axc=fig.add_subplot(gs[1,:]);axd=fig.add_subplot(gs[2,0]);axe=fig.add_subplot(gs[2,1])
    prior.shared_legend(fig,tuple(ds))
    for ax,field,ylabel,letter in [(axa,'horizontal_err_m','Horizontal error (m)','a'),(axb,'yaw_err_deg','Heading error (deg)','b')]:
        for label,d in reversed(list(ds.items())):
            line(ax,d.time-66,d[field],gap=.1,color='#0072B2' if label=='LegSA-GINS' else '#D55E00',ls='-' if label=='LegSA-GINS' else '--',lw=.9)
        ax.set(xlim=(0,274),xlabel='Time (s)',ylabel=ylabel);tidy(ax,xbins=4,ybins=4);panel(ax,letter,'GNSS position noise')
    source_styles=[('receiver_position','#222222','-','GNSS position'),('dual_antenna_yaw','#009E73','--','Dual-antenna heading'),('go2_horizontal_velocity','#CC79A7',':','Body velocity')]
    for source,color,ls,label in source_styles:
        d=tr[tr.source_id==source].sort_values('time')
        line(axc,d.time-66,d.combined_R_scale,gap=.45,color=color,ls=ls,lw=.85,label=label)
    axc.set(xlim=(0,274),ylim=(.7,13),xlabel='Time (s)',ylabel='Covariance multiplier')
    tidy(axc,xbins=6,ybins=4);axc.set_yticks([1,5,10]);panel(axc,'c','Recorded source-dependent covariance scaling')
    axc.legend(loc='upper center',bbox_to_anchor=(.5,1.0),ncol=3,fontsize=7.6,columnspacing=1.1,handlelength=2.5)
    core=frames['CORE5951']
    counts=[]
    for method in ['A04','F04']:
        d=core[core.internal_method_id==method];assert len(d)==541
        counts.append(int((d.evaluation_status=='NOT_RUN_ALGORITHM_FAILURE').sum()))
    # Native outcomes distinguish divergence from unavailable initial heading.
    av=prior.AV[(prior.AV.domain=='CORE')&(prior.AV.method_id.isin(['A04','F04']))]
    vals=[int(((av.method_id==m)&(av.native_status=='ALGORITHM_FAILURE_DIVERGED')).sum()) for m in ['A04','F04']]
    assert vals==[19,13]
    axd.barh([1,0],vals,color=['#D55E00','#0072B2'],height=.5)
    axd.set_yticks([1,0],['Weighting off','LegSA-GINS']);axd.set_xlim(0,22);axd.set_xticks([0,5,10,15,20]);axd.set_xlabel('Divergent runs (out of 541)')
    for y,n in zip([1,0],vals):axd.text(n+.45,y,str(n),va='center',fontsize=9)
    panel(axd,'d','Divergence across 541 cases')
    d=prior.PAIRS[(prior.PAIRS.module=='SA')&(prior.PAIRS.joint_finite==True)]
    x=d.ablation_horizontal_rmse_m.to_numpy();y=d.candidate_horizontal_rmse_m.to_numpy()
    assert len(d)==513 and (x>0).all() and (y>0).all()
    axe.scatter(x,y,color='#0072B2',s=8,alpha=.6,edgecolors='none',rasterized=True)
    axe.plot([.05,25],[.05,25],ls='--',color='#777777',lw=.7)
    axe.set(xscale='log',yscale='log',xlim=(.05,25),ylim=(.05,25),xlabel='Without weighting: H RMSE (m)',ylabel='LegSA-GINS: H RMSE (m)')
    axe.set_xticks([.1,1,10],['0.1','1','10']);axe.set_yticks([.1,1,10],['0.1','1','10']);panel(axe,'e','Paired positioning errors')
    median_mm=float(np.median(y-x)*1000)
    axe.text(.04,.955,f'Median change: {median_mm:+.2f} mm',transform=axe.transAxes,ha='left',va='top',fontsize=8)
    ins=axe.inset_axes([.61,.20,.34,.30]);ins.scatter(x,y,color='#0072B2',s=6,alpha=.6,edgecolors='none',rasterized=True)
    ins.plot([.09,.11],[.09,.11],ls='--',color='#777777',lw=.6);ins.set(xlim=(.094,.104),ylim=(.094,.104));ins.set_xticks([.096,.102]);ins.set_yticks([.096,.102]);ins.tick_params(labelsize=7)
    return export(fig,FIGS,'Q5_source_weighting',
        caption_en='Benefits and costs of source-dependent weighting. (a,b) Horizontal and heading errors in a saved GNSS position-noise case (horizontal standard deviation 3 m, vertical 5 m). (c) Recorded covariance multipliers for three observation sources in the same run. (d) Divergent runs across 541 cases; both configurations additionally have nine cases without valid initial heading. (e) Whole-run horizontal RMSE for the 513 cases completed by both configurations. Points below the identity line favour LegSA-GINS; the inset enlarges the nominal error range. The cases reuse one recorded route with controlled observation perturbations.',
        caption_zh='来源加权的收益与位置精度代价。（a,b）已保存的GNSS位置加噪案例中的水平和航向误差，水平标准差3 m、竖直5 m。（c）同次运行三个观测来源的实际协方差放大倍数。（d）541个案例的发散次数；两种配置各另有九例缺少有效初始航向。（e）双方均完成的513例的全窗水平RMSE。等值线下方表示完整方法误差更小，插图放大正常误差量级。案例来自同一实测路线的受控观测扰动。',
        meaning_zh='权重轨迹说明各来源受到不同程度的降权；误差轨迹与完整案例集合共同显示，发散和大航向偏离减少，同时保留位置精度代价。',
        sources=[DATA/'SINGLEMODULE_CASE_PAIRS2164.csv',DATA/'CORE5951.csv',TRACE,*prior.USED],axes=[axa,axb,axc,axd,axe],
        technical_notes={'representative_case':'D15_seed_00','source_trace_rows':len(tr),'source_trace_plot':['receiver_position','dual_antenna_yaw','go2_horizontal_velocity'],'other_sources':'All six sources retained in D15_SOURCE_WEIGHT_TRACE_ALL.csv','candidate_run_id':pair.candidate_run_id,'ablation_run_id':pair.ablation_run_id,'common_completed':513,'median_h_cost_mm':median_mm,'no_valid_heading_each':9,'reuse_level':'structural adaptation of existing A03, adding actual retained weighting trace','inset_alignment':'different-scale inset excluded; five main axes measured'})

def main():
    p=argparse.ArgumentParser();p.add_argument('--only',choices=['tables','velocity','tilt','heading','weighting']);a=p.parse_args();setup()
    frames=read_tables()
    if a.only in (None,'velocity'):prior.USED.clear();prior.velocity(FIGS)
    if a.only in (None,'tilt'):prior.USED.clear();prior.tilt(FIGS)
    if a.only in (None,'heading'):heading()
    if a.only in (None,'weighting'):weighting(frames)
    print('tables read in full:',{k:len(v) for k,v in frames.items()})

if __name__=='__main__':main()
