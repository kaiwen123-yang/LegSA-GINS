"""Manuscript tables from retained HX and V3 records; no reference access."""
from __future__ import annotations
import csv
import json
import math
from pathlib import Path
import numpy as np

from .hx05_common import alias, dump, sha

SEQUENCES=('BY2','BY2H','BY2O')
METRICS=('yaw_rmse_deg','horizontal_rmse_m','up_rmse_m')
FAMILIES=('位置噪声','位置偏差','位置中断','速度中断','航向噪声','航向中断','多普勒','时间戳','A2')
HEADING=('EXT01','EXT02','EXT03','EXT04_FAR','EXT04_PAR','RTKLIB_UNMODIFIED_MOVING_BASE')
SEGMENTS={'occlusion_primary':(3369.94,3411.95),'occlusion_secondary':(3495.94,3508.94),
          'inside_union':None,'outside':None,'full':(3186.,3563.)}


def finite(value):
    try:return math.isfinite(float(value))
    except (TypeError,ValueError):return False


def fmt(value):
    return f'{float(value):.6f}'.rstrip('0').rstrip('.') if finite(value) else str(value)


def write_csv(path, rows):
    assert rows
    with Path(path).open('x',newline='',encoding='utf-8') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator='\n');writer.writeheader();writer.writerows(rows)


class Sources:
    def __init__(self, roots):
        self.roots=roots;self.files={};self.cells={};self.cache={}

    def read(self,path):
        key=alias(path,self.roots)
        if key not in self.cache:
            digest=sha(path);self.files[key]=digest
            with Path(path).open(newline='') as f:
                self.cache[key]=[dict(row,_line=i) for i,row in enumerate(csv.DictReader(f),2)]
        return self.cache[key]

    def ref(self,path,rows,fields,operation='exact archived field; display rounded to six decimal places'):
        key=alias(path,self.roots)
        if key not in self.files:self.files[key]=sha(path)
        return {'file':key,'sha256':self.files[key],'lines':[x['_line'] for x in rows],
                'fields':list(fields),'operation':operation}

    def cell(self,key,text,metrics,refs,notes=''):
        assert key not in self.cells and text
        self.cells[key]={'display':text,'metrics':metrics,'sources':refs,'notes':notes}
        return text


def choose(rows,**filters):
    return [r for r in rows if all(r.get(k)==v for k,v in filters.items())]


def heading_slice_statistics(selected):
    """Keep archived causal hold errors; absent reference support is not zero."""
    n=len(selected);valid=sum(int(x['valid']) for x in selected)
    ve=[float(x['error_valid_deg']) for x in selected if finite(x['error_valid_deg'])]
    he=[float(x['error_hold_deg']) for x in selected if finite(x['error_hold_deg'])]
    return {'paired_epochs':n,'valid_epochs':valid,
            'availability':valid/n if n else 'UNAVAILABLE_NO_PAIRED_EPOCHS',
            'valid_scored_epochs':len(ve),
            'valid_rmse_deg':float(np.sqrt(np.mean(np.square(ve)))) if ve else 'UNAVAILABLE_NO_VALID_EPOCHS',
            'hold_scored_epochs':len(he),
            'hold_rmse_deg':float(np.sqrt(np.mean(np.square(he)))) if he else 'UNAVAILABLE_NO_PREVIOUS_VALID_HEADING'}


def long_cell(book,path,key,rows,kind):
    by={r['metric']:r for r in rows}
    keys={'heading':('availability','valid_rmse_deg','hold_rmse_deg'),
          'relative':('position_drift_m_per_100m','heading_drift_deg_per_min','aligned_horizontal_rmse_m','reference_path_length_m'),
          'nav':(*METRICS,'coverage_ratio'),
          'ratio':('ratio_fixed_rate','ratio_fixed_rmse_deg'),
          'q2':('q2_float_rate','q2_float_rmse_deg')}[kind]
    metrics={};parts=[];used=[];extra_refs=[]
    for name in keys:
        r=by.get(name)
        if r is None:
            reasons=[x for x in rows if x['metric'] in ('run_status','status','frozen_evaluation_status')]
            reason='; '.join(x['failure_flag']+': '+x['value'] for x in reasons) or 'NOT_REPORTED_IN_ARCHIVE'
            metrics[name]=reason;parts.append(name+'='+reason);used+=reasons
        else:
            v=r['value'];valid=finite(v)
            reason='UNAVAILABLE_'+(r['failure_flag'] if r['failure_flag']!='NONE' else 'NO_VALID_EPOCHS')
            metrics[name]=float(v) if valid else reason
            parts.append(name+'='+(fmt(v) if valid else reason));used.append(r)
            if name in ('availability','ratio_fixed_rate','q2_float_rate','coverage_ratio'):
                metrics[name+'_denominator']=r['denominator_or_valid_epochs']
                parts[-1]+=' ['+r['denominator_or_valid_epochs']+']'
    # Preserve diagnostic coverage separately from frozen matched/output coverage.
    if 'row_coverage' in by:
        r=by['row_coverage'];used.append(r);metrics['row_coverage']=float(r['value']);metrics['row_count']=r['denominator_or_valid_epochs']
        parts.append('rows='+r['denominator_or_valid_epochs'])
    if 'frozen_evaluation_status' in by and by['frozen_evaluation_status']['failure_flag']!='NONE':
        r=by['frozen_evaluation_status'];used.append(r)
        seq=r['sequence'];case='C00' if seq=='BY2' else r['start_mode']
        source=book.roots['HX02']/'RUNS'/f'{seq}__GINAV__NONE__{case}__NA'/'eval/D8_BOUNDED_GATE.json'
        bounds=json.loads(source.read_text());first=bounds['first_violation']
        metrics['failure_detail']=bounds
        parts=[f'ALGORITHM_FAILURE_DIVERGED: speed={fmt(first["speed_mps"])} m/s @ {fmt(first["time_seconds"])} s']
        key_source=alias(source,book.roots);book.files[key_source]=sha(source)
        extra_refs.append({'file':key_source,'sha256':book.files[key_source],'fields':['failure_classification','first_violation.speed_mps','first_violation.time_seconds'],'operation':'exact archived D8 violation; native process completion is not scientific success'})
    refs=[book.ref(path,used,('metric','value','denominator_or_valid_epochs','failure_flag','notes'))]+extra_refs
    return book.cell(key,'; '.join(parts),metrics,refs)


def main_tables(book,out):
    p=book.roots;longpath=p['HX02']/'90_AGGREGATE/EXTERNAL_FIVE_CATEGORY_TABLE.csv';long=book.read(longpath)
    offpath=p['HX02E']/'90_AGGREGATE/HARTLEY_OFFICIAL_TABLE.csv';official=book.read(offpath)
    abpath=p['V3']/'07C_FAILURE_FAMILY_CONFIG/FULL_ABLATION_TABLE_V3.csv';ab=book.read(abpath)
    main=[];supp=[]
    specs=[('双天线航向',m,'LIT' if 'RTKLIB' not in m else '-', 'METHOD','heading') for m in HEADING]
    specs += [('四足状态估计','HARTLEY_OFFICIAL','OFF-LIT','METHOD','relative'),
              ('四足状态估计','LEG-DR','C4','INPUT_REFERENCE','relative'),
              ('松耦合','LC01','LIT','METHOD','nav'),('单天线','EXT05C','LIT','METHOD','nav'),
              ('单天线','LC02_GINAV','-','METHOD','nav')]
    specs += [('LegSA参照',m,'V3','REFERENCE','nav') for m in ('F04','F02','F01')]
    supplements=[('松耦合','LC01-S','S','SUPPLEMENT','nav'),('单天线','EXT05C-S','S','SUPPLEMENT','nav'),
                ('四足状态估计','HARTLEY_OFFICIAL','OFF-DEF','SUPPLEMENT','relative'),
                ('四足状态估计','Hartley-S','S','UNVALIDATED_PORT','relative'),
                ('四足状态估计','Hartley-LIT','LIT','UNVALIDATED_PORT','relative'),
                ('双天线航向','EXT03','RATIO_FIXED_SUBSET','SUBSET','ratio'),
                ('双天线航向','RTKLIB_UNMODIFIED_MOVING_BASE','Q2_SUBSET','SUBSET','q2')]
    supplements += [('BY2H起点敏感性',m,c,'FILE_START_SUPPLEMENT','nav') for m,c in [('LC01','LIT'),('LC01-S','S'),('EXT05C','LIT'),('EXT05C-S','S')]]
    for table_name,registry,dest in [('MAIN',specs,main),('SUPP',supplements,supp)]:
        for index,(category,method,config,role,kind) in enumerate(registry,1):
            row={'category':category,'method':method,'config':config,'role':role,
                 'output_type':{'heading':'heading_only','relative':'relative_pose','nav':'imu_point_nav','ratio':'heading_subset','q2':'heading_subset'}[kind]}
            ids=[]
            for seq in SEQUENCES:
                key=f'{table_name}.{index:02d}.{seq}';ids.append(key)
                start='CONTRACT_START' if seq=='BY2H' else 'FILE_START'
                if role=='FILE_START_SUPPLEMENT' and seq!='BY2H':
                    row[seq]=book.cell(key,'NOT_APPLICABLE: BY2H FILE_START supplement',{},[],notes='This row is defined only for BY2H.');continue
                if role=='FILE_START_SUPPLEMENT':start='FILE_START'
                if method in ('F04','F02','F01'):
                    rr=choose(ab,method_id=method,sequence_id=seq);assert len(rr)==1
                    x=rr[0];metrics={k:float(x[k]) if finite(x[k]) else 'UNAVAILABLE_ARCHIVED_STATUS' for k in (*METRICS,'coverage_ratio')}
                    metrics['matched_epoch_count']=int(x['matched_epoch_count']);metrics['output_epoch_count']=int(x['output_epoch_count'])
                    text='; '.join(k+'='+fmt(metrics[k]) for k in METRICS)+f'; matched={metrics["matched_epoch_count"]}/{metrics["output_epoch_count"]}'
                    row[seq]=book.cell(key,text,metrics,[book.ref(abpath,rr,(*METRICS,'coverage_ratio','matched_epoch_count','output_epoch_count'))]);continue
                if method=='LEG-DR':
                    f=p['HX05']/'RUNS'/seq/'RESULT.json';d=json.loads(f.read_text());m=d['metrics']
                    keys=('position_drift_m_per_100m','heading_drift_deg_per_min','aligned_horizontal_rmse_m','reference_path_length_m')
                    vals={k:m[k] for k in keys}
                    ref={'file':alias(f,p),'sha256':sha(f),'fields':['metrics.'+k for k in keys],'operation':'exact generated metric; display rounded to six decimal places'}
                    book.files[alias(f,p)]=ref['sha256'];row[seq]=book.cell(key,'; '.join(k+'='+fmt(v) for k,v in vals.items()),vals,[ref]);continue
                if method=='HARTLEY_OFFICIAL':
                    selected=choose(official,method_id=method,config=config,sequence=seq);source=offpath
                else:
                    selected=choose(long,method_id=method,sequence=seq,start_mode=start);source=longpath
                assert selected,(method,seq,start)
                row[seq]=long_cell(book,source,key,selected,kind)
            row['source_ids']=' | '.join(ids)
            row['notes']='自写移植，未通过精度验证，见 HX-02D' if role=='UNVALIDATED_PORT' else '同一份运动学输入不经滤波能达到的漂移水平；机载姿态是输入；非文献方法' if method=='LEG-DR' else '子集指标，不替代主行' if role=='SUBSET' else 'BY2H FILE_START sensitivity' if role=='FILE_START_SUPPLEMENT' else 'v3 evaluation point; distinct output types retain their own denominators'
            dest.append(row)
    return main,supp


def degradation(book,out,supp):
    p=book.roots;r2=p['HX03R2']/'90_AGGREGATE'
    summary_path=r2/'DEGRADATION_EXTERNAL_SUMMARY_R2.csv';summ=book.read(summary_path)
    paired_path=r2/'DEGRADATION_PAIRED_R2.csv';pairs=book.read(paired_path)
    case_path=r2/'DEGRADATION_EXTERNAL_TABLE_R2.csv';cases=book.read(case_path)
    core_path=p['V3']/'07_AGGREGATE/CORE_541_DISTRIBUTION_V3.csv';core=book.read(core_path)
    add_path=p['V3']/'07_AGGREGATE/ADDENDUM_TABLE_V3.csv';add=book.read(add_path)
    output=[];structured={}
    for family in FAMILIES:
        registered_rows=choose(cases,family=family,method='LC01');ids={r['case_id'] for r in registered_rows};den=len(ids)
        assert den in (9,18,27)
        row={'family':family};sources=[];structured[family]={}
        for method in ('LC01','EXT05C','F02','F03','A04','F04','LC01-BR'):
            if method=='LC01-BR' and family!='A2':continue
            key=f'DEGRADATION.{family}.{method}';sources.append(key);values={};refs=[];pieces=[]
            for metric in METRICS:
                if method in ('LC01','EXT05C','LC01-BR'):
                    rr=choose(summ,level='family',group=family,method=method,metric=metric);assert len(rr)==1;x=rr[0]
                    stat={'median':float(x['median']) if finite(x['median']) else None,'p95':float(x['p95']) if finite(x['p95']) else None,'finite_n':int(x['finite_n']),'registered_n':int(x['registered_n']),'failure_n':int(x['failure_n'])}
                    assert stat['registered_n']==den
                    refs.append(book.ref(summary_path,rr,('median','p95','finite_n','registered_n','failure_n')))
                else:
                    source=add_path if family=='A2' else core_path
                    rr=[x for x in (add if family=='A2' else core) if x['method_id']==method and x['case_id'] in ids and (family=='A2' or x['metric']==metric)]
                    field=metric if family=='A2' else 'value';vv=[float(x[field]) for x in rr if finite(x.get(field))]
                    stat={'median':float(np.median(vv)) if vv else None,'p95':float(np.percentile(vv,95)) if vv else None,'finite_n':len(vv),'registered_n':den,'failure_n':den-len(vv)}
                    refs += [book.ref(source,rr,('case_id','method_id',field),'finite values for the listed case IDs; numpy median and percentile(95, method=linear); no PRE_FAILURE'),book.ref(case_path,registered_rows,('family','case_id'),'distinct case IDs define the registered denominator')]
                values[metric]=stat
                pieces.append(metric+('=' +fmt(stat['median'])+'/'+fmt(stat['p95']) if stat['finite_n'] else '=UNAVAILABLE_NO_FINITE_SAMPLES')+f' [finite={stat["finite_n"]}/{den}; failure_or_unavailable={stat["failure_n"]}]')
            text='18/18 原生发散' if family=='位置噪声' and method in ('LC01','EXT05C') else '; '.join(pieces)
            book.cell(key,text,values,refs,'median/P95; spread across cases, not a confidence interval');structured[family][method]=values
            if method!='LC01-BR':row[method]=text
            else:
                empty='NOT_APPLICABLE: A2 supplement is BY2 only'
                supp.append({'category':'A2退化补充','method':'LC01-BR','config':'LIT-BR','role':'MODIFIED_LC01_A2_ONLY','output_type':'degradation_family_summary','BY2':text,'BY2H':empty,'BY2O':empty,'source_ids':key,'notes':'改动过的 LC01；只用于 A2 补充；median/P95，不是三序列 C00 结果'})
        for target in ('F04','F02'):
            key=f'PAIRED.{family}.LC01-{target}';values={};refs=[];pieces=[]
            for metric in METRICS:
                rr=choose(pairs,level='family',group=family,method='LC01',reference_method=target,metric=metric);assert len(rr)==1;x=rr[0]
                n=int(x['paired_n']);v=float(x['difference_median']) if finite(x['difference_median']) else None
                values[metric]={'median':v,'paired_n':n};pieces.append(metric+'='+(fmt(v) if n else 'UNAVAILABLE_NO_FINITE_PAIRS')+f' [n={n}]')
                refs.append(book.ref(paired_path,rr,('difference_median','paired_n','difference_definition')))
            row['LC01_minus_'+target]=book.cell(key,'; '.join(pieces),values,refs);sources.append(key)
        row['source_ids']=' | '.join(sources)
        row['notes']='LC01 只移位置时间，F04 在 v3 下全程无有效航向，暴露不同' if family=='时间戳' else 'D14/D21: LC01、EXT05C 各 18/18 原生发散；PRE_FAILURE 不并入分布' if family=='位置噪声' else '各指标只纳入有限值；失败或不可用保留登记分母；配对仅双方有限'
        output.append(row)
    write_csv(out/'DEGRADATION_MANUSCRIPT.csv',output)
    return output,structured


def segmented(book,out):
    p=book.roots;rows=[]
    for method in HEADING:
        label='RTKLIB' if 'RTKLIB' in method else method
        native='EXT04' if method.startswith('EXT04') else label
        config='NONE' if native=='RTKLIB' else 'LIT'
        source=p['HX02']/'RUNS'/f'BY2O__{native}__{config}__FILE_START__NA'/'eval/HEADING/OUTPUT'/f'HEADING_ERROR_SERIES_{label}.csv'
        records=book.read(source);times=np.array([float(x['t_rel_s']) for x in records])
        primary=(times>=3369.94)&(times<=3411.95);secondary=(times>=3495.94)&(times<=3508.94);union=primary|secondary
        masks={'occlusion_primary':primary,'occlusion_secondary':secondary,'inside_union':union,'outside':~union,'full':np.ones(len(times),dtype=bool)}
        for segment,mask in masks.items():
            selected=[x for x,m in zip(records,mask) if m];statistics=heading_slice_statistics(selected)
            key=f'SEGMENT.{method}.{segment}'
            row={'method':method,'segment':segment,**statistics,'horizontal_rmse_m':'NOT_APPLICABLE_HEADING_ONLY','up_rmse_m':'NOT_APPLICABLE_HEADING_ONLY','status':'AVAILABLE' if statistics['valid_scored_epochs'] else 'NO_VALID_HEADING','source_id':key,'original_fields_json':'NOT_APPLICABLE_DERIVED_SEGMENT'}
            book.cell(key,'BY2O '+method+' '+segment,dict(row),[book.ref(source,selected,('t_rel_s','valid','error_valid_deg','error_hold_deg'),'closed segment mask; availability=sum(valid)/rows; RMS finite archived error values; do not restart the causal hold at segment boundaries')]);rows.append(row)
    source=p['V3']/'07_AGGREGATE/BY2O_SEGMENT_TABLE.csv'
    for x in book.read(source):
        if x['method_id'] not in ('LC01','EXT05C','F01','F02','F03','F04') or x['evaluator_contract']!='evaluator_contract_v3':continue
        key=f'SEGMENT.{x["method_id"]}.{x["segment_id"]}';n=x['count']
        row={'method':x['method_id'],'segment':x['segment_id'],'paired_epochs':'NOT_REPORTED_IN_SEALED_SEGMENT_TABLE','valid_epochs':'NOT_REPORTED_IN_SEALED_SEGMENT_TABLE','availability':'NOT_REPORTED_IN_SEALED_SEGMENT_TABLE','valid_scored_epochs':n,'valid_rmse_deg':x['yaw_rmse_deg'],'hold_scored_epochs':'NOT_REPORTED_IN_SEALED_SEGMENT_TABLE','hold_rmse_deg':'NOT_REPORTED_IN_SEALED_SEGMENT_TABLE','horizontal_rmse_m':x['h_rmse_m'],'up_rmse_m':x['up_rmse_m'],'status':x['status'],'source_id':key,'original_fields_json':json.dumps({k:v for k,v in x.items() if k!='_line'},ensure_ascii=False,separators=(',',':'))}
        book.cell(key,'verbatim sealed segment row',dict(row),[book.ref(source,[x],tuple(k for k in x if k!='_line'),'verbatim selected v3 row; unavailable heading-only fields are not imputed')]);rows.append(row)
    longpath=p['HX02']/'90_AGGREGATE/EXTERNAL_FIVE_CATEGORY_TABLE.csv'
    failure=choose(book.read(longpath),method_id='LC02_GINAV',sequence='BY2O',metric='frozen_evaluation_status');assert len(failure)==1
    for segment in SEGMENTS:
        key=f'SEGMENT.GINav.{segment}';text='ALGORITHM_FAILURE_DIVERGED: no segment evaluation'
        row={k:text for k in rows[0]};row.update(method='GINav',segment=segment,status=text,source_id=key,original_fields_json=failure[0]['notes'])
        book.cell(key,text,dict(row),[book.ref(longpath,failure,('value','failure_flag','notes'))]);rows.append(row)
    assert len(rows)==65
    write_csv(out/'BY2O_SEGMENT_TABLE_EXT.csv',rows)
    return rows


def build(roots,out):
    out=Path(out);out.mkdir(parents=True,exist_ok=False);book=Sources(roots)
    main,supp=main_tables(book,out);degr,structured=degradation(book,out,supp);segments=segmented(book,out)
    write_csv(out/'EXTERNAL_THREE_SEQUENCE_MANUSCRIPT.csv',main)
    write_csv(out/'EXTERNAL_THREE_SEQUENCE_SUPPLEMENT.csv',supp)
    dump(out/'SOURCE_CITATIONS.json',book.cells)
    dump(out/'SOURCE_SHA256.json',book.files)
    dump(out/'MANUSCRIPT_DATA.json',{'main':main,'supplement':supp,'degradation':structured,'segments':segments,'cells':book.cells})
    return {'main_rows':len(main),'supplement_rows':len(supp),'degradation_rows':len(degr),'segment_rows':len(segments),'source_files':len(book.files),'source_cells':len(book.cells)}
