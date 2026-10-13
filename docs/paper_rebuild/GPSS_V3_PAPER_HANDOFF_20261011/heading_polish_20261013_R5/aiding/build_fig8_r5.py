"""Three fixed mechanism cases: input perturbation, logged covariance, heading response."""
from pathlib import Path
import json
import numpy as np,pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.text import Text
from PIL import Image
from audit_panel_alignment import require_matplotlib_panel_alignment

P=Path(__file__).resolve().parent
for k in ['figures','preview','qa']:(P/k).mkdir(exist_ok=True)
plt.rcParams.update({'font.family':'sans-serif','font.sans-serif':['Arial','Liberation Sans','DejaVu Sans'],'font.size':8,'axes.labelsize':8,'axes.titlesize':8.5,'xtick.labelsize':8,'ytick.labelsize':8,'legend.fontsize':8,'legend.frameon':False,'axes.spines.top':False,'axes.spines.right':False,'axes.linewidth':.65,'xtick.direction':'out','ytick.direction':'out','xtick.major.size':2.5,'ytick.major.size':2.5,'pdf.fonttype':42,'svg.fonttype':'none','path.simplify':False})
BLUE='#2563EB';PURPLE='#8B5CF6';GRAY='#5F6B7A';ORANGE='#E76F51'
cases=json.loads((P/'SELECTED_CASES.json').read_text())
BIN_TABLES=[]

def line(ax,t,y,color,ls='-',lw=.8,gap=.1,z=3):
    t=np.asarray(t);y=np.asarray(y)
    for ind in np.split(np.arange(len(t)),np.flatnonzero(np.diff(t)>gap)+1):
        if len(ind):ax.plot(t[ind],y[ind],color=color,ls=ls,lw=lw,rasterized=True,zorder=z)

def title(ax,letter,label):ax.set_title(f'({letter}) {label}',loc='left',fontweight='bold',pad=8)

def temporal_summary(ax,t,y,color,ls,label,case,source):
    t=np.asarray(t);y=np.asarray(y);valid=(t>=0)&(t<=120)&np.isfinite(t)&np.isfinite(y)
    t=t[valid];y=y[valid];bins=np.minimum(np.floor(t).astype(int),119)
    records=[]
    for k in range(120):
        v=y[bins==k]
        records.append({'case':case,'source':source,'interval_start_s':k,'interval_end_s':k+1,'last_bin_closed_right':k==119,'count':len(v),'minimum':np.min(v) if len(v) else np.nan,'median':np.median(v) if len(v) else np.nan,'maximum':np.max(v) if len(v) else np.nan})
    d=pd.DataFrame(records);assert d['count'].sum()==len(y)
    BIN_TABLES.extend(records)
    # One-second bins retain every sample; ranges show within-bin extrema, not uncertainty across replays.
    edges=np.arange(121,dtype=float)
    ax.fill_between(edges,np.r_[d.minimum.to_numpy(),d.minimum.iloc[-1]],np.r_[d.maximum.to_numpy(),d.maximum.iloc[-1]],step='post',color=color,alpha=.13,linewidth=0,zorder=2,rasterized=True)
    ax.plot(np.arange(120)+.5,d['median'],color=color,ls=ls,lw=1.1 if source=='weighting_off' else .95,label=label,zorder=6 if source=='full' else 5)
    return len(y)

def save(fig,name):
    fig.canvas.draw()
    require_matplotlib_panel_alignment(fig,json_out=P/'qa'/f'{name}.alignment.json',strict=True,tolerance_pt=1.5,gutter_tolerance_pt=1.5)
    ren=fig.canvas.get_renderer();bb=fig.bbox;texts=[x for x in fig.findobj(Text) if x.get_visible() and x.get_text()];clip=[]
    for t in texts:
        box=t.get_window_extent(ren)
        if box.x0<bb.x0-2 or box.x1>bb.x1+2 or box.y0<bb.y0-2 or box.y1>bb.y1+2:clip.append(t.get_text())
    q={'width_mm':fig.get_figwidth()*25.4,'height_mm':fig.get_figheight()*25.4,'minimum_font_pt':min(t.get_fontsize() for t in texts),'clipped_text':clip,'display_aggregation':'Fixed nonoverlapping1s bins; median line and min–max range, all native samples counted; not a seed confidence interval','fitted_smoothing':False,'navigation_metrics_recomputed':False,'intentional_hero_column':'Right heading-response panels span three GridSpec columns; left/middle each span one equal-width data column, separated by empty gutters.'}
    (P/'qa'/f'{name}.layout.json').write_text(json.dumps(q,indent=2),encoding='utf8')
    fig.savefig(P/'figures'/f'{name}.pdf',dpi=600,facecolor='white')
    fig.savefig(P/'figures'/f'{name}.svg',dpi=600,facecolor='white')
    fig.savefig(P/'figures'/f'{name}.png',dpi=600,facecolor='white')
    fig.savefig(P/'figures'/f'{name}.tiff',dpi=600,facecolor='white',pil_kwargs={'compression':'tiff_lzw'})
    fig.savefig(P/'preview'/f'{name}.png',dpi=450,facecolor='white')
    Image.open(P/'preview'/f'{name}.png').convert('L').save(P/'qa'/f'{name}_gray.png')
    plt.close(fig);print('SAVED',name,flush=True)

def draw():
    fig=plt.figure(figsize=(174/25.4,222/25.4))
    gs=fig.add_gridspec(3,7,width_ratios=[1,.5,1,.5,2/3,2/3,2/3],left=.105,right=.985,bottom=.105,top=.84,hspace=.68,wspace=0)
    axs=[]
    for r in range(3):axs.append([fig.add_subplot(gs[r,0]),fig.add_subplot(gs[r,2]),fig.add_subplot(gs[r,4:7])])
    fig.legend(handles=[Line2D([],[],color=GRAY,lw=.8,label='Added input change'),Line2D([],[],color=ORANGE,ls='--',lw=1,label='Reported uncertainty')],loc='upper left',bbox_to_anchor=(.025,.998),ncol=1,fontsize=8,handlelength=2.4)
    fig.legend(handles=[Line2D([],[],color=PURPLE,ls='--',lw=1,label='Without source weighting'),Line2D([],[],color=BLUE,lw=1,label='LegSA-GINS')],loc='upper right',bbox_to_anchor=(.99,.998),ncol=1,fontsize=8,handlelength=2.4)
    for j,lab in enumerate(['Input degradation','Covariance adjustment','Heading response']):
        bb=axs[0][j].get_position();fig.text(bb.x0+bb.width/2,.925,lab,ha='center',fontweight='bold',fontsize=8.5)
        fig.text(bb.x0+bb.width/2,.887,'Median · IQR · range' if j==1 else '1-s median / range',ha='center',fontsize=8)
    labels=['Position noise','Heading quality','Body-velocity noise'];params=['σH/V = 3/5 m','σ = 10°; low std','σ = 1 m/s']
    point_counts=[]
    for r,case in enumerate(cases):
        typ=case['type'];inp=pd.read_csv(P/'data'/f'{typ}_input_change.csv.gz');x=inp[inp.elapsed_s.between(0,120)].copy()
        a,b,c=axs[r];y=x.input_change_magnitude.where(x.input_valid)
        temporal_summary(a,x.elapsed_s,y,GRAY,'-','Added input change',typ,'input_change')
        temporal_summary(a,x.elapsed_s,x.reported_std_norm.where(x.input_valid),ORANGE,'--','Reported uncertainty',typ,'reported_uncertainty')
        ymax=float(np.nanmax(y));a.set(xlim=(0,120),ylim=(0,ymax*1.28),xlabel='Time (s)',ylabel=f'Input change ({case["input_unit"]})');a.set_xticks([0,60,120]);a.yaxis.set_major_locator(plt.MaxNLocator(4))
        title(a,chr(97+r*3),labels[r]);a.text(.97,.98,params[r],transform=a.transAxes,ha='right',va='top',fontsize=8)
        q=pd.read_csv(P/'tables'/f'{typ}_actual_covariance_summary.csv')
        for i,z in q.iterrows():
            b.plot([z.minimum,z.maximum],[i,i],color=GRAY,lw=.7)
            b.plot([z.q25,z.q75],[i,i],color=GRAY,lw=4,solid_capstyle='butt')
            b.scatter(z['median'],i,s=22,color=BLUE,zorder=4)
        b.axvline(1,color='#BDC4CC',ls=':',lw=.6,zorder=0)
        b.set(xlim=(0,11.2),ylim=(2.45,-.45),xlabel='Multiplier (×)');b.set_yticks([0,1,2],['Position','Body v','Heading']);b.set_xticks([1,5,10]);title(b,chr(98+r*3),'Recorded scaling')
        for method,rid in [('off',case['off_run']),('full',case['full_run'])]:
            d=pd.read_csv(P/'data'/f'{rid}_errors.csv.gz');t=d.time-66;k=t.between(0,120)
            temporal_summary(c,t[k],d.loc[k,'yaw_err_deg'],BLUE if method=='full' else PURPLE,'-' if method=='full' else '--','LegSA-GINS' if method=='full' else 'Without source weighting',typ,'full' if method=='full' else 'weighting_off')
            point_counts.append({'case':typ,'method':method,'run_id':rid,'whole_series_rows':len(d),'display_rows':int(k.sum())})
        c.axhline(0,color='#A7ADB4',ls=':',lw=.6,zorder=0);c.set(xlim=(0,120),xlabel='Time (s)',ylabel='Heading error (deg)');c.set_xticks([0,60,120]);c.yaxis.set_major_locator(plt.MaxNLocator(4));title(c,chr(99+r*3),'Near-neutral yaw' if typ=='D53' else 'Heading error')
        yaw=f'274-s yaw RMSE: {case["off_yaw_rmse_deg"]:.4g}° → {case["full_yaw_rmse_deg"]:.4g}°'
        h=f'H RMSE: {case["off_H_rmse_m"]:.4g} → {case["full_H_rmse_m"]:.4g} m'
        c.text(.5,-.34,yaw+'\n'+h,transform=c.transAxes,ha='center',va='top',fontsize=8,linespacing=1.5)
        if typ=='D53':c.text(1,1.02,'ΔRMSE = −0.0008°',transform=c.transAxes,ha='right',va='bottom',fontsize=8)
    pd.DataFrame(point_counts).to_csv(P/'tables/PLOTTED_NAV_SERIES_COUNTS.csv',index=False)
    pd.DataFrame(BIN_TABLES).to_csv(P/'tables/ONE_SECOND_DISPLAY_SUMMARIES.csv',index=False)
    save(fig,'F08_heading_quality_scaling')

if __name__=='__main__':draw()
