from legsa_gins.da_repro.dd_los_provider import BaselineEpoch
from legsa_gins.da_repro.method_contracts import TARGET_METHODS
from legsa_gins.da_repro.method_runner import run_method


def test_da3r2_methods_all_emit_full_backend_estimates():
    epochs = [
        BaselineEpoch(1.0, 1.0, 0.0, 0.0, 1, 8, 0.01, 0.01, 0.02, 4.0, 90.0, 0.0, "fixed"),
        BaselineEpoch(1.2, 0.9, 0.1, 0.0, 2, 8, 0.03, 0.03, 0.04, 2.0, 83.0, 353.0, "float"),
    ]
    for method in TARGET_METHODS:
        out = run_method(method.method_id, epochs, [])
        assert len(out) == len(epochs)
        assert out[0].valid is True
