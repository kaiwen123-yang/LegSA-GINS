from pathlib import Path
import os,re,csv,json,hashlib
G=Path('/mnt/g/LegSA-GINS-project');S=G/'clean_rebuild_202607/stages'
R=Path('/home/kaiwen/research/LegSA-GINS-WORKTREES/audit-code-xbpg-20261001')
O=G/'V3研究记录梳理_20261011/fusion'
roots=[p for p in S.iterdir() if p.is_dir() and p.name.startswith(('CLEAN2','CLEAN3','CLEAN4'))]
roots += [R/'docs/paper_rebuild/hext',R/'configs/paper_rebuild']
key=re.compile(r'huber|cauchy|tukey|igg3|barron|switchable|robust_family|oim_family',re.I)
hits=[]; searched=[]; counts={}; roles=[]
for root in roots:
    n=0
    for dp,dns,fns in os.walk(root):
        dns[:]=[x for x in dns if x not in ['.git','__pycache__'] and not re.search(r'(^RUNS$|^CASE|NATIVE_RUNS|OFFLINE_EVALUATION|ALGORITHM_RUNS|ABLATION_RUNS|RUN_[0-9]|ARCHIVE|SOURCE_SNAPSHOT)',x,re.I)]
        for name in fns:
            p=Path(dp)/name
            if p.suffix.lower() not in ['.md','.csv','.json','.yaml','.yml','.txt','.log','.jsonl']:continue
            # bounded metadata/log/summary search; no multi-GB epoch series.
            if p.stat().st_size>2_000_000:continue
            if any(q in name.lower() for q in ['error_series','nav.csv','innovation.csv','nis.csv','openat','strace']):continue
            b=p.read_bytes(); t=b.decode('utf-8-sig',errors='replace');n+=1
            ms=[(i+1,line[:600]) for i,line in enumerate(t.splitlines()) if key.search(line)]
            if ms:
                hits.append({'path':str(p),'line_matches':ms[:30],'match_count':len(ms),'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()})
    counts[str(root)]=n
    print('finished_root',str(root),n,flush=True)
print(json.dumps({'searched_files':sum(counts.values()),'hit_files':len(hits),'counts':counts},ensure_ascii=False))
(O/'BOUNDED_ROBUST_SEARCH.json').write_text(json.dumps({'scope':counts,'filters':'text metadata <=2MB; skip error/nav/innovation/nis/openat/strace; no solver/evaluator calls','hits':hits},ensure_ascii=False,indent=2))
for x in hits:print(x['path'],x['line_matches'][:2])

# Existing same-point tables: locate existing values and support, never transform new outputs.
same=[]
for sub in ['hext/FGO_COMPARISON','hext/FGO_REPRODUCTION_FIX_20261004','FGO_COMPLETE_AUDIT_20261004','GPSS_V3_FIGURES_20261008']:
    rt=R/'docs/paper_rebuild'/sub
    for p in rt.rglob('*'):
        if p.is_file() and p.suffix in ['.md','.csv','.json','.py'] and p.stat().st_size<2_000_000:
            b=p.read_bytes();t=b.decode('utf-8-sig',errors='replace')
            ms=[(i+1,l[:1200]) for i,l in enumerate(t.splitlines()) if (re.search(r'V3|LegSA',l,re.I) and re.search(r'GNSS1|POI|COMMON',l,re.I))]
            if ms:same.append({'path':str(p),'matches':ms[:20],'match_count':len(ms),'sha256':hashlib.sha256(b).hexdigest()})
(O/'EXISTING_SAME_POINT_SEARCH.json').write_text(json.dumps(same,ensure_ascii=False,indent=2))
print('same_point_hit_files',len(same))
