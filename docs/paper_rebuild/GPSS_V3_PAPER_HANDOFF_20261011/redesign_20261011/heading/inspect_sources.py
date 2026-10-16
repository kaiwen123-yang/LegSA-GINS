from pathlib import Path
import json, pandas as pd, fitz
O=Path(__file__).parent
root=Path('/mnt/g/LegSA-GINS-project/clean_rebuild_202607/stages')
records=json.loads((root/'CLEAN8_PROTOCOL_V3/FINAL_RUN_RECORDS.json').read_text())
selected=[r for r in records if r.get('configuration_id')=='F04' and r.get('case_id')=='C00']
print('V3NATURAL',json.dumps(selected,ensure_ascii=False)[:16000])
for d in [root/'CLEAN7_T5A_HEADING_SENSITIVITY/T5A_R/01_EPOCH_SETS',root/'CLEAN7_T5A_HEADING_SENSITIVITY/01_EPOCH_SETS',root/'CLEAN7_T5A_HEADING_SENSITIVITY/T5A_R/05_AGGREGATE']:
 for p in d.rglob('*.csv'):
  x=pd.read_csv(p); print('FILE',str(p),len(x),list(x),x.head(1).to_dict('records'))
lib=Path('/mnt/g/LegSA-GINS-project/论文')
papers=['Constrained_Wrapped_Least_Squares_A_Tool_for_High-Accuracy_GNSS_Attitude_Determination.pdf','GPS_BDS_Dual-Antenna_Attitude_Determination_With_Baseline-Length_Constrained_Ambiguity_Resolution_Method_and_Performance_Evaluation.pdf','s00190-010-0380-8.pdf','1805.10410v1.pdf']
pdfo=O/'literature';pdfo.mkdir(exist_ok=True)
for name in papers:
 doc=fitz.open(lib/name);txt=[];found=[]
 for i,p in enumerate(doc):
  t=p.get_text();txt.append(t)
  if ('Fig.' in t or 'Figure' in t) and ('error' in t.lower() or 'observab' in t.lower() or 'success' in t.lower()):found.append(i)
 (pdfo/(Path(name).stem+'.txt')).write_text('\n'.join(txt))
 picks=found[-2:] if found else [0]
 for i in picks:doc[i].get_pixmap(matrix=fitz.Matrix(1.3,1.3)).save(pdfo/(Path(name).stem+f'_p{i+1}.png'))
 print('PAPER',name,'pages',len(doc),'rendered',[i+1 for i in picks])
