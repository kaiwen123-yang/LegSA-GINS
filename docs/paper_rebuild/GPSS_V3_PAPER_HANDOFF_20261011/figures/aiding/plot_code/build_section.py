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
