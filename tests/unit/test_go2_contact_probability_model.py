"""N7B4 contact probability 单元测试：概率不是 contact truth。"""

from legsa_gins.go2_prior.go2_contact_confidence_features import build_contact_confidence_features
from legsa_gins.go2_prior.go2_contact_probability_model import build_contact_probability_models

from .test_go2_contact_confidence_features import _rows


def test_contact_probability_model_selects_diagnostic_candidate():
    features, _ = build_contact_confidence_features(_rows())
    timeseries, report = build_contact_probability_models(features)
    assert timeseries
    assert report["selected_contact_probability_model"]
    assert report["contact_probability_model_ready"] is True
    assert report["trace_solver_input"] is False
