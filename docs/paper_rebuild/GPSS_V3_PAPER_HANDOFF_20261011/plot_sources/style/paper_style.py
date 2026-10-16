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
