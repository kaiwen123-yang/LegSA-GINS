"""Locate an executed spike by comparing two existing, hash-verified inputs."""
from pathlib import Path
import json,hashlib,shutil
import pandas as pd,numpy as np
P=Path(__file__).resolve().parent
native=Path('/mnt/g/LegSA-GINS-project/clean_rebuild_202607/stages/CLEAN8_PROTOCOL_V3/03_NATIVE/RUN_00004')
cfg=(native/'V3_RUNTIME_CONFIG.yaml').read_text()
src=Path(next(x for x in cfg.splitlines() if x.startswith('gnsspath:')).split('"')[1])
summary=json.loads((native/'V3_NATIVE_SUMMARY.json').read_text())
h=hashlib.sha256(src.read_bytes()).hexdigest();assert h==summary['provider_hashes']['gnsspath']
shutil.copy2(src,P/'data/CLEAN_ORIGINAL_GNSS18.gnss')
clean=pd.read_csv(src,sep=r'\s+',header=None);bad=pd.read_csv(P/'data/RUN_03381_ORIGINAL_GNSS18.gnss',sep=r'\s+',header=None)
assert len(clean)==len(bad)==1510
assert np.array_equal(clean[0].round(6).to_numpy(),bad[0].round(6).to_numpy())
delta=(bad[13]-clean[13]+180)%360-180
spike=np.isclose(np.abs(delta),10,atol=2e-5,rtol=0)
assert np.all(np.isclose(delta,0,atol=2e-5,rtol=0)|spike)
full=pd.DataFrame({'receiver_time_s':bad[0],'elapsed_s':bad[0]-66,'clean_heading_deg':clean[13],'perturbed_heading_deg':bad[13],'executed_signed_change_deg':delta,'is_10deg_spike':spike})
full.to_csv(P/'tables/F10_D35_ALL_INPUT_DIFFERENCES.csv',index=False)
starts=spike&~pd.Series(spike).shift(1,fill_value=False).to_numpy()
eligible=full[starts&(full.elapsed_s>=40)&(full.elapsed_s<274)]
chosen=eligible.iloc[0]
start_index=int(chosen.name);end_index=start_index
while end_index+1<len(full) and bool(spike[end_index+1]):end_index+=1
t=float(chosen.elapsed_s);event_end=float(full.iloc[end_index].elapsed_s+.2)
event={'case_id':'D35_seed_00','source_run':'RUN_03381','clean_source':str(src),'clean_sha256':h,'clean_recorded_sha256':summary['provider_hashes']['gnsspath'],'compared_input_rows':1510,'timestamp_key_matches':1510,'spike_rows':int(spike.sum()),'first_selected_event_elapsed_s':t,'last_spike_row_elapsed_s':float(full.iloc[end_index].elapsed_s),'event_display_end_s':event_end,'detail_start_elapsed_s':t-5,'detail_end_elapsed_s':t+5,'signed_change_deg':float(chosen.executed_signed_change_deg),'selection_rule':'First contiguous executed ±10-degree input-change episode beginning at or after elapsed40s in the evaluation window; display5s before and5s after its start. Selected from input differences only, not from reference or output errors.','reconstruction':False,'new_random_sampling':False}
(P/'F10_SPIKE_EVENT_SELECTION.json').write_text(json.dumps(event,indent=2),encoding='utf8')
print(json.dumps(event,indent=2))
