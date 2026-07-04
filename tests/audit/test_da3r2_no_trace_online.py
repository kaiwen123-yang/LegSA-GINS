from legsa_gins.da_repro.method_contracts import target_method_ids
from legsa_gins.da_repro.method_runner import matrix_queue


def test_da3r2_no_trace_online():
    assert all(row["trace_used_online"] == "false" for row in matrix_queue(target_method_ids()))
