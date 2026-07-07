from scripts.experiments.run_paper10_da3_da03_liu_cwls import _synthetic_cwls_rows


def test_da03_synthetic_validation_passes():
    _cases, rows, summary = _synthetic_cwls_rows()
    assert rows
    assert summary["synthetic_validation_pass"] is True
    assert summary["max_length_error_m"] < 0.02
    assert summary["max_noise_free_yaw_abs_error_deg"] < 1.0
    assert summary["wrap_179_minus179_pass"] is True
    assert summary["trace_used"] is False
