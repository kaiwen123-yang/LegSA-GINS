"""Q2 manuscript figures: read saved results only, without scientific solver calls."""
from pathlib import Path
import sys, json, shutil, hashlib, csv
import numpy as np
import pandas as pd

ROOT=Path('/home/kaiwen/research/LegSA-GINS-WORKTREES/audit-code-xbpg-20261001')
DOC=ROOT/'docs/paper_rebuild'
STYLE=DOC/'GPSS_V3_FIGURES_20261008/redesign_20261009'
sys.path.insert(0,str(STYLE))
from paper_style import setup, panel, tidy, export, MM, plt
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

OUT=Path(__file__).resolve().parent
TABLES=OUT/'tables'; TABLES.mkdir(parents=True,exist_ok=True)
DATA=OUT/'data'; DATA.mkdir(exist_ok=True)
OLD=Path('/mnt/g/LegSA-GINS-project/V3论文组图_20261008/redesign_20261009/figures')
REC=Path('/mnt/g/LegSA-GINS-project/V3研究记录梳理_20261011/heading')
CURVES=DOC/'JOURNAL_REFRAME_20261004/figures'
SEQ=['BY2','BY2H','BY2O']
NAMES=['Nominal walking','Large body motion','Antenna obstruction']
ZH=['常规行走','大幅机身运动','单侧天线遮挡']
START=[66.,413.,3186.];DUR=[274.,270.,377.]
COLORS=['#0072B2','#D55E00','#009E73']; STYLES=['-','--','-.']
sources=[]
def read(p):
    p=Path(p); d=pd.read_csv(p,encoding='utf-8-sig')
    sources.append({'source':str(p),'rows':len(d),'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'read':'all rows'})
    return d
def preserve(p,name=None):
    p=Path(p);d=read(p);q=TABLES/(name or p.name);shutil.copy2(p,q);return q,d
def public(p):
    return str(p).replace('/mnt/g/','G:/').replace('/home/kaiwen/','//wsl.localhost/Ubuntu-22.04/home/kaiwen/')

def prepare():
    preserve(REC/'EXISTING_HEADING_METRICS.csv')
    preserve(REC/'EXPERIMENTS.csv','ALL_HEADING_EXPERIMENTS.csv')
    selected=[
      'hext/HX07R/HX07R_MANUSCRIPT_ROWS.csv','hext/HX07R/HX07R_SUPPLEMENT_ROWS.csv','hext/HX07R/HX07R_BY2O_SEGMENTS.csv',
      'hext/DG01/DG01_OVERVIEW.csv','hext/DG01/DG01_FIX_STATUS_TIMELINE.csv','hext/DG01/DG01_RTKLIB_CONFIG_AUDIT.csv',
      'hext/DG01R/DG01R_CLOCK_OFFSET.csv','hext/DG01R/DG01R_VERSION_COMPARISON.csv','hext/DG01R/DG01R_RINEX_CROSSCHECK.csv',
      'hext/EXT_REPRODUCTION/v2_fix/COMMON_SUPPORT_ALL.csv','hext/EXT_REPRODUCTION/v2_fix/V1_V2_SAME_METHOD_COMMON_SUPPORT.csv',
      'hext/EXT_REPRODUCTION/v2_fix/NATIVE_RUN_SUMMARY.csv',
      'AR_V3_RESEARCH_20261006/RTKLIB_EPOCH_DIAGNOSTICS.csv','AR_V3_RESEARCH_20261006/RTKLIB_Q1_LARGE_LENGTH_DIAGNOSTICS.csv',
      'AR_V3_RESEARCH_20261006/INPUT_AUDIT_DIFFERENCES.csv','AR_V3_RESEARCH_20261006/INPUT_AUDIT_OLD_LLI.csv',
      'AR_V3_RESEARCH_20261006/classic_qualification/RESULTS.csv','AR_V3_RESEARCH_20261006/motion_pair_qualification/RESULTS.csv']
    for f in selected:
        name=Path(f).name
        if 'classic_qualification' in f:name='CLASSIC_QUALIFICATION_RESULTS.csv'
        if 'motion_pair_qualification' in f:name='MOTION_PAIR_RESULTS.csv'
        preserve(DOC/f,name)
    far=[]
    hxroot=Path('/mnt/g/LegSA-GINS-project/clean_rebuild_202607/stages/CLEAN9_EXTERNAL_COMPARISON/HX02_FIVE_CATEGORY/RUNS')
    for folder in sorted(hxroot.glob('*__EXT04__*')):
        seq=folder.name.split('__')[0]
        base=folder/'native/ARTIFACT/05_EXT04_WU2025_MODULE/C00'
        for name in ['EXT04_C00_POLICY_SUMMARY.csv','EXT04_C00_FAILURE_LEDGER.csv','EXT04_POLICY_PARAMETER_REGISTRY.csv','EXT04_STOCHASTIC_PARAMETER_REGISTRY.csv']:
            _,d=preserve(base/name,seq+'_'+name)
            if name=='EXT04_C00_POLICY_SUMMARY.csv':d.insert(0,'sequence',seq);far.append(d)
    full=pd.concat(far,ignore_index=True);full.to_csv(TABLES/'FAR_PAR_ALL_THREE_TRIALS.csv',index=False)
    assert len(full)==6 and full.accepted_count.eq(0).all()
    # Read every retained window record used by the two supplemental figures.
    for s in SEQ:
        for v in ['V0','V0E','V1','V2']:
            p=CURVES/f'block_04/data/{s}_{v}_full_saved_heading.csv.gz';read(p);shutil.copy2(p,DATA/p.name)
        p=CURVES/f'block_06/data/{s}_all_methods_all_window_epochs.csv.gz';read(p);shutil.copy2(p,DATA/p.name)
    for name in ['RTKLIB_DIAGNOSTIC_SUMMARY.json','INPUT_AUDIT_SUMMARY.json']:
        p=DOC/'AR_V3_RESEARCH_20261006'/name;data=json.loads(p.read_text());shutil.copy2(p,TABLES/name)

def main_figure():
    setup();fig,ax=plt.subplots(2,2,figsize=(174*MM,150*MM))
    fig.subplots_adjust(left=.115,right=.98,bottom=.12,top=.88,wspace=.35,hspace=.80)
    frames=[];summary=[]
    for seq,nm,zh,t0,dur,c,st in zip(SEQ,NAMES,ZH,START,DUR,COLORS,STYLES):
        p=DATA/f'{seq}_V0_full_saved_heading.csv.gz';d=read(p);valid=d.valid.eq(1)&d.error_valid_deg.notna();z=d.loc[valid]
        vals=np.sort(np.abs(z.error_valid_deg.to_numpy()));f=np.arange(1,len(vals)+1)/len(vals)
        ax[0,0].step(vals,f,where='post',color=c,ls=st,lw=1.05)
        frames.append(z)
        summary.append({'sequence':seq,'scenario':nm,'new_outputs':len(z),'paired_epochs':len(d),'new_output_fraction':len(z)/len(d)})
    a=ax[0,0];a.set(xlim=(0,180),ylim=(0,1.025),xlabel='Absolute heading error (deg)',ylabel='Cumulative fraction')
    a.set_xticks([0,60,120,180]);a.set_yticks([0,.5,1]);panel(a,'a','New heading accuracy')
    inset=a.inset_axes([.43,.16,.53,.51])
    for z,c,st in zip(frames,COLORS,STYLES):
        vals=np.sort(np.abs(z.error_valid_deg.to_numpy()));f=np.arange(1,len(vals)+1)/len(vals)
        inset.step(vals,f,where='post',color=c,ls=st,lw=.9)
    inset.set(xlim=(0,20),ylim=(0,1.025));inset.set_xticks([0,10,20]);inset.set_yticks([0,.5,1]);inset.tick_params(labelsize=7.3)
    inset.set_title('0–20°',fontsize=7.5,pad=2)
    for spine in inset.spines.values():spine.set_visible(True);spine.set_linewidth(.55)
    a=ax[0,1]
    for i,(z,t0,dur,c,nm,sm) in enumerate(zip(frames,START,DUR,COLORS,NAMES,summary)):
        y=2-i;a.plot([0,dur],[y,y],color='#D7D7D7',lw=3,zorder=0)
        a.scatter(z.t_rel_s-t0,np.full(len(z),y),color=c,marker='|',s=25,lw=.8)
        a.text(0,y+.24,nm,fontsize=8,ha='left',va='bottom')
        a.text(390,y+.24,f"{100*sm['new_output_fraction']:.1f}%",fontsize=8,ha='right',va='bottom')
    a.set(xlim=(0,400),ylim=(-.35,2.65),xlabel='Time from trial start (s)');a.set_yticks([]);a.set_xticks([0,100,200,300,400]);panel(a,'b','New heading output')
    p=TABLES/'RTKLIB_EPOCH_DIAGNOSTICS.csv';trace=read(p)
    q=trace[(trace.q==1)&(trace.observation_relative_s>=66)&(trace.observation_relative_s<=340)].copy()
    q['elapsed_s']=q.output_relative_s-66
    bad=q.fixed_large_length_residual_count.gt(0)
    assert len(q)==153 and bad.sum()==35
    assert q.baseline_length_m.between(.20,.75).all()
    q.to_csv(DATA/'NOMINAL_Q1_BASELINE_DISPLAY.csv',index=False)
    for cidx,lim in enumerate([(0,274),(10,22)]):
        a=ax[1,cidx];a.axhspan(.31,.39,color='#E9E9E9',zorder=0)
        a.axhline(.35,color='#222222',ls='--',lw=.8,zorder=1)
        z=q[q.elapsed_s.between(*lim)];b=z.fixed_large_length_residual_count.gt(0)
        a.scatter(z.loc[~b,'elapsed_s'],z.loc[~b,'baseline_length_m'],s=11,facecolors='none',edgecolors='#0072B2',lw=.7,zorder=3)
        a.scatter(z.loc[b,'elapsed_s'],z.loc[b,'baseline_length_m'],s=17,color='#D55E00',marker='x',lw=.85,zorder=4)
        a.set(xlim=lim,ylim=(.20,.75),xlabel='Time from trial start (s)',ylabel='Baseline length (m)')
        a.set_yticks([.2,.35,.5,.7]);tidy(a,xbins=4,ybins=4);a.set_yticks([.2,.35,.5,.7])
        panel(a,chr(99+cidx),'Fixed-baseline length' if cidx==0 else 'Enlarged interval')
    ax[1,0].axvspan(10,22,color='#E3D3C7',alpha=.65,zorder=.2)
    fig.legend(handles=[Line2D([],[],color=c,ls=st,label=n) for c,st,n in zip(COLORS,STYLES,NAMES)],loc='upper center',bbox_to_anchor=(.55,.992),ncol=3,columnspacing=1.2)
    fig.legend(handles=[Line2D([],[],marker='o',mfc='none',mec='#0072B2',ls='',label='Residual ≤ 4σ'),Line2D([],[],marker='x',color='#D55E00',ls='',label='Residual > 4σ'),Line2D([],[],color='#222222',ls='--',label='Nominal 0.35 m')],loc='upper center',bbox_to_anchor=(.55,.493),ncol=3,columnspacing=1.1)
    en='Availability and physical consistency of short-baseline heading from the original RTKLIB moving-base configuration. (a) Cumulative distributions of absolute heading errors at newly available fixed outputs for the three trials; the inset enlarges 0–20° without renormalizing. (b) New-output times; percentages refer to all paired epochs within each trial. (c) Baseline lengths of all 153 fixed outputs in the nominal-walking evaluation window, including 35 with a logged length residual above 4σ. The dashed line is the installed length of 0.35 m, and the gray band is ±4σ with the configured length standard deviation σ = 0.01 m. (d) Enlargement of the shaded 10–22 s interval in (c). All panels use the saved trial windows; the heading quantity is obtained from the horizontal projection of the lateral baseline and compared with the reference yaw.'
    zh='原始RTKLIB动基线配置下，短基线航向的输出可用性与物理一致性。(a) 三种工况中新固定输出的绝对航向误差累积分布，小窗放大0–20°，保持原累积分布分母。(b) 新固定输出的时刻；百分比以各实验窗内的全部配对历元为分母。(c) 常规行走评价窗内全部153个固定输出的基线长度，其中35个日志长度残差超过4σ。虚线为安装长度0.35 m，灰带为配置长度标准差σ=0.01 m所对应的±4σ范围。(d) 放大(c)中的10–22 s着色区间。所有面板均使用保存的实验窗口；航向由横向基线的水平投影换算，并与参考航向比较。'
    export(fig,OUT,'Q2_heading_availability_and_consistency',caption_en=en,caption_zh=zh,meaning_zh='新固定输出的覆盖率与输出后的物理一致性是两个问题：本组数据中固定解稀疏，且固定状态仍可能伴随显著长度残差。',sources=[DATA/f'{s}_V0_full_saved_heading.csv.gz' for s in SEQ]+[p],technical_notes={'saved_result_only':True,'paired_counts':summary,'trace_window_Q1':153,'trace_window_large_length_Q1':35,'trace_full_history_Q1':177,'trace_full_history_epochs':1509,'conditional_CDF':'Each CDF uses native-valid outputs only. Coverage shown separately. No held values or interpolation.','time_convention':'Upper panels elapsed from each evaluation start; lower panels use clock-corrected output time minus66s, selected by saved observation time.','mechanism':'All35 Q1 length warnings had at least one successful float update with the length pseudo-observation. Fixed postfit logs but does not reject these residuals. No unique physical-cause inference.','zoom_selection':'10–22s displays the saved cluster including maximum length0.7077479565m at16s; preexisting diagnostic case, not a new run.','reference_quantity':'Lateral-baseline projected heading compared with commercial fused Euler yaw; under roll/pitch the quantities differ.','no_new_scientific_calls':True},axes=list(ax.flat))
    pd.DataFrame(summary).to_csv(TABLES/'Q2_MAIN_OUTPUT_COUNTS.csv',index=False)

def copy_supplements():
    mapping=[('C03','SQ2_RTKLIB_all_configurations','RTKLIB四配置的航向精度和连续性'),('C04','SQ2_raw_dual_antenna_methods','三种原始双天线处理路线的方向与输出')]
    for old,new,title in mapping:
        for ext in ['png','pdf','svg']:shutil.copy2(OLD/(old+'.'+ext),OUT/(new+'.'+ext))
        (OUT/'preview').mkdir(exist_ok=True)
        for suffix in ['.png','_gray.png']:shutil.copy2(OLD/'preview'/(old+suffix),OUT/'preview'/(new+suffix))
        meta=json.loads((OLD/(old+'.json')).read_text());meta['id']=new;meta['title_zh']=title
        meta['reused_from']=public(OLD/(old+'.json'));meta['visual_review']='PENDING';meta['reused_figure_sha256']={x:hashlib.sha256((OUT/(new+'.'+x)).read_bytes()).hexdigest() for x in ['png','pdf','svg']}
        meta['reuse_note']='Figure data and layout retained from the completed 2026-10-09 export; all15 saved source tables reread in full for this package. Current color and grayscale visual review required.'
        if old=='C04':
            meta['caption_en']='Heading errors and available output times for three raw dual-antenna processing methods during nominal walking, large body motion and single-antenna obstruction. The upper row shows errors of the recorded valid directional candidates, and the lower row marks their output times. C-LAMBDA and C-WLS denote independent implementations of the corresponding constrained objectives; these candidate outputs have no integer acceptance test. DD-KF uses the saved double-difference filter output. Curves break across unavailable epochs and angular wrapping; no held values are inserted. The plotted direction is derived from the horizontal projection of the lateral baseline and compared with the reference yaw.'
            meta['caption_zh']='三种原始双天线观测处理方法在常规行走、大幅机身运动与单侧天线遮挡下的航向误差和输出时刻。上排为已记录有效方向候选的误差，下排为输出时间。C-LAMBDA和C-WLS为对应约束目标的独立实现，其候选输出未设整数接受检验；DD-KF使用保存的双差滤波输出。缺测和角度跳变处断线，不插入保持值。所画方向由横向基线的水平投影换算，并与参考航向比较。'
        (OUT/(new+'.json')).write_text(json.dumps(meta,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

def raw_methods_figure():
    setup();fig,axs=plt.subplots(2,3,figsize=(174*MM,132*MM))
    fig.subplots_adjust(left=.14,right=.98,bottom=.13,top=.88,wspace=.30,hspace=.65)
    methods=['EXT01','EXT02','EXT03'];names=['C-LAMBDA','C-WLS','DD-KF'];counts=[];paths=[]
    for c,(seq,t0,dur) in enumerate(zip(SEQ,START,DUR)):
        p=DATA/f'{seq}_all_methods_all_window_epochs.csv.gz';d=read(p);paths.append(p)
        for j,(method,name,col,style) in enumerate(zip(methods,names,COLORS,STYLES)):
            z=d[d.method_id.eq(method)];q=z[z.valid.eq(1)&z.error_valid_deg.notna()]
            vals=np.sort(np.abs(q.error_valid_deg));prob=np.arange(1,len(vals)+1)/len(vals)
            axs[0,c].step(vals,prob,where='post',color=col,ls=style,lw=1.0)
            axs[1,c].plot([0,dur],[2-j,2-j],color='#DDDDDD',lw=4,zorder=0)
            axs[1,c].scatter(q.t_rel_s-t0,np.full(len(q),2-j),color=col,marker='|',s=24,lw=.7)
            counts.append({'sequence':seq,'method':method,'available':len(q),'denominator':len(z)})
        a=axs[0,c];a.set(xlim=(0,180),ylim=(0,1.02),xlabel='Absolute error (deg)');a.set_xticks([0,90,180]);a.set_yticks([0,.5,1]);panel(a,chr(97+c),NAMES[c])
        a=axs[1,c];a.set(xlim=(0,dur),ylim=(-.5,2.5),xlabel='Time (s)');a.set_yticks([2,1,0],names);a.tick_params(labelleft=c==0);tidy(a,xbins=3);a.set_yticks([2,1,0],names);panel(a,chr(100+c))
    axs[0,0].set_ylabel('Cumulative fraction');axs[1,0].set_ylabel('Available output')
    fig.legend(handles=[Line2D([],[],color=c,ls=s,label=n) for c,s,n in zip(COLORS,STYLES,names)],loc='upper center',bbox_to_anchor=(.54,.99),ncol=3)
    en='Heading-error distributions and output availability for three raw dual-antenna processing methods during nominal walking, large body motion and single-antenna obstruction. The upper row shows cumulative distributions of absolute directional error at each method’s recorded valid outputs; the lower row marks their output times. C-LAMBDA and C-WLS denote independent implementations of the constrained objectives, with no integer acceptance test on these candidates. DD-KF uses the saved double-difference filter output. No held heading is added. The plotted direction is derived from the horizontal projection of the lateral baseline and compared with the reference yaw.'
    zh='三种原始双天线观测处理方法在常规行走、大幅机身运动与单侧天线遮挡下的航向误差分布和可用输出。上排为各方法已记录有效输出时刻的绝对方向误差累积分布，下排标出对应输出时间。C-LAMBDA和C-WLS为对应约束目标的独立实现，这些方向候选未设整数接受检验；DD-KF使用保存的双差滤波输出，不插入保持航向。所画方向由横向基线的水平投影换算，并与参考航向比较。'
    export(fig,OUT,'SQ2_raw_dual_antenna_methods',caption_en=en,caption_zh=zh,meaning_zh='完整使用九组保存结果，把方向误差分布与输出覆盖分开呈现，避免密集正负180度跳转线遮住三种方法的差别。',sources=paths,technical_notes={'identity':'EXT V2 TECH_RETRY_2 generation2 saved results; no post-result guard backfill','support':counts,'cdf':'Absolute saved native-valid errors sorted for display only; no interpolation, holding or scientific recomputation. Each method uses its own valid support.','candidate_vs_fixed':'EXT01/02 have no acceptance test; DD-KF ratio-accepted subset78/70/5 is not true integer success.','quantity':'Projected lateral-baseline heading versus commercial fused Euler yaw.','read_scope':'All3 combined-window source tables and every method row read.','no_new_scientific_calls':True},axes=list(axs.flat))
    pd.DataFrame(counts).to_csv(TABLES/'RAW_METHOD_OUTPUT_COUNTS.csv',index=False)

if __name__=='__main__':
    if '--main-only' in sys.argv: main_figure()
    else:
        prepare();main_figure();copy_supplements();raw_methods_figure()
        pd.DataFrame(sources).to_csv(OUT/'SOURCES_READ.csv',index=False)
        print('saved source tables:',len(sources),'scientific calls:0')
