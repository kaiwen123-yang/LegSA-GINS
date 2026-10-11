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
