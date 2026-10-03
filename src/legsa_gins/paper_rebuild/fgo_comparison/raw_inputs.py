"""Undifferenced RAWX inputs for the two Wen papers, without reference access.

Reuse the existing decoder and broadcast library, not the moving-baseline DD
model. Raw-code WLS is only an initial guess; every retained code measurement
crosses into the graph, including large residuals. No trajectory is imported.
"""
from __future__ import annotations
import argparse
import collections
import ctypes
import hashlib
import json
import math
from pathlib import Path
import subprocess
import time

import numpy as np

from ..horizontal_literature import shared_raw_backend as raw
from ..horizontal_literature.phase2_runner import CompactCacheReader, validate_compact_cache
from ..horizontal_literature.reproduction_backend import rotate_with_geometric_flight
from ..horizontal_literature.reproduction_prepare import LIBRARY_PINS, SEQUENCES

C = 299792458.0
OMEGA = 7.2921151467e-5


def sha256(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda: f.read(1024*1024), b''): h.update(b)
    return h.hexdigest()


def dump(path, obj):
    Path(path).write_text(json.dumps(obj, indent=2, ensure_ascii=False, allow_nan=False)+'\n')


def aliases(path):
    return json.loads(Path(path).read_text())['aliases']


def portable(path, roots):
    value = str(path)
    for a, p in sorted(roots.items(), key=lambda x: -len(x[1])):
        if value == p or value.startswith(p+'/'): return a+value[len(p):]
    return value


def compile_corrections(roots):
    build = Path(roots['<FGO_BUILD>'])/'lib'
    build.mkdir(parents=True, exist_ok=True)
    code = Path(roots['<CODE_ROOT>'])
    source = code/'src/legsa_gins/paper_rebuild/fgo_comparison/rtklib_corrections.c'
    external = Path(roots['<HX02_EXTERNAL_ROOT>'])
    lib = Path(roots['<EXT_REPRO_BUILD>'])/'lib'
    for name, pin in LIBRARY_PINS.items():
        if sha256(lib/name) != pin: raise ValueError('Frozen RTKLIB library mismatch: '+name)
    header = external/'RTKLIB/src/rtklib.h'
    target = build/'libfgo_corrections.so'
    receipt = build/'BUILD.json'
    signature = {'source_sha256': sha256(source), 'header_sha256': sha256(header),
                 'rtklib': LIBRARY_PINS, 'rtklib_commit': '180043ee24b6d2b168f98b64be15f69d50046b1a'}
    if target.exists():
        old = json.loads(receipt.read_text())
        if old['inputs'] != signature or old['binary_sha256'] != sha256(target):
            raise ValueError('Existing correction extension differs; use new build identity')
        return target
    args = ['gcc', '-O2', '-shared', '-fPIC', '-Wall', '-Wextra', '-DTRACE',
            '-DENAGLO','-DENAQZS','-DENAGAL','-DENACMP','-DENAIRN','-DNFREQ=5','-DNEXOBS=3',
            '-I'+str(header.parent), str(source), '-L'+str(lib), '-lrtklib_legsa',
            '-Wl,-rpath,'+str(lib), '-lm', '-o', str(target)]
    subprocess.run(args, check=True, capture_output=True)
    dump(receipt, {'inputs': signature, 'binary_sha256': sha256(target),
                   'argv': [portable(x, roots) for x in args]})
    return target


class Corrections:
    def __init__(self, path):
        self.lib = ctypes.CDLL(str(path))
        ptr = ctypes.POINTER(ctypes.c_double)
        self.fun = self.lib.fgo_corrections
        self.fun.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_double,
                             ctypes.c_int, ptr, ptr, ctypes.c_double, ptr]
        self.fun.restype = ctypes.c_int

    def compute(self, provider, epoch, identity, point, azel):
        p = (ctypes.c_double*3)(*point)
        a = (ctypes.c_double*2)(*azel)
        out = (ctypes.c_double*6)()
        ok = self.fun(provider._handle, epoch.gps_week, epoch.gps_tow_seconds,
                      provider.satellite_number(identity), p, a,
                      raw.signal_frequency_hz(identity), out)
        if not ok: raise raw.RawBackendError('Atmosphere/TGD unavailable')
        return np.asarray(out)


def code_sigma(elevation, cno, parameters):
    """goGPS cofactor q; q is a variance, not an information weight.

    Wen2021 Eq15 labels q W then inverts it in Eq16. The author's executable
    convention (GNSS_Tools::cofactorMatrixCal_WLS then sqrt(1/weight)) resolves
    this as sigma=sqrt(q), so lower elevation/CNO means less information.
    """
    T,A,a,F = (float(parameters[k]) for k in ('T','A','a','F'))
    q = (1/np.sin(elevation)**2 * 10**(-(np.asarray(cno)-T)/a) *
         ((A/10**(-(F-T)/a)-1)*(np.asarray(cno)-T)/(F-T)+1))
    if np.any(~np.isfinite(q)) or np.any(q <= 0): raise ValueError('Invalid code cofactor')
    return np.sqrt(q)


def solve_code_wls(satellites, codes, sigma, systems, initial):
    """Independent code-only WLS, with only observed constellation clocks."""
    sat, codes, sigma = map(np.asarray, (satellites,codes,sigma))
    used = np.unique(systems)
    if len(codes) < 3+len(used): return None
    system_design = np.column_stack([np.asarray(systems)==s for s in used]).astype(float)
    point = np.asarray(initial,float).copy()
    clocks = np.zeros(len(used))
    for it in range(50):
        d = point-sat; r = np.linalg.norm(d,axis=1)
        J = np.column_stack((d/r[:,None],system_design))/sigma[:,None]
        residual = (codes-r-system_design@clocks)/sigma
        step, _, rank, _ = np.linalg.lstsq(J,residual,rcond=None)
        if rank != J.shape[1]: return None
        point += step[:3]; clocks += step[3:]
        if not np.isfinite(point).all() or np.linalg.norm(point)>1e8: return None
        if np.max(np.abs(step))<1e-4:
            all_clocks = np.full(2,np.nan); all_clocks[used] = clocks
            return point, all_clocks, it+1
    return None


def doppler_wls(satellites, velocities, clock_rates, frequencies, doppler,
                sigma_range_rate, point):
    """RAWX D is negative range rate: rho_dot = -lambda*D.

    Use broadcast satellite velocity/clock drift and the derivative of the
    first-order Sagnac term (GNC Eq9), with unrotated transmit positions here.
    Position factors independently use a rotated satellite, exactly once.
    """
    sv, vv = np.asarray(satellites), np.asarray(velocities)
    los = sv-np.asarray(point); los /= np.linalg.norm(los,axis=1)[:,None]
    H = np.column_stack((-los,np.ones(len(sv))))
    H[:,0] += OMEGA/C*sv[:,1]
    H[:,1] -= OMEGA/C*sv[:,0]
    pred0 = np.sum(los*vv,axis=1) + OMEGA/C*(vv[:,1]*point[0]-vv[:,0]*point[1])
    observed = -C/np.asarray(frequencies)*np.asarray(doppler)
    rhs = observed-pred0+C*np.asarray(clock_rates)
    Hwhite = H/np.asarray(sigma_range_rate)[:,None]
    if len(sv)<4 or np.linalg.matrix_rank(Hwhite)<4: return None
    x, *_ = np.linalg.lstsq(Hwhite,rhs/np.asarray(sigma_range_rate),rcond=None)
    cov = np.linalg.inv(Hwhite.T@Hwhite)
    return x[:3], cov[:3,:3], x[3], rhs-H@x


def selected_measurements(epoch, config, counts=None):
    counts = counts if counts is not None else collections.Counter()
    best = {}
    for m in epoch.measurements:
        counts['raw_signal_count']+=1
        ident = m.identity
        allowed = (ident.gnss_id,ident.sig_id,ident.freq_id) in ((0,0,0),(3,0,0),(3,1,0))
        if not allowed: counts['unsupported_signal']+=1; continue
        if not m.pseudorange_valid or not 1e6<m.pr_mes_m<1e8: counts['invalid_code']+=1; continue
        if m.cno_dbhz < config['minimum_cno_dbhz']: counts['below_cno']+=1; continue
        key = ident.gnss_id, ident.sv_id
        if key in best: counts['duplicate_signal']+=1
        if key not in best or (m.cno_dbhz,-ident.sig_id) > (best[key].cno_dbhz,-best[key].identity.sig_id): best[key]=m
    counts['selected_signal_count']+=len(best)
    return [best[k] for k in sorted(best)]


def bootstrap_code(provider, epoch, config):
    try:
        coarse=provider.pntpos_rawx_epoch(epoch,raw.RTKLIB_NAVSYS_GPS_BDS,[0,0,0])
    except raw.PntPosBridgeError as error:
        if 'PNTPOS_NO_SUPPORTED_RAW_MEASUREMENTS' in str(error): return None
        raise
    if coarse.accepted: return coarse.position_ecef_m
    try: return raw.gps_l1_code_spp(epoch,provider,min_cno_dbhz=config['minimum_cno_dbhz'],max_iterations=50).position_ecef_m
    except raw.RawBackendError: return None


def prepare(roots_path, sequence, config_path):
    roots=aliases(roots_path); config=json.loads(Path(config_path).read_text())
    dest=Path(roots['<FGO_ROOT>'])/'inputs'/sequence
    dest.mkdir(parents=True,exist_ok=False)
    old=Path(roots['<EXT_REPRO_ROOT>'])/'inputs'/sequence
    info=json.loads((old/'INPUT.json').read_text())
    cm=json.loads((old/'cache/CACHE_MANIFEST.json').read_text())
    if cm != info['cache']: raise ValueError('Registered raw cache identity changed')
    validate_compact_cache(old/'cache',source_fingerprint=info['cache']['source_fingerprint'],expected_pair_count=info['pair_count'])
    for r in (1,2):
        if sha256(old/f'gnss{r}.nav') != info['source_files'][f'gnss{r}.nav']['sha256']:
            raise ValueError('Navigation input pin mismatch')
    binary=compile_corrections(roots); correction=Corrections(binary)
    reader=CompactCacheReader(old/'cache')
    base=SEQUENCES[sequence][2]; window=SEQUENCES[sequence][3]
    times=315964800.0+reader.epochs['gps_week'].astype(float)*604800+reader.epochs['gps_tow_seconds']-18.0-base
    # A single fixed nearest-epoch rule is applied before observing any output.
    choices={}
    for i,t in enumerate(times):
        key=int(round(float(t)))
        if t>window[1]+0.001 or abs(t-key)>.05: continue
        if key not in choices or abs(t-key)<abs(times[choices[key]]-key): choices[key]=i
    selected=[choices[k] for k in sorted(choices)]
    nominal_slots=list(range(int(round(float(times[0]))),int(window[1])+1))
    n=len(selected); t=np.asarray(times[selected]); initial=np.full((n,3),np.nan); clocks=np.full((n,2),np.nan)
    dopp=np.full((n,3),np.nan); dcov=np.full((n,3,3),np.nan); fitcov=dcov.copy(); valid=np.zeros(n,bool)
    rows=[]; accounting=[]; previous=None; bootstrap_calls=0; code_calls=0
    started=time.perf_counter()
    with raw.RtklibBroadcastProvider(Path(roots['<EXT_REPRO_BUILD>'])/'lib/liblegsa_rtklib_bridge.so',[old/'gnss1.nav',old/'gnss2.nav']) as provider:
        for k,idx in enumerate(selected):
            epoch,_=reader.pair(idx); prefilter=collections.Counter(); ms=selected_measurements(epoch,config,prefilter)
            if epoch.leap_seconds != 18: raise ValueError('GPS/UTC leap-second contract mismatch')
            excluded=collections.Counter(); seed=previous
            if seed is None:
                bootstrap_calls+=1
                seed=bootstrap_code(provider,epoch,config)
            if seed is None:
                accounting.append({'epoch_index':k,'time_rel_s':float(t[k]),'raw_index':idx,'status':'NO_RAW_CODE_INITIAL_GEOMETRY','available_selected_signals':len(ms),'prefilter_counts':dict(prefilter)})
                continue
            records=[]
            for m in ms:
                try:
                    state=provider.state(m.identity,epoch.gps_week,epoch.gps_tow_seconds,m.pr_mes_m)
                    if state.health: excluded['UNHEALTHY']+=1; continue
                    sat=rotate_with_geometric_flight(state.position_ecef_m,seed)
                    azel=raw.azimuth_elevation(seed,sat)
                    if azel[1]<math.radians(config['minimum_elevation_deg']): excluded['BELOW_ELEVATION']+=1; continue
                    cor=correction.compute(provider,epoch,m.identity,seed,azel)
                    code=m.pr_mes_m+C*state.clock_bias_s-cor[0]-cor[1]-cor[2]+cor[3]
                    records.append((m,state,sat,azel,cor,code))
                except raw.RawBackendError: excluded['NO_BROADCAST_OR_CORRECTION']+=1
            if records:
                sats=np.asarray([r[2] for r in records]);codes=np.asarray([r[5] for r in records])
                systems=np.asarray([0 if r[0].identity.gnss_id==0 else 1 for r in records])
                sig=code_sigma(np.asarray([r[3][1] for r in records]),np.asarray([r[0].cno_dbhz for r in records]),config['code_weight_gnc'])
                code_calls+=1; sol=solve_code_wls(sats,codes,sig,systems,seed)
                if sol is not None:
                    initial[k],clocks[k],_=sol;valid[k]=True;previous=initial[k].copy()
                else: initial[k]=seed
                for j,(m,state,sat,azel,cor,code) in enumerate(records):
                    rows.append({'epoch_index':k,'system':int(systems[j]),'sv_id':m.identity.sv_id,'sig_id':m.identity.sig_id,
                                 'sat_pos_ecef_m':sat,'pseudorange_m':code,'raw_pseudorange_m':m.pr_mes_m,
                                 'pr_sigma_m':float(sig[j]),'pr_sigma_wen_m':float(code_sigma(azel[1],m.cno_dbhz,config['code_weight_wen'])),
                                 'elevation_rad':azel[1],'cno_dbhz':m.cno_dbhz,'ionosphere_m':cor[0],'troposphere_m':cor[1],'tgd_m':cor[2],
                                 'satellite_clock_m':C*state.clock_bias_s})
                dm=[r for r in records if np.isfinite(r[0].do_mes_hz) and r[0].do_std_code<15]
                if len(dm)>=4:
                    frequencies=np.asarray([raw.signal_frequency_hz(r[0].identity) for r in dm])
                    dsigma=np.maximum(config['doppler_range_rate_floor_mps'],C/frequencies*np.asarray([.002*2**r[0].do_std_code for r in dm]))
                    ds=doppler_wls([r[1].position_ecef_m for r in dm],[r[1].velocity_ecef_mps for r in dm],
                                   [r[1].clock_drift_sps for r in dm],frequencies,[r[0].do_mes_hz for r in dm],dsigma,initial[k])
                    if ds is not None: dopp[k],fitcov[k]=ds[:2];dcov[k]=np.eye(3)*config['doppler_graph_std_mps']**2
            accounting.append({'epoch_index':k,'time_rel_s':float(t[k]),'raw_index':idx,'status':'WLS_INITIALIZED' if valid[k] else 'WLS_UNAVAILABLE',
                               'available_selected_signals':len(ms),'retained_codes':len(records),'prefilter_counts':dict(prefilter),'excluded':dict(excluded),'doppler_available':bool(np.isfinite(dopp[k]).all())})
            if k%50==0: print(json.dumps({'prepare':sequence,'epoch':k,'total':n,'raw_wls_initialized':int(valid[:k+1].sum())}),flush=True)
    data={key:np.asarray([r[key] for r in rows]) for key in rows[0]} if rows else {
        'epoch_index':np.empty(0,int),'system':np.empty(0,int),'sat_pos_ecef_m':np.empty((0,3)),
        'pseudorange_m':np.empty(0),'pr_sigma_m':np.empty(0),'pr_sigma_wen_m':np.empty(0)}
    data.update(time_rel_s=t,initial_position_ecef_m=initial,initial_clock_m=clocks,doppler_velocity_ecef_mps=dopp,
                doppler_covariance=dcov,doppler_fit_covariance=fitcov,spp_valid=valid,original_raw_index=np.asarray(selected))
    np.savez_compressed(dest/'RAW_INPUT.npz',**data)
    manifest={'schema':'fgo_comparison.raw_input.v1','sequence':sequence,'base_time':base,'window_seconds':window,
              'data_mode':'real_raw_reuse','synthetic_data_used':False,'semisynthetic_data_used':False,'trace_used_online':False,
              'raw_source_hashes':info['raw_hash_locks'],'provider_hashes':{name:x['sha256'] for name,x in cm['files'].items()},
              'navigation_hashes':{f'gnss{r}.nav':sha256(old/f'gnss{r}.nav') for r in (1,2)},
              'corrections_binary_sha256':sha256(binary),'config_hash':sha256(config_path),
              'code_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=roots['<CODE_ROOT>'],text=True).strip(),
              'input_sha256':sha256(dest/'RAW_INPUT.npz'),'epoch_count':n,'code_observation_count':len(rows),
              'raw_epoch_count':len(times),'unselected_raw_epoch_count':len(times)-n,
              'nominal_one_hz_slot_count':len(nominal_slots),'missing_one_hz_slots':[k for k in nominal_slots if k not in choices],
              'expected_window_one_hz_slots':int(window[1]-window[0])+1,
              'raw_pairing_gate':{'pair_count':info['pair_count'],'pair_failures':info.get('pair_failures',[])},
              'wls_initialization_count':code_calls,'coarse_raw_pntpos_initialization_calls':bootstrap_calls,
              'doppler_epochs':int(np.isfinite(dopp).all(axis=1).sum()),'raw_wls_valid_epochs':int(valid.sum()),
              'elapsed_seconds':time.perf_counter()-started,'accounting':accounting,
              'old_comparison_solver_reruns':0,'receiver_imu_as_body_imu':False,'final_v23_output_solver_input':False,
              'LegSA_output_solver_input':False,'per_case_tuning':False,'output_only_correction':False,
              'epoch_deleted_for_metric':False,'old_runtime_input_count':0}
    dump(dest/'INPUT_MANIFEST.json',manifest)
    return manifest


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--roots',required=True);p.add_argument('--sequence',choices=SEQUENCES,required=True);p.add_argument('--config',required=True)
    a=p.parse_args();prepare(a.roots,a.sequence,a.config)
