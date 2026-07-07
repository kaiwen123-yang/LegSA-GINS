import numpy as np

from legsa_gins.da_repro.baseline_constraint import BaselineConstraint
from legsa_gins.da_repro.clambda_solver import solve_constrained_lambda
from legsa_gins.da_repro.lambda_solver import solve_integer_least_squares


def test_lambda_solver_fixes_nearest_integer():
    result = solve_integer_least_squares([1.05, -2.1], np.eye(2), search_radius=2)
    assert result.fixed == (1, -2)
    assert result.ratio is not None


def test_constrained_lambda_filters_by_baseline_length():
    constraint = BaselineConstraint(nominal_length_m=1.0, tolerance_m=0.2)

    def baseline(ints):
        return (float(ints[0]), 0.0, 0.0)

    result = solve_constrained_lambda([1.1], [[1.0]], baseline_from_integer=baseline, constraint=constraint)
    assert result.fixed == (1,)
    assert result.constraint_passed is True
