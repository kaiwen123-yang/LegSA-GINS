"""Publication-only helpers. No estimator or evaluator imports or calls."""
import os
os.environ.update(OMP_NUM_THREADS='1', MKL_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', MPLCONFIGDIR=str(__import__('pathlib').Path(__file__).resolve().parents[1] / '_build'), PYTHONDONTWRITEBYTECODE='1')
import sys, csv, json, hashlib, importlib.util
from pathlib import Path
W = Path(__file__).resolve().parents[4]
P = W / 'paper_package/gpss_v0'
V = Path('/mnt/g/LegSA-GINS-project/clean_rebuild_202607/stages/CLEAN8_PROTOCOL_V3')
H = W / 'docs/paper_rebuild/hext/HX05'
U = W / 'docs/paper_rebuild/v3/uncertainty'
INPUTS = []
def record(p):
    p=Path(p).resolve()
    assert not any(x in str(p).lower() for x in ['.bag','.fpl','/raw/','/raw_data/']),p
    assert 'trace' not in p.name.lower(),p
    b=p.read_bytes(); rec={'path':str(p),'sha256':hashlib.sha256(b).hexdigest(),'bytes':len(b)}
    INPUTS.append(rec)
    log=P/'READ_FILES.json'; old=json.loads(log.read_text()) if log.exists() else []
    old=[x for x in old if x['path']!=str(p)];old.append(rec)
    log.write_text(json.dumps(sorted(old,key=lambda x:x['path']),indent=2)+'\n')
    return p
def readcsv(p):
    return list(csv.DictReader(record(p).open()))
def writecsv(p, rows, fields=None):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields or list(rows[0]),lineterminator='\n');w.writeheader();w.writerows(rows)
def module(name):
    path=W/'src/legsa_gins/paper_rebuild/publication'/f'{name}.py';record(path)
    spec=importlib.util.spec_from_file_location('ms01_'+name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
def plot_setup():
    import matplotlib
    matplotlib.use('Agg')
    style=module('style');style.apply_rcparams()
    import matplotlib.pyplot as plt
    return plt
COLORS={'F01':'#4D4D4D','F02':'#E69F00','F03':'#56B4E9','A04':'#CC79A7','F04':'#D55E00','LC01':'#0072B2'}
STYLES={'F01':':','F02':'--','F03':':','A04':'-.','F04':'-','LC01':'--'}
def finish(fig, num, status='REDRAWN', panel='all'):
    qa=module('qa');checks=qa.check_figure(fig,num)
    for ext in ['png','pdf','svg']:
        fig.savefig(P/'figures'/f'{num}.{ext}',dpi=max(600,4097/fig.get_figwidth()))
    checks+=qa.check_png(P/'figures'/f'{num}.png',num)
    for c in checks:c['pass']=bool(c['pass'])
    (P/'figures'/f'{num}_QA.json').write_text(json.dumps(checks,indent=2)+'\n')
    assert all(x['pass'] for x in checks),checks
    row={'manuscript_figure':num,'panel':panel,'status':status,'source_or_script':'figures/scripts/'+Path(sys.argv[0]).name,'data_sources':';'.join(x['path'] for x in INPUTS),'data_sha256':';'.join(x['sha256'] for x in INPUTS),'caption_source':('SUPPLEMENT_GPSS_v0.md' if num.startswith('S') else 'MANUSCRIPT_GPSS_v0.md'),'qa_notes':f'{len(checks)}/{len(checks)} machine checks; raster review recorded in report'}
    mp=P/'FIGURE_MAP.csv';old=list(csv.DictReader(mp.open())) if mp.exists() else [];old=[r for r in old if r['manuscript_figure']!=num];old.append(row);writecsv(mp,old)
    print(num,'QA',len(checks),'PASS')
def panel(ax,letter):
    ax.text(-.14,1.03,'('+letter+')',transform=ax.transAxes,fontsize=9,fontweight='bold')
def error_path(seq,method):
    ix=json.loads(record(U/'UA01_INPUT_SHA256.json').read_text())['inputs']
    if method=='LC01':
        matches=[x for x in ix if 'error_series' in x['path'] and ((seq+'__LC01__' in x['path']) or (seq=='BY2' and '/LC01_EXT05A/' in x['path']))]
    else:
        runs=readcsv(W/'docs/paper_rebuild/v3/ERROR_SERIES_RETENTION_INDEX.csv')
        run=next(r['run_id'] for r in runs if r['sequence_id']==seq and r['method_id']==method and (r['case_id']=='C00_clean_normal' or r['domain']=='SEQUENCE'))
        matches=[x for x in ix if 'error_series' in x['path'] and '/'+run+'/' in x['path'] and '/v3/' in x['path']]
    assert len(matches)==1,(seq,method,matches)
    p=record(matches[0]['path']); assert INPUTS[-1]['sha256']==matches[0]['sha256'];return p
def error_data(seq,method):
    import pandas as pd
    df=pd.read_csv(error_path(seq,method))
    a,b={'BY2':(66,340),'BY2H':(413,683),'BY2O':(3186,3563)}[seq]
    return df[(df.time>=a)&(df.time<=b)]
