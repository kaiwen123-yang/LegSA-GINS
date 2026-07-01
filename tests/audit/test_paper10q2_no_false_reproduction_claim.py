from scripts.paper10q2_horizontal_reconciliation import build_method_rows


def test_no_false_exact_or_faithful_algorithm_promotion_from_registry_assets():
    rows = build_method_rows(
        {
            "da_registry": [
                {
                    "method_id": "DA01",
                    "method_name": "C-LAMBDA",
                    "literature_identity": "dual antenna attitude",
                    "fidelity": "proxy_or_reimplementation_evidence_only",
                    "forbidden_claim": "official exact reproduction",
                }
            ],
            "lc_registry": [
                {
                    "method_id": "LC01",
                    "method_name": "Chang",
                    "literature_identity": "loose coupling",
                    "fidelity": "paper-level reproduction/proxy",
                    "forbidden_claim": "official implementation unless source-proven",
                }
            ],
            "lse_registry": [],
            "paper4g_ledger": [],
            "paper4a_da": [],
            "paper10c_go2_rows": [],
        }
    )
    assert all(row["exact_reproduction"] == "false" for row in rows)
    assert not any(row["reproduction_type"] == "FAITHFUL_ALGORITHM_REPRODUCTION" for row in rows)
