#!/usr/bin/env python3
"""Pure synthetic arithmetic/parser checks; never launches a native process."""
import argparse
import copy
import json
from pathlib import Path
import unittest

import analyze_events as a
import numpy as np

OUTPUT = None


def mat(value):
    n = np.asarray(value, dtype=float)
    return dict(rows=n.shape[0], cols=n.shape[1], layout="row_major", data=n.ravel().tolist())


def state(t=200.0, shift=0.0):
    return dict(time=t, position_blh_rad_m=[0.5, 1.2, 3.0], velocity_ned_mps=[shift, 0.0, 0.0],
                rpy_rad=[0.0, 0.0, 0.0], Cbn=np.eye(3).tolist(), qbn_wxyz=[1.0, 0.0, 0.0, 0.0],
                gyr_bias=[0.0]*3, acc_bias=[0.0]*3, gyr_scale=[0.0]*3, acc_scale=[0.0]*3, antlever_m=[0.0]*3)


def sa_snapshot(candidate="BASELINE", bad_nis=False, off=False, dx_value=0.5):
    h = np.zeros((1, 21)); h[0, 0] = 1
    dx = np.zeros(21); dx[0] = dx_value
    dz = [2.0]
    nu = 2.0 - dx_value
    actual = nu if candidate == "N12_ONLY" else 2.0
    nis = actual * actual / 2
    innovation = dict(nis=nis + int(bad_nis), dof=1, normalized_innovation=abs(actual)/np.sqrt(2),
                      used_innovation_covariance=True, residual_norm=abs(actual), base_R_trace=1.0,
                      hph_trace=1.0, innovation_cov_trace=2.0)
    if candidate != "BASELINE":
        innovation["residual_vector"] = [actual]
    return dict(dz=dz, H=mat(h), dx_before=dx.tolist(), P_before=mat(np.eye(21)), base_R=mat([[1.0]]),
                effective_R=mat([[1.0 if off else 2.0]]), source_enabled=not off, qm_active_scaling=False,
                metadata=dict(source="go2_attitude_roll_pitch", std_xyz=[0.1, 0.2, 999.0]), innovation=innovation,
                result=dict(combined_R_scale=1.0 if off else 2.0, lsim_R_scale=1.5, oim_R_scale=2.0,
                            source_cap=10.0, accepted=True, rejected=False))


def events(candidate="BASELINE", *, accepted=True, with_measurement=True, shift=0.0,
           bad_nis=False, extra_event=False, split=False, t=200.0):
    raw = []
    context = dict(imu_seq=1, gnss_input_seq=1, measurement_attempt_seq=1, sa_seq=1, ekf_seq=1,
                   source="go2_attitude_roll_pitch", row_id=0, measurement_time=t, gnss_time=t,
                   imu_previous_time=t-0.01, imu_current_time=t, state_time=t, res=3 if split else 2,
                   **{k: 0 for k in a.COUNTERS})
    def add(kind, snap):
        raw.append(dict(event_seq=len(raw)+1, run_id="SYNTHETIC", event=kind, available_time="UNKNOWN",
                        data=copy.deepcopy(snap) if kind.startswith("OBSERVER_") else dict(context=copy.deepcopy(context), snapshot=copy.deepcopy(snap))))
    add("OBSERVER_BEGIN", dict(schema="V3_MECHANISM_OBSERVER_1"))
    add("CONFIGURATION", dict(use_innovation_covariance=True))
    if candidate != "BASELINE":
        add("CANDIDATE_DEFINITION", dict(candidate_id=candidate))
    selected = dict(source_status="active", std_roll_rad=0.1, std_pitch_rad=0.2)
    add("GNSS_INPUT", dict(effective=dict(time=t, has_position=False, has_velocity=False, has_yaw=False),
                           auxiliary_candidates=dict(go2_roll_pitch=dict(config_enabled=True, solver_enabled=True, match_found=True, selected_input=selected))))
    add("IMU_OPPORTUNITY", dict(initialized=True, res=context["res"]))
    if extra_event:
        add("RP_ONLY_INPUT", dict(gnss_event_time=t, preinnovation_qualified=True))
    if split:
        add("IMU_SPLIT_AFTER", {})
        add("PROPAGATION_AFTER", dict(state=state(t-0.005)))
    if with_measurement:
        s = sa_snapshot(candidate, bad_nis=bad_nis)
        add("MEASUREMENT_ATTEMPT", dict(state=state(t)))
        add("SA_EVALUATION_BEGIN", {k: s[k] for k in a.SNAPSHOT_FIELDS})
        add("SA_EVALUATION", s)
        if accepted:
            add("EKF_BEFORE", dict(dz=s["dz"], H=s["H"], dx_before=s["dx_before"], P_before=s["P_before"], R=s["effective_R"], state=state(t)))
            delta = [0.5] + [0.0]*20
            add("EKF_AFTER", dict(actual_innovation=[1.5], actual_Hdx=[0.5], actual_delta=delta,
                                  actual_S=mat([[3.0]]), dx_after=[1.0]+[0.0]*20, P_after=mat(np.eye(21)), state=state(t)))
            context["rp_update_count"] = 1
        add("MEASUREMENT_DECISION", dict(accepted=accepted, reason="ACCEPTED" if accepted else "SOURCE_AWARE_REJECT"))
        add("FEEDBACK_AFTER", dict(state=state(t, shift), dx=[0.0]*21))
    add("PROPAGATION_AFTER", dict(state=state(t, shift)))
    if candidate != "BASELINE":
        add("COVARIANCE_HEALTH", a.covariance_health(np.eye(21)))
    add("OBSERVER_END", dict(prior_event_count=len(raw)))
    return raw


class Checks(unittest.TestCase):
    def setUp(self):
        self.root = OUTPUT / self.id().split(".")[-1]
        self.root.mkdir(parents=True, exist_ok=False)

    def scan(self, data, label="stream", candidate="BASELINE"):
        path = self.root / (label + ".jsonl")
        path.write_text("".join(a.js(x)+"\n" for x in data))
        out = self.root / (label + "_cache")
        result = a.scan_stream(path, out, source_alias="<SYNTHETIC>/"+label+".jsonl", run_id="SYNTHETIC", candidate_id=candidate,
                               group="SYNTHETIC", identity={"synthetic_fixture_only": True})
        return path, out, result

    def test_covariance_scaled_spd_unmodified(self):
        p = np.array([[1e-16, 0.2], [0.2, 1e16]])
        before = p.copy(); r = a.covariance_health(p)
        self.assertEqual(r["status"], a.GOOD_P); np.testing.assert_array_equal(p, before)

    def test_covariance_nonfinite_offdiagonal(self):
        p = np.eye(3); p[0, 1] = np.nan
        self.assertEqual(a.covariance_health(p)["status"], "NONFINITE_MATRIX")

    def test_covariance_nonpositive_diagonal(self):
        self.assertEqual(a.covariance_health(np.diag([1.0, 0.0]))["status"], "NONPOSITIVE_DIAGONAL")

    def test_covariance_asymmetry_boundary(self):
        p = np.eye(2); p[0, 1] = 1e-10
        self.assertTrue(a.covariance_health(p)["symmetric_within_tolerance"])
        p[0, 1] = np.nextafter(1e-10, np.inf)
        self.assertEqual(a.covariance_health(p)["status"], "ASYMMETRIC")

    def test_covariance_rank_deficiency(self):
        self.assertEqual(a.covariance_health(np.ones((2, 2)))["status"], "NEAR_SINGULAR_NUMERICALLY_UNRESOLVED")

    def test_covariance_negative_pivot(self):
        self.assertEqual(a.covariance_health(np.array([[1, 2], [2, 1]]))["status"], "CHOLESKY_NEGATIVE_PIVOT_RISK")

    def test_raw_and_conditional_nis(self):
        for candidate in ["BASELINE", "N12_ONLY", "N16_ONLY", "N09_RP_ONLY"]:
            s = sa_snapshot(candidate); r = a.analyze_sa(s, s, candidate, {"use_innovation_covariance": True})
            self.assertEqual(r["validation_status"], "VALIDATED")
            self.assertEqual(r["raw_nis"], 2.0); self.assertEqual(r["conditional_nis"], 1.125)

    def test_sa_off_not_actual_weight_change(self):
        s = sa_snapshot(off=True)
        r = a.analyze_sa(s, s, "BASELINE", {"use_innovation_covariance": True})
        self.assertEqual(r["validation_status"], "VALIDATED"); self.assertFalse(r["source_enabled"])

    def test_same_snapshot_gate(self):
        s = sa_snapshot(); begin = copy.deepcopy(s); begin["dx_before"][0] = 1.0
        self.assertEqual(a.analyze_sa(s, begin, "BASELINE", {"use_innovation_covariance": True})["validation_status"], "VALIDATION_FAILED")

    def test_conditional_zero(self):
        s = sa_snapshot("N12_ONLY", dx_value=2.0)
        self.assertEqual(a.analyze_sa(s, s, "N12_ONLY", {"use_innovation_covariance": True})["conditional_nis"], 0.0)

    def test_fallback(self):
        s = sa_snapshot("N12_ONLY")
        s["innovation"].update(used_innovation_covariance=False)
        self.assertEqual(a.analyze_sa(s, s, "N12_ONLY", {"use_innovation_covariance": False})["validation_status"], "VALIDATED")

    def test_window_endpoints(self):
        self.assertIn("FIXED_196_2_216_2_HALF_OPEN", a.time_windows(196.2))
        self.assertNotIn("FIXED_196_2_216_2_HALF_OPEN", a.time_windows(216.2))
        self.assertIn("FULL_RUN_66_340_CLOSED", a.time_windows(340.0))

    def test_good_stream_and_no_double_SA_count(self):
        _, _, r = self.scan(events("N16_ONLY"), candidate="N16_ONLY")
        self.assertEqual(r["analysis_status"], "VALIDATED")
        self.assertEqual(r["sa_validation_counts"], {"VALIDATED": 1})
        self.assertEqual(r["covariance"]["ALL_IMU_END_CANDIDATE"]["count"], 1)

    def test_baseline_only_EKF_covariance(self):
        _, _, r = self.scan(events())
        self.assertEqual(r["covariance"]["EKF_SNAPSHOT_BASELINE_ONLY"]["count"], 2)
        self.assertNotIn("ALL_IMU_END_CANDIDATE", r["covariance"])

    def test_complete_stream_failed_analysis(self):
        _, _, r = self.scan(events(bad_nis=True))
        self.assertEqual(r["stream_status"], "COMPLETE")
        self.assertEqual(r["analysis_status"], "VALIDATION_FAILED")

    def test_sequence_gap(self):
        data = events(); data[3]["event_seq"] += 1
        _, _, r = self.scan(data); self.assertEqual(r["stream_status"], "INCOMPLETE_OR_INVALID")

    def test_footer_missing(self):
        _, _, r = self.scan(events()[:-1]); self.assertEqual(r["stream_status"], "INCOMPLETE_OR_INVALID")

    def test_footer_prior_count(self):
        data = events(); data[-1]["data"]["prior_event_count"] -= 1
        _, _, r = self.scan(data); self.assertEqual(r["stream_status"], "INCOMPLETE_OR_INVALID")

    def test_extra_after_footer(self):
        data = events(); data.append(copy.deepcopy(data[-1]))
        _, _, r = self.scan(data); self.assertEqual(r["stream_status"], "INCOMPLETE_OR_INVALID")

    def test_cache_reuse_zero_payload_open(self):
        path, out, r = self.scan(events())
        again = a.scan_stream(path, out, source_alias="<SYNTHETIC>/stream.jsonl", run_id="SYNTHETIC")
        self.assertTrue(again["cache_reused"]); self.assertEqual(again["event_payload_opens_this_call"], 0)

    def test_changed_stat_refuses_rescan(self):
        path, out, _ = self.scan(events()); path.write_text(path.read_text()+" ")
        with self.assertRaisesRegex(ValueError, "CACHE_IDENTITY_OR_STAT_CHANGED"):
            a.scan_stream(path, out, source_alias="<SYNTHETIC>/stream.jsonl", run_id="SYNTHETIC")

    def test_partial_cache_refuses_rescan(self):
        path, out, _ = self.scan(events()[:-1])
        with self.assertRaisesRegex(ValueError, "NO_AUTOMATIC_RESCAN"):
            a.scan_stream(path, out, source_alias="<SYNTHETIC>/stream.jsonl", run_id="SYNTHETIC")

    def test_stable_match_despite_extra_event(self):
        _, b, _ = self.scan(events(), "base")
        _, c, _ = self.scan(events("N16_ONLY", extra_event=True), "candidate", "N16_ONLY")
        r = a.compare_caches(c, b, self.root/"comparison")
        self.assertEqual(r["measurement_counts"]["PAIRED"], 1)
        self.assertEqual(r["common_IMU_counts"]["EXACTLY_EQUAL"], 1)

    def test_added_RP_no_fabricated_baseline(self):
        _, b, _ = self.scan(events(with_measurement=False), "base")
        _, c, _ = self.scan(events("N09_RP_ONLY", shift=0.1, extra_event=True, split=True), "candidate", "N09_RP_ONLY")
        r = a.compare_caches(c, b, self.root/"comparison")
        added = r["first_differences"]["FIRST_ADDED_ACCEPTED_UPDATE"]
        self.assertIsNone(added["baseline"])
        self.assertEqual(r["measurement_counts"]["ADDED_CANDIDATE_MEASUREMENT"], 1)
        self.assertIn("FIRST_COMMON_IMU_DIFFERENCE_AFTER_ADDED_UPDATE", r["first_differences"])
        d = r["first_differences"]["FIRST_COMMON_IMU_AFTER_ADDED_ACCEPTED_UPDATE"]
        self.assertEqual(d["propagation_counts"], {"candidate": 2, "baseline": 1})
        q = [x for x in r["original_RP_opportunities"] if x["window"] == "FIXED_196_2_216_2_HALF_OPEN" and x["measure"] == "candidate_actual_accepted_GNSS_inputs"]
        self.assertEqual(q[0]["count"], 1)

    def test_policy_accepted_but_no_EKF_not_actual_acceptance(self):
        _, _, r = self.scan(events(accepted=False))
        self.assertEqual(r["analysis_status"], "VALIDATED")
        self.assertEqual(r["final_actual_counters"]["rp_update_count"], 0)

    def test_original_RP_gate_inf_matches_cpp(self):
        s = dict(auxiliary_candidates=dict(go2_roll_pitch=dict(config_enabled=True, solver_enabled=True, match_found=True,
                    selected_input=dict(source_status="active", std_roll_rad="Infinity", std_pitch_rad=0.1))))
        self.assertTrue(a.rp_qualification(s))
        s["auxiliary_candidates"]["go2_roll_pitch"]["selected_input"]["std_roll_rad"] = "NaN"
        self.assertFalse(a.rp_qualification(s))

    def test_R_scale_zero_entry_and_threshold(self):
        self.assertTrue(a.scaled_matrix_matches(np.array([[2., 0.], [0., 4.]]), np.diag([1., 2.]), 2.))
        self.assertFalse(a.scaled_matrix_matches(np.array([[2., 1e-50], [0., 4.]]), np.diag([1., 2.]), 2.))

    def test_state_Cbn_nested_array(self):
        d = a.state_diff(state(), state())
        self.assertTrue(all(x["status"] == "EXACTLY_EQUAL" for x in d.values()))

    def test_added_rejected_RP_still_reports_split_state(self):
        _, b, _ = self.scan(events(with_measurement=False), "base")
        _, c, _ = self.scan(events("N09_RP_ONLY", accepted=False, shift=1e-12, split=True), "candidate", "N09_RP_ONLY")
        r = a.compare_caches(c, b, self.root/"comparison")
        self.assertNotIn("FIRST_ADDED_ACCEPTED_UPDATE", r["first_differences"])
        self.assertIn("FIRST_COMMON_IMU_DIFFERENCE_AFTER_ADDED_ATTEMPT", r["first_differences"])

    def test_actual_counter_disagreement(self):
        data = events()
        for e in data:
            if not e["event"].startswith("OBSERVER_"):
                e["data"]["context"]["rp_update_count"] = 0
        _, _, r = self.scan(data)
        self.assertEqual(r["analysis_status"], "VALIDATION_FAILED")
        self.assertIn("ACTUAL_UPDATE_COUNTER_MISMATCH", [x["kind"] for x in r["diagnostic_anomalies"]])

    def test_candidate_identity_mismatch(self):
        _, _, r = self.scan(events("N12_ONLY"), candidate="N16_ONLY")
        self.assertEqual(r["stream_status"], "INCOMPLETE_OR_INVALID")

    def test_candidate_missing_health(self):
        data = [x for x in events("N16_ONLY") if x["event"] != "COVARIANCE_HEALTH"]
        for i, x in enumerate(data, 1): x["event_seq"] = i
        data[-1]["data"]["prior_event_count"] = len(data)-1
        _, _, r = self.scan(data, candidate="N16_ONLY")
        self.assertEqual(r["analysis_status"], "VALIDATION_FAILED")

    def test_duplicate_stable_key_remains_unresolved(self):
        data = events()
        selected = [copy.deepcopy(x) for x in data if x["event"] in ("MEASUREMENT_ATTEMPT", "SA_EVALUATION_BEGIN", "SA_EVALUATION", "EKF_BEFORE", "EKF_AFTER", "MEASUREMENT_DECISION")]
        for e in selected:
            e["data"]["context"]["measurement_attempt_seq"] = 2
            e["data"]["context"]["rp_update_count"] += 1
        data[-1:-1] = selected
        for i, x in enumerate(data, 1): x["event_seq"] = i
        data[-1]["data"]["prior_event_count"] = len(data)-1
        _, _, r = self.scan(data)
        self.assertEqual(r["stream_status"], "COMPLETE")
        self.assertEqual(r["analysis_status"], "VALIDATION_FAILED")
        self.assertIn("AMBIGUOUS_STABLE_MEASUREMENT_KEYS", [x["kind"] for x in r["diagnostic_anomalies"]])

    def test_bad_matrix_shape(self):
        s = sa_snapshot(); s["H"]["data"].pop()
        self.assertEqual(a.analyze_sa(s, s, "BASELINE", {"use_innovation_covariance": True})["validation_status"], "UNAVAILABLE")

    def test_frozen_inverse_cutoff(self):
        with self.assertRaisesRegex(ValueError, "SINGULAR"):
            a.inverse_frozen(np.array([[np.nextafter(1e-15, 0.0)]]))
        self.assertAlmostEqual(a.inverse_frozen(np.array([[1e-15]]))[0, 0]/1e15, 1.0)

    def test_baseline_gate_exact_integer_and_string_counts(self):
        receipt = dict(slot_id="RUN_TEST__observed", status="COMPLETED_BYTE_IDENTICAL", access_passed=True,
            scientific_manifest_match=True, exit_code=0, observer_identity_status="BYTE_IDENTICAL",
            output_comparisons=[dict(status="BYTE_IDENTICAL") for _ in range(5)])
        access = dict(passed=True, native_exec_count=1)
        for value in [1, "1", True, False, 1.0, "UNKNOWN", "01", " 1", 0, 2, None]:
            receipt["native_exec_count"] = value
            a.write_json(self.root/"REPLAY_RECEIPT.json", receipt); a.write_json(self.root/"ACCESS_REVIEW.json", access)
            if type(value) in (int, str) and value in (1, "1"):
                self.assertTrue(all(a.baseline_gate(self.root, "RUN_TEST")["checks"].values()))
            else:
                with self.assertRaisesRegex(ValueError, "BASELINE_GATE"):
                    a.baseline_gate(self.root, "RUN_TEST")
        receipt["native_exec_count"] = "1"; access["native_exec_count"] = True
        a.write_json(self.root/"REPLAY_RECEIPT.json", receipt); a.write_json(self.root/"ACCESS_REVIEW.json", access)
        with self.assertRaisesRegex(ValueError, "BASELINE_GATE"):
            a.baseline_gate(self.root, "RUN_TEST")

    def test_candidate_gate_exact_integer_and_string_counts(self):
        item = dict(slot_id="N16_ONLY__RUN_TEST", original_config_sha256="a"*64)
        receipt = dict(slot_id=item["slot_id"], status="COMPLETED", access_passed=True, exit_code=0,
            config_sha256=item["original_config_sha256"], output_hashes=[dict(candidate_sha256="b"*64) for _ in range(5)])
        access = dict(passed=True, native_exec_count=1)
        for value in [1, "1", True, False, 1.0, "UNKNOWN", "01", " 1", 0, 2, None]:
            receipt["native_exec_count"] = value
            a.write_json(self.root/"CANDIDATE_RECEIPT.json", receipt); a.write_json(self.root/"ACCESS_REVIEW.json", access)
            if type(value) in (int, str) and value in (1, "1"):
                self.assertTrue(all(a.candidate_gate(self.root, item)["checks"].values()))
            else:
                with self.assertRaisesRegex(ValueError, "CANDIDATE_GATE"):
                    a.candidate_gate(self.root, item)
        receipt["native_exec_count"] = "1"; access["native_exec_count"] = "UNKNOWN"
        a.write_json(self.root/"CANDIDATE_RECEIPT.json", receipt); a.write_json(self.root/"ACCESS_REVIEW.json", access)
        with self.assertRaisesRegex(ValueError, "CANDIDATE_GATE"):
            a.candidate_gate(self.root, item)

    def test_early_failure_records_partial_hash_not_complete_scan(self):
        data = events(); data[2]["event_seq"] = 99
        _, _, r = self.scan(data)
        self.assertFalse(r["physical_eof_reached"]); self.assertFalse(r["complete_valid_stream"])
        self.assertEqual(r["payload_open_attempts_this_call"], 1)
        self.assertEqual(r["complete_payload_scan_count"], 0); self.assertIsNone(r["source_sha256"])
        self.assertEqual(r["hash_scope"], "PARTIAL_OR_UNSTABLE_READ_BYTES_ONLY")
        self.assertEqual(len(r["bytes_read_sha256"]), 64)

    def test_full_physical_read_without_footer_has_full_hash(self):
        _, _, r = self.scan(events()[:-1])
        self.assertTrue(r["physical_eof_reached"]); self.assertFalse(r["complete_valid_stream"])
        self.assertEqual(r["complete_payload_scan_count"], 1)
        self.assertEqual(r["hash_scope"], "FULL_STABLE_FILE")
        self.assertEqual(len(r["source_sha256"]), 64)

    def test_cache_requires_current_schema_and_analyzer(self):
        _, out, r = self.scan(events())
        for field, wrong in [("schema", "OLD_CACHE_SCHEMA"), ("analyzer_sha256", "0"*64)]:
            bad = dict(r); bad[field] = wrong; a.write_json(out/"SCAN_RECEIPT.json", bad)
            with self.assertRaisesRegex(ValueError, "CACHE_SCHEMA_OR_ANALYZER_PIN"):
                a.read_cache(out)
        a.write_json(out/"SCAN_RECEIPT.json", r)

    def test_cache_requires_registered_object_and_sides(self):
        _, b, _ = self.scan(events(), "base")
        _, c, _ = self.scan(events("N16_ONLY"), "candidate", "N16_ONLY")
        with self.assertRaisesRegex(ValueError, "CACHE_REGISTERED_OBJECT_IDENTITY"):
            a.compare_caches(c, b, self.root/"bad_identity", expected_candidate={"source_path": "<SYNTHETIC>/wrong.jsonl"})
        with self.assertRaisesRegex(ValueError, "CACHE_COMPARISON_SIDE_IDENTITY"):
            a.compare_caches(b, c, self.root/"wrong_sides")
        self.assertFalse((self.root/"bad_identity").exists())


def main():
    global OUTPUT
    p = argparse.ArgumentParser(); p.add_argument("--output", required=True, type=Path)
    args = p.parse_args(); OUTPUT = args.output
    OUTPUT.mkdir(parents=True, exist_ok=False)
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Checks))
    a.write_json(OUTPUT/"TEST_RECEIPT.json", dict(data_mode="synthetic_fixture_only", tests=result.testsRun,
        failures=[dict(test=str(t), traceback=v) for t, v in result.failures],
        errors=[dict(test=str(t), traceback=v) for t, v in result.errors],
        passed=result.testsRun-len(result.failures)-len(result.errors), new_native_calls=0, evaluator_calls=0,
        real_event_payload_reads=0, analyzer_sha256=a.sha(Path(a.__file__)), test_source_sha256=a.sha(Path(__file__))))
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
