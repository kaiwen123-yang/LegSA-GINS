from pathlib import Path
import json,pandas as pd
P=Path(__file__).resolve().parent
ROOT=Path('/mnt/g/LegSA-GINS-project/clean_rebuild_202607/stages/CLEAN8_PROTOCOL_V3')
rows=[]
for rid in ['RUN_02985','RUN_03183','RUN_03381']:
    run=ROOT/'03_NATIVE/V3R_CONTINUATION'/rid
    line=next(x for x in (run/'V3_RUNTIME_CONFIG.yaml').read_text().splitlines() if x.startswith('gnsspath:'))
    original=Path(line.split('"')[1]);tail=str(original).split('CLEAN8_PROTOCOL_V3/',1)[1]
    candidates=[original,ROOT/tail,ROOT/'00_CONTROL/ORIGINAL_V3_METADATA'/tail]
    tr=pd.read_csv(run/'PORT_GNSS_UPDATE_TRACE.csv')
    weight=pd.read_csv(run/'SOURCE_AWARE_WEIGHT_TRACE.csv.gz')
    rows.append({'run_id':rid,'provider_candidates':[{'path':str(x),'exists':x.exists()} for x in candidates],
                 'update_trace_rows':len(tr),'update_trace_columns':tr.columns.tolist(),
                 'yaw_updated':int(tr.yaw_update.eq(1).sum()),'yaw_not_updated':int(tr.yaw_update.eq(0).sum()),
                 'yaw_residual_nonmissing':int(tr.yaw_residual_deg.notna().sum()),'weight_trace_columns':weight.columns.tolist()})
    tr.to_csv(P/'data'/f'{rid}_ACTUAL_GNSS_UPDATE_TRACE.csv',index=False)
(P/'qa/RETAINED_HEADING_INPUT_READOUT.json').write_text(json.dumps(rows,indent=2),encoding='utf8')
print(json.dumps(rows,indent=2))
