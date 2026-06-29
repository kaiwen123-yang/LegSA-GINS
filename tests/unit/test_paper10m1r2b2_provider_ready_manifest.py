from legsa_gins.degradation.m1r2b2_provider_regen import build_provider_ready


class _Paths:
    pass


def test_provider_ready_requires_effect_lineage_and_wrap_pass() -> None:
    old_status = [
        {
            "case_id": "case",
            "case_index": "0",
            "degradation_type_id": "CLEAN",
            "seed_index": "none",
            "provider_generation_status": "CLEAN_POINTER_READY",
            "effect_validation_status": "PASS",
        }
    ]
    effect = [{"case_id": "case", "effect_validation_status": "PASS"}]
    lineage = [{"case_id": "case", "yaw_lineage_validation_status": "PASS"}]
    wrap = [{"case_id": "case", "yaw_wrap_validation_status": "PASS"}]
    ready = build_provider_ready(_Paths(), old_status, effect, lineage, wrap)
    assert ready[0]["provider_ready"] == "true"
    assert ready[0]["rmse_selected_sign"] == "false"

