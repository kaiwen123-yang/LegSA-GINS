"""Read-only RD/RP/HV selection replay from GNSS input and native call timestamps.

This is a scheduler audit, not a filter replay. State-dependent residual/weight
acceptance cannot be reconstructed from provider timestamps and is unavailable.
"""
from __future__ import annotations
import csv
import json
import math
from pathlib import Path

import numpy as np

from ..manifest import sha256_file

SOURCE_LOCATIONS = {
    'call_sites': 'cpp/legsa_v23_port_core/src/kf_gins/gi_engine.cpp:398-407',
    'RD_selection': 'cpp/legsa_v23_port_core/src/kf_gins/gi_engine.cpp:996-1029',
    'RP_selection': 'cpp/legsa_v23_port_core/src/kf_gins/gi_engine.cpp:1080-1103',
    'HV_selection': 'cpp/legsa_v23_port_core/src/kf_gins/gi_engine.cpp:1137-1165',
    'RD_loader': 'cpp/legsa_v23_port_core/src/factors/raw_doppler_factor_loader.cpp:174-233',
    'RP_HV_loader': 'cpp/legsa_v23_port_core/src/factors/go2_weak_prior_loader.cpp:111-270',
    'RD_provider_gate': 'cpp/legsa_v23_port_core/src/factors/raw_doppler_factor.cpp:14-16',
    'RP_provider_gate': 'cpp/legsa_v23_port_core/src/factors/go2_weak_prior_factor.cpp:16-18',
    'native_time_precision': 'cpp/legsa_v23_port_core/src/runtime/port_runtime.cpp:1456-1460',
}
FIELDS = ('update_index','native_printed_gnss_time','gnss_input_row_1based','update_time',
          'position_valid','velocity_valid','yaw_valid','module','profile_enabled','provider_solver_enabled',
          'provider_path','provider_row_1based_including_header','provider_time','provider_source_time',
          'dt_signed_seconds','dt_absolute_seconds','tolerance_seconds','time_gate','static_provider_gate',
          'selection_status','previous_selection_same_source','source_selected_previously',
          'source_selection_occurrence','final_update_acceptance','state_gate_note')


def _bool(value, default=False):
    return default if value is None or value=='' else str(value).lower() in ('true','1','yes','on')


def _number(row, key, default):
    value=row.get(key)
    return float(default if value is None or value=='' else value)


def _read_csv(path):
    path=Path(path)
    if path.is_symlink() or not path.is_file():raise ValueError('Missing/symlink audit input: '+str(path))
    with path.open(newline='',encoding='utf-8-sig') as handle:
        return [{k:v.strip() for k,v in row.items()} for row in csv.DictReader(handle)]


def select_last_nearest(times, update_time, tolerance, eligibility=None):
    """C++ <= scan semantics: equal-distance winner is last in FILE order."""
    times=np.asarray(times,float)
    if not math.isfinite(update_time) or not math.isfinite(tolerance) or tolerance<0:
        raise ValueError('Invalid scheduler time or tolerance')
    if not np.isfinite(times).all():raise ValueError('Nonfinite provider time')
    distances=np.abs(times-update_time)
    allowed=distances<=tolerance
    if eligibility is not None:allowed &= np.asarray(eligibility,bool)
    indices=np.flatnonzero(allowed)
    if not len(indices):return None
    minimum=distances[indices].min()
    return int(indices[distances[indices]==minimum][-1])


def _provider(module, config):
    path_key={'RD':'raw_doppler_factor_path','RP':'go2_attitude_prior_path','HV':'go2_horizontal_velocity_prior_path'}[module]
    enable_key={'RD':'enable_raw_doppler','RP':'enable_go2_roll_pitch_prior','HV':'enable_go2_horizontal_velocity_prior'}[module]
    tolerance_key={'RD':'raw_doppler_time_tolerance_sec','RP':'go2_attitude_prior_time_tolerance_sec','HV':'go2_velocity_prior_time_tolerance_sec'}[module]
    enabled=_bool(config.get(enable_key))
    if not enabled:return {'enabled':False,'solver_enabled':False,'rows':[],'path':config.get(path_key),'tolerance':None}
    # No guessed defaults for frozen runtime settings or provider file identity.
    path=Path(config[path_key]);rows=_read_csv(path);times=np.array([_number(r,'time',0.) for r in rows])
    if not np.isfinite(times).all():raise ValueError('Provider time nonfinite: '+module)
    tolerance=float(config[tolerance_key]);eligible=np.ones(len(rows),bool);static=[]
    for r in rows:
        if module=='RD':
            lineage=all(r.get(k,'')==str(config[k]) for k in ('raw_doppler_backend_id','obs_source_hash',
                    'nav_source_hash','conversion_config_hash','covariance_policy'))
            valid=_bool(r.get('valid')) and r.get('provider_status')=='available'
            gate=lineage and valid and int(max(0,_number(r,'sat_count',0)))>=int(config['raw_doppler_min_sat'])
        elif module=='RP':
            gate=(r.get('source_status')=='active' and
                  _number(r,'std_roll_rad',float(config['go2_attitude_prior_std_roll_deg'])*math.pi/180)>0 and
                  _number(r,'std_pitch_rad',float(config['go2_attitude_prior_std_pitch_deg'])*math.pi/180)>0)
        else:
            # The native loader uses exact lowercase strings for these two fields.
            gate=(r.get('source_status')=='active' and r.get('go2_velocity_truth_claim','false')!='true')
        static.append(bool(gate))
    if module=='RD':
        # Formal CLEAN5 profile requests lineage-required RD. Native loader rejects
        # any invalid lineage, not only the selected epoch, before solving.
        lineage_all=all(all(r.get(k,'')==str(config[k]) for k in ('raw_doppler_backend_id','obs_source_hash',
                  'nav_source_hash','conversion_config_hash','covariance_policy')) for r in rows)
        solver_enabled=lineage_all and any(_bool(r.get('valid')) and r.get('provider_status')=='available' for r in rows)
    elif module=='RP':solver_enabled=any(r.get('source_status')=='active' for r in rows)
    else:
        eligible=np.array([_bool(r.get('update_flag'),True) for r in rows],bool)
        solver_enabled=any(g and e for g,e in zip(static,eligible))
    return {'enabled':enabled,'solver_enabled':bool(solver_enabled),'rows':rows,'path':str(path),
            'sha256':sha256_file(path),'times':times,'tolerance':tolerance,'eligible':eligible,'static':static}


def build_scheduling_ledger(*, config, gnss, native_rows, providers):
    """Pure selection ledger; providers are normalized by _provider, no raw reference."""
    gnss=np.asarray(gnss,float)
    if gnss.ndim!=2 or gnss.shape[1]!=18 or not np.isfinite(gnss).all():raise ValueError('Expected finite GNSS18')
    if np.any(np.diff(gnss[:,0])<=0) or not np.isin(gnss[:,15:18],[0,1]).all():raise ValueError('Invalid GNSS time/validity')
    if not np.all(gnss[:,15]==1):raise ValueError('P02 scheduling scope requires position_valid=1 on every row')
    if _bool(config.get('enable_qa_fallback')) or _bool(config.get('enable_basic_dual_yaw_baseline')):
        raise ValueError('Scheduler audit scope excludes QA routing/basic-dual early return')
    ledger=[];seen={m:{} for m in providers};last={m:None for m in providers}
    for native in native_rows:
        printed=float(native['gnss_time'])
        # Native diagnostic prints 9 decimals; identify the unique source token,
        # then replay using its full precision. This is serialization, not fitting.
        matches=np.flatnonzero(np.abs(gnss[:,0]-printed)<=.500001e-9)
        if len(matches)!=1:raise ValueError('Native GNSS time has no unique GNSS18 token at printed precision')
        j=int(matches[0]);update=float(gnss[j,0])
        for module,provider in providers.items():
            row={'update_index':native['update_index'],'native_printed_gnss_time':printed,
                 'gnss_input_row_1based':j+1,'update_time':update,'position_valid':int(gnss[j,15]),
                 'velocity_valid':int(gnss[j,16]),'yaw_valid':int(gnss[j,17]),'module':module,
                 'profile_enabled':provider['enabled'],'provider_solver_enabled':provider['solver_enabled'],
                 'provider_path':provider['path'],'tolerance_seconds':provider['tolerance'],
                 'final_update_acceptance':'NOT_CALLED','state_gate_note':'provider selection is not final update count',
                 'selection_status':'DISABLED_BY_PROFILE','time_gate':False,'static_provider_gate':None,
                 'previous_selection_same_source':False,'source_selected_previously':False,'source_selection_occurrence':0}
            if provider['enabled']:
                row['selection_status']='PROVIDER_DISABLED'
                if provider['solver_enabled']:
                    k=select_last_nearest(provider['times'],update,provider['tolerance'],provider['eligible'])
                    row['selection_status']='NO_MATCH_WITHIN_TIME_GATE'
                    if k is not None:
                        source=provider['rows'][k];dt=float(provider['times'][k])-update
                        count=seen[module].get(k,0)+1;seen[module][k]=count
                        row.update(provider_row_1based_including_header=k+2,provider_time=float(provider['times'][k]),
                            provider_source_time=_number(source,'source_time',provider['times'][k]),dt_signed_seconds=dt,
                            dt_absolute_seconds=abs(dt),time_gate=True,static_provider_gate=provider['static'][k],
                            selection_status='SELECTED_STATIC_PASS' if provider['static'][k] else 'SELECTED_STATIC_REJECT',
                            previous_selection_same_source=last[module]==k,source_selected_previously=count>1,
                            source_selection_occurrence=count,
                            final_update_acceptance='UNAVAILABLE_STATE_DEPENDENT' if provider['static'][k] else 'REJECTED_STATIC_PROVIDER_GATE',
                            state_gate_note={'RD':'residual gate when SA disabled; otherwise source-aware rejection/weighting',
                                'RP':'source-aware gate if prior_sourceaware enabled',
                                'HV':'source-aware gate if horizontal_velocity_source_aware enabled'}[module])
                        last[module]=k
            ledger.append(row)
    return ledger


def audit_scheduling(*, config, output_root, native_trace=None, gnss_path=None):
    """Write exclusive ledger+summary to caller-approved audit root (never modify runs)."""
    output=Path(output_root)
    if output.is_symlink() or any(p.is_symlink() for p in output.parents):raise ValueError('Symlink audit output')
    output.mkdir(parents=True,exist_ok=True)
    names=('AUXILIARY_SELECTION_LEDGER.csv','AUXILIARY_SCHEDULING_AUDIT.json')
    if any((output/name).exists() for name in names):raise FileExistsError('Scheduling audit already exists')
    summary={'schema_version':'paper_rebuild.clean5.parity.scheduler_audit.v1','sources':SOURCE_LOCATIONS,
        'trace_reference_read_count':0,'nav_read_count':0,'fit_used':False,'solver_executions':0,
        'tie_policy':'last equal-distance row in original provider CSV order; <= comparison',
        'consumption_policy':'no provider consumption/dedup; same source may be selected repeatedly',
        'state_gate_policy':'selection/static eligibility only; final acceptance UNAVAILABLE_STATE_DEPENDENT',
        'native_call_time_policy':'unique GNSS18 time token matching native 9-decimal serialization',
        'status':'UNAVAILABLE_NATIVE_CALL_TRACE','ledger_rows':0}
    ledger=[]
    if native_trace is not None and Path(native_trace).is_file():
        native_path=Path(native_trace)
        if native_path.name!='PORT_GNSS_UPDATE_TRACE.csv':raise ValueError('Only native GNSS-call diagnostic allowed')
        gnss_path=Path(gnss_path or config['gnsspath'])
        if gnss_path.is_symlink():raise ValueError('Symlink GNSS input')
        gnss=np.loadtxt(gnss_path,ndmin=2);native=_read_csv(native_path)
        providers={m:_provider(m,config) for m in ('RD','RP','HV')}
        ledger=build_scheduling_ledger(config=config,gnss=gnss,native_rows=native,providers=providers)
        summary.update(status='SCHEDULING_AUDIT_COMPLETE',actual_gnss_call_count=len(native),ledger_rows=len(ledger),
            gnss_sha256=sha256_file(gnss_path),native_trace_sha256=sha256_file(native_path),
            providers={m:{k:p.get(k) for k in ('path','sha256','enabled','solver_enabled','tolerance')} for m,p in providers.items()},
            modules={m:{'time_selected_count':sum(r['time_gate'] for r in ledger if r['module']==m),
                'static_pass_count':sum(r['static_provider_gate'] is True for r in ledger if r['module']==m),
                'static_reject_count':sum(r['static_provider_gate'] is False for r in ledger if r['module']==m),
                'repeated_source_selection_count':sum(r['source_selected_previously'] for r in ledger if r['module']==m),
                'unique_source_rows':len({r['provider_row_1based_including_header'] for r in ledger if r['module']==m and r['time_gate']}),
                'final_update_count':'UNAVAILABLE_FROM_SCHEDULER_ONLY'} for m in providers})
    with (output/names[0]).open('x',newline='',encoding='utf-8') as f:
        writer=csv.DictWriter(f,fieldnames=FIELDS);writer.writeheader();writer.writerows(ledger)
    summary['ledger_sha256']=sha256_file(output/names[0])
    with (output/names[1]).open('x',encoding='utf-8') as f:json.dump(summary,f,indent=2,allow_nan=False);f.write('\n')
    return summary
