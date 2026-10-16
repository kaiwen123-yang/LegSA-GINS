"""Visual-only R6. Read the existing R5 one-second summaries without recomputation."""
from pathlib import Path
import argparse,json,hashlib
import numpy as np,pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.text import Text
from PIL import Image
from audit_panel_alignment import require_matplotlib_panel_alignment

P=Path(__file__).resolve().parent
ap=argparse.ArgumentParser();ap.add_argument('--source-dir',default='/mnt/g/LegSA-GINS-project/V3正文精修_20261013_R5/aiding');args=ap.parse_args();S=Path(args.source_dir)
for k in ['figures','preview','qa']:(P/k).mkdir(exist_ok=True)
cases=json.loads((S/'SELECTED_CASES.json').read_text());bins=pd.read_csv(S/'tables/ONE_SECOND_DISPLAY_SUMMARIES.csv')
assert len(bins)==1440
plt.rcParams.update({'font.family':'sans-serif','font.sans-serif':['Arial','Liberation Sans','DejaVu Sans'],'font.size':8,'axes.labelsize':8,'axes.titlesize':8.5,'xtick.labelsize':8,'ytick.labelsize':8,'legend.fontsize':8,'legend.frameon':False,'axes.spines.top':False,'axes.spines.right':False,'axes.linewidth':.65,'xtick.direction':'out','ytick.direction':'out','xtick.major.size':2.5,'ytick.major.size':2.5,'pdf.fonttype':42,'svg.fonttype':'none','path.simplify':False})
BLUE='#175C9E';OFF='#C66B3D';GRAY='#4F565E';TEAL='#238B8A'
USED=[]

def trace(ax,case,source,color,ls='-',z=3):
    d=bins[bins.case.eq(case)&bins.source.eq(source)].sort_values('interval_start_s');assert len(d)==120
    edge=np.r_[d.interval_start_s.to_numpy(),d.interval_end_s.iloc[-1]]
    lo=np.r_[d.minimum.to_numpy(),d.minimum.iloc[-1]];hi=np.r_[d.maximum.to_numpy(),d.maximum.iloc[-1]]
    ax.fill_between(edge,lo,hi,step='post',color=color,alpha=.10,linewidth=0,zorder=1,rasterized=True)
    ax.plot((d.interval_start_s+d.interval_end_s)/2,d['median'],color=color,ls=ls,lw=1.05 if source=='weighting_off' else .98,zorder=z)
    USED.append({'case':case,'source':source,'bin_rows':len(d),'raw_samples_counted':int(d['count'].sum()),'minimum':float(d.minimum.min()),'maximum':float(d.maximum.max())})
    return d

fig=plt.figure(figsize=(174/25.4,198/25.4))
widths=[1.15/3]*3+[.40]+[.8/2]*2+[.40]+[1.45/4]*4
gs=fig.add_gridspec(3,11,width_ratios=widths,left=.10,right=.985,bottom=.11,top=.835,hspace=.56,wspace=0)
axs=[[fig.add_subplot(gs[r,0:3]),fig.add_subplot(gs[r,4:6]),fig.add_subplot(gs[r,7:11])] for r in range(3)]
fig.legend(handles=[Line2D([],[],color=GRAY,lw=1,label='Added input change'),Line2D([],[],color=TEAL,ls='--',lw=1,label='Reported uncertainty')],loc='upper left',bbox_to_anchor=(.035,.999),ncol=1,fontsize=8,handlelength=2.5)
fig.legend(handles=[Line2D([],[],color=OFF,ls='--',lw=1.1,label='Without source weighting'),Line2D([],[],color=BLUE,lw=1.1,label='LegSA-GINS')],loc='upper right',bbox_to_anchor=(.99,.999),ncol=1,fontsize=8,handlelength=2.5)
headers=['Input degradation','Source covariance','Heading response']
subheads=['Change from clean input\n1-s median / range','Actual updates\nMedian · IQR · range','1-s median / range\n274-s RMSE: yaw (°) / H (m)']
for j in range(3):
    pos=axs[0][j].get_position();xc=pos.x0+pos.width/2
    fig.text(xc,.928,headers[j],ha='center',fontweight='bold',fontsize=8.5)
    fig.text(xc,.889,subheads[j],ha='center',va='center',fontsize=8,linespacing=1.2)
labels=['Position noise','Heading quality','Body-velocity noise'];params=['σH/V = 3/5 m','σ = 10°; low std','σ = 1 m/s']
for r,case in enumerate(cases):
    typ=case['type'];a,b,c=axs[r]
    d=trace(a,typ,'input_change',GRAY);trace(a,typ,'reported_uncertainty',TEAL,'--',4)
    ymax=float(d.maximum.max());a.set(xlim=(0,120),ylim=(0,ymax*1.28),xlabel='Time (s)',ylabel=f'Input change ({case["input_unit"]})');a.set_xticks([0,60,120]);a.yaxis.set_major_locator(plt.MaxNLocator(4))
    a.set_title(f'({chr(97+r*3)}) {labels[r]}',loc='left',fontweight='bold',pad=7)
    a.text(.97,.98,params[r],transform=a.transAxes,ha='right',va='top',fontsize=8)
    q=pd.read_csv(S/'tables'/f'{typ}_actual_covariance_summary.csv')
    for i,z in q.iterrows():
        b.plot([z.minimum,z.maximum],[i,i],color='#7A838D',lw=.7)
        b.plot([z.q25,z.q75],[i,i],color='#7A838D',lw=4,solid_capstyle='butt')
        b.scatter(z['median'],i,s=22,color=BLUE,zorder=4)
    b.axvline(1,color='#C2C8CE',ls=':',lw=.6,zorder=0)
    b.set(xlim=(0,11.2),ylim=(2.45,-.45),xlabel='Multiplier (×)');b.set_yticks([0,1,2],['Position','Body v','Heading']);b.set_xticks([1,5,10]);b.set_title(f'({chr(98+r*3)})',loc='left',fontweight='bold',pad=7)
    trace(c,typ,'weighting_off',OFF,'--',5);trace(c,typ,'full',BLUE,'-',6)
    c.axhline(0,color='#A8AFB7',ls=':',lw=.6,zorder=0)
    c.set(xlim=(0,120),xlabel='Time (s)',ylabel='Heading error (deg)');c.set_xticks([0,60,120]);c.yaxis.set_major_locator(plt.MaxNLocator(4))
    metric=f'{case["off_yaw_rmse_deg"]:.4g}→{case["full_yaw_rmse_deg"]:.4g}° / {case["off_H_rmse_m"]:.4g}→{case["full_H_rmse_m"]:.4g} m'
    c.set_title(f'({chr(99+r*3)}) {metric}',loc='left',fontsize=8,fontweight='normal',pad=7)
    if typ=='D53':c.text(.5,-.31,'Near-neutral yaw: ΔRMSE = −0.0008°',transform=c.transAxes,ha='center',va='top',fontsize=8)

name='F08_heading_quality_scaling'
fig.canvas.draw()
require_matplotlib_panel_alignment(fig,json_out=P/'qa'/f'{name}.alignment.json',strict=True,tolerance_pt=1.5,gutter_tolerance_pt=1.5)
ren=fig.canvas.get_renderer();bbox=fig.bbox;clipped=[];texts=[t for t in fig.findobj(Text) if t.get_visible() and t.get_text()]
for t in texts:
    bb=t.get_window_extent(ren)
    if bb.x0<bbox.x0-2 or bb.x1>bbox.x1+2 or bb.y0<bbox.y0-2 or bb.y1>bbox.y1+2:clipped.append(t.get_text())
layout={'width_mm':174,'height_mm':198,'data_column_width_ratio':[1.15,.8,1.45],'minimum_font_pt':min(t.get_fontsize() for t in texts),'clipped_text':clipped,'palette':{'full':BLUE,'off':OFF,'input':GRAY,'reported_uncertainty':TEAL},'range_alpha':.10,'data_change':False,'bin_recomputation':False,'input_data_source':str(S)}
(P/'qa'/f'{name}.layout.json').write_text(json.dumps(layout,indent=2),encoding='utf8')
fig.savefig(P/'figures'/f'{name}.pdf',dpi=600,facecolor='white')
fig.savefig(P/'figures'/f'{name}.svg',dpi=600,facecolor='white')
fig.savefig(P/'figures'/f'{name}.png',dpi=600,facecolor='white')
fig.savefig(P/'figures'/f'{name}.tiff',dpi=600,facecolor='white',pil_kwargs={'compression':'tiff_lzw'})
fig.savefig(P/'preview'/f'{name}.png',dpi=450,facecolor='white')
Image.open(P/'preview'/f'{name}.png').convert('L').save(P/'qa'/f'{name}_gray.png')
source_files=[S/'SELECTED_CASES.json',S/'tables/ONE_SECOND_DISPLAY_SUMMARIES.csv',*[S/'tables'/f'{c["type"]}_actual_covariance_summary.csv' for c in cases]]
pointer={'source_version':'R5','source_root':str(S),'files':[{'path':str(f),'sha256':hashlib.sha256(f.read_bytes()).hexdigest()} for f in source_files],'used_summaries':USED,'copying_raw_data':False,'new_solver_provider_evaluator_calls':0,'visual_only_revision':True}
(P/'SOURCE_POINTER.json').write_text(json.dumps(pointer,ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps(layout,ensure_ascii=False,indent=2));print('SAVED',name)
