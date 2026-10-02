"""Pure synthetic arithmetic/schema tests; no native, evaluator or real inputs."""
import copy
import io
import json
import math
from pathlib import Path
import tempfile
import unittest

import analyze_innovation as a


def config():
    return dict(enable_source_aware_weighting=True, policy_version="clean_v1_conservative_innovation_covariance",
                mode="lsim_oim", method_family="clean_v1_conservative_quadratic", deadband=1.5, moderate=2.5, strong=4.0,
                global_cap=25.0, position_cap=5.0, receiver_velocity_cap=8.0, yaw_cap=10.0, raw_doppler_cap=15.0,
                rp_cap=10.0, hv_cap=10.0, reject_extreme=False, no_R_shrink=True, use_innovation_covariance=True,
                sources={s: dict(enabled=True, lsim_enabled=True, oim_enabled=True) for s in a.ALPHA},
                source_aware_go2_readiness_lsim_enabled=False, source_aware_go2_readiness_low_scale=2.0,
                source_aware_go2_impact_or_rough_scale=2.0, source_aware_go2_motion_unknown_scale=1.25,
                source_aware_go2_in_place_turn_scale=1.15, hv_vertical_disabled=True, hv_mode="horizontal_2d")


def metadata(source="go2_horizontal_velocity"):
    return dict(source=source, time=200.0, valid=True, std_xyz=[1.0, 1.0, 999.0], yaw_std_rad=.01,
                time_diff_sec=0.0, sat_count=10, provider_status="available", quality_flag="nominal",
                covariance_available=True, rel_valid=True, ant_valid=True, ant_state="available",
                spike_candidate=False, go2_readiness_metadata_available=False, go2_motion_state="STANCE_STABLE",
                go2_readiness_flag=True, go2_readiness_score=1.0, go2_stance_stable=True,
                go2_in_place_turn=False, go2_impact_or_rough=False, go2_readiness_low=False)


def mat(rows):
    return {"rows": len(rows), "cols": len(rows[0]), "layout": "row_major", "data": [v for row in rows for v in row]}


def event_fixture(dz=(1.0, 2.0), dx=(.1, -.2), source="go2_horizontal_velocity", c=None, md=None, p=None):
    """Make a fully synthetic snapshot; independent hand checks appear below."""
    c, md = c or config(), md or metadata(source)
    p = p or [[2.0, .5], [.5, 3.0]]
    r = [[md["std_xyz"][0] ** 2, 0.0], [0.0, md["std_xyz"][1] ** 2]]
    s = [[p[i][j] + r[i][j] for j in range(2)] for i in range(2)]
    determinant = s[0][0] * s[1][1] - s[0][1] * s[1][0]
    nis = (s[1][1] * dz[0] ** 2 - (s[0][1] + s[1][0]) * dz[0] * dz[1] + s[0][0] * dz[1] ** 2) / determinant
    normalized = math.sqrt(nis / 2)
    old = a.policy(md, c, source, normalized)
    alpha_available = a.enabled(c, source) and c["mode"] in ("lsim_oim", "oim_only") and c["sources"][source]["oim_enabled"] and normalized > c["deadband"]
    snapshot = dict(dz=list(dz), H=mat([[1.0, 0.0], [0.0, 1.0]]), dx_before=list(dx), P_before=mat(p),
                    base_R=mat(r), effective_R=mat(a.scaled(r, old["combined"])), metadata=md,
                    source_enabled=a.enabled(c, source), qm_active_scaling=False,
                    innovation=dict(nis=nis, dof=2, normalized_innovation=normalized, used_innovation_covariance=True,
                                    base_R_trace=r[0][0] + r[1][1], hph_trace=p[0][0] + p[1][1],
                                    innovation_cov_trace=s[0][0] + s[1][1]),
                    result=dict(lsim_R_scale=old["lsim"], oim_R_scale=old["oim"], combined_R_scale=old["combined"],
                                source_cap=c[a.CAP_KEY[source]], accepted=not old["rejected"], rejected=old["rejected"],
                                reason_codes=["SYNTHETIC_FIXTURE"], oim_alpha_available=alpha_available,
                                oim_alpha=a.ALPHA[source] if alpha_available else "NaN",
                                oim_multiplier=old["formula"]["multiplier"] if alpha_available else "NaN",
                                oim_raw_scale=old["formula"]["raw"] if alpha_available else "NaN"))
    event = dict(run_id="SYNTHETIC_FIXTURE", event_seq=4, event="SA_EVALUATION", available_time="UNKNOWN",
                 data=dict(context=dict(source=source, row_id=0, measurement_attempt_seq=1, sa_seq=1), snapshot=snapshot))
    begin = {k: copy.deepcopy(snapshot[k]) for k in a.SNAPSHOT_KEYS}
    return event, c, begin


class ArithmeticTests(unittest.TestCase):
    def row(self, *args, **kwargs):
        event, c, begin = event_fixture(*args, **kwargs)
        before = copy.deepcopy(event)
        row = a.analyze_event(event, c, begin)
        self.assertEqual(event, before, "offline arithmetic must not mutate original snapshot")
        self.assertEqual(row["status"], "VALIDATED_SAME_SNAPSHOT", row)
        self.assertFalse(row["actual_R_mutated"])
        self.assertTrue(row["closedloop_not_tested"])
        return row

    def test_full_offdiagonal_nis_hand_calculation(self):
        row = self.row()
        self.assertAlmostEqual(row["dz_nis_recomputed"], 14 / 11.75)
        self.assertAlmostEqual(row["innovation_nis"], 15.78 / 11.75)
        self.assertEqual(json.loads(row["Hdx_json"]), [.1, -.2])
        self.assertAlmostEqual(json.loads(row["nu_json"])[1], 2.2)

    def test_threshold_exact_and_strict_greater(self):
        c, s = config(), "dual_antenna_yaw"
        self.assertEqual(a.oim(1.5, c, s)["raw"], 1.0)
        self.assertEqual(a.oim(2.5, c, s)["raw"], 1.03)
        self.assertAlmostEqual(a.oim(4.0, c, s)["raw"], 1.225)
        over = a.oim(math.nextafter(4.0, math.inf), c, s)
        self.assertEqual(over["multiplier"], 1.6)
        self.assertAlmostEqual(over["raw"], 1 + .03 * 1.6 * (math.nextafter(4.0, math.inf) - 1.5) ** 2)
        self.assertNotAlmostEqual(over["raw"], 1.6 * (1 + .03 * 2.5 ** 2))

    def test_boundary_ambiguous_and_clear(self):
        near = a.boundary_crossings(2.5, math.nextafter(2.5, math.inf), 2, config())
        self.assertEqual(near[0]["status"], "BOUNDARY_AMBIGUOUS")
        clear = a.boundary_crossings(2.4, 2.6, 2, config())
        self.assertEqual(clear[0]["status"], "CROSSED")

    def test_cap_and_no_shrink(self):
        c = config()
        self.assertEqual(a.oim(1000, c, "raw_doppler_velocity")["capped"], 15)
        c["global_cap"] = 2
        self.assertEqual(a.oim(1000, c, "raw_doppler_velocity")["capped"], 2)
        self.assertEqual(a.cap(-3, c, "raw_doppler_velocity"), 1)

    def test_R_change_uses_scale_tolerance_not_R_units(self):
        tiny = [[1e-12, 0], [0, 1e-12]]
        self.assertTrue(a.scaled_R_changed(tiny, 1.0, 1.001))
        self.assertTrue(a.matrix_scale_matches(a.scaled(tiny, 1.001), tiny, 1.001))
        self.assertFalse(a.matrix_scale_matches(a.scaled(tiny, 1.001), tiny, 1.0))
        self.assertFalse(a.scaled_R_changed([[0.0]], 1.0, 2.0))

    def test_n12_cap_masked(self):
        md = metadata("raw_doppler_velocity"); md["std_xyz"] = [1, 1, 1]
        row = self.row(dz=(1000, 1000), dx=(1, 1), source="raw_doppler_velocity", md=md)
        self.assertTrue(row["nis_changed"])
        self.assertTrue(row["oim_cap_masked"])
        self.assertFalse(row["shadow_final_R_changed"])

    def test_n12_lsim_masked(self):
        row = self.row(dz=(5, 5), dx=(.5, .5))
        self.assertTrue(row["oim_capped_changed"])
        self.assertTrue(row["lsim_masked"])
        self.assertEqual(row["n12_classification"], "OIM_CHANGE_MASKED_BY_LSIM")

    def test_n12_final_r_changes(self):
        md = metadata("dual_antenna_yaw"); md["std_xyz"] = [1, 1, 1]
        row = self.row(dz=(10, 10), dx=(1, 1), source="dual_antenna_yaw", md=md)
        self.assertTrue(row["shadow_final_R_changed"])
        self.assertEqual(row["n12_classification"], "SHADOW_FINAL_R_CHANGED")

    def test_hdx_nonzero_same_nis(self):
        row = self.row(dz=(1, 2), dx=(2, 4))
        self.assertTrue(row["Hdx_nonzero"])
        self.assertFalse(row["nis_changed"])

    def test_sa_off_never_actual_weight_change(self):
        c = config(); c["enable_source_aware_weighting"] = False
        row = self.row(dz=(50, 50), dx=(10, 10), c=c)
        self.assertEqual(row["old_combined"], 1)
        self.assertEqual(row["new_combined"], 1)
        self.assertEqual(row["n12_classification"], "SA_DISABLED_SHADOW_NOT_APPLIED")
        self.assertFalse(row["shadow_final_R_changed"])
        self.assertFalse(row["n16_eligible"])

    def test_source_oim_mask(self):
        c = config(); c["sources"]["go2_horizontal_velocity"]["oim_enabled"] = False
        row = self.row(dz=(20, 20), dx=(1, 1), c=c)
        self.assertEqual(row["n12_classification"], "OIM_MASKED_BY_CONFIGURATION")
        self.assertFalse(row["shadow_final_R_changed"])

    def test_n16_999_2d_shadow_only(self):
        row = self.row()
        self.assertTrue(row["n16_eligible"])
        self.assertEqual(row["n16_old_std_max"], 999)
        self.assertEqual(row["n16_shadow_std_max"], 1)
        self.assertEqual(row["n16_old_lsim"], 2)
        self.assertEqual(row["n16_shadow_lsim"], 1)
        self.assertTrue(row["n16_shadow_final_R_changed"])

    def test_n16_other_lsim_preserved(self):
        md = metadata(); md["time_diff_sec"] = .3
        row = self.row(md=md)
        self.assertEqual(row["n16_old_lsim"], 2.5)
        self.assertEqual(row["n16_shadow_lsim"], 2.5)
        self.assertFalse(row["n16_shadow_final_R_changed"])
        self.assertIn("lsim_time_alignment_suspicious", row["n16_shadow_lsim_components_json"])

    def test_n16_oim_masks_changed_lsim(self):
        row = self.row(dz=(20, 20), dx=(.1, .1))
        self.assertTrue(row["n16_lsim_changed"])
        self.assertFalse(row["n16_shadow_final_R_changed"])
        self.assertEqual(row["n16_classification"], "LSIM_CHANGE_MASKED_BY_OIM_OR_CAP")

    def test_n16_requires_real_2d_r(self):
        event, c, begin = event_fixture()
        event["data"]["snapshot"]["metadata"]["std_xyz"] = [2, 1, 999]
        row = a.analyze_event(event, c, begin)
        self.assertFalse(row["n16_eligible"])
        self.assertIn("TWO_DIMENSIONAL_BASE_R_NOT_ESTABLISHED", row["n16_ineligible_reason"])

    def test_n16_mask_and_std_boundary(self):
        c, md = config(), metadata()
        md["std_xyz"] = [10, 1, 999]
        self.assertEqual(a.lsim(md, c, "go2_horizontal_velocity", True)["scale"], 1)
        md["std_xyz"][0] = math.nextafter(10, math.inf)
        self.assertEqual(a.lsim(md, c, "go2_horizontal_velocity", True)["scale"], 2)
        c["sources"]["go2_horizontal_velocity"]["lsim_enabled"] = False
        row = self.row(c=c)
        self.assertFalse(row["n16_eligible"])

    def test_lsim_time_and_yaw_threshold_endpoints(self):
        c, md = config(), metadata("dual_antenna_yaw")
        md["std_xyz"] = [1, 1, 1]
        for dt, expected in ((.08, 1), (math.nextafter(.08, math.inf), 1.5),
                             (.25, 1.5), (math.nextafter(.25, math.inf), 2.5)):
            md["time_diff_sec"] = dt
            self.assertEqual(a.lsim(md, c, "dual_antenna_yaw")["scale"], expected)
        md["time_diff_sec"] = 0
        for yaw, expected in ((15 * a.D2R, 1), (math.nextafter(15 * a.D2R, math.inf), 2),
                              (30 * a.D2R, 2), (math.nextafter(30 * a.D2R, math.inf), 6)):
            md["yaw_std_rad"] = yaw
            self.assertEqual(a.lsim(md, c, "dual_antenna_yaw")["scale"], expected)

    def test_readiness_lsim_preserved(self):
        c, md = config(), metadata()
        c["source_aware_go2_readiness_lsim_enabled"] = True
        md["go2_readiness_metadata_available"] = True; md["go2_readiness_low"] = True
        row = self.row(c=c, md=md)
        self.assertEqual(row["n16_shadow_lsim"], 2)
        self.assertIn("GO2_READINESS_LOW", row["n16_shadow_lsim_components_json"])

    def test_failed_old_nis_blocks_classification(self):
        event, c, begin = event_fixture()
        event["data"]["snapshot"]["innovation"]["nis"] += 1
        row = a.analyze_event(event, c, begin)
        self.assertEqual(row["status"], "OLD_SNAPSHOT_VALIDATION_FAILED")
        self.assertEqual(row["n12_classification"], "UNCLASSIFIABLE_VALIDATION_FAILED")

    def test_same_snapshot_begin_required(self):
        event, c, begin = event_fixture(); begin["dx_before"][0] += .1
        row = a.analyze_event(event, c, begin)
        self.assertFalse(row["same_snapshot"])
        self.assertEqual(row["status"], "OLD_SNAPSHOT_VALIDATION_FAILED")

    def test_fallback_qm_and_layout_are_unavailable(self):
        for change in ("fallback", "qm", "layout"):
            event, c, begin = event_fixture()
            s = event["data"]["snapshot"]
            if change == "fallback": s["innovation"]["used_innovation_covariance"] = False
            elif change == "qm": s["qm_active_scaling"] = True
            else: s["H"]["layout"] = "column_major"
            self.assertEqual(a.analyze_event(event, c, begin)["status"], "UNAVAILABLE_SNAPSHOT")

    def test_singular_inverse_no_regularization(self):
        with self.assertRaisesRegex(ValueError, "singular"):
            a.inverse([[1, 1], [1, 1]])


class StreamAndGateTests(unittest.TestCase):
    def fixture_stream(self, omit_end=False, wrong_end=False):
        event, c, begin = event_fixture()
        records = [dict(run_id=event["run_id"], event_seq=1, event="OBSERVER_BEGIN", data={"schema": "V3_MECHANISM_OBSERVER_1"}),
                   dict(run_id=event["run_id"], event_seq=2, event="CONFIGURATION", data={"snapshot": c}),
                   dict(run_id=event["run_id"], event_seq=3, event="SA_EVALUATION_BEGIN", data={"context": {"sa_seq": 1}, "snapshot": begin}), event]
        if not omit_end:
            records.append(dict(run_id=event["run_id"], event_seq=5, event="OBSERVER_END", data={"prior_event_count": 3 if wrong_end else 4}))
        return io.BytesIO(b"".join((json.dumps(x) + "\n").encode() for x in records))

    def test_direct_begin_end_schema_and_counts(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as directory:
            summary, examples = a.analyze_stream(self.fixture_stream(), "<SYNTHETIC>/events.jsonl", "SYNTHETIC_FIXTURE", Path(directory))
            self.assertEqual(summary["stream_status"], "COMPLETE")
            self.assertEqual(summary["analysis_status"], "VALIDATED")
            self.assertEqual(a.analysis_exit_code(summary), 0)
            self.assertEqual(summary["event_counts"]["SA_EVALUATION"], 1)
            self.assertEqual(examples[0]["source_line_1based"], 4)
            self.assertEqual(summary["rows"][0]["counts"]["status:VALIDATED_SAME_SNAPSHOT"], 1)

    def test_missing_or_wrong_end_not_complete(self):
        for flags in ({"omit_end": True}, {"wrong_end": True}):
            with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as directory:
                summary, _ = a.analyze_stream(self.fixture_stream(**flags), "<SYNTHETIC>/events.jsonl", "SYNTHETIC_FIXTURE", Path(directory))
                self.assertEqual(summary["stream_status"], "INCOMPLETE_EVENT_STREAM")
                self.assertEqual(summary["analysis_status"], "VALIDATION_FAILED")
                self.assertEqual(a.analysis_exit_code(summary), 2)

    def test_complete_stream_failed_SA_keeps_evidence_and_fails_analysis(self):
        records = [json.loads(row) for row in self.fixture_stream().getvalue().splitlines()]
        records[3]["data"]["snapshot"]["innovation"]["nis"] += 1.0
        stream = io.BytesIO(b"".join((json.dumps(x) + "\n").encode() for x in records))
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as directory:
            summary, examples = a.analyze_stream(stream, "<SYNTHETIC>/events.jsonl", "SYNTHETIC_FIXTURE", Path(directory))
            self.assertEqual(summary["stream_status"], "COMPLETE")
            self.assertEqual(summary["analysis_status"], "VALIDATION_FAILED")
            self.assertEqual(summary["failed_SA_events"], 1)
            self.assertEqual(summary["unavailable_SA_events"], 0)
            self.assertEqual(a.analysis_exit_code(summary), 2)
            self.assertEqual(len(examples), 1)
            self.assertIn("OLD_SNAPSHOT_VALIDATION_FAILED", (Path(directory) / "SA_EVENT_ANALYSIS.csv").read_text())
            self.assertTrue((Path(directory) / "KEY_SNAPSHOTS.jsonl").stat().st_size > 0)

    def test_complete_stream_no_SA_not_validated(self):
        records = [json.loads(row) for row in self.fixture_stream().getvalue().splitlines()]
        records = records[:2] + [dict(run_id="SYNTHETIC_FIXTURE", event_seq=3, event="OBSERVER_END", data={"prior_event_count": 2})]
        stream = io.BytesIO(b"".join((json.dumps(x) + "\n").encode() for x in records))
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as directory:
            summary, _ = a.analyze_stream(stream, "<SYNTHETIC>/events.jsonl", "SYNTHETIC_FIXTURE", Path(directory))
            self.assertEqual(summary["stream_status"], "COMPLETE")
            self.assertEqual(summary["analysis_status"], "NO_SA_EVENTS")
            self.assertFalse(summary["all_SA_events_validated"])
            self.assertEqual(a.analysis_exit_code(summary), 2)

    def test_history_access_and_manifest_gates(self):
        receipt = dict(slot_id="R__original", status="COMPLETED_BYTE_IDENTICAL", access_passed=True,
                       scientific_manifest_match=True, native_exec_count="1", exit_code=0,
                       output_comparisons=[dict(status="BYTE_IDENTICAL") for _ in range(5)], history_identity_status="BYTE_IDENTICAL")
        access = dict(passed=True, native_exec_count=1)
        self.assertTrue(all(a.check_replay_identity(receipt, access, "R", "original").values()))
        for key in ("status", "access_passed", "scientific_manifest_match", "history_identity_status"):
            invalid = dict(receipt); invalid[key] = False
            with self.assertRaisesRegex(ValueError, "REPLAY_IDENTITY_NOT_ESTABLISHED"):
                a.check_replay_identity(invalid, access, "R", "original")


if __name__ == "__main__":
    unittest.main(verbosity=2)
