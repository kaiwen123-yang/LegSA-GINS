"""Plot saved frozen-V3 observations and matched replay outcomes; no estimation."""
from pathlib import Path
import json,sys,shutil,argparse
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.colors import TwoSlopeNorm,LogNorm,LinearSegmentedColormap
from PIL import Image

OUT=Path(__file__).resolve().parent
BASE=Path('/mnt/g/LegSA-GINS-project/V3五问题论文组图_20261011')
TAB=BASE/'aiding/tables'
SKILL=Path('/mnt/c/Users/ykw/.codex/skills/nature-figure/scripts')
sys.path.insert(0,str(SKILL))
from audit_panel_alignment import require_matplotlib_panel_alignment
for p in ['preview','figures','tables','qa']:(OUT/p).mkdir(exist_ok=True)
plt.rcParams.update({'font.family':'sans-serif','font.sans-serif':['Arial','Liberation Sans','DejaVu Sans'],
 'font.size':8,'axes.labelsize':8,'axes.titlesize':8.5,'xtick.labelsize':8,'ytick.labelsize':8,
 'legend.fontsize':8,'legend.frameon':False,'axes.spines.top':False,'axes.spines.right':False,
 'axes.linewidth':.6,'xtick.direction':'out','ytick.direction':'out','xtick.major.size':2.5,
 'ytick.major.size':2.5,'pdf.fonttype':42,'svg.fonttype':'none','path.simplify':False})
BLUE='#0072B2';ORANGE='#D55E00';PURPLE='#98669C';GRAY='#858585';GREEN='#009E73'
STYLE={'F01':(GRAY,':','Basic GNSS/INS'),'F03':(ORANGE,'--','Basic + heading'),
 'F04':(BLUE,'-','LegSA-GINS'),'A05':(PURPLE,'--','Without tilt aiding'),
 'A06':(PURPLE,'--','Without body velocity'),'A04':(PURPLE,'--','Without source weighting')}
SEQS=['BY2','BY2H','BY2O'];START={'BY2':66,'BY2H':413,'BY2O':3186}
NAMES=['Nominal walking','Large body motion','Antenna obstruction']
AV=pd.read_csv(TAB/'ERROR_SERIES_AVAILABILITY6468.csv')
CORE=pd.read_csv(TAB/'CORE5951.csv');ADD=pd.read_csv(TAB/'ADD495.csv')
PAIR=pd.read_csv(TAB/'SINGLEMODULE_CASE_PAIRS2164.csv')
NAT=pd.read_csv(TAB/'NATURAL33.csv')
SOURCES=[];CACHE={};CAPTIONS={}

def series(run):
    if run not in CACHE:
        p=Path(AV.loc[AV.run_id==run,'path'].iloc[0]);d=pd.read_csv(p)
        assert d.time.is_monotonic_increasing
        CACHE[run]=d;SOURCES.append({'run_id':run,'path':str(p),'rows':len(d)})
    return CACHE[run]

def natseries(seq,method):
    a=AV[(AV.sequence_id==seq)&(AV.method_id==method)]
    a=a[a.case_id=='C00_clean_normal'] if seq=='BY2' else a[a.domain=='SEQUENCE']
    assert len(a)==1
    return series(a.run_id.iloc[0])

def line(ax,t,y,color,ls='-',lw=.8):
    t=np.asarray(t);y=np.asarray(y);splits=np.flatnonzero(np.diff(t)>.1)+1
    for inds in np.split(np.arange(len(t)),splits):
        if len(inds):ax.plot(t[inds],y[inds],color=color,ls=ls,lw=lw,rasterized=True)

def panel(ax,letter,title):
    ax.set_title(f'({letter}) {title}',loc='left',fontweight='bold',pad=8)

def save(fig,name,axes,rows=None,cols=None):
    fig.canvas.draw()
    ids=[f'p{i}' for i in range(len(axes))]
    kw={}
    if rows:kw['row_groups']=[[ids[i] for i in row] for row in rows]
    if cols:kw['column_groups']=[[ids[i] for i in col] for col in cols]
    require_matplotlib_panel_alignment(fig,axes=axes,panel_ids=ids,strict=True,
        tolerance_pt=1.5,gutter_tolerance_pt=1.5,json_out=OUT/'qa'/f'{name}.alignment.json',**kw)
    fig.savefig(OUT/'figures'/f'{name}.pdf',dpi=600,facecolor='white')
    fig.savefig(OUT/'figures'/f'{name}.svg',dpi=600,facecolor='white')
    fig.savefig(OUT/'figures'/f'{name}.png',dpi=600,facecolor='white')
    fig.savefig(OUT/'preview'/f'{name}.png',dpi=300,facecolor='white')
    # A lossless compressed TIFF is a publication export, not a processed data image.
    fig.savefig(OUT/'figures'/f'{name}.tiff',dpi=600,facecolor='white',pil_kwargs={'compression':'tiff_lzw'})
    Image.open(OUT/'preview'/f'{name}.png').convert('L').save(OUT/'preview'/f'{name}_gray.png')
    plt.close(fig);print('SAVED',name,flush=True)

def fig6():
    fig,axs=plt.subplots(3,3,figsize=(174/25.4,171/25.4))
    fig.subplots_adjust(left=.095,right=.985,bottom=.075,top=.85,wspace=.29,hspace=.60)
    fig.legend(handles=[Line2D([],[],color=STYLE[m][0],ls=STYLE[m][1],label=STYLE[m][2]) for m in ['F01','F03','A05','F04']],
        loc='upper center',bbox_to_anchor=(.53,.999),ncol=2,handlelength=2.5,columnspacing=2)
    fields=['yaw_err_deg','roll_err_deg','pitch_err_deg'];metrics=['yaw_rmse_deg','roll_rmse_deg','pitch_rmse_deg']
    natural_rows=[]
    for col,(seq,scene) in enumerate(zip(SEQS,NAMES)):
        pos=axs[0,col].get_position()
        fig.text(pos.x0+pos.width/2,.928,scene,ha='center',fontsize=9,fontweight='bold')
        for row,(field,metric) in enumerate(zip(fields,metrics)):
            ax=axs[row,col];methods=['F01','F03','F04'] if row==0 else ['A05','F04'];vals=[]
            for m in methods:
                d=natseries(seq,m);color,ls,_=STYLE[m];line(ax,d.time-START[seq],d[field],color,ls,lw=.6 if m=='F04' else .75)
                v=float(NAT[(NAT.sequence_id==seq)&(NAT.internal_method_id==m)][metric].iloc[0]);vals.append(v)
                natural_rows.append(dict(scene=scene,sequence_id=seq,method=m,metric=metric,rmse=v))
            ax.axhline(0,color='#777777',ls=':',lw=.5)
            ax.set_title(f'({chr(97+row*3+col)}) '+['Heading','Roll','Pitch'][row],loc='left',fontweight='bold',pad=8,y=1.13)
            # Direct quantitative labels expose small but real differences without changing the data.
            ax.text(.015,1.035,'RMSE:',transform=ax.transAxes,fontsize=8,ha='left',va='bottom')
            for j,(m,v) in enumerate(zip(methods,vals)):
                ax.text(.38+j*(.205 if row==0 else .31),1.035,f'{v:.2f}',transform=ax.transAxes,color=STYLE[m][0],fontsize=8,ha='left',va='bottom')
            ax.set_xlim(0,274 if seq!='BY2O' else 377)
            ax.set_xticks([0,100,200] if seq!='BY2O' else [0,150,300])
            if col==0:ax.set_ylabel('Error (deg)')
            if row==2:ax.set_xlabel('Time (s)')
            if row==0:ax.set_ylim(-20,23);ax.set_yticks([-15,0,15])
            elif row==1:ax.set_ylim(-5,10);ax.set_yticks([-4,0,4,8])
            else:ax.set_ylim(-12,9);ax.set_yticks([-8,-4,0,4,8])
            if col>0:ax.tick_params(labelleft=False)
    pd.DataFrame(natural_rows).to_csv(OUT/'tables/F06_NATURAL_ATTITUDE_RMSE.csv',index=False)
    CAPTIONS['F06_attitude']={'en':'Contribution of short-baseline heading and onboard tilt observations to attitude estimation. Columns show nominal walking, large body motion, and antenna obstruction. (a–c) Heading errors for basic GNSS/INS, the same basic configuration with heading updates, and LegSA-GINS. All share the initial direction. (d–i) Roll and pitch errors for LegSA-GINS with and without tilt aiding. Colour-matched values above each panel give the whole-window RMSE in degrees. Every original sample is retained; gaps are broken at 0.1 s. The comparisons isolate heading addition only between the two basic configurations and tilt removal only within the full configuration.',
      'zh':'短基线航向和机载倾角观测对姿态估计的作用。三列对应常规行走、大幅机身运动和单侧天线遮挡。(a–c)比较共享初始方向的基础GNSS/INS、基础配置增加航向更新、完整方法；(d–i)比较完整方法保留和关闭倾角辅助的横滚及俯仰误差。各面板上方以曲线同色数字给出全窗RMSE（度），使曲线重合处的真实量差可以直接读取。保留全部原始样本，时间缺口不连线。'}
    save(fig,'F06_attitude',list(axs.flat),rows=[[0,1,2],[3,4,5],[6,7,8]],cols=[[0,3,6],[1,4,7],[2,5,8]])

def fig7():
    fig,axs=plt.subplots(2,2,figsize=(174/25.4,151/25.4))
    fig.subplots_adjust(left=.115,right=.98,bottom=.09,top=.78,wspace=.36,hspace=.59)
    fig.legend(handles=[Line2D([],[],color=STYLE[m][0],ls=STYLE[m][1],label=STYLE[m][2]) for m in ['A06','F04']],loc='upper center',bbox_to_anchor=(.55,.998),ncol=2,handlelength=2.5)
    headers=['All GNSS observations interrupted','Translation interrupted; heading retained']
    for col,txt in enumerate(headers):
        x=[.115,.615][col];fig.text(x,.913,txt,fontsize=8.0,fontweight='bold',ha='left')
        fig.text(x,.865,'Heading: unavailable\nAuxiliary updates: paused' if col==0 else 'Heading: updated\nAuxiliary updates: active',fontsize=8,ha='left',va='center',linespacing=1.5)
    stats=[]
    for col,fam in enumerate(['A1','A2']):
        ax=axs[0,col];rows=ADD[(ADD.case_family==fam)&(ADD.duration_s==20)&(ADD.seed_index=='seed_00')]
        t0=float(rows.outage_start_s.iloc[0]);saved={}
        for m in ['A06','F04']:
            r=rows[rows.internal_method_id==m].iloc[0];d=series(r.run_id);t=d.time-t0;keep=t.between(-4,32)
            color,ls,_=STYLE[m];line(ax,t[keep],d.loc[keep,'horizontal_err_m'],color,ls,1.0);saved[m]=(t,d)
        ax.axvspan(0,20,color='#F0F0F0',zorder=-2);ax.axvline(20,color='#555555',ls=':',lw=.7)
        ax.set(xlim=(-4,32),xlabel='Time from interruption start (s)',ylabel='Horizontal error (m)')
        ax.set_xticks([0,10,20,30]);panel(ax,chr(97+col),'20-s interruption and recovery')
        ax.annotate('GNSS\nrestored',xy=(20,.97),xycoords=('data','axes fraction'),xytext=(.985,.73),textcoords='axes fraction',ha='right',fontsize=8,arrowprops={'arrowstyle':'-','lw':.5})
        if col==1:
            ins=ax.inset_axes([.09,.48,.40,.35]);t,d=saved['F04'];q=t.between(0,20)
            line(ins,t[q],d.loc[q,'horizontal_err_m'],BLUE,lw=.9);ins.set(xlim=(0,20),ylim=(0,2.5));ins.set_xticks([0,20]);ins.set_yticks([0,2]);ins.tick_params(labelsize=8,pad=1)
            ins.set_title('LegSA-GINS',fontsize=8,color=BLUE,pad=2)
        ax=axs[1,col];dur=[10,20,30] if fam=='A1' else [10,20]
        for i,n in enumerate(dur):
            d=ADD[(ADD.case_family==fam)&(ADD.duration_s==n)]
            a=d[d.internal_method_id=='F04'].set_index('seed_index').sort_index();b=d[d.internal_method_id=='A06'].set_index('seed_index').sort_index();assert list(a.index)==list(b.index) and len(a)==9
            assert np.isfinite(a.horizontal_rmse_m).all() and np.isfinite(b.horizontal_rmse_m).all()
            assert (a.horizontal_rmse_m>0).all() and (b.horizontal_rmse_m>0).all()
            for j,k in enumerate(a.index):
                jitter=(j-4)*.01;x=[i-.13+jitter,i+.13+jitter];y=[b.loc[k,'horizontal_rmse_m'],a.loc[k,'horizontal_rmse_m']]
                ax.plot(x,y,color='#BBBBBB',lw=.7,zorder=1)
                ax.scatter(x,y,color=[PURPLE,BLUE],marker='o',s=17,zorder=2)
            stats.append(dict(condition=fam,duration_s=n,n_pairs=9,without_velocity_median=b.horizontal_rmse_m.median(),full_median=a.horizontal_rmse_m.median()))
        ax.set_yscale('log');ax.set_ylim(.075,65);ax.set_yticks([.1,1,10],['0.1','1','10']);ax.set_xticks(range(len(dur)),[str(v) for v in dur]);ax.set_xlim(-.4,len(dur)-.6)
        ax.set(xlabel='Interruption duration (s)',ylabel='Whole-window H RMSE (m)');panel(ax,chr(99+col),'All nine placements per duration')
    pd.DataFrame(stats).to_csv(OUT/'tables/F07_ALL_NINE_PLACEMENTS_SUMMARY.csv',index=False)
    CAPTIONS['F07_conditional_translation']={'en':'Conditional translation benefit of body-velocity aiding during controlled interruptions of recorded observations. (a,b) One 20-s interruption and recovery, with its exact observation and update conditions stated above each column. Grey shading denotes the interrupted interval and the dotted line the restoration of GNSS observations. The inset shows the full-method error during the heading-retained interruption. (c,d) Whole-window horizontal RMSE for all nine interruption placements per duration on one recorded route; lines join the same placement. In the evaluated implementation, complete GNSS loss also pauses the auxiliary updates. Thus the two columns compare operating conditions, not a pure factorial removal of heading. No averaging or smoothing is applied to the time histories.',
      'zh':'实测观测受控中断中机身速度辅助的条件平移收益。每列上方直接列出航向观测和辅助更新状态。(a,b)一处20秒中断及恢复，灰色区间为中断，虚线为GNSS恢复；插图完整展示保留航向时完整方法的中断期误差。(c,d)同一实测路线每个时长全部九个布置的全窗水平RMSE，细线连接相同布置。全部GNSS中断在所评价实现中也暂停辅助更新，因此左右列比较的是实际工作条件，不构成纯航向有无的因果隔离。'}
    save(fig,'F07_conditional_translation',list(axs.flat),rows=[[0,1],[2,3]],cols=[[0,2],[1,3]])

def fig8():
    fig,axs=plt.subplots(3,2,figsize=(174/25.4,187/25.4))
    fig.subplots_adjust(left=.12,right=.98,bottom=.075,top=.91,wspace=.37,hspace=.61)
    fig.legend(handles=[Line2D([],[],color=STYLE[m][0],ls=STYLE[m][1],label=STYLE[m][2]) for m in ['A04','F04']],loc='upper center',bbox_to_anchor=(.55,.999),ncol=2,handlelength=2.5)
    pair=PAIR[(PAIR.module=='SA')&(PAIR.case_id=='D15_seed_00')].iloc[0]
    ds={'A04':series(pair.ablation_run_id),'F04':series(pair.candidate_run_id)}
    for ax,field,ylabel,letter,title in [(axs[0,0],'yaw_err_deg','Heading error (deg)','a','Heading benefit'),(axs[0,1],'horizontal_err_m','Horizontal error (m)','b','Positioning cost')]:
        for m,d in ds.items():
            if letter=='a':line(ax,d.time-66,d[field],STYLE[m][0],STYLE[m][1],.85)
            else:
                assert np.isfinite(d[field]).all()
                x=np.sort(d[field]);y=np.arange(1,len(x)+1)/len(x)*100
                ax.plot(x,y,color=STYLE[m][0],ls=STYLE[m][1],lw=1.1)
        if letter=='a':ax.set(xlim=(0,274),xlabel='Time (s)',ylabel=ylabel)
        else:ax.set(xlabel='Horizontal error (m)',ylabel='Cumulative epochs (%)',ylim=(0,100),xlim=(0,12))
        panel(ax,letter,title)
        vals=[pair.ablation_yaw_rmse_deg,pair.candidate_yaw_rmse_deg] if letter=='a' else [pair.ablation_horizontal_rmse_m,pair.candidate_horizontal_rmse_m]
        ax.text(.96,.12 if letter=='b' else .97,f'RMSE: {vals[0]:.2f} → {vals[1]:.2f}',transform=ax.transAxes,ha='right',va='top',fontsize=8,bbox={'facecolor':'white','edgecolor':'none','alpha':.85,'pad':1.5})
    tr=pd.read_csv(TAB/'D15_SOURCE_WEIGHT_TRACE_ALL.csv');ax=axs[1,0]
    for i,(key,col,label) in enumerate([('receiver_position','#333333','GNSS position'),('dual_antenna_yaw',GREEN,'Heading'),('go2_horizontal_velocity',PURPLE,'Body velocity')]):
        x=tr[tr.source_id==key].combined_R_scale.to_numpy();a,b,c,d,e=np.quantile(x,[0,.25,.5,.75,1])
        ax.plot([i,i],[a,e],color=col,lw=.8);ax.plot([i,i],[b,d],color=col,lw=7,solid_capstyle='butt');ax.scatter(i,c,color='white',edgecolors=col,s=22,zorder=3)
    ax.set(xlim=(-.45,2.45),ylim=(.5,11),ylabel='Covariance multiplier');ax.set_yticks([1,5,10]);ax.set_xticks([0,1,2],['Position','Heading','Body velocity']);panel(ax,'c','Recorded source multipliers')
    ax=axs[1,1];out=pd.read_csv(TAB/'FULL_OUTCOME55.csv');o=out[(out.domain=='CORE')&out.internal_method_id.isin(['A04','F04'])].set_index('internal_method_id')
    for i,m in enumerate(['A04','F04']):
        left=0
        for fld,color in [('completed',BLUE),('diverged',ORANGE),('no_valid_heading','#BDBDBD')]:
            val=int(o.loc[m,fld]);ax.barh(i,val,left=left,color=color,height=.48);left+=val
        ax.text(5,i,str(int(o.loc[m,'completed'])),va='center',color='white',fontsize=8)
        ax.text(0,i+.35,f"{int(o.loc[m,'diverged'])} diverged; {int(o.loc[m,'no_valid_heading'])} no initial heading",fontsize=8,ha='left')
    ax.set_yticks([0,1],['Weighting off','LegSA-GINS']);ax.set_xlim(0,541);ax.set_xticks([0,270,541]);ax.set_xlabel('Registered cases');ax.set_ylim(-.4,1.65);panel(ax,'d','Run outcomes')
    joint=PAIR[(PAIR.module=='SA')&PAIR.joint_finite].copy();assert len(joint)==513
    for ax,field,scale,unit,letter,title in [(axs[2,0],'delta_horizontal_rmse_m',1000,'mm','e','Paired positioning change'),(axs[2,1],'delta_yaw_rmse_deg',1,'deg','f','Paired heading change')]:
        x=np.sort(joint[field].to_numpy()*scale);y=np.arange(1,len(x)+1)/len(x)*100
        ax.plot(x,y,color=BLUE,lw=1.2);ax.axvline(0,color='#777777',ls=':',lw=.7)
        ax.set_xscale('symlog',linthresh=1 if scale==1000 else .02);ax.set_ylim(0,100);ax.set_yticks([0,50,100]);ax.set_xlabel(f'Full − weighting off ({unit})');ax.set_ylabel('Cumulative cases (%)');panel(ax,letter,title)
        ticks=[-1000,-10,0,10,1000] if scale==1000 else [-100,-1,0,1]
        ax.set_xticks(ticks,[str(v) for v in ticks]);ax.minorticks_off()
        median_text=f'median {np.median(x):+.3f} {unit}' if scale==1000 else 'median ≈ 0 deg'
        ax.text(.97,.07,f'n = 513\n{median_text}',transform=ax.transAxes,ha='right',va='bottom',fontsize=8)
    joint.to_csv(OUT/'tables/F08_ALL_513_MATCHED_CASES.csv',index=False)
    pd.DataFrame([{'metric':k,'n_pairs':len(joint),'median_full_minus_ablation':float(joint[k].median())} for k in ['delta_horizontal_rmse_m','delta_yaw_rmse_deg']]).to_csv(OUT/'tables/F08_PAIRED_MEDIANS.csv',index=False)
    CAPTIONS['F08_quality_tradeoffs']={'en':'Source-dependent covariance scaling under degraded observation quality. (a,b) Heading and horizontal errors in one recorded-data replay with added GNSS position noise (horizontal standard deviation 3 m, vertical 5 m). (c) The actually recorded covariance multipliers for three observation sources; all six sources are retained in source data. (d) All 541 registered outcomes for each configuration, including divergence and absence of an initial heading. (e,f) Empirical cumulative distributions of full-minus-ablation RMSE in the 513 jointly completed cases; negative changes favour the full configuration. Signed-log horizontal axes retain both small changes and tails, with linear neighbourhoods of ±1 mm and ±0.02 degrees. Extra completions do not enter these paired distributions.',
      'zh':'观测质量下降时来源协方差缩放的收益与代价。(a,b)代表位置加噪回放中航向误差明显降低而位置误差略增；(c)实际记录的来源倍率，倍率增大代表相对降低信任，全部六来源轨迹保存在源数据；(d)每配置全部541个注册结果，包括发散和无初始方向；(e,f)双方均完成的513例中完整方法减关闭加权的RMSE变化累积分布，负值表示完整方法误差较低。横轴为有符号对数，零附近分别为±1毫米和±0.02度的线性区，保留小变化及长尾。新增完成案例不混入共同配对。'}
    save(fig,'F08_quality_tradeoffs',list(axs.flat),rows=[[0,1],[2,3],[4,5]],cols=[[0,2,4],[1,3,5]])

FAMILIES=['gnss_outage','gnss_sampling','position_value','position_std_status','dual_yaw','velocity_raw_doppler','go2_prior_metadata','multi_source_mixed']
FAMNAMES=['GNSS outage','GNSS sampling','Position values','Position quality','Heading','Velocity / Doppler','Body-prior metadata','Mixed sources']
MODS=['RD','SA','RP','HV'];MODLABEL=['Doppler','Weighting','Tilt','Body vel.']

def replay_tables():
    rows=[];keep=PAIR[(PAIR.case_family!='clean')]
    for family in FAMILIES:
        for mod in MODS:
            d=keep[(keep.case_family==family)&(keep.module==mod)];p=d[d.joint_finite]
            for metric in ['horizontal_rmse_m','yaw_rmse_deg','roll_rmse_deg','pitch_rmse_deg']:
                b=p['ablation_'+metric].to_numpy();a=p['candidate_'+metric].to_numpy();assert (b>0).all()
                rel=100*(b-a)/b
                rows.append({'family':family,'module':mod,'metric':metric,'registered':len(d),'paired':len(p),
                  'median_improvement_percent':np.median(rel),'full_lower':int((a<b).sum()),'full_higher':int((a>b).sum()),
                  'ablation_failed_full_completed':int(((d.ablation_status!='COMPLETED')&(d.candidate_status=='COMPLETED')).sum()),
                  'full_failed_ablation_completed':int(((d.candidate_status!='COMPLETED')&(d.ablation_status=='COMPLETED')).sum()),
                  'both_failed':int(((d.candidate_status!='COMPLETED')&(d.ablation_status!='COMPLETED')).sum())})
    d=pd.DataFrame(rows);d.to_csv(OUT/'tables/F10_FAMILY_PAIRED_EFFECTS.csv',index=False);return d

def fig10():
    d=replay_tables();fig,axs=plt.subplots(2,2,figsize=(174/25.4,189/25.4))
    fig.subplots_adjust(left=.245,right=.98,bottom=.25,top=.89,wspace=.28,hspace=.36)
    effectmap=LinearSegmentedColormap.from_list('paired_effect',[PURPLE,'#F8F8F8',BLUE])
    for k,(metric,title) in enumerate(zip(['horizontal_rmse_m','yaw_rmse_deg','roll_rmse_deg','pitch_rmse_deg'],['Horizontal position','Heading','Roll','Pitch'])):
        ax=axs.flat[k];v=d[d.metric==metric].pivot(index='family',columns='module',values='median_improvement_percent').reindex(index=FAMILIES,columns=MODS)
        im=ax.imshow(v.values,cmap=effectmap,norm=TwoSlopeNorm(vmin=-40,vcenter=0,vmax=40),aspect='auto')
        for r in range(8):
            for c in range(4):
                val=v.iloc[r,c];text=f'{val:+.1f}' if abs(val)>=.05 else '0.0';ax.text(c,r,text,ha='center',va='center',fontsize=8,color='white' if abs(val)>27 else '#222222')
        ax.set_xticks(range(4),MODLABEL,rotation=30,ha='right');ax.set_yticks(range(8),FAMNAMES if k%2==0 else ['']*8)
        ax.tick_params(axis='both',length=0,pad=5);panel(ax,chr(97+k),title)
        for s in ax.spines.values():s.set_visible(False)
    cb=fig.add_axes([.34,.144,.50,.018]);cbar=fig.colorbar(im,cax=cb,orientation='horizontal',extend='both');cbar.set_ticks([-40,0,40]);cbar.set_label('Median paired RMSE improvement (%)',fontsize=8)
    fig.text(.60,.071,'Positive: full method lower error; negative: ablation lower error',ha='center',fontsize=8)
    fig.text(.60,.039,'Completed / 540: full 518; −Doppler 517; −weighting 512;',ha='center',fontsize=8)
    fig.text(.60,.017,'−tilt 518; −body velocity 518.',ha='center',fontsize=8)
    fig.text(.60,.981,'Controlled replay: all 60 perturbation types',ha='center',fontsize=9,fontweight='bold')
    fig.text(.60,.945,'Nine registered variants per type · four matched ablations',ha='center',fontsize=8)
    # Complete status is carried beside conditional numerical effects in a compact supplementary source table.
    CAPTIONS['F10_semisynthetic_complementarity']={'en':'Conditional contribution of four observations and quality handling across all 60 perturbation types in controlled replay of one recorded trajectory. Each type has nine registered placements, yielding 540 perturbed cases per configuration. Cells show the median paired percentage reduction in RMSE, 100(ablation − full)/ablation, for raw Doppler, source weighting, tilt and body-velocity removal, grouped by the perturbed physical information. Positive values favour the full method; negative values favour the corresponding ablation. Only jointly completed cases enter each conditional numerical cell, and all completion and failure memberships are retained in the accompanying source table and extended full-configuration maps. No independent-trial significance claim is made. Colour saturates at ±50%; printed numbers retain the full value.',
      'zh':'同一实测路线全部60种观测扰动的受控回放中，四项观测及质量处理的条件贡献。每类扰动九个布置，每配置共540个扰动案例。格内为同案例RMSE相对改善率100×(消融−完整)/消融的中位数，正值有利于完整方法，负值有利于消融。列对应原始Doppler、来源加权、倾角、机身速度的单开关控制；行按受扰物理信息分组。数值只使用双方均完成的配对，全部完成和失败成员保留在配表与全配置扩展图。颜色在±50%饱和，数值标注保留原值。本实验是观测层半合成回放，不等同于独立外场重复或硬件在环。'}
    save(fig,'F10_semisynthetic_complementarity',list(axs.flat),rows=[[0,1],[2,3]],cols=[[0,2],[1,3]])

def extended():
    methods=['F01','F02','F03','F04','A03','A04','A05','A06','A07','A08','A09']
    labels=['Basic','Pos. + yaw','Basic + yaw','LegSA-GINS','−Doppler','−Weighting','−Tilt','−Body vel.','−Tilt, vel.','−W., tilt, vel.','−D., tilt, vel.']
    valid=CORE[CORE.evaluation_status=='COMPLETED']
    # All 61 registered types and every configuration are present, including types with no completed output.
    types=['CLEAN']+[f'D{i:02}' for i in range(1,61)]
    rows=[]
    for typ in types:
        for method in methods:
            a=CORE[(CORE.degradation_type_id==typ)&(CORE.internal_method_id==method)];v=a[a.evaluation_status=='COMPLETED'];assert len(a) in [1,9]
            rows.append({'type':typ,'method':method,'registered':len(a),'completed':len(v),'horizontal_rmse_m_median':v.horizontal_rmse_m.median(),'yaw_rmse_deg_median':v.yaw_rmse_deg.median(),'family':a.case_family.iloc[0]})
    result=pd.DataFrame(rows);result.to_csv(OUT/'tables/ALL61_TYPES_ALL11_CONFIGURATIONS.csv',index=False)
    for metric,title,name in [('horizontal_rmse_m_median','Horizontal RMSE (m)','E10_all_configurations_horizontal'),('yaw_rmse_deg_median','Heading RMSE (deg)','E10_all_configurations_heading')]:
        fig,ax=plt.subplots(figsize=(174/25.4,269/25.4));fig.subplots_adjust(left=.10,right=.98,bottom=.10,top=.875)
        v=result.pivot(index='type',columns='method',values=metric).reindex(index=types,columns=methods)
        cmap=plt.get_cmap('viridis').copy();cmap.set_bad('#E8E8E8');positive=v.values[np.isfinite(v.values)];im=ax.imshow(v,cmap=cmap,norm=LogNorm(vmin=positive.min(),vmax=positive.max()),aspect='auto')
        ax.set_xticks(range(11),labels,rotation=60,ha='left');ax.xaxis.tick_top();ax.set_yticks(range(61),['Clean']+[f'{i:02}' for i in range(1,61)])
        ax.tick_params(labelsize=8,length=0,pad=3);ax.set_ylabel('Perturbation type (01–60); exact definitions in source table')
        for r,typ in enumerate(types):
            for c,m in enumerate(methods):
                a=result[(result.type==typ)&(result.method==m)].iloc[0]
                if a.completed<a.registered:ax.text(c,r,'×' if a.completed==0 else str(int(a.completed)),fontsize=8,ha='center',va='center',color='#333333' if a.completed==0 else 'white')
        cb=fig.add_axes([.21,.055,.60,.015]);bar=fig.colorbar(im,cax=cb,orientation='horizontal')
        ticks=[v for v in [.01,.1,1,10,100] if positive.min()<=v<=positive.max()]
        bar.set_ticks(ticks,labels=[str(v) for v in ticks]);bar.minorticks_off();bar.set_label(title,fontsize=8)
        CAPTIONS[name]={'en':'All registered perturbation types and all eleven frozen-V3 configurations. Cell colour denotes the median RMSE among completed runs on a logarithmic scale. A cross indicates no completed run; a number indicates the number completed out of nine when fewer than nine completed. The clean row has one registered run. Exact type definitions and every native outcome are preserved in source data. These controls use the same recorded route and are not eleven external methods.','zh':'全部注册扰动类型与全部十一种冻结V3配置。颜色为已完成结果的RMSE中位数（对数色标）；叉表示无完成输出，数字表示九次中完成不足九次的数量；干净条件仅一例。精确扰动定义与每个原生结果保留于源数据。十一列为内部配置，不能当作十一种外部算法。'}
        save(fig,name,[ax])

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--only',default='all');a=ap.parse_args()
    for name,fn in [('6',fig6),('7',fig7),('8',fig8),('10',fig10),('extended',extended)]:
        if a.only in ['all',name]:fn()
    for n in ['CORE5951','ADD495','NATURAL33','FULL_OUTCOME55','SINGLEMODULE_CASE_PAIRS2164','METHOD_CONFIGURATION_MAP','CONFIGURATION_CONTRASTS','D15_SOURCE_WEIGHT_TRACE_ALL','SA_SIX_EXTRA_COMPLETIONS']:
        shutil.copy2(TAB/(n+'.csv'),OUT/'tables'/(n+'.csv'))
    source_file=OUT/'SOURCES.json'
    sources_by_run={r['run_id']:r for r in json.loads(source_file.read_text())} if source_file.exists() and a.only!='all' else {}
    sources_by_run.update({r['run_id']:r for r in SOURCES})
    source_file.write_text(json.dumps(list(sources_by_run.values()),ensure_ascii=False,indent=2))
    cp=OUT/'CAPTIONS.json';prev=json.loads(cp.read_text()) if cp.exists() else {};prev.update(CAPTIONS)
    if 'F08_quality_tradeoffs' in prev:
        prev['F08_quality_tradeoffs']['en']=prev['F08_quality_tradeoffs']['en'].replace('(a,b) Heading and horizontal errors','(a) Heading error history and (b) the empirical distribution of all horizontal-error epochs').replace('The actually recorded covariance multipliers for three observation sources','Ranges (thin lines), interquartile ranges (thick segments), and medians (circles) of the actually recorded covariance multipliers for three observation sources')
        prev['F08_quality_tradeoffs']['zh']=prev['F08_quality_tradeoffs']['zh'].replace('(a,b)代表位置加噪回放中航向误差明显降低而位置误差略增','(a)代表位置加噪回放中的完整航向误差时序；(b)同一例全部历元水平误差的累积分布，展示位置代价').replace('(c)实际记录的来源倍率','(c)实际来源倍率的全范围（细线）、四分位区间（粗线）和中位数（圆点）')
    if 'F10_semisynthetic_complementarity' in prev:
        prev['F10_semisynthetic_complementarity']['en']=prev['F10_semisynthetic_complementarity']['en'].replace('nine registered placements','nine registered variants').replace('±50%','±40%')
        prev['F10_semisynthetic_complementarity']['zh']=prev['F10_semisynthetic_complementarity']['zh'].replace('每类扰动九个布置','每类扰动九个注册变体').replace('±50%','±40%')
    cp.write_text(json.dumps(prev,ensure_ascii=False,indent=2))
    (OUT/'CAPTIONS.md').write_text('\n\n'.join('## '+k+'\n\n'+v['zh']+'\n\n'+v['en'] for k,v in prev.items()))

if __name__=='__main__':main()
