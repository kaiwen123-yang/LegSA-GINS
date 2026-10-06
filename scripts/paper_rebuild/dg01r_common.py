#!/usr/bin/env python3
"""DG01R roots, guarded reads, and deterministic tabular serialization."""
import os
os.environ.update(OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1')
import ast,csv,json,hashlib,datetime,math,re,subprocess,shutil
from pathlib import Path
from collections import defaultdict,Counter
import numpy as np
import pandas as pd
import yaml
from dg01_analysis import satellite,nearest,stats
W=Path(__file__).resolve().parents[2]
CFG=yaml.safe_load((W/'configs/paper_rebuild/DATA_PATHS.CLEAN3R4.local.yaml').read_text())['paths']
C=Path(CFG['clean_root']);D=C/'stages/CLEAN10_GNSS_RAW_DIAGNOSTIC/DG01';O=D.parent/'DG01R';R=W/'docs/paper_rebuild/hext/DG01R';S=Path(CFG['hx02_scratch']).parent/'DG01R'
EXT=Path(CFG['horizontal_literature_rtklib_root']);SEQ={'BY2':(1772784000.,66.,340.),'BY2H':(1772784000.,413.,683.),'BY2O':(1772780400.,3186.,3563.)}
PRE=json.loads((O/'PREFLIGHT.json').read_text());PINS={str(D/p):v['sha256'] for p,v in PRE['DG01_output_pins'].items()};PINS.update({x['path']:x['expected'] for x in PRE['raw_pins']});PINS.update({p:v['sha256'] for p,v in json.loads((D/'INPUT_SHA256.json').read_text()).items()});PINS.update(PRE['rtklib_tracked_sha256']);SOURCES={}
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def read(p):
 p=Path(p).resolve()
 if any(x in str(p).lower() for x in ['trace','.bag','.fpl']):raise RuntimeError('FORBIDDEN_INPUT '+str(p))
 digest=sha(p)
 if str(p) in PINS and PINS[str(p)]!=digest:raise RuntimeError('INPUT_SHA_MISMATCH '+str(p))
 SOURCES[str(p)]={'sha256':digest,'bytes':p.stat().st_size};return p
def alias(p):return str(p).replace(str(W),'<W>').replace(str(C),'<CLEAN_ROOT>').replace(CFG['raw_root'],'<RAW_ROOT>').replace(str(EXT),'<RTKLIB_ROOT>')
def save_sources():
 p=O/'INPUT_SHA256.json';d=json.loads(p.read_text()) if p.exists() else {};d.update(SOURCES);p.write_text(json.dumps(d,indent=2)+'\n');(R/'DG01R_INPUT_SHA256.json').write_text(json.dumps({alias(k):v for k,v in d.items()},indent=2)+'\n')
def log(s):
 with (O/'PROGRESS.txt').open('a') as f:f.write(datetime.datetime.now(datetime.timezone.utc).isoformat()+' '+s+'\n')
 print(s,flush=True)
def write(name,rows,repo=False):
 d=rows if isinstance(rows,pd.DataFrame) else pd.DataFrame(rows);p=(R if repo else O)/name;d.to_csv(p,index=False,float_format='%.17g',lineterminator='\n')
def load(name):return pd.read_csv(read(D/name),float_precision='round_trip')
def wrap(a):return np.asarray(a)-np.ceil(np.asarray(a)-.5)
def nav_ephemeris(s):
 ep=defaultdict(list)
 for r in [1,2]:
  p=next(Path(p) for p in PINS if '/'+s+'__RTKLIB__' in p and p.endswith('/gnss'+str(r)+'.nav'));lines=read(p).read_text().splitlines();i=next(i for i,l in enumerate(lines) if 'END OF HEADER' in l)+1
  while i<len(lines):
   l=lines[i];sy=l[0];n=4 if sy in ['R','S'] else 8;block=lines[i:i+n];i+=n
   if sy not in ['G','E','C','J']:continue
   vals=[float(l[j:j+19].replace('D','E')) for j in [23,42,61]]
   for ll in block[1:]:vals += [float(ll[j:j+19].replace('D','E')) if ll[j:j+19].strip() else 0 for j in [4,23,42,61]]
   ep[(sy,int(block[0][1:3]))].append(vals)
 return ep
def summarize(d,version):
 rows=[]
 for key,g in d.groupby(['sequence','gnss','signal','frequency_hz','fix_group'],dropna=False):
  a=g.fractional_cycles.to_numpy();a=a[np.isfinite(a)];z=np.mean(np.exp(2j*np.pi*a)) if len(a) else complex(np.nan,np.nan)
  row=dict(zip(['sequence','gnss','signal','frequency_hz','fix_group'],key));row.update(version=version,n_registered=len(g),n_missing=len(g)-len(a),**stats(a),p95_abs_cycles=np.percentile(abs(a),95) if len(a) else np.nan,frac_abs_gt025=np.mean(abs(a)>.25) if len(a) else np.nan,circular_mean_cycles=np.angle(z)/(2*np.pi),circular_sd_cycles=np.sqrt(-2*np.log(min(1,max(abs(z),1e-15))))/(2*np.pi) if len(a) else np.nan,source='DD_ALL_VERSIONS.csv.gz');rows.append(row)
 return rows
