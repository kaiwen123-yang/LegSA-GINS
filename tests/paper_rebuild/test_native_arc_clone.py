"""Eight registered synthetic production ARC integration cases; never real data.

24 harness processes are planned (cap 32), plus the frozen old 16 tests' 28.
Finite-difference probes run inside one synthetic process and touch GIEngine
stateFeedback, not a copy of its retraction. No test claims calibrated truth.
"""
import csv
import hashlib
import json
import os
import struct
import subprocess
import time
from pathlib import Path

import numpy as np
from scipy.spatial.transform import Rotation

STAGE = Path(os.environ["NATIVE_ARC_TEST_STAGE"])
BIN = STAGE / "native_arc_clone_harness"
LOG = STAGE / "ARC_HARNESS_INVOCATIONS.jsonl"
MAX_CALLS = 32
FIELDS = (
    "schema_version sequence_id block_id endpoint_id role source_time_s "
    "source_time_bits_hex replay_execution_time_s actual_available_time_s "
    "availability_mode epoch_index endpoint_model_fingerprint"
).split()


def call(op, *, path=None, fail=False, telemetry=1):
    # Root runs one pytest worker. Persist PENDING before spawn: interruption,
    # timeout or nonzero status still consumes one of the fixed process budget.
    records = [json.loads(x) for x in LOG.read_text().splitlines()] if LOG.exists() else []
    assert len(records) < MAX_CALLS, "ARC harness process budget exhausted BEFORE spawn"
    path = Path(path) if path is not None else STAGE / ("arc_diag_" + op)
    command = [str(BIN), op, str(path)]
    payload = ""
    file_identity = None
    if path.is_file():
        data = path.read_bytes()
        file_identity = dict(path=str(path), bytes=len(data), sha256=hashlib.sha256(data).hexdigest())
    row = dict(
        ordinal=len(records) + 1, op=op, command=command, input=payload,
        input_sha256=hashlib.sha256(payload.encode()).hexdigest(),
        synthetic_file=file_identity, binary_sha256=hashlib.sha256(BIN.read_bytes()).hexdigest(),
        telemetry=telemetry, started_unix_s=time.time(), status="PENDING",
        returncode=None, stdout="", stderr="", timeout_s=30,
    )
    records.append(row)

    def persist():
        # Atomic replacement keeps exactly one row per launch including failures.
        temporary = LOG.with_suffix(".jsonl.tmp")
        temporary.write_text("".join(json.dumps(r, sort_keys=True) + "\n" for r in records))
        temporary.replace(LOG)

    persist()
    env = dict(os.environ, LEGSA_ARC_NATIVE_TELEMETRY=str(telemetry))
    try:
        proc = subprocess.run(command, input=payload, text=True, capture_output=True,
                              timeout=30, env=env)
        row.update(status="COMPLETED", returncode=proc.returncode,
                   stdout=proc.stdout, stderr=proc.stderr)
    except subprocess.TimeoutExpired as exc:
        def decoded(x): return x.decode(errors="replace") if isinstance(x, bytes) else (x or "")
        row.update(status="TIMEOUT", stdout=decoded(exc.stdout), stderr=decoded(exc.stderr))
        raise
    except BaseException as exc:
        row.update(status="LAUNCH_OR_INTERRUPTION_ERROR", stderr=repr(exc))
        raise
    finally:
        row["ended_unix_s"] = time.time()
        persist()
    if fail:
        assert proc.returncode != 0, proc.stdout
        return proc.stderr
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)


def a(o, key):
    return np.asarray(o[key], dtype=float)


def bits(t):
    return struct.pack(">d", t).hex()


def rows():
    return [dict(
        schema_version="1", sequence_id="SYNTHETIC", block_id="B0",
        endpoint_id="B0_" + role, role=role, source_time_s=format(t, ".17g"),
        source_time_bits_hex=bits(t), replay_execution_time_s=format(t, ".17g"),
        actual_available_time_s="", availability_mode="SOURCE_TIME_REPLAY_ASSUMPTION",
        epoch_index=str(index), endpoint_model_fingerprint="",
    ) for role, t, index in (("START", 1.123456789012345, 0), ("END", 1.923456741328716, 4))]


def csvfile(path, values):
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(values)


def no_measurements(o):
    assert o["phase_updates"] == o["foot_updates"] == o["foot_attempts"] == 0


def dri(q):
    # Independent WGS84 metric for finite-difference reset oracle.
    eccentricity2, major = 0.0066943799901413156, 6378137.
    t = 1 - eccentricity2 * np.sin(q[0]) ** 2
    rn = major / np.sqrt(t)
    rm = major * (1 - eccentricity2) / t ** 1.5
    return np.diag([1 / (rm + q[2]), 1 / ((rn + q[2]) * np.cos(q[0])), -1.])


def test_01_strict_csv_config_and_off(tmp_path):
    p = tmp_path / "synthetic_arc.csv"
    original = rows()
    csvfile(p, original)
    o = call("read", path=p)
    assert o["rows"] == 2 and o["all_actual_NA_and_bits_match"]
    assert o["times"] == [float(r["source_time_s"]) for r in original]
    corruptions = (
        ("schema_version", "2", "SCHEMA_OR_COLUMN_COUNT"),
        ("source_time_bits_hex", "0000000000000000", "EXACT_TIME_ORDER_OR_BITS"),
        ("actual_available_time_s", "1.5", "ACTUAL_AVAILABLE_FIELD_MUST_BE_EMPTY"),
        ("replay_execution_time_s", "1.1", "EXACT_TIME_ORDER_OR_BITS"),
    )
    for key, value, reason in corruptions:
        bad = [dict(r) for r in original]
        bad[0][key] = value
        csvfile(p, bad)
        assert reason in call("read", path=p, fail=True)
    assert "EXPLICIT_TIME_MAPPING_REQUIRED" in call("bad_time_scale", fail=True)
    assert "EXPLICIT_INPUT_PINS_REQUIRED" in call("bad_manifest", fail=True)
    o = call("off", path=tmp_path / "off")
    assert o["default_off"] and o["off_read_rejected"] and o["legacy_equal"]
    assert o["P_shape"] == 21 and not (tmp_path / "off").exists()
    # SHA fields are declarations here. Only the future external frozen runner
    # can establish content-hash identity; the native parser does not hash files.


def test_02_two_blocks_and_empty_model_keep_denominator():
    o = call("lifecycle")
    assert (o["source_rows"], o["source_blocks"], o["event_rows"]) == (4, 2, 4)
    assert o["covered"] == o["starts"] == o["ends"] == o["retires"] == 2
    assert not o["active"] and len(o["P"]) == 21
    no_measurements(o)
    assert all(o[x] == 0 for x in ("GNSS", "RP", "HV", "RD", "SA"))
    assert len(o["priors"]) == len(o["lifecycle"]) == 2
    endpoint_ids = []
    for k, row in enumerate(o["lifecycle"]):
        assert row["status"] == "COVERED_END_PRIOR" and row["owner"] == "ARC"
        assert row["clone_created"] and row["end_time"] - row["start_time"] < .800000000000001
        assert row["start_state_time"] == row["start_time"]
        assert row["end_state_time"] == row["end_time"]
        assert row["start_actual_available"] is row["end_actual_available"] is None
        assert row["start_dispatch"] < row["end_dispatch"]
        endpoint_ids.extend([row["start_id"], row["end_id"]])
        assert bool(row["start_model"]) == bool(row["end_model"]) == (k == 0)
    assert len(set(endpoint_ids)) == 4
    np.testing.assert_array_equal(o["P"], a(o["priors"][-1], "P24")[:21, :21])


def test_03_actual_propagation_split_conserves_measured_increments():
    o = call("split")
    segments = o["segments"]
    assert len(segments) == 3
    assert [s["start"] for s in segments] == [1., 1.123456789012345, 1.923456741328716]
    assert [s["end"] for s in segments] == [1.123456789012345, 1.923456741328716, 2.]
    for field, input_field in (("dt", "input_dt"), ("dtheta", "input_dtheta"), ("dvel", "input_dvel")):
        np.testing.assert_allclose(np.sum([s[field] for s in segments], axis=0),
                                   o[input_field], atol=2e-15, rtol=2e-15)
    assert not any(s["compensated"] for s in segments)
    row = o["lifecycle"][0]
    assert row["start_state_time"] == 1.123456789012345
    assert row["end_state_time"] == 1.923456741328716
    assert row["start_state_time"] != round(row["start_state_time"], 6)
    no_measurements(o)
    assert all(o[x] == 0 for x in ("GNSS", "RP", "HV", "RD", "SA"))


def test_04_production_gnss_aux_hv_before_arc_at_exact_time():
    for op, endpoint_times in (("ordering_mid", (1.15, 1.95)), ("ordering_end", (1.2, 2.))):
        o = call(op)
        assert o["covered"] == 1 and o["samples"] == 3
        assert o["GNSS"] == o["RP"] == o["HV"] == 3
        no_measurements(o)
        ledger = o["conditioning"]
        assert [r["ordinal"] for r in ledger] == list(range(1, len(ledger) + 1))
        for t, kind in zip(endpoint_times, ("ARC_START", "ARC_END")):
            same = [r for r in ledger if r["time"] == t]
            arc = [r for r in same if r["kind"] == kind]
            assert len(arc) == 1
            updates = [r for r in same if r["kind"] == "ORDINARY_UPDATE"]
            tags = {r["tag"] for r in updates}
            assert {"GNSS_POSITION_SOURCE_AWARE", "RECEIVER_VELOCITY", "GO2_ATTITUDE_RP"} <= tags
            if op == "ordering_end":
                assert "BODY_HORIZONTAL_VELOCITY" in tags
            else:
                assert "BODY_HORIZONTAL_VELOCITY" not in tags
            assert max(r["ordinal"] for r in updates) < arc[0]["ordinal"]
            resets = [r for r in same if r["kind"] == "FULL_RESET"]
            assert resets and max(r["ordinal"] for r in updates) < resets[-1]["ordinal"] < arc[0]["ordinal"]
        prior = o["priors"][0]
        np.testing.assert_array_equal(prior["dx24"], np.zeros(24))
        assert prior["start_update"] < prior["end_update"]
        assert prior["start_reset"] < prior["end_reset"]
        assert np.linalg.norm(a(prior, "clone_C0") - a(prior, "start_C0")) > 1e-8
        if op == "ordering_end":
            np.testing.assert_array_equal(o["P"], a(prior, "P24")[:21, :21])
        life = o["lifecycle"][0]
        assert life["start_dispatch_phase"] == life["end_dispatch_phase"] == "POST_ALL_EXISTING_UPDATES_AT_TIMESTAMP"


def test_05_production_joint_update_reset_and_endpoint_mapping_FD():
    o = call("mapping")
    p, m, h21, r, z = (a(o, k) for k in ("before_update_P", "before_update_mean", "H21", "R", "z"))
    h = np.c_[h21, np.zeros((3, 3))]
    gain = np.linalg.solve(h @ p @ h.T + r, h @ p).T
    expected_mean = m + gain @ (z - h @ m)
    b = np.eye(24) - gain @ h
    expected_cov = b @ p @ b.T + gain @ r @ gain.T
    np.testing.assert_allclose(o["after_update_mean"], expected_mean, atol=2e-15)
    np.testing.assert_allclose(o["after_update_P"], expected_cov, atol=3e-15)
    assert np.linalg.norm(a(o, "after_update_mean")[21:] - m[21:]) > 1e-6
    assert np.linalg.norm(a(o, "after_update_P")[:21, 21:] - p[:21, 21:]) > 1e-6

    correction = a(o, "after_update_mean")
    gp = np.linalg.solve(dri(a(o, "after_feedback_blh")), dri(a(o, "before_feedback_blh")))

    def reset_perturbation(delta):
        result = delta.copy()
        result[:3] = gp @ delta[:3]
        for k in (6, 21):
            result[k:k+3] = (
                Rotation.from_rotvec(correction[k:k+3] + delta[k:k+3])
                * Rotation.from_rotvec(-correction[k:k+3])
            ).as_rotvec()
        return result

    eps = 1e-7
    reset = np.column_stack([(reset_perturbation(eps*u) - reset_perturbation(-eps*u))/(2*eps)
                             for u in np.eye(24)])
    np.testing.assert_allclose(o["after_feedback_P"], reset @ expected_cov @ reset.T,
                               atol=1e-10, rtol=1e-8)
    np.testing.assert_array_equal(o["after_feedback_mean"], np.zeros(24))
    prior = o["priors"][0]
    derivatives = []
    for plus, minus in (("clone_plus", "clone_minus"), ("current_plus", "current_minus")):
        derivatives.append(np.column_stack([
            Rotation.from_matrix(cp @ cm.T).as_rotvec() / (2 * step)
            for cp, cm, step in zip(a(o, plus), a(o, minus), o["fd_steps"])
        ]))
    finite_difference = np.vstack(derivatives)
    np.testing.assert_allclose(prior["B6"], finite_difference, atol=1.5e-9, rtol=2e-6)
    # Resolve the much smaller moving-NED connection separately.
    np.testing.assert_allclose(a(prior, "B6")[3:, :3], finite_difference[3:, :3],
                               atol=3e-14, rtol=2e-6)
    assert np.linalg.norm(finite_difference[3:, :3]) > 1e-8
    bp, pp = a(prior, "B6"), a(prior, "P24")
    np.testing.assert_allclose(prior["P6"], bp @ pp @ bp.T, atol=3e-16)
    np.testing.assert_allclose(prior["P6"], finite_difference @ pp @ finite_difference.T,
                               atol=1e-10, rtol=1e-8)
    naive = bp.copy()
    naive[3:, :3] = 0
    assert np.linalg.norm(bp @ pp @ bp.T - naive @ pp @ naive.T) > 1e-14
    assert np.linalg.eigvalsh(a(prior, "P6")).min() > -1e-13
    np.testing.assert_array_equal(o["P"], pp[:21, :21])
    no_measurements(o)


def test_06_null_and_telemetry_scientific_outputs_byte_identical(tmp_path):
    paths = [tmp_path / "NULL", tmp_path / "TELEMETRY"]
    outputs = [call("identity", path=p, telemetry=k) for k, p in enumerate(paths)]
    assert outputs[0] == outputs[1]
    # A dedicated production PVT-priority fixture emits genuine heading rows;
    # configured-policy mode would create no heading event file.
    heading_rows = list(csv.DictReader((paths[0] / "HEADING_SOURCE_EVENTS.csv").open()))
    assert len(heading_rows) == 3
    assert all(r["pvt_present"] == r["pvt_attempted"] == "1" for r in heading_rows)
    assert any(r["accepted"] == "1" for r in heading_rows)
    common = {"KF_GINS_Navresult.nav", "KF_GINS_STD.txt", "KF_GINS_IMU_ERR.txt",
              "ARC_LIFECYCLE.csv", "ARC_CONDITIONING_EVENTS.jsonl", "ARC_IMU_SEGMENTS.csv",
              "HEADING_SOURCE_EVENTS.csv", "BODY_VELOCITY_EVENTS.csv"}
    files = [{p.name for p in directory.iterdir() if p.is_file()} for directory in paths]
    assert common <= files[0] and common <= files[1]
    assert files[1] - files[0] == {"ARC_JOINT_PRIORS.jsonl"} and not files[0] - files[1]
    for name in files[0] - {"RUN_MANIFEST.json"}:
        assert (paths[0] / name).read_bytes() == (paths[1] / name).read_bytes(), name
    manifests = [json.loads((p / "RUN_MANIFEST.json").read_text()) for p in paths]
    assert manifests[0].pop("arc_native_telemetry_enabled") is False
    assert manifests[1].pop("arc_native_telemetry_enabled") is True
    assert manifests[0] == manifests[1]
    assert manifests[0]["arc_actual_available_time"] is None
    assert manifests[0]["arc_phase_state_cross"] == "UNKNOWN"
    assert manifests[0]["arc_phase_updates"] == manifests[0]["arc_foot_pair_updates"] == 0
    priors = [json.loads(x) for x in (paths[1] / "ARC_JOINT_PRIORS.jsonl").read_text().splitlines()]
    assert len(priors) == 1
    p = priors[0]
    assert p["actual_available_time_s"] is None and p["phase_state_cross"] == "UNKNOWN"
    assert p["pin_validation"] == "DECLARED_PINS_EXTERNAL_RUNNER_VERIFICATION_REQUIRED"
    assert p["prior_scope"] == "INHERITED_WORKING_MODEL_CONDITIONAL_ON_EXECUTED_PREFIX_NOT_CALIBRATED_TRUTH"
    np.testing.assert_array_equal(p["P6"], outputs[1]["priors"][0]["P6"])


def test_07_uncovered_initial_terminal_missing_and_malformed():
    for op in ("initial", "terminal", "missing_end"):
        o = call(op)
        assert o["source_blocks"] == 1 and o["covered"] == 0
        assert o["uncovered_initial"] + o["uncovered_terminal"] == 1
        assert o["cleanup_unchanged"] and not o["active"] and len(o["P"]) == 21
        assert not o["priors"]
        no_measurements(o)
        row = o["lifecycle"][0]
        if op == "initial":
            assert row["status"] == "UNCOVERED_INITIAL_STATE"
            assert row["start_state_time"] is None and row["owner"] == "NONE"
            assert not row["clone_created"] and row["start_dispatch_phase"] == "NOT_DISPATCHED"
        else:
            assert row["status"] == "UNCOVERED_TERMINAL" and row["owner"] == "ARC"
            assert row["clone_created"] and row["end_state_time"] is None
            assert row["end_dispatch_phase"] == "NOT_DISPATCHED"
        if op == "missing_end":
            assert row["end_time"] is None
    for op, reason in (("duplicate", "EXACT_TIME_ORDER_OR_BITS"),
                       ("unordered", "END_WITHOUT_MATCHING_START"),
                       ("mismatch", "END_WITHOUT_MATCHING_START"),
                       ("overlap", "OVERLAPPING_BLOCKS")):
        assert reason in call(op, fail=True)


def test_08_production_mutual_exclusion_reset_and_covariance_guards(tmp_path):
    o = call("guards")
    assert o["foot_arc_rejected"] == "ARC_AND_FOOT_CLONE_MODES_ARE_EXCLUSIVE"
    assert o["qa_rejected"] == o["qm_rejected"] == "ATTITUDE_CLONE_REQUIRES_FULL_UNCLIPPED_FEEDBACK_QA_QM_OFF"
    assert o["current_covariance_rejected"] and o["clipped_feedback_rejected"]
    p = a(o, "frozen_joint_P")
    assert p.shape == (24, 24)
    np.testing.assert_array_equal(p[15:21], np.zeros((6, 24)))
    np.testing.assert_array_equal(p[:, 15:21], np.zeros((24, 6)))
    np.testing.assert_array_equal(o["scale"], np.zeros(3))
    legacy = call("off", path=tmp_path / "never_created")
    assert legacy["default_off"] and legacy["off_read_rejected"] and legacy["legacy_equal"]
    assert legacy["P_shape"] == 21 and not (tmp_path / "never_created").exists()
