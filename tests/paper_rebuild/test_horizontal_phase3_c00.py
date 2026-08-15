from __future__ import annotations

import inspect
import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

import legsa_gins.paper_rebuild.horizontal_literature.phase3_runner as phase3
from legsa_gins.paper_rebuild.horizontal_literature.ext03_yang2024 import TrackingMemory
from legsa_gins.paper_rebuild.horizontal_literature.phase3_runner import (
    DEFAULT_WORKERS, MAX_WORKERS, NATIVE_FILE_NAMES, Variant,
    deterministic_variant_schedule, load_phase3_contract, requested_variants,
    validate_native_freeze,
)
from legsa_gins.paper_rebuild.horizontal_literature.phase3_signal_inventory import (
    audit_signal_availability, integer_compatible,
)
from legsa_gins.paper_rebuild.horizontal_literature.shared_raw_backend import (
    RawxEpoch, RawxMeasurement, SatelliteState, SignalIdentity,
)


ROOT = Path(__file__).resolve().parents[2]


class _Provider:
    status = "TEST_BROADCAST_PROVIDER"

    def state(self, identity, gps_week, gps_tow_seconds, pseudorange_m=None):
        return SatelliteState(np.asarray([20_200_000.0 + identity.sv_id, 14_000_000.0, 21_000_000.0]), np.zeros(3))


class _UnhealthyProvider(_Provider):
    def state(self, identity, gps_week, gps_tow_seconds, pseudorange_m=None):
        state = super().state(identity, gps_week, gps_tow_seconds, pseudorange_m)
        return SatelliteState(state.position_ecef_m, state.velocity_ecef_mps, health=1)


def _measurement(gnss: int, sv: int, sig: int, *, cp_std: int = 2, cp: float = 10.0, status: int = 0x07, locktime_ms: int = 1000):
    return RawxMeasurement(SignalIdentity(gnss, sv, sig, 0), 22_000_000.0 + sv, cp, -1000.0, locktime_ms, 45, 2, cp_std, 2, status)


def _epoch(measurements, tow=100.0, receiver_status=1):
    return RawxEpoch(tow, 2409, 18, receiver_status, 1, tuple(measurements))


def test_contract_locks_identity_grid_reference_closure_and_15_native_outputs():
    contract = load_phase3_contract()
    assert contract["paper_source"]["doi"] == "10.1109/TIM.2024.3374423"
    assert contract["formal_reproduction_level"] == "FAITHFUL_ALGORITHM_REPRODUCTION"
    assert contract["reproduction_qualifier"] == "WITH_DECLARED_UNSPECIFIED_STOCHASTIC_INSTANTIATION"
    assert contract["algorithm"]["ratio_threshold"] == 3.0
    assert contract["algorithm"]["initial_baseline_covariance_m2"] == 900.0
    assert contract["algorithm"]["initial_ambiguity_covariance_cycle2"] == 900.0
    assert contract["algorithm"]["sensitivity_baseline_sigmas_m"] == [0.001, 0.005, 0.010, 0.020, 0.050]
    assert len(requested_variants(contract)) == 10
    assert len(NATIVE_FILE_NAMES) == 15
    assert contract["runtime_topology"]["native_files"] == NATIVE_FILE_NAMES
    assert "signal-audit" in contract["lifecycle_modes"]
    flags = contract["data_flags"]
    assert flags["trace_open_count_before_native_freeze"] == 0
    assert flags["HPPOSECEF_semantic_decode_count_before_native_freeze"] == 0
    assert flags["phase_bias_calibration"] is False
    assert contract["signal_registry"]["GPS_L1"]["rinex_rtklib"] == ["1C"]
    assert contract["signal_registry"]["BDS_B2"]["rinex_rtklib"] == ["7I"]
    assert contract["observation_contract"]["elevation_mask_deg"] == 15.0
    assert contract["observation_contract"]["receiver_initialization"] == "PINNED_RTKLIB_PNTPOS_RAW_CODE_SPP_ONLY"
    assert contract["observation_contract"]["receiver_initialization_options"]["pntpos_relative_humidity"] == 0.7
    assert contract["observation_contract"]["DD_troposphere"]["relative_humidity"] == 0.0
    registry_names = {row["parameter"] for row in phase3.ADAPTER_STOCHASTIC_REGISTRY}
    assert {"number_of_frequencies", "elevation_mask", "minimum_fixes_to_hold", "satellite_clock_stability", "maximum_differential_age", "SPP_Saastamoinen_relative_humidity", "SPP_Saastamoinen_error_sigma"} <= registry_names
    assert "ambiguity_process_noise" not in registry_names  # core registry is authoritative
    assert len(registry_names) == len(phase3.ADAPTER_STOCHASTIC_REGISTRY)
    assert all(row["trace_tuned"] is False for row in phase3.ADAPTER_STOCHASTIC_REGISTRY)


def test_variant_scheduler_parallelizes_variants_not_recursive_epochs():
    variants = requested_variants(load_phase3_contract())
    schedule = deterministic_variant_schedule(variants, DEFAULT_WORKERS)
    assert len(schedule) == 10
    assert sorted(item for slot in schedule for item in slot) == sorted(variants)
    source = inspect.getsource(phase3.run_variant_sequence)
    assert "for index in range(count)" in source
    assert "ProcessPoolExecutor" not in source
    runner_source = inspect.getsource(phase3)
    assert "ProcessPoolExecutor(max_workers=workers)" in runner_source
    assert "ProcessPoolExecutor(max_workers=min(workers" not in runner_source
    with pytest.raises(phase3.Phase3RunnerError):
        deterministic_variant_schedule(variants, MAX_WORKERS + 1)


def test_integer_compatible_reuses_exact_shared_half_cycle_cpstd_and_cpmes_semantics():
    assert integer_compatible(_measurement(0, 1, 0))
    assert not integer_compatible(_measurement(0, 1, 0, cp_std=15))
    assert not integer_compatible(_measurement(0, 1, 0, cp=-0.5))
    assert not integer_compatible(_measurement(0, 1, 0, status=0x03))


def test_signal_mode_gate_requires_same_satellites_across_both_frequencies():
    # Each frequency independently has two satellites, but their SV sets are
    # disjoint.  A single constellation pivot therefore cannot be formed.
    disjoint = [
        _measurement(0, 1, 0), _measurement(0, 2, 0),
        _measurement(0, 3, 3), _measurement(0, 4, 3),
    ]
    result = audit_signal_availability([(_epoch(disjoint), _epoch(disjoint))], _Provider())
    gps = next(item for item in result.mode_support if item.system_mode == "GPS_DUAL_FREQUENCY")
    assert gps.supported is False and gps.eligible_epoch_count == 0


def test_signal_inventory_supports_exact_common_gps_and_reports_exact_codes():
    common = [
        _measurement(0, 1, 0), _measurement(0, 2, 0),
        _measurement(0, 1, 3), _measurement(0, 2, 3),
    ]
    result = audit_signal_availability([(_epoch(common), _epoch(common))], _Provider())
    gps = next(item for item in result.mode_support if item.system_mode == "GPS_DUAL_FREQUENCY")
    assert gps.supported and gps.eligible_epoch_count == 1
    l1 = next(row for row in result.rows if row.receiver == "GNSS1" and row.signal_name == "1C")
    l2 = next(row for row in result.rows if row.receiver == "GNSS1" and row.signal_name == "2L")
    assert (l1.raw_count, l1.common_integer_compatible_count, l1.common_state_available_count) == (2, 2, 2)
    assert l2.rinex_rtklib_mapping == "G:2L"
    assert len(result.epoch_rows) == 2 * 7
    keys = {(row["epoch_index"], row["receiver"], row["gnss_id"], row["sig_id"], row["freq_id"]) for row in result.epoch_rows}
    assert len(keys) == len(result.epoch_rows)


def test_signal_epoch_inventory_conserves_every_pair_receiver_registered_identity():
    common = [_measurement(0, 1, 0), _measurement(0, 2, 0), _measurement(0, 1, 3), _measurement(0, 2, 3)]
    pairs = [(_epoch(common, 100.0 + 0.2*index), _epoch(common, 100.0 + 0.2*index)) for index in range(3)]
    result = audit_signal_availability(pairs, _Provider())
    assert len(result.epoch_rows) == 3 * 2 * 7
    assert {row["epoch_index"] for row in result.epoch_rows} == {0,1,2}
    assert all(row["row_scope"] == "EPOCH" for row in result.epoch_rows)


def test_signal_inventory_rejects_unhealthy_broadcast_state_without_elevation_gate():
    common = [_measurement(0, 1, 0), _measurement(0, 2, 0), _measurement(0, 1, 3), _measurement(0, 2, 3)]
    result = audit_signal_availability([(_epoch(common), _epoch(common))], _UnhealthyProvider())
    gps_rows = [row for row in result.rows if row.signal_group.startswith("GPS_")]
    assert gps_rows and all(row.satellite_state_available_count == 0 for row in gps_rows)
    gps_support = next(row for row in result.mode_support if row.system_mode == "GPS_DUAL_FREQUENCY")
    assert gps_support.supported is False
    assert "EPHEMERIS" in gps_support.terminal_reason


def test_tracking_flags_validity_and_half_state_transitions_but_not_initialization():
    memory, receiver_status = {}, {}
    first = _epoch([_measurement(0, 1, 0, status=0x07)])
    initialized = phase3._tracking_input(first, first, (), SimpleNamespace(ambiguity_identities=()), None, memory, receiver_status)
    assert not initialized.actual_carrier_lli_tracking_discontinuities
    assert not initialized.receiver_locktime_resets
    assert not initialized.half_cycle_state_changes
    assert not initialized.receiver_clock_reset_events
    half = _epoch([_measurement(0, 1, 0, status=0x03, locktime_ms=1100)], tow=100.2)
    half_changed = phase3._tracking_input(half, half, (), SimpleNamespace(ambiguity_identities=()), None, memory, receiver_status)
    assert len(half_changed.half_cycle_state_changes) == 1
    assert not half_changed.actual_carrier_lli_tracking_discontinuities
    carrier = _epoch([_measurement(0, 1, 0, status=0x01, locktime_ms=1200)], tow=100.4)
    carrier_changed = phase3._tracking_input(carrier, carrier, (), SimpleNamespace(ambiguity_identities=()), None, memory, receiver_status)
    assert len(carrier_changed.actual_carrier_lli_tracking_discontinuities) == 1
    assert not carrier_changed.receiver_locktime_resets
    lock = _epoch([_measurement(0, 1, 0, status=0x01, locktime_ms=10)], tow=100.6)
    lock_changed = phase3._tracking_input(lock, lock, (), SimpleNamespace(ambiguity_identities=()), None, memory, receiver_status)
    assert len(lock_changed.receiver_locktime_resets) == 1
    clock = _epoch([_measurement(0, 1, 0, status=0x01, locktime_ms=20)], tow=100.8, receiver_status=0x03)
    clock_changed = phase3._tracking_input(clock, clock, (), SimpleNamespace(ambiguity_identities=()), None, memory, receiver_status)
    assert len(clock_changed.receiver_clock_reset_events) == 1
    assert not clock_changed.actual_carrier_lli_tracking_discontinuities


def test_cycle_event_categories_round_trip_in_phase3_csv(tmp_path):
    path = tmp_path / "slips.csv"
    phase3._write_csv(path, [{"actual_carrier_lli_tracking_event_count": 1, "receiver_locktime_reset_event_count": 2, "half_cycle_state_change_event_count": 3, "receiver_clock_reset_event_count": 4, "method_state_initialization": False, "reasons": [["G01", ["RECEIVER_CLOCK_RESET_EVENT"]]]}])
    row = phase3._read_csv(path)[0]
    assert [int(row[name]) for name in ("actual_carrier_lli_tracking_event_count", "receiver_locktime_reset_event_count", "half_cycle_state_change_event_count", "receiver_clock_reset_event_count")] == [1,2,3,4]
    assert row["method_state_initialization"] == "false"
    assert json.loads(row["reasons"])[0][1] == ["RECEIVER_CLOCK_RESET_EVENT"]


def test_tracking_prior_dd_is_transformed_across_pivot_change():
    old_ids = (
        phase3.AmbiguityIdentity("GPS", "G02", "GPS_L1", "G01"),
        phase3.AmbiguityIdentity("GPS", "G03", "GPS_L1", "G01"),
    )
    target_ids = (
        phase3.AmbiguityIdentity("GPS", "G01", "GPS_L1", "G02"),
        phase3.AmbiguityIdentity("GPS", "G03", "GPS_L1", "G02"),
    )
    previous = SimpleNamespace(ambiguity_identities=old_ids, state=np.asarray([0,0,0,2.0,5.0]))
    empty = _epoch(())
    tracking = phase3._tracking_input(empty, empty, (), SimpleNamespace(ambiguity_identities=target_ids), previous, {}, {})
    assert tracking.estimated_dd_ambiguity_cycles[target_ids[0]] == pytest.approx(-2.0)
    assert tracking.estimated_dd_ambiguity_cycles[target_ids[1]] == pytest.approx(3.0)


def test_native_freeze_revalidates_every_hash_and_row_conservation(tmp_path):
    for key, name in NATIVE_FILE_NAMES.items():
        if key != "native_freeze":
            (tmp_path / name).write_text(f"{key}\n", encoding="utf-8")
    hashes = {key: phase3._sha256(tmp_path / NATIVE_FILE_NAMES[key]) for key in phase3.FREEZE_HASH_KEYS}
    freeze = {
        "schema_version": "horizontal_literature.phase3.native_freeze.v1",
        "native_hashes": hashes,
        "trace_open_count_at_freeze": 0,
        "HPPOSECEF_semantic_decode_count_at_freeze": 0,
        "paired_epoch_count": 3,
        "variant_count": 2,
        "heading_row_count": 6,
    }
    (tmp_path / NATIVE_FILE_NAMES["native_freeze"]).write_text(json.dumps(freeze), encoding="utf-8")
    assert validate_native_freeze(tmp_path)["heading_row_count"] == 6
    (tmp_path / NATIVE_FILE_NAMES["runtime"]).write_text("mutated\n", encoding="utf-8")
    with pytest.raises(phase3.Phase3RunnerError, match="hash mismatch"):
        validate_native_freeze(tmp_path)


def test_failure_ledger_exactly_matches_invalid_heading_stable_keys():
    invalid = {"system_mode":"GPS", "constraint_mode":"CONSTRAINED", "baseline_sigma_m":"0.01", "epoch_index":"7", "gps_week":"2409", "gps_tow_seconds":"100.2", "solution_state":"invalid", "failure_code":"GNSS1_PNTPOS_REJECTED"}
    valid = {**invalid, "epoch_index":"8", "solution_state":"float", "failure_code":""}
    ledger = [{key: invalid[key] for key in ("system_mode","constraint_mode","baseline_sigma_m","epoch_index","gps_week","gps_tow_seconds","failure_code")}]
    phase3._validate_failure_ledger_matches_invalid_headings([invalid,valid], ledger)
    with pytest.raises(phase3.Phase3RunnerError, match="exactly match"):
        phase3._validate_failure_ledger_matches_invalid_headings([invalid,valid], [{**ledger[0], "failure_code":"WRONG"}])


def test_production_uses_shared_pntpos_not_custom_numpy_spp_and_records_receiver_audit():
    source = inspect.getsource(phase3)
    assert "provider.pntpos_rawx_epoch" in source
    assert "def raw_multignss_spp" not in source
    assert "raw_pntpos_receiver_audit" in source
    assert "pntpos_bridge_provenance" in source
    assert "GNSS1_PNTPOS_REJECTED" not in source  # constructed through stable receiver prefix


def test_observation_failure_code_and_registry_applicability_are_explicit():
    error = phase3.Phase3ObservationError("INSUFFICIENT_GPS_DUAL_FREQUENCY_COMMON_SATELLITES", "count=1")
    assert error.code == "INSUFFICIENT_GPS_DUAL_FREQUENCY_COMMON_SATELLITES"
    by_name = {row["parameter"]: row for row in phase3.ADAPTER_STOCHASTIC_REGISTRY}
    assert by_name["phase_measurement_sigma_model"]["primary_or_sensitivity"] == "primary"
    assert by_name["ionosphere_process_noise"]["primary_or_sensitivity"] == "diagnostic"
    assert "INACTIVE_IN_PRODUCTION_ADAPTER" in by_name["minimum_fixes_to_hold"]["source"]
    for name in ("relative_filter_iterations", "ambiguity_resolution_mode", "BDS_ambiguity_resolution", "minimum_lock_to_fix", "minimum_fixes_to_hold", "AR_maximum_iterations"):
        assert by_name[name]["primary_or_sensitivity"] == "diagnostic"
    assert "rtkpos.c:varerr" in by_name["phase_measurement_sigma_model"]["paper_equation_or_RTKLIB_symbol"]
    assert "rtkcmn.c:varerr" not in str(phase3.ADAPTER_STOCHASTIC_REGISTRY)
    assert by_name["position_process_noise"]["primary_or_sensitivity"] == "diagnostic"
    assert by_name["GPS_measurement_error_factor"]["paper_equation_or_RTKLIB_symbol"] == "rtklib.h:EFACT_GPS; rtkpos.c:varerr"
    assert {"pntpos_code_error_factor", "pntpos_pseudorange_variance_formula", "pntpos_minimum_error_elevation", "pntpos_code_bias_error_sigma", "pntpos_broadcast_ionosphere_error_factor", "pntpos_broadcast_ionosphere_variance", "pntpos_Saastamoinen_variance", "pntpos_maximum_iterations", "pntpos_satellite_broadcast_variance", "pntpos_chi_square_validation", "pntpos_maximum_GDOP"} <= set(by_name)


def test_post_trace_gate_and_phase2_recovery_identity_are_exact():
    source = inspect.getsource(phase3._post_native_diagnostics)
    assert "receiver_epoch_field_count_verified\") != 3018" in source
    assert "POST_NATIVE_RECOVERY_PROXY_TIME_ASSOCIATION_R1" in source
    assert "identity_fractional_pairs" in source
    assert "phase2.FRACTIONAL_FIELDS" in source


def test_rtklib_pos_parser_accepts_comma_and_whitespace_and_rejects_bad_rows():
    header = "%  GPST        e-baseline(m) n-baseline(m) u-baseline(m) Q ns sde sdn sdu sden sdnu sdue age ratio\n"
    rows = phase3._parse_rtklib_enu_pos(header + "2409,123.000,0.1,-0.2,0.3,1,12,0.01,0.02,0.03,0,0,0,0.2,1234.5\n2409 123.200 0.2 -0.1 0.4 2 10 0.1 0.1 0.1 0 0 0 0.4 2.9\n")
    assert [row["quality"] for row in rows] == [1, 2]
    assert rows[0]["baseline_enu_m"] == [0.1, -0.2, 0.3]
    assert rows[0]["baseline_ned_m"] == [-0.2, 0.1, -0.3]
    assert rows[0]["age_s"] == 0.2 and rows[0]["ratio"] == 1234.5
    with pytest.raises(phase3.Phase3RunnerError, match="exactly 15"):
        phase3._parse_rtklib_enu_pos("2409,123,0.1\n")
    with pytest.raises(phase3.Phase3RunnerError, match="non-finite"):
        phase3._parse_rtklib_enu_pos("2409,123,0.1,-0.2,0.3,1,12,0.01,0.02,0.03,0,0,0,0.2,nan\n")


def test_rtklib_comparison_associates_plus_2ms_and_converts_enu_to_ned():
    parsed = phase3._parse_rtklib_enu_pos("2409,123.000,2,1,-3,1,12,0.01,0.02,0.03,0,0,0,0.2,1234.5\n")
    native = [
        {"gps_week":"2409","gps_tow_seconds":str(tow),"baseline_ned_m":"[1,2,3]","paper_ratio_fixed":"true","ratio":"4.0"}
        for tow in (122.998,123.198,123.398)
    ]
    comparison = phase3._rtklib_native_comparison(parsed, native)
    assert comparison["time_associated_count"] == 1
    assert comparison["baseline_vector_difference_m"]["mean"] == pytest.approx(0.0)
    assert comparison["fixed_float_overlap"]["FIXED_FIXED"] == 1
    assert comparison["ratio_by_time_association"][0]["rtklib_ratio"] == 1234.5
    assert comparison["ratio_by_time_association"][0]["stock_minus_rawx_seconds"] == pytest.approx(0.002)


def test_rtklib_time_association_handles_missing_epochs_and_rejects_tie_and_reuse():
    native = [{"gps_week":"2409","gps_tow_seconds":str(tow)} for tow in (10.998,11.198,11.398,11.598)]
    stock = [{"gps_week":2409,"gps_tow_seconds":tow} for tow in (11.000,11.400)]
    associated = phase3._associate_rtklib_native_times(stock,native)
    assert [row["association_status"] for row in associated] == ["ASSOCIATED_UNIQUE_NEAREST_SAME_WEEK"]*2
    assert [row["stock_minus_rawx_seconds"] for row in associated] == pytest.approx([0.002,0.002])
    tie_native = [{"gps_week":"2409","gps_tow_seconds":str(tow)} for tow in (20.0,20.2)]
    tie = phase3._associate_rtklib_native_times([{"gps_week":2409,"gps_tow_seconds":20.1}],tie_native)
    assert tie[0]["association_status"] == "REJECTED_MIDPOINT_TIE"
    reuse_stock = [{"gps_week":2409,"gps_tow_seconds":tow} for tow in (19.98,20.02)]
    reuse = phase3._associate_rtklib_native_times(reuse_stock,tie_native)
    assert [row["association_status"] for row in reuse] == ["ASSOCIATED_UNIQUE_NEAREST_SAME_WEEK","REJECTED_NATIVE_REUSE"]


def test_rtklib_recovery_inventory_freezes_primary_post_report_status(tmp_path):
    native_root = tmp_path/"C00"; primary = native_root/"POST_NATIVE"; primary.mkdir(parents=True)
    frozen = {}
    for index in range(11):
        path = primary/f"payload_{index}.dat"; path.write_bytes(f"payload-{index}".encode())
        frozen[path.name] = phase3._sha256(path)
    (primary/"EXT03_C00_POST_NATIVE_FREEZE.json").write_text(json.dumps({"schema_version":"horizontal_literature.phase3.post_native_freeze.v1","files":frozen}),encoding="utf-8")
    report = tmp_path/"PHASE3_EXT03_C00_REPORT.md"; report.write_text("report",encoding="utf-8")
    status = tmp_path/"PHASE3_STATUS.json"; status.write_text("status",encoding="utf-8")
    preflight = SimpleNamespace(paths=SimpleNamespace(native_root=native_root,final_report=report,final_status=status))
    before = phase3._primary_post_recovery_inventory(preflight,expected_file_count=12)
    after = phase3._primary_post_recovery_inventory(preflight,expected_file_count=12)
    assert before == after and before["primary_post_file_count"] == 12
    (primary/"payload_0.dat").write_bytes(b"mutated")
    with pytest.raises(phase3.Phase3RunnerError,match="post-native hash mismatch"):
        phase3._primary_post_recovery_inventory(preflight,expected_file_count=12)
    source = inspect.getsource(phase3._post_native_diagnostics)
    assert 'freeze.get("source_fingerprint"' in source
    assert "supersedes_for_rtklib_time_association_only" in source
    assert "post-native recovery report/status collision" in source
    narrow=inspect.getsource(phase3._post_native_rtklib_time_recovery)
    assert "reconstruct_ubx_stream" not in narrow and "_locked_trace_bytes" not in narrow
    assert "RTKLIB_UNMODIFIED_MOVING_BASE.pos" in narrow


def test_trace_summary_adds_all_valid_denominator_and_invalid_has_no_coverage():
    rows=[]
    for index,(state,window,error,fixed) in enumerate((("float",True,1.0,"false"),("paper_ratio_fixed",True,-2.0,"true"),("float",False,None,"false"),("invalid",True,None,"false"),("invalid",True,None,"false"))):
        rows.append({"system_mode":"GPS_BDS_DUAL_FREQUENCY","constraint_mode":"CONSTRAINED","baseline_sigma_m":"0.01","solution_state":state,"paper_ratio_fixed":fixed,"fixed_window_matched":"true" if window else "false","native_minus_trace_wrapsafe_deg":"" if error is None else str(error),"gps_tow_seconds":str(100+0.2*index)})
    summary=phase3._build_trace_summary_rows(rows)
    all_valid=next(row for row in summary if row["solution_state"]=="ALL_VALID")
    invalid=next(row for row in summary if row["solution_state"]=="invalid")
    assert all_valid["fixed_window_input_count"]==4
    assert all_valid["valid_matched_count"]==2
    assert all_valid["valid_coverage"]==0.5
    assert all_valid["paper_ratio_fixed_matched_count"]==1
    assert all_valid["count"]==2 and all_valid["rmse"]==pytest.approx(np.sqrt(2.5))
    assert invalid["coverage"] is None
    assert invalid["window_timestamp_fraction"]==1.0
    with pytest.raises(phase3.Phase3RunnerError,match="canonical CSV boolean"):
        phase3._build_trace_summary_rows([{**rows[0],"fixed_window_matched":"False"}])
    narrow=inspect.getsource(phase3._post_native_rtklib_time_recovery)
    assert "EXT03_C00_TRACE_SUMMARY_R1.csv" in narrow
    for evidence in ("1370","541","0.3948905109","105","0.0766423358","84.3438","101","40.6308","158.788","129.8"):
        assert evidence in narrow


def test_phase3_csv_boolean_round_trip_preserves_post_classification(tmp_path):
    path = tmp_path / "roundtrip.csv"
    phase3._write_csv(path, [
        {"solution_state": "paper_ratio_fixed", "paper_ratio_fixed": True, "body_yaw_deg": 12.0, "epoch_index": 0},
        {"solution_state": "float", "paper_ratio_fixed": False, "body_yaw_deg": 13.0, "epoch_index": 1},
    ])
    rows = phase3._read_csv(path)
    assert [row["paper_ratio_fixed"] for row in rows] == ["true", "false"]
    proxy_fixed = [row for row in rows if row.get("paper_ratio_fixed") == "true"]
    trace_input = [{**row, "method_native_accepted": "true" if row.get("solution_state") in {"float", "paper_ratio_fixed"} and row.get("body_yaw_deg") else "false"} for row in rows]
    phase_fixed_rate = sum(row.get("paper_ratio_fixed") == "true" for row in rows) / len(rows)
    assert [row["epoch_index"] for row in proxy_fixed] == ["0"]
    assert [row["method_native_accepted"] for row in trace_input] == ["true", "true"]
    assert phase_fixed_rate == 0.5


def test_jsonable_preserves_dataclass_keyed_tracking_memory_as_strict_json():
    identity = phase3.AmbiguityIdentity("GPS", "G02", "GPS_L1", "G01")
    memory = TrackingMemory(
        geometry_free_m={("GPS", "G02"): 0.1},
        melbourne_wubbena_m={("GPS", "G02"): 0.2},
        estimated_dd_ambiguity_cycles={identity: 7.25},
    )
    payload = phase3._jsonable(memory)
    encoded = json.dumps(payload, sort_keys=True, allow_nan=False)
    decoded = json.loads(encoded)
    ambiguity = decoded["estimated_dd_ambiguity_cycles"]
    assert len(ambiguity) == 1
    assert next(iter(ambiguity.values())) == 7.25
    assert '"satellite":"G02"' in next(iter(ambiguity))


def test_runtime_dependency_hash_validation_fails_closed_after_mutation(tmp_path):
    for relative, payload in (("lib/librtklib_legsa.so", b"so"), ("EXT03_PNTPOS_BRIDGE.patch", b"patch"), ("Makefile", b"make")):
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
    expected = phase3._runtime_dependency_hashes(tmp_path)
    phase3._validate_runtime_dependency_hashes(tmp_path, expected)
    (tmp_path / "lib/librtklib_legsa.so").write_bytes(b"mutated")
    with pytest.raises(phase3.Phase3RunnerError, match="changed after preflight"):
        phase3._validate_runtime_dependency_hashes(tmp_path, expected)


def test_worker_failure_evidence_is_timestamped_non_success_and_no_replace(tmp_path, monkeypatch):
    monkeypatch.setattr(phase3.time, "time_ns", lambda: 123456789)
    path = phase3._write_worker_failure_evidence(tmp_path, {"phase": "TEST", "submitted_task_count": 3, "completed_task_count": 1, "failed_task_count": 1, "worker_failure_count": 1})
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["successful_native_claimed"] is False
    assert (payload["submitted_task_count"], payload["completed_task_count"], payload["failed_task_count"]) == (3,1,1)
    with pytest.raises(phase3.Phase3RunnerError, match="collision"):
        phase3._write_worker_failure_evidence(tmp_path, payload)


def _stable_resource_snapshot():
    return {"swap_in_pages":0, "swap_out_pages":0, "swap_used_bytes":0, "cpu_count":16, "load_average_1m_5m_15m":[1.0,1.0,1.0], "ram_available_bytes":8_000_000_000}


def test_resource_probe_workers16_records_zero_failures(tmp_path, monkeypatch):
    raw = tmp_path / "raw.csv"; raw.write_bytes(b"x" * 4096)
    monkeypatch.setattr(phase3.phase2, "_system_resource_snapshot", lambda _root: _stable_resource_snapshot())
    monkeypatch.setattr(phase3.phase2, "_temperature_stability", lambda _before,_after: {"available":True,"stable":True})
    evidence = phase3._resource_probe(SimpleNamespace(stage_root=tmp_path, gnss1_raw=raw), 16)
    assert evidence["worker_failure_count"] == 0
    assert evidence["requested_workers"] == 16
    assert evidence["stable_RAM_swap_CPU_load_IO"] is True


def test_rejected_workers20_probe_is_preserved_after_attempt_identity(tmp_path, monkeypatch):
    raw = tmp_path / "raw.csv"; raw.write_bytes(b"x" * 4096)
    attempt = tmp_path / ".attempt_EXT03_test"; attempt.mkdir()
    (attempt / "ATTEMPT_IDENTITY.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(phase3.phase2, "_system_resource_snapshot", lambda _root: _stable_resource_snapshot())
    monkeypatch.setattr(phase3.phase2, "_temperature_stability", lambda _before,_after: {"available":False,"stable":False})
    with pytest.raises(phase3.ResourceProbeRejected) as caught:
        phase3._resource_probe(SimpleNamespace(stage_root=tmp_path, gnss1_raw=raw), 20)
    monkeypatch.setattr(phase3.time, "time_ns", lambda: 987654321)
    evidence_path = phase3._write_resource_probe_failure_evidence(attempt, caught.value)
    payload = json.loads(evidence_path.read_text(encoding="utf-8"))
    assert (attempt / "ATTEMPT_IDENTITY.json").is_file()
    assert payload["successful_native_claimed"] is False
    assert payload["resource_probe"]["resource_gate_rejected"] is True
    assert payload["resource_probe"]["worker_failure_count"] == 0
    assert payload["resource_probe"]["before"]["ram_available_bytes"] == 8_000_000_000
    source = inspect.getsource(phase3.run_phase3)
    assert source.index("hidden_attempt.mkdir") < source.index("_resource_probe(preflight.paths, workers)")


def test_provenance_labels_base_head_and_hashed_dirty_overlay_without_machine_root():
    source = inspect.getsource(phase3.preflight_phase3)
    assert "BASE_HEAD_ONLY_WITH_HASHED_RUNTIME_SOURCE_OVERLAY" in source
    assert "status_porcelain_sha256" in source
    assert "runtime_dependency_overlay_sha256" in source
    assert '"status_porcelain":' not in source
    assert "REPOSITORY_RELATIVE_PATHS_HASHED_NO_MACHINE_ROOT" in source
    assert "ENUMERATED_RUNTIME_SOURCE_PATHS_ONLY" in source
    first = {"scope": "ENUMERATED_RUNTIME_SOURCE_PATHS_ONLY", "runtime_source_overlay_sha256": "same", "global_worktree_audit_metadata": {"status_porcelain_sha256": "unrelated-a"}}
    second = {**first, "global_worktree_audit_metadata": {"status_porcelain_sha256": "unrelated-b"}}
    assert phase3._scientific_overlay_identity(first) == phase3._scientific_overlay_identity(second)


def test_rtklib_diagnostic_config_is_explicit_and_sensitivity_excludes_unconstrained():
    source = inspect.getsource(phase3._post_native_diagnostics)
    for option in ("pos1-snrmask", "pos1-tidecorr", "pos2-arlockcnt", "pos2-aroutcnt", "pos2-arminfix", "pos2-armaxiter", "pos2-maxage", "pos2-rejionno", "stats-eratio1", "stats-prnaccelh", "stats-prnpos", "ant1-postype", "ant2-postype"):
        assert option in source
    flatten = inspect.getsource(phase3._flatten_native)
    assert 'row["constraint_mode"] == "CONSTRAINED"' in flatten


def test_cli_defaults_to_formal_full_and_exposes_explicit_preflight_signal_audit():
    completed = subprocess.run([sys.executable, str(ROOT / "scripts/paper_rebuild/run_horizontal_literature_phase3.py"), "--help"], text=True, capture_output=True, check=True)
    assert "signal-audit" in completed.stdout
    assert "--workers" in completed.stdout and "--post-recovery-id" in completed.stdout
    source = (ROOT / "scripts/paper_rebuild/run_horizontal_literature_phase3.py").read_text(encoding="utf-8")
    assert 'default="full"' in source
