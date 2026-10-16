"""Paper figures 3 and 9 from retained outputs only; no estimator/evaluator calls."""
from pathlib import Path
import sys,json,subprocess
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Rectangle
from matplotlib.ticker import MaxNLocator,ScalarFormatter,NullLocator
from PIL import Image

ROOT=Path('/mnt/g/LegSA-GINS-project')
OUT=Path(__file__).resolve().parent
OLD=ROOT/'V3论文组图_20261008/redesign_20261009/figures'
NAV=ROOT/'V3五问题论文组图_20261011/navigation/data'
FOCUS=ROOT/'V3论文组图_20261008/focused_20261011/comparison/data'
REPO=Path('/home/kaiwen/research/LegSA-GINS-WORKTREES/audit-code-xbpg-20261001')
POSE=REPO/'docs/paper_rebuild/GPSS_V3_FIGURES_20261008/redesign_20261009/data'
SCRIPTS=Path('/mnt/c/Users/ykw/.codex/skills/nature-figure/scripts')
sys.path.insert(0,str(SCRIPTS))
from audit_panel_alignment import require_matplotlib_panel_alignment
for x in ['data','preview','qa']:(OUT/x).mkdir(exist_ok=True)
SEQ=['BY2','BY2H','BY2O'];START={'BY2':66,'BY2H':413,'BY2O':3186};DUR={'BY2':274,'BY2H':270,'BY2O':377}
SCENE={'BY2':'Nominal walking','BY2H':'Large body motion','BY2O':'Antenna obstruction'}
COL={'F04':'#0072B2','LC01':'#D55E00','LC01-S':'#E69F00','EXT05C':'#8C510A','EXT05C-S':'#C08B3E','LC01-BR':'#A65F32','OISAM':'#009E73','WEN_TC':'#777777','GNC':'#AA4499','GINAV':'#777777'}
MARK={'BY2':'o','BY2H':'^','BY2O':'s'}
WIDTH=174/25.4
plt.rcParams.update({'font.family':'sans-serif','font.sans-serif':['Arial','Liberation Sans','DejaVu Sans'],'font.size':8,'axes.labelsize':8,'axes.titlesize':8.5,'xtick.labelsize':8,'ytick.labelsize':8,'legend.fontsize':8,'legend.frameon':False,'axes.spines.top':False,'axes.spines.right':False,'axes.linewidth':.6,'xtick.direction':'out','ytick.direction':'out','xtick.major.size':2.5,'ytick.major.size':2.5,'pdf.fonttype':42,'svg.fonttype':'none','path.simplify':False,'savefig.facecolor':'white'})
SOURCES=[];READOUT=[]
def read(path):
    path=Path(path);d=pd.read_csv(path);SOURCES.append(str(path));READOUT.append({'path':str(path),'rows':len(d),'columns':list(d),'missing':d.isna().sum().to_dict()});return d
def panel(ax,tag,title):
    ax.set_gid(tag);ax.set_title('('+tag+') '+title,loc='left',pad=8)
def line(ax,t,y,gap=.1,**kw):
    t=np.asarray(t);y=np.asarray(y)
    for ids in np.split(np.arange(len(t)),np.flatnonzero(np.diff(t)>gap)+1):
        if len(ids):ax.plot(t[ids],y[ids],**kw)
def xyline(ax,d,x,y,**kw):
    t=d.time_s.to_numpy()
    for ids in np.split(np.arange(len(t)),np.flatnonzero(np.diff(t)>.1)+1):
        if len(ids):ax.plot(d[x].to_numpy()[ids],d[y].to_numpy()[ids],**kw)
def tidy(ax):
    ax.xaxis.set_major_locator(MaxNLocator(3));ax.yaxis.set_major_locator(MaxNLocator(3))
    ax.tick_params(pad=2)
def export(fig,name,axes,notes,en,zh):
    fig.canvas.draw()
    require_matplotlib_panel_alignment(fig,axes=axes,json_out=OUT/'qa'/(name+'.alignment.json'),strict=True,tolerance_pt=1.5,gutter_tolerance_pt=1.5)
    fig.savefig(OUT/(name+'.pdf'),dpi=600)
    fig.savefig(OUT/(name+'.svg'),dpi=600)
    fig.savefig(OUT/(name+'.png'),dpi=600)
    fig.savefig(OUT/(name+'.tiff'),dpi=600)
    fig.savefig(OUT/(name+'.eps'),dpi=600)
    fig.savefig(OUT/'preview'/(name+'.png'),dpi=300)
    Image.open(OUT/'preview'/(name+'.png')).convert('L').save(OUT/'preview'/(name+'_gray.png'))
    audits={}
    for label,args in [('text',['audit_pdf_text.py',str(OUT/(name+'.pdf')),'--min-pt','8','--json']),('collision',['audit_figure_collisions.py',str(OUT/(name+'.pdf')),'--json-out',str(OUT/'qa'/(name+'.collisions.json'))])]:
        r=subprocess.run([sys.executable,str(SCRIPTS/args[0]),*args[1:]],text=True,capture_output=True)
        (OUT/'qa'/(name+'.'+label+'.log')).write_text(r.stdout+r.stderr);audits[label]=r.returncode
    meta={'id':name,'width_mm':174,'height_mm':round(fig.get_figheight()*25.4,1),'caption_en':en,'caption_zh':zh,'notes':notes,'sources':sorted(set(SOURCES)),'audits':audits,'new_solver_evaluator_provider_calls':0,'scientific_freeze':'7d43b9af26120ed5dde21f53e515386361072ba6','visual_review':'PENDING'}
    (OUT/(name+'.json')).write_text(json.dumps(meta,ensure_ascii=False,indent=2));plt.close(fig);print(name,audits,flush=True)

def fig3():
    fig,axs=plt.subplots(3,3,figsize=(WIDTH,182/25.4))
    fig.subplots_adjust(left=.095,right=.985,bottom=.075,top=.905,wspace=.52,hspace=.73)
    windows=[]
    for row,s in enumerate(SEQ):
        d=read(POSE/(s+'_display_pose.csv.gz'));t=d.time_s.to_numpy();elapsed=t-START[s]
        # Select by reference motion only, before inspecting estimator error.
        mid=START[s]+(204.945 if s=='BY2O' else DUR[s]/2)
        a=np.searchsorted(t,t-.5);b=np.clip(np.searchsorted(t,t+.5),0,len(d)-1)
        xy=d[['east_truth_m','north_truth_m']].to_numpy()
        speed=np.linalg.norm(xy[b]-xy[a],axis=1)/np.maximum(t[b]-t[a],1e-6)
        candidates=np.flatnonzero((np.abs(t-mid)<=15)&(speed>=.3))
        moving_selection=bool(len(candidates))
        if not moving_selection:candidates=np.flatnonzero(np.abs(t-mid)<=15)
        ci=candidates[np.argmin(np.abs(t[candidates]-mid))];centre=t[ci]
        spatial=d[d.time_s.between(centre-.1,centre+.1)].copy()
        lo,hi=centre-8,centre+8
        windows.append({'sequence':s,'target_centre_s':mid,'chosen_centre_s':centre,'elapsed_centre_s':centre-START[s],'reference_speed_mps':speed[ci],'spatial_window_s':[centre-.1,centre+.1],'error_window_s':[lo,hi],'selection':'Nearest reference-moving epoch to the predeclared centre' if moving_selection else 'No reference motion >=0.3 m/s in the 30-second neighbourhood; fixed centre retained as a stationary interval','selection_threshold_mps':.3,'no_estimator_error_used_in_selection':True,'spatial_epochs':len(spatial),'full_epochs':len(d)})
        # Full route with sparse actual body headings, all coordinates retained.
        ax=axs[row,0]
        for key,c,ls,lw in [('truth','#333333','--',1),('legsa',COL['F04'],'-',.75)]:xyline(ax,d,'east_'+key+'_m','north_'+key+'_m',color=c,ls=ls,lw=lw,rasterized=True)
        ix=np.searchsorted(t,np.arange(t[0]+15,t[-1],40));ix=ix[ix<len(d)]
        th=np.deg2rad(d.heading_legsa_ned_deg.to_numpy()[ix])
        ax.quiver(d.east_legsa_m.to_numpy()[ix],d.north_legsa_m.to_numpy()[ix],7*np.sin(th),7*np.cos(th),angles='xy',scale_units='xy',scale=1,color=COL['F04'],width=.006,zorder=5)
        ax.plot(d.east_truth_m.iloc[0],d.north_truth_m.iloc[0],marker='o',mfc='white',mec='#222222',ms=4,zorder=6)
        ax.scatter(d.east_truth_m.iloc[ci],d.north_truth_m.iloc[ci],s=75,facecolors='none',edgecolors='#AA4499',lw=1,zorder=6)
        ax.set(xlabel='East (m)',ylabel='North (m)');ax.set_aspect('equal',adjustable='datalim');tidy(ax)
        panel(ax,chr(97+3*row),SCENE[s])
        # A 0.2-second spatial detail in centimetres, relative to reference centre.
        ax=axs[row,1];e0,n0=xy[ci]
        for key,c,ls,lw in [('truth','#333333','--',1),('legsa',COL['F04'],'-',1)]:
            ss=spatial.copy();ss['e']=100*(ss['east_'+key+'_m']-e0);ss['n']=100*(ss['north_'+key+'_m']-n0);xyline(ax,ss,'e','n',color=c,ls=ls,lw=lw)
            ax.scatter(ss.e.iloc[0],ss.n.iloc[0],marker='o',s=11,facecolors='white',edgecolors=c,linewidths=.7,zorder=5)
        ax.set(xlabel='East offset (cm)',ylabel='North offset (cm)');ax.set_aspect('equal',adjustable='datalim');tidy(ax)
        panel(ax,chr(98+3*row),f'{centre-START[s]-.1:.1f}–{centre-START[s]+.1:.1f} s detail')
        # Same event on the native comparison clock; no reconstructed external path.
        ax=axs[row,2]
        for m,ls in [('LC01','--'),('LC01-S',':'),('F04','-')]:
            q=read(OLD/'data'/f'C01_{s}_{m}_saved_errors.csv.gz');z=q[q.elapsed_s.between(lo-START[s],hi-START[s])]
            line(ax,z.elapsed_s,100*z.horizontal_err_m,color=COL[m],ls=ls,lw=.75 if m!='F04' else 1,rasterized=True,zorder=3 if m=='F04' else 2)
        ax.axvspan(centre-START[s]-.1,centre-START[s]+.1,fc='#D9E6EF',lw=0,zorder=0)
        ax.set(xlabel='Elapsed time (s)',ylabel='Horizontal error (cm)',xlim=(lo-START[s],hi-START[s]),ylim=(0,None));tidy(ax)
        panel(ax,chr(99+3*row),'Local position error')
    handles=[Line2D([],[],color='#333333',ls='--',label='Reference'),Line2D([],[],color=COL['F04'],label='LegSA-GINS'),Line2D([],[],color=COL['LC01'],ls='--',label='Dual-position IEKF (LIT)'),Line2D([],[],color=COL['LC01-S'],ls=':',label='Dual-position IEKF (cal.)')]
    fig.legend(handles=handles,loc='upper center',bbox_to_anchor=(.52,.987),ncol=2,columnspacing=1.5,handlelength=2.7)
    pd.DataFrame(windows).to_csv(OUT/'data/F03_WINDOWS.csv',index=False)
    en='Recorded routes, local position detail and external-filter errors. Rows represent nominal walking, large body motion and antenna obstruction. Left: complete reference and LegSA-GINS paths; arrows show body heading and the purple ring locates the detail. Middle: a 0.2-second view in centimetres, referred to the reference position at its centre; circles denote its first epoch. Right: retained horizontal errors of LegSA-GINS and dual-position IEKFs over the same 16-second neighbourhood; shading denotes the middle-panel interval. The first two centres lie at the temporal midpoint during motion; the third lies at the midpoint of the first registered obstruction and is nearly stationary. Centre selection uses reference motion only; axes preserve equal spatial scale.'
    zh='三场景的完整路线、局部空间误差与外部滤波误差。左列保留参考与本文全部轨迹，箭头表示机身航向，紫圈定位中列路段；中列放大0.2秒轨迹，以中心时刻参考位置为原点、单位厘米，圆圈为该片段首时刻；右列在同一16秒邻域展示本文与双位置IEKF文献/标定参数的原始水平误差，浅带为中列区间。前两场景采用评价窗中点的运动时刻，第三场景采用首个登记遮挡中点、当时参考位置近乎静止。中心选择仅依据参考运动，空间轴保持等比例。'
    export(fig,'F03_route_local_comparison',list(axs.flat),{'windows':windows,'all_curve_points_retained':True,'arrow_length_meaning':'Graphical direction glyph; not speed','physical_point':'Reference and LegSA reconstructed at original POI; IEKF error series retains its frozen evaluator contract','new_accuracy_metrics':0},en,zh)

def fig9():
    natural=read(NAV/'LC_NATIVE_TABLE_READ.csv')
    for c in ['h_rmse_m','yaw_rmse_deg']:natural[c]=pd.to_numeric(natural[c],errors='coerce')
    rows=[]
    notes=json.loads((OLD/'data/C01_DATA_NOTES.json').read_text());SOURCES.append(str(OLD/'data/C01_DATA_NOTES.json'))
    for s in SEQ:
        q=[x for x in notes['rmse_saved_error_checks'] if x['sequence']==s and x['method']=='F04']
        rows.append({'sequence_id':s,'method_id':'F04','start_convention':'FORMAL','h_rmse_m':next(float(x['saved_rmse_token']) for x in q if x['metric']=='h_rmse_m'),'yaw_rmse_deg':next(float(x['saved_rmse_token']) for x in q if x['metric']=='yaw_rmse_deg'),'evaluation_status':'COMPLETED'})
    natural=pd.concat([pd.DataFrame(rows),natural],ignore_index=True)
    natural.to_csv(OUT/'data/F09_NATURAL_ALL19_ROWS.csv',index=False)
    common=read(NAV/'V3_OISAM_COMMON_POINT.csv');paired=read(NAV/'A2_ALL18_MATCHED_RESULTS.csv');fgo=read(NAV/'FGO_GNSS1_ALL36_RESULTS.csv');ginav=read(NAV/'GINAV_ACTUAL_RESULTS.csv')
    methods=['F04','LC01','LC01-S','EXT05C','EXT05C-S']
    labels=['LegSA-GINS','Dual-pos. LIT','Dual-pos. cal.','Single-pos. LIT','Single-pos. cal.']
    fig,axs=plt.subplots(3,2,figsize=(WIDTH,221/25.4))
    fig.subplots_adjust(left=.19,right=.98,bottom=.10,top=.91,wspace=.84,hspace=.68)
    for col,(metric,xlab,title) in enumerate([('h_rmse_m','Horizontal RMSE (cm)','Natural trials: positioning'),('yaw_rmse_deg','Heading RMSE (°)','Natural trials: heading')]):
        ax=axs[0,col]
        for i,m in enumerate(methods):
            for j,s in enumerate(SEQ):
                sub=natural[(natural.sequence_id==s)&(natural.method_id==m)]
                for _,r in sub.iterrows():
                    alt=s=='BY2H' and r.start_convention=='FILE_START'
                    if pd.notna(r[metric]):
                        x=r[metric]*(100 if metric=='h_rmse_m' else 1)
                        ax.scatter(x,i+(j-1)*.2,s=23,marker=MARK[s],facecolors='white' if alt else COL[m],edgecolors=COL[m],lw=.85,zorder=3)
                    # A failed run has no RMSE coordinate; report it in the shared
                    # text area below the two natural-trial panels.
            ax.axhline(i+.5,color='#EEEEEE',lw=.6,zorder=0)
        ax.set_yticks(range(len(methods)),labels);ax.set_ylim(4.6,-.6);ax.set_xlabel(xlab);ax.tick_params(axis='y',length=0,pad=5)
        if col==0:ax.set_xlim(0,22);ax.set_xticks([0,5,10,15,20])
        else:ax.set_xscale('log');ax.set_xlim(1,80);ax.set_xticks([1,3,10,30],['1','3','10','30']);ax.xaxis.set_minor_locator(NullLocator())
        panel(ax,chr(97+col),title)
    # Matched OiSAM/V3 precision with identical reference point and exact support.
    ax=axs[1,0];ratio_rows=[]
    labs=[];i=0
    for s in ['BY2','BY2O']:
        v=common[(common.sequence_id==s)&(common.method_id=='V3_F04')].iloc[0];o=common[(common.sequence_id==s)&(common.method_id=='OISAM')].iloc[0]
        for met,lab in [('horizontal_rmse_m','position'),('yaw_rmse_deg','heading')]:
            ratio=o[met]/v[met];ax.scatter(ratio,i,s=30,marker=MARK[s],color=COL['OISAM'],zorder=3);labs.append(('Nominal' if s=='BY2' else 'Obstruction')+'\n'+lab)
            ratio_rows.append({'sequence':s,'metric':met,'v3':v[met],'oisam':o[met],'oisam_over_v3':ratio,'matched_epochs':v.matched_epoch_count});i+=1
    ax.axvline(1,color=COL['F04'],lw=1);ax.set_yticks(range(4),labs);ax.tick_params(axis='y',length=0,pad=5);ax.set(ylim=(3.6,-.6),xlim=(.5,3),xlabel='RMSE ratio (OiSAM / LegSA-GINS)');ax.set_xticks([.5,1,2,3]);panel(ax,'c','OiSAM: matched-point accuracy')
    pd.DataFrame(ratio_rows).to_csv(OUT/'data/F09_OISAM_COMMON_PRECISION.csv',index=False)
    # Native position solution coverage: preserve registered 1-Hz supports.
    ax=axs[1,1];coverage=[]
    cov_methods=[('F04','LegSA-GINS'),('OISAM_STRICT','OiSAM: single init.'),('OISAM_RESTART','OiSAM: restart'),('GINAV','GINav SPP/INS')]
    for i,(m,label) in enumerate(cov_methods):
        for j,s in enumerate(SEQ):
            den=DUR[s]+1
            if m=='F04':n=len(read(FOCUS/(s+'_V3_POI_nominal.csv.gz')));color=COL['F04'];state='matched to nominal seconds within 5 ms'
            elif m=='OISAM_STRICT':n=int(common[(common.sequence_id==s)&(common.method_id=='OISAM')].iloc[0].own_finite_epoch_count);color=COL['OISAM'];state='strict finite own states'
            elif m=='OISAM_RESTART':n=int(fgo[(fgo.sequence_id==s)&(fgo.method_id=='OISAM')&(fgo.support=='OWN_VALID')&(fgo.support_role=='PRIMARY_DYNAMIC_ONLY')].iloc[0].matched_epoch_count);color=COL['OISAM'];state='dynamic own states after recorded-gap restarts'
            else:n=int(ginav[ginav.sequence==s].iloc[0].output_count);color=COL['GINAV'];state=ginav[ginav.sequence==s].iloc[0].status
            pct=100*n/den;ax.scatter(pct,i+(j-1)*.19,s=24,marker=MARK[s],facecolors=color if m!='OISAM_RESTART' else 'white',edgecolors=color,lw=.9)
            coverage.append({'sequence':s,'method':m,'count':n,'denominator':den,'percentage':pct,'definition':state})
        ax.axhline(i+.5,color='#EEEEEE',lw=.6,zorder=0)
    ax.set_yticks(range(4),[x[1] for x in cov_methods]);ax.tick_params(axis='y',length=0,pad=5);ax.set(ylim=(3.6,-.6),xlim=(-4,104),xlabel='Output epochs / nominal slots (%)');ax.set_xticks([0,50,100]);panel(ax,'d','Full-window output availability')
    pd.DataFrame(coverage).to_csv(OUT/'data/F09_OUTPUT_COVERAGE.csv',index=False)
    # The baseline-retaining method exists in the controlled 18-case experiment.
    ax=axs[2,0];a2m=['F04','LC01','EXT05C','LC01-BR'];a2l=['LegSA-GINS','Dual-pos. IEKF','Single-pos. IEKF','Baseline-retaining']
    for i,m in enumerate(a2m):
        for j,dur in enumerate([10,20]):
            vals=paired[paired.duration_s==dur][m+'_horizontal_rmse_m'].to_numpy();ys=i+(j-.5)*.23+np.linspace(-.035,.035,len(vals))
            ax.scatter(vals,ys,s=17,marker='o' if dur==10 else 's',facecolors='white' if dur==10 else COL[m],edgecolors=COL[m],lw=.6,zorder=3)
        ax.axhline(i+.5,color='#EEEEEE',lw=.6,zorder=0)
    ax.set_yticks(range(4),a2l);ax.tick_params(axis='y',length=0,pad=5);ax.set_ylim(3.6,-.6);ax.set_xscale('log');ax.set_xlim(.04,12);ax.set_xticks([.1,1,10],['0.1','1','10']);ax.xaxis.set_minor_locator(NullLocator());ax.set_xlabel('Whole-run horizontal RMSE (m)');panel(ax,'e','Position interruption: all 18 cases')
    fig.legend(handles=[Line2D([],[],marker='o',color='#555555',mfc='white',ls='None',label='10 s interruption'),Line2D([],[],marker='s',color='#555555',ls='None',label='20 s interruption')],loc='lower left',bbox_to_anchor=(.18,.005),ncol=2,columnspacing=1.1,handletextpad=.3)
    # Different information layers remain visibly separated and use the same GNSS1 point.
    ax=axs[2,1];fm=['OISAM','WEN_TC','GNC'];fl=['OiSAM restart\nRTK + IMU','TC-FGO\nCode + IMU','GNC-FGO\nCode + Doppler']
    fs=fgo[(fgo.support=='OWN_VALID')&(fgo.support_role=='PRIMARY_DYNAMIC_ONLY')]
    for i,m in enumerate(fm):
        for j,s in enumerate(SEQ):
            val=fs[(fs.sequence_id==s)&(fs.method_id==m)].iloc[0].horizontal_rmse_m
            ax.scatter(val,i+(j-1)*.18,s=25,marker=MARK[s],color=COL[m],zorder=3)
        ax.axhline(i+.5,color='#EEEEEE',lw=.6,zorder=0)
    ax.set_yticks(range(3),fl);ax.tick_params(axis='y',length=0,pad=5);ax.set_ylim(2.6,-.6);ax.set_xscale('log');ax.set_xlim(.025,15);ax.set_xticks([.03,.1,1,10],['0.03','0.1','1','10']);ax.xaxis.set_minor_locator(NullLocator());ax.set_xlabel('Horizontal RMSE at GNSS1 (m)');panel(ax,'f','FGO inputs: own valid outputs')
    fig.legend(handles=[Line2D([],[],marker=MARK[s],color='#555555',ls='None',label=SCENE[s],markersize=4) for s in SEQ],loc='upper center',bbox_to_anchor=(.55,.986),ncol=3,columnspacing=.85,handletextpad=.45)
    fig.text(.19,.945,'Natural trials: filled = primary start; open = alternate start',fontsize=8)
    fig.text(.19,.646,'Failed run: single-pos. IEKF (cal.); large body motion; file start',fontsize=8,color=COL['EXT05C'])
    en='Navigation comparisons with explicitly separated input and output conditions. (a,b) Natural-trial position and heading errors for LegSA-GINS and all four dual/single-position IEKF parameter identities. For large body motion, filled triangles use the registered contract start and open triangles retain file-start sensitivity runs. The failed calibrated single-position file-start run is identified in the text area below the panels and has no assigned RMSE coordinate. (c) OiSAM-to-LegSA-GINS RMSE ratios on identical midpoint and nominal-time supports (274 nominal and 54 initial obstruction epochs; no common dynamic output in large body motion). (d) Native position-output availability on the registered one-hertz slots; output availability does not imply accuracy, and GINav outputs remain visible where the speed gate fails. (e) All 18 registered position-interruption cases, including the baseline-retaining IEKF; circles and squares denote 10 and 20 seconds. (f) FGO positioning at GNSS1 on each method\'s own valid dynamic outputs, with the input layer stated beside each method; these supports and the physical point differ from the common midpoint comparison in (c). Raw-code methods and solution-level methods are not pooled into one ranking.'
    zh='导航系统横向比较，分开显示输入与输出条件。（a,b）本文及双/单位置IEKF两种参数的全部自然场景结果；大幅运动的实心三角为登记起点，空心三角保留文件起点敏感性结果。标定单位置IEKF的文件起点失败运行在两面板下方单独说明，不给它赋予RMSE坐标。（c）OiSAM与本文在同一中点、同一名义时刻上的RMSE比值：常规274对，遮挡初段54对，大幅运动无共同动态输出。（d）登记一赫兹时刻的输出可用性；有输出不等同于准确，GINav速度检查失败的输出数量也保留。（e）全部18个位置中断条件，纳入保留基线IEKF；圆/方分别为10/20秒。（f）各FGO路线在GNSS1天线点、各自有效动态输出上的水平RMSE；其物理点和支持范围与(c)共同中点比较不同，标签明确输入层。原始码与解级路线不混成一个总排名。'
    export(fig,'F09_navigation_all_families',list(axs.flat),{'natural_rows':len(natural),'natural_failures':int(natural.h_rmse_m.isna().sum()),'geometry_exception':'All four BY2H dual-position IEKF natural start/parameter rows retain AVAILABLE_GEOMETRIC_AUDIT_FAIL','OiSAM_common':{'BY2':274,'BY2H':0,'BY2O':54},'coverage_definition':'Saved position epochs over registered nominal one-second slots. V3 applies original 5ms nominal gate; OiSAM/GINav native one-Hz states. IEKF high-rate own coverage remains in companion table, not inferred comparable 1Hz slots.','ginav_accuracy':'BY2 and BY2O speed-gate failure => NA; BY2H only two outputs, H=2.894928 and yaw=11.662263; full values retained in source table','all_degradation_cases_figure':'Controlled interruption results in panel e; the full 396 logical degradation rows and all 744 paired summaries remain in source tables','selected_primary_and_alternate_starts':'BY2/BY2O FILE_START; BY2H CONTRACT_START primary and FILE_START alternative; none removed','no_cross_point_position_overlay':True},en,zh)
    ginav.to_csv(OUT/'data/F09_GINAV_ALL_RESULTS.csv',index=False);fgo.to_csv(OUT/'data/F09_FGO_ALL36_ROWS.csv',index=False);paired.to_csv(OUT/'data/F09_INTERRUPTION_ALL18.csv',index=False)

if __name__=='__main__':
    for name in sys.argv[1:] or ['3','9']:{'3':fig3,'9':fig9}[name]()
    old=json.loads((OUT/'SOURCE_READOUT.json').read_text()) if (OUT/'SOURCE_READOUT.json').exists() else []
    reads={x['path']:x for x in old+READOUT}
    (OUT/'SOURCE_READOUT.json').write_text(json.dumps(list(reads.values()),ensure_ascii=False,indent=2))
    (OUT/'SOURCE_PATHS.json').write_text(json.dumps(sorted(set(SOURCES)|set(reads)),ensure_ascii=False,indent=2))
