#!/usr/bin/env python3
"""Transcribe existing per-call receipts, hashes and counters. Never executes science."""
import argparse, csv, json
from pathlib import Path

HERE=Path(__file__).resolve().parent
def write(p,rows):
    with p.open('w',newline='') as f:
        w=csv.DictWriter(f,list(rows[0]),lineterminator='\n');w.writeheader();w.writerows(rows)
def main():
    p=argparse.ArgumentParser();p.add_argument('--roots',type=Path,required=True);p.add_argument('--candidate-id',required=True);a=p.parse_args()
    aliases=json.loads(a.roots.read_text())['aliases']
    def resolve(s):
        for k,v in sorted(aliases.items(),key=lambda x:len(x[0]),reverse=True):
            if s==k or s.startswith(k+'/'):return Path(v+s[len(k):])
        raise ValueError(s)
    def alias(s):
        for k,v in sorted(aliases.items(),key=lambda x:len(x[1]),reverse=True):s=s.replace(v,k)
        return s
    queue=list(csv.DictReader((HERE/'CANDIDATE_QUEUE.csv').open()));ledger={x['slot_id']:x for x in csv.DictReader((HERE/'RUN_MANIFEST.csv').open())}
    out=HERE/'native_results'/a.candidate_id;out.mkdir(parents=True,exist_ok=True)
    metrics=[];hashes=[];identities=[];statuses=[]
    for q in queue:
        if q['candidate_id']!=a.candidate_id:continue
        r=ledger[q['slot_id']];rec=resolve(q['candidate_outputs'])/'CANDIDATE_RECEIPT.json'
        if not rec.exists():
            statuses.append({**r,'access_passed':'UNKNOWN','fixed_manifest_identity':'UNKNOWN'});continue
        x=json.loads(rec.read_text());m=x.get('native_manifest',{});baseline=json.loads((resolve(q['baseline_outputs'])/'RUN_MANIFEST.json').read_text())
        checks=x.get('data_role_manifest_check',{})
        statuses.append({**r,'access_passed':x.get('access_passed','UNKNOWN'),'fixed_manifest_identity':all(y['same'] for y in checks.values()) if checks else 'UNKNOWN'})
        for key,value in m.items():
            if (key in ['starttime','endtime','source_commit','run_id','cov_health_status','cov_health_first_failure_time','yaw_NORMAL','yaw_DOWNWEIGHT','yaw_REJECT']
                or key.endswith('_count') or key.endswith('_rows') or key in ['module_update_counts','source_aware_R_scale_stats_by_source']):
                metrics.append({'slot_id':q['slot_id'],'field':key,'baseline_value':alias(json.dumps(baseline.get(key),sort_keys=True)),
                    'candidate_value':alias(json.dumps(value,sort_keys=True)),'baseline_source':q['baseline_outputs']+'/RUN_MANIFEST.json',
                    'candidate_source':q['candidate_outputs']+'/RUN_MANIFEST.json','source_key':'/'+key})
        for y in x.get('output_hashes',[]):hashes.append({'slot_id':q['slot_id'],**y,'source_receipt':q['candidate_outputs']+'/CANDIDATE_RECEIPT.json'})
        for key,y in checks.items():identities.append({'slot_id':q['slot_id'],'field':key,'baseline':alias(json.dumps(y['baseline'],sort_keys=True)),
            'candidate':alias(json.dumps(y['candidate'],sort_keys=True)),'same':y['same'],'source_receipt':q['candidate_outputs']+'/CANDIDATE_RECEIPT.json','source_key':'/data_role_manifest_check/'+key})
    for name,rows in [('STATUS.csv',statuses),('COUNTERS.csv',metrics),('OUTPUT_HASHES.csv',hashes),('FIXED_IDENTITY.csv',identities)]:
        if rows:write(out/name,rows)
    summary={'candidate_id':a.candidate_id,'planned_combinations':len(statuses),'actual_native_calls':sum(int(r['native_calls']) for r in statuses if r['native_calls'].isdigit()),
        'completed':sum(r['status']=='COMPLETED' for r in statuses),'evaluator_calls_by_this_collector':0,'new_performance_calculation':False,
        'operation':'lossless receipt/counter transcription only','statuses':[{'slot_id':r['slot_id'],'status':r['status']} for r in statuses]}
    (out/'SUMMARY.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary))
if __name__=='__main__':main()
