from scripts.paper10q2_horizontal_reconciliation import GATE_DECISION, build_method_rows, counts_by_type


def test_gate_decision_combines_qa_reexport_and_dual_targeted_rerun():
    rows = build_method_rows(
        {
            "da_registry": [
                {
                    "method_id": "DA02",
                    "method_name": "Yang GPS/BDS KF",
                    "literature_identity": "dual antenna",
                    "fidelity": "paper-level method family proxy",
                    "forbidden_claim": "source-code official implementation",
                }
            ],
            "lc_registry": [],
            "lse_registry": [],
            "paper4g_ledger": [],
            "paper4a_da": [],
            "paper10c_go2_rows": [],
        }
    )
    assert GATE_DECISION == "TARGETED_RERUN_REQUIRED_DUAL_AND_QA"
    assert any(row["method_id"].startswith("PAPER2A_QA") and row["reexport_required"] == "true" for row in rows)
    assert any(row["method_id"] == "REG_DA02" and row["rerun_required"] == "true" for row in rows)
    assert counts_by_type(rows)["EXACT_REPRODUCTION"] == 0
