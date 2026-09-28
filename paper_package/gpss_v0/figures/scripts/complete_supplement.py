"""Supplement formatting from the task's explicit source list."""
from common import *
import re,yaml
def add(id,name,rows,sources,derivation):
    out='tables/'+name+'.csv';writecsv(P/out,rows)
    mp=P/'TABLE_MAP.csv';rr=list(csv.DictReader(mp.open()));rr=[r for r in rr if r['manuscript_table']!=id];rr.append(dict(manuscript_table=id,output_csv=out,source_files=';'.join(map(str,sources)),derivation=derivation));writecsv(mp,rr)
methodp=record(W/'docs/paper_rebuild/PROTOCOL_V2_METHOD_STATEMENT.md');text=methodp.read_text().split('## Protocol v2.1 — three sensor corrections')[1]
calp=record(W/'docs/paper_rebuild/CLEAN5_SENSOR_CALIBRATION_RECORD.md');cal=calp.read_text()
contractp=record(W/'configs/paper_rebuild/final_v23_parity_contract.yaml');ct=yaml.safe_load(contractp.read_text())
def find(obj,key):
    if isinstance(obj,dict):
        if key in obj:return obj[key]
        for v in obj.values():
            r=find(v,key)
            if r is not None:return r
    return None
pars=[]
def par(p,v,u,s):pars.append({'Parameter':p,'Value':v,'Unit':u,'Basis':s})
par('Heading standard-deviation marker',re.search(r'proxy (\d+\.\d+) degrees',text).group(1),'deg','Primary-sequence increment-residual proxy; not independent denser-grid white noise')
par('Horizontal-velocity scale','1/'+re.search(r'k_HV=1/(\d+\.\d+)',text).group(1),'ratio','Fixed source model; no transfer-sequence refit')
par('Horizontal-velocity standard deviation',re.search(r'σ_HV=(\d+\.\d+)',text).group(1),'m/s','Residual proxy; not an independently identified white-noise component')
par('Roll/pitch standard deviation',re.search(r'std 保持 (\d+\.\d+)',text).group(1),'deg','Robot weak prior')
par('Accelerometer scale',re.search(r'`s=([\d.]+)',cal).group(1),'ratio','Reference-free primary-sequence calibration')
for line in cal.splitlines():
 if re.match(r'\| (north|east|down)/',line):
  cells=[c.strip() for c in line.strip('|').split('|')];par('VRW index '+cells[0],cells[1],'(m/s)/sqrt(h)','Parameter-index proxy; not identified physical body-axis covariance');par('Accelerometer-bias std index '+cells[0],cells[2],'mGal','Transferred unchanged')
for key,u in [('arw_deg_sqrt_h','deg/sqrt(h)'),('gyro_bias_std_deg_h','deg/h'),('yaw_std_min_deg','deg'),('yaw_std_soft_deg','deg'),('yaw_std_hard_deg','deg'),('yaw_res_soft_deg','deg'),('yaw_res_hard_deg','deg'),('yaw_downweight_scale','variance ratio'),('antlever_frd_m','m')]:par(key,json.dumps(find(ct,key)),u,'Fixed implementation setting')
for seq,path in [('BY2',contractp),('BY2H',W/'configs/paper_rebuild/clean5/CLEAN5_BY2H_SEQUENCE_CONTRACT.yaml'),('BY2O',W/'configs/paper_rebuild/clean5/CLEAN5_BY2O_SEQUENCE_CONTRACT.yaml')]:
 d=yaml.safe_load(record(path).read_text());par(seq+' base time',find(d,'base_time_unix_seconds') or find(d,'base_time'),'Unix s','Sequence time origin');par(seq+' evaluation window',{'BY2':'[66,340]','BY2H':'[413,683]','BY2O':'[3186,3563]'}[seq],'s','Contract window')
add('S1','S01_configuration',pars,[methodp,calp,contractp,W/'configs/paper_rebuild/clean5/CLEAN5_BY2H_SEQUENCE_CONTRACT.yaml',W/'configs/paper_rebuild/clean5/CLEAN5_BY2O_SEQUENCE_CONTRACT.yaml'],'Extract literal calibration markers from the named correction section and calibration record; fixed thresholds and base times from YAML. Parameter tokens intentionally retain source precision.')
sp=record(W/'docs/paper_rebuild/hext/T5A_R_HEADING_SENSITIVITY.md');block=sp.read_text().split('## SENSITIVITY_TABLE_V3.csv')[1].split('```csv')[1].split('```')[0].strip();rows=list(csv.DictReader(block.splitlines()));out=[]
for m in ['F02','F04']:
 for v,label in [('FROZEN_V21','Status heading, 1 Hz'),('R1','Raw heading, 1 Hz'),('R5','Raw heading, 5 Hz')]:
  out.append({'Method':m,'Input':label,**{s:f"{float(next(r['yaw_rmse_deg'] for r in rows if r['method_id']==m and r['sequence_id']==s and r['variant']==v)):.3f}" for s in ['BY2','BY2H','BY2O']}})
add('S7','S07_heading_source',out,[sp],'Parse embedded SENSITIVITY_TABLE_V3 CSV, select F02/F04 and status/raw low-rate/raw higher-rate variants; rename labels; copy yaw only, round to three decimals.')
main=readcsv(V/'07_AGGREGATE/MAIN_TABLE_V3.csv');out=[]
for r in main:
 if r['method_id'] in ['LC01','LC01-S','F04'] and (r['config']=='PROTOCOL_V3' or r['start_convention']==('CONTRACT_START' if r['sequence_id']=='BY2H' else 'FILE_START')):
  out.append({'Sequence':r['sequence_id'],'Method':r['method_id'],**{k:f'{float(r[k]):.3f}' for k in ['yaw_rmse_deg','roll_rmse_deg','pitch_rmse_deg']}})
add('S5c','S05c_attitude',out,[V/'07_AGGREGATE/MAIN_TABLE_V3.csv'],'Select primary-start LC01, LC01-S and F04 attitude rows; copy all three attitude metrics.')
add('S10','S10_audit_note',[{'Item':'Audit tool correction after results','Statement':'The observer projection was corrected to WGS84; the original evaluator scientific outputs were unchanged.','Consequence':'Previously audit-unavailable entries could be admitted using the corrected check; no new trajectory was selected.'}],[H/'HX05_CLOSEOUT.md'],'Transcribe the conclusion at the correction summary; omit diagnostic history, numerical transition counts and internal task identifiers.')
# Display-only English labels and shorter human-readable metric names.
for p in (P/'tables').glob('*.csv'):
 content=p.read_text().replace('not applicable','not applicable').replace('lower_quality_but_valid_A1','lower_quality_but_valid_heading')
 content=content.replace('速度噪声','Velocity noise').replace('frozen, uncorrected','fixed, uncorrected').replace('(UNC-02)','(paired intervals)').replace('protocol-v3','study')
 p.write_text(content)
print('Supplement tables complete')
