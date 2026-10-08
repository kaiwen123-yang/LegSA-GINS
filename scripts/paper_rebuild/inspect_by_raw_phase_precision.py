"""Fixed BY2 first50-epoch source diagnostic; inputs and output paths are supplied by --config."""
from pathlib import Path
import argparse,sys,json,hashlib,struct,collections
import numpy as np
arg=argparse.ArgumentParser();arg.add_argument('--config',required=True);args=arg.parse_args();cfg=json.loads(Path(args.config).read_text());R=Path(cfg['repository']);sys.path.insert(0,str(R/'src'));from legsa_gins.paper_rebuild.horizontal_literature import shared_raw_backend as raw
OUT=Path(cfg['output_directory']);P=Path(cfg['plan_path']);plan=json.loads(P.read_text());reg=json.loads(Path(cfg['input_registry']).read_text());recs=[v for v in plan['records'] if 100.1979<=v['time_s']<=110.0];keys={(v['key'][0],round(v['key'][1]*1e6)):round(v['time_s']*1000) for v in recs};measurement={};source=[]
def key(payload):
 tow,week=struct.unpack_from('<dH',payload);return week,round(tow*1e6)
for rx in (1,2):
 ureg=reg['source_files'][f'gnss{rx}.ubx'];ubx=Path(ureg['source'].replace('<CLEAN_ROOT>',cfg['clean_root']));data=ubx.read_bytes();hits={}
 for cls,mid,payload in raw.iter_ubx_frames(data):
  if (cls,mid)==(2,21) and key(payload) in keys:
   t=keys[key(payload)];assert t not in hits;hits[t]=payload
 assert len(hits)==50
 creg=reg['raw_hash_locks'][f'gnss{rx}'];csv=Path(cfg['raw_root'])/creg['relative_path'];original={}
 for rownum,cell in enumerate(raw.read_csv_data_cells(csv),start=2):
  frames,_,_=raw._scan_valid_ubx_frames(cell)
  for frame in frames:
   for cls,mid,payload in raw.iter_ubx_frames(frame):
    if (cls,mid)==(2,21) and key(payload) in keys:
     t=keys[key(payload)];assert t not in original;original[t]=(payload,rownum)
  if len(original)==50:break
 assert len(original)==50
 source.append({'rx':rx,'ubx_path':str(ubx),'ubx_hash_matches_pin':hashlib.sha256(data).hexdigest()==ureg['sha256'],'ubx_sha256':hashlib.sha256(data).hexdigest(),'csv_path':str(csv),'csv_hash_matches_pin':hashlib.sha256(csv.read_bytes()).hexdigest()==creg['sha256'],'csv_sha256':hashlib.sha256(csv.read_bytes()).hexdigest(),'selected_payloads_equal':[hits[t]==original[t][0] for t in sorted(hits)],'selected_csv_rows':[original[t][1] for t in sorted(hits)]})
 for t,payload in hits.items():measurement[rx,t]={raw.identity_text(m.identity):m for m in raw.decode_rawx(payload).measurements}
checks=[];rows=[]
for rec in recs:
 t=round(rec['time_s']*1000);f=rec['families']['GPS_GAL_BDS_DUAL'];md=f['metadata'];ids=md['sd_identities'];idx={s:i for i,s in enumerate(ids)};labels=[json.loads(v) for v in f['ambiguity_labels']];D=np.zeros((len(labels),len(ids)));var=[]
 for i,(target,_,pivot,_) in enumerate(labels):D[i,idx[target]]=1;D[i,idx[pivot]]=-1
 for sig in ids:
  a,b=measurement[1,t][sig],measurement[2,t][sig];wave=raw.wavelength_m(a.identity);ap,al,_=raw.rawx_standard_deviations(a);bp,bl,_=raw.rawx_standard_deviations(b);var.append((ap*ap+bp*bp,wave*wave*(al*al+bl*bl)))
  for rx,m in [(1,a),(2,b)]:
   parts=sig.split(':');rows.append({'time_s':rec['time_s'],'rx':rx,'signal':sig,'group':':'.join([parts[0],parts[2],parts[3]]),'cno_dbhz':m.cno_dbhz,'cpStdev_code':m.cp_std_code,'reported_phase_sigma_cycles':.004*m.cp_std_code,'used_phase_sigma_cycles':raw.rawx_standard_deviations(m)[1],'used_phase_sigma_m':raw.rawx_standard_deviations(m)[1]*wave,'tracking_status':m.tracking_status,'locktime_ms':m.locktime_ms})
 T=np.block([[D,np.zeros_like(D)],[np.zeros_like(D),D]]);expected=T@np.diag(np.array(var).T.reshape(-1))@T.T;z=np.load(P.parent/f['file']);checks.append({'time_s':rec['time_s'],'Q_max_abs_difference':float(np.max(abs(expected-z['Q']))),'raw_admitted_receiver_signal_samples':2*len(ids)})
groups=[]
for group in sorted({v['group'] for v in rows}):
 v=[r for r in rows if r['group']==group];groups.append({'group':group,'raw_samples':len(v),'cpStdev_histogram':dict(sorted(collections.Counter(r['cpStdev_code'] for r in v).items())),'CNO_range_dbhz':[min(r['cno_dbhz'] for r in v),max(r['cno_dbhz'] for r in v)],'used_phase_sigma_cycles_range':[min(r['used_phase_sigma_cycles'] for r in v),max(r['used_phase_sigma_cycles'] for r in v)],'used_phase_sigma_m_range':[min(r['used_phase_sigma_m'] for r in v),max(r['used_phase_sigma_m'] for r in v)]})
out={'scope':'Same fixed50 BY2 epochs only; original receiver measurement metadata and rawQ reconstruction, no navigation or new model.','sources':source,'checks':checks,'raw_samples':len(rows),'group_summaries':groups,'interpretation':{'Q_field_or_unit_error_found':False,'Q_max_abs_difference':max(v['Q_max_abs_difference'] for v in checks),'phase_sigma_policy':'RAWX cpStdev code is linear0.004*code cycles; convert once by physical signal wavelength into meters. The existing0.004-cycle floor has no effect on admitted rows in this window because all observed codes>=2.','CNO_policy':'CNO gates eligibility, while original phaseQ uses receiver-reported cpStdev and wavelength. It is not an additional fitted phase-variance multiplier.','boundary':'Receiver-internal precision is not evidence that environmental multipath/phase biases are fully represented; this check only rules out a field/unit mismatch in these blocks.'},'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()};assert out['interpretation']['Q_max_abs_difference']==0;assert min(v['cpStdev_code'] for v in rows)>=2;(OUT/'RAW_PHASE_NOISE_CHECK.json').write_text(json.dumps(out,indent=2,ensure_ascii=False)+'\n');(OUT/'RAW_PHASE_NOISE_ROWS.json').write_text(json.dumps(rows,indent=2)+'\n');print('RAW_NOISE',out['interpretation']);print('GROUPS',json.dumps(groups));print('SOURCE_BYTES',[(v['rx'],all(v['selected_payloads_equal']),v['ubx_hash_matches_pin'],v['csv_hash_matches_pin']) for v in source],flush=True)
