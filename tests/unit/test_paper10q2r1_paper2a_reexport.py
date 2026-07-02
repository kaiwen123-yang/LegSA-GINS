from pathlib import Path

from scripts.paper10q2r1_paper2a_reexport import (
    dataset_counts_from_secondary,
    method_classification_rows,
    required_files_check,
)


def test_dataset_counts_from_secondary_summary_text():
    rows = [{"evidence": "PAPER2A completed BY2 840/840, BY3 497/497, XB 560/560, total 1897 completed evaluable rows."}]
    assert dataset_counts_from_secondary(rows) == {"BY2": 840, "BY3": 497, "XB": 560}


def test_method_classification_is_policy_not_exact():
    rows = method_classification_rows({"BY2": 840, "BY3": 497, "XB": 560}, "COUNT_FROM_SUPERVISOR_ONLY_NOT_ROW_PROVEN")
    assert len(rows) == 7
    assert all(row["exact_reproduction"] == "false" for row in rows)
    assert all(row["policy_baseline"] == "true" for row in rows)
    assert all(row["appendix_candidate"] == "true" for row in rows)


def test_required_files_check_marks_secondary_only():
    checks = required_files_check({"PAPER2A_METHOD_RUNTIME_PROOF_TABLE.csv": Path("proof.csv")}, True)
    by_name = {row["required_file"]: row for row in checks}
    assert by_name["PAPER2A_METHOD_RUNTIME_PROOF_TABLE.csv"]["status"] == "FOUND_DIRECT"
    assert by_name["PAPER2A_ROW_LEVEL_MASTER_TABLE.csv"]["status"] == "SECONDARY_SUMMARY_ONLY"
