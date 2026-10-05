#!/usr/bin/env python3
"""Read-only actual-config and Git-history evidence census; no scientific entry points."""
import csv, hashlib, json, subprocess
from pathlib import Path
import yaml
ROOT=Path('/home/kaiwen/research/LegSA-GINS-WORKTREES/audit-code-xbpg-20261001')
OUT=ROOT/'docs/paper_rebuild/TIM_EVIDENCE_20261005/data_and_selection'
NATIVE=Path('/mnt/g/LegSA-GINS-project/clean_rebuild_202607/stages/CLEAN8_PROTOCOL_V3/03_NATIVE')
DIRS={'BY2':'RUN_00004','BY2H':'V3R_CONTINUATION/SEQUENCE_BY2H_F04','BY2O':'V3R_CONTINUATION/SEQUENCE_BY2O_F04'}
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(n,o):(OUT/n).write_text(json.dumps(o,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def csvwrite(n,rs):
 with (OUT/n).open('w',encoding='utf-8',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(rs[0]));w.writeheader();w.writerows(rs)
def token(v):return json.dumps(v,ensure_ascii=False,separators=(',',':'),sort_keys=True)
def category(k):
 if k in ('initpos','initvel','initatt','initgb','initab'):return 'INITIALIZATION_RULE_OUTPUT_NOT_GLOBAL_FIT'
 if k in ('starttime','endtime'):return 'SEQUENCE_WINDOW'
 if any(s in k for s in ('path','file','output','stage','protocol','case','sequence','synthetic','data_mode','code_commit','hash')) or k in ('algorithm_id','method_id','case_id','run_id','run_label','runtime_role'):return 'IDENTITY_PATH_OR_METHOD_ALIAS'
 return 'MODEL_OR_POLICY_PARAMETER'
configs={s:yaml.safe_load((NATIVE/d/'V3_RUNTIME_CONFIG.yaml').read_text()) for s,d in DIRS.items()}
keys=sorted(set().union(*(x.keys() for x in configs.values())))
rows=[]
for k in keys:
 vals={s:token(c.get(k,{'__missing__':True})) for s,c in configs.items()}
 rows.append({'key':k,'classification':category(k),**vals,'all_equal':len(set(vals.values()))==1})
csvwrite('ACTUAL_F04_PARAMETER_TRANSFER.csv',rows)
csvwrite('ACTUAL_F04_CONFIG_DIFFERENCES.csv',[r for r in rows if not r['all_equal']])
DOCS=['CLEAN5_SENSOR_CALIBRATION_RECORD.md','SENSOR_MODEL_CLOSEOUT_AUDIT.md','A04_F04_ROLE_DECISION_RULE.md','PROTOCOL_V2_METHOD_STATEMENT.md','v3/PROTOCOL_V3_PREREG.md','V3_STORY_20261004/SELECTION_HISTORY_LEDGER.csv','audit_xbpg_20261001/SELECTION_AND_REFERENCE_REVIEW.md']
paths=[ROOT/'docs/paper_rebuild'/d for d in DOCS]+[ROOT/'src/legsa_gins/paper_rebuild/clean6_sensor_v21/providers.py',ROOT/'src/legsa_gins/paper_rebuild/clean5_calibrated/calibration.py']
paths +=[NATIVE/d/b for d in DIRS.values() for b in ('V3_RUNTIME_CONFIG.yaml','RUN_MANIFEST.json')]
pins=[{'path':str(p),'bytes':p.stat().st_size,'sha256':sha(p)} for p in paths]
log=subprocess.check_output(['git','log','--date=iso-strict','--format=%H\t%ad\t%s','--']+[str((ROOT/'docs/paper_rebuild'/d).relative_to(ROOT)) for d in DOCS[:5]],cwd=ROOT,text=True)
(OUT/'GIT_SELECTION_HISTORY.tsv').write_text('commit\tcommit_time\tsubject\n'+log,encoding='utf-8')
dump('SELECTION_SOURCE_PINS.json',{'repo_head_at_census':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),'source_files':pins,'field_count':len(rows),'equal_fields':sum(r['all_equal'] for r in rows),'different_fields':sum(not r['all_equal'] for r in rows),'scientific_executions':0,'source_and_original_result_writes':0,'machine_scope':'Every actual YAML field parsed and compared; semantic classification does not imply every source word manually read.'})
print(json.dumps({'fields':len(rows),'equal':sum(r['all_equal'] for r in rows),'differences':[r for r in rows if not r['all_equal']]},ensure_ascii=False,indent=2))
