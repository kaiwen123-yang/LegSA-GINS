"""Partial selection contracts: geometry-only, full Q, exact arcs and classes."""
from dataclasses import replace
import json
from types import SimpleNamespace

import numpy as np
import pytest

from legsa_gins.paper_rebuild.carrier_phase import partial as part
from legsa_gins.paper_rebuild.carrier_phase.multignss import GroupDD, MultiGnssEpoch, SignalIdentity, signal_spec
from legsa_gins.paper_rebuild.carrier_phase.temporal import TemporalModelError, assemble_epochs
from legsa_gins.paper_rebuild.carrier_phase.admission import AdmissionConfig, CausalAdmissionSession

GROUPS = ((0, 0, 0), (0, 3, 0), (2, 0, 0))


def sid(identity):
    return ":".join(str(x) for x in (identity.gnss_id, identity.sv_id, identity.sig_id, identity.freq_id))


def epoch(k, *, reset_target=None, reset_pivot=None, flat=False):
    m = 9
    a = np.zeros((18, m))
    h = np.tile(np.eye(3), (3, 1))
    h[3:] += np.array([.05, -.02, .03])
    if flat:
        h[:, 2] = 0
    b = np.vstack((h, h))
    # Includes shared-pivot-like phase terms and code/phase/cross-frequency terms.
    scales = np.r_[np.ones(m)*.5, np.linspace(.003, .02, m)]
    corr = .6*np.eye(18)+.4*np.ones((18, 18))
    q = scales[:, None]*corr*scales[None, :]
    labels, descriptions = [], []
    for g, key in enumerate(GROUPS):
        pivot = SignalIdentity(key[0], 1, key[1], key[2])
        targets = tuple(SignalIdentity(key[0], j+2, key[1], key[2]) for j in range(3))
        first = 3*g
        columns = tuple(range(first, first+3))
        rows = columns+tuple(i+m for i in columns)
        pivot_token = "pivot-new" if reset_pivot == g and k >= 2 else "pivot-old"
        for j, target in enumerate(targets):
            token = "target-new" if reset_target == (g, j) and k >= 2 else "target-old"
            labels.append(json.dumps([sid(target), token, sid(pivot), pivot_token], separators=(",", ":")))
            a[first+j+m, first+j] = signal_spec(target).wavelength_m
        descriptions.append((key, pivot, targets, rows, columns))
    n = np.arange(m)+42
    y = a@n+b@np.array([.21, -.14, .28])
    groups = tuple(GroupDD(key, pivot, targets, y[list(rows)], a[np.ix_(rows, columns)],
                          b[list(rows)], q[np.ix_(rows, rows)],
                          tuple(labels[i] for i in columns), rows, columns)
                   for key, pivot, targets, rows, columns in descriptions)
    return MultiGnssEpoch(100.+.2*k, y, a, b, q, tuple(labels), groups,
                          {"arc_label_policy": "EXPLICIT_SD_ARCS", "baseline_frame": "ECEF"})


def models(**kwargs):
    return tuple(epoch(k, **kwargs) for k in range(5))


def fake_result(plan, *, scope="two_best_selected_integer_classes", same_class=False, certified=True):
    n = np.arange(plan.problem.ambiguity_count)+71
    alt = n.copy()
    if not same_class:
        alt[plan.problem.ambiguity_labels.index(plan.selection.selected_labels[0])] += 1
    else:
        nuisance = next(i for i, s in enumerate(plan.problem.ambiguity_labels)
                        if s not in plan.selection.selected_labels)
        alt[nuisance] += 1
    return SimpleNamespace(
        certificate=SimpleNamespace(global_optimum_certified=certified,
                                    certificate_scope=scope,
                                    distinct_ambiguity_labels=plan.selection.selected_labels,
                                    distinct_ambiguity_classes=2),
        best=SimpleNamespace(ambiguity=n), second=SimpleNamespace(ambiguity=alt))


def test_default_policy_and_selection_ignore_every_observation_value():
    original = models()
    a = part.preselect_partial_labels(original)
    # Even NaN y is not inspected by selection; prepare/solver validate y later.
    altered = tuple(replace(m, y=np.full_like(m.y, np.nan)) for m in original)
    assert part.preselect_partial_labels(altered) == a
    assert a.ready and len(a.selected_labels) == 8
    assert len(a.stable_labels) == 9 and not a.unstable_labels
    assert a.selected_at == pytest.approx(100.8)
    assert a.steps[-1].minimum_phase_rank == 3
    assert a.steps[-1].minimum_phase_rows == 8
    assert a.integer_success_probability is None
    with pytest.raises(TemporalModelError):
        part.prepare_partial_search(altered, length_m=.35)


def test_full_correlated_Q_information_matches_dense_oracle():
    ms = models()
    selected = part.preselect_partial_labels(ms)
    chosen = []
    for step in selected.steps:
        chosen.append(step.added_label)
        values = []
        for model in ms:
            support = part.partial_support_rows(model, chosen)
            rows = list(support.rows_retained)
            x = model.B[rows]
            q = model.Q[np.ix_(rows, rows)]
            values.append(np.linalg.slogdet(x.T @ np.linalg.solve(q, x))[1])
        assert step.worst_epoch_logdet_information == pytest.approx(min(values), abs=1e-11)
    rows = list(part.partial_support_rows(ms[0], selected.selected_labels).rows_retained)
    q = ms[0].Q[np.ix_(rows, rows)]
    x = ms[0].B[rows]
    diagonal_score = np.linalg.slogdet(x.T @ np.linalg.solve(np.diag(np.diag(q)), x))[1]
    assert abs(selected.steps[-1].worst_epoch_logdet_information-diagonal_score) > .1


def test_reset_target_and_pivot_are_excluded_from_all_five_epoch_intersection():
    ms = models(reset_target=(0, 0), reset_pivot=2)
    selected = part.preselect_partial_labels(ms)
    assert selected.ready and len(selected.stable_labels) == 5
    assert len(selected.unstable_labels) == 8
    assert len(selected.selected_labels) == 5
    assert {key for key, _ in selected.selected_group_counts} == {(0, 0, 0), (0, 3, 0)}
    assert not any(json.loads(s)[0] == "0:2:0:0" for s in selected.selected_labels)


def test_phase_geometry_must_have_rank_three_at_every_selection_epoch():
    ms = list(models())
    ms[3] = epoch(3, flat=True)
    result = part.preselect_partial_labels(ms)
    assert not result.ready and result.status == "UNAVAILABLE_PHASE_GEOMETRY"
    assert result.steps[-1].minimum_phase_rank == 2


def test_minimum_and_maximum_control_support_without_future_selection():
    result = part.preselect_partial_labels(models(), part.PartialPolicy(max_ambiguities=4))
    assert result.ready and len(result.selected_labels) == 4
    too_few = part.preselect_partial_labels(models(reset_pivot=0, reset_target=(1, 0)),
                                          part.PartialPolicy(min_ambiguities=6))
    assert too_few.status == "UNAVAILABLE_INSUFFICIENT_CONTINUOUS_ARCS"
    assert not too_few.selected_labels


@pytest.mark.parametrize("change", [
    {"selection_epochs": 0}, {"min_ambiguities": True}, {"max_ambiguities": 3},
    {"epoch_interval_s": 0}, {"time_tolerance_s": .1},
])
def test_policy_rejects_invalid_counts_and_time_slots(change):
    with pytest.raises(TemporalModelError):
        part.PartialPolicy(**change)


def test_exact_window_required_and_missing_or_reordered_slots_rejected():
    with pytest.raises(TemporalModelError, match="exactly"):
        part.preselect_partial_labels(models()[:4])
    ms = list(models())
    ms[2] = replace(ms[2], time_s=ms[2].time_s+.05)
    with pytest.raises(TemporalModelError, match="time slots"):
        part.preselect_partial_labels(ms)
    with pytest.raises(TemporalModelError, match="time slots"):
        part.preselect_partial_labels(tuple(reversed(models())))


def test_epoch_local_labels_and_wrong_group_identity_cannot_share_N():
    ms = list(models())
    ms[0] = replace(ms[0], metadata={"arc_label_policy": "EPOCH_LOCAL", "baseline_frame": "ECEF"})
    with pytest.raises(TemporalModelError, match="explicit SD"):
        part.preselect_partial_labels(ms)
    ms = list(models())
    g = replace(ms[0].groups[0], pivot=SignalIdentity(0, 1, 3, 0))
    ms[0] = replace(ms[0], groups=(g,)+ms[0].groups[1:])
    with pytest.raises(TemporalModelError, match="pivot group"):
        part.preselect_partial_labels(ms)


def test_wrong_wavelength_and_uncovered_group_rejected():
    ms = list(models())
    a = ms[0].A.copy()
    a[9, 0] *= 2
    ms[0] = replace(ms[0], A=a)
    with pytest.raises(TemporalModelError, match="wavelength"):
        part.preselect_partial_labels(ms)
    ms = list(models())
    ms[0] = replace(ms[0], groups=ms[0].groups[:-1])
    with pytest.raises(TemporalModelError, match="cover"):
        part.preselect_partial_labels(ms)


def test_search_wrapper_keeps_full_original_nuisance_problem(monkeypatch):
    ms = models(reset_target=(0, 0))
    plan = part.prepare_partial_search(ms, length_m=.37, policy=part.PartialPolicy(max_ambiguities=4))
    original = assemble_epochs(ms, length_m=.37)
    for name in ("y", "A", "B", "Q", "lengths"):
        np.testing.assert_array_equal(getattr(plan.problem, name), getattr(original, name))
    assert plan.problem.ambiguity_count == 10
    assert len(plan.selection.selected_labels) == 4
    expected = object()
    def mock_solver(problem, library, **kwargs):
        assert problem is plan.problem
        assert library == "unit-test-library"
        assert kwargs["distinct_ambiguity_labels"] == plan.selection.selected_labels
        assert kwargs["node_limit"] == 123
        assert problem.A.shape[1] == 10  # nuisance N neither dropped nor set to zero
        return expected
    monkeypatch.setattr(part, "solve_temporal", mock_solver)
    assert part.solve_partial(plan, "unit-test-library", node_limit=123) is expected
    unavailable = part.prepare_partial_search(models(flat=True), length_m=.37)
    with pytest.raises(TemporalModelError, match="unavailable"):
        part.solve_partial(unavailable, "unit-test-library")


def test_freeze_exposes_only_selected_integers_and_distinct_classes():
    plan = part.prepare_partial_search(models(), length_m=.35)
    result = fake_result(plan)
    primary, competitor = part.freeze_partial_candidates(plan, result, source_id="synthetic-test")
    assert set(primary.integers) == set(plan.selection.selected_labels)
    assert primary.active_labels == plan.selection.selected_labels
    assert len(primary.integers) == 8 < plan.problem.ambiguity_count
    assert primary.integers != competitor.integers
    assert primary.selected_at == pytest.approx(100.8)
    assert all(n >= 71 for n in primary.integers.values())


@pytest.mark.parametrize("kwargs", [
    {"scope": "two_best_full_integer_vectors"}, {"same_class": True}, {"certified": False},
])
def test_freeze_rejects_old_full_top_two_and_unproven_partial_classes(kwargs):
    plan = part.prepare_partial_search(models(), length_m=.35)
    with pytest.raises(TemporalModelError):
        part.freeze_partial_candidates(plan, fake_result(plan, **kwargs), source_id="test")


def test_freeze_rejects_other_subset_certificate_and_reduced_vector():
    plan = part.prepare_partial_search(models(), length_m=.35)
    result = fake_result(plan)
    result.certificate.distinct_ambiguity_labels = tuple(reversed(plan.selection.selected_labels))
    with pytest.raises(TemporalModelError, match="exact certified"):
        part.freeze_partial_candidates(plan, result, source_id="test")
    result = fake_result(plan)
    result.best.ambiguity = result.best.ambiguity[:8]
    with pytest.raises(TemporalModelError, match="complete nuisance"):
        part.freeze_partial_candidates(plan, result, source_id="test")


def test_future_projection_keeps_all_codes_full_principal_Q_and_blocks_new_arc():
    plan = part.prepare_partial_search(models(), length_m=.35,
                                       policy=part.PartialPolicy(max_ambiguities=4))
    fixed = plan.selection.selected_labels
    original = epoch(5)
    support = part.partial_support_rows(original, fixed)
    assert support.rows_retained[:9] == tuple(range(9))
    assert len(support.phase_rows_retained) == 4
    assert len(support.rows_withheld) == 5
    first = original.ambiguity_labels.index(fixed[0])
    group, target = divmod(first, 3)
    changed = epoch(5, reset_target=(group, target))
    new_support = part.partial_support_rows(changed, fixed)
    assert new_support.missing_selected_labels == (fixed[0],)
    assert first+9 in new_support.rows_withheld
    assert new_support.rows_retained[:9] == tuple(range(9))
    rows = list(new_support.rows_retained)
    q = changed.Q[np.ix_(rows, rows)]
    assert np.count_nonzero(q-np.diag(np.diag(q))) > 0
    assert len(new_support.phase_rows_retained) == 3


def test_existing_admission_does_not_inherit_subset_integer_across_new_arc():
    plan = part.prepare_partial_search(models(), length_m=.35,
                                       policy=part.PartialPolicy(max_ambiguities=4))
    primary, competitor = part.freeze_partial_candidates(plan, fake_result(plan), source_id="test")
    session = CausalAdmissionSession(primary, competitor,
                                    AdmissionConfig(validation_epochs=1, length_m=.35))
    index = epoch(5).ambiguity_labels.index(plan.selection.selected_labels[0])
    session.observe(epoch(5, reset_target=divmod(index, 3)))
    result = session.finalize()
    assert result.status == "UNRESOLVED_ACTIVE_ARC_CHANGED"
    assert not result.shadow_accepted
