"""Plot retained frozen-V3 results. No solver, provider or evaluator invocation."""
from pathlib import Path
import argparse,json,shutil
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.text import Text
from PIL import Image

OUT=Path(__file__).resolve().parent
BASE=Path('/mnt/g/LegSA-GINS-project/V3五问题论文组图_20261011/aiding/tables')
PREV=Path('/mnt/g/LegSA-GINS-project/V3正文重绘_20261011/aiding/tables')
if not BASE.exists():BASE=OUT/'tables'
if not PREV.exists():PREV=OUT/'tables'
for name in ['figures','preview','tables','data','qa']:(OUT/name).mkdir(exist_ok=True)
plt.rcParams.update({'font.family':'sans-serif','font.sans-serif':['Arial','Liberation Sans','DejaVu Sans'],
 'font.size':8,'axes.labelsize':8,'axes.titlesize':8.5,'xtick.labelsize':8,'ytick.labelsize':8,
 'legend.fontsize':8,'legend.frameon':False,'axes.spines.top':False,'axes.spines.right':False,
 'axes.linewidth':.65,'xtick.direction':'out','ytick.direction':'out','xtick.major.size':2.5,
 'ytick.major.size':2.5,'pdf.fonttype':42,'svg.fonttype':'none','path.simplify':False})
BLUE='#0072B2';ORANGE='#D55E00';PURPLE='#956DA8';GRAY='#777777';GREEN='#009E73'
ST={'F01':(GRAY,':','Basic GNSS/INS'),'F03':(ORANGE,'--','Basic + heading'),
 'F04':(BLUE,'-','LegSA-GINS'),'A05':(PURPLE,'--','Without tilt aiding'),
 'A06':(PURPLE,'--','Without body velocity'),'A04':(PURPLE,'--','Without source weighting')}
SEQ=['BY2','BY2H','BY2O'];START={'BY2':66,'BY2H':413,'BY2O':3186}
SCENES=['Nominal walking','Large body motion','Antenna obstruction']
AV=pd.read_csv(BASE/'ERROR_SERIES_AVAILABILITY6468.csv');CORE=pd.read_csv(PREV/'CORE5951.csv')
ADD=pd.read_csv(PREV/'ADD495.csv');PAIR=pd.read_csv(PREV/'SINGLEMODULE_CASE_PAIRS2164.csv')
NAT=pd.read_csv(PREV/'NATURAL33.csv');DEFS=pd.read_csv(PREV/'REGISTERED_61_TYPE_DEFINITIONS.csv')
CACHE={};SOURCES=[];META={};QA=[]

def series(run):
    if run not in CACHE:
        r=AV[AV.run_id==run].iloc[0];p=Path(r.path);local=OUT/'data'/f'{run}.csv.gz'
        readpath=p if p.exists() else local;assert readpath.exists(),(run,r.current_state)
        d=pd.read_csv(readpath);assert d.time.is_monotonic_increasing
        CACHE[run]=d;SOURCES.append({'run_id':run,'source_path':str(p),'rows':len(d)})
        d[['time','yaw_err_deg','horizontal_err_m']].to_csv(local,index=False,compression='gzip')
    return CACHE[run]
def native(seq,m):
    r=AV[(AV.sequence_id==seq)&(AV.method_id==m)]
    r=r[r.case_id=='C00_clean_normal'] if seq=='BY2' else r[r.domain=='SEQUENCE']
    assert len(r)==1
    return series(r.run_id.iloc[0])
def runrow(case,m):
    r=CORE[(CORE.case_id==case)&(CORE.internal_method_id==m)];assert len(r)==1
    return r.iloc[0]
def curve(ax,t,y,m,lw=.8):
    t=np.asarray(t);y=np.asarray(y);c,ls,_=ST[m]
    for inds in np.split(np.arange(len(t)),np.flatnonzero(np.diff(t)>.1)+1):
        if len(inds):ax.plot(t[inds],y[inds],color=c,ls=ls,lw=lw,rasterized=True,zorder=5 if m in ['F03','A04','A05','A06'] else 4)
def zero(ax):ax.axhline(0,color='#AAAAAA',lw=.5,ls=':',zorder=-3)
def title(ax,label,text):ax.set_title(f'({label}) {text}',loc='left',fontweight='bold',pad=7)
def legend(fig,methods,y=.997,ncol=None):
    fig.legend(handles=[Line2D([],[],color=ST[m][0],ls=ST[m][1],lw=1.2,label=ST[m][2]) for m in methods],
      loc='upper center',bbox_to_anchor=(.53,y),ncol=ncol or len(methods),handlelength=2.6,columnspacing=1.4)
def save(fig,name):
    fig.canvas.draw();ren=fig.canvas.get_renderer();bb=fig.bbox;clipped=[];fonts=[]
    for t in fig.findobj(Text):
        if not t.get_visible() or not t.get_text():continue
        fonts.append(t.get_fontsize());b=t.get_window_extent(ren)
        if b.x0<bb.x0-2 or b.x1>bb.x1+2 or b.y0<bb.y0-2 or b.y1>bb.y1+2:clipped.append(t.get_text())
    q={'figure':name,'width_mm':round(fig.get_figwidth()*25.4,4),'height_mm':round(fig.get_figheight()*25.4,4),
      'min_text_pt':min(fonts),'text_outside_canvas':clipped,'data_line_smoothing':False,'png_dpi':600}
    (OUT/'qa'/f'{name}.json').write_text(json.dumps(q,indent=2),encoding='utf8');QA.append(q)
    for ext in ['pdf','svg','png']:
        fig.savefig(OUT/'figures'/f'{name}.{ext}',dpi=600,facecolor='white')
    fig.savefig(OUT/'figures'/f'{name}.tiff',dpi=600,facecolor='white',pil_kwargs={'compression':'tiff_lzw'})
    fig.savefig(OUT/'preview'/f'{name}.png',dpi=240,facecolor='white')
    Image.open(OUT/'preview'/f'{name}.png').convert('L').save(OUT/'preview'/f'{name}_gray.png')
    plt.close(fig);print('SAVED',name,flush=True)

def fig6():
    # Windows are replaced by the event table shared with Fig 3 once available.
    events_path=OUT.parent/'navigation/data/F03_EVENT_WINDOWS.csv'
    if events_path.exists():
        ev=pd.read_csv(events_path);windows={r.sequence:(float(r.elapsed_start_s),float(r.elapsed_end_s),r.label) for _,r in ev.iterrows()}
        ev.to_csv(OUT/'tables/F06_F03_SHARED_EVENTS.csv',index=False)
    else:
        windows={'BY2':(80,100,'Reference-defined turning interval'),'BY2H':(80,100,'Reference-defined turning interval'),'BY2O':(173.94,235.95,'Registered obstruction with 10-s context')}
    fig,axs=plt.subplots(3,3,figsize=(174/25.4,174/25.4),gridspec_kw={'height_ratios':[1.3,1.2,.85]})
    fig.subplots_adjust(left=.10,right=.985,bottom=.07,top=.915,wspace=.34,hspace=.58)
    legend(fig,['F01','F03','F04'],y=1.0)
    rows=[]
    for j,(seq,scene) in enumerate(zip(SEQ,SCENES)):
        lo,hi,label=windows[seq];ds={m:native(seq,m) for m in ['F01','F03','F04']}
        ax=axs[0,j]
        for m,d in ds.items():curve(ax,d.time-START[seq],d.yaw_err_deg,m,.65 if m=='F04' else .85)
        zero(ax);ax.axvspan(lo,hi,color='#EEE9DF',zorder=-4);ax.set(xlim=(0,274 if seq!='BY2O' else 377),ylim=(-20,23),xlabel='Time (s)')
        ax.set_xticks([0,100,200] if seq!='BY2O' else [0,100,200,300])
        ax.set_yticks([-15,0,15]);title(ax,chr(97+j),scene)
        if j==0:ax.set_ylabel('Heading error (deg)')
        else:ax.tick_params(labelleft=False)
        ax=axs[1,j]
        for m,d in ds.items():
            t=d.time-START[seq];q=t.between(lo,hi);curve(ax,t[q],d.loc[q,'yaw_err_deg'],m,1)
        zero(ax);ax.set(xlim=(lo,hi),xlabel='Time (s)');title(ax,chr(100+j),'Turn: 80–100 s' if seq!='BY2O' else 'Obstruction and recovery')
        if seq=='BY2O':
            ax.axvspan(183.94,225.95,color='#EEE9DF',zorder=-4);ax.set_xticks([180,200,220])
        else:ax.set_xticks([80,85,90,95,100])
        if j==0:ax.set_ylabel('Heading error (deg)')
        # Compact explicit values for the independent tilt ablation, without hiding small gains.
        ax=axs[2,j]
        for i,(metric,lab) in enumerate([('roll_rmse_deg','Roll'),('pitch_rmse_deg','Pitch')]):
            vals=[]
            for m in ['A05','F04']:
                v=float(NAT[(NAT.sequence_id==seq)&(NAT.internal_method_id==m)][metric].iloc[0]);vals.append(v)
                rows.append({'sequence_id':seq,'method_id':m,'metric':metric,'rmse_deg':v})
            ax.plot(vals,[i,i],color='#BBBBBB',lw=1.3)
            ax.scatter(vals,[i,i],s=26,c=[PURPLE,BLUE],marker='o',zorder=3)
        ax.set(ylim=(-.6,1.6),xlim=(1.3,3.6),xlabel='Whole-window RMSE (deg)');ax.set_yticks([0,1],['Roll','Pitch']);ax.invert_yaxis()
        ax.set_xticks([1.5,2.5,3.5])
        title(ax,chr(103+j),'Tilt-aiding contribution')
    axs[2,1].legend(handles=[Line2D([],[],color=PURPLE,marker='o',lw=0,label='Tilt off'),Line2D([],[],color=BLUE,marker='o',lw=0,label='Full')],loc='lower right',fontsize=8,handlelength=.8)
    pd.DataFrame(rows).to_csv(OUT/'tables/F06_TILT_SUMMARY.csv',index=False)
    pd.DataFrame([{'sequence_id':s,'relative_start_s':w[0],'relative_end_s':w[1],'event_label':w[2]} for s,w in windows.items()]).to_csv(OUT/'tables/F06_EVENT_WINDOWS.csv',index=False)
    META['F06_heading_and_tilt']={'claim':'持续方向更新是自然记录中航向改善的主要来源；倾角观测对roll/pitch另有分量相关作用。','panels_zh':['a–c：三条自然记录的航向误差全时序，淡色区为下一排同一窗口。','d–f：同一时间窗的原始误差样本放大，无平滑；灰→橙检验持续航向，橙→蓝展示完整配置额外变化。','g–i：同窗之外的全记录roll/pitch RMSE，紫点关闭倾角、蓝点完整，连线仅连接同场景同指标。'],'limitation':'roll/pitch点图是独立的A05对F04消融；不能把F01对F04解释为纯航向单开关。','windows':windows}
    save(fig,'F06_heading_and_tilt')

def status(ax,fam):
    ax.set(xlim=(-4,32),ylim=(-.5,2.7));ax.axis('off')
    for i,label in enumerate(['Position','Heading','Body update']):
        y=2-i;active=(i>0 and fam=='A2')
        ax.plot([-4,32],[y,y],color='#53636C',lw=4,solid_capstyle='butt')
        if not active:ax.plot([0,20],[y,y],color='#DDD7CD',lw=4,solid_capstyle='butt')
        ax.text(-5,y,label,ha='right',va='center',fontsize=8)
    ax.text(10,2.55,'interruption',ha='center',fontsize=8,color='#555555')
    ax.axvline(0,color='#999',lw=.6);ax.axvline(20,color='#999',lw=.6)

def fig7():
    fig=plt.figure(figsize=(174/25.4,204/25.4));gs=fig.add_gridspec(4,2,height_ratios=[.34,.75,1.1,1.0],left=.17,right=.98,bottom=.085,top=.915,hspace=.63,wspace=.48)
    legend(fig,['A06','F04'],y=1.)
    stats=[];end=[]
    for col,fam in enumerate(['A1','A2']):
        sa=fig.add_subplot(gs[0,col]);status(sa,fam);sa.set_title('All GNSS interrupted' if fam=='A1' else 'Heading retained',loc='left',fontweight='bold',pad=17)
        rows=ADD[(ADD.case_family==fam)&(ADD.duration_s==20)&(ADD.seed_index=='seed_00')];t0=float(rows.outage_start_s.iloc[0]);ds={}
        for m in ['A06','F04']:
            rr=rows[rows.internal_method_id==m].iloc[0];d=series(rr.run_id);ds[m]=d
            b=d[(d.time>=t0)&(d.time<t0+20)].iloc[-1]
            end.append({'family':fam,'method_id':m,'run_id':rr.run_id,'last_before_restoration_time_s':float(b.time),'horizontal_error_m':float(b.horizontal_err_m),'yaw_error_deg':float(b.yaw_err_deg),'whole_window_horizontal_rmse_m':rr.horizontal_rmse_m})
        for row,field,yl in [(1,'yaw_err_deg','Heading error (deg)'),(2,'horizontal_err_m','Horizontal error (m)')]:
            ax=fig.add_subplot(gs[row,col]);
            for m,d in ds.items():
                t=d.time-t0;k=t.between(-4,32);curve(ax,t[k],d.loc[k,field],m,.9)
            ax.axvspan(0,20,color='#F3F0EA',zorder=-4);ax.axvline(20,color='#777',ls=':',lw=.7);ax.set(xlim=(-4,32),ylabel=yl)
            title(ax,chr(97+(row-1)*2+col),'Heading error' if row==1 else 'Position error and recovery')
            if row==1:ax.set_xticklabels([])
            else:
                ax.set_xlabel('Time from interruption start (s)');ax.set_xticks([0,10,20,30]);ax.text(20.3,.95,'restored',transform=ax.get_xaxis_transform(),fontsize=8,va='top')
                if col==1:
                    ins=ax.inset_axes([.11,.52,.40,.32]);d=ds['F04'];t=d.time-t0;k=t.between(0,20);curve(ins,t[k],d.loc[k,field],'F04',.9)
                    ins.set(xlim=(0,20),ylim=(0,2.5));ins.set_xticks([0,20]);ins.set_yticks([0,2]);ins.tick_params(labelsize=8,pad=1);ins.set_title('Full: same interval',fontsize=8,pad=2)
        ax=fig.add_subplot(gs[3,col]);dur=[10,20,30] if fam=='A1' else [10,20]
        for i,n in enumerate(dur):
            dd=ADD[(ADD.case_family==fam)&(ADD.duration_s==n)];a=dd[dd.internal_method_id=='F04'].set_index('seed_index').sort_index();b=dd[dd.internal_method_id=='A06'].set_index('seed_index').sort_index();assert len(a)==len(b)==9
            for j,k in enumerate(a.index):
                xx=[i-.13+(j-4)*.013,i+.13+(j-4)*.013];yy=[b.loc[k,'horizontal_rmse_m'],a.loc[k,'horizontal_rmse_m']]
                ax.plot(xx,yy,color='#C3C3C3',lw=.7);ax.scatter(xx,yy,c=[PURPLE,BLUE],s=17,zorder=3)
            stats.append({'condition':fam,'duration_s':n,'pairs':9,'without_HV_whole_window_median_m':b.horizontal_rmse_m.median(),'full_whole_window_median_m':a.horizontal_rmse_m.median()})
        ax.set_yscale('log');ax.set_ylim(.075,65);ax.set_yticks([.1,1,10],['0.1','1','10']);ax.set_xticks(range(len(dur)),[str(v) for v in dur]);ax.set_xlim(-.45,len(dur)-.55)
        ax.set(xlabel='Interruption duration (s)',ylabel='Whole-window H RMSE (m)');title(ax,chr(101+col),'Nine paired placements; log scale')
    pd.DataFrame(stats).to_csv(OUT/'tables/F07_ALL45_CASE_PAIRS_SUMMARY.csv',index=False);pd.DataFrame(end).to_csv(OUT/'tables/F07_REPRESENTATIVE_ENDPOINTS.csv',index=False)
    fig.text(.54,.018,'Status strips for full method: dark = available / updated; light = paused.',ha='center',fontsize=8)
    META['F07_heading_retained_translation']={'claim':'方向与辅助更新持续时，机身速度辅助显著限制平移漂移。','panels_zh':['最上方状态条：深色有效，浅色暂停；三行分别为位置观测、方向观测、机身辅助更新。','a–b：同一20秒中断的航向误差。','c–d：同一时间轴的水平误差；20秒恢复后的下降为观测校正，非真实轨迹凸起。','e–f：各时长全部九个布置的全窗RMSE，细线配对同一次布置；纵轴对数，不是中断末端误差。'],'limitation':'左右条件同时改变航向与辅助更新调度，不能解释为独立heading×HV因子实验。HV构造还继承冻结的历史A1方向。'}
    save(fig,'F07_heading_retained_translation')

def fig8():
    fig=plt.figure(figsize=(174/25.4,160/25.4));gs=fig.add_gridspec(3,2,height_ratios=[1.25,.9,.85],left=.115,right=.98,bottom=.085,top=.92,hspace=.60,wspace=.38)
    legend(fig,['A04','F04'],y=1.)
    pair=PAIR[(PAIR.module=='SA')&(PAIR.case_id=='D15_seed_00')].iloc[0];ds={'A04':series(pair.ablation_run_id),'F04':series(pair.candidate_run_id)}
    ax=fig.add_subplot(gs[0,:])
    for m,d in ds.items():curve(ax,d.time-66,d.yaw_err_deg,m,.8)
    zero(ax);ax.set(xlim=(0,274),ylabel='Heading error (deg)');ax.set_xticklabels([]);title(ax,'a','Same replay: heading error')
    ax.text(.97,.9,f'Whole-window RMSE: {pair.ablation_yaw_rmse_deg:.2f}° → {pair.candidate_yaw_rmse_deg:.2f}°',transform=ax.transAxes,ha='right',va='top',fontsize=8)
    ax=fig.add_subplot(gs[1,:]);tracepath=PREV/'D15_SOURCE_WEIGHT_TRACE_ALL.csv'
    tr=pd.read_csv(tracepath if tracepath.exists() else OUT/'data/F08_ACTUAL_R_TRACE.csv.gz')
    for key,col,ls,label in [('receiver_position','#444444','-','Position'),('dual_antenna_yaw',GREEN,':','Heading'),('go2_horizontal_velocity',PURPLE,'--','Body velocity')]:
        d=tr[tr.source_id==key];ax.plot(d.time-66,d.combined_R_scale,color=col,ls=ls,lw=.7,label=label,rasterized=True)
    ax.set(xlim=(0,274),ylim=(.6,10.8),xlabel='Time (s)',ylabel='Covariance multiplier');ax.set_xticks([0,50,100,150,200,250]);ax.set_yticks([1,5,10]);title(ax,'b','Actual source scaling')
    ax.legend(loc='lower right',bbox_to_anchor=(1,1.02),ncol=3,fontsize=8)
    ax=fig.add_subplot(gs[2,0]);labels=['Weighting off','Full'];v=[pair.ablation_horizontal_rmse_m,pair.candidate_horizontal_rmse_m]
    ax.plot(v,[0,1],color='#BBBBBB',lw=1.2);ax.scatter(v,[0,1],c=[PURPLE,BLUE],s=32,zorder=3)
    ax.set_yticks([0,1],['Off','Full']);ax.invert_yaxis();ax.set_ylim(1.4,-.4);ax.set_xlim(0,4.1);ax.set_xlabel('Horizontal RMSE (m)');title(ax,'c','Same replay: position cost')
    for i,vv in enumerate(v):ax.annotate(f'{vv:.2f}',(vv,i),xytext=(5,0),textcoords='offset points',va='center',fontsize=8)
    ax=fig.add_subplot(gs[2,1]);joint=PAIR[(PAIR.module=='SA')&PAIR.joint_finite];assert len(joint)==513
    gain=-joint.delta_yaw_rmse_deg.to_numpy();xx=np.sort(gain);yy=np.arange(1,len(xx)+1)/len(xx)*100
    ax.plot(xx,yy,color=BLUE,lw=1);ax.axvline(0,color='#AAA',lw=.7,ls=':');ax.set_xscale('symlog',linthresh=.02);ax.set_xticks([-1,0,1,100],['−1','0','1','100']);ax.minorticks_off()
    ax.set(ylim=(0,100),xlabel='Heading RMSE reduction (deg)',ylabel='Paired cases (%)');title(ax,'d','513 pairs; signed-log scale')
    ax.text(.97,.08,'Positive = full lower error',transform=ax.transAxes,ha='right',va='bottom',fontsize=8)
    fig.text(.54,.012,'Completed: 513 → 519 of 541 cases; all outcomes retained in the source tables.',ha='center',fontsize=8)
    joint.assign(heading_rmse_reduction_deg=-joint.delta_yaw_rmse_deg).to_csv(OUT/'tables/F08_ALL_513_PAIRS.csv',index=False)
    tr.to_csv(OUT/'data/F08_ACTUAL_R_TRACE.csv.gz',index=False,compression='gzip')
    META['F08_heading_quality_scaling']={'claim':'位置观测受扰时，来源协方差调整可维持较好的航向，但不保证同等位置改善。','panels_zh':['a：固定D15_seed_00代表例的航向误差，全部原始样本。','b：同次运行真实R倍率，同一时间轴；增大代表相对降低信任。','c：同次运行位置RMSE，保留代价但不与航向争夺主图面积。','d：513个双方均完成案例的yaw RMSE降低量累计分布，正值有利完整方法；有符号对数轴保留小变化和长尾。'],'case':'D15_seed_00','noise':'H sigma 3 m, V sigma 5 m; full-sequence source degradation','status':'541 full configurations: 519 complete, 13 divergence, 9 no heading; weighting off 513/19/9','limitation':'实际R与误差同轴便于关联，不凭形状推断尚未验证的唯一因果机制；新增完成6例不进入513配对CDF。'}
    save(fig,'F08_heading_quality_scaling')

def corrected_tables():
    d=DEFS.copy();inactive={'D29','D40','D55','D56'}
    def group(r):
        k=r.degradation_type_id
        if k=='CLEAN':return 'Clean reference'
        if k in inactive:return 'Unchanged estimator inputs'
        if k in ['D51','D52']:return 'Onboard tilt observations'
        if k in ['D53','D54']:return 'Body velocity observations'
        return {'dual_yaw':'Short-baseline heading','gnss_outage':'GNSS observation availability','gnss_sampling':'GNSS sampling','position_value':'Position values','position_std_status':'Position uncertainty','velocity_raw_doppler':'Velocity observations','multi_source_mixed':'Multiple observation sources'}[r.case_family]
    d['physical_input_group']=d.apply(group,axis=1);d['registered_active_measurement_path']=~d.degradation_type_id.isin(inactive|{'CLEAN'})
    d['physical_duplicate_of']=np.where(d.degradation_type_id=='D28','D25','');d['exposure_note']=''
    notes={'D29':'Metadata-only; formal solver values unchanged.','D40':'Baseline magnitude metadata has no active scalar-measurement path.','D55':'Contact/motion audit metadata only.','D56':'Foot-speed/contact audit metadata only.','D25':'Same realized physical parameters as D28; identities retained.','D28':'Same realized std x4 as D25; not independent mechanism.','D51':'RP dropout 50%; remaining roll/pitch sigma 3 deg; HV rotation source unchanged.','D52':'RP bias vector norm 2 deg, not 2 deg on each axis.','D53':'HV N/E noise sigma 1 m/s.','D54':'Seeds 00–03 scale x1.5; 04–07 dropout 50%; 08 both; retain branch.'}
    for k,v in notes.items():d.loc[d.degradation_type_id==k,'exposure_note']=v
    for k in ['D32','D33','D34','D35','D38']:d.loc[d.degradation_type_id==k,'exposure_note']='Realized angular disturbance extended over original 1-s cells; not independent 5-Hz noise.'
    d.to_csv(OUT/'tables/ALL61_PHYSICAL_INPUT_MAP.csv',index=False)
    merged=CORE.merge(d[['degradation_type_id','physical_input_group','registered_active_measurement_path','physical_duplicate_of','exposure_note']],on='degradation_type_id',how='left')
    assert len(merged)==5951
    merged.to_csv(OUT/'tables/ALL5951_RESULTS_WITH_INPUT_GROUPS.csv',index=False)
    CORE[CORE.evaluation_status!='COMPLETED'].to_csv(OUT/'tables/ALL_CORE_NONCOMPLETIONS.csv',index=False)
    PAIR.to_csv(OUT/'tables/ALL2164_ORIGINAL_ABLATION_PAIRS.csv',index=False)
    summaries=[]
    for (k,m),x in merged.groupby(['degradation_type_id','internal_method_id']):
        finite=x.yaw_rmse_deg.dropna()
        summaries.append({'degradation_type_id':k,'method_id':m,'registered':len(x),'completed':int((x.evaluation_status=='COMPLETED').sum()),'diverged':int((x.failure_classification=='ALGORITHM_FAILURE_DIVERGED').sum()),'no_heading':int(x.failure_classification.str.contains('HEADING').sum()),'conditional_yaw_rmse_median_deg':finite.median() if len(finite) else np.nan})
    pd.DataFrame(summaries).to_csv(OUT/'tables/ALL61x11_STATUS_AND_HEADING.csv',index=False)
    return d

def fig10():
    corrected_tables()
    fig=plt.figure(figsize=(174/25.4,156/25.4));gs=fig.add_gridspec(2,6,height_ratios=[1.05,1.25],left=.105,right=.985,bottom=.10,top=.88,wspace=.8,hspace=.64)
    legend(fig,['F01','F03','F04'],y=1.)
    fig.text(.55,.94,'Same recorded route; nine registered variants per nonzero condition',ha='center',fontsize=8)
    configs=[(['CLEAN','D30','D31'],[0,5,20],'Heading interruption (s)','Availability'),(['CLEAN','D32','D33'],[0,1,5],'Injected heading σ (deg)','Noise level'),(['CLEAN','D34','D35'],[0,5,10],'10° spike probability (%)','Outlier frequency')]
    rows=[]
    for j,(types,levels,xlab,ttl) in enumerate(configs):
        ax=fig.add_subplot(gs[0,2*j:2*j+2])
        for m in ['F01','F03','F04']:
            med=[]
            for k,x in zip(types,levels):
                dd=CORE[(CORE.degradation_type_id==k)&(CORE.internal_method_id==m)]
                assert (dd.evaluation_status=='COMPLETED').all()
                y=dd.yaw_rmse_deg.to_numpy();med.append(np.median(y))
                # Tiny deterministic horizontal offsets distinguish variants; physical levels remain ticks.
                off=np.linspace(-.025,.025,len(y))*(max(levels)-min(levels))
                ax.scatter(x+off,y,color=ST[m][0],s=10,alpha=.50,marker={'F01':'s','F03':'^','F04':'o'}[m],zorder=3)
                for _,r in dd.iterrows():rows.append({'panel':j,'physical_level':x,'degradation_type_id':k,'method_id':m,'run_id':r.run_id,'case_id':r.case_id,'heading_rmse_deg':r.yaw_rmse_deg})
            ax.plot(levels,med,color=ST[m][0],ls=ST[m][1],lw=1.1,marker={'F01':'s','F03':'^','F04':'o'}[m],ms=3.5)
        ax.set(xlabel=xlab,ylim=(0,9.3));ax.set_xticks(levels);ax.set_yticks([0,2,4,6,8]);title(ax,chr(97+j),ttl)
        if j==0:ax.set_ylabel('Whole-window yaw RMSE (deg)')
        else:ax.tick_params(labelleft=False)
    ax=fig.add_subplot(gs[1,:3]);case='D59_seed_00'
    for m in ['A04','F04']:
        r=runrow(case,m);d=series(r.run_id);curve(ax,d.time-66,d.yaw_err_deg,m,.8)
    zero(ax);ax.set(xlim=(0,274),xlabel='Time (s)',ylabel='Heading error (deg)');ax.set_xticks([0,100,200]);title(ax,'d','Position / velocity-source conflict')
    ax.legend(handles=[Line2D([],[],color=ST[m][0],ls=ST[m][1],label='Weighting off' if m=='A04' else 'Full') for m in ['A04','F04']],loc='upper right',fontsize=8)
    ax=fig.add_subplot(gs[1,3:]);dd=CORE[(CORE.degradation_type_id=='D59')&CORE.internal_method_id.isin(['A04','F04'])]
    for i,seed in enumerate(sorted(dd.seed_index.unique())):
        rr=dd[dd.seed_index==seed].set_index('internal_method_id');a=rr.loc['A04','yaw_rmse_deg'];b=rr.loc['F04','yaw_rmse_deg']
        if np.isfinite(a):
            ax.plot([i-.12,i+.12],[a,b],color='#BBBBBB',lw=.8)
            ax.scatter(i-.12,a,s=24,facecolor='white',edgecolor=PURPLE,zorder=4)
        ax.scatter(i+.12,b,s=32 if seed in ['seed_02','seed_04'] else 24,color=BLUE,alpha=1 if seed in ['seed_02','seed_04'] else .55,zorder=4)
        if seed in ['seed_02','seed_04']:ax.annotate(f'{b:.1f}°',(i+.12,b),xytext=(3,5),textcoords='offset points',fontsize=8,color=BLUE)
    ax.set(xlim=(-.6,8.6),ylim=(-5,170),xlabel='Registered variant',ylabel='Whole-window yaw RMSE (deg)');ax.set_xticks(range(9),[str(i+1) for i in range(9)]);title(ax,'e','All nine conflict variants')
    ax.text(.02,.98,'Full: 9/9 complete; off: 8/9',transform=ax.transAxes,ha='left',va='top',fontsize=8)
    pd.DataFrame(rows).to_csv(OUT/'tables/F10_ALL_DIRECTION_SENSITIVITY_CASES.csv',index=False)
    dd.to_csv(OUT/'tables/F10_ALL_NINE_CONFLICT_VARIANTS.csv',index=False)
    META['F10_heading_sensitivity']={'claim':'可用性与方向扰动改变时，持续方向约束的航向收益保持；多源冲突仍存在失败边界。','panels_zh':['a：零、5、20秒方向中断下全窗yaw RMSE；位置等其他源仍按登记条件运行。','b：原始1秒单元实现的方向噪声σ0/1/5度，逐seed点和中位线。','c：±10度尖峰的登记概率0/5/10%，同样保留全部九个variant；不是独立5Hz抽样。','d：跨源冲突D59_seed_00的完整航向误差时序，是该族唯一保留时序的配对。','e：全部九个冲突variant的原始yaw RMSE，线配对同一个variant；蓝点完整，空紫点关闭来源加权。特别标明第3、5例的55.8°、69.3°大误差，完成不等于准确；第5例关闭加权无数值，因为真实发散。'],'selection':'Physical levels use all registered D30–35 variants. D59_seed_00 is the only retained paired time history. All nine D59 original metrics are shown; unavailable released time histories are not regenerated.','limitation':'零扰动只有一条真实clean运行，未复制成九次；线连接物理递增强度的中位数，不是置信区间。D59边界无新的失效阈值推断。D51–54实际body先验单独配图；D29/D40/D55/D56没有正式输入变化，单列表格。'}
    save(fig,'F10_heading_sensitivity')

def support_body_quality():
    fig,axs=plt.subplots(1,2,figsize=(174/25.4,85/25.4));fig.subplots_adjust(left=.1,right=.98,bottom=.30,top=.77,wspace=.36)
    fig.text(.54,.945,'Actual changes to onboard tilt and body-velocity observations',ha='center',fontsize=9,fontweight='bold')
    ax=axs[0];source=[]
    for x,k in enumerate(['D51','D52']):
        dd=PAIR[(PAIR.degradation_type_id==k)&(PAIR.module=='RP')];assert len(dd)==9 and dd.joint_finite.all()
        for off,metric,col,mark in [(-.13,'roll_rmse_deg',BLUE,'o'),(.13,'pitch_rmse_deg',ORANGE,'^')]:
            y=dd['ablation_'+metric]-dd['candidate_'+metric];ax.scatter(x+off+np.linspace(-.06,.06,9),y,color=col,s=19,marker=mark)
            ax.plot([x+off-.08,x+off+.08],[y.median()]*2,color='#333',lw=1)
            source.extend({'case_id':r.case_id,'metric':metric,'group':k,'reduction':float(r['ablation_'+metric]-r['candidate_'+metric])} for _,r in dd.iterrows())
    zero(ax);ax.set_xticks([0,1],['Tilt dropout\n+ noise','Tilt bias\n2° vector']);ax.set_ylabel('RMSE reduction (deg)');ax.set_xlim(-.4,1.4);title(ax,'a','Tilt aiding')
    ax.legend(handles=[Line2D([],[],color=BLUE,marker='o',lw=0,label='Roll'),Line2D([],[],color=ORANGE,marker='^',lw=0,label='Pitch')],ncol=2,loc='lower right',bbox_to_anchor=(1,1.015),fontsize=8,handlelength=.8)
    ax=axs[1]
    dd=PAIR[(PAIR.degradation_type_id.isin(['D53','D54']))&(PAIR.module=='HV')]
    groups=[dd[dd.degradation_type_id=='D53'],dd[(dd.degradation_type_id=='D54')&dd.seed_index.isin([f'seed_{i:02d}' for i in range(4)])],dd[(dd.degradation_type_id=='D54')&dd.seed_index.isin([f'seed_{i:02d}' for i in range(4,8)])],dd[(dd.degradation_type_id=='D54')&(dd.seed_index=='seed_08')]]
    labels=['Noise\n1 m/s','Scale\n×1.5','Dropout\n50%','Both']
    for x,dd in enumerate(groups):
        y=(dd.ablation_horizontal_rmse_m-dd.candidate_horizontal_rmse_m)*1000
        ax.scatter(x+np.linspace(-.07,.07,len(dd)),y,color=BLUE,s=20);ax.plot([x-.12,x+.12],[y.median()]*2,color='#333',lw=1)
        source.extend({'case_id':r.case_id,'metric':'horizontal_rmse_m','group':labels[x].replace('\n',' '),'reduction':float(r.ablation_horizontal_rmse_m-r.candidate_horizontal_rmse_m)} for _,r in dd.iterrows())
    zero(ax);ax.set_xticks(range(4),labels);ax.set_ylabel('Horizontal RMSE reduction (mm)');ax.set_xlim(-.35,3.35);title(ax,'b','Body-velocity contribution')
    pd.DataFrame(source).to_csv(OUT/'tables/S_ACTUAL_BODY_QUALITY_PAIRS.csv',index=False)
    fig.text(.54,.055,'Positive: full lower error. Each point is a registered variant; short black lines are medians.',ha='center',fontsize=8)
    save(fig,'S_actual_body_observation_quality')

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--fig',default='all');args=ap.parse_args()
    for k,fn in [('6',fig6),('7',fig7),('8',fig8),('10',fig10),('body',support_body_quality)]:
        if args.fig in ('all',k):fn()
    for f in ['CORE5951.csv','ADD495.csv','NATURAL33.csv','REGISTERED_541_CASE_DEFINITIONS.csv','REGISTERED_61_TYPE_DEFINITIONS.csv','FULL_OUTCOME55.csv','CONFIGURATION_CONTRASTS.csv','SINGLEMODULE_CASE_PAIRS2164.csv']:
        if (PREV/f).exists() and (PREV/f).resolve()!=(OUT/'tables'/f).resolve():shutil.copy2(PREV/f,OUT/'tables'/f)
    AV.to_csv(OUT/'tables/ERROR_SERIES_AVAILABILITY6468.csv',index=False)
    (OUT/'SOURCE_SERIES.json').write_text(json.dumps(SOURCES,ensure_ascii=False,indent=2),encoding='utf8')
    (OUT/'FIGURE_READERS.json').write_text(json.dumps(META,ensure_ascii=False,indent=2),encoding='utf8')
    (OUT/'qa/DELIVERY.json').write_text(json.dumps({'scope':'frozen V3 saved results only','solver_calls':0,'provider_calls':0,'evaluator_calls':0,'figures':QA},ensure_ascii=False,indent=2),encoding='utf8')
if __name__=='__main__':main()
