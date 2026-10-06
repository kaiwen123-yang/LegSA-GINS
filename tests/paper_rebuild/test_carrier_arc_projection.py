"""Independent SD generative checks for rectangular DD observation transport."""
import numpy as np
import pytest
from legsa_gins.paper_rebuild.carrier_phase.arc_relations import SdArcNode, DdArcRelation, FrozenIntegerGraph
from legsa_gins.paper_rebuild.carrier_phase.arc_projection import transport_epoch
from legsa_gins.paper_rebuild.carrier_phase.admission import FrozenCandidate
from legsa_gins.paper_rebuild.carrier_phase.multignss import MultiGnssEpoch, GroupDD, raw, signal_spec
from legsa_gins.paper_rebuild.carrier_phase.temporal import TemporalModelError


def fixture():
    # Old pivot G01 is absent. New pivot G06 has an entirely unknown integer.
    current = [SdArcNode(f"0:{s}:0:0", "a") for s in (2, 3, 4, 5, 6)]
    oldpivot = SdArcNode("0:1:0:0", "a")
    labels = tuple(DdArcRelation(n, oldpivot).label for n in current[:4])
    old = FrozenCandidate.from_mapping("old", 10., dict(zip(labels, [2, -1, 5, 3])), labels, "known-synthetic")
    graph = FrozenIntegerGraph.from_candidate(old).advance(current, time_s=11.)
    wave = signal_spec(raw.SignalIdentity(0, 1, 0, 0)).wavelength_m
    d = np.c_[np.eye(4), -np.ones(4)]
    u = np.kron(np.eye(2), d)
    n_sd = np.array([12, 9, 15, 13, 99])
    geometry = np.array([[.2,.1,.7], [.4,-.5,.6], [-.7,.2,.1], [.3,.8,-.4], [-.4,-.4,.8]])
    b = np.array([.2, -.25, .14])
    noise = np.array([.02, -.04, .08, -.01, .03, .001, -.002, .004, -.001, .02])
    ysd = np.r_[geometry @ b, geometry @ b + wave*n_sd] + noise
    factor = np.diag([2.]*5 + [.01]*5)
    factor[7, 0] = .001
    factor[8, 6] = .004
    sd_q = factor @ factor.T
    y, bb, qq = u @ ysd, u @ np.vstack([geometry, geometry]), u @ sd_q @ u.T
    aa = np.vstack([np.zeros((4, 4)), wave*np.eye(4)])
    ddlabels = tuple(DdArcRelation(n, current[-1]).label for n in current[:4])
    pivot = raw.SignalIdentity(0, 6, 0, 0)
    satellites = tuple(raw.SignalIdentity(0, s, 0, 0) for s in (2, 3, 4, 5))
    group = GroupDD((0, 0, 0), pivot, satellites, y, aa, bb, qq, ddlabels, tuple(range(8)), tuple(range(4)))
    model = MultiGnssEpoch(11., y, aa, bb, qq, ddlabels, (group,), {
        "arc_label_policy":"EXPLICIT_SD_ARCS", "baseline_frame":"ECEF",
        "receiver_order":"GNSS2_MINUS_GNSS1", "dd_sign":"SATELLITE_MINUS_PIVOT"})
    return graph, model, current, (ysd, sd_q, geometry, n_sd, b, noise, u)


def test_unknown_new_pivot_cancels_and_full_covariance_matches_direct_sd():
    graph, model, nodes, values = fixture()
    ysd, qsd, geometry, nsd, baseline, noise, original_u = values
    view = transport_epoch(model, graph)
    assert view.phase_rows == view.phase_rank == 3
    dnew = np.array([[-1,1,0,0,0], [-1,0,1,0,0], [-1,0,0,1,0]], float)
    direct = np.zeros((7,10))
    direct[:4] = original_u[:4]
    direct[4:, 5:] = dnew
    np.testing.assert_allclose(view.model.y, direct @ ysd, atol=2e-15)
    np.testing.assert_allclose(view.model.B, direct @ np.vstack([geometry,geometry]), atol=2e-15)
    np.testing.assert_allclose(view.model.Q, direct @ qsd @ direct.T, atol=2e-15)
    integers = np.array([x[1] for x in view.relation_projection.integer_items])
    np.testing.assert_array_equal(integers, dnew @ nsd)
    residual = view.model.y-view.model.A@integers-view.model.B@baseline
    np.testing.assert_allclose(residual, direct @ noise, atol=3e-15)
    assert not view.search_certificate_transferred
    assert not view.accepted_integer_measurement
    assert not view.all_alternatives_covered


def test_one_survivor_cannot_create_phase_measurement():
    graph, model, nodes, _ = fixture()
    graph = graph.advance([nodes[0]], time_s=12.)
    from dataclasses import replace
    view = transport_epoch(replace(model, time_s=12.), graph)
    assert view.model is None
    assert view.phase_rows == 0
    assert view.status == "NO_IDENTIFIABLE_SURVIVING_PHASE"


def test_time_and_receiver_order_fail_closed():
    graph, model, _, _ = fixture()
    from dataclasses import replace
    with pytest.raises(TemporalModelError, match="times"):
        transport_epoch(replace(model,time_s=12.), graph)
    with pytest.raises(TemporalModelError, match="receiver order"):
        transport_epoch(replace(model,metadata={**model.metadata, "receiver_order":"REVERSED"}), graph)


def test_removing_target_retains_only_conditionally_known_relations():
    graph, model, nodes, _ = fixture()
    graph = graph.advance([nodes[0], nodes[2], nodes[3], nodes[4]], time_s=12.)
    from dataclasses import replace
    view = transport_epoch(replace(model,time_s=12.), graph)
    assert view.phase_rows == 2
    assert all("0:3:0:0" not in label for label in view.model.ambiguity_labels)
    assert view.model.Q.shape == (6,6)  # all four code rows still present
