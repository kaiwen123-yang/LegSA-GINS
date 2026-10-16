from pathlib import Path
import json,subprocess,sys
import pandas as pd
import fitz
OUT=Path(__file__).resolve().parent
SKILL=Path('/mnt/c/Users/ykw/.codex/skills/nature-figure/scripts')
REG=Path('/mnt/g/LegSA-GINS-project/clean_rebuild_202607/stages/CLEAN8_PROTOCOL_V3/00_CONTROL/ORIGINAL_V3_METADATA/00_PREREGISTRATION/REGISTRY.json')
registry=json.loads(REG.read_text());core=pd.read_csv(OUT/'tables/CORE5951.csv')
rows={r['case_id']:r['case_meta'] for r in registry if r['case_id'] in set(core.case_id)}
assert len(rows)==541,len(rows)
meta=pd.DataFrame(rows.values());meta.to_csv(OUT/'tables/REGISTERED_541_CASE_DEFINITIONS.csv',index=False)
types=meta.sort_values('case_id').drop_duplicates('degradation_type_id');types.to_csv(OUT/'tables/REGISTERED_61_TYPE_DEFINITIONS.csv',index=False)
print(meta.groupby('case_family')[['seed_effective','independent_realization']].value_counts().to_string())
results=[]
for p in sorted((OUT/'figures').glob('*.pdf')):
    text=subprocess.run([sys.executable,str(SKILL/'audit_pdf_text.py'),str(p),'--min-pt','8','--json'],capture_output=True,text=True)
    (OUT/'qa'/f'{p.stem}.text.json').write_text(text.stdout)
    col=subprocess.run([sys.executable,str(SKILL/'audit_figure_collisions.py'),str(p),'--json-out',str(OUT/'qa'/f'{p.stem}.collision.json')],capture_output=True,text=True)
    (OUT/'qa'/f'{p.stem}.collision.log').write_text(col.stdout+col.stderr)
    report=json.loads((OUT/'qa'/f'{p.stem}.collision.json').read_text())
    results.append({'figure':p.stem,'pdf_text_exit':text.returncode,'collision_exit':col.returncode,'collision_verdict':report.get('verdict',report.get('status'))})
    print(p.stem,'text',text.returncode,'collision',col.returncode,report.get('verdict',report.get('status')),flush=True)
validation=subprocess.run([sys.executable,str(SKILL/'validate_figure.py'),str(OUT/'build_revised_aiding.py'),'--json'],capture_output=True,text=True)
(OUT/'qa/source_validation.json').write_text(validation.stdout)
(OUT/'qa/AUDIT_INDEX.json').write_text(json.dumps(results,indent=2))
