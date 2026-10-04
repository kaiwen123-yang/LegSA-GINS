"""Independent CSV-to-figure utilities; no scientific pipeline imports or writes."""
import os
os.environ.update(MPLCONFIGDIR='/tmp/legsa_reframe_figures', OPENBLAS_NUM_THREADS='1')
import csv,gzip,hashlib,io,json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

def sha(b): return hashlib.sha256(b).hexdigest()
def setup():
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':17,'axes.titlesize':22,
     'axes.labelsize':17,'legend.fontsize':14,'axes.spines.top':False,'axes.spines.right':False,
     'axes.linewidth':1.1,'svg.fonttype':'none','pdf.fonttype':42,'path.simplify':False,
     'figure.facecolor':'white','axes.facecolor':'white','savefig.facecolor':'white'})
def frame(ax):
    ax.grid(True,color='#D9DEE5',linewidth=.6,alpha=.75);ax.set_axisbelow(True)
def segments(t,limit=.1):
    return np.split(np.arange(len(t)),np.flatnonzero(np.diff(t)>limit)+1)
def line(ax,t,y,limit=.1,**kw):
    for i,part in enumerate(segments(t,limit)):
        k=dict(kw)
        if i: k.pop('label',None)
        ax.plot(t[part],y[part],**k)
class Book:
    def __init__(self,folder):
        self.root=Path(folder); self.data=self.root/'data'; self.data.mkdir(parents=True,exist_ok=True)
        self.inputs=[];self.figures=[]
    def rows(self,path,pin=None):
        p=Path(path); raw=p.read_bytes(); plain=gzip.decompress(raw) if p.suffix=='.gz' else raw
        if pin: assert pin in (sha(raw),sha(plain)),(p,pin)
        assert raw==p.read_bytes(),f'Input changed during read: {p}'
        self.inputs.append({'path':str(p),'file_sha256':sha(raw),'decompressed_sha256':sha(plain),
                            'bytes':len(raw),'unchanged_after_read':True})
        return list(csv.DictReader(io.StringIO(plain.decode('utf-8-sig'))))
    def json(self,path):
        p=Path(path);b=p.read_bytes();assert b==p.read_bytes()
        self.inputs.append({'path':str(p),'file_sha256':sha(b),'bytes':len(b),'unchanged_after_read':True})
        return json.loads(b)
    def copy(self,name,rows,fields=None):
        fields=fields or list(rows[0]);s=io.StringIO();wr=csv.DictWriter(s,fieldnames=fields,lineterminator='\n')
        wr.writeheader();wr.writerows({k:r[k] for k in fields} for r in rows)
        b=s.getvalue().encode();p=self.data/(name+'.csv.gz');p.write_bytes(gzip.compress(b,mtime=0))
        self.inputs[-1]['plot_copy']={'path':str(p.relative_to(self.root)),'sha256':sha(p.read_bytes()),
                                     'plain_sha256':sha(b),'rows':len(rows),'columns':fields}
        return pd.DataFrame([{k:r[k] for k in fields} for r in rows])
    def figure(self,fig,name,claim,caption,role='claim-supporting evidence',**extra):
        files=[]
        for ext in ['png','pdf','svg']:
            p=self.root/(name+'.'+ext)
            kw={'metadata':{'Date':None}} if ext=='svg' else {'metadata':{'CreationDate':None,'ModDate':None}} if ext=='pdf' else {}
            fig.savefig(p,dpi=300,bbox_inches='tight',pad_inches=.12,**kw)
            files.append({'path':p.name,'sha256':sha(p.read_bytes()),'bytes':p.stat().st_size})
        self.figures.append({'id':name,'dominant_claim':claim,'caption':caption,'panel_role':role,'exports':files,**extra})
        plt.close(fig)
    def seal(self,script,**extra):
        j={'scope':'Presentation-only existing CSV redraw','no_solver_calls':True,'no_evaluator_calls':True,
           'raw_reference_payload_opens':0,'script_sha256':sha(Path(script).read_bytes()),
           'utilities_sha256':sha(Path(__file__).read_bytes()),'inputs':self.inputs,'figures':self.figures,**extra}
        (self.root/'BUILD_RECEIPT.json').write_text(json.dumps(j,ensure_ascii=False,indent=2)+'\n')
        print(json.dumps({'figures':len(self.figures),'sources':len(self.inputs),'output':str(self.root)}))
