"""Input-only same-iTOW remap, with exact frozen receipt-nearest lineage replay."""
from __future__ import annotations
import re
from ...input_generation.process_data_compat import _nearest, _ffill_bfill, _status_base_rows
from ..ubx_nav_pvt import extract_pvt_velocity_rows
from ..clean5_parity.input_audit import epoch_key, stamp

POLICY='SAME_ITOW_REMAP_AUTHORIZED'
FOOTNOTE='时标项含 RV 同历元重配'


def replay_original_matches(status_path,raw_path,status,pvt,base_time):
    """Reuse original nearest + forward/backward fill; attach identity by receipt stamp."""
    base_rows,missing=_status_base_rows(status_path,base_time=base_time,max_rows=None)
    if missing or len(base_rows)!=len(status):raise ValueError('Original status-row replay mismatch')
    by_receipt={}
    for key,p in pvt.items():
        receipt=p['receipt_stamp']
        if receipt in by_receipt:raise ValueError('Ambiguous original PVT receipt identity')
        by_receipt[receipt]=key
    candidates=extract_pvt_velocity_rows(raw_path,base_time=base_time)
    for row in candidates:
        if row['stamp'] not in by_receipt:raise ValueError('Original PVT not in strict decoded receipt inventory')
        row['itow_ms']=by_receipt[row['stamp']]
        decoded=pvt[row['itow_ms']]['velocity_mps']
        if [round(row[k]*1000) for k in ('vn','ve','vd')]!=[round(v*1000) for v in decoded]:
            raise ValueError('Active PVT integer-mm/s decoder differs')
    selected=[]
    for base,s in zip(base_rows,status):
        if base['time']!=stamp(s,'sys_stamp.')-base_time:raise ValueError('Original sorted status lineage mismatch')
        match=_nearest(candidates,base['time'],key='time',tolerance=.1)
        selected.append({'match':match,'direct_match':match is not None})
    # All three PVT components are present together, so propagating the selected
    # source record is identical to the original per-component ffill then bfill.
    _ffill_bfill(selected,['match'])
    if any(r['match'] is None for r in selected):raise ValueError('Original PVT fill left missing identity')
    return selected


def remap_v1(v0_bytes,status,pvt,original_matches,*,base_time,window):
    lines=v0_bytes.splitlines(keepends=True)
    if len(lines)!=len(status) or len(lines)!=len(original_matches):raise ValueError('Remap row count mismatch')
    weeks={int(float(s['time_gps_wno'])) for s in status}
    if len(weeks)!=1:raise ValueError('Week rollover requires explicit contract')
    week=weeks.pop()
    utc=lambda key:315964800+week*604800+key/1000-18
    ledger=[];output=[];changed=0
    for index,(line,s,match) in enumerate(zip(lines,status,original_matches)):
        tokens=line.split();old=match['match'];key=epoch_key(s)
        if len(tokens)!=15:raise ValueError('Expected frozen GNSS15')
        original=[f'{float(format(old[k],".12g")):.6f}'.encode() for k in ('vn','ve','vd')]
        if tokens[7:10]!=original:raise ValueError(f'Frozen receipt-nearest RV replay mismatch row {index}')
        header=stamp(s,'header.stamp.');sys=stamp(s,'sys_stamp.')
        if abs(float(tokens[0])-(sys-base_time))>1e-6:raise ValueError('Frozen status timestamp lineage mismatch')
        valid=key in pvt
        if not valid and window[0]<=header-base_time<=window[1]:raise ValueError('Missing same-iTOW RV inside window')
        new=[f'{v:.6f}'.encode() for v in pvt[key]['velocity_mps']] if valid else tokens[7:10]
        # Preserve whitespace and every token other than the three RV values.
        spans=list(re.finditer(rb'\S+',line));parts=[];start=0
        for j,value in zip(range(7,10),new):parts.extend([line[start:spans[j].start()],value]);start=spans[j].end()
        parts.append(line[start:]);new_line=b''.join(parts);new_tokens=new_line.split()
        if new_tokens[:7]!=tokens[:7] or new_tokens[10:]!=tokens[10:]:raise ValueError('Non-RV token changed')
        is_changed=new!=tokens[7:10];changed+=is_changed;output.append(new_line)
        ledger.append({'row_index_zero_based':index,'itow_ms':key,'status_header_time':header-base_time,
            'status_sys_time':sys-base_time,'status_header_unix':header,'status_sys_unix':sys,
            'same_itow_time':utc(key)-base_time,'RV_valid':int(valid),'inside_window':window[0]<=header-base_time<=window[1],
            'old_RV_tokens':[v.decode() for v in tokens[7:10]],'new_RV_tokens':[v.decode() for v in new],
            'RV_tokens_changed':is_changed,'old_match_mode':'receipt_nearest' if match['direct_match'] else 'receipt_nearest_then_ffill_bfill',
            'old_PVT_itow_ms':old['itow_ms'],'old_PVT_time':utc(old['itow_ms'])-base_time,
            'old_PVT_receipt_unix':old['stamp'],'old_PVT_receipt_time':old['stamp']-base_time,
            'old_PVT_receipt_minus_itow_s':old['stamp']-utc(old['itow_ms']),
            'status_sys_minus_old_PVT_itow_s':sys-utc(old['itow_ms']),
            'same_itow_PVT_receipt_unix':pvt[key]['receipt_stamp'] if valid else 'UNAVAILABLE',
            'same_itow_PVT_receipt_minus_itow_s':pvt[key]['receipt_stamp']-utc(key) if valid else 'UNAVAILABLE',
            'missing_policy':'unchanged finite frozen placeholder; RV_valid=0' if not valid else 'exact same-iTOW observation'})
    return b''.join(output),{'policy':POLICY,'time_term_footnote':FOOTNOTE,'row_count':len(lines),
        'original_RV_replay_all_tokens_equal':True,'RV_changed_row_count':changed,
        'non_time_measurement_tokens_byte_equal_to_true_V0':changed==0,
        'position_and_std_tokens_byte_equal_to_true_V0':True,'yaw_and_std_tokens_byte_equal_to_true_V0':True,
        'RV_std_tokens_byte_equal_to_true_V0':True,'ledger':ledger,
        'changed_rows':[r for r in ledger if r['RV_tokens_changed']],
        'matching_source':'src/legsa_gins/input_generation/process_data_compat.py:_status_base_rows,_nearest,_ffill_bfill',
        'active_decoder_source':'src/legsa_gins/paper_rebuild/ubx_nav_pvt.py:extract_pvt_velocity_rows',
        'identity_method':'exact receipt stamp to UBX iTOW; no velocity reverse lookup','nearest_tolerance_seconds':.1}
