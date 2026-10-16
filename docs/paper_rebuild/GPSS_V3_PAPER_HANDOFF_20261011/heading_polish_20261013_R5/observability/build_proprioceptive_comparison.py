"""One shared question: relative-motion information and heading gauge.

No solver, evaluator or provider is called. All curves are retained saved
states or previously evaluated errors; the initial10s alignment is not refit.
"""
from pathlib import Path
import sys,json,subprocess
import numpy as np,pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import FancyArrowPatch
from PIL import Image

O=Path(__file__).parent
SK=Path('/mnt/c/Users/ykw/.codex/skills/nature-figure/scripts');sys.path.insert(0,str(SK))
from audit_panel_alignment import require_matplotlib_panel_alignment
for s in ['preview','qa','source_data']:(O/s).mkdir(exist_ok=True)
plt.rcParams.update({'font.family':'sans-serif','font.sans-serif':['DejaVu Sans'],
 'font.size':8,'axes.labelsize':8,'axes.titlesize':8.5,'xtick.labelsize':8,'ytick.labelsize':8,
 'legend.fontsize':8,'legend.frameon':False,'axes.spines.top':False,'axes.spines.right':False,
 'axes.linewidth':.6,'xtick.major.size':2.5,'ytick.major.size':2.5,
 'pdf.fonttype':42,'svg.fonttype':'none','path.simplify':False,'savefig.facecolor':'white'})
YCOL={-150:'#8A8F98',-100:'#E76F51',-50:'#8A8F98',0:'#2563EB',50:'#8A8F98',100:'#009E9A',150:'#8A8F98'}
YLS={-150:':',-100:'--',-50:'-.',0:'-',50:(0,(3,1,1,1)),100:'-.',150:(0,(6,2))}
MCOL={'OFF-LIT':'#E76F51','LEG-DR':'#009E9A'}
MLINE={'OFF-LIT':'-','LEG-DR':'--'}
NAMES={'OFF-LIT':'Contact-aided InEKF','LEG-DR':'Kinematic DR + onboard attitude'}
SEQS=['BY2','BY2H','BY2O'];SCENES=['Nominal walking','Large body motion','Antenna obstruction']
metrics=pd.read_csv(O/'source_data/ROBOT_RELATIVE_RESULTS.csv')
relative={(s,m):pd.read_csv(O/f'source_data/relative/{s}_{m}_relative_errors.csv.gz')
          for s in SEQS for m in ['OFF-LIT','LEG-DR','OFF-DEF']}
runs={int(p.name.split('_')[-1].split('.')[0]):pd.read_csv(p) for p in (O/'source_data/gauge').glob('native_initial_yaw_*.csv.gz')}
assert len(runs)==7
primary=metrics[metrics.condition.isin(MCOL)].copy()
primary.to_csv(O/'source_data/TWO_ROUTE_METRICS_ALL_SCENES.csv',index=False)

contract={
 'claim':'Contact-only InEKF retains its known initial-yaw freedom; the completed InEKF and onboard-attitude-assisted kinematic route show different relative-motion errors after one initial alignment.',
 'role':'Known-gauge illustration plus the two author-confirmed completed proprioceptive routes.',
 'a_b':'Retained H5/H6 IJRR-reported backend, seven initialized yaw settings; no new ensemble.',
 'c_d':'Official contact InEKF literature parameters vs contact-kinematic dead reckoning with onboard attitude, using saved one-time10s-aligned errors.',
 'main_sequence':'Nominal walking is the preselected primary recording, not chosen for best gap.',
 'other_sequences':'S04 shows all three recordings and both selected routes; OFF-DEF remains a parameter-sensitivity table.',
 'input_difference':'LEG-DR uses onboard attitude and foot velocity; contact InEKF estimates attitude from body IMU plus contact/foot-position proxies.',
 'method_identity_difference':'The gauge experiment backend and later official InEKF evaluation are distinct implementations and protocols; no seven-yaw claim made for OFF-LIT or LEG-DR.',
 'new_solver_evaluator_provider_calls':0,'new_alignment_fits':0,'backend':'Python',
 'export':{'width_mm':174,'min_font_pt':8,'PNG_dpi':600,'preview_dpi':400}}
(O/'FIGURE_CONTRACT.json').write_text(json.dumps(contract,ensure_ascii=False,indent=2)+'\n')

def metric(s,m,key):return float(metrics[(metrics.sequence==s)&(metrics.condition==m)].iloc[0][key])
def curve(ax,d,column,m,lw=1.2):
    # Existing unsupported epochs remain gaps. Do not connect across missing support.
    t=d.elapsed_s.to_numpy();y=d[column].to_numpy()
    for ix in np.split(np.arange(len(d)),np.flatnonzero(np.diff(t)>.101)+1):
        if len(ix):ax.plot(t[ix],y[ix],color=MCOL[m],ls=MLINE[m],lw=lw,zorder=3)

def save(fig,name,axes,meta):
    fig.canvas.draw()
    options={}
    if name.startswith('F04'):
        options={'panel_ids':list('abcd'),'exemptions':[{'panels':list('abcd'),'checks':['column'],
                 'reason':'The two equal-scale square gauge panels are deliberately narrower than the two relative-error time panels; each comparable row retains identical sizes and gutters.'}]}
    require_matplotlib_panel_alignment(fig,axes=axes,
       json_out=O/'qa'/f'{name}.alignment.json',overlay_svg=O/'qa'/f'{name}.alignment.svg',
       tolerance_pt=1.5,gutter_tolerance_pt=1.5,strict=True,**options)
    for ext in ['pdf','svg']:fig.savefig(O/f'{name}.{ext}')
    fig.savefig(O/f'{name}.png',dpi=600);fig.savefig(O/f'{name}.tiff',dpi=600,pil_kwargs={'compression':'tiff_lzw'})
    fig.savefig(O/'preview'/f'{name}.png',dpi=400)
    Image.open(O/'preview'/f'{name}.png').convert('L').save(O/'preview'/f'{name}_gray.png')
    qa={}
    for tag,cmd in [('text',['audit_pdf_text.py',str(O/f'{name}.pdf'),'--min-pt','8','--json']),
                    ('collisions',['audit_figure_collisions.py',str(O/f'{name}.pdf'),'--json-out',str(O/'qa'/f'{name}.collisions.json')])]:
        r=subprocess.run([sys.executable,str(SK/cmd[0]),*cmd[1:]],capture_output=True,text=True)
        (O/'qa'/f'{name}.{tag}.log').write_text(r.stdout+r.stderr);qa[tag]=r.returncode
    meta.update(width_mm=174,height_mm=fig.get_figheight()*25.4,min_font_pt=8,audits=qa,
                new_solver_evaluator_provider_calls=0,new_alignment_fits=0,visual_review='PENDING')
    (O/f'{name}.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2)+'\n')
    plt.close(fig);print(name,qa,flush=True)

def main():
    fig,axs=plt.subplots(2,2,figsize=(174/25.4,162/25.4),gridspec_kw={'height_ratios':[1.05,.85]})
    fig.subplots_adjust(left=.10,right=.978,bottom=.09,top=.86,wspace=.42,hspace=.65)
    a,b,c,d=axs.flat
    anchor=runs[0][['local_x_m','local_y_m','local_z_m']].to_numpy();mx=0.
    for yaw in [-150,-50,50,150,-100,100,0]:
        q=runs[yaw];p=q[['local_x_m','local_y_m','local_z_m']].to_numpy()
        t=np.deg2rad(yaw);rz=np.array([[np.cos(t),np.sin(t),0],[-np.sin(t),np.cos(t),0],[0,0,1]])
        aligned=p@rz.T;mx=max(mx,float(np.linalg.norm(aligned-anchor,axis=1).max()))
        main=yaw in [-100,0,100]
        for ax,xy in [(a,p),(b,aligned)]:
            ax.plot(xy[:,0],xy[:,1],color=YCOL[yaw],ls=YLS[yaw],lw=1.1 if main else .6,zorder=5 if main else 2)
        a.plot(*p[-1,:2],'o',ms=2.5,color=YCOL[yaw],zorder=7)
    for yaw in [-100,0,100]:
        t=np.deg2rad(yaw);a.annotate('',xy=(46*np.cos(t),46*np.sin(t)),xytext=(0,0),
              arrowprops={'arrowstyle':'-|>','color':YCOL[yaw],'lw':1.2,'mutation_scale':9},zorder=10)
    for ax in [a,b]:
        ax.set(xlim=(-150,150),ylim=(-150,150),xticks=[-100,0,100],yticks=[-100,0,100],xlabel='Local x (m)',ylabel='Local y (m)')
        ax.set_aspect('equal',adjustable='box');ax.plot(0,0,'k*',ms=5,zorder=12)
    a.set_title('(a) Different initial headings',loc='left',pad=5)
    b.set_title('(b) Known rotation removed',loc='left',pad=5)
    b.text(.97,.055,'Seven paths overlap\nMax. difference: 1.89 × 10⁻⁷ m',transform=b.transAxes,
           ha='right',va='bottom',fontsize=8,color='#2563EB')
    yhandles=[Line2D([],[],color=YCOL[y],ls=YLS[y],lw=1.2,label=f'{y:+d}°' if y else '0°') for y in [-100,0,100]]
    yhandles.append(Line2D([],[],color='#8A8F98',lw=.7,label='Other four initial yaws'))
    fig.legend(handles=yhandles,loc='upper center',bbox_to_anchor=(.54,.995),ncol=4,
               columnspacing=.9,title='Same estimator and inputs; seven initial yaw settings',title_fontsize=8.5)
    for m in MCOL:
        q=relative['BY2',m];curve(c,q,'horizontal_err_m',m);curve(d,q,'yaw_err_deg',m)
    for ax in [c,d]:
        ax.axvspan(0,10,color='#E5E7EB',zorder=0)
        ax.set(xlim=(0,274),xticks=[0,100,200],xlabel='Elapsed time (s)')
    c.set(ylabel='Relative horizontal error (m)',ylim=(0,128),yticks=[0,40,80,120])
    d.set_ylabel('Relative heading error (deg)');d.axhline(0,color='#B8B8B8',lw=.5,zorder=0)
    c.set_title('(c) Relative displacement',loc='left',pad=5)
    d.set_title('(d) Relative heading',loc='left',pad=5)
    for ax,key,unit in [(c,'horizontal_rmse_m','m'),(d,'yaw_rmse_deg','°')]:
        for k,m in enumerate(MCOL):
            ax.text(.075,.94-.105*k,f'{"InEKF" if m=="OFF-LIT" else "Kinematic DR"}: {metric("BY2",m,key):.2f} {unit} RMSE',
                    transform=ax.transAxes,ha='left',va='top',fontsize=8,color=MCOL[m])
    handles=[Line2D([],[],color=MCOL[m],ls=MLINE[m],lw=1.3,label=NAMES[m]) for m in MCOL]
    gap_mid=(a.get_position().y0+c.get_position().y1)/2
    fig.legend(handles=handles,loc='center',bbox_to_anchor=(.54,gap_mid),ncol=1,
        title='Nominal walking · one initial 10 s alignment',title_fontsize=8.5,labelspacing=.45,handlelength=2.5)
    save(fig,'F04_proprioceptive_heading_and_two_routes',[a,b,c,d],
         {'role':'main','gauge_native_histories':7,'gauge_rows_per_history':63277,'gauge_residual_max_m':mx,
          'main_relative_sequence':'BY2','main_relative_rows_per_route':2741,
          'relative_methods':['official Hartley OFF-LIT','HX05 LEG-DR with onboard attitude'],
          'relative_window':[66,340],'saved_alignment_window':[66,76],
          'relative_metrics':primary[primary.sequence=='BY2'].drop(columns=['source']).to_dict('records'),
          'boundary':'Gauge panels use an earlier reported-IJRR backend. Relative comparison uses the later official library and the onboard-attitude-dependent kinematic route; no same seven-yaw experiment exists for those two routes.'})

def supplement():
    fig,axs=plt.subplots(2,3,figsize=(174/25.4,139/25.4))
    fig.subplots_adjust(left=.10,right=.978,bottom=.105,top=.80,wspace=.36,hspace=.44)
    for j,(s,scene) in enumerate(zip(SEQS,SCENES)):
        for row,key in enumerate(['horizontal_err_m','yaw_err_deg']):
            ax=axs[row,j]
            for m in MCOL:curve(ax,relative[s,m],key,m,lw=1.)
            ax.axvspan(0,10,color='#E5E7EB',zorder=0)
            duration=float(relative[s,'LEG-DR'].elapsed_s.max())
            ax.set(xlim=(0,duration),xlabel='Elapsed time (s)')
            if row==0:ax.set_title(f'({chr(97+j)}) {scene}',loc='left',pad=5);ax.set_ylim(0,165)
            else:ax.set_title(f'({chr(100+j)}) {scene}',loc='left',pad=5);ax.axhline(0,color='#BBBBBB',lw=.5,zorder=0)
            if j==0:ax.set_ylabel('Relative horizontal error (m)' if row==0 else 'Relative heading error (deg)')
    fig.legend(handles=[Line2D([],[],color=MCOL[m],ls=MLINE[m],lw=1.3,label=NAMES[m]) for m in MCOL],
       loc='upper center',bbox_to_anchor=(.54,.98),ncol=1,
       title='One initial 10 s alignment for each recorded route',title_fontsize=8.5,labelspacing=.6)
    save(fig,'S04_two_proprioceptive_routes_all_scenes',list(axs.flat),
         {'role':'supplement','recordings':3,'methods':list(MCOL),'OFF_DEF_role':'Full metrics retained as parameter sensitivity, not a third algorithm.',
          'rows_per_route':{'BY2':2741,'BY2H':2700,'BY2O':3771},'all_saved_rows_retained':True,
          'alignment':'Saved one-time yaw+translation fit in first10s; no refit.'})

if __name__=='__main__':main();supplement()
