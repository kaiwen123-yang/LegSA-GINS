from pathlib import Path
import pandas as pd, gzip, json, re
R=Path('/mnt/g/LegSA-GINS-project/clean_rebuild_202607/stages/CLEAN8_PROTOCOL_V3')
root=Path('/mnt/g/LegSA-GINS-project/V3五问题论文组图_20261011/heading')
for seq,run in [('BY2','RUN_00004'),('BY2H','V3R_CONTINUATION/SEQUENCE_BY2H_F04'),('BY2O','V3R_CONTINUATION/SEQUENCE_BY2O_F04')]:
 d=R/'03_NATIVE'/run
 print('RUN',seq,d,d.exists())
 if not d.exists():continue
 cfg=(d/'V3_RUNTIME_CONFIG.yaml').read_text();m=re.search(r'gnsspath:\s*"([^"]+)"',cfg)
 p=Path(m.group(1));a=pd.read_csv(p,sep=r'\s+',header=None,comment='#');print('PROVIDER',p,a.shape,a.head(1).to_dict('records'))
 tp=d/'PORT_GNSS_UPDATE_TRACE.csv.gz'
 if not tp.exists():tp=d/'PORT_GNSS_UPDATE_TRACE.csv'
 tr=pd.read_csv(tp);print('TRACE',len(tr),list(tr),tr.head(2).to_dict('records'))
 x=pd.read_csv(root/f'data/{seq}_V0_full_saved_heading.csv.gz');print('EXT',len(x),list(x),x.head(1).to_dict('records'))
 ((Path(__file__).parent)/(seq+'_input_path.json')).write_text(json.dumps({'provider':str(p),'native':str(d)}))
