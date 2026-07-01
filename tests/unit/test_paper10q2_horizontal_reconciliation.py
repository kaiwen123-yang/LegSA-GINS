from scripts.paper10q2_horizontal_reconciliation import build_method_rows


def test_build_method_rows_marks_no_exact_reproduction():
    rows = build_method_rows(
        {
            "da_registry": [
                {
                    "method_id": "DA01",
                    "method_name": "C-LAMBDA",
                    "literature_identity": "dual antenna",
                    "fidelity": "proxy",
                    "forbidden_claim": "official exact reproduction",
                }
            ],
            "lc_registry": [],
            "lse_registry": [],
            "paper4g_ledger": [],
            "paper4a_da": [],
            "paper10c_go2_rows": [],
        }
    )
    assert rows
    assert all(row["exact_reproduction"] == "false" for row in rows)
    assert any(row["method_id"] == "REG_DA01" for row in rows)


def test_qa_rows_require_reexport_before_paper_use():
    rows = build_method_rows({"da_registry": [], "lc_registry": [], "lse_registry": [], "paper4g_ledger": [], "paper4a_da": [], "paper10c_go2_rows": []})
    qa_rows = [row for row in rows if row["method_id"].startswith("PAPER2A_QA")]
    assert len(qa_rows) == 7
    assert all(row["reexport_required"] == "true" for row in qa_rows)
    assert all(row["reproduction_type"] == "PAPER_DERIVED_POLICY_BASELINE" for row in qa_rows)
