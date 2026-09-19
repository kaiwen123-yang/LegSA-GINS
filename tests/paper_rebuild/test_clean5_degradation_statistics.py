"""P-07 inference boundaries and fixed-coverage external conversion."""
import numpy as np
import pandas as pd
import pytest

from legsa_gins.paper_rebuild.clean5_degradation.statistics import paired_statistics, strict_same_direction
from legsa_gins.paper_rebuild.clean5_degradation.evaluation import GINAV_COLUMNS, ginav_nav


SPEC = {'bootstrap': {'seed': 260910007, 'resamples': 10000}}


def test_constant_case_pairs_have_degenerate_interval_and_exact_signed_rank_probability():
    result = paired_statistics([-2.] * 6, SPEC)
    assert (result['median_delta'], result['ci95_low'], result['ci95_high']) == (-2., -2., -2.)
    assert result['n'] == 6 and result['win_rate'] == 1.
    assert result['wilcoxon_p'] == pytest.approx(.03125)


def test_ties_stay_in_win_rate_denominator_and_zero_handling():
    result = paired_statistics([-1., 0., 0., 1.], SPEC)
    assert result['n'] == 4 and result['win_rate'] == .25 and result['tie_count'] == 2
    zero = paired_statistics([0., 0., 0.], SPEC)
    assert zero['wilcoxon_p'] == 1. and zero['ci95_low'] == zero['ci95_high'] == 0.


def test_resampling_is_reproducible_and_does_not_mutate_pairs():
    values = np.array([-9., -2., 0., 1., 4., 20.])
    before = values.copy()
    first = paired_statistics(values, SPEC)
    assert first == paired_statistics(values, SPEC)
    assert np.array_equal(values, before)


@pytest.mark.parametrize('values', [[1., float('nan')], [float('inf')]])
def test_nonfinite_case_pairs_fail_instead_of_silent_deletion(values):
    with pytest.raises(ValueError, match='no silent case deletion'):
        paired_statistics(values, SPEC)


def test_strict_direction_requires_both_median_and_win_rate_side():
    ref = dict(status='AVAILABLE', median_delta=-1., win_rate=.7)
    assert strict_same_direction(ref, dict(ref, median_delta=-.001, win_rate=.51))
    for candidate in (dict(ref, median_delta=0.), dict(ref, median_delta=1.),
                      dict(ref, win_rate=.5), dict(ref, win_rate=.49), {'status': 'UNAVAILABLE'}):
        assert not strict_same_direction(ref, candidate)


def test_single_pair_has_bootstrap_but_no_signed_rank_claim():
    result = paired_statistics([-1.], SPEC)
    assert result['ci95_low'] == result['ci95_high'] == -1.
    assert result['wilcoxon_p'] is None and result['wilcoxon_status'] == 'UNAVAILABLE_N_LESS_THAN_2'


def test_ginav_conversion_preserves_frd_ned_and_only_crops_fixed_endpoints():
    source = np.arange(55., dtype=float).reshape(5, 11)
    source[:, 1] = [65., 66., 200., 340., 341.]
    frame = pd.DataFrame(source, columns=GINAV_COLUMNS)
    assert np.array_equal(ginav_nav(frame, [66., 340.]), source[1:4])
    assert np.array_equal(frame.to_numpy(), source)


def test_ginav_duplicate_epoch_fails_without_deduplication():
    source = np.ones((2, 11))
    with pytest.raises(ValueError, match='Invalid GINav'):
        ginav_nav(pd.DataFrame(source, columns=GINAV_COLUMNS), [66., 340.])
