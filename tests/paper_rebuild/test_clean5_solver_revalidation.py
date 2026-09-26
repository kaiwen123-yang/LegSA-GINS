"""C-04b synthetic validation and literal frozen-v1 parser regression fixtures.

Live files are not read by tests. The two native-string fixtures below were
copied from the authorized v1 RUN_MANIFEST/config outputs, never from raw data.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest
import yaml

from legsa_gins.paper_rebuild.clean5_sequence import profile_expectations as expectations
from legsa_gins.paper_rebuild.clean5_sequence import solver_validation as validation
from legsa_gins.paper_rebuild.clean5_sequence.runtime_config import METHODS
from legsa_gins.paper_rebuild.manifest import sha256_file
from test_clean5_solver_runner import native_counters, native_manifest, synthetic_config


FROZEN_V1_NATIVE_STRINGS = {'BY2H': {'source_config_sha256': '9be7ab15093a40e38c3e9412ad94015316cd81acccf29a14895ed3ab24dc05e0',
          'source_manifest_sha256': 'e346ece2d3c26d4adf9f07653fbc68c1dddc314db7905e7adcd5db29e9ff91ec',
          'yaml_lines': 'raw_doppler_backend_source_files: '
                        '["BY2_BY3/2026-03-06/fixption数据/2026.3.6/by3/vrtk2_a87c6e_2026-03-06-08-06-39_minimal/gnss1-raw.csv", '
                        '"BY2_BY3/2026-03-06/fixption数据/2026.3.6/by3/vrtk2_a87c6e_2026-03-06-08-06-39_minimal/gnss1-status.csv"]\n'
                        'raw_doppler_backend_source_hashes: '
                        '{"BY2_BY3/2026-03-06/fixption数据/2026.3.6/by3/vrtk2_a87c6e_2026-03-06-08-06-39_minimal/gnss1-raw.csv": '
                        '"b6e0e3108b0902350eb7655fe1a2db23a8f320136ddc6c54bcd7e5dbe2d17508", '
                        '"BY2_BY3/2026-03-06/fixption数据/2026.3.6/by3/vrtk2_a87c6e_2026-03-06-08-06-39_minimal/gnss1-status.csv": '
                        '"6e169474adea70ef9899ef02409015f7cd225aadf1efbe63e51af2a39e297ef2"}\n',
          'native_values': {'raw_doppler_backend_source_files': 'BY2_BY3/2026-03-06/fixption数据/2026.3.6/by3/vrtk2_a87c6e_2026-03-06-08-06-39_minimal/gnss1-raw.csv"  '
                                                                '"BY2_BY3/2026-03-06/fixption数据/2026.3.6/by3/vrtk2_a87c6e_2026-03-06-08-06-39_minimal/gnss1-status.csv',
                            'raw_doppler_backend_source_hashes': '{"BY2_BY3/2026-03-06/fixption数据/2026.3.6/by3/vrtk2_a87c6e_2026-03-06-08-06-39_minimal/gnss1-raw.csv": '
                                                                 '"b6e0e3108b0902350eb7655fe1a2db23a8f320136ddc6c54bcd7e5dbe2d17508"  '
                                                                 '"BY2_BY3/2026-03-06/fixption数据/2026.3.6/by3/vrtk2_a87c6e_2026-03-06-08-06-39_minimal/gnss1-status.csv": '
                                                                 '"6e169474adea70ef9899ef02409015f7cd225aadf1efbe63e51af2a39e297ef2"}'},
          'actual_module_counters': {'position_update_count': 270,
                                     'receiver_velocity_update_count': 270,
                                     'dual_yaw_attempt_count': 270,
                                     'dual_yaw_accepted_count': 265,
                                     'yaw_NORMAL': 114,
                                     'yaw_DOWNWEIGHT': 151,
                                     'yaw_REJECT': 5,
                                     'raw_doppler_update_count': 177,
                                     'source_aware_evaluation_count': 1522,
                                     'source_aware_weight_changed_count': 1328,
                                     'go2_roll_pitch_update_count': 270,
                                     'go2_horizontal_velocity_update_count': 270,
                                     'selected_fgo_feedback_update_count': 0,
                                     'nine_factor_fgo_update_count': 0,
                                     'multi_state_qm_update_count': 0,
                                     'qa_fallback_count': 0,
                                     'contact_fk_update_count': 0}},
 'BY2O': {'source_config_sha256': '00ad2d0f74d0af6ee49d82f8329fce5d85df83a055366c98c2f760d0ae860ca5',
          'source_manifest_sha256': 'e03757349d91454914f785efd342ed25f2a8104a5a277769706eb912f8ea999a',
          'yaml_lines': 'raw_doppler_backend_source_files: '
                        '["BY2_BY3/2026-03-06/fixption数据/2026.3.6/by1/vrtk2_a87c6e_2026-03-06-07-52-22_minimal/gnss1-raw.csv", '
                        '"BY2_BY3/2026-03-06/fixption数据/2026.3.6/by1/vrtk2_a87c6e_2026-03-06-07-52-22_minimal/gnss1-status.csv"]\n'
                        'raw_doppler_backend_source_hashes: '
                        '{"BY2_BY3/2026-03-06/fixption数据/2026.3.6/by1/vrtk2_a87c6e_2026-03-06-07-52-22_minimal/gnss1-raw.csv": '
                        '"6035d50419eaa0ff29d9a4b053dbed5d715fd2bec38f44ad4b4be02ca54a4ba9", '
                        '"BY2_BY3/2026-03-06/fixption数据/2026.3.6/by1/vrtk2_a87c6e_2026-03-06-07-52-22_minimal/gnss1-status.csv": '
                        '"c3958ba9442c1a84b25c3be6ab649cc3aad2e5976c3f525127a2136d9b72255f"}\n',
          'native_values': {'raw_doppler_backend_source_files': 'BY2_BY3/2026-03-06/fixption数据/2026.3.6/by1/vrtk2_a87c6e_2026-03-06-07-52-22_minimal/gnss1-raw.csv"  '
                                                                '"BY2_BY3/2026-03-06/fixption数据/2026.3.6/by1/vrtk2_a87c6e_2026-03-06-07-52-22_minimal/gnss1-status.csv',
                            'raw_doppler_backend_source_hashes': '{"BY2_BY3/2026-03-06/fixption数据/2026.3.6/by1/vrtk2_a87c6e_2026-03-06-07-52-22_minimal/gnss1-raw.csv": '
                                                                 '"6035d50419eaa0ff29d9a4b053dbed5d715fd2bec38f44ad4b4be02ca54a4ba9"  '
                                                                 '"BY2_BY3/2026-03-06/fixption数据/2026.3.6/by1/vrtk2_a87c6e_2026-03-06-07-52-22_minimal/gnss1-status.csv": '
                                                                 '"c3958ba9442c1a84b25c3be6ab649cc3aad2e5976c3f525127a2136d9b72255f"}'}}}


@pytest.mark.parametrize("dataset", ["BY2H", "BY2O"])
def test_real_native_collection_strings_follow_loader_not_json(dataset):
    fixture = FROZEN_V1_NATIVE_STRINGS[dataset]
    config = synthetic_config("AB1111")
    config.update(yaml.safe_load(fixture["yaml_lines"]))
    raw = "\n".join(key + ": " + json.dumps(value, ensure_ascii=False) for key, value in config.items()) + "\n"
    manifest = native_manifest(config)
    manifest.update(fixture["native_values"])
    for key, actual in fixture["native_values"].items():
        assert validation.native_loader_string(raw, key) == actual
        with pytest.raises(json.JSONDecodeError):
            json.loads(actual)
    assert validation.validate_clean5_manifest(manifest, raw, {"identity": {"dataset_id": dataset}})["passed"]
    manifest["raw_doppler_backend_source_hashes"] += " "
    with pytest.raises(validation.SolverValidationError, match="provenance mismatch"):
        validation.validate_clean5_manifest(manifest, raw, {"identity": {"dataset_id": dataset}})


def test_native_loader_exact_quotes_whitespace_comment_and_delimiter_rules():
    text = 'k: ["a", "b"] # native comment\n'
    assert validation.native_loader_string(text, "k") == 'a"  "b'
    assert validation.native_loader_string("k = ' a,b ' # tail", "k") == " a b "
    assert validation.native_loader_string('k: "a#b"', "k") == '"a'
    # readKeyValues uses '=' before ':' exactly as the native loader does.
    with pytest.raises(validation.SolverValidationError, match="line missing"):
        validation.native_loader_string('k: "a=b"', "k")


@pytest.fixture
def epoch_inputs(tmp_path):
    times = [0.5, 1.0, 1.5, 2.0, 3.0, 4.0, 4.5]
    path = tmp_path / "synthetic_gnss15.txt"
    path.write_text("".join(str(time) + " 0" * 14 + "\n" for time in times))
    imu_path = tmp_path / "synthetic_imu7.txt"
    imu_path.write_text("".join(str(time) + " 0" * 6 + "\n" for time in (1.5, 2.0, 3.0, 5.0)))
    config = {"starttime": 1.0, "endtime": 4.0, "gnsspath": str(path), "imupath": str(imu_path)}
    audit = {"first_imu_time": 1.5, "last_imu_time": 5.0, "imu_row_count": 4,
        "first_gnss_time": 0.5, "last_gnss_time": 4.5, "gnss_row_count": len(times),
        "config_starttime": 1.0, "config_endtime": 4.0,
        "effective_starttime": 1.5, "effective_endtime": 4.0,
        "overlap_start": 1.5, "overlap_end": 4.0,
        "gnss_rows_in_overlap": 3, "gnss_rows_after_start_before_end": 3,
        "trace_solver_input": False, "final_v23_output_solver_input": False,
        "paper_performance_claim": False}
    return config, audit, path


def test_expected_epochs_uses_first_aligned_imu_and_inclusive_config_end(epoch_inputs):
    result = validation.expected_update_epochs(*epoch_inputs)
    assert result["configured_window_rows"] == 5
    assert result["t_init"] == 1.5
    assert result["next_imu_time"] == 2.0
    assert result["expected_update_count"] == 3
    assert result["skipped_epoch_times"] == [1.0, 1.5]
    assert result["eligible_epoch_times"] == [2.0, 3.0, 4.0]
    assert result["effective_starttime_source"] == "PORT_INPUT_TIMELINE_SNAPSHOT.json.effective_starttime"
    assert all(row["reason"] == "precedes_first_aligned_imu_sample" for row in result["skipped_epochs"])
    assert result["causative_imu_gap"] is None
    assert not result["expected_count_derived_from_actual_counters"]
    assert not result["expected_count_derived_from_NAV"]


@pytest.mark.parametrize("key,value", [("effective_starttime", 2.0), ("first_imu_time", 2.0),
    ("config_endtime", 5.0), ("effective_endtime", 3.0), ("gnss_row_count", 6),
    ("gnss_rows_in_overlap", 4), ("trace_solver_input", True)])
def test_expected_epochs_refuses_inconsistent_audit(epoch_inputs, key, value):
    config, audit, path = epoch_inputs
    audit[key] = value
    with pytest.raises(validation.SolverValidationError):
        validation.expected_update_epochs(config, audit, path)


def test_expected_epochs_refuses_nonfinite_or_non15_provider(epoch_inputs):
    config, audit, path = epoch_inputs
    path.write_text("1.5 " + "0 " * 13 + "nan\n")
    with pytest.raises(validation.AlgorithmFailure):
        validation.expected_update_epochs(config, audit, path)
    path.write_text("1.5 " + "0 " * 13 + "\n")
    with pytest.raises(validation.SolverValidationError):
        validation.expected_update_epochs(config, audit, path)


def test_by2h_actual_native_counters_still_reject_superseded_272_epoch_gate():
    manifest = FROZEN_V1_NATIVE_STRINGS["BY2H"]["actual_module_counters"]
    assert manifest["position_update_count"] == 270
    with pytest.raises(validation.CounterMismatch) as failure:
        validation.validate_profile_counters("AB1111", manifest, 272)
    assert failure.value.counters["position_update_count"] == 270
    assert "position_update_count != 272" in str(failure.value)


@pytest.mark.parametrize("method,pattern", [("F01", "11000000"), ("F02", "10100000"),
    ("F03", "11100000"), ("A04", "11110011"), ("F04", "11111111")])
def test_feature_patterns_derived_from_existing_registries(method, pattern):
    flags = expectations.profile_flags(METHODS[method])
    assert "".join("1" if flags[key] else "0" for key in expectations.C00_METRIC_FLAGS.values()) == pattern


def test_canonical_pattern_assertion_hash_and_feature_mismatch(tmp_path, monkeypatch):
    source = tmp_path / "synthetic_module_patterns.csv"
    fields = ["method_id", "case_family", "metric_name", "count", "finite_count", "non_null_count",
              "mean", "min", "max", "worst_case_id"]
    rows = []
    for method, profile in METHODS.items():
        flags = expectations.profile_flags(profile)
        for metric, flag in expectations.C00_METRIC_FLAGS.items():
            value = 3.0 if flags[flag] else 0.0
            rows.append({"method_id": method, "case_family": "clean", "metric_name": metric,
                "count": 1, "finite_count": 1, "non_null_count": 1,
                "mean": value, "min": value, "max": value, "worst_case_id": "C00_clean_normal"})
    def write():
        with source.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)
    write()
    with pytest.raises(ValueError, match="SHA256"):
        expectations.verify_canonical_patterns(source)
    monkeypatch.setattr(expectations, "C00_MODULE_ACTION_SHA256", sha256_file(source))
    assert expectations.verify_canonical_patterns(source)["patterns"]["F02"] == "10100000"
    rows[0].update(mean=0.0, min=0.0, max=0.0)
    write()
    monkeypatch.setattr(expectations, "C00_MODULE_ACTION_SHA256", sha256_file(source))
    with pytest.raises(ValueError, match="pattern mismatch"):
        expectations.verify_canonical_patterns(source)


def test_by2h_copied_boundary_timestamps_select_t_init_independently(tmp_path):
    # Only boundary timestamps copied from the frozen BY2H providers; the small
    # zero-filled payloads and remaining GNSS grid are explicitly synthetic.
    imu_times = [394.945055, 407.017058, 413.041069, 413.047045, 692.919118]
    gnss_times = [411.211805, 412.203816, 413.203355] + [float(t) + 0.2 for t in range(414, 683)]
    imu = tmp_path / "synthetic_boundary_imu7.txt"
    gnss = tmp_path / "synthetic_boundary_gnss15.txt"
    imu.write_text("".join(str(t) + " 0" * 6 + "\n" for t in imu_times))
    gnss.write_text("".join(str(t) + " 0" * 14 + "\n" for t in gnss_times))
    config = {"starttime": 411.0, "endtime": 683.0, "imupath": str(imu), "gnsspath": str(gnss)}
    audit = {"first_imu_time": imu_times[0], "last_imu_time": imu_times[-1], "imu_row_count": len(imu_times),
        "first_gnss_time": gnss_times[0], "last_gnss_time": gnss_times[-1], "gnss_row_count": len(gnss_times),
        "config_starttime": 411.0, "config_endtime": 683.0, "effective_starttime": 411.0,
        "effective_endtime": gnss_times[-1], "overlap_start": 411.0, "overlap_end": gnss_times[-1],
        "gnss_rows_in_overlap": 272, "gnss_rows_after_start_before_end": 272,
        "trace_solver_input": False, "final_v23_output_solver_input": False, "paper_performance_claim": False}
    result = validation.expected_update_epochs(config, audit, gnss)
    assert result["native_effective_starttime"] == 411.0
    assert result["t_init"] == 413.041069
    assert result["expected_update_count"] == 270
    assert result["configured_window_rows"] == 272
    assert result["skipped_epoch_times"] == [411.211805, 412.203816]
    gap = result["causative_imu_gap"]
    assert (gap["start_s"], gap["end_s"]) == (407.017058, 413.041069)
    assert gap["duration_seconds"] == pytest.approx(6.024011)
    assert validation.validate_profile_counters("AB1111",
        FROZEN_V1_NATIVE_STRINGS["BY2H"]["actual_module_counters"], result["expected_update_count"])
    assert validation.validate_nav_alignment(413.047045, result)["passed"]


def test_aligned_native_field_if_present_must_match_provider(epoch_inputs):
    config, audit, path = epoch_inputs
    audit["first_aligned_imu_time"] = 1.5
    assert validation.expected_update_epochs(config, audit, path)["native_aligned_imu_fields"] == {"first_aligned_imu_time": 1.5}
    audit["first_aligned_imu_time"] = 2.0
    with pytest.raises(validation.SolverValidationError, match="aligned IMU field"):
        validation.expected_update_epochs(config, audit, path)


@pytest.mark.parametrize("times", [(1.5, 1.5, 3.0, 5.0), (1.5, 2.0, float("nan"), 5.0)])
def test_imu_increment_times_must_be_finite_strictly_increasing(epoch_inputs, times):
    config, audit, path = epoch_inputs
    Path(config["imupath"]).write_text("".join(str(t) + " 0" * 6 + "\n" for t in times))
    with pytest.raises(validation.SolverValidationError):
        validation.expected_update_epochs(config, audit, path)


def test_initialization_requires_a_following_imu_increment(epoch_inputs):
    config, audit, path = epoch_inputs
    config["starttime"] = audit["config_starttime"] = audit["effective_starttime"] = audit["overlap_start"] = 3.9
    config["endtime"] = audit["config_endtime"] = 6.0
    audit["effective_endtime"] = audit["overlap_end"] = 4.5
    with pytest.raises(validation.SolverValidationError, match="following increment"):
        validation.expected_update_epochs(config, audit, path)


@pytest.mark.parametrize("first_nav,accepted", [(2.0, True), (2.25, True), (2.5, True), (2.500001, False), (1.5, False)])
def test_nav_first_matches_next_input_imu_with_one_interval_max(epoch_inputs, first_nav, accepted):
    result = validation.expected_update_epochs(*epoch_inputs)
    if accepted:
        proof = validation.validate_nav_alignment(first_nav, result)
        assert proof["passed"] and proof["tolerance_seconds"] == 0.5
    else:
        with pytest.raises(validation.SolverValidationError, match="NAV first time"):
            validation.validate_nav_alignment(first_nav, result)


def test_normal_alignment_bracket_does_not_invent_an_imu_hole(tmp_path):
    imu = tmp_path / "synthetic_imu7.txt"
    gnss = tmp_path / "synthetic_gnss15.txt"
    imu_times = [0.998, 1.003, 1.008, 2.003]
    gnss_times = [1.0, 1.5, 2.0]
    imu.write_text("".join(str(t) + " 0" * 6 + "\n" for t in imu_times))
    gnss.write_text("".join(str(t) + " 0" * 14 + "\n" for t in gnss_times))
    config = {"starttime": 1.0, "endtime": 2.0, "imupath": str(imu), "gnsspath": str(gnss)}
    audit = {"first_imu_time": 0.998, "last_imu_time": 2.003, "imu_row_count": 4,
        "first_gnss_time": 1.0, "last_gnss_time": 2.0, "gnss_row_count": 3,
        "config_starttime": 1.0, "config_endtime": 2.0, "effective_starttime": 1.0,
        "effective_endtime": 2.0, "overlap_start": 1.0, "overlap_end": 2.0,
        "gnss_rows_in_overlap": 2, "gnss_rows_after_start_before_end": 2,
        "trace_solver_input": False, "final_v23_output_solver_input": False, "paper_performance_claim": False}
    result = validation.expected_update_epochs(config, audit, gnss)
    assert result["t_init"] == 1.003
    assert result["skipped_epoch_times"] == [1.0]
    assert result["initialization_bracketing_interval"]["duration_seconds"] == pytest.approx(0.005)
    assert result["causative_imu_gap"] is None
    assert result["skipped_epochs"][0]["note"] == "initialization boundary exclusion; no IMU hole identified"
