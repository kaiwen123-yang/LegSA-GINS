"""Combine saved S9/S8 attitude evidence without rerunning estimation."""
from pathlib import Path
import argparse, json, sys, subprocess
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from PIL import Image

OUT=Path(__file__).resolve().parent
BASE=OUT.parent
TABLES=BASE/'aiding/tables'
SKILL=Path('/mnt/c/Users/ykw/.codex/skills/nature-figure/scripts')
sys.path.insert(0,str(SKILL))
from audit_panel_alignment import require_matplotlib_panel_alignment

SEQ=['BY2','BY2H','BY2O']
START={'BY2':66,'BY2H':413,'BY2O':3186}
NAMES={'BY2':'Nominal walking','BY2H':'Large body motion','BY2O':'Antenna obstruction'}
WINDOW={'BY2':(125,145),'BY2H':(125,145),'BY2O':(194,214)}
STYLES={
    'F01':dict(color='#818181',ls=(0,(1,2)),lw=.65,label='Basic GNSS/INS'),
    'F03':dict(color='#D55E00',ls=(0,(6,3)),lw=1.0,label='Basic + dual-antenna heading'),
    'F04':dict(color='#0072B2',ls='-',lw=.60,label='LegSA-GINS'),
    'A05':dict(color='#A35C9C',ls=(0,(3,2)),lw=.75,label='Without tilt aiding'),
}
FIELDS=['yaw_err_deg','roll_err_deg','pitch_err_deg']
NAME='M_attitude_heading_and_tilt'

def prepare(source_root):
    table_root=source_root/'aiding/tables'
    av=pd.read_csv(table_root/'ERROR_SERIES_AVAILABILITY6468.csv')
    natural=pd.read_csv(table_root/'NATURAL33.csv')
    cache={}; profiles=[]; metrics=[]; sources=[]
    for seq in SEQ:
        for method in ['F01','F03','F04','A05']:
            a=av[(av.sequence_id==seq)&(av.method_id==method)]
            a=a[a.case_id=='C00_clean_normal'] if seq=='BY2' else a[a.domain=='SEQUENCE']
            assert len(a)==1,(seq,method,len(a))
            p=Path(a.iloc[0].path)
            d=pd.read_csv(p,usecols=['time',*FIELDS])
            assert d.time.is_monotonic_increasing
            cache[seq,method]=d
            row=natural[(natural.sequence_id==seq)&(natural.internal_method_id==method)]
            assert len(row)==1
            for field in FIELDS:
                x=d[field].to_numpy()
                profiles.append(dict(sequence=seq,method=method,field=field,rows=len(d),
                    missing=int(np.isnan(x).sum()),min=float(np.nanmin(x)),max=float(np.nanmax(x)),
                    time_min=float(d.time.min()-START[seq]),time_max=float(d.time.max()-START[seq])))
            metrics.append({'scene':NAMES[seq],'sequence_id':seq,'method_id':method,
                            **{k:float(row.iloc[0][k]) for k in ['yaw_rmse_deg','roll_rmse_deg','pitch_rmse_deg']}})
            sources.append(dict(sequence_id=seq,method_id=method,run_id=a.iloc[0].run_id,path=str(p),rows=len(d)))
    pd.DataFrame(profiles).to_csv(OUT/'SOURCE_PROFILE.csv',index=False)
    pd.DataFrame(metrics).to_csv(OUT/'NATURAL_ATTITUDE_METRICS.csv',index=False)
    (OUT/'SOURCES.json').write_text(json.dumps(sources,ensure_ascii=False,indent=2)+'\n')
    print('Read saved series:',len(sources),'rows:',sum(s['rows'] for s in sources),flush=True)
    return cache

def plot_line(ax,d,seq,field,method,zoom=False):
    t=d.time.to_numpy()-START[seq];y=d[field].to_numpy()
    if zoom:
        lo,hi=WINDOW[seq];keep=(t>=lo)&(t<=hi);t=t[keep];y=y[keep]
    # Preserve all original samples. Break lines at genuine timestamp gaps.
    split=np.flatnonzero(np.diff(t)>.1)+1
    style=STYLES[method].copy();style.pop('label')
    if zoom:style['lw']=.85 if method!='F04' else .65
    for ids in np.split(np.arange(len(t)),split):
        if len(ids):ax.plot(t[ids],y[ids],**style,rasterized=not zoom)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--final',action='store_true')
    ap.add_argument('--source-root',type=Path,default=BASE);a=ap.parse_args()
    OUT.mkdir(exist_ok=True);(OUT/'qa').mkdir(exist_ok=True);(OUT/'preview').mkdir(exist_ok=True)
    data=prepare(a.source_root)
    plt.rcParams.update({'font.family':'sans-serif','font.sans-serif':['Arial','Liberation Sans','DejaVu Sans'],
        'font.size':8,'axes.labelsize':8.5,'xtick.labelsize':7.5,'ytick.labelsize':7.5,
        'legend.fontsize':7.8,'legend.frameon':False,'axes.linewidth':.6,
        'axes.spines.top':False,'axes.spines.right':False,'xtick.direction':'in','ytick.direction':'in',
        'xtick.major.width':.6,'ytick.major.width':.6,'xtick.major.size':2.5,'ytick.major.size':2.5,
        'pdf.fonttype':42,'svg.fonttype':'none','savefig.facecolor':'white','path.simplify':False})
    fig=plt.figure(figsize=(174/25.4,177/25.4))
    left=.095;right=.985;gap=.045;width=(right-left-2*gap)/3
    bottoms=[.657,.361,.065];height=.225
    axs=np.empty((3,3),dtype=object);insets=[]
    limits=[(-20,40),(-5,10),(-11.5,9)]
    ticks=[[-15,0,15],[-4,0,4,8],[-8,-4,0,4,8]]
    # Shared row scales; two distinct legends preserve the two scientific controls.
    for row,field in enumerate(FIELDS):
        methods=['F01','F03','F04'] if row==0 else ['A05','F04']
        for col,seq in enumerate(SEQ):
            ax=fig.add_axes([left+col*(width+gap),bottoms[row],width,height]);axs[row,col]=ax
            for method in methods:plot_line(ax,data[seq,method],seq,field,method)
            tmin=min(float(data[seq,m].time.min()-START[seq]) for m in methods)
            tmax=max(float(data[seq,m].time.max()-START[seq]) for m in methods)
            ax.set_xlim(min(0,tmin)-2,tmax+2);ax.set_ylim(limits[row]);ax.set_yticks(ticks[row])
            ax.set_xticks([0,100,200] if seq!='BY2O' else [0,150,300])
            ax.axhline(0,color='#969696',lw=.5,ls=(0,(2,2)),zorder=0)
            ax.set_title(f'({chr(97+row*3+col)})',loc='left',fontsize=9,fontweight='bold',pad=4)
            if col==0:ax.set_ylabel(['Heading error (deg)','Roll error (deg)','Pitch error (deg)'][row],labelpad=5)
            else:ax.tick_params(labelleft=False)
            if row==2:ax.set_xlabel('Time (s)',labelpad=4)
            if row==0:
                # Insets occupy reserved headroom, above the complete observed envelope.
                lo,hi=WINDOW[seq];ax.axvspan(lo,hi,ymax=.57,facecolor='#EAEAEA',edgecolor='none',linewidth=0,zorder=-1)
                ins=ax.inset_axes([.47,.70,.51,.27]);insets.append(ins)
                for m in ['F01','F04','F03']:plot_line(ins,data[seq,m],seq,field,m,zoom=True)
                ins.axhline(0,color='#AAAAAA',lw=.45,zorder=0)
                ins.set_xlim(lo,hi);ins.set_ylim(-14,7)
                ins.set_xticks([lo,hi]);ins.set_yticks([-10,0])
                ins.get_xticklabels()[0].set_ha('left')
                ins.get_xticklabels()[-1].set_ha('right')
                ins.tick_params(labelsize=6.1,length=2,pad=1.5)
                for spine in ins.spines.values():
                    spine.set_visible(True);spine.set_linewidth(.5);spine.set_edgecolor('#999999')
                ins.set_facecolor('white')
                # Check that the inset cannot hide any full-history line.
                floor=limits[row][0]+.70*(limits[row][1]-limits[row][0])
                xr=ax.get_xlim();span=(xr[0]+.47*(xr[1]-xr[0]),xr[0]+.98*(xr[1]-xr[0]))
                for m in methods:
                    d=data[seq,m];t=d.time-START[seq];mask=t.between(*span)
                    assert d.loc[mask,field].max()<floor,(seq,m,'inset overlaps data')
    for col,seq in enumerate(SEQ):
        fig.text(left+col*(width+gap)+width/2,.929,NAMES[seq],ha='center',va='center',fontsize=9)
    def handles(methods):
        return [Line2D([],[],color=STYLES[m]['color'],ls=STYLES[m]['ls'],lw=1.05,label=STYLES[m]['label']) for m in methods]
    fig.legend(handles=handles(['F01','F03','F04']),loc='upper center',bbox_to_anchor=(.545,.996),
               ncol=3,handlelength=2.6,columnspacing=1.45)
    fig.legend(handles=handles(['A05','F04']),loc='upper center',bbox_to_anchor=(.545,.640),
               ncol=2,handlelength=2.6,columnspacing=2.2)
    fig.canvas.draw()
    alignment=require_matplotlib_panel_alignment(fig,axes=list(axs.flat),
        panel_ids=list('abcdefghi'),row_groups=[list('abc'),list('def'),list('ghi')],
        column_groups=[list('adg'),list('beh'),list('cfi')],
        json_out=OUT/'qa/attitude.alignment.json',strict=True,tolerance_pt=1.5,gutter_tolerance_pt=1.5)
    fig.savefig(OUT/'preview'/f'{NAME}.png',dpi=300)
    with Image.open(OUT/'preview'/f'{NAME}.png') as im:im.convert('L').save(OUT/'preview'/f'{NAME}_gray.png')
    if a.final:
        fig.savefig(OUT/(NAME+'.pdf'),dpi=600)
        fig.savefig(OUT/(NAME+'.svg'),dpi=600)
        fig.savefig(OUT/(NAME+'.png'),dpi=600)
    metadata={'figure_id':NAME,'source_figures':['S9','S8'],'width_mm':174,'height_mm':177,
        'layout':'three scenes by heading/roll/pitch','heading_methods':['F01','F03','F04'],
        'tilt_methods':['A05','F04'],'inset_windows_elapsed_s':WINDOW,
        'line_gap_break_s':.1,'smoothing':False,'downsampling':False,
        'full_history_rasterized_dpi':600,'inset_lines_vector':True,
        'frozen_science_commit':'7d43b9af26120ed5dde21f53e515386361072ba6',
        'scientific_runs':0,'caption_status':'DRAFT_FOR_AUTHOR_DISCUSSION',
        'alignment_status':alignment.get('status',alignment.get('verdict')),
        'alignment_scope':'Nine main axes; the three different-scale heading insets are outside comparable groups.',
        'visual_review':'PENDING'}
    (OUT/f'{NAME}.json').write_text(json.dumps(metadata,ensure_ascii=False,indent=2)+'\n')
    plt.close(fig)
    print('Preview rendered; final exports:',a.final,flush=True)

if __name__=='__main__':main()
