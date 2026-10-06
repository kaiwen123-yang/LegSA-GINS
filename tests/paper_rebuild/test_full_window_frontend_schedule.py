"""Six scheduling contracts with fake data/services; no scientific kernels."""
from dataclasses import dataclass
import csv,importlib.util,json
from pathlib import Path
from types import SimpleNamespace
import pytest
from legsa_gins.paper_rebuild.carrier_phase.measurement import CarrierBaselineMeasurement

ROOT=Path(__file__).resolve().parents[2]
import sys
sys.path.insert(0,str(ROOT/'scripts/paper_rebuild/carrier_phase'))
spec=importlib.util.spec_from_file_location('full_window_frontend_schedule_under_test',ROOT/'scripts/paper_rebuild/carrier_phase/full_window_frontend.py')
frontend=importlib.util.module_from_spec(spec);sys.modules[spec.name]=frontend;spec.loader.exec_module(frontend)
LEDGER={'scheduler_runs':0,'mock_acquisition_calls':0,'mock_provider_advance_calls':0,
        'integer_search':0,'GLS':0,'GLRT':0,'sphere':0,'real_models':0,'native_navigation':0,'reference':0}


class Clock:
    def __init__(self):self.value=0.
    def monotonic(self):return self.value


@dataclass
class Model:
    time_s:float


@dataclass
class Domain:
    compatible_class_count:int=1
    phase_rows:int=5
    phase_rank:int=3
    retired_nodes:tuple=()


@dataclass
class Step:
    status:str
    domain:Domain|None
    measurement:CarrierBaselineMeasurement


class Harness:
    def __init__(self,tmp_path,monkeypatch,*,counts=(30,),service=.0,candidates=1,missing=(),gap_index=None,total_budget=1200.):
        self.clock=Clock();self.instances=[];self.acquisitions=[];self.service=service
        self.out=tmp_path/'out';self.sequences=[];self.saved={};self.models={};self.candidates=candidates
        for j,count in enumerate(counts):
            seq='MOCK'+str(j);self.sequences.append(seq);records=[]
            for i in range(count):
                t=100.+j*100.+i*.2+(2. if gap_index is not None and i>=gap_index else 0.)
                built=(j,i) not in set(missing)
                rec=dict(time_s=t,anchor_ecef_m=[1.,0.,0.],families={frontend.FAMILY:dict(status='BUILT' if built else 'UNAVAILABLE',file=f'model_{i}.npz')})
                records.append(rec)
            self.saved[seq]=dict(records=records,lambda_library='/not/read/mock-library.so')
        self.plan=dict(sequences=[dict(sequence=s,seal_sha256='synthetic',window_s=[self.saved[s]['records'][0]['time_s'],self.saved[s]['records'][-1]['time_s']+.2]) for s in self.sequences],
            source_pins={},prepared_complete_sha256='mock',prepared_summary_sha256='mock',lambda_library_sha256='mock',
            budgets=dict(total_processing_s=total_budget,enumeration_calls=100))
        def load_inputs(prepared,spec):
            s=spec['sequence'];saved=self.saved[s]
            return tmp_path/s/'MODELS',saved,dict(files={r['families'][frontend.FAMILY]['file']:dict(sha256='mock') for r in saved['records']}),{}
        def read(path):
            if Path(path)==frontend.ROOT/frontend.PLAN_REL:return self.plan
            if Path(path).name=='COMPLETE.json':return dict(status='COMPLETE')
            raise AssertionError('unexpected input read '+str(path))
        def acquire(block,library,source_id,counts,limits):
            LEDGER['mock_acquisition_calls']+=1
            self.clock.value+=self.service
            valid=len(block)==5 and all(m is not None for _,m in block)
            valid=valid and all(abs(block[k+1][0]['time_s']-block[k][0]['time_s']-.2)<.01 for k in range(4))
            if not valid:
                self.acquisitions.append(dict(source_id=source_id,unavailable=True))
                return None,dict(status='SELECTION_INPUT_UNAVAILABLE')
            n=len(self.acquisitions)+1
            # Deliberately better advertised score for newer sources. Scheduler
            # must never consult it to replace a healthy owner.
            source=SimpleNamespace(source_id=source_id,selected_at=block[-1][0]['time_s'],
                integers=tuple(range(self.candidates)),fingerprint=f'fp{n}',ordinal=n,advertised_width=1./n)
            self.acquisitions.append(dict(source_id=source_id,source=source))
            return source,dict(status='COMPLETE_MOCK_SOURCE',advertised_width=source.advertised_width)
        harness=self
        class Provider:
            def __init__(self,source,*,source_available_at_s,policy):
                self.source=source;self.source_available_at_s=source_available_at_s
                self.terminal=False;self.alive_nodes=();self.streak=0;self.seen=[]
                harness.instances.append(self)
            def advance(self,model,*,time_s,qualified_nodes,horizontal_axes,decision_time_s,calls):
                LEDGER['mock_provider_advance_calls']+=1
                assert decision_time_s>=self.source_available_at_s
                assert decision_time_s>=time_s
                self.seen.append((time_s,model is None,decision_time_s))
                self.streak=0 if model is None else self.streak+1
                valid=self.streak>=5 and model is not None and time_s==decision_time_s
                m=CarrierBaselineMeasurement(time_s,decision_time_s,valid,'MOCK_VALID' if valid else 'MOCK_VALIDATING',
                    (float(self.source.ordinal),0.,0.) if valid else None,
                    ((1.,0.,0.),(0.,1.,0.),(0.,0.,1.)) if valid else None)
                return Step(m.status,Domain() if model is not None else None,m)
        def forbidden(*a,**kw):raise AssertionError('scientific estimator must not execute in scheduler tests')
        monkeypatch.setattr(frontend,'time',self.clock)
        monkeypatch.setattr(frontend,'read',read)
        monkeypatch.setattr(frontend,'registered',lambda *a:None)
        monkeypatch.setattr(frontend,'checked',lambda *a:None)
        monkeypatch.setattr(frontend,'load_inputs',load_inputs)
        monkeypatch.setattr(frontend,'load_model',lambda path,rec,family:Model(rec['time_s']))
        monkeypatch.setattr(frontend,'axes',lambda anchor:None)
        monkeypatch.setattr(frontend,'current_nodes',lambda provider,t,events:((),{}))
        monkeypatch.setattr(frontend,'source_acquire',acquire)
        monkeypatch.setattr(frontend,'CompleteSetPointProvider',Provider)
        for name in ('enumerate_candidate_envelope','filter_length_necessary_support','prepare_selected_likelihood'):
            monkeypatch.setattr(frontend,name,forbidden)
        LEDGER['scheduler_runs']+=1
        frontend.run(SimpleNamespace(registration_commit='0'*40,prepared=str(tmp_path/'synthetic_prepared'),output=str(self.out)))
        self.rows={};self.csv={};self.acquire_rows={}
        for s in self.sequences:
            with (self.out/s/'EPOCHS.csv').open() as f:self.rows[s]=list(csv.DictReader(f))
            with (self.out/s/'CARRIER.csv').open() as f:self.csv[s]=list(csv.DictReader(f))
            with (self.out/s/'ACQUISITIONS.csv').open() as f:self.acquire_rows[s]=list(csv.DictReader(f))
        self.summary=json.loads((self.out/'SUMMARY.json').read_text())


def test_01_healthy_owner_not_ranked_and_promotion_epoch_invalid(tmp_path,monkeypatch):
    h=Harness(tmp_path,monkeypatch,counts=(25,));rows=h.rows['MOCK0'];csvrows=h.csv['MOCK0']
    first=h.instances[0].source.source_id
    assert rows[9]['status']=='PROMOTED_OWNER_NEXT_SLOT_ONLY' and rows[9]['valid']=='0'
    assert any(p.source.ordinal==2 and p.streak>=5 for p in h.instances)
    assert all(r['owner_source']==first for r in rows[10:] if r['valid']=='1')
    assert all(float(r['b_ecef_x'])==1. for r in csvrows if r['valid']=='1')
    assert len(csvrows)==25 and len({r['measurement_time'] for r in csvrows})==25


def test_02_recorded_point65_service_busy_and_no_model_catchup(tmp_path,monkeypatch):
    h=Harness(tmp_path,monkeypatch,counts=(18,),service=.65);rows=h.rows['MOCK0']
    assert all(rows[i]['status']=='WORKER_BUSY_NO_CURRENT_EXPORT' and rows[i]['valid']=='0' for i in (5,6,7))
    first=h.instances[0]
    assert [round(t,3) for t,missing,_ in first.seen if missing]==[101.,101.2,101.4]
    assert all(rows[i]['valid']=='0' for i in range(13))
    assert rows[12]['status']=='PROMOTED_OWNER_NEXT_SLOT_ONLY'
    assert rows[13]['valid']=='1'


def test_03_missing_current_model_is_invalid_and_not_stale_reuse(tmp_path,monkeypatch):
    h=Harness(tmp_path,monkeypatch,counts=(20,),missing=((0,12),));rows=h.rows['MOCK0']
    assert rows[10]['valid']=='1' and rows[11]['valid']=='1'
    assert all(rows[i]['valid']=='0' for i in range(12,17))
    assert rows[17]['valid']=='1'
    assert any(abs(t-102.4)<1e-10 and missing for t,missing,_ in h.instances[0].seen)


def test_04_complete65_source_preserved_not_truncated(tmp_path,monkeypatch):
    h=Harness(tmp_path,monkeypatch,counts=(10,),candidates=65)
    assert not h.instances
    assert len(h.acquire_rows['MOCK0'])==2
    assert all(r['status']=='COMPLETE_SOURCE_OVER_ACTIVATION_RESOURCE_CAP' and r['source_candidates']=='65' for r in h.acquire_rows['MOCK0'])
    assert all(r['valid']=='0' for r in h.rows['MOCK0'])


def test_05_global_deadline_retains_every_remaining_row_across_sequences(tmp_path,monkeypatch):
    h=Harness(tmp_path,monkeypatch,counts=(15,10),service=.65,total_budget=.3)
    assert h.summary['status']=='PARTIAL_PROCESSING_LIMIT'
    assert len(h.rows['MOCK0'])==15 and len(h.rows['MOCK1'])==10
    remaining=h.rows['MOCK0'][5:]+h.rows['MOCK1']
    assert all(r['status']=='NOT_EXECUTED_PROCESSING_LIMIT' and r['valid']=='0' for r in remaining)
    assert len(h.acquire_rows['MOCK0'])+len(h.acquire_rows['MOCK1'])==5
    assert sum(r['status']=='NOT_EXECUTED_PROCESSING_LIMIT' for s in h.sequences for r in h.acquire_rows[s])==4


def test_06_input_time_gap_clears_both_sources_without_resurrection(tmp_path,monkeypatch):
    h=Harness(tmp_path,monkeypatch,counts=(20,),gap_index=13);rows=h.rows['MOCK0']
    before={p.source.source_id for p in h.instances[:2]}
    assert rows[12]['owner_source'] and rows[12]['pending_source']
    assert rows[13]['source_change']=='True' and rows[13]['valid']=='0'
    assert rows[13]['owner_source']==rows[13]['pending_source']==''
    assert all(r['owner_source'] not in before and r['pending_source'] not in before for r in rows[13:])
    assert all(r['valid']=='0' for r in rows[13:])


@pytest.fixture(scope='module',autouse=True)
def receipt():
    yield
    print('FULL_WINDOW_SCHEDULER_MOCK_LEDGER '+json.dumps(LEDGER,sort_keys=True))
