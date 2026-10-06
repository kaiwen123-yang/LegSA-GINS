#!/usr/bin/env python3
"""Aggregate R2 audit dispositions; all LegSA values are read from sealed tables."""
from __future__ import annotations
import builtins
import io
import os
from pathlib import Path

def deny_reference(original):
    def checked(file,*args,**kwargs):
        if isinstance(file,(str,bytes,os.PathLike)):
            name=os.fsdecode(file)
            if '/data/raw/' in name or 'trace_vrtk' in Path(name).name or name.endswith(('.bag','.fpl')):
                raise RuntimeError('HARD_STOP_REPORT_REFERENCE_OPEN')
        return original(file,*args,**kwargs)
    return checked
builtins.open=deny_reference(builtins.open)
io.open=deny_reference(io.open)

import csv
import hashlib
import json
import math
import shutil
from collections import Counter

import numpy as np
import yaml

METRICS=('yaw_rmse_deg','horizontal_rmse_m','up_rmse_m')
EXTRA=('audit_status_R1','audit_status_R2','observer_discrepancy_R2')


def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(1<<20),b''):h.update(b)
    return h.hexdigest()


def load_csv(p):
    with p.open() as f:return list(csv.DictReader(f))


def csv_write(p,rows):
    with p.open('x',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator='\n');w.writeheader();w.writerows(rows)


def write(p,value):
    with p.open('x') as f:f.write(json.dumps(value,ensure_ascii=False,sort_keys=True,indent=2,allow_nan=False)+'\n')


def finite(x):
    try:return math.isfinite(float(x))
    except (ValueError,TypeError):return False


def distribution(xs):
    a=[float(x) for x in xs if finite(x)]
    return {'finite_n':len(a),'median':float(np.median(a)) if a else '',
            'p95':float(np.percentile(a,95)) if a else '', 'max':max(a) if a else ''}


def audit_group(rows):
    a={k:json.dumps(dict(sorted(Counter(r[k] for r in rows).items())),sort_keys=True,separators=(',',':')) for k in EXTRA[:2]}
    values=[json.loads(r['observer_discrepancy_R2']) for r in rows if r['observer_discrepancy_R2']]
    a['observer_discrepancy_R2']=json.dumps({k:max(v[k] for v in values) for k in ('horizontal_max_m','up_max_m','yaw_max_deg')},sort_keys=True,separators=(',',':')) if values else ''
    return a


def table(head,rows):
    return '\n'.join(['| '+' | '.join(head)+' |','| '+' | '.join(['---']*len(head))+' |']+['| '+' | '.join(str(x) for x in r)+' |' for r in rows])


def main():
    W=Path.cwd();local=yaml.safe_load((W/'configs/paper_rebuild/DATA_PATHS.CLEAN3R4.local.yaml').read_text())['paths']
    stages=Path(local['clean_root'])/'stages';old=stages/'CLEAN9_EXTERNAL_COMPARISON/HX03_DEGRADATION'
    root=stages/'CLEAN9_EXTERNAL_COMPARISON/HX03R2_AUDIT_REEVAL';control=root/'00_CONTROL'
    scratch=Path(local['hx02_scratch'])/'HX03R2/REPORT_R2';scratch.mkdir(parents=True,exist_ok=False)
    mapping=json.loads((control/'RUN_MAPPING_R2.json').read_text())
    bycase={(r['case_id'],r['method']):r for r in mapping}
    slots=json.loads((control/'EVALUATION_SLOTS_R2.json').read_text())
    outcomes={};identity_rows=[];residual_dir=scratch/'AUDIT_RESIDUALS';residual_dir.mkdir()
    for slot in slots:
        rd=root/'RUNS'/slot['run_id']/(slot['version']+'_R2')
        r=json.loads((rd/'RESULT_R2.json').read_text());receipt=json.loads((rd/'ARCHIVE_RECEIPT_R2.json').read_text())
        for n in ('RESULT_R2.json','SCIENTIFIC_IDENTITY_R2.json','AUDIT_RESIDUALS_R2.csv.gz'):
            if sha(rd/n)!=receipt['files_sha256'][n]:raise RuntimeError('HARD_STOP_ARCHIVE_IDENTITY')
        if not r['scientific_identity']['passed'] or not r['old_available_metrics_identity']['passed']:
            raise RuntimeError('HARD_STOP_SCIENTIFIC_IDENTITY')
        outcomes[(slot['run_id'],slot['version'])]=r
        target=residual_dir/(slot['slot_id']+'_R2.csv.gz');shutil.copyfile(rd/'AUDIT_RESIDUALS_R2.csv.gz',target)
        if sha(target)!=r['residuals_sha256']:raise RuntimeError('HARD_STOP_RESIDUAL_COPY')
        s=r['scientific_identity']
        identity_rows.append({'slot_id':slot['slot_id'],'role':slot['role'],
            'summary_R1_sha256':s['summary_json']['R1'],'summary_R2_sha256':s['summary_json']['R2'],
            'error_series_R1_sha256':s['error_series_csv']['R1'],'error_series_R2_sha256':s['error_series_csv']['R2'],
            'passed':True,'R1_available_metric_fields':r['old_available_metrics_identity']['field_count'],
            'R1_available_metrics_equal':r['old_available_metrics_identity']['passed'],
            'trace_open_count':r['trace_open_count'],'trace_sha256':r['trace_sha256'],
            'audit_status_R1':r['audit_status_R1'],'audit_status_R2':r['audit_status_R2'],
            'horizontal_max_m':r['observer_discrepancy_R2']['horizontal_max_m'],
            'up_max_m':r['observer_discrepancy_R2']['up_max_m'],'yaw_max_deg':r['observer_discrepancy_R2']['yaw_max_deg'],
            'residual_file':'AUDIT_RESIDUALS/'+target.name,'residual_sha256':r['residuals_sha256']})
    if len(outcomes)!=492:raise RuntimeError('HARD_STOP_MISSING_EVALUATION_SLOT')
    csv_write(scratch/'SCIENTIFIC_IDENTITY_R2.csv',identity_rows)
    versions={};old_versions={};logical_equal=0
    for version in ('v3','v2'):
        old_table=load_csv(old/'90_AGGREGATE'/('DEGRADATION_EXTERNAL_TABLE.csv' if version=='v3' else 'DEGRADATION_EXTERNAL_TABLE_V2.csv'))
        new=[]
        for oldrow in old_table:
            row=dict(oldrow)
            case=row['case_id'].replace('D61_','D62_') if row['type']=='D61' else row['case_id']
            m=bycase[(case,row['method'])];result=outcomes.get((m['evaluation_source_run_id'],version))
            if result is None:
                if m['native_failure_class']!='ALGORITHM_FAILURE_DIVERGED':raise RuntimeError('HARD_STOP_UNRESOLVED_EQUIVALENCE')
                row.update(audit_status_R1='NOT_EVALUATED',audit_status_R2='NOT_EVALUATED',observer_discrepancy_R2='')
            else:
                row.update({k:result[k] for k in EXTRA[:2]})
                discrepancy={k:result['observer_discrepancy_R2'][k] for k in ('horizontal_max_m','up_max_m','yaw_max_deg')}
                row['observer_discrepancy_R2']=json.dumps(discrepancy,sort_keys=True,separators=(',',':'))
                metric=result['row']
                row['source_run_dir']='$HX03R2/RUNS/'+m['evaluation_source_run_id']+'/'+version+'_R2'
                if oldrow['failure_class']=='ALGORITHM_FAILURE_DIVERGED':
                    for key,value in zip(('pre_failure_yaw','pre_failure_h','pre_failure_up'),METRICS):row[key]=metric.get(value,'')
                elif result['audit_status_R2']=='PASS':
                    row['failure_class']='NONE'
                    for key in METRICS:row[key]=metric[key]
                    row['yaw_p95_deg']=metric['yaw_p95_absolute_deg']
                else:
                    row['failure_class']='UNAVAILABLE_EVALUATION_FAILED'
                    for key in (*METRICS,'yaw_p95_deg'):row[key]=''
                if oldrow['failure_class']=='NONE':
                    for key in (*METRICS,'yaw_p95_deg'):
                        if float(oldrow[key])!=float(row[key]):raise RuntimeError('HARD_STOP_OLD_AVAILABLE_LOGICAL_METRIC_DIFFER: '+str((case,row['method'],version,key,oldrow[key],row[key])))
                    logical_equal+=1
            new.append(row)
        if len(new)!=396:raise RuntimeError('HARD_STOP_LOGICAL_ROWS')
        versions[version]=new;old_versions[version]=old_table
        csv_write(scratch/('DEGRADATION_EXTERNAL_TABLE_R2.csv' if version=='v3' else 'DEGRADATION_EXTERNAL_TABLE_V2_R2.csv'),new)
    rows=versions['v3'];original=old_versions['v3'];summary=[];transitions=[]
    for level in ('type','family'):
        for group in dict.fromkeys(r[level] for r in rows):
            for method in ('LC01','EXT05C','LC01-BR'):
                subset=[r for r in rows if r[level]==group and r['method']==method]
                before=[r for r in original if r[level]==group and r['method']==method]
                if not subset:continue
                changes=Counter((a['failure_class'],b['failure_class']) for a,b in zip(before,subset))
                transitions.append({'level':level,'group':group,'method':method,'registered_n':len(subset),
                    'R1_unavailable_n':sum(r['failure_class']=='UNAVAILABLE_EVALUATION_FAILED' for r in before),
                    'unavailable_to_finite_n':changes[('UNAVAILABLE_EVALUATION_FAILED','NONE')],
                    'R2_unavailable_n':sum(r['failure_class']=='UNAVAILABLE_EVALUATION_FAILED' for r in subset),
                    'R2_algorithm_failure_n':sum(r['failure_class']=='ALGORITHM_FAILURE_DIVERGED' for r in subset),
                    'R2_finite_n':sum(r['failure_class']=='NONE' for r in subset),**audit_group(subset)})
                for metric in METRICS:
                    summary.append({'level':level,'group':group,'method':method,
                        'method_label':'改动过的 LC01' if method=='LC01-BR' else method,'metric':metric,
                        'registered_n':len(subset),'failure_n':sum(r['failure_class']!='NONE' for r in subset),
                        **distribution([r[metric] for r in subset if r['failure_class']=='NONE']),**audit_group(subset)})
    csv_write(scratch/'DEGRADATION_EXTERNAL_SUMMARY_R2.csv',summary);csv_write(scratch/'STATE_TRANSITIONS_R2.csv',transitions)
    reference={};v3=stages/'CLEAN8_PROTOCOL_V3';core=v3/'07_AGGREGATE/CORE_541_DISTRIBUTION_V3.csv';add=v3/'07_AGGREGATE/ADDENDUM_TABLE_V3.csv';targets=('F04','F02','F03','A04')
    for r in load_csv(core):
        if r['method_id'] in targets and r['metric'] in METRICS:reference[(r['case_id'],r['method_id'],r['metric'])]=r['value']
    for r in load_csv(add):
        if r['method_id'] in targets:
            for metric in METRICS:reference[(r['case_id'],r['method_id'],metric)]=r.get(metric,'')
    paired=[]
    for s in summary:
        subset=[r for r in rows if r[s['level']]==s['group'] and r['method']==s['method']]
        for target in targets:
            values=[float(r[s['metric']])-float(reference[(r['case_id'],target,s['metric'])]) for r in subset if r['failure_class']=='NONE' and finite(r[s['metric']]) and finite(reference.get((r['case_id'],target,s['metric'])))]
            d=distribution(values)
            paired.append({k:s[k] for k in ('level','group','method','method_label','metric')} | {
                'reference_method':target,'registered_n':len(subset),'paired_n':d['finite_n'],
                'difference_median':d['median'],'difference_p95':d['p95'],'difference_definition':'external_minus_reference',
                'source':'$V3/07_AGGREGATE/'+(add.name if s['group'] in ('A2','A1等价报告','D62','D61') else core.name),**audit_group(subset)})
    csv_write(scratch/'DEGRADATION_PAIRED_R2.csv',paired)
    # Assert A1 is still exactly the LC01 A2 result, including failure rows.
    lookup={(r['case_id'],r['method']):r for r in rows}
    for r in rows:
        if r['type']=='D61':
            match=lookup[(r['case_id'].replace('D61_','D62_'),'LC01')]
            for k in (*METRICS,'yaw_p95_deg','failure_class',*EXTRA):
                if r[k]!=match[k]:raise RuntimeError('HARD_STOP_A1_A2_EQUIVALENCE')
    unavailable=[r for r in rows if r['failure_class']=='UNAVAILABLE_EVALUATION_FAILED']
    write(scratch/'STILL_UNAVAILABLE_R2.json',unavailable)
    disposition=Counter((a['failure_class'],b['failure_class']) for a,b in zip(original,rows))
    text=['# HX-03R-2：WGS84 观察器更正后的外部退化评估','','本任务属于结果之后的审计工具修正。冻结评估器、原生 NAV、D8 和 D12 的 0.01 m/0.01° 阈值均未改；原 HX-03 表和目录保留。',
        '采用 clean6_canonical_v2/evaluation.py:39–85 的既有 WGS84 观察器；HX-03R-1 发现旧球面近似的水平不一致中位数 0.03913079253370084 m、相对量中位数 0.022802420226922474、与最大水平误差回归 R²=0.9469042880015941。来源：HX03R/DIAGNOSTIC_STATISTICS.json:logical,unique_cross_run_regressions。',
        '冻结原始 summary.json 和 error_series.csv 在每个 v3/v2 槽位逐字节比对；EVALUATION_RESULT.json 仅引用旧处置记录。逐槽位证明见 SCIENTIFIC_IDENTITY_R2.csv。', '',
        'R1→R2 状态变化（逻辑 396 行，A1 18 行是 A2 别名）：','',table(['R1','R2','行数'],[[a,b,n] for (a,b),n in disposition.items()]),'',
        '各型/族与方法的变化：','',table(['层级','组','方法','分母','不可用→有限','R2 仍不可用','R2 算法失败','R2 有限'],[[r[k] for k in ('level','group','method','registered_n','unavailable_to_finite_n','R2_unavailable_n','R2_algorithm_failure_n','R2_finite_n')] for r in transitions]),'',
        '各族有限样本中位数（° / m / m）：','']
    family_rows=[]
    for t in [r for r in transitions if r['level']=='family']:
        ss={r['metric']:r for r in summary if r['level']=='family' and r['group']==t['group'] and r['method']==t['method']}
        family_rows.append([t['group'],t['method'],t['R2_finite_n'],t['registered_n']]+[ss[k]['median'] for k in METRICS])
    text += [table(['族','方法','有限 n','分母','yaw 中位数/°','水平中位数/m','高程中位数/m'],family_rows),'',
        '以上状态与中位数来源 STATE_TRANSITIONS_R2.csv、DEGRADATION_EXTERNAL_SUMMARY_R2.csv（level=family）；配对只用双方有限样本，差为外部方法减 LegSA，分母与配对数均保留。', '',
        'A2 的 LC01 主行与 A1 等价报告逐例指标、失败标记和审计状态完全相同，共 18 对。LC01-BR 是改动过的 LC01，仅 A2 补充；三者各自有限分母见上表，不把 PRE_FAILURE 纳入有限样本统计。', '',
        f'仍不可用行：{len(unavailable)}/396，完整清单与残差量见 STILL_UNAVAILABLE_R2.json；原生发散状态保持不变。', '',
        'D31 与 D57 的暴露差异保持原登记：D31 的 LC01 跳过整次双天线更新，EXT05C 更新不读 p2；D57 的位置时间扰动与 v3 LegSA 的有效航向为零不是同一种输入暴露。', '',
        '逐历元审计残差保存在 AUDIT_RESIDUALS/；水平门采用东/北残差向量范数，同时保存水平误差模长之差、高程差和圆周 yaw 差。逐槽位最大值时刻及观察器 RMSE/P95 在 RUNS/*/*_R2/AUDIT_DETAIL_R2.json。','',
        f'492/492 槽位的两份冻结原始输出哈希一致；旧可用逻辑行在 v3/v2 合计 {logical_equal} 行，四项表中科学指标逐项相等。科学一致性证明见 SCIENTIFIC_IDENTITY_R2.csv 和 AGGREGATE_RECEIPT_R2.json。', '',
        '执行与访问：原生 0、LegSA 解算/评估 0/0；正式评估子进程 492 次（含登记前 6 次，矩阵不重复）；各子进程仅打开参考 1 次并核哈希。最初一次外层/内层 strace 冲突发生在 Python 子进程执行前，实际评估与参考打开均为 0；原启动失败与处置记录保留在 00_CONTROL/PREEXEC_FAILURE_01_R2/，不计入 492 次科学调用。', '',
        'Outcome：按相同投影观察器与原阈值重新处置全部旧评估槽位；有限与失败如实保留，没有性能筛选或算法重跑。R2 是新结果版本，未回写 HX-03。参考为 Fixposition 输出，不声明为独立真值。','']
    (scratch/'HX03R2_RESULTS.md').write_text('\n'.join(text))
    write(scratch/'AGGREGATE_RECEIPT_R2.json',{'rows_v3':len(rows),'rows_v2':len(versions['v2']),'evaluation_slots':492,
        'scientific_file_pairs_equal':492,'individual_scientific_files_equal':984,'old_available_logical_rows_equal':logical_equal,
        'R1_to_R2_counts':[{'R1':a,'R2':b,'n':n} for (a,b),n in disposition.items()],
        'summary_rows':len(summary),'paired_rows':len(paired),'A1_A2_equivalent_pairs':18,
        'still_unavailable_n':len(unavailable),'legsa_input_tables':{core.name:sha(core),add.name:sha(add)},
        'quantile_method':'numpy percentile default linear','native_calls':0,'legsa_evaluation':0,'reference_opens_in_aggregation':0,
        'files_sha256':{str(p.relative_to(scratch)):sha(p) for p in scratch.rglob('*') if p.is_file()}})
    dest=root/'90_AGGREGATE';dest.mkdir(exist_ok=False)
    for p in scratch.rglob('*'):
        if p.is_file():
            target=dest/p.relative_to(scratch);target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,target)
            if sha(p)!=sha(target):raise RuntimeError('HARD_STOP_AGGREGATE_COPY')
    shutil.rmtree(scratch)
    print(json.dumps({'rows':len(rows),'summary':len(summary),'paired':len(paired),'transitions':[{ 'R1':a,'R2':b,'n':n} for (a,b),n in disposition.items()]}))


if __name__=='__main__':main()
