"""Strict Decimal rule-formula checks; never creates or changes an Outcome."""
from __future__ import annotations
import csv
import json
from decimal import Decimal,localcontext
from pathlib import Path
from ..clean5_sequence.decision_inputs import _compare,_decimal
from ..clean5_parity.runtime import resolve,write_json
from ..manifest import sha256_file


def compare_segments(rows,*,rule,old):
    """Rows are CSV tokens from newly completed WINDOW_SEGMENT_SUMMARY.csv."""
    lookup={}
    for n,r in enumerate(rows,2):
        if r['dataset_id'] not in ('BY2H','BY2O') or r['method_id'] not in ('A04','F04'):continue
        key=(r['dataset_id'],r['segment_id'],r['method_id'],r['metric_name'])
        if key in lookup:raise ValueError('Duplicate robustness metric identity')
        lookup[key]=(r,n)
    def value(ds,segment,method,metric,column):
        r,n=lookup[(ds,segment,method,metric)]
        if int(r['count'])<=0:raise ValueError('No metric sample support')
        return _decimal(r[column],str((ds,segment,method,metric,column)),nonnegative=True),r.get('source_row',f'WINDOW_SEGMENT_SUMMARY.csv:{n}')+'/'+column
    def check(ds,segment,metric,column,scale,offset,formula):
        a,ap=value(ds,segment,'A04',metric,column);f,fp=value(ds,segment,'F04',metric,column)
        with localcontext() as context:
            context.prec=max(64,sum(len(x.as_tuple().digits)+abs(x.adjusted()) for x in [a,f])+20)
            return _compare(f,Decimal(scale)*a-Decimal(offset),formula=formula,input_paths=[ap,fp],rule=rule)
    heading={'yaw_rmse_deg':check('BY2H','full','yaw','rmse','1','.50','yawRMSE(F04) <= yawRMSE(A04) - 0.50 deg'),
             'yaw_p95_deg':check('BY2H','full','yaw','p95_abs','.5','0','yawP95(F04) <= 0.5 * yawP95(A04)')}
    position={}
    for ds,segment in [('BY2H','full'),('BY2O','full'),('BY2O','outside')]:
        position[ds+'_'+segment]={label:check(ds,segment,metric,'rmse','1.10','0',formula) for label,metric,formula in [
            ('horizontal_rmse_m','horizontal','horizontalRMSE(F04) <= 1.10 * horizontalRMSE(A04)'),
            ('up_rmse_m','up','upRMSE(F04) <= 1.10 * upRMSE(A04)')]}
    changes=[]
    def attach(current,previous,key):
        prior=previous['strict_pass']
        if type(prior)is not bool:raise ValueError('Old strict comparison status unavailable')
        current.update(old_strict_pass=prior,comparison_to_frozen='MAINTAINED' if current['strict_pass']==prior else 'REVERSED')
        changes.append({'test':key,'old_strict_pass':prior,'calibrated_strict_pass':current['strict_pass'],'status':current['comparison_to_frozen']})
    for label,v in heading.items():attach(v,old['tests']['heading']['branches'][label],'heading/'+label)
    for window,checks in position.items():
        for label,v in checks.items():attach(v,old['tests']['position']['windows'][window][label],'position/'+window+'/'+label)
    executable=old['tests']['heading']['executable']
    if executable is not True:raise ValueError('Frozen BY2H physical gate not executable')
    heading_pass=any(v['strict_pass'] for v in heading.values());position_pass=all(v['strict_pass'] for checks in position.values() for v in checks.values())
    aggregates={}
    for name,p in [('heading',heading_pass),('position',position_pass)]:
        previous=old['tests'][name]['status']
        if previous not in ('PASS','FAIL'):raise ValueError('Frozen test status unavailable')
        current='PASS' if p else 'FAIL';aggregates[name]={'formula_check_status':current,'old_status':previous,'comparison_to_frozen':'MAINTAINED' if current==previous else 'REVERSED'}
    return {'heading_branches':heading,'position_comparisons':position,'individual_comparisons':changes,'aggregate_formula_checks':aggregates,
            'classification':'NOT_THE_PREREGISTERED_COMPARISON_PROTOCOL','new_outcome_created':False,'outcome_changed':False,
            'arithmetic':'exact Decimal CSV tokens, no tolerance/rounding; threshold equality is not strict pass',
            'comparison_baseline':'original frozen v2 decision inputs for both calibrated v2 and v3',
            'heading_combination':'OR of two branches','position_combination':'AND of all six comparisons','metric_recomputation_count':0}


def comparison_csv_rows(result):
    """Flatten existing comparison outputs, without a second formula evaluation."""
    rows=[]
    for version,check in result['versions'].items():
        for name,branch in check['heading_branches'].items():
            rows.append({'version':version,'record_type':'individual','test':'heading/'+name,**branch})
        for window,items in check['position_comparisons'].items():
            for name,branch in items.items():rows.append({'version':version,'record_type':'individual','test':'position/'+window+'/'+name,**branch})
        for name,status in check['aggregate_formula_checks'].items():
            rows.append({'version':version,'record_type':'aggregate','test':name,**status})
    for row in rows:
        row.update(classification=result['classification'],outcome_changed=False,new_outcome_created=False)
    return rows


def robustness_check(*,registry,contract,stage_root):
    spec=contract['robustness'];stage=Path(stage_root)
    def pin(entry):
        path=resolve(entry['path'],registry)
        if path.is_symlink() or sha256_file(path)!=entry['sha256']:raise ValueError('Frozen robustness source changed')
        return path
    rule=pin(spec['rule']);oldpath=pin(spec['old_decision_inputs']);old=json.loads(oldpath.read_text())
    result={'classification':'NOT_THE_PREREGISTERED_COMPARISON_PROTOCOL','rule_source':spec['rule'],'old_decision_inputs':spec['old_decision_inputs'],
            'new_outcome_created':False,'outcome_changed':False,'versions':{},'reference_payload_read_count':0}
    for version in ['v2','v3']:
        path=stage/'08_AGGREGATE/WINDOW_SEGMENT_SUMMARY.csv' if version=='v2' else stage/'08_AGGREGATE/v3/WINDOW_SEGMENT_SUMMARY.csv'
        with path.open(newline='') as f:rows=list(csv.DictReader(f))
        result['versions'][version]=compare_segments(rows,rule=spec['rule'],old=old)
        result['versions'][version]['metric_source']={'path':str(path),'sha256':sha256_file(path)}
    pin(spec['rule']);pin(spec['old_decision_inputs'])
    write_json(stage/'08_AGGREGATE/CALIBRATED_CHAIN_ROBUSTNESS_CHECK.json',result)
    from ..clean5_parity.evaluation import _csv
    _csv(stage/'08_AGGREGATE/CALIBRATED_CHAIN_ROBUSTNESS_CHECK.csv',comparison_csv_rows(result))
    return result
