from tests.paper10m1r2a_v2_common import read_csv


def test_case_manifest_trace_is_evaluation_only():
    rows = read_csv("04_CASE_MANIFEST/CANONICAL_BY2_DEGRADATION_CASE_MANIFEST.csv")
    assert {row["trace_eval_only"] for row in rows} == {"true"}
    assert {row["final_v23_output_solver_input_allowed"] for row in rows} == {"false"}
    assert {row["legsa_output_solver_input_allowed"] for row in rows} == {"false"}
    assert {row["go2_truth_claim_allowed"] for row in rows} == {"false"}


def test_queue_drafts_keep_trace_eval_only_and_locked_now():
    for rel in [
        "06_QUEUE_DRAFT/PAPER10M1R2B_PROVIDER_GENERATION_QUEUE_DRAFT.csv",
        "06_QUEUE_DRAFT/PAPER10M1R2C_FULL_ALGORITHM_QUEUE_DRAFT.csv",
        "06_QUEUE_DRAFT/PAPER10M1R2D_INTERNAL_ABLATION_QUEUE_DRAFT.csv",
    ]:
        rows = read_csv(rel)
        assert {row["trace_eval_only"] for row in rows} == {"true"}
        assert {row["run_allowed_now"] for row in rows} == {"false"}
