from copy import deepcopy
import math
import pytest
from acceptance import decide, ratio_gate


def cils(best=2., second=6.):
    return dict(valid=True, method="EXT01", search_complete=True,
                solver=dict(global_optimum_certified=True,
                            best=dict(ambiguity=[1, 2], objective=best),
                            second=dict(ambiguity=[1, 3], objective=second)))


def cwls(candidates=((1, 2.), (1, 2.), (2, 8.))):
    return dict(valid=True, method="EXT02", search_complete=True,
                solver=dict(candidate_count=len(candidates), integer_ambiguities=[1], objective=2.,
                            diagnostics=[dict(integer_ambiguities=[key], objective=cost,
                                              converged=True, integer_vector_stable=True,
                                              failure_code=None) for key, cost in candidates]))


@pytest.mark.parametrize("best,second,accepted", [(2., 6., True), (2., 5.999, False),
                                                  (2., 2., False), (2., 10., True)])
def test_ratio_orientation_and_exact_boundary(best, second, accepted):
    assert ratio_gate(best, second).accepted == accepted


@pytest.mark.parametrize("best,second,state", [(0., 6., "ZERO_BEST_COST"),
                                               (0., 0., "ZERO_BEST_COST"),
                                               (-1., 6., "INVALID_COST"),
                                               (2., math.inf, "INVALID_COST"),
                                               (math.nan, 6., "INVALID_COST"),
                                               (6., 2., "UNSORTED_COST")])
def test_degenerate_costs(best, second, state):
    d = ratio_gate(best, second)
    assert not d.accepted and d.acceptance_state == state


def test_duplicate_refinement_starts_are_not_second_integer_solution():
    d = decide(cwls())
    assert d.accepted and d.ratio == 4 and d.distinct_hypotheses == 2


def test_repeated_candidate_minimum_with_nonminimum_first_start():
    d = decide(cwls(((1, 10.), (1, 2.), (2, 8.))))
    assert d.accepted and d.ratio == 4


@pytest.mark.parametrize("record", [cils(), cwls()])
def test_never_salvages_native_failure_and_does_not_mutate(record):
    record["valid"] = False
    record["failure_code"] = "SEARCH_TIMEOUT"
    before = deepcopy(record)
    assert decide(record).acceptance_state == "NATIVE_INVALID"
    assert record == before


def test_incomplete_search_rejected_even_with_good_ratio():
    d = cils(); d["solver"]["global_optimum_certified"] = False
    assert decide(d).acceptance_state == "NO_GLOBAL_SEARCH_CERTIFICATE"


def test_missing_second_solution_rejected():
    d = cils(); d["solver"]["second"] = None
    assert decide(d).acceptance_state == "NO_SECOND_DISTINCT_HYPOTHESIS"
    assert decide(cwls(((1, 2.), (1, 2.)))).acceptance_state == "NO_SECOND_DISTINCT_HYPOTHESIS"


def test_cwls_failed_candidate_is_not_silently_deleted():
    d = cwls(); d["solver"]["diagnostics"][-1]["converged"] = False
    assert decide(d).acceptance_state == "INCOMPLETE_CANDIDATE_POOL"


def test_cwls_missing_saved_candidate_is_not_silently_deleted():
    d = cwls(); d["solver"]["diagnostics"].pop()
    assert decide(d).acceptance_state == "INCOMPLETE_CANDIDATE_POOL"


def test_reference_or_error_field_does_not_affect_acceptance():
    d = cwls(); before = decide(d)
    d.update(reference_heading=179, yaw_error=-150, v3_heading=0)
    assert decide(d) == before


def test_wrong_selected_solution_is_not_replaced():
    d = cwls(); d["solver"]["integer_ambiguities"] = [2]
    assert decide(d).acceptance_state == "SELECTED_SOLUTION_NOT_BEST"


def test_duplicate_clambda_best_second_rejected():
    d = cils(); d["solver"]["second"]["ambiguity"] = [1, 2]
    assert decide(d).acceptance_state == "DUPLICATE_INTEGER_HYPOTHESES"
