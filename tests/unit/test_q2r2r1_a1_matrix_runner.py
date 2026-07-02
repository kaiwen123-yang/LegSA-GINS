from legsa_gins.external_dual.matrix_runner import matrix_queue
from legsa_gins.external_dual.method_contracts import selected_methods


def test_a1_matrix_queue_has_minimum_360_rows_for_120_cases():
    cases = [{"case_id": f"case_{idx}", "case_family": "toy", "degradation_type_id": "D00"} for idx in range(120)]
    rows = matrix_queue(list(selected_methods()), cases)
    assert len(rows) == 360
    assert {row["trace_used_online"] for row in rows} == {"false"}
    assert {row["receiver_imu_as_body_imu"] for row in rows} == {"false"}
