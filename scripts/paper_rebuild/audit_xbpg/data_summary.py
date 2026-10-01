#!/usr/bin/env python3
"""Summarize complete scan caches without opening any estimator output."""
import argparse
import csv
import json
from pathlib import Path

import numpy as np
import yaml
from legsa_gins.paper_rebuild.audit_xbpg.data_scan import SESSIONS, NS, GPS_EPOCH_UNIX, quantiles, timeline


def write_csv(path, rows):
    fields=list(dict.fromkeys(k for r in rows for k in r))
    with path.open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=fields,lineterminator='\n');w.writeheader();w.writerows(rows)


def main(config):
    paths=yaml.safe_load(config.read_text())['paths'];root=Path(paths['audit_root'])/'data_audit'
    docs=Path(paths['code_root'])/'docs/paper_rebuild/audit_xbpg_20261001'
    datasets={f'S{i}':json.loads((root/f'S{i}.json').read_text()) for i in range(1,5)}
    go2={f'xb{i}':json.loads((root/f'xb{i}.json').read_text()) for i in range(1,5)}
    quality=[];coverage=[];pairing=[];support=[];full={}
    for seq,files in datasets.items():
        i=int(seq[1:]); base=root/'decoded'/seq
        a=np.load(base/'gnss1-raw.npz');b=np.load(base/'gnss2-raw.npz')
        t=a['RXM_RAWX__time_ns'];gstart=int(t.min());gend=int(t.max())
        for log,gr in go2.items():
            start=max(gstart,gr['time']['min_ns']);end=min(gend,gr['time']['max_ns']);span=max(0,(end-start)/NS)
            gt=np.load(root/'decoded'/f'{log}.npz')['time_ns']
            pairing.append(dict(sequence=seq,session_time=SESSIONS[i-1],go2_log=log,
                                gnss_start_ns=gstart,gnss_end_ns=gend,go2_start_ns=gr['time']['min_ns'],go2_end_ns=gr['time']['max_ns'],
                                intersection_start_ns=start if span else '',intersection_end_ns=end if span else '',intersection_s=span,
                                gnss_epochs_in_intersection=int(np.sum((t>=start)&(t<=end))) if span else 0,
                                go2_messages_in_intersection=int(np.sum((gt>=start)&(gt<=end))) if span else 0,
                                gnss_span_coverage=span/((gend-gstart)/NS),go2_span_coverage=span/gr['time']['span_s'],
                                pairing_status='UNIQUE_TIME_OVERLAP_CLOCK_CALIBRATION_UNVERIFIED' if span else 'NO_TIME_OVERLAP'))
        common,ia,ib=np.intersect1d(a['NAV_HPPOSECEF__itow_ms'],b['NAV_HPPOSECEF__itow_ms'],return_indices=True)
        xyz=lambda d,idx:np.array([d['NAV_HPPOSECEF__'+k][idx] for k in ('x_m','y_m','z_m')]).T
        length=np.linalg.norm(xyz(b,ib)-xyz(a,ia),axis=1)
        posa=dict(zip(a['NAV_PVT__itow_ms'],a['NAV_PVT__carrSoln']));posb=dict(zip(b['NAV_PVT__itow_ms'],b['NAV_PVT__carrSoln']))
        statepairs={}
        for tt in common:
            k=f'{posa.get(tt,"NA")}/{posb.get(tt,"NA")}';statepairs[k]=statepairs.get(k,0)+1
        finite=(~a['NAV_HPPOSECEF__invalid_ecef'][ia]) & (~b['NAV_HPPOSECEF__invalid_ecef'][ib])
        geod=np.load(base/'user_io-out-poi_geodetic.npz')
        trace=np.load(next(base.glob('trace_*.npz')))
        n=len(geod['measurement_ns']);diffs={}
        for tr,g in [('lat','p.vector3.x'),('lon','p.vector3.y'),('height','p.vector3.z'),('yaw','ypr.vector3.x'),('pitch','ypr.vector3.y'),('roll','ypr.vector3.z')]:
            diffs[tr]=float(np.max(np.abs(trace[tr]-geod[g]))) if len(trace[tr])==n else None
        detail=dict(rawx_g1_time=timeline(a['RXM_RAWX__time_ns']),rawx_g2_time=timeline(b['RXM_RAWX__time_ns']),
                    rawx_g1_minus_g2_ms=quantiles((a['RXM_RAWX__time_ns']-b['RXM_RAWX__time_ns'])/1e6) if len(a['RXM_RAWX__time_ns'])==len(b['RXM_RAWX__time_ns']) else {'status':'UNEQUAL_COUNT_NO_INDEX_PAIR'},
                    hp_exact_itow_pairs=len(common),hp_flags_valid_pairs=int(finite.sum()),hp_pair_baseline_length_m_all=quantiles(length),
                    hp_pair_baseline_length_m_valid=quantiles(length[finite]),carrier_state_pairs=statepairs,double_fixed_n=statepairs.get('2/2',0),
                    trace_vs_poi_geodetic_same_row_max_abs=diffs,
                    trace_arrival_minus_geodetic_arrival_s=quantiles((trace['arrival_ns']-geod['arrival_ns'])/NS),
                    trace_processed_lat_minus_lon_max_deg=float(np.max(np.abs(trace['processed_lat']-trace['lon']))),
                    trace_processed_lon_minus_lat_max_deg=float(np.max(np.abs(trace['processed_lon']-trace['lat']))),
                    reference_measurement_time=timeline(geod['measurement_ns']))
        full[seq]=detail
        np.savez_compressed(base/'paired_hp_observations.npz',itow_ms=common,gnss2_minus_gnss1_ecef_m=xyz(b,ib)-xyz(a,ia),length_m=length,flags_valid=finite,
                            carrier1=np.asarray([posa.get(tt,-1) for tt in common]),carrier2=np.asarray([posb.get(tt,-1) for tt in common]))
        for fname,r in files.items():
            tt=r.get('measurement_time',{});tt=tt if tt.get('n') else r.get('time',{})
            coverage.append(dict(sequence=seq,file=fname,source_alias=r['source_alias'],sha256=r['sha256'],bytes=r['bytes'],rows=r['rows'],
                                 scan_depth='FULL_STREAM_PARSED',semantic_scope='NUMERIC_SCHEMA_ONLY_SENSITIVE_VALUES_EXCLUDED' if r.get('sensitive_values_excluded') else 'SCHEMA_AND_SELECTED_PHYSICAL_SEMANTICS',
                                 rejected_rows=len(r.get('rejects',[])),details_alias=f'<AUDIT_ROOT>/data_audit/{seq}.json'))
            quality.append(dict(sequence=seq,source=fname,rows=r['rows'],rejects=len(r.get('rejects',[])),first_ns=tt.get('min_ns',''),last_ns=tt.get('max_ns',''),span_s=tt.get('span_s',''),unique_times=tt.get('unique_n',''),duplicate_times=tt.get('duplicate_n',''),out_of_order=tt.get('out_of_order_n',''),rate_hz=tt.get('unique_rate_hz',''),dt_p50_s=tt.get('adjacent_dt_s',{}).get('median',''),dt_p95_s=tt.get('adjacent_dt_s',{}).get('p95',''),max_gap_s=tt.get('unique_dt_s',{}).get('max',''),arrival_delay_p50_s=r.get('arrival_minus_measurement_s',{}).get('median',''),arrival_delay_max_s=r.get('arrival_minus_measurement_s',{}).get('max',''),status='PARTIAL_MALFORMED_RECORD_RETAINED' if r.get('rejects') else 'FULL_SCANNED'))
        for module,status,reason in [
            ('position+Go2_IMU/F01','BLOCKED_PHYSICAL_IDENTITY','Go2 stamp absolute overlap exists, but acquisition clock/PPS mapping and Go2-APC lever arm/installation for this recording are unverified; no BY2 transform copied.'),
            ('scalar_heading/F02_F03_A04_F04','NO_DOUBLE_FIXED_OBSERVATIONS','Exact HP iTOW paired observations exist; NAV-PVT carrSoln=2 has zero epochs in both receivers. Body geometry is independently unverified.'),
            ('B3_raw_vector','INPUT_DIAGNOSTIC_ONLY','ECEF differences available; receiver errors meters to tens of meters, zero dual fixed, unknown mount vector; no complete B3 solver identity inherited.'),
            ('RV','GNSS_ONLY_OBSERVATION_AVAILABLE','NAV-PVT velocity and sAcc decoded; not raw Doppler; fusion needs verified receiver-IMU lever arm and time.'),
            ('RD','NATIVE_INPUT_READINESS_CONDITIONAL_EPHEMERIS','RAWX doMes and SFRBX full histories present. Native decoder/ephemeris coverage and valid velocity count must be established in actual run.'),
            ('RP','RAW_FIELD_AVAILABLE_FUSION_BLOCKED','Go2 quaternion/rpy present and wxyz reconstruction matches; weak prior shares Go2 IMU, installation not independently certified.'),
            ('HV','FRAME_AND_TIME_UNVERIFIED','Go2 velocity present but exact captured SDK frame contract and world-yaw connection unknown; status-derived yaw is not reliable here.'),
            ('contact_based','DIAGNOSTIC_FIELDS_ONLY','Foot forces/positions/speeds present, no lowstate joint encoders or independent FK; no complete contact estimator enabled.'),
            ('commercial_reference','QUALIFIED_ONLY_AS_SAME_SOURCE_POI_REFERENCE','Trace matches original POI geodetic values but records arrival time; use original header timestamps and qualified POI transform. Not independent truth.'),
            ('RTKLIB_moving_base','NATIVE_EXPLORATORY_ELIGIBLE','Two valid UBX receiver streams and raw ephemeris messages exist; measured tags differ 7-8ms. No body-yaw conversion or baseline-length constraint.'),
        ]:support.append(dict(sequence=seq,module=module,status=status,reason=reason,dual_fixed_n=0,geometry='UNKNOWN_FOR_THIS_RECORDING',clock_mapping='OVERLAP_CONFIRMED_CALIBRATION_UNVERIFIED'))
    for log,r in go2.items():
        tt=r['time']
        coverage.append(dict(sequence=log,file=log+'.txt',source_alias=r['source_alias'],sha256=r['sha256'],bytes=r['bytes'],rows=r['total_message_candidates'],scan_depth='FULL_STREAM_PARSED',semantic_scope='NUMERIC_SCHEMA_UNITS_AND_QUATERNION_CHECK',rejected_rows=len(r['rejects']),details_alias=f'<AUDIT_ROOT>/data_audit/{log}.json'))
        quality.append(dict(sequence=log,source=log+'.txt',rows=r['rows'],rejects=len(r['rejects']),first_ns=tt['min_ns'],last_ns=tt['max_ns'],span_s=tt['span_s'],unique_times=tt['unique_n'],duplicate_times=tt['duplicate_n'],out_of_order=tt['out_of_order_n'],rate_hz=tt['unique_rate_hz'],dt_p50_s=tt['adjacent_dt_s']['median'],dt_p95_s=tt['adjacent_dt_s']['p95'],max_gap_s=tt['unique_dt_s']['max'],status='TAIL_PARTIAL_REJECTED'))
    for filename,rows in [('SEQUENCE_PAIRING.csv',pairing),('INPUT_SUPPORT.csv',support),('DATA_QUALITY.csv',quality),('DATA_COVERAGE.csv',coverage)]:write_csv(docs/filename,rows)
    (root/'SUMMARY.json').write_text(json.dumps(full,indent=2)+'\n')
    print(json.dumps(full,indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--local-config',type=Path,required=True)
    main(p.parse_args().local_config)
