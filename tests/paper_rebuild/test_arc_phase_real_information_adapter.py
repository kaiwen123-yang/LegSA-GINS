"""Three frozen synthetic adapter cases; no real files or residual/information calls."""
import copy
import hashlib
from pathlib import Path
import struct
import sys

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts/paper_rebuild/carrier_phase"))
import arc_phase_real_information as adapter

A = 6378137.0
E2 = 0.0066943799901413156
RM_EQUATOR = A * (1.0 - E2)
E_EQUATOR = np.array([[0., 0., -1.], [0., 1., 0.], [1., 0., 0.]])


def synthetic_prior():
    # Analytic equator oracle, independent of adapter.frame_jacobian.
    j = np.zeros((3, 21))
    j[1, 0] = 1.0 / RM_EQUATOR
    j[2, 1] = -1.0 / A
    j[:, 6:9] = E_EQUATOR
    b = np.zeros((6, 24))
    b[:3, 21:] = np.eye(3)
    b[3:, :21] = j
    std = [1000., 2000., 3000., 1., 2., 3., .1, .2, .3,
           .01, .02, .03, .1, .2, .3, .0001, .0002, .0003,
           .0001, .0002, .0003, .4, .5, .6]
    latent = np.diag(std)
    latent[6, 0] = .04
    latent[7, 1] = -.03
    latent[21, 0] = .06
    latent[21, 7] = .09
    latent[22, 1] = -.07
    latent[22, 8] = .05
    latent[23, 6] = -.08
    p24 = latent @ latent.T
    # Direct analytic error components:
    # clone xyz, current ECEF=(-phi_D, phi_E+pos_N/RM, phi_N-pos_E/A).
    projected_latent = np.vstack((
        latent[21], latent[22], latent[23], -latent[8],
        latent[7] + latent[0] / RM_EQUATOR,
        latent[6] - latent[1] / A))
    expected_p6 = projected_latent @ projected_latent.T
    cbn = np.array([[0., -1., 0.], [1., 0., 0.], [0., 0., 1.]])
    expected_c1 = np.array([[0., 0., -1.], [1., 0., 0.], [0., -1., 0.]])
    corrected_c0 = np.array([[0., 0., 1.], [0., 1., 0.], [-1., 0., 0.]])
    prior = dict(P24=p24.tolist(), P6=expected_p6.tolist(), dx24=[0.] * 24,
                 current_blh=[0., 0., 0.], J1=j.tolist(), B6=b.tolist(),
                 current_cbn=cbn.tolist(), current_C1=expected_c1.tolist(),
                 clone_C0_given_end=corrected_c0.tolist(), start_C0=np.eye(3).tolist())
    return prior, j, b, expected_p6, corrected_c0, expected_c1


def binary64(value):
    return struct.pack(">d", value).hex()


def join_fixture():
    sid = "SYNTHETIC"
    bid = sid + ":BLOCK:0"
    spec = dict(sequence_id=sid, blocks=1, priors=1, legal_models=1,
                legal_intersection=1, run_id=sid + "__ARC_EMPTY_MODEL",
                event_sha256="e" * 64, manifest_sha256="f" * 64)
    events = []
    endpoints = []
    for role, index, time, fp in (("START", 0, .2, "a" * 64), ("END", 4, 1., "b" * 64)):
        event = dict(schema_version="1", sequence_id=sid, block_id=bid,
                     endpoint_id=f"{sid}:EPOCH:{index}", role=role,
                     source_time_s=format(time, ".17g"),
                     replay_execution_time_s=format(time, ".17g"),
                     source_time_bits_hex=binary64(time), actual_available_time_s="",
                     availability_mode="SOURCE_TIME_REPLAY_ASSUMPTION",
                     epoch_index=str(index), endpoint_model_fingerprint=fp)
        events.append(event)
        endpoint = dict(event)
        endpoint.pop("schema_version")
        endpoint.update(source_time_s=time, replay_execution_time_s=time,
                        actual_available_time_s=None, epoch_index=index)
        endpoints.append(endpoint)
    life = dict(sequence_id=sid, block_id=bid, status="COVERED_END_PRIOR",
                clone_created="1", clone_owner_at_creation="ARC", planned_clone_owner="ARC",
                actual_available_time_s="", availability_mode="SOURCE_TIME_REPLAY_ASSUMPTION",
                dispatch_phase="POST_ALL_EXISTING_UPDATES_AT_TIMESTAMP",
                start_dispatch_phase="POST_ALL_EXISTING_UPDATES_AT_TIMESTAMP",
                end_dispatch_phase="POST_ALL_EXISTING_UPDATES_AT_TIMESTAMP",
                start_dispatch_ordinal="1", end_dispatch_ordinal="2",
                start_update_ordinal="1", start_reset_ordinal="1",
                end_update_ordinal="2", end_reset_ordinal="2")
    for prefix, event in zip(("start", "end"), events):
        for suffix, field in (("endpoint_id", "endpoint_id"), ("epoch_index", "epoch_index"),
                              ("source_time_bits_hex", "source_time_bits_hex"),
                              ("model_fingerprint", "endpoint_model_fingerprint")):
            life[prefix + "_" + suffix] = event[field]
        for suffix in ("source_time_s", "replay_execution_time_s", "state_time_s"):
            life[prefix + "_" + suffix] = event["source_time_s"]
    ledger = []
    # ARC source dispatch ordinal != conditioning ledger ordinal:
    # ordinary/reset precede START, so START is dispatch 1 but ledger 3.
    for ordinal, (kind, time, u, reset, active) in enumerate((
            ("ORDINARY_UPDATE", .1, 1, 0, False),
            ("FULL_RESET", .1, 1, 1, False),
            ("ARC_START", .2, 1, 1, True),
            ("ORDINARY_UPDATE", .6, 2, 1, True),
            ("FULL_RESET", .6, 2, 2, True),
            ("ARC_END", 1., 2, 2, True)), 1):
        ledger.append(dict(ordinal=ordinal, kind=kind, state_time_s=time,
                           state_time_bits_hex=binary64(time), update_ordinal=u,
                           reset_ordinal=reset, clone_owner="ARC" if active else "NONE",
                           block_id=bid if active else "", source_tag="SYNTHETIC",
                           provider_measurement_identity="SYNTHETIC_ONLY",
                           actual_available_time_s=None, phase_state_cross="UNKNOWN"))
    prior = dict(schema_version=1, start=endpoints[0], end=endpoints[1],
                 start_state_time_s=.2, end_state_time_s=1.,
                 start_update_ordinal=1, end_update_ordinal=2,
                 start_reset_ordinal=1, end_reset_ordinal=2, conditioning_ordinal=5,
                 run_id=spec["run_id"], arc_source_events_sha256=spec["event_sha256"],
                 arc_schedule_manifest_sha256=spec["manifest_sha256"],
                 source_time_scale_id="UTC_UNIX_MINUS_REGISTERED_BASE_SECONDS",
                 source_time_mapping_id=sid + ":SEALED_RAWX_UTC_AND_CALIBRATED_IMU_BASE_V1",
                 pin_validation="DECLARED_PINS_EXTERNAL_RUNNER_VERIFICATION_REQUIRED",
                 config_binary_provider_hash_binding="EXTERNAL_SEALED_RUN_RECEIPT_REQUIRED",
                 dispatch_phase="POST_ALL_EXISTING_UPDATES_AT_TIMESTAMP",
                 actual_available_time_s=None, phase_state_cross="UNKNOWN",
                 error_order="current21_P_V_PHI_BG_BA_SG_SA_then_ECEF_clone3",
                 error_units="m_mps_rad_radps_mps2_dimensionless_dimensionless_rad",
                 error_convention="position_velocity_estimate_minus_true_attitude_and_clone_positive_left_truth_from_nominal_bias_scale_true_minus_nominal",
                 prior_scope="INHERITED_WORKING_MODEL_CONDITIONAL_ON_EXECUTED_PREFIX_NOT_CALIBRATED_TRUTH")
    prior["conditioning_information_id"] = (
        spec["run_id"] + ":" + spec["event_sha256"] + ":" + spec["manifest_sha256"]
        + ":U2:R2:L5:T" + binary64(1.))
    detail = dict(row=dict(sequence=sid, block_index=0, first_epoch_index=0,
                           last_epoch_index=4, start_s=.2, end_s=1.,
                           actual_available_time_s=None, navigation_admitted=False,
                           cross_time_covariance_known=False,
                           status="LEGAL_SAME_ARC_CONTRAST", endpoint_models_available=True),
                  epoch0_fingerprint="a" * 64, epoch1_fingerprint="b" * 64)
    native = dict(lifecycle_status_counts={"COVERED_END_PRIOR": 1})
    return spec, events, [life], [prior], [detail], ledger, native


def test_01_equator_full_cross_prior_uses_end_frame():
    prior, expected_j, expected_b, expected_p6, c0, c1 = synthetic_prior()
    before = copy.deepcopy(prior)
    cne, j = adapter.frame_jacobian([0., 0., 0.])
    np.testing.assert_array_equal(cne, E_EQUATOR)
    np.testing.assert_allclose(j, expected_j, rtol=2e-15, atol=0.)
    p6, out_c0, out_c1, diagnostics = adapter.qualify_prior(prior)
    np.testing.assert_array_equal(p6, expected_p6)
    np.testing.assert_array_equal(out_c0, c0)
    np.testing.assert_array_equal(out_c1, c1)
    assert not np.array_equal(out_c0, prior["start_C0"])
    assert diagnostics["P6_mapping_error"] <= 2e-10
    assert diagnostics["P24"]["repaired"] is False
    assert diagnostics["P6"]["repaired"] is False
    assert prior == before
    without_position = expected_b.copy()
    without_position[3:, :3] = 0.
    wrong = without_position @ np.asarray(prior["P24"]) @ without_position.T
    assert not np.allclose(wrong, expected_p6, rtol=1e-9, atol=1e-14)


def test_02_bad_mapping_or_indefinite_prior_is_unresolved_without_repair():
    prior, *_ = synthetic_prior()
    bad_cases = []
    missing_j = copy.deepcopy(prior)
    missing_j["J1"][1][0] = 0.
    bad_cases.append((missing_j, "J1_ELEMENT_ERROR"))
    missing_b = copy.deepcopy(prior)
    missing_b["B6"][4][0] = 0.
    bad_cases.append((missing_b, "B6_ELEMENT_ERROR"))
    wrong_c1 = copy.deepcopy(prior)
    wrong_c1["current_C1"] = np.eye(3).tolist()
    bad_cases.append((wrong_c1, "C1_FRAME_MAPPING"))
    indefinite = copy.deepcopy(prior)
    indefinite["P24"][0][1] = indefinite["P24"][1][0] = 4e6
    bad_cases.append((indefinite, "FULL_P24_NUMERICAL_PSD"))
    for value, reason in bad_cases:
        before = copy.deepcopy(value)
        with pytest.raises(adapter.core.InformationError, match="UNRESOLVED_" + reason):
            adapter.qualify_prior(value)
        assert value == before


def test_03_exact_join_schema_and_hash_refuse_corruption(tmp_path):
    fixture = join_fixture()
    joined = adapter.join_sequence(*copy.deepcopy(fixture))
    assert len(joined) == 1 and joined[0][0] == "SYNTHETIC:BLOCK:0"
    bad = copy.deepcopy(fixture)
    bad[1][0]["schema_version"] = "2"
    with pytest.raises(ValueError, match="source identity"):
        adapter.join_sequence(*bad)
    bad = copy.deepcopy(fixture)
    bad[3][0]["start"]["source_time_s"] = np.nextafter(.2, np.inf)
    with pytest.raises(ValueError, match="endpoint exact double"):
        adapter.join_sequence(*bad)
    payload = b'{"synthetic_metadata":true}\n'
    path = tmp_path / "synthetic_metadata.json"
    path.write_bytes(payload)
    pin = dict(path=str(path), sha256=hashlib.sha256(payload).hexdigest(),
               size_bytes=len(payload))
    reg = dict(aliases={}, metadata_pins={"toy": pin}, input_pins={})
    inputs = adapter.Inputs(reg)
    assert inputs.json("toy") == {"synthetic_metadata": True}
    assert inputs.read("toy") == payload and len(inputs.receipts) == 1
    inputs.final_stat()
    # Invalid JSON plus a wrong hash must fail at the pre-decode SHA gate.
    bad_payload = b'not JSON'
    bad_path = tmp_path / "bad_synthetic_metadata.json"
    bad_path.write_bytes(bad_payload)
    bad_reg = dict(aliases={}, metadata_pins={"toy": dict(
        path=str(bad_path), size_bytes=len(bad_payload), sha256="0" * 64)}, input_pins={})
    with pytest.raises(ValueError, match="input SHA mismatch"):
        adapter.Inputs(bad_reg).json("toy")
