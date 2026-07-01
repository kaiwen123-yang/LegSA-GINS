from scripts.paper10m1r2e_claim_boundary import forbidden_claim_markdown
from scripts.paper10m1r2e_result_review import module_review_rows


def test_forbidden_claims_are_explicitly_marked_forbidden():
    text = forbidden_claim_markdown().lower()
    for phrase in [
        "universal superiority",
        "final paper claim readiness",
        "by3 yaw generalization",
        "complete 9f fgo validation",
        "go2 joint effectiveness",
        "fgo feedback effectiveness",
    ]:
        assert phrase in text
        assert "do not" in text


def test_zero_delta_modules_get_forbidden_effective_wording():
    data = {
        "d_contrib": [
            {
                "removed_module": "go2_joint_factor",
                "case_count": "541",
                "median_delta_horizontal_rmse_m": "0",
                "module_help_count": "0",
                "module_hurt_count": "0",
                "same_order_count": "541",
                "metric_tradeoff_count": "0",
                "strong_help_family": "",
                "weak_help_family": "",
                "hurt_family": "",
                "notes": "",
            },
            {
                "removed_module": "fgo_feedback_or_ekf_only_alias",
                "case_count": "541",
                "median_delta_horizontal_rmse_m": "0",
                "module_help_count": "0",
                "module_hurt_count": "0",
                "same_order_count": "541",
                "metric_tradeoff_count": "0",
                "strong_help_family": "",
                "weak_help_family": "",
                "hurt_family": "",
                "notes": "",
            },
        ]
    }
    rows = module_review_rows(data)
    forbidden = " ".join(row["forbidden_wording_cn"] for row in rows)
    assert "Go2 joint" in forbidden
    assert "FGO feedback" in forbidden
    assert "已验证有效" in forbidden
