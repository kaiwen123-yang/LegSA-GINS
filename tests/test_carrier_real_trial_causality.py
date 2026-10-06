"""Causal NAV admission tests; no raw data, SPP, CILS or evaluator executed."""
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/paper_rebuild/carrier_phase/real_trial.py"
spec = importlib.util.spec_from_file_location("carrier_real_trial_causality", SCRIPT)
trial = importlib.util.module_from_spec(spec)
spec.loader.exec_module(trial)


def fixture_manifest(tmp_path, cutoff=100.0, **extra):
    nav = tmp_path / "prefix.nav"
    nav.write_bytes(b"synthetic navigation identity fixture")
    data = {
        "causal_cutoff_relative_s": cutoff,
        "old_full_history_navigation_loaded": False,
        "navigation": [{"path": str(nav), "sha256": trial.digest(nav)}],
    }
    data.update(extra)
    p = tmp_path / "NAVIGATION_MANIFEST.json"
    p.write_text(json.dumps(data))
    return p, nav


def test_explicit_prefix_equal_start_and_before_actual_epoch(tmp_path):
    p, nav = fixture_manifest(tmp_path)
    paths, audit = trial.checked_navigation_manifest(p, {}, start_s=100, first_epoch_s=100.198)
    assert paths == [nav]
    assert audit["first_processed_rawx_s"] == 100.198
    assert audit["inherited_full_history_navigation_opened"] is False


def test_no_default_full_history_fallback():
    with pytest.raises(ValueError, match="CAUSAL_NAVIGATION_MANIFEST_REQUIRED"):
        trial.checked_navigation_manifest(None, {}, start_s=100)


@pytest.mark.parametrize("cutoff", [None, True, "100", float("nan"), float("inf")])
def test_explicit_finite_cutoff_required(tmp_path, cutoff):
    p, _ = fixture_manifest(tmp_path, cutoff)
    with pytest.raises(ValueError, match="FINITE_CAUSAL_NAVIGATION_CUTOFF_REQUIRED"):
        trial.checked_navigation_manifest(p, {}, start_s=100)


def test_future_prefix_rejected_before_opening_navigation(tmp_path):
    p, nav = fixture_manifest(tmp_path, 100.2)
    nav.unlink()
    with pytest.raises(ValueError, match="NAVIGATION_PREFIX_AFTER_REQUESTED_START"):
        trial.checked_navigation_manifest(p, {}, start_s=100)


def test_actual_epoch_causality_is_separate_from_requested_start(tmp_path):
    p, _ = fixture_manifest(tmp_path, 100)
    with pytest.raises(ValueError, match="NAVIGATION_PREFIX_AFTER_FIRST_EPOCH"):
        trial.checked_navigation_manifest(p, {}, start_s=100, first_epoch_s=99.998)


@pytest.mark.parametrize("flag", [None, True])
def test_full_history_or_unspecified_source_is_not_admitted(tmp_path, flag):
    p, _ = fixture_manifest(tmp_path, old_full_history_navigation_loaded=flag)
    with pytest.raises(ValueError, match="FULL_HISTORY_NAVIGATION_NOT_ALLOWED"):
        trial.checked_navigation_manifest(p, {}, start_s=100)


def test_prefix_file_identity_is_required(tmp_path):
    p, nav = fixture_manifest(tmp_path)
    nav.write_bytes(b"changed")
    with pytest.raises(ValueError, match="explicit navigation identity changed"):
        trial.checked_navigation_manifest(p, {}, start_s=100)


def test_nonfinite_or_empty_input(tmp_path):
    p, _ = fixture_manifest(tmp_path)
    with pytest.raises(ValueError, match="FINITE_START_REQUIRED"):
        trial.checked_navigation_manifest(p, {}, start_s=float("nan"))
    with pytest.raises(ValueError, match="FINITE_FIRST_EPOCH_REQUIRED"):
        trial.checked_navigation_manifest(p, {}, start_s=100, first_epoch_s=float("nan"))
    data=json.loads(p.read_text()); data["navigation"]=[]; p.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="NAVIGATION_PREFIX_EMPTY"):
        trial.checked_navigation_manifest(p, {}, start_s=100)


def test_prepare_does_not_open_inherited_full_history_nav(tmp_path, monkeypatch):
    p, nav = fixture_manifest(tmp_path, 100)
    source = tmp_path / "synthetic.ubx"
    source.write_bytes(b"fake raw payload; decoded by stub")
    reg = tmp_path / "inputs/BY2"
    reg.mkdir(parents=True)
    info = {"base_time": 0, "navigation": [str(tmp_path/"missing_old1.nav"),
              str(tmp_path/"missing_old2.nav")], "source_files": {}}
    for rx in (1, 2):
        info["source_files"][f"gnss{rx}.ubx"] = {
            "source": "<EXT_REPRO_ROOT>/synthetic.ubx", "sha256": trial.digest(source)}
        info["source_files"][f"gnss{rx}.nav"] = {"sha256": "NEVER_OPEN"}
    (reg/"INPUT.json").write_text(json.dumps(info))
    monkeypatch.setattr(trial, "aliases", lambda _: {
        "<EXT_REPRO_ROOT>": str(tmp_path), "<EXT_REPRO_BUILD>": str(tmp_path)})
    monkeypatch.setattr(trial, "revision", lambda _: "synthetic-test-only")
    monkeypatch.setattr(trial, "source_snapshot", lambda _: {})
    monkeypatch.setattr(trial.raw, "iter_ubx_frames", lambda _: [(2, 0x15, b"")])
    epoch = SimpleNamespace(gps_week=1, gps_tow_seconds=100.198, receiver_status=0,
                            measurements=())
    monkeypatch.setattr(trial.raw, "decode_rawx", lambda _: epoch)
    monkeypatch.setattr(trial, "localtime", lambda e, _: e.gps_tow_seconds)
    class FakeProvider:
        last_qualification = {}
        def __init__(self, _lib, paths):
            assert paths == [nav]
        def __enter__(self): return self
        def __exit__(self, *_): return False
    monkeypatch.setattr(trial, "CheckedRtklibProvider", FakeProvider)
    def no_spp(*_args, **_kwargs):
        raise trial.raw.RawBackendError("synthetic test stub; no SPP")
    monkeypatch.setattr(trial.raw, "gps_l1_code_spp", no_spp)
    out=tmp_path/"prepared"
    trial.prepare(SimpleNamespace(output=out, code=tmp_path, roots=tmp_path/"roots",
        navigation_manifest=p, sequence="BY2", start=100., stop=101.,
        max_gap=.21, tdcp_limit=.5, length=.35))
    plan=json.loads((out/"PLAN.json").read_text())
    audit=plan["inputs"]["navigation_override"]
    assert audit["first_processed_rawx_s"] == 100.198
    assert audit["inherited_full_history_navigation_opened"] is False
    assert plan["records"][0]["spp_failure"] == "synthetic test stub; no SPP"


def schedule_fixture(tmp_path, cutoffs=(100., 120., 140.)):
    entries=[]; paths=[]
    for k,t in enumerate(cutoffs):
        directory=tmp_path/str(k); directory.mkdir()
        manifest,nav=fixture_manifest(directory,t)
        paths.append((manifest,nav))
        entries.append({"cutoff_relative_s":t,"manifest":str(manifest),
                        "manifest_sha256":trial.digest(manifest)})
    schedule=tmp_path/"schedule.json"
    schedule.write_text(json.dumps({"schema":"causal_navigation_schedule.v1",
        "old_full_history_navigation_loaded":False,"entries":entries}))
    return schedule,paths


def provider_recorder(monkeypatch):
    opened=[]; closed=[]
    class StubProvider:
        def __init__(self,library,paths):
            self.paths=paths; self.last_qualification={}
            opened.append(paths)
        def __enter__(self): return self
        def __exit__(self,*args): closed.append(self.paths)
    monkeypatch.setattr(trial,"CheckedRtklibProvider",StubProvider)
    return opened,closed


def test_schedule_delays_all_future_payload_opens_and_switches_exactly(tmp_path,monkeypatch):
    schedule,paths=schedule_fixture(tmp_path)
    opened,closed=provider_recorder(monkeypatch)
    read=Path.read_bytes; text=Path.read_text; reads=[]
    def read_bytes(path,*a,**kw):
        reads.append(path); return read(path,*a,**kw)
    def read_text(path,*a,**kw):
        reads.append(path); return text(path,*a,**kw)
    monkeypatch.setattr(Path,"read_bytes",read_bytes)
    monkeypatch.setattr(Path,"read_text",read_text)
    with trial.NavigationReplay({},"unused",start_s=100,schedule=schedule) as replay:
        assert opened==[]
        assert all(path not in reads for pair in paths for path in pair)
        one,audit=replay.advance(100.198)
        assert audit["causal_cutoff_relative_s"]==100
        same,_=replay.advance(119.999)
        assert one is same
        assert all(path not in reads for pair in paths[1:] for path in pair)
        two,audit=replay.advance(120.)
        assert two is not one and audit["causal_cutoff_relative_s"]==120
        assert all(path not in reads for path in paths[2])
        assert opened==[[paths[0][1]],[paths[1][1]]]
        assert closed==[[paths[0][1]]]
    assert closed==opened
    assert len(replay.switches)==2


def test_unused_future_manifest_may_be_absent_but_selected_one_must_exist(tmp_path,monkeypatch):
    schedule,paths=schedule_fixture(tmp_path)
    paths[1][0].unlink(); paths[1][1].unlink()
    opened,_=provider_recorder(monkeypatch)
    with trial.NavigationReplay({},"unused",start_s=100,schedule=schedule) as replay:
        replay.advance(100.198)
        with pytest.raises(FileNotFoundError):replay.advance(120)
        assert len(opened)==1


def test_schedule_jump_uses_latest_eligible_never_intermediate_or_future(tmp_path,monkeypatch):
    schedule,paths=schedule_fixture(tmp_path)
    opened,_=provider_recorder(monkeypatch)
    with trial.NavigationReplay({},"unused",start_s=100,schedule=schedule) as replay:
        _,audit=replay.advance(145)
        assert audit["causal_cutoff_relative_s"]==140
        assert opened==[[paths[2][1]]]


@pytest.mark.parametrize("times",[(120.,140.),(100.,100.),(100.,90.)])
def test_schedule_start_and_order_fail_closed(tmp_path,times):
    schedule,_=schedule_fixture(tmp_path,times)
    with pytest.raises(ValueError):trial.NavigationReplay({},"unused",start_s=100,schedule=schedule)


def test_schedule_declared_cutoff_cannot_launder_future_manifest(tmp_path,monkeypatch):
    schedule,paths=schedule_fixture(tmp_path)
    entry=json.loads(paths[1][0].read_text()); entry["causal_cutoff_relative_s"]=121
    paths[1][0].write_text(json.dumps(entry)); paths[1][1].unlink()
    data=json.loads(schedule.read_text()); data["entries"][1]["manifest_sha256"]=trial.digest(paths[1][0])
    schedule.write_text(json.dumps(data))
    provider_recorder(monkeypatch)
    with trial.NavigationReplay({},"unused",start_s=100,schedule=schedule) as replay:
        replay.advance(100.2)
        with pytest.raises(ValueError,match="SCHEDULE_MANIFEST_CUTOFF_MISMATCH"):
            replay.advance(120)


def test_schedule_identity_and_epoch_order_checked(tmp_path,monkeypatch):
    schedule,paths=schedule_fixture(tmp_path)
    provider_recorder(monkeypatch)
    with trial.NavigationReplay({},"unused",start_s=100,schedule=schedule) as replay:
        replay.advance(100.2)
        for t in (100.2,99.,float("nan")):
            with pytest.raises(ValueError,match="STRICTLY_INCREASING"):replay.advance(t)
        paths[1][0].write_text("modified")
        with pytest.raises(ValueError,match="IDENTITY_CHANGED"):replay.advance(120)


def test_exactly_one_navigation_mode(tmp_path):
    manifest,_=fixture_manifest(tmp_path)
    for kwargs in ({},{"manifest":manifest,"schedule":manifest}):
        with pytest.raises(ValueError,match="EXACTLY_ONE"):
            trial.NavigationReplay({},"unused",start_s=100,**kwargs)


def pivot_fixture(monkeypatch):
    from dataclasses import replace
    import math
    import numpy as np
    from legsa_gins.paper_rebuild.carrier_phase import multignss as mg
    from legsa_gins.paper_rebuild.horizontal_literature.reproduction_backend import PairGeometry
    ids=[trial.raw.SignalIdentity(0,sv,0,0) for sv in (1,2,3,4)]
    measurements=tuple(trial.raw.RawxMeasurement(i,2.1e7,1.1e8,-500.,2000,45,2,2,2,7) for i in ids)
    first=trial.raw.RawxEpoch(100.,2408,18,1,1,measurements)
    anchor=np.array([6378137.,0.,0.])
    def geometry(e1,e2,left,right,provider,point):
        u=np.array([.9,.1,.3]); known=0.
        return PairGeometry(anchor+2.1e7*u,anchor+2.1e7*u,u,u,known,0.,known,
                            math.radians(20+left.identity.sv_id))
    monkeypatch.setattr(mg,"pair_geometry",geometry)
    return first,replace(first),anchor,ids,{i:f"arc_{i.sv_id}" for i in ids}


def test_reselect_retains_qualified_pivot_despite_higher_elevation(monkeypatch):
    e1,e2,anchor,ids,arcs=pivot_fixture(monkeypatch)
    pivots={(0,0,0):ids[0]}
    model,events=trial.build_with_pivot_policy(e1,e2,object(),anchor,groups=[(0,0,0)],
        pivots=pivots,arc_ids=arcs,policy="reselect_when_missing")
    assert events==[] and model.groups[0].pivot==ids[0]


def test_reselect_uses_only_current_qualified_and_restarts_dd_labels(monkeypatch):
    from dataclasses import replace
    e1,e2,anchor,ids,arcs=pivot_fixture(monkeypatch)
    pivots={(0,0,0):ids[0]}
    before,_=trial.build_with_pivot_policy(e1,e2,object(),anchor,groups=[(0,0,0)],
        pivots=pivots,arc_ids=arcs)
    e2=replace(e2,measurements=tuple(m for m in e2.measurements if m.identity!=ids[0]))
    with pytest.raises(trial.raw.RawBackendError,match="NO_QUALIFIED"):
        trial.build_with_pivot_policy(e1,e2,object(),anchor,groups=[(0,0,0)],pivots=pivots,arc_ids=arcs)
    model,events=trial.build_with_pivot_policy(e1,e2,object(),anchor,groups=[(0,0,0)],
        pivots=pivots,arc_ids=arcs,policy="reselect_when_missing")
    assert model.groups[0].pivot==ids[-1] and pivots[(0,0,0)]==ids[-1]
    assert len(events)==1 and events[0]["integer_transfer"] is False
    assert not set(before.ambiguity_labels)&set(model.ambiguity_labels)


def test_no_pivot_switch_on_arbitrary_model_error(monkeypatch):
    e1,e2,anchor,ids,arcs=pivot_fixture(monkeypatch)
    pivots={(0,0,0):ids[0]}; calls=[]
    def fail(*args,**kwargs):
        calls.append(1); raise trial.raw.RawBackendError("UNRELATED_INPUT_ERROR")
    monkeypatch.setattr(trial,"build_multignss_epoch",fail)
    with pytest.raises(trial.raw.RawBackendError,match="UNRELATED"):
        trial.build_with_pivot_policy(e1,e2,object(),anchor,groups=[(0,0,0)],
            pivots=pivots,arc_ids=arcs,policy="reselect_when_missing")
    assert len(calls)==1 and pivots[(0,0,0)]==ids[0]


def test_schedule_registry_and_selected_prefix_lineage(tmp_path,monkeypatch):
    schedule,paths=schedule_fixture(tmp_path)
    data=json.loads(schedule.read_text()); data["registry_sha256"]="registry-A"
    data["entries"][0]["reuse_initial_prefix"]=True
    schedule.write_text(json.dumps(data))
    provider_recorder(monkeypatch)
    with trial.NavigationReplay({},"unused",start_s=100,schedule=schedule) as replay:
        with pytest.raises(ValueError,match="REGISTRY_MISMATCH"):
            replay.bind_inputs("wrong",0,{"1":"a","2":"b"})
        replay.bind_inputs("registry-A",0,{"1":"a","2":"b"})
        replay.advance(100.2)
        paths[1][1].unlink()
        # The new manifest lacks same-registry fields; reject before NAV open.
        with pytest.raises(ValueError,match="PREFIX_LINEAGE_MISMATCH"):
            replay.advance(120)


@pytest.mark.parametrize("hold,expected_built",[(0.,1),(20.,2)])
def test_prepare_anchor_hold_is_opt_in_past_only_and_never_interpolates(tmp_path,monkeypatch,hold,expected_built):
    from dataclasses import dataclass
    import numpy as np
    @dataclass
    class Spp:
        position_ecef_m: tuple
    p,nav=fixture_manifest(tmp_path)
    source=tmp_path/"synthetic.ubx";source.write_bytes(b"three synthetic frames")
    reg=tmp_path/"inputs/BY2";reg.mkdir(parents=True)
    info={"base_time":0,"source_files":{f"gnss{rx}.ubx":{
        "source":"<EXT_REPRO_ROOT>/synthetic.ubx","sha256":trial.digest(source)} for rx in (1,2)}}
    (reg/"INPUT.json").write_text(json.dumps(info))
    monkeypatch.setattr(trial,"aliases",lambda _: {"<EXT_REPRO_ROOT>":str(tmp_path),"<EXT_REPRO_BUILD>":str(tmp_path)})
    monkeypatch.setattr(trial,"revision",lambda _:"synthetic-only")
    monkeypatch.setattr(trial,"source_snapshot",lambda _: {})
    times=(100.198,101.198,121.198)
    monkeypatch.setattr(trial.raw,"iter_ubx_frames",lambda _: [(2,0x15,k) for k in range(3)])
    monkeypatch.setattr(trial.raw,"decode_rawx",lambda k: SimpleNamespace(gps_week=1,
        gps_tow_seconds=times[k],receiver_status=0,measurements=()))
    monkeypatch.setattr(trial,"localtime",lambda e,_:e.gps_tow_seconds)
    provider_recorder(monkeypatch)
    def spp(epoch,*_args,**_kwargs):
        if epoch.gps_tow_seconds==times[0]:return Spp((6378137.,0.,0.))
        raise trial.raw.RawBackendError("current code rank failure")
    monkeypatch.setattr(trial.raw,"gps_l1_code_spp",spp)
    built=[]
    def build(e1,e2,provider,anchor,**kwargs):
        built.append((e1.gps_tow_seconds,tuple(anchor)))
        return SimpleNamespace(y=np.zeros(2),A=np.ones((2,1)),B=np.ones((2,3)),Q=np.eye(2),
            groups=(),ambiguity_labels=("synthetic",),metadata={})
    monkeypatch.setattr(trial,"build_multignss_epoch",build)
    out=tmp_path/"prepared"
    trial.prepare(SimpleNamespace(output=out,code=tmp_path,roots=tmp_path/"roots",
        navigation_manifest=p,sequence="BY2",start=100.,stop=122.,max_gap=25.,tdcp_limit=.5,
        length=.35,max_anchor_hold_s=hold))
    plan=json.loads((out/"PLAN.json").read_text()); rows=plan["records"]
    assert len(rows)==3 and len(built)==len(trial.FAMILIES)*expected_built
    assert rows[0]["anchor_decision"]["status"]=="CURRENT_RAW_CODE_ANCHOR"
    assert rows[-1]["anchor_decision"]["status"]=="UNAVAILABLE_HOLD_TOO_OLD"
    assert rows[-1]["families"]=={}
    assert all(row["navigation"]["causal_cutoff_relative_s"]==100 for row in rows)
    assert all(row["anchor_decision"]["navigation_measurement"] is False for row in rows)
    if hold:
        assert rows[1]["anchor_decision"]["held"] is True
        assert rows[1]["anchor_decision"]["source_time_s"]==times[0]
        assert rows[1]["anchor_ecef_m"]==rows[0]["anchor_ecef_m"]
        assert rows[1]["spp_failure"]=="current code rank failure"
