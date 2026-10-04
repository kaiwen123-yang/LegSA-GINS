"""Presentation-only redraw from saved evaluation CSVs. No solver/evaluator imports.

Every retained formal-window curve sample is drawn. The small gzipped CSVs are
column-only copies; numeric tokens retain their source decimal strings.
"""
import os
os.environ.update(MPLCONFIGDIR='/tmp/legsa_reframe_figures', OPENBLAS_NUM_THREADS='1')
import csv, gzip, hashlib, io, json
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

HERE = Path(__file__).resolve().parent
W = HERE.parents[4]
V = Path('/mnt/g/LegSA-GINS-project/clean_rebuild_202607/stages/CLEAN8_PROTOCOL_V3')
DATA = HERE / 'data'; DATA.mkdir(exist_ok=True)
WINDOWS = {'BY2': (66.,340.), 'BY2H': (413.,683.), 'BY2O': (3186.,3563.)}
INPUTS = []; FIGURES = []
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':17,'axes.titlesize':22,
 'axes.labelsize':17,'legend.fontsize':14,'axes.spines.top':False,'axes.spines.right':False,
 'axes.linewidth':1.1,'svg.fonttype':'none','pdf.fonttype':42,'path.simplify':False,
 'figure.facecolor':'white','axes.facecolor':'white','savefig.facecolor':'white'})
COLORS = {'F04':'#0072B2','LC01':'#D55E00'}

def sha(b): return hashlib.sha256(b).hexdigest()
def read_source(path, expected=None):
    path=Path(path); raw=path.read_bytes()
    plain=gzip.decompress(raw) if path.suffix=='.gz' else raw
    if expected: assert sha(raw)==expected or sha(plain)==expected,(path,expected)
    assert path.read_bytes()==raw, f'Input changed during read: {path}'
    INPUTS.append({'path':str(path),'file_sha256':sha(raw),'decompressed_sha256':sha(plain),
                   'file_bytes':len(raw),'unchanged_after_read':True})
    return list(csv.DictReader(io.StringIO(plain.decode('utf-8-sig'))))

def small_copy(name, rows, fields):
    s=io.StringIO(); out=csv.DictWriter(s,fieldnames=fields,lineterminator='\n')
    out.writeheader(); out.writerows({k:r[k] for k in fields} for r in rows)
    b=s.getvalue().encode(); p=DATA/(name+'.csv.gz'); p.write_bytes(gzip.compress(b,mtime=0))
    INPUTS[-1]['plot_copy']={'relative_path':str(p.relative_to(HERE)), 'rows':len(rows),
                            'columns':fields,'sha256':sha(p.read_bytes()),'plain_sha256':sha(b)}
    return pd.DataFrame([{k:r[k] for k in fields} for r in rows]).apply(pd.to_numeric)

def frame(ax):
    ax.grid(True,color='#D9DEE5',linewidth=.6,alpha=.75)
    ax.set_axisbelow(True)

def finish(fig,name,claim,role,caption):
    files=[]
    for ext in ['png','pdf','svg']:
        p=HERE/(name+'.'+ext)
        kw={'metadata':{'Date':None}} if ext=='svg' else {'metadata':{'CreationDate':None,'ModDate':None}} if ext=='pdf' else {}
        fig.savefig(p,dpi=300,bbox_inches='tight',pad_inches=.12,**kw)
        files.append({'path':p.name,'sha256':sha(p.read_bytes()),'bytes':p.stat().st_size})
    FIGURES.append({'id':name,'dominant_claim':claim,'panel_role':role,'caption':caption,
                    'exports':files,'all_saved_formal_samples_drawn':True})
    plt.close(fig)

def error_path(seq,method,ix):
    if method=='F04':
        run='RUN_00004' if seq=='BY2' else 'SEQUENCE_'+seq+'_F04'
        m=[x for x in ix if '/'+run+'/' in x['path'] and '/v3/' in x['path'] and 'error_series' in x['path']]
    else:
        m=[x for x in ix if 'error_series' in x['path'] and ((seq+'__LC01__' in x['path']) or (seq=='BY2' and '/LC01_EXT05A/' in x['path']))]
    assert len(m)==1,(seq,method)
    p=Path(m[0]['path'])
    if not p.exists() and p.with_suffix(p.suffix+'.gz').exists(): p=p.with_suffix(p.suffix+'.gz')
    return p,m[0]['sha256']

def main():
    pinpath=W/'docs/paper_rebuild/v3/uncertainty/UA01_INPUT_SHA256.json'
    pins=json.loads(pinpath.read_text())['inputs']
    original_main=read_source(V/'07_AGGREGATE/MAIN_TABLE_V3.csv')
    natural=read_source(V/'07C_FAILURE_FAMILY_CONFIG/FULL_ABLATION_TABLE_V3.csv')
    support=[]
    for seq,(a,b) in WINDOWS.items():
        ds={}
        for method in ['F04','LC01']:
            p,pin=error_path(seq,method,pins); rows=read_source(p,pin)
            rows=[r for r in rows if a<=float(r['time'])<=b]
            ds[method]=small_copy(seq+'_'+method+'_errors',rows,
                                  ['time','horizontal_err_m','yaw_err_deg','roll_err_deg','pitch_err_deg'])
        fig,axes=plt.subplots(2,1,figsize=(12,6.8),sharex=True)
        fig.subplots_adjust(left=.095,right=.99,top=.84,bottom=.16,hspace=.18)
        fig.suptitle(seq+' | Full-window position and heading errors',x=.09,ha='left',y=.985,fontweight='bold')
        for method in ['F04','LC01']:
            d=ds[method]
            start='CONTRACT_START' if seq=='BY2H' else 'FILE_START'
            sr=next(r for r in (natural if method=='F04' else original_main)
                    if r['sequence_id']==seq and r['method_id']==method
                    and (method=='F04' or r['start_convention']==start))
            denominator=int(sr['output_epoch_count'])
            assert int(sr['matched_epoch_count'])==len(d)
            support.append({'sequence':seq,'method':method,'matched':len(d),
                            'observed_output_denominator':denominator,'window_start_s':a,'window_end_s':b,
                            'scope':'saved matched/output; not nominal time-grid coverage'})
            label=('Proposed' if method=='F04' else 'Two-receiver IEKF')+f'  ({len(d):,}/{denominator:,})'
            for ax,key in zip(axes,['horizontal_err_m','yaw_err_deg']):
                # Break only at actual discontinuities; never bridge input/output gaps.
                t=d.time.to_numpy(); y=d[key].to_numpy().copy()
                cut=np.flatnonzero(np.diff(t)>.1)+1
                for i,part in enumerate(np.split(np.arange(len(t)),cut)):
                    ax.plot(t[part]-a,y[part],color=COLORS[method],lw=.7 if method=='F04' else .65,
                            alpha=.85,label=label if i==0 else None,zorder=3 if method=='F04' else 2)
        for ax in axes:
            frame(ax); ax.set_xlim(0,b-a)
            if seq=='BY2O':
                for left,right in [(3369.94,3411.95),(3495.94,3508.94)]:
                    ax.axvspan(left-a,right-a,color='#E6E6E6',zorder=0)
        axes[0].set_ylabel('Horizontal error (m)'); axes[1].set_ylabel('Yaw error (°)')
        axes[1].set_xlabel('Elapsed time from formal window start (s)')
        axes[0].legend(loc='upper left',bbox_to_anchor=(0,1.28),ncol=2,frameon=False)
        note='Saved evaluator v3; declared dual-antenna midpoint; shared-GNSS commercial reference.'
        if seq=='BY2H': note+='  IEKF geometric audit: FAIL.'
        fig.text(.095,.035,note,fontsize=11,color='#4B5563')
        finish(fig,'R01_'+seq+'_full_window',
          'Continuous errors and adverse excursions are visible throughout the original formal window.',
          'case illustration; position above, heading below',
          f'Original V3 F04 versus LC01 ({"CONTRACT_START" if seq=="BY2H" else "FILE_START"}); all saved matched samples are drawn without smoothing. Fractions use each method observed output denominator, not a nominal time grid, common support or independent sample count. No interpolation across gaps; no alignment or new scoring. '+note)

    with (DATA/'curve_support.csv').open('w',newline='') as f:
        wr=csv.DictWriter(f,fieldnames=list(support[0]),lineterminator='\n');wr.writeheader();wr.writerows(support)

    table=read_source(V/'07C_FAILURE_FAMILY_CONFIG/FULL_ABLATION_TABLE_V3.csv')
    fields=['sequence_id','method_id','effective_profile','horizontal_rmse_m','yaw_rmse_deg',
            'matched_epoch_count','output_epoch_count','unmatched_epoch_count','status','run_id']
    s=io.StringIO(); wr=csv.DictWriter(s,fieldnames=fields,lineterminator='\n');wr.writeheader();wr.writerows({k:r[k] for k in fields} for r in table)
    p=DATA/'natural_all_33.csv';p.write_text(s.getvalue())
    INPUTS[-1]['plot_copy']={'relative_path':str(p.relative_to(HERE)),'rows':len(table),'columns':fields,'sha256':sha(p.read_bytes())}
    methods=['F04','A03','A04','A05','A06','A07','A08','A09','F01','F02','F03']
    labels=['Proposed','Without raw Doppler','Without source weighting','Without roll/pitch prior',
            'Without body-velocity prior','Without both robot priors','Without weighting + robot priors',
            'Without Doppler + robot priors','GNSS/INS; no online dual heading',
            'Dual heading; receiver velocity off','Dual heading + receiver velocity']
    fig,axes=plt.subplots(1,2,figsize=(12.4,7.2),sharey=True)
    fig.subplots_adjust(left=.31,right=.985,bottom=.22,top=.83,wspace=.24)
    fig.suptitle('Natural sequences | All 11 original configurations',x=.04,ha='left',y=.975,fontweight='bold')
    y=np.arange(len(methods)); markers=['o','s','^']; colors=['#0072B2','#D55E00','#009E73']
    for col,key in enumerate(['horizontal_rmse_m','yaw_rmse_deg']):
        ax=axes[col]
        for seq,marker,color,offset in zip(WINDOWS,markers,colors,[-.18,0,.18]):
            vals=[float(next(r[key] for r in table if r['sequence_id']==seq and r['method_id']==m)) for m in methods]
            ax.scatter(vals,y+offset,s=62,marker=marker,color=color,label=seq,zorder=3)
        ax.set_xlabel('Horizontal RMSE (m)' if col==0 else 'Yaw RMSE (°)');frame(ax)
        ax.set_ylim(len(methods)-.5,-.8)
        for boundary in [4.5,7.5]: ax.axhline(boundary,color='#9CA3AF',lw=.9,ls='--')
    axes[0].set_yticks(y,labels,fontsize=12.5)
    axes[0].legend(loc='upper left',bbox_to_anchor=(0,1.13),ncol=3,frameon=False)
    fig.text(.04,.03,'All 33 runs completed. The first four contrasts remove one module; remaining rows change several inputs.\nNatural sequences show small, non-monotone differences: this chart does not establish universal module gains.',fontsize=11,color='#4B5563')
    finish(fig,'R02_natural_all_11_configurations',
            'The complete natural-sequence ablation retains non-monotone and small effects.',
            'single-module evidence separated from multi-input configurations',
            'Existing horizontal/yaw RMSE tokens from FULL_ABLATION_TABLE_V3, 33/33 COMPLETED; actual matched/output counts retained in the adjacent source CSV. Every method has the common historical dual-heading initialization. No statistics or evaluation recomputed.')
    receipt={'scope':'PRESENTATION_ONLY; original frozen V3 and historical LC01','no_solver_calls':True,
      'no_evaluator_calls':True,'raw_reference_payload_opens':0,'input_pin_index_sha256':sha(pinpath.read_bytes()),
      'inputs':INPUTS,'figures':FIGURES,'script_sha256':sha(Path(__file__).read_bytes())}
    (HERE/'BUILD_RECEIPT.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'figures':len(FIGURES),'sources':len(INPUTS),'output':str(HERE)}))

if __name__=='__main__': main()
