"""Physical integer/gauge counterexamples; no field correctness claims."""
import json
import numpy as np
import pytest

from legsa_gins.paper_rebuild.carrier_phase.admission import FrozenCandidate
from legsa_gins.paper_rebuild.carrier_phase.arc_relations import (
    SdArcNode, DdArcRelation, FrozenIntegerGraph, project_ensemble, full_rebase_matrix,
)
from legsa_gins.paper_rebuild.carrier_phase.temporal import TemporalModelError


def node(sv, arc="rx1:a|rx2:b", gnss=0, signal=0):
    return SdArcNode(f"{gnss}:{sv}:{signal}:0", arc)


def edge(a, b):
    return DdArcRelation(a, b).label


def candidate(items, name="one", active=None):
    return FrozenCandidate.from_mapping(name, 10., dict(items),
        tuple(label for label, _ in items) if active is None else tuple(active),
        "synthetic-known-integer-physical-arc-fixture")


def graph(items, name="one", active=None):
    return FrozenIntegerGraph.from_candidate(candidate(items, name, active))


@pytest.mark.parametrize("gnss,signal", [(0, 0), (2, 0), (3, 1)])
def test_pivot_loss_preserves_survivor_integer_difference(gnss, signal):
    p, a, b = [node(i, gnss=gnss, signal=signal) for i in (1, 2, 3)]
    old = graph([(edge(a, p), 7), (edge(b, p), -2)])
    new = old.advance([a, b], time_s=10.2)
    result = new.project([edge(a, b), edge(b, a)], time_s=10.2)
    assert [x.integer for x in result.relations] == [9, -9]
    assert not result.search_certificate_transferred
    assert not result.accepted_integer_measurement
    assert result.false_fix_probability is None
    assert old.nodes == tuple(sorted([p, a, b]))


@pytest.mark.parametrize("arc", ["rx1:new|rx2:b", "rx1:a|rx2:new"])
def test_either_receiver_new_arc_does_not_inherit(arc):
    p, a, b = node(1), node(2), node(3)
    new_a = node(2, arc=arc)
    new = graph([(edge(a, p), 7), (edge(b, p), -2)]).advance([p, new_a, b], time_s=11.)
    result = new.project([edge(new_a, p), edge(b, p)], time_s=11.)
    assert result.relations[0].integer is None
    assert result.relations[1].integer == -2


def test_retired_same_token_cannot_resurrect():
    p, a, b = node(1), node(2), node(3)
    old = graph([(edge(a, p), 7), (edge(b, p), -2)])
    lost = old.advance([p, b], time_s=11.)
    returned = lost.advance([p, a, b], time_s=12.)
    assert returned.project([edge(a, p)], time_s=12.).relations[0].integer is None
    assert returned.project([edge(b, p)], time_s=12.).relations[0].integer == -2


def test_full_interruption_never_repopulates_without_new_hypothesis():
    p, a = node(1), node(2)
    empty = graph([(edge(a, p), 7)]).advance([], time_s=11.)
    back = empty.advance([p, a], time_s=12.)
    assert back.nodes == ()
    assert back.project([edge(a, p)], time_s=12.).integer_items == ()


def test_disconnected_gauges_cannot_be_joined():
    a, b, c, d = [node(i) for i in range(1, 5)]
    g = graph([(edge(a, b), 2), (edge(c, d), 3)])
    r = g.project([edge(a, c)], time_s=10.)
    assert r.relations[0].status == "DISCONNECTED_INTEGER_GAUGES"


def test_cycle_consistency_and_sign():
    a, b, c = [node(i) for i in range(1, 4)]
    valid = [(edge(a, b), 2), (edge(b, c), -5), (edge(a, c), -3)]
    g = graph(valid)
    assert g.project([edge(c, a)], time_s=10.).relations[0].integer == 3
    with pytest.raises(TemporalModelError, match="cycle"):
        graph(valid[:-1] + [(edge(a, c), -2)])


def test_signature_is_pivot_order_and_integer_gauge_invariant():
    a, b, c, d = [node(i) for i in range(1, 5)]
    # Absolute physical integers are [100,107,98,120]; only differences are known.
    first = graph([(edge(b, a), 7), (edge(c, a), -2), (edge(d, a), 20)])
    second = graph([(edge(a, c), 2), (edge(d, c), 22), (edge(b, c), 9)], "other")
    assert first.canonical_signature == second.canonical_signature
    assert first.origin_fingerprint != second.origin_fingerprint


def test_nuisance_integer_is_not_promoted_to_active_relation():
    a, b, c = [node(i) for i in range(1, 4)]
    g = graph([(edge(b, a), 7), (edge(c, a), -2)], active=[edge(b, a)])
    assert c not in g.nodes
    assert not g.project([edge(c, a)], time_s=10.).integer_items


def test_old_distinct_top_two_can_merge_after_projection():
    p, a, b, lost = [node(i) for i in range(1, 5)]
    one = graph([(edge(a, p), 7), (edge(b, p), -2), (edge(lost, p), 1)], "one")
    two = graph([(edge(a, p), 7), (edge(b, p), -2), (edge(lost, p), 2)], "two")
    ensemble = project_ensemble(
        [x.advance([a, b], time_s=11.) for x in (one, two)], [edge(a, b)], time_s=11.)
    assert len(ensemble.classes) == 1
    assert len(ensemble.classes[0].origin_fingerprints) == ensemble.origin_count == 2
    assert not ensemble.all_current_integer_alternatives_covered
    assert not ensemble.search_certificate_transferred
    assert not ensemble.accepted_integer_measurement


def test_distinct_projected_classes_are_not_accepted_or_complete():
    a, b = node(1), node(2)
    ensemble = project_ensemble(
        [graph([(edge(a, b), 1)], "one"), graph([(edge(a, b), 2)], "two")],
        [edge(a, b)], time_s=10.)
    assert len(ensemble.classes) == 2
    assert not ensemble.accepted_integer_measurement
    assert not ensemble.all_current_integer_alternatives_covered


def test_cross_frequency_or_constellation_relation_rejected():
    with pytest.raises(TemporalModelError, match="same exact group"):
        edge(node(2, signal=3), node(1))
    with pytest.raises(TemporalModelError, match="same exact group"):
        edge(node(2, gnss=2), node(1))


def test_duplicate_arc_versions_and_nonmonotonic_time_fail_before_mutation():
    a, b = node(1), node(2)
    g = graph([(edge(a, b), 2)])
    signature = g.canonical_signature
    for t in (10., 9., float("nan")):
        with pytest.raises(TemporalModelError):
            g.advance([a, b], time_s=t)
    with pytest.raises(TemporalModelError, match="different SD arcs"):
        g.advance([a, node(1, "new"), b], time_s=11.)
    with pytest.raises(TemporalModelError, match="current epoch"):
        g.project([edge(a, b)], time_s=11.)
    assert g.canonical_signature == signature


def test_large_derived_integer_is_not_silently_rounded():
    p, a, b = node(1), node(2), node(3)
    limit = 2**53 - 1
    g = graph([(edge(a, p), limit), (edge(b, p), -limit)])
    with pytest.raises(TemporalModelError, match="exact downstream"):
        g.project([edge(a, b)], time_s=10.)


def test_full_rebase_preserves_physical_dd_noise_and_raw_likelihood():
    nodes = [node(i) for i in range(1, 5)]
    old = [edge(x, nodes[0]) for x in nodes[1:]]
    new = [edge(nodes[i], nodes[2]) for i in (3, 0, 1)]
    transform = full_rebase_matrix(old, new)
    inverse = full_rebase_matrix(new, old)
    np.testing.assert_array_equal(transform @ inverse, np.eye(3, dtype=int))

    def incidence(labels):
        matrix = np.zeros((len(labels), len(nodes)))
        for row, label in enumerate(labels):
            relation = DdArcRelation.from_label(label)
            matrix[row, nodes.index(relation.target)] = 1
            matrix[row, nodes.index(relation.pivot)] = -1
        return matrix

    do, dn = incidence(old), incidence(new)
    np.testing.assert_array_equal(transform @ do, dn)
    sd_q = np.array([[4., .2, .1, -.1], [.2, 3., .4, .2],
                     [.1, .4, 2., .3], [-.1, .2, .3, 5.]])
    qo, qn = do @ sd_q @ do.T, dn @ sd_q @ dn.T
    np.testing.assert_allclose(transform @ qo @ transform.T, qn, atol=2e-14)
    sd_error = np.array([.03, -.02, .005, .08])
    ro, rn = do @ sd_error, dn @ sd_error
    assert ro @ np.linalg.solve(qo, ro) == pytest.approx(rn @ np.linalg.solve(qn, rn), abs=1e-14)
    sd_geometry = np.array([[.2,.1,.7], [.4,-.5,.6], [-.7,.2,.1], [.3,.8,-.4]])
    np.testing.assert_allclose(transform @ do @ sd_geometry, dn @ sd_geometry, atol=1e-14)
    true_n = np.array([100, 107, 98, 120])
    np.testing.assert_array_equal(transform @ do @ true_n, dn @ true_n)


def test_multi_group_full_rebase_does_not_mix_frequency_clocks():
    p, a, b = node(1), node(2), node(3)
    q, c = node(1, gnss=2), node(2, gnss=2)
    old = [edge(a, p), edge(b, p), edge(c, q)]
    new = [edge(q, c), edge(p, b), edge(a, b)]
    transform = full_rebase_matrix(old, new)
    np.testing.assert_array_equal(transform @ np.array([4, 9, -3]), [3, -9, -5])
    np.testing.assert_array_equal(full_rebase_matrix(new, old) @ transform, np.eye(3, dtype=int))


def test_full_rebase_rejects_subset_new_arc_and_redundant_cycle():
    p, a, b = node(1), node(2), node(3)
    old = [edge(a, p), edge(b, p)]
    with pytest.raises(TemporalModelError):
        full_rebase_matrix(old, [edge(a, b)])
    with pytest.raises(TemporalModelError):
        full_rebase_matrix(old, [edge(a, node(1, "new")), edge(b, node(1, "new"))])
    loop = [*old, edge(a, b)]
    with pytest.raises(TemporalModelError, match="spanning forest"):
        full_rebase_matrix(loop, loop)


@pytest.mark.parametrize("label", ["bad", "[]", '["0:2:0:0","","0:1:0:0","a"]',
    '["0:2:3:0","a","0:1:0:0","a"]', '["00:2:0:0","a","0:1:0:0","a"]'])
def test_malformed_labels_fail_closed(label):
    with pytest.raises(TemporalModelError):
        DdArcRelation.from_label(label)


def test_semantic_duplicate_request_and_origin_rejected():
    a, b = node(1), node(2)
    label = edge(a, b)
    g = graph([(label, 2)])
    differently_formatted = json.dumps(json.loads(label), indent=1)
    with pytest.raises(TemporalModelError, match="semantic requested"):
        g.project([label, differently_formatted], time_s=10.)
    with pytest.raises(TemporalModelError, match="distinct nonempty"):
        project_ensemble([g, g], [label], time_s=10.)


def test_advance_canonical_signature_reorders_components_after_root_loss():
    p, a, b, c, d = [node(i) for i in (1, 7, 8, 5, 6)]
    old = graph([(edge(a, p), 4), (edge(b, p), 7), (edge(d, c), -2)])
    projected = old.advance([a, b, c, d], time_s=11.)
    fresh = graph([(edge(b, a), 3), (edge(d, c), -2)])
    assert projected.canonical_signature == fresh.canonical_signature


def test_code_phase_two_frequency_likelihood_rebase_with_full_covariance():
    from legsa_gins.paper_rebuild.carrier_phase.multignss import signal_spec, raw
    a, b, c = [node(i) for i in (1, 2, 3)]
    d, e, f = [node(i, signal=3) for i in (1, 2, 3)]
    old = [edge(b, a), edge(c, a), edge(e, d), edge(f, d)]
    new = [edge(a, c), edge(b, c), edge(d, f), edge(e, f)]
    t = full_rebase_matrix(old, new)
    inv = full_rebase_matrix(new, old)
    u = np.kron(np.eye(2), t)
    waves = [signal_spec(raw.SignalIdentity(0, 1, sig, 0)).wavelength_m for sig in (0, 0, 3, 3)]
    design_n = np.vstack([np.zeros((4, 4)), np.diag(waves)])
    n = np.array([1, -3, 8, 2])
    h = np.array([[.2,.3,.1], [.5,-.3,.2], [.4,.2,-.6], [-.1,.7,.5]])
    design_b = np.vstack([h, h])
    baseline = np.array([.2, -.25, .14])
    noise = np.array([.1,-.2,.3,-.1,.002,-.003,.001,.004])
    observation = design_n @ n + design_b @ baseline + noise
    # Full Q includes code/phase and cross-frequency correlations.
    fct = np.diag([2., 3., 1., 4., .1, .2, .15, .12])
    fct[4, 0] = .01
    fct[6, 4] = .04
    fct[5, 1] = -.02
    q = fct @ fct.T
    anew = u @ design_n @ inv
    np.testing.assert_allclose(anew, design_n, atol=1e-15)
    res = u @ observation - anew @ (t @ n) - (u @ design_b) @ baseline
    np.testing.assert_allclose(res, u @ noise, atol=2e-15)
    assert noise @ np.linalg.solve(q, noise) == pytest.approx(
        res @ np.linalg.solve(u @ q @ u.T, res), rel=1e-12)
