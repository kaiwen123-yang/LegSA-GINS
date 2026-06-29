from legsa_gins.evaluation.yaw_metric_repair import CORRECTED_SUFFIX


def test_corrected_metric_suffix_is_explicit():
    assert CORRECTED_SUFFIX == "corrected_evaluator_only"
