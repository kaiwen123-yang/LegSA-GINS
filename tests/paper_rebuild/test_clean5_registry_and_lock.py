"""CLEAN5 registry and append-only locks, using only synthetic temporary files."""
from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from legsa_gins.paper_rebuild.clean5_sequence import raw_lock, registry
from legsa_gins.paper_rebuild.evidence import BY2_BODY_RELATIVE_PATH, BY2_FIX_PREFIX, BY2_RAW_RELATIVE_PATHS, BY2_TRACE_NAME
from legsa_gins.paper_rebuild.manifest import ManifestContractError, sha256_file
from legsa_gins.paper_rebuild.paths import PathContractError, load_yaml_mapping
from legsa_gins.paper_rebuild.clean5_sequence import probes

REGISTRY_PATH = Path(__file__).resolve().parents[2] / "configs/paper_rebuild/clean5/CLEAN5_SEQUENCE_REGISTRY.yaml"


@pytest.mark.parametrize("name", ["trace_synthetic.csv", "synthetic.bag", "synthetic.fpl"])
def test_probe_guard_rejects_forbidden_paths_before_open(tmp_path, name):
    import io
    import os
    source = tmp_path / name
    source.write_text("synthetic input must never be read")
    with pytest.raises(probes.ProbeContractError):
        probes.open_probe_file(source)
    with probes.forbidden_path_guard(tmp_path, [source]):
        for opener in (lambda: source.open(), lambda: open(source), lambda: io.open(source),
                       lambda: os.open(source, os.O_RDONLY)):
            with pytest.raises(probes.ProbeContractError):
                opener()


def test_probe_guard_rejects_raw_write_and_unlisted_input_and_symlink(tmp_path):
    allowed = tmp_path / "gnss1-status.csv"
    allowed.write_text("pos_valid\n1\n")
    denied = tmp_path / "other.csv"
    denied.write_text("not allowed")
    trace = tmp_path / "trace_source.csv"
    trace.write_text("forbidden")
    link = tmp_path / "alias.csv"
    link.symlink_to(trace)
    with probes.forbidden_path_guard(tmp_path, [allowed, link]):
        assert allowed.read_text() == "pos_valid\n1\n"
        for action in (lambda: allowed.write_text("bad"), denied.read_text, link.read_text):
            with pytest.raises(probes.ProbeContractError):
                action()
    assert allowed.read_text() == "pos_valid\n1\n"


def test_time_rules_use_first_valid_status_and_window_margins():
    rows = [{"sys_stamp.secs": "1772783990", "sys_stamp.nsecs": "0", "pos_valid": "false"},
            {"sys_stamp.secs": "1772784055", "sys_stamp.nsecs": "206795000", "pos_valid": "true",
             "utc_year": "2026", "utc_month": "3", "utc_day": "6"}]
    rules = probes.time_rules(rows)
    assert rules["R1"] == 1772784000.0
    assert rules["R3"] == 1772784000.0
    windows = probes.candidate_window_bprime([55.206795, 349.8], [50, 360],
                                             [55.206795, 357.201323], [55.206795, 349.8])
    assert windows["rule_B_prime"] == {"t_start": 66.0, "t_end": 340.0}
    # The end margin is 9 s from common coverage, not 17 s from GNSS1 alone.
    shorter = probes.candidate_window_bprime([55.206795, 339.8], [50, 360],
                                             [55.206795, 357.201323], [55.206795, 339.8])
    assert shorter["rule_B_prime"] == {"t_start": 66.0, "t_end": 330.0}


def test_failed_probe_item_preserves_error_and_allows_later_items():
    report = {}
    visits = []

    def fail_kick():
        visits.append("d")
        raise ValueError("synthetic kick detector has no candidate")

    probes.run_item(report, "d_window_candidates", fail_kick)
    probes.run_item(report, "e_initialization", lambda: {"ran_after_d": visits.append("e") is None})
    probes.run_item(report, "f_occlusion_candidates", lambda: {"ran_after_d": visits.append("f") is None})
    probes.run_item(report, "g_source_fields", lambda: {"ran_after_d": visits.append("g") is None})
    assert visits == ["d", "e", "f", "g"]
    assert report["d_window_candidates"]["status"] == "FAIL"
    assert report["d_window_candidates"]["error_class"] == "ValueError"
    assert report["d_window_candidates"]["error_message"] == "synthetic kick detector has no candidate"
    assert all(report[key]["status"] == "PASS" for key in
               ("e_initialization", "f_occlusion_candidates", "g_source_fields"))


def test_occlusion_keeps_all_segments_without_selecting_a_window():
    rows = []
    for t, available in enumerate([True, False, False, True, False]):
        rows.append({"sys_stamp.secs": str(t), "sys_stamp.nsecs": "0", "header.stamp.secs": str(t),
                     "header.stamp.nsecs": "0", "pos_valid": str(available), "rel_valid": "true",
                     "ant_valid": "true", "ant_state": "2", "fix_type": "4", "num_sv": "15"})
    epochs, result = probes.occlusion_rows(rows, list(rows[0]), 0, rows, [{"timestamp": t} for t in range(5)], .6)
    assert len(epochs) == 5
    assert [(s["start"], s["end"], s["duration"]) for s in result["segments"]] == [(1, 2, 1), (4, 4, 0)]
    assert result["fix_fields"] == ["fix_type"] and result["satellite_fields"] == ["num_sv"]


def test_occlusion_includes_a1_absent_due_to_gnss1_status():
    two = [{"sys_stamp.secs": "1", "sys_stamp.nsecs": "0", "header.stamp.secs": "1",
            "header.stamp.nsecs": "0", "pos_valid": "true", "rel_valid": "true", "ant_valid": "true", "ant_state": "2"}]
    one = [{**two[0], "rel_valid": "false"}]
    epochs, report = probes.occlusion_rows(two, list(two[0]), 0, one, [], .6)
    assert epochs[0]["candidate_unavailable"] and not epochs[0]["a1_epoch_available"]
    assert report["segments"][0]["trigger_flags"] == ["a1_not_constructed_at_matched_gnss1_epoch"]




@pytest.mark.parametrize("a,b,expected", [(359, 1, 2), (1, 359, 2), (-179, 179, 2), (0, 180, 180), (10, 710, 20)])
def test_absolute_yaw_increment_is_wrap_safe_and_at_most_180(a, b, expected):
    assert probes.absolute_yaw_increment(a, b) == expected
    assert 0 <= probes.absolute_yaw_increment(a, b) <= 180


def test_heading_only_resume_preserves_a_to_g_and_never_retries_kick(tmp_path, monkeypatch):
    from legsa_gins.paper_rebuild import kick_alignment, providers

    bundle, _, _, _, _ = _fixture(tmp_path)
    item_keys = ("a_inventory", "b_base_time", "c_a1_baseline", "d_window_candidates",
                 "e_initialization", "f_occlusion_candidates", "g_source_fields")
    previous = {}
    for dataset, seq in bundle.sequences.items():
        report = {"dataset_id": dataset, "stage_id": seq.stage_id, "data_mode": seq.data_mode,
                  "status": "COMPLETED_WITH_ITEM_FAILURES", "synthetic_data_used": True,
                  **{key: {"status": "PASS", "preserved_marker": dataset + ":" + key} for key in item_keys}}
        report["d_window_candidates"].update(status="FAIL", rule_B_prime={"t_start": 66.0, "t_end": 340.0},
                                            rule_A={"status": "FAIL", "error_message": "preserved original kick failure"})
        previous[dataset] = report
        seq.probe_dir.mkdir(parents=True)
        (seq.probe_dir / "PROBE_REPORT.json").write_text(json.dumps(report))

    forbidden_calls = []
    reads = []

    def forbidden(*args, **kwargs):
        forbidden_calls.append("kick_or_body_or_tf")
        raise AssertionError("Heading continuation must not retry kick or read Go2/tf")

    def status_csv(path, **kwargs):
        reads.append(Path(path).name)
        assert Path(path).name in {"gnss1-status.csv", "gnss2-status.csv"}
        rows = [{"sys_stamp.secs": "1772784066", "sys_stamp.nsecs": "0", "pos_valid": "true",
                 "utc_year": "2026", "utc_month": "3", "utc_day": "6", "fix_type": "4",
                 "fix_ok": "true", "pos_acc_h": "0.01", "pos_acc_v": "0.02"}]
        return list(rows[0]), rows

    def synthetic_a1(*args, **kwargs):
        assert kwargs["base_time"] == 1772784000.0
        # Frozen body convention maps these two candidates to NED 359 and 1 degrees.
        return [{"aligned_time": 66.0, "yaw_baseline_deg": -269.0, "baseline_len_m": .35},
                {"aligned_time": 67.0, "yaw_baseline_deg": 89.0, "baseline_len_m": .35}], {}

    monkeypatch.setattr(probes, "_csv", status_csv)
    monkeypatch.setattr(probes, "_tf_summary", forbidden)
    monkeypatch.setattr(providers, "parse_go2_body_state_text", forbidden)
    monkeypatch.setattr(kick_alignment, "detect_frozen_go2_kick", forbidden)
    monkeypatch.setattr(providers, "build_a1_dual_diff_yaw_rows", synthetic_a1)
    reports = probes.run_probes(bundle, {}, {}, {}, resume_heading_only=True)
    assert forbidden_calls == []
    assert sorted(reads) == ["gnss1-status.csv"] * 3 + ["gnss2-status.csv"] * 3
    for dataset, report in reports.items():
        assert {key: report[key] for key in item_keys} == {key: previous[dataset][key] for key in item_keys}
        assert report["h_heading_quality"]["status"] == "PASS"
        increment = report["h_heading_quality"]["abs_adjacent_yaw_increment_deg"]
        assert increment["min"] == increment["median"] == increment["p95"] == increment["max"] == 2.0
        assert report["status"] == "COMPLETED_WITH_ITEM_FAILURES"
        assert report["heading_only_continuation"] is True

def test_a1_missing_segments_use_strict_twice_median_and_descending_duration():
    # Sorted intervals: 1, 1, 2, 3, 1, 5, 1; median = 1, so exactly 2 is not missing.
    times = [0, 1, 2, 4, 7, 8, 13, 14]
    result = probes.a1_missing_segments([{"aligned_time": t} for t in reversed(times)])
    assert result["median_interval_seconds"] == 1
    assert [(r["start"], r["end"], r["duration"]) for r in result["segments"]] == [(8, 13, 5), (4, 7, 3)]
    assert all(r["epoch_count"] == 0 and r["bounding_epoch_count"] == 2 for r in result["segments"])


def test_tf_summary_reads_multiple_ros_blocks_and_keeps_first_pair_values(tmp_path):
    def block(parent, child, x, w):
        return (f'header:\n  frame_id: "{parent}"\nchild_frame_id: "{child}"\ntransform:\n'
                f'  translation:\n    x: {x}\n    y: -0.03\n    z: 0.4\n'
                f'  rotation:\n    x: 0.0\n    y: 0.0\n    z: 0.0\n    w: {w}')

    transforms = "[" + ", ".join([block("map", "base", "0.01200", "1.000"),
                                  block("base", "sensor", "0.350", "0.707"),
                                  block("map", "base", "999", "0")]) + "]"
    source = tmp_path / "tf_static.csv"
    with source.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["Time", "transforms"])
        writer.writeheader()
        writer.writerow({"Time": "123.456", "transforms": transforms})
    result = probes._tf_summary(source, retain_all=True)
    assert result["row_count"] == 1
    assert result["unique_frame_pairs"] == [["map", "base"], ["base", "sensor"]]
    first, second = result["first_raw_transform_per_pair"]
    assert first["translation"]["x"] == "0.01200" and first["quaternion"]["w"] == "1.000"
    assert second["translation"]["x"] == "0.350" and second["quaternion"]["w"] == "0.707"
    assert first["first_csv_time"] == "123.456"
    assert result["all_raw_rows"][0]["transforms"] == transforms

def _load_cli():
    import importlib.util
    script = REGISTRY_PATH.parents[3] / "scripts/paper_rebuild/clean5_lock_and_probe.py"
    spec = importlib.util.spec_from_file_location("clean5_cli_for_test", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_strace_audit_counts_duplicate_reads_and_forbidden_opens(tmp_path):
    module = _load_cli()
    bundle, _, _, _, _ = _fixture(tmp_path)
    inventory = raw_lock.inventory_lock_paths(bundle)
    log = tmp_path / "openat.log"
    # json's unicode escapes are different from strace's octal escapes; use raw UTF-8 here.
    lines = [f'123 openat(AT_FDCWD, "{path}", O_RDONLY|O_CLOEXEC) = 3\n' for _, path in inventory]
    log.write_text("".join(lines))
    assert module.audit_strace(log, bundle, "lock", inventory)["pass"]
    log.write_text("".join(lines + [lines[0]]))
    assert not module.audit_strace(log, bundle, "lock", inventory)["pass"]
    log.write_text(f'123 openat(AT_FDCWD, "{bundle.sequences["BY2"].trace_path}", O_RDONLY) = 3\n')
    audit = module.audit_strace(log, bundle, "probe", inventory)
    assert not audit["pass"] and audit["forbidden_open_counts"]["trace"] == 1



@pytest.mark.parametrize("row_count,digest", [(43, "faa31580c7fff73b52fcf6d27c97cfdd9187e67a55968a2ab42e6737b0eabb67"), (44, "0" * 64)])
def test_c01b_probe_lock_rejects_wrong_count_or_hash(tmp_path, monkeypatch, row_count, digest):
    module = _load_cli()
    monkeypatch.setattr(module.raw_lock, "read_independent_lock",
                        lambda root: {"row_count": row_count, "sha256": digest})
    with pytest.raises(RuntimeError, match="independent lock identity mismatch"):
        module.verify_probe_lock(tmp_path)


@pytest.mark.parametrize("resume_heading_only", [False, True])
def test_probe_phase_keeps_item_failures_and_verifies_locks_before_and_after(tmp_path, monkeypatch, resume_heading_only):
    from types import SimpleNamespace

    module = _load_cli()
    bundle, registry_path, local_path, _, _ = _fixture(tmp_path)
    calls = {"original": 0, "independent": 0}

    def original(root):
        calls["original"] += 1
        return {"rows": {}}

    def independent(root):
        calls["independent"] += 1
        return {"rows": {}, "row_count": 44, "sha256": module.C01B_INDEPENDENT_LOCK_SHA256}

    audit = bundle.sequences["BY2H"].probe_dir / "LOCK_PHASE_STRACE_AUDIT.json"
    audit.parent.mkdir(parents=True)
    audit.write_text(json.dumps({"pass": True, "phase_exit_code": 0, "raw_forbidden_writes": 0,
                                 "lock_sha256": module.C01B_INDEPENDENT_LOCK_SHA256}))
    monkeypatch.setattr(module.raw_lock, "verify_original_lock", original)
    monkeypatch.setattr(module.raw_lock, "read_independent_lock", independent)
    monkeypatch.setattr(module, "provenance", lambda *args: {})
    calls["probe_kwargs"] = []
    def synthetic_probes(*args, **kwargs):
        calls["probe_kwargs"].append(kwargs)
        return {
        "BY2": {"status": "COMPLETED_WITH_ITEM_FAILURES", "b_base_time": {"status": "PASS", "R1": 1772784000.0},
                "d_window_candidates": {"status": "FAIL", "failed_subitems": ["rule_A"],
                                        "rule_B_prime": {"t_start": 66.0, "t_end": 340.0},
                                        "rule_A": {"status": "FAIL", "error_class": "ValueError", "error_message": "synthetic missing kick"}},
                "g_source_fields": {"status": "PASS"}},
        }
    monkeypatch.setattr(probes, "run_probes", synthetic_probes)
    result = module.execute_phase(SimpleNamespace(phase="probe", registry=registry_path, paths_config=local_path,
                                                  resume_heading_only=resume_heading_only), bundle, [])
    assert result["BY2"]["status"] == "COMPLETED_WITH_ITEM_FAILURES"
    assert result["BY2"]["all_items_pass"] is False
    d = result["BY2"]["items"]["d_window_candidates"]
    assert d["rule_B_prime"] == {"t_start": 66.0, "t_end": 340.0}
    assert d["failed_subitems"] == ["rule_A"]
    assert d["subitems"]["rule_A"]["error_message"] == "synthetic missing kick"
    assert result["BY2"]["items"]["g_source_fields"]["status"] == "PASS"
    assert calls["original"] >= 2 and calls["independent"] == 2
    assert calls["probe_kwargs"] == [{"resume_heading_only": resume_heading_only}]

def _fixture(tmp_path):
    spec = load_yaml_mapping(REGISTRY_PATH)
    registry_path = tmp_path / "registry.json"
    registry_path.write_text(json.dumps(spec), encoding="utf-8")
    roots = {key: tmp_path / key for key in ("raw_root", "clean_root", "code_root")}
    for path in roots.values():
        path.mkdir()
    paths = {key: str(path) for key, path in roots.items()}
    csv_names = [Path(relative).name for relative in BY2_RAW_RELATIVE_PATHS
                 if relative.endswith(".csv") and not Path(relative).name.startswith("trace_")]
    rows = []
    for dataset, item in spec["sequences"].items():
        fix = roots["raw_root"] / item["fix_prefix"]
        body = roots["raw_root"] / item["go2_body"]
        fix.mkdir(parents=True)
        body.parent.mkdir(parents=True, exist_ok=True)
        paths[f"{dataset.lower()}_fix_root"] = str(fix)
        paths[f"{dataset.lower()}_go2_body"] = str(body)
        sources = [fix / name for name in csv_names + [item["trace_name"]]]
        sources += [body, Path(str(fix) + ".bag"), Path(str(fix) + ".fpl")]
        for source in sources:
            source.write_bytes(b"synthetic_header\nsynthetic_value\n")
            rows.append(dict(zip(raw_lock.LOCK_COLUMNS, (
                str(source.relative_to(roots["raw_root"])), str(source.stat().st_size), sha256_file(source),
                "line_count:2" if source.suffix == ".csv" else f"file_type:{source.suffix[1:]}",
                "synthetic_fixture", dataset, "true", str(source.stat().st_mtime_ns),
            ))))
    config_path = tmp_path / "local.json"
    config_path.write_text(json.dumps({"paths": paths}), encoding="utf-8")
    original = roots["clean_root"] / "01_RAW_HASH_LOCK/RAW_FILE_HASH_LOCK.csv"
    original.parent.mkdir()
    _write_lock(original, rows)
    bundle = registry.load_registry(registry_path, config_path)
    return bundle, registry_path, config_path, original, {"original_expected_hash": sha256_file(original), "original_expected_rows": len(rows)}


def _write_lock(path, rows):
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=raw_lock.LOCK_COLUMNS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def test_registry_loads_three_sequences_and_preserves_by2_control(tmp_path):
    bundle, _, _, _, _ = _fixture(tmp_path)
    assert set(bundle.sequences) == {"BY2", "BY2H", "BY2O"}
    control = bundle.sequences["BY2"]
    assert (control.fix_prefix, control.go2_body, control.trace_name) == (BY2_FIX_PREFIX, BY2_BODY_RELATIVE_PATH, BY2_TRACE_NAME)
    assert control.probe_dir == bundle.clean_root / "stages/CLEAN5_BY2_CONTROL_PROBES"
    for dataset in ("BY2H", "BY2O"):
        seq = bundle.sequences[dataset]
        assert seq.probe_dir == bundle.clean_root / "stages" / seq.stage_id / "00_RAW_INVENTORY_AND_PROBES"
        assert seq.fix_root == bundle.raw_root / seq.fix_prefix


@pytest.mark.parametrize("bad", ["G:/raw/by3", r"G:\raw\by3", "../by3", "experiments/by3", "reports/stages/by3"])
def test_registry_rejects_windows_legacy_and_traversal_relative_paths(tmp_path, bad):
    _, spec_path, local_path, _, _ = _fixture(tmp_path)
    spec = json.loads(spec_path.read_text())
    spec["sequences"]["BY2H"]["fix_prefix"] = bad
    spec_path.write_text(json.dumps(spec))
    with pytest.raises(PathContractError):
        registry.load_registry(spec_path, local_path, require_sources=False)


@pytest.mark.parametrize("kind", ["windows", "legacy", "traversal", "outside", "mismatch"])
def test_registry_rejects_bad_local_paths(tmp_path, kind):
    bundle, spec_path, local_path, _, _ = _fixture(tmp_path)
    config = json.loads(local_path.read_text())
    values = {
        "windows": r"G:\raw\by3", "legacy": str(tmp_path / "experiments/by3"),
        "traversal": str(bundle.raw_root / "x/../by3"), "outside": str(tmp_path / "outside"),
        "mismatch": str(bundle.raw_root / "wrong"),
    }
    config["paths"]["by2h_fix_root"] = values[kind]
    local_path.write_text(json.dumps(config))
    with pytest.raises(PathContractError):
        registry.load_registry(spec_path, local_path, require_sources=False)


def test_registry_rejects_symlink_escape(tmp_path):
    bundle, spec_path, local_path, _, _ = _fixture(tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir()
    link = bundle.raw_root / "escape"
    link.symlink_to(outside, target_is_directory=True)
    spec = json.loads(spec_path.read_text())
    spec["sequences"]["BY2H"]["fix_prefix"] = "escape"
    spec_path.write_text(json.dumps(spec))
    local = json.loads(local_path.read_text())
    local["paths"]["by2h_fix_root"] = str(link)
    local_path.write_text(json.dumps(local))
    with pytest.raises(PathContractError):
        registry.load_registry(spec_path, local_path, require_sources=False)


def test_independent_lock_is_idempotent_and_keeps_original_hash(tmp_path, monkeypatch):
    bundle, _, _, original, options = _fixture(tmp_path)
    original_bytes = original.read_bytes()
    selected = raw_lock.inventory_lock_paths(bundle)
    assert len(selected) == 44
    calls = []
    original_hasher = raw_lock.sha256_file

    def record_hash(path, *, chunk_size):
        if bundle.raw_root in Path(path).parents:
            calls.append((Path(path), chunk_size))
        return original_hasher(path, chunk_size=chunk_size)

    monkeypatch.setattr(raw_lock, "sha256_file", record_hash)
    first = raw_lock.build_independent_lock(bundle, inventory=selected, **options)
    assert first["row_count"] == 44
    assert len(calls) == 44 and set(calls) == {(path, 1024 * 1024) for _, path in selected}
    assert {row["dataset"] for row in first["rows"].values()} == {"BY2H", "BY2O"}
    assert {row["line_count_or_file_type"] for row in first["rows"].values()} >= {"line_count:2"}
    locked = Path(first["lock_path"])
    first_bytes = locked.read_bytes()
    calls.clear()
    second = raw_lock.build_independent_lock(bundle, inventory=selected, **options)
    assert locked.read_bytes() == first_bytes
    assert first["sha256"] == second["sha256"]
    assert len(calls) == 44 and len({path for path, _ in calls}) == 44
    assert original.read_bytes() == original_bytes
    assert sha256_file(original) == options["original_expected_hash"]


def test_independent_lock_appends_without_rewriting_existing_bytes(tmp_path):
    bundle, _, _, original, options = _fixture(tmp_path)
    first = raw_lock.build_independent_lock(bundle, **options)
    lock = Path(first["lock_path"])
    partial = [row for row in first["rows"].values() if row["dataset"] == "BY2H"]
    _write_lock(lock, partial)
    prior = lock.read_bytes()
    full = raw_lock.build_independent_lock(bundle, **options)
    assert lock.read_bytes().startswith(prior)
    assert full["row_count"] == 44
    assert all(full["rows"][row["relative_path"]] == row for row in partial)
    assert sha256_file(original) == options["original_expected_hash"]


@pytest.mark.parametrize("field,value", [("sha256", "0" * 64), ("size_bytes", "999"), ("dataset", "BY2")])
def test_independent_lock_mismatch_fails_without_appending(tmp_path, field, value):
    bundle, _, _, original, options = _fixture(tmp_path)
    first = raw_lock.build_independent_lock(bundle, **options)
    lock = Path(first["lock_path"])
    rows = list(first["rows"].values())
    rows[0][field] = value
    _write_lock(lock, rows)
    before = lock.read_bytes()
    with pytest.raises(ManifestContractError, match="disagrees"):
        raw_lock.build_independent_lock(bundle, **options)
    assert lock.read_bytes() == before
    assert sha256_file(original) == options["original_expected_hash"]


def test_original_lock_verification_fails_closed(tmp_path):
    bundle, _, _, original, options = _fixture(tmp_path)
    verified = raw_lock.verify_original_lock(bundle.clean_root, expected_hash=options["original_expected_hash"],
                                            expected_rows=options["original_expected_rows"])
    assert verified["row_count"] == 66
    with pytest.raises(ManifestContractError, match="SHA-256 mismatch"):
        raw_lock.verify_original_lock(bundle.clean_root, expected_hash="0" * 64, expected_rows=66)
    with pytest.raises(ManifestContractError, match="row count mismatch"):
        raw_lock.verify_original_lock(bundle.clean_root, expected_hash=sha256_file(original), expected_rows=9980)
