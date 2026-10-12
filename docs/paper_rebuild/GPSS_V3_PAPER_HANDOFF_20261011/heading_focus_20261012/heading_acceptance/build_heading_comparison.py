"""Heading-front-end comparison: saved errors and preregistered ratio masks."""
from pathlib import Path
import sys, json, hashlib
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

O=Path(__file__).parent
SK=Path('/mnt/c/Users/ykw/.codex/skills/nature-figure/scripts')
sys.path.insert(0,str(SK))
from audit_panel_alignment import require_matplotlib_panel_alignment

for name in ['preview','qa','figure_data']:(O/name).mkdir(exist_ok=True)
OLD=Path('/mnt/g/LegSA-GINS-project/V3五问题论文组图_20261011/heading/data')
OWN=Path('/mnt/g/LegSA-GINS-project/V3正文重绘_20261011/heading/source_data')
NEW=pd.read_csv(O/'ACCEPTED_ERROR_SERIES.csv')
SUM=pd.read_csv(O/'ACCEPTANCE_SUMMARY.csv')
SEQ=['BY2','BY2H','BY2O']
NAMES=['Nominal walking','Large body motion','Antenna obstruction']
START={'BY2':66,'BY2H':413,'BY2O':3186}
COL={'own':'#0072B2','rtk':'#D55E00','EXT01':'#009E73','EXT02':'#8B5A99','dd':'#555555'}
PROFILE=[]

def read(p):
    d=pd.read_csv(p)
    PROFILE.append(dict(path=str(p),rows=len(d),columns=list(d),sha256=hashlib.sha256(p.read_bytes()).hexdigest()))
    return d

OWN_DATA={s:read(OWN/f'{s}_input_heading_figure_match.csv.gz') for s in SEQ}
RTK={s:{v:read(OLD/f'{s}_{v}_full_saved_heading.csv.gz') for v in ['V0','V0E','V1','V2']} for s in SEQ}
RAW={s:read(OLD/f'{s}_all_methods_all_window_epochs.csv.gz') for s in SEQ}

CONTRACT={
 'question':'Which direction-processing chain provides accurate heading observations over the robot recording?',
 'claim':'The position-product direction selected by the native V3 update has smaller heading errors on these recordings; a separate project-added cost-ratio screen does not remove every large error in the raw carrier methods.',
 'archetype':'asymmetric quantitative comparison',
 'backend':'Python matplotlib',
 'panels':{'a':'Large body motion: input and used proposed direction, with default RTKLIB output and the same preselected 80-100 s turning zoom.',
           'b':'Same full recording: original C-LAMBDA/C-WLS estimates and their distinct project-added ratio-screen outputs.',
           'c-e':'Each complete-record error distribution; native C-L/C-WLS dashed and project-added screen solid; fixed default RTKLIB and DD-KF shown; all RTKLIB variants retained in CSV.'},
 'event':'Reference-confirmed 80-100s turn, shared with F03/F06, selected from reference motion not method error.',
 'method_scope':'Direction observations, not fused navigation posterior. Different input/validity chains; own support, with separate exact common-support table for raw methods.',
 'ratio_scope':'project-added ratio screen >=3, preregistered 6a1e536; no integer correctness claim',
 'full_window_support':'Counts beneath distributions are native output counts, with the full formal window denominator. Error CDF includes finite reference-supported samples.',
 'displaced_material':'RTKLIB V0E/V1/V2 and DD-KF native diagnostics remain ALL_DIRECTION_ROUTE_METRICS.csv; original candidates remain dashed distributions.',
 'width_mm':174,'height_mm':192,'min_font_pt':8.0,'no_smoothing':True,'new_native_solver_calls':0
}
(O/'FIGURE_CONTRACT.json').write_text(json.dumps(CONTRACT,ensure_ascii=False,indent=2)+'\n')

plt.rcParams.update({'font.family':'sans-serif','font.sans-serif':['DejaVu Sans'],
 'font.size':8,'axes.titlesize':8.5,'axes.labelsize':8,'xtick.labelsize':8,'ytick.labelsize':8,
 'legend.fontsize':8,'axes.spines.top':False,'axes.spines.right':False,'axes.linewidth':.6,
 'pdf.fonttype':42,'svg.fonttype':'none','path.simplify':False,'legend.frameon':False})

def ecdf(ax,e,color,lw=1,ls='-',alpha=1,zorder=3,limit=15):
    e=np.sort(np.abs(np.asarray(e,dtype=float)));e=e[np.isfinite(e)]
    if len(e):
        n=np.searchsorted(e,limit,side='right')
        ax.step(np.r_[0,e[:n],limit],np.r_[0,np.arange(1,n+1)/len(e),n/len(e)],where='post',color=color,lw=lw,ls=ls,alpha=alpha,zorder=zorder)


fig=plt.figure(figsize=(174/25.4,192/25.4))
gs=fig.add_gridspec(3,3,left=.102,right=.976,bottom=.215,top=.875,
                    hspace=.72,wspace=.38,height_ratios=[1.,1.,1.08])
a=fig.add_subplot(gs[0,:2]);ins=fig.add_subplot(gs[0,2]);b=fig.add_subplot(gs[1,:]); cs=[fig.add_subplot(gs[2,j]) for j in range(3)]
own=OWN_DATA['BY2H'];rtk=RTK['BY2H']['V0']
a.plot(own.elapsed_s,own.input_error_deg.where(own.input_heading_valid),color='#A9BBC7',lw=.55,alpha=.9,zorder=1)
a.plot(own.elapsed_s,own.input_error_deg.where(own.accepted),color=COL['own'],lw=1.,zorder=5)
a.scatter(rtk.loc[rtk.valid.eq(1),'t_rel_s']-413,rtk.loc[rtk.valid.eq(1),'error_valid_deg'],
          marker='s',s=6,facecolors='none',edgecolors=COL['rtk'],linewidths=.6,zorder=3)
a.axvspan(80,100,color='#CED9DE',alpha=.45,zorder=0)
a.set_title('(a) Large body motion: full recording',loc='left',pad=6)
a.set(xlim=(0,270),ylim=(-185,185),yticks=[-180,0,180],ylabel='Heading error (deg)',xlabel='Time (s)')
a.axhline(0,color='#CCCCCC',lw=.4,zorder=0)
# Same reference-selected turn used by F03 and F06; no error-based window search.
ins.set_facecolor('white')
zz=own.elapsed_s.between(80,100);zr=(rtk.t_rel_s-413).between(80,100)&rtk.valid.eq(1)
ins.plot(own.loc[zz,'elapsed_s'],own.loc[zz,'input_error_deg'].where(own.loc[zz,'accepted']),color=COL['own'],lw=.9)
ins.scatter(rtk.loc[zr,'t_rel_s']-413,rtk.loc[zr,'error_valid_deg'],marker='s',s=5,facecolors='none',edgecolors=COL['rtk'],linewidths=.6)
values=np.r_[own.loc[zz&own.accepted,'input_error_deg'].dropna(),rtk.loc[zr,'error_valid_deg'].dropna()]
lo=min(-2,float(np.min(values))-1);hi=max(2,float(np.max(values))+1)
ins.set(xlim=(80,100),ylim=(lo,hi),xticks=[80,90,100]);ins.tick_params(labelsize=8,length=2,pad=1)
ins.set_yticks([-5,0,5])
ins.set_title('Turning interval',loc='left',fontsize=8.5,pad=6)
ins.set_xlabel('Time (s)');ins.set_ylabel('Heading error (deg)',labelpad=1)
for sp in ins.spines.values():sp.set_visible(True);sp.set_color('#8B969C');sp.set_linewidth(.5)

for m,marker in [('EXT01','o'),('EXT02','x')]:
    d=NEW[NEW.sequence.eq('BY2H')&NEW.method_id.eq(m)]
    t=d.t_rel_s-413
    b.scatter(t[d.native_valid],d.loc[d.native_valid,'error_valid_deg'],s=2.2,color=COL[m],alpha=.25,marker='.',zorder=1)
    if marker=='o':b.scatter(t[d.accepted],d.loc[d.accepted,'error_accepted_deg'],s=7,facecolors='none',edgecolors=COL[m],linewidths=.55,zorder=3)
    else:b.scatter(t[d.accepted],d.loc[d.accepted,'error_accepted_deg'],s=7,color=COL[m],linewidths=.55,marker='x',zorder=4)
b.axhline(0,color='#CCCCCC',lw=.4,zorder=0)
b.axvspan(80,100,color='#CED9DE',alpha=.35,zorder=0)
b.set_title('(b) C-LAMBDA and C-WLS: original estimates and added ratio screen',loc='left',pad=6)
b.set(xlim=(0,270),ylim=(-185,185),yticks=[-180,0,180],ylabel='Heading error (deg)',xlabel='Time (s)')

metrics=[]
def metric(seq,method,support,d,valid,errorcol):
    e=d.loc[valid,errorcol].dropna().to_numpy()
    metrics.append(dict(sequence=seq,method=method,support=support,denominator=len(d),outputs=int(valid.sum()),
                        scored=len(e),coverage_percent=100*valid.mean(),rmse_deg=float(np.sqrt(np.mean(e**2))) if len(e) else np.nan,
                        p95_abs_deg=float(np.percentile(np.abs(e),95)) if len(e) else np.nan))
    return e

for j,(seq,name,ax) in enumerate(zip(SEQ,NAMES,cs)):
    own=OWN_DATA[seq]
    oe=metric(seq,'Proposed direction','native used observations',own,own.accepted,'input_error_deg')
    metric(seq,'Proposed direction','input before native selection',own,own.input_heading_valid,'input_error_deg')
    rtk=RTK[seq]['V0']; re=metric(seq,'RTKLIB V0','native fixed',rtk,rtk.valid.eq(1),'error_valid_deg')
    dd=RAW[seq][RAW[seq].method_id.eq('EXT03')].copy()
    de=metric(seq,'DD-KF','native ratio fixed',dd,dd.error_ratio_fixed_deg.notna(),'error_ratio_fixed_deg')
    curves=[(oe,COL['own'],1.55,'-',1,8),(re,COL['rtk'],1.05,'-',1,6),(de,COL['dd'],.9,'-.',1,2)]
    counts=[f'Used: {int(own.accepted.sum())}/{len(own)}',f'RTKLIB: {int(rtk.valid.eq(1).sum())}/{len(rtk)}']
    for m,label in [('EXT01','C-L'),('EXT02','C-WLS')]:
        d=NEW[NEW.sequence.eq(seq)&NEW.method_id.eq(m)]
        e=metric(seq,label,'native original',d,d.native_valid,'error_valid_deg')
        es=metric(seq,label,'project-added ratio screen >=3',d,d.accepted,'error_accepted_deg')
        curves += [(e,COL[m],.85,'--',.55,1),(es,COL[m],1.1,'-',1,5)]
        counts.append(f'{label}: {int(d.native_valid.sum())}→{int(d.accepted.sum())}/{len(d)}')
    counts.append(f'DD-KF: {int(dd.error_ratio_fixed_deg.notna().sum())}/{len(dd)}')
    for e,c,lw,ls,alpha,z in curves:ecdf(ax,e,c,lw,ls,alpha,z)
    ax.set(xlim=(0,15),ylim=(0,1.025),xticks=[0,5,10,15],yticks=[0,.5,1],xlabel='Absolute heading error (deg)')
    ax.set_title(f'({chr(99+j)}) {name}',loc='left',pad=7)
    if j==0:ax.set_ylabel('Cumulative fraction')
    ax.grid(axis='y',color='#E5E5E5',lw=.4)
    # Full 0–180° tail remains visible; main axis is the explicitly labelled precision view.
    inset=ax.inset_axes([.49,.14,.48,.30]);inset.set_facecolor('white')
    for e,c,lw,ls,alpha,z in curves:ecdf(inset,e,c,.65 if lw<1.5 else .9,ls,alpha,z,limit=180)
    inset.set(xlim=(0,180),ylim=(0,1.025),xticks=[0,180],yticks=[]);inset.tick_params(labelsize=8,length=2,pad=1)
    inset.get_xticklabels()[0].set_ha('left');inset.get_xticklabels()[-1].set_ha('right')
    for sp in inset.spines.values():sp.set_visible(True);sp.set_linewidth(.45);sp.set_color('#777777')
    ax.text(0,-.35,'Outputs / full window',transform=ax.transAxes,fontsize=8,weight='bold',va='top')
    for k,txt in enumerate(counts):ax.text(0,-.47-.112*k,txt,transform=ax.transAxes,fontsize=8,va='top',color='#444444')
    # Full RTKLIB four-variant metrics remain explicit, not best-of-four chosen.
    for v in ['V0E','V1','V2']:
        d=RTK[seq][v];metric(seq,'RTKLIB '+v,'native fixed',d,d.valid.eq(1),'error_valid_deg')

handles=[Line2D([],[],color=COL['own'],lw=1.7,label='Proposed: used direction'),
         Line2D([],[],color='#A9BBC7',lw=.8,label='Proposed: input before selection'),
         Line2D([],[],marker='s',mfc='none',mec=COL['rtk'],color=COL['rtk'],lw=.8,ms=3.5,label='RTKLIB (default)'),
         Line2D([],[],color=COL['EXT01'],marker='o',mfc='none',lw=1,ms=3.5,label='C-LAMBDA'),
         Line2D([],[],color=COL['EXT02'],marker='x',lw=1,ms=3.5,label='C-WLS'),
         Line2D([],[],color=COL['dd'],ls='-.',lw=.9,label='DD-KF (native ratio fixed)')]
fig.legend(handles=handles,loc='upper center',bbox_to_anchor=(.54,.997),ncol=2,
           columnspacing=2,handlelength=2.5,labelspacing=.5)
fig.text(.54,.019,'C-LAMBDA / C-WLS: faint or dashed = original; solid or markers = project-added ratio screen (≥3).',
         ha='center',fontsize=8)
fig.canvas.draw()
require_matplotlib_panel_alignment(fig,axes=[a,ins,b,*cs],json_out=str(O/'qa/F05.alignment.json'),
                                   overlay_svg=str(O/'qa/F05.alignment.svg'),tolerance_pt=1.5,
                                   gutter_tolerance_pt=1.5,strict=True)
name='F05_heading_error_comparison'
fig.savefig(O/f'{name}.pdf',dpi=600)
fig.savefig(O/f'{name}.svg',dpi=600)
fig.savefig(O/f'{name}.png',dpi=600)
fig.savefig(O/f'{name}.tiff',dpi=600,pil_kwargs={'compression':'tiff_lzw'})
fig.savefig(O/'preview'/f'{name}.png',dpi=300)
plt.close(fig)
from PIL import Image
Image.open(O/'preview'/f'{name}.png').convert('L').save(O/'preview'/f'{name}_gray.png')
pd.DataFrame(metrics).to_csv(O/'ALL_DIRECTION_ROUTE_METRICS.csv',index=False)
(O/'SOURCE_PROFILE.json').write_text(json.dumps(PROFILE,ensure_ascii=False,indent=2)+'\n')
print(name)
