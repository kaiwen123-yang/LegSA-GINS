"""Select and format authorized publication sources; never re-evaluate a run."""
from common import *
from display_evidence import publication_budget_rows
import re, yaml, collections
MAP=[]
COMPRESSED_TABLE_IDS={'T03_fault_families':'S16a','T04_nominal_navigation':'3;S11a','T05_by2o_segments':'4','T05b_heading_segments':'S16b','T06_ladder_results':'S11b','T07_external_methods':'S13a','T08_external_faults':'S13b'}
def fmt(v):
    try:
        if str(v).strip() in ('','nan'):return 'Not reported'
        n=float(v)
        return f'{n:.3f}' if '.' in str(v) or 'e' in str(v).lower() else str(v)
    except (ValueError,TypeError):return str(v)
def table(id,name,rows,sources,derivation):
    id=COMPRESSED_TABLE_IDS.get(name,id)
    path='tables/'+name+'.csv';writecsv(P/path,[{k:fmt(v) for k,v in r.items()} for r in rows]);MAP.append(dict(manuscript_table=id,output_csv=path,source_files=';'.join(str(s) for s in sources),derivation=derivation))
main=readcsv(V/'07_AGGREGATE/MAIN_TABLE_V3.csv')
ladder=['F01','F02','F03','A04','F04'];seqs=['BY2','BY2H','BY2O']
def mainrow(seq,m):
    found=[r for r in main if r['sequence_id']==seq and r['method_id']==m and (r['config']=='PROTOCOL_V3' or r['start_convention']==('CONTRACT_START' if seq=='BY2H' else 'FILE_START'))]
    assert len(found)==1,(seq,m);return found[0]
ext=readcsv(H/'EXTERNAL_THREE_SEQUENCE_MANUSCRIPT.csv')
num=lambda s,k:re.search(re.escape(k)+r'=([-+\d.eE]+)',s).group(1)
unc=record(U/'UNC01_UNCERTAINTY_BUDGET.md');ut=unc.read_text()
speeds=re.search(r'mean speed ([\d.]+) / ([\d.]+) / ([\d.]+) m/s',ut).groups()
rates=re.search(r'yaw-rate RMS ([\d.]+) / ([\d.]+) / ([\d.]+)',ut).groups()
rows=[]
for i,s in enumerate(seqs):
 a,b={'BY2':(66,340),'BY2H':(413,683),'BY2O':(3186,3563)}[s]
 rows.append({'Sequence':s,'Window (s)':f'[{a}, {b}]','Duration (s)':b-a,'Epochs (F04)':mainrow(s,'F04')['matched_epoch_count'],'Reference distance (m)':num(next(r for r in ext if r['method']=='LEG-DR')[s],'reference_path_length_m'),'Mean speed (m/s)':speeds[i],'Yaw-rate RMS (deg/s)':rates[i],'Character': ['Primary calibration sequence','Transfer sequence; contract start','Antenna degradation and stationary interval'][i]})
table('1','T01_main_three_sequence',rows,[V/'07_AGGREGATE/MAIN_TABLE_V3.csv',H/'EXTERNAL_THREE_SEQUENCE_MANUSCRIPT.csv',unc,W/'configs/paper_rebuild/final_v23_parity_contract.yaml'],'Select F04 matched counts; parse LEG-DR reference_path_length_m; transcribe motion statistics from authorized uncertainty document section 3; window endpoints from contracts; duration=end-start. No raw inputs.')
methods=record(W/'configs/paper_rebuild/methods.yaml');md=yaml.safe_load(methods.read_text());print('method keys',md.keys())
# Explicit configuration definitions from methods.yaml and canonical ablation map.
rows=[]
for m,vel,gate,rd,sa,rp,hv in [('F01',1,0,0,0,0,0),('F02',0,0,0,0,0,0),('F03',1,1,0,0,0,0),('A04',1,1,1,0,1,1),('F04',1,1,1,1,1,1)]:
 rows.append({'Method':m,'GNSS position':'On','Receiver velocity':'On' if vel else 'Off','Shared dual-yaw initialization':'On','Online heading':'Off' if m=='F01' else 'On','Residual gate':'On' if gate else 'Off','Raw Doppler':'On' if rd else 'Off','Source-aware':'On' if sa else 'Off','Roll/pitch':'On' if rp else 'Off','Horizontal velocity':'On' if hv else 'Off'})
table('2','T02_configuration_ladder',rows,[methods,W/'configs/paper_rebuild/canonical_by2_internal_ablation_modes.yaml',W/'configs/paper_rebuild/final_v23_parity_contract.yaml'],'Translate online switches separately from shared dual-yaw initialization; F03=AB0000 and F04=AB1111; F02 lacks receiver velocity; source-aware is the A04-to-F04 difference.')
faultp=record(W/'configs/paper_rebuild/degradation_60types_9seeds.yaml');fault=yaml.safe_load(faultp.read_text());groups=collections.defaultdict(list)
for r in fault['degradation_types']:groups[r['family']].append(r)
table('3','T03_fault_families',[{'Family':f.replace('_',' '),'Types':', '.join(r['id'] for r in rr),'Injected channels':', '.join(sorted(set(x for r in rr for x in r['affected_sources']))),'Cases per method':len(rr)*fault['matrix']['seeds_per_type']} for f,rr in groups.items()],[faultp],'Group registered type definitions by family; count types times seeds_per_type; no result aggregation.')
def metricrows(methods):
 return [{'Sequence':s,'Method':m,'Yaw RMSE (deg)':mainrow(s,m)['yaw_rmse_deg'],'Horizontal RMSE (m)':mainrow(s,m)['h_rmse_m'],'Up RMSE (m)':mainrow(s,m)['up_rmse_m'],'Epochs':mainrow(s,m)['matched_epoch_count']} for s in seqs for m in methods]
table('4','T04_nominal_navigation',metricrows(ladder+['LC01','EXT05C']),[V/'07_AGGREGATE/MAIN_TABLE_V3.csv'],'Select sequence and method; internal configuration; LC01/EXT05C LIT, BY2H CONTRACT_START and otherwise FILE_START; select metrics and matched count.')
segp=V/'07_AGGREGATE/BY2O_SEGMENT_TABLE.csv';seg=readcsv(segp)
rows=[{'Segment':r['segment_id'].replace('occlusion_',''),'Method':r['method_id'],'Epochs':r['count'],'Yaw RMSE (deg)':r['yaw_rmse_deg'],'Horizontal RMSE (m)':r['h_rmse_m'],'Up RMSE (m)':r['up_rmse_m']} for r in seg if r['method_id'] in ['F02','F03','A04','F04','LC01'] and r['segment_id'] in ['occlusion_primary','occlusion_secondary','outside'] and r['variant'] in ['PROTOCOL_V3',''] and r['evaluator_contract']=='evaluator_contract_v3']
table('5a','T05_by2o_segments',rows,[segp],'Select primary, secondary and outside rows; exclude sensitivity variants; retain LC01 literature row.')
segx=readcsv(H/'BY2O_SEGMENT_TABLE_EXT.csv')
table('5b','T05b_heading_segments',[{k:r[k] for k in ['method','segment','paired_epochs','valid_epochs','availability','valid_rmse_deg','hold_rmse_deg','status']} for r in segx if r['method'].startswith(('EXT01','EXT02','EXT03','EXT04','RTKLIB')) and r['segment'] in ['occlusion_primary','occlusion_secondary','outside']],[H/'BY2O_SEGMENT_TABLE_EXT.csv'],'Select heading-output slice rows; valid and causal-hold denominators remain distinct.')
table('6','T06_ladder_results',metricrows(ladder),[V/'07_AGGREGATE/MAIN_TABLE_V3.csv'],'Same identity selection as Table 4, five configurations only.')
def cell(s):
 s=re.sub(r'(?<![A-Za-z0-9_])[-+]?\d+\.\d+(?:[eE][-+]?\d+)?',lambda m:f'{float(m.group()):.3f}',s)
 return s.replace('原生发散','algorithm divergence').replace('发散','diverged').replace('未通过精度验证','accuracy validation failed')
cats={'双天线模糊度/基线航向':'Dual-antenna heading','四足状态估计':'Legged state estimation','松耦合 GNSS/INS':'Loosely coupled GNSS/INS','单天线 GNSS/INS':'Single-antenna GNSS/INS'}
table('7','T07_external_methods',[{'Method':r['method'],'Configuration':r['config'].replace('V3','Study configuration'),'Output type':r['output_type'],**{s:cell(r[s]) for s in seqs}} for r in ext],[H/'EXTERNAL_THREE_SEQUENCE_MANUSCRIPT.csv'],'Select all 14 identities and per-sequence cells; round numeric tokens without changing denominators or statuses. Legend defines H/R/N fields.')
degr=readcsv(H/'DEGRADATION_MANUSCRIPT.csv');fam_en=dict(zip([r['family'] for r in degr],['Position noise','Position bias','Position outage','Velocity outage','Heading noise','Heading outage','Doppler','Timestamps','A2']))
table('8','T08_external_faults',[{'Family':fam_en[r['family']],**{k:cell(r[k]) for k in ['LC01','EXT05C','F02','F04','LC01_minus_F04','LC01_minus_F02']}} for r in degr],[H/'DEGRADATION_MANUSCRIPT.csv'],'Retain nine family rows and requested methods; cells are median/P95 [finite/registered; failures]; retain finite-pair differences, no re-aggregation.')
full=readcsv(V/'07C_FAILURE_FAMILY_CONFIG/FULL_ABLATION_TABLE_V3.csv')
table('S3','S03_full_ablation',[{'Sequence':r['sequence_id'],'Method':r['method_id'],**{k:r[k] for k in ['yaw_rmse_deg','horizontal_rmse_m','up_rmse_m','roll_rmse_deg','pitch_rmse_deg','matched_epoch_count','evaluation_status']}} for r in full],[V/'07C_FAILURE_FAMILY_CONFIG/FULL_ABLATION_TABLE_V3.csv'],'Select all 33 current evaluation rows and displayed metrics.')
fail=readcsv(V/'07C_FAILURE_FAMILY_CONFIG/FAILURE_FAMILY_CONFIG.csv');print('failure identities',sorted(set((r['protocol'],r['evaluator_version']) for r in fail)))
table('S4','S04_failures',[{k:r[k] for k in ['case_family','method_id','failure_classification','failure_count','registered_count']} for r in fail if r['protocol']=='v3' and r['evaluator_version']=='v3'],[V/'07C_FAILURE_FAMILY_CONFIG/FAILURE_FAMILY_CONFIG.csv'],'Select protocol=v3 and evaluator_version=v3, keep zero counts.')
sup=readcsv(H/'EXTERNAL_THREE_SEQUENCE_SUPPLEMENT.csv')
table('S5a','S05_external_supplement',[{'Method':r['method'],'Configuration':r['config'],**{s:cell(r[s]) for s in seqs}} for r in sup],[H/'EXTERNAL_THREE_SEQUENCE_SUPPLEMENT.csv'],'All supplement identities, including alternate start and LC01-BR; parse rounding only.')
dr=readcsv(H/'D43_VELOCITY_NOISE_SUPPLEMENT.csv');table('S5b','S05b_D43',dr,[H/'D43_VELOCITY_NOISE_SUPPLEMENT.csv'],'All rows; direct display rounding.')
sens=readcsv(V/'07_AGGREGATE/T5BCR_REFERENCE_THREE_SEQUENCES_V3.csv');names={'R5SIGMA':'Recalibrated constant heading weight','R5W':'Per-epoch receiver-reported heading weight','B3':'Three-dimensional baseline measurement'}
table('S6','S06_heading_weight',[{'Variant':names[v],**{s:next(r['yaw_rmse_deg'] for r in sens if r['method_id']=='F04' and r['variant']==v and r['sequence_id']==s) for s in seqs}} for v in names],[V/'07_AGGREGATE/T5BCR_REFERENCE_THREE_SEQUENCES_V3.csv'],'Select F04 and the three supplied sensitivity variants; yaw only, constants omitted.')
sub=readcsv(V/'07_AGGREGATE/SUBSET61_SUMMARY_V3.csv');table('S8','S08_subset61',[{k:r[k] for k in ['method_id','metric','registered_count','finite_count','algorithm_failure_count','median','p95','maximum']} for r in sub if r['metric'] in ['yaw_rmse_deg','horizontal_rmse_m','up_rmse_m']],[V/'07_AGGREGATE/SUBSET61_SUMMARY_V3.csv'],'Select yaw/horizontal/up summary rows; no subset-selection explanation.')
for id,name,src,filterfn in [('S9a','S09_uncertainty_budget','UNC_BUDGET.csv',lambda r:r['row'] in ['1','2','3','4','5','6','9','10']),('S9b','S09b_paired_intervals','UNC_DISTINGUISHABILITY.csv',lambda r:True),('S9c','S09c_window_intervals','UNC_REALIZATION_INTERVALS.csv',lambda r:True)]:
 rr=readcsv(U/src);rr=[r for r in rr if filterfn(r)]
 if id=='S9a':rr=publication_budget_rows(rr)
 table(id,name,rr,[U/src],'Select requested rows; retain original interval direction and denominators; numerical display rounding only.')
table('S2','S02_fault_types',[{'Type':r['id'],'Family':r['family'].replace('_',' '),'Definition':r['name'].replace('_',' '),'Parameters':json.dumps(r['parameters'],ensure_ascii=False),'Seeds':'00–08; anchors in S2b'} for r in fault['degradation_types']],[faultp],'Direct YAML definitions, including source-specific fault parameters.')
table('S2b','S02b_seed_anchors',[{k:r[k] for k in ['seed_index','seed_value','anchor_name','anchor_time_s']} for r in fault['seeds']],[faultp],'Direct seed and anchor definitions; no reference-driven selection.')

# Publication-only summaries produced by independent read-only audits; original science inputs stay unchanged.
repair=Path('/mnt/g/LegSA-GINS-project/修复_20261004')
cadence=readcsv(repair/'DELIVERED_IMU_CADENCE_AUDIT.csv')
table('S17','S17_delivered_imu_cadence',[{'Sequence':r['sequence'],'Formal output records':r['formal_output_records'],'Median output interval':r['median_output_dt_s']+' s','Mean records per second':r['mean_output_rate_hz'],'Intervals over 0.1 s':r['long_dt_over_0_1_s']} for r in cadence],[repair/'DELIVERED_IMU_CADENCE_AUDIT.json',repair/'DELIVERED_IMU_CADENCE_AUDIT.csv'],'Read-only timestamp summaries; exact intervals are kept in the external receipt; no estimator/evaluator used and no physical internal rate inferred.')
hv=readcsv(repair/'HISTORICAL_HV_LEAVE_ONE_OUT_SUMMARY.csv')
table('S18','S18_historical_hv_leave_one_out',[{'Family':'A1' if r['type']=='D61' else 'A2','Duration (s)':r['duration_s'],'Finite/registered pairs':r['finite_pairs']+'/'+r['registered_pairs'],'Mean delta H (m)':r['mean_delta'],'Median delta H (m)':r['median_delta'],'Negative/positive/zero':r['negative_pairs']+'/'+r['positive_pairs']+'/'+r['zero_pairs']} for r in hv if r['metric']=='horizontal_rmse_m'],[repair/'HISTORICAL_HV_LEAVE_ONE_OUT_REVIEW.json',repair/'HISTORICAL_HV_LEAVE_ONE_OUT_SUMMARY.csv'],'Existing historical scalar RMSE pairs F04-A06, arithmetic only; identity gates and exact values in external receipt; no native replay/bootstrap or independent-reference claim.')

writecsv(P/'TABLE_MAP.csv',MAP)
print('Tables',len(MAP))
