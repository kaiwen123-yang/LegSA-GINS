"""Compact new/retained tables; no solver or reference access."""
from __future__ import annotations
import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from .evaluation import common_time_rows, statistics, evaluation_directory, resolve
from .raw_inputs import aliases, dump, portable, sha256
from .retained_results import read_retained
from .runner import json_safe, summarize_runs, write_csv


def series(descriptor):
    if not descriptor or not descriptor['exists']: return None
    frame=pd.read_csv(descriptor['path'])
    for key,value in descriptor['filters'].items(): frame=frame.loc[frame[key]==value]
    mapping={descriptor['time_column']:'time',**{v:k for k,v in descriptor['columns'].items()}}
    frame=frame.rename(columns=mapping)
    return frame[[c for c in ['time',*descriptor['columns']] if c in frame]].copy()


FIELDS=['sequence_id','method_id','start_policy','support','status','physical_point','input_layer',
        'expected_epoch_count','actual_epoch_count','finite_epoch_count','matched_epoch_count','missing_or_invalid_count',
        'own_actual_epoch_count','own_finite_epoch_count','own_matched_epoch_count','epoch_count_scope','common_nominal_gate_s',
        'paired_epoch_denominator','reference_epoch_count','coverage_fraction','coverage_denominator',
        'horizontal_rmse_m','vertical_rmse_m','position_3d_rmse_m','horizontal_p95_m','vertical_p95_m','position_3d_p95_m',
        'yaw_rmse_deg','roll_rmse_deg','pitch_rmse_deg','yaw_p95_deg','attitude_is_estimated',
        'first_output_s','last_output_s','maximum_gap_with_window_edges_s','native_invalid_epochs_in_window',
        'native_valid_maximum_gap_s','maximum_uncovered_interval_with_window_edges_s','held_age_max_s','gap_events_in_window',
        'solver_and_adapter_elapsed_s','native_runtime_seconds','runtime_boundary','solve_mode',
        'old_result_reused','metric_origin','geometric_audit_status','failure_classification','comparison_boundary',
        'base_time','window_start_s','window_end_s','source_path','source_row_key','error_path']


def audit_evaluation(roots,sequence):
    from ..clean5_sequence.io_audit import audited_open_records
    root=Path(roots['<FGO_ROOT>']);code=Path(roots['<CODE_ROOT>'])
    out=evaluation_directory(roots,sequence)
    recorded=json.loads((out/'EVALUATION.json').read_text()).get('access_log')
    path=resolve(recorded,roots) if recorded else root/'logs'/f'EVALUATE_{sequence}_FINAL_OPENAT.strace'
    records=audited_open_records(path,code)
    references=[r for r in records if r['path'].startswith(roots['<RAW_ROOT>']+'/') and 'trace' in Path(r['path']).name.lower()]
    passed=len(references)==1 and references[0]['return_code']>=0 and 'O_RDONLY' in references[0]['flags']
    receipt={'sequence':sequence,'evaluator_children':1,'reference_payload_opens':len(references),
             'reference_open_records':references,'openat_sha256':sha256(path),'passed':passed}
    dump(out/'EVALUATION_ACCESS.json',receipt)
    if not passed: raise ValueError('Offline reference access contract failed')
    return receipt


def publish_tables(roots_path, sequences):
    roots=aliases(roots_path);root=Path(roots['<FGO_ROOT>']);docs=Path(roots['<FGO_DOCS>'])
    rows=[];new=[];receipts=[]
    for seq in sequences:
        directory=evaluation_directory(roots,seq)
        audit_evaluation(roots,seq)
        evaluated=json.loads((directory/'EVALUATION.json').read_text())['rows']
        own=[r for r in evaluated if r['support']=='OWN_VALID']
        for row in evaluated:
            row.update(coverage_denominator='registered nominal 1Hz slots in closed window',
                       metric_origin='NEW_REAL_OUTPUT_OFFLINE_EVALUATION',
                       comparison_boundary='different sensor systems; GNSS1 and POI points explicitly separated',
                       runtime_boundary='native solve plus input loading/hash/AHRS/output adapter wall time; not online delay')
        errors={r['method_id']:pd.read_csv(directory/(r['method_id']+'_ERRORS.csv')) for r in own}
        # A same-point, raw-GNSS pair does not lose support because OiSAM had an IMU gap.
        raw_pair=common_time_rows([r for r in own if r['method_id'] in ('GNC','WEN_TC')],
                                 {m:errors[m] for m in ('GNC','WEN_TC')})
        for r in raw_pair: r['support']='COMMON_RAW_POSITION_TIME';r['comparison_boundary']='same GNSS1 point and pseudorange source; AHRS/IMU versus Doppler auxiliary input'
        retained=read_retained(roots,seq)
        v3=next(r for r in retained if r['method_id']=='V3_F04')
        old=series(v3['error_series'])
        poi_pair=[]
        if old is not None:
            start,end=v3['window_start_s'],v3['window_end_s']
            old=old.loc[(old.time>=start)&(old.time<=end)].copy()
            # Only existing actual epochs within the fixed 5ms matching gate;
            # no interpolation or reference-plus-error trajectory recovery.
            keys=np.rint(old.time.to_numpy()).astype(int)
            mask=np.abs(old.time.to_numpy()-keys)<=.005
            old=old.loc[mask].copy()
            # High-rate V3 can have two samples in the tolerance band. Choose
            # nearest in time without inspecting error magnitude.
            old['nominal']=np.rint(old.time).astype(int);old['distance']=np.abs(old.time-old.nominal)
            old=old.sort_values(['nominal','distance']).drop_duplicates('nominal').sort_values('time')
            old['valid']=np.isfinite(old[['horizontal_err_m','position_3d_err_m']]).all(axis=1).astype(int)
            oi=next(r for r in own if r['method_id']=='OISAM')
            v3common={**v3,'expected_epoch_count':oi['expected_epoch_count']}
            poi_pair=common_time_rows([oi,v3common],{'OISAM':errors['OISAM'],'V3_F04':old})
            for r in poi_pair:
                r['support']='COMMON_POI_OISAM_V3_TIME'
                r['metric_origin']='DERIVED_COMMON_TIME_FROM_RETAINED_ERRORS' if r['method_id']=='V3_F04' else 'NEW_REAL_OUTPUT_OFFLINE_EVALUATION'
                r['comparison_boundary']='same POI; each epoch within 5ms of same nominal second (pair separation <=10ms); different sensor inputs/system design'
                r['coverage_denominator']='registered 1Hz comparison slots; V3 own support preserved separately'
                if r['method_id']=='V3_F04':
                    r['source_path']=v3['error_series']['source_path']
                    r['source_row_key']=f"run_id={v3['run_id']};common_with=OISAM;nominal_gate_s=0.005"
                    r['error_path']=v3['error_series']['source_path']
            receipts.append({'sequence':seq,'retained_error':v3['error_series']['source_path'],
                             'read_payload_sha256':sha256(v3['error_series']['path']),
                             'operation':'read existing error series for common-time statistics; no old evaluator/solver',
                             'common_poi_epochs':poi_pair[0]['matched_epoch_count']})
        seqrows=evaluated+raw_pair+poi_pair+retained
        own_by_method={r['method_id']:r for r in own+retained if r['method_id'] in ('GNC','WEN_TC','OISAM','V3_F04')}
        for r in seqrows:
            if r['support'].startswith('COMMON_'):
                original=own_by_method[r['method_id']]
                for count in ('actual_epoch_count','finite_epoch_count','matched_epoch_count'):
                    r['own_'+count]=original.get(count)
                r['actual_epoch_count']=r['matched_epoch_count']
                r['epoch_count_scope']='actual/finite/matched count the selected common subset; own_* retain native window counts'
                r['common_nominal_gate_s']=.005
                r['comparison_boundary']+='; each method within 5ms of nominal second, not a pairwise 5ms gate' if r['support']!='COMMON_POI_OISAM_V3_TIME' else ''
            else:
                r['epoch_count_scope']='original own support; see coverage_denominator for retained results'
        rows.extend(seqrows);new.extend(evaluated+raw_pair+[r for r in poi_pair if r['method_id']=='OISAM'])
        write_csv(directory/'COMPARISON_TABLE.csv',[{k:r.get(k) for k in FIELDS} for r in seqrows],FIELDS)
        # Full retained source row strings stay external; the compact public
        # table links them and preserves every support/start variant.
        portable_retained=[]
        for r in retained:
            copy=dict(r)
            for name in ('error_series','trajectory'):
                if copy.get(name): copy[name]={k:v for k,v in copy[name].items() if k!='path'}
            portable_retained.append(copy)
        dump(directory/'RETAINED_SOURCE_ROWS.json',json_safe(portable_retained))
    write_csv(docs/'COMPARISON_TABLE.csv',[{k:r.get(k) for k in FIELDS} for r in rows],FIELDS)
    write_csv(docs/'METRICS.csv',[{k:r.get(k) for k in FIELDS} for r in new],FIELDS)
    dump(root/'TABLE_SOURCES.json',receipts)
    summarize_runs(roots_path)
    return rows


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--roots',required=True);parser.add_argument('--sequences',nargs='+',choices=['BY2','BY2H','BY2O'],required=True)
    args=parser.parse_args();print(json.dumps({'rows':len(publish_tables(args.roots,args.sequences))}))
