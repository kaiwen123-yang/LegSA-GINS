from pathlib import Path
import pandas as pd,numpy as np,json
R=Path('/mnt/g/LegSA-GINS-project');N=R/'V3五问题论文组图_20261011/navigation/data';F=R/'V3论文组图_20261008/focused_20261011/comparison/data';O=Path(__file__).parent
readout={}
for name in ['BY2_OISAM_STRICT_states.csv.gz','BY2_OISAM_SEGMENTED_states.csv.gz','BY2_OISAM_SEGMENTED_GNSS1_full.csv.gz','BY2_V3_POI_full.csv.gz']:
 p=F/name;d=pd.read_csv(p);readout[name]={'rows':len(d),'columns':list(d),'first':d.head(1).to_dict('records')};print(name,readout[name],flush=True)
for root in [R/'clean_rebuild_202607/stages/CLEAN5_DEGSUBSET_BY2/09_HORIZONTAL_V3/LC01_EXT05A',R/'clean_rebuild_202607/stages/CLEAN5_DEGSUBSET_BY2/09_HORIZONTAL_V3/EXT05C']:
 print('LEGACY',root,[str(p.relative_to(root)) for p in root.rglob('*') if p.is_file() and any(w in p.name.lower() for w in ['nav','native','summary'])],flush=True)
native=pd.read_csv(N/'LC_NATIVE_TABLE_READ.csv');print('LCnotes')
for _,row in native.iterrows():
 if row.sequence_id in ['BY2','BY2H']:
  print(row.sequence_id,row.method_id,row.start_convention,row.error_series_source,json.loads(row.notes),flush=True)
ex=pd.read_csv(N/'EXPERIMENTS.csv')
print('GINAV',ex[ex.method.str.contains('GINav',na=False)][['sequence','native_record','error_series']].to_dict('records'),flush=True)
for _,row in ex[ex.method.str.contains('GINav',na=False)].iterrows():
 p=Path(row.native_record);j=json.loads(p.read_text());print('GINAV_RUN',row.sequence,j,flush=True)
fgo=Path('/home/kaiwen/research/LegSA-GINS-SCRATCH/FGO_REPRODUCTION_FIX_20261004/FGO_REPRODUCTION_FINAL_20261004T054410Z')
for m in ['WEN_TC','GNC']:
 p=fgo/'runs/BY2'/m/'PAPER_CONTRACT';print('FGO',m,[str(q.name) for q in p.iterdir()],flush=True)
 for name in ['STATES.csv','RUN.json']:
  q=p/name
  if q.exists():
   d=pd.read_csv(q) if name.endswith('csv') else json.loads(q.read_text());print(name,{'rows':len(d),'columns':list(d),'first':d.head(1).to_dict('records')} if isinstance(d,pd.DataFrame) else d,flush=True)
(O/'TRAJECTORY_INVENTORY.json').write_text(json.dumps(readout,ensure_ascii=False,indent=2))
