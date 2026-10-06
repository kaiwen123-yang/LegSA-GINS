"""Eight synthetic/mock checks only; no real payload or search is opened."""
from dataclasses import dataclass, replace
from pathlib import Path
from types import SimpleNamespace
import hashlib
import importlib.util
import json
import math
import sys

import numpy as np
import pytest

from legsa_gins.paper_rebuild.horizontal_literature.shared_raw_backend import (
    RawxMeasurement, RawxEpoch, SignalIdentity, identity_text)
from legsa_gins.paper_rebuild.carrier_phase.rawx_fault_overlay import (
    apply_rawx_fault_overlay, code_doppler_fingerprint, local_time)
from legsa_gins.paper_rebuild.carrier_phase.arcs import ArcConfig, ArcTracker
from legsa_gins.paper_rebuild.carrier_phase.observations import from_rawx, EpochKey, single_difference

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts/paper_rebuild/carrier_phase"
sys.path.insert(0, str(SCRIPTS))
SIGS = (SignalIdentity(0,1,0,0), SignalIdentity(0,2,0,0), SignalIdentity(0,3,0,0),
        SignalIdentity(0,1,3,0), SignalIdentity(2,1,0,0))
GROUPS = ((0,0,0), (0,3,0), (2,0,0))
BASE = 315964800.0


def generated(count=501):
    result = {}
    for rx in (1,2):
        result[rx] = tuple(RawxEpoch(i*.2,0,0,0,1,tuple(
            RawxMeasurement(s,2e7+10*j+rx,1e6+10*j+rx+2*(i*.2),-2.,
                            min(64500,1000+i*200),45,3,2,3,7)
            for j,s in enumerate(SIGS))) for i in range(count))
    return result


def overlay(epochs):
    return apply_rawx_fault_overlay(epochs,base_time=BASE,window_s=(0.,100.),supported_groups=GROUPS,
        pivot_history={local_time(e,BASE):(SIGS[0],SIGS[3],SIGS[4]) for e in epochs[1]})


def import_script(name):
    spec=importlib.util.spec_from_file_location("test_"+name,SCRIPTS/(name+".py"))
    m=importlib.util.module_from_spec(spec);sys.modules[spec.name]=m;spec.loader.exec_module(m)
    return m


def test_01_fixed_events_preserve_time_code_clock_and_receiver_one():
    source=generated();result=overlay(source)
    assert result.epochs[1] is source[1]
    assert [x['start_s'] for x in result.audit['events']]==[25.,50.,75.]
    assert [x['modified_epochs'] for x in result.audit['events']]==[5,5,5]
    assert result.audit['events'][0]['signal']==identity_text(SIGS[0])
    assert result.audit['events'][2]['signal']==identity_text(SIGS[1])
    assert code_doppler_fingerprint(source)==code_doppler_fingerprint(result.epochs)
    assert all(m.carrier_valid and m.locktime_ms>0 for e in source[2] for m in e.measurements)
    assert result.audit['data_mode']=='RAWX_OBSERVATION_LEVEL_SEMISYNTHETIC'
    assert not result.audit['real_integer_truth_available']


def test_02_physical_arc_retirement_and_reacquisition_not_numeric_resurrection():
    source=generated();result=overlay(source);tracker=ArcTracker(ArcConfig(.21,.5));events={}
    for epoch in result.epochs[2]:
        es=tracker.update_epoch('2',EpochKey(0,epoch.gps_tow_seconds),
                               [from_rawx('2',epoch,m) for m in epoch.measurements])
        events[round(epoch.gps_tow_seconds,1)]={x.signal:x for x in es}
    assert events[25.][SIGS[0]].arc_token is None
    assert events[26.][SIGS[0]].arc_token != events[24.8][SIGS[0]].arc_token
    assert events[26.][SIGS[1]].arc_token == events[24.8][SIGS[1]].arc_token
    assert all(x.arc_token is None for x in events[50.].values())
    assert all(events[51.][s].arc_token != events[49.8][s].arc_token for s in SIGS)
    # The post-outage numeric phase is exactly the original again; identity is not.
    assert result.epochs[2][130].measurements[0].cp_mes_cycles == source[2][130].measurements[0].cp_mes_cycles


def test_03_phase_pulse_is_cycles_rx2_minus_rx1_not_code_or_halfcycle_edit():
    source=generated();result=overlay(source);i=375;s=SIGS[1]
    m0=source[2][i].measurements[1];m1=result.epochs[2][i].measurements[1]
    assert m1.cp_mes_cycles-m0.cp_mes_cycles==.25
    assert m1.tracking_status==m0.tracking_status and m1.locktime_ms==m0.locktime_ms
    e1=source[1][i]
    before=single_difference(from_rawx('1',e1,e1.measurements[1]),from_rawx('2',source[2][i],m0))
    after=single_difference(from_rawx('1',e1,e1.measurements[1]),from_rawx('2',result.epochs[2][i],m1))
    assert after.phase_cycles-before.phase_cycles==.25
    assert math.isclose(after.phase_m-before.phase_m,.25*from_rawx('2',source[2][i],m0).wavelength_m,abs_tol=1e-10)
    assert result.epochs[2][380].measurements[1]==source[2][380].measurements[1]


def test_04_pre_event_unqualified_signal_and_short_tail_not_replaced():
    source=generated();bad={rx:list(source[rx]) for rx in (1,2)}
    for rx in (1,2):
        for i in range(120,125):
            e=bad[rx][i]
            bad[rx][i]=replace(e,measurements=tuple(replace(m,do_mes_hz=float('nan')) for m in e.measurements))
    result=overlay(bad)
    assert result.audit['events'][0]['status']=='NOT_IMPLEMENTABLE'
    assert result.audit['events'][0]['start_s']==25.
    assert result.audit['events'][0]['modified_measurements']==0
    short=generated(51)
    result=apply_rawx_fault_overlay(short,base_time=BASE,window_s=(0.,10.),supported_groups=GROUPS)
    assert all(x['reason']=='INSUFFICIENT_REGISTERED_POSTFAULT_SUPPORT' for x in result.audit['events'])
    assert all(x['modified_measurements']==0 for x in result.audit['events'])


def test_05_sentinel_and_future_values_cannot_change_pre_event_selection():
    source=generated();result=overlay(source);bad={1:source[1],2:list(source[2])}
    e=bad[2][375];ms=list(e.measurements);ms[1]=replace(ms[1],cp_mes_cycles=-.5)
    bad[2][375]=replace(e,measurements=tuple(ms));changed=overlay(bad)
    assert changed.audit['events'][2]['signal']==result.audit['events'][2]['signal']
    assert changed.epochs[2][375].measurements[1].cp_mes_cycles==-.5
    assert changed.audit['events'][2]['modified_epochs']==4
    with pytest.raises(ValueError,match='strictly increasing'):
        overlay({1:source[1],2:(source[2][1],source[2][0],*source[2][2:])})


def test_06_anchor_cache_rejects_code_time_and_navigation_mismatch():
    trial=import_script('rawx_fault_trial');epochs=generated(2)
    inp={'registry_sha256':'registry','raw_sources':{'1':{'sha256':'one'},'2':{'sha256':'two'}},
         'navigation_override':{'sha256':'nav'}}
    nav={'schedule_index':0};records=[]
    for e in epochs[1]:
        t=local_time(e,BASE)
        records.append({'key':[0,e.gps_tow_seconds],'time_s':t,'navigation':nav,'anchor_ecef_m':[1.,2.,3.],
            'anchor_decision':{'time_s':t,'available':True,'source_time_s':t,'position_ecef_m':[1.,2.,3.]}})
    saved={'sequence':'X','window_s':[0.,.2],'base_time':BASE,'inputs':inp,'records':records}
    reuse=trial.SealedCodeAnchorReuse(saved,seal_sha256='s',plan_sha256='p')
    reuse.bind(sequence='X',window_s=[0.,.2],base_time=BASE,inputs=inp,epochs=epochs,navigation_audit={'sha256':'nav'})
    assert reuse.for_epoch((0,0.),0.,nav)['anchor_decision']['position_ecef_m']==[1.,2.,3.]
    with pytest.raises(RuntimeError,match='causal identity'):reuse.for_epoch((0,0.),.2,nav)
    with pytest.raises(RuntimeError,match='causal identity'):reuse.for_epoch((0,0.),0.,{'schedule_index':1})
    bad={1:epochs[1],2:list(epochs[2])};e=bad[2][0];ms=list(e.measurements);ms[0]=replace(ms[0],pr_mes_m=1.)
    bad[2][0]=replace(e,measurements=tuple(ms))
    with pytest.raises(RuntimeError,match='changed cached code'):reuse.verify_overlay(epochs,bad)


def test_07_prepare_default_and_optional_hooks_use_same_existing_builder(monkeypatch,tmp_path):
    rt=import_script('real_trial');epochs=generated(2)[1]
    ext=tmp_path/'ext';reg=ext/'inputs/X/INPUT.json';reg.parent.mkdir(parents=True)
    sources={}
    for rx in (1,2):
        f=tmp_path/f'rx{rx}.ubx';f.write_bytes(bytes([rx]))
        sources[f'gnss{rx}.ubx']={'source':str(f),'sha256':hashlib.sha256(f.read_bytes()).hexdigest()}
    reg.write_text(json.dumps({'base_time':BASE,'source_files':sources}))
    roots={'<EXT_REPRO_ROOT>':str(ext),'<EXT_REPRO_BUILD>':str(tmp_path)}
    monkeypatch.setattr(rt,'aliases',lambda _:roots);monkeypatch.setattr(rt,'expand',lambda p,r:Path(p))
    monkeypatch.setattr(rt,'revision',lambda _: 'mock');monkeypatch.setattr(rt,'source_snapshot',lambda _: {})
    monkeypatch.setattr(rt.raw,'iter_ubx_frames',lambda _: iter((2,0x15,e) for e in epochs))
    monkeypatch.setattr(rt.raw,'decode_rawx',lambda e:e)
    class Replay:
        def __init__(self,*a,**k):
            self.entries=[{'cutoff_relative_s':0.}];self.input_audit={'schedule':'mock','sha256':'nav'}
            self.qualification={};self.switches=[]
        def bind_inputs(self,*a):pass
        def __enter__(self):return self
        def __exit__(self,*a):return False
        def advance(self,t):return None,{'schedule_index':0}
    monkeypatch.setattr(rt,'NavigationReplay',Replay)
    @dataclass
    class SPP:
        position_ecef_m:tuple=(1.,2.,3.)
    spp_calls=[];builder_calls=[]
    monkeypatch.setattr(rt.raw,'gps_l1_code_spp',lambda *a,**k:(spp_calls.append(1) or SPP()))
    def build(*a,**k):
        builder_calls.append(tuple(k['groups']))
        return SimpleNamespace(y=np.zeros(2),A=np.zeros((2,1)),B=np.zeros((2,3)),Q=np.eye(2),
            metadata={},groups=(),ambiguity_labels=('N',)),[]
    monkeypatch.setattr(rt,'build_with_pivot_policy',build)
    args=dict(roots=tmp_path,code=tmp_path,sequence='X',start=0.,stop=.2,length=.35,max_gap=.21,tdcp_limit=.5,
              pivot_policy='reselect_when_missing')
    rt.prepare(SimpleNamespace(**args,output=tmp_path/'default'))
    assert len(spp_calls)==2 and len(builder_calls)==6
    default=json.loads((tmp_path/'default/PLAN.json').read_text())
    assert set(default['families'])==set(rt.FAMILIES) and 'data_mode' not in default
    class Reuse:
        identity={'mock':'bound'}
        def bind(self,**k):pass
        def verify_overlay(self,before,after):assert code_doppler_fingerprint(before)==code_doppler_fingerprint(after)
        def for_epoch(self,key,t,nav):return {'anchor_decision':{'time_s':t,'available':True,'held':False,
            'position_ecef_m':[1.,2.,3.],'status':'MOCK_CACHED'}}
    rt.prepare(SimpleNamespace(**args,output=tmp_path/'reuse'),anchor_reuse=Reuse(),prepare_families=('GPS_GAL_BDS_DUAL',),
        epoch_overlay=lambda e,b:SimpleNamespace(epochs=e,audit={'data_mode':'RAWX_OBSERVATION_LEVEL_SEMISYNTHETIC'}))
    assert len(spp_calls)==2 and len(builder_calls)==8
    saved=json.loads((tmp_path/'reuse/PLAN.json').read_text())
    assert saved['spp_calls']==0 and set(saved['families'])=={'GPS_GAL_BDS_DUAL'}


def test_08_frontend_supplied_contract_checked_both_before_and_after(monkeypatch,tmp_path):
    f=import_script('full_window_frontend');seen=[]
    plan={'sequences':[],'prepared_complete_sha256':'c','prepared_summary_sha256':'s',
          'budgets':{'total_processing_s':1200.}}
    monkeypatch.setattr(f,'checked',lambda *x:None)
    monkeypatch.setattr(f,'read',lambda p: {'status':'COMPLETE'} if Path(p).name=='COMPLETE.json' else plan)
    monkeypatch.setattr(f,'registered',lambda *x:seen.append('default'))
    args=SimpleNamespace(registration_commit='mock',output=tmp_path/'supplied',prepared=tmp_path)
    f.run(args,supplied_plan=plan,registration_check=lambda commit,p:seen.append('supplied'))
    assert seen==['supplied','supplied']
    f.run(SimpleNamespace(**{**vars(args),'output':tmp_path/'default'}))
    assert seen==['supplied','supplied','default','default']
    assert json.loads((tmp_path/'supplied/SUMMARY.json').read_text())['counts']['enumeration_calls']==0
    with pytest.raises(ValueError,match='EXPLICIT_REGISTRATION'):
        f.run(args,supplied_plan=plan)
