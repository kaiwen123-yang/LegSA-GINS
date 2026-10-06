"""Six local empty-prefix interfaces; no real UBX, converter or native calls."""
from pathlib import Path
from types import SimpleNamespace
import hashlib
import importlib.util
import json
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def module(monkeypatch):
    name = "_empty_navigation_real_trial"
    spec = importlib.util.spec_from_file_location(
        name, ROOT / "scripts/paper_rebuild/carrier_phase/real_trial.py")
    mod = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, name, mod)
    spec.loader.exec_module(mod)
    return mod


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dump(path, value):
    path.write_text(json.dumps(value))
    return path


def manifest(tmp, time=66., available=False):
    paths = []
    if available:
        nav = tmp / f"navigation{time}.nav"
        nav.write_text("mock NAV; not passed to any native reader\n")
        paths = [{"path": str(nav), "sha256": digest(nav), "receiver": 2}]
    obj = dict(causal_cutoff_relative_s=time, old_full_history_navigation_loaded=False,
        navigation=paths, navigation_availability="AVAILABLE" if available else "NO_NAV_OUTPUT_AT_PREFIX",
        conversion_outcomes=[dict(receiver=i, returncode=0,
            navigation_output_present=bool(available and i == 2)) for i in (1, 2)],
        registry_sha256="registered", base_time=0., source_ubx_sha256={"1": "a", "2": "b"})
    return dump(tmp / f"manifest{time}.json", obj)


def schedule(tmp, files):
    return dump(tmp / "schedule.json", dict(schema="causal_navigation_schedule.v1",
        old_full_history_navigation_loaded=False, registry_sha256="registered",
        entries=[dict(cutoff_relative_s=t, manifest=str(p),
                      manifest_sha256=digest(p) if p.exists() else "future-not-written")
                 for t, p in files]))


def replay(module, path):
    r = module.NavigationReplay({}, Path("unused-library"), start_s=66.,
        schedule=path, allow_empty_navigation=True)
    r.bind_inputs("registered", 0., {"1": "a", "2": "b"})
    return r


def test_default_still_rejects_empty_prefix(module, tmp_path):
    p = manifest(tmp_path)
    with pytest.raises(ValueError, match="NAVIGATION_PREFIX_EMPTY"):
        module.checked_navigation_manifest(p, {}, start_s=66.)
    with pytest.raises(ValueError, match="NAVIGATION_PREFIX_EMPTY"):
        module.NavigationReplay({}, Path("unused"), start_s=66., manifest=p)


def test_opt_in_requires_explicit_success_and_matching_source(module, tmp_path):
    p = manifest(tmp_path)
    original = json.loads(p.read_text())
    mutations = [
        {"navigation_availability": "AVAILABLE"},
        {"conversion_outcomes": None},
        {"conversion_outcomes": [dict(receiver=1, returncode=1, navigation_output_present=False),
                                 dict(receiver=2, returncode=0, navigation_output_present=False)]},
        {"conversion_outcomes": [dict(receiver=1, returncode=0, navigation_output_present=True),
                                 dict(receiver=2, returncode=0, navigation_output_present=False)]},
    ]
    for mutation in mutations:
        dump(p, {**original, **mutation})
        with pytest.raises(ValueError):
            module.checked_navigation_manifest(p, {}, start_s=66., allow_empty_navigation=True)
    dump(p, original)
    with pytest.raises(ValueError, match="LINEAGE"):
        module.checked_navigation_manifest(p, {}, start_s=66., allow_empty_navigation=True,
            expected_lineage={"registry_sha256": "wrong"})
    paths, audit = module.checked_navigation_manifest(
        p, {}, start_s=66., allow_empty_navigation=True)
    assert paths == [] and audit["navigation_availability"] == "NO_NAV_OUTPUT_AT_PREFIX"


def test_empty_provider_yields_no_spp_or_anchor_and_audits_satellites(module):
    # Four valid code observations suffice for eligibility, but no ephemeris
    # must make the existing raw SPP fail without a made-up satellite state.
    raw = module.raw
    obs = tuple(raw.RawxMeasurement(raw.SignalIdentity(0, sv, 0, 0),
        2.1e7, 1e8, 0., 1000, 40, 0, 0, 0, 7) for sv in range(1, 5))
    epoch = raw.RawxEpoch(460882., 2408, 18, 1, 1, obs)
    provider = module.UnavailableBroadcastProvider()
    with pytest.raises(raw.RawBackendError, match="geometry is rank deficient") as failure:
        raw.gps_l1_code_spp(epoch, provider, None, earth_rotation_delay="iterated_geometric")
    assert len(provider.last_qualification) == 4
    assert all(x["status"] == "NO_NAV_OUTPUT_AT_PREFIX" for x in provider.last_qualification.values())
    anchor = module.CausalRawCodeAnchor(module.AnchorPolicy(max_hold_age_s=20.))
    assert not anchor.resolve(66.2, failure=str(failure.value)).available


def test_future_manifest_not_opened_while_empty_current_is_retained(module, tmp_path, monkeypatch):
    p = manifest(tmp_path)
    future = tmp_path / "not_created_future.json"
    sched = schedule(tmp_path, [(66., p), (80., future)])
    monkeypatch.setattr(module, "CheckedRtklibProvider",
        lambda *args: pytest.fail("native provider must not open for empty prefix"))
    with replay(module, sched) as r:
        for time in (66.198, 70., 79.999):
            provider, audit = r.advance(time)
            assert isinstance(provider, module.UnavailableBroadcastProvider)
            assert audit["schedule_index"] == 0
        assert len(r.switches) == 1
        assert not future.exists()


def test_available_prefix_recovers_only_at_cutoff_and_no_stale_fallback(module, tmp_path, monkeypatch):
    p0, p1, p2 = manifest(tmp_path), manifest(tmp_path, 80., True), manifest(tmp_path, 100.)
    sched = schedule(tmp_path, [(66., p0), (80., p1), (100., p2)])
    opened = []
    class Provider:
        def __init__(self, library, paths):
            opened.append(tuple(paths)); self.last_qualification = {}; self.closed = False
        def __enter__(self): return self
        def __exit__(self, *args): self.closed = True
    monkeypatch.setattr(module, "CheckedRtklibProvider", Provider)
    with replay(module, sched) as r:
        assert isinstance(r.advance(79.998)[0], module.UnavailableBroadcastProvider)
        assert opened == []
        available, audit = r.advance(80.)
        assert isinstance(available, Provider) and len(opened) == 1
        assert audit["navigation_availability"] == "AVAILABLE"
        assert r.advance(99.998)[0] is available
        absent, _ = r.advance(100.)
        assert isinstance(absent, module.UnavailableBroadcastProvider)
        assert available.closed and len(opened) == 1
        assert [x["epoch_time_s"] for x in r.switches] == [79.998, 80., 100.]


def test_one_receiver_nav_uses_only_existing_file_with_absence_metadata(module, tmp_path):
    p = manifest(tmp_path, available=True)
    paths, audit = module.checked_navigation_manifest(p, {}, start_s=66.)
    assert len(paths) == 1
    assert paths[0].name == "navigation66.0.nav"
    assert audit["conversion_outcomes"][0]["navigation_output_present"] is False
    assert audit["conversion_outcomes"][1]["navigation_output_present"] is True
    data = json.loads(p.read_text())
    data["conversion_outcomes"][0]["navigation_output_present"] = True
    dump(p, data)
    with pytest.raises(ValueError, match="MISMATCH"):
        module.checked_navigation_manifest(p, {}, start_s=66., allow_empty_navigation=True)

