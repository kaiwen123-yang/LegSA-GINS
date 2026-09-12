"""C-05 entry gates and header-only syscall evidence on synthetic files only."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from types import SimpleNamespace

import pytest

from legsa_gins.paper_rebuild.clean5_sequence import header_evidence as headers
from legsa_gins.paper_rebuild.clean5_sequence import offline_eval as offline
from legsa_gins.paper_rebuild.clean5_sequence import decision_inputs

REPO = Path(__file__).resolve().parents[2]
HEADER = b"\xef\xbb\xbfaligned_time,lat,lon,height,roll,pitch,yaw,\xe5\xa4\x87\xe6\xb3\xa8\n"
SENTINEL = b"DATA_LINE_MUST_NOT_BE_READ,12345,67890\n"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


@pytest.fixture
def header_files(tmp_path):
    raw, clean = tmp_path / "raw", tmp_path / "clean"
    raw.mkdir()
    clean.mkdir()
    output = clean / "header_audit"
    output.mkdir()
    paths = []
    for dataset in ("BY2", "BY2H", "BY2O"):
        path = raw / (dataset + "_参考轨迹.csv")
        path.write_bytes(HEADER + SENTINEL)
        paths.append(path)
    return raw, clean, output, paths


def test_read_header_stops_at_first_newline_with_one_byte_reads(monkeypatch, header_files):
    path = header_files[-1][0]
    actual = headers.os.read
    chunks, sizes = [], []

    def observed(fd, size):
        value = actual(fd, size)
        chunks.append(value)
        sizes.append(size)
        return value

    monkeypatch.setattr(headers.os, "read", observed)
    result = headers.read_header(path)
    assert set(sizes) == {1} and b"".join(chunks) == HEADER
    assert result["bytes_read"] == len(HEADER) and result["header_bytes_hex"] == HEADER.hex()
    assert result["header_sha256"] == hashlib.sha256(HEADER).hexdigest()
    assert result["data_line_bytes_read"] == 0 and result["read_role"] == "header_only_read"
    assert result["columns"][-1] == "备注" and result["columns"][0] == "aligned_time"


@pytest.mark.parametrize("payload,reason", [(b"no newline", "terminal newline"),
    (b"x" * 65536 + b"\n", "64 KiB"), (b"time,lat,lat\n", "Duplicate")])
def test_invalid_header_is_refused_without_data_parsing(tmp_path, payload, reason):
    path = tmp_path / "synthetic.csv"
    path.write_bytes(payload)
    with pytest.raises(RuntimeError, match=reason):
        headers.read_header(path)


HEADER_CHILD = r'''
import hashlib,json,os,sys
from legsa_gins.paper_rebuild.clean5_sequence.header_evidence import read_header
mode, paths = sys.argv[1], json.loads(sys.argv[2])
rows=[]
for path in paths:
    if mode == 'correct':
        rows.append(read_header(path))
        continue
    fd=os.open(path,os.O_RDONLY)
    try:
        if mode == 'prefetch':
            payload=os.read(fd,65536)
            payload=payload[:payload.index(b'\n')+1]
        else:
            payload=b''
            while not payload.endswith(b'\n'):
                payload+=os.read(fd,1)
            os.read(fd,1)
    finally:
        os.close(fd)
    rows.append({'path':path,'header_bytes_hex':payload.hex(),'data_line_bytes_read':0})
print(json.dumps(rows,ensure_ascii=False))
'''


@pytest.mark.parametrize("mode,passed", [("correct", True), ("extra_byte", False), ("prefetch", False)])
def test_header_syscall_evidence_covers_three_utf8_paths_and_rejects_prefetch(header_files, mode, passed):
    assert shutil.which("strace"), "header proof requires strace"
    raw, clean, output, paths = header_files
    log = output / "HEADERS.strace"
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1", "PYTHONPATH": str(REPO / "src"),
           "CLEAN5_EVALUATOR_CAPTURE_CONFIG": ""}
    child = subprocess.run(["strace", "-f", "-yy", "-s", "65535", "-e", "trace=openat,read,close",
        "-o", str(log), sys.executable, "-B", "-c", HEADER_CHILD, mode,
        json.dumps([str(p) for p in paths], ensure_ascii=False)],
        cwd=REPO, env=env, capture_output=True, text=True, timeout=30)
    assert child.returncode == 0, child.stderr
    rows = json.loads(child.stdout)
    report = headers.audit_headers(log, rows, cwd=REPO, raw_root=raw, clean_root=clean, output_root=output)
    assert report["passed"] is passed
    assert report["trace_open_count"] == 3 and report["bag_open_count"] == report["fpl_open_count"] == 0
    assert report["write_scope"]["pass"] and report["write_scope"]["raw_write_open_count"] == 0
    assert report["strace_sha256"] == sha(log)
    if passed:
        assert report["data_line_bytes_read"] == 0
        assert all(row["header_bytes_hex"] == HEADER.hex() for row in rows)
        assert "DATA_LINE_MUST_NOT_BE_READ" not in log.read_text()
    else:
        assert report["data_line_bytes_read"] is None
        assert any("header line" in failure or "single-byte" in failure for failure in report["failures"])


@pytest.mark.parametrize("columns,expected", [
    (["aligned_time", "lat", "processed_lat", "lon", "processed_lon", "height", "roll", "pitch", "yaw"],
     {"time": "aligned_time", "lat": "lat", "lon": "lon", "height": "height", "roll": "roll", "pitch": "pitch", "yaw": "yaw"}),
    (["sys_stamp", "processed_lat", "lat", "processed_lon", "lon", "processed_height", "height", "roll", "pitch", "processed_yaw", "yaw", "aligned_time"],
     {"time": "aligned_time", "lat": "processed_lat", "lon": "processed_lon", "height": "processed_height", "roll": "roll", "pitch": "pitch", "yaw": "processed_yaw"}),
    (["TIME", "Latitude", "Longitude", "Altitude", "ROLL", "PITCH", "YAW"],
     {"time": "TIME", "lat": "Latitude", "lon": "Longitude", "height": "Altitude", "roll": "ROLL", "pitch": "PITCH", "yaw": "YAW"}),
])
def test_column_resolution_reproduces_archived_candidate_then_source_order(columns, expected):
    assert headers.select_columns(columns) == expected


@pytest.fixture
def registry(tmp_path):
    clean, raw = tmp_path / "clean", tmp_path / "raw"
    clean.mkdir()
    raw.mkdir()
    return SimpleNamespace(clean_root=clean, raw_root=raw, code_root=REPO,
        sequences={ds: SimpleNamespace(stage_id=ds + "_SYNTHETIC_STAGE", trace_path=raw / (ds + ".csv"))
                   for ds in ("BY2H", "BY2O")})


@pytest.mark.parametrize("dataset", ["BY2H", "BY2O"])
@pytest.mark.parametrize("status,full", [("FAIL", "FAIL"), ("PENDING", "PENDING"), ("PASS", "PENDING")])
def test_a2_not_pass_refuses_before_preflight_nav_or_evaluator(monkeypatch, registry, dataset, status, full):
    gate_path = offline.identity_root(registry) / "EVALUATOR_IDENTITY_GATE.json"
    gate_path.parent.mkdir(parents=True)
    gate_path.write_text(json.dumps({"status": status, "full_identity_gate": full,
                                    "evaluator_sha256": offline.EVALUATOR_SHA256}))

    def forbidden(*args, **kwargs):
        raise AssertionError("A2 denial must precede all H/O input or evaluator access")

    for name in ("preflight", "trace_lock", "evaluate"):
        monkeypatch.setattr(offline, name, forbidden)
    monkeypatch.setattr(offline, "git_head", lambda path: "a" * 40)
    with pytest.raises(RuntimeError, match="A2 identity gate not PASS"):
        offline.run_sequence(registry, dataset, registry.clean_root / "not_read.py", registry.clean_root / "not_read_attempt")
    assert not (registry.clean_root / "stages" / registry.sequences[dataset].stage_id).exists()


@pytest.fixture
def identity_evidence(registry):
    root = offline.identity_root(registry)
    (root / "HEADER_ONLY").mkdir(parents=True)
    gate = {"status": "PASS", "full_identity_gate": "PASS", "code_commit": "a" * 40,
            "evaluator_sha256": offline.EVALUATOR_SHA256,
            "A2_1": {"passed": True, "runs": [{"method_id": "A04"}, {"method_id": "F04"}]},
            "A2_2": {"passed": True, "runs": [{"fixture": n} for n in range(4)]},
            "A2_3": {"passed": True, "strace": {"passed": True, "trace_open_count": 3,
                        "bag_open_count": 0, "fpl_open_count": 0, "data_line_bytes_read": 0}},
            "evidence_files": {}}
    files = {"A2_1": "A2_1_C00_REPRODUCTION_GATE.json", "A2_2": "A2_2_SYNTHETIC_GATE.json",
             "A2_3": "HEADER_ONLY/HEADER_GATE.json"}
    for key, name in files.items():
        path = root / name
        path.write_text(json.dumps(gate[key]))
        gate["evidence_files"][name] = sha(path)
    path = root / "EVALUATOR_IDENTITY_GATE.json"
    path.write_text(json.dumps(gate))
    return path, gate, files


def test_complete_identity_gate_passes_with_three_locked_components(identity_evidence):
    path, gate, _ = identity_evidence
    assert offline.validate_identity_gate(path, code_commit="a" * 40) == gate


@pytest.mark.parametrize("key", ["A2_1", "A2_2", "A2_3"])
def test_fake_top_pass_cannot_hide_failed_child_before_evaluation(monkeypatch, registry, identity_evidence, key):
    path, gate, files = identity_evidence
    gate[key]["passed"] = False
    child = path.parent / files[key]
    child.write_text(json.dumps(gate[key]))
    gate["evidence_files"][files[key]] = sha(child)
    path.write_text(json.dumps(gate))
    monkeypatch.setattr(offline, "git_head", lambda path: "a" * 40)

    def forbidden(*args, **kwargs):
        raise AssertionError("Failed component must stop before H/O NAV/preflight/evaluation")

    for name in ("preflight", "trace_lock", "evaluate"):
        monkeypatch.setattr(offline, name, forbidden)
    with pytest.raises(RuntimeError, match="component gate not PASS"):
        offline.run_sequence(registry, "BY2H", registry.clean_root / "not_read.py", registry.clean_root / "not_read_attempt")


@pytest.mark.parametrize("defect", ["hash_changed", "embedded_mismatch", "data_prefetched", "run_count", "code_changed"])
def test_identity_evidence_rejects_sidecar_drift_and_incomplete_audit(identity_evidence, defect):
    path, gate, files = identity_evidence
    code = "a" * 40
    if defect == "hash_changed":
        child = path.parent / files["A2_1"]
        child.write_bytes(child.read_bytes() + b"\n")
    elif defect == "embedded_mismatch":
        gate["A2_1"]["unexpected_change"] = True
    elif defect in {"data_prefetched", "run_count"}:
        key = "A2_3" if defect == "data_prefetched" else "A2_2"
        if defect == "data_prefetched":
            gate[key]["strace"]["data_line_bytes_read"] = 1
        else:
            gate[key]["runs"].pop()
        child = path.parent / files[key]
        child.write_text(json.dumps(gate[key]))
        gate["evidence_files"][files[key]] = sha(child)
    else:
        code = "b" * 40
    path.write_text(json.dumps(gate))
    with pytest.raises(RuntimeError):
        offline.validate_identity_gate(path, code_commit=code)


@pytest.fixture
def summary_pair():
    position = {k: float(i + 1) for i, k in enumerate([
        "north_rmse_m", "east_rmse_m", "up_rmse_m", "horizontal_rmse_m", "position_3d_rmse_m",
        "horizontal_p95_m", "vertical_p95_m"])}
    attitude = {k: float(i + 11) for i, k in enumerate([
        "roll_rmse_deg", "pitch_rmse_deg", "yaw_rmse_deg", "roll_p95_deg", "pitch_p95_deg", "yaw_p95_deg"])}
    mapped = {"vertical_p95_m": "up_p95_absolute_m", "yaw_p95_deg": "yaw_p95_absolute_deg",
              "roll_p95_deg": "roll_p95_absolute_deg", "pitch_p95_deg": "pitch_p95_absolute_deg"}
    row = {mapped.get(k, k): v for group in (position, attitude) for k, v in group.items()}
    return {"position": position, "attitude": attitude}, row


def test_all_thirteen_summary_rmse_p95_mappings(summary_pair):
    checks = offline.summary_checks(*summary_pair)
    assert len(checks) == 13 and all(row["passed"] for row in checks)
    assert {row["result_field"] for row in checks} == set(summary_pair[1])
    assert all(row["relative_difference"] == 0 for row in checks)
    assert next(row for row in checks if row["summary_field"] == "position/vertical_p95_m")["result_field"] == "up_p95_absolute_m"


@pytest.mark.parametrize("defect", ["row_missing", "row_nan", "summary_inf", "mismatch", "zero_vs_nonzero", "summary_missing"])
def test_summary_gate_fails_missing_nonfinite_or_mismatched_fields(summary_pair, defect):
    summary, row = summary_pair
    if defect == "row_missing":
        row.pop("yaw_p95_absolute_deg")
    elif defect == "row_nan":
        row["up_rmse_m"] = float("nan")
    elif defect == "summary_inf":
        summary["attitude"]["yaw_rmse_deg"] = float("inf")
    elif defect == "mismatch":
        row["horizontal_rmse_m"] *= 1.000001
    elif defect == "zero_vs_nonzero":
        row["up_rmse_m"] = 0
    else:
        summary["attitude"].pop("roll_p95_deg")
    with pytest.raises(RuntimeError):
        offline.summary_checks(summary, row)


def test_summary_zero_equality_and_small_relative_difference_pass(summary_pair):
    summary, row = summary_pair
    summary["position"]["up_rmse_m"] = row["up_rmse_m"] = 0.0
    row["yaw_rmse_deg"] *= 1 + 1e-12
    checks = offline.summary_checks(summary, row)
    assert len(checks) == 13 and all(item["passed"] for item in checks)


@pytest.fixture
def decision_sources(registry):
    expected = {}
    for ds in ("BY2H", "BY2O"):
        stage = registry.clean_root / "stages" / registry.sequences[ds].stage_id
        (stage / "08_AGGREGATE").mkdir(parents=True)
        table = stage / "08_AGGREGATE/WINDOW_SEGMENT_SUMMARY.csv"
        table.write_text("synthetic_table_test_only\n")
        (stage / "07_OFFLINE_EVALUATION").mkdir()
        gate = {"status": "PASS", "aggregate_files": {table.name: {"sha256": sha(table)}},
                "decision_source_hashes": {"yaw_gate": "1" * 64, "occlusion_window": "2" * 64}}
        (stage / "07_OFFLINE_EVALUATION/EVALUATION_SEQUENCE_GATE.json").write_text(json.dumps(gate))
        expected[ds] = gate
    (registry.clean_root / "stages/CLEAN5_DECISION").mkdir()
    return registry, expected


def test_decision_passes_sealed_hashes_to_extractor_and_never_overwrites(monkeypatch, decision_sources):
    registry, expected = decision_sources
    calls = []

    def extract(**kwargs):
        calls.append(kwargs)
        return {"extraction_status": "PASS", "synthetic_test_only": True}

    monkeypatch.setattr(decision_inputs, "extract_decision_inputs", extract)
    offline.run_decision(registry)
    destination = registry.clean_root / decision_inputs.DECISION_INPUTS_RELATIVE_PATH
    original = destination.read_bytes()
    assert calls[0]["expected_source_hashes"] == {
        "by2h_table": expected["BY2H"]["aggregate_files"]["WINDOW_SEGMENT_SUMMARY.csv"]["sha256"],
        "by2o_table": expected["BY2O"]["aggregate_files"]["WINDOW_SEGMENT_SUMMARY.csv"]["sha256"],
        "yaw_gate": "1" * 64, "occlusion_window": "2" * 64}
    with pytest.raises(FileExistsError):
        offline.run_decision(registry)
    assert destination.read_bytes() == original


@pytest.mark.parametrize("defect", ["aggregate_mutation", "sequence_failed"])
def test_decision_requires_two_pass_gates_and_unchanged_aggregate(monkeypatch, decision_sources, defect):
    registry, expected = decision_sources
    stage = registry.clean_root / "stages" / registry.sequences["BY2O"].stage_id
    if defect == "aggregate_mutation":
        (stage / "08_AGGREGATE/WINDOW_SEGMENT_SUMMARY.csv").write_text("changed\n")
    else:
        path = stage / "07_OFFLINE_EVALUATION/EVALUATION_SEQUENCE_GATE.json"
        value = json.loads(path.read_text())
        value["status"] = "FAIL"
        path.write_text(json.dumps(value))

    def forbidden(**kwargs):
        raise AssertionError("Decision extraction must follow both prerequisites")

    monkeypatch.setattr(decision_inputs, "extract_decision_inputs", forbidden)
    with pytest.raises(RuntimeError):
        offline.run_decision(registry)
    assert not (registry.clean_root / decision_inputs.DECISION_INPUTS_RELATIVE_PATH).exists()
