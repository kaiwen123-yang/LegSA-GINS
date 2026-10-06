"""C-06 publication handoff tests using only synthetic source directories."""

import csv
import gzip
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import zipfile

import pytest


@pytest.fixture(scope="module")
def pack():
    path = Path(__file__).resolve().parents[2] / "scripts/paper_rebuild/clean5_pack_v1.py"
    spec = importlib.util.spec_from_file_location("clean5_pack_v1_under_test", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def roots(tmp_path):
    source, raw = tmp_path / "clean", tmp_path / "raw"
    source.mkdir()
    raw.mkdir()
    return source, raw, tmp_path / "handoff.zip"


def _csv(path, columns, rows):
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(columns)
        writer.writerows(rows)
    return path


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def test_column_allowlist_keeps_c541_and_clean5_fields_in_source_order(pack):
    columns = [
        "private_notes", "method_id", "horizontal_rmse_m", "trace_payload",
        "yaw_p95_absolute_deg", "source_aware_evaluation_count", "segment_id",
        "rmse", "p95_abs", "max_abs", "signed_mean", "unit", "metric_name",
        "time_start", "time_end", "secondary_run_epoch_count", "runtime_seconds",
    ]
    chosen = pack.choose_columns(columns, clean5=True)
    assert chosen == [name for name in columns if name not in {"private_notes", "trace_payload"}]
    assert pack.choose_columns(columns, clean5=False) == [
        name for name in columns
        if name in pack.IDENT or pack.KEEP_COL.search(name)
    ]


def test_payload_or_secret_names_cannot_enter_through_broad_metric_regex(pack):
    chosen = pack.choose_columns(
        ["run_id", "secret_count", "raw_trace_coverage", "trace_payload", "password", "yaw_rmse_deg"],
        clean5=True,
    )
    assert chosen == ["run_id", "yaw_rmse_deg"]


def test_by2_whitelist_preserves_data_role_provenance(pack):
    columns = ["dataset_id", "data_mode", "synthetic_data_used", "semisynthetic_data_used", "trace_used_online"]
    assert pack.choose_columns(columns, clean5=False) == columns


@pytest.mark.parametrize("named", [False, True])
def test_fixed_10hz_uses_first_original_row_and_preserves_missing_bins(pack, named):
    times = [10.009, 10.099, 10.105, 10.19, 10.403, 10.409]
    rows = [
        {"time": str(t), "value": str(v)} if named else [str(t), str(v)]
        for t, v in zip(times, [900, -100, 42, 10000, -3, 100000])
    ]
    kept, probe = pack.select_10hz_rows(
        rows, time_column="time" if named else 0, start=10.0,
    )
    assert kept == [rows[0], rows[2], rows[4]]
    assert all(actual is rows[index] for actual, index in zip(kept, [0, 2, 4]))
    assert probe["bins"] == [0, 1, 4]
    assert probe["source_rows"] == 6
    assert probe["package_rows"] == 3
    assert probe["step_seconds"] == 0.1
    assert probe["display_only"] is True


@pytest.mark.parametrize("time_column", [0, 1])
def test_10hz_boundaries_are_left_closed_without_interpolation(pack, time_column):
    rows = [[str(t), str(t)] for t in [0.0, 0.09, 0.1, 0.1999, 0.2, 0.3]]
    kept, probe = pack.select_10hz_rows(rows, time_column=time_column, start=0.0)
    assert kept == [rows[0], rows[2], rows[4], rows[5]]
    assert probe["bins"] == [0, 1, 2, 3]


@pytest.mark.parametrize("times", [[0.1, 0.09], [0.1, float("nan")], [0.1, float("inf")]])
def test_sampling_rejects_nonmonotonic_or_nonfinite_time(pack, times):
    with pytest.raises(ValueError):
        pack.select_10hz_rows([[time, 1] for time in times], time_column=0, start=0.0)


def test_numeric_nav_and_std_time_columns_and_original_gnss_trace(pack, roots):
    source, raw, output = roots
    nav_lines = [
        "2200 10.009 999 0 0 0 0 0 0 0 0\n",
        "2200 10.099 -999 0 0 0 0 0 0 0 0\n",
        "2200 10.105 7 0 0 0 0 0 0 0 0\n",
        "2200 10.403 11 0 0 0 0 0 0 0 0\n",
    ]
    std_lines = [line.split(" ", 1)[1] for line in nav_lines]
    nav, std = source / "KF_GINS_Navresult.nav", source / "KF_GINS_STD.txt"
    nav.write_text("".join(nav_lines))
    std.write_text("".join(std_lines))
    trace = source / "PORT_GNSS_UPDATE_TRACE.csv"
    trace_bytes = b"time,attempt,residual\r\n10.009,1,-0.000\r\n10.105,1,7.000\r\n"
    trace.write_bytes(trace_bytes)
    with pack.PackageBuilder(output, source_roots=[source], raw_root=raw) as builder:
        nav_entry = builder.add_numeric_10hz(nav, "BY2H/nav.nav.gz", time_column=1, start=10.0)
        std_entry = builder.add_numeric_10hz(std, "BY2H/std.txt.gz", time_column=0, start=10.0)
        trace_entry = builder.add_file(trace, "BY2H/PORT_GNSS_UPDATE_TRACE.csv")
        builder.finish()
    with zipfile.ZipFile(output) as archive:
        assert gzip.decompress(archive.read("BY2H/nav.nav.gz")).decode().splitlines() == [
            nav_lines[index].rstrip("\n") for index in [0, 2, 3]
        ]
        assert gzip.decompress(archive.read("BY2H/std.txt.gz")).decode().splitlines() == [
            std_lines[index].rstrip("\n") for index in [0, 2, 3]
        ]
        assert archive.read("BY2H/PORT_GNSS_UPDATE_TRACE.csv") == trace_bytes
    for entry, path in [(nav_entry, nav), (std_entry, std)]:
        assert entry["source_sha256"] == _sha(path.read_bytes())
        assert entry["source_rows"] == 4 and entry["package_rows"] == 3
        assert entry["display_only"] is True
    assert trace_entry["source_sha256"] == trace_entry["package_sha256"] == _sha(trace_bytes)


def test_error_series_filters_columns_samples_first_and_probes_source_and_package(pack, roots):
    source, raw, output = roots
    columns = list(pack.SERIES_COLS) + ["private_notes", "trace_payload"]
    series = _csv(source / "error_series.csv", columns, [
        [0.0, "1.0", "2.0", "3.0", "1.00", "4.0", "5.0", "6.0", "-0.000000", "SECRET", "RAW"],
        [0.05, "1.0", "2.0", "3.0", "888", "4.0", "5.0", "6.0", "999", "SECRET", "RAW"],
        [0.4, "1.0", "2.0", "3.0", "3.00", "4.0", "5.0", "6.0", "2.0", "SECRET", "RAW"],
    ])
    with pack.PackageBuilder(output, source_roots=[source], raw_root=raw) as builder:
        entry = builder.add_error_series_10hz(series, "series.csv.gz", start=0.0)
        probe = builder.finish()
    with zipfile.ZipFile(output) as archive:
        payload = archive.read("series.csv.gz")
        text = gzip.decompress(payload).decode()
        parsed = list(csv.DictReader(io.StringIO(text)))
        assert list(parsed[0]) == pack.SERIES_COLS
        assert [row["time"] for row in parsed] == ["0.0", "0.4"]
        assert parsed[0]["yaw_err_deg"] == "-0.000000"
        assert "SECRET" not in text and "RAW" not in text
        stored_probe = json.loads(archive.read("IDENTITY_PROBE.json"))
        assert stored_probe == probe
        assert entry in stored_probe["entries"]
        assert stored_probe["pack_script_sha256"] == _sha(Path(pack.__file__).read_bytes())
    assert entry["source_sha256"] == _sha(series.read_bytes())
    assert entry["package_sha256"] == _sha(payload)
    assert entry["source_rows"] == 3 and entry["package_rows"] == 2
    assert entry["source_columns"] == columns
    assert entry["columns"] == pack.SERIES_COLS


def test_evaluation_csv_contains_only_selected_columns_without_full_copy(pack, roots):
    source, raw, output = roots
    table = _csv(source / "UNIQUE_EVALUATION_RESULTS.csv", [
        "run_id", "yaw_rmse_deg", "private_notes", "trace_payload"
    ], [["BY2H_A04_AB1011", "2.059813237028886", "SECRET", "RAW"]])
    with pack.PackageBuilder(output, source_roots=[source], raw_root=raw) as builder:
        columns = pack.choose_columns(["run_id", "yaw_rmse_deg", "private_notes", "trace_payload"], clean5=True)
        builder.add_csv(table, "08_AGGREGATE/UNIQUE_EVALUATION_RESULTS.csv.gz", columns=columns)
        builder.finish()
    with zipfile.ZipFile(output) as archive:
        assert not any(name.startswith("FULL_") for name in archive.namelist())
        payloads = b"".join(archive.read(name) for name in archive.namelist())
        text = gzip.decompress(archive.read("08_AGGREGATE/UNIQUE_EVALUATION_RESULTS.csv.gz"))
        assert b"SECRET" not in payloads + text and b"RAW" not in payloads + text
        assert text.decode().splitlines()[0] == "run_id,yaw_rmse_deg"


@pytest.fixture
def clean5_inputs(pack, roots, tmp_path, monkeypatch, request):
    source, raw, output = roots
    dataset = getattr(request, "param", "BY2H")
    code = tmp_path / "code"
    stage = source / "stages" / pack.STAGES[dataset]
    aggregate = stage / "08_AGGREGATE"
    aggregate.mkdir(parents=True)
    contract_dir = code / "configs/paper_rebuild/clean5"
    contract_dir.mkdir(parents=True)

    def write_json(path, value):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value) + "\n")
        return _sha(path.read_bytes())

    columns = ["run_id", "method_id", "effective_configuration_id", "output_root", "yaw_rmse_deg", "private_notes", "trace_payload"]
    table_rows, sealed_files = [], []
    for method, configuration in pack.METHODS.items():
        run_id = f"{dataset}_{method}_{configuration}"
        native = stage / "04_SOLVER_RUNS_V2" / run_id
        native.mkdir(parents=True)
        nav = native / "KF_GINS_Navresult.nav"
        std = native / "KF_GINS_STD.txt"
        nav.write_text("2200 10.01 1 2 3 4 5 6 7 8 9\n2200 10.02 9 8 7 6 5 4 3 2 1\n2200 10.41 1 2 3 4 5 6 7 8 9\n")
        std.write_text("10.01 1 2 3 4 5 6 7 8 9\n10.02 9 8 7 6 5 4 3 2 1\n10.41 1 2 3 4 5 6 7 8 9\n")
        write_json(native / "RUN_MANIFEST.json", {"data_mode": "synthetic_pack_test", "run_id": run_id})
        (native / "PORT_GNSS_UPDATE_TRACE.csv").write_bytes(b"time,attempt\r\n10.01,1\r\n")
        for item in native.iterdir():
            sealed_files.append({"relative_path": item.relative_to(stage).as_posix(), "sha256": _sha(item.read_bytes())})
        evaluation = stage / "07_OFFLINE_EVALUATION/PER_RUN" / run_id
        evaluation.mkdir(parents=True)
        _csv(evaluation / "error_series.csv", pack.SERIES_COLS, [[time] + ["0.00"] * 8 for time in [10.01, 10.02, 10.41]])
        table_rows.append([run_id, method, configuration, str(native), "1.234567", "SECRET_CELL", "RAW_PAYLOAD_CELL"])
    _csv(aggregate / "UNIQUE_EVALUATION_RESULTS.csv", columns, table_rows)
    _csv(aggregate / "LOGICAL_EVALUATION_RESULTS.csv", columns, table_rows + [table_rows[2], table_rows[4]])
    original_aggregate = b'{ "copied_byte_exactly": true, "unselected_field": 123 }\n'
    (aggregate / "FIELD_DEFINITIONS.json").write_bytes(original_aggregate)
    event = stage / "01_SEQUENCE_CONTRACT/attempt/EVENT_WINDOW_V2.json"
    event_sha = write_json(event, {"synthetic": True})
    contract_path = contract_dir / f"CLEAN5_{dataset}_SEQUENCE_CONTRACT.yaml"
    contract = {
        "contract_version": 2,
        "time_contract": {"base_time": pack.BASE_TIMES[dataset]},
        "window_contract": {"t_start": 10.0, "t_end": 11.0, "event_report_relative_path": event.relative_to(stage).as_posix()},
        "event_window_report_sha256": event_sha,
        "synthetic_fixture_label": "frozen source definition",
    }
    if dataset == "BY2O":
        occlusion_sha = write_json(stage / "01_SEQUENCE_CONTRACT/OCCLUSION_WINDOW.json", {"main_window": {"t0": 10.1, "t1": 10.3}})
        contract["occlusion_window"] = {"report_sha256": occlusion_sha}
    contract_sha = write_json(contract_path, contract)
    provider_path = stage / "02_PROVIDER_FREEZE/PROVIDER_MANIFEST.json"
    provider_sha = write_json(provider_path, {"data_mode": "synthetic_pack_test"})
    seal_dir = stage / "05_OUTPUT_SEAL_V2"
    seal_dir.mkdir(parents=True)
    registries = []
    for name, rows in [("UNIQUE_RUN_TERMINAL_REGISTRY.csv", table_rows), ("LOGICAL_RESULT_TERMINAL_REGISTRY.csv", table_rows + [table_rows[2], table_rows[4]])]:
        item = _csv(seal_dir / name, ["run_id", "terminal_status"], [[row[0], "COMPLETED"] for row in rows])
        registries.append({"relative_path": item.relative_to(stage).as_posix(), "sha256": _sha(item.read_bytes())})
    seal_sha = write_json(stage / "05_OUTPUT_SEAL_V2/OUTPUT_SEAL.json", {
        "dataset_id": dataset, "audits_passed": True, "trace_reads_before_seal": 0,
        "raw_write_open_count": 0, "files": sealed_files, "registries": registries,
    })
    seal_gate_path = seal_dir / "SEAL_GATE.json"
    seal_gate_sha = write_json(seal_gate_path, {"status": "PASS", "contract_version": 2, "contract": contract})
    gate_sha = write_json(stage / "07_OFFLINE_EVALUATION/EVALUATION_SEQUENCE_GATE.json", {
        "status": "PASS", "dataset_id": dataset, "completed_evaluations": 5,
        "logical_result_count": 7, "post_seal_hashes_unchanged": True,
        "output_seal_sha256": seal_sha, "window": {"t_start": 10.0, "t_end": 11.0},
        "aggregate_files": {item.name: {"path": str(item), "sha256": _sha(item.read_bytes())} for item in aggregate.iterdir()},
    })
    pins = {"evaluation_gate": gate_sha, "output_seal": seal_sha, "provider_manifest": provider_sha,
            "contract": contract_sha, "seal_gate": seal_gate_sha}
    monkeypatch.setitem(pack.PINS, dataset, pins)
    raw_sentinel = raw / "trace.csv"
    raw_sentinel.write_bytes(b"RAW_MUST_NEVER_BE_PACKAGED\n")
    return dict(source=source, raw=raw, output=output, code=code, dataset=dataset,
                aggregate_bytes=original_aggregate, contract_path=contract_path,
                seal_gate_path=seal_gate_path, contract=contract, pins=pins,
                provider_path=provider_path, stage=stage)


@pytest.mark.parametrize("clean5_inputs", ["BY2H", "BY2O"], indirect=True)
def test_clean5_orchestrator_keeps_all_aggregates_without_unfiltered_evaluation_copy(pack, clean5_inputs):
    fixture = clean5_inputs
    source, raw, output, code, dataset = [fixture[key] for key in ["source", "raw", "output", "code", "dataset"]]
    with pack.PackageBuilder(output, source_roots=[source, code], raw_root=raw) as builder:
        result = pack._pack_clean5(builder, source, code, dataset)
        probe = builder.finish({"sequences": {dataset: result}})
    assert result["unique_runs"] == 5 and result["logical_rows"] == 7
    assert probe["raw_trace_included"] is False and probe["raw_files_opened"] == 0
    with zipfile.ZipFile(output) as archive:
        names = set(archive.namelist())
        members = {name for name in names if "/08_AGGREGATE/" in name}
        assert members == {
            f"{dataset}/08_AGGREGATE/UNIQUE_EVALUATION_RESULTS.csv.gz",
            f"{dataset}/08_AGGREGATE/LOGICAL_EVALUATION_RESULTS.csv.gz",
            f"{dataset}/08_AGGREGATE/FIELD_DEFINITIONS.json",
        }
        assert archive.read(f"{dataset}/08_AGGREGATE/FIELD_DEFINITIONS.json") == fixture["aggregate_bytes"]
        for name in names:
            payload = archive.read(name)
            if name.endswith(".gz"):
                payload = gzip.decompress(payload)
            assert b"SECRET_CELL" not in payload
            assert b"RAW_PAYLOAD_CELL" not in payload
            assert b"RAW_MUST_NEVER_BE_PACKAGED" not in payload
        assert len([name for name in names if name.endswith("/PORT_GNSS_UPDATE_TRACE.csv")]) == 5


@pytest.mark.parametrize("clean5_inputs", ["BY2H", "BY2O"], indirect=True)
@pytest.mark.parametrize("mutation", ["contract_other_key", "provider_hash", "base_time", "registry_hash"])
def test_frozen_sequence_dependencies_reject_changes(pack, clean5_inputs, mutation):
    fixture = clean5_inputs
    if mutation == "provider_hash":
        fixture["provider_path"].write_text('{"data_mode":"changed"}\n')
    elif mutation == "registry_hash":
        (fixture["stage"] / "05_OUTPUT_SEAL_V2/UNIQUE_RUN_TERMINAL_REGISTRY.csv").write_text("run_id,terminal_status\nchanged,COMPLETED\n")
    else:
        contract = json.loads(fixture["contract_path"].read_text())
        if mutation == "contract_other_key":
            # The evaluation window is byte-for-byte equal; another frozen input
            # field must still be protected by the complete contract hash.
            contract["synthetic_fixture_label"] = "mutated without changing window"
        else:
            # Re-pin this synthetic metadata so the failure exercises the base-time
            # rule itself rather than merely the earlier whole-file hash check.
            contract["time_contract"]["base_time"] = 123.0
        fixture["contract_path"].write_text(json.dumps(contract) + "\n")
        if mutation == "base_time":
            fixture["pins"]["contract"] = _sha(fixture["contract_path"].read_bytes())
            seal_gate = {"status": "PASS", "contract_version": 2, "contract": contract}
            fixture["seal_gate_path"].write_text(json.dumps(seal_gate) + "\n")
            fixture["pins"]["seal_gate"] = _sha(fixture["seal_gate_path"].read_bytes())
    with pack.PackageBuilder(fixture["output"], source_roots=[fixture["source"], fixture["code"]], raw_root=fixture["raw"]) as builder:
        with pytest.raises(ValueError):
            pack._pack_clean5(builder, fixture["source"], fixture["code"], fixture["dataset"])


def test_generated_subset_manifest_has_package_digest_and_row_count(pack, roots):
    source, raw, output = roots
    member = "BY2/error_series_subset/SUBSET_MANIFEST.csv"
    content = "run_id,rows_full,rows_kept,status\nRUN_00002,6,3,OK\nRUN_00003,6,3,OK\n"
    with pack.PackageBuilder(output, source_roots=[source], raw_root=raw) as builder:
        builder.add_generated(member, content)
        probe = builder.finish()
    with zipfile.ZipFile(output) as archive:
        payload = archive.read(member)
        recorded = json.loads(archive.read("IDENTITY_PROBE.json"))
    entries = [entry for entry in recorded["generated_entries"] if entry["member"] == member]
    assert len(entries) == 1
    assert entries[0]["package_sha256"] == _sha(payload)
    assert entries[0]["package_rows"] == 2
    assert entries[0]["package_bytes"] == len(payload)
    assert entries[0]["source_path"] is None
    assert entries[0]["source_sha256"] is None
    assert entries[0]["source_rows"] is None
    assert recorded == probe


def test_existing_output_is_never_replaced(pack, roots):
    source, raw, output = roots
    output.write_bytes(b"previous attempt sentinel")
    with pytest.raises((FileExistsError, ValueError)):
        with pack.PackageBuilder(output, source_roots=[source], raw_root=raw):
            pytest.fail("existing output was admitted")
    assert output.read_bytes() == b"previous attempt sentinel"


@pytest.mark.parametrize("member", ["../escape.csv", "/absolute.csv", "nested/../../escape.csv", "nested\\escape.csv"])
def test_unsafe_archive_paths_are_rejected(pack, roots, member):
    source, raw, output = roots
    item = source / "metadata.json"
    item.write_text("{}")
    with pack.PackageBuilder(output, source_roots=[source], raw_root=raw) as builder:
        with pytest.raises(ValueError):
            builder.add_file(item, member)


@pytest.mark.parametrize("kind", ["raw", "outside", "symlink"])
def test_source_boundaries_reject_raw_trace_outside_root_and_symlink(pack, roots, tmp_path, kind):
    source, raw, output = roots
    target = raw / "trace.csv" if kind != "outside" else tmp_path / "outside.json"
    target.write_text("synthetic forbidden payload\n")
    if kind == "symlink":
        link = source / "metadata.json"
        link.symlink_to(target)
        target = link
    with pack.PackageBuilder(output, source_roots=[source], raw_root=raw) as builder:
        with pytest.raises(ValueError):
            builder.add_file(target, "metadata.json")


def test_raw_root_is_denied_even_when_its_parent_is_an_allowed_source(pack, roots, tmp_path):
    _, raw, output = roots
    trace = raw / "trace.csv"
    trace.write_text("synthetic raw reference\n")
    with pack.PackageBuilder(output, source_roots=[tmp_path], raw_root=raw) as builder:
        with pytest.raises(ValueError):
            builder.add_file(trace, "trace.csv")


@pytest.mark.parametrize("name", ["trace.csv", "trace_BY2H.csv.gz"])
def test_trace_payload_is_denied_inside_allowed_clean_root(pack, roots, name):
    source, raw, output = roots
    trace = source / name
    payload = b"time,lat,lon,height\n1,2,3,4\n"
    trace.write_bytes(gzip.compress(payload) if name.endswith(".gz") else payload)
    with pack.PackageBuilder(output, source_roots=[source], raw_root=raw) as builder:
        with pytest.raises(ValueError):
            builder.add_file(trace, "renamed_metadata.bin")


def _c00_rows():
    # Frozen six-decimal table anchors, not a metric recomputation fixture.
    return [
        dict(zip(("method_id", "effective_configuration_id", "horizontal_rmse_m", "position_3d_rmse_m", "yaw_rmse_deg"), values), case_id="C00_clean_normal", run_id={"F02":"RUN_00002", "F03":"RUN_00003", "A04":"RUN_00006", "F04":"RUN_00004"}[values[0]])
        for values in [
            ("F02", "basic_dual_yaw_EKF", "0.355526", "0.893102", "2.338427"),
            ("F03", "AB0000", "0.352517", "0.890581", "1.962413"),
            ("A04", "AB1011", "0.352386", "0.890358", "1.934076"),
            ("F04", "AB1111", "0.354803", "0.926378", "1.954959"),
        ]
    ]


def test_c00_anchor_probe_reads_table_fields_without_accepting_nearby_case(pack):
    rows = _c00_rows()
    assert pack.validate_c00_anchors(rows)
    wrong = [dict(row, case_id="D01_changed") for row in rows]
    with pytest.raises(ValueError):
        pack.validate_c00_anchors(wrong)


@pytest.mark.parametrize("change", ["wrong_value", "missing", "duplicate", "nonfinite", "near_case", "wrong_config"])
def test_c00_anchor_validation_is_fail_closed(pack, change):
    rows = _c00_rows()
    if change == "wrong_value":
        rows[-1]["yaw_rmse_deg"] = "1.813898"
    elif change == "missing":
        rows.pop()
    elif change == "duplicate":
        rows.append(dict(rows[-1]))
    elif change == "near_case":
        rows[-1]["case_id"] = "prefix_C00_clean_normal"
    elif change == "wrong_config":
        rows[-1]["effective_configuration_id"] = "AB1011"
    else:
        rows[-1]["yaw_rmse_deg"] = "nan"
    with pytest.raises(ValueError):
        pack.validate_c00_anchors(rows)
