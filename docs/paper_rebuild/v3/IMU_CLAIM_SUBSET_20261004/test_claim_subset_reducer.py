from pathlib import Path
import importlib.util,json,hashlib,math
import numpy as np
import pandas as pd
p=Path('/mnt/g/LegSA-GINS-project/修复_20261004/publish_claim_subset.py')
spec=importlib.util.spec_from_file_location('claim_reducer',p);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
checks=[]
def check(name,condition):
    assert condition,name;checks.append({'name':name,'passed':True})
meta={'outage_start_s':66.2,'outage_end_s':66.5}
original=np.array([66100000,66200000,66300000,66400000,66500000,66600000,67100000,71500000,71600000,76500000,76600000,96500000,96600000],dtype=np.int64)
left=pd.DataFrame({'time':[66.1,66.2,66.3,66.4,66.5,66.6],'horizontal_err_m':[1,3,4,7,8,9]})
right=pd.DataFrame({'time':[66.1,66.2,66.3,66.5,66.6],'horizontal_err_m':[1,4,3,8,9]})
a,b,common,count=m.paired_frames(left,right,original,meta,'fault')
check('Fault half-open keepsstart excludesend; denominator preservesmissing lastfault epoch',list(common)==[66200000,66300000] and count==3)
check('Pair RMSE usesexactcommon support independently',abs(m.rmse(a.horizontal_err_m)-math.sqrt(12.5))<1e-12 and abs(m.rmse(b.horizontal_err_m)-math.sqrt(12.5))<1e-12)
check('Endpoint stayslast ORIGINAL observed fault epoch evenwhenonepairmissesit',m.endpoint_key(original,meta)==66400000 and 66400000 not in m.keys(right))
check('Recovery 0to5 isend-open and5closed',list(original[m.domain_mask(original,meta,'recovery_0_5')])==[66600000,67100000,71500000])
check('Recovery5to10 is5open and10closed',list(original[m.domain_mask(original,meta,'recovery_5_10')])==[71600000,76500000])
check('Recovery10to30 includes30second boundary excludes10',list(original[m.domain_mask(original,meta,'recovery_10_30')])==[76600000,96500000])
check('No emptydomain score fabricated',m.rmse([]) is None)
try:m.keys(pd.DataFrame({'time':[66.2,66.20000001]}));raise AssertionError('mustreject')
except ValueError:check('Microsecond keycollision rejected',True)
try:m.rmse([1,float('nan')]);raise AssertionError('mustreject')
except ValueError:check('Nonfinite metric rejected ratherthan dropped',True)
empty=pd.DataFrame(columns=['time',*m.METRICS.values()])
check('True unavailable objectdtype errorframe admitted as empty without numericalmetrics',len(m.validate_error_frame(empty,original))==0)
a,b,common,count=m.paired_frames(left,empty,original,meta,'fault')
check('Unavailable pair keepsoriginal denominator andfabricatesnozeroRMSE',len(common)==0 and count==3 and m.rmse(a.horizontal_err_m) is None)
valid_runs=[{'run_id':str(i)} for i in range(135)]
check('Exact135 uniqueIDs admitted beforedictconstruction',len(m.unique_run_ids(valid_runs))==135)
for name,rows in [('Same135lengthduplicateID rejected',valid_runs[:-1]+[valid_runs[0]]),('134runcohort rejected',valid_runs[:-1])]:
    try:m.unique_run_ids(rows);raise AssertionError('mustreject')
    except ValueError:check(name,True)
receipt={'status':'PAIRED_REDUCER_FOURTEEN_BOUNDARY_AND_IDENTITY_REGRESSIONS_PASSED','checks':checks,
 'solver_invocations':0,'evaluator_invocations':0,'reference_trace_reads':0,
 'reducer_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),
 'test_helper_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
out=Path('/mnt/g/LegSA-GINS-project/修复_20261004/CLAIM_REDUCER_BOUNDARY_TESTS_FINAL.json')
with out.open('x') as f:json.dump(receipt,f,indent=2)
print(json.dumps({'status':receipt['status'],'checks':len(checks)}))
