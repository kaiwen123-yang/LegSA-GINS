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
