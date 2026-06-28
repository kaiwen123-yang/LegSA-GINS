from tests.paper10m1r2b_common import read_csv


def test_trace_and_external_outputs_are_not_provider_inputs():
    rows = read_csv("05_PROVIDER_READY/PAPER10M1R2B_PROVIDER_READY_MANIFEST.csv")
    assert {row["trace_used"] for row in rows} == {"false"}
    assert {row["final_v23_output_used"] for row in rows} == {"false"}
    assert {row["legsa_output_used"] for row in rows} == {"false"}
