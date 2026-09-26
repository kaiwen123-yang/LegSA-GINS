"""HX-05 static publication figures from the manuscript data artifact."""
from __future__ import annotations
import json
from pathlib import Path
import numpy as np
from matplotlib.lines import Line2D
from matplotlib.transforms import blended_transform_factory

from ..publication import style,qa
from .hx05_common import dump,sha
from .hx05_tables import FAMILIES,SEQUENCES,finite

LABEL={'EXT01':'EXT01','EXT02':'EXT02','EXT03':'EXT03','EXT04_FAR':'EXT04 FAR','EXT04_PAR':'EXT04 PAR',
       'RTKLIB_UNMODIFIED_MOVING_BASE':'RTKLIB','LC02_GINAV':'GINav','HARTLEY_OFFICIAL':'Official LIT','LEG-DR':'LEG-DR'}
COLOR={'LC01':'#0072B2','EXT05C':'#009E73','LC02_GINAV':'#7B4F9D','HARTLEY_OFFICIAL':'#0072B2','LEG-DR':'#009E73',**style.COLORS}
FAMILY_LABEL=('Position\nnoise','Position\nbias','Position\noutage','Velocity\noutage','Heading\nnoise','Heading\noutage','Doppler','Time\nstamps','A2')


def find(data,method,config=None,supplement=False):
    rows=[r for r in data['supplement' if supplement else 'main'] if r['method']==method and (config is None or r['config']==config) and r['role']!='FILE_START_SUPPLEMENT']
    assert len(rows)==1,(method,config)
    return rows[0]


def cell(data,row,sequence):
    key=row['source_ids'].split(' | ')[SEQUENCES.index(sequence)]
    return data['cells'][key]['metrics'],key


def references(data,sequence,metric,ax):
    output=[]
    for method in ('F04','F02'):
        values,key=cell(data,find(data,method),sequence);v=values[metric]
        if finite(v):ax.axvline(v,color=style.COLORS[method],ls=style.LINESTYLES[method],lw=.9,zorder=1)
        output.append({'method':method,'metric':metric,'value':v,'source_id':key})
    return output


def rows_panel(ax,data,sequence,rows,metric,*,scale='linear',limits=None,reference_metric=None):
    entries=[]
    for i,row in enumerate(rows):
        values,key=cell(data,row,sequence);v=values.get(metric)
        if finite(v):
            x=float(v)*100 if metric=='availability' else float(v)
            ax.plot(x,i,'o',ms=3.6,color=COLOR.get(row['method'],'#4D4D4D'),zorder=3)
            if row['method']=='LC02_GINAV' and sequence=='BY2H':
                ax.text(.98,i+.26,'2/271 epochs',transform=blended_transform_factory(ax.transAxes,ax.transData),ha='right',va='center',fontsize=7)
        else:
            status='Diverged' if 'failure_detail' in values else 'No valid heading' if row['output_type']=='heading_only' else 'Unavailable'
            ax.text(.03,i,status,transform=blended_transform_factory(ax.transAxes,ax.transData),ha='left',va='center',fontsize=7,color='#555555')
        entries.append({'method':row['method'],'config':row['config'],'metric':metric,'value':v,'source_id':key})
    ax.set_yticks(range(len(rows)),[LABEL.get(r['method'],r['method']) for r in rows]);ax.set_ylim(len(rows)-.5,-.6)
    ax.set_xscale(scale)
    if limits:ax.set_xlim(*limits)
    ax.grid(axis='x',alpha=.65)
    refs=references(data,sequence,reference_metric,ax) if reference_metric else []
    return {'sequence':sequence,'entries':entries,'references':refs,'no_empty_panel':bool(entries)}


def fig02s(data):
    fig,axes=style.new_figure(5,3,10.1,hspace=.72,wspace=.95)
    headings=[r for r in data['main'] if r['output_type']=='heading_only']
    navigation=[find(data,m) for m in ('LC01','EXT05C','LC02_GINAV','F01')]
    relative=[find(data,'HARTLEY_OFFICIAL'),find(data,'LEG-DR')]
    definitions=[(headings,'availability','Availability (%)','linear',(0,105),None),
                 (headings,'valid_rmse_deg','Valid yaw RMSE (°)','log',(.1,200),'yaw_rmse_deg'),
                 (navigation,'yaw_rmse_deg','Yaw RMSE (°)','log',(.1,200),'yaw_rmse_deg'),
                 (navigation,'horizontal_rmse_m','Horizontal RMSE (m)','log',(.01,10),'horizontal_rmse_m'),
                 (relative,'position_drift_m_per_100m','Position drift (m) per 100 m','linear',None,None)]
    drifts=[cell(data,r,s)[0]['position_drift_m_per_100m'] for r in relative for s in SEQUENCES]
    low=min(0,min(float(x) for x in drifts if finite(x)));high=max(float(x) for x in drifts if finite(x));span=max(high-low,1)
    records=[]
    for row,(methods,metric,xlabel,scale,limits,ref) in enumerate(definitions):
        for col,seq in enumerate(SEQUENCES):
            ax=axes[row,col]
            if row==0:ax.set_title(seq,pad=17,fontweight='bold')
            rec=rows_panel(ax,data,seq,methods,metric,scale=scale,limits=(low-.05*span,high+.1*span) if row==4 else limits,reference_metric=ref)
            ax.set_xlabel(xlabel);style.panel_label(ax,chr(97+row*3+col),x=-.55,y=1.02)
            if row==4:ax.axvline(0,color='#999999',lw=.6)
            records.append(rec)
    handles=[Line2D([0],[0],color=style.COLORS[m],ls=style.LINESTYLES[m],label=m+' reference') for m in ('F04','F02')]
    fig.legend(handles=handles,loc='upper center',bbox_to_anchor=(.5,1.003),ncol=2)
    return fig,records


def fig02d(data):
    fig,axes=style.new_figure(3,1,7.9,hspace=.58)
    records=[];methods=('LC01','F02','F04');markers={'LC01':'o','F02':'s','F04':'D'}
    for j,(metric,label) in enumerate([('yaw_rmse_deg','Yaw RMSE (°)'),('horizontal_rmse_m','Horizontal RMSE (m)'),('up_rmse_m','Vertical RMSE (m)')]):
        ax=axes[j,0];entries=[];positive=[]
        for k,method in enumerate(methods):
            for i,family in enumerate(FAMILIES):
                st=data['degradation'][family][method][metric];x=i+(k-1)*.19
                if st['finite_n']:
                    med,upper=st['median'],st['p95'];assert upper>=med and med>0
                    ax.vlines(x,med,upper,color=COLOR[method],lw=1.1)
                    ax.plot(x,med,marker=markers[method],ms=4,color=COLOR[method],ls='none')
                    ax.plot(x,upper,marker='_',ms=5,color=COLOR[method],ls='none');positive.extend((med,upper))
                else:
                    transform=blended_transform_factory(ax.transData,ax.transAxes)
                    ax.plot(x,.025,marker='x',color=COLOR[method],ms=5,transform=transform,clip_on=False)
                    ax.text(x,.08,f'0/{st["registered_n"]}',color=COLOR[method],rotation=90,ha='center',va='bottom',fontsize=7,transform=transform)
                entries.append({'family':family,'method':method,'metric':metric,**st,'source_id':f'DEGRADATION.{family}.{method}'})
        ax.set_yscale('log');ax.set_ylim(min(positive)*.32,max(positive)*2);ax.set_xlim(-.55,8.55)
        ax.set_xticks(range(9),FAMILY_LABEL);ax.set_ylabel(label);ax.grid(axis='y',alpha=.7)
        style.panel_label(ax,chr(97+j),x=-.1,y=1.02)
        records.append({'metric':metric,'entries':entries,'no_empty_panel':bool(entries),'interval':'median to empirical P95; not confidence interval'})
    handles=[Line2D([0],[0],marker=markers[m],color=COLOR[m],label=m,lw=1) for m in methods]
    handles.append(Line2D([0],[0],marker='x',color='#555555',ls='none',label='No finite result (n/N shown)'))
    fig.legend(handles=handles,loc='upper center',bbox_to_anchor=(.5,1.005),ncol=4)
    return fig,records


def sfig_hx(data):
    rows=[find(data,'Hartley-S',supplement=True),find(data,'Hartley-LIT',supplement=True),
          find(data,'HARTLEY_OFFICIAL','OFF-LIT'),find(data,'HARTLEY_OFFICIAL','OFF-DEF',supplement=True),find(data,'LEG-DR')]
    names=['Port S','Port LIT','Official LIT','Official DEF','LEG-DR']
    colors=['#777777','#444444','#0072B2','#56B4E9','#009E73'];markers=['x','+','o','s','D']
    fig,axes=style.new_figure(2,3,5.2,hspace=.58,wspace=.95);records=[]
    for j,(metric,label) in enumerate([('position_drift_m_per_100m','Position drift (m) per 100 m'),('heading_drift_deg_per_min','Heading drift (°) per min')]):
        vals=[cell(data,r,s)[0].get(metric) for r in rows for s in SEQUENCES];numbers=[float(v) for v in vals if finite(v)]
        lo=min(0,min(numbers));hi=max(numbers);spread=max(hi-lo,1)
        for col,seq in enumerate(SEQUENCES):
            ax=axes[j,col];entries=[]
            for i,r in enumerate(rows):
                value,key=cell(data,r,seq);v=value.get(metric)
                if finite(v):ax.plot(v,i,marker=markers[i],color=colors[i],ms=4,ls='none')
                else:ax.text(.04,i,'Initialization stopped',fontsize=7,va='center',transform=blended_transform_factory(ax.transAxes,ax.transData))
                entries.append({'method':r['method'],'config':r['config'],'value':v,'metric':metric,'source_id':key})
            ax.set_yticks(range(5),names);ax.set_ylim(4.6,-.6);ax.set_xlim(lo-.07*spread,hi+.1*spread)
            ax.axvline(0,color='#999999',lw=.6);ax.grid(axis='x',alpha=.65);ax.set_xlabel(label)
            if j==0:ax.set_title(seq,pad=15,fontweight='bold')
            style.panel_label(ax,chr(97+j*3+col),x=-.55,y=1.02)
            records.append({'sequence':seq,'entries':entries,'no_empty_panel':True})
    fig.legend(handles=[Line2D([0],[0],marker=m,color=c,ls='none',label=n) for n,c,m in zip(names,colors,markers)],loc='upper center',bbox_to_anchor=(.5,1.02),ncol=3)
    return fig,records


CAPTIONS='''# Caption drafts

**FIG02S. External comparisons on three sequences.** Columns show BY2, BY2H and BY2O. Rows separate method-native heading availability, heading RMSE on valid epochs, navigation yaw RMSE, navigation horizontal RMSE, and relative-position drift per 100 m. F04 and F02 appear as reference lines only on panels with the corresponding archived RMSE metric. Availability denominators are method-native paired epochs; navigation and relative-pose panels retain their own evaluation support. GINav has two evaluated epochs out of 271 integer-second slots on BY2H and is marked as diverged on BY2 and BY2O. Unavailable values are labelled rather than drawn as zero. Relative-pose estimates receive one yaw-and-translation alignment over the first 10 s; the signed drift is an OLS slope against cumulative reference distance, not endpoint error. LEG-DR uses onboard attitude and contact kinematics and is an input-information reference, not a literature method.

**FIG02D. Degradation-family results under the corrected WGS84 consistency audit.** Points show the median and upper caps the empirical 95th percentile across finite runs for LC01, F02 and F04. The intervals describe between-case spread, not confidence intervals. Crosses and n/N annotations identify groups with no finite results; these runs remain in the registered denominator. LC01 has 18/18 native divergence cases in the position-noise family. Paired differences in the accompanying table include only cases finite for both methods. In the timestamp family, LC01 shifts position epochs, whereas F04 has no valid heading throughout the V3 run; the input exposure differs. Original native outputs and frozen evaluator scientific outputs are unchanged by the audit correction.

**SFIG-HX. Hartley implementations and a kinematic input reference.** The custom Hartley ports, the unchanged official Hartley library with OFF-LIT and OFF-DEF configurations, and LEG-DR are shown on the three sequences. Rows show signed position-drift slopes per 100 m and signed heading-drift slopes per minute after the same initial 10 s yaw-and-translation alignment. The custom ports did not pass accuracy validation and their BY2H initialization stopped; these outcomes remain visible. LEG-DR conditions on onboard Go2 attitude, so its result is not an independent bound on input accuracy. All errors are relative to the recorded reference.
'''


def render(data_path,out):
    data=json.loads(Path(data_path).read_text());out=Path(out);out.mkdir(parents=True,exist_ok=False)
    manifest=[];checks=[];hashes={}
    for name,fn in [('FIG02S',fig02s),('FIG02D',fig02d),('SFIG-HX',sfig_hx)]:
        fig,bindings=fn(data)
        checks.extend(qa.check_figure(fig,name));files=style.save_figure(fig,out,name)
        checks.extend(qa.check_png(Path(files['png']),name));hashes[name]=qa.average_hash(Path(files['png']))
        checks.append({'figure_id':name,'check':'all_panels_bound_to_source_cells','pass':bool(all(r['no_empty_panel'] for r in bindings)),'detail':f'{len(bindings)} panels; values and unavailable states retained'})
        checks.append({'figure_id':name,'check':'legend_present','pass':bool(fig.legends),'detail':'explicit figure legend and method axis labels'})
        files['bindings']=bindings;manifest.append(files)
        import matplotlib.pyplot as plt
        plt.close(fig)
    duplicates=qa.duplicate_pairs(hashes)
    checks.append({'figure_id':'ALL','check':'not_duplicate_rasters','pass':not duplicates,'detail':str(duplicates)})
    for row in checks:row['pass']=bool(row['pass'])
    dump(out/'FIGURE_MANIFEST.json',{'data_sha256':sha(data_path),'figures':manifest})
    dump(out/'MACHINE_QA.json',{'passed':all(r['pass'] for r in checks),'checks':checks,'actual_visual_review':'PENDING'})
    (out/'CAPTIONS_HX05.md').write_text(CAPTIONS)
    assert all(r['pass'] for r in checks),'HX05_FIGURE_MACHINE_QA_FAILED'
    return manifest
