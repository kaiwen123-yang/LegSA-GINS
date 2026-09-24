"""HX-02 adapters: sequence override, heading tables, convention diagnostic, coverage, GINav NAV."""
from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
import yaml

from legsa_gins.paper_rebuild.hext import (
    hx02_convention,
    hx02_coverage_evaluation,
    hx02_ginav,
    hx02_ginav_nav,
    hx02_heading_tables,
    hx02_rtklib,
)
from legsa_gins.paper_rebuild.horizontal_literature import sequence_override

REPO = Path(__file__).resolve().parents[2]
LOCAL = REPO / "configs/paper_rebuild/DATA_PATHS.CLEAN3R4.local.yaml"
BASE = 1772784000.0
WEEK = 2408
LEAP = 18


def _spec(tmp_path, **changes):
    spec = {"schema": sequence_override.SPEC_SCHEMA, "sequence_id": "BY2H", "data_mode": "real_raw",
            "raw_root": str(tmp_path / "raw"), "fix_root": str(tmp_path / "raw/fix"),
            "gnss1_raw": str(tmp_path / "raw/fix/gnss1-raw.csv"), "gnss2_raw": str(tmp_path / "raw/fix/gnss2-raw.csv"),
            "raw_hash_lock": str(tmp_path / "lock.csv"), "base_time": BASE, "window": [413.0, 683.0],
            "start_convention": "CONTRACT_START", "native_start_rel_s": 413.0, "full_pair_count": 4,
            "selected_pair_count": 2, "artifact_root": str(tmp_path / "artifact"), "method_id": "EXT01",
            "leap_seconds": LEAP, **changes}
    path = tmp_path / "SPEC.json"
    path.write_text(json.dumps(spec))
    return path


def _tow(rel):
    return BASE + rel - (315964800.0 + WEEK * 604800.0) + LEAP


@pytest.fixture
def clean_override(monkeypatch):
    monkeypatch.setattr(sequence_override, "_ACTIVE", None)
    yield sequence_override


def test_override_selects_contract_start_pairs_and_refuses_second_activation(tmp_path, clean_override):
    spec = clean_override.activate(_spec(tmp_path))
    assert spec["spec_path"].endswith("SPEC.json")
    epoch = lambda rel: SimpleNamespace(gps_week=WEEK, gps_tow_seconds=_tow(rel), leap_seconds=LEAP)  # noqa: E731
    pairs = [(epoch(rel), epoch(rel)) for rel in (412.8, 412.998, 413.198, 500.0)]
    kept = clean_override.select_pairs(pairs)
    assert [round(p[0].gps_tow_seconds - _tow(0.0), 3) for p in kept] == [413.198, 500.0]
    assert clean_override.full_pair_count(1509) == 4 and clean_override.expected_pair_count(1509) == 2
    assert clean_override.rtklib_start_arguments((WEEK, _tow(413.198))) == ["-ts", "2026/03/06", "08:07:11.198"]
    with pytest.raises(sequence_override.SequenceOverrideError, match="first selected pair"):
        clean_override.rtklib_start_arguments(None)
    with pytest.raises(sequence_override.SequenceOverrideError, match="already active"):
        clean_override.activate(_spec(tmp_path))


def test_override_defaults_and_refusals(tmp_path, clean_override):
    assert clean_override.full_pair_count(1509) == 1509 and clean_override.option("variant_ids") is None
    assert clean_override.rtklib_start_arguments(None) == []
    with pytest.raises(sequence_override.SequenceOverrideError, match="disagree"):
        clean_override.activate(_spec(tmp_path, native_start_rel_s=None))
    with pytest.raises(sequence_override.SequenceOverrideError, match="reference trajectory"):
        clean_override.activate(_spec(tmp_path, gnss1_raw=str(tmp_path / "raw/fix/trace_vrtk.csv")))
    spec = clean_override.activate(_spec(tmp_path, start_convention="FILE_START", native_start_rel_s=None))
    epoch = SimpleNamespace(gps_week=WEEK, gps_tow_seconds=_tow(1.0), leap_seconds=LEAP)
    assert clean_override.select_pairs([(epoch, epoch)]) == [(epoch, epoch)] and spec["method_id"] == "EXT01"
    assert clean_override.rtklib_start_arguments((WEEK, _tow(1.0))) == []


def _native_csv(path, rows):
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    return path


def test_heading_table_adapters_keep_every_native_epoch_and_the_method_flag(tmp_path):
    base = {"gps_week": str(WEEK), "gps_tow_seconds": "100.2", "body_yaw_deg": "10.5"}
    ext01 = _native_csv(tmp_path / "e1.csv", [
        {**base, "epoch_index": "0", "integer_solution_returned": "true"},
        {**base, "epoch_index": "1", "gps_tow_seconds": "100.4", "integer_solution_returned": "false", "body_yaw_deg": ""}])
    rows = hx02_heading_tables.ext01(ext01, LEAP)["EXT01"]
    assert [r["valid"] for r in rows] == [1, 0] and rows[1]["body_yaw_deg"] == ""
    assert float(rows[0]["time_unix_s"]) == pytest.approx(315964800.0 + WEEK * 604800.0 + 100.2 - LEAP)
    ext03 = _native_csv(tmp_path / "e3.csv", [
        {**base, "epoch_index": "0", "system_mode": "GPS_BDS_DUAL_FREQUENCY", "constraint_mode": "CONSTRAINED",
         "baseline_sigma_m": "0.01", "solution_state": "float", "paper_ratio_fixed": "false"},
        {**base, "epoch_index": "0", "system_mode": "GPS_BDS_DUAL_FREQUENCY", "constraint_mode": "CONSTRAINED",
         "baseline_sigma_m": "0.02", "solution_state": "fixed", "paper_ratio_fixed": "true"},
        {**base, "epoch_index": "1", "gps_tow_seconds": "100.4", "system_mode": "GPS_BDS_DUAL_FREQUENCY",
         "constraint_mode": "CONSTRAINED", "baseline_sigma_m": "0.01", "solution_state": "fixed",
         "paper_ratio_fixed": "true"}])
    rows = hx02_heading_tables.ext03(ext03, LEAP)["EXT03"]
    assert [(r["epoch_index"], r["valid"], r["ratio_fixed"]) for r in rows] == [(0, 1, 0), (1, 1, 1)]
    ext04 = _native_csv(tmp_path / "e4.csv", [
        {**base, "epoch_index": "1", "system_mode": "GPS_BDS_DUAL_FREQUENCY", "policy_identity": "FAR_ALL_AMBIGUITIES",
         "accepted_by_policy": "false"},
        {**base, "epoch_index": "0", "system_mode": "GPS_BDS_DUAL_FREQUENCY",
         "policy_identity": "EXT04_PAR_DECLARED_POLICY_V1", "accepted_by_policy": "true"},
        {**base, "epoch_index": "0", "system_mode": "GPS_L1", "policy_identity": "FAR_ALL_AMBIGUITIES",
         "accepted_by_policy": "true"},
        {**base, "epoch_index": "0", "system_mode": "GPS_BDS_DUAL_FREQUENCY",
         "policy_identity": "EXT04_PAR_DECLARED_POLICY_V1_RATIO_2P0", "accepted_by_policy": "true"}])
    tables = hx02_heading_tables.ext04(ext04, LEAP)
    assert {k: [(r["epoch_index"], r["valid"]) for r in v] for k, v in tables.items()} == {
        "EXT04_FAR": [(1, 0)], "EXT04_PAR": [(0, 1)]}
    written = tmp_path / "table.csv"
    digest = hx02_heading_tables.write_table(rows, written)
    assert digest == hashlib.sha256(written.read_bytes()).hexdigest()
    assert written.read_text().splitlines()[0] == "epoch_index,gps_week,gps_tow_seconds,time_unix_s,valid,body_yaw_deg,ratio_fixed"


def _rows(differences, proxy_base=100.0):
    rows, proxy = [], {}
    for index, difference in enumerate(differences):
        tow = 1000.0 + 0.2 * index
        proxy[int(round(tow * 1000))] = proxy_base
        rows.append({"valid": "1", "gps_tow_seconds": repr(tow), "body_yaw_deg": repr((proxy_base + difference) % 360.0)})
    return rows, proxy


@pytest.mark.parametrize("differences, status", [
    ([1.0, -2.0, 3.0, 0.5, 179.0], "PASS"),
    ([88.0, 91.0, 95.0, -20.0, 100.0], "HARD_STOP"),
    ([-172.0, 178.0, -175.0, 10.0, -179.0], "HARD_STOP"),
    ([60.0, 65.0, 62.0], "PASS"),
])
def test_convention_diagnostic_median_bands(differences, status):
    rows, proxy = _rows(differences)
    result = hx02_convention.diagnose(rows, proxy)
    assert result["status"] == status and result["hard_stop"] == (status == "HARD_STOP")
    assert result["compared_epochs"] == len(differences)
    assert result["median_deg"] == pytest.approx(float(np.median([hx02_convention.wrap180(d) for d in differences])))


def test_convention_diagnostic_without_overlap_is_unavailable_not_a_stop():
    rows, _proxy = _rows([0.0, 1.0])
    result = hx02_convention.diagnose(rows, {})
    assert result == {"compared_epochs": 0, "median_deg": None, "hard_stop": False,
                      "status": "UNAVAILABLE_NO_METHOD_VALID_DUAL_FIXED_EPOCH"}
    rows[0]["valid"] = "0"
    rows[1]["valid"] = "0"
    assert hx02_convention.diagnose(rows, _proxy)["compared_epochs"] == 0


def test_coverage_definitions_on_a_synthetic_sparse_output():
    times = [66.0, 67.0, 68.0, 80.0, 81.0, 200.0, 340.0, 341.0]
    result = hx02_coverage_evaluation.coverage(times, (66.0, 340.0))
    assert result["expected_integer_epochs"] == 275 and result["valid_rows_in_window"] == 7
    assert result["row_coverage_fraction"] == pytest.approx(7 / 275)
    assert result["temporal_coverage_fraction"] == pytest.approx(274.0 / 274.0)
    assert result["max_gap_s"] == pytest.approx(140.0) and result["segment_count"] == 4
    empty = hx02_coverage_evaluation.coverage([10.0, 20.0], (66.0, 340.0))
    assert empty["valid_rows_in_window"] == 0 and empty["segment_count"] == 0 and empty["row_coverage_fraction"] == 0.0


def test_rtklib_contract_start_argument_is_the_first_selected_pair_in_gpst():
    assert hx02_rtklib.gpst_start_arguments([(WEEK, _tow(413.198)), (WEEK, _tow(413.398))]) == \
        ["-ts", "2026/03/06", "08:07:11.198"]


def _clean_root():
    if not LOCAL.is_file():
        return None
    return Path(yaml.safe_load(LOCAL.read_text(encoding="utf-8"))["paths"]["clean_root"])


CLEAN4_POS = "stages/CLEAN4_BY2_HORIZONTAL_LITERATURE_COMPARISON/11_LC02_GINAV2021_OFFICIAL_REPRODUCTION/runtime/r4c/s/g4/GINAV_BY2_C00_NATIVE_SOLUTION.pos"
V3_ATTEMPT_NAV = "stages/CLEAN5_DEGSUBSET_BY2/09_HORIZONTAL_V3/LC02_GINAV/GINAV_FIXED_WINDOW_NAV.nav"
CLEAN4_TEMPLATE = "stages/CLEAN4_BY2_HORIZONTAL_LITERATURE_COMPARISON/11_LC02_GINAV2021_OFFICIAL_REPRODUCTION/runtime/r4b/s/g3c/BY2_GINAV_SPP_LC.ini"


def test_ginav_adapter_reproduces_the_v3_attempt_nav_byte_for_byte(tmp_path):
    clean = _clean_root()
    if clean is None or not (clean / CLEAN4_POS).is_file() or not (clean / V3_ATTEMPT_NAV).is_file():
        pytest.skip("CLEAN4 GINav .pos or v3 attempt NAV not available on this machine")
    pos = clean / CLEAN4_POS
    assert hashlib.sha256(pos.read_bytes()).hexdigest().startswith("39453826")
    result = hx02_ginav_nav.convert(pos, base_time=BASE, window=(66.0, 340.0), out_dir=tmp_path / "nav")
    window_nav = tmp_path / "nav" / "GINAV_WINDOW_NAV11.nav"
    assert (hashlib.sha256(window_nav.read_bytes()).hexdigest()
            == hashlib.sha256((clean / V3_ATTEMPT_NAV).read_bytes()).hexdigest()
            == "f0fa3e71270cce08ce6174376a694a00a92f725116f8cec86eed4d8062529012")
    assert result["window_rows"] == 77
    times = [float(line.split()[1]) for line in (tmp_path / "nav" / "GINAV_NATIVE_NAV11.nav").read_text().splitlines()
             if line.strip()]
    cov = hx02_coverage_evaluation.coverage(times, (66.0, 340.0))
    assert (cov["valid_rows_in_window"], cov["expected_integer_epochs"], cov["max_gap_s"], cov["segment_count"]) == (
        77, 275, 11.0, 38)
    assert cov["row_coverage_fraction"] == pytest.approx(0.28)
    assert cov["temporal_coverage_fraction"] == pytest.approx(0.6204270072992701)


def test_ginav_config_clone_changes_only_the_declared_lines(tmp_path):
    clean = _clean_root()
    if clean is None or not (clean / CLEAN4_TEMPLATE).is_file():
        pytest.skip("CLEAN4 BY2 derived GINav configuration not available on this machine")
    from datetime import datetime
    template = clean / CLEAN4_TEMPLATE
    result = hx02_ginav.derive_config(template, tmp_path / "BY2H.ini", data_dir=tmp_path / "data",
                                      start=datetime(2026, 3, 6, 8, 7, 11), end=datetime(2026, 3, 6, 8, 11, 50))
    original = template.read_bytes().decode("ascii").splitlines()
    derived = (tmp_path / "BY2H.ini").read_bytes().decode("ascii").splitlines()
    changed = [i for i, (a, b) in enumerate(zip(original, derived)) if a != b]
    assert len(original) == len(derived) and len(changed) == 3
    assert {line.split("=")[0].strip() for line in (derived[i] for i in changed)} == {"data_dir", "start_time", "end_time"}
    assert result["replaced"]["start_time"]["new"] == "2026/03/06 08:07:11"
    with pytest.raises(FileExistsError):
        hx02_ginav.derive_config(template, tmp_path / "BY2H.ini", data_dir=tmp_path, start=datetime(2026, 3, 6),
                                 end=datetime(2026, 3, 6))


def test_matlab_is_resolved_only_from_the_local_key(tmp_path):
    config = tmp_path / "local.yaml"
    config.write_text("paths:\n  code_root: /x\n", encoding="utf-8")
    with pytest.raises(hx02_ginav.GinavRunError, match="RUN_FAILED_ENVIRONMENT"):
        hx02_ginav.matlab_executable(config)
    config.write_text("paths:\n  hx02_matlab_executable: /nonexistent/matlab.exe\n", encoding="utf-8")
    assert hx02_ginav.matlab_executable(config) == Path("/nonexistent/matlab.exe")


def test_header_only_official_solution_is_reported_not_converted(tmp_path):
    from legsa_gins.paper_rebuild.horizontal_literature.ginav2021.outputs import OutputContractError
    pos = tmp_path / "header_only.pos"
    pos.write_text("% program   : GINav v0.1.0\n% mode      : SPP/INS LC\n%\n"
                   "%  GPST              x-ecef(m)      y-ecef(m)      z-ecef(m)   Q  ns\n", encoding="utf-8")
    with pytest.raises(OutputContractError, match="no data rows"):
        hx02_ginav_nav.convert(pos, base_time=BASE, window=(66.0, 340.0), out_dir=tmp_path / "nav")
