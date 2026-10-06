"""Read-only, complete XB CSV/terminal audit and loss-accounted decoded caches.

Raw paths come exclusively from ignored local config. Caches retain integer ns
and row/block identities; they are observations, not solver providers or truth.
No alignment, resampling, reference-based choice, or estimator is performed.
"""
from __future__ import annotations

import ast
import binascii
import csv
import hashlib
import json
import math
import re
import struct
from collections import Counter, defaultdict
from decimal import Decimal
from pathlib import Path

import numpy as np
import yaml

SESSIONS = ('12-25-13', '12-33-29', '12-40-53', '12-49-30')
NS = 1_000_000_000
GPS_EPOCH_UNIX = 315964800
ANSI = re.compile(r'\x1b\][^\x07]*(?:\x07|\x1b\\)|\x1b\[[0-?]*[ -/]*[@-~]')
NUMBER = re.compile(r'^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?$')
GO2_DIMS = {'imu_state.quaternion': 4, 'imu_state.gyroscope': 3,
            'imu_state.accelerometer': 3, 'imu_state.rpy': 3,
            'position': 3, 'velocity': 3, 'foot_force': 4,
            'foot_position_body': 12, 'foot_speed_body': 12,
            'range_obstacle': 4}
GO2_SCALARS = ('error_code', 'mode', 'progress', 'gait_type',
               'foot_raise_height', 'body_height', 'yaw_speed',
               'imu_state.temperature')
UBX_NAMES = {(1, 7): 'NAV-PVT', (1, 19): 'NAV-HPPOSECEF',
             (1, 60): 'NAV-RELPOSNED', (2, 21): 'RXM-RAWX',
             (2, 19): 'RXM-SFRBX', (1, 34): 'NAV-CLOCK',
             (1, 53): 'NAV-SAT', (1, 67): 'NAV-SIG'}


def decimal_ns(value: str) -> int:
    """Convert decimal seconds without first rounding through binary float."""
    return int(Decimal(value) * NS)


def stamp_ns(row: dict, prefix: str) -> int:
    sec, nsec = int(row[prefix + 'secs']), int(row[prefix + 'nsecs'])
    if not 0 <= nsec < NS:
        raise ValueError('nanoseconds_out_of_range')
    return sec * NS + nsec


def quantiles(values) -> dict:
    a = np.asarray(values, dtype=float)
    finite = a[np.isfinite(a)]
    if not finite.size:
        return {'n': int(a.size), 'finite': 0}
    v = np.quantile(finite, [0, .01, .05, .5, .95, .99, 1])
    return dict(n=int(a.size), finite=int(finite.size),
                **dict(zip(('min', 'p01', 'p05', 'median', 'p95', 'p99', 'max'), map(float, v))))


def timeline(values) -> dict:
    a = np.asarray(values, dtype=np.int64)
    if not a.size:
        return {'n': 0}
    d = np.diff(a)
    unique = np.unique(a)
    span = int(unique[-1] - unique[0]) / NS
    return dict(n=int(a.size), unique_n=int(unique.size), first_ns=int(a[0]),
                last_ns=int(a[-1]), min_ns=int(unique[0]), max_ns=int(unique[-1]),
                span_s=span, duplicate_n=int(a.size - unique.size),
                adjacent_duplicate_n=int(np.sum(d == 0)), out_of_order_n=int(np.sum(d < 0)),
                message_rate_hz=(len(a)-1)/span if span else None,
                unique_rate_hz=(len(unique)-1)/span if span else None,
                adjacent_dt_s=quantiles(d / NS), unique_dt_s=quantiles(np.diff(unique) / NS),
                gaps_gt_20ms=int(np.sum(np.diff(unique) > 20_000_000)),
                gaps_gt_100ms=int(np.sum(np.diff(unique) > 100_000_000)),
                gaps_gt_1s=int(np.sum(np.diff(unique) > NS)))


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda: f.read(1024 * 1024), b''):
            h.update(b)
    return h.hexdigest()


def clean_terminal_line(line: str) -> str:
    """Remove terminal escape instructions; model backspace as deleting a char.

    CRLF is a line ending. Lone CR uses the last rendered fragment. This policy
    is loss-accounted in terminal_control_counts, never silently applied to CSV.
    """
    line = ANSI.sub('', line.rstrip('\r\n'))
    if '\r' in line:
        line = line.rsplit('\r', 1)[-1]
    if '\b' in line:
        chars = []
        for c in line:
            if c == '\b':
                if chars:
                    chars.pop()
            else:
                chars.append(c)
        line = ''.join(chars)
    return line


def parse_go2_block(lines: list[str]) -> dict:
    """Strict numeric subset of ROS echo YAML; no constructors or code eval.

    Supports numeric scalar leaves and numeric block lists, rejects duplicate
    keys, unknown syntax, nonfinite values and dimensions. Does not resample.
    """
    out, stack, list_key, list_indent = {}, [], None, None
    seen = set()
    for line in lines:
        if not line.strip():
            continue
        indent = len(line) - len(line.lstrip(' '))
        text = line.strip()
        if text.startswith('- '):
            if list_key is None or indent!=list_indent or not NUMBER.fullmatch(text[2:].strip()):
                raise ValueError('invalid_list_item')
            out[list_key].append(float(text[2:].strip()))
            continue
        if ':' not in text:
            raise ValueError('non_yaml_line')
        key, value = text.split(':', 1)
        if not re.fullmatch(r'[A-Za-z_][A-Za-z_0-9]*', key):
            raise ValueError('invalid_key')
        while stack and stack[-1][0] >= indent:
            stack.pop()
        full = '.'.join([x[1] for x in stack] + [key])
        if full in seen:
            raise ValueError('duplicate_key:' + full)
        seen.add(full)
        value = value.strip()
        list_key = None
        if not value:
            if full in GO2_DIMS:
                out[full] = []
                list_key = full
                list_indent = indent
            else:
                stack.append((indent, key))
        elif NUMBER.fullmatch(value):
            out[full] = int(value) if full in ('stamp.sec', 'stamp.nanosec') else float(value)
        else:
            raise ValueError('invalid_numeric:' + full)
    for key in ('stamp.sec', 'stamp.nanosec'):
        if key not in out:
            raise ValueError('missing:' + key)
    if not 0 <= out['stamp.nanosec'] < NS:
        raise ValueError('nanoseconds_out_of_range')
    for key, dim in GO2_DIMS.items():
        if key not in out or len(out[key]) != dim:
            raise ValueError('missing_or_bad_dimension:' + key)
    for key in GO2_SCALARS:
        if key not in out:
            raise ValueError('missing:' + key)
    if not all(np.isfinite(np.asarray(v, dtype=float)).all() for v in out.values()):
        raise ValueError('nonfinite_numeric')
    out['time_ns'] = out['stamp.sec'] * NS + out['stamp.nanosec']
    return out


def scan_go2(path: Path, cache_path: Path) -> dict:
    records = defaultdict(list)
    rejects, controls, shell = [], Counter(), []
    block, start, blocks, lines_n, delimiters = [], None, 0, 0, 0
    def consume(end, terminated):
        nonlocal blocks
        if start is None:
            return
        blocks += 1
        try:
            row = parse_go2_block(block)
        except ValueError as e:
            rejects.append(dict(block=blocks, start_line=start, end_line=end,
                                reason=str(e), delimiter_terminated=terminated))
            return
        for k, v in row.items():
            records[k].append(v)
        records['source_start_line'].append(start)
        records['delimiter_terminated'].append(terminated)
    with path.open(encoding='utf-8', errors='strict', newline='') as f:
        for number, raw in enumerate(f, 1):
            lines_n = number
            for key, marker in [('CR', '\r'), ('backspace', '\b'), ('escape', '\x1b')]:
                controls[key] += raw.count(marker)
            line = clean_terminal_line(raw)
            if line == 'stamp:':
                if start is not None:
                    consume(number-1, False)
                block, start = [line], number
            elif line == '---':
                delimiters += 1
                consume(number, True)
                block, start = [], None
            elif start is not None:
                block.append(line)
            elif line.strip():
                # Do not retain terminal account names / hostnames in exports.
                shell.append(number)
        if start is not None:
            consume(lines_n, False)
    arrays = {k.replace('.', '_'): np.asarray(v) for k, v in records.items()}
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(cache_path, **arrays)
    stats = {}
    for k in GO2_DIMS.keys() | set(GO2_SCALARS):
        a = np.asarray(records[k])
        stats[k] = dict(shape=list(a.shape), summary=quantiles(a),
                        adjacent_identical_n=int(np.sum(np.all(a[1:] == a[:-1], axis=1))) if a.ndim == 2 else int(np.sum(a[1:] == a[:-1])),
                        unique_values=int(np.unique(a).size))
    q = np.asarray(records['imu_state.quaternion'])
    rpy = np.asarray(records['imu_state.rpy'])
    w,x,y,z = q.T
    recovered = np.array([np.arctan2(2*(w*x+y*z),1-2*(x*x+y*y)),
                          np.arcsin(np.clip(2*(w*y-z*x),-1,1)),
                          np.arctan2(2*(w*z+x*y),1-2*(y*y+z*z))]).T
    error = np.arctan2(np.sin(recovered-rpy), np.cos(recovered-rpy))
    return dict(rows=len(records['time_ns']), total_message_candidates=blocks,
                delimiter_count=delimiters, line_count=lines_n, rejects=rejects,
                terminal_control_counts=dict(controls), shell_line_count=len(shell),
                accepted_unterminated_n=int(np.sum(~arrays['delimiter_terminated'])),
                time=timeline(records['time_ns']), fields=stats,
                quaternion_norm=quantiles(np.linalg.norm(q,axis=1)),
                quaternion_wxyz_vs_rpy_max_abs_rad=np.max(np.abs(error),axis=0).tolist(),
                cache=cache_path.name)


def parse_bytes_cell(value: str) -> bytes:
    parsed = ast.literal_eval(value)
    if not isinstance(parsed, bytes):
        raise ValueError('data_cell_not_bytes')
    return parsed


def ubx_frames(data: bytes):
    """Require complete exact frames; never repair checksum or skip junk."""
    offset = 0
    while offset < len(data):
        if data[offset:offset+2] != b'\xb5\x62':
            raise ValueError('non_ubx_or_junk')
        if offset + 8 > len(data):
            raise ValueError('truncated_ubx_header')
        length = struct.unpack_from('<H', data, offset+4)[0]
        end = offset + length + 8
        if end > len(data):
            raise ValueError('truncated_ubx_payload')
        frame = data[offset:end]
        a,b = 0,0
        for c in frame[2:-2]:
            a = (a+c) & 255
            b = (b+a) & 255
        if frame[-2:] != bytes((a,b)):
            raise ValueError('ubx_checksum')
        yield frame[2], frame[3], frame[6:-2], frame
        offset = end


def decode_ubx(cls: int, mid: int, p: bytes) -> dict:
    """Decode u-blox integer scale factors; validity flags remain separate."""
    key = (cls,mid)
    out = {}
    if key == (1,19):
        if len(p) != 28: raise ValueError('HPPOSECEF_length')
        out = dict(itow_ms=struct.unpack_from('<I',p,4)[0], version=p[0], flags=p[23])
        for i,k in enumerate(('x_m','y_m','z_m')):
            out[k] = struct.unpack_from('<i',p,8+4*i)[0]*.01 + struct.unpack_from('<b',p,20+i)[0]*.0001
        out['pacc_m'] = struct.unpack_from('<I',p,24)[0]*.0001
        out['invalid_ecef'] = bool(p[23]&1)
    elif key == (1,7):
        if len(p) not in (84,92): raise ValueError('PVT_length')
        out = dict(itow_ms=struct.unpack_from('<I',p,0)[0],year=struct.unpack_from('<H',p,4)[0],month=p[6],day=p[7],hour=p[8],minute=p[9],second=p[10],valid=p[11],nano=struct.unpack_from('<i',p,16)[0],fix_type=p[20],flags=p[21],carrSoln=(p[21]>>6)&3,gnss_fix_ok=bool(p[21]&1),numSV=p[23])
        for off,name,scale in [(24,'lon_deg',1e-7),(28,'lat_deg',1e-7),(32,'height_m',.001),(36,'hMSL_m',.001),(48,'velN_mps',.001),(52,'velE_mps',.001),(56,'velD_mps',.001),(60,'gSpeed_mps',.001),(64,'headMot_deg',1e-5)]:
            out[name]=struct.unpack_from('<i',p,off)[0]*scale
        for off,name,scale in [(40,'hacc_m',.001),(44,'vacc_m',.001),(68,'sacc_mps',.001),(72,'headacc_deg',1e-5)]:
            out[name]=struct.unpack_from('<I',p,off)[0]*scale
    elif key == (1,60):
        if len(p) not in (40,64): raise ValueError('RELPOSNED_length')
        out = dict(version=p[0], ref_station_id=struct.unpack_from('<H',p,2)[0],itow_ms=struct.unpack_from('<I',p,4)[0])
        hp = 32 if len(p)==64 else 20
        for i,name in enumerate(('relN_m','relE_m','relD_m')):
            out[name]=struct.unpack_from('<i',p,8+4*i)[0]*.01+struct.unpack_from('<b',p,hp+i)[0]*.0001
        flagoff=60 if len(p)==64 else 36
        flags=struct.unpack_from('<I',p,flagoff)[0]
        out.update(flags=flags,carrSoln=(flags>>3)&3,gnss_fix_ok=bool(flags&1),diff_soln=bool(flags&2),relpos_valid=bool(flags&4),moving_base=bool(flags&32),heading_valid=bool(flags&256))
        if len(p)==64:
            out['length_m']=struct.unpack_from('<i',p,20)[0]*.01+struct.unpack_from('<b',p,35)[0]*.0001
            out['heading_deg']=struct.unpack_from('<i',p,24)[0]*1e-5
            for i,n in enumerate(('accN_m','accE_m','accD_m','accLength_m')): out[n]=struct.unpack_from('<I',p,36+4*i)[0]*.0001
    elif key == (2,21):
        if len(p)<16 or len(p)!=16+32*p[11]: raise ValueError('RAWX_numMeas_length')
        tow,week=struct.unpack_from('<dH',p,0)
        leap=struct.unpack_from('<b',p,10)[0]
        if not math.isfinite(tow): raise ValueError('RAWX_nonfinite_time')
        # Receiver status bit 0 validates leapS. No empirical offset is fitted.
        out=dict(rcv_tow=tow, week=week, leap_s=leap, numMeas=p[11], rec_stat=p[12],version=p[13],time_ns=(GPS_EPOCH_UNIX+week*604800-leap)*NS+round(tow*NS))
        signals=[]
        for off in range(16,len(p),32):
            pr,cp,dop=struct.unpack_from('<ddf',p,off)
            signals.append(dict(pr_m=pr,cp_cycles=cp,doppler_hz=dop,gnss_id=p[off+20],sv_id=p[off+21],sig_id=p[off+22],freq_id=p[off+23],lock_ms=struct.unpack_from('<H',p,off+24)[0],cno=p[off+26],pr_std=p[off+27],cp_std=p[off+28],dop_std=p[off+29],trk_stat=p[off+30]))
        out['signals']=signals
    elif key == (2,19):
        if len(p)<8 or len(p)!=8+4*p[4]: raise ValueError('SFRBX_numWords_length')
        out=dict(gnss_id=p[0],sv_id=p[1],freq_id=p[3],numWords=p[4],version=p[6])
        if p[0]==0 and p[4]>=2:
            out['gps_subframe_id']=(struct.unpack_from('<I',p,12)[0]>>8)&7
    elif key == (1,34):
        if len(p)!=20: raise ValueError('CLOCK_length')
        itow,bias,drift,tacc,facc=struct.unpack('<IiiII',p)
        out=dict(itow_ms=itow,clock_bias_ns=bias,clock_drift_nsps=drift,tacc_ns=tacc,facc_psps=facc)
    return out


def crc24q(data: bytes) -> int:
    crc=0
    for c in data:
        crc ^= c<<16
        for _ in range(8):
            crc <<= 1
            if crc & 0x1000000: crc ^= 0x1864CFB
    return crc & 0xffffff


def decode_novb(data: bytes) -> tuple[str, dict]:
    """NOV_B length and native CRC, INSPVAX interpreted only as reference."""
    if len(data)<32 or data[:3]!=b'\xaa\x44\x12': raise ValueError('NOV_B_header')
    header=data[3];length=struct.unpack_from('<H',data,8)[0]
    if len(data)!=header+length+4: raise ValueError('NOV_B_length')
    crc=binascii.crc32(data[:-4],0xffffffff)^0xffffffff
    if crc!=struct.unpack_from('<I',data,len(data)-4)[0]: raise ValueError('NOV_B_crc32')
    mid=struct.unpack_from('<H',data,4)[0]
    if mid!=1465: return f'NOV_B-{mid}', {}
    if header!=28 or length!=126: raise ValueError('INSPVAX_layout')
    week=struct.unpack_from('<H',data,14)[0];tow=struct.unpack_from('<I',data,16)[0]
    out=dict(week=week,itow_ms=tow,time_status=data[13],ins_status=struct.unpack_from('<I',data,28)[0],position_type=struct.unpack_from('<I',data,32)[0])
    for off,name in [(36,'lat_deg'),(44,'lon_deg'),(52,'height_m'),(64,'velN_mps'),(72,'velE_mps'),(80,'velU_mps'),(88,'roll_deg'),(96,'pitch_deg'),(104,'azimuth_deg')]:out[name]=struct.unpack_from('<d',data,off)[0]
    return 'NOV_B-INSPVAX', out


def scan_raw(path: Path, outdir: Path) -> dict:
    counts, declared, errors, signals, sfrbx = Counter(), Counter(), [], Counter(), Counter()
    tf_values=defaultdict(set)
    decoded=defaultdict(list); arrivals=[]; rawx_offsets=[]; bytes_n=0; ubx_n=0; rtcm_n=0
    outdir.mkdir(parents=True,exist_ok=True)
    with path.open(newline='',encoding='utf-8-sig') as f, (outdir/(path.stem+'.ubx')).open('wb') as uf:
        reader=csv.DictReader(f)
        for row_n,row in enumerate(reader,2):
            arrivals.append(decimal_ns(row['Time'])); declared[row.get('name','')]+=1
            try:
                data=parse_bytes_cell(row['data']);bytes_n+=len(data)
                if data.startswith(b'\xb5\x62'):
                    for cls,mid,p,frame in ubx_frames(data):
                        ubx_n+=1; name=UBX_NAMES.get((cls,mid),f'UBX-{cls:02x}-{mid:02x}');counts[name]+=1
                        uf.write(frame)
                        d=decode_ubx(cls,mid,p)
                        if not d: continue
                        d['row']=row_n; d['arrival_ns']=arrivals[-1]
                        if name=='RXM-RAWX':
                            rawx_offsets.append((d['arrival_ns']-d['time_ns'])/NS)
                            for s in d.pop('signals'):
                                signals[f"{s['gnss_id']}:{s['sig_id']}:{s['freq_id']}"]+=1
                                for field in ['doppler_hz','cno','cp_std','trk_stat']:
                                    decoded['RAWX_SIGNALS_'+field].append(s[field])
                            if not d['rec_stat']&1: errors.append(dict(row=row_n,reason='RAWX_leap_seconds_not_valid'))
                        if name=='RXM-SFRBX': sfrbx[f"{d['gnss_id']}:{d['sv_id']}:{d.get('gps_subframe_id','NA')}"]+=1
                        decoded[name].append(d)
                elif data.startswith(b'\xd3'):
                    off=0
                    while off<len(data):
                        if data[off]!=0xd3 or off+6>len(data): raise ValueError('RTCM_header')
                        n=((data[off+1]&3)<<8)+data[off+2];end=off+n+6
                        if end>len(data): raise ValueError('RTCM_length')
                        if crc24q(data[off:end-3])!=int.from_bytes(data[end-3:end],'big'): raise ValueError('RTCM_crc24q')
                        typ=(data[off+3]<<4)|(data[off+4]>>4);counts[f'RTCM-{typ}']+=1;rtcm_n+=1;off=end
                elif data.startswith(b'$'):
                    for line in data.strip().splitlines():
                        head,sep,tail=line.rpartition(b'*')
                        if not sep: raise ValueError('NMEA_missing_checksum')
                        ck=0
                        for v in head[1:]: ck^=v
                        if ck!=int(tail[:2],16): raise ValueError('NMEA_checksum')
                        fields=head[1:].split(b',')
                        name=('FP_A-'+fields[1].decode('ascii')) if fields[0]==b'FP' else ('NMEA-'+fields[0].decode('ascii'))
                        counts[name]+=1
                        if name=='FP_A-TF':
                            # Only frame ids and numeric transforms, never TEXT/network data.
                            edge=fields[5].decode('ascii')+'->'+fields[6].decode('ascii')
                            tf_values[edge].add(tuple(float(v) for v in fields[7:14]))
                elif data.startswith(b'\xaa\x44\x12'):
                    name,d=decode_novb(data);counts[name]+=1
                    d.update(row=row_n,arrival_ns=arrivals[-1]);decoded[name].append(d)
                else: counts['OTHER_PROTOCOL']+=1
            except (ValueError,SyntaxError,KeyError,struct.error) as e:
                errors.append(dict(row=row_n,reason=str(e)))
    arr={}
    for name,rows in decoded.items():
        if not rows: continue
        if isinstance(rows[0],dict):
            for key in rows[0]:
                if all(key in r for r in rows): arr[name.replace('-','_')+'__'+key]=np.asarray([r[key] for r in rows])
        else: arr[name]=np.asarray(rows)
    np.savez_compressed(outdir/(path.stem+'.npz'),**arr)
    return dict(rows=len(arrivals),time=timeline(arrivals),declared_message_counts=dict(declared),
                verified_message_counts=dict(counts),ubx_frames=ubx_n,rtcm_frames=rtcm_n,
                decoded_bytes=bytes_n,rejects=errors,rawx_signal_counts=dict(signals),
                sfrbx_counts=dict(sfrbx),rawx_arrival_minus_measurement_s=quantiles(rawx_offsets),
                fpa_tf_distinct_numeric_transforms={k:sorted(v) for k,v in tf_values.items()},
                decoded_cache=(path.stem+'.npz'))


def scan_csv(path: Path, cache: Path) -> dict:
    """Visit every cell. Numeric values and whitelisted categories only leave raw."""
    times,measurements,sys_times=[],[],[]; numeric=defaultdict(list); categories=defaultdict(Counter)
    n=0; rejects=[]; header=[]; nested_fail=0; transforms=set()
    sensitive=path.name in ('ntrip-info.csv','user_io-status.csv')
    with path.open(newline='',encoding='utf-8-sig') as f:
        reader=csv.DictReader(f);header=reader.fieldnames or []
        for n,row in enumerate(reader,1):
            if None in row or any(v is None for v in row.values()): rejects.append(dict(row=n+1,reason='column_count'))
            try:
                times.append(decimal_ns(row.get('Time',row.get('time',''))))
                if 'header.stamp.secs' in row: measurements.append(stamp_ns(row,'header.stamp.'))
                if 'sys_stamp.secs' in row: sys_times.append(stamp_ns(row,'sys_stamp.'))
            except (ValueError,KeyError): rejects.append(dict(row=n+1,reason='timestamp'))
            for k,v in row.items():
                if k is None or v is None: continue
                if sensitive: continue
                if k in ('Time','time') or k.endswith('.secs') or k.endswith('.nsecs'): continue
                if NUMBER.fullmatch(v): numeric[k].append(float(v))
                elif v in ('True','False'): categories[k][v]+=1
                elif k.endswith('frame_id'): categories[k][v]+=1
                elif k.startswith('processed_'):
                    try:
                        a=np.asarray(ast.literal_eval(v),dtype=float)
                        if a.size!=1: raise ValueError('nested_scalar_dimension')
                        numeric[k].append(float(a.ravel()[0]))
                    except (ValueError,SyntaxError): nested_fail+=1
                elif k=='transforms':
                    # ROS textual list is not JSON/YAML; preserve whole text locally
                    # and identify declared edge pairs only, never invent a matrix.
                    parents=re.findall(r'(?m)^\s*frame_id:\s*"([^"]*)"',v)
                    children=re.findall(r'child_frame_id:\s*"([^"]*)"',v)
                    transforms.update(zip(parents,children))
    arrays={k:np.asarray(v) for k,v in numeric.items() if len(v)==n}
    arrays['arrival_ns']=np.asarray(times,dtype=np.int64)
    if len(measurements)==n: arrays['measurement_ns']=np.asarray(measurements,dtype=np.int64)
    if len(sys_times)==n: arrays['sys_ns']=np.asarray(sys_times,dtype=np.int64)
    cache.parent.mkdir(parents=True,exist_ok=True)
    np.savez_compressed(cache,**arrays)
    stats={k:dict(nonempty_numeric=len(v),distribution=quantiles(v)) for k,v in numeric.items()}
    delta=(np.asarray(times,dtype=np.int64)-np.asarray(measurements,dtype=np.int64))/NS if len(times)==len(measurements) and times else []
    sysdelta=(np.asarray(sys_times,dtype=np.int64)-np.asarray(measurements,dtype=np.int64))/NS if len(sys_times)==len(measurements) and sys_times else []
    return dict(rows=n,columns=header,rejects=rejects,time=timeline(times),measurement_time=timeline(measurements),
                arrival_minus_measurement_s=quantiles(delta),sys_minus_measurement_s=quantiles(sysdelta),
                numeric=stats,categories={k:dict(v) for k,v in categories.items()},
                nested_parse_failures=nested_fail,tf_edges=sorted(transforms),sensitive_values_excluded=sensitive)


def scan_xlsx(path: Path) -> dict:
    from zipfile import ZipFile
    from xml.etree import ElementTree as ET
    ns='{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'
    sheets=[]
    with ZipFile(path) as z:
        for name in sorted(n for n in z.namelist() if re.fullmatch(r'xl/worksheets/sheet\d+\.xml',n)):
            count=0; numeric=defaultdict(list); formulas=0; blanks=0
            with z.open(name) as f:
                for event,elem in ET.iterparse(f,events=('end',)):
                    if elem.tag==ns+'row':
                        count+=1
                        for cell in elem.findall(ns+'c'):
                            col=re.sub(r'\d','',cell.attrib['r'])
                            val=cell.find(ns+'v')
                            formulas+=cell.find(ns+'f') is not None
                            if val is None: blanks+=1
                            elif cell.attrib.get('t','n')=='n': numeric[col].append(float(val.text))
                        elem.clear()
            sheets.append(dict(sheet_xml=name,rows=count,formulas=formulas,empty_value_cells=blanks,
                               numeric={str(k):quantiles(v) for k,v in numeric.items()}))
    return dict(rows=sum(x['rows'] for x in sheets),sheets=sheets,rejects=[])


def run(local_config: Path, part='all') -> None:
    paths=yaml.safe_load(local_config.read_text())['paths']
    raw=Path(paths['xbpg_raw_root']); root=Path(paths['audit_root'])/'data_audit'
    root.mkdir(parents=True,exist_ok=True)
    if part in ('all','go2'):
        for i in range(1,5):
            p=raw/'高层数据'/f'xb{i}.txt'; key=f'xb{i}'
            report=scan_go2(p,root/'decoded'/f'{key}.npz')
            report.update(source_alias=f'<XBPG_RAW>/高层数据/{p.name}',sha256=sha256(p),bytes=p.stat().st_size,data_mode='REAL_RAW',synthetic_data_used=False,semisynthetic_data_used=False)
            (root/f'{key}.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n')
            print(key,report['rows'],report['time'],flush=True)
    if part in ('all','gnss','userio'):
        for i,s in enumerate(SESSIONS,1):
            d=next((raw/'fixpositon数据').glob('*'+s+'_minimal')); summary={}
            if part=='userio':summary=json.loads((root/f'S{i}.json').read_text())
            for p in sorted(d.iterdir()):
                if not p.is_file(): continue
                if part=='userio' and p.name!='userio-raw.csv': continue
                if p.name in ('gnss1-raw.csv','gnss2-raw.csv','corr-raw.csv','userio-raw.csv'):
                    report=scan_raw(p,root/'decoded'/f'S{i}')
                elif p.suffix=='.csv': report=scan_csv(p,root/'decoded'/f'S{i}'/(p.stem+'.npz'))
                elif p.suffix=='.xlsx': report=scan_xlsx(p)
                else: report=dict(rows=None,rejects=[],status='IDENTITY_ONLY_UNSUPPORTED_TYPE')
                report.update(source_alias=f'<XBPG_RAW>/S{i}/{p.name.replace(d.name,"SESSION")}',sha256=sha256(p),bytes=p.stat().st_size,data_mode='REAL_RAW',synthetic_data_used=False,semisynthetic_data_used=False)
                summary[p.name.replace(d.name,'SESSION')]=report
                (root/f'S{i}.json').write_text(json.dumps(summary,indent=2,ensure_ascii=False)+'\n')
                print('S'+str(i),p.name,report['rows'],len(report['rejects']),flush=True)
            (root/f'S{i}.json').write_text(json.dumps(summary,indent=2,ensure_ascii=False)+'\n')
