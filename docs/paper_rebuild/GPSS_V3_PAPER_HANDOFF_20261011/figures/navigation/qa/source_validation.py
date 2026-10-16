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

from pathlib import Path
import json, numpy as np, pandas as pd
from matplotlib.lines import Line2D
from paper_style import setup,plt,MM,line,tidy,panel,export
OUT=Path(__file__).resolve().parent;DATA=OUT/'data'
COL={'F04':'#0072B2','LC01':'#D55E00','EXT05C':'#009E73','LC01-BR':'#CC79A7'}
LS={'F04':'-','LC01':'--','EXT05C':'-.','LC01-BR':':'}
NAME={'F04':'LegSA-GINS','LC01':'Dual-position IEKF','EXT05C':'Single-position IEKF','LC01-BR':'Baseline-retaining IEKF'}
def save(fig,name,en,zh,meaning,src,axs,notes):
    return export(fig,OUT,name,caption_en=en,caption_zh=zh,meaning_zh=meaning,sources=src,axes=list(axs.flat),technical_notes=notes)

def a2():
    fig,ax=plt.subplots(2,2,figsize=(174*MM,150*MM));fig.subplots_adjust(left=.10,right=.98,bottom=.105,top=.84,wspace=.32,hspace=.54)
    sources=[]
    for m in NAME:
        p=DATA/(m+'_A2_20s_seed00.csv.gz');d=pd.read_csv(p);sources.append(p);use=d[(d.time>=191.2)&(d.time<=231.2)]
        for j,k in enumerate(['horizontal_err_m','yaw_err_deg']):line(ax[0,j],use.time-196.2,use[k],gap=.101,color=COL[m],ls=LS[m],lw=1.05)
    for j in range(2):
        ax[0,j].axvspan(0,20,color='#E6E6E6',zorder=0);ax[0,j].set(xlim=(-5,35),xlabel='Time from interruption start (s)');tidy(ax[0,j],4,4)
    ax[0,0].set_ylabel('Horizontal error (m)');ax[0,1].set_ylabel('Heading error (°)');ax[0,1].axhline(0,color='#888888',lw=.5)
    inset=ax[0,0].inset_axes([.08,.54,.39,.37])
    for m in NAME:
        d=pd.read_csv(DATA/(m+'_A2_20s_seed00.csv.gz'));q=d[d.time.between(196.2,204.2)]
        line(inset,q.time-196.2,q.horizontal_err_m,gap=.101,color=COL[m],ls=LS[m],lw=.8)
    inset.set(xlim=(0,8),ylim=(-.05,10));inset.set_xticks([0,4,8]);inset.set_yticks([3,6,9]);inset.tick_params(labelsize=6.5,pad=1.5);inset.set_title('First 8 s',fontsize=7,pad=2)
    panel(ax[0,0],'a','20-s position interruption');panel(ax[0,1],'b','Heading during the same event')
    t=pd.read_csv(DATA/'DEGRADATION_EXTERNAL_TABLE_R2.csv');f=pd.read_csv(DATA/'A2_F04_existing.csv');rows=[]
    for dur in [10,20]:
        for seed in [f'seed_{i:02d}' for i in range(9)]:
            rr={'duration_s':dur,'seed':seed}
            for m in NAME:
                r=f[(f.duration_s==dur)&(f.seed_index==seed)].iloc[0] if m=='F04' else t[(t.method==m)&(t.case_id==f'D62_{dur}s_{seed}')].iloc[0]
                for metric in ['horizontal_rmse_m','yaw_rmse_deg']:rr[m+'_'+metric]=r[metric]
            rows.append(rr)
    pairs=pd.DataFrame(rows);pairs.to_csv(DATA/'A2_ALL18_MATCHED_RESULTS.csv',index=False)
    for j,k in enumerate(['horizontal_rmse_m','yaw_rmse_deg']):
        for base,dur in enumerate([10,20]):
            q=pairs[pairs.duration_s==dur];xs=np.array([base*1.4-.36,base*1.4-.12,base*1.4+.12,base*1.4+.36])
            for i,(_,r) in enumerate(q.iterrows()):
                off=(i-4)*.007
                ax[1,j].plot(xs+off,[r[m+'_'+k] for m in NAME],color='#CCCCCC',lw=.45,zorder=1)
                for z,m in enumerate(NAME):ax[1,j].scatter(xs[z]+off,r[m+'_'+k],s=15,marker=['o','s','^','D'][z],color=COL[m],edgecolors='white',linewidth=.2,zorder=3)
        ax[1,j].set(xlim=(-.65,2.05),xlabel='Interruption duration (s)');ax[1,j].set_xticks([0,1.4],['10','20']);ax[1,j].set_yscale('log');ax[1,j].set_ylabel('Whole-run '+('horizontal RMSE (m)' if j==0 else 'heading RMSE (°)'))
    panel(ax[1,0],'c','All nine placements per duration');panel(ax[1,1],'d','All nine placements per duration')
    ax[1,1].set_yticks([2,3,5,10,20,50],['2','3','5','10','20','50']);ax[1,1].set_ylim(1.6,60)
    handles=[Line2D([],[],color=COL[m],ls=LS[m],marker=['o','s','^','D'][i],markersize=3,label=NAME[m],lw=1.2) for i,m in enumerate(NAME)]
    fig.legend(handles=handles,loc='upper center',bbox_to_anchor=(.55,.988),ncol=2,handlelength=2.6,columnspacing=1.1)
    en='Navigation during GNSS position interruptions. (a,b) Horizontal and heading errors for the first registered 20-s interruption; gray shading marks the interrupted interval, and the inset enlarges its first 8 s. The dual- and single-position IEKFs omit their position updates, while the baseline-retaining IEKF continues relative-baseline updates. LegSA-GINS retains its available heading and robot-motion aids. (c,d) Whole-run RMSE for every registered 10-s and 20-s interruption, with nine placements per duration; thin lines connect the same placement across methods. The baseline-retaining IEKF preserves heading but does not automatically improve positioning. Logarithmic scales retain all finite outcomes.'
    zh='GNSS位置中断时的导航结果。（a,b）首个登记20秒中断的位置和航向误差，灰带表示中断区间，小窗放大中断后的前8秒；双位置和单位置IEKF停止位置更新，保留基线的IEKF继续进行相对基线更新，LegSA-GINS保留可用航向及机身运动辅助。（c,d）全部10秒和20秒中断的整段RMSE，每个时长九个布置；细线连接同一布置的四种方法。保留基线的IEKF维持了航向，但没有自动改善位置结果。对数坐标保留全部有限结果。'
    save(fig,'Q3_02_heading_retention',en,zh,'上排显示位置中断中误差如何增长，下排说明这一现象在全部18个登记条件中的分布。',sources+[DATA/'A2_ALL18_MATCHED_RESULTS.csv'],ax,{'example_case':'D62_20s_seed_00','time_origin_s':196.2,'display_window_s':[-5,35],'selection':'First registered case, fixed input interruption and 5s-before/15s-after window','paired_cases':18,'native_finite_per_method':18,'all_rows_drawn':True,'systems_have_different_auxiliary_inputs':True,'new_solver_evaluator_provider_calls':0})

def segmented():
    fig,ax=plt.subplots(3,2,figsize=(174*MM,178*MM));fig.subplots_adjust(left=.105,right=.98,bottom=.08,top=.89,wspace=.31,hspace=.55)
    sources=[]
    for i,(s,n,zoom) in enumerate([('BY2','Nominal walking',(127,147)),('BY2H','Large body motion',(0,18)),('BY2O','Antenna obstruction',(52,72))]):
        p=DATA/(s+'_COMMON_SEGMENTED_HEADING.csv.gz');d=pd.read_csv(p);sources.append(p)
        for j in range(2):
            q=d if j==0 else d[d.elapsed_s.between(*zoom)]
            for k,c,ls in [('v3_yaw_err_deg','#0072B2','-'),('oisam_yaw_err_deg','#D55E00','--')]:line(ax[i,j],q.elapsed_s,q[k],gap=1.001,color=c,ls=ls,lw=1.)
            ax[i,j].axhline(0,color='#888888',lw=.5);ax[i,j].set_xlabel('Elapsed time (s)');ax[i,j].set_ylabel('Heading error (°)');tidy(ax[i,j],4,4)
        ax[i,0].axvspan(*zoom,color='#E6E6E6',zorder=0);ax[i,0].set_xlim(0,377 if s=='BY2O' else (270 if s=='BY2H' else 274));ax[i,1].set_xlim(*zoom)
        if s!='BY2':
            gaps=pd.read_csv(DATA/'GAPS.csv');gaps=gaps[(gaps.sequence==s)&(gaps.method=='SOURCE_IMU')]
            origin=413 if s=='BY2H' else 3186
            for _,g in gaps.iterrows():
                if g.right_s-origin>=zoom[0] and g.left_s-origin<=zoom[1]:ax[i,1].axvspan(max(zoom[0],g.left_s-origin),min(zoom[1],g.right_s-origin),color='#D5D5D5',zorder=0)
        panel(ax[i,0],chr(97+i*2),n);panel(ax[i,1],chr(98+i*2),'Central interval' if s=='BY2' else 'First in-window restart')
    fig.legend(handles=[Line2D([],[],color='#0072B2',lw=1.2,label='LegSA-GINS'),Line2D([],[],color='#D55E00',ls='--',lw=1.2,label='OiSAM-FGO (reinitialized)')],loc='upper center',bbox_to_anchor=(.55,.98),ncol=2)
    en='Heading errors with OiSAM reinitialized at recorded IMU gaps. Left panels show all matched dynamic-output epochs throughout the three trials. Right panels enlarge a fixed central interval for nominal walking and the first restart inside the other two evaluation windows. Light shading in the left panels identifies the enlarged interval; darker shading in the right panels marks the recorded IMU gap. Initialization-only states are excluded, and curves break across unavailable dynamic outputs. Both methods use the same nominal evaluation seconds and the same heading convention. These heading comparisons do not mix the different position reference points used in the archived evaluations.'
    zh='OiSAM在实测IMU缺口处重新初始化后的航向误差。左列展示三条记录全部匹配动态输出历元，右列分别放大常规行走的固定中间时段，以及另外两条记录评价窗内的首次恢复过程。左图浅色带表示放大区间，右图深灰带表示实测IMU缺口。仅初始化状态不进入曲线，动态输出缺失处断线。两方法使用相同名义评价秒及一致航向定义；本图不混用原评价中不同的位置参考点。'
    save(fig,'Q3_03_OiSAM_reinitialized_heading',en,zh,'在允许按真实输入缺口重新初始化后，比较两方法整段航向，而非只用OiSAM一次初始化后的早停描述它。',sources+[DATA/'GAPS.csv'],ax,{'heading':'wrapped estimated NED body yaw minus reference NED body yaw; already evaluated','matched_dynamic_counts':{s:len(pd.read_csv(DATA/(s+'_COMMON_SEGMENTED_HEADING.csv.gz'))) for s in ['BY2','BY2H','BY2O']},'position_metrics_not_plotted':True,'protocol':'OiSAM predeclared IMU blocks, one initialization per block, not failure-triggered restart','zoom_selection':'Nominal centered interval; H/O first actual in-window input restart','new_solver_evaluator_provider_calls':0})

def classic():
    p=pd.read_csv(DATA/'DEGRADATION_PAIRED_R2.csv');t=pd.read_csv(DATA/'DEGRADATION_EXTERNAL_TABLE_R2.csv')
    types=['D14','D21','D16','D18','D03','D04','D43','D42','D05','D33','D35','D32','D31','D06','D46','D47','D50','D57']
    labels=['Position noise I','Position noise II','Position bias I','Position bias II','Position outage I','Position outage II','Velocity noise','Velocity outage I','Velocity outage II','Heading noise I','Heading noise II','Heading noise III','Heading outage I','Heading outage II','Doppler I','Doppler II','Doppler III','Timestamp shift']
    fig,ax=plt.subplots(1,2,figsize=(174*MM,174*MM));fig.subplots_adjust(left=.30,right=.985,bottom=.11,top=.91,wspace=.18)
    for j,(metric,title,unit) in enumerate([('horizontal_rmse_m','Horizontal positioning','m'),('yaw_rmse_deg','Heading','°')]):
        a=ax[j];a.axvline(0,color='#777777',lw=.65)
        for i,ty in enumerate(types):
            for mi,m in enumerate(['LC01','EXT05C']):
                r=p[(p.level=='type')&(p.group==ty)&(p.method==m)&(p.metric==metric)&(p.reference_method=='F04')].iloc[0];y=i+(mi-.5)*.22
                if r.paired_n:
                    a.plot([r.difference_median,r.difference_p95],[y,y],color=COL[m],lw=.8)
                    a.scatter(r.difference_median,y,color=COL[m],marker='o' if mi==0 else 's',s=19,zorder=3)
                    a.scatter(r.difference_p95,y,facecolors='white',edgecolors=COL[m],marker='o' if mi==0 else 's',s=13,zorder=3)
            if ty in ['D14','D21','D57']:a.text(.96,i,'9/9 diverged' if ty!='D57' else 'No common pairs',transform=a.get_yaxis_transform(),ha='right',va='center',fontsize=7.2,color='#666666')
        a.set_ylim(len(types)-.5,-.7);a.set_yticks(range(len(types)),labels if j==0 else ['']*len(types));a.tick_params(axis='y',length=0,pad=6);a.set_xscale('symlog',linthresh=.02);a.set_xlabel('IEKF − LegSA-GINS RMSE ('+unit+')');panel(a,chr(97+j),title)
        a.set_xticks([0,.1,1,10] if j==1 else [-10,-1,0,1,10]);a.set_xticklabels(['0','0.1','1','10'] if j==1 else ['−10','−1','0','1','10'],fontsize=7.5);a.set_xlim((-.03,40) if j==1 else (-15,15))
        for pos in [1.5,3.5,5.5,8.5,11.5,13.5,16.5]:a.axhline(pos,color='#E8E8E8',lw=.5)
    fig.legend(handles=[Line2D([],[],color=COL[m],marker='o' if m=='LC01' else 's',lw=.8,label=NAME[m]) for m in ['LC01','EXT05C']],loc='upper center',bbox_to_anchor=(.58,.98),ncol=2)
    mapping=pd.DataFrame({'type':types,'figure_label':labels});mapping.to_csv(DATA/'CLASSIC18_LABEL_MAP.csv',index=False)
    en='Paired RMSE differences across all 18 registered degradation types. Filled markers denote the median external-IEKF minus LegSA-GINS difference over jointly finite cases; open markers denote the 95th percentile, with connecting lines showing the median-to-percentile interval. Each type contains nine registered cases. Negative values favour the IEKF. Both IEKFs diverge in all nine cases for each position-noise type; timestamp-shift cases have no valid common pairs. The symmetric-log axis retains small differences and large excursions. Some velocity, Doppler and heading faults act on channels not read by an external filter; these are input-equivalence controls rather than independent robustness demonstrations. Full type definitions, all 396 logical results and all 744 paired summaries accompany the figure.'
    zh='全部18种登记退化类型的配对RMSE差。实心点为共同有限样本中“外部IEKF减LegSA-GINS”的中位数，空心点为95百分位，连线表示二者之间的区间；每种退化登记九个案例。负值表示IEKF误差较低。两种位置噪声下，两种IEKF均各9/9发散；时间戳扰动无有效共同配对。对称对数轴同时保留小差值和大偏离。部分速度、多普勒及航向故障作用于外部滤波器未读取的通道，属于输入等价控制。完整类型定义、396条逻辑结果和744条配对汇总随图交付。'
    save(fig,'Q3_04_all_degradation_pairs',en,zh,'这张补充图保留所有故障类别和反例；它逐类比较，不把异质故障混成一个总排名。',[DATA/'DEGRADATION_PAIRED_R2.csv',DATA/'DEGRADATION_EXTERNAL_TABLE_R2.csv',DATA/'CLASSIC18_LABEL_MAP.csv'],ax,{'cases_per_type':9,'types':18,'pairs_source_rows':len(p),'logical_result_rows':len(t),'interval':'median to p95, not confidence interval','sign':'external minus F04','aliases':'A1 aliases and A2 support are separately retained in full data and Q3_02','no_op_types':['D43','D42','D46','D47','D50'],'new_solver_evaluator_provider_calls':0})

if __name__=='__main__':
    import sys
    setup()
    calls={'a2':a2,'segmented':segmented,'classic':classic}
    for k in sys.argv[1:] or calls: calls[k]()
