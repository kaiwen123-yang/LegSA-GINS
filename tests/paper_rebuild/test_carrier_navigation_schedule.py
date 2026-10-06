"""Synthetic causal-navigation schedule regressions; no native/raw real runs."""
from pathlib import Path
from types import SimpleNamespace
import importlib.util
import json
import struct
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts/paper_rebuild/carrier_phase"
WEEK, LEAP = 2408, 18
BASE = 315964800. + WEEK * 604800. - LEAP


@pytest.fixture
def modules(monkeypatch):
    def load(name, path):
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec)
        monkeypatch.setitem(sys.modules, name, module)
        spec.loader.exec_module(module)
        return module
    prepare = load("prepare_navigation", SCRIPTS / "prepare_navigation.py")
    schedule = load("_test_prepare_navigation_schedule", SCRIPTS / "prepare_navigation_schedule.py")
    return prepare, schedule


def rawx(module, tow, week=WEEK):
    body = struct.pack("<dHbBBB2s", tow, week, LEAP, 0, 1, 1, b"\0\0")
    return module.wrap_frame(2, 0x15, body)


def sfrbx(module, sv, gnss=0, signal=0):
    words = 8 if gnss == 2 else 10
    body = struct.pack("<8B", gnss, sv, signal, 0, words, 0, 2, 0)
    body += struct.pack("<" + "I" * words, *range(words))
    return module.wrap_frame(2, 0x13, body)


def dump(path, value):
    path.write_text(json.dumps(value))


def test_closed_prefix_excludes_untagged_future_and_trailing_frames(tmp_path, modules):
    prepare, _ = modules
    frames = [sfrbx(prepare, 1), rawx(prepare, 100.),
              sfrbx(prepare, 2), rawx(prepare, 110.),
              sfrbx(prepare, 3), rawx(prepare, 120.), sfrbx(prepare, 4)]
    source = tmp_path / "source.ubx"; source.write_bytes(b"".join(frames))
    for cutoff, expected in [(99., b""), (100., b"".join(frames[:2])),
                              (105., b"".join(frames[:2])),
                              (110., b"".join(frames[:4])),
                              (999., b"".join(frames[:6]))]:
        payload, audit = prepare.scan(source, BASE, cutoff)
        assert payload == expected
        assert audit["last_kept_rawx_relative_s"] is None or audit["last_kept_rawx_relative_s"] <= cutoff
    assert source.read_bytes() == b"".join(frames)


@pytest.mark.parametrize("times", [[100., 110., 90.], [100., 100.], [100., float("nan")],
                                   [100., float("inf")]])
def test_rawx_time_disorder_cannot_include_future_frames(tmp_path, modules, times):
    prepare, _ = modules
    source = tmp_path / "bad.ubx"
    source.write_bytes(b"".join(rawx(prepare, t) + sfrbx(prepare, i+1)
                               for i, t in enumerate(times)))
    with pytest.raises(ValueError, match="RAWX_TIME_ORDER|VALID_RAWX_GPS_TIME"):
        prepare.scan(source, BASE, 100.)


def test_gps_week_rollover_is_ordered_absolute_time(tmp_path, modules):
    prepare, _ = modules
    frames = [rawx(prepare, 604799.8), sfrbx(prepare, 2),
              rawx(prepare, .2, WEEK+1), sfrbx(prepare, 3)]
    source = tmp_path / "week.ubx"; source.write_bytes(b"".join(frames))
    payload, audit = prepare.scan(source, BASE, 604800.3)
    assert payload == b"".join(frames[:3])
    assert audit["last_kept_rawx_relative_s"] == pytest.approx(604800.2, abs=3e-7)


def test_galileo_component_filter_does_not_release_future_e1b(tmp_path, modules):
    prepare, _ = modules
    e1 = sfrbx(prepare, 2, 2, 1)
    e5 = sfrbx(prepare, 3, 2, 6)
    future_e1 = sfrbx(prepare, 4, 2, 1)
    source = tmp_path / "gal.ubx"
    source.write_bytes(e1 + e5 + rawx(prepare, 100.) + future_e1 + rawx(prepare, 110.))
    payload, _ = prepare.scan(source, BASE, 100.)
    assert payload == e1 + rawx(prepare, 100.)
    # This checks conservative frame release; CRC remains converter-enforced.


@pytest.fixture
def configured(tmp_path, modules, monkeypatch):
    prepare, schedule = modules
    initial_dir = tmp_path / "initial"; initial_dir.mkdir()
    converter = initial_dir / "qualified_convbin"; converter.write_bytes(b"qualified immutable converter")
    raw_sources = {}
    registry = {"base_time": BASE, "source_files": {}}
    for rx in (1, 2):
        source = tmp_path / f"receiver{rx}.ubx"
        source.write_bytes(sfrbx(prepare, rx) + rawx(prepare, 100.) +
                           sfrbx(prepare, rx+2) + rawx(prepare, 110.) +
                           sfrbx(prepare, rx+4) + rawx(prepare, 120.) +
                           sfrbx(prepare, rx+6) + rawx(prepare, 130.))
        raw_sources[str(rx)] = {"path": str(source), "sha256": prepare.digest(source)}
        registry["source_files"][f"gnss{rx}.ubx"] = {
            "source": str(source), "sha256": prepare.digest(source)}
    registry_path = tmp_path / "INPUT.json"; dump(registry_path, registry)
    initial_nav = []
    for rx in (1, 2):
        nav = initial_dir / f"nav{rx}.nav"; nav.write_text("G06 initial navigation\n")
        initial_nav.append({"path": str(nav), "sha256": prepare.digest(nav), "receiver": rx})
    initial_manifest = initial_dir / "NAVIGATION_MANIFEST.json"
    dump(initial_manifest, {"causal_cutoff_relative_s": 100.,
                           "old_full_history_navigation_loaded": False,
                           "converter": {"executable_sha256": prepare.digest(converter)},
                           "navigation": initial_nav})
    pins = initial_dir / "INPUT_PINS.json"
    dump(pins, {"registry": str(registry_path), "registry_sha256": prepare.digest(registry_path),
                "ubx": raw_sources})
    args = SimpleNamespace(initial_manifest=initial_manifest, registry=registry_path,
                           converter=converter, clean_root=tmp_path, output=tmp_path/"schedule",
                           cutoffs=[110., 120.])
    calls = []
    def fake_run(argv, *, cwd, capture_output, text, timeout):
        # No gcc/make, subprocess, external decoder, or native algorithm runs.
        assert argv[0] == str(converter)
        assert argv[1:5] == ["-r", "ubx", "-v", "3.04"]
        assert argv[argv.index("-trace")+1] == "0"
        assert timeout == 60
        payload = Path(argv[-1]).read_bytes()
        values = [prepare.raw.decode_rawx(body).gps_tow_seconds
                  for cls, ident, body in prepare.raw.iter_ubx_frames(payload)
                  if (cls, ident) == (2, 0x15)]
        cutoff = float(Path(cwd).name.removeprefix("PREFIX_"))
        assert values and max(values) <= cutoff
        calls.append((tuple(argv), payload))
        Path(argv[argv.index("-n")+1]).write_text("G06 synthetic NAV line\n")
        Path(argv[argv.index("-o")+1]).write_text("unused observation output\n")
        return SimpleNamespace(returncode=0, stdout="stub", stderr="")
    monkeypatch.setattr(schedule.subprocess, "run", fake_run)
    return SimpleNamespace(prepare=prepare, schedule=schedule, args=args, pins=pins,
                           registry=registry, calls=calls, raw_sources=raw_sources)


def test_schedule_reuses_pinned_converter_and_records_source_lineage(configured):
    c = configured
    before = {p: p.read_bytes() for p in (
        c.args.converter, c.args.initial_manifest, c.args.registry, c.pins)}
    c.schedule.run(c.args)
    assert len(c.calls) == 4
    schedule = json.loads((c.args.output/"NAVIGATION_SCHEDULE.json").read_text())
    assert [e["cutoff_relative_s"] for e in schedule["entries"]] == [100., 110., 120.]
    assert schedule["entries"][0]["reuse_initial_prefix"] is True
    assert schedule["registry_sha256"] == c.prepare.digest(c.args.registry)
    plan = json.loads((c.args.output/"PLAN.json").read_text())
    assert plan["new_build_count"] == 0 and plan["reference_reads"] == 0
    for entry in schedule["entries"][1:]:
        path = Path(entry["manifest"])
        assert c.prepare.digest(path) == entry["manifest_sha256"]
        manifest = json.loads(path.read_text())
        assert manifest["converter_reused_not_rebuilt"] is True
        assert manifest["registry_sha256"] == c.prepare.digest(c.args.registry)
        assert manifest["base_time"] == BASE
        assert manifest["source_ubx_sha256"] == {
            rx: row["sha256"] for rx, row in c.raw_sources.items()}
        for row in manifest["navigation"]:
            assert row["sha256"] == c.prepare.digest(row["path"])
    assert all(p.read_bytes() == data for p, data in before.items())


@pytest.mark.parametrize("cutoffs", [[], [100.], [99.], [120., 110.], [110., 110.],
                                      [float("nan")], [float("inf")]])
def test_invalid_cutoff_contract_rejected_before_converter(configured, cutoffs):
    c = configured; c.args.cutoffs = cutoffs
    with pytest.raises(ValueError):
        c.schedule.run(c.args)
    assert not c.calls and not c.args.output.exists()


@pytest.mark.parametrize("initial_time", [float("nan"), float("inf")])
def test_nonfinite_initial_prefix_cannot_bypass_order(configured, initial_time):
    c = configured
    initial = json.loads(c.args.initial_manifest.read_text())
    initial["causal_cutoff_relative_s"] = initial_time
    dump(c.args.initial_manifest, initial)
    with pytest.raises(ValueError):
        c.schedule.run(c.args)
    assert not c.calls


def test_other_self_consistent_registry_cannot_extend_initial_dataset(configured):
    c = configured
    c.registry["base_time"] += 10
    dump(c.args.registry, c.registry)
    with pytest.raises(ValueError, match="registry differ"):
        c.schedule.run(c.args)
    assert not c.calls


def test_receiver_order_and_identity_bound_to_initial_prefix(configured):
    c = configured
    pins = json.loads(c.pins.read_text())
    pins["ubx"]["1"]["sha256"] = pins["ubx"]["2"]["sha256"]
    dump(c.pins, pins)
    with pytest.raises(ValueError, match="receiver identity differ"):
        c.schedule.run(c.args)
    assert not c.calls


def test_source_payload_tampering_fails_before_converter(configured):
    c = configured
    Path(c.raw_sources["1"]["path"]).write_bytes(b"changed raw")
    with pytest.raises(ValueError, match="raw source identity"):
        c.schedule.run(c.args)
    assert not c.calls


def test_converter_tampering_fails_without_rebuild(configured):
    c = configured; c.args.converter.write_bytes(b"modified converter")
    with pytest.raises(ValueError, match="converter identity"):
        c.schedule.run(c.args)
    assert not c.calls


def test_existing_output_never_overwritten(configured):
    c = configured; c.args.output.mkdir(); sentinel = c.args.output/"keep"
    sentinel.write_text("preserve")
    with pytest.raises(ValueError, match="preserve existing"):
        c.schedule.run(c.args)
    assert sentinel.read_text() == "preserve" and not c.calls


def test_converter_failure_preserves_attempt_without_complete_schedule(configured, monkeypatch):
    c = configured
    def fail(*args, **kwargs):
        return SimpleNamespace(returncode=1, stdout="", stderr="synthetic failure")
    monkeypatch.setattr(c.schedule.subprocess, "run", fail)
    with pytest.raises(RuntimeError, match="preserve attempt"):
        c.schedule.run(c.args)
    assert (c.args.output/"PLAN.json").is_file()
    assert not (c.args.output/"NAVIGATION_SCHEDULE.json").exists()
    assert len(list(c.args.output.rglob("CONVERT_RX1.stderr"))) == 1


@pytest.mark.parametrize("tow", [-.1, 604800.])
def test_invalid_raw_tow_is_not_normalized_into_a_different_week(tmp_path, modules, tow):
    prepare, _ = modules
    source = tmp_path / "tow.ubx"; source.write_bytes(rawx(prepare, tow))
    with pytest.raises(ValueError, match="VALID_RAWX_GPS_TIME"):
        prepare.scan(source, BASE, 100.)


@pytest.mark.parametrize("base,cutoff", [(float("nan"), 100.), (BASE, float("inf")),
                                       (BASE, float("nan"))])
def test_scan_requires_finite_declared_time_domain(tmp_path, modules, base, cutoff):
    prepare, _ = modules
    source = tmp_path / "source.ubx"; source.write_bytes(rawx(prepare, 100.))
    with pytest.raises(ValueError, match="FINITE_PREFIX_TIME"):
        prepare.scan(source, base, cutoff)


def test_submillisecond_name_collision_rejected_before_any_converter(configured):
    c = configured; c.args.cutoffs = [110.0001, 110.0002]
    with pytest.raises(ValueError, match="collide"):
        c.schedule.run(c.args)
    assert not c.calls and not c.args.output.exists()


def test_nonfinite_registry_origin_even_with_matching_pins_is_rejected(configured):
    c = configured
    c.registry["base_time"] = float("nan")
    dump(c.args.registry, c.registry)
    pins = json.loads(c.pins.read_text())
    pins["registry_sha256"] = c.prepare.digest(c.args.registry)
    dump(c.pins, pins)
    with pytest.raises(ValueError, match="finite registry"):
        c.schedule.run(c.args)
    assert not c.calls
