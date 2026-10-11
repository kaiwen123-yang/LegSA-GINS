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

"""Relative-motion comparisons from the nine completed aligned error records."""
from pathlib import Path
import sys,json
import numpy as np,pandas as pd
from matplotlib.lines import Line2D

REPO=Path('/home/kaiwen/research/LegSA-GINS-WORKTREES/audit-code-xbpg-20261001')
sys.path.insert(0,str(REPO/'docs/paper_rebuild/GPSS_V3_FIGURES_20261008/redesign_20261009'))
from paper_style import setup,panel,export,plt,MM
OUT=Path(__file__).resolve().parent
DATA=OUT/'data';DATA.mkdir(exist_ok=True)
setup()
SEQS=['BY2','BY2H','BY2O'];START={'BY2':66.,'BY2H':413.,'BY2O':3186.};DURATION={'BY2':274.,'BY2H':270.,'BY2O':377.}
METHODS=['OFF-LIT','OFF-DEF','LEG-DR']
NAME={'OFF-LIT':'InEKF (literature)','OFF-DEF':'InEKF (example)','LEG-DR':'Kinematic integration'}
COLOR={'OFF-LIT':'#AA4499','OFF-DEF':'#777777','LEG-DR':'#009E73'}
STYLE={'OFF-LIT':'-','OFF-DEF':'--','LEG-DR':'-.'}

def main():
    frames={};sources=[];metrics=[];profile=[]
    for s in SEQS:
        start={'BY2':'C00','BY2H':'CONTRACT_START','BY2O':'FILE_START'}[s]
        for m in METHODS:
            if m=='LEG-DR':folder=REPO/'docs/paper_rebuild/hext/HX05/LEG_DR'/s/'eval/OUTPUT'
            else:folder=REPO/'docs/paper_rebuild/hext/HX02E/RUNS'/f'{s}__HARTLEY_OFFICIAL__{m}__{start}'/'eval/OUTPUT'
            source=folder/f'RELATIVE_POSE_ERROR_SERIES_{m}.csv';sources.append(source)
            d=pd.read_csv(source);d['elapsed_s']=d.t_rel_s-START[s];frames[s,m]=d
            assert d.t_rel_s.is_monotonic_increasing and np.isfinite(d[['horizontal_err_m','yaw_err_deg']]).all().all()
            d.to_csv(DATA/f'{s}_{m}_relative_errors.csv.gz',index=False)
            p=folder/'RELATIVE_POSE_METRICS.json';v=json.loads(p.read_text());sources.append(p)
            metrics.append({'sequence':s,'condition':m,'reader_name':NAME[m],'source':str(p),'original_metrics_json':json.dumps(v,ensure_ascii=False)})
            profile.append({'sequence':s,'condition':m,'rows':len(d),'first_time':d.t_rel_s.iloc[0],'last_time':d.t_rel_s.iloc[-1],
                            'horizontal_max_m':d.horizontal_err_m.max(),'yaw_min_deg':d.yaw_err_deg.min(),'yaw_max_deg':d.yaw_err_deg.max()})
    pd.DataFrame(metrics).to_csv(OUT/'ROBOT_RELATIVE_METRICS.csv',index=False)
    pd.DataFrame(profile).to_csv(OUT/'SOURCE_PROFILE.csv',index=False)
    fig,axes=plt.subplots(2,3,figsize=(174*MM,139*MM))
    fig.subplots_adjust(left=.11,right=.985,top=.86,bottom=.12,wspace=.32,hspace=.52)
    for c,s in enumerate(SEQS):
        for row,col in enumerate(['horizontal_err_m','yaw_err_deg']):
            ax=axes[row,c];ax.set_gid(chr(97+row*3+c))
            for m in METHODS:
                d=frames[s,m]
                cuts=np.diff(d.t_rel_s)>.15
                if row:cuts|=np.abs(np.diff(d[col]))>180
                for ids in np.split(np.arange(len(d)),np.flatnonzero(cuts)+1):
                    ax.plot(d.elapsed_s.to_numpy()[ids],d[col].to_numpy()[ids],color=COLOR[m],ls=STYLE[m],lw=.95,rasterized=True)
            ax.set_xlim(0,DURATION[s]);ax.set_xticks([0,100,200] if s!='BY2O' else [0,150,300])
            ax.set_ylim((0,165) if row==0 else (-25,175));ax.set_yticks([0,50,100,150])
            if row:ax.axhline(0,color='#999999',ls=':',lw=.5,zorder=0);ax.set_xlabel('Elapsed time (s)')
            if c==0:ax.set_ylabel('Horizontal error (m)' if row==0 else 'Heading error (°)')
            panel(ax,chr(97+row*3+c),s if row==0 else '')
    zoom=axes[0,0].inset_axes([.15,.56,.53,.38])
    for m in METHODS:
        d=frames['BY2',m];q=d[d.elapsed_s<=40]
        zoom.plot(q.elapsed_s,q.horizontal_err_m,color=COLOR[m],ls=STYLE[m],lw=.8)
    zoom.set_xlim(0,40);zoom.set_ylim(bottom=0);zoom.set_xticks([0,20,40]);zoom.tick_params(labelsize=6.5,length=2)
    zoom.yaxis.set_major_locator(__import__('matplotlib').ticker.MaxNLocator(3))
    zoom.set_title('First 40 s',fontsize=7,pad=2)
    for sp in zoom.spines.values():sp.set_visible(True);sp.set_linewidth(.5)
    fig.legend(handles=[Line2D([],[],color=COLOR[m],ls=STYLE[m],label=NAME[m],lw=1.2) for m in METHODS],
               loc='upper center',bbox_to_anchor=(.55,.985),ncol=3,columnspacing=1.,handlelength=2.5)
    en=('Relative-motion errors from contact-aided state estimation. '
        'Each column corresponds to one trial; the upper and lower rows show horizontal and heading errors after a single translation and yaw alignment over the first 10 s of the evaluation window. '
        'The official contact-aided InEKF is shown with literature and example noise settings. '
        'Kinematic integration uses contact-foot velocity and onboard attitude. The inset enlarges the first 40 s of nominal walking. '
        'All curves retain the completed evaluation times.')
    zh=('接触辅助状态估计的相对运动误差。各列分别对应一种工况；在评价窗开始的10 s内进行一次平移与航向对齐后，上、下排分别为水平和航向误差。'
        '官方接触辅助InEKF分别采用文献与示例噪声设置；接触运动学积分使用接触足速度和机载姿态。小窗放大常规行走的前40 s。曲线采用已完成评价的原时刻。')
    result=export(fig,OUT,'S01_robot_relative_motion',caption_en=en,caption_zh=zh,
      meaning_zh='结构图解释绝对方向自由度；这张补充图展示同一平台输入下相对状态估计的实际误差演化，以及机载姿态参与的运动学积分参照。',
      sources=sources,technical_notes={'all_rows_retained':True,'new_solver_evaluator_provider_calls':0,
         'official_version':'ef16e8a1df72f9272111a488880e3fe9d161f59f','alignment':'one translation plus yaw fit during first10s, no continuous reference correction',
         'kinematic_velocity':'-mean_contact(omega cross foot_position + foot_speed_body), rotated by onboard rpy',
         'comparison_role':'relative odometry and input diagnostic, no flat absolute-GNSS accuracy ranking','local_window':'first40 seconds, fixed elapsed-time interval'},
      axes=list(axes.flat),row_groups=[['a','b','c'],['d','e','f']],column_groups=[['a','d'],['b','e'],['c','f']])
    (OUT/'CAPTIONS.md').write_text(en+'\n\n'+zh+'\n')
if __name__=='__main__':main()
