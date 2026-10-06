"""Independently inspect sealed metadata rows only. Never open raw or reference records."""
from pathlib import Path
from collections import defaultdict
import csv,json,hashlib

ROOT=Path(__file__).resolve().parents[3]
OUT=ROOT/'docs/paper_rebuild/TIM_AR_DEVELOPMENT_20261006'
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def flag(row,key): return row[key]=='True'
def main():
 summary=json.loads((OUT/'RAW_ARC_SUMMARY.json').read_text())
 p=OUT/'RAW_ARC_GPS_L1_TRACKING.csv'
 rows=list(csv.DictReader(p.open()))
 grouped=defaultdict(list)
 for row in rows: grouped[(row['receiver'],row['signal'])].append(row)
 keys={rx:{(r['gps_week'],r['gps_tow_seconds']) for r in rows if r['receiver']==rx} for rx in ['1','2']}
 times={rx:sorted({float(r['time_s']) for r in rows if r['receiver']==rx}) for rx in ['1','2']}
 signals=['0:6:0:0','0:11:0:0','0:17:0:0','0:19:0:0']
 reset_fields=['gap_reset','receiver_clock_reset','tracking_lock_reset_detected','cycle_slip_detected','half_cycle_state_changed','carrier_validity_changed','time_reversal_detected','arc_reset_due_to_tracking']
 details=[]
 for rx in ['1','2']:
  for sig in signals:
   rr=sorted(grouped[(rx,sig)],key=lambda x:float(x['time_s']))
   detail={'receiver':int(rx),'signal':sig,'rows':len(rr),'unique_keys':len({(r['gps_week'],r['gps_tow_seconds']) for r in rr}),'arc_ids':sorted({int(r['arc_id']) for r in rr}),'all_pr_cp_half_valid':all(all(flag(r,k) for k in ['pseudorange_valid','carrier_valid','half_cycle_valid']) for r in rr),'half_subtracted_states':sorted({r['half_cycle_subtracted'] for r in rr}),'min_locktime_ms':min(int(r['locktime_ms']) for r in rr),'cno_range_dbhz':[min(int(r['cno_dbhz']) for r in rr),max(int(r['cno_dbhz']) for r in rr)],'cp_std_code_range':[min(int(r['cp_std_code']) for r in rr),max(int(r['cp_std_code']) for r in rr)],'events':{k:sum(flag(r,k) for r in rr) for k in reset_fields},'first_observation_count':sum(flag(r,'first_observation') for r in rr)}
   details.append(detail)
 counted_events={k:sum(flag(r,k) for r in rows) for k in summary['tracking_event_counts']}
 checks={
  'tracking_file_hash_matches_seal':sha(p)==summary['result_hashes']['GPS_L1_TRACKING.csv'],
  'ten_unique_keys_each':all(len(x)==10 for x in keys.values()),
  'exact_receiver_week_tow_sets':keys['1']==keys['2'],
  'exact_receiver_reported_time_sets':times['1']==times['2'],
  'four_signals_ten_per_receiver':all(d['rows']==10 and d['unique_keys']==10 for d in details),
  'four_signals_valid_fields':all(d['all_pr_cp_half_valid'] for d in details),
  'four_signals_single_arc_positive_lock':all(d['arc_ids']==[1] and d['min_locktime_ms']>0 for d in details),
  'four_signals_no_reset_events':all(not any(d['events'].values()) for d in details),
  'summarized_event_counts_match_all177_tracking_rows':counted_events==summary['tracking_event_counts'],
  'interval_signals_match':set(summary['metadata_feasible_intervals'][0]['signals'])==set(signals),
  'interval_endpoints_match':summary['metadata_feasible_intervals'][0]['start_s']==times['1'][0] and summary['metadata_feasible_intervals'][0]['end_s']==times['1'][-1],
 }
 output={'status':'PASS_METADATA_ROWS_ONLY' if all(checks.values()) else 'FAIL','checks':checks,'tracking_rows':len(rows),'stable_signal_receiver_rows':sum(d['rows'] for d in details),'exact_paired_epochs':len(keys['1']&keys['2']),'time_range_s':[times['1'][0],times['1'][-1]],'duration_between_first_last_s':times['1'][-1]-times['1'][0],'details':details,'event_counts_all_rows':counted_events,'raw_reads_by_review':0,'reference_reads_by_review':0,'solver_calls_by_review':0,'input_sha256':{'RAW_ARC_SUMMARY.json':sha(OUT/'RAW_ARC_SUMMARY.json'),'RAW_ARC_GPS_L1_TRACKING.csv':sha(p)},'review_script_sha256':sha(Path(__file__)),'scope':'Independent recomputation from sealed decoded metadata only; no new raw decode, geometry, elevations, ambiguity solving or physical slip test. Saturated locktime and stable flags do not prove continuity before the window. Four signals yield candidate DD support, not proven geometric rank or correct integers.'}
 (OUT/'RAW_ARC_METADATA_REVIEW.json').write_text(json.dumps(output,ensure_ascii=False,indent=2)+'\n')
 print(json.dumps({'status':output['status'],'failed':[k for k,v in checks.items() if not v],'paired_epochs':output['exact_paired_epochs'],'stable_rows':output['stable_signal_receiver_rows'],'time_range_s':output['time_range_s']}))
 if not all(checks.values()): raise SystemExit(1)
if __name__=='__main__':main()
